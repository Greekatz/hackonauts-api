"""
State Management / Incident Context
Keeps track of incidents across multiple re-runs.
"""
from typing import Dict, List, Optional, Any
from datetime import datetime
import uuid

from core import (
    Incident, IncidentStatus, IncidentSeverity, LogEntry, MetricsSnapshot,
    RCAResult, RecoveryAction, StabilityReport, AnomalyDetection, logger
)


class IncidentManager:
    """Manages incident lifecycle and state."""

    def __init__(self):
        self.incidents: Dict[str, Incident] = {}
        self.active_incident_id: Optional[str] = None

    def create_incident(
        self,
        title: str,
        description: str = "",
        severity: IncidentSeverity = IncidentSeverity.MEDIUM,
        anomaly: Optional[AnomalyDetection] = None,
        logs: Optional[List[LogEntry]] = None,
        metrics: Optional[List[MetricsSnapshot]] = None
    ) -> Incident:
        """Create a new incident."""
        incident = Incident(
            title=title,
            description=description,
            severity=severity,
            anomaly=anomaly,
            logs=logs or [],
            metrics=metrics or [],
            status=IncidentStatus.OPEN
        )

        self.incidents[incident.id] = incident
        self.active_incident_id = incident.id

        logger.info(f"Incident created: {incident.id}", {
            "title": title,
            "severity": severity.value
        })

        return incident

    def get_incident(self, incident_id: str) -> Optional[Incident]:
        """Get an incident by ID."""
        return self.incidents.get(incident_id)

    def get_active_incident(self) -> Optional[Incident]:
        """Get the currently active incident."""
        if self.active_incident_id:
            return self.incidents.get(self.active_incident_id)
        return None

    def update_incident(self, incident_id: str, **updates) -> Optional[Incident]:
        """Update incident fields."""
        incident = self.incidents.get(incident_id)
        if not incident:
            return None

        for key, value in updates.items():
            if hasattr(incident, key):
                setattr(incident, key, value)

        incident.updated_at = datetime.utcnow()
        return incident

    def add_logs(self, incident_id: str, logs: List[LogEntry]) -> bool:
        """Add logs to an incident."""
        incident = self.incidents.get(incident_id)
        if not incident:
            return False

        incident.logs.extend(logs)
        incident.updated_at = datetime.utcnow()
        return True

    def add_metrics(self, incident_id: str, metrics: List[MetricsSnapshot]) -> bool:
        """Add metrics to an incident."""
        incident = self.incidents.get(incident_id)
        if not incident:
            return False

        incident.metrics.extend(metrics)
        incident.updated_at = datetime.utcnow()
        return True

    def set_rca(self, incident_id: str, rca: RCAResult) -> bool:
        """Set RCA result for an incident."""
        incident = self.incidents.get(incident_id)
        if not incident:
            return False

        incident.rca = rca
        incident.status = IncidentStatus.INVESTIGATING
        incident.updated_at = datetime.utcnow()

        logger.info(f"RCA set for incident {incident_id}", {
            "root_cause": rca.root_cause[:100]
        })
        return True

    def add_recommended_action(self, incident_id: str, action: RecoveryAction) -> bool:
        """Add a recommended action to an incident."""
        incident = self.incidents.get(incident_id)
        if not incident:
            return False

        incident.recommended_actions.append(action)
        incident.updated_at = datetime.utcnow()
        return True

    def record_action_taken(self, incident_id: str, action: RecoveryAction) -> bool:
        """Record an action that was executed."""
        incident = self.incidents.get(incident_id)
        if not incident:
            return False

        action.executed = True
        action.executed_at = datetime.utcnow()
        incident.actions_taken.append(action)
        incident.status = IncidentStatus.MITIGATING
        incident.updated_at = datetime.utcnow()

        logger.log_autoheal_action(
            action=action.action_type,
            service=action.parameters.get("service", "unknown"),
            success=True,
            details=action.result
        )
        return True

    def add_stability_report(self, incident_id: str, report: StabilityReport) -> bool:
        """Add a stability report to an incident."""
        incident = self.incidents.get(incident_id)
        if not incident:
            return False

        incident.stability_reports.append(report)
        incident.updated_at = datetime.utcnow()
        return True

    def increment_agent_runs(self, incident_id: str) -> int:
        """Increment and return the agent run count."""
        incident = self.incidents.get(incident_id)
        if not incident:
            return 0

        incident.agent_runs += 1
        incident.updated_at = datetime.utcnow()
        return incident.agent_runs

    def resolve_incident(self, incident_id: str, summary: str) -> bool:
        """Mark an incident as resolved."""
        incident = self.incidents.get(incident_id)
        if not incident:
            return False

        incident.status = IncidentStatus.RESOLVED
        incident.resolution_summary = summary
        incident.resolved_at = datetime.utcnow()
        incident.updated_at = datetime.utcnow()

        if self.active_incident_id == incident_id:
            self.active_incident_id = None

        logger.info(f"Incident resolved: {incident_id}", {
            "summary": summary[:100]
        })
        return True

    def close_incident(self, incident_id: str) -> bool:
        """Mark an incident as closed."""
        incident = self.incidents.get(incident_id)
        if not incident:
            return False

        incident.status = IncidentStatus.CLOSED
        incident.updated_at = datetime.utcnow()

        if self.active_incident_id == incident_id:
            self.active_incident_id = None

        return True

    def get_incident_summary(self, incident_id: str) -> Dict[str, Any]:
        """Get a summary of an incident for reporting."""
        incident = self.incidents.get(incident_id)
        if not incident:
            return {}

        return {
            "id": incident.id,
            "title": incident.title,
            "status": incident.status.value,
            "severity": incident.severity.value,
            "created_at": incident.created_at.isoformat(),
            "updated_at": incident.updated_at.isoformat(),
            "duration_minutes": (
                (incident.resolved_at or datetime.utcnow()) - incident.created_at
            ).total_seconds() / 60,
            "root_cause": incident.rca.root_cause if incident.rca else None,
            "actions_taken": len(incident.actions_taken),
            "agent_runs": incident.agent_runs,
            "stability_trend": self._get_stability_trend(incident),
            "resolution_summary": incident.resolution_summary,
        }

    def _get_stability_trend(self, incident: Incident) -> str:
        """Get stability trend from incident reports."""
        if not incident.stability_reports:
            return "unknown"

        recent = incident.stability_reports[-5:]
        stable_count = sum(1 for r in recent if r.is_stable)

        if stable_count == len(recent):
            return "stable"
        elif stable_count == 0:
            return "critical"
        elif stable_count > len(recent) / 2:
            return "improving"
        else:
            return "degrading"

    def list_incidents(
        self,
        status: Optional[IncidentStatus] = None,
        limit: int = 50
    ) -> List[Incident]:
        """List incidents with optional filtering."""
        incidents = list(self.incidents.values())

        if status:
            incidents = [i for i in incidents if i.status == status]

        # Sort by created_at descending
        incidents.sort(key=lambda x: x.created_at, reverse=True)

        return incidents[:limit]

    def get_history(self, incident_id: str) -> List[Dict[str, Any]]:
        """Get full history of an incident for final summary."""
        incident = self.incidents.get(incident_id)
        if not incident:
            return []

        history = []

        # Add creation event
        history.append({
            "timestamp": incident.created_at.isoformat(),
            "event": "incident_created",
            "details": {"title": incident.title, "severity": incident.severity.value}
        })

        # Add RCA if available
        if incident.rca:
            history.append({
                "timestamp": incident.updated_at.isoformat(),
                "event": "rca_completed",
                "details": {
                    "root_cause": incident.rca.root_cause,
                    "factors": incident.rca.contributing_factors
                }
            })

        # Add actions taken
        for action in incident.actions_taken:
            history.append({
                "timestamp": action.executed_at.isoformat() if action.executed_at else None,
                "event": "action_executed",
                "details": {
                    "type": action.action_type,
                    "description": action.description,
                    "result": action.result
                }
            })

        # Add stability reports
        for report in incident.stability_reports:
            history.append({
                "timestamp": report.timestamp.isoformat(),
                "event": "stability_check",
                "details": {
                    "is_stable": report.is_stable,
                    "details": report.details
                }
            })

        # Sort by timestamp
        history.sort(key=lambda x: x["timestamp"] or "")

        return history


# Global incident manager instance
incident_manager = IncidentManager()
