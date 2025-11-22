# System Reliability Assistant (SRA)

An autonomous incident detection and response platform powered by IBM watsonx. The system ingests logs and metrics, detects anomalies, performs root cause analysis, and executes automated remediation actions.

## Architecture Overview

```
+-------------------+     +-------------------+     +-------------------+
|   Your Services   | --> |   SRA SDK         | --> |   Backend API     |
|   (with SRA SDK)  |     |   (Log/Metrics)   |     |   (FastAPI)       |
+-------------------+     +-------------------+     +-------------------+
                                                            |
                          +-------------------+             |
                          |   watsonx Agent   | <-----------+
                          |   (RCA/Planning)  |             |
                          +-------------------+             |
                                                            v
                          +-------------------+     +-------------------+
                          |   Notifications   | <-- |   Auto-Healing    |
                          |   (Slack/Email)   |     |   (Remediation)   |
                          +-------------------+     +-------------------+
```

## Components

### Backend API (`/backend`)

Production-grade FastAPI backend with the following modules:

| Module | Path | Description |
|--------|------|-------------|
| Core | `/backend/core/` | Configuration, data models, logging |
| Engines | `/backend/engines/` | Ingestion, anomaly detection, stability evaluation, state management |
| Integrations | `/backend/integrations/` | watsonx agent client, auto-healing, notifications |
| Utils | `/backend/utils/` | CLI tool, mock data generator |
| SDK | `/backend/sdk/` | System Reliability Assistant Python SDK |

### System Reliability Assistant SDK (`/backend/sdk`)

Lightweight Python SDK for automatic log collection and metrics tracking.

## Installation

### Backend

```bash
cd backend
pip install -r requirements.txt
python main.py
```

The server runs at `http://localhost:8000`. API documentation is available at `http://localhost:8000/docs`.

### SDK (for your applications)

```bash
pip install sra
```

## Configuration

Copy the environment variables to your `.env` file:

```env
# watsonx Integration
WATSONX_API_KEY=your-api-key
WATSONX_PROJECT_ID=your-project-id
WATSONX_AGENT_URL=https://your-watsonx-agent-endpoint

# API Security
API_KEY=your-backend-api-key

# Notifications (optional)
SLACK_WEBHOOK_URL=
DISCORD_WEBHOOK_URL=
SMTP_HOST=smtp.gmail.com
SMTP_PORT=587
SMTP_USER=
SMTP_PASSWORD=

# Ticketing (optional)
JIRA_URL=
JIRA_USER=
JIRA_API_TOKEN=
JIRA_PROJECT_KEY=
```

## Usage

### Integrating the SDK

```python
from sra import SRALogger, MetricsCollector

# Initialize logger
logger = SRALogger(
    api_key="your-api-key",
    endpoint="https://your-backend.com",
    service="my-service",
    environment="production"
)

# Log events
logger.info("Application started")
logger.error("Database connection failed", extra={"db_host": "localhost"})

# Initialize metrics
metrics = MetricsCollector(
    api_key="your-api-key",
    endpoint="https://your-backend.com",
    service="my-service"
)

# Record metrics
metrics.gauge("active_users", 150)
metrics.counter("requests_total")
metrics.timing("request_duration_ms", 45.2)

# Auto-collect system metrics
metrics.start_system_metrics(interval=30)
```

### Using with Python Logging

```python
import logging
from sra import SRAHandler

handler = SRAHandler(
    api_key="your-api-key",
    endpoint="https://your-backend.com",
    service="my-service"
)
logging.root.addHandler(handler)

# All standard logging now goes to the platform
logging.info("This is captured by SRA")
```

### CLI Tool

```bash
# Check backend health
python -m backend.utils.cli health

# Generate a mock incident for testing
python -m backend.utils.cli generate-incident --type database

# List incidents
python -m backend.utils.cli list-incidents

# Trigger agent for an incident
python -m backend.utils.cli trigger-agent <incident_id>

# Check system stability
python -m backend.utils.cli check-stability

# Execute auto-heal action
python -m backend.utils.cli autoheal restart my-service
```

## API Endpoints

### Health and Status

| Method | Endpoint | Description |
|--------|----------|-------------|
| GET | `/health` | Health check |
| GET | `/status` | System status |

### Log and Metrics Ingestion

| Method | Endpoint | Description |
|--------|----------|-------------|
| POST | `/ingest/logs` | Ingest structured logs |
| POST | `/ingest/logs/raw` | Ingest raw log strings |
| POST | `/ingest/metrics` | Ingest metrics |
| POST | `/ingest/snapshot` | Ingest metrics snapshot |

### Anomaly Detection

| Method | Endpoint | Description |
|--------|----------|-------------|
| GET | `/anomaly/status` | Get anomaly detection status |
| POST | `/anomaly/force-incident` | Force incident mode |

### Agent and RCA

| Method | Endpoint | Description |
|--------|----------|-------------|
| POST | `/agent/trigger` | Trigger agent for incident |
| POST | `/agent/force-rca` | Force RCA with provided data |

### Stability

| Method | Endpoint | Description |
|--------|----------|-------------|
| GET | `/stability/check` | Check system stability |
| POST | `/stability/set-baseline` | Set stability baseline |

### Auto-Healing

| Method | Endpoint | Description |
|--------|----------|-------------|
| POST | `/autoheal/restart` | Restart a service |
| POST | `/autoheal/scale` | Scale service replicas |
| POST | `/autoheal/flush` | Flush cache |
| POST | `/autoheal/clear-queue` | Clear message queue |
| POST | `/autoheal/reroute` | Reroute traffic |
| POST | `/autoheal/rollback` | Rollback deployment |
| GET | `/autoheal/actions` | List available actions |

### Incident Management

| Method | Endpoint | Description |
|--------|----------|-------------|
| GET | `/incidents` | List incidents |
| GET | `/incidents/{id}` | Get incident details |
| GET | `/incidents/{id}/summary` | Get incident summary |
| GET | `/incidents/{id}/history` | Get incident history |
| POST | `/incidents/{id}/resolve` | Resolve incident |
| POST | `/incidents/{id}/close` | Close incident |

### Notifications

| Method | Endpoint | Description |
|--------|----------|-------------|
| POST | `/notify/{incident_id}` | Send notifications |
| POST | `/notify/custom` | Send custom notification |

### Testing

| Method | Endpoint | Description |
|--------|----------|-------------|
| POST | `/mock/generate-incident` | Generate mock incident |
| POST | `/mock/generate-logs` | Generate mock logs |
| POST | `/mock/generate-metrics` | Generate mock metrics |
| GET | `/mock/incident-types` | List mock incident types |

## Features

### Anomaly Detection

- Error rate spike detection
- Latency outlier detection
- CPU and memory threshold monitoring
- Known failure pattern matching (database, memory, disk, network issues)
- Configurable thresholds

### Auto-Healing Actions

- Service restart (Docker, Kubernetes, systemd)
- Replica scaling
- Cache flushing (Redis, Memcached)
- Queue clearing (RabbitMQ, Redis)
- Traffic rerouting
- Deployment rollback
- Dry-run mode for testing

### Notification Channels

- Slack (webhook)
- Discord (webhook)
- Email (SMTP)
- Jira (ticket creation)
- ServiceNow (incident creation)

### Stability Evaluation

- Metrics threshold checking
- Log error rate analysis
- Baseline comparison
- Trend analysis (stable, improving, degrading, critical)
- Agent re-run logic based on stability

## Project Structure

```
hackonauts-api/
├── .env                    # Environment configuration
├── README.md               # This file
└── backend/
    ├── main.py             # FastAPI application entry point
    ├── requirements.txt    # Python dependencies
    ├── core/
    │   ├── __init__.py
    │   ├── config.py       # Configuration management
    │   ├── models.py       # Pydantic data models
    │   └── logger.py       # Structured logging
    ├── engines/
    │   ├── __init__.py
    │   ├── ingestion.py    # Log/metrics ingestion and parsing
    │   ├── anomaly_detection.py  # Anomaly detection engine
    │   ├── stability.py    # Stability evaluation
    │   └── state_manager.py # Incident state management
    ├── integrations/
    │   ├── __init__.py
    │   ├── agent_client.py # watsonx agent client
    │   ├── autoheal.py     # Auto-healing execution
    │   └── notifications.py # Notification services
    ├── utils/
    │   ├── __init__.py
    │   ├── cli.py          # Command-line interface
    │   └── mock_data.py    # Mock data generator
    └── sdk/
        ├── __init__.py
        ├── client.py       # SRA HTTP client
        ├── logger.py       # SRALogger, SRAHandler
        ├── metrics.py      # MetricsCollector
        ├── setup.py        # PyPI package configuration
        └── README.md       # SDK documentation
```

## License

MIT
