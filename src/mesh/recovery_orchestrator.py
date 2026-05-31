"""Closed-loop orchestrator for bounded mesh node recovery."""

from __future__ import annotations

import time
import uuid
from typing import Callable

from src.mesh.recovery_contracts import (
    BoundedClaims,
    NodeState,
    RecoveryEvidenceV1,
    generate_node_id_hash,
)
from src.mesh.recovery_policy import RecoveryPolicyManager


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
        post_action_wait_seconds: float = 15.0,
        sleeper: Callable[[float], None] | None = None,
        clock: Callable[[], float] | None = None,
    ) -> None:
        self.node_id = node_id
        self.local_audit_secret = local_audit_secret
        self.policy_manager = policy_manager
        self.restart_action = restart_action
        self.get_node_state = get_node_state
        self.post_action_wait_seconds = post_action_wait_seconds
        self._sleeper = sleeper or time.sleep
        self._clock = clock or time.monotonic

    def run_recovery_flow(
        self,
        *,
        incident_id: str,
        incident_key: str,
    ) -> RecoveryEvidenceV1:
        if not incident_id:
            raise ValueError("incident_id cannot be empty")

        started = self._clock()
        before_state = self.get_node_state()
        policy_result = self.policy_manager.check_policy(incident_key)
        policy_decision = policy_result.to_decision()
        node_id_hash = generate_node_id_hash(self.node_id, self.local_audit_secret)

        if not policy_result.allowed:
            return RecoveryEvidenceV1(
                event_id=self._new_event_id(),
                incident_id=incident_id,
                node_id_hash=node_id_hash,
                action="block_and_escalate",
                policy_decision=policy_decision,
                before=before_state,
                after=before_state,
                claim_gate=self._unproven_claims(),
                duration_ms=self._duration_ms(started),
                return_code=1,
                escalation_required=True,
            )

        self.policy_manager.record_action(incident_key)
        return_code = int(self.restart_action())
        self._sleeper(self.post_action_wait_seconds)
        after_state = self.get_node_state()
        claim_gate = self._build_claims(before_state, after_state)
        escalation_required = (
            return_code != 0
            or claim_gate.local_peer_visible != "PROVEN"
            or claim_gate.packet_loss_metric_decreased != "PROVEN"
        )

        return RecoveryEvidenceV1(
            event_id=self._new_event_id(),
            incident_id=incident_id,
            node_id_hash=node_id_hash,
            action="restart_local_mesh_agent",
            policy_decision=policy_decision,
            before=before_state,
            after=after_state,
            claim_gate=claim_gate,
            duration_ms=self._duration_ms(started),
            return_code=return_code,
            escalation_required=escalation_required,
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
        local_peer_ok = after_state.yggdrasil_status == "Peers visible"
        yggdrasil_improved = (
            before_state.yggdrasil_status != after_state.yggdrasil_status
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
