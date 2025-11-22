"""
Testing & Mock Data Utilities
Generates synthetic incidents and data for testing/demos.
"""
import random
from datetime import datetime, timedelta
from typing import List, Optional, Dict, Any
import uuid

from core import (
    LogEntry, MetricEntry, MetricsSnapshot, LogLevel,
    IncidentSeverity, Incident
)


class MockDataGenerator:
    """Generates realistic mock data for testing."""

    # Sample service names
    SERVICES = [
        "api-gateway", "auth-service", "user-service", "payment-service",
        "inventory-service", "order-service", "notification-service",
        "cache-service", "database-proxy", "load-balancer"
    ]

    # Sample error messages by type
    ERROR_TEMPLATES = {
        "database": [
            "Connection refused to database server at {host}:{port}",
            "Database connection pool exhausted - max connections: {max}",
            "Query timeout after {timeout}ms: {query}",
            "Deadlock detected in transaction {tx_id}",
            "Replication lag exceeded threshold: {lag}ms"
        ],
        "memory": [
            "OutOfMemoryError: Java heap space",
            "Memory allocation failed: requested {size}MB, available {available}MB",
            "GC overhead limit exceeded - heap usage at {percent}%",
            "OOM killer invoked for process {pid}",
            "Memory leak detected in {component}: {growth}MB/hour"
        ],
        "network": [
            "Connection reset by peer: {host}",
            "DNS resolution failed for {hostname}",
            "Socket timeout connecting to {service}: {timeout}ms",
            "SSL handshake failed: certificate expired",
            "Connection refused: {host}:{port}"
        ],
        "service": [
            "Service {service} returned HTTP {status}",
            "Circuit breaker OPEN for {service}",
            "Request to {service} timed out after {timeout}ms",
            "Service {service} is unavailable",
            "Rate limit exceeded for {service}: {rate}/s"
        ],
        "disk": [
            "No space left on device: {mount}",
            "Disk quota exceeded for user {user}",
            "I/O error on device {device}: {error}",
            "Filesystem {fs} is read-only",
            "Disk usage critical: {mount} at {percent}%"
        ]
    }

    INFO_TEMPLATES = [
        "Request processed successfully in {time}ms",
        "User {user_id} logged in from {ip}",
        "Cache hit for key {key}",
        "Health check passed for {service}",
        "Configuration reloaded for {component}",
        "Scheduled job {job} completed successfully"
    ]

    @classmethod
    def generate_log_entry(
        cls,
        level: Optional[LogLevel] = None,
        error_type: Optional[str] = None,
        service: Optional[str] = None
    ) -> LogEntry:
        """Generate a single log entry."""
        if level is None:
            level = random.choices(
                [LogLevel.DEBUG, LogLevel.INFO, LogLevel.WARNING, LogLevel.ERROR, LogLevel.CRITICAL],
                weights=[10, 60, 15, 12, 3]
            )[0]

        service = service or random.choice(cls.SERVICES)

        if level in [LogLevel.ERROR, LogLevel.CRITICAL]:
            error_type = error_type or random.choice(list(cls.ERROR_TEMPLATES.keys()))
            template = random.choice(cls.ERROR_TEMPLATES[error_type])
            message = cls._fill_template(template)
        else:
            template = random.choice(cls.INFO_TEMPLATES)
            message = cls._fill_template(template)

        return LogEntry(
            timestamp=datetime.utcnow() - timedelta(seconds=random.randint(0, 300)),
            level=level,
            message=message,
            service=service,
            source=f"{service}-{random.randint(1, 5)}",
            trace_id=str(uuid.uuid4())[:8] if random.random() > 0.5 else None
        )

    @classmethod
    def _fill_template(cls, template: str) -> str:
        """Fill in template placeholders with realistic values."""
        replacements = {
            "{host}": f"10.0.{random.randint(1, 255)}.{random.randint(1, 255)}",
            "{hostname}": random.choice(["db-primary", "cache-01", "api-server", "lb-west"]),
            "{port}": str(random.choice([5432, 6379, 3306, 8080, 443])),
            "{max}": str(random.randint(50, 200)),
            "{timeout}": str(random.randint(1000, 30000)),
            "{query}": "SELECT * FROM users WHERE...",
            "{tx_id}": str(uuid.uuid4())[:8],
            "{lag}": str(random.randint(1000, 10000)),
            "{size}": str(random.randint(512, 4096)),
            "{available}": str(random.randint(10, 100)),
            "{percent}": str(random.randint(85, 99)),
            "{pid}": str(random.randint(1000, 65535)),
            "{component}": random.choice(["RequestHandler", "CacheManager", "ConnectionPool"]),
            "{growth}": str(random.randint(10, 500)),
            "{service}": random.choice(cls.SERVICES),
            "{status}": str(random.choice([500, 502, 503, 504, 429])),
            "{rate}": str(random.randint(100, 10000)),
            "{mount}": random.choice(["/", "/var/log", "/data", "/tmp"]),
            "{user}": f"user_{random.randint(1, 1000)}",
            "{device}": random.choice(["sda1", "nvme0n1", "xvda"]),
            "{error}": random.choice(["read error", "write error", "sector error"]),
            "{fs}": random.choice(["ext4", "xfs", "btrfs"]),
            "{time}": str(random.randint(5, 500)),
            "{user_id}": str(random.randint(10000, 99999)),
            "{ip}": f"{random.randint(1, 255)}.{random.randint(1, 255)}.{random.randint(1, 255)}.{random.randint(1, 255)}",
            "{key}": f"cache:user:{random.randint(1, 1000)}",
            "{job}": random.choice(["cleanup", "backup", "sync", "report"]),
        }

        result = template
        for placeholder, value in replacements.items():
            result = result.replace(placeholder, value)
        return result

    @classmethod
    def generate_logs(
        cls,
        count: int = 50,
        error_rate: float = 0.2,
        service: Optional[str] = None
    ) -> List[LogEntry]:
        """Generate multiple log entries."""
        logs = []
        for _ in range(count):
            if random.random() < error_rate:
                level = random.choice([LogLevel.ERROR, LogLevel.CRITICAL])
            else:
                level = random.choices(
                    [LogLevel.DEBUG, LogLevel.INFO, LogLevel.WARNING],
                    weights=[5, 80, 15]
                )[0]
            logs.append(cls.generate_log_entry(level=level, service=service))

        # Sort by timestamp
        logs.sort(key=lambda x: x.timestamp)
        return logs

    @classmethod
    def generate_metrics_snapshot(
        cls,
        stress_level: float = 0.0  # 0.0 = normal, 1.0 = critical
    ) -> MetricsSnapshot:
        """Generate a metrics snapshot."""
        # Base values (normal operation)
        base_cpu = random.uniform(20, 40)
        base_memory = random.uniform(40, 60)
        base_latency = random.uniform(50, 150)
        base_error_rate = random.uniform(0.001, 0.01)
        base_throughput = random.uniform(1000, 5000)

        # Apply stress
        if stress_level > 0:
            base_cpu += stress_level * 50
            base_memory += stress_level * 35
            base_latency += stress_level * 2000
            base_error_rate += stress_level * 0.15
            base_throughput *= (1 - stress_level * 0.5)

        return MetricsSnapshot(
            timestamp=datetime.utcnow(),
            cpu_percent=min(99, base_cpu + random.uniform(-5, 5)),
            memory_percent=min(99, base_memory + random.uniform(-5, 5)),
            latency_ms=max(10, base_latency + random.uniform(-20, 20)),
            error_rate=max(0, min(1, base_error_rate + random.uniform(-0.005, 0.005))),
            throughput=max(100, base_throughput + random.uniform(-200, 200))
        )

    @classmethod
    def generate_metric_series(
        cls,
        count: int = 20,
        incident_at: Optional[int] = None,  # Index where incident starts
        recovery_at: Optional[int] = None   # Index where recovery starts
    ) -> List[MetricsSnapshot]:
        """Generate a time series of metrics."""
        snapshots = []
        stress = 0.0

        for i in range(count):
            # Simulate incident
            if incident_at and i >= incident_at:
                if recovery_at and i >= recovery_at:
                    # Recovery phase
                    stress = max(0, stress - 0.15)
                else:
                    # Incident ramp up
                    stress = min(1.0, stress + 0.2)

            snapshot = cls.generate_metrics_snapshot(stress_level=stress)
            snapshot.timestamp = datetime.utcnow() - timedelta(minutes=(count - i))
            snapshots.append(snapshot)

        return snapshots

    @classmethod
    def generate_database_incident(cls) -> Dict[str, Any]:
        """Generate a database connection failure incident."""
        return {
            "title": "Database Connection Pool Exhausted",
            "description": "Multiple services reporting database connection failures",
            "severity": IncidentSeverity.HIGH,
            "logs": cls.generate_logs(count=30, error_rate=0.6),
            "metrics": cls.generate_metric_series(count=15, incident_at=10)
        }

    @classmethod
    def generate_memory_leak_incident(cls) -> Dict[str, Any]:
        """Generate a memory leak incident."""
        logs = cls.generate_logs(count=40, error_rate=0.4)
        # Add specific OOM errors
        for _ in range(5):
            logs.append(cls.generate_log_entry(
                level=LogLevel.CRITICAL,
                error_type="memory"
            ))
        logs.sort(key=lambda x: x.timestamp)

        return {
            "title": "Memory Leak Detected - OOM Errors",
            "description": "Services experiencing out of memory errors with increasing frequency",
            "severity": IncidentSeverity.CRITICAL,
            "logs": logs,
            "metrics": cls.generate_metric_series(count=20, incident_at=8)
        }

    @classmethod
    def generate_latency_spike_incident(cls) -> Dict[str, Any]:
        """Generate a latency spike incident."""
        return {
            "title": "API Latency Spike",
            "description": "Response times exceeding SLA thresholds",
            "severity": IncidentSeverity.MEDIUM,
            "logs": cls.generate_logs(count=25, error_rate=0.3),
            "metrics": cls.generate_metric_series(count=15, incident_at=5, recovery_at=12)
        }

    @classmethod
    def generate_service_outage_incident(cls) -> Dict[str, Any]:
        """Generate a service outage incident."""
        service = random.choice(cls.SERVICES)
        logs = cls.generate_logs(count=50, error_rate=0.7, service=service)

        return {
            "title": f"Service Outage: {service}",
            "description": f"{service} is returning 5xx errors and failing health checks",
            "severity": IncidentSeverity.CRITICAL,
            "logs": logs,
            "metrics": cls.generate_metric_series(count=20, incident_at=5)
        }

    @classmethod
    def generate_disk_full_incident(cls) -> Dict[str, Any]:
        """Generate a disk full incident."""
        logs = cls.generate_logs(count=20, error_rate=0.5)
        # Add disk errors
        for _ in range(8):
            logs.append(cls.generate_log_entry(
                level=LogLevel.CRITICAL,
                error_type="disk"
            ))
        logs.sort(key=lambda x: x.timestamp)

        return {
            "title": "Disk Space Critical",
            "description": "Log partition approaching 100% usage",
            "severity": IncidentSeverity.HIGH,
            "logs": logs,
            "metrics": cls.generate_metric_series(count=15, incident_at=10)
        }

    @classmethod
    def generate_random_incident(cls) -> Dict[str, Any]:
        """Generate a random incident type."""
        generators = [
            cls.generate_database_incident,
            cls.generate_memory_leak_incident,
            cls.generate_latency_spike_incident,
            cls.generate_service_outage_incident,
            cls.generate_disk_full_incident
        ]
        return random.choice(generators)()


# Global instance
mock_generator = MockDataGenerator()
