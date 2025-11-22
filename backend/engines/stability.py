"""
Stability Evaluation Engine
Works with the LLM to determine if the system is "healthy enough."
"""
from typing import List, Optional, Dict, Any
from datetime import datetime, timedelta
import statistics

from core import (
    LogEntry, MetricsSnapshot, StabilityReport, LogLevel,
    config, logger
)


class StabilityEvaluator:
    """Evaluates system stability based on metrics and logs."""

    def __init__(self):
        self.thresholds = config.THRESHOLDS
        self.baseline_metrics: Optional[MetricsSnapshot] = None
        self.stability_history: List[StabilityReport] = []

    def set_baseline(self, metrics: MetricsSnapshot):
        """Set a baseline for comparison during stability checks."""
        self.baseline_metrics = metrics
        logger.info("Stability baseline set", {
            "cpu": metrics.cpu_percent,
            "memory": metrics.memory_percent,
            "latency": metrics.latency_ms,
            "error_rate": metrics.error_rate
        })

    def evaluate_metrics(self, current: MetricsSnapshot) -> tuple[bool, List[str]]:
        """Check if current metrics meet success thresholds."""
        issues = []

        # Check absolute thresholds
        if current.cpu_percent and current.cpu_percent > self.thresholds.cpu_threshold:
            issues.append(f"CPU {current.cpu_percent}% exceeds threshold {self.thresholds.cpu_threshold}%")

        if current.memory_percent and current.memory_percent > self.thresholds.memory_threshold:
            issues.append(f"Memory {current.memory_percent}% exceeds threshold {self.thresholds.memory_threshold}%")

        if current.latency_ms and current.latency_ms > self.thresholds.latency_threshold_ms:
            issues.append(f"Latency {current.latency_ms}ms exceeds threshold {self.thresholds.latency_threshold_ms}ms")

        if current.error_rate and current.error_rate > self.thresholds.error_rate_threshold:
            issues.append(f"Error rate {current.error_rate * 100}% exceeds threshold {self.thresholds.error_rate_threshold * 100}%")

        # Compare to baseline if available
        if self.baseline_metrics:
            if current.latency_ms and self.baseline_metrics.latency_ms:
                if current.latency_ms > self.baseline_metrics.latency_ms * 2:
                    issues.append(f"Latency 2x higher than baseline")

            if current.error_rate and self.baseline_metrics.error_rate:
                if current.error_rate > self.baseline_metrics.error_rate * 3:
                    issues.append(f"Error rate 3x higher than baseline")

        return len(issues) == 0, issues

    def evaluate_logs(self, logs: List[LogEntry], window_minutes: int = 5) -> tuple[bool, List[str]]:
        """Check if recent logs indicate stability."""
        issues = []
        cutoff = datetime.utcnow() - timedelta(minutes=window_minutes)
        recent_logs = [log for log in logs if log.timestamp >= cutoff]

        if not recent_logs:
            return True, []

        # Count by level
        error_count = sum(1 for log in recent_logs if log.level == LogLevel.ERROR)
        critical_count = sum(1 for log in recent_logs if log.level == LogLevel.CRITICAL)

        if critical_count > 0:
            issues.append(f"{critical_count} critical errors in last {window_minutes} minutes")

        if error_count > 10:
            issues.append(f"{error_count} errors in last {window_minutes} minutes")

        # Check for recurring errors (same message pattern)
        error_messages = [log.message[:50] for log in recent_logs if log.level in [LogLevel.ERROR, LogLevel.CRITICAL]]
        if error_messages:
            from collections import Counter
            common = Counter(error_messages).most_common(1)
            if common and common[0][1] > 5:
                issues.append(f"Recurring error pattern: '{common[0][0]}...' ({common[0][1]} times)")

        return len(issues) == 0, issues

    def evaluate(
        self,
        metrics: Optional[MetricsSnapshot] = None,
        logs: Optional[List[LogEntry]] = None,
        llm_judgment: Optional[str] = None
    ) -> StabilityReport:
        """Full stability evaluation."""

        metrics_ok = True
        logs_ok = True
        details_parts = []
        error_rate = None

        if metrics:
            metrics_ok, metrics_issues = self.evaluate_metrics(metrics)
            if metrics_issues:
                details_parts.extend(metrics_issues)
            error_rate = metrics.error_rate

        if logs:
            logs_ok, log_issues = self.evaluate_logs(logs)
            if log_issues:
                details_parts.extend(log_issues)

        # Determine overall stability
        is_stable = metrics_ok and logs_ok

        # If LLM judgment is provided, factor it in
        if llm_judgment:
            llm_says_ok = "ok" in llm_judgment.lower() or "stable" in llm_judgment.lower() or "healthy" in llm_judgment.lower()
            # LLM can override to unstable, but not to stable
            if not llm_says_ok:
                is_stable = False
                details_parts.append(f"LLM assessment: {llm_judgment}")

        report = StabilityReport(
            timestamp=datetime.utcnow(),
            is_stable=is_stable,
            metrics_ok=metrics_ok,
            logs_ok=logs_ok,
            error_rate=error_rate,
            details="; ".join(details_parts) if details_parts else "System stable",
            llm_judgment=llm_judgment
        )

        self.stability_history.append(report)

        logger.info(f"Stability evaluation: {'STABLE' if is_stable else 'UNSTABLE'}", {
            "is_stable": is_stable,
            "metrics_ok": metrics_ok,
            "logs_ok": logs_ok,
            "details": report.details
        })

        return report

    def get_stability_trend(self, count: int = 5) -> Dict[str, Any]:
        """Get trend from recent stability reports."""
        recent = self.stability_history[-count:] if self.stability_history else []

        if not recent:
            return {"trend": "unknown", "stable_count": 0, "total": 0}

        stable_count = sum(1 for r in recent if r.is_stable)

        if stable_count == len(recent):
            trend = "stable"
        elif stable_count == 0:
            trend = "critical"
        elif stable_count > len(recent) / 2:
            trend = "improving"
        else:
            trend = "degrading"

        return {
            "trend": trend,
            "stable_count": stable_count,
            "total": len(recent),
            "latest_stable": recent[-1].is_stable if recent else None
        }

    def should_rerun_agent(self) -> bool:
        """Decide whether to re-run the agent based on stability."""
        trend = self.get_stability_trend()

        # Always re-run if critical
        if trend["trend"] == "critical":
            return True

        # Re-run if degrading and not recently stable
        if trend["trend"] == "degrading":
            return True

        # Don't re-run if stable
        if trend["trend"] == "stable" and trend["stable_count"] >= 3:
            return False

        # Re-run if improving but not yet stable
        if trend["trend"] == "improving" and trend["stable_count"] < 3:
            return True

        return False


# Global evaluator instance
stability_evaluator = StabilityEvaluator()
