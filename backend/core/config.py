"""
Configuration Management Module
Loads and manages all config values from environment variables.
"""
import os
from dotenv import load_dotenv
from pydantic import BaseModel
from typing import Optional

load_dotenv()


class ThresholdConfig(BaseModel):
    error_rate_threshold: float = 0.05  # 5% error rate
    cpu_threshold: float = 85.0  # 85% CPU usage
    memory_threshold: float = 90.0  # 90% memory usage
    latency_threshold_ms: float = 2000.0  # 2 seconds
    throughput_drop_threshold: float = 0.3  # 30% drop


class Config:
    # WatsonX Orchestrate
    WATSONX_API_KEY: str = os.getenv("WATSONX_API_KEY", "")
    WATSONX_INSTANCE_ID: str = os.getenv("WATSONX_INSTANCE_ID", "")
    WATSONX_AGENT_ID: str = os.getenv("WATSONX_AGENT_ID", "")
    WATSONX_URL: str = os.getenv("WATSONX_URL", "")

    # Slack Integration
    SLACK_WEBHOOK_URL: str = os.getenv("SLACK_WEBHOOK_URL", "")
    SLACK_BOT_TOKEN: str = os.getenv("SLACK_BOT_TOKEN", "")
    SLACK_CHANNEL: str = os.getenv("SLACK_CHANNEL", "#incidents")

    # Discord Integration
    DISCORD_WEBHOOK_URL: str = os.getenv("DISCORD_WEBHOOK_URL", "")

    # Email Integration
    SMTP_HOST: str = os.getenv("SMTP_HOST", "smtp.gmail.com")
    SMTP_PORT: int = int(os.getenv("SMTP_PORT", "587"))
    SMTP_USER: str = os.getenv("SMTP_USER", "")
    SMTP_PASSWORD: str = os.getenv("SMTP_PASSWORD", "")
    EMAIL_FROM: str = os.getenv("EMAIL_FROM", "")
    EMAIL_TO: str = os.getenv("EMAIL_TO", "")

    # Jira Integration
    JIRA_URL: str = os.getenv("JIRA_URL", "")
    JIRA_USER: str = os.getenv("JIRA_USER", "")
    JIRA_API_TOKEN: str = os.getenv("JIRA_API_TOKEN", "")
    JIRA_PROJECT_KEY: str = os.getenv("JIRA_PROJECT_KEY", "")

    # ServiceNow Integration
    SERVICENOW_URL: str = os.getenv("SERVICENOW_URL", "")
    SERVICENOW_USER: str = os.getenv("SERVICENOW_USER", "")
    SERVICENOW_PASSWORD: str = os.getenv("SERVICENOW_PASSWORD", "")

    # Redis (for buffering)
    REDIS_URL: str = os.getenv("REDIS_URL", "redis://localhost:6379")

    # Admin API Key (for server-to-server / admin operations)
    ADMIN_API_KEY: str = os.getenv("ADMIN_API_KEY", "")

    # Thresholds
    THRESHOLDS: ThresholdConfig = ThresholdConfig()

    # Agent Settings
    MAX_AGENT_RETRIES: int = int(os.getenv("MAX_AGENT_RETRIES", "5"))
    STABILITY_CHECK_INTERVAL: int = int(os.getenv("STABILITY_CHECK_INTERVAL", "30"))  # seconds


config = Config()
