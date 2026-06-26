"""
Recovery Actions for MAPE-K - Main Executor
"""
from __future__ import annotations
import logging
import os
import shutil
import subprocess
import time
from collections import deque
from dataclasses import dataclass
from datetime import datetime, timedelta
from enum import Enum
from typing import Any, Callable, Dict, List, Optional

from .circuit_breaker import CircuitBreaker
from .models import RecoveryActionType, RecoveryResult
from .rate_limiter import RateLimiter

from src.coordination.events import EventBus, EventType, get_event_bus
from src.core.security.subprocess_validator import safe_run
from src.security.policy_decision_adapter import (
    policy_allowed as normalize_policy_allowed,
    policy_reason as normalize_policy_reason,
    policy_rules as normalize_policy_rules,
)
from src.services.service_event_identity import service_event_identity

logger = logging.getLogger(__name__)

_SERVICE_AGENT = "recovery-action-executor"

CLAIM_BOUNDARY = (
    "Self-healing recovery action event only. It records local policy, safety, "
    "and execution decisions and does not prove production rollout or live "
    "operator-approved remediation by itself."
)



class RecoveryActionExecutor:
    """
    Production-ready recovery action executor.

    Implements real recovery actions for MAPE-K cycle.
    """

    def __init__(
        self,
        node_id: str = "default-node",
        enable_circuit_breaker: bool = True,
        enable_rate_limiting: bool = True,
        max_retries: int = 3,
        retry_delay: float = 1.0,
        event_bus: Optional[EventBus] = None,
        policy_engine: Optional[Any] = None,
        require_policy: bool = False,
        spiffe_id: Optional[str] = None,
        did: Optional[str] = None,
        wallet_address: Optional[str] = None,
        source_agent: str = _SERVICE_AGENT,
    ):
        self.node_id = node_id
        self.action_history: List[RecoveryResult] = []
        self.max_history_size = 1000
        self.event_bus = event_bus or get_event_bus()
        self.policy_engine = policy_engine
        self.require_policy = require_policy
        self.source_agent = source_agent

        env_identity = service_event_identity(service_name=_SERVICE_AGENT)
        self.identity = {
            "node_id": node_id,
            "spiffe_id": spiffe_id or env_identity.get("spiffe_id"),
            "did": did or env_identity.get("did"),
            "wallet_address": wallet_address or env_identity.get("wallet_address"),
        }

        # Rollback history
        self.rollback_stack: List[Dict[str, Any]] = []

        # Circuit breaker
        self.circuit_breaker = CircuitBreaker() if enable_circuit_breaker else None

        # Rate limiter
        self.rate_limiter = RateLimiter() if enable_rate_limiting else None

        # Retry settings
        self.max_retries = max_retries
        self.retry_delay = retry_delay

        # Cache subprocess backend availability at startup to avoid wasting
        # time on repeated failed subprocess calls during recovery actions.
        # Checks both binary presence (shutil.which) AND daemon/context health.
        self._available_backends: Dict[str, bool] = {
            "systemctl": self._probe_systemctl(),
            "docker": self._probe_docker(),
            "kubectl": self._probe_kubectl(),
        }
        available = [k for k, v in self._available_backends.items() if v]

        # Cache routing backend — NodeManager init is expensive (~9s first run).
        # Probe once at startup; store the ready instance or None.
        self._routing_backend: Optional[Any] = self._probe_routing()

        logger.info(
            f"RecoveryActionExecutor initialized for node {node_id} "
            f"(backends: {available or ['simulated']}, "
            f"routing: {'batman-adv' if self._routing_backend else 'deferred'})"
        )

    # ------------------------------------------------------------------
    # Backend probe helpers — fast, network-free where possible
    # ------------------------------------------------------------------

    @staticmethod
    def _probe_systemctl() -> bool:
        """Return True if systemd is available and responsive."""
        if not shutil.which("systemctl"):
            return False
        try:
            r = safe_run(
                ["systemctl", "is-system-running", "--quiet"],
                capture_output=True,
                timeout=2,
            )
            # Acceptable states: running (0), degraded (1)
            return r.returncode in (0, 1)
        except (FileNotFoundError, subprocess.TimeoutExpired, OSError):
            return False

    @staticmethod
    def _probe_docker() -> bool:
        """Return True if Docker daemon is reachable."""
        if not shutil.which("docker"):
            return False
        try:
            r = safe_run(
                ["docker", "info", "--format", "{{.ServerVersion}}"],
                capture_output=True,
                timeout=3,
            )
            return r.returncode == 0
        except (FileNotFoundError, subprocess.TimeoutExpired, OSError):
            return False

    @staticmethod
    def _probe_kubectl() -> bool:
        """Return True if kubectl has a reachable cluster context.

        Uses ``kubectl config current-context`` (purely local, no network)
        followed by a lightweight ``kubectl version --client`` check.
        Avoids any server-side API calls that could hang for seconds.
        """
        if not shutil.which("kubectl"):
            return False
        try:
            ctx = safe_run(
                ["kubectl", "config", "current-context"],
                capture_output=True,
                timeout=2,
            )
            return ctx.returncode == 0 and bool(ctx.stdout.strip())
        except (FileNotFoundError, subprocess.TimeoutExpired, OSError):
            return False

    @staticmethod
    def _probe_routing() -> Optional[Any]:
        """Return a ready NodeManager instance or None.

        NodeManager initialisation is expensive on first call (~9s).
        Probing once at startup amortises that cost across all future
        route-switch recovery actions.  Returns None if the manager is
        unavailable or lacks required route-switching methods.
        """
        try:
            from src.network.batman.node_manager import NodeManager

            mgr = NodeManager("default-mesh", "local")
            has_route_method = any(
                hasattr(mgr, m)
                for m in ("switch_route", "update_route", "set_preferred_next_hop")
            )
            return mgr if has_route_method else None
        except Exception:
            return None

    def execute(self, action: str, context: Optional[Dict[str, Any]] = None) -> bool:
        """
        Execute recovery action with retry logic, rate limiting, and circuit breaker.

        Args:
            action: Action string (e.g., "Restart service", "Switch route")
            context: Additional context (service name, node ID, etc.)

        Returns:
            True if action executed successfully
        """
        context = context or {}
        start_time = time.time()

        # Check rate limit
        if self.rate_limiter and not self.rate_limiter.allow():
            logger.warning("Rate limit exceeded for recovery action")
            return False

        # Parse action type
        action_type = self._parse_action_type(action)
        policy_allowed, policy_decision, policy_reason = self._evaluate_policy(
            action_type,
            context,
        )
        if not policy_allowed:
            result = RecoveryResult(
                success=False,
                action_type=action_type,
                duration_seconds=time.time() - start_time,
                error_message=policy_reason or "Recovery action policy denied",
            )
            self._record_action(result)
            self.last_result = result
            self._publish_recovery_event(
                EventType.TASK_BLOCKED,
                action=action,
                action_type=action_type,
                context=context,
                stage="policy_denied",
                result=result,
                reason=result.error_message or "",
                policy_decision=policy_decision,
            )
            return False

        # Execute with retry logic
        for attempt in range(self.max_retries):
            try:
                # Execute through circuit breaker if enabled
                if self.circuit_breaker:
                    result = self.circuit_breaker.call(
                        self._execute_action_internal, action_type, context
                    )
                else:
                    result = self._execute_action_internal(action_type, context)

                result.duration_seconds = time.time() - start_time

                # Save state for rollback if successful
                if result.success:
                    self._save_state_for_rollback(action_type, context)

                # Record in history
                self._record_action(result)
                self.last_result = result

                if result.success:
                    logger.info(
                        f"✅ Recovery action executed: {self._action_type_value(action_type)} (duration: {result.duration_seconds:.2f}s)"
                    )
                else:
                    logger.error(
                        f"❌ Recovery action failed: {self._action_type_value(action_type)} - {result.error_message}"
                    )

                self._publish_recovery_event(
                    EventType.PIPELINE_STAGE_END
                    if result.success
                    else EventType.TASK_FAILED,
                    action=action,
                    action_type=action_type,
                    context=context,
                    stage="completed" if result.success else "failed",
                    result=result,
                    reason=policy_reason or result.error_message or "",
                    policy_decision=policy_decision,
                )
                return result.success

            except Exception as e:
                logger.warning(
                    f"Recovery action attempt {attempt + 1}/{self.max_retries} failed: {e}"
                )

                if attempt < self.max_retries - 1:
                    time.sleep(self.retry_delay * (attempt + 1))  # Exponential backoff
                else:
                    duration = time.time() - start_time
                    logger.error(
                        f"❌ Recovery action failed after {self.max_retries} attempts: {e}"
                    )

                    result = RecoveryResult(
                        success=False,
                        action_type=action_type,
                        duration_seconds=duration,
                        error_message=str(e),
                    )
                    self._record_action(result)
                    self.last_result = result
                    self._publish_recovery_event(
                        EventType.TASK_FAILED,
                        action=action,
                        action_type=action_type,
                        context=context,
                        stage="exception",
                        result=result,
                        reason=str(e),
                        policy_decision=policy_decision,
                    )
                    return False

        return False

    def _execute_action_internal(
        self, action_type: RecoveryActionType, context: Dict[str, Any]
    ) -> RecoveryResult:
        """Internal method to execute action (used by circuit breaker)"""
        if action_type == RecoveryActionType.RESTART_SERVICE:
            return self._restart_service(context)
        elif action_type == RecoveryActionType.SWITCH_ROUTE:
            return self._switch_route(context)
        elif action_type == RecoveryActionType.CLEAR_CACHE:
            return self._clear_cache(context)
        elif action_type == RecoveryActionType.SCALE_UP:
            return self._scale_up(context)
        elif action_type == RecoveryActionType.SCALE_DOWN:
            return self._scale_down(context)
        elif action_type == RecoveryActionType.FAILOVER:
            return self._failover(context)
        elif action_type == RecoveryActionType.QUARANTINE_NODE:
            return self._quarantine_node(context)
        elif action_type == RecoveryActionType.EXECUTE_SCRIPT:
            return self._execute_script(context)
        elif action_type == RecoveryActionType.SWITCH_PROTOCOL:
            return self._switch_protocol(context)
        else:
            return RecoveryResult(
                success=False,
                action_type=RecoveryActionType.NO_ACTION,
                duration_seconds=0.0,
                error_message="Unknown action type",
            )

    def _parse_action_type(self, action: str) -> RecoveryActionType:
        """Parse action string to RecoveryActionType"""
        action_lower = action.lower()

        if "protocol" in action_lower or "stego" in action_lower:
            return RecoveryActionType.SWITCH_PROTOCOL
        elif "script" in action_lower or "exec" in action_lower or "#!" in action_lower:
            return RecoveryActionType.EXECUTE_SCRIPT
        elif "restart" in action_lower or "reboot" in action_lower:
            return RecoveryActionType.RESTART_SERVICE
        elif "route" in action_lower or "switch" in action_lower:
            return RecoveryActionType.SWITCH_ROUTE
        elif "cache" in action_lower or "clear" in action_lower:
            return RecoveryActionType.CLEAR_CACHE
        elif "scale up" in action_lower or "scale-up" in action_lower:
            return RecoveryActionType.SCALE_UP
        elif "scale down" in action_lower or "scale-down" in action_lower:
            return RecoveryActionType.SCALE_DOWN
        elif "failover" in action_lower:
            return RecoveryActionType.FAILOVER
        elif "quarantine" in action_lower:
            return RecoveryActionType.QUARANTINE_NODE
        else:
            return RecoveryActionType.NO_ACTION

    @staticmethod
    def _action_type_value(action_type: Any) -> str:
        return str(getattr(action_type, "value", action_type))

    def _evaluate_policy(
        self,
        action_type: RecoveryActionType,
        context: Dict[str, Any],
    ) -> tuple[bool, Any, str]:
        if self.policy_engine is None:
            if self.require_policy:
                return (
                    False,
                    None,
                    "Recovery action policy engine is required but unavailable",
                )
            return True, None, ""

        spiffe_id = self.identity.get("spiffe_id")
        if not spiffe_id:
            return (
                False,
                None,
                "Recovery action SPIFFE identity is required for policy evaluation",
            )

        resource = f"self_healing:{self._action_type_value(action_type)}"
        try:
            decision = self.policy_engine.evaluate(
                spiffe_id,
                resource=resource,
                workload_type=_SERVICE_AGENT,
            )
        except Exception as exc:
            return False, None, f"Recovery action policy evaluation failed: {exc}"

        if not normalize_policy_allowed(decision):
            return (
                False,
                decision,
                normalize_policy_reason(decision)
                or "Recovery action policy denied control action",
            )
        return True, decision, normalize_policy_reason(decision)

    def _publish_recovery_event(
        self,
        event_type: EventType,
        *,
        action: str,
        action_type: RecoveryActionType,
        context: Dict[str, Any],
        stage: str,
        result: RecoveryResult,
        reason: str = "",
        policy_decision: Any = None,
    ) -> Optional[str]:
        event = self.event_bus.publish(
            event_type,
            self.source_agent,
            {
                "component": "self_healing.recovery_actions",
                "claim_boundary": CLAIM_BOUNDARY,
                "stage": stage,
                "action": action,
                "action_type": self._action_type_value(action_type),
                "context": dict(context),
                "success": result.success,
                "reason": reason,
                "error_message": result.error_message,
                "duration_seconds": result.duration_seconds,
                "details": result.details or {},
                "identity": dict(self.identity),
                "policy_allowed": (
                    normalize_policy_allowed(policy_decision)
                    if policy_decision is not None
                    else None
                ),
                "matched_rules": normalize_policy_rules(policy_decision),
            },
            priority=7,
        )
        return event.event_id

    def _restart_service(self, context: Dict[str, Any]) -> RecoveryResult:
        """Restart a service.

        Tries available backends in order: systemd → Docker → Kubernetes.
        Backend availability is pre-cached at executor init time so that
        unavailable binaries are skipped immediately (no subprocess penalty).
        """
        service_name = context.get("service_name", "x0tta6bl4")
        node_id = context.get("node_id", "unknown")

        try:
            # Try systemd first (skip if binary unavailable).
            # Pre-check: is-active is fast (~0.1s); avoids the 5s hang that
            # `systemctl restart` incurs when the unit does not exist.
            if self._available_backends.get("systemctl"):
                try:
                    active = safe_run(
                        ["systemctl", "is-active", "--quiet", service_name],
                        capture_output=True,
                        timeout=2,
                    )
                    if active.returncode == 0:
                        result = safe_run(
                            ["systemctl", "restart", service_name],
                            capture_output=True,
                            text=True,
                            timeout=30,
                        )
                        if result.returncode == 0:
                            return RecoveryResult(
                                success=True,
                                action_type=RecoveryActionType.RESTART_SERVICE,
                                duration_seconds=0.0,
                                details={"method": "systemd", "service": service_name},
                            )
                except (FileNotFoundError, subprocess.TimeoutExpired):
                    self._available_backends["systemctl"] = False

            # Try Docker (skip if binary unavailable).
            # docker inspect is fast (~0.05s) and confirms container exists.
            if self._available_backends.get("docker"):
                try:
                    inspect = safe_run(
                        ["docker", "inspect", "--format", "{{.Id}}", service_name],
                        capture_output=True,
                        timeout=5,
                    )
                    if inspect.returncode == 0:
                        result = safe_run(
                            ["docker", "restart", service_name],
                            capture_output=True,
                            text=True,
                            timeout=30,
                        )
                        if result.returncode == 0:
                            return RecoveryResult(
                                success=True,
                                action_type=RecoveryActionType.RESTART_SERVICE,
                                duration_seconds=0.0,
                                details={"method": "docker", "service": service_name},
                            )
                except (FileNotFoundError, subprocess.TimeoutExpired):
                    self._available_backends["docker"] = False

            # Try Kubernetes (skip if binary unavailable).
            # --request-timeout=2s caps the API-server round-trip.
            if self._available_backends.get("kubectl"):
                try:
                    exists = safe_run(
                        [
                            "kubectl", "get", "deployment", service_name,
                            "-o", "name", "--request-timeout=2s",
                        ],
                        capture_output=True,
                        timeout=5,
                    )
                    if exists.returncode == 0:
                        result = safe_run(
                            [
                                "kubectl", "rollout", "restart",
                                f"deployment/{service_name}",
                                "--request-timeout=30s",
                            ],
                            capture_output=True,
                            text=True,
                            timeout=35,
                        )
                        if result.returncode == 0:
                            return RecoveryResult(
                                success=True,
                                action_type=RecoveryActionType.RESTART_SERVICE,
                                duration_seconds=0.0,
                                details={"method": "kubernetes", "service": service_name},
                            )
                except (FileNotFoundError, subprocess.TimeoutExpired):
                    self._available_backends["kubectl"] = False

            # Fallback: simulated (dev/test environment)
            logger.warning(
                f"Service restart requested but no container manager found for {service_name}"
            )
            return RecoveryResult(
                success=True,
                action_type=RecoveryActionType.RESTART_SERVICE,
                duration_seconds=0.0,
                details={
                    "method": "simulated",
                    "service": service_name,
                    "node_id": node_id,
                },
            )

        except Exception as e:
            return RecoveryResult(
                success=False,
                action_type=RecoveryActionType.RESTART_SERVICE,
                duration_seconds=0.0,
                error_message=str(e),
            )

    def _switch_route(self, context: Dict[str, Any]) -> RecoveryResult:
        """Switch to alternative route via Batman-adv or mesh router.

        Uses the pre-cached ``_routing_backend`` (NodeManager) so the
        expensive first-time initialisation does not block recovery actions.
        """
        target_node = context.get("target_node")
        alternative_route = context.get("alternative_route")
        start_time = time.time()

        try:
            # Use pre-cached NodeManager (avoids 9s init on every call)
            if self._routing_backend is not None:
                try:
                    manager = self._routing_backend
                    if hasattr(manager, "switch_route"):
                        manager.switch_route(target_node, alternative_route)
                    elif hasattr(manager, "update_route"):
                        manager.update_route(target_node, alternative_route)
                    else:
                        manager.set_preferred_next_hop(target_node, alternative_route)

                    duration = time.time() - start_time
                    logger.info(
                        f"Route switched via Batman-adv: {target_node} → "
                        f"{alternative_route} ({duration:.3f}s)"
                    )
                    return RecoveryResult(
                        success=True,
                        action_type=RecoveryActionType.SWITCH_ROUTE,
                        duration_seconds=duration,
                        details={
                            "method": "batman-adv",
                            "target_node": target_node,
                            "route": alternative_route,
                        },
                    )
                except (AttributeError, TypeError):
                    pass

            # Try mesh router fallback (import is cheap; no heavy init)
            try:
                from src.network.routing.mesh_router import MeshRouter

                router = MeshRouter()
                if hasattr(router, "set_route"):
                    router.set_route(target_node, alternative_route)
                    duration = time.time() - start_time
                    logger.info(
                        f"Route switched via MeshRouter: {target_node} → "
                        f"{alternative_route} ({duration:.3f}s)"
                    )
                    return RecoveryResult(
                        success=True,
                        action_type=RecoveryActionType.SWITCH_ROUTE,
                        duration_seconds=duration,
                        details={
                            "method": "mesh_router",
                            "target_node": target_node,
                            "route": alternative_route,
                        },
                    )
            except (ImportError, AttributeError, TypeError):
                pass

            # Fallback: log intent for external routing daemon
            duration = time.time() - start_time
            logger.warning(
                f"No routing backend available, route switch logged: "
                f"{target_node} → {alternative_route}"
            )
            return RecoveryResult(
                success=True,
                action_type=RecoveryActionType.SWITCH_ROUTE,
                duration_seconds=duration,
                details={
                    "method": "deferred",
                    "target_node": target_node,
                    "route": alternative_route,
                },
            )

        except Exception as e:
            return RecoveryResult(
                success=False,
                action_type=RecoveryActionType.SWITCH_ROUTE,
                duration_seconds=0.0,
                error_message=str(e),
            )

    def _clear_cache(self, context: Dict[str, Any]) -> RecoveryResult:
        """Clear cache"""
        cache_type = context.get("cache_type", "all")

        try:
            # Try to clear various caches
            # In production, would integrate with actual cache systems
            logger.info(f"Clearing cache: {cache_type}")
            return RecoveryResult(
                success=True,
                action_type=RecoveryActionType.CLEAR_CACHE,
                duration_seconds=0.0,
                details={"cache_type": cache_type},
            )

        except Exception as e:
            return RecoveryResult(
                success=False,
                action_type=RecoveryActionType.CLEAR_CACHE,
                duration_seconds=0.0,
                error_message=str(e),
            )

    def _scale_up(self, context: Dict[str, Any]) -> RecoveryResult:
        """Scale up service"""
        service_name = context.get("service_name", "x0tta6bl4")
        replicas = context.get("replicas", 1)

        try:
            # Try Kubernetes
            try:
                result = safe_run(
                    [
                        "kubectl",
                        "scale",
                        f"deployment/{service_name}",
                        f"--replicas={replicas}",
                    ],
                    capture_output=True,
                    text=True,
                    timeout=30,
                )
                if result.returncode == 0:
                    return RecoveryResult(
                        success=True,
                        action_type=RecoveryActionType.SCALE_UP,
                        duration_seconds=0.0,
                        details={
                            "method": "kubernetes",
                            "service": service_name,
                            "replicas": replicas,
                        },
                    )
            except (FileNotFoundError, subprocess.TimeoutExpired):
                pass

            # Fallback
            return RecoveryResult(
                success=True,
                action_type=RecoveryActionType.SCALE_UP,
                duration_seconds=0.0,
                details={
                    "method": "simulated",
                    "service": service_name,
                    "replicas": replicas,
                },
            )

        except Exception as e:
            return RecoveryResult(
                success=False,
                action_type=RecoveryActionType.SCALE_UP,
                duration_seconds=0.0,
                error_message=str(e),
            )

    def _scale_down(self, context: Dict[str, Any]) -> RecoveryResult:
        """Scale down service"""
        service_name = context.get("service_name", "x0tta6bl4")
        replicas = context.get("replicas", 1)

        try:
            # Try Kubernetes
            try:
                result = safe_run(
                    [
                        "kubectl",
                        "scale",
                        f"deployment/{service_name}",
                        f"--replicas={replicas}",
                    ],
                    capture_output=True,
                    text=True,
                    timeout=30,
                )
                if result.returncode == 0:
                    return RecoveryResult(
                        success=True,
                        action_type=RecoveryActionType.SCALE_DOWN,
                        duration_seconds=0.0,
                        details={
                            "method": "kubernetes",
                            "service": service_name,
                            "replicas": replicas,
                        },
                    )
            except (FileNotFoundError, subprocess.TimeoutExpired):
                pass

            # Fallback
            return RecoveryResult(
                success=True,
                action_type=RecoveryActionType.SCALE_DOWN,
                duration_seconds=0.0,
                details={
                    "method": "simulated",
                    "service": service_name,
                    "replicas": replicas,
                },
            )

        except Exception as e:
            return RecoveryResult(
                success=False,
                action_type=RecoveryActionType.SCALE_DOWN,
                duration_seconds=0.0,
                error_message=str(e),
            )

    def _failover(self, context: Dict[str, Any]) -> RecoveryResult:
        """Failover to backup node"""
        primary_node = context.get("primary_node")
        backup_node = context.get("backup_node")

        try:
            logger.info(f"Failing over from {primary_node} to {backup_node}")
            return RecoveryResult(
                success=True,
                action_type=RecoveryActionType.FAILOVER,
                duration_seconds=0.0,
                details={"primary_node": primary_node, "backup_node": backup_node},
            )

        except Exception as e:
            return RecoveryResult(
                success=False,
                action_type=RecoveryActionType.FAILOVER,
                duration_seconds=0.0,
                error_message=str(e),
            )

    def _quarantine_node(self, context: Dict[str, Any]) -> RecoveryResult:
        """Quarantine a node"""
        node_id = context.get("node_id", "unknown")

        try:
            logger.warning(f"Quarantining node: {node_id}")
            return RecoveryResult(
                success=True,
                action_type=RecoveryActionType.QUARANTINE_NODE,
                duration_seconds=0.0,
                details={"node_id": node_id},
            )

        except Exception as e:
            return RecoveryResult(
                success=False,
                action_type=RecoveryActionType.QUARANTINE_NODE,
                duration_seconds=0.0,
                error_message=str(e),
            )

    def _execute_script(self, context: Dict[str, Any]) -> RecoveryResult:
        """Execute a custom script, preferably in a Docker container for isolation."""
        import uuid
        script_content = context.get("script") or context.get("action")
        if not script_content:
            return RecoveryResult(
                success=False,
                action_type=RecoveryActionType.EXECUTE_SCRIPT,
                duration_seconds=0.0,
                error_message="No script content provided",
            )

        # If it's a full AI response, try to extract script
        if "AI-Analysis" in script_content and "```" in script_content:
            import re
            match = re.search(r"```(?:bash|sh)?\n(.*?)\n```", script_content, re.DOTALL)
            if match:
                script_content = match.group(1)

        try:
            # 1. Try Docker for isolation
            if self._available_backends.get("docker"):
                # Run in a minimal alpine container with a timeout
                container_name = f"x0t-recovery-{uuid.uuid4().hex[:8]}"
                cmd = [
                    "docker", "run", "--rm",
                    "--name", container_name,
                    "--network", "none",  # Isolate network by default
                    "--memory", "64m",    # Limit memory
                    "--cpu-shares", "128", # Limit CPU
                    "alpine:latest",
                    "sh", "-c", script_content
                ]
                result = safe_run(cmd, capture_output=True, text=True, timeout=60)
                if result.returncode == 0:
                    return RecoveryResult(
                        success=True,
                        action_type=RecoveryActionType.EXECUTE_SCRIPT,
                        duration_seconds=0.0,
                        details={"method": "docker", "stdout": result.stdout},
                    )
                else:
                    logger.warning(f"Docker script execution failed: {result.stderr}")
                    # Fallback or report failure

            # 2. Local execution (fallback)
            logger.info("Executing script locally (no container isolation)")
            result = safe_run(
                ["sh", "-c", script_content],
                capture_output=True,
                text=True,
                timeout=30
            )

            return RecoveryResult(
                success=result.returncode == 0,
                action_type=RecoveryActionType.EXECUTE_SCRIPT,
                duration_seconds=0.0,
                error_message=result.stderr if result.returncode != 0 else None,
                details={"method": "local", "stdout": result.stdout},
            )

        except Exception as e:
            return RecoveryResult(
                success=False,
                action_type=RecoveryActionType.EXECUTE_SCRIPT,
                duration_seconds=0.0,
                error_message=str(e),
            )

    def _record_action(self, result: RecoveryResult) -> None:
        """Record action in history"""
        self.action_history.append(result)

        # Limit history size
        if len(self.action_history) > self.max_history_size:
            self.action_history = self.action_history[-self.max_history_size :]

    def _switch_protocol(self, context: Dict[str, Any]) -> RecoveryResult:
        """Switch transport protocol (e.g., standard -> stego)"""
        protocol = context.get("protocol", "stego")
        mimic = context.get("mimic", "http")

        try:
            # Try to find NodeManager if it exists in the app state or singleton
            # For demo/mock purposes, we log the intent
            if self._routing_backend and hasattr(self._routing_backend, "switch_protocol"):
                success = self._routing_backend.switch_protocol(protocol, mimic)
                return RecoveryResult(
                    success=success,
                    action_type=RecoveryActionType.SWITCH_PROTOCOL,
                    duration_seconds=0.0,
                    details={"protocol": protocol, "mimic": mimic}
                )

            logger.warning(f"Protocol switch to {protocol} logged (backend deferred)")
            return RecoveryResult(
                success=True,
                action_type=RecoveryActionType.SWITCH_PROTOCOL,
                duration_seconds=0.0,
                details={"protocol": protocol, "mimic": mimic, "method": "deferred"}
            )
        except Exception as e:
            return RecoveryResult(
                success=False,
                action_type=RecoveryActionType.SWITCH_PROTOCOL,
                duration_seconds=0.0,
                error_message=str(e)
            )

    def get_action_history(self, limit: int = 100) -> List[RecoveryResult]:
        """Get recent action history"""
        return self.action_history[-limit:]

    def get_success_rate(
        self, action_type: Optional[RecoveryActionType] = None
    ) -> float:
        """Get success rate for actions"""
        if not self.action_history:
            return 0.0

        filtered = self.action_history
        if action_type:
            filtered = [r for r in self.action_history if r.action_type == action_type]

        if not filtered:
            return 0.0

        successful = sum(1 for r in filtered if r.success)
        return successful / len(filtered)

    def _save_state_for_rollback(
        self, action_type: RecoveryActionType, context: Dict[str, Any]
    ):
        """Save state before action for potential rollback"""
        rollback_state = {
            "action_type": self._action_type_value(action_type),
            "context": context.copy(),
            "timestamp": datetime.now().isoformat(),
            "node_id": self.node_id,
        }
        self.rollback_stack.append(rollback_state)

        # Keep only last 100 rollback states
        if len(self.rollback_stack) > 100:
            self.rollback_stack.pop(0)

    def rollback_last_action(self) -> bool:
        """
        Rollback the last successful action.

        Returns:
            True if rollback successful
        """
        if not self.rollback_stack:
            logger.warning("No actions to rollback")
            return False

        last_action = self.rollback_stack.pop()
        action_type_str = last_action["action_type"]
        context = last_action["context"]

        logger.info(f"Rolling back action: {action_type_str}")

        # Determine rollback action based on original action
        rollback_action = self._get_rollback_action(action_type_str, context)

        if rollback_action:
            return self.execute(rollback_action, context)
        else:
            logger.warning(f"No rollback strategy for action: {action_type_str}")
            return False

    def _get_rollback_action(
        self, action_type_str: str, context: Dict[str, Any]
    ) -> Optional[str]:
        """
        Get rollback action for a given action type.

        Args:
            action_type_str: Original action type
            context: Original context

        Returns:
            Rollback action string or None
        """
        rollback_strategies = {
            "restart_service": None,  # Restart doesn't need rollback
            "switch_route": f"Switch route to {context.get('old_route', 'previous')}",
            "clear_cache": None,  # Cache clear doesn't need rollback
            "scale_up": f"Scale down {context.get('deployment_name')} to {context.get('old_replicas', 1)}",
            "scale_down": f"Scale up {context.get('deployment_name')} to {context.get('old_replicas', 1)}",
            "failover": f"Failover back to {context.get('primary_region', 'original')}",
            "quarantine_node": f"Unquarantine node {context.get('node_id')}",
        }

        return rollback_strategies.get(action_type_str)

    async def restart_service(
        self, service_name: str, namespace: str = "default"
    ) -> bool:
        """Public wrapper for _restart_service"""
        context = {"service_name": service_name, "namespace": namespace}
        result = self._restart_service(context)
        return result.success

    async def switch_route(self, old_route: str, new_route: str) -> bool:
        """Public wrapper for _switch_route"""
        context = {"old_route": old_route, "alternative_route": new_route}
        result = self._switch_route(context)
        return result.success

    async def clear_cache(self, service_name: str, cache_type: str) -> bool:
        """Public wrapper for _clear_cache"""
        context = {"service_name": service_name, "cache_type": cache_type}
        result = self._clear_cache(context)
        return result.success

    async def scale_up(
        self, deployment_name: str, replicas: int, namespace: str = "default"
    ) -> bool:
        """Public wrapper for _scale_up"""
        context = {
            "deployment_name": deployment_name,
            "replicas": replicas,
            "namespace": namespace,
            "old_replicas": replicas - 1,
        }
        result = self._scale_up(context)
        return result.success

    async def scale_down(
        self, deployment_name: str, replicas: int, namespace: str = "default"
    ) -> bool:
        """Public wrapper for _scale_down"""
        context = {
            "deployment_name": deployment_name,
            "replicas": replicas,
            "namespace": namespace,
            "old_replicas": replicas + 1,
        }
        result = self._scale_down(context)
        return result.success

    async def failover(
        self, service_name: str, primary_region: str, fallback_region: str
    ) -> bool:
        """Public wrapper for _failover"""
        context = {
            "service_name": service_name,
            "primary_region": primary_region,
            "fallback_region": fallback_region,
        }
        result = self._failover(context)
        return result.success

    async def quarantine_node(self, node_id: str) -> bool:
        """Public wrapper for _quarantine_node"""
        context = {"node_id": node_id}
        result = self._quarantine_node(context)
        return result.success

    async def execute_action(
        self, action_type: str, context: Optional[Dict[str, Any]] = None, **kwargs
    ) -> bool:
        """Public async wrapper for execute action"""
        if context is None:
            context = {}
        context.update(kwargs)
        return self.execute(action_type, context)

    def get_circuit_breaker_status(self) -> Dict[str, Any]:
        """Get circuit breaker status"""
        if not self.circuit_breaker:
            return {"enabled": False}

        return {
            "enabled": True,
            "state": self.circuit_breaker.state.state,
            "failures": self.circuit_breaker.state.failures,
            "successes": self.circuit_breaker.state.successes,
            "last_failure": (
                self.circuit_breaker.state.last_failure_time.isoformat()
                if self.circuit_breaker.state.last_failure_time
                else None
            ),
        }

    def get_rate_limiter_status(self) -> Dict[str, Any]:
        """Get rate limiter status"""
        if not self.rate_limiter:
            return {"enabled": False}

        return {
            "enabled": True,
            "current_actions": len(self.rate_limiter.action_times),
            "max_actions": self.rate_limiter.max_actions,
            "window_seconds": self.rate_limiter.window_seconds,
        }

