"""
Slack App Integration
Full OAuth flow, slash commands, and event handling for multi-workspace support.
"""
import hmac
import hashlib
import time
import json
from typing import Optional, Dict, Any, List
from urllib.parse import urlencode

import httpx
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from core import config, logger


# =============================================================================
# Constants
# =============================================================================

# Severity level to emoji mapping (used across multiple functions)
SEVERITY_EMOJI = {
    "low": ":large_blue_circle:",
    "medium": ":large_yellow_circle:",
    "high": ":large_orange_circle:",
    "critical": ":red_circle:",
}
DEFAULT_SEVERITY_EMOJI = ":white_circle:"

# Slack API constants
SLACK_API_BASE = "https://slack.com/api"
SLACK_OAUTH_URL = "https://slack.com/oauth/v2/authorize"

# Request verification
TIMESTAMP_MAX_AGE_SECONDS = 300  # 5 minutes
CHANNEL_FETCH_LIMIT = 200

# Display limits
MAX_ERRORS_DISPLAY = 5
MAX_DESCRIPTION_LENGTH = 500
MAX_RCA_LENGTH = 500


def get_severity_emoji(severity: str) -> str:
    """Get emoji for a severity level."""
    return SEVERITY_EMOJI.get(severity.lower(), DEFAULT_SEVERITY_EMOJI)


# =============================================================================
# Slack Block Kit Builder
# =============================================================================

class SlackBlockBuilder:
    """Helper class for building Slack Block Kit blocks."""

    @staticmethod
    def header(text: str, emoji: bool = True) -> Dict[str, Any]:
        """Create a header block."""
        return {
            "type": "header",
            "text": {"type": "plain_text", "text": text, "emoji": emoji}
        }

    @staticmethod
    def section(text: str, markdown: bool = True) -> Dict[str, Any]:
        """Create a section block with text."""
        return {
            "type": "section",
            "text": {"type": "mrkdwn" if markdown else "plain_text", "text": text}
        }

    @staticmethod
    def section_fields(fields: List[Dict[str, str]]) -> Dict[str, Any]:
        """Create a section block with fields."""
        return {
            "type": "section",
            "fields": [{"type": "mrkdwn", "text": f"*{f['label']}:*\n{f['value']}"} for f in fields]
        }

    @staticmethod
    def divider() -> Dict[str, Any]:
        """Create a divider block."""
        return {"type": "divider"}

    @staticmethod
    def context(text: str) -> Dict[str, Any]:
        """Create a context block."""
        return {
            "type": "context",
            "elements": [{"type": "mrkdwn", "text": text}]
        }

    @staticmethod
    def button(text: str, action_id: str, value: str = "", style: Optional[str] = None) -> Dict[str, Any]:
        """Create a button element."""
        btn = {
            "type": "button",
            "text": {"type": "plain_text", "text": text},
            "action_id": action_id,
            "value": value
        }
        if style:
            btn["style"] = style
        return btn

    @staticmethod
    def actions(buttons: List[Dict[str, Any]]) -> Dict[str, Any]:
        """Create an actions block with buttons."""
        return {"type": "actions", "elements": buttons}


# =============================================================================
# HTTP Client Manager
# =============================================================================

class SlackHTTPClient:
    """Shared HTTP client for Slack API calls with standardized error handling."""

    def __init__(self):
        self._client: Optional[httpx.AsyncClient] = None

    async def get_client(self) -> httpx.AsyncClient:
        """Get or create the shared HTTP client."""
        if self._client is None or self._client.is_closed:
            self._client = httpx.AsyncClient(timeout=30.0)
        return self._client

    async def close(self):
        """Close the HTTP client."""
        if self._client and not self._client.is_closed:
            await self._client.aclose()
            self._client = None

    async def post(
        self,
        endpoint: str,
        bot_token: Optional[str] = None,
        data: Optional[Dict] = None,
        json_data: Optional[Dict] = None
    ) -> Dict[str, Any]:
        """Make a POST request to Slack API with standardized error handling."""
        client = await self.get_client()
        headers = {}
        if bot_token:
            headers["Authorization"] = f"Bearer {bot_token}"

        try:
            response = await client.post(
                f"{SLACK_API_BASE}/{endpoint}",
                headers=headers,
                data=data,
                json=json_data
            )
            result = response.json()

            if not result.get("ok"):
                error = result.get("error", "Unknown error")
                logger.warning(f"Slack API error on {endpoint}: {error}")

            return result
        except Exception as e:
            logger.error(f"Slack API request failed: {endpoint} - {str(e)}")
            return {"ok": False, "error": str(e)}

    async def get(
        self,
        endpoint: str,
        bot_token: str,
        params: Optional[Dict] = None
    ) -> Dict[str, Any]:
        """Make a GET request to Slack API with standardized error handling."""
        client = await self.get_client()
        headers = {"Authorization": f"Bearer {bot_token}"}

        try:
            response = await client.get(
                f"{SLACK_API_BASE}/{endpoint}",
                headers=headers,
                params=params
            )
            result = response.json()

            if not result.get("ok"):
                error = result.get("error", "Unknown error")
                logger.warning(f"Slack API error on {endpoint}: {error}")

            return result
        except Exception as e:
            logger.error(f"Slack API request failed: {endpoint} - {str(e)}")
            return {"ok": False, "error": str(e)}


# Global HTTP client instance
_http_client = SlackHTTPClient()


class SlackApp:
    """
    Slack App with OAuth 2.0 support for multi-workspace installations.

    Flow:
    1. User clicks "Connect Slack" -> redirect to get_install_url()
    2. User approves in Slack -> Slack redirects to callback with code
    3. handle_oauth_callback() exchanges code for tokens
    4. Tokens stored in database per workspace
    """

    def __init__(self):
        self.client_id = config.SLACK_CLIENT_ID
        self.client_secret = config.SLACK_CLIENT_SECRET
        self.signing_secret = config.SLACK_SIGNING_SECRET
        self.redirect_uri = config.SLACK_REDIRECT_URI
        self.scopes = config.SLACK_SCOPES
        self.http = _http_client

    def get_install_url(self, state: Optional[str] = None) -> str:
        """
        Generate the Slack OAuth install URL.

        Args:
            state: Optional state parameter (e.g., user_id) to pass through OAuth

        Returns:
            URL to redirect user to for Slack installation
        """
        params = {
            "client_id": self.client_id,
            "scope": self.scopes,
            "redirect_uri": self.redirect_uri,
        }
        if state:
            params["state"] = state

        return f"{SLACK_OAUTH_URL}?{urlencode(params)}"

    async def handle_oauth_callback(self, code: str) -> Dict[str, Any]:
        """
        Exchange OAuth code for access tokens.

        Args:
            code: The temporary code from Slack OAuth redirect

        Returns:
            Dict with team_id, team_name, bot_token, bot_user_id, scopes

        Raises:
            Exception: If OAuth fails
        """
        data = await self.http.post(
            "oauth.v2.access",
            data={
                "client_id": self.client_id,
                "client_secret": self.client_secret,
                "code": code,
                "redirect_uri": self.redirect_uri,
            }
        )

        if not data.get("ok"):
            error = data.get("error", "Unknown error")
            logger.error(f"Slack OAuth failed: {error}")
            raise Exception(f"Slack OAuth failed: {error}")

        return {
            "team_id": data.get("team", {}).get("id"),
            "team_name": data.get("team", {}).get("name"),
            "bot_token": data.get("access_token"),
            "bot_user_id": data.get("bot_user_id"),
            "scopes": data.get("scope"),
            "user_token": data.get("authed_user", {}).get("access_token"),
        }

    def verify_request(self, timestamp: str, signature: str, body: bytes) -> bool:
        """
        Verify that a request is genuinely from Slack.

        Args:
            timestamp: X-Slack-Request-Timestamp header
            signature: X-Slack-Signature header
            body: Raw request body

        Returns:
            True if request is valid
        """
        if not self.signing_secret:
            logger.warning("Slack signing secret not configured")
            return True  # Skip verification if not configured

        # Check timestamp to prevent replay attacks
        try:
            time_diff = abs(time.time() - int(timestamp))
            if time_diff > TIMESTAMP_MAX_AGE_SECONDS:
                logger.warning(f"Slack timestamp too old: {time_diff}s (max {TIMESTAMP_MAX_AGE_SECONDS}s)")
                return False
        except (ValueError, TypeError) as e:
            logger.warning(f"Invalid timestamp: {timestamp} - {e}")
            return False

        # Compute expected signature
        sig_basestring = f"v0:{timestamp}:{body.decode('utf-8')}"
        expected = "v0=" + hmac.new(
            self.signing_secret.encode(),
            sig_basestring.encode(),
            hashlib.sha256
        ).hexdigest()

        match = hmac.compare_digest(expected, signature)
        if not match:
            logger.warning(f"Signature mismatch - expected: {expected[:30]}... got: {signature[:30]}...")
        return match

    async def list_channels(self, bot_token: str) -> List[Dict[str, Any]]:
        """List all public channels in the workspace."""
        data = await self.http.get(
            "conversations.list",
            bot_token,
            params={"types": "public_channel", "limit": CHANNEL_FETCH_LIMIT}
        )
        return data.get("channels", []) if data.get("ok") else []

    async def join_channel(self, bot_token: str, channel_id: str) -> Dict[str, Any]:
        """Join a channel."""
        return await self.http.post(
            "conversations.join",
            bot_token=bot_token,
            json_data={"channel": channel_id}
        )

    async def create_channel(self, bot_token: str, name: str) -> Optional[str]:
        """Create a new public channel and return its ID."""
        data = await self.http.post(
            "conversations.create",
            bot_token=bot_token,
            json_data={"name": name, "is_private": False}
        )
        if data.get("ok"):
            channel_id = data.get("channel", {}).get("id")
            logger.info(f"Created channel: #{name}")
            return channel_id
        else:
            logger.warning(f"Failed to create channel {name}: {data.get('error')}")
            return None

    async def auto_join_incidents_channel(self, bot_token: str) -> Optional[str]:
        """
        Find and join a channel named 'incidents' (or similar).
        Creates the channel if it doesn't exist.

        Args:
            bot_token: The workspace's bot token

        Returns:
            The channel ID if joined/created, None otherwise
        """
        channels = await self.list_channels(bot_token)

        # Look for incidents-related channels
        target_names = ["incidents", "incident", "alerts", "sra-incidents"]

        for channel in channels:
            if channel.get("name", "").lower() in target_names:
                channel_id = channel.get("id")
                result = await self.join_channel(bot_token, channel_id)
                if result.get("ok"):
                    logger.info(f"Auto-joined channel: #{channel.get('name')}")
                    return channel_id

        # No matching channel found - create one
        logger.info("No incidents channel found, creating #sra-incidents")
        channel_id = await self.create_channel(bot_token, "sra-incidents")
        return channel_id

    async def uninstall_app(self, bot_token: str) -> Dict[str, Any]:
        """
        Uninstall/revoke the app from a workspace.

        Args:
            bot_token: The workspace's bot token

        Returns:
            Slack API response
        """
        data = await self.http.post(
            "apps.uninstall",
            bot_token=bot_token,
            data={
                "client_id": self.client_id,
                "client_secret": self.client_secret
            }
        )
        if data.get("ok"):
            logger.info("App uninstalled from workspace")
        else:
            logger.error(f"Failed to uninstall app: {data.get('error')}")
        return data

    async def send_welcome_message(self, bot_token: str, channel: str) -> Dict[str, Any]:
        """
        Send a welcome message when the bot joins a channel.

        Args:
            bot_token: The workspace's bot token
            channel: Channel ID to send welcome message to

        Returns:
            Slack API response
        """
        blocks = [
            SlackBlockBuilder.header(":wave: Hello! I'm SRA Bot"),
            SlackBlockBuilder.section(
                "I'm your *Autonomous Incident Response Assistant* powered by IBM watsonx. "
                "I help detect, analyze, and resolve incidents automatically."
            ),
            SlackBlockBuilder.divider(),
            SlackBlockBuilder.section(
                "*What I can do:*\n"
                ":mag: *Monitor* - Watch your logs and metrics for anomalies\n"
                ":rotating_light: *Alert* - Send instant incident notifications\n"
                ":detective: *Analyze* - Perform AI-powered root cause analysis\n"
                ":wrench: *Heal* - Execute automated remediation actions"
            ),
            SlackBlockBuilder.section(
                "*Commands:*\n"
                "• `/sra-status` - Check system status\n"
                "• `/sra-check` - Review recent logs for errors\n"
                "• `/sra-incidents` - List recent incidents\n"
                "• `/sra-rca <id>` - Trigger root cause analysis\n"
                "• `@SRA help` - Get help anytime"
            ),
            SlackBlockBuilder.divider(),
            SlackBlockBuilder.context(
                ":robot_face: Powered by *SRA + IBM watsonx* | I'll notify you here when incidents occur"
            )
        ]

        return await self.send_message(
            bot_token=bot_token,
            channel=channel,
            text="Hello! I'm SRA Bot - your Autonomous Incident Response Assistant.",
            blocks=blocks
        )

    async def send_message(
        self,
        bot_token: str,
        channel: str,
        text: str,
        blocks: Optional[List[Dict]] = None,
        thread_ts: Optional[str] = None
    ) -> Dict[str, Any]:
        """
        Send a message to a Slack channel.

        Args:
            bot_token: The workspace's bot token
            channel: Channel ID or name
            text: Message text (fallback for notifications)
            blocks: Optional Block Kit blocks for rich formatting
            thread_ts: Optional thread timestamp to reply in thread

        Returns:
            Slack API response
        """
        payload = {
            "channel": channel,
            "text": text,
        }
        if blocks:
            payload["blocks"] = blocks
        if thread_ts:
            payload["thread_ts"] = thread_ts

        return await self.http.post(
            "chat.postMessage",
            bot_token=bot_token,
            json_data=payload
        )

    async def broadcast_alert(
        self,
        bot_token: str,
        message: str,
        blocks: List[Dict],
        ping_everyone: bool = True
    ) -> List[Dict[str, Any]]:
        """
        Broadcast an alert to ALL channels the bot is in.

        Args:
            bot_token: The workspace's bot token
            message: Fallback text message
            blocks: Block Kit blocks for rich formatting
            ping_everyone: If True, prepend <!channel> to ping everyone

        Returns:
            List of results for each channel
        """
        results = []

        # Get all channels the bot is a member of
        data = await self.http.get(
            "conversations.list",
            bot_token,
            params={"types": "public_channel,private_channel", "limit": CHANNEL_FETCH_LIMIT}
        )

        if not data.get("ok"):
            logger.error(f"Failed to list channels: {data.get('error')}")
            return results

        channels = data.get("channels", [])

        # Filter to channels where bot is a member
        bot_channels = [c for c in channels if c.get("is_member")]

        for channel in bot_channels:
            channel_id = channel.get("id")

            # Prepend @channel ping if requested
            alert_text = f"<!channel> {message}" if ping_everyone else message
            alert_blocks = blocks.copy()

            if ping_everyone:
                # Add ping at the top of blocks
                alert_blocks.insert(0, SlackBlockBuilder.section("<!channel>"))

            result = await self.send_message(
                bot_token=bot_token,
                channel=channel_id,
                text=alert_text,
                blocks=alert_blocks
            )
            results.append({
                "channel": channel.get("name"),
                "channel_id": channel_id,
                "ok": result.get("ok"),
                "error": result.get("error")
            })

            if result.get("ok"):
                logger.info(f"Broadcast alert to #{channel.get('name')}")
            else:
                logger.error(f"Failed to send to #{channel.get('name')}: {result.get('error')}")

        return results

    async def broadcast_incident_alert(
        self,
        bot_token: str,
        incident: Dict[str, Any],
        ping_everyone: bool = True
    ) -> List[Dict[str, Any]]:
        """
        Broadcast an incident alert to ALL channels the bot is in.

        Args:
            bot_token: The workspace's bot token
            incident: Incident data dict
            ping_everyone: If True, ping @channel

        Returns:
            List of results for each channel
        """
        severity = incident.get("severity", "medium")
        severity_emoji = get_severity_emoji(severity)
        incident_id = incident.get("id", "N/A")

        blocks = [
            SlackBlockBuilder.header(f"{severity_emoji} INCIDENT ALERT: {incident.get('title', 'Unknown')}"),
            {
                "type": "section",
                "fields": [
                    {"type": "mrkdwn", "text": f"*Severity:*\n{severity.upper()}"},
                    {"type": "mrkdwn", "text": f"*Status:*\n{incident.get('status', 'open')}"},
                    {"type": "mrkdwn", "text": f"*ID:*\n`{incident_id[:8]}`"},
                    {"type": "mrkdwn", "text": f"*Time:*\n{incident.get('created_at', 'Unknown')}"}
                ]
            },
            SlackBlockBuilder.divider(),
            SlackBlockBuilder.section(
                f"*Description:*\n{incident.get('description', 'No description')[:MAX_DESCRIPTION_LENGTH]}"
            )
        ]

        # Add RCA if available
        rca = incident.get("rca")
        if rca:
            blocks.append(SlackBlockBuilder.section(
                f"*Root Cause:*\n{rca.get('root_cause', 'Under investigation')[:MAX_RCA_LENGTH]}"
            ))

        # Add action buttons
        blocks.append(SlackBlockBuilder.actions([
            SlackBlockBuilder.button(":white_check_mark: Acknowledge", "ack_incident", incident_id, "primary"),
            SlackBlockBuilder.button(":mag: View Details", "view_incident", incident_id)
        ]))

        blocks.append(SlackBlockBuilder.context(":robot_face: Powered by *SRA + IBM watsonx*"))

        return await self.broadcast_alert(
            bot_token=bot_token,
            message=f"INCIDENT ALERT: {incident.get('title', 'Unknown')} [{severity.upper()}]",
            blocks=blocks,
            ping_everyone=ping_everyone
        )

    async def send_incident_alert(
        self,
        bot_token: str,
        channel: str,
        incident: Dict[str, Any]
    ) -> Dict[str, Any]:
        """
        Send a formatted incident alert to Slack.

        Args:
            bot_token: The workspace's bot token
            channel: Channel to send to
            incident: Incident data dict

        Returns:
            Slack API response
        """
        severity = incident.get("severity", "medium")
        severity_emoji = get_severity_emoji(severity)
        incident_id = incident.get("id", "N/A")

        blocks = [
            SlackBlockBuilder.header(f"{severity_emoji} Incident Alert: {incident.get('title', 'Unknown')}"),
            {
                "type": "section",
                "fields": [
                    {"type": "mrkdwn", "text": f"*Severity:*\n{severity.upper()}"},
                    {"type": "mrkdwn", "text": f"*Status:*\n{incident.get('status', 'open')}"},
                    {"type": "mrkdwn", "text": f"*ID:*\n`{incident_id[:8]}`"},
                    {"type": "mrkdwn", "text": f"*Time:*\n{incident.get('created_at', 'Unknown')}"}
                ]
            },
            SlackBlockBuilder.divider(),
            SlackBlockBuilder.section(
                f"*Description:*\n{incident.get('description', 'No description')[:MAX_DESCRIPTION_LENGTH]}"
            )
        ]

        # Add RCA if available
        rca = incident.get("rca")
        if rca:
            blocks.append(SlackBlockBuilder.section(
                f"*Root Cause:*\n{rca.get('root_cause', 'Under investigation')[:MAX_RCA_LENGTH]}"
            ))

        # Add action buttons
        blocks.append(SlackBlockBuilder.actions([
            SlackBlockBuilder.button("View Details", "view_incident", incident_id),
            SlackBlockBuilder.button("Check Logs", "check_logs", "", "primary"),
            SlackBlockBuilder.button("Acknowledge", "ack_incident", incident_id, "danger")
        ]))

        return await self.send_message(
            bot_token=bot_token,
            channel=channel,
            text=f"Incident Alert: {incident.get('title', 'Unknown')} [{severity.upper()}]",
            blocks=blocks
        )

    async def send_log_check_response(
        self,
        bot_token: str,
        channel: str,
        logs: List[Dict[str, Any]],
        thread_ts: Optional[str] = None
    ) -> Dict[str, Any]:
        """
        Send log check results to Slack.

        Args:
            bot_token: The workspace's bot token
            channel: Channel to send to
            logs: List of log entries
            thread_ts: Optional thread to reply to

        Returns:
            Slack API response
        """
        if not logs:
            return await self.send_message(
                bot_token=bot_token,
                channel=channel,
                text=":white_check_mark: No recent errors found in logs.",
                thread_ts=thread_ts
            )

        # Group by level
        errors = [l for l in logs if l.get("level") in ["error", "critical"]]
        warnings = [l for l in logs if l.get("level") == "warning"]

        blocks = [
            SlackBlockBuilder.header(":mag: Log Check Results"),
            {
                "type": "section",
                "fields": [
                    {"type": "mrkdwn", "text": f"*Errors:* {len(errors)}"},
                    {"type": "mrkdwn", "text": f"*Warnings:* {len(warnings)}"},
                    {"type": "mrkdwn", "text": f"*Total Logs:* {len(logs)}"},
                ]
            },
            SlackBlockBuilder.divider()
        ]

        # Show recent errors (limited)
        for log in errors[:MAX_ERRORS_DISPLAY]:
            blocks.append(SlackBlockBuilder.section(
                f":x: `{log.get('timestamp', '')}` [{log.get('service', 'unknown')}]\n"
                f"```{log.get('message', '')[:200]}```"
            ))

        if len(errors) > MAX_ERRORS_DISPLAY:
            blocks.append(SlackBlockBuilder.context(
                f"_...and {len(errors) - MAX_ERRORS_DISPLAY} more errors_"
            ))

        return await self.send_message(
            bot_token=bot_token,
            channel=channel,
            text=f"Log Check: {len(errors)} errors, {len(warnings)} warnings",
            blocks=blocks,
            thread_ts=thread_ts
        )

    async def send_rca_report(
        self,
        bot_token: str,
        channel: str,
        incident_id: str,
        rca: Dict[str, Any],
        actions: List[Dict[str, Any]],
        show_autoheal_button: bool = True
    ) -> Dict[str, Any]:
        """
        Send RCA analysis results to Slack with optional autoheal button.

        Args:
            bot_token: The workspace's bot token
            channel: Channel to send to
            incident_id: The incident ID
            rca: RCA analysis data
            actions: List of recommended actions
            show_autoheal_button: Whether to show the "Execute Fix" button

        Returns:
            Slack API response
        """
        blocks = [
            SlackBlockBuilder.header(":detective: Root Cause Analysis Complete"),
            SlackBlockBuilder.section(f"*Incident:* `{incident_id[:8]}`"),
            SlackBlockBuilder.divider(),
            SlackBlockBuilder.section(f"*Root Cause:*\n{rca.get('root_cause', 'Unknown')}")
        ]

        # Contributing factors
        factors = rca.get("contributing_factors", [])
        if factors:
            factor_text = "\n".join([f"- {f}" for f in factors[:MAX_ERRORS_DISPLAY]])
            blocks.append(SlackBlockBuilder.section(f"*Contributing Factors:*\n{factor_text}"))

        # Recommended actions - filter to show only automatable ones
        automatable_actions = [a for a in actions if a.get('automated', False)]
        manual_actions = [a for a in actions if not a.get('automated', False)]

        if automatable_actions:
            blocks.append(SlackBlockBuilder.divider())
            blocks.append(SlackBlockBuilder.section("*:wrench: Automatable Fixes:*"))
            for action in automatable_actions[:3]:
                action_type = action.get('action_type', 'Unknown')
                service = action.get('service', '')
                service_text = f" (`{service}`)" if service else ""
                blocks.append(SlackBlockBuilder.section(
                    f":gear: *{action_type}*{service_text}\n{action.get('description', '')[:200]}"
                ))

        if manual_actions:
            blocks.append(SlackBlockBuilder.section("*:clipboard: Manual Steps Required:*"))
            for action in manual_actions[:3]:
                blocks.append(SlackBlockBuilder.section(
                    f":point_right: *{action.get('action_type', 'Unknown')}*\n{action.get('description', '')[:200]}"
                ))

        # Add action buttons
        buttons = []
        if show_autoheal_button and automatable_actions:
            buttons.append(SlackBlockBuilder.button(
                ":zap: Execute Auto-Fix",
                "execute_autoheal",
                incident_id,
                "danger"  # Red button to indicate caution
            ))
        buttons.append(SlackBlockBuilder.button(
            ":rotating_light: Escalate",
            "escalate_incident",
            incident_id,
            "danger"
        ))
        buttons.append(SlackBlockBuilder.button(
            ":white_check_mark: Mark Resolved",
            "resolve_incident",
            incident_id,
            "primary"
        ))
        buttons.append(SlackBlockBuilder.button(
            ":x: Dismiss",
            "dismiss_incident",
            incident_id
        ))

        if buttons:
            blocks.append(SlackBlockBuilder.actions(buttons))

        blocks.append(SlackBlockBuilder.context(
            ":warning: *Auto-fix will execute system commands. Review before clicking.*"
        ))

        return await self.send_message(
            bot_token=bot_token,
            channel=channel,
            text=f"RCA Complete for incident {incident_id[:8]}",
            blocks=blocks
        )

    async def send_escalation(
        self,
        bot_token: str,
        channel: str,
        incident_id: str,
        incident_title: str,
        severity: str,
        escalated_by: str,
        summary: Optional[str] = None
    ) -> Dict[str, Any]:
        """
        Send an escalation alert to the Slack channel with @channel mention.

        Args:
            bot_token: The workspace's bot token
            channel: Channel to send to
            incident_id: The incident ID
            incident_title: Title of the incident
            severity: Severity level
            escalated_by: User who triggered escalation
            summary: Optional summary of the issue

        Returns:
            Slack API response
        """
        severity_emoji = get_severity_emoji(severity)

        blocks = [
            SlackBlockBuilder.header(":rotating_light: INCIDENT ESCALATED - HELP NEEDED :rotating_light:"),
            SlackBlockBuilder.section(
                f"<!channel> *An incident requires immediate attention!*"
            ),
            SlackBlockBuilder.divider(),
            SlackBlockBuilder.section_fields([
                {"label": "Incident", "value": f"`{incident_id[:8]}`"},
                {"label": "Severity", "value": f"{severity_emoji} {severity.upper()}"},
            ]),
            SlackBlockBuilder.section(f"*Title:* {incident_title}"),
        ]

        if summary:
            blocks.append(SlackBlockBuilder.section(f"*Summary:*\n{summary[:MAX_DESCRIPTION_LENGTH]}"))

        blocks.append(SlackBlockBuilder.divider())
        blocks.append(SlackBlockBuilder.section(
            f":bust_in_silhouette: *Escalated by:* <@{escalated_by}>"
        ))
        blocks.append(SlackBlockBuilder.section(
            ":point_right: *Please respond in thread if you can assist.*"
        ))

        # Add buttons for responders
        buttons = [
            SlackBlockBuilder.button(
                ":raised_hand: I'm Looking Into It",
                "acknowledge_escalation",
                incident_id,
                "primary"
            ),
            SlackBlockBuilder.button(
                ":eyes: View Incident",
                "view_incident",
                incident_id
            ),
        ]
        blocks.append(SlackBlockBuilder.actions(buttons))

        blocks.append(SlackBlockBuilder.context(
            f":clock1: Escalated at <!date^{int(time.time())}^{{date_short_pretty}} {{time}}|now>"
        ))

        return await self.send_message(
            bot_token=bot_token,
            channel=channel,
            text=f"ESCALATION: {incident_title} - @channel help needed!",
            blocks=blocks
        )


class SlackCommandHandler:
    """Handles Slack slash commands."""

    def __init__(self, slack_app: SlackApp):
        self.slack = slack_app

    async def handle_command(
        self,
        command: str,
        text: str,
        user_id: str,
        channel_id: str,
        team_id: str,
        response_url: str,
        bot_token: str,
        db: AsyncSession
    ) -> Dict[str, Any]:
        """
        Route and handle slash commands.

        Commands:
            /sra-check - Check recent logs for errors
            /sra-status - Get system status
            /sra-incidents - List recent incidents
            /sra-rca <incident_id> - Trigger RCA for an incident
        """
        command = command.lstrip("/")

        if command == "sra-check" or command == "sra":
            return await self._handle_check(text, channel_id, bot_token, db)
        elif command == "sra-status":
            return await self._handle_status(channel_id, bot_token)
        elif command == "sra-incidents":
            return await self._handle_incidents(text, channel_id, bot_token)
        elif command == "sra-rca":
            return await self._handle_rca(text, channel_id, bot_token)
        else:
            return {
                "response_type": "ephemeral",
                "text": f"Unknown command: {command}. Available: /sra-check, /sra-status, /sra-incidents, /sra-rca"
            }

    async def _handle_check(
        self,
        text: str,
        channel_id: str,
        bot_token: str,
        db: AsyncSession
    ) -> Dict[str, Any]:
        """Handle /sra-check command - check recent logs."""
        from engines import ingestion_buffer

        # Parse optional time range (default 15 minutes)
        minutes = 15
        if text:
            try:
                minutes = int(text.strip())
            except ValueError:
                pass

        logs = ingestion_buffer.get_recent_logs(minutes=minutes)
        error_logs = [l for l in logs if l.level.value in ["error", "critical", "warning"]]

        # Convert to dict for send_log_check_response
        log_dicts = [
            {
                "timestamp": l.timestamp.isoformat() if l.timestamp else "",
                "level": l.level.value,
                "service": l.service or "unknown",
                "message": l.message
            }
            for l in error_logs
        ]

        await self.slack.send_log_check_response(
            bot_token=bot_token,
            channel=channel_id,
            logs=log_dicts
        )

        return {"response_type": "in_channel"}

    async def _handle_status(self, channel_id: str, bot_token: str) -> Dict[str, Any]:
        """Handle /sra-status command - get system status."""
        from engines import incident_manager, stability_evaluator, ingestion_buffer

        active_incident = incident_manager.get_active_incident()
        trend = stability_evaluator.get_stability_trend()

        status_emoji = ":white_check_mark:" if not active_incident else ":warning:"

        blocks = [
            SlackBlockBuilder.header(f"{status_emoji} System Status"),
            {
                "type": "section",
                "fields": [
                    {"type": "mrkdwn", "text": f"*Status:*\n{'Incident Active' if active_incident else 'Operational'}"},
                    {"type": "mrkdwn", "text": f"*Stability Trend:*\n{trend}"},
                    {"type": "mrkdwn", "text": f"*Buffered Logs:*\n{len(ingestion_buffer.logs)}"},
                    {"type": "mrkdwn", "text": f"*Buffered Metrics:*\n{len(ingestion_buffer.snapshots)}"}
                ]
            }
        ]

        if active_incident:
            blocks.append(SlackBlockBuilder.section(
                f"*Active Incident:*\n`{active_incident.id[:8]}` - {active_incident.title}"
            ))

        await self.slack.send_message(
            bot_token=bot_token,
            channel=channel_id,
            text="System Status",
            blocks=blocks
        )

        return {"response_type": "in_channel"}

    async def _handle_incidents(self, text: str, channel_id: str, bot_token: str) -> Dict[str, Any]:
        """Handle /sra-incidents command - list recent incidents."""
        from engines import incident_manager

        # Parse optional limit
        limit = 5
        if text:
            try:
                limit = min(int(text.strip()), 10)
            except ValueError:
                pass

        incidents = incident_manager.list_incidents(limit=limit)

        if not incidents:
            await self.slack.send_message(
                bot_token=bot_token,
                channel=channel_id,
                text=":white_check_mark: No incidents found."
            )
            return {"response_type": "in_channel"}

        blocks = [SlackBlockBuilder.header(":clipboard: Recent Incidents")]

        for inc in incidents:
            severity_emoji = get_severity_emoji(inc.severity.value)
            blocks.append(SlackBlockBuilder.section(
                f"{severity_emoji} `{inc.id[:8]}` *{inc.title}*\n"
                f"Status: {inc.status.value} | {inc.created_at.strftime('%Y-%m-%d %H:%M')}"
            ))

        await self.slack.send_message(
            bot_token=bot_token,
            channel=channel_id,
            text=f"Found {len(incidents)} incidents",
            blocks=blocks
        )

        return {"response_type": "in_channel"}

    async def _handle_rca(self, text: str, channel_id: str, bot_token: str) -> Dict[str, Any]:
        """Handle /sra-rca command - trigger RCA for an incident."""
        from integrations import agent_orchestrator

        if not text or not text.strip():
            return {
                "response_type": "ephemeral",
                "text": "Usage: /sra-rca <incident_id>"
            }

        incident_id = text.strip()

        # Send acknowledgment
        await self.slack.send_message(
            bot_token=bot_token,
            channel=channel_id,
            text=f":hourglass_flowing_sand: Triggering RCA for incident `{incident_id[:8]}`..."
        )

        # Trigger RCA (async)
        try:
            result = await agent_orchestrator.run_rca_workflow(incident_id)

            if result and result.rca:
                await self.slack.send_rca_report(
                    bot_token=bot_token,
                    channel=channel_id,
                    incident_id=incident_id,
                    rca=result.rca.model_dump() if hasattr(result.rca, 'model_dump') else result.rca,
                    actions=[a.model_dump() if hasattr(a, 'model_dump') else a for a in result.recommended_actions]
                )
            else:
                await self.slack.send_message(
                    bot_token=bot_token,
                    channel=channel_id,
                    text=f":x: RCA could not be completed for incident `{incident_id[:8]}`"
                )
        except Exception as e:
            logger.error(f"RCA command failed: {str(e)}")
            await self.slack.send_message(
                bot_token=bot_token,
                channel=channel_id,
                text=f":x: RCA failed: {str(e)}"
            )

        return {"response_type": "in_channel"}


class SlackEventHandler:
    """Handles Slack events (mentions, messages, etc.)."""

    def __init__(self, slack_app: SlackApp, command_handler: SlackCommandHandler):
        self.slack = slack_app
        self.commands = command_handler

    async def handle_event(
        self,
        event: Dict[str, Any],
        team_id: str,
        bot_token: str,
        db: AsyncSession
    ) -> Dict[str, Any]:
        """
        Handle incoming Slack events.

        Supported events:
            - app_mention: Bot was mentioned
            - message: Direct message to bot
            - member_joined_channel: Bot was added to a channel
        """
        event_type = event.get("type")

        if event_type == "app_mention":
            return await self._handle_mention(event, bot_token, db)
        elif event_type == "message":
            # Only handle DMs (no subtype means it's a regular message)
            if not event.get("subtype") and event.get("channel_type") == "im":
                return await self._handle_dm(event, bot_token, db)
        elif event_type == "member_joined_channel":
            return await self._handle_bot_joined_channel(event, bot_token)

        return {"ok": True}

    async def _handle_bot_joined_channel(
        self,
        event: Dict[str, Any],
        bot_token: str
    ) -> Dict[str, Any]:
        """Handle when the bot is added to a channel - send welcome message."""
        channel = event.get("channel")
        user = event.get("user")  # The user who joined

        # We need to check if it's the bot that joined
        # Get bot user ID from token
        data = await self.slack.http.get("auth.test", bot_token)
        bot_user_id = data.get("user_id")

        # Only send welcome if it's the bot that joined
        if user == bot_user_id:
            await self.slack.send_welcome_message(bot_token, channel)
            logger.info(f"Bot joined channel {channel}, sent welcome message")

        return {"ok": True}

    async def _handle_mention(
        self,
        event: Dict[str, Any],
        bot_token: str,
        db: AsyncSession
    ) -> Dict[str, Any]:
        """Handle @bot mentions."""
        text = event.get("text", "").lower()
        channel = event.get("channel")
        thread_ts = event.get("thread_ts") or event.get("ts")

        # Parse intent from mention
        if "check" in text or "logs" in text:
            from engines import ingestion_buffer
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
            await self.slack.send_log_check_response(
                bot_token=bot_token,
                channel=channel,
                logs=error_logs,
                thread_ts=thread_ts
            )
        elif "status" in text:
            await self.commands._handle_status(channel, bot_token)
        elif "incident" in text:
            await self.commands._handle_incidents("5", channel, bot_token)
        elif "help" in text:
            await self.slack.send_message(
                bot_token=bot_token,
                channel=channel,
                text="*Available Commands:*\n"
                     "- `@bot check` or `/sra-check` - Check recent logs\n"
                     "- `@bot status` or `/sra-status` - System status\n"
                     "- `@bot incidents` or `/sra-incidents` - List incidents\n"
                     "- `/sra-rca <id>` - Trigger RCA analysis",
                thread_ts=thread_ts
            )
        else:
            await self.slack.send_message(
                bot_token=bot_token,
                channel=channel,
                text="I can help you with:\n"
                     "- *check logs* - Review recent error logs\n"
                     "- *status* - Check system status\n"
                     "- *incidents* - List recent incidents\n"
                     "- *help* - Show all commands",
                thread_ts=thread_ts
            )

        return {"ok": True}

    async def _handle_dm(
        self,
        event: Dict[str, Any],
        bot_token: str,
        db: AsyncSession
    ) -> Dict[str, Any]:
        """Handle direct messages to the bot."""
        # Treat DMs the same as mentions
        return await self._handle_mention(event, bot_token, db)


# Global instances
slack_app = SlackApp()
slack_command_handler = SlackCommandHandler(slack_app)
slack_event_handler = SlackEventHandler(slack_app, slack_command_handler)
