# System Reliability Assistant (SRA)

An autonomous incident detection and response platform powered by IBM watsonx. The system ingests logs and metrics, detects anomalies, performs root cause analysis, and executes automated remediation actions.

## Quick Start (For Users)

### 1. Create an Account

```bash
curl -X POST https://your-sra-backend.com/auth/register \
  -H "Content-Type: application/json" \
  -d '{"email": "you@example.com", "password": "your-secure-password"}'
```

Response:
```json
{
  "access_token": "eyJhbGc...",
  "token_type": "bearer",
  "user": {"id": "...", "email": "you@example.com", ...}
}
```

### 2. Generate an API Key

```bash
curl -X POST https://your-sra-backend.com/api-keys \
  -H "Authorization: Bearer eyJhbGc..." \
  -H "Content-Type: application/json" \
  -d '{"name": "my-production-app"}'
```

Response:
```json
{
  "key": "sra_a1b2c3d4e5f6...",
  "name": "my-production-app",
  "created_at": "2025-01-01T00:00:00Z",
  "is_active": true
}
```

Save this key - you'll use it in your application. You can create up to 3 API keys per account.

### 3. Integrate into Your Application

#### Option A: Direct API (Any Language)

```bash
# Send logs
curl -X POST https://your-sra-backend.com/ingest/logs \
  -H "X-API-Key: sra_a1b2c3d4e5f6..." \
  -H "Content-Type: application/json" \
  -d '{
    "logs": [
      {"level": "error", "message": "Database connection timeout", "service": "api-gateway"},
      {"level": "warning", "message": "High memory usage detected", "service": "api-gateway"}
    ]
  }'

# Send metrics
curl -X POST https://your-sra-backend.com/ingest/snapshot \
  -H "X-API-Key: sra_a1b2c3d4e5f6..." \
  -H "Content-Type: application/json" \
  -d '{
    "snapshot": {
      "cpu_percent": 85.5,
      "memory_percent": 72.0,
      "error_rate": 0.05,
      "latency_ms": 250
    }
  }'
```

#### Option B: Python SDK

```bash
pip install sra-sdk
```

```python
from sra_sdk import SRALogger, MetricsCollector

# Initialize logger
logger = SRALogger(
    api_key="sra_a1b2c3d4e5f6...",
    endpoint="https://your-sra-backend.com",
    service="my-service"
)

# Send logs
logger.info("Application started")
logger.error("Database connection failed", extra={"db_host": "localhost"})

# Initialize metrics
metrics = MetricsCollector(
    api_key="sra_a1b2c3d4e5f6...",
    endpoint="https://your-sra-backend.com",
    service="my-service"
)

# Record metrics
metrics.gauge("active_users", 150)
metrics.counter("requests_total")
metrics.timing("request_duration_ms", 45.2)

# Auto-collect system metrics (CPU, memory, etc.)
metrics.start_system_metrics(interval=30)
```

#### Option C: Python Logging Integration

```python
import logging
from sra_sdk import SRAHandler

# Add SRA handler to your existing logging
handler = SRAHandler(
    api_key="sra_a1b2c3d4e5f6...",
    endpoint="https://your-sra-backend.com",
    service="my-service"
)
logging.root.addHandler(handler)

# Your existing logging code now sends to SRA
logging.info("User logged in")
logging.error("Payment failed", extra={"user_id": "123"})
```

### 4. View Incidents

When SRA detects anomalies, it automatically creates incidents:

```bash
# List all incidents
curl -H "X-API-Key: sra_a1b2c3d4e5f6..." \
  https://your-sra-backend.com/incidents

# Get incident details
curl -H "X-API-Key: sra_a1b2c3d4e5f6..." \
  https://your-sra-backend.com/incidents/{incident_id}

# Get incident summary with RCA
curl -H "X-API-Key: sra_a1b2c3d4e5f6..." \
  https://your-sra-backend.com/incidents/{incident_id}/summary
```

---

## Account Management

### Login (Get New Token)

```bash
curl -X POST https://your-sra-backend.com/auth/login \
  -H "Content-Type: application/json" \
  -d '{"email": "you@example.com", "password": "your-password"}'
```

### View Your Profile

```bash
curl -H "Authorization: Bearer your-token" \
  https://your-sra-backend.com/auth/me
```

### List Your API Keys

```bash
curl -H "Authorization: Bearer your-token" \
  https://your-sra-backend.com/api-keys
```

### Revoke an API Key

```bash
curl -X DELETE -H "Authorization: Bearer your-token" \
  https://your-sra-backend.com/api-keys/sra_a1b2c3
```

### Delete an API Key Permanently

```bash
curl -X DELETE -H "Authorization: Bearer your-token" \
  https://your-sra-backend.com/api-keys/sra_a1b2c3/delete
```

---

## What SRA Detects

| Anomaly Type | Detection Method |
|--------------|------------------|
| High Error Rate | Error logs exceed 5% of total |
| CPU Overload | CPU usage > 85% |
| Memory Pressure | Memory usage > 90% |
| Latency Spikes | Response time > 2000ms |
| Database Issues | Connection timeout/refused patterns |
| Disk Full | Disk space warnings |
| Network Errors | Connection reset patterns |

---

## Auto-Healing Actions

When incidents are detected, SRA can automatically execute remediation:

| Action | Description |
|--------|-------------|
| Restart Service | Restart via Docker, Kubernetes, or systemd |
| Scale Replicas | Increase service instances |
| Flush Cache | Clear Redis/Memcached |
| Clear Queue | Drain message queues |
| Reroute Traffic | Redirect to healthy endpoints |
| Rollback | Revert to previous deployment |

---

## Architecture Overview

```
+-------------------+     +-------------------+     +-------------------+
|   Your Services   | --> |   SRA API/SDK     | --> |   Backend API     |
|   (with API Key)  |     |   (Log/Metrics)   |     |   (PostgreSQL)    |
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

---

## API Reference

### Authentication

| Method | Endpoint | Auth | Description |
|--------|----------|------|-------------|
| POST | `/auth/register` | None | Create account |
| POST | `/auth/login` | None | Login, get token |
| POST | `/auth/logout` | Bearer | Logout |
| GET | `/auth/me` | Bearer | Get profile |

### API Keys

| Method | Endpoint | Auth | Description |
|--------|----------|------|-------------|
| POST | `/api-keys` | Bearer | Create key (max 3) |
| GET | `/api-keys` | Bearer | List your keys |
| DELETE | `/api-keys/{prefix}` | Bearer | Revoke key |
| DELETE | `/api-keys/{prefix}/delete` | Bearer | Delete key |

### Data Ingestion

| Method | Endpoint | Auth | Description |
|--------|----------|------|-------------|
| POST | `/ingest/logs` | API Key | Send structured logs |
| POST | `/ingest/logs/raw` | API Key | Send raw log strings |
| POST | `/ingest/metrics` | API Key | Send metrics |
| POST | `/ingest/snapshot` | API Key | Send metrics snapshot |

### Incidents

| Method | Endpoint | Auth | Description |
|--------|----------|------|-------------|
| GET | `/incidents` | API Key | List incidents |
| GET | `/incidents/{id}` | API Key | Get incident details |
| GET | `/incidents/{id}/summary` | API Key | Get summary with RCA |
| POST | `/incidents/{id}/resolve` | API Key | Mark resolved |
| POST | `/incidents/{id}/close` | API Key | Close incident |

### Monitoring

| Method | Endpoint | Auth | Description |
|--------|----------|------|-------------|
| GET | `/health` | None | Health check |
| GET | `/status` | API Key | System status |
| GET | `/anomaly/status` | API Key | Anomaly detection status |
| GET | `/stability/check` | API Key | Stability check |

---

## Self-Hosting

### Prerequisites

- Python 3.8+
- PostgreSQL 13+
- IBM watsonx account (for RCA)

### Installation

```bash
git clone https://github.com/Greekatz/hackonauts-api.git
cd hackonauts-api/backend

# Install dependencies
pip install -r requirements.txt
pip install sqlalchemy asyncpg

# Create PostgreSQL database
createdb sra

# Configure environment
cp .env.example .env
# Edit .env with your settings

# Run the server
python main.py
```

### Environment Variables

```env
# Database (PostgreSQL)
DATABASE_URL=postgresql+asyncpg://postgres:password@localhost:5432/sra

# Admin API Key (generate a strong key)
ADMIN_API_KEY=sra_admin_your_secure_key_here

# watsonx Integration
WATSONX_API_KEY=your-watsonx-api-key
WATSONX_PROJECT_ID=your-project-id
WATSONX_AGENT_URL=https://your-watsonx-agent-endpoint

# Notifications (optional)
SLACK_WEBHOOK_URL=https://hooks.slack.com/services/xxx
DISCORD_WEBHOOK_URL=https://discord.com/api/webhooks/xxx
SMTP_HOST=smtp.gmail.com
SMTP_PORT=587
SMTP_USER=your-email
SMTP_PASSWORD=your-password
```

The server runs at `http://localhost:8000`. API docs at `http://localhost:8000/docs`.

---

## SDK Installation

```bash
pip install sra-sdk
```

For system metrics (CPU, memory):
```bash
pip install sra-sdk[metrics]
```

PyPI: https://pypi.org/project/sra-sdk/

---

## License

MIT
