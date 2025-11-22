"""
API Gateway / Main Application
Production-grade FastAPI backend with all endpoints.
"""
import time
from typing import List, Optional, Dict, Any
from datetime import datetime
from contextlib import asynccontextmanager

from fastapi import FastAPI, HTTPException, Depends, Header, Request, BackgroundTasks
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse

from core import (
    LogEntry, MetricEntry, MetricsSnapshot, Incident, IncidentSeverity,
    IncidentStatus, LogIngestionRequest, MetricIngestionRequest,
    MetricsSnapshotRequest, AutoHealRequest, NotificationRequest,
    ForceRCARequest, AnomalyDetection, StabilityReport, RecoveryAction,
    config, logger
)
from engines import (
    ingestion_buffer, LogParser, MetricsNormalizer,
    anomaly_detector, stability_evaluator, incident_manager
)
from integrations import (
    agent_orchestrator, autoheal_executor, HealingAction, notification_manager
)
from utils import mock_generator


# Lifespan context manager
@asynccontextmanager
async def lifespan(app: FastAPI):
    logger.info("Starting Incident Response Backend")
    yield
    logger.info("Shutting down Incident Response Backend")


# Create FastAPI app
app = FastAPI(
    title="Incident Response Backend",
    description="Production-grade backend for autonomous incident response with watsonx integration",
    version="1.0.0",
    lifespan=lifespan
)

# CORS middleware
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)


# API Key authentication
async def verify_api_key(x_api_key: str = Header(None, alias="X-API-Key")):
    if not config.API_KEY:
        return True  # No auth configured
    if x_api_key != config.API_KEY:
        raise HTTPException(status_code=401, detail="Invalid API key")
    return True


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

@app.get("/health")
async def health_check():
    """Basic health check endpoint."""
    return {"status": "healthy", "timestamp": datetime.utcnow().isoformat()}


@app.get("/status")
async def system_status(auth: bool = Depends(verify_api_key)):
    """Get overall system status."""
    active_incident = incident_manager.get_active_incident()
    trend = stability_evaluator.get_stability_trend()

    return {
        "status": "operational",
        "timestamp": datetime.utcnow().isoformat(),
        "active_incident": active_incident.id if active_incident else None,
        "stability_trend": trend,
        "buffer_stats": {
            "logs": len(ingestion_buffer.logs),
            "metrics": len(ingestion_buffer.metrics),
            "snapshots": len(ingestion_buffer.snapshots)
        }
    }


# ============================================================================
# Log & Metrics Ingestion Endpoints
# ============================================================================

@app.post("/ingest/logs")
async def ingest_logs(
    request: LogIngestionRequest,
    background_tasks: BackgroundTasks,
    auth: bool = Depends(verify_api_key)
):
    """Ingest log entries."""
    ingestion_buffer.add_logs(request.logs)

    # Check for anomalies in background
    background_tasks.add_task(check_for_anomalies)

    return {
        "status": "accepted",
        "count": len(request.logs),
        "timestamp": datetime.utcnow().isoformat()
    }


@app.post("/ingest/logs/raw")
async def ingest_raw_logs(
    raw_logs: List[str],
    source: Optional[str] = None,
    background_tasks: BackgroundTasks = None,
    auth: bool = Depends(verify_api_key)
):
    """Ingest raw log strings (parsed automatically)."""
    parsed = []
    for raw in raw_logs:
        if "\n" in raw:
            parsed.extend(LogParser.parse_multiline(raw, source))
        else:
            parsed.append(LogParser.parse(raw, source))

    ingestion_buffer.add_logs(parsed)

    if background_tasks:
        background_tasks.add_task(check_for_anomalies)

    return {
        "status": "accepted",
        "count": len(parsed),
        "timestamp": datetime.utcnow().isoformat()
    }


@app.post("/ingest/metrics")
async def ingest_metrics(
    request: MetricIngestionRequest,
    background_tasks: BackgroundTasks,
    auth: bool = Depends(verify_api_key)
):
    """Ingest metric entries."""
    ingestion_buffer.add_metrics(request.metrics)

    # Normalize to snapshot
    snapshot = MetricsNormalizer.normalize(request.metrics)
    ingestion_buffer.add_snapshot(snapshot)

    # Check for anomalies
    background_tasks.add_task(check_for_anomalies)

    return {
        "status": "accepted",
        "count": len(request.metrics),
        "timestamp": datetime.utcnow().isoformat()
    }


@app.post("/ingest/snapshot")
async def ingest_snapshot(
    request: MetricsSnapshotRequest,
    background_tasks: BackgroundTasks,
    auth: bool = Depends(verify_api_key)
):
    """Ingest a metrics snapshot directly."""
    ingestion_buffer.add_snapshot(request.snapshot)

    # Check for anomalies
    background_tasks.add_task(check_for_anomalies)

    return {
        "status": "accepted",
        "timestamp": datetime.utcnow().isoformat()
    }


# ============================================================================
# Anomaly Detection Endpoints
# ============================================================================

@app.get("/anomaly/status")
async def get_anomaly_status(auth: bool = Depends(verify_api_key)):
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
    auth: bool = Depends(verify_api_key)
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
    auth: bool = Depends(verify_api_key)
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
    auth: bool = Depends(verify_api_key)
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
async def check_stability(auth: bool = Depends(verify_api_key)):
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
    auth: bool = Depends(verify_api_key)
):
    """Set a baseline for stability comparison."""
    stability_evaluator.set_baseline(snapshot)
    return {"status": "baseline set"}


# ============================================================================
# Auto-Healing Endpoints
# ============================================================================

@app.post("/autoheal/restart")
async def autoheal_restart(
    request: AutoHealRequest,
    auth: bool = Depends(verify_api_key)
):
    """Restart a service."""
    result = await autoheal_executor.execute(
        action=HealingAction.RESTART_SERVICE,
        service=request.service,
        parameters=request.parameters,
        incident_id=request.incident_id
    )
    return result


@app.post("/autoheal/scale")
async def autoheal_scale(
    request: AutoHealRequest,
    auth: bool = Depends(verify_api_key)
):
    """Scale service replicas."""
    result = await autoheal_executor.execute(
        action=HealingAction.SCALE_REPLICAS,
        service=request.service,
        parameters=request.parameters,
        incident_id=request.incident_id
    )
    return result


@app.post("/autoheal/flush")
async def autoheal_flush(
    request: AutoHealRequest,
    auth: bool = Depends(verify_api_key)
):
    """Flush cache."""
    result = await autoheal_executor.execute(
        action=HealingAction.FLUSH_CACHE,
        service=request.service,
        parameters=request.parameters,
        incident_id=request.incident_id
    )
    return result


@app.post("/autoheal/clear-queue")
async def autoheal_clear_queue(
    request: AutoHealRequest,
    auth: bool = Depends(verify_api_key)
):
    """Clear a message queue."""
    result = await autoheal_executor.execute(
        action=HealingAction.CLEAR_QUEUE,
        service=request.service,
        parameters=request.parameters,
        incident_id=request.incident_id
    )
    return result


@app.post("/autoheal/reroute")
async def autoheal_reroute(
    request: AutoHealRequest,
    auth: bool = Depends(verify_api_key)
):
    """Reroute traffic."""
    result = await autoheal_executor.execute(
        action=HealingAction.REROUTE_TRAFFIC,
        service=request.service,
        parameters=request.parameters,
        incident_id=request.incident_id
    )
    return result


@app.post("/autoheal/rollback")
async def autoheal_rollback(
    request: AutoHealRequest,
    auth: bool = Depends(verify_api_key)
):
    """Rollback deployment."""
    result = await autoheal_executor.execute(
        action=HealingAction.ROLLBACK_DEPLOYMENT,
        service=request.service,
        parameters=request.parameters,
        incident_id=request.incident_id
    )
    return result


@app.get("/autoheal/actions")
async def list_autoheal_actions(auth: bool = Depends(verify_api_key)):
    """List available auto-healing actions."""
    return autoheal_executor.get_available_actions()


@app.post("/autoheal/dry-run")
async def set_autoheal_dry_run(
    enabled: bool = True,
    auth: bool = Depends(verify_api_key)
):
    """Enable/disable dry run mode for auto-healing."""
    autoheal_executor.set_dry_run(enabled)
    return {"dry_run": enabled}


# ============================================================================
# Incident Management Endpoints
# ============================================================================

@app.get("/incidents")
async def list_incidents(
    status: Optional[str] = None,
    limit: int = 50,
    auth: bool = Depends(verify_api_key)
):
    """List incidents."""
    status_enum = IncidentStatus(status) if status else None
    return incident_manager.list_incidents(status=status_enum, limit=limit)


@app.get("/incidents/{incident_id}")
async def get_incident(
    incident_id: str,
    auth: bool = Depends(verify_api_key)
):
    """Get incident details."""
    incident = incident_manager.get_incident(incident_id)
    if not incident:
        raise HTTPException(status_code=404, detail="Incident not found")
    return incident.model_dump()


@app.get("/incidents/{incident_id}/summary")
async def get_incident_summary(
    incident_id: str,
    auth: bool = Depends(verify_api_key)
):
    """Get incident summary."""
    summary = incident_manager.get_incident_summary(incident_id)
    if not summary:
        raise HTTPException(status_code=404, detail="Incident not found")
    return summary


@app.get("/incidents/{incident_id}/history")
async def get_incident_history(
    incident_id: str,
    auth: bool = Depends(verify_api_key)
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
    auth: bool = Depends(verify_api_key)
):
    """Resolve an incident."""
    success = incident_manager.resolve_incident(incident_id, summary)
    if not success:
        raise HTTPException(status_code=404, detail="Incident not found")
    return {"status": "resolved", "incident_id": incident_id}


@app.post("/incidents/{incident_id}/close")
async def close_incident(
    incident_id: str,
    auth: bool = Depends(verify_api_key)
):
    """Close an incident."""
    success = incident_manager.close_incident(incident_id)
    if not success:
        raise HTTPException(status_code=404, detail="Incident not found")
    return {"status": "closed", "incident_id": incident_id}


# ============================================================================
# Notification Endpoints
# ============================================================================

@app.post("/notify/{incident_id}")
async def notify_incident(
    incident_id: str,
    channels: Optional[List[str]] = None,
    auth: bool = Depends(verify_api_key)
):
    """Send notifications for an incident."""
    results = await notification_manager.notify_incident(incident_id, channels)
    return results


@app.post("/notify/custom")
async def send_custom_notification(
    channel: str,
    message: str,
    subject: Optional[str] = None,
    auth: bool = Depends(verify_api_key)
):
    """Send a custom notification."""
    success = await notification_manager.send_custom_message(
        channel=channel,
        message=message,
        subject=subject
    )
    return {"success": success, "channel": channel}


# ============================================================================
# Mock Data / Testing Endpoints
# ============================================================================

@app.post("/mock/generate-incident")
async def generate_mock_incident(
    incident_type: Optional[str] = None,
    auth: bool = Depends(verify_api_key)
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
    auth: bool = Depends(verify_api_key)
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
    auth: bool = Depends(verify_api_key)
):
    """Generate mock metrics and ingest them."""
    for _ in range(count):
        snapshot = mock_generator.generate_metrics_snapshot(stress_level=stress_level)
        ingestion_buffer.add_snapshot(snapshot)

    return {"generated": count, "stress_level": stress_level}


@app.get("/mock/incident-types")
async def list_mock_incident_types(auth: bool = Depends(verify_api_key)):
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
# Background Tasks
# ============================================================================

async def check_for_anomalies():
    """Background task to check for anomalies and trigger incidents."""
    recent_logs = ingestion_buffer.get_recent_logs(minutes=5)
    recent_snapshots = ingestion_buffer.get_recent_snapshots(count=3)
    latest_snapshot = recent_snapshots[-1] if recent_snapshots else None

    detection = anomaly_detector.detect(logs=recent_logs, metrics=latest_snapshot)

    if detection.detected:
        # Check if we already have an active incident
        active = incident_manager.get_active_incident()
        if not active:
            # Create new incident
            incident = incident_manager.create_incident(
                title=f"Detected: {detection.anomaly_type}",
                description=detection.description,
                severity=detection.severity,
                anomaly=detection,
                logs=recent_logs,
                metrics=recent_snapshots
            )
            logger.info(f"Auto-created incident: {incident.id}")


async def run_agent_workflow(incident_id: str):
    """Background task to run the agent workflow."""
    try:
        await agent_orchestrator.run_rca_workflow(incident_id)
    except Exception as e:
        logger.error(f"Agent workflow failed: {str(e)}")


# ============================================================================
# Run the application
# ============================================================================

if __name__ == "__main__":
    import uvicorn
    uvicorn.run(app, host="0.0.0.0", port=8000)
