"""
Metrics Collector
Collects and forwards system and application metrics.
"""
import threading
import time
import platform
from typing import Optional, Dict, Any, Callable
from datetime import datetime

from .client import SRAClient


class MetricsCollector:
    """
    Collects and sends metrics to SRA backend.

    Usage:
        from sra import MetricsCollector

        metrics = MetricsCollector(api_key="your-key", endpoint="https://api.example.com")

        # Manual metrics
        metrics.gauge("active_users", 150)
        metrics.counter("requests_total", 1)
        metrics.timing("request_duration_ms", 45.2)

        # Auto-collect system metrics
        metrics.start_system_metrics(interval=30)
    """

    def __init__(
        self,
        api_key: str,
        endpoint: str = "http://localhost:8000",
        service: Optional[str] = None,
        default_tags: Optional[Dict[str, str]] = None,
        **client_kwargs
    ):
        self.client = SRAClient(api_key=api_key, endpoint=endpoint, **client_kwargs)
        self.service = service
        self.default_tags = default_tags or {}

        self._system_thread: Optional[threading.Thread] = None
        self._stop_system = threading.Event()
        self._counters: Dict[str, float] = {}
        self._lock = threading.Lock()

    def _send_metric(self, name: str, value: float, unit: Optional[str] = None, tags: Optional[Dict[str, str]] = None):
        """Send a metric to the backend."""
        metric_data = {
            "timestamp": datetime.utcnow().isoformat(),
            "name": name,
            "value": value,
            "unit": unit,
            "service": self.service,
            "tags": {**self.default_tags, **(tags or {})}
        }
        self.client.send_metric(metric_data)

    def gauge(self, name: str, value: float, unit: Optional[str] = None, tags: Optional[Dict[str, str]] = None):
        """Record a gauge metric (point-in-time value)."""
        self._send_metric(name, value, unit, tags)

    def counter(self, name: str, increment: float = 1, tags: Optional[Dict[str, str]] = None):
        """Increment a counter metric."""
        with self._lock:
            key = f"{name}:{str(tags)}"
            self._counters[key] = self._counters.get(key, 0) + increment
            self._send_metric(name, self._counters[key], "count", tags)

    def timing(self, name: str, duration_ms: float, tags: Optional[Dict[str, str]] = None):
        """Record a timing metric."""
        self._send_metric(name, duration_ms, "ms", tags)

    def histogram(self, name: str, value: float, unit: Optional[str] = None, tags: Optional[Dict[str, str]] = None):
        """Record a histogram metric."""
        self._send_metric(name, value, unit, tags)

    def timed(self, name: str, tags: Optional[Dict[str, str]] = None):
        """
        Context manager/decorator for timing code blocks.

        Usage:
            with metrics.timed("db_query"):
                result = db.query(...)

            @metrics.timed("process_request")
            def handle_request():
                ...
        """
        return TimedContext(self, name, tags)

    def start_system_metrics(self, interval: float = 30.0):
        """Start collecting system metrics in the background."""
        if self._system_thread and self._system_thread.is_alive():
            return

        self._stop_system.clear()
        self._system_thread = threading.Thread(target=self._collect_system_metrics, args=(interval,), daemon=True)
        self._system_thread.start()

    def stop_system_metrics(self):
        """Stop collecting system metrics."""
        self._stop_system.set()
        if self._system_thread:
            self._system_thread.join(timeout=5.0)

    def _collect_system_metrics(self, interval: float):
        """Background thread for collecting system metrics."""
        while not self._stop_system.is_set():
            try:
                self._send_system_snapshot()
            except Exception:
                pass
            self._stop_system.wait(interval)

    def _send_system_snapshot(self):
        """Collect and send system metrics."""
        try:
            import psutil

            # CPU
            cpu_percent = psutil.cpu_percent(interval=1)
            self.gauge("system.cpu_percent", cpu_percent, "%")

            # Memory
            memory = psutil.virtual_memory()
            self.gauge("system.memory_percent", memory.percent, "%")
            self.gauge("system.memory_used_mb", memory.used / (1024 * 1024), "MB")
            self.gauge("system.memory_available_mb", memory.available / (1024 * 1024), "MB")

            # Disk
            disk = psutil.disk_usage("/")
            self.gauge("system.disk_percent", disk.percent, "%")
            self.gauge("system.disk_used_gb", disk.used / (1024 * 1024 * 1024), "GB")

            # Network (if available)
            try:
                net = psutil.net_io_counters()
                self.gauge("system.network_bytes_sent", net.bytes_sent, "bytes")
                self.gauge("system.network_bytes_recv", net.bytes_recv, "bytes")
            except Exception:
                pass

        except ImportError:
            # psutil not installed, send basic info
            self.gauge("system.platform", 1, tags={"platform": platform.system()})

    def flush(self):
        """Flush all pending metrics."""
        self.client.flush()

    def shutdown(self):
        """Shutdown the metrics collector."""
        self.stop_system_metrics()
        self.client.shutdown()


class TimedContext:
    """Context manager for timing code blocks."""

    def __init__(self, collector: MetricsCollector, name: str, tags: Optional[Dict[str, str]] = None):
        self.collector = collector
        self.name = name
        self.tags = tags
        self.start_time: Optional[float] = None

    def __enter__(self):
        self.start_time = time.time()
        return self

    def __exit__(self, exc_type, exc_val, exc_tb):
        if self.start_time:
            duration_ms = (time.time() - self.start_time) * 1000
            self.collector.timing(self.name, duration_ms, self.tags)
        return False

    def __call__(self, func: Callable):
        """Allow use as a decorator."""
        def wrapper(*args, **kwargs):
            with self:
                return func(*args, **kwargs)
        return wrapper
