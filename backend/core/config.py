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
    # ==========================================================================
    # Application Settings
    # ==========================================================================
    APP_NAME: str = os.getenv("APP_NAME", "SRA Incident Response")
    DEBUG: bool = os.getenv("DEBUG", "false").lower() == "true"
    FRONTEND_URL: str = os.getenv("FRONTEND_URL", "http://localhost:5173")

    # ==========================================================================
    # Security Settings
    # ==========================================================================
    # Admin API Key (for server-to-server / admin operations)
    ADMIN_API_KEY: str = os.getenv("ADMIN_API_KEY", "")

    # Password hashing settings
    BCRYPT_ROUNDS: int = int(os.getenv("BCRYPT_ROUNDS", "12"))

    # Session settings
    SESSION_TOKEN_EXPIRE_HOURS: int = int(os.getenv("SESSION_TOKEN_EXPIRE_HOURS", "24"))

    # ==========================================================================
    # User & API Key Limits
    # ==========================================================================
    MAX_API_KEYS_PER_USER: int = int(os.getenv("MAX_API_KEYS_PER_USER", "3"))

    # ==========================================================================
    # Rate Limiting
    # ==========================================================================
    RATE_LIMIT_REQUESTS: int = int(os.getenv("RATE_LIMIT_REQUESTS", "100"))  # requests per window
    RATE_LIMIT_WINDOW_SECONDS: int = int(os.getenv("RATE_LIMIT_WINDOW_SECONDS", "60"))  # window size

    # ==========================================================================
    # WatsonX Orchestrate
    # ==========================================================================
    WATSONX_API_KEY: str = os.getenv("WATSONX_API_KEY", "")
    WATSONX_INSTANCE_ID: str = os.getenv("WATSONX_INSTANCE_ID", "")
    WATSONX_AGENT_ID: str = os.getenv("WATSONX_AGENT_ID", "")
    WATSONX_URL: str = os.getenv("WATSONX_URL", "")

    # ==========================================================================
    # Slack Integration
    # ==========================================================================
    SLACK_WEBHOOK_URL: str = os.getenv("SLACK_WEBHOOK_URL", "")
    SLACK_BOT_TOKEN: str = os.getenv("SLACK_BOT_TOKEN", "")
    SLACK_CHANNEL: str = os.getenv("SLACK_CHANNEL", "incidents")

    # Slack OAuth (for multi-workspace installations)
    SLACK_CLIENT_ID: str = os.getenv("SLACK_CLIENT_ID", "")
    SLACK_CLIENT_SECRET: str = os.getenv("SLACK_CLIENT_SECRET", "")
    SLACK_SIGNING_SECRET: str = os.getenv("SLACK_SIGNING_SECRET", "")
    SLACK_REDIRECT_URI: str = os.getenv("SLACK_REDIRECT_URI", "")
    SLACK_SCOPES: str = os.getenv("SLACK_SCOPES", "chat:write,commands,app_mentions:read,channels:history,im:history")

    # ==========================================================================
    # Discord Integration
    # ==========================================================================
    DISCORD_WEBHOOK_URL: str = os.getenv("DISCORD_WEBHOOK_URL", "")

    # ==========================================================================
    # Email Integration
    # ==========================================================================
    SMTP_HOST: str = os.getenv("SMTP_HOST", "smtp.gmail.com")
    SMTP_PORT: int = int(os.getenv("SMTP_PORT", "587"))
    SMTP_USER: str = os.getenv("SMTP_USER", "")
    SMTP_PASSWORD: str = os.getenv("SMTP_PASSWORD", "")
    EMAIL_FROM: str = os.getenv("EMAIL_FROM", "")
    EMAIL_TO: str = os.getenv("EMAIL_TO", "")

    # ==========================================================================
    # Jira Integration
    # ==========================================================================
    JIRA_URL: str = os.getenv("JIRA_URL", "")
    JIRA_USER: str = os.getenv("JIRA_USER", "")
    JIRA_API_TOKEN: str = os.getenv("JIRA_API_TOKEN", "")
    JIRA_PROJECT_KEY: str = os.getenv("JIRA_PROJECT_KEY", "")

    # ==========================================================================
    # ServiceNow Integration
    # ==========================================================================
    SERVICENOW_URL: str = os.getenv("SERVICENOW_URL", "")
    SERVICENOW_USER: str = os.getenv("SERVICENOW_USER", "")
    SERVICENOW_PASSWORD: str = os.getenv("SERVICENOW_PASSWORD", "")

    # ==========================================================================
    # Redis (for buffering/caching)
    # ==========================================================================
    REDIS_URL: str = os.getenv("REDIS_URL", "redis://localhost:6379")

    # ==========================================================================
    # Ingestion Buffer Settings
    # ==========================================================================
    INGESTION_BUFFER_MAX_SIZE: int = int(os.getenv("INGESTION_BUFFER_MAX_SIZE", "10000"))
    INGESTION_BUFFER_TTL_MINUTES: int = int(os.getenv("INGESTION_BUFFER_TTL_MINUTES", "60"))

    # ==========================================================================
    # Thresholds
    # ==========================================================================
    THRESHOLDS: ThresholdConfig = ThresholdConfig()

    # ==========================================================================
    # Agent Settings
    # ==========================================================================
    MAX_AGENT_RETRIES: int = int(os.getenv("MAX_AGENT_RETRIES", "5"))
    STABILITY_CHECK_INTERVAL: int = int(os.getenv("STABILITY_CHECK_INTERVAL", "30"))  # seconds

    # ==========================================================================
    # Auto-Healing Settings
    # ==========================================================================
    # If True, agent will automatically execute recommended healing actions
    # If False (default), actions are only recommended but not executed
    AUTO_EXECUTE_ACTIONS: bool = os.getenv("AUTO_EXECUTE_ACTIONS", "false").lower() == "true"
    # Run autoheal in dry-run mode (log actions but don't execute)
    AUTOHEAL_DRY_RUN: bool = os.getenv("AUTOHEAL_DRY_RUN", "true").lower() == "true"


config = Config()
