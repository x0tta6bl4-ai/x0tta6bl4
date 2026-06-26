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
import hashlib
import shutil
import signal
import tempfile
from typing import Any, Dict, List, Optional

from src.libx0t.core.subprocess_validator import safe_popen
import time
from dataclasses import dataclass
from enum import Enum
from pathlib import Path
from typing import Any, Dict, List, Optional

from src.core.thinking.agent_thinking import AgentThinkingCoach

logger = logging.getLogger(__name__)


def _safe_hash(value: Any) -> Optional[str]:
    if value is None:
        return None
    return hashlib.sha256(str(value).encode("utf-8")).hexdigest()


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
        self.thinking_coach = AgentThinkingCoach(
            agent_id="libx0t-spire-agent-manager",
            role="security",
            capabilities=("zero-trust", "ops"),
        )
        self.last_thinking_context: Dict[str, Any] = {}

        self._spire_agent_bin = self._find_spire_binary("spire-agent")
        self._spire_server_bin = self._find_spire_binary("spire-server")
        self._record_thinking(
            "libx0t_spire_agent_manager_initialized",
            "track real SPIRE agent lifecycle without treating mocks as proof",
            {
                "agent_binary_configured": bool(self._spire_agent_bin),
                "server_binary_configured": bool(self._spire_server_bin),
            },
        )

        logger.info(
            "SPIRE Agent manager initialized: config=%s, socket=%s",
            config_path,
            socket_path,
        )

    def _record_thinking(
        self,
        task_type: str,
        goal: str,
        extra: Optional[Dict[str, Any]] = None,
    ) -> Dict[str, Any]:
        context: Dict[str, Any] = {
            "type": task_type,
            "goal": goal,
            "agent_running": (
                self.agent_process is not None
                and self.agent_process.poll() is None
            ),
            "join_token_configured": bool(self._join_token),
            "config_path_hash": _safe_hash(self.config_path),
            "socket_path_hash": _safe_hash(self.socket_path),
            "constraints": {
                "require_real_unix_socket": True,
                "mock_is_not_spire_evidence": True,
                "redact_join_tokens": True,
                "redact_raw_spiffe_ids": True,
                "redact_raw_paths": True,
            },
            "safety_boundary": (
                "Local SPIRE agent lifecycle state is not proof of workload SVID "
                "possession, mTLS dataplane delivery, customer traffic, or "
                "production readiness."
            ),
        }
        if extra:
            context.update(extra)
        self.last_thinking_context = self.thinking_coach.prepare_task(context)
        return self.last_thinking_context

    def get_thinking_status(self) -> Dict[str, Any]:
        """Expose thinking profile and latest redacted SPIRE agent context."""
        return {
            "thinking": self.thinking_coach.status(),
            "last_thinking_context": self.last_thinking_context,
        }

    def start(self) -> bool:
        """
        Start SPIRE Agent process and wait for it to become ready.

        Returns:
            True if the agent was started successfully.
        """
        if self.agent_process and self.agent_process.poll() is None:
            self._record_thinking(
                "libx0t_spire_agent_start",
                "avoid starting duplicate SPIRE agent process",
                {"status": "already_running"},
            )
            logger.warning("SPIRE Agent already running")
            return True

        try:
            self._record_thinking(
                "libx0t_spire_agent_start",
                "start real SPIRE agent and wait for a verified Unix socket",
                {
                    "status": "start_requested",
                    "config_exists": self.config_path.exists(),
                },
            )
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

            self.agent_process = safe_popen(
                cmd,
                stdout=subprocess.PIPE,
                stderr=subprocess.PIPE,
                env=env,
                preexec_fn=os.setsid,
            )

            logger.info("Started SPIRE Agent (PID=%s)", self.agent_process.pid)

            for _ in range(20):
                if self._socket_ready():
                    self._record_thinking(
                        "libx0t_spire_agent_start",
                        "record verified SPIRE Unix socket readiness",
                        {
                            "status": "socket_ready",
                            "real_unix_socket": True,
                            "pid_present": self.agent_process.pid is not None,
                        },
                    )
                    logger.info("SPIRE Agent socket is ready at %s", self.socket_path)
                    return True
                time.sleep(0.5)

            self._record_thinking(
                "libx0t_spire_agent_start",
                "reject SPIRE readiness when verified Unix socket does not appear",
                {"status": "socket_timeout", "real_unix_socket": False},
            )
            logger.error("SPIRE Agent socket did not appear within timeout")
            self.stop()
            return False
        except Exception:
            self._record_thinking(
                "libx0t_spire_agent_start",
                "record SPIRE agent start failure without exposing raw paths",
                {"status": "start_failed"},
            )
            logger.exception("Failed to start SPIRE Agent")
            return False

    def stop(self) -> bool:
        """
        Stop SPIRE Agent gracefully.

        Returns:
            True if agent stopped successfully.
        """
        if not self.agent_process or self.agent_process.poll() is not None:
            self._record_thinking(
                "libx0t_spire_agent_stop",
                "avoid stopping when no real SPIRE agent process is running",
                {"status": "not_running"},
            )
            logger.info("No running SPIRE Agent process to stop")
            return True

        try:
            self._record_thinking(
                "libx0t_spire_agent_stop",
                "stop real SPIRE agent process gracefully",
                {
                    "status": "stop_requested",
                    "pid_present": getattr(self.agent_process, "pid", None)
                    is not None,
                },
            )
            logger.info("Stopping SPIRE Agent (PID=%s)", self.agent_process.pid)
            os.killpg(os.getpgid(self.agent_process.pid), signal.SIGTERM)

            for _ in range(20):
                if self.agent_process.poll() is not None:
                    self._record_thinking(
                        "libx0t_spire_agent_stop",
                        "record graceful SPIRE agent stop",
                        {"status": "stopped_gracefully"},
                    )
                    logger.info("SPIRE Agent stopped gracefully")
                    self._cleanup()
                    return True
                time.sleep(0.5)

            logger.warning("SPIRE Agent did not stop gracefully, sending SIGKILL")
            os.killpg(os.getpgid(self.agent_process.pid), signal.SIGKILL)
            self.agent_process.wait(timeout=5)
            self._cleanup()
            self._record_thinking(
                "libx0t_spire_agent_stop",
                "record forced SPIRE agent stop after graceful timeout",
                {"status": "stopped_forcefully"},
            )
            return True
        except Exception:
            self._record_thinking(
                "libx0t_spire_agent_stop",
                "record SPIRE agent stop failure without exposing process details",
                {"status": "stop_failed"},
            )
            logger.exception("Failed to stop SPIRE Agent")
            return False

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
        self._record_thinking(
            "libx0t_spire_agent_attest_node",
            "handle node attestation request without exposing join token material",
            {
                "strategy": strategy.value,
                "token_present": "token" in attestation_data,
            },
        )

        if strategy == AttestationStrategy.JOIN_TOKEN:
            token = attestation_data.get("token")
            if not token:
                self._record_thinking(
                    "libx0t_spire_agent_attest_node",
                    "reject join-token attestation when token is absent",
                    {"strategy": strategy.value, "status": "missing_token"},
                )
                raise ValueError("join_token strategy requires 'token' parameter")

            self._join_token = token
            logger.info(
                "Join token has been set. It will be used for agent attestation."
            )

            # If agent is already running, restart it to apply the new token
            if self.agent_process and self.agent_process.poll() is None:
                logger.info("Restarting agent to apply new join token.")
                self._record_thinking(
                    "libx0t_spire_agent_attest_node",
                    "restart SPIRE agent so explicit join token can be applied",
                    {"strategy": strategy.value, "status": "restart_required"},
                )
                self.stop()
                return self.start()

            self._record_thinking(
                "libx0t_spire_agent_attest_node",
                "store explicit join token for next real SPIRE agent start",
                {"strategy": strategy.value, "status": "pending_next_start"},
            )
            return True

        self._record_thinking(
            "libx0t_spire_agent_attest_node",
            "reject unsupported attestation strategy until implemented",
            {"strategy": strategy.value, "status": "unsupported_strategy"},
        )
        logger.warning(
            "Attestation strategy %s is not fully implemented", strategy.value
        )
        return False

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
        self._record_thinking(
            "libx0t_spire_agent_register_workload",
            "register workload through real spire-server CLI without raw IDs in status",
            {
                "spiffe_id_hash": _safe_hash(entry.spiffe_id),
                "parent_id_hash": _safe_hash(entry.parent_id),
                "selector_count": len(entry.selectors),
                "ttl_seconds": int(entry.ttl),
            },
        )

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
            result = subprocess.run(
                cmd, capture_output=True, check=True, text=True, timeout=30
            )
            logger.info(
                "Successfully registered workload entry: %s", result.stdout.strip()
            )
            self._record_thinking(
                "libx0t_spire_agent_register_workload",
                "record successful workload registration command",
                {"status": "registered", "selector_count": len(entry.selectors)},
            )
            return True
        except FileNotFoundError:
            self._record_thinking(
                "libx0t_spire_agent_register_workload",
                "record missing spire-server binary for workload registration",
                {"status": "server_binary_missing"},
            )
            logger.error("`spire-server` binary not found, cannot register workload.")
            return False
        except subprocess.CalledProcessError as e:
            self._record_thinking(
                "libx0t_spire_agent_register_workload",
                "record failed workload registration command with redacted stderr",
                {"status": "command_failed", "error_type": type(e).__name__},
            )
            logger.error(
                "Failed to register workload %s. Error: %s",
                entry.spiffe_id,
                e.stderr,
            )
            return False
        except Exception:
            self._record_thinking(
                "libx0t_spire_agent_register_workload",
                "record unexpected workload registration failure",
                {"status": "unexpected_failure"},
            )
            logger.exception(
                "An unexpected error occurred during workload registration."
            )
            return False

    def list_workloads(self) -> List[WorkloadEntry]:
        """
        List all registered workloads from SPIRE Server.

        Uses `spire-server entry show` to fetch all registered entries.

        Returns:
            List of workload entries.
        """
        if not self._spire_server_bin:
            self._record_thinking(
                "libx0t_spire_agent_list_workloads",
                "reject workload listing when spire-server binary is absent",
                {"status": "server_binary_missing"},
            )
            logger.warning("spire-server binary not found, cannot list workloads")
            return []

        try:
            self._record_thinking(
                "libx0t_spire_agent_list_workloads",
                "list workloads through real spire-server CLI with redacted output",
                {"status": "list_requested"},
            )
            # Execute: spire-server entry show
            cmd = [self._spire_server_bin, "entry", "show"]
            result = subprocess.run(cmd, capture_output=True, text=True, timeout=30)

            if result.returncode != 0:
                self._record_thinking(
                    "libx0t_spire_agent_list_workloads",
                    "record failed workload listing command",
                    {"status": "command_failed"},
                )
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
            self._record_thinking(
                "libx0t_spire_agent_list_workloads",
                "record workload listing count without raw SPIFFE IDs",
                {"status": "listed", "workload_count": len(workloads)},
            )
            return workloads

        except FileNotFoundError:
            self._record_thinking(
                "libx0t_spire_agent_list_workloads",
                "record missing spire-server binary while listing workloads",
                {"status": "server_binary_missing"},
            )
            logger.warning("spire-server binary not found, cannot list workloads")
            return []
        except subprocess.TimeoutExpired:
            self._record_thinking(
                "libx0t_spire_agent_list_workloads",
                "record workload listing timeout",
                {"status": "timeout"},
            )
            logger.error("Timeout while listing workloads")
            return []
        except Exception as e:
            self._record_thinking(
                "libx0t_spire_agent_list_workloads",
                "record unexpected workload listing failure",
                {"status": "unexpected_failure", "error_type": type(e).__name__},
            )
            logger.exception(f"Error listing workloads: {e}")
            return []

    def health_check(self) -> bool:
        """
        Check SPIRE Agent health via its process status, socket, and healthcheck command.

        Returns:
            True if the agent is healthy.
        """
        if not self.agent_process or self.agent_process.poll() is not None:
            self._record_thinking(
                "libx0t_spire_agent_health_check",
                "report unhealthy when no real SPIRE agent process is running",
                {"status": "process_not_running"},
            )
            return False

        if not self._socket_ready():
            self._record_thinking(
                "libx0t_spire_agent_health_check",
                "report unhealthy when SPIRE endpoint is not a verified Unix socket",
                {"status": "socket_not_ready", "real_unix_socket": False},
            )
            return False

        try:
            # print("DEBUG: Calling subprocess.run in health_check") # Removed debug print
            result = subprocess.run(
                [
                    self._spire_agent_bin,
                    "healthcheck",
                    "-socketPath",
                    str(self.socket_path),
                ],
                capture_output=True,
                timeout=5,
            )
            healthy = result.returncode == 0
            self._record_thinking(
                "libx0t_spire_agent_health_check",
                "record real spire-agent healthcheck command result",
                {
                    "status": "healthy" if healthy else "unhealthy",
                    "real_unix_socket": True,
                },
            )
            return healthy
        except Exception:
            self._record_thinking(
                "libx0t_spire_agent_health_check",
                "record failed spire-agent healthcheck command as unhealthy",
                {"status": "healthcheck_failed", "real_unix_socket": True},
            )
            logger.exception("SPIRE Agent healthcheck command failed")
            return False

    # ------------------------------------------------------------------
    # Internal helpers
    # ------------------------------------------------------------------

    def _socket_ready(self) -> bool:
        """Return True only when the SPIRE endpoint is a real Unix socket."""
        try:
            return bool(self.socket_path.exists()) and bool(self.socket_path.is_socket())
        except Exception:
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
            except Exception:
                logger.exception("Failed to remove generated SPIRE config")

        self._generated_config_path = None
        self.agent_process = None

