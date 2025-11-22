"""
System Reliability Assistant (SRA)
Lightweight logging SDK for automatic incident detection and response.
"""
from .client import SRAClient
from .logger import SRALogger, SRAHandler, capture_exceptions
from .metrics import MetricsCollector

__version__ = "0.1.0"
__all__ = ["SRAClient", "SRALogger", "SRAHandler", "MetricsCollector", "capture_exceptions"]
