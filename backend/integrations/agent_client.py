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
    """Client for communicating with watsonx Orchestrate Agent API."""

    def __init__(self):
        self.api_key = config.WATSONX_API_KEY
        self.agent_url = config.WATSONX_URL
        self.max_retries = config.MAX_AGENT_RETRIES
        self._access_token = None
        self._token_expires = None

    async def _get_access_token(self) -> str:
        """Get IAM access token from API key."""
        # Check if we have a valid cached token
        if self._access_token and self._token_expires and datetime.utcnow() < self._token_expires:
            return self._access_token

        try:
            async with httpx.AsyncClient(timeout=30.0) as client:
                response = await client.post(
                    "https://iam.cloud.ibm.com/identity/token",
                    headers={"Content-Type": "application/x-www-form-urlencoded"},
                    data={
                        "grant_type": "urn:ibm:params:oauth:grant-type:apikey",
                        "apikey": self.api_key
                    }
                )

                if response.status_code == 200:
                    data = response.json()
                    self._access_token = data.get("access_token")
                    # Token typically valid for 1 hour, refresh at 50 min
                    from datetime import timedelta
                    self._token_expires = datetime.utcnow() + timedelta(minutes=50)
                    return self._access_token
                else:
                    logger.error(f"Failed to get IAM token: {response.status_code}")
                    return ""
        except Exception as e:
            logger.error(f"IAM token error: {str(e)}")
            return ""

    def _build_prompt(
        self,
        logs: List[LogEntry],
        metrics: List[MetricsSnapshot],
        context: Optional[Dict[str, Any]] = None
    ) -> str:
        """Build the prompt for the agent."""
        prompt_parts = ["Analyze the following incident data and provide root cause analysis:\n"]

        # Add logs
        if logs:
            prompt_parts.append("\n## Error Logs:")
            for log in logs[-30:]:  # Last 30 logs
                prompt_parts.append(f"- {log.timestamp} [{log.level.value.upper()}] {log.message}")

        # Add metrics
        if metrics:
            prompt_parts.append("\n\n## System Metrics:")
            for m in metrics[-10:]:  # Last 10 snapshots
                parts = []
                if m.cpu_percent is not None:
                    parts.append(f"CPU: {m.cpu_percent}%")
                if m.memory_percent is not None:
                    parts.append(f"Memory: {m.memory_percent}%")
                if m.latency_ms is not None:
                    parts.append(f"Latency: {m.latency_ms}ms")
                if m.error_rate is not None:
                    parts.append(f"Error Rate: {m.error_rate*100:.1f}%")
                if parts:
                    prompt_parts.append(f"- {m.timestamp}: {', '.join(parts)}")

        # Add context
        if context:
            prompt_parts.append(f"\n\n## Additional Context:")
            for key, value in context.items():
                prompt_parts.append(f"- {key}: {value}")

        prompt_parts.append("\n\nProvide:")
        prompt_parts.append("1. Root cause analysis")
        prompt_parts.append("2. Contributing factors")
        prompt_parts.append("3. Recommended actions to resolve")
        prompt_parts.append("4. Assessment of current system stability")

        return "\n".join(prompt_parts)

    async def call_agent(
        self,
        incident_id: str,
        logs: List[LogEntry],
        metrics: List[MetricsSnapshot],
        context: Optional[Dict[str, Any]] = None
    ) -> AgentResponse:
        """Call the watsonx Orchestrate agent with incident context."""

        if not self.agent_url:
            logger.error("WATSONX_URL not configured")
            return AgentResponse(
                incident_id=incident_id,
                summary="watsonx agent not configured",
                system_ok=False
            )

        # Get access token
        access_token = await self._get_access_token()
        if not access_token:
            return AgentResponse(
                incident_id=incident_id,
                summary="Failed to authenticate with watsonx",
                system_ok=False
            )

        # Build the prompt
        prompt = self._build_prompt(logs, metrics, context)

        # Build request payload (OpenAI-compatible chat completions format)
        request_data = {
            "messages": [
                {"role": "user", "content": prompt}
            ],
            "stream": False
        }

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
                        "Authorization": f"Bearer {access_token}",
                        "Content-Type": "application/json",
                        "Accept": "application/json"
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
        """Parse the watsonx Orchestrate chat completions response."""
        try:
            # Extract the message content from chat completions format
            content = ""
            if "choices" in result:
                for choice in result.get("choices", []):
                    msg = choice.get("message", {})
                    content = msg.get("content", "")
                    if content:
                        break

            # If no choices, check for direct content
            if not content:
                content = result.get("content", result.get("response", str(result)))

            # Parse the text response to extract structured data
            content_lower = content.lower()

            # Extract root cause from response text
            root_cause = content
            contributing_factors = []
            evidence = []

            # Try to identify key sections in the response
            if "root cause" in content_lower:
                # Extract text after "root cause"
                idx = content_lower.find("root cause")
                root_cause = content[idx:idx+500].split("\n")[0:3]
                root_cause = " ".join(root_cause).strip()

            # Look for contributing factors
            if "contributing" in content_lower or "factors" in content_lower:
                contributing_factors = ["See full analysis in response"]

            # Look for recommended actions
            actions = []
            action_keywords = ["restart", "scale", "increase", "decrease", "clear", "flush", "rollback", "check", "monitor"]
            for keyword in action_keywords:
                if keyword in content_lower:
                    actions.append(RecoveryAction(
                        action_type="suggested",
                        description=f"Consider: {keyword} related action (see full response)",
                        automated=False
                    ))

            # Determine system status from response
            system_ok = False
            ok_indicators = ["stable", "resolved", "fixed", "normal", "healthy", "recovered"]
            not_ok_indicators = ["critical", "failure", "down", "exhausted", "timeout", "error"]

            for indicator in ok_indicators:
                if indicator in content_lower:
                    system_ok = True
                    break

            for indicator in not_ok_indicators:
                if indicator in content_lower:
                    system_ok = False
                    break

            # Build RCA result
            rca = RCAResult(
                root_cause=root_cause[:500] if len(root_cause) > 500 else root_cause,
                contributing_factors=contributing_factors,
                evidence=evidence,
                confidence=0.7
            )

            response = AgentResponse(
                incident_id=incident_id,
                rca=rca,
                recommended_actions=actions[:5],  # Limit to 5 actions
                summary=content[:1000] if len(content) > 1000 else content,
                system_ok=system_ok,
                confidence=0.7,
                raw_response=content
            )

            logger.log_agent_response(incident_id, {
                "has_rca": True,
                "action_count": len(actions),
                "system_ok": system_ok,
                "response_length": len(content)
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
