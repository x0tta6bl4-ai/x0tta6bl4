#!/usr/bin/env python3
"""
eBPF Anomaly Detector for x0tta6bl4 Self-Healing
Integrates eBPF network metrics with MAPE-K loop for automatic recovery.

Monitors:
- Packet drop rates
- Latency spikes
- Queue congestion
- Route failures

Triggers self-healing actions when anomalies detected.
"""

import asyncio
import logging
import os
import shutil
import subprocess
import time
from dataclasses import dataclass
from enum import Enum
from pathlib import Path
from typing import Any, Dict, List, Optional

from ..coordination.events import EventBus, EventType, get_event_bus
from ..integration.spine import (
    SafeActuator,
    SafeActuatorEvidenceMetadata,
    SafeActuatorResult,
)
from ..network.ebpf.bcc_probes import MeshNetworkProbes
from ..network.ebpf.loader import EBPFLoader
from src.security.policy_decision_adapter import (
    policy_allowed as normalize_policy_allowed,
    policy_reason as normalize_policy_reason,
    policy_rules as normalize_policy_rules,
)
from ..services.service_event_identity import service_event_identity
from .mape_k import MAPEKAnalyzer, MAPEKExecutor, MAPEKMonitor, MAPEKPlanner

logger = logging.getLogger(__name__)

_SERVICE_AGENT = "ebpf-self-healing"
EBPF_CLAIM_BOUNDARY = (
    "eBPF self-healing recovery event only. It records local policy and safe "
    "actuator state; it is not restored dataplane, route convergence, kernel "
    "forwarding correctness, production rollout, live traffic, or live "
    "throughput evidence."
)
EBPF_SAFE_ACTUATOR_CLAIM_BOUNDARY = (
    "eBPF SafeActuator metadata proves only a local, policy-gated recovery "
    "action attempt for one interface. It is not restored dataplane, route "
    "convergence, kernel forwarding correctness, live customer traffic, "
    "external DPI bypass, settlement finality, or production readiness proof."
)
EBPF_RECOVERY_CLAIM_GATE_SCHEMA = "x0tta6bl4.self_healing.ebpf_recovery_claim_gate.v1"


def _ebpf_recovery_claim_gate(result: Optional[Dict[str, Any]]) -> Dict[str, Any]:
    local_action_recorded = result is not None
    local_action_succeeded = bool(
        result and result.get("success") is True and result.get("simulated") is not True
    )
    return {
        "schema": EBPF_RECOVERY_CLAIM_GATE_SCHEMA,
        "local_ebpf_recovery_action_recorded": local_action_recorded,
        "local_ebpf_recovery_action_succeeded": local_action_succeeded,
        "local_policy_decision_recorded": True,
        "safe_actuator_result_recorded": local_action_recorded,
        "restored_dataplane_claim_allowed": False,
        "route_convergence_claim_allowed": False,
        "kernel_forwarding_correctness_claim_allowed": False,
        "dataplane_delivery_claim_allowed": False,
        "traffic_delivery_claim_allowed": False,
        "live_customer_traffic_confirmed": False,
        "external_dpi_bypass_confirmed": False,
        "settlement_finality_confirmed": False,
        "production_readiness_claim_allowed": False,
        "claim_allowed": {
            "local_ebpf_recovery_lifecycle": local_action_recorded,
            "local_safe_actuator_success": local_action_succeeded,
            "restored_dataplane": False,
            "route_convergence": False,
            "kernel_forwarding_correctness": False,
            "dataplane_delivery": False,
            "traffic_delivery": False,
            "live_customer_traffic": False,
            "external_dpi_bypass": False,
            "settlement_finality": False,
            "production_readiness": False,
        },
        "claim_boundary": EBPF_CLAIM_BOUNDARY,
        "payloads_redacted": True,
    }


class EBPFAnomalyType(Enum):
    """Types of eBPF-detected anomalies"""

    HIGH_PACKET_DROPS = "high_packet_drops"
    LATENCY_SPIKE = "latency_spike"
    QUEUE_CONGESTION = "queue_congestion"
    ROUTE_FAILURE = "route_failure"
    LOW_THROUGHPUT = "low_throughput"


@dataclass
class EBPFAnomaly:
    """Represents a detected anomaly"""

    anomaly_type: EBPFAnomalyType
    severity: str  # LOW, MEDIUM, HIGH, CRITICAL
    metric_value: float
    threshold: float
    interface: str
    timestamp: float
    description: str


class EBPFAnalyzer(MAPEKAnalyzer):
    """
    Analyzes eBPF metrics for anomalies and root causes.
    """

    def __init__(self):
        super().__init__()
        self.anomaly_history: List[EBPFAnomaly] = []
        self.baseline_metrics = {
            "packet_drop_rate": 0.01,  # 1%
            "avg_latency_ms": 10.0,
            "queue_congestion": 50,  # 50% full
            "throughput_mbps": 100.0,
        }

    def analyze(self, metrics: Dict[str, Any]) -> Optional[EBPFAnomaly]:
        """
        Analyze eBPF metrics for anomalies.

        Args:
            metrics: Current eBPF statistics

        Returns:
            Anomaly if detected, None otherwise
        """
        # Check packet drops
        drop_rate = self._calculate_drop_rate(metrics)
        if drop_rate > self.baseline_metrics["packet_drop_rate"] * 5:  # 5% threshold
            severity = "HIGH" if drop_rate > 0.1 else "MEDIUM"
            return EBPFAnomaly(
                anomaly_type=EBPFAnomalyType.HIGH_PACKET_DROPS,
                severity=severity,
                metric_value=drop_rate,
                threshold=self.baseline_metrics["packet_drop_rate"] * 5,
                interface=metrics.get("interface", "unknown"),
                timestamp=time.time(),
                description=f"Packet drop rate {drop_rate:.2%} exceeds threshold",
            )

        # Check latency
        avg_latency = metrics.get("avg_latency_ns", 0) / 1e6  # Convert to ms
        if avg_latency > self.baseline_metrics["avg_latency_ms"] * 3:  # 3x baseline
            return EBPFAnomaly(
                anomaly_type=EBPFAnomalyType.LATENCY_SPIKE,
                severity="HIGH",
                metric_value=avg_latency,
                threshold=self.baseline_metrics["avg_latency_ms"] * 3,
                interface=metrics.get("interface", "unknown"),
                timestamp=time.time(),
                description=f"Latency spike: {avg_latency:.1f}ms",
            )

        # Check queue congestion
        queue_cong = metrics.get("queue_congestion", 0)
        if queue_cong > self.baseline_metrics["queue_congestion"]:
            severity = "CRITICAL" if queue_cong > 90 else "HIGH"
            return EBPFAnomaly(
                anomaly_type=EBPFAnomalyType.QUEUE_CONGESTION,
                severity=severity,
                metric_value=queue_cong,
                threshold=self.baseline_metrics["queue_congestion"],
                interface=metrics.get("interface", "unknown"),
                timestamp=time.time(),
                description=f"Queue congestion: {queue_cong:.1f}%",
            )

        return None

    def _calculate_drop_rate(self, metrics: Dict[str, Any]) -> float:
        """Calculate packet drop rate from stats"""
        total = metrics.get("total_packets", 0)
        dropped = metrics.get("dropped_packets", 0)

        if total == 0:
            return 0.0

        return dropped / total


class EBPFPlanner(MAPEKPlanner):
    """
    Plans recovery actions for eBPF anomalies.
    """

    def plan(self, anomaly: EBPFAnomaly) -> List[Dict[str, Any]]:
        """
        Generate recovery plan for anomaly.

        Returns:
            List of recovery actions
        """
        actions = []

        if anomaly.anomaly_type == EBPFAnomalyType.HIGH_PACKET_DROPS:
            actions.extend(
                [
                    {
                        "action": "clear_packet_queues",
                        "interface": anomaly.interface,
                        "priority": "HIGH",
                        "description": "Flush packet queues to reduce drops",
                    },
                    {
                        "action": "adjust_route_weights",
                        "interface": anomaly.interface,
                        "priority": "MEDIUM",
                        "description": "Redistribute traffic to less congested routes",
                    },
                ]
            )

        elif anomaly.anomaly_type == EBPFAnomalyType.LATENCY_SPIKE:
            actions.extend(
                [
                    {
                        "action": "optimize_ebpf_program",
                        "interface": anomaly.interface,
                        "priority": "HIGH",
                        "description": "Reload optimized eBPF program",
                    },
                    {
                        "action": "enable_hw_offload",
                        "interface": anomaly.interface,
                        "priority": "MEDIUM",
                        "description": "Enable hardware offload if available",
                    },
                ]
            )

        elif anomaly.anomaly_type == EBPFAnomalyType.QUEUE_CONGESTION:
            actions.extend(
                [
                    {
                        "action": "increase_queue_size",
                        "interface": anomaly.interface,
                        "priority": "HIGH",
                        "description": "Dynamically increase queue buffer size",
                    },
                    {
                        "action": "throttle_traffic",
                        "interface": anomaly.interface,
                        "priority": "MEDIUM",
                        "description": "Apply traffic shaping to prevent overflow",
                    },
                ]
            )

        return actions


class EBPFExecutor(MAPEKExecutor):
    """
    Executes recovery actions for eBPF anomalies.
    """

    def __init__(
        self,
        loader: EBPFLoader,
        node_id: str = "default-node",
        event_bus: Optional[EventBus] = None,
        event_project_root: str = ".",
        policy_engine: Optional[Any] = None,
        require_policy: Optional[bool] = None,
        source_agent: str = _SERVICE_AGENT,
        spiffe_id: Optional[str] = None,
        did: Optional[str] = None,
        wallet_address: Optional[str] = None,
        safe_actuator: Optional[SafeActuator] = None,
    ):
        super().__init__()
        self.loader = loader
        self.node_id = node_id
        self.source_agent = source_agent
        self.event_project_root = event_project_root
        self.event_bus = (
            event_bus if event_bus is not None else self._default_event_bus(event_project_root)
        )
        self.policy_engine = policy_engine
        self.require_policy = (
            require_policy
            if require_policy is not None
            else self._env_bool("X0TTA6BL4_EBPF_RECOVERY_POLICY_REQUIRED", False)
            or self._env_bool("X0TTA6BL4_RECOVERY_POLICY_REQUIRED", False)
            or self._env_bool("X0TTA6BL4_PRODUCTION", False)
        )
        if self.policy_engine is None and self.require_policy:
            self.policy_engine = self._default_policy_engine()
        service_identity = service_event_identity(service_name="ebpf-self-healing")
        self.identity = {
            "node_id": node_id,
            "spiffe_id": spiffe_id or service_identity["spiffe_id"],
            "did": did or service_identity["did"],
            "wallet_address": wallet_address or service_identity["wallet_address"],
        }
        self.safe_actuator = safe_actuator or SafeActuator(self._execute_action_internal)

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
            logger.error("Failed to initialize eBPF self-healing EventBus: %s", exc)
            return None

    @staticmethod
    def _default_policy_engine() -> Optional[Any]:
        try:
            from src.security.zero_trust.policy_engine import get_policy_engine

            return get_policy_engine()
        except Exception as exc:
            logger.error("Failed to initialize eBPF self-healing policy engine: %s", exc)
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

    @staticmethod
    def _action_resource_name(action_type: str) -> str:
        action_lower = str(action_type or "unknown_action").lower().strip()
        slug = "".join(
            char if char.isalnum() else "_"
            for char in action_lower
        ).strip("_")
        while "__" in slug:
            slug = slug.replace("__", "_")
        return slug or "unknown_action"

    def _safe_actuator_evidence_metadata_from_flags(
        self,
        *,
        action_type: str,
        success: bool,
        simulated: bool,
        policy_allowed: bool,
    ) -> SafeActuatorEvidenceMetadata:
        action_resource = self._action_resource_name(action_type)
        local_action_succeeded = bool(success and not simulated)
        claim_gate = {
            "schema": "x0tta6bl4.self_healing.ebpf.safe_actuator_claim_gate.v1",
            "surface": "self_healing.ebpf.execute",
            "action_type": str(action_type),
            "action_resource": action_resource,
            "local_ebpf_recovery_action_recorded": True,
            "local_ebpf_recovery_action_succeeded": local_action_succeeded,
            "local_policy_decision_recorded": True,
            "policy_allowed": bool(policy_allowed),
            "safe_actuator_result_recorded": True,
            "local_safe_actuator_success": local_action_succeeded,
            "restored_dataplane_claim_allowed": False,
            "route_convergence_claim_allowed": False,
            "kernel_forwarding_correctness_claim_allowed": False,
            "dataplane_delivery_claim_allowed": False,
            "traffic_delivery_claim_allowed": False,
            "live_customer_traffic_confirmed": False,
            "customer_traffic_claim_allowed": False,
            "external_dpi_bypass_confirmed": False,
            "settlement_finality_confirmed": False,
            "external_settlement_finality_claim_allowed": False,
            "production_slo_claim_allowed": False,
            "production_readiness_claim_allowed": False,
            "claim_boundary": EBPF_SAFE_ACTUATOR_CLAIM_BOUNDARY,
            "payloads_redacted": True,
            "redacted": True,
        }
        return SafeActuatorEvidenceMetadata(
            claim_gate=claim_gate,
            evidence={
                "component": "self_healing.ebpf_anomaly_detector",
                "resource": f"self_healing:ebpf:{action_resource}",
                "action_type": str(action_type),
                "raw_context_values_redacted": True,
                "raw_command_output_redacted": True,
                "payloads_redacted": True,
                "redacted": True,
            },
            source_agents=[self.source_agent],
            claim_boundary=EBPF_SAFE_ACTUATOR_CLAIM_BOUNDARY,
            redacted=True,
        )

    def _safe_actuator_evidence_metadata(
        self,
        action_type: str,
        actuator_result: SafeActuatorResult,
        *,
        policy_allowed: bool,
    ) -> SafeActuatorEvidenceMetadata:
        metadata = actuator_result.evidence_metadata
        if metadata.claim_gate:
            return metadata
        return self._safe_actuator_evidence_metadata_from_flags(
            action_type=action_type,
            success=actuator_result.success,
            simulated=actuator_result.simulated,
            policy_allowed=policy_allowed,
        )

    def _publish_recovery_event(
        self,
        event_type: EventType,
        *,
        stage: str,
        action_type: str,
        context: Dict[str, Any],
        result: Optional[Dict[str, Any]] = None,
        reason: str = "",
        policy_decision: Any = None,
        safe_actuator_evidence_metadata: Optional[
            SafeActuatorEvidenceMetadata
        ] = None,
    ) -> Optional[str]:
        if self.event_bus is None:
            return None
        action_resource = self._action_resource_name(action_type)
        payload = {
            "component": "self_healing.ebpf_anomaly_detector",
            "stage": stage,
            "action_type": action_type,
            "action_resource": action_resource,
            "resource": f"self_healing:ebpf:{action_resource}",
            "node_id": self.identity["node_id"],
            "spiffe_id": self.identity["spiffe_id"],
            "did": self.identity["did"],
            "wallet_address": self.identity["wallet_address"],
            "identity": dict(self.identity),
            "context": self._safe_context(context),
            "result": self._safe_context(result or {}) if result is not None else None,
            "success": result.get("success") if result is not None else None,
            "reason": reason,
            "policy_required": self.require_policy or self.policy_engine is not None,
            "policy_allowed": self._policy_allowed(policy_decision)
            if policy_decision is not None
            else None,
            "policy_reason": self._policy_reason(policy_decision)
            if policy_decision is not None
            else "",
            "matched_rules": self._policy_rules(policy_decision)
            if policy_decision is not None
            else [],
            "claim_gate": _ebpf_recovery_claim_gate(result),
            "restored_dataplane_claim_allowed": False,
            "route_convergence_claim_allowed": False,
            "kernel_forwarding_correctness_claim_allowed": False,
            "dataplane_delivery_claim_allowed": False,
            "traffic_delivery_claim_allowed": False,
            "live_customer_traffic_confirmed": False,
            "external_dpi_bypass_confirmed": False,
            "settlement_finality_confirmed": False,
            "production_readiness_claim_allowed": False,
            "claim_boundary": EBPF_CLAIM_BOUNDARY,
        }
        if safe_actuator_evidence_metadata is not None:
            payload["safe_actuator_evidence_metadata"] = (
                safe_actuator_evidence_metadata.to_dict()
            )
            payload["safe_actuator_claim_gate"] = dict(
                safe_actuator_evidence_metadata.claim_gate
            )
        try:
            event = self.event_bus.publish(event_type, self.source_agent, payload, priority=7)
            return event.event_id
        except Exception as exc:
            logger.error("Failed to publish eBPF self-healing event: %s", exc)
            return None

    def _evaluate_action_policy(self, action_type: str) -> tuple[bool, Any, str]:
        if self.policy_engine is None:
            if self.require_policy:
                return False, None, "eBPF self-healing policy engine is required but unavailable"
            return True, None, ""
        spiffe_id = self.identity.get("spiffe_id")
        if not spiffe_id:
            return False, None, "eBPF self-healing SPIFFE identity is required for policy evaluation"
        action_resource = self._action_resource_name(action_type)
        try:
            decision = self.policy_engine.evaluate(
                spiffe_id,
                resource=f"self_healing:ebpf:{action_resource}",
                workload_type="self-healing",
            )
        except Exception as exc:
            return False, None, f"eBPF self-healing policy evaluation failed: {exc}"
        if not self._policy_allowed(decision):
            return False, decision, self._policy_reason(decision) or "eBPF self-healing policy denied action"
        return True, decision, self._policy_reason(decision)

    def execute(self, action: Dict[str, Any]) -> bool:
        """
        Execute a recovery action.

        Returns:
            True if successful, False otherwise
        """
        try:
            context = dict(action or {})
            action_type = str(context.get("action", "unknown_action"))
            interface = str(context.get("interface", ""))
            context["interface"] = interface

            if not action_type or action_type == "unknown_action" or not interface:
                reason = "eBPF action and interface are required"
                result = {"success": False, "reason": reason}
                self._publish_recovery_event(
                    EventType.TASK_FAILED,
                    stage="invalid_action",
                    action_type=action_type,
                    context=context,
                    result=result,
                    reason=reason,
                )
                return False

            self._publish_recovery_event(
                EventType.COORDINATION_REQUEST,
                stage="received",
                action_type=action_type,
                context=context,
            )

            policy_allowed, policy_decision, policy_reason = (
                self._evaluate_action_policy(action_type)
            )
            if not policy_allowed:
                result = {
                    "success": False,
                    "reason": policy_reason,
                    "policy_required": True,
                    "matched_rules": self._policy_rules(policy_decision),
                }
                self._publish_recovery_event(
                    EventType.TASK_BLOCKED,
                    stage="policy_denied",
                    action_type=action_type,
                    context=context,
                    result=result,
                    reason=policy_reason,
                    policy_decision=policy_decision,
                )
                return False

            self._publish_recovery_event(
                EventType.PIPELINE_STAGE_START,
                stage="actuator_start",
                action_type=action_type,
                context=context,
                reason=policy_reason,
                policy_decision=policy_decision,
            )
            actuator_result = self.safe_actuator.execute(action_type, context)
            actuator_metadata = self._safe_actuator_evidence_metadata(
                action_type,
                actuator_result,
                policy_allowed=True,
            )
            if actuator_result.simulated:
                reason = actuator_result.reason or "safe actuator returned simulated result"
                result = {
                    "success": False,
                    "reason": reason,
                    "simulated": True,
                }
                self._publish_recovery_event(
                    EventType.TASK_FAILED,
                    stage="actuator_simulated",
                    action_type=action_type,
                    context=context,
                    result=result,
                    reason=reason,
                    policy_decision=policy_decision,
                    safe_actuator_evidence_metadata=actuator_metadata,
                )
                return False

            result = {
                "success": actuator_result.success,
                "reason": actuator_result.reason,
                "simulated": actuator_result.simulated,
            }
            self._publish_recovery_event(
                EventType.PIPELINE_STAGE_END
                if actuator_result.success
                else EventType.TASK_FAILED,
                stage="actuator_completed"
                if actuator_result.success
                else "actuator_failed",
                action_type=action_type,
                context=context,
                result=result,
                reason=actuator_result.reason or policy_reason,
                policy_decision=policy_decision,
                safe_actuator_evidence_metadata=actuator_metadata,
            )
            return actuator_result.success

        except Exception as e:
            logger.error(f"Failed to execute eBPF action: {e}")
            return False

    def _execute_action_internal(
        self,
        action_type: str,
        context: Dict[str, Any],
    ) -> SafeActuatorResult:
        interface = str(context.get("interface", ""))

        if action_type == "clear_packet_queues":
            success = self._clear_queues(interface)
            return SafeActuatorResult(
                success,
                evidence_metadata=self._safe_actuator_evidence_metadata_from_flags(
                    action_type=action_type,
                    success=success,
                    simulated=False,
                    policy_allowed=True,
                ),
            )

        if action_type == "adjust_route_weights":
            success = self._adjust_routes(interface)
            return SafeActuatorResult(
                success,
                evidence_metadata=self._safe_actuator_evidence_metadata_from_flags(
                    action_type=action_type,
                    success=success,
                    simulated=False,
                    policy_allowed=True,
                ),
            )

        if action_type == "optimize_ebpf_program":
            success = self._reload_ebpf(interface)
            return SafeActuatorResult(
                success,
                evidence_metadata=self._safe_actuator_evidence_metadata_from_flags(
                    action_type=action_type,
                    success=success,
                    simulated=False,
                    policy_allowed=True,
                ),
            )

        if action_type == "enable_hw_offload":
            success = self._enable_hw_offload(interface)
            return SafeActuatorResult(
                success,
                evidence_metadata=self._safe_actuator_evidence_metadata_from_flags(
                    action_type=action_type,
                    success=success,
                    simulated=False,
                    policy_allowed=True,
                ),
            )

        if action_type == "increase_queue_size":
            success = self._increase_queue_size(interface)
            return SafeActuatorResult(
                success,
                evidence_metadata=self._safe_actuator_evidence_metadata_from_flags(
                    action_type=action_type,
                    success=success,
                    simulated=False,
                    policy_allowed=True,
                ),
            )

        if action_type == "throttle_traffic":
            success = self._throttle_traffic(interface)
            return SafeActuatorResult(
                success,
                evidence_metadata=self._safe_actuator_evidence_metadata_from_flags(
                    action_type=action_type,
                    success=success,
                    simulated=False,
                    policy_allowed=True,
                ),
            )

        logger.warning(f"Unknown action: {action_type}")
        return SafeActuatorResult(
            False,
            f"unknown eBPF action: {action_type}",
            evidence_metadata=self._safe_actuator_evidence_metadata_from_flags(
                action_type=action_type,
                success=False,
                simulated=False,
                policy_allowed=True,
            ),
        )

    @staticmethod
    def _interface_exists(interface: str) -> bool:
        return bool(interface) and Path("/sys/class/net", interface).exists()

    def _run_command(self, command: List[str]) -> bool:
        if not command:
            return False
        executable = command[0]
        if shutil.which(executable) is None:
            logger.warning("Required recovery command is unavailable: %s", executable)
            return False
        try:
            subprocess.run(
                command,
                check=True,
                stdout=subprocess.DEVNULL,
                stderr=subprocess.PIPE,
                text=True,
            )
            return True
        except subprocess.CalledProcessError as exc:
            logger.warning(
                "Recovery command failed: %s stderr=%s",
                " ".join(command),
                (exc.stderr or "").strip(),
            )
            return False

    def _clear_queues(self, interface: str) -> bool:
        """Clear packet queues"""
        if not self._interface_exists(interface):
            logger.warning("Cannot clear queues; interface does not exist: %s", interface)
            return False

        if self._run_command(["tc", "qdisc", "replace", "dev", interface, "root", "fq"]):
            logger.info(f"Cleared queues on {interface}")
            return True
        return False

    def _adjust_routes(self, interface: str) -> bool:
        """Adjust routing weights"""
        if not self._interface_exists(interface):
            logger.warning("Cannot adjust routes; interface does not exist: %s", interface)
            return False

        if self._run_command(["ip", "route", "flush", "cache"]):
            logger.info("Flushed route cache after anomaly on %s", interface)
            return True
        return False

    def _reload_ebpf(self, interface: str) -> bool:
        """Reload optimized eBPF program"""
        try:
            self.loader.cleanup()
            # Reload with optimized settings
            self.loader.load_programs()
            logger.info(f"Reloaded eBPF on {interface}")
            return True
        except Exception:
            return False

    def _enable_hw_offload(self, interface: str) -> bool:
        """Enable hardware offload"""
        if not self._interface_exists(interface):
            logger.warning("Cannot enable hardware offload; interface does not exist: %s", interface)
            return False

        command = ["ethtool", "-K", interface, "tso", "on", "gso", "on", "gro", "on"]
        if self._run_command(command):
            logger.info(f"Enabled HW offload on {interface}")
            return True
        return False

    def _increase_queue_size(self, interface: str) -> bool:
        """Increase queue buffer size"""
        if not self._interface_exists(interface):
            logger.warning("Cannot increase queue size; interface does not exist: %s", interface)
            return False

        if self._run_command(["ip", "link", "set", interface, "txqueuelen", "1000"]):
            logger.info(f"Increased queue size on {interface}")
            return True
        return False

    def _throttle_traffic(self, interface: str) -> bool:
        """Apply traffic throttling"""
        if not self._interface_exists(interface):
            logger.warning("Cannot throttle traffic; interface does not exist: %s", interface)
            return False

        rate = os.getenv("X0TTA6BL4_EBPF_THROTTLE_RATE", "100mbit")
        burst = os.getenv("X0TTA6BL4_EBPF_THROTTLE_BURST", "32kbit")
        latency = os.getenv("X0TTA6BL4_EBPF_THROTTLE_LATENCY", "400ms")
        command = [
            "tc",
            "qdisc",
            "replace",
            "dev",
            interface,
            "root",
            "tbf",
            "rate",
            rate,
            "burst",
            burst,
            "latency",
            latency,
        ]
        if self._run_command(command):
            logger.info("Applied traffic throttling on %s at %s", interface, rate)
            return True
        return False


class EBPFSelfHealingController:
    """
    Main controller for eBPF self-healing.
    Integrates all MAPE-K components.
    """

    def __init__(
        self,
        interface: str = "eth0",
        node_id: str = "default-node",
        event_bus: Optional[EventBus] = None,
        event_project_root: str = ".",
        policy_engine: Optional[Any] = None,
        require_policy: Optional[bool] = None,
        source_agent: str = _SERVICE_AGENT,
        spiffe_id: Optional[str] = None,
        did: Optional[str] = None,
        wallet_address: Optional[str] = None,
        safe_actuator: Optional[SafeActuator] = None,
    ):
        self.interface = interface
        self.loader = EBPFLoader(interface)
        self.probes = MeshNetworkProbes(interface)

        # MAPE-K components
        self.monitor = MAPEKMonitor()
        self.analyzer = EBPFAnalyzer()
        self.planner = EBPFPlanner()
        self.executor = EBPFExecutor(
            self.loader,
            node_id=node_id,
            event_bus=event_bus,
            event_project_root=event_project_root,
            policy_engine=policy_engine,
            require_policy=require_policy,
            source_agent=source_agent,
            spiffe_id=spiffe_id,
            did=did,
            wallet_address=wallet_address,
            safe_actuator=safe_actuator,
        )

        # Register eBPF anomaly detector
        self.monitor.register_detector(self._detect_anomalies)

        self.running = False

    def _detect_anomalies(self, metrics: Dict[str, Any]) -> bool:
        """Custom anomaly detector for eBPF metrics"""
        anomaly = self.analyzer.analyze(metrics)
        if anomaly:
            logger.warning(f"eBPF anomaly detected: {anomaly.description}")
            # Trigger MAPE-K loop
            asyncio.create_task(self._handle_anomaly(anomaly))
            return True
        return False

    async def _handle_anomaly(self, anomaly: EBPFAnomaly):
        """Handle detected anomaly through MAPE-K loop"""
        # Plan recovery
        actions = self.planner.plan(anomaly)

        # Execute actions
        for action in actions:
            success = self.executor.execute(action)
            if success:
                logger.info(f"Executed recovery action: {action['action']}")
            else:
                logger.error(f"Failed to execute: {action['action']}")

    async def start_monitoring(self):
        """Start self-healing monitoring loop"""
        self.running = True
        logger.info("Starting eBPF self-healing monitoring...")

        while self.running:
            try:
                # Collect current metrics
                ebpf_stats = self.loader.get_stats()
                probe_metrics = self.probes.get_current_metrics()

                # Combine metrics
                current_metrics = {
                    **ebpf_stats,
                    **probe_metrics,
                    "interface": self.interface,
                }

                # Run monitoring
                self.monitor.monitor(current_metrics)

                await asyncio.sleep(10)  # Check every 10 seconds

            except Exception as e:
                logger.error(f"Monitoring error: {e}")
                await asyncio.sleep(5)

    async def stop_monitoring(self):
        """Stop monitoring and cleanup"""
        self.running = False
        self.loader.cleanup()
        self.probes.cleanup()
        logger.info("Stopped eBPF self-healing monitoring")


# Integration with main MAPE-K
def integrate_ebpf_self_healing(mape_k_manager, interface: str = "eth0"):
    """
    Integrate eBPF self-healing with main MAPE-K manager.

    Args:
        mape_k_manager: SelfHealingManager instance
        interface: Network interface to monitor

    Returns:
        EBPFSelfHealingController instance
    """
    ebpf_controller = EBPFSelfHealingController(interface)

    # Register the eBPF anomaly detector with MAPE-K monitor
    mape_k_manager.monitor.register_detector(ebpf_controller._detect_anomalies)

    logger.info("eBPF anomaly detector registered with MAPE-K monitor")
    return ebpf_controller
