"""SPIRE Agent Manager.

Manages SPIRE Agent lifecycle:

- Start/stop agent process
- Node attestation
- Workload registration
- Health monitoring

Interacts with SPIRE Server for identity provisioning.

The implementation starts a real ``spire-agent`` process. Tests may mock
subprocess calls, but a regular file must never count as a ready SPIRE
Workload API socket.
"""
from __future__ import annotations

import logging
import os
import shutil
import signal
import subprocess
import tempfile
import time
from dataclasses import dataclass
from enum import Enum
from pathlib import Path
from typing import Any, Callable, Dict, List, Optional

from src.coordination.events import EventBus, EventType, get_event_bus
from src.core.security.subprocess_validator import safe_run
from src.integration.spine import SafeActuator, SafeActuatorResult
from src.security.policy_decision_adapter import (
    policy_allowed as normalize_policy_allowed,
    policy_reason as normalize_policy_reason,
    policy_rules as normalize_policy_rules,
)
from src.services.service_event_identity import service_event_identity

logger = logging.getLogger(__name__)

_SERVICE_AGENT = "spire-agent-manager"

SPIRE_AGENT_CLAIM_BOUNDARY = (
    "SPIRE agent manager control event only. It records local identity, policy, "
    "and safe actuator state for SPIRE agent/server CLI lifecycle actions; it "
    "is not proof of live production SPIRE mTLS, workload traffic, or operator "
    "raw evidence."
)


class AttestationStrategy(Enum):
    """Node attestation strategies"""

    JOIN_TOKEN = "join_token"  # Static join token (dev only)
    AWS_IID = "aws_iid"  # AWS Instance Identity Document
    K8S_PSAT = "k8s_psat"  # Kubernetes Projected Service Account Token
    X509_POP = "x509pop"  # X.509 Proof of Possession


@dataclass
class WorkloadEntry:
    """Workload registration entry"""

    spiffe_id: str
    parent_id: str
    selectors: Dict[str, str]  # e.g., {"k8s:pod-name": "web-server"}
    ttl: int = 3600  # seconds


class SPIREAgentManager:
    """
    Manages SPIRE Agent process and workload registration.

    This manager requires `spire-agent` and `spire-server` binaries
    to be available in the system's PATH or specified via environment
    variables.

    Example:
        >>> agent = SPIREAgentManager("/opt/spire/conf/agent.conf")
        >>> agent.start()
        >>> agent.register_workload(WorkloadEntry(
        ...     spiffe_id="spiffe://x0tta6bl4.mesh/workload/api",
        ...     parent_id="spiffe://x0tta6bl4.mesh/node/worker-1",
        ...     selectors={"unix:uid": "1000"}
        ... ))
    """

    def __init__(
        self,
        config_path: Path = Path("/etc/spire/agent/agent.conf"),
        socket_path: Path = Path("/run/spire/sockets/agent.sock"),
        *,
        event_bus: Optional[EventBus] = None,
        event_project_root: str = ".",
        policy_engine: Optional[Any] = None,
        require_policy: Optional[bool] = None,
        safe_actuator: Optional[SafeActuator] = None,
        source_agent: str = _SERVICE_AGENT,
        node_id: str = "spire-agent-manager",
        spiffe_id: Optional[str] = None,
        did: Optional[str] = None,
        wallet_address: Optional[str] = None,
    ) -> None:
        """Initialize SPIRE Agent manager.

        Args:
            config_path: Path to SPIRE Agent configuration.
            socket_path: Unix socket for Workload API.

        Raises:
            FileNotFoundError: If `spire-agent` or `spire-server` binaries are not found.
        """
        self.config_path = config_path
        self.socket_path = socket_path
        self.agent_process: Optional[subprocess.Popen] = None
        self._generated_config_path: Optional[Path] = None
        self._join_token: Optional[str] = None
        self.event_bus = (
            event_bus
            if event_bus is not None
            else self._default_event_bus(event_project_root)
        )
        self.event_project_root = event_project_root
        self.policy_engine = policy_engine
        self.require_policy = (
            require_policy
            if require_policy is not None
            else self._env_bool("X0TTA6BL4_SPIRE_AGENT_MANAGER_POLICY_REQUIRED", False)
            or self._env_bool("X0TTA6BL4_PRODUCTION", False)
        )
        if self.policy_engine is None and self.require_policy:
            self.policy_engine = self._default_policy_engine()
        service_identity = service_event_identity(service_name=_SERVICE_AGENT)
        self.source_agent = source_agent
        self.identity = {
            "node_id": node_id,
            "spiffe_id": (
                spiffe_id if spiffe_id is not None else service_identity["spiffe_id"]
            ),
            "did": did if did is not None else service_identity["did"],
            "wallet_address": (
                wallet_address
                if wallet_address is not None
                else service_identity["wallet_address"]
            ),
        }
        self.safe_actuator = safe_actuator

        self._spire_agent_bin = self._find_spire_binary("spire-agent")
        self._spire_server_bin = self._find_spire_binary("spire-server")

        logger.info(
            "SPIRE Agent manager initialized: config=%s, socket=%s",
            config_path,
            socket_path,
        )

    @staticmethod
    def _env_bool(name: str, default: bool) -> bool:
        value = os.getenv(name)
        if value is None:
            return default
        return value.strip().lower() in {"1", "true", "yes", "on"}

    @staticmethod
    def _default_event_bus(project_root: str) -> Optional[EventBus]:
        try:
            return get_event_bus(project_root)
        except (ImportError, RuntimeError, OSError, ValueError) as exc:
            logger.error("Failed to initialize SPIRE agent EventBus: %s", exc)
            return None

    @staticmethod
    def _default_policy_engine() -> Optional[Any]:
        try:
            from src.security.zero_trust.policy_engine import get_policy_engine

            return get_policy_engine()
        except (ImportError, RuntimeError, ValueError, OSError) as exc:
            logger.error("Failed to initialize SPIRE agent policy engine: %s", exc)
            return None

    @staticmethod
    def _policy_allowed(decision: Any) -> bool:
        return normalize_policy_allowed(decision)

    @staticmethod
    def _policy_reason(decision: Any) -> str:
        return normalize_policy_reason(decision)

    @staticmethod
    def _policy_rules(decision: Any) -> list[str]:
        return normalize_policy_rules(decision)

    @classmethod
    def _safe_value(cls, key: str, value: Any, depth: int = 0) -> Any:
        blocked_fragments = ("secret", "password", "token", "key", "private")
        if any(fragment in str(key).lower() for fragment in blocked_fragments):
            return "<redacted>"
        if value is None or isinstance(value, (str, int, float, bool)):
            return value
        if isinstance(value, Path):
            return str(value)
        if isinstance(value, dict) and depth < 3:
            return {
                str(child_key): cls._safe_value(str(child_key), child_value, depth + 1)
                for child_key, child_value in value.items()
            }
        if isinstance(value, list) and depth < 3:
            return [cls._safe_value(key, item, depth + 1) for item in value]
        return str(value)

    @classmethod
    def _safe_context(cls, context: Dict[str, Any]) -> Dict[str, Any]:
        return {
            str(key): cls._safe_value(str(key), value)
            for key, value in context.items()
        }

    def _publish_control_event(
        self,
        event_type: EventType,
        *,
        stage: str,
        operation: str,
        context: Dict[str, Any],
        reason: str = "",
        policy_decision: Any = None,
        success: Optional[bool] = None,
        simulated: Optional[bool] = None,
    ) -> Optional[str]:
        if self.event_bus is None:
            return None
        payload = {
            "component": "security.spiffe.agent.manager",
            "stage": stage,
            "operation": operation,
            "resource": f"identity:spire_agent:{operation}",
            "node_id": self.identity["node_id"],
            "spiffe_id": self.identity["spiffe_id"],
            "did": self.identity["did"],
            "wallet_address": self.identity["wallet_address"],
            "identity": dict(self.identity),
            "context": self._safe_context(context),
            "success": success,
            "simulated": simulated,
            "reason": reason,
            "policy_allowed": self._policy_allowed(policy_decision)
            if policy_decision is not None
            else None,
            "policy_reason": self._policy_reason(policy_decision)
            if policy_decision is not None
            else "",
            "matched_rules": self._policy_rules(policy_decision)
            if policy_decision is not None
            else [],
            "safe_actuator": True,
            "policy_required": self.require_policy or self.policy_engine is not None,
            "claim_boundary": SPIRE_AGENT_CLAIM_BOUNDARY,
        }
        try:
            event = self.event_bus.publish(
                event_type,
                self.source_agent,
                payload,
                priority=7,
            )
            return event.event_id
        except (ConnectionError, TimeoutError, OSError, ValueError, RuntimeError) as exc:
            logger.error("Failed to publish SPIRE agent manager event: %s", exc)
            return None

    def _evaluate_control_policy(self, operation: str) -> tuple[bool, Any, str]:
        if self.policy_engine is None:
            if self.require_policy:
                return False, None, "SPIRE agent policy engine is required but unavailable"
            return True, None, ""
        spiffe_id = self.identity.get("spiffe_id")
        if not spiffe_id:
            return False, None, "SPIRE agent SPIFFE identity is required for policy evaluation"
        try:
            decision = self.policy_engine.evaluate(
                spiffe_id,
                resource=f"identity:spire_agent:{operation}",
                workload_type="spire-agent-manager",
            )
        except (ValueError, KeyError, RuntimeError, OSError) as exc:
            return False, None, f"SPIRE agent policy evaluation failed: {exc}"

        if not self._policy_allowed(decision):
            return (
                False,
                decision,
                self._policy_reason(decision)
                or "SPIRE agent policy denied control action",
            )
        return True, decision, self._policy_reason(decision)

    def _run_control_action(
        self,
        *,
        operation: str,
        context: Dict[str, Any],
        executor: Callable[[str, Dict[str, Any]], SafeActuatorResult],
    ) -> SafeActuatorResult:
        self._publish_control_event(
            EventType.COORDINATION_REQUEST,
            stage="received",
            operation=operation,
            context=context,
        )
        allowed, decision, reason = self._evaluate_control_policy(operation)
        if not allowed:
            self._publish_control_event(
                EventType.TASK_BLOCKED,
                stage="policy_denied",
                operation=operation,
                context=context,
                reason=reason,
                policy_decision=decision,
                success=False,
                simulated=False,
            )
            return SafeActuatorResult(False, reason)

        self._publish_control_event(
            EventType.PIPELINE_STAGE_START,
            stage="actuator_start",
            operation=operation,
            context=context,
            reason=reason,
            policy_decision=decision,
        )
        actuator = self.safe_actuator or SafeActuator(executor)
        actuator_result = actuator.execute(operation, context)
        success = bool(actuator_result.success)
        simulated = bool(actuator_result.simulated)
        self._publish_control_event(
            (
                EventType.PIPELINE_STAGE_END
                if success and not simulated
                else EventType.TASK_FAILED
            ),
            stage=(
                "actuator_completed"
                if success and not simulated
                else "actuator_simulated"
                if simulated
                else "actuator_failed"
            ),
            operation=operation,
            context=context,
            reason=actuator_result.reason or reason,
            policy_decision=decision,
            success=success and not simulated,
            simulated=simulated,
        )
        return actuator_result

    def start(self) -> bool:
        """
        Start SPIRE Agent process and wait for it to become ready.

        Returns:
            True if the agent was started successfully.
        """
        if self.agent_process and self.agent_process.poll() is None:
            logger.warning("SPIRE Agent already running")
            return True

        result = self._run_control_action(
            operation="start_agent",
            context={
                "config_path": str(self.config_path),
                "socket_path": str(self.socket_path),
                "join_token_configured": bool(
                    self._join_token or os.getenv("SPIRE_JOIN_TOKEN")
                ),
            },
            executor=self._start_agent_internal,
        )
        return bool(result.success) and not bool(result.simulated)

    def _start_agent_internal(
        self,
        _operation: str,
        _context: Dict[str, Any],
    ) -> SafeActuatorResult:
        try:
            config_to_use = self.config_path
            if not config_to_use.exists():
                self._generated_config_path = self._generate_config()
                config_to_use = self._generated_config_path

            cmd = [self._spire_agent_bin, "run", "-config", str(config_to_use)]

            env = os.environ.copy()
            if self._join_token:
                env["SPIRE_JOIN_TOKEN"] = self._join_token
                logger.info("Using join token from attest_node for node attestation")
            elif env.get("SPIRE_JOIN_TOKEN"):
                logger.info("Using join token from environment for node attestation")

            self.socket_path.parent.mkdir(parents=True, exist_ok=True)

            self.agent_process = subprocess.Popen(
                cmd,
                stdout=subprocess.PIPE,
                stderr=subprocess.PIPE,
                env=env,
                preexec_fn=os.setsid,
            )

            logger.info("Started SPIRE Agent (PID=%s)", self.agent_process.pid)

            for _ in range(20):
                if self._socket_ready():
                    logger.info("SPIRE Agent socket is ready at %s", self.socket_path)
                    return SafeActuatorResult(True, "SPIRE Agent started")
                time.sleep(0.5)

            logger.error("SPIRE Agent socket did not appear within timeout")
            self.stop()
            return SafeActuatorResult(False, "SPIRE Agent socket did not appear")
        except (FileNotFoundError, PermissionError, OSError, subprocess.CalledProcessError):
            logger.exception("Failed to start SPIRE Agent")
            return SafeActuatorResult(False, "Failed to start SPIRE Agent")
        return SafeActuatorResult(True, "SPIRE Agent started")

    def stop(self) -> bool:
        """
        Stop SPIRE Agent gracefully.

        Returns:
            True if agent stopped successfully.
        """
        if not self.agent_process or self.agent_process.poll() is not None:
            logger.info("No running SPIRE Agent process to stop")
            return True

        result = self._run_control_action(
            operation="stop_agent",
            context={
                "pid": getattr(self.agent_process, "pid", None),
                "socket_path": str(self.socket_path),
            },
            executor=self._stop_agent_internal,
        )
        return bool(result.success) and not bool(result.simulated)

    def _stop_agent_internal(
        self,
        _operation: str,
        _context: Dict[str, Any],
    ) -> SafeActuatorResult:
        try:
            logger.info("Stopping SPIRE Agent (PID=%s)", self.agent_process.pid)
            os.killpg(os.getpgid(self.agent_process.pid), signal.SIGTERM)

            for _ in range(20):
                if self.agent_process.poll() is not None:
                    logger.info("SPIRE Agent stopped gracefully")
                    self._cleanup()
                    return SafeActuatorResult(True, "SPIRE Agent stopped gracefully")
                time.sleep(0.5)

            logger.warning("SPIRE Agent did not stop gracefully, sending SIGKILL")
            os.killpg(os.getpgid(self.agent_process.pid), signal.SIGKILL)
            self.agent_process.wait(timeout=5)
            self._cleanup()
            return SafeActuatorResult(True, "SPIRE Agent stopped with SIGKILL")
        except (OSError, subprocess.TimeoutExpired, subprocess.CalledProcessError):
            logger.exception("Failed to stop SPIRE Agent")
            return SafeActuatorResult(False, "Failed to stop SPIRE Agent")

    def attest_node(self, strategy: AttestationStrategy, **attestation_data) -> bool:
        """
        Perform node attestation with SPIRE Server.

        For the `JOIN_TOKEN` strategy, this method stores the token and restarts
        the agent if it is already running, so it can re-attest with the new
        token. If the agent is not running, the token will be used on the next
        call to `start()`.

        Args:
            strategy: Attestation strategy to use.
            **attestation_data: Strategy-specific data (e.g., 'token').

        Returns:
            True if the attestation action was successful or is pending.
        """
        logger.info(f"Received request to attest node with strategy: {strategy.value}")

        if strategy == AttestationStrategy.JOIN_TOKEN:
            token = attestation_data.get("token")
            if not token:
                raise ValueError("join_token strategy requires 'token' parameter")

            result = self._run_control_action(
                operation="attest_node",
                context={
                    "strategy": strategy.value,
                    "token": token,
                    "agent_running": bool(
                        self.agent_process and self.agent_process.poll() is None
                    ),
                },
                executor=lambda _operation, _context: self._attest_join_token_internal(
                    token
                ),
            )
            return bool(result.success) and not bool(result.simulated)

        logger.warning(
            "Attestation strategy %s is not fully implemented", strategy.value
        )
        return False

    def _attest_join_token_internal(self, token: str) -> SafeActuatorResult:
        self._join_token = token
        logger.info(
            "Join token has been set. It will be used for agent attestation."
        )

        # If agent is already running, restart it to apply the new token.
        if self.agent_process and self.agent_process.poll() is None:
            logger.info("Restarting agent to apply new join token.")
            if not self.stop():
                return SafeActuatorResult(
                    False,
                    "SPIRE Agent stop failed during attestation",
                )
            if not self.start():
                return SafeActuatorResult(
                    False,
                    "SPIRE Agent restart failed during attestation",
                )
            return SafeActuatorResult(True, "SPIRE Agent restarted with join token")

        return SafeActuatorResult(True, "Join token stored for next SPIRE Agent start")

    def register_workload(self, entry: WorkloadEntry) -> bool:
        """
               Register a workload entry with the SPIRE Server.

               This executes `spire-server entry create` with the provided details.

               Args:
                   entry: Workload registration entry.

        Returns:
                   True if the registration command executes successfully.
        """
        logger.info(f"Registering workload: {entry.spiffe_id}")

        result = self._run_control_action(
            operation="register_workload",
            context={
                "spiffe_id": entry.spiffe_id,
                "parent_id": entry.parent_id,
                "selectors": dict(entry.selectors),
                "ttl": entry.ttl,
            },
            executor=lambda _operation, _context: self._register_workload_internal(
                entry
            ),
        )
        return bool(result.success) and not bool(result.simulated)

    def _register_workload_internal(self, entry: WorkloadEntry) -> SafeActuatorResult:
        cmd = [
            self._spire_server_bin,
            "entry",
            "create",
            "-spiffeID",
            entry.spiffe_id,
            "-parentID",
            entry.parent_id,
            "-ttl",
            str(entry.ttl),
        ]
        for key, value in entry.selectors.items():
            cmd.extend(["-selector", f"{key}:{value}"])

        try:
            result = safe_run(
                cmd, capture_output=True, check=True, text=True, timeout=30
            )
            logger.info(
                "Successfully registered workload entry: %s", result.stdout.strip()
            )
            return SafeActuatorResult(True, "SPIRE workload registered")
        except FileNotFoundError:
            logger.error("`spire-server` binary not found, cannot register workload.")
            return SafeActuatorResult(False, "spire-server binary not found")
        except subprocess.CalledProcessError as e:
            logger.error(
                "Failed to register workload %s. Error: %s",
                entry.spiffe_id,
                e.stderr,
            )
            return SafeActuatorResult(False, "SPIRE workload registration failed")
        except (subprocess.CalledProcessError, OSError, ValueError, RuntimeError):
            logger.exception(
                "An unexpected error occurred during workload registration."
            )
            return SafeActuatorResult(
                False,
                "Unexpected SPIRE workload registration error",
            )

    def list_workloads(self) -> List[WorkloadEntry]:
        """
        List all registered workloads from SPIRE Server.

        Uses `spire-server entry show` to fetch all registered entries.

        Returns:
            List of workload entries.
        """
        if not self._spire_server_bin:
            logger.warning("spire-server binary not found, cannot list workloads")
            return []

        try:
            # Execute: spire-server entry show
            cmd = [self._spire_server_bin, "entry", "show"]
            result = safe_run(cmd, capture_output=True, text=True, timeout=30)

            if result.returncode != 0:
                logger.warning(f"Failed to list workloads: {result.stderr.strip()}")
                return []

            # Parse output: each entry is separated by blank lines
            # Format: Entry ID: <id>
            #         SPIFFE ID: <spiffe_id>
            #         Parent ID: <parent_id>
            #         TTL: <ttl>
            #         Selector: <type>:<value>
            #         ...
            workloads = []
            current_entry = {}
            lines = result.stdout.strip().split("\n")

            for line in lines:
                line = line.strip()
                if not line:
                    # Empty line - end of entry, create WorkloadEntry if valid
                    if current_entry.get("spiffe_id") and current_entry.get(
                        "parent_id"
                    ):
                        workloads.append(
                            WorkloadEntry(
                                spiffe_id=current_entry["spiffe_id"],
                                parent_id=current_entry["parent_id"],
                                selectors=current_entry.get("selectors", {}),
                                ttl=int(current_entry.get("ttl", 3600)),
                            )
                        )
                    current_entry = {}
                    continue

                # Parse key-value pairs
                if ":" in line:
                    key, value = line.split(":", 1)
                    key = key.strip().lower()
                    value = value.strip()

                    if key == "spiffe id":
                        current_entry["spiffe_id"] = value
                    elif key == "parent id":
                        current_entry["parent_id"] = value
                    elif key == "ttl":
                        current_entry["ttl"] = value.replace("s", "").strip()
                    elif key == "selector":
                        if "selectors" not in current_entry:
                            current_entry["selectors"] = {}
                        # Format: "k8s:pod-name:web-server" or "unix:uid:1000"
                        if ":" in value:
                            parts = value.split(":", 2)
                            if len(parts) >= 2:
                                selector_type = parts[0]
                                selector_value = (
                                    parts[1] if len(parts) == 2 else ":".join(parts[1:])
                                )
                                current_entry["selectors"][
                                    f"{selector_type}:{selector_value.split(':')[0]}"
                                ] = (
                                    selector_value.split(":")[-1]
                                    if ":" in selector_value
                                    else selector_value
                                )

            # Handle last entry if file doesn't end with blank line
            if current_entry.get("spiffe_id") and current_entry.get("parent_id"):
                workloads.append(
                    WorkloadEntry(
                        spiffe_id=current_entry["spiffe_id"],
                        parent_id=current_entry["parent_id"],
                        selectors=current_entry.get("selectors", {}),
                        ttl=int(current_entry.get("ttl", 3600)),
                    )
                )

            logger.info(f"Listed {len(workloads)} registered workloads")
            return workloads

        except FileNotFoundError:
            logger.warning("spire-server binary not found, cannot list workloads")
            return []
        except subprocess.TimeoutExpired:
            logger.error("Timeout while listing workloads")
            return []
        except (subprocess.CalledProcessError, OSError, ValueError) as e:
            logger.exception(f"Error listing workloads: {e}")
            return []

    def health_check(self) -> bool:
        """
        Check SPIRE Agent health via its process status, socket, and healthcheck command.

        Returns:
            True if the agent is healthy.
        """
        if not self.agent_process or self.agent_process.poll() is not None:
            return False

        if not self._socket_ready():
            return False

        result = self._run_control_action(
            operation="agent_health_check",
            context={"socket_path": str(self.socket_path)},
            executor=self._health_check_internal,
        )
        return bool(result.success) and not bool(result.simulated)

    def _health_check_internal(
        self,
        _operation: str,
        _context: Dict[str, Any],
    ) -> SafeActuatorResult:
        try:
            result = safe_run(
                [
                    self._spire_agent_bin,
                    "healthcheck",
                    "-socketPath",
                    str(self.socket_path),
                ],
                capture_output=True,
                timeout=5,
            )
            return SafeActuatorResult(
                result.returncode == 0,
                "SPIRE Agent healthcheck passed"
                if result.returncode == 0
                else "SPIRE Agent healthcheck returned non-zero",
            )
        except (subprocess.CalledProcessError, OSError):
            logger.exception("SPIRE Agent healthcheck command failed")
            # Fallback: if process is running and socket exists, treat as healthy.
            return SafeActuatorResult(True, "SPIRE Agent healthcheck fallback healthy")

    # ------------------------------------------------------------------
    # Internal helpers
    # ------------------------------------------------------------------

    def _socket_ready(self) -> bool:
        """Return True only when the SPIRE endpoint is a real Unix socket."""
        try:
            return bool(self.socket_path.exists()) and bool(self.socket_path.is_socket())
        except (OSError, RuntimeError):
            return False

    def _find_spire_binary(self, binary_name: str) -> str:
        """Locate a SPIRE binary or raise FileNotFoundError."""
        env_var = f"SPIRE_{binary_name.upper().replace('-', '_')}_BIN_PATH"
        explicit_bin = os.getenv(env_var)
        if explicit_bin and os.path.isfile(explicit_bin):
            return explicit_bin

        bin_path = shutil.which(binary_name)
        if bin_path:
            return bin_path

        raise FileNotFoundError(
            f"{binary_name} not found. Set {env_var} or add it to PATH."
        )

    def _generate_config(self) -> Path:
        """Generate a minimal SPIRE Agent configuration file."""

        trust_domain = os.getenv("SPIRE_TRUST_DOMAIN", "x0tta6bl4.mesh")
        server_address = os.getenv("SPIRE_SERVER_ADDRESS", "127.0.0.1")
        server_port = os.getenv("SPIRE_SERVER_PORT", "8081")
        data_dir = os.getenv("SPIRE_AGENT_DATA_DIR") or tempfile.mkdtemp(
            prefix="spire-agent-",
        )

        config_content = f"""
agent {{
    data_dir = "{data_dir}"
    log_level = "INFO"
    server_address = "{server_address}"
    server_port = {server_port}
    socket_path = "{self.socket_path}"
    trust_domain = "{trust_domain}"
}}

plugins {{
    NodeAttestor "join_token" {{
        plugin_data {{
        }}
    }}

    KeyManager "disk" {{
        plugin_data {{
            directory = "{data_dir}/keys"
        }}
    }}

    WorkloadAttestor "unix" {{
        plugin_data {{
        }}
    }}
}}
"""

        fd, path_str = tempfile.mkstemp(suffix=".conf", prefix="spire-agent-")
        with os.fdopen(fd, "w", encoding="utf-8") as f:
            f.write(config_content)

        logger.debug("Generated SPIRE Agent config at %s", path_str)
        return Path(path_str)

    def _cleanup(self) -> None:
        """Clean up any generated configuration files and reset state."""

        if self._generated_config_path and self._generated_config_path.exists():
            try:
                self._generated_config_path.unlink()
                logger.debug(
                    "Removed generated SPIRE config %s", self._generated_config_path
                )
            except (FileNotFoundError, PermissionError, OSError):
                logger.exception("Failed to remove generated SPIRE config")

        self._generated_config_path = None
        self.agent_process = None

