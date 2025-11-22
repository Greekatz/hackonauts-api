# System Reliability Assistant (SRA)

Lightweight Python SDK for automatic log collection, metrics tracking, and incident detection.

## Installation

```bash
pip install sra
```

For system metrics collection:
```bash
pip install sra[metrics]
```

## Quick Start

### Basic Logging

```python
from sra import SRALogger

logger = SRALogger(
    api_key="your-api-key",
    endpoint="https://your-backend.com",
    service="my-service",
    environment="production"
)

logger.info("Application started")
logger.warning("High memory usage detected")
logger.error("Database connection failed", extra={"db_host": "localhost"})
```

### Integration with Python Logging

```python
import logging
from sra import SRAHandler

handler = SRAHandler(
    api_key="your-api-key",
    endpoint="https://your-backend.com",
    service="my-service"
)
logging.root.addHandler(handler)

logging.info("This is forwarded to SRA")
logging.error("Errors are captured automatically")
```

### Metrics Collection

```python
from sra import MetricsCollector

metrics = MetricsCollector(
    api_key="your-api-key",
    endpoint="https://your-backend.com",
    service="my-service"
)

metrics.gauge("active_users", 150)
metrics.counter("requests_total")
metrics.timing("request_duration_ms", 45.2)

# Auto-collect system metrics
metrics.start_system_metrics(interval=30)
```

### Exception Capture

```python
from sra import SRALogger, capture_exceptions

logger = SRALogger(api_key="your-key", capture_exceptions=True)

@capture_exceptions(logger)
def risky_function():
    return 1 / 0
```

## Configuration

### SRALogger Options

| Parameter | Type | Default | Description |
|-----------|------|---------|-------------|
| api_key | str | required | Your API key |
| endpoint | str | http://localhost:8000 | Backend URL |
| service | str | None | Service name |
| environment | str | None | Environment |
| capture_exceptions | bool | True | Auto-capture exceptions |
| batch_size | int | 50 | Logs per batch |
| flush_interval | float | 5.0 | Seconds between flushes |

## License

MIT
