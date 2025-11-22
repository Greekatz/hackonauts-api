"""
Logging & Debug Layer
Provides structured logging for the backend itself.
"""
import logging
import sys
from datetime import datetime
from typing import Any, Dict, Optional
import json


class StructuredFormatter(logging.Formatter):
    """Custom formatter that outputs JSON structured logs."""

    def format(self, record: logging.LogRecord) -> str:
        log_data = {
            "timestamp": datetime.utcnow().isoformat(),
            "level": record.levelname,
            "logger": record.name,
            "message": record.getMessage(),
            "module": record.module,
            "function": record.funcName,
            "line": record.lineno,
        }

        if hasattr(record, "extra_data"):
            log_data["data"] = record.extra_data

        if record.exc_info:
            log_data["exception"] = self.formatException(record.exc_info)

        return json.dumps(log_data)


class BackendLogger:
    """Logger for backend operations."""

    def __init__(self, name: str = "incident-backend"):
        self.logger = logging.getLogger(name)
        self.logger.setLevel(logging.DEBUG)

        # Console handler with structured output
        console_handler = logging.StreamHandler(sys.stdout)
        console_handler.setLevel(logging.DEBUG)
        console_handler.setFormatter(StructuredFormatter())

        if not self.logger.handlers:
            self.logger.addHandler(console_handler)

    def _log(self, level: int, message: str, data: Optional[Dict[str, Any]] = None):
        extra = {"extra_data": data} if data else {}
        self.logger.log(level, message, extra=extra)

    def debug(self, message: str, data: Optional[Dict[str, Any]] = None):
        self._log(logging.DEBUG, message, data)

    def info(self, message: str, data: Optional[Dict[str, Any]] = None):
        self._log(logging.INFO, message, data)

    def warning(self, message: str, data: Optional[Dict[str, Any]] = None):
        self._log(logging.WARNING, message, data)

    def error(self, message: str, data: Optional[Dict[str, Any]] = None):
        self._log(logging.ERROR, message, data)

    def critical(self, message: str, data: Optional[Dict[str, Any]] = None):
        self._log(logging.CRITICAL, message, data)

    # Specialized logging methods
    def log_api_call(self, endpoint: str, method: str, status: int, duration_ms: float, data: Optional[Dict] = None):
        self.info(f"API Call: {method} {endpoint}", {
            "endpoint": endpoint,
            "method": method,
            "status": status,
            "duration_ms": duration_ms,
            **(data or {})
        })

    def log_agent_request(self, incident_id: str, request_data: Dict):
        self.info(f"Agent Request for incident {incident_id}", {
            "incident_id": incident_id,
            "request": request_data
        })

    def log_agent_response(self, incident_id: str, response_data: Dict, success: bool):
        level = logging.INFO if success else logging.ERROR
        self._log(level, f"Agent Response for incident {incident_id}", {
            "incident_id": incident_id,
            "response": response_data,
            "success": success
        })

    def log_autoheal_action(self, action: str, service: str, success: bool, details: Optional[str] = None):
        level = logging.INFO if success else logging.ERROR
        self._log(level, f"Auto-heal action: {action} on {service}", {
            "action": action,
            "service": service,
            "success": success,
            "details": details
        })

    def log_anomaly_detected(self, anomaly_type: str, severity: str, details: Dict):
        self.warning(f"Anomaly detected: {anomaly_type}", {
            "anomaly_type": anomaly_type,
            "severity": severity,
            **details
        })


# Global logger instance
logger = BackendLogger()
