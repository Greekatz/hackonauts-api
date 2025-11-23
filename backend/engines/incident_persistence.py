"""
Incident Persistence Layer
Handles saving/loading incidents to/from database.
"""
import json
from typing import Optional, List
from datetime import datetime

from sqlalchemy import select, desc
from sqlalchemy.ext.asyncio import AsyncSession

from core import (
    Incident, IncidentStatus, IncidentSeverity, LogEntry, MetricsSnapshot,
    RCAResult, RecoveryAction, StabilityReport, AnomalyDetection, logger,
    IncidentDB
)


class IncidentPersistence:
    """Handles incident database operations."""

    @staticmethod
    def incident_to_db(incident: Incident) -> dict:
        """Convert Incident model to database-ready dict."""
        return {
            "id": incident.id,
            "created_at": incident.created_at,
            "updated_at": incident.updated_at,
            "status": incident.status.value,
            "severity": incident.severity.value,
            "title": incident.title,
            "description": incident.description,
            "resolution_summary": incident.resolution_summary,
            "resolved_at": incident.resolved_at,
            "logs_json": json.dumps([l.model_dump() for l in incident.logs], default=str),
            "metrics_json": json.dumps([m.model_dump() for m in incident.metrics], default=str),
            "anomaly_json": json.dumps(incident.anomaly.model_dump(), default=str) if incident.anomaly else None,
            "rca_json": json.dumps(incident.rca.model_dump(), default=str) if incident.rca else None,
            "actions_json": json.dumps([a.model_dump() for a in incident.actions_taken], default=str),
            "stability_json": json.dumps([s.model_dump() for s in incident.stability_reports], default=str),
            "agent_runs": str(incident.agent_runs)
        }

    @staticmethod
    def db_to_incident(db_incident: IncidentDB) -> Incident:
        """Convert database record to Incident model."""
        # Parse JSON fields
        logs = []
        if db_incident.logs_json:
            try:
                logs_data = json.loads(db_incident.logs_json)
                logs = [LogEntry(**l) for l in logs_data]
            except (json.JSONDecodeError, Exception):
                pass

        metrics = []
        if db_incident.metrics_json:
            try:
                metrics_data = json.loads(db_incident.metrics_json)
                metrics = [MetricsSnapshot(**m) for m in metrics_data]
            except (json.JSONDecodeError, Exception):
                pass

        anomaly = None
        if db_incident.anomaly_json:
            try:
                anomaly = AnomalyDetection(**json.loads(db_incident.anomaly_json))
            except (json.JSONDecodeError, Exception):
                pass

        rca = None
        if db_incident.rca_json:
            try:
                rca = RCAResult(**json.loads(db_incident.rca_json))
            except (json.JSONDecodeError, Exception):
                pass

        actions_taken = []
        if db_incident.actions_json:
            try:
                actions_data = json.loads(db_incident.actions_json)
                actions_taken = [RecoveryAction(**a) for a in actions_data]
            except (json.JSONDecodeError, Exception):
                pass

        stability_reports = []
        if db_incident.stability_json:
            try:
                stability_data = json.loads(db_incident.stability_json)
                stability_reports = [StabilityReport(**s) for s in stability_data]
            except (json.JSONDecodeError, Exception):
                pass

        return Incident(
            id=db_incident.id,
            created_at=db_incident.created_at,
            updated_at=db_incident.updated_at,
            status=IncidentStatus(db_incident.status),
            severity=IncidentSeverity(db_incident.severity),
            title=db_incident.title or "",
            description=db_incident.description or "",
            resolution_summary=db_incident.resolution_summary,
            resolved_at=db_incident.resolved_at,
            logs=logs,
            metrics=metrics,
            anomaly=anomaly,
            rca=rca,
            actions_taken=actions_taken,
            stability_reports=stability_reports,
            agent_runs=int(db_incident.agent_runs or 0)
        )

    @staticmethod
    async def save_incident(db: AsyncSession, incident: Incident) -> None:
        """Save or update an incident in the database."""
        result = await db.execute(
            select(IncidentDB).where(IncidentDB.id == incident.id)
        )
        existing = result.scalar_one_or_none()

        data = IncidentPersistence.incident_to_db(incident)

        if existing:
            # Update existing record
            for key, value in data.items():
                if key != "id":
                    setattr(existing, key, value)
        else:
            # Create new record
            db_incident = IncidentDB(**data)
            db.add(db_incident)

        await db.commit()
        logger.info(f"Incident saved to database: {incident.id}")

    @staticmethod
    async def load_incident(db: AsyncSession, incident_id: str) -> Optional[Incident]:
        """Load an incident from the database."""
        result = await db.execute(
            select(IncidentDB).where(IncidentDB.id == incident_id)
        )
        db_incident = result.scalar_one_or_none()

        if db_incident:
            return IncidentPersistence.db_to_incident(db_incident)
        return None

    @staticmethod
    async def list_incidents(
        db: AsyncSession,
        status: Optional[IncidentStatus] = None,
        limit: int = 50
    ) -> List[Incident]:
        """List incidents from database with optional filtering."""
        query = select(IncidentDB).order_by(desc(IncidentDB.created_at)).limit(limit)

        if status:
            query = query.where(IncidentDB.status == status.value)

        result = await db.execute(query)
        db_incidents = result.scalars().all()

        return [IncidentPersistence.db_to_incident(i) for i in db_incidents]

    @staticmethod
    async def get_active_incidents(db: AsyncSession) -> List[Incident]:
        """Get all non-closed incidents."""
        result = await db.execute(
            select(IncidentDB).where(
                IncidentDB.status.in_(["open", "investigating", "mitigating"])
            ).order_by(desc(IncidentDB.created_at))
        )
        db_incidents = result.scalars().all()
        return [IncidentPersistence.db_to_incident(i) for i in db_incidents]


# Export for convenience
incident_persistence = IncidentPersistence()
