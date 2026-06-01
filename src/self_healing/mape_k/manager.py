"""
MAPE-K Self-Healing Core for x0tta6bl4
Implements Monitor, Analyze, Plan, Execute, Knowledge loop
"""

import logging
import time
from datetime import datetime
from typing import Any, Dict, List, Optional

from src.coordination.events import EventBus, EventType, get_event_bus
from src.integration.spine import SafeActuator, SafeActuatorEvidenceMetadata
from src.services.service_event_identity import service_event_identity

from .monitor import MAPEKMonitor
from .analyzer import MAPEKAnalyzer
from .planner import MAPEKPlanner
from .executor import MAPEKExecutor
from .knowledge import MAPEKKnowledge
from .utils import (
    _sha256_text,
    _safe_numeric_summary,
    _safe_metric_keys,
    _safe_issue_summary,
    _safe_action_summary,
    _safe_monitor_result,
    _safe_downstream_evidence,
)

logger = logging.getLogger(__name__)

_SERVICE_AGENT = "self-healing-mapek"
_SERVICE_LAYER = "self_healing_mapek_control_spine"
_RECOVERY_EXECUTOR_AGENT = "recovery-action-executor"
_DOWNSTREAM_EVENT_ID_LIMIT = 10
_DEFAULT_REMEDIATION_COOLDOWN_SECONDS = 600.0
_MAPEK_RESOURCES = {
    "monitor": "self_healing:mapek:monitor",
    "execute": "self_healing:mapek:execute",
    "verify": "self_healing:mapek:verify",
}
SELF_HEALING_MAPEK_CLAIM_BOUNDARY = (
    "Self-healing MAPE-K control-spine event only. It records local monitor and "
    "execute decisions, service identity presence, safe-actuator state, bounded "
    "numeric summaries, action/issue hashes, and redacted outcome metadata. It "
    "does not expose raw node IDs, logs, service IDs, scripts, recovery payloads, "
    "or prove that a remote recovery changed live network state."
)
SELF_HEALING_MAPEK_SAFE_ACTUATOR_CLAIM_BOUNDARY = (
    "Self-healing MAPE-K SafeActuator metadata is local control-action evidence. "
    "It may reference redacted downstream recovery EventBus evidence, but it does "
    "not prove customer traffic delivery, external reachability, production SLOs, "
    "or production readiness."
)
SELF_HEALING_MAPEK_VERIFICATION_CLAIM_BOUNDARY = (
    "Self-healing MAPE-K verification evidence is local post-action observed "
    "state only. It can prove that the next local heartbeat is healthy or back "
    "under the local anomaly threshold; it does not prove customer traffic, "
    "external reachability, production SLOs, or production readiness."
)


def _identity_metadata() -> Dict[str, Any]:
    identity = service_event_identity(service_name=_SERVICE_AGENT)
    return {
        "service_name": _SERVICE_AGENT,
        "spiffe_id_configured": bool(identity.get("spiffe_id")),
        "did_configured": bool(identity.get("did")),
        "wallet_address_configured": bool(identity.get("wallet_address")),
        "redacted": True,
    }


def _event_bus_or_none(
    event_bus: Optional[EventBus],
    event_project_root: str,
) -> Optional[EventBus]:
    if event_bus is not None:
        return event_bus
    try:
        return get_event_bus(event_project_root)
    except Exception as exc:
        logger.error("Failed to initialize self-healing MAPE-K EventBus: %s", exc)
        return None


def _event_ids_for_agent(
    event_bus: Optional[EventBus],
    source_agent: str,
) -> List[str]:
    if event_bus is None:
        return []
    try:
        events = event_bus.get_event_history(
            source_agent=source_agent,
            limit=EventBus.MAX_EVENT_HISTORY,
        )
    except Exception as exc:
        logger.error("Failed to read downstream EventBus history: %s", exc)
        return []
    return [str(event.event_id) for event in events]


def _new_event_ids_for_agent(
    event_bus: Optional[EventBus],
    source_agent: str,
    before_ids: List[str],
) -> List[str]:
    before = set(before_ids)
    return [
        event_id
        for event_id in _event_ids_for_agent(event_bus, source_agent)
        if event_id not in before
    ]


def _event_payloads_for_ids(
    event_bus: Optional[EventBus],
    *,
    source_agent: str,
    event_ids: List[str],
) -> List[Dict[str, Any]]:
    if event_bus is None or not event_ids:
        return []
    wanted = set(str(event_id) for event_id in event_ids if event_id)
    try:
        events = event_bus.get_event_history(
            source_agent=source_agent,
            limit=EventBus.MAX_EVENT_HISTORY,
        )
    except Exception as exc:
        logger.error("Failed to read downstream EventBus payloads: %s", exc)
        return []

    payloads: List[Dict[str, Any]] = []
    for event in events:
        if event.event_id not in wanted or not isinstance(event.data, dict):
            continue
        payloads.append(dict(event.data))
    return payloads


def _latest_downstream_claim_gate(payloads: List[Dict[str, Any]]) -> Dict[str, Any]:
    for payload in reversed(payloads):
        claim_gate = payload.get("claim_gate")
        if isinstance(claim_gate, dict):
            return dict(claim_gate)
    return {}


def _self_healing_safe_actuator_claim_gate(
    *,
    success: bool,
    simulated: bool,
    downstream_evidence: Dict[str, Any],
    downstream_claim_gate: Dict[str, Any],
) -> Dict[str, Any]:
    downstream_events_total = int(downstream_evidence.get("events_total") or 0)
    downstream_restored_dataplane = bool(
        downstream_claim_gate.get("restored_dataplane_claim_allowed")
    )
    downstream_dataplane_confirmed = bool(
        downstream_claim_gate.get("dataplane_confirmed")
    )
    local_action_allowed = bool(success and not simulated)

    blockers: List[str] = []
    if not success:
        blockers.append("safe_actuator_result_not_successful")
    if simulated:
        blockers.append("safe_actuator_result_simulated")
    if downstream_events_total <= 0:
        blockers.append("downstream_recovery_evidence_missing")
    if not downstream_claim_gate:
        blockers.append("downstream_recovery_claim_gate_missing")
    if downstream_restored_dataplane and not downstream_dataplane_confirmed:
        blockers.append("downstream_dataplane_confirmation_missing")

    restored_dataplane_allowed = bool(
        local_action_allowed
        and downstream_restored_dataplane
        and downstream_dataplane_confirmed
    )

    return {
        "schema": "x0tta6bl4.self_healing_mapek.safe_actuator_claim_gate.v1",
        "surface": "self_healing.mapek.execute",
        "local_control_action_claim_allowed": local_action_allowed,
        "safe_actuator_result_recorded": True,
        "safe_actuator_result_successful": bool(success),
        "safe_actuator_result_simulated": bool(simulated),
        "downstream_recovery_evidence_present": downstream_events_total > 0,
        "downstream_recovery_claim_gate_present": bool(downstream_claim_gate),
        "dataplane_confirmed": downstream_dataplane_confirmed,
        "post_action_dataplane_revalidated": bool(
            downstream_claim_gate.get("post_action_dataplane_revalidated")
        ),
        "restored_dataplane_claim_allowed": restored_dataplane_allowed,
        "traffic_delivery_claim_allowed": False,
        "customer_traffic_claim_allowed": False,
        "external_reachability_claim_allowed": False,
        "production_slo_claim_allowed": False,
        "production_readiness_claim_allowed": False,
        "blockers": blockers,
        "downstream_claim_gate_summary": {
            "schema": str(downstream_claim_gate.get("schema") or ""),
            "restored_dataplane_claim_allowed": downstream_restored_dataplane,
            "dataplane_confirmed": downstream_dataplane_confirmed,
            "production_readiness_claim_allowed": bool(
                downstream_claim_gate.get("production_readiness_claim_allowed")
            ),
            "values_redacted": True,
        },
        "claim_boundary": SELF_HEALING_MAPEK_SAFE_ACTUATOR_CLAIM_BOUNDARY,
        "redacted": True,
    }


def _safe_actuator_evidence_metadata(
    *,
    event_bus: Optional[EventBus],
    success: bool,
    simulated: bool,
    downstream_event_ids: List[str],
) -> SafeActuatorEvidenceMetadata:
    downstream_evidence = _safe_downstream_evidence(
        downstream_event_ids,
        limit=_DOWNSTREAM_EVENT_ID_LIMIT,
    )
    downstream_payloads = _event_payloads_for_ids(
        event_bus,
        source_agent=_RECOVERY_EXECUTOR_AGENT,
        event_ids=downstream_event_ids,
    )
    downstream_claim_gate = _latest_downstream_claim_gate(downstream_payloads)
    claim_gate = _self_healing_safe_actuator_claim_gate(
        success=success,
        simulated=simulated,
        downstream_evidence=downstream_evidence,
        downstream_claim_gate=downstream_claim_gate,
    )
    return SafeActuatorEvidenceMetadata(
        claim_gate=claim_gate,
        evidence=downstream_evidence,
        source_agents=downstream_evidence.get("source_agents", []),
        event_ids=downstream_evidence.get("event_ids", []),
        claim_boundary=SELF_HEALING_MAPEK_SAFE_ACTUATOR_CLAIM_BOUNDARY,
        redacted=True,
    )


def _verification_claim_gate(
    *,
    success: bool,
    is_healthy: bool,
    metric_recovered: bool,
) -> Dict[str, Any]:
    blockers: List[str] = []
    if not success:
        blockers.append("post_action_local_state_not_recovered")
    if not is_healthy and not metric_recovered:
        blockers.append("post_action_metrics_still_anomalous")
    return {
        "schema": "x0tta6bl4.self_healing_mapek.verification_claim_gate.v1",
        "surface": "self_healing.mapek.verify",
        "local_healing_verification_claim_allowed": bool(success),
        "local_state_healthy": bool(is_healthy),
        "local_metric_recovered": bool(metric_recovered),
        "restored_dataplane_claim_allowed": False,
        "traffic_delivery_claim_allowed": False,
        "customer_traffic_claim_allowed": False,
        "external_reachability_claim_allowed": False,
        "production_slo_claim_allowed": False,
        "production_readiness_claim_allowed": False,
        "blockers": blockers,
        "claim_boundary": SELF_HEALING_MAPEK_VERIFICATION_CLAIM_BOUNDARY,
        "redacted": True,
    }


class SelfHealingManager:
    """
    Self-Healing Manager with MAPE-K feedback loop.
    """

    def __init__(
        self,
        node_id: str = "default",
        threshold_manager=None,
        knowledge_storage=None,
        *,
        event_bus: Optional[EventBus] = None,
        event_project_root: str = ".",
    ):
        self.node_id = node_id
        self.event_project_root = event_project_root
        self.event_bus = _event_bus_or_none(event_bus, event_project_root)

        if knowledge_storage:
            from src.storage.mapek_integration import MAPEKKnowledgeStorageAdapter
            adapter = MAPEKKnowledgeStorageAdapter(knowledge_storage, node_id)
            self.knowledge = MAPEKKnowledge(knowledge_storage=adapter)
        else:
            self.knowledge = MAPEKKnowledge()

        self.threshold_manager = threshold_manager
        self.monitor = MAPEKMonitor(knowledge=self.knowledge, threshold_manager=threshold_manager)
        self.analyzer = MAPEKAnalyzer()
        self.planner = MAPEKPlanner(knowledge=self.knowledge)
        self.executor = MAPEKExecutor(event_bus=self.event_bus)

        self.recovery_start_times: Dict[str, float] = {}
        self.recovery_events: Dict[str, str] = {}
        self.pending_verifications: Dict[str, Dict[str, Any]] = {}
        self.remediation_cooldown_seconds = _DEFAULT_REMEDIATION_COOLDOWN_SECONDS
        self.remediation_cooldowns: Dict[str, float] = {}

        self.feedback_updates = 0
        self.threshold_adjustments = 0
        self.strategy_improvements = 0
        if self.threshold_manager and hasattr(
            self.threshold_manager,
            "check_and_apply_dao_proposals",
        ):
            try:
                self.threshold_adjustments += int(
                    self.threshold_manager.check_and_apply_dao_proposals() or 0
                )
            except Exception as exc:
                logger.warning("Failed to apply DAO threshold proposals: %s", exc)

    def _publish_cycle_event(
        self,
        event_type: EventType,
        *,
        stage: str,
        operation: str,
        status: str,
        metrics: Optional[Dict[str, Any]] = None,
        check_result: Any = None,
        issue: str = "",
        action: str = "",
        success: Optional[bool] = None,
        simulated: Optional[bool] = None,
        duration_ms: float = 0.0,
        mttr: Optional[float] = None,
        error_type: Optional[str] = None,
        downstream_event_ids: Optional[List[str]] = None,
        safe_actuator_evidence_metadata: Optional[SafeActuatorEvidenceMetadata] = None,
    ) -> Optional[str]:
        if self.event_bus is None:
            return None

        payload: Dict[str, Any] = {
            "component": "self_healing.mape_k",
            "stage": stage,
            "operation": operation,
            "resource": _MAPEK_RESOURCES.get(operation, f"self_healing:mapek:{operation}"),
            "service_name": _SERVICE_AGENT,
            "layer": _SERVICE_LAYER,
            "identity": _identity_metadata(),
            "status": status,
            "node_id_present": bool(self.node_id),
            "node_id_sha256": _sha256_text(str(self.node_id)),
            "node_id_redacted": True,
            "duration_ms": round(duration_ms, 3),
            "read_only": operation == "monitor" or operation == "verify",
            "observed_state": operation == "monitor" or operation == "verify",
            "control_action": operation == "execute",
            "safe_actuator": operation == "execute",
            "metrics": {
                "keys": _safe_metric_keys(metrics or {}),
                "numeric": _safe_numeric_summary(metrics or {}),
                "values_redacted": True,
            },
            "monitor_result": _safe_monitor_result(check_result),
            "issue": _safe_issue_summary(issue),
            "action": _safe_action_summary(action),
            "success": success,
            "simulated": simulated,
            "downstream_evidence": _safe_downstream_evidence(downstream_event_ids, limit=_DOWNSTREAM_EVENT_ID_LIMIT),
            "mttr_seconds": round(float(mttr), 6) if mttr is not None else None,
            "input_redacted": True,
            "claim_boundary": SELF_HEALING_MAPEK_CLAIM_BOUNDARY,
        }
        if operation == "execute":
            metadata = (
                safe_actuator_evidence_metadata
                if safe_actuator_evidence_metadata is not None
                else SafeActuatorEvidenceMetadata()
            )
            payload["safe_actuator_evidence_metadata"] = metadata.to_dict()
            payload["claim_gate"] = dict(metadata.claim_gate)
        elif operation == "verify":
            verification = check_result if isinstance(check_result, dict) else {}
            payload["claim_gate"] = _verification_claim_gate(
                success=bool(success),
                is_healthy=verification.get("is_healthy") is True,
                metric_recovered=verification.get("metric_recovered") is True,
            )
        if error_type:
            payload["error"] = {"type": error_type, "message_redacted": True}

        try:
            event = self.event_bus.publish(event_type, _SERVICE_AGENT, payload, priority=7)
            return event.event_id
        except Exception as exc:
            logger.error("Failed to publish self-healing MAPE-K event: %s", exc)
            return None

    def run_cycle(self, metrics: Dict):
        """Run MAPE-K cycle with Verification phase."""
        monitor_start = time.time()
        _check_result = self.monitor.check(metrics)
        anomaly_detected = _check_result.get("anomaly_detected", False) if isinstance(_check_result, dict) else bool(_check_result)
        monitor_duration = time.time() - monitor_start

        verification_success: Optional[bool] = None
        if self.node_id in self.pending_verifications:
            verification_success = self._verify_healing(metrics, _check_result)

        self._publish_cycle_event(
            EventType.PIPELINE_STAGE_END, stage="monitor_completed", operation="monitor",
            status="anomaly_detected" if anomaly_detected else "healthy",
            metrics=metrics, check_result=_check_result, duration_ms=monitor_duration * 1000,
        )

        if anomaly_detected:
            if verification_success is False:
                logger.warning(
                    "Skipping immediate self-healing retry after failed verification "
                    "for node %s.",
                    _sha256_text(str(self.node_id)),
                )
                return

            issue = self.analyzer.analyze(metrics, node_id=self.node_id)
            action = self.planner.plan(issue)
            cooldown_key = self._remediation_key(issue, action)
            cooldown_until = self.remediation_cooldowns.get(cooldown_key, 0.0)
            if cooldown_until > time.time():
                self._publish_cycle_event(
                    EventType.TASK_FAILED,
                    stage="execute_blocked_by_cooldown",
                    operation="execute",
                    status="blocked_by_cooldown",
                    metrics=metrics,
                    issue=issue,
                    action=action,
                    success=False,
                    simulated=False,
                    duration_ms=0.0,
                    error_type="RemediationCooldownActive",
                    safe_actuator_evidence_metadata=self._blocked_safe_actuator_metadata(
                        "remediation_cooldown_active"
                    ),
                )
                logger.warning(
                    "Self-healing action blocked by remediation cooldown for node %s.",
                    _sha256_text(str(self.node_id)),
                )
                return

            self.remediation_cooldowns[cooldown_key] = (
                time.time() + self.remediation_cooldown_seconds
            )

            execute_start = time.time()
            downstream_before = _event_ids_for_agent(self.event_bus, _RECOVERY_EXECUTOR_AGENT)

            actuator = SafeActuator(self.executor)
            actuator_result = actuator.execute(
                action,
                {"node_id": self.node_id, "metrics": metrics},
            )
            success = bool(actuator_result.success)
            simulated = bool(actuator_result.simulated)

            downstream_event_ids = _new_event_ids_for_agent(self.event_bus, _RECOVERY_EXECUTOR_AGENT, downstream_before)
            execute_duration = time.time() - execute_start
            safe_actuator_evidence_metadata = _safe_actuator_evidence_metadata(
                event_bus=self.event_bus,
                success=bool(success),
                simulated=simulated,
                downstream_event_ids=downstream_event_ids,
            )

            self._publish_cycle_event(
                (EventType.PIPELINE_STAGE_END if success and not simulated else EventType.TASK_FAILED),
                stage=("execute_completed" if success and not simulated else "execute_simulated" if simulated else "execute_failed"),
                operation="execute", status="success" if success and not simulated else "failed",
                metrics=metrics, issue=issue, action=action, success=success and not simulated,
                simulated=simulated, duration_ms=execute_duration * 1000,
                error_type=None if success else "SafeActuatorFailure", downstream_event_ids=downstream_event_ids,
                safe_actuator_evidence_metadata=safe_actuator_evidence_metadata,
            )

            if success:
                # Mark for verification in the next heartbeat
                self.pending_verifications[self.node_id] = {
                    "action": action,
                    "issue": issue,
                    "start_time": time.time(),
                    "initial_metrics": metrics
                }
                logger.info(f"Recovery action {action} initiated. Waiting for verification.")

            self.knowledge.record(metrics, issue, action, success=success)

    def _verify_healing(
        self,
        current_metrics: Dict,
        check_result: Dict[str, Any],
    ) -> bool:
        """Check if the system actually improved after an action."""
        pending = self.pending_verifications.pop(self.node_id)

        if isinstance(check_result, dict):
            is_healthy = not check_result.get("anomaly_detected", False)
        else:
            is_healthy = not bool(check_result)
        improvement = False

        # Quantitative check (e.g. packet loss decreased)
        old_loss = pending["initial_metrics"].get("packet_loss_percent", 0.0)
        new_loss = current_metrics.get("packet_loss_percent", 0.0)

        if new_loss < old_loss:
            improvement = True

        metric_recovered = (
            new_loss < old_loss
            and new_loss <= self.monitor.default_thresholds["packet_loss_percent"]
        )
        verification_success = is_healthy or metric_recovered
        duration = time.time() - pending["start_time"]

        self._publish_cycle_event(
            EventType.HEALING_VERIFIED if verification_success else EventType.TASK_FAILED,
            stage="verification_completed",
            operation="verify",
            status="verified" if verification_success else "not_verified",
            metrics=current_metrics,
            check_result={
                "is_healthy": is_healthy,
                "metric_improved": improvement,
                "metric_recovered": metric_recovered,
                "anomaly_detected": not verification_success,
            },
            issue=pending["issue"],
            action=pending["action"],
            success=verification_success,
            duration_ms=duration * 1000,
            mttr=duration
        )

        if verification_success:
            logger.info(
                "Healing verified for node %s after action hash %s. "
                "Packet loss: %s -> %s.",
                _sha256_text(str(self.node_id)),
                _sha256_text(str(pending["action"])),
                old_loss,
                new_loss,
            )
            self._apply_feedback_loop(pending["issue"], pending["action"], True, duration)
        else:
            logger.warning(
                "Healing verification failed for node %s after action hash %s.",
                _sha256_text(str(self.node_id)),
                _sha256_text(str(pending["action"])),
            )
            self._apply_feedback_loop(pending["issue"], pending["action"], False, duration)
        return verification_success

    @staticmethod
    def _is_noop_action(action: str) -> bool:
        normalized = " ".join(action.lower().split())
        return normalized in {"", "no action", "no action needed", "nothing to do", "do nothing", "monitor", "monitor only"}

    def _remediation_key(self, issue: str, action: str) -> str:
        return ":".join(
            [
                _sha256_text(str(self.node_id)),
                _sha256_text(str(issue)),
                _sha256_text(str(action)),
            ]
        )

    @staticmethod
    def _blocked_safe_actuator_metadata(reason: str) -> SafeActuatorEvidenceMetadata:
        claim_gate = _self_healing_safe_actuator_claim_gate(
            success=False,
            simulated=False,
            downstream_evidence={"events_total": 0},
            downstream_claim_gate={},
        )
        blockers = list(claim_gate.get("blockers", []))
        blockers.append(reason)
        claim_gate["blockers"] = blockers
        claim_gate["safe_actuator_result_recorded"] = False
        claim_gate["remediation_cooldown_active"] = reason == "remediation_cooldown_active"
        return SafeActuatorEvidenceMetadata(
            claim_gate=claim_gate,
            evidence={"events_total": 0, "payloads_redacted": True},
            claim_boundary=SELF_HEALING_MAPEK_SAFE_ACTUATOR_CLAIM_BOUNDARY,
            redacted=True,
        )

    def _apply_feedback_loop(self, issue: str, action: str, success: bool, mttr: float):
        self.feedback_updates += 1
        if success and mttr < 3.0:
            self.threshold_adjustments += 1
        elif not success or mttr > 7.0:
            self.threshold_adjustments += 1
        if success: self.strategy_improvements += 1
        if self.feedback_updates % 10 == 0:
            logger.info(f"Feedback loop stats: updates={self.feedback_updates}, threshold_adjustments={self.threshold_adjustments}, strategy_improvements={self.strategy_improvements}")

    def get_feedback_stats(self) -> Dict[str, Any]:
        return {
            "feedback_updates": self.feedback_updates,
            "threshold_adjustments": self.threshold_adjustments,
            "strategy_improvements": self.strategy_improvements,
            "knowledge_base_size": len(self.knowledge.incidents),
            "successful_patterns": sum(
                len(patterns) for patterns in self.knowledge.successful_patterns.values()
            ),
            "failed_patterns": sum(
                len(patterns) for patterns in self.knowledge.failed_patterns.values()
            ),
        }

    def integrate_ebpf_self_healing(self, interface: str = "eth0"):
        try:
            from ..ebpf_anomaly_detector import integrate_ebpf_self_healing
            return integrate_ebpf_self_healing(self, interface)
        except ImportError:
            return None
