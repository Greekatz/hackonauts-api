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

## How SRA Works

### LLM-Powered Monitoring

SRA uses IBM watsonx to continuously monitor your system every 5 minutes. The LLM analyzes:
- Recent logs (INFO, WARNING, ERROR, CRITICAL)
- System metrics (CPU, memory, latency, error rates)

The LLM is configured to be **conservative** - it only flags clear, significant problems like:
- ERROR or CRITICAL log messages indicating actual failures
- Severe resource exhaustion (very high CPU/memory)
- Service outages, crashes, or connection failures
- Sustained high error rates

Normal operational variation and INFO/DEBUG logs are ignored.

### Detection Examples

| Anomaly Type | What Triggers It |
|--------------|------------------|
| Database Failure | Connection refused, timeout, pool exhausted |
| Memory Leak | OOM errors, heap space exhausted |
| CPU Overload | Health check failures, thread pool exhausted |
| Disk Full | No space left on device errors |
| External API Down | Circuit breaker open, upstream timeouts |
| Auth Failures | Spike in 401 errors, JWT validation failures |

---

## Auto-Healing Actions

When incidents are detected, SRA sends alerts to Slack with recommended fix actions. Users can choose to execute auto-healing with a single button click.

### Slack-Based Workflow

```
LLM Detects Issue → Creates Incident → Sends to Slack
                                            ↓
                    ┌─────────────────────────────────────────┐
                    │  Slack Alert with:                      │
                    │  - Issue summary & root cause           │
                    │  - Recommended actions                  │
                    │  - "Execute Auto-Fix" button            │
                    └─────────────────────────────────────────┘
                                            ↓
                    User clicks button → Actions executed
                    (respects AUTOHEAL_DRY_RUN setting)
```

### Available Actions

| Action | Description |
|--------|-------------|
| restart_service | Restart via Docker, Kubernetes, or systemd |
| scale_replicas | Increase service instances |
| flush_cache | Clear Redis/Memcached |
| clear_queue | Drain message queues |
| reroute_traffic | Redirect to healthy endpoints |
| rollback_deployment | Revert to previous deployment |
| clear_disk | Free up disk space |

### Safety Controls

| Setting | Default | Description |
|---------|---------|-------------|
| `AUTOHEAL_DRY_RUN` | `true` | Log actions without executing (safe mode) |

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
| GET | `/version` | None | API version info |
| GET | `/status` | API Key | System status |
| GET | `/anomaly/status` | API Key | Anomaly detection status |
| GET | `/stability/check` | API Key | Stability check |

### Slack Integration

| Method | Endpoint | Auth | Description |
|--------|----------|------|-------------|
| GET | `/slack/install` | Bearer | Get Slack OAuth install URL |
| GET | `/slack/oauth/callback` | None | OAuth callback handler |
| POST | `/slack/events` | Slack Signature | Slack events webhook |
| POST | `/slack/commands` | Slack Signature | Slash commands handler |
| GET | `/slack/workspaces` | Bearer | List connected workspaces |
| DELETE | `/slack/workspaces/{team_id}` | None | Disconnect workspace |
| POST | `/slack/workspaces/{team_id}/test` | Bearer | Test connection |

### Auto-Healing

| Method | Endpoint | Auth | Description |
|--------|----------|------|-------------|
| POST | `/autoheal/{action}` | API Key | Execute healing action |
| GET | `/autoheal/actions` | API Key | List available actions |
| POST | `/autoheal/dry-run` | API Key | Enable/disable dry run |

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

# Slack App (for multi-workspace bot)
SLACK_CLIENT_ID=your-slack-client-id
SLACK_CLIENT_SECRET=your-slack-client-secret
SLACK_SIGNING_SECRET=your-slack-signing-secret
SLACK_REDIRECT_URI=https://your-domain.com/slack/oauth/callback

# Auto-Healing (optional)
AUTOHEAL_DRY_RUN=true         # Set to false to actually run commands
```

The server runs at `http://localhost:8000`. API docs at `http://localhost:8000/docs`.

---

## Slack Bot Setup

SRA includes a Slack bot for real-time incident alerts and slash commands.

### 1. Create a Slack App

1. Go to [api.slack.com/apps](https://api.slack.com/apps) and create a new app
2. Under **OAuth & Permissions**, add these bot token scopes:
   - `channels:join`, `channels:read`, `chat:write`
   - `commands`, `groups:read`, `im:read`, `im:write`
   - `users:read`

### 2. Configure Slash Commands

Add these commands under **Slash Commands**:
- `/sra-status` - Check system status
- `/sra-check` - Review recent logs for errors
- `/sra-incidents` - List recent incidents
- `/sra-rca` - Trigger root cause analysis

### 3. Enable Events

Under **Event Subscriptions**:
- Request URL: `https://your-domain.com/slack/events`
- Subscribe to: `app_mention`, `member_joined_channel`, `message.im`

### 4. Install to Workspace

Users can connect their Slack workspace via:
```bash
curl -H "Authorization: Bearer your-token" \
  https://your-sra-backend.com/slack/install
```

The bot will:
- Auto-join `#incidents` channel if it exists
- Send welcome messages when added to channels
- Broadcast alerts with `@channel` when incidents occur

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
