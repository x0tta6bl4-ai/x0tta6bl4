"""Closed-loop orchestrator for bounded mesh node recovery."""

from __future__ import annotations

import logging
import time
import uuid
from typing import Any, Callable, Mapping

from src.core.thinking.agent_thinking import AgentThinkingCoach
from src.coordination.events import EventBus, EventType
from src.mesh.recovery_contracts import (
    BoundedClaims,
    DataplaneEvidenceRef,
    NodeState,
    PostActionDataplaneClaimGate,
    PostActionDataplaneRevalidation,
    RecoveryEvidenceV1,
    ServiceIdentityEvidence,
    build_dataplane_evidence_ref,
    build_post_action_dataplane_claim_gate,
    generate_node_id_hash,
)
from src.mesh.recovery_policy import RecoveryPolicyManager
from src.services.service_event_identity import service_event_identity


logger = logging.getLogger(__name__)

MESH_RECOVERY_SOURCE_AGENT = "mesh-recovery-orchestrator"
MESH_RECOVERY_LAYER = "mesh_recovery_control_spine"
MESH_RECOVERY_EVENTBUS_SCHEMA = "mesh_node_degradation_recovery.eventbus.v1"
MESH_RECOVERY_CLAIM_BOUNDARY = (
    "Local mesh recovery evidence only. A restart plus local revalidation can "
    "prove bounded node-state changes, but it does not prove customer traffic, "
    "remote peer authenticity, external dataplane delivery, or production readiness."
)
MESH_RECOVERY_DATAPLANE_CLAIM_BOUNDARY = (
    "Post-action dataplane proof metadata only. Local recovery is not treated "
    "as restored dataplane unless a bounded, redacted dataplane proof event is "
    "attached. Customer traffic still requires a separate end-to-end proof."
)


def _identity_metadata() -> ServiceIdentityEvidence:
    identity = service_event_identity(service_name=MESH_RECOVERY_SOURCE_AGENT)
    return ServiceIdentityEvidence(
        service_name=MESH_RECOVERY_SOURCE_AGENT,
        spiffe_id_configured=bool(identity.get("spiffe_id")),
        did_configured=bool(identity.get("did")),
        wallet_address_configured=bool(identity.get("wallet_address")),
    )


class MeshRecoveryOrchestrator:
    """Run observe -> policy -> action -> revalidate -> evidence."""

    def __init__(
        self,
        *,
        node_id: str,
        local_audit_secret: str,
        policy_manager: RecoveryPolicyManager,
        restart_action: Callable[[], int],
        get_node_state: Callable[[], NodeState],
        dataplane_probe: Callable[[], Mapping[str, Any]] | None = None,
        event_bus: EventBus | None = None,
        source_agent: str = MESH_RECOVERY_SOURCE_AGENT,
        post_action_wait_seconds: float = 15.0,
        sleeper: Callable[[float], None] | None = None,
        clock: Callable[[], float] | None = None,
    ) -> None:
        self.node_id = node_id
        self.local_audit_secret = local_audit_secret
        self.policy_manager = policy_manager
        self.restart_action = restart_action
        self.get_node_state = get_node_state
        self.dataplane_probe = dataplane_probe
        self.event_bus = event_bus
        self.source_agent = source_agent
        self.post_action_wait_seconds = post_action_wait_seconds
        self._sleeper = sleeper or time.sleep
        self._clock = clock or time.monotonic
        self.thinking_coach = AgentThinkingCoach(
            agent_id=source_agent,
            role="healing",
            capabilities=("ops", "zero-trust"),
            extra_techniques=("mape_k", "chaos_driven_design"),
        )
        self.last_thinking_context: dict[str, Any] = {}

    def run_recovery_flow(
        self,
        *,
        incident_id: str,
        incident_key: str,
    ) -> RecoveryEvidenceV1:
        if not incident_id:
            raise ValueError("incident_id cannot be empty")

        started = self._clock()
        self.last_thinking_context = self.thinking_coach.prepare_task(
            {
                "task_type": "mesh_node_recovery_flow",
                "goal": "Run bounded observe-policy-action-revalidate recovery for a mesh node.",
                "incident_id_present": True,
                "incident_key_present": bool(incident_key),
                "constraints": {
                    "source_agent": self.source_agent,
                    "post_action_wait_seconds": self.post_action_wait_seconds,
                    "dataplane_probe_configured": self.dataplane_probe is not None,
                    "do_not_expose_raw_node_id": True,
                },
            }
        )
        before_state = self.get_node_state()
        policy_result = self.policy_manager.check_policy(incident_key)
        policy_decision = policy_result.to_decision()
        node_id_hash = generate_node_id_hash(self.node_id, self.local_audit_secret)
        service_identity = _identity_metadata()

        if not policy_result.allowed:
            evidence = RecoveryEvidenceV1(
                event_id=self._new_event_id(),
                incident_id=incident_id,
                node_id_hash=node_id_hash,
                service_identity=service_identity,
                action="block_and_escalate",
                policy_decision=policy_decision,
                before=before_state,
                after=before_state,
                claim_gate=self._unproven_claims(),
                post_action_dataplane_revalidation=self._dataplane_not_attempted(
                    reason="recovery_action_not_allowed"
                ),
                duration_ms=self._duration_ms(started),
                return_code=1,
                escalation_required=True,
            )
            self._publish_recovery_event(evidence)
            return evidence

        self.policy_manager.record_action(incident_key)
        action_error = False
        action_error_type: str | None = None
        try:
            return_code = int(self.restart_action())
        except Exception as exc:
            action_error = True
            action_error_type = type(exc).__name__
            return_code = 1
            logger.error(
                "Mesh recovery restart action failed: %s",
                action_error_type,
            )
        self._sleeper(self.post_action_wait_seconds)
        after_state = self.get_node_state()
        claim_gate = self._build_claims(before_state, after_state)
        local_revalidation_passed = (
            return_code == 0
            and after_state.local_health == "OK"
            and claim_gate.local_peer_visible == "PROVEN"
            and claim_gate.packet_loss_metric_decreased == "PROVEN"
        )
        post_action_dataplane_revalidation = self._dataplane_revalidation(
            local_revalidation_passed=local_revalidation_passed
        )
        dataplane_probe_failed = (
            post_action_dataplane_revalidation.probe_attempted
            and not post_action_dataplane_revalidation.restored_dataplane_claim_allowed
        )
        post_action_safe_mode_required = (
            return_code != 0
            or after_state.local_health != "OK"
            or claim_gate.local_peer_visible != "PROVEN"
            or claim_gate.packet_loss_metric_decreased != "PROVEN"
        )
        escalation_required = (
            post_action_safe_mode_required
            or dataplane_probe_failed
        )

        evidence = RecoveryEvidenceV1(
            event_id=self._new_event_id(),
            incident_id=incident_id,
            node_id_hash=node_id_hash,
            service_identity=service_identity,
            action="restart_local_mesh_agent",
            policy_decision=policy_decision,
            before=before_state,
            after=after_state,
            claim_gate=claim_gate,
            post_action_dataplane_revalidation=post_action_dataplane_revalidation,
            duration_ms=self._duration_ms(started),
            return_code=return_code,
            action_error=action_error,
            action_error_type=action_error_type,
            action_error_redacted=True,
            escalation_required=escalation_required,
            post_action_safe_mode_required=post_action_safe_mode_required,
        )
        self._publish_recovery_event(evidence)
        return evidence

    def _publish_recovery_event(self, evidence: RecoveryEvidenceV1) -> str | None:
        if self.event_bus is None:
            return None

        event_type = (
            EventType.TASK_BLOCKED
            if evidence.escalation_required
            else EventType.PIPELINE_STAGE_END
        )
        payload = self._event_payload(evidence)
        try:
            event = self.event_bus.publish(
                event_type,
                self.source_agent,
                payload,
                priority=7 if evidence.escalation_required else 5,
            )
            return event.event_id
        except Exception as exc:
            logger.error("Failed to publish mesh recovery evidence event: %s", exc)
            return None

    def _event_payload(self, evidence: RecoveryEvidenceV1) -> dict[str, object]:
        stage = "recovery_revalidated"
        status = "success"
        if evidence.action == "block_and_escalate":
            stage = "recovery_blocked"
            status = "blocked"
        elif evidence.escalation_required:
            stage = "recovery_escalated"
            status = "failed"

        policy = evidence.policy_decision
        service_identity = evidence.service_identity
        service_identity_payload = service_identity.model_dump(mode="json")
        return {
            "schema": MESH_RECOVERY_EVENTBUS_SCHEMA,
            "recovery_evidence_schema": evidence.schema,
            "component": "src.mesh.recovery_orchestrator",
            "operation": "mesh_node_degradation_recovery",
            "service_name": MESH_RECOVERY_SOURCE_AGENT,
            "source_alias": self.source_agent,
            "layer": MESH_RECOVERY_LAYER,
            "stage": stage,
            "status": status,
            "success": status == "success",
            "duration_ms": evidence.duration_ms,
            "return_code": evidence.return_code,
            "returncode": evidence.return_code,
            "action_error": evidence.action_error,
            "action_error_type": evidence.action_error_type,
            "action_error_redacted": evidence.action_error_redacted,
            "recovery_event_id": evidence.event_id,
            "incident_id": evidence.incident_id,
            "incident_key_redacted": True,
            "action": evidence.action,
            "policy_allowed": policy.allowed,
            "cooldown_active": policy.cooldown_active,
            "safe_mode_required": (
                policy.safe_mode_required
                or evidence.post_action_safe_mode_required
            ),
            "policy_safe_mode_required": policy.safe_mode_required,
            "post_action_safe_mode_required": (
                evidence.post_action_safe_mode_required
            ),
            "execution_limit_checked": policy.execution_limit_checked,
            "escalation_required": evidence.escalation_required,
            "node_id_hash": evidence.node_id_hash,
            "identity": {"node_id_hash": evidence.node_id_hash},
            "identity_fields_present": {
                "node_id_hash": bool(evidence.node_id_hash),
                "spiffe_id": service_identity.spiffe_id_configured,
                "did": service_identity.did_configured,
                "wallet_address": service_identity.wallet_address_configured,
            },
            "service_identity": service_identity_payload,
            "observed_state": True,
            "before": evidence.before.model_dump(mode="json"),
            "after": evidence.after.model_dump(mode="json"),
            "claim_gate": evidence.claim_gate.model_dump(mode="json"),
            "post_action_dataplane_revalidation": (
                evidence.post_action_dataplane_revalidation.model_dump(mode="json")
                if evidence.post_action_dataplane_revalidation is not None
                else None
            ),
            "post_action_dataplane_revalidated": (
                evidence.post_action_dataplane_revalidation.post_action_dataplane_revalidated
                if evidence.post_action_dataplane_revalidation is not None
                else False
            ),
            "dataplane_confirmed": (
                evidence.post_action_dataplane_revalidation.dataplane_confirmed
                if evidence.post_action_dataplane_revalidation is not None
                else False
            ),
            "customer_traffic_restored": (
                evidence.claim_gate.customer_traffic_restored
            ),
            "raw_values_redacted": evidence.raw_values_redacted,
            "raw_identifiers_redacted": True,
            "payloads_redacted": True,
            "claim_boundary": MESH_RECOVERY_CLAIM_BOUNDARY,
            "thinking": self.thinking_coach.status(),
            "last_thinking_context": self.last_thinking_context,
        }

    def _dataplane_revalidation(
        self,
        *,
        local_revalidation_passed: bool,
    ) -> PostActionDataplaneRevalidation:
        if self.dataplane_probe is None:
            return self._dataplane_not_attempted(
                reason="no_post_action_dataplane_probe_configured"
            )
        if not local_revalidation_passed:
            return self._dataplane_not_attempted(reason="local_revalidation_failed")

        try:
            raw_result = dict(self.dataplane_probe())
        except Exception as exc:
            logger.error("Failed to run mesh recovery dataplane probe: %s", exc)
            raw_result = {
                "status": "error",
                "dataplane_confirmed": False,
                "evidence": {},
            }

        evidence = self._dataplane_evidence_ref(raw_result.get("evidence"))
        dataplane_confirmed = bool(raw_result.get("dataplane_confirmed"))
        gate = self._dataplane_claim_gate(
            probe_attempted=True,
            dataplane_confirmed=dataplane_confirmed,
            evidence=evidence,
        )
        status = "success" if gate.restored_dataplane_claim_allowed else "failed"
        reason = (
            "bounded_dataplane_probe_succeeded"
            if gate.restored_dataplane_claim_allowed
            else "bounded_dataplane_probe_failed"
        )
        return PostActionDataplaneRevalidation(
            status=status,
            reason=reason,
            probe_attempted=True,
            post_action_dataplane_revalidated=(
                gate.post_action_dataplane_revalidated
            ),
            dataplane_confirmed=dataplane_confirmed,
            restored_dataplane_claim_allowed=gate.restored_dataplane_claim_allowed,
            claim_gate=gate,
            evidence=evidence,
            claim_boundary=MESH_RECOVERY_DATAPLANE_CLAIM_BOUNDARY,
        )

    def _dataplane_not_attempted(
        self,
        *,
        reason: str,
    ) -> PostActionDataplaneRevalidation:
        evidence = self._dataplane_evidence_ref({})
        gate = self._dataplane_claim_gate(
            probe_attempted=False,
            dataplane_confirmed=False,
            evidence=evidence,
        )
        return PostActionDataplaneRevalidation(
            status="not_attempted",
            reason=reason,
            probe_attempted=False,
            post_action_dataplane_revalidated=False,
            dataplane_confirmed=False,
            restored_dataplane_claim_allowed=False,
            claim_gate=gate,
            evidence=evidence,
            claim_boundary=MESH_RECOVERY_DATAPLANE_CLAIM_BOUNDARY,
        )

    @staticmethod
    def _safe_nonnegative_int(value: Any, default: int = 0) -> int:
        try:
            return max(0, int(value))
        except (TypeError, ValueError):
            return default

    @classmethod
    def _dataplane_evidence_ref(cls, value: Any) -> DataplaneEvidenceRef:
        return build_dataplane_evidence_ref(value)

    @staticmethod
    def _dataplane_claim_gate(
        *,
        probe_attempted: bool,
        dataplane_confirmed: bool,
        evidence: DataplaneEvidenceRef,
    ) -> PostActionDataplaneClaimGate:
        return build_post_action_dataplane_claim_gate(
            probe_required=True,
            probe_enabled=True,
            probe_target_present=True,
            probe_attempted=probe_attempted,
            dataplane_confirmed=dataplane_confirmed,
            evidence=evidence,
            claim_boundary=MESH_RECOVERY_DATAPLANE_CLAIM_BOUNDARY,
        )

    @staticmethod
    def _new_event_id() -> str:
        return f"evt-{uuid.uuid4()}"

    def _duration_ms(self, started: float) -> int:
        return max(0, int((self._clock() - started) * 1000))

    @staticmethod
    def _unproven_claims() -> BoundedClaims:
        return BoundedClaims(
            local_peer_visible="UNPROVEN",
            yggdrasil_status_improved="UNPROVEN",
            packet_loss_metric_decreased="UNPROVEN",
            customer_traffic_restored="UNPROVEN_AWAITING_DATAPLANE_PROOF",
        )

    @staticmethod
    def _build_claims(before_state: NodeState, after_state: NodeState) -> BoundedClaims:
        health_ok = after_state.local_health == "OK"
        local_peer_ok = after_state.yggdrasil_status == "Peers visible"
        yggdrasil_improved = (
            health_ok
            and before_state.yggdrasil_status != after_state.yggdrasil_status
            and local_peer_ok
        )
        packet_loss_decreased = (
            after_state.packet_loss_pct < before_state.packet_loss_pct
            and after_state.packet_loss_pct < 1.0
        )

        return BoundedClaims(
            local_peer_visible="PROVEN" if local_peer_ok else "UNPROVEN",
            yggdrasil_status_improved=(
                "PROVEN" if yggdrasil_improved else "UNPROVEN"
            ),
            packet_loss_metric_decreased=(
                "PROVEN" if packet_loss_decreased else "UNPROVEN"
            ),
            customer_traffic_restored="UNPROVEN_AWAITING_DATAPLANE_PROOF",
        )
