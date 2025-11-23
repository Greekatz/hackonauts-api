"""
Notification & Ticket Integration Layer
Handles Slack, Email, Discord, Jira, ServiceNow integrations.
"""
import asyncio
import smtplib
from email.mime.text import MIMEText
from email.mime.multipart import MIMEMultipart
from typing import Optional, Dict, Any, List

import httpx

from core import Incident, IncidentSeverity, config, logger
from engines import incident_manager


class DiscordNotifier:
    """Discord webhook integration."""

    def __init__(self):
        self.webhook_url = config.DISCORD_WEBHOOK_URL

    async def send(self, message: str, embeds: Optional[List[Dict]] = None) -> bool:
        """Send message to Discord."""
        if not self.webhook_url:
            logger.warning("Discord webhook URL not configured")
            return False

        payload = {
            "content": message,
            "embeds": embeds or []
        }

        try:
            async with httpx.AsyncClient() as client:
                response = await client.post(self.webhook_url, json=payload)
                return response.status_code in [200, 204]
        except Exception as e:
            logger.error(f"Discord webhook error: {str(e)}")
            return False

    async def send_incident_alert(self, incident: Incident) -> bool:
        """Send formatted incident alert to Discord."""
        severity_color = {
            IncidentSeverity.LOW: 0x36a64f,
            IncidentSeverity.MEDIUM: 0xffcc00,
            IncidentSeverity.HIGH: 0xff9900,
            IncidentSeverity.CRITICAL: 0xff0000
        }

        embed = {
            "title": f"[ALERT] Incident: {incident.title}",
            "color": severity_color.get(incident.severity, 0x808080),
            "fields": [
                {"name": "Severity", "value": incident.severity.value, "inline": True},
                {"name": "Status", "value": incident.status.value, "inline": True},
                {"name": "ID", "value": incident.id[:8], "inline": True},
            ],
            "timestamp": incident.created_at.isoformat()
        }

        if incident.description:
            embed["description"] = incident.description[:1000]

        if incident.rca:
            embed["fields"].append({
                "name": "Root Cause",
                "value": incident.rca.root_cause[:500],
                "inline": False
            })

        return await self.send(message="", embeds=[embed])


class EmailNotifier:
    """Email notification via SMTP."""

    def __init__(self):
        self.smtp_host = config.SMTP_HOST
        self.smtp_port = config.SMTP_PORT
        self.smtp_user = config.SMTP_USER
        self.smtp_password = config.SMTP_PASSWORD
        self.email_from = config.EMAIL_FROM
        self.email_to = config.EMAIL_TO

    async def send(self, subject: str, body: str, html: bool = False) -> bool:
        """Send email notification."""
        if not all([self.smtp_host, self.smtp_user, self.email_from, self.email_to]):
            logger.warning("Email not configured")
            return False

        try:
            msg = MIMEMultipart("alternative")
            msg["Subject"] = subject
            msg["From"] = self.email_from
            msg["To"] = self.email_to

            if html:
                msg.attach(MIMEText(body, "html"))
            else:
                msg.attach(MIMEText(body, "plain"))

            # Run SMTP in thread pool to not block
            loop = asyncio.get_event_loop()
            await loop.run_in_executor(None, self._send_smtp, msg)
            return True

        except Exception as e:
            logger.error(f"Email send error: {str(e)}")
            return False

    def _send_smtp(self, msg: MIMEMultipart) -> None:
        """Synchronous SMTP send."""
        with smtplib.SMTP(self.smtp_host, self.smtp_port) as server:
            server.starttls()
            if self.smtp_password:
                server.login(self.smtp_user, self.smtp_password)
            server.sendmail(self.email_from, self.email_to.split(","), msg.as_string())

    async def send_incident_alert(self, incident: Incident) -> bool:
        """Send formatted incident email."""
        subject = f"[{incident.severity.value.upper()}] Incident: {incident.title}"

        body = f"""
        <html>
        <body>
        <h2>Incident Alert</h2>
        <table>
            <tr><td><strong>Title:</strong></td><td>{incident.title}</td></tr>
            <tr><td><strong>Severity:</strong></td><td>{incident.severity.value}</td></tr>
            <tr><td><strong>Status:</strong></td><td>{incident.status.value}</td></tr>
            <tr><td><strong>ID:</strong></td><td>{incident.id}</td></tr>
            <tr><td><strong>Created:</strong></td><td>{incident.created_at.strftime('%Y-%m-%d %H:%M UTC')}</td></tr>
        </table>

        <h3>Description</h3>
        <p>{incident.description or 'No description'}</p>
        """

        if incident.rca:
            body += f"""
        <h3>Root Cause Analysis</h3>
        <p>{incident.rca.root_cause}</p>
        """

        body += "</body></html>"

        return await self.send(subject, body, html=True)


class JiraClient:
    """Jira ticket integration."""

    def __init__(self):
        self.url = config.JIRA_URL
        self.user = config.JIRA_USER
        self.api_token = config.JIRA_API_TOKEN
        self.project_key = config.JIRA_PROJECT_KEY

    async def create_ticket(
        self,
        summary: str,
        description: str,
        issue_type: str = "Bug",
        priority: str = "Medium"
    ) -> Optional[str]:
        """Create a Jira ticket."""
        if not all([self.url, self.user, self.api_token, self.project_key]):
            logger.warning("Jira not configured")
            return None

        payload = {
            "fields": {
                "project": {"key": self.project_key},
                "summary": summary,
                "description": description,
                "issuetype": {"name": issue_type},
                "priority": {"name": priority}
            }
        }

        try:
            async with httpx.AsyncClient() as client:
                response = await client.post(
                    f"{self.url}/rest/api/2/issue",
                    json=payload,
                    auth=(self.user, self.api_token),
                    headers={"Content-Type": "application/json"}
                )

                if response.status_code == 201:
                    data = response.json()
                    ticket_key = data.get("key")
                    logger.info(f"Jira ticket created: {ticket_key}")
                    return ticket_key
                else:
                    logger.error(f"Jira API error: {response.status_code} - {response.text}")
                    return None

        except Exception as e:
            logger.error(f"Jira error: {str(e)}")
            return None

    async def create_incident_ticket(self, incident: Incident) -> Optional[str]:
        """Create a Jira ticket for an incident."""
        priority_map = {
            IncidentSeverity.LOW: "Low",
            IncidentSeverity.MEDIUM: "Medium",
            IncidentSeverity.HIGH: "High",
            IncidentSeverity.CRITICAL: "Highest"
        }

        description = f"""
h2. Incident Details
* *ID:* {incident.id}
* *Severity:* {incident.severity.value}
* *Status:* {incident.status.value}
* *Created:* {incident.created_at.strftime('%Y-%m-%d %H:%M UTC')}

h2. Description
{incident.description or 'No description provided'}
"""

        if incident.rca:
            description += f"""
h2. Root Cause Analysis
{incident.rca.root_cause}

h3. Contributing Factors
{chr(10).join('* ' + f for f in incident.rca.contributing_factors)}
"""

        return await self.create_ticket(
            summary=f"[Incident] {incident.title}",
            description=description,
            issue_type="Bug",
            priority=priority_map.get(incident.severity, "Medium")
        )


class ServiceNowClient:
    """ServiceNow ticket integration."""

    def __init__(self):
        self.url = config.SERVICENOW_URL
        self.user = config.SERVICENOW_USER
        self.password = config.SERVICENOW_PASSWORD

    async def create_incident(
        self,
        short_description: str,
        description: str,
        urgency: int = 2,
        impact: int = 2
    ) -> Optional[str]:
        """Create a ServiceNow incident."""
        if not all([self.url, self.user, self.password]):
            logger.warning("ServiceNow not configured")
            return None

        payload = {
            "short_description": short_description,
            "description": description,
            "urgency": str(urgency),
            "impact": str(impact)
        }

        try:
            async with httpx.AsyncClient() as client:
                response = await client.post(
                    f"{self.url}/api/now/table/incident",
                    json=payload,
                    auth=(self.user, self.password),
                    headers={
                        "Content-Type": "application/json",
                        "Accept": "application/json"
                    }
                )

                if response.status_code == 201:
                    data = response.json()
                    incident_number = data.get("result", {}).get("number")
                    logger.info(f"ServiceNow incident created: {incident_number}")
                    return incident_number
                else:
                    logger.error(f"ServiceNow API error: {response.status_code}")
                    return None

        except Exception as e:
            logger.error(f"ServiceNow error: {str(e)}")
            return None

    async def create_from_incident(self, incident: Incident) -> Optional[str]:
        """Create ServiceNow incident from our incident."""
        urgency_map = {
            IncidentSeverity.LOW: 3,
            IncidentSeverity.MEDIUM: 2,
            IncidentSeverity.HIGH: 2,
            IncidentSeverity.CRITICAL: 1
        }

        impact_map = {
            IncidentSeverity.LOW: 3,
            IncidentSeverity.MEDIUM: 2,
            IncidentSeverity.HIGH: 2,
            IncidentSeverity.CRITICAL: 1
        }

        description = f"""
Incident ID: {incident.id}
Severity: {incident.severity.value}
Created: {incident.created_at.strftime('%Y-%m-%d %H:%M UTC')}

{incident.description or 'No description'}
"""

        if incident.rca:
            description += f"\n\nRoot Cause:\n{incident.rca.root_cause}"

        return await self.create_incident(
            short_description=incident.title,
            description=description,
            urgency=urgency_map.get(incident.severity, 2),
            impact=impact_map.get(incident.severity, 2)
        )


class NotificationManager:
    """Unified notification manager."""

    def __init__(self):
        # Import here to avoid circular imports
        from .slack_app import slack_app
        self.slack_app = slack_app
        self.discord = DiscordNotifier()
        self.email = EmailNotifier()
        self.jira = JiraClient()
        self.servicenow = ServiceNowClient()

    async def notify_incident(
        self,
        incident_id: str,
        channels: Optional[List[str]] = None
    ) -> Dict[str, Any]:
        """Send notifications to specified channels."""
        incident = incident_manager.get_incident(incident_id)
        if not incident:
            return {"error": True, "message": "Incident not found"}

        # Default to all channels if not specified
        if channels is None:
            channels = ["slack", "discord", "email"]

        results: Dict[str, Any] = {}

        if "slack" in channels:
            # Use webhook for simple notifications
            results["slack"] = await self._send_slack_webhook(incident)

        if "discord" in channels:
            results["discord"] = await self.discord.send_incident_alert(incident)

        if "email" in channels:
            results["email"] = await self.email.send_incident_alert(incident)

        if "jira" in channels:
            ticket = await self.jira.create_incident_ticket(incident)
            results["jira"] = ticket is not None
            if ticket:
                results["jira_ticket"] = ticket

        if "servicenow" in channels:
            ticket = await self.servicenow.create_from_incident(incident)
            results["servicenow"] = ticket is not None
            if ticket:
                results["servicenow_ticket"] = ticket

        return results

    async def _send_slack_webhook(self, incident: Incident) -> bool:
        """Send incident alert via Slack webhook (simple integration)."""
        webhook_url = config.SLACK_WEBHOOK_URL
        if not webhook_url:
            logger.warning("Slack webhook URL not configured")
            return False

        severity_colors = {
            IncidentSeverity.LOW: "#36a64f",
            IncidentSeverity.MEDIUM: "#ffcc00",
            IncidentSeverity.HIGH: "#ff9900",
            IncidentSeverity.CRITICAL: "#ff0000"
        }

        payload = {
            "text": f"New incident detected: {incident.title}",
            "attachments": [{
                "color": severity_colors.get(incident.severity, "#808080"),
                "blocks": [
                    {
                        "type": "header",
                        "text": {
                            "type": "plain_text",
                            "text": f"[{incident.severity.value.upper()}] Incident: {incident.title}"
                        }
                    },
                    {
                        "type": "section",
                        "fields": [
                            {"type": "mrkdwn", "text": f"*Severity:*\n{incident.severity.value}"},
                            {"type": "mrkdwn", "text": f"*Status:*\n{incident.status.value}"},
                            {"type": "mrkdwn", "text": f"*ID:*\n{incident.id[:8]}"},
                            {"type": "mrkdwn", "text": f"*Created:*\n{incident.created_at.strftime('%Y-%m-%d %H:%M UTC')}"}
                        ]
                    },
                    {
                        "type": "section",
                        "text": {
                            "type": "mrkdwn",
                            "text": f"*Description:*\n{incident.description[:500] if incident.description else 'No description'}"
                        }
                    }
                ]
            }]
        }

        if incident.rca:
            payload["attachments"][0]["blocks"].append({
                "type": "section",
                "text": {
                    "type": "mrkdwn",
                    "text": f"*Root Cause:*\n{incident.rca.root_cause[:500]}"
                }
            })

        try:
            async with httpx.AsyncClient() as client:
                response = await client.post(webhook_url, json=payload)
                return response.status_code == 200
        except Exception as e:
            logger.error(f"Slack webhook error: {str(e)}")
            return False

    async def send_custom_message(
        self,
        channel: str,
        message: str,
        **kwargs: Any
    ) -> bool:
        """Send a custom message to a specific channel."""
        if channel == "slack":
            return await self._send_slack_custom(message)
        elif channel == "discord":
            return await self.discord.send(message)
        elif channel == "email":
            subject = kwargs.get("subject", "Notification")
            return await self.email.send(subject, message)
        else:
            logger.warning(f"Unknown notification channel: {channel}")
            return False

    async def _send_slack_custom(self, message: str) -> bool:
        """Send custom message to Slack via webhook."""
        webhook_url = config.SLACK_WEBHOOK_URL
        if not webhook_url:
            return False

        try:
            async with httpx.AsyncClient() as client:
                response = await client.post(webhook_url, json={"text": message})
                return response.status_code == 200
        except Exception as e:
            logger.error(f"Slack webhook error: {str(e)}")
            return False


# Global notification manager
notification_manager = NotificationManager()
