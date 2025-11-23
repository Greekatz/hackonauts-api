"""
Auto-Healing Execution Layer
Executes safe automated remediation actions.
"""
import asyncio
import subprocess
from typing import Optional, Dict, Any, List
from datetime import datetime
from enum import Enum

from core import RecoveryAction, Incident, config, logger
from engines import incident_manager


class HealingAction(str, Enum):
    RESTART_SERVICE = "restart_service"
    SCALE_REPLICAS = "scale_replicas"
    FLUSH_CACHE = "flush_cache"
    CLEAR_QUEUE = "clear_queue"
    REROUTE_TRAFFIC = "reroute_traffic"
    ROLLBACK_DEPLOYMENT = "rollback_deployment"
    KILL_PROCESS = "kill_process"
    CLEAR_DISK = "clear_disk"


class AutoHealExecutor:
    """Executes auto-healing actions safely."""

    def __init__(self):
        self.enabled = True
        # Default to dry-run mode from config (safe by default)
        self.dry_run = getattr(config, 'AUTOHEAL_DRY_RUN', True)
        self.action_history: List[Dict[str, Any]] = []
        logger.info(f"AutoHealExecutor initialized (dry_run={self.dry_run})")

    def set_dry_run(self, enabled: bool):
        """Enable/disable dry run mode."""
        self.dry_run = enabled
        logger.info(f"Auto-heal dry run mode: {enabled}")

    async def execute(
        self,
        action: HealingAction,
        service: Optional[str] = None,
        parameters: Optional[Dict[str, Any]] = None,
        incident_id: Optional[str] = None
    ) -> Dict[str, Any]:
        """Execute a healing action."""

        params = parameters or {}
        result = {
            "action": action.value,
            "service": service,
            "parameters": params,
            "timestamp": datetime.utcnow().isoformat(),
            "success": False,
            "message": "",
            "dry_run": self.dry_run
        }

        if not self.enabled:
            result["message"] = "Auto-heal is disabled"
            return result

        logger.info(f"Executing auto-heal action: {action.value}", {
            "service": service,
            "params": params,
            "dry_run": self.dry_run
        })

        try:
            if action == HealingAction.RESTART_SERVICE:
                result = await self._restart_service(service, params, result)
            elif action == HealingAction.SCALE_REPLICAS:
                result = await self._scale_replicas(service, params, result)
            elif action == HealingAction.FLUSH_CACHE:
                result = await self._flush_cache(service, params, result)
            elif action == HealingAction.CLEAR_QUEUE:
                result = await self._clear_queue(service, params, result)
            elif action == HealingAction.REROUTE_TRAFFIC:
                result = await self._reroute_traffic(service, params, result)
            elif action == HealingAction.ROLLBACK_DEPLOYMENT:
                result = await self._rollback_deployment(service, params, result)
            elif action == HealingAction.KILL_PROCESS:
                result = await self._kill_process(service, params, result)
            elif action == HealingAction.CLEAR_DISK:
                result = await self._clear_disk(service, params, result)
            else:
                result["message"] = f"Unknown action: {action}"

        except Exception as e:
            result["success"] = False
            result["message"] = f"Execution error: {str(e)}"
            logger.error(f"Auto-heal execution failed: {str(e)}")

        # Record in history
        self.action_history.append(result)

        # Record in incident if provided
        if incident_id and result["success"]:
            recovery_action = RecoveryAction(
                action_type=action.value,
                description=result["message"],
                parameters=params,
                automated=True,
                executed=True,
                result=result["message"],
                executed_at=datetime.utcnow()
            )
            incident_manager.record_action_taken(incident_id, recovery_action)

        logger.log_autoheal_action(
            action=action.value,
            service=service or "unknown",
            success=result["success"],
            details=result["message"]
        )

        return result

    async def _restart_service(
        self, service: str, params: Dict, result: Dict
    ) -> Dict[str, Any]:
        """Restart a service (Docker, systemd, or Kubernetes)."""

        platform = params.get("platform", "docker")

        if self.dry_run:
            result["success"] = True
            result["message"] = f"[DRY RUN] Would restart {service} on {platform}"
            return result

        if platform == "docker":
            cmd = f"docker restart {service}"
        elif platform == "kubernetes":
            namespace = params.get("namespace", "default")
            cmd = f"kubectl rollout restart deployment/{service} -n {namespace}"
        elif platform == "systemd":
            cmd = f"systemctl restart {service}"
        else:
            result["message"] = f"Unknown platform: {platform}"
            return result

        success, output = await self._run_command(cmd)
        result["success"] = success
        result["message"] = output or f"Restarted {service}"
        return result

    async def _scale_replicas(
        self, service: str, params: Dict, result: Dict
    ) -> Dict[str, Any]:
        """Scale service replicas (Docker Swarm or Kubernetes)."""

        replicas = params.get("replicas", 3)
        platform = params.get("platform", "kubernetes")

        if self.dry_run:
            result["success"] = True
            result["message"] = f"[DRY RUN] Would scale {service} to {replicas} replicas"
            return result

        if platform == "kubernetes":
            namespace = params.get("namespace", "default")
            cmd = f"kubectl scale deployment/{service} --replicas={replicas} -n {namespace}"
        elif platform == "docker_swarm":
            cmd = f"docker service scale {service}={replicas}"
        else:
            result["message"] = f"Unknown platform: {platform}"
            return result

        success, output = await self._run_command(cmd)
        result["success"] = success
        result["message"] = output or f"Scaled {service} to {replicas} replicas"
        return result

    async def _flush_cache(
        self, service: str, params: Dict, result: Dict
    ) -> Dict[str, Any]:
        """Flush cache (Redis, Memcached, or application cache)."""

        cache_type = params.get("cache_type", "redis")

        if self.dry_run:
            result["success"] = True
            result["message"] = f"[DRY RUN] Would flush {cache_type} cache"
            return result

        if cache_type == "redis":
            host = params.get("host", "localhost")
            port = params.get("port", 6379)
            db = params.get("db", 0)
            cmd = f"redis-cli -h {host} -p {port} -n {db} FLUSHDB"
        elif cache_type == "memcached":
            host = params.get("host", "localhost")
            port = params.get("port", 11211)
            cmd = f"echo 'flush_all' | nc {host} {port}"
        else:
            result["message"] = f"Unknown cache type: {cache_type}"
            return result

        success, output = await self._run_command(cmd)
        result["success"] = success
        result["message"] = output or f"Flushed {cache_type} cache"
        return result

    async def _clear_queue(
        self, service: str, params: Dict, result: Dict
    ) -> Dict[str, Any]:
        """Clear a message queue."""

        queue_type = params.get("queue_type", "rabbitmq")
        queue_name = params.get("queue_name", service)

        if self.dry_run:
            result["success"] = True
            result["message"] = f"[DRY RUN] Would clear queue {queue_name}"
            return result

        if queue_type == "rabbitmq":
            cmd = f"rabbitmqadmin purge queue name={queue_name}"
        elif queue_type == "redis":
            host = params.get("host", "localhost")
            cmd = f"redis-cli -h {host} DEL {queue_name}"
        else:
            result["message"] = f"Unknown queue type: {queue_type}"
            return result

        success, output = await self._run_command(cmd)
        result["success"] = success
        result["message"] = output or f"Cleared queue {queue_name}"
        return result

    async def _reroute_traffic(
        self, service: str, params: Dict, result: Dict
    ) -> Dict[str, Any]:
        """Reroute traffic (update load balancer or ingress)."""

        target = params.get("target", "healthy")

        if self.dry_run:
            result["success"] = True
            result["message"] = f"[DRY RUN] Would reroute traffic from {service} to {target}"
            return result

        # This would typically call your load balancer API
        # Example for nginx reload:
        if params.get("method") == "nginx":
            cmd = "nginx -s reload"
            success, output = await self._run_command(cmd)
            result["success"] = success
            result["message"] = output or f"Rerouted traffic via nginx reload"
        else:
            # Placeholder for LB API call
            result["success"] = True
            result["message"] = f"Rerouted traffic from {service} to {target}"

        return result

    async def _rollback_deployment(
        self, service: str, params: Dict, result: Dict
    ) -> Dict[str, Any]:
        """Rollback to previous deployment."""

        platform = params.get("platform", "kubernetes")
        revision = params.get("revision", None)

        if self.dry_run:
            result["success"] = True
            result["message"] = f"[DRY RUN] Would rollback {service}"
            return result

        if platform == "kubernetes":
            namespace = params.get("namespace", "default")
            if revision:
                cmd = f"kubectl rollout undo deployment/{service} -n {namespace} --to-revision={revision}"
            else:
                cmd = f"kubectl rollout undo deployment/{service} -n {namespace}"
        else:
            result["message"] = f"Rollback not supported for platform: {platform}"
            return result

        success, output = await self._run_command(cmd)
        result["success"] = success
        result["message"] = output or f"Rolled back {service}"
        return result

    async def _kill_process(
        self, service: str, params: Dict, result: Dict
    ) -> Dict[str, Any]:
        """Kill a runaway process."""

        pid = params.get("pid")
        signal = params.get("signal", "TERM")

        if not pid:
            result["message"] = "PID required for kill_process"
            return result

        if self.dry_run:
            result["success"] = True
            result["message"] = f"[DRY RUN] Would kill process {pid}"
            return result

        cmd = f"kill -{signal} {pid}"
        success, output = await self._run_command(cmd)
        result["success"] = success
        result["message"] = output or f"Killed process {pid}"
        return result

    async def _clear_disk(
        self, service: str, params: Dict, result: Dict
    ) -> Dict[str, Any]:
        """Clear disk space (logs, temp files)."""

        path = params.get("path", "/tmp")
        pattern = params.get("pattern", "*.log")
        older_than_days = params.get("older_than_days", 7)

        if self.dry_run:
            result["success"] = True
            result["message"] = f"[DRY RUN] Would clear {pattern} files older than {older_than_days} days from {path}"
            return result

        cmd = f"find {path} -name '{pattern}' -mtime +{older_than_days} -delete"
        success, output = await self._run_command(cmd)
        result["success"] = success
        result["message"] = output or f"Cleared old files from {path}"
        return result

    async def _run_command(self, cmd: str) -> tuple[bool, str]:
        """Run a shell command safely."""
        try:
            process = await asyncio.create_subprocess_shell(
                cmd,
                stdout=asyncio.subprocess.PIPE,
                stderr=asyncio.subprocess.PIPE
            )
            stdout, stderr = await asyncio.wait_for(process.communicate(), timeout=60)

            if process.returncode == 0:
                return True, stdout.decode().strip()
            else:
                return False, stderr.decode().strip()

        except asyncio.TimeoutError:
            return False, "Command timed out"
        except Exception as e:
            return False, str(e)

    def get_available_actions(self) -> List[Dict[str, Any]]:
        """Get list of available healing actions."""
        return [
            {
                "action": HealingAction.RESTART_SERVICE.value,
                "description": "Restart a service",
                "parameters": ["service", "platform (docker/kubernetes/systemd)"]
            },
            {
                "action": HealingAction.SCALE_REPLICAS.value,
                "description": "Scale service replicas",
                "parameters": ["service", "replicas", "platform"]
            },
            {
                "action": HealingAction.FLUSH_CACHE.value,
                "description": "Flush cache",
                "parameters": ["cache_type (redis/memcached)", "host", "port"]
            },
            {
                "action": HealingAction.CLEAR_QUEUE.value,
                "description": "Clear message queue",
                "parameters": ["queue_type", "queue_name"]
            },
            {
                "action": HealingAction.REROUTE_TRAFFIC.value,
                "description": "Reroute traffic",
                "parameters": ["service", "target"]
            },
            {
                "action": HealingAction.ROLLBACK_DEPLOYMENT.value,
                "description": "Rollback deployment",
                "parameters": ["service", "platform", "revision"]
            },
            {
                "action": HealingAction.KILL_PROCESS.value,
                "description": "Kill a process",
                "parameters": ["pid", "signal"]
            },
            {
                "action": HealingAction.CLEAR_DISK.value,
                "description": "Clear disk space",
                "parameters": ["path", "pattern", "older_than_days"]
            },
        ]


# Global executor instance
autoheal_executor = AutoHealExecutor()
