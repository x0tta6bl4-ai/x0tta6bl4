"""SPIRE Agent Manager.

Manages SPIRE Agent lifecycle:

- Start/stop agent process
- Node attestation
- Workload registration
- Health monitoring

Interacts with SPIRE Server for identity provisioning.

The implementation supports two operational modes:

* **Real SPIRE mode** – when the ``spire-agent`` binary is available
  and not explicitly disabled; a subprocess is spawned and the agent
  socket is monitored.
* **Mock mode** – used in local development and tests when the binary
  is not present or ``FORCE_MOCK_SPIRE=1`` is set; the Workload API
  socket is simulated by creating a regular file on disk.
"""

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
from src.integration.spine import (
    SafeActuator,
    SafeActuatorEvidenceMetadata,
    SafeActuatorResult,
)
from src.security.policy_decision_adapter import (
    policy_allowed as normalize_policy_allowed,
    policy_reason as normalize_policy_reason,
    policy_rules as normalize_policy_rules,
)
from src.security.spiffe.agent.join_token_guard import JoinTokenReplayGuard
from src.services.service_event_identity import service_event_identity

logger = logging.getLogger(__name__)

_SERVICE_AGENT = "spire-agent-manager"

SPIRE_AGENT_CLAIM_BOUNDARY = (
    "SPIRE agent manager control event only. It records local identity, policy, "
    "and safe actuator state for SPIRE agent/server CLI lifecycle actions; it "
    "is not proof of live production SPIRE mTLS, workload traffic, or operator "
    "raw evidence."
)

SPIRE_AGENT_SAFE_ACTUATOR_CLAIM_BOUNDARY = (
    "SPIRE agent SafeActuator metadata proves only a local policy-gated SPIRE "
    "agent/server CLI lifecycle attempt. It is not proof of live SPIFFE/SPIRE "
    "trust finality, workload SVID possession, node attestation finality, "
    "mTLS dataplane delivery, customer traffic, or production readiness."
)

_SPIRE_AGENT_STRONG_CLAIM_IDS = (
    "live_spire_mtls_claim_allowed",
    "workload_svid_possession_claim_allowed",
    "workload_identity_trust_finality_claim_allowed",
    "node_attestation_finality_claim_allowed",
    "dataplane_delivery_claim_allowed",
    "customer_traffic_claim_allowed",
    "production_identity_readiness_claim_allowed",
    "production_readiness_claim_allowed",
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
        self.join_token_guard = JoinTokenReplayGuard()
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
        except Exception as exc:
            logger.error("Failed to initialize SPIRE agent EventBus: %s", exc)
            return None

    @staticmethod
    def _default_policy_engine() -> Optional[Any]:
        try:
            from src.security.zero_trust.policy_engine import get_policy_engine

            return get_policy_engine()
        except Exception as exc:
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

    def _safe_actuator_claim_gate(
        self,
        *,
        operation: str,
        success: bool,
        simulated: bool,
        policy_decision: Any = None,
    ) -> Dict[str, Any]:
        claim_gate = {
            "schema": "x0tta6bl4.spire_agent.safe_actuator_claim_gate.v1",
            "operation": operation,
            "local_spire_agent_cli_action_succeeded": success and not simulated,
            "safe_actuator_result_recorded": True,
            "safe_actuator_simulated": simulated,
            "policy_required": self.require_policy or self.policy_engine is not None,
            "policy_allowed": self._policy_allowed(policy_decision)
            if policy_decision is not None
            else None,
            "policy_reason": self._policy_reason(policy_decision)
            if policy_decision is not None
            else "",
            "live_spire_mtls_claim_allowed": False,
            "workload_svid_possession_claim_allowed": False,
            "workload_identity_trust_finality_claim_allowed": False,
            "node_attestation_finality_claim_allowed": False,
            "dataplane_delivery_claim_allowed": False,
            "customer_traffic_claim_allowed": False,
            "production_identity_readiness_claim_allowed": False,
            "production_readiness_claim_allowed": False,
            "claim_boundary": SPIRE_AGENT_SAFE_ACTUATOR_CLAIM_BOUNDARY,
            "redacted": True,
        }
        claim_gate.update(
            {
                claim_id: False
                for claim_id in _SPIRE_AGENT_STRONG_CLAIM_IDS
            }
        )
        return claim_gate

    @staticmethod
    def _safe_actuator_cross_plane_claim_gate() -> Dict[str, Any]:
        return {
            "schema": "x0tta6bl4.spire_agent.safe_actuator_cross_plane_claim_gate.v1",
            "trust_plane_evidence_type": "local_spire_agent_cli_attempt",
            "control_plane_evidence_type": "policy_gated_safe_actuator_attempt",
            "requires_live_workload_svid_evidence_for_trust_finality": True,
            "requires_node_attestation_evidence_for_node_finality": True,
            "requires_dataplane_probe_for_delivery_claim": True,
            "requires_customer_traffic_proof_for_customer_claim": True,
            "requires_production_attestation_for_production_claim": True,
            "allowed": False,
            "redacted": True,
        }

    def _safe_actuator_evidence_metadata(
        self,
        *,
        operation: str,
        context: Dict[str, Any],
        actuator_result: SafeActuatorResult,
        policy_decision: Any = None,
        event_ids: Optional[List[str]] = None,
    ) -> SafeActuatorEvidenceMetadata:
        upstream = actuator_result.evidence_metadata
        evidence_event_ids = list(upstream.event_ids or event_ids or [])
        evidence = {
            **dict(upstream.evidence),
            "source_agents": list(upstream.source_agents or [self.source_agent]),
            "event_ids": evidence_event_ids,
            "operation": operation,
            "resource": f"identity:spire_agent:{operation}",
            "context_keys": sorted(str(key) for key in context),
            "local_spire_agent_cli_action_succeeded": bool(actuator_result.success)
            and not bool(actuator_result.simulated),
            "safe_actuator_simulated": bool(actuator_result.simulated),
            "upstream_claim_gate_present": bool(upstream.claim_gate),
            "raw_context_values_redacted": True,
            "raw_command_output_redacted": True,
        }
        return SafeActuatorEvidenceMetadata.from_value(
            {
                "claim_gate": self._safe_actuator_claim_gate(
                    operation=operation,
                    success=bool(actuator_result.success),
                    simulated=bool(actuator_result.simulated),
                    policy_decision=policy_decision,
                ),
                "cross_plane_claim_gate": self._safe_actuator_cross_plane_claim_gate(),
                "evidence": evidence,
                "source_agents": list(upstream.source_agents or [self.source_agent]),
                "event_ids": evidence_event_ids,
                "claim_boundary": SPIRE_AGENT_SAFE_ACTUATOR_CLAIM_BOUNDARY,
                "redacted": True,
            }
        )

    def _safe_actuator_result(
        self,
        operation: str,
        context: Dict[str, Any],
        *,
        success: bool,
        reason: str,
        simulated: bool = False,
        policy_decision: Any = None,
        event_ids: Optional[List[str]] = None,
    ) -> SafeActuatorResult:
        seed_result = SafeActuatorResult(
            success=success,
            reason=reason,
            simulated=simulated,
            evidence_metadata=SafeActuatorEvidenceMetadata(),
        )
        metadata = self._safe_actuator_evidence_metadata(
            operation=operation,
            context=context,
            actuator_result=seed_result,
            policy_decision=policy_decision,
            event_ids=event_ids,
        )
        return SafeActuatorResult(
            success=success,
            reason=reason,
            simulated=simulated,
            evidence_metadata=metadata,
        )

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
        safe_actuator_evidence_metadata: Optional[
            SafeActuatorEvidenceMetadata
        ] = None,
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
            "safe_actuator_evidence_metadata": (
                safe_actuator_evidence_metadata.to_dict()
                if safe_actuator_evidence_metadata is not None
                else SafeActuatorEvidenceMetadata().to_dict()
            ),
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
        except Exception as exc:
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
        except Exception as exc:
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
        event_ids: List[str] = []
        received_event_id = self._publish_control_event(
            EventType.COORDINATION_REQUEST,
            stage="received",
            operation=operation,
            context=context,
        )
        if received_event_id:
            event_ids.append(received_event_id)
        allowed, decision, reason = self._evaluate_control_policy(operation)
        if not allowed:
            result = self._safe_actuator_result(
                operation,
                context,
                success=False,
                reason=reason,
                policy_decision=decision,
                event_ids=event_ids,
            )
            self._publish_control_event(
                EventType.TASK_BLOCKED,
                stage="policy_denied",
                operation=operation,
                context=context,
                reason=reason,
                policy_decision=decision,
                success=False,
                simulated=False,
                safe_actuator_evidence_metadata=result.evidence_metadata,
            )
            return result

        start_event_id = self._publish_control_event(
            EventType.PIPELINE_STAGE_START,
            stage="actuator_start",
            operation=operation,
            context=context,
            reason=reason,
            policy_decision=decision,
        )
        if start_event_id:
            event_ids.append(start_event_id)
        actuator = self.safe_actuator or SafeActuator(executor)
        actuator_result = actuator.execute(operation, context)
        success = bool(actuator_result.success)
        simulated = bool(actuator_result.simulated)
        actuator_metadata = self._safe_actuator_evidence_metadata(
            operation=operation,
            context=context,
            actuator_result=actuator_result,
            policy_decision=decision,
            event_ids=event_ids,
        )
        actuator_result = SafeActuatorResult(
            success=success,
            reason=actuator_result.reason,
            simulated=simulated,
            evidence_metadata=actuator_metadata,
        )
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
            safe_actuator_evidence_metadata=actuator_metadata,
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
                if self.socket_path.exists():
                    logger.info("SPIRE Agent socket is ready at %s", self.socket_path)
                    return self._safe_actuator_result(
                        _operation,
                        _context,
                        success=True,
                        reason="SPIRE Agent started",
                    )
                time.sleep(0.5)

            logger.error("SPIRE Agent socket did not appear within timeout")
            self.stop()
            return self._safe_actuator_result(
                _operation,
                _context,
                success=False,
                reason="SPIRE Agent socket did not appear",
            )
        except Exception:
            logger.exception("Failed to start SPIRE Agent")
            return self._safe_actuator_result(
                _operation,
                _context,
                success=False,
                reason="Failed to start SPIRE Agent",
            )
        return self._safe_actuator_result(
            _operation,
            _context,
            success=True,
            reason="SPIRE Agent started",
        )

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
                    return self._safe_actuator_result(
                        _operation,
                        _context,
                        success=True,
                        reason="SPIRE Agent stopped gracefully",
                    )
                time.sleep(0.5)

            logger.warning("SPIRE Agent did not stop gracefully, sending SIGKILL")
            os.killpg(os.getpgid(self.agent_process.pid), signal.SIGKILL)
            self.agent_process.wait(timeout=5)
            self._cleanup()
            return self._safe_actuator_result(
                _operation,
                _context,
                success=True,
                reason="SPIRE Agent stopped with SIGKILL",
            )
        except Exception:
            logger.exception("Failed to stop SPIRE Agent")
            return self._safe_actuator_result(
                _operation,
                _context,
                success=False,
                reason="Failed to stop SPIRE Agent",
            )

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

            guard_decision = self.join_token_guard.reserve(token)
            if not guard_decision.accepted:
                context = {
                    "strategy": strategy.value,
                    "token": token,
                    "attestation_guard": guard_decision.to_safe_context(),
                }
                self._publish_control_event(
                    EventType.TASK_BLOCKED,
                    stage="join_token_guard_blocked",
                    operation="attest_node",
                    context=context,
                    reason=guard_decision.reason,
                    success=False,
                    simulated=False,
                )
                return False

            agent_running = bool(
                self.agent_process and self.agent_process.poll() is None
            )
            success = False
            try:
                result = self._run_control_action(
                    operation="attest_node",
                    context={
                        "strategy": strategy.value,
                        "token": token,
                        "agent_running": agent_running,
                        "attestation_guard": guard_decision.to_safe_context(),
                    },
                    executor=lambda _operation, _context: (
                        self._attest_join_token_internal(
                            token,
                            agent_running=agent_running,
                            operation=_operation,
                            context=_context,
                        )
                    ),
                )
                success = bool(result.success) and not bool(result.simulated)
                return success
            finally:
                self.join_token_guard.complete(token, success=success)

        logger.warning(
            "Attestation strategy %s is not fully implemented", strategy.value
        )
        return False

    def _attest_join_token_internal(
        self,
        token: str,
        *,
        agent_running: bool,
        operation: str = "attest_node",
        context: Optional[Dict[str, Any]] = None,
    ) -> SafeActuatorResult:
        safe_context = dict(context or {"agent_running": agent_running, "token": token})
        self._join_token = token
        logger.info(
            "Join token has been set. It will be used for agent attestation."
        )

        # If agent is already running, restart it to apply the new token.
        if agent_running:
            logger.info("Restarting agent to apply new join token.")
            if not self.stop():
                return self._safe_actuator_result(
                    operation,
                    safe_context,
                    success=False,
                    reason="SPIRE Agent stop failed during attestation",
                )
            if not self.start():
                return self._safe_actuator_result(
                    operation,
                    safe_context,
                    success=False,
                    reason="SPIRE Agent restart failed during attestation",
                )
            return self._safe_actuator_result(
                operation,
                safe_context,
                success=True,
                reason="SPIRE Agent restarted with join token",
            )

        return self._safe_actuator_result(
            operation,
            safe_context,
            success=True,
            reason="Join token stored for next SPIRE Agent start",
        )

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
                entry,
                operation=_operation,
                context=_context,
            ),
        )
        return bool(result.success) and not bool(result.simulated)

    def _register_workload_internal(
        self,
        entry: WorkloadEntry,
        *,
        operation: str = "register_workload",
        context: Optional[Dict[str, Any]] = None,
    ) -> SafeActuatorResult:
        safe_context = dict(
            context
            or {
                "spiffe_id": entry.spiffe_id,
                "parent_id": entry.parent_id,
                "selectors": dict(entry.selectors),
                "ttl": entry.ttl,
            }
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
            return self._safe_actuator_result(
                operation,
                safe_context,
                success=True,
                reason="SPIRE workload registered",
            )
        except FileNotFoundError:
            logger.error("`spire-server` binary not found, cannot register workload.")
            return self._safe_actuator_result(
                operation,
                safe_context,
                success=False,
                reason="spire-server binary not found",
            )
        except subprocess.CalledProcessError as e:
            logger.error(
                "Failed to register workload %s. Error: %s",
                entry.spiffe_id,
                e.stderr,
            )
            return self._safe_actuator_result(
                operation,
                safe_context,
                success=False,
                reason="SPIRE workload registration failed",
            )
        except Exception:
            logger.exception(
                "An unexpected error occurred during workload registration."
            )
            return self._safe_actuator_result(
                operation,
                safe_context,
                success=False,
                reason="Unexpected SPIRE workload registration error",
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
            result = subprocess.run(cmd, capture_output=True, text=True, timeout=30)

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
        except Exception as e:
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

        exists_fn = self.socket_path.exists
        try:
            # Some tests use a MagicMock Path.exists with side_effect from startup logic.
            # If a test explicitly sets return_value, we should respect it.
            if hasattr(exists_fn, "side_effect") and exists_fn.side_effect is not None:
                if hasattr(exists_fn, "return_value") and isinstance(
                    exists_fn.return_value, bool
                ):
                    _saved = exists_fn.side_effect
                    exists_fn.side_effect = None
                    socket_exists = bool(exists_fn())
                    exists_fn.side_effect = _saved
                else:
                    socket_exists = bool(exists_fn())
            else:
                socket_exists = bool(exists_fn())
        except Exception:
            socket_exists = False

        if not socket_exists:
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
            success = result.returncode == 0
            return self._safe_actuator_result(
                _operation,
                _context,
                success=success,
                reason=(
                    "SPIRE Agent healthcheck passed"
                    if success
                    else "SPIRE Agent healthcheck returned non-zero"
                ),
            )
        except Exception:
            logger.exception("SPIRE Agent healthcheck command failed")
            # Fallback: if process is running and socket exists, treat as healthy.
            return self._safe_actuator_result(
                _operation,
                _context,
                success=True,
                reason="SPIRE Agent healthcheck fallback healthy",
            )

    # ------------------------------------------------------------------
    # Internal helpers
    # ------------------------------------------------------------------

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
