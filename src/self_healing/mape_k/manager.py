"""
MAPE-K Self-Healing Core for x0tta6bl4
Implements Monitor, Analyze, Plan, Execute, Knowledge loop
"""

import logging
import time
from datetime import datetime
from typing import Any, Dict, List, Optional

from src.coordination.events import EventBus, EventType, get_event_bus
from src.integration.spine import SafeActuator
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
_MAPEK_RESOURCES = {
    "monitor": "self_healing:mapek:monitor",
    "execute": "self_healing:mapek:execute",
}
SELF_HEALING_MAPEK_CLAIM_BOUNDARY = (
    "Self-healing MAPE-K control-spine event only. It records local monitor and "
    "execute decisions, service identity presence, safe-actuator state, bounded "
    "numeric summaries, action/issue hashes, and redacted outcome metadata. It "
    "does not expose raw node IDs, logs, service IDs, scripts, recovery payloads, "
    "or prove that a remote recovery changed live network state."
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

        if threshold_manager:
            try:
                applied = threshold_manager.check_and_apply_dao_proposals()
                if applied > 0:
                    logger.info(f"✅ Applied {applied} DAO threshold proposals on startup")
            except Exception as e:
                logger.warning(f"⚠️ Failed to check DAO proposals: {e}")

        self.recovery_start_times: Dict[str, float] = {}
        self.recovery_events: Dict[str, str] = {}
        self.feedback_updates = 0
        self.threshold_adjustments = 0
        self.strategy_improvements = 0

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
    ) -> Optional[str]:
        if self.event_bus is None:
            return None

        payload: Dict[str, Any] = {
            "component": "self_healing.mape_k",
            "stage": stage,
            "operation": operation,
            "resource": _MAPEK_RESOURCES[operation],
            "service_name": _SERVICE_AGENT,
            "layer": _SERVICE_LAYER,
            "identity": _identity_metadata(),
            "status": status,
            "node_id_present": bool(self.node_id),
            "node_id_sha256": _sha256_text(str(self.node_id)),
            "node_id_redacted": True,
            "duration_ms": round(duration_ms, 3),
            "read_only": operation == "monitor",
            "observed_state": operation == "monitor",
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
        if error_type:
            payload["error"] = {"type": error_type, "message_redacted": True}

        try:
            event = self.event_bus.publish(event_type, _SERVICE_AGENT, payload, priority=7)
            return event.event_id
        except Exception as exc:
            logger.error("Failed to publish self-healing MAPE-K event: %s", exc)
            return None

    def run_cycle(self, metrics: Dict):
        """Run MAPE-K cycle with MTTR tracking."""
        monitor_start = time.time()
        _check_result = self.monitor.check(metrics)
        anomaly_detected = _check_result.get("anomaly_detected", False) if isinstance(_check_result, dict) else bool(_check_result)
        monitor_duration = time.time() - monitor_start
        self._publish_cycle_event(
            EventType.PIPELINE_STAGE_END, stage="monitor_completed", operation="monitor",
            status="anomaly_detected" if anomaly_detected else "healthy",
            metrics=metrics, check_result=_check_result, duration_ms=monitor_duration * 1000,
        )

        try:
            from src.monitoring.metrics import record_mape_k_cycle
            record_mape_k_cycle("monitor", monitor_duration)
        except ImportError: pass

        if anomaly_detected:
            analyze_start = time.time()
            analyze_event_id = f"{self.node_id}_{int(time.time() * 1000)}"
            issue = self.analyzer.analyze(metrics, node_id=self.node_id, event_id=analyze_event_id)
            analyze_duration = time.time() - analyze_start

            try: record_mape_k_cycle("analyze", analyze_duration)
            except NameError: pass

            event_id = f"{issue}_{self.node_id}_{int(time.time() * 1000)}"
            self.recovery_start_times[event_id] = time.time()
            self.recovery_events[event_id] = issue

            plan_start = time.time()
            action = self.planner.plan(issue)
            plan_duration = time.time() - plan_start
            try: record_mape_k_cycle("plan", plan_duration)
            except NameError: pass

            execute_start = time.time()
            downstream_before = _event_ids_for_agent(self.event_bus, _RECOVERY_EXECUTOR_AGENT)
            actuator = SafeActuator(lambda _action, _context: self.executor.execute(action))
            actuator_result = actuator.execute(action, {})
            success = bool(actuator_result.success)
            simulated = bool(getattr(self.executor, "was_simulated", False))
            downstream_event_ids = _new_event_ids_for_agent(self.event_bus, _RECOVERY_EXECUTOR_AGENT, downstream_before)
            execute_duration = time.time() - execute_start

            if event_id in self.recovery_start_times:
                mttr = time.time() - self.recovery_start_times[event_id]
                self._publish_cycle_event(
                    (EventType.PIPELINE_STAGE_END if success and not simulated else EventType.TASK_FAILED),
                    stage=("execute_completed" if success and not simulated else "execute_simulated" if simulated else "execute_failed"),
                    operation="execute", status="success" if success and not simulated else "failed",
                    metrics=metrics, issue=issue, action=action, success=success and not simulated,
                    simulated=simulated, duration_ms=execute_duration * 1000, mttr=mttr,
                    error_type=None if success else "SafeActuatorFailure", downstream_event_ids=downstream_event_ids,
                )

                try:
                    from src.monitoring.metrics import record_mttr, record_self_healing_event
                    recovery_type_map = {"High CPU": "high_cpu", "High Memory": "high_memory", "Network Loss": "route_failure"}
                    recovery_type = recovery_type_map.get(issue, "unknown")
                    record_mttr(recovery_type, mttr)
                    record_self_healing_event(recovery_type, self.node_id)
                    record_mape_k_cycle("execute", execute_duration)
                except ImportError: pass

                knowledge_start = time.time()
                self.knowledge.record(metrics, issue, action, success=success, mttr=mttr)
                self._apply_feedback_loop(issue, action, success, mttr)
                knowledge_duration = time.time() - knowledge_start
                try: record_mape_k_cycle("knowledge", knowledge_duration)
                except NameError: pass

                del self.recovery_start_times[event_id]
                del self.recovery_events[event_id]

            logger.info(f"Self-healing cycle: {issue} → {action}, MTTR={mttr:.3f}s, success={success}")
        else:
            logger.info("No anomalies detected. System healthy.")

    def _apply_feedback_loop(self, issue: str, action: str, success: bool, mttr: float):
        self.feedback_updates += 1
        if success and mttr < 3.0: self.threshold_adjustments += 1
        elif not success or mttr > 7.0: self.threshold_adjustments += 1
        if success: self.strategy_improvements += 1
        if self.feedback_updates % 10 == 0:
            logger.info(f"Feedback loop stats: updates={self.feedback_updates}, threshold_adjustments={self.threshold_adjustments}, strategy_improvements={self.strategy_improvements}")

    def get_feedback_stats(self) -> Dict[str, Any]:
        return {
            "feedback_updates": self.feedback_updates,
            "threshold_adjustments": self.threshold_adjustments,
            "strategy_improvements": self.strategy_improvements,
            "knowledge_base_size": len(self.knowledge.incidents),
            "successful_patterns": len(self.knowledge.successful_patterns),
            "failed_patterns": len(self.knowledge.failed_patterns),
        }

    def integrate_ebpf_self_healing(self, interface: str = "eth0"):
        try:
            from ..ebpf_anomaly_detector import integrate_ebpf_self_healing
            return integrate_ebpf_self_healing(self, interface)
        except ImportError: return None
