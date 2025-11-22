"""
Anomaly Detection Engine
Detects when something looks wrong enough to trigger the agent.
"""
from typing import List, Optional, Dict, Any, Tuple
from datetime import datetime, timedelta
from collections import deque
import statistics

from core import (
    LogEntry, MetricsSnapshot, AnomalyDetection, IncidentSeverity, LogLevel,
    config, logger
)


class StatisticalAnalyzer:
    """Basic statistical analysis for metrics."""

    def __init__(self, window_size: int = 100):
        self.window_size = window_size
        self.history: Dict[str, deque] = {}

    def add_value(self, metric_name: str, value: float):
        """Add a value to the metric history."""
        if metric_name not in self.history:
            self.history[metric_name] = deque(maxlen=self.window_size)
        self.history[metric_name].append(value)

    def get_moving_average(self, metric_name: str, window: int = 10) -> Optional[float]:
        """Calculate moving average for a metric."""
        if metric_name not in self.history or len(self.history[metric_name]) < window:
            return None
        values = list(self.history[metric_name])[-window:]
        return statistics.mean(values)

    def get_std_dev(self, metric_name: str) -> Optional[float]:
        """Calculate standard deviation for a metric."""
        if metric_name not in self.history or len(self.history[metric_name]) < 2:
            return None
        return statistics.stdev(self.history[metric_name])

    def is_outlier(self, metric_name: str, value: float, threshold: float = 2.0) -> bool:
        """Check if a value is an outlier (beyond N standard deviations)."""
        avg = self.get_moving_average(metric_name)
        std = self.get_std_dev(metric_name)

        if avg is None or std is None or std == 0:
            return False

        z_score = abs(value - avg) / std
        return z_score > threshold


class FailurePatternMatcher:
    """Matches known failure patterns in logs."""

    KNOWN_PATTERNS = [
        {
            "name": "database_connection_failure",
            "keywords": ["connection refused", "database", "timeout", "connection pool"],
            "severity": IncidentSeverity.HIGH,
        },
        {
            "name": "out_of_memory",
            "keywords": ["out of memory", "oom", "heap space", "memory allocation"],
            "severity": IncidentSeverity.CRITICAL,
        },
        {
            "name": "disk_full",
            "keywords": ["disk full", "no space left", "disk quota exceeded"],
            "severity": IncidentSeverity.CRITICAL,
        },
        {
            "name": "authentication_failure",
            "keywords": ["authentication failed", "unauthorized", "401", "invalid token"],
            "severity": IncidentSeverity.MEDIUM,
        },
        {
            "name": "rate_limiting",
            "keywords": ["rate limit", "too many requests", "429", "throttled"],
            "severity": IncidentSeverity.MEDIUM,
        },
        {
            "name": "service_unavailable",
            "keywords": ["service unavailable", "503", "upstream", "connection reset"],
            "severity": IncidentSeverity.HIGH,
        },
        {
            "name": "ssl_certificate_issue",
            "keywords": ["ssl", "certificate", "handshake", "tls"],
            "severity": IncidentSeverity.HIGH,
        },
        {
            "name": "null_pointer",
            "keywords": ["nullpointerexception", "null reference", "none type", "undefined"],
            "severity": IncidentSeverity.MEDIUM,
        },
        {
            "name": "deadlock",
            "keywords": ["deadlock", "lock timeout", "waiting for lock"],
            "severity": IncidentSeverity.CRITICAL,
        },
        {
            "name": "network_failure",
            "keywords": ["network unreachable", "dns", "socket", "econnrefused"],
            "severity": IncidentSeverity.HIGH,
        },
    ]

    @classmethod
    def match(cls, logs: List[LogEntry]) -> List[Dict[str, Any]]:
        """Find matching failure patterns in logs."""
        matches = []

        for log in logs:
            message_lower = log.message.lower()
            for pattern in cls.KNOWN_PATTERNS:
                if any(keyword in message_lower for keyword in pattern["keywords"]):
                    matches.append({
                        "pattern": pattern["name"],
                        "severity": pattern["severity"],
                        "log": log,
                    })

        return matches


class AnomalyDetector:
    """Main anomaly detection engine."""

    def __init__(self):
        self.stats = StatisticalAnalyzer()
        self.thresholds = config.THRESHOLDS
        self.force_incident_mode = False

    def force_incident(self, enabled: bool = True):
        """Manual override to force incident mode."""
        self.force_incident_mode = enabled
        logger.info(f"Force incident mode: {enabled}")

    def analyze_metrics(self, snapshot: MetricsSnapshot) -> List[Tuple[str, str, IncidentSeverity]]:
        """Analyze metrics snapshot for anomalies."""
        anomalies = []

        # Update statistical history
        if snapshot.cpu_percent is not None:
            self.stats.add_value("cpu", snapshot.cpu_percent)
        if snapshot.memory_percent is not None:
            self.stats.add_value("memory", snapshot.memory_percent)
        if snapshot.latency_ms is not None:
            self.stats.add_value("latency", snapshot.latency_ms)
        if snapshot.error_rate is not None:
            self.stats.add_value("error_rate", snapshot.error_rate)
        if snapshot.throughput is not None:
            self.stats.add_value("throughput", snapshot.throughput)

        # Check thresholds
        if snapshot.cpu_percent and snapshot.cpu_percent > self.thresholds.cpu_threshold:
            severity = IncidentSeverity.CRITICAL if snapshot.cpu_percent > 95 else IncidentSeverity.HIGH
            anomalies.append(("cpu_high", f"CPU at {snapshot.cpu_percent}%", severity))

        if snapshot.memory_percent and snapshot.memory_percent > self.thresholds.memory_threshold:
            severity = IncidentSeverity.CRITICAL if snapshot.memory_percent > 95 else IncidentSeverity.HIGH
            anomalies.append(("memory_high", f"Memory at {snapshot.memory_percent}%", severity))

        if snapshot.latency_ms and snapshot.latency_ms > self.thresholds.latency_threshold_ms:
            severity = IncidentSeverity.HIGH if snapshot.latency_ms > 5000 else IncidentSeverity.MEDIUM
            anomalies.append(("latency_high", f"Latency at {snapshot.latency_ms}ms", severity))

        if snapshot.error_rate and snapshot.error_rate > self.thresholds.error_rate_threshold:
            severity = IncidentSeverity.CRITICAL if snapshot.error_rate > 0.2 else IncidentSeverity.HIGH
            anomalies.append(("error_rate_high", f"Error rate at {snapshot.error_rate * 100}%", severity))

        # Check for outliers
        if snapshot.latency_ms and self.stats.is_outlier("latency", snapshot.latency_ms, threshold=3.0):
            anomalies.append(("latency_spike", f"Latency spike detected: {snapshot.latency_ms}ms", IncidentSeverity.MEDIUM))

        # Check for throughput drop
        if snapshot.throughput:
            avg_throughput = self.stats.get_moving_average("throughput")
            if avg_throughput and snapshot.throughput < avg_throughput * (1 - self.thresholds.throughput_drop_threshold):
                anomalies.append(("throughput_drop", f"Throughput dropped to {snapshot.throughput}", IncidentSeverity.HIGH))

        return anomalies

    def analyze_logs(self, logs: List[LogEntry]) -> List[Tuple[str, str, IncidentSeverity]]:
        """Analyze logs for anomalies."""
        anomalies = []

        # Count error levels
        error_count = sum(1 for log in logs if log.level in [LogLevel.ERROR, LogLevel.CRITICAL])
        critical_count = sum(1 for log in logs if log.level == LogLevel.CRITICAL)

        if critical_count > 0:
            anomalies.append(("critical_logs", f"{critical_count} critical log entries", IncidentSeverity.CRITICAL))

        if error_count > 5:
            severity = IncidentSeverity.HIGH if error_count > 20 else IncidentSeverity.MEDIUM
            anomalies.append(("error_burst", f"{error_count} error log entries", severity))

        # Check for known failure patterns
        pattern_matches = FailurePatternMatcher.match(logs)
        for match in pattern_matches:
            anomalies.append((
                match["pattern"],
                f"Pattern detected: {match['pattern']} - {match['log'].message[:100]}",
                match["severity"]
            ))

        return anomalies

    def detect(
        self,
        logs: Optional[List[LogEntry]] = None,
        metrics: Optional[MetricsSnapshot] = None
    ) -> AnomalyDetection:
        """Main detection method - combines all analyses."""

        if self.force_incident_mode:
            return AnomalyDetection(
                detected=True,
                anomaly_type="forced_incident",
                severity=IncidentSeverity.HIGH,
                description="Incident mode forced by operator",
                confidence=1.0
            )

        all_anomalies = []

        if metrics:
            all_anomalies.extend(self.analyze_metrics(metrics))

        if logs:
            all_anomalies.extend(self.analyze_logs(logs))

        if not all_anomalies:
            return AnomalyDetection(detected=False)

        # Determine overall severity (highest found)
        severity_order = [IncidentSeverity.LOW, IncidentSeverity.MEDIUM, IncidentSeverity.HIGH, IncidentSeverity.CRITICAL]
        max_severity = max(all_anomalies, key=lambda x: severity_order.index(x[2]))[2]

        # Build description
        descriptions = [a[1] for a in all_anomalies]
        affected = list(set(a[0] for a in all_anomalies))

        logger.log_anomaly_detected(
            anomaly_type=affected[0] if affected else "unknown",
            severity=max_severity.value,
            details={"anomalies": [{"type": a[0], "desc": a[1]} for a in all_anomalies]}
        )

        return AnomalyDetection(
            detected=True,
            anomaly_type=affected[0] if len(affected) == 1 else "multiple",
            severity=max_severity,
            description="; ".join(descriptions[:5]),  # Limit description length
            affected_metrics=affected,
            confidence=min(0.9, 0.5 + 0.1 * len(all_anomalies))  # Higher confidence with more signals
        )


# Global detector instance
anomaly_detector = AnomalyDetector()
