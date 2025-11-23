"""
Agent Triggering & Re-run Logic
Communicates with the watsonx agent workflow and executes recommended actions.
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


# =============================================================================
# Action Mapping - Maps agent keywords to executable HealingActions
# =============================================================================

# Import here to avoid circular import at module level
def _get_autoheal_executor():
    from integrations.autoheal import autoheal_executor, HealingAction
    return autoheal_executor, HealingAction


# Map keywords in agent response to HealingAction types
ACTION_KEYWORD_MAP = {
    # Restart actions
    "restart": "restart_service",
    "reboot": "restart_service",
    "restart service": "restart_service",
    # Scale actions
    "scale": "scale_replicas",
    "scale up": "scale_replicas",
    "increase replica": "scale_replicas",
    "add instance": "scale_replicas",
    # Cache actions
    "clear cache": "flush_cache",
    "flush cache": "flush_cache",
    "invalidate cache": "flush_cache",
    # Queue actions
    "clear queue": "clear_queue",
    "purge queue": "clear_queue",
    "drain queue": "clear_queue",
    # Traffic actions
    "reroute": "reroute_traffic",
    "redirect traffic": "reroute_traffic",
    "failover": "reroute_traffic",
    # Rollback actions
    "rollback": "rollback_deployment",
    "revert": "rollback_deployment",
    "previous version": "rollback_deployment",
    # Disk actions
    "clear disk": "clear_disk",
    "free disk": "clear_disk",
    "delete logs": "clear_disk",
    "clean logs": "clear_disk",
}


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

    def _build_monitoring_prompt(
        self,
        logs: List[LogEntry],
        metrics: List[MetricsSnapshot]
    ) -> str:
        """
        Build prompt for continuous monitoring - detects anomalies AND provides fix.

        The LLM should:
        1. Analyze logs/metrics for ANY issues
        2. If issue found: return anomaly=true with cause and fix
        3. If no issue: return anomaly=false
        """
        prompt_parts = [
            "Analyze the system monitoring data below and provide your assessment.",
            "",
            "Be CONSERVATIVE - only report problems for CLEAR, SIGNIFICANT issues:",
            "- ERROR or CRITICAL log messages indicating actual failures",
            "- Severe resource exhaustion (very high CPU/memory)",
            "- Service outages, crashes, or connection failures",
            "- Sustained high error rates",
            "",
            "Do NOT flag normal operational variation. INFO and DEBUG logs are normal.",
            "",
            "Provide your response as a JSON object with these fields:",
            "- anomaly_detected: boolean (true only if real problem found)",
            "- severity: string (low, medium, high, or critical) - only if anomaly_detected is true",
            "- title: string (brief issue title) - only if anomaly_detected is true",
            "- root_cause: string (what is causing the problem) - only if anomaly_detected is true",
            "- contributing_factors: array of strings - only if anomaly_detected is true",
            "- recommended_actions: array of objects with action, service, reason - only if anomaly_detected is true",
            "- summary: string (brief summary of findings)",
            "",
            "Valid action types: restart_service, scale_replicas, flush_cache, clear_queue, rollback_deployment, clear_disk",
            "",
        ]

        # Add metrics
        if metrics:
            prompt_parts.append("## Current System Metrics:")
            for m in metrics[-5:]:
                parts = []
                if m.cpu_percent is not None:
                    parts.append(f"CPU: {m.cpu_percent}%")
                if m.memory_percent is not None:
                    parts.append(f"Memory: {m.memory_percent}%")
                if m.latency_ms is not None:
                    parts.append(f"Latency: {m.latency_ms}ms")
                if m.error_rate is not None:
                    parts.append(f"Error Rate: {m.error_rate*100:.1f}%")
                if m.throughput is not None:
                    parts.append(f"Throughput: {m.throughput}")
                if parts:
                    prompt_parts.append(f"  - {m.timestamp}: {', '.join(parts)}")

        # Add logs
        if logs:
            prompt_parts.append("\n## Recent Logs:")
            for log in logs[-30:]:
                prompt_parts.append(f"  - [{log.level.value.upper()}] {log.timestamp}: {log.message[:200]}")

        prompt_parts.append("\nRemember: Output ONLY valid JSON. No other text.")

        return "\n".join(prompt_parts)

    def _build_prompt(
        self,
        logs: List[LogEntry],
        metrics: List[MetricsSnapshot],
        context: Optional[Dict[str, Any]] = None
    ) -> str:
        """Build the prompt for RCA (legacy - used when incident already exists)."""
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

    async def monitor_system(
        self,
        logs: List[LogEntry],
        metrics: List[MetricsSnapshot],
        max_retries: int = 3
    ) -> Optional[Dict[str, Any]]:
        """
        Call the LLM to monitor system health. Retries if JSON parsing fails.

        Returns:
            Dict with anomaly info if detected, None if system is healthy
            {
                "anomaly_detected": True,
                "severity": "high",
                "title": "...",
                "root_cause": "...",
                "contributing_factors": [...],
                "recommended_actions": [...],
                "summary": "..."
            }
        """
        if not self.agent_url:
            logger.warning("WATSONX_URL not configured, skipping LLM monitoring")
            return None

        # Get access token
        access_token = await self._get_access_token()
        if not access_token:
            logger.error("Failed to authenticate with watsonx for monitoring")
            return None

        # Build monitoring prompt
        prompt = self._build_monitoring_prompt(logs, metrics)

        request_data = {
            "messages": [
                {"role": "user", "content": prompt}
            ],
            "stream": False
        }

        for attempt in range(1, max_retries + 1):
            logger.info(f"Sending monitoring request to watsonx (attempt {attempt}/{max_retries}, logs={len(logs)}, metrics={len(metrics)})")

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
                        logger.error(f"Monitoring API error: {response.status_code}")
                        if attempt < max_retries:
                            await asyncio.sleep(2)
                            continue
                        return None

                    result = response.json()
                    parsed = self._parse_monitoring_response(result)

                    # If parsing failed (returned None but we got a response), retry
                    if parsed is None:
                        content = self._extract_content(result)
                        # Check if it was a parse failure vs. genuinely healthy system
                        if content and self._is_parse_failure(content):
                            logger.warning(f"Failed to parse LLM response, retrying... (attempt {attempt}/{max_retries})")
                            if attempt < max_retries:
                                await asyncio.sleep(2)
                                continue

                    return parsed

            except httpx.TimeoutException:
                logger.error(f"Monitoring API timeout (attempt {attempt}/{max_retries})")
                if attempt < max_retries:
                    await asyncio.sleep(2)
                    continue
                return None
            except Exception as e:
                logger.error(f"Monitoring API exception: {str(e)}")
                if attempt < max_retries:
                    await asyncio.sleep(2)
                    continue
                return None

        return None

    def _is_parse_failure(self, content: str) -> bool:
        """Check if the response indicates a parse failure vs. healthy system."""
        content_lower = content.lower()

        # LLM error indicators - these should trigger retry
        error_indicators = [
            "i have encountered an error",
            "invalid tool call",
            "please try again",
            "i cannot process",
            "i cannot",
            "i'm unable",
            "as an ai",
        ]

        for indicator in error_indicators:
            if indicator in content_lower:
                return True

        return False

    def _parse_monitoring_response(self, result: Dict[str, Any]) -> Optional[Dict[str, Any]]:
        """Parse the monitoring response from watsonx."""
        try:
            content = self._extract_content(result)
            if not content:
                return None

            import re
            import json

            # Try to extract JSON from the response
            json_str = None

            # Method 1: Look for ```json``` code blocks
            json_match = re.search(r'```json\s*(.*?)\s*```', content, re.DOTALL)
            if json_match:
                json_str = json_match.group(1)

            # Method 2: Look for raw JSON object
            if not json_str:
                json_match = re.search(r'\{[^{}]*(?:\{[^{}]*\}[^{}]*)*\}', content, re.DOTALL)
                if json_match:
                    json_str = json_match.group(0)

            # Try to parse JSON if found
            if json_str:
                try:
                    data = json.loads(json_str)

                    # Check if anomaly detected
                    if not data.get("anomaly_detected", False):
                        logger.debug("LLM reports system healthy (JSON)")
                        return None

                    # Return the anomaly data
                    return {
                        "anomaly_detected": True,
                        "severity": data.get("severity", "medium"),
                        "title": data.get("title", "Issue detected"),
                        "root_cause": data.get("root_cause", "Unknown"),
                        "contributing_factors": data.get("contributing_factors", []),
                        "recommended_actions": data.get("recommended_actions", []),
                        "summary": data.get("summary", content[:500])
                    }
                except json.JSONDecodeError:
                    logger.warning("JSON found but failed to parse, falling back to text analysis")

            # Fallback: Parse plain text response for anomaly indicators
            return self._parse_plain_text_monitoring(content)

        except Exception as e:
            logger.error(f"Failed to parse monitoring response: {str(e)}")
            return None

    def _parse_plain_text_monitoring(self, content: str) -> Optional[Dict[str, Any]]:
        """
        Fallback parser for when LLM returns plain text instead of JSON.
        Extracts anomaly info from natural language response.
        """
        content_lower = content.lower()

        # Check for LLM error messages - don't treat as system anomaly
        llm_error_indicators = [
            "i have encountered an error",
            "invalid tool call",
            "please try again",
            "i cannot",
            "i'm unable",
            "as an ai",
        ]

        for indicator in llm_error_indicators:
            if indicator in content_lower:
                logger.warning(f"LLM returned error message, not system analysis: {content[:100]}")
                return None

        # Check for "no issues" indicators - system is healthy
        healthy_indicators = [
            "no issues", "no anomal", "system is healthy", "everything looks normal",
            "no problems", "operating normally", "all clear", "no errors detected",
            "system healthy", "looks good", "no concerns"
        ]

        for indicator in healthy_indicators:
            if indicator in content_lower:
                logger.debug(f"LLM reports system healthy (text: '{indicator}')")
                return None

        # Check for problem indicators
        problem_indicators = [
            "error", "issue", "problem", "failure", "anomaly", "high cpu",
            "high memory", "timeout", "crash", "exception", "degraded",
            "spike", "elevated", "critical", "warning", "alert"
        ]

        has_problem = any(ind in content_lower for ind in problem_indicators)

        if not has_problem:
            logger.debug("No problem indicators found in text response")
            return None

        # Extract severity from text
        severity = "medium"
        if "critical" in content_lower:
            severity = "critical"
        elif "high" in content_lower or "severe" in content_lower:
            severity = "high"
        elif "low" in content_lower or "minor" in content_lower:
            severity = "low"

        # Extract a title from the first sentence
        first_sentence = content.split(".")[0].strip()
        title = first_sentence[:100] if first_sentence else "Issue detected from analysis"

        # Try to identify recommended actions from text
        actions = []
        for keyword, action_type in ACTION_KEYWORD_MAP.items():
            if keyword in content_lower:
                # Try to find associated service
                service = self._extract_service_from_context(content)
                actions.append({
                    "action": action_type,
                    "service": service,
                    "reason": f"Extracted from analysis: {keyword}"
                })
                break  # Just get the first matching action

        logger.info(f"Parsed plain text response as anomaly (severity={severity})")

        return {
            "anomaly_detected": True,
            "severity": severity,
            "title": title,
            "root_cause": content[:500],  # Use the full text as root cause
            "contributing_factors": [],
            "recommended_actions": actions,
            "summary": content[:500]
        }

    async def call_agent(
        self,
        incident_id: str,
        logs: List[LogEntry],
        metrics: List[MetricsSnapshot],
        context: Optional[Dict[str, Any]] = None
    ) -> AgentResponse:
        """Call the watsonx Orchestrate agent with incident context (legacy)."""

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
            content = self._extract_content(result)

            if not content:
                return AgentResponse(
                    incident_id=incident_id,
                    summary="Empty response from agent",
                    system_ok=False,
                    raw_response=str(result)
                )

            # Parse structured sections from response
            root_cause = self._extract_section(content, ["root cause", "root-cause", "primary cause", "main issue"])
            contributing_factors = self._extract_list_section(content, ["contributing factors", "contributing", "factors", "related issues"])
            evidence = self._extract_list_section(content, ["evidence", "indicators", "symptoms"])
            recommended_actions = self._extract_actions(content)

            # Determine system status
            system_ok = self._assess_system_status(content)

            # Calculate confidence based on response quality
            confidence = self._calculate_confidence(root_cause, contributing_factors, recommended_actions)

            # Build RCA result
            rca = RCAResult(
                root_cause=root_cause[:500] if root_cause else "See full analysis",
                contributing_factors=contributing_factors[:5],
                evidence=evidence[:5],
                confidence=confidence
            )

            response = AgentResponse(
                incident_id=incident_id,
                rca=rca,
                recommended_actions=recommended_actions[:5],
                summary=content[:1000] if len(content) > 1000 else content,
                system_ok=system_ok,
                confidence=confidence,
                raw_response=content
            )

            logger.log_agent_response(incident_id, {
                "has_rca": True,
                "action_count": len(recommended_actions),
                "system_ok": system_ok,
                "response_length": len(content),
                "confidence": confidence
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

    def _extract_content(self, result: Dict[str, Any]) -> str:
        """Extract content from various response formats."""
        # OpenAI chat completions format
        if "choices" in result:
            for choice in result.get("choices", []):
                msg = choice.get("message", {})
                content = msg.get("content", "")
                if content:
                    return content

        # Direct content formats
        for key in ["content", "response", "text", "output", "answer"]:
            if key in result and result[key]:
                return str(result[key])

        return str(result)

    def _extract_section(self, content: str, keywords: List[str]) -> str:
        """Extract a section of text following any of the keywords."""
        content_lower = content.lower()

        for keyword in keywords:
            if keyword in content_lower:
                idx = content_lower.find(keyword)
                # Get text after keyword, up to next section or 500 chars
                section_text = content[idx:]
                lines = section_text.split("\n")[0:5]
                extracted = " ".join(lines).strip()
                # Clean up the keyword prefix
                for kw in keywords:
                    if extracted.lower().startswith(kw):
                        extracted = extracted[len(kw):].lstrip(":- ")
                return extracted[:500]

        return ""

    def _extract_list_section(self, content: str, keywords: List[str]) -> List[str]:
        """Extract a bulleted/numbered list section."""
        content_lower = content.lower()
        items = []

        for keyword in keywords:
            if keyword in content_lower:
                idx = content_lower.find(keyword)
                section = content[idx:idx+1000]
                lines = section.split("\n")[1:10]  # Skip header line

                for line in lines:
                    line = line.strip()
                    # Match bullet points or numbered items
                    if line and (line.startswith(("-", "*", "1", "2", "3", "4", "5")) or ":" in line[:30]):
                        clean = line.lstrip("-*0123456789.) ").strip()
                        if clean and len(clean) > 5:
                            items.append(clean[:200])

                if items:
                    break

        return items if items else ["See full analysis in response"]

    def _extract_actions(self, content: str) -> List[RecoveryAction]:
        """Extract recommended actions from response and mark executable ones."""
        actions = []
        content_lower = content.lower()
        seen_types = set()

        # First, check for executable actions (ones we can actually run)
        for keyword, action_type in ACTION_KEYWORD_MAP.items():
            if keyword in content_lower and action_type not in seen_types:
                seen_types.add(action_type)
                idx = content_lower.find(keyword)
                context = content[max(0, idx-30):idx+100].strip()

                # Try to extract service name from context
                service = self._extract_service_from_context(context)

                actions.append(RecoveryAction(
                    action_type=action_type,
                    description=context[:200],
                    automated=True,  # Mark as automatable
                    service=service,
                    parameters={}
                ))

        # Also extract non-executable recommendations
        manual_patterns = {
            "database": "Database maintenance required",
            "connection": "Check network connections",
            "timeout": "Adjust timeout settings",
            "retry": "Implement retry logic",
            "monitor": "Increase monitoring",
            "investigate": "Manual investigation needed",
            "review": "Review configuration",
        }

        for keyword, description in manual_patterns.items():
            if keyword in content_lower and keyword not in seen_types:
                idx = content_lower.find(keyword)
                context = content[max(0, idx-30):idx+100].strip()

                actions.append(RecoveryAction(
                    action_type=keyword,
                    description=f"{description} - {context[:150]}",
                    automated=False  # Not automatable
                ))

        return actions

    def _extract_service_from_context(self, context: str) -> Optional[str]:
        """Try to extract a service name from the context around an action keyword."""
        # Common service name patterns
        import re

        # Look for patterns like "restart api-gateway", "service: user-service"
        patterns = [
            r'(?:restart|scale|service[:\s]+)([a-z][a-z0-9\-_]+)',
            r'([a-z][a-z0-9\-_]+)(?:\s+service)',
            r'the\s+([a-z][a-z0-9\-_]+)',
        ]

        context_lower = context.lower()
        for pattern in patterns:
            match = re.search(pattern, context_lower)
            if match:
                service = match.group(1)
                # Filter out common non-service words
                if service not in ['the', 'a', 'an', 'this', 'that', 'your', 'our', 'service', 'system']:
                    return service

        return None

    def _assess_system_status(self, content: str) -> bool:
        """Determine if system is OK based on response content."""
        content_lower = content.lower()

        # Strong negative indicators (weighted more heavily)
        critical_indicators = ["critical", "failure", "down", "crash", "outage", "unavailable"]
        for indicator in critical_indicators:
            if indicator in content_lower:
                return False

        # Positive indicators
        ok_indicators = ["stable", "resolved", "fixed", "normal", "healthy", "recovered", "operational"]
        ok_count = sum(1 for ind in ok_indicators if ind in content_lower)

        # Negative indicators
        not_ok_indicators = ["error", "issue", "problem", "degraded", "slow", "timeout"]
        not_ok_count = sum(1 for ind in not_ok_indicators if ind in content_lower)

        return ok_count > not_ok_count

    def _calculate_confidence(
        self,
        root_cause: str,
        contributing_factors: List[str],
        actions: List[RecoveryAction]
    ) -> float:
        """Calculate confidence score based on response quality."""
        confidence = 0.5  # Base confidence

        # Root cause quality
        if root_cause and len(root_cause) > 50:
            confidence += 0.15
        if root_cause and len(root_cause) > 100:
            confidence += 0.1

        # Contributing factors
        if contributing_factors and contributing_factors[0] != "See full analysis in response":
            confidence += 0.1

        # Actions identified
        if actions:
            confidence += min(0.15, len(actions) * 0.03)

        return min(0.95, confidence)


class AgentOrchestrator:
    """Orchestrates agent calls with re-run logic and action execution."""

    def __init__(self):
        self.client = WatsonXAgentClient()
        self.max_retries = config.MAX_AGENT_RETRIES
        self.check_interval = config.STABILITY_CHECK_INTERVAL
        self.auto_execute = config.AUTO_EXECUTE_ACTIONS if hasattr(config, 'AUTO_EXECUTE_ACTIONS') else False

    async def run_rca_workflow(
        self,
        incident_id: str,
        auto_execute: Optional[bool] = None
    ) -> AgentResponse:
        """
        Run the full RCA workflow with stability checks and re-runs.

        Args:
            incident_id: The incident to analyze
            auto_execute: Override auto-execution setting (None uses default)

        Returns:
            AgentResponse with RCA and executed actions
        """
        should_execute = auto_execute if auto_execute is not None else self.auto_execute

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

            # Execute recommended actions if enabled
            if should_execute and response.recommended_actions:
                executed = await self._execute_recommended_actions(
                    incident_id,
                    response.recommended_actions
                )
                logger.info(f"Executed {executed} automated actions for incident {incident_id}")

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

    async def _execute_recommended_actions(
        self,
        incident_id: str,
        actions: List[RecoveryAction]
    ) -> int:
        """
        Execute automated actions recommended by the agent.

        Args:
            incident_id: The incident ID for logging
            actions: List of recommended actions

        Returns:
            Number of actions successfully executed
        """
        autoheal_executor, HealingAction = _get_autoheal_executor()
        executed_count = 0

        # Map action_type strings to HealingAction enum
        action_type_map = {
            "restart_service": HealingAction.RESTART_SERVICE,
            "scale_replicas": HealingAction.SCALE_REPLICAS,
            "flush_cache": HealingAction.FLUSH_CACHE,
            "clear_queue": HealingAction.CLEAR_QUEUE,
            "reroute_traffic": HealingAction.REROUTE_TRAFFIC,
            "rollback_deployment": HealingAction.ROLLBACK_DEPLOYMENT,
            "clear_disk": HealingAction.CLEAR_DISK,
        }

        for action in actions:
            # Only execute actions marked as automated
            if not action.automated:
                continue

            healing_action = action_type_map.get(action.action_type)
            if not healing_action:
                logger.debug(f"No executor for action type: {action.action_type}")
                continue

            logger.info(f"Executing action: {action.action_type} for incident {incident_id}")

            try:
                result = await autoheal_executor.execute(
                    action=healing_action,
                    service=getattr(action, 'service', None),
                    parameters=getattr(action, 'parameters', {}),
                    incident_id=incident_id
                )

                if result.get("success"):
                    executed_count += 1
                    action.executed = True
                    action.result = result.get("message")
                    action.executed_at = datetime.utcnow()
                    logger.info(f"Action {action.action_type} succeeded: {result.get('message')}")
                else:
                    logger.warning(f"Action {action.action_type} failed: {result.get('message')}")

            except Exception as e:
                logger.error(f"Error executing action {action.action_type}: {str(e)}")

        return executed_count

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
