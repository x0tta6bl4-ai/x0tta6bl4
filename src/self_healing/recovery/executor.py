"""
Recovery Actions for MAPE-K - Main Executor
"""

from __future__ import annotations
import logging
import shutil
import subprocess
import time
from datetime import datetime
from typing import Any, Dict, List, Optional

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
    Policy-gated recovery action executor.

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
        if max_retries < 1 or retry_delay < 0:
            raise ValueError("max_retries must be positive and retry_delay non-negative")
        self.last_result: RecoveryResult | None = None
        self.node_id = node_id
        self.action_history: List[RecoveryResult] = []
        self.max_history_size = 1000
        self.event_bus = event_bus if event_bus is not None else get_event_bus()
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
        self.circuit_breaker = (
            CircuitBreaker(is_failure=lambda result: not result.success)
            if enable_circuit_breaker
            else None
        )

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
            f"(backends: {available or ['unavailable']}, "
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
                hasattr(mgr, m) for m in ("switch_route", "update_route", "set_preferred_next_hop")
            )
            return mgr if has_route_method else None
        except Exception:
            return None

    def execute(
        self,
        action: str,
        context: Optional[Dict[str, Any]] = None,
        *,
        _record_rollback: bool = True,
    ) -> bool:
        """
        Execute recovery action with retry logic, rate limiting, and circuit breaker.

        Args:
            action: Action string (e.g., "Restart service", "Switch route")
            context: Additional context (service name, node ID, etc.)

        Returns:
            True if action executed successfully
        """
        context = dict(context or {})
        start_time = time.monotonic()

        action_type = self._parse_action_type(action)
        if self.rate_limiter and not self.rate_limiter.allow():
            result = RecoveryResult(
                False, action_type, error_message="Rate limit exceeded for recovery action"
            )
            self.last_result = result
            self._record_action(result)
            self._publish_recovery_event(
                EventType.TASK_BLOCKED,
                action=action,
                action_type=action_type,
                context=context,
                stage="rate_limited",
                result=result,
                reason=result.error_message,
            )
            return False
        policy_allowed, policy_decision, policy_reason = self._evaluate_policy(
            action_type,
            context,
        )
        if not policy_allowed:
            result = RecoveryResult(
                success=False,
                action_type=action_type,
                duration_seconds=time.monotonic() - start_time,
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

                result.duration_seconds = time.monotonic() - start_time

                # Save state for rollback if successful
                if result.success and _record_rollback:
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
                    EventType.PIPELINE_STAGE_END if result.success else EventType.TASK_FAILED,
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
                    time.sleep(
                        self.retry_delay * (attempt + 1)
                    )  # Linear backoff (preserve retry timing)
                else:
                    duration = time.monotonic() - start_time
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
        handlers = {
            RecoveryActionType.RESTART_SERVICE: self._restart_service,
            RecoveryActionType.SWITCH_ROUTE: self._switch_route,
            RecoveryActionType.CLEAR_CACHE: self._clear_cache,
            RecoveryActionType.SCALE_UP: self._scale_up,
            RecoveryActionType.SCALE_DOWN: self._scale_down,
            RecoveryActionType.FAILOVER: self._failover,
            RecoveryActionType.QUARANTINE_NODE: self._quarantine_node,
            RecoveryActionType.EXECUTE_SCRIPT: self._execute_script,
            RecoveryActionType.SWITCH_PROTOCOL: self._switch_protocol,
        }
        handler = handlers.get(action_type)
        if handler is None:
            return RecoveryResult(
                False, RecoveryActionType.NO_ACTION, error_message="Unknown action type"
            )
        return handler(context)

    @staticmethod
    def _unavailable(action_type: RecoveryActionType, **details: Any) -> RecoveryResult:
        """A logged intent is not an executed recovery action."""
        return RecoveryResult(
            success=False,
            action_type=action_type,
            error_message="No backend executed the requested recovery action",
            details={**details, "method": "unavailable"},
        )

    def _parse_action_type(self, action: str) -> RecoveryActionType:
        """Parse action string to RecoveryActionType"""
        action_lower = action.strip().lower()
        try:
            return RecoveryActionType(action_lower)
        except ValueError:
            pass

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
                normalize_policy_reason(decision) or "Recovery action policy denied control action",
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
        try:
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
        except Exception:
            logger.exception("Recovery event publication failed; action will not be repeated")
            return None

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
                            "kubectl",
                            "get",
                            "deployment",
                            service_name,
                            "-o",
                            "name",
                            "--namespace",
                            context.get("namespace", "default"),
                            "--request-timeout=2s",
                        ],
                        capture_output=True,
                        timeout=5,
                    )
                    if exists.returncode == 0:
                        result = safe_run(
                            [
                                "kubectl",
                                "rollout",
                                "restart",
                                f"deployment/{service_name}",
                                "--namespace",
                                context.get("namespace", "default"),
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

            # No backend executed the request.
            logger.warning(
                f"Service restart requested but no container manager found for {service_name}"
            )
            return RecoveryResult(
                success=False,
                error_message="No backend executed the requested recovery action",
                action_type=RecoveryActionType.RESTART_SERVICE,
                duration_seconds=0.0,
                details={
                    "method": "unavailable",
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
        start_time = time.monotonic()

        try:
            # Use pre-cached NodeManager (avoids 9s init on every call)
            if self._routing_backend is not None:
                try:
                    manager = self._routing_backend
                    if hasattr(manager, "switch_route"):
                        outcome = manager.switch_route(target_node, alternative_route)
                    elif hasattr(manager, "update_route"):
                        outcome = manager.update_route(target_node, alternative_route)
                    else:
                        outcome = manager.set_preferred_next_hop(target_node, alternative_route)

                    if outcome is False:
                        return RecoveryResult(
                            False,
                            RecoveryActionType.SWITCH_ROUTE,
                            error_message="Routing backend rejected route change",
                        )
                    duration = time.monotonic() - start_time
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
                    if router.set_route(target_node, alternative_route) is False:
                        return RecoveryResult(
                            False,
                            RecoveryActionType.SWITCH_ROUTE,
                            error_message="Mesh router rejected route change",
                        )
                    duration = time.monotonic() - start_time
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

            # A logged intent cannot be counted as successful execution.
            duration = time.monotonic() - start_time
            logger.warning(
                f"No routing backend available, route switch logged: "
                f"{target_node} → {alternative_route}"
            )
            return RecoveryResult(
                success=False,
                error_message="No backend executed the requested recovery action",
                action_type=RecoveryActionType.SWITCH_ROUTE,
                duration_seconds=duration,
                details={
                    "method": "unavailable",
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
        return self._unavailable(
            RecoveryActionType.CLEAR_CACHE, cache_type=context.get("cache_type", "all")
        )

    def _scale_up(self, context: Dict[str, Any]) -> RecoveryResult:
        return self._scale(RecoveryActionType.SCALE_UP, context)

    def _scale_down(self, context: Dict[str, Any]) -> RecoveryResult:
        return self._scale(RecoveryActionType.SCALE_DOWN, context)

    def _scale(self, action_type: RecoveryActionType, context: Dict[str, Any]) -> RecoveryResult:
        service = context.get("deployment_name") or context.get("service_name", "x0tta6bl4")
        replicas = context.get("replicas", 1)
        namespace = context.get("namespace", "default")
        if isinstance(replicas, bool) or not isinstance(replicas, int) or replicas < 0:
            return RecoveryResult(
                False, action_type, error_message="replicas must be a non-negative integer"
            )
        details = {"service": service, "replicas": replicas, "namespace": namespace}
        if not self._available_backends.get("kubectl"):
            return self._unavailable(action_type, **details)
        try:
            result = safe_run(
                [
                    "kubectl",
                    "scale",
                    f"deployment/{service}",
                    f"--replicas={replicas}",
                    "--namespace",
                    namespace,
                    "--request-timeout=25s",
                ],
                capture_output=True,
                text=True,
                timeout=30,
            )
            return RecoveryResult(
                success=result.returncode == 0,
                action_type=action_type,
                error_message=(result.stderr or "Kubernetes scaling failed")
                if result.returncode
                else None,
                details={**details, "method": "kubernetes"},
            )
        except Exception as exc:
            return RecoveryResult(False, action_type, error_message=str(exc), details=details)

    def _failover(self, context: Dict[str, Any]) -> RecoveryResult:
        return self._unavailable(
            RecoveryActionType.FAILOVER,
            primary_node=context.get("primary_node"),
            backup_node=context.get("backup_node"),
        )

    def _quarantine_node(self, context: Dict[str, Any]) -> RecoveryResult:
        return self._unavailable(
            RecoveryActionType.QUARANTINE_NODE, node_id=context.get("node_id", "unknown")
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
                    "docker",
                    "run",
                    "--rm",
                    "--name",
                    container_name,
                    "--network",
                    "none",  # Isolate network by default
                    "--memory",
                    "64m",  # Limit memory
                    "--cpu-shares",
                    "128",  # Limit CPU
                    "alpine:latest",
                    "sh",
                    "-c",
                    script_content,
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
                ["sh", "-c", script_content], capture_output=True, text=True, timeout=30
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
                    details={"protocol": protocol, "mimic": mimic},
                )

            logger.warning(f"Protocol switch to {protocol} logged (backend deferred)")
            return RecoveryResult(
                success=False,
                error_message="No backend executed the requested recovery action",
                action_type=RecoveryActionType.SWITCH_PROTOCOL,
                duration_seconds=0.0,
                details={"protocol": protocol, "mimic": mimic, "method": "unavailable"},
            )
        except Exception as e:
            return RecoveryResult(
                success=False,
                action_type=RecoveryActionType.SWITCH_PROTOCOL,
                duration_seconds=0.0,
                error_message=str(e),
            )

    def get_action_history(self, limit: int = 100) -> List[RecoveryResult]:
        """Get recent action history"""
        return self.action_history[-limit:] if limit > 0 else []

    def get_success_rate(self, action_type: Optional[RecoveryActionType] = None) -> float:
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

    def _save_state_for_rollback(self, action_type: RecoveryActionType, context: Dict[str, Any]):
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

        last_action = self.rollback_stack[-1]
        inverse = self._build_rollback(last_action["action_type"], last_action["context"])
        if inverse is None:
            logger.warning("No evidenced rollback for action: %s", last_action["action_type"])
            return False
        action, context = inverse
        if not self.execute(action, context, _record_rollback=False):
            return False
        self.rollback_stack.pop()
        return True

    @staticmethod
    def _build_rollback(
        action_type: str, context: Dict[str, Any]
    ) -> Optional[tuple[str, Dict[str, Any]]]:
        """Build an inverse only when the caller supplied the previous state.

        This submits a compensating command; it does not verify convergence.
        """
        inverse_context = dict(context)
        if action_type == RecoveryActionType.SWITCH_ROUTE:
            previous = context.get("old_route")
            if not previous:
                return None
            inverse_context["alternative_route"] = previous
            return RecoveryActionType.SWITCH_ROUTE, inverse_context
        if action_type in (RecoveryActionType.SCALE_UP, RecoveryActionType.SCALE_DOWN):
            previous = context.get("old_replicas")
            if isinstance(previous, bool) or not isinstance(previous, int) or previous < 0:
                return None
            inverse_context["replicas"] = previous
            inverse_action = (
                RecoveryActionType.SCALE_DOWN
                if action_type == RecoveryActionType.SCALE_UP
                else RecoveryActionType.SCALE_UP
            )
            return inverse_action, inverse_context
        return None

    def _get_rollback_action(self, action_type_str: str, context: Dict[str, Any]) -> Optional[str]:
        """Compatibility accessor; execution also requires the inverse context."""
        inverse = self._build_rollback(action_type_str, context)
        return inverse[0] if inverse else None

    async def restart_service(self, service_name: str, namespace: str = "default") -> bool:
        """Public wrapper for _restart_service"""
        context = {"service_name": service_name, "namespace": namespace}
        return self.execute(RecoveryActionType.RESTART_SERVICE, context)

    async def switch_route(self, old_route: str, new_route: str) -> bool:
        """Public wrapper for _switch_route"""
        context = {"old_route": old_route, "alternative_route": new_route}
        return self.execute(RecoveryActionType.SWITCH_ROUTE, context)

    async def clear_cache(self, service_name: str, cache_type: str) -> bool:
        """Public wrapper for _clear_cache"""
        context = {"service_name": service_name, "cache_type": cache_type}
        return self.execute(RecoveryActionType.CLEAR_CACHE, context)

    async def scale_up(
        self, deployment_name: str, replicas: int, namespace: str = "default"
    ) -> bool:
        """Public wrapper for _scale_up"""
        context = {
            "deployment_name": deployment_name,
            "replicas": replicas,
            "namespace": namespace,
        }
        return self.execute(RecoveryActionType.SCALE_UP, context)

    async def scale_down(
        self, deployment_name: str, replicas: int, namespace: str = "default"
    ) -> bool:
        """Public wrapper for _scale_down"""
        context = {
            "deployment_name": deployment_name,
            "replicas": replicas,
            "namespace": namespace,
        }
        return self.execute(RecoveryActionType.SCALE_DOWN, context)

    async def failover(self, service_name: str, primary_region: str, fallback_region: str) -> bool:
        """Public wrapper for _failover"""
        context = {
            "service_name": service_name,
            "primary_region": primary_region,
            "fallback_region": fallback_region,
        }
        return self.execute(RecoveryActionType.FAILOVER, context)

    async def quarantine_node(self, node_id: str) -> bool:
        """Public wrapper for _quarantine_node"""
        context = {"node_id": node_id}
        return self.execute(RecoveryActionType.QUARANTINE_NODE, context)

    async def execute_action(
        self, action_type: str, context: Optional[Dict[str, Any]] = None, **kwargs
    ) -> bool:
        """Public async wrapper for execute action"""
        context = {**(context or {}), **kwargs}
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
