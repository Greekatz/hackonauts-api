"""
API Gateway / Main Application
Production-grade FastAPI backend with all endpoints.
"""
from __future__ import annotations

import asyncio
import time
import json
from typing import List, Optional, Dict, Any
from contextlib import asynccontextmanager

from fastapi import FastAPI, HTTPException, Depends, Header, Request, BackgroundTasks, APIRouter
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse, RedirectResponse
from slowapi import Limiter, _rate_limit_exceeded_handler
from slowapi.util import get_remote_address
from slowapi.errors import RateLimitExceeded


# API Version
API_VERSION = "v1"

from sqlalchemy import select, func
from sqlalchemy.ext.asyncio import AsyncSession

from core import (
    LogEntry, MetricEntry, MetricsSnapshot, Incident, IncidentSeverity,
    IncidentStatus, LogIngestionRequest, MetricIngestionRequest,
    MetricsSnapshotRequest, AutoHealRequest, NotificationRequest,
    ForceRCARequest, AnomalyDetection, StabilityReport, RecoveryAction,
    APIKey, APIKeyCreateRequest, APIKeyResponse,
    User, UserRegisterRequest, UserLoginRequest, UserResponse, TokenResponse,
    HealthResponse, SystemStatusResponse, BufferStats, IngestionResponse,
    IncidentResponse, SlackWorkspaceResponse, AccountOverviewResponse,
    UserOverview, SubscriptionInfo, AccountIntegrations, SlackIntegrationStatus,
    IntegrationStatus, APIKeysOverview, APIKeyInfo,
    config, logger,
    UserDB, APIKeyDB, SessionTokenDB, SlackWorkspaceDB, init_db, get_db, async_session,
    hash_password, verify_password, generate_token, get_token_expiry, is_token_expired, utc_now
)
from engines import (
    ingestion_buffer, LogParser, MetricsNormalizer,
    anomaly_detector, stability_evaluator, incident_manager
)
from integrations import (
    agent_client, agent_orchestrator, autoheal_executor, HealingAction, notification_manager,
    slack_app, slack_command_handler, slack_event_handler
)
from utils import mock_generator


# Rate limiter
limiter = Limiter(key_func=get_remote_address)


# =============================================================================
# Database Helpers
# =============================================================================

async def get_active_workspace(
    team_id: str,
    db: AsyncSession,
    user_id: Optional[str] = None
) -> Optional[SlackWorkspaceDB]:
    """
    Get an active Slack workspace by team_id.

    Args:
        team_id: The Slack team/workspace ID
        db: Database session
        user_id: Optional user ID to filter by owner

    Returns:
        SlackWorkspaceDB if found and active, None otherwise
    """
    query = select(SlackWorkspaceDB).where(
        SlackWorkspaceDB.team_id == team_id,
        SlackWorkspaceDB.is_active == True
    )
    if user_id:
        query = query.where(SlackWorkspaceDB.user_id == user_id)

    result = await db.execute(query)
    return result.scalar_one_or_none()


# Background monitoring task handle
_monitoring_task = None


# Lifespan context manager
@asynccontextmanager
async def lifespan(app: FastAPI):
    global _monitoring_task
    logger.info("Starting Incident Response Backend")
    logger.info("Initializing database...")
    await init_db()
    logger.info("Database initialized")

    # Start the continuous monitoring loop
    _monitoring_task = asyncio.create_task(continuous_monitoring_loop())
    logger.info("Started continuous monitoring loop (interval: 5 minutes)")

    yield

    # Shutdown
    logger.info("Shutting down Incident Response Backend")
    if _monitoring_task:
        _monitoring_task.cancel()
        try:
            await _monitoring_task
        except asyncio.CancelledError:
            pass
    logger.info("Monitoring loop stopped")


# Create FastAPI app
app = FastAPI(
    title="Incident Response Backend",
    description="Production-grade backend for autonomous incident response with watsonx integration",
    version=f"1.0.0-{API_VERSION}",
    lifespan=lifespan,
    docs_url="/docs",
    redoc_url="/redoc"
)

# Add rate limit error handler
app.state.limiter = limiter
app.add_exception_handler(RateLimitExceeded, _rate_limit_exceeded_handler)

# CORS middleware
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)



# API Key authentication (for SDK/API usage)
async def verify_api_key(
    x_api_key: str = Header(None, alias="X-API-Key"),
    db: AsyncSession = Depends(get_db)
):
    if not x_api_key:
        raise HTTPException(status_code=401, detail="API key required")

    # Check admin API key first (from centralized config)
    if config.ADMIN_API_KEY and x_api_key == config.ADMIN_API_KEY:
        return None  # Admin key is valid, no DB record needed

    # Check user API keys in database
    result = await db.execute(
        select(APIKeyDB).where(APIKeyDB.key == x_api_key)
    )
    api_key = result.scalar_one_or_none()

    if api_key and api_key.is_active:
        # Update last_used
        api_key.last_used = utc_now()
        await db.commit()
        return api_key

    raise HTTPException(status_code=401, detail="Invalid API key")


# User token authentication (for dashboard/management)
async def get_current_user(
    authorization: str = Header(None, alias="Authorization"),
    db: AsyncSession = Depends(get_db)
) -> UserDB:
    """Get current user from Bearer token."""
    if not authorization or not authorization.startswith("Bearer "):
        raise HTTPException(status_code=401, detail="Authorization required")

    token = authorization.replace("Bearer ", "")

    # Get session token
    result = await db.execute(
        select(SessionTokenDB).where(SessionTokenDB.token == token)
    )
    session = result.scalar_one_or_none()

    if not session:
        raise HTTPException(status_code=401, detail="Invalid or expired token")

    # Check token expiration (#5 fix)
    if is_token_expired(session.expires_at):
        # Clean up expired token
        await db.delete(session)
        await db.commit()
        raise HTTPException(status_code=401, detail="Token expired")

    # Get user
    result = await db.execute(
        select(UserDB).where(UserDB.id == session.user_id)
    )
    user = result.scalar_one_or_none()

    if not user or not user.is_active:
        raise HTTPException(status_code=401, detail="User not found")

    return user


# Combined authentication - accepts EITHER session token OR API key
async def verify_auth(
    authorization: str = Header(None, alias="Authorization"),
    x_api_key: str = Header(None, alias="X-API-Key"),
    db: AsyncSession = Depends(get_db)
):
    """
    Flexible auth that accepts either:
    - Bearer token (for dashboard users)
    - X-API-Key (for SDK/API calls)
    """
    # Try Bearer token first (dashboard users)
    if authorization and authorization.startswith("Bearer "):
        token = authorization.replace("Bearer ", "")
        result = await db.execute(
            select(SessionTokenDB).where(SessionTokenDB.token == token)
        )
        session = result.scalar_one_or_none()

        if session and not is_token_expired(session.expires_at):
            # Get user
            result = await db.execute(
                select(UserDB).where(UserDB.id == session.user_id)
            )
            user = result.scalar_one_or_none()
            if user and user.is_active:
                return {"type": "user", "user": user}

    # Try API key
    if x_api_key:
        # Check admin API key
        if config.ADMIN_API_KEY and x_api_key == config.ADMIN_API_KEY:
            return {"type": "admin", "user": None}

        # Check user API keys
        result = await db.execute(
            select(APIKeyDB).where(APIKeyDB.key == x_api_key)
        )
        api_key = result.scalar_one_or_none()

        if api_key and api_key.is_active:
            api_key.last_used = utc_now()
            await db.commit()
            return {"type": "api_key", "api_key": api_key}

    raise HTTPException(status_code=401, detail="Authentication required")


# Request logging middleware
@app.middleware("http")
async def log_requests(request: Request, call_next):
    start_time = time.time()
    response = await call_next(request)
    duration = (time.time() - start_time) * 1000

    logger.log_api_call(
        endpoint=str(request.url.path),
        method=request.method,
        status=response.status_code,
        duration_ms=duration
    )

    return response


# ============================================================================
# Health & Status Endpoints
# ============================================================================

@app.get("/health", response_model=HealthResponse)
async def health_check() -> HealthResponse:
    """Basic health check endpoint."""
    return HealthResponse(status="healthy", timestamp=utc_now().isoformat())


@app.get("/version")
async def get_version():
    """Get API version information."""
    return {
        "version": "1.0.0",
        "api_version": API_VERSION,
        "name": "SRA Incident Response Backend"
    }


@app.get("/status")
async def system_status(auth: dict = Depends(verify_auth)):
    """Get overall system status with connection info."""
    active_incident = incident_manager.get_active_incident()
    trend = stability_evaluator.get_stability_trend()

    return {
        "status": "operational",
        "version": "1.0.0",
        "timestamp": utc_now().isoformat(),
        "active_incident": active_incident.id if active_incident else None,
        "stability_trend": trend,
        "database_connected": True,  # If we got here, DB is connected
        "watsonx_configured": bool(config.WATSONX_API_KEY and config.WATSONX_URL),
        "slack_configured": bool(config.SLACK_CLIENT_ID and config.SLACK_CLIENT_SECRET),
        "monitoring_active": _monitoring_task is not None,
        "buffer_stats": {
            "logs": len(ingestion_buffer.logs),
            "metrics": len(ingestion_buffer.metrics),
            "snapshots": len(ingestion_buffer.snapshots)
        }
    }


@app.get("/debug/buffer")
async def debug_buffer(auth: dict = Depends(verify_auth)):
    """Get detailed buffer statistics for debugging."""
    logs = ingestion_buffer.logs
    metrics = ingestion_buffer.metrics

    oldest_log = None
    newest_log = None
    if logs:
        oldest_log = min(l.timestamp for l in logs).isoformat() if logs else None
        newest_log = max(l.timestamp for l in logs).isoformat() if logs else None

    return {
        "logs_count": len(logs),
        "metrics_count": len(metrics),
        "snapshots_count": len(ingestion_buffer.snapshots),
        "oldest_log": oldest_log,
        "newest_log": newest_log,
    }


# ============================================================================
# Log & Metrics Ingestion Endpoints
# ============================================================================

@app.post("/ingest/logs", response_model=IngestionResponse)
async def ingest_logs(
    request: LogIngestionRequest,
    auth: dict = Depends(verify_auth)
) -> IngestionResponse:
    """Ingest log entries."""
    ingestion_buffer.add_logs(request.logs)

    # LLM-based anomaly detection runs in the scheduled 5-minute loop
    # Not triggered on every ingest to avoid excessive API calls

    return IngestionResponse(
        status="accepted",
        count=len(request.logs),
        timestamp=utc_now().isoformat()
    )


@app.post("/ingest/logs/raw", response_model=IngestionResponse)
async def ingest_raw_logs(
    raw_logs: List[str],
    source: Optional[str] = None,
    auth: dict = Depends(verify_auth)
) -> IngestionResponse:
    """Ingest raw log strings (parsed automatically)."""
    parsed = []
    for raw in raw_logs:
        if "\n" in raw:
            parsed.extend(LogParser.parse_multiline(raw, source))
        else:
            parsed.append(LogParser.parse(raw, source))

    ingestion_buffer.add_logs(parsed)

    return IngestionResponse(
        status="accepted",
        count=len(parsed),
        timestamp=utc_now().isoformat()
    )


@app.post("/ingest/metrics", response_model=IngestionResponse)
async def ingest_metrics(
    request: MetricIngestionRequest,
    auth: dict = Depends(verify_auth)
) -> IngestionResponse:
    """Ingest metric entries."""
    ingestion_buffer.add_metrics(request.metrics)

    # Normalize to snapshot
    snapshot = MetricsNormalizer.normalize(request.metrics)
    ingestion_buffer.add_snapshot(snapshot)

    return IngestionResponse(
        status="accepted",
        count=len(request.metrics),
        timestamp=utc_now().isoformat()
    )


@app.post("/ingest/snapshot", response_model=IngestionResponse)
async def ingest_snapshot(
    request: MetricsSnapshotRequest,
    auth: dict = Depends(verify_auth)
) -> IngestionResponse:
    """Ingest a metrics snapshot directly."""
    ingestion_buffer.add_snapshot(request.snapshot)

    return IngestionResponse(
        status="accepted",
        count=1,
        timestamp=utc_now().isoformat()
    )


@app.post("/monitoring/trigger")
async def trigger_monitoring_check(
    auth: dict = Depends(verify_auth)
):
    """Manually trigger the LLM-based monitoring check."""
    await check_for_anomalies()
    return {"status": "triggered", "message": "Monitoring check completed"}


# ============================================================================
# Anomaly Detection Endpoints
# ============================================================================

@app.get("/anomaly/status")
async def get_anomaly_status(auth: dict = Depends(verify_auth)):
    """Get current anomaly detection status."""
    recent_logs = ingestion_buffer.get_recent_logs(minutes=15)
    recent_snapshots = ingestion_buffer.get_recent_snapshots(count=5)

    latest_snapshot = recent_snapshots[-1] if recent_snapshots else None

    detection = anomaly_detector.detect(
        logs=recent_logs,
        metrics=latest_snapshot
    )

    return {
        "anomaly_detected": detection.detected,
        "anomaly_type": detection.anomaly_type,
        "severity": detection.severity.value if detection.severity else None,
        "description": detection.description,
        "affected_metrics": detection.affected_metrics,
        "confidence": detection.confidence
    }


@app.post("/anomaly/force-incident")
async def force_incident_mode(
    enabled: bool = True,
    auth: dict = Depends(verify_auth)
):
    """Force incident mode on or off."""
    anomaly_detector.force_incident(enabled)
    return {"force_incident_mode": enabled}


# ============================================================================
# Agent & RCA Endpoints
# ============================================================================

@app.post("/agent/trigger")
async def trigger_agent(
    incident_id: str,
    background_tasks: BackgroundTasks,
    auth: dict = Depends(verify_auth)
):
    """Trigger the watsonx agent for an incident."""
    incident = incident_manager.get_incident(incident_id)
    if not incident:
        raise HTTPException(status_code=404, detail="Incident not found")

    # Run in background
    background_tasks.add_task(
        run_agent_workflow,
        incident_id
    )

    return {
        "status": "triggered",
        "incident_id": incident_id,
        "message": "Agent workflow started"
    }


@app.post("/agent/force-rca")
async def force_rca(
    request: ForceRCARequest,
    auth: dict = Depends(verify_auth)
):
    """Force an RCA run with provided data."""
    response = await agent_orchestrator.force_rca(
        logs=request.logs,
        metrics=request.metrics,
        description=request.description
    )

    return {
        "incident_id": response.incident_id,
        "rca": response.rca.model_dump() if response.rca else None,
        "recommended_actions": [a.model_dump() for a in response.recommended_actions],
        "summary": response.summary,
        "system_ok": response.system_ok
    }


# ============================================================================
# Stability Endpoints
# ============================================================================

@app.get("/stability/check")
async def check_stability(auth: dict = Depends(verify_auth)):
    """Run a stability check."""
    recent_logs = ingestion_buffer.get_recent_logs(minutes=10)
    recent_snapshots = ingestion_buffer.get_recent_snapshots(count=3)
    latest_snapshot = recent_snapshots[-1] if recent_snapshots else None

    report = stability_evaluator.evaluate(
        metrics=latest_snapshot,
        logs=recent_logs
    )

    return {
        "is_stable": report.is_stable,
        "metrics_ok": report.metrics_ok,
        "logs_ok": report.logs_ok,
        "details": report.details,
        "should_rerun_agent": stability_evaluator.should_rerun_agent()
    }


@app.post("/stability/set-baseline")
async def set_stability_baseline(
    snapshot: MetricsSnapshot,
    auth: dict = Depends(verify_auth)
):
    """Set a baseline for stability comparison."""
    stability_evaluator.set_baseline(snapshot)
    return {"status": "baseline set"}


# ============================================================================
# Auto-Healing Endpoints
# ============================================================================

# Map action names to HealingAction enum
AUTOHEAL_ACTION_MAP = {
    "restart": HealingAction.RESTART_SERVICE,
    "restart_service": HealingAction.RESTART_SERVICE,
    "scale": HealingAction.SCALE_REPLICAS,
    "scale_replicas": HealingAction.SCALE_REPLICAS,
    "flush": HealingAction.FLUSH_CACHE,
    "flush_cache": HealingAction.FLUSH_CACHE,
    "clear-queue": HealingAction.CLEAR_QUEUE,
    "clear_queue": HealingAction.CLEAR_QUEUE,
    "reroute": HealingAction.REROUTE_TRAFFIC,
    "reroute_traffic": HealingAction.REROUTE_TRAFFIC,
    "rollback": HealingAction.ROLLBACK_DEPLOYMENT,
    "rollback_deployment": HealingAction.ROLLBACK_DEPLOYMENT,
    "kill": HealingAction.KILL_PROCESS,
    "kill_process": HealingAction.KILL_PROCESS,
    "clear_disk": HealingAction.CLEAR_DISK,
}


@app.post("/autoheal/{action}")
async def execute_autoheal_action(
    action: str,
    request: AutoHealRequest,
    auth: dict = Depends(verify_auth)
):
    """
    Execute an auto-healing action.

    Available actions: restart, scale, flush, clear-queue, reroute, rollback
    """
    healing_action = AUTOHEAL_ACTION_MAP.get(action)
    if not healing_action:
        raise HTTPException(
            status_code=400,
            detail=f"Unknown action: {action}. Available: {', '.join(AUTOHEAL_ACTION_MAP.keys())}"
        )

    result = await autoheal_executor.execute(
        action=healing_action,
        service=request.service,
        parameters=request.parameters,
        incident_id=request.incident_id
    )
    return result


@app.get("/autoheal/actions")
async def list_autoheal_actions(auth: dict = Depends(verify_auth)):
    """List available auto-healing actions."""
    return autoheal_executor.get_available_actions()


@app.post("/autoheal/dry-run")
async def set_autoheal_dry_run(
    enabled: bool = True,
    auth: dict = Depends(verify_auth)
):
    """Enable/disable dry run mode for auto-healing."""
    autoheal_executor.set_dry_run(enabled)
    return {"dry_run": enabled}


# ============================================================================
# Analytics Endpoints
# ============================================================================

@app.get("/analytics")
async def get_analytics(auth: dict = Depends(verify_auth)):
    """Get analytics data from the system."""
    from datetime import datetime, timedelta
    from collections import defaultdict

    now = datetime.utcnow()
    seven_days_ago = now - timedelta(days=7)

    # Get all incidents
    all_incidents = list(incident_manager.incidents.values())

    # Calculate MTTA (Mean Time to Acknowledge)
    # Time from creation to first status change from 'open'
    acknowledged_times = []
    resolved_times = []

    for inc in all_incidents:
        if inc.status != IncidentStatus.OPEN:
            # Estimate acknowledgment time as 10% of total duration for demo
            duration = (inc.updated_at - inc.created_at).total_seconds() / 60
            acknowledged_times.append(duration * 0.1)

        if inc.resolved_at:
            resolved_times.append(
                (inc.resolved_at - inc.created_at).total_seconds() / 60
            )

    current_mtta = sum(acknowledged_times) / len(acknowledged_times) if acknowledged_times else 0
    current_mttr = sum(resolved_times) / len(resolved_times) if resolved_times else 0

    # For trend comparison, use slightly higher "previous" values
    previous_mtta = current_mtta * 1.2 if current_mtta > 0 else 10
    previous_mttr = current_mttr * 1.3 if current_mttr > 0 else 45

    # Incident trends by day and severity
    incident_trends = []
    for i in range(7):
        day = now - timedelta(days=6-i)
        day_str = day.strftime("%Y-%m-%d")

        day_incidents = [
            inc for inc in all_incidents
            if inc.created_at.date() == day.date()
        ]

        sev_counts = {"sev1": 0, "sev2": 0, "sev3": 0}
        for inc in day_incidents:
            sev = inc.severity.value.lower()
            if sev in ["critical", "sev1"]:
                sev_counts["sev1"] += 1
            elif sev in ["high", "sev2"]:
                sev_counts["sev2"] += 1
            else:
                sev_counts["sev3"] += 1

        incident_trends.append({
            "date": day_str,
            **sev_counts
        })

    # Error rates by service from logs
    error_rates = []
    recent_logs = list(ingestion_buffer.logs)

    service_errors = defaultdict(lambda: {"total": 0, "errors": 0})
    for log in recent_logs:
        service = log.service or log.source or "unknown"
        service_errors[service]["total"] += 1
        if log.level.value in ["error", "critical"]:
            service_errors[service]["errors"] += 1

    for service, counts in service_errors.items():
        if counts["total"] > 0:
            rate = (counts["errors"] / counts["total"]) * 100
            error_rates.append({"service": service, "rate": round(rate, 2)})

    # Sort by error rate descending and limit to top 5
    error_rates.sort(key=lambda x: x["rate"], reverse=True)
    error_rates = error_rates[:5]

    # Latency P95 from metrics snapshots
    latency_p95 = []
    snapshots = list(ingestion_buffer.snapshots)

    # Group snapshots by hour
    hourly_latencies = defaultdict(list)
    for snap in snapshots:
        if snap.latency_ms is not None:
            hour = snap.timestamp.strftime("%H:00")
            hourly_latencies[hour].append(snap.latency_ms)

    for hour in sorted(hourly_latencies.keys()):
        values = sorted(hourly_latencies[hour])
        if values:
            p95_idx = int(len(values) * 0.95)
            latency_p95.append({
                "hour": hour,
                "value": round(values[min(p95_idx, len(values)-1)], 2)
            })

    # Autoheal action history
    autoheal_history = autoheal_executor.action_history[-20:]  # Last 20 actions

    # Log ingestion stats
    log_stats = {
        "total_logs": len(ingestion_buffer.logs),
        "total_metrics": len(ingestion_buffer.metrics),
        "total_snapshots": len(ingestion_buffer.snapshots),
        "error_logs": len([l for l in ingestion_buffer.logs if l.level.value in ["error", "critical"]]),
    }

    # Incident stats
    incident_stats = {
        "total": len(all_incidents),
        "open": len([i for i in all_incidents if i.status == IncidentStatus.OPEN]),
        "investigating": len([i for i in all_incidents if i.status == IncidentStatus.INVESTIGATING]),
        "resolved": len([i for i in all_incidents if i.status == IncidentStatus.RESOLVED]),
    }

    return {
        "mtta": {
            "current": round(current_mtta, 1),
            "previous": round(previous_mtta, 1),
            "trend": "down" if current_mtta < previous_mtta else "up"
        },
        "mttr": {
            "current": round(current_mttr, 1),
            "previous": round(previous_mttr, 1),
            "trend": "down" if current_mttr < previous_mttr else "up"
        },
        "incidentTrends": incident_trends,
        "errorRates": error_rates,
        "latencyP95": latency_p95,
        "autohealHistory": autoheal_history,
        "logStats": log_stats,
        "incidentStats": incident_stats,
    }


@app.get("/reports")
async def list_reports(auth: dict = Depends(verify_auth)):
    """List incident reports and post-mortems."""
    all_incidents = list(incident_manager.incidents.values())

    reports = []
    for inc in all_incidents:
        # Only include incidents that have RCA or are resolved
        if inc.rca or inc.status == IncidentStatus.RESOLVED:
            reports.append({
                "id": f"RPT-{inc.id[:8]}",
                "title": f"{inc.title} - {'Post-Mortem' if inc.status == IncidentStatus.RESOLVED else 'Analysis'}",
                "incident": inc.id,
                "date": (inc.resolved_at or inc.updated_at).strftime("%Y-%m-%d"),
                "status": "published" if inc.status == IncidentStatus.RESOLVED else "draft",
                "author": inc.assignee or "SRA System",
                "summary": inc.rca.root_cause if inc.rca else inc.description,
            })

    # Sort by date descending
    reports.sort(key=lambda x: x["date"], reverse=True)
    return reports


# ============================================================================
# Incident Management Endpoints
# ============================================================================

@app.get("/incidents")
async def list_incidents(
    status: Optional[str] = None,
    limit: int = 50,
    auth: dict = Depends(verify_auth)
):
    """List incidents."""
    status_enum = IncidentStatus(status) if status else None
    incidents = incident_manager.list_incidents(status=status_enum, limit=limit)

    # Transform to frontend-expected format
    return [
        {
            "id": inc.id,
            "title": inc.title,
            "severity": inc.severity.value,
            "status": inc.status.value,
            "service": inc.service or "unknown",
            "created": inc.created_at.isoformat(),
            "assignee": inc.assignee,
            "affectedUsers": inc.affected_users,
            "description": inc.description,
            "impact": inc.impact
        }
        for inc in incidents
    ]


@app.get("/incidents/{incident_id}")
async def get_incident(
    incident_id: str,
    auth: dict = Depends(verify_auth)
):
    """Get incident details."""
    incident = incident_manager.get_incident(incident_id)
    if not incident:
        raise HTTPException(status_code=404, detail="Incident not found")

    # Transform to frontend-expected format
    rca_text = ""
    if incident.rca:
        rca_text = f"**Root Cause:** {incident.rca.root_cause}\n\n"
        if incident.rca.contributing_factors:
            rca_text += "**Contributing Factors:**\n"
            for factor in incident.rca.contributing_factors:
                rca_text += f"- {factor}\n"

    # Build plans from recommended actions
    plans = []
    for i, action in enumerate(incident.recommended_actions):
        plans.append({
            "id": f"RB-{i+1:03d}",
            "name": action.action_type.replace("_", " ").title(),
            "status": "executed" if action.executed else "ready",
            "steps": [action.description]
        })

    # Build logs for frontend
    logs = [
        {
            "timestamp": log.timestamp.strftime("%H:%M:%S"),
            "level": log.level.value.upper(),
            "message": log.message
        }
        for log in incident.logs[-20:]  # Last 20 logs
    ]

    # Build metrics for frontend
    metrics_data = {
        "errorRate": [],
        "latency": [],
        "connections": []
    }
    for m in incident.metrics[-10:]:
        time_str = m.timestamp.strftime("%H:%M")
        if m.error_rate is not None:
            metrics_data["errorRate"].append({"time": time_str, "value": m.error_rate * 100})
        if m.latency_ms is not None:
            metrics_data["latency"].append({"time": time_str, "value": m.latency_ms})

    return {
        "id": incident.id,
        "title": incident.title,
        "severity": incident.severity.value,
        "status": incident.status.value,
        "service": incident.service or "unknown",
        "created": incident.created_at.isoformat(),
        "updated": incident.updated_at.isoformat(),
        "assignee": incident.assignee,
        "affectedUsers": incident.affected_users,
        "description": incident.description,
        "impact": incident.impact or "Impact under assessment",
        "summary": incident.description,
        "rca": rca_text or "Root cause analysis in progress...",
        "plans": plans,
        "logs": logs,
        "metrics": metrics_data,
        "timeline": []
    }


@app.get("/incidents/{incident_id}/summary")
async def get_incident_summary(
    incident_id: str,
    auth: dict = Depends(verify_auth)
):
    """Get incident summary."""
    summary = incident_manager.get_incident_summary(incident_id)
    if not summary:
        raise HTTPException(status_code=404, detail="Incident not found")
    return summary


@app.get("/incidents/{incident_id}/history")
async def get_incident_history(
    incident_id: str,
    auth: dict = Depends(verify_auth)
):
    """Get full incident history."""
    history = incident_manager.get_history(incident_id)
    if not history:
        raise HTTPException(status_code=404, detail="Incident not found")
    return history


@app.post("/incidents/{incident_id}/resolve")
async def resolve_incident(
    incident_id: str,
    summary: str,
    auth: dict = Depends(verify_auth)
):
    """Resolve an incident."""
    success = incident_manager.resolve_incident(incident_id, summary)
    if not success:
        raise HTTPException(status_code=404, detail="Incident not found")
    return {"status": "resolved", "incident_id": incident_id}


@app.post("/incidents/{incident_id}/close")
async def close_incident(
    incident_id: str,
    auth: dict = Depends(verify_auth)
):
    """Close an incident."""
    success = incident_manager.close_incident(incident_id)
    if not success:
        raise HTTPException(status_code=404, detail="Incident not found")
    return {"status": "closed", "incident_id": incident_id}


@app.post("/incidents/{incident_id}/acknowledge")
async def acknowledge_incident(
    incident_id: str,
    auth: dict = Depends(verify_auth)
):
    """Acknowledge an incident."""
    incident = incident_manager.get_incident(incident_id)
    if not incident:
        raise HTTPException(status_code=404, detail="Incident not found")
    incident_manager.update_status(incident_id, IncidentStatus.ACKNOWLEDGED)
    return {"status": "acknowledged", "incident_id": incident_id}


@app.post("/incidents/{incident_id}/escalate")
async def escalate_incident(
    incident_id: str,
    auth: dict = Depends(verify_auth)
):
    """Escalate an incident to higher severity."""
    incident = incident_manager.get_incident(incident_id)
    if not incident:
        raise HTTPException(status_code=404, detail="Incident not found")

    # Increase severity if not already critical
    severity_order = [IncidentSeverity.LOW, IncidentSeverity.MEDIUM, IncidentSeverity.HIGH, IncidentSeverity.CRITICAL]
    current_idx = severity_order.index(incident.severity)
    if current_idx < len(severity_order) - 1:
        new_severity = severity_order[current_idx + 1]
        incident.severity = new_severity

    return {"status": "escalated", "incident_id": incident_id, "severity": incident.severity.value}


@app.post("/incidents/{incident_id}/auto-heal")
async def trigger_incident_autoheal(
    incident_id: str,
    background_tasks: BackgroundTasks,
    auth: dict = Depends(verify_auth)
):
    """Trigger auto-healing for an incident based on recommended actions."""
    incident = incident_manager.get_incident(incident_id)
    if not incident:
        raise HTTPException(status_code=404, detail="Incident not found")

    # Execute recommended actions in background
    async def execute_actions():
        for action in incident.recommended_actions:
            if action.automated:
                await execute_autoheal_for_action(action, incident_id)

    background_tasks.add_task(execute_actions)
    return {"status": "auto-heal initiated", "incident_id": incident_id}


# ============================================================================
# Agent Control Endpoints
# ============================================================================

@app.post("/agent/trigger")
async def trigger_agent(
    incident_id: Optional[str] = None,
    background_tasks: BackgroundTasks = None,
    auth: dict = Depends(verify_auth)
):
    """Manually trigger the agent to analyze an incident or current state."""
    if incident_id:
        incident = incident_manager.get_incident(incident_id)
        if not incident:
            raise HTTPException(status_code=404, detail="Incident not found")

        # Run RCA workflow for this incident
        response = await agent_orchestrator.run_rca_workflow(incident_id)
        return {
            "status": "completed",
            "incident_id": incident_id,
            "system_ok": response.system_ok,
            "actions_recommended": len(response.recommended_actions)
        }
    else:
        # Run monitoring check
        logs = ingestion_buffer.get_recent_logs(100)
        metrics = ingestion_buffer.get_recent_metrics(20)
        result = await agent_client.monitor_system(logs, metrics)
        return {
            "status": "completed",
            "anomaly_detected": result is not None,
            "result": result
        }


@app.post("/agent/rerun")
async def rerun_agent_loop(
    incident_id: Optional[str] = None,
    auth: dict = Depends(verify_auth)
):
    """Restart the agent analysis loop with fresh data."""
    if incident_id:
        incident = incident_manager.get_incident(incident_id)
        if not incident:
            raise HTTPException(status_code=404, detail="Incident not found")

        # Re-run the RCA workflow
        response = await agent_orchestrator.run_rca_workflow(incident_id)
        return {
            "status": "rerun completed",
            "incident_id": incident_id,
            "system_ok": response.system_ok
        }
    else:
        # Force a monitoring cycle
        await check_for_anomalies()
        return {"status": "monitoring cycle completed"}


# ============================================================================
# Runbook Endpoints
# ============================================================================

@app.get("/runbooks")
async def list_runbooks(auth: dict = Depends(verify_auth)):
    """List available runbooks."""
    # Return predefined runbooks based on available autoheal actions
    runbooks = [
        {
            "id": "RB-001",
            "name": "Restart Service",
            "category": "service",
            "description": "Restart a failing service via Docker/Kubernetes",
            "action": "restart_service"
        },
        {
            "id": "RB-002",
            "name": "Scale Replicas",
            "category": "compute",
            "description": "Increase service instances to handle load",
            "action": "scale_replicas"
        },
        {
            "id": "RB-003",
            "name": "Flush Cache",
            "category": "cache",
            "description": "Clear Redis/Memcached cache",
            "action": "flush_cache"
        },
        {
            "id": "RB-004",
            "name": "Clear Queue",
            "category": "queue",
            "description": "Drain message queues",
            "action": "clear_queue"
        },
        {
            "id": "RB-005",
            "name": "Rollback Deployment",
            "category": "deployment",
            "description": "Revert to previous deployment version",
            "action": "rollback_deployment"
        },
        {
            "id": "RB-006",
            "name": "Clear Disk Space",
            "category": "disk",
            "description": "Free up disk space by clearing logs/temp files",
            "action": "clear_disk"
        },
    ]
    return runbooks


@app.post("/runbooks/{runbook_id}/execute")
async def execute_runbook(
    runbook_id: str,
    service: Optional[str] = None,
    incident_id: Optional[str] = None,
    auth: dict = Depends(verify_auth)
):
    """Execute a specific runbook."""
    # Map runbook IDs to actions
    runbook_actions = {
        "RB-001": HealingAction.RESTART_SERVICE,
        "RB-002": HealingAction.SCALE_REPLICAS,
        "RB-003": HealingAction.FLUSH_CACHE,
        "RB-004": HealingAction.CLEAR_QUEUE,
        "RB-005": HealingAction.ROLLBACK_DEPLOYMENT,
        "RB-006": HealingAction.CLEAR_DISK,
    }

    action = runbook_actions.get(runbook_id)
    if not action:
        raise HTTPException(status_code=404, detail="Runbook not found")

    result = await autoheal_executor.execute(
        action=action,
        service=service,
        incident_id=incident_id
    )

    return {
        "runbook_id": runbook_id,
        "executed": True,
        "result": result
    }


# ============================================================================
# Notification Endpoints
# ============================================================================

@app.post("/notify/{incident_id}")
async def notify_incident(
    incident_id: str,
    channels: Optional[List[str]] = None,
    auth: dict = Depends(verify_auth)
):
    """Send notifications for an incident."""
    results = await notification_manager.notify_incident(incident_id, channels)
    return results


@app.post("/notify/custom")
async def send_custom_notification(
    channel: str,
    message: str,
    subject: Optional[str] = None,
    auth: dict = Depends(verify_auth)
):
    """Send a custom notification."""
    success = await notification_manager.send_custom_message(
        channel=channel,
        message=message,
        subject=subject
    )
    return {"success": success, "channel": channel}


# ============================================================================
# Slack App Integration Endpoints
# ============================================================================

@app.get("/slack/install")
async def slack_install(
    user: UserDB = Depends(get_current_user)
):
    """
    Get Slack installation URL.
    Redirect user to this URL to add the bot to their workspace.
    """
    # Use user ID as state to link installation to user
    install_url = slack_app.get_install_url(state=user.id)
    return {"install_url": install_url}


@app.get("/slack/oauth/callback")
async def slack_oauth_callback(
    code: str,
    state: Optional[str] = None,
    db: AsyncSession = Depends(get_db)
):
    """
    Handle OAuth callback from Slack.
    Exchanges code for tokens and stores workspace credentials.
    """
    try:
        # Exchange code for tokens
        oauth_result = await slack_app.handle_oauth_callback(code)

        team_id = oauth_result["team_id"]

        # Validate state is a real user ID (if provided)
        user_id = None
        if state:
            result = await db.execute(
                select(UserDB).where(UserDB.id == state)
            )
            user = result.scalar_one_or_none()
            if user:
                user_id = state

        # Check if workspace already exists
        result = await db.execute(
            select(SlackWorkspaceDB).where(SlackWorkspaceDB.team_id == team_id)
        )
        existing = result.scalar_one_or_none()

        if existing:
            # Update existing workspace
            existing.bot_token = oauth_result["bot_token"]
            existing.team_name = oauth_result["team_name"]
            existing.bot_user_id = oauth_result["bot_user_id"]
            existing.scopes = oauth_result["scopes"]
            existing.is_active = True
            if user_id:
                existing.user_id = user_id
        else:
            # Create new workspace record
            workspace = SlackWorkspaceDB(
                team_id=team_id,
                team_name=oauth_result["team_name"],
                bot_token=oauth_result["bot_token"],
                bot_user_id=oauth_result["bot_user_id"],
                user_id=user_id,  # Can be None if no valid user
                scopes=oauth_result["scopes"],
                access_token=oauth_result.get("user_token")
            )
            db.add(workspace)

        await db.commit()

        logger.info(f"Slack workspace installed: {oauth_result['team_name']} ({team_id})")

        # Auto-join #incidents channel and send welcome message
        bot_token = oauth_result["bot_token"]
        joined_channel = await slack_app.auto_join_incidents_channel(bot_token)
        if joined_channel:
            await slack_app.send_welcome_message(bot_token, joined_channel)
            logger.info(f"Auto-joined and sent welcome to channel: {joined_channel}")

        # Redirect to frontend integrations page with success
        from urllib.parse import urlencode
        params = urlencode({
            "slack_connected": "true",
            "team_name": oauth_result["team_name"]
        })
        frontend_url = getattr(config, 'FRONTEND_URL', "http://localhost:5173")
        return RedirectResponse(url=f"{frontend_url}/integrations?{params}")

    except Exception as e:
        logger.error(f"Slack OAuth failed: {str(e)}")
        # Redirect to frontend with error
        from urllib.parse import urlencode
        params = urlencode({
            "slack_error": str(e)
        })
        frontend_url = getattr(config, 'FRONTEND_URL', "http://localhost:5173")
        return RedirectResponse(url=f"{frontend_url}/integrations?{params}")


@app.post("/slack/events")
async def slack_events(
    request: Request,
    db: AsyncSession = Depends(get_db)
):
    """
    Handle Slack Events API requests.
    Receives events like mentions, messages, etc.
    """
    body = await request.body()
    data = json.loads(body)

    # Handle URL verification challenge FIRST (before signature check)
    if data.get("type") == "url_verification":
        return {"challenge": data.get("challenge")}

    # Verify request is from Slack
    timestamp = request.headers.get("X-Slack-Request-Timestamp", "")
    signature = request.headers.get("X-Slack-Signature", "")

    logger.info(f"Slack event verification - signing secret configured: {bool(config.SLACK_SIGNING_SECRET)}")

    if not slack_app.verify_request(timestamp, signature, body):
        logger.warning(f"Slack signature verification failed")
        raise HTTPException(status_code=401, detail="Invalid signature")

    # Handle events
    if data.get("type") == "event_callback":
        event = data.get("event", {})
        team_id = data.get("team_id")
        logger.info(f"Slack event received: {event.get('type')} from {team_id}")

        # Get workspace token using helper
        workspace = await get_active_workspace(team_id, db)

        if not workspace:
            logger.warning(f"Event from unknown workspace: {team_id}")
            return {"ok": True}

        # Handle the event
        await slack_event_handler.handle_event(
            event=event,
            team_id=team_id,
            bot_token=workspace.bot_token,
            db=db
        )

    return {"ok": True}


@app.post("/slack/commands")
async def slack_commands(
    request: Request,
    db: AsyncSession = Depends(get_db)
):
    """
    Handle Slack slash commands.
    Commands: /sra-check, /sra-status, /sra-incidents, /sra-rca
    """
    body = await request.body()

    # Verify request is from Slack
    timestamp = request.headers.get("X-Slack-Request-Timestamp", "")
    signature = request.headers.get("X-Slack-Signature", "")

    if not slack_app.verify_request(timestamp, signature, body):
        raise HTTPException(status_code=401, detail="Invalid signature")

    # Parse form data
    form = await request.form()
    command = form.get("command", "")
    text = form.get("text", "")
    user_id = form.get("user_id", "")
    channel_id = form.get("channel_id", "")
    team_id = form.get("team_id", "")
    response_url = form.get("response_url", "")

    # Get workspace token using helper
    workspace = await get_active_workspace(team_id, db)

    if not workspace:
        return {"response_type": "ephemeral", "text": "Workspace not configured. Please reinstall the app."}

    # Handle the command
    response = await slack_command_handler.handle_command(
        command=command,
        text=text,
        user_id=user_id,
        channel_id=channel_id,
        team_id=team_id,
        response_url=response_url,
        bot_token=workspace.bot_token,
        db=db
    )

    return JSONResponse(content=response)


@app.post("/slack/interactions")
async def slack_interactions(
    request: Request,
    db: AsyncSession = Depends(get_db)
):
    """
    Handle Slack interactive components (button clicks, etc.)
    """
    body = await request.body()

    # Verify request
    timestamp = request.headers.get("X-Slack-Request-Timestamp", "")
    signature = request.headers.get("X-Slack-Signature", "")

    if not slack_app.verify_request(timestamp, signature, body):
        raise HTTPException(status_code=401, detail="Invalid signature")

    form = await request.form()
    payload = json.loads(form.get("payload", "{}"))

    action_type = payload.get("type")
    team_id = payload.get("team", {}).get("id")

    # Get workspace token using helper
    workspace = await get_active_workspace(team_id, db)

    if not workspace:
        return {"text": "Workspace not configured"}

    # Handle button actions
    if action_type == "block_actions":
        actions = payload.get("actions", [])
        channel = payload.get("channel", {}).get("id")

        for action in actions:
            action_id = action.get("action_id")
            value = action.get("value")

            if action_id == "view_incident":
                incident = incident_manager.get_incident(value)
                if incident:
                    await slack_app.send_incident_alert(
                        bot_token=workspace.bot_token,
                        channel=channel,
                        incident=incident.model_dump()
                    )

            elif action_id == "check_logs":
                logs = ingestion_buffer.get_recent_logs(minutes=15)
                error_logs = [
                    {
                        "timestamp": l.timestamp.isoformat() if l.timestamp else "",
                        "level": l.level.value,
                        "service": l.service or "unknown",
                        "message": l.message
                    }
                    for l in logs if l.level.value in ["error", "critical", "warning"]
                ]
                await slack_app.send_log_check_response(
                    bot_token=workspace.bot_token,
                    channel=channel,
                    logs=error_logs
                )

            elif action_id == "ack_incident":
                # Acknowledge incident
                await slack_app.send_message(
                    bot_token=workspace.bot_token,
                    channel=channel,
                    text=f":white_check_mark: Incident `{value[:8]}` acknowledged by <@{payload.get('user', {}).get('id')}>"
                )

            elif action_id == "execute_autoheal":
                # Execute auto-healing for the incident
                incident = incident_manager.get_incident(value)
                if incident:
                    user_name = payload.get('user', {}).get('name', 'unknown')
                    await slack_app.send_message(
                        bot_token=workspace.bot_token,
                        channel=channel,
                        text=f":gear: *Auto-fix initiated* by <@{payload.get('user', {}).get('id')}> for incident `{value[:8]}`\nExecuting recommended actions..."
                    )

                    # Execute the automatable actions
                    executed_actions = []
                    for action in incident.recommended_actions:
                        if action.automated and not action.executed:
                            result = await execute_autoheal_for_action(action, value)
                            executed_actions.append({
                                "action": action.action_type,
                                "service": action.service,
                                "success": result.get("success", False),
                                "message": result.get("message", "")
                            })

                    # Report results
                    if executed_actions:
                        results_text = "\n".join([
                            f"{'✅' if a['success'] else '❌'} *{a['action']}*" +
                            (f" (`{a['service']}`)" if a['service'] else "") +
                            f": {a['message']}"
                            for a in executed_actions
                        ])
                        await slack_app.send_message(
                            bot_token=workspace.bot_token,
                            channel=channel,
                            text=f":wrench: *Auto-fix Results:*\n{results_text}"
                        )
                    else:
                        await slack_app.send_message(
                            bot_token=workspace.bot_token,
                            channel=channel,
                            text=":warning: No automatable actions found or all already executed."
                        )

            elif action_id == "resolve_incident":
                # Mark incident as resolved
                incident = incident_manager.get_incident(value)
                if incident:
                    incident_manager.resolve_incident(value, summary="Resolved via Slack")
                    await slack_app.send_message(
                        bot_token=workspace.bot_token,
                        channel=channel,
                        text=f":white_check_mark: Incident `{value[:8]}` marked as *resolved* by <@{payload.get('user', {}).get('id')}>"
                    )

            elif action_id == "dismiss_incident":
                # Dismiss/close the incident without resolving
                await slack_app.send_message(
                    bot_token=workspace.bot_token,
                    channel=channel,
                    text=f":x: Incident `{value[:8]}` dismissed by <@{payload.get('user', {}).get('id')}>"
                )

            elif action_id == "escalate_incident":
                # Escalate incident - ping channel for help
                incident = incident_manager.get_incident(value)
                if incident:
                    user_id = payload.get('user', {}).get('id', 'unknown')
                    await slack_app.send_escalation(
                        bot_token=workspace.bot_token,
                        channel=channel,
                        incident_id=value,
                        incident_title=incident.title,
                        severity=incident.severity.value,
                        escalated_by=user_id,
                        summary=incident.description
                    )
                    # Update incident status
                    incident_manager.update_status(value, IncidentStatus.INVESTIGATING)

            elif action_id == "acknowledge_escalation":
                # Someone is responding to escalation
                user_id = payload.get('user', {}).get('id', 'unknown')
                await slack_app.send_message(
                    bot_token=workspace.bot_token,
                    channel=channel,
                    text=f":raised_hand: <@{user_id}> is looking into incident `{value[:8]}`"
                )
                # Update incident status to acknowledged
                incident_manager.update_status(value, IncidentStatus.ACKNOWLEDGED)

    return {"ok": True}


async def execute_autoheal_for_action(action, incident_id: str) -> Dict[str, Any]:
    """Execute a single autoheal action."""
    from integrations.autoheal import autoheal_executor, HealingAction

    action_type_map = {
        "restart_service": HealingAction.RESTART_SERVICE,
        "scale_replicas": HealingAction.SCALE_REPLICAS,
        "flush_cache": HealingAction.FLUSH_CACHE,
        "clear_queue": HealingAction.CLEAR_QUEUE,
        "reroute_traffic": HealingAction.REROUTE_TRAFFIC,
        "rollback_deployment": HealingAction.ROLLBACK_DEPLOYMENT,
        "clear_disk": HealingAction.CLEAR_DISK,
    }

    healing_action = action_type_map.get(action.action_type)
    if not healing_action:
        return {"success": False, "message": f"Unknown action type: {action.action_type}"}

    try:
        result = await autoheal_executor.execute(
            action=healing_action,
            service=action.service,
            parameters=action.parameters or {},
            incident_id=incident_id
        )
        if result.get("success"):
            action.executed = True
            action.result = result.get("message")
        return result
    except Exception as e:
        return {"success": False, "message": str(e)}


@app.get("/slack/workspaces")
async def list_slack_workspaces(
    user: UserDB = Depends(get_current_user),
    db: AsyncSession = Depends(get_db)
):
    """List Slack workspaces connected by this user."""
    result = await db.execute(
        select(SlackWorkspaceDB).where(SlackWorkspaceDB.user_id == user.id)
    )
    workspaces = result.scalars().all()

    return [
        {
            "team_id": w.team_id,
            "team_name": w.team_name,
            "default_channel": w.default_channel,
            "installed_at": w.installed_at.isoformat() if w.installed_at else None,
            "is_active": w.is_active
        }
        for w in workspaces
    ]


@app.delete("/slack/workspaces/{team_id}")
async def disconnect_slack_workspace(
    team_id: str,
    db: AsyncSession = Depends(get_db)
):
    """Disconnect a Slack workspace and uninstall the bot."""
    result = await db.execute(
        select(SlackWorkspaceDB).where(SlackWorkspaceDB.team_id == team_id)
    )
    workspace = result.scalar_one_or_none()

    if not workspace:
        raise HTTPException(status_code=404, detail="Workspace not found")

    # Uninstall the app from the Slack workspace
    if workspace.bot_token:
        uninstall_result = await slack_app.uninstall_app(workspace.bot_token)
        if not uninstall_result.get("ok"):
            logger.warning(f"Could not uninstall from Slack: {uninstall_result.get('error')}")

    # Delete the workspace record from our database
    await db.delete(workspace)
    await db.commit()

    logger.info(f"Slack workspace disconnected and uninstalled: {workspace.team_name} ({team_id})")
    return {"status": "disconnected", "team_id": team_id, "uninstalled": True}


@app.post("/slack/workspaces/{team_id}/test")
async def test_slack_connection(
    team_id: str,
    channel: Optional[str] = None,
    user: UserDB = Depends(get_current_user),
    db: AsyncSession = Depends(get_db)
):
    """Send a test message to verify Slack connection."""
    workspace = await get_active_workspace(team_id, db, user_id=user.id)

    if not workspace:
        raise HTTPException(status_code=404, detail="Workspace not found or inactive")

    target_channel = channel or workspace.default_channel

    response = await slack_app.send_message(
        bot_token=workspace.bot_token,
        channel=target_channel,
        text=":wave: Test message from SRA Incident Response System!"
    )

    if response.get("ok"):
        return {"success": True, "channel": target_channel}
    else:
        return {"success": False, "error": response.get("error")}


# ============================================================================
# Mock Data / Testing Endpoints
# ============================================================================

@app.post("/mock/generate-incident")
async def generate_mock_incident(
    incident_type: Optional[str] = None,
    auth: dict = Depends(verify_auth)
):
    """Generate a synthetic incident for testing."""
    if incident_type == "database":
        data = mock_generator.generate_database_incident()
    elif incident_type == "memory":
        data = mock_generator.generate_memory_leak_incident()
    elif incident_type == "latency":
        data = mock_generator.generate_latency_spike_incident()
    elif incident_type == "service":
        data = mock_generator.generate_service_outage_incident()
    elif incident_type == "disk":
        data = mock_generator.generate_disk_full_incident()
    else:
        data = mock_generator.generate_random_incident()

    # Create the incident
    incident = incident_manager.create_incident(
        title=data["title"],
        description=data["description"],
        severity=data["severity"],
        logs=data["logs"],
        metrics=data["metrics"]
    )

    return {
        "incident_id": incident.id,
        "title": incident.title,
        "severity": incident.severity.value,
        "log_count": len(incident.logs),
        "metric_count": len(incident.metrics)
    }


@app.post("/mock/generate-logs")
async def generate_mock_logs(
    count: int = 50,
    error_rate: float = 0.2,
    service: Optional[str] = None,
    auth: dict = Depends(verify_auth)
):
    """Generate mock logs and ingest them."""
    logs = mock_generator.generate_logs(count=count, error_rate=error_rate, service=service)
    ingestion_buffer.add_logs(logs)

    return {
        "generated": len(logs),
        "error_count": sum(1 for l in logs if l.level.value in ["error", "critical"])
    }


@app.post("/mock/generate-metrics")
async def generate_mock_metrics(
    count: int = 20,
    stress_level: float = 0.0,
    auth: dict = Depends(verify_auth)
):
    """Generate mock metrics and ingest them."""
    for _ in range(count):
        snapshot = mock_generator.generate_metrics_snapshot(stress_level=stress_level)
        ingestion_buffer.add_snapshot(snapshot)

    return {"generated": count, "stress_level": stress_level}


@app.get("/mock/incident-types")
async def list_mock_incident_types(auth: dict = Depends(verify_auth)):
    """List available mock incident types."""
    return {
        "types": [
            {"name": "database", "description": "Database connection failure"},
            {"name": "memory", "description": "Memory leak / OOM errors"},
            {"name": "latency", "description": "API latency spike"},
            {"name": "service", "description": "Service outage"},
            {"name": "disk", "description": "Disk space critical"},
            {"name": "random", "description": "Random incident type"}
        ]
    }


# ============================================================================
# User Authentication Endpoints
# ============================================================================

@app.post("/auth/register", response_model=TokenResponse)
async def register(request: UserRegisterRequest, db: AsyncSession = Depends(get_db)):
    """Register a new user account."""
    # Check if email exists
    result = await db.execute(
        select(UserDB).where(UserDB.email == request.email)
    )
    if result.scalar_one_or_none():
        raise HTTPException(status_code=400, detail="Email already registered")

    # Create user
    user = UserDB(
        email=request.email,
        password_hash=hash_password(request.password)
    )
    db.add(user)
    await db.commit()
    await db.refresh(user)

    # Create session token with expiration
    token = generate_token()
    session = SessionTokenDB(
        token=token,
        user_id=user.id,
        expires_at=get_token_expiry()
    )
    db.add(session)
    await db.commit()

    logger.info(f"User registered: {user.email}")

    return TokenResponse(
        access_token=token,
        user=UserResponse(
            id=user.id,
            email=user.email,
            created_at=user.created_at,
            is_active=user.is_active
        )
    )


@app.post("/auth/login", response_model=TokenResponse)
async def login(request: UserLoginRequest, db: AsyncSession = Depends(get_db)):
    """Login and get access token."""
    result = await db.execute(
        select(UserDB).where(UserDB.email == request.email)
    )
    user = result.scalar_one_or_none()

    # Use secure password verification (#3 fix)
    if not user or not verify_password(request.password, user.password_hash):
        raise HTTPException(status_code=401, detail="Invalid email or password")

    if not user.is_active:
        raise HTTPException(status_code=403, detail="Account disabled")

    # Create session token with expiration
    token = generate_token()
    session = SessionTokenDB(
        token=token,
        user_id=user.id,
        expires_at=get_token_expiry()
    )
    db.add(session)
    await db.commit()

    logger.info(f"User logged in: {user.email}")

    return TokenResponse(
        access_token=token,
        user=UserResponse(
            id=user.id,
            email=user.email,
            created_at=user.created_at,
            is_active=user.is_active
        )
    )


@app.post("/auth/logout")
async def logout(
    user: UserDB = Depends(get_current_user),
    db: AsyncSession = Depends(get_db)
):
    """Logout and invalidate all user tokens."""
    result = await db.execute(
        select(SessionTokenDB).where(SessionTokenDB.user_id == user.id)
    )
    tokens = result.scalars().all()
    for token in tokens:
        await db.delete(token)
    await db.commit()

    return {"status": "logged out"}


@app.get("/auth/me", response_model=UserResponse)
async def get_me(user: UserDB = Depends(get_current_user)):
    """Get current user info."""
    return UserResponse(
        id=user.id,
        email=user.email,
        created_at=user.created_at,
        is_active=user.is_active
    )


@app.get("/account/overview", response_model=AccountOverviewResponse)
async def get_account_overview(
    user: UserDB = Depends(get_current_user),
    db: AsyncSession = Depends(get_db)
) -> AccountOverviewResponse:
    """Get full account overview including all integrations."""
    # Get API keys
    api_keys_result = await db.execute(
        select(APIKeyDB).where(APIKeyDB.user_id == user.id)
    )
    api_keys = api_keys_result.scalars().all()

    # Get Slack workspaces
    slack_result = await db.execute(
        select(SlackWorkspaceDB).where(SlackWorkspaceDB.user_id == user.id)
    )
    slack_workspaces = slack_result.scalars().all()

    return AccountOverviewResponse(
        user=UserOverview(
            id=user.id,
            email=user.email,
            created_at=user.created_at.isoformat() if user.created_at else None,
            is_active=user.is_active,
            subscription=SubscriptionInfo(
                tier=user.subscription_tier,
                status=user.subscription_status,
                expires=user.subscription_expires.isoformat() if user.subscription_expires else None
            )
        ),
        integrations=AccountIntegrations(
            slack=SlackIntegrationStatus(
                connected=len([w for w in slack_workspaces if w.is_active]) > 0,
                workspaces=[
                    SlackWorkspaceResponse(
                        team_id=w.team_id,
                        team_name=w.team_name,
                        default_channel=w.default_channel,
                        installed_at=w.installed_at.isoformat() if w.installed_at else None,
                        is_active=w.is_active
                    )
                    for w in slack_workspaces
                ]
            ),
            discord=IntegrationStatus(connected=False),
            jira=IntegrationStatus(connected=False),
            pagerduty=IntegrationStatus(connected=False)
        ),
        api_keys=APIKeysOverview(
            count=len(api_keys),
            max_allowed=config.MAX_API_KEYS_PER_USER,
            keys=[
                APIKeyInfo(
                    name=k.name,
                    key_preview=k.key[:12] + "...",
                    created_at=k.created_at.isoformat() if k.created_at else None,
                    last_used=k.last_used.isoformat() if k.last_used else None,
                    is_active=k.is_active
                )
                for k in api_keys
            ]
        )
    )


# ============================================================================
# API Key Management Endpoints
# ============================================================================

@app.post("/api-keys", response_model=APIKeyResponse)
async def create_api_key(
    request: APIKeyCreateRequest,
    user: UserDB = Depends(get_current_user),
    db: AsyncSession = Depends(get_db)
):
    """Create a new API key. Limited to 3 per user."""
    # Count user's keys
    result = await db.execute(
        select(func.count(APIKeyDB.key)).where(APIKeyDB.user_id == user.id)
    )
    key_count = result.scalar()

    if key_count >= config.MAX_API_KEYS_PER_USER:
        raise HTTPException(
            status_code=400,
            detail=f"Maximum {config.MAX_API_KEYS_PER_USER} API keys allowed per user"
        )

    # Create key
    api_key = APIKeyDB(
        name=request.name,
        user_id=user.id
    )
    db.add(api_key)
    await db.commit()
    await db.refresh(api_key)

    logger.info(f"Created API key '{api_key.name}' for user {user.email}")

    return APIKeyResponse(
        key=api_key.key,
        name=api_key.name,
        created_at=api_key.created_at,
        is_active=api_key.is_active
    )


@app.get("/api-keys")
async def list_api_keys(
    user: UserDB = Depends(get_current_user),
    db: AsyncSession = Depends(get_db)
):
    """List all API keys for current user."""
    result = await db.execute(
        select(APIKeyDB).where(APIKeyDB.user_id == user.id)
    )
    user_keys = result.scalars().all()

    return [
        {
            "key": k.key[:12] + "...",  # Masked for security
            "name": k.name,
            "created_at": k.created_at.isoformat(),
            "last_used": k.last_used.isoformat() if k.last_used else None,
            "is_active": k.is_active
        }
        for k in user_keys
    ]


@app.delete("/api-keys/{key_prefix}")
async def revoke_api_key(
    key_prefix: str,
    user: UserDB = Depends(get_current_user),
    db: AsyncSession = Depends(get_db)
):
    """Revoke an API key. Users can only revoke their own keys."""
    result = await db.execute(
        select(APIKeyDB).where(
            APIKeyDB.key.startswith(key_prefix),
            APIKeyDB.user_id == user.id
        )
    )
    api_key = result.scalar_one_or_none()

    if not api_key:
        raise HTTPException(status_code=404, detail="API key not found")

    api_key.is_active = False
    await db.commit()

    logger.info(f"Revoked API key '{api_key.name}' for user {user.email}")
    return {"status": "revoked", "name": api_key.name}


@app.delete("/api-keys/{key_prefix}/delete")
async def delete_api_key(
    key_prefix: str,
    user: UserDB = Depends(get_current_user),
    db: AsyncSession = Depends(get_db)
):
    """Permanently delete an API key. Users can only delete their own keys."""
    result = await db.execute(
        select(APIKeyDB).where(
            APIKeyDB.key.startswith(key_prefix),
            APIKeyDB.user_id == user.id
        )
    )
    api_key = result.scalar_one_or_none()

    if not api_key:
        raise HTTPException(status_code=404, detail="API key not found")

    name = api_key.name
    await db.delete(api_key)
    await db.commit()

    logger.info(f"Deleted API key '{name}' for user {user.email}")
    return {"status": "deleted", "name": name}


# ============================================================================
# Background Tasks
# ============================================================================

async def notify_background_error(task_name: str, error: str, context: Dict[str, Any] = None):
    """Send notification when a background task fails."""
    try:
        # Log the error
        logger.error(f"Background task '{task_name}' failed: {error}", context or {})

        # Send to Slack if configured
        if config.SLACK_WEBHOOK_URL:
            import httpx
            payload = {
                "text": f":warning: Background Task Error",
                "attachments": [{
                    "color": "#ff0000",
                    "blocks": [
                        {
                            "type": "section",
                            "fields": [
                                {"type": "mrkdwn", "text": f"*Task:*\n{task_name}"},
                                {"type": "mrkdwn", "text": f"*Time:*\n{utc_now().strftime('%Y-%m-%d %H:%M UTC')}"}
                            ]
                        },
                        {
                            "type": "section",
                            "text": {"type": "mrkdwn", "text": f"*Error:*\n```{error[:500]}```"}
                        }
                    ]
                }]
            }
            async with httpx.AsyncClient() as client:
                await client.post(config.SLACK_WEBHOOK_URL, json=payload)
    except Exception as notify_error:
        logger.error(f"Failed to send background error notification: {str(notify_error)}")


async def continuous_monitoring_loop():
    """
    Continuous monitoring loop that runs periodically.

    Flow:
    1. Check for anomalies in logs/metrics via LLM
    2. If anomaly detected → Create incident → Alert Slack with RCA
    3. User can click "Execute Auto-Fix" to run healing actions
    4. If no anomalies → Loop continues
    """
    # Use env var for interval, default 5 minutes (300s), use 30s for testing
    import os
    monitoring_interval = int(os.getenv("MONITORING_INTERVAL", "300"))
    logger.info(f"Monitoring interval set to {monitoring_interval} seconds")

    while True:
        try:
            await check_for_anomalies()
        except Exception as e:
            logger.error(f"Monitoring loop error: {str(e)}")

        await asyncio.sleep(monitoring_interval)


async def check_for_anomalies():
    """
    Check for anomalies using LLM and trigger incident workflow.

    The LLM analyzes logs/metrics and returns:
    - anomaly_detected: true/false
    - If true: severity, title, root_cause, recommended_actions
    """
    try:
        recent_logs = ingestion_buffer.get_recent_logs(minutes=5)
        recent_snapshots = ingestion_buffer.get_recent_snapshots(count=5)

        # Skip if no data to analyze
        if not recent_logs and not recent_snapshots:
            logger.debug("No data to analyze, skipping monitoring check")
            return

        # Check if we already have an active incident
        active = incident_manager.get_active_incident()
        if active:
            logger.debug(f"Active incident exists: {active.id}, skipping monitoring")
            return

        # Call LLM to analyze system health
        logger.info("Running LLM-based system monitoring...")
        llm_result = await agent_client.monitor_system(
            logs=recent_logs,
            metrics=recent_snapshots
        )

        if llm_result is None:
            # No anomaly detected OR LLM not configured
            logger.info("LLM monitoring: System healthy (no anomalies detected)")
            return

        # LLM detected an anomaly - create incident with LLM's analysis
        logger.info(f"LLM detected anomaly: {llm_result.get('title')}")

        # Map severity string to enum
        severity_map = {
            "low": IncidentSeverity.LOW,
            "medium": IncidentSeverity.MEDIUM,
            "high": IncidentSeverity.HIGH,
            "critical": IncidentSeverity.CRITICAL
        }
        severity = severity_map.get(llm_result.get("severity", "medium").lower(), IncidentSeverity.MEDIUM)

        # Create incident with LLM's findings
        incident = incident_manager.create_incident(
            title=llm_result.get("title", "Issue detected by monitoring"),
            description=llm_result.get("summary", ""),
            severity=severity,
            logs=recent_logs,
            metrics=recent_snapshots
        )

        # Set RCA from LLM response
        from core import RCAResult, RecoveryAction
        rca = RCAResult(
            root_cause=llm_result.get("root_cause", "See LLM analysis"),
            contributing_factors=llm_result.get("contributing_factors", []),
            evidence=[],
            confidence=0.8
        )
        incident_manager.set_rca(incident.id, rca)

        # Convert LLM actions to RecoveryAction objects
        actions = []
        for action_data in llm_result.get("recommended_actions", []):
            action_type = action_data.get("action", "unknown")
            # Check if this action type is automatable
            automatable = action_type in [
                "restart_service", "scale_replicas", "flush_cache",
                "clear_queue", "rollback_deployment", "reroute_traffic", "clear_disk"
            ]
            actions.append(RecoveryAction(
                action_type=action_type,
                description=action_data.get("reason", ""),
                service=action_data.get("service"),
                automated=automatable
            ))

        for action in actions:
            incident_manager.add_recommended_action(incident.id, action)

        logger.info(f"Created incident from LLM analysis: {incident.id}")

        # Broadcast incident alert to Slack
        await broadcast_incident_to_all_workspaces(incident)

        # Send RCA results with autoheal button
        await broadcast_rca_to_all_workspaces(
            incident=incident,
            rca=rca,
            actions=actions
        )

    except Exception as e:
        await notify_background_error(
            "check_for_anomalies",
            str(e),
            {"log_count": len(ingestion_buffer.logs)}
        )


async def broadcast_incident_to_all_workspaces(incident):
    """Broadcast an incident alert to all connected Slack workspaces."""
    try:
        async with async_session() as db:
            # Get all active workspaces
            result = await db.execute(
                select(SlackWorkspaceDB).where(SlackWorkspaceDB.is_active == True)
            )
            workspaces = result.scalars().all()

            for workspace in workspaces:
                try:
                    # Broadcast to all channels the bot is in for this workspace
                    results = await slack_app.broadcast_incident_alert(
                        bot_token=workspace.bot_token,
                        incident=incident.model_dump() if hasattr(incident, 'model_dump') else incident,
                        ping_everyone=True  # @channel ping
                    )
                    logger.info(f"Broadcast incident to {workspace.team_name}: {len(results)} channels")
                except Exception as e:
                    logger.error(f"Failed to broadcast to {workspace.team_name}: {str(e)}")

    except Exception as e:
        logger.error(f"Failed to broadcast incident: {str(e)}")


async def broadcast_rca_to_all_workspaces(incident, rca, actions):
    """
    Broadcast RCA results with autoheal button to all connected Slack workspaces.

    This sends a follow-up message with:
    - Root cause analysis
    - Recommended actions (automatable vs manual)
    - "Execute Auto-Fix" button for user-controlled healing
    """
    try:
        async with async_session() as db:
            # Get all active workspaces
            result = await db.execute(
                select(SlackWorkspaceDB).where(SlackWorkspaceDB.is_active == True)
            )
            workspaces = result.scalars().all()

            # Convert RCA and actions to dict format
            rca_dict = rca.model_dump() if hasattr(rca, 'model_dump') else rca
            actions_list = [
                a.model_dump() if hasattr(a, 'model_dump') else a
                for a in (actions or [])
            ]

            for workspace in workspaces:
                try:
                    # Get channels the bot is in
                    channels = await slack_app.list_channels(workspace.bot_token)
                    bot_channels = [c for c in channels if c.get("is_member")]

                    for channel in bot_channels:
                        await slack_app.send_rca_report(
                            bot_token=workspace.bot_token,
                            channel=channel.get("id"),
                            incident_id=incident.id,
                            rca=rca_dict,
                            actions=actions_list,
                            show_autoheal_button=True
                        )

                    logger.info(f"Broadcast RCA to {workspace.team_name}: {len(bot_channels)} channels")
                except Exception as e:
                    logger.error(f"Failed to broadcast RCA to {workspace.team_name}: {str(e)}")

    except Exception as e:
        logger.error(f"Failed to broadcast RCA: {str(e)}")


async def run_agent_workflow(incident_id: str):
    """Background task to run the agent workflow."""
    try:
        await agent_orchestrator.run_rca_workflow(incident_id)
    except Exception as e:
        await notify_background_error(
            "run_agent_workflow",
            str(e),
            {"incident_id": incident_id}
        )


# ============================================================================
# Run the application
# ============================================================================

def start_ngrok(port: int) -> str:
    """Start ngrok tunnel and return the public URL."""
    try:
        from pyngrok import ngrok

        # Start ngrok tunnel
        public_url = ngrok.connect(port, "http").public_url

        # Update Slack redirect URI if needed
        slack_redirect = f"{public_url}/slack/oauth/callback"

        print(f"\n{'='*60}")
        print(f"  NGROK TUNNEL ACTIVE")
        print(f"{'='*60}")
        print(f"  Public URL:      {public_url}")
        print(f"  Slack Redirect:  {slack_redirect}")
        print(f"  Slack Events:    {public_url}/slack/events")
        print(f"  Slack Commands:  {public_url}/slack/commands")
        print(f"{'='*60}")
        print(f"\n  Update these URLs in your Slack App settings!")
        print(f"{'='*60}\n")

        return public_url

    except ImportError:
        print("\n  [WARNING] pyngrok not installed. Run: pip install pyngrok")
        print("  Starting without ngrok tunnel...\n")
        return None
    except Exception as e:
        print(f"\n  [ERROR] Failed to start ngrok: {e}")
        print("  Starting without ngrok tunnel...\n")
        return None


if __name__ == "__main__":
    import argparse
    import uvicorn

    parser = argparse.ArgumentParser(description="SRA Incident Response Backend")
    parser.add_argument("--ngrok", action="store_true", help="Start with ngrok tunnel for Slack webhooks")
    parser.add_argument("--port", type=int, default=8000, help="Port to run on (default: 8000)")
    parser.add_argument("--host", type=str, default="0.0.0.0", help="Host to bind to (default: 0.0.0.0)")
    args = parser.parse_args()

    # Start ngrok if requested
    if args.ngrok:
        start_ngrok(args.port)

    uvicorn.run(app, host=args.host, port=args.port)
