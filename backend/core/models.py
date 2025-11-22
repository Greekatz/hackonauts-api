"""
Data Models for the Incident Response Backend
"""
from pydantic import BaseModel, Field
from typing import Optional, List, Dict, Any
from datetime import datetime
from enum import Enum
import uuid


class LogLevel(str, Enum):
    DEBUG = "debug"
    INFO = "info"
    WARNING = "warning"
    ERROR = "error"
    CRITICAL = "critical"


class IncidentSeverity(str, Enum):
    LOW = "low"
    MEDIUM = "medium"
    HIGH = "high"
    CRITICAL = "critical"


class IncidentStatus(str, Enum):
    OPEN = "open"
    INVESTIGATING = "investigating"
    MITIGATING = "mitigating"
    RESOLVED = "resolved"
    CLOSED = "closed"


class LogEntry(BaseModel):
    timestamp: datetime = Field(default_factory=lambda: datetime.utcnow())
    level: LogLevel = LogLevel.INFO
    message: str
    source: Optional[str] = None
    service: Optional[str] = None
    trace_id: Optional[str] = None
    metadata: Dict[str, Any] = Field(default_factory=dict)


class MetricEntry(BaseModel):
    timestamp: datetime = Field(default_factory=lambda: datetime.utcnow())
    name: str
    value: float
    unit: Optional[str] = None
    service: Optional[str] = None
    tags: Dict[str, str] = Field(default_factory=dict)


class MetricsSnapshot(BaseModel):
    timestamp: datetime = Field(default_factory=lambda: datetime.utcnow())
    cpu_percent: Optional[float] = None
    memory_percent: Optional[float] = None
    latency_ms: Optional[float] = None
    error_rate: Optional[float] = None
    throughput: Optional[float] = None
    custom_metrics: Dict[str, float] = Field(default_factory=dict)


class AnomalyDetection(BaseModel):
    detected: bool = False
    anomaly_type: Optional[str] = None
    severity: IncidentSeverity = IncidentSeverity.LOW
    description: Optional[str] = None
    affected_metrics: List[str] = Field(default_factory=list)
    confidence: float = 0.0


class RCAResult(BaseModel):
    root_cause: str
    contributing_factors: List[str] = Field(default_factory=list)
    evidence: List[str] = Field(default_factory=list)
    confidence: float = 0.0


class RecoveryAction(BaseModel):
    action_type: str
    description: str
    parameters: Dict[str, Any] = Field(default_factory=dict)
    automated: bool = False
    executed: bool = False
    result: Optional[str] = None
    executed_at: Optional[datetime] = None


class StabilityReport(BaseModel):
    timestamp: datetime = Field(default_factory=lambda: datetime.utcnow())
    is_stable: bool = False
    metrics_ok: bool = False
    logs_ok: bool = False
    error_rate: Optional[float] = None
    details: str = ""
    llm_judgment: Optional[str] = None


class Incident(BaseModel):
    id: str = Field(default_factory=lambda: str(uuid.uuid4()))
    created_at: datetime = Field(default_factory=lambda: datetime.utcnow())
    updated_at: datetime = Field(default_factory=lambda: datetime.utcnow())
    status: IncidentStatus = IncidentStatus.OPEN
    severity: IncidentSeverity = IncidentSeverity.MEDIUM
    title: str = ""
    description: str = ""

    # Context
    logs: List[LogEntry] = Field(default_factory=list)
    metrics: List[MetricsSnapshot] = Field(default_factory=list)
    anomaly: Optional[AnomalyDetection] = None

    # Analysis
    rca: Optional[RCAResult] = None
    recommended_actions: List[RecoveryAction] = Field(default_factory=list)
    actions_taken: List[RecoveryAction] = Field(default_factory=list)

    # Stability tracking
    stability_reports: List[StabilityReport] = Field(default_factory=list)
    agent_runs: int = 0

    # Resolution
    resolution_summary: Optional[str] = None
    resolved_at: Optional[datetime] = None


class AgentRequest(BaseModel):
    incident_id: str
    logs: List[LogEntry]
    metrics: List[MetricsSnapshot]
    context: Dict[str, Any] = Field(default_factory=dict)


class AgentResponse(BaseModel):
    incident_id: str
    rca: Optional[RCAResult] = None
    recommended_actions: List[RecoveryAction] = Field(default_factory=list)
    summary: str = ""
    system_ok: bool = False
    confidence: float = 0.0
    raw_response: Optional[str] = None


# Request/Response models for API
class LogIngestionRequest(BaseModel):
    logs: List[LogEntry]
    service: Optional[str] = None


class MetricIngestionRequest(BaseModel):
    metrics: List[MetricEntry]
    service: Optional[str] = None


class MetricsSnapshotRequest(BaseModel):
    snapshot: MetricsSnapshot
    service: Optional[str] = None


class AutoHealRequest(BaseModel):
    incident_id: Optional[str] = None
    service: Optional[str] = None
    parameters: Dict[str, Any] = Field(default_factory=dict)


class NotificationRequest(BaseModel):
    incident_id: str
    channel: str  # slack, email, discord, jira, servicenow
    message: Optional[str] = None
    priority: str = "medium"


class ForceRCARequest(BaseModel):
    logs: Optional[List[LogEntry]] = None
    metrics: Optional[List[MetricsSnapshot]] = None
    description: Optional[str] = None


# User Authentication
class User(BaseModel):
    id: str = Field(default_factory=lambda: str(uuid.uuid4()))
    email: str
    password_hash: str
    created_at: datetime = Field(default_factory=lambda: datetime.utcnow())
    is_active: bool = True


class UserRegisterRequest(BaseModel):
    email: str
    password: str


class UserLoginRequest(BaseModel):
    email: str
    password: str


class UserResponse(BaseModel):
    id: str
    email: str
    created_at: datetime
    is_active: bool


class TokenResponse(BaseModel):
    access_token: str
    token_type: str = "bearer"
    user: UserResponse


# API Key Management
class APIKey(BaseModel):
    key: str = Field(default_factory=lambda: f"sra_{uuid.uuid4().hex}")
    name: str
    user_id: str  # Links to user
    created_at: datetime = Field(default_factory=lambda: datetime.utcnow())
    last_used: Optional[datetime] = None
    is_active: bool = True


class APIKeyCreateRequest(BaseModel):
    name: str


class APIKeyResponse(BaseModel):
    key: str
    name: str
    created_at: datetime
    is_active: bool
