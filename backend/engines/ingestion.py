"""
Log & Metrics Ingestion Layer
Handles continuous intake of operational signals.
"""
from typing import List, Dict, Any, Optional
from datetime import datetime, timedelta
from collections import deque
import json
import re

from core import LogEntry, MetricEntry, MetricsSnapshot, LogLevel, logger


class LogParser:
    """Parses various log formats into structured LogEntry objects."""

    # Common log patterns
    PATTERNS = {
        "json": r'^\s*\{.*\}\s*$',
        "apache": r'^(\S+) \S+ \S+ \[([^\]]+)\] "([^"]*)" (\d+) (\d+)',
        "nginx": r'^(\S+) - \S+ \[([^\]]+)\] "([^"]*)" (\d+) (\d+)',
        "syslog": r'^(\w+\s+\d+\s+\d+:\d+:\d+)\s+(\S+)\s+(\S+):\s+(.*)$',
        "python": r'^(\d{4}-\d{2}-\d{2}\s+\d{2}:\d{2}:\d{2},\d+)\s+-\s+(\w+)\s+-\s+(.*)$',
    }

    LEVEL_KEYWORDS = {
        LogLevel.DEBUG: ["debug", "trace", "verbose"],
        LogLevel.INFO: ["info", "information"],
        LogLevel.WARNING: ["warn", "warning"],
        LogLevel.ERROR: ["error", "err", "fail", "failed", "failure"],
        LogLevel.CRITICAL: ["critical", "fatal", "panic", "emergency"],
    }

    @classmethod
    def parse(cls, raw_log: str, source: Optional[str] = None) -> LogEntry:
        """Parse a raw log string into a LogEntry."""
        # Try JSON first
        if re.match(cls.PATTERNS["json"], raw_log.strip()):
            try:
                data = json.loads(raw_log)
                return LogEntry(
                    timestamp=cls._parse_timestamp(data.get("timestamp", data.get("time", data.get("@timestamp")))),
                    level=cls._extract_level(data.get("level", data.get("severity", "info"))),
                    message=data.get("message", data.get("msg", str(data))),
                    source=source or data.get("source", data.get("logger")),
                    service=data.get("service", data.get("app")),
                    trace_id=data.get("trace_id", data.get("traceId")),
                    metadata=data
                )
            except json.JSONDecodeError:
                pass

        # Try other patterns
        for pattern_name, pattern in cls.PATTERNS.items():
            if pattern_name == "json":
                continue
            match = re.match(pattern, raw_log)
            if match:
                return cls._parse_pattern(pattern_name, match, raw_log, source)

        # Fallback: plain text
        return LogEntry(
            timestamp=datetime.utcnow(),
            level=cls._detect_level(raw_log),
            message=raw_log,
            source=source
        )

    @classmethod
    def _parse_timestamp(cls, ts: Any) -> datetime:
        """Parse various timestamp formats."""
        if ts is None:
            return datetime.utcnow()
        if isinstance(ts, datetime):
            return ts
        if isinstance(ts, (int, float)):
            return datetime.fromtimestamp(ts)

        # Try common formats
        formats = [
            "%Y-%m-%dT%H:%M:%S.%fZ",
            "%Y-%m-%dT%H:%M:%SZ",
            "%Y-%m-%d %H:%M:%S,%f",
            "%Y-%m-%d %H:%M:%S",
            "%d/%b/%Y:%H:%M:%S %z",
        ]
        for fmt in formats:
            try:
                return datetime.strptime(str(ts), fmt)
            except ValueError:
                continue

        return datetime.utcnow()

    @classmethod
    def _extract_level(cls, level_str: str) -> LogLevel:
        """Extract log level from string."""
        level_lower = str(level_str).lower()
        for level, keywords in cls.LEVEL_KEYWORDS.items():
            if level_lower in keywords or level_lower == level.value:
                return level
        return LogLevel.INFO

    @classmethod
    def _detect_level(cls, message: str) -> LogLevel:
        """Detect log level from message content."""
        message_lower = message.lower()
        for level, keywords in reversed(list(cls.LEVEL_KEYWORDS.items())):
            for keyword in keywords:
                if keyword in message_lower:
                    return level
        return LogLevel.INFO

    @classmethod
    def _parse_pattern(cls, pattern_name: str, match, raw_log: str, source: Optional[str]) -> LogEntry:
        """Parse matched pattern into LogEntry."""
        groups = match.groups()

        if pattern_name in ["apache", "nginx"]:
            return LogEntry(
                timestamp=cls._parse_timestamp(groups[1]),
                level=LogLevel.ERROR if int(groups[3]) >= 400 else LogLevel.INFO,
                message=f"{groups[2]} - {groups[3]}",
                source=source or groups[0],
                metadata={"status_code": int(groups[3]), "bytes": int(groups[4])}
            )
        elif pattern_name == "syslog":
            return LogEntry(
                timestamp=cls._parse_timestamp(groups[0]),
                level=cls._detect_level(groups[3]),
                message=groups[3],
                source=source or groups[1],
                service=groups[2]
            )
        elif pattern_name == "python":
            return LogEntry(
                timestamp=cls._parse_timestamp(groups[0]),
                level=cls._extract_level(groups[1]),
                message=groups[2],
                source=source
            )

        return LogEntry(message=raw_log, source=source)

    @classmethod
    def parse_multiline(cls, raw_logs: str, source: Optional[str] = None) -> List[LogEntry]:
        """Parse multiline logs (e.g., stack traces)."""
        entries = []
        current_entry = []
        stack_trace_pattern = r'^\s+(at\s+|Traceback|File\s+"|Caused by:|\.\.\.)'

        for line in raw_logs.split('\n'):
            if not line.strip():
                continue

            # Check if this is a continuation (stack trace line)
            if re.match(stack_trace_pattern, line) and current_entry:
                current_entry.append(line)
            else:
                # Save previous entry if exists
                if current_entry:
                    combined = '\n'.join(current_entry)
                    entries.append(cls.parse(combined, source))
                current_entry = [line]

        # Don't forget the last entry
        if current_entry:
            combined = '\n'.join(current_entry)
            entries.append(cls.parse(combined, source))

        return entries


class IngestionBuffer:
    """In-memory buffer for logs and metrics with TTL."""

    def __init__(self, max_size: int = None, ttl_minutes: int = None):
        from core import config
        self.max_size = max_size or config.INGESTION_BUFFER_MAX_SIZE
        self.ttl = timedelta(minutes=ttl_minutes or config.INGESTION_BUFFER_TTL_MINUTES)
        self.logs: deque = deque(maxlen=self.max_size)
        self.metrics: deque = deque(maxlen=self.max_size)
        self.snapshots: deque = deque(maxlen=1000)

    def add_log(self, entry: LogEntry):
        """Add a log entry to the buffer."""
        self.logs.append(entry)
        self._cleanup()

    def add_logs(self, entries: List[LogEntry]):
        """Add multiple log entries."""
        for entry in entries:
            self.logs.append(entry)
        self._cleanup()

    def add_metric(self, entry: MetricEntry):
        """Add a metric entry to the buffer."""
        self.metrics.append(entry)
        self._cleanup()

    def add_metrics(self, entries: List[MetricEntry]):
        """Add multiple metric entries."""
        for entry in entries:
            self.metrics.append(entry)
        self._cleanup()

    def add_snapshot(self, snapshot: MetricsSnapshot):
        """Add a metrics snapshot."""
        self.snapshots.append(snapshot)

    def get_recent_logs(self, minutes: int = 15, level: Optional[LogLevel] = None) -> List[LogEntry]:
        """Get recent logs within time window."""
        cutoff = datetime.utcnow() - timedelta(minutes=minutes)
        logs = [log for log in self.logs if log.timestamp >= cutoff]
        if level:
            logs = [log for log in logs if log.level == level]
        return logs

    def get_recent_metrics(self, minutes: int = 15, name: Optional[str] = None) -> List[MetricEntry]:
        """Get recent metrics within time window."""
        cutoff = datetime.utcnow() - timedelta(minutes=minutes)
        metrics = [m for m in self.metrics if m.timestamp >= cutoff]
        if name:
            metrics = [m for m in metrics if m.name == name]
        return metrics

    def get_recent_snapshots(self, count: int = 10) -> List[MetricsSnapshot]:
        """Get the most recent metric snapshots."""
        return list(self.snapshots)[-count:]

    def get_error_logs(self, minutes: int = 15) -> List[LogEntry]:
        """Get error and critical logs."""
        cutoff = datetime.utcnow() - timedelta(minutes=minutes)
        return [
            log for log in self.logs
            if log.timestamp >= cutoff and log.level in [LogLevel.ERROR, LogLevel.CRITICAL]
        ]

    def _cleanup(self):
        """Remove entries older than TTL."""
        cutoff = datetime.utcnow() - self.ttl

        # Clean logs
        while self.logs and self.logs[0].timestamp < cutoff:
            self.logs.popleft()

        # Clean metrics
        while self.metrics and self.metrics[0].timestamp < cutoff:
            self.metrics.popleft()


class MetricsNormalizer:
    """Normalizes metrics into a standard format."""

    METRIC_ALIASES = {
        "cpu": ["cpu_percent", "cpu_usage", "cpu_utilization", "processor"],
        "memory": ["memory_percent", "mem_usage", "ram_usage", "memory_utilization"],
        "latency": ["latency_ms", "response_time", "duration", "elapsed"],
        "error_rate": ["error_percent", "failure_rate", "error_ratio"],
        "throughput": ["requests_per_second", "rps", "qps", "tps"],
    }

    @classmethod
    def normalize(cls, metrics: List[MetricEntry]) -> MetricsSnapshot:
        """Convert a list of metrics into a normalized snapshot."""
        snapshot = MetricsSnapshot()

        for metric in metrics:
            name_lower = metric.name.lower()

            # Map to standard names
            for standard_name, aliases in cls.METRIC_ALIASES.items():
                if name_lower in aliases or name_lower == standard_name:
                    if standard_name == "cpu":
                        snapshot.cpu_percent = metric.value
                    elif standard_name == "memory":
                        snapshot.memory_percent = metric.value
                    elif standard_name == "latency":
                        snapshot.latency_ms = metric.value
                    elif standard_name == "error_rate":
                        snapshot.error_rate = metric.value
                    elif standard_name == "throughput":
                        snapshot.throughput = metric.value
                    break
            else:
                # Store as custom metric
                snapshot.custom_metrics[metric.name] = metric.value

        return snapshot


# Global ingestion buffer
ingestion_buffer = IngestionBuffer()
