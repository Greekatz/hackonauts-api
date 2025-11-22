"""
Agent Triggering & Re-run Logic
Communicates with the watsonx agent workflow.
"""
import asyncio
from typing import Optional, Dict, Any, List
from datetime import datetime
import httpx

from core import (
    Incident, LogEntry, MetricsSnapshot, AgentRequest, AgentResponse,
    RCAResult, RecoveryAction, IncidentSeverity, config, logger
)
from engines import incident_manager, stability_evaluator


class WatsonXAgentClient:
    """Client for communicating with watsonx Agent API."""

    def __init__(self):
        self.api_key = config.WATSONX_API_KEY
        self.project_id = config.WATSONX_PROJECT_ID
        self.agent_url = config.WATSONX_AGENT_URL
        self.max_retries = config.MAX_AGENT_RETRIES

    async def call_agent(
        self,
        incident_id: str,
        logs: List[LogEntry],
        metrics: List[MetricsSnapshot],
        context: Optional[Dict[str, Any]] = None
    ) -> AgentResponse:
        """Call the watsonx agent with incident context."""

        # Build request payload
        request_data = {
            "incident_id": incident_id,
            "logs": [log.model_dump() for log in logs[-50:]],  # Last 50 logs
            "metrics": [m.model_dump() for m in metrics[-20:]],  # Last 20 snapshots
            "context": context or {},
            "timestamp": datetime.utcnow().isoformat()
        }

        # For datetime serialization
        def serialize_datetime(obj):
            if isinstance(obj, datetime):
                return obj.isoformat()
            raise TypeError(f"Type {type(obj)} not serializable")

        logger.log_agent_request(incident_id, {
            "log_count": len(logs),
            "metric_count": len(metrics)
        })

        try:
            async with httpx.AsyncClient(timeout=120.0) as client:
                response = await client.post(
                    self.agent_url,
                    json=request_data,
                    headers={
                        "Authorization": f"Bearer {self.api_key}",
                        "Content-Type": "application/json",
                        "X-Project-ID": self.project_id
                    }
                )

                if response.status_code != 200:
                    logger.error(f"Agent API error: {response.status_code}", {
                        "response": response.text[:500]
                    })
                    return AgentResponse(
                        incident_id=incident_id,
                        summary=f"Agent API error: {response.status_code}",
                        system_ok=False
                    )

                result = response.json()
                return self._parse_agent_response(incident_id, result)

        except httpx.TimeoutException:
            logger.error("Agent API timeout")
            return AgentResponse(
                incident_id=incident_id,
                summary="Agent API timeout",
                system_ok=False
            )
        except Exception as e:
            logger.error(f"Agent API exception: {str(e)}")
            return AgentResponse(
                incident_id=incident_id,
                summary=f"Agent error: {str(e)}",
                system_ok=False,
                raw_response=str(e)
            )

    def _parse_agent_response(self, incident_id: str, result: Dict[str, Any]) -> AgentResponse:
        """Parse the agent's response into structured format."""
        try:
            # Extract RCA
            rca = None
            if "rca" in result or "root_cause" in result:
                rca_data = result.get("rca", {})
                rca = RCAResult(
                    root_cause=rca_data.get("root_cause", result.get("root_cause", "")),
                    contributing_factors=rca_data.get("contributing_factors", []),
                    evidence=rca_data.get("evidence", []),
                    confidence=rca_data.get("confidence", 0.5)
                )

            # Extract recommended actions
            actions = []
            for action_data in result.get("recommended_actions", result.get("actions", [])):
                if isinstance(action_data, str):
                    actions.append(RecoveryAction(
                        action_type="suggested",
                        description=action_data,
                        automated=False
                    ))
                elif isinstance(action_data, dict):
                    actions.append(RecoveryAction(
                        action_type=action_data.get("type", action_data.get("action_type", "suggested")),
                        description=action_data.get("description", str(action_data)),
                        parameters=action_data.get("parameters", {}),
                        automated=action_data.get("automated", False)
                    ))

            # Extract system status
            system_ok = result.get("system_ok", result.get("is_stable", False))
            if isinstance(system_ok, str):
                system_ok = system_ok.lower() in ["true", "yes", "ok", "stable"]

            response = AgentResponse(
                incident_id=incident_id,
                rca=rca,
                recommended_actions=actions,
                summary=result.get("summary", result.get("message", "")),
                system_ok=system_ok,
                confidence=result.get("confidence", 0.5),
                raw_response=str(result)
            )

            logger.log_agent_response(incident_id, {
                "has_rca": rca is not None,
                "action_count": len(actions),
                "system_ok": system_ok
            }, success=True)

            return response

        except Exception as e:
            logger.error(f"Failed to parse agent response: {str(e)}", {"raw": str(result)[:500]})
            return AgentResponse(
                incident_id=incident_id,
                summary=f"Failed to parse response: {str(e)}",
                system_ok=False,
                raw_response=str(result)
            )


class AgentOrchestrator:
    """Orchestrates agent calls with re-run logic."""

    def __init__(self):
        self.client = WatsonXAgentClient()
        self.max_retries = config.MAX_AGENT_RETRIES
        self.check_interval = config.STABILITY_CHECK_INTERVAL

    async def run_rca_workflow(
        self,
        incident_id: str,
        force: bool = False
    ) -> AgentResponse:
        """Run the full RCA workflow with stability checks and re-runs."""

        incident = incident_manager.get_incident(incident_id)
        if not incident:
            return AgentResponse(
                incident_id=incident_id,
                summary="Incident not found",
                system_ok=False
            )

        run_count = 0
        final_response = None

        while run_count < self.max_retries:
            run_count += 1
            incident_manager.increment_agent_runs(incident_id)

            logger.info(f"Starting agent run {run_count}/{self.max_retries} for incident {incident_id}")

            # Call the agent
            response = await self.client.call_agent(
                incident_id=incident_id,
                logs=incident.logs,
                metrics=incident.metrics,
                context={
                    "run_number": run_count,
                    "previous_actions": [a.model_dump() for a in incident.actions_taken],
                    "severity": incident.severity.value
                }
            )

            final_response = response

            # Update incident with results
            if response.rca:
                incident_manager.set_rca(incident_id, response.rca)

            for action in response.recommended_actions:
                incident_manager.add_recommended_action(incident_id, action)

            # Check if system is now OK
            if response.system_ok:
                logger.info(f"Agent reports system OK after run {run_count}")

                # Verify with stability check
                stability_report = stability_evaluator.evaluate(
                    metrics=incident.metrics[-1] if incident.metrics else None,
                    logs=incident.logs,
                    llm_judgment="ok" if response.system_ok else "not ok"
                )

                incident_manager.add_stability_report(incident_id, stability_report)

                if stability_report.is_stable:
                    logger.info(f"System confirmed stable - ending workflow")
                    incident_manager.resolve_incident(
                        incident_id,
                        summary=response.summary or "System stabilized"
                    )
                    break

            # Wait before next run
            if run_count < self.max_retries:
                logger.info(f"Waiting {self.check_interval}s before next stability check")
                await asyncio.sleep(self.check_interval)

                # Check if we should re-run
                if not stability_evaluator.should_rerun_agent():
                    logger.info("Stability check passed - no re-run needed")
                    break

        return final_response or AgentResponse(
            incident_id=incident_id,
            summary="Workflow completed",
            system_ok=False
        )

    async def force_rca(
        self,
        logs: Optional[List[LogEntry]] = None,
        metrics: Optional[List[MetricsSnapshot]] = None,
        description: Optional[str] = None
    ) -> AgentResponse:
        """Force an RCA run without anomaly detection."""

        # Create a new incident
        incident = incident_manager.create_incident(
            title=description or "Manual RCA Request",
            description=description or "Forced RCA triggered by operator",
            severity=IncidentSeverity.MEDIUM,
            logs=logs,
            metrics=metrics
        )

        logger.info(f"Force RCA initiated - incident {incident.id}")

        # Run single agent call (no loop for forced RCA)
        response = await self.client.call_agent(
            incident_id=incident.id,
            logs=logs or [],
            metrics=metrics or [],
            context={"forced": True}
        )

        if response.rca:
            incident_manager.set_rca(incident.id, response.rca)

        return response


# Global instances
agent_client = WatsonXAgentClient()
agent_orchestrator = AgentOrchestrator()
