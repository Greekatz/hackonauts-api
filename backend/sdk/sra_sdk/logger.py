"""
SRA Logger
Drop-in logging solution with automatic capture and forwarding.
"""
import logging
import sys
import traceback
from typing import Optional, Dict, Any, Callable
from datetime import datetime
from functools import wraps

from .client import SRAClient


class SRALogger:
    """
    High-level logger that captures and forwards logs to SRA backend.

    Usage:
        from sra import SRALogger

        logger = SRALogger(api_key="your-key", endpoint="https://api.example.com")
        logger.info("Application started")
        logger.error("Something went wrong", extra={"user_id": 123})
    """

    LEVELS = {
        "debug": "debug",
        "info": "info",
        "warning": "warning",
        "error": "error",
        "critical": "critical"
    }

    def __init__(
        self,
        api_key: str,
        endpoint: str = "http://localhost:8000",
        service: Optional[str] = None,
        environment: Optional[str] = None,
        capture_exceptions: bool = True,
        **client_kwargs
    ):
        self.client = SRAClient(api_key=api_key, endpoint=endpoint, **client_kwargs)
        self.service = service
        self.environment = environment
        self._default_extra: Dict[str, Any] = {}

        if capture_exceptions:
            self._install_exception_hook()

    def _install_exception_hook(self):
        """Install global exception handler."""
        original_hook = sys.excepthook

        def exception_hook(exc_type, exc_value, exc_tb):
            self.exception(exc_value, exc_info=(exc_type, exc_value, exc_tb))
            original_hook(exc_type, exc_value, exc_tb)

        sys.excepthook = exception_hook

    def set_default_extra(self, **kwargs):
        """Set default extra fields included in all logs."""
        self._default_extra.update(kwargs)

    def _log(self, level: str, message: str, extra: Optional[Dict[str, Any]] = None, exc_info: Optional[tuple] = None):
        """Internal logging method."""
        log_data = {
            "timestamp": datetime.utcnow().isoformat(),
            "level": level,
            "message": message,
            "service": self.service,
            "metadata": {
                **self._default_extra,
                **(extra or {}),
                "environment": self.environment
            }
        }

        if exc_info:
            log_data["metadata"]["exception"] = {
                "type": exc_info[0].__name__ if exc_info[0] else None,
                "message": str(exc_info[1]) if exc_info[1] else None,
                "traceback": "".join(traceback.format_exception(*exc_info)) if exc_info[2] else None
            }

        self.client.send_log(log_data)

    def debug(self, message: str, extra: Optional[Dict[str, Any]] = None):
        """Log a debug message."""
        self._log("debug", message, extra)

    def info(self, message: str, extra: Optional[Dict[str, Any]] = None):
        """Log an info message."""
        self._log("info", message, extra)

    def warning(self, message: str, extra: Optional[Dict[str, Any]] = None):
        """Log a warning message."""
        self._log("warning", message, extra)

    def warn(self, message: str, extra: Optional[Dict[str, Any]] = None):
        """Alias for warning."""
        self.warning(message, extra)

    def error(self, message: str, extra: Optional[Dict[str, Any]] = None, exc_info: bool = False):
        """Log an error message."""
        ei = sys.exc_info() if exc_info else None
        self._log("error", message, extra, exc_info=ei)

    def critical(self, message: str, extra: Optional[Dict[str, Any]] = None, exc_info: bool = False):
        """Log a critical message."""
        ei = sys.exc_info() if exc_info else None
        self._log("critical", message, extra, exc_info=ei)

    def exception(self, message: str = "Exception occurred", extra: Optional[Dict[str, Any]] = None, exc_info: Optional[tuple] = None):
        """Log an exception with traceback."""
        ei = exc_info or sys.exc_info()
        self._log("error", message, extra, exc_info=ei)

    def flush(self):
        """Flush all pending logs."""
        self.client.flush()

    def shutdown(self):
        """Shutdown the logger."""
        self.client.shutdown()


class SRAHandler(logging.Handler):
    """
    Python logging.Handler that forwards logs to SRA.

    Usage:
        import logging
        from sra import SRAHandler

        handler = SRAHandler(api_key="your-key", endpoint="https://api.example.com")
        logging.root.addHandler(handler)

        # Now all standard logging goes to SRA
        logging.info("This goes to SRA")
    """

    LEVEL_MAP = {
        logging.DEBUG: "debug",
        logging.INFO: "info",
        logging.WARNING: "warning",
        logging.ERROR: "error",
        logging.CRITICAL: "critical"
    }

    def __init__(
        self,
        api_key: str,
        endpoint: str = "http://localhost:8000",
        service: Optional[str] = None,
        environment: Optional[str] = None,
        level: int = logging.NOTSET,
        **client_kwargs
    ):
        super().__init__(level)
        self.client = SRAClient(api_key=api_key, endpoint=endpoint, **client_kwargs)
        self.service = service
        self.environment = environment

    def emit(self, record: logging.LogRecord):
        """Emit a log record."""
        try:
            level = self.LEVEL_MAP.get(record.levelno, "info")

            log_data = {
                "timestamp": datetime.utcnow().isoformat(),
                "level": level,
                "message": self.format(record),
                "service": self.service,
                "source": record.name,
                "metadata": {
                    "environment": self.environment,
                    "module": record.module,
                    "function": record.funcName,
                    "line": record.lineno,
                    "pathname": record.pathname
                }
            }

            # Include exception info if present
            if record.exc_info:
                log_data["metadata"]["exception"] = {
                    "type": record.exc_info[0].__name__ if record.exc_info[0] else None,
                    "message": str(record.exc_info[1]) if record.exc_info[1] else None,
                    "traceback": self.formatter.formatException(record.exc_info) if self.formatter else None
                }

            # Include any extra fields
            if hasattr(record, "__dict__"):
                standard_attrs = {
                    "name", "msg", "args", "created", "filename", "funcName",
                    "levelname", "levelno", "lineno", "module", "msecs",
                    "pathname", "process", "processName", "relativeCreated",
                    "stack_info", "exc_info", "exc_text", "thread", "threadName", "message"
                }
                extra = {k: v for k, v in record.__dict__.items() if k not in standard_attrs}
                if extra:
                    log_data["metadata"]["extra"] = extra

            self.client.send_log(log_data)

        except Exception:
            self.handleError(record)

    def close(self):
        """Close the handler."""
        self.client.shutdown()
        super().close()


def capture_exceptions(logger: SRALogger):
    """
    Decorator to capture exceptions from a function.

    Usage:
        @capture_exceptions(logger)
        def my_function():
            # If this raises, it's logged automatically
            raise ValueError("Something went wrong")
    """
    def decorator(func: Callable):
        @wraps(func)
        def wrapper(*args, **kwargs):
            try:
                return func(*args, **kwargs)
            except Exception as e:
                logger.exception(f"Exception in {func.__name__}: {str(e)}")
                raise
        return wrapper
    return decorator
