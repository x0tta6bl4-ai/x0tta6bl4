"""
MAPE-K integration for Swarm Intelligence.
"""
from __future__ import annotations
import asyncio
import logging
import os
from datetime import datetime
from typing import Any, Dict, List, Optional

from src.coordination.events import EventBus, EventType, get_event_bus
from src.integration.spine import (
    AsyncSafeActuator,
    SafeActuatorEvidenceMetadata,
    SafeActuatorResult,
)
from src.security.policy_decision_adapter import (
    policy_allowed as normalize_policy_allowed,
    policy_reason as normalize_policy_reason,
    policy_rules as normalize_policy_rules,
)
from src.services.service_event_identity import service_event_identity

from .types import (
    DecisionPriority,
    DecisionResult,
    MAPEK_CLAIM_BOUNDARY,
    SwarmAction,
)

logger = logging.getLogger(__name__)

_SERVICE_AGENT = "swarm-mapek"
_STRONG_CLAIM_IDS = (
    "cluster_wide_consensus_finality",
    "production_action_applied",
    "restored_dataplane",
    "customer_traffic_restored",
    "external_settlement_finality",
    "production_readiness",
)

class MAPEKIntegration:
    """
    Integration with MAPE-K autonomic loop for autonomous decisions.

    Provides:
    - Monitor: Collect swarm state and metrics
    - Analyze: Detect anomalies and opportunities
    - Plan: Generate action proposals
    - Execute: Apply approved actions
    - Knowledge: Learn from outcomes
    """

    def __init__(
        self,
        swarm_intelligence: Any,
        *,
        event_bus: Optional[EventBus] = None,
        event_project_root: str = ".",
        policy_engine: Optional[Any] = None,
        require_policy: Optional[bool] = None,
        source_agent: str = _SERVICE_AGENT,
        spiffe_id: Optional[str] = None,
        did: Optional[str] = None,
        wallet_address: Optional[str] = None,
        safe_actuator: Optional[Any] = None,
        mesh_detector: Optional[Any] = None,
    ):
        self.swarm = swarm_intelligence
        self._metrics_history: List[Dict[str, Any]] = []
        self._action_history: List[Dict[str, Any]] = []
        self._learning_data: Dict[str, Any] = {}
        self.source_agent = source_agent
        self.event_project_root = event_project_root
        self.event_bus = (
            event_bus if event_bus is not None else self._default_event_bus(event_project_root)
        )
        self.policy_engine = policy_engine
        self.require_policy = (
            require_policy
            if require_policy is not None
            else self._env_bool("X0TTA6BL4_SWARM_MAPEK_POLICY_REQUIRED", False)
            or self._env_bool("X0TTA6BL4_SWARM_POLICY_REQUIRED", False)
            or self._env_bool("X0TTA6BL4_PRODUCTION", False)
        )
        if self.policy_engine is None and self.require_policy:
            self.policy_engine = self._default_policy_engine()
        service_identity = service_event_identity(service_name="swarm-mapek")
        self.identity = {
            "node_id": getattr(swarm_intelligence, "node_id", ""),
            "spiffe_id": spiffe_id or service_identity["spiffe_id"],
            "did": did or service_identity["did"],
            "wallet_address": wallet_address or service_identity["wallet_address"],
        }
        self._last_decision_result: Optional[DecisionResult] = None
        self.safe_actuator = safe_actuator or AsyncSafeActuator(self._propose_action_internal)
        self.mesh_detector = mesh_detector
        self._mesh_topology_cache: Optional[Dict[str, Any]] = None

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
            logger.error("Failed to initialize swarm MAPE-K EventBus: %s", exc)
            return None

    @staticmethod
    def _default_policy_engine() -> Optional[Any]:
        try:
            from src.security.zero_trust.policy_engine import get_policy_engine

            return get_policy_engine()
        except Exception as exc:
            logger.error("Failed to initialize swarm MAPE-K policy engine: %s", exc)
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

    @classmethod
    def _action_claim_gate(
        cls,
        *,
        action_type: str,
        success: bool,
        simulated: bool,
        action_present: bool,
        decision_result: Optional[DecisionResult],
    ) -> Dict[str, Any]:
        decision_present = decision_result is not None
        decision_approved = bool(getattr(decision_result, "approved", False))
        blockers = [
            "cluster_wide_consensus_finality_requires_independent_quorum_evidence",
            "production_action_requires_runtime_post_action_evidence",
            "dataplane_claim_requires_dedicated_dataplane_probe",
            "settlement_finality_requires_external_chain_evidence",
            "production_readiness_requires_cross_plane_proof",
        ]
        if not action_present:
            blockers.append("swarm_action_missing")
        if simulated:
            blockers.append("safe_actuator_result_simulated")
        if not success:
            blockers.append("safe_actuator_result_not_successful")
        if decision_present and not decision_approved:
            blockers.append("local_swarm_decision_rejected")

        local_decision_claim_allowed = (
            success and not simulated and decision_present and decision_approved
        )
        return {
            "schema": "x0tta6bl4.swarm_mapek.safe_actuator_claim_gate.v1",
            "surface": "swarm.intelligence.mapek",
            "action_type": str(action_type or ""),
            "safe_actuator_result_recorded": True,
            "local_safe_actuator_success": bool(success),
            "local_swarm_action_observed_claim_allowed": action_present,
            "local_swarm_decision_result_claim_allowed": local_decision_claim_allowed,
            "cluster_wide_consensus_finality_claim_allowed": False,
            "production_action_applied_claim_allowed": False,
            "restored_dataplane_claim_allowed": False,
            "customer_traffic_restored_claim_allowed": False,
            "external_settlement_finality_claim_allowed": False,
            "production_readiness_claim_allowed": False,
            "blocked_claim_ids": list(_STRONG_CLAIM_IDS),
            "blockers": blockers,
            "claim_boundary": (
                "Swarm MAPE-K SafeActuator metadata proves only a local guarded "
                "proposal/decision callback outcome. It does not prove cluster-wide "
                "consensus finality, production action application, dataplane or "
                "customer traffic recovery, external settlement finality, or "
                "production readiness."
            ),
            "redacted": True,
        }

    @staticmethod
    def _cross_plane_claim_gate() -> Dict[str, Any]:
        return {
            "schema": "x0tta6bl4.cross_plane_proof_gate.v1",
            "surface": "swarm.intelligence.mapek.safe_actuator",
            "decision": "CROSS_PLANE_CLAIMS_BLOCKED",
            "allowed": False,
            "requested_claim_ids": list(_STRONG_CLAIM_IDS),
            "blockers": ["swarm_mapek_local_decision_only"],
            "claim_boundary": (
                "Swarm MAPE-K records local guarded action flow. Strong claims still "
                "need independent cross-plane evidence from consensus, dataplane, "
                "settlement, and production readiness gates."
            ),
        }

    @classmethod
    def _safe_actuator_evidence_metadata(
        cls,
        *,
        action_type: str,
        context: Dict[str, Any],
        success: bool,
        simulated: bool = False,
        decision_result: Optional[DecisionResult] = None,
    ) -> SafeActuatorEvidenceMetadata:
        action = context.get("_action")
        action_present = isinstance(action, SwarmAction)
        action_id = getattr(action, "action_id", "") if action_present else ""
        action_priority = (
            getattr(getattr(action, "priority", None), "value", "")
            if action_present
            else ""
        )
        decision_present = decision_result is not None
        consensus_mode = ""
        if decision_present:
            consensus_mode = str(getattr(decision_result.consensus_mode, "value", ""))

        evidence = {
            "source_agents": [_SERVICE_AGENT],
            "event_ids": [],
            "action_id": str(action_id),
            "action_type": str(action_type or ""),
            "resource": f"swarm:mapek:{cls._action_resource_name(action_type)}",
            "action_resource": cls._action_resource_name(action_type),
            "action_present": action_present,
            "requires_consensus": bool(getattr(action, "requires_consensus", False))
            if action_present
            else False,
            "priority": str(action_priority),
            "decision_result_present": decision_present,
            "decision_approved": bool(getattr(decision_result, "approved", False)),
            "decision_id_present": bool(getattr(decision_result, "decision_id", "")),
            "consensus_mode": consensus_mode,
            "participation_rate": float(
                getattr(decision_result, "participation_rate", 0.0) or 0.0
            ),
            "votes_for": int(getattr(decision_result, "votes_for", 0) or 0),
            "votes_against": int(getattr(decision_result, "votes_against", 0) or 0),
            "votes_abstain": int(getattr(decision_result, "votes_abstain", 0) or 0),
            "parameters_redacted": True,
            "identity_values_redacted": True,
            "raw_context_values_redacted": True,
            "raw_result_values_redacted": True,
        }
        claim_gate = cls._action_claim_gate(
            action_type=action_type,
            success=success,
            simulated=simulated,
            action_present=action_present,
            decision_result=decision_result,
        )
        return SafeActuatorEvidenceMetadata.from_value(
            {
                "claim_gate": claim_gate,
                "cross_plane_claim_gate": cls._cross_plane_claim_gate(),
                "evidence": evidence,
                "source_agents": [_SERVICE_AGENT],
                "event_ids": [],
                "claim_boundary": claim_gate["claim_boundary"],
                "redacted": True,
            }
        )

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

    def _action_context(self, action: SwarmAction) -> Dict[str, Any]:
        return {
            "node_id": self.identity["node_id"],
            "action_id": action.action_id,
            "action_type": action.action_type,
            "description": action.description,
            "parameters": dict(action.parameters),
            "proposer_id": action.proposer_id,
            "requires_consensus": action.requires_consensus,
            "timeout_ms": action.timeout_ms,
            "priority": action.priority.value,
        }

    def _publish_execution_event(
        self,
        event_type: EventType,
        *,
        stage: str,
        action: SwarmAction,
        context: Dict[str, Any],
        result: Optional[Dict[str, Any]] = None,
        reason: str = "",
        policy_decision: Any = None,
        safe_actuator_evidence_metadata: Optional[SafeActuatorEvidenceMetadata] = None,
    ) -> Optional[str]:
        if self.event_bus is None:
            return None
        action_resource = self._action_resource_name(action.action_type)
        payload = {
            "component": "swarm.intelligence.mapek",
            "stage": stage,
            "action_id": action.action_id,
            "action_type": action.action_type,
            "action_resource": action_resource,
            "resource": f"swarm:mapek:{action_resource}",
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
            "safe_actuator": True,
            "safe_actuator_evidence_metadata": (
                safe_actuator_evidence_metadata.to_dict()
                if safe_actuator_evidence_metadata is not None
                else SafeActuatorResult(success=False).to_dict()
            ),
            "claim_boundary": MAPEK_CLAIM_BOUNDARY,
        }
        try:
            event = self.event_bus.publish(event_type, self.source_agent, payload, priority=7)
            return event.event_id
        except Exception as exc:
            logger.error("Failed to publish swarm MAPE-K event: %s", exc)
            return None

    def _evaluate_action_policy(self, action: SwarmAction) -> tuple[bool, Any, str]:
        if self.policy_engine is None:
            if self.require_policy:
                return False, None, "swarm MAPE-K policy engine is required but unavailable"
            return True, None, ""
        spiffe_id = self.identity.get("spiffe_id")
        if not spiffe_id:
            return False, None, "swarm MAPE-K SPIFFE identity is required for policy evaluation"
        action_resource = self._action_resource_name(action.action_type)
        try:
            decision = self.policy_engine.evaluate(
                spiffe_id,
                resource=f"swarm:mapek:{action_resource}",
                workload_type="swarm-mapek",
            )
        except Exception as exc:
            return False, None, f"swarm MAPE-K policy evaluation failed: {exc}"
        if not self._policy_allowed(decision):
            return False, decision, self._policy_reason(decision) or "swarm MAPE-K policy denied action"
        return True, decision, self._policy_reason(decision)

    async def _execute_safe_actuator(
        self,
        action_type: str,
        context: Dict[str, Any],
    ) -> SafeActuatorResult:
        raw = self.safe_actuator.execute(action_type, context)
        if asyncio.iscoroutine(raw):
            raw = await raw
        if isinstance(raw, SafeActuatorResult):
            return raw
        if isinstance(raw, dict):
            return SafeActuatorResult.from_value(raw)
        return SafeActuatorResult(
            success=bool(raw),
            reason="" if raw else "safe actuator returned false",
        )

    async def _propose_action_internal(
        self,
        _action_type: str,
        context: Dict[str, Any],
    ) -> SafeActuatorResult:
        action = context.get("_action")
        if not isinstance(action, SwarmAction):
            return SafeActuatorResult(
                False,
                "swarm MAPE-K action is missing",
                metadata=self._safe_actuator_evidence_metadata(
                    action_type=_action_type,
                    context=context,
                    success=False,
                ).to_dict(),
            )
        decision_result = await self.swarm.propose_action(action)
        self._last_decision_result = decision_result
        evidence_metadata = self._safe_actuator_evidence_metadata(
            action_type=_action_type,
            context=context,
            success=decision_result.approved,
            decision_result=decision_result,
        )
        if decision_result.approved:
            return SafeActuatorResult(
                True,
                decision_result.reason,
                metadata=evidence_metadata.to_dict(),
            )
        return SafeActuatorResult(
            False,
            decision_result.reason or "swarm consensus rejected MAPE-K action",
            metadata=evidence_metadata.to_dict(),
        )

    async def monitor(self) -> Dict[str, Any]:
        """Collect swarm state and metrics.

        When a mesh_detector is configured, also collects live mesh topology
        snapshots for GNN-based anomaly detection in the analyze phase.
        """
        status = await self.swarm.get_consensus_status()
        nodes = self.swarm.get_nodes()

        metrics = {
            "timestamp": datetime.utcnow().isoformat(),
            "consensus_status": status.value,
            "active_nodes": sum(1 for n in nodes if n.is_active),
            "total_nodes": len(nodes),
            "pending_decisions": len(self.swarm._pending_decisions),
        }

        # Collect mesh topology snapshot when a detector is available
        self._mesh_topology_cache = None
        if self.mesh_detector is not None:
            try:
                mesh_data = None
                if hasattr(self.swarm, "get_mesh_topology"):
                    mesh_data = self.swarm.get_mesh_topology()
                elif hasattr(self.swarm, "network"):
                    net = self.swarm.network
                    mesh_data = {
                        "node_features": getattr(net, "node_features", []),
                        "edge_index": getattr(net, "edge_index", []),
                    }
                if mesh_data is not None:
                    self._mesh_topology_cache = mesh_data
                    metrics["mesh_topology_collected"] = True
                    metrics["mesh_num_nodes"] = len(
                        mesh_data.get("node_features", []))
                    metrics["mesh_num_edges"] = len(
                        mesh_data.get("edge_index", []))
                else:
                    metrics["mesh_topology_collected"] = False
            except Exception as exc:
                logger.warning("Failed to collect mesh topology: %s", exc)
                metrics["mesh_topology_collected"] = False

        self._metrics_history.append(metrics)
        if len(self._metrics_history) > 100:
            self._metrics_history = self._metrics_history[-100:]

        return metrics

    def analyze(self, metrics: Dict[str, Any]) -> List[Dict[str, Any]]:
        """Analyze metrics for anomalies and opportunities.

        Runs both rule-based checks (availability, backlog) and, when a
        mesh_detector is configured, GNN-based anomaly detection on mesh
        network topology.
        """
        anomalies = []

        # ── Rule-based checks ──────────────────────────────────────

        # Check node availability
        active_ratio = metrics.get("active_nodes", 0) / max(metrics.get("total_nodes", 1), 1)
        if active_ratio < 0.5:
            anomalies.append({
                "type": "low_availability",
                "severity": "high",
                "value": active_ratio,
                "source": "mapek_rules",
            })

        # Check pending decisions backlog
        pending = metrics.get("pending_decisions", 0)
        if pending > 10:
            anomalies.append({
                "type": "decision_backlog",
                "severity": "medium",
                "value": pending,
                "source": "mapek_rules",
            })

        # ── GNN-based mesh anomaly detection ───────────────────────
        if self.mesh_detector is not None and self._mesh_topology_cache is not None:
            try:
                self._analyze_mesh_topology(anomalies)
            except Exception as exc:
                logger.warning("Mesh GNN analysis failed: %s", exc)

        return anomalies

    def _analyze_mesh_topology(self, anomalies: List[Dict[str, Any]]) -> None:
        """Run GNN-based anomaly detection on cached mesh topology."""
        mesh = self._mesh_topology_cache
        if not mesh:
            return

        node_features = mesh.get("node_features", [])
        edge_index = mesh.get("edge_index", [])
        if not node_features or not edge_index:
            return

        # Run batch prediction
        import time
        t0 = time.time()
        try:
            predictions = self.mesh_detector.predict_topology(node_features, edge_index)
        except Exception as exc:
            logger.warning("MeshGNN prediction failed: %s", exc)
            return

        inference_ms = (time.time() - t0) * 1000.0
        logger.info("Mesh GNN inference on %d nodes in %.1fms",
                    len(predictions), inference_ms)

        # Aggregate per-node predictions into topology-level anomalies
        anomaly_nodes = [p for p in predictions if p.is_anomaly]
        if not anomaly_nodes:
            return

        # Count anomaly scores to classify the event type
        scores = [p.anomaly_score for p in anomaly_nodes]
        mean_score = sum(scores) / max(len(scores), 1)
        anomaly_ratio = len(anomaly_nodes) / max(len(predictions), 1)

        if anomaly_ratio > 0.4:
            # Widespread anomalies → possible cascade or partition
            anomalies.append({
                "type": "mesh_topology_instability",
                "severity": "high",
                "value": anomaly_ratio,
                "mean_score": mean_score,
                "anomalous_nodes": len(anomaly_nodes),
                "total_nodes": len(predictions),
                "inference_ms": round(inference_ms, 2),
                "source": "mesh_gnn",
            })
        elif anomaly_ratio > 0.15:
            anomalies.append({
                "type": "mesh_link_degradation_cluster",
                "severity": "medium",
                "value": anomaly_ratio,
                "mean_score": mean_score,
                "anomalous_nodes": len(anomaly_nodes),
                "total_nodes": len(predictions),
                "inference_ms": round(inference_ms, 2),
                "source": "mesh_gnn",
            })
        else:
            # Isolated anomalies — individual node/link issues
            worst = max(anomaly_nodes, key=lambda p: p.anomaly_score)
            anomalies.append({
                "type": "mesh_node_anomaly",
                "severity": "low",
                "value": worst.anomaly_score,
                "node_id": worst.node_id,
                "anomalous_nodes": len(anomaly_nodes),
                "total_nodes": len(predictions),
                "inference_ms": round(inference_ms, 2),
                "source": "mesh_gnn",
            })

    def plan(self, anomalies: List[Dict[str, Any]]) -> List[SwarmAction]:
        """Generate action proposals based on anomalies."""
        actions = []

        for anomaly in anomalies:
            a_type = anomaly["type"]
            a_severity = anomaly.get("severity", "low")

            # ── Rule-based anomaly types ───────────────────────────
            if a_type == "low_availability":
                actions.append(SwarmAction(
                    action_type="healing",
                    description="Initiate node recovery procedure",
                    parameters=anomaly,
                    priority=DecisionPriority.HIGH,
                ))
            elif a_type == "decision_backlog":
                actions.append(SwarmAction(
                    action_type="scaling",
                    description="Request additional decision capacity",
                    parameters=anomaly,
                    priority=DecisionPriority.NORMAL,
                ))

            # ── GNN-based mesh anomaly types ───────────────────────
            elif a_type == "mesh_topology_instability":
                severity = a_severity or "high"
                actions.append(SwarmAction(
                    action_type="mesh_isolation",
                    description=(
                        f"Mesh topology instability detected: "
                        f"{anomaly.get('anomalous_nodes', '?')} anomalous nodes "
                        f"(mean score {anomaly.get('mean_score', 0):.2f})"
                    ),
                    parameters=anomaly,
                    priority=DecisionPriority.HIGH if severity == "high" else DecisionPriority.NORMAL,
                ))
            elif a_type == "mesh_link_degradation_cluster":
                actions.append(SwarmAction(
                    action_type="redundancy",
                    description=(
                        f"Link degradation cluster: "
                        f"{anomaly.get('anomalous_nodes', '?')} nodes affected"
                    ),
                    parameters=anomaly,
                    priority=DecisionPriority.NORMAL,
                ))
            elif a_type == "mesh_node_anomaly":
                actions.append(SwarmAction(
                    action_type="inspection",
                    description=(
                        f"Suspicious node: {anomaly.get('node_id', '?')} "
                        f"(score {anomaly.get('value', 0):.2f})"
                    ),
                    parameters=anomaly,
                    priority=DecisionPriority.LOW,
                ))

        return actions

    async def execute(self, action: SwarmAction) -> Dict[str, Any]:
        """Execute an approved action."""
        result = {
            "action_id": action.action_id,
            "action_type": action.action_type,
            "executed_at": datetime.utcnow().isoformat(),
            "success": False,
            "safe_actuator": True,
        }
        context = self._action_context(action)

        try:
            self._last_decision_result = None
            self._publish_execution_event(
                EventType.COORDINATION_REQUEST,
                stage="received",
                action=action,
                context=context,
            )

            policy_allowed, policy_decision, policy_reason = (
                self._evaluate_action_policy(action)
            )
            if not policy_allowed:
                result.update({
                    "error": policy_reason,
                    "policy_required": True,
                    "matched_rules": self._policy_rules(policy_decision),
                })
                self._publish_execution_event(
                    EventType.TASK_BLOCKED,
                    stage="policy_denied",
                    action=action,
                    context=context,
                    result=result,
                    reason=policy_reason,
                    policy_decision=policy_decision,
                )
                return result

            self._publish_execution_event(
                EventType.PIPELINE_STAGE_START,
                stage="actuator_start",
                action=action,
                context=context,
                reason=policy_reason,
                policy_decision=policy_decision,
            )

            actuator_context = dict(context)
            actuator_context["_action"] = action
            actuator_result = await self._execute_safe_actuator(
                action.action_type,
                actuator_context,
            )
            result["safe_actuator_evidence_metadata"] = (
                actuator_result.evidence_metadata.to_dict()
            )
            if self._last_decision_result is not None:
                result["decision"] = self._last_decision_result.to_dict()

            if actuator_result.simulated:
                reason = actuator_result.reason or "safe actuator returned simulated result"
                result.update({"error": reason, "simulated": True})
                self._publish_execution_event(
                    EventType.TASK_FAILED,
                    stage="actuator_simulated",
                    action=action,
                    context=context,
                    result=result,
                    reason=reason,
                    policy_decision=policy_decision,
                    safe_actuator_evidence_metadata=actuator_result.evidence_metadata,
                )
            elif actuator_result.success:
                result.update({
                    "success": True,
                    "reason": actuator_result.reason or policy_reason,
                    "simulated": actuator_result.simulated,
                })
                self._publish_execution_event(
                    EventType.PIPELINE_STAGE_END,
                    stage="actuator_completed",
                    action=action,
                    context=context,
                    result=result,
                    reason=actuator_result.reason or policy_reason,
                    policy_decision=policy_decision,
                    safe_actuator_evidence_metadata=actuator_result.evidence_metadata,
                )
            else:
                reason = actuator_result.reason or "swarm MAPE-K safe actuator failed"
                result.update({"error": reason, "simulated": actuator_result.simulated})
                self._publish_execution_event(
                    EventType.TASK_FAILED,
                    stage="actuator_failed",
                    action=action,
                    context=context,
                    result=result,
                    reason=reason,
                    policy_decision=policy_decision,
                    safe_actuator_evidence_metadata=actuator_result.evidence_metadata,
                )
        except Exception as e:
            result["error"] = str(e)
            self._publish_execution_event(
                EventType.TASK_FAILED,
                stage="actuator_error",
                action=action,
                context=context,
                result=result,
                reason=str(e),
            )
        finally:
            self._action_history.append(result)
            if len(self._action_history) > 50:
                self._action_history = self._action_history[-50:]

        return result

    def learn(self, action: SwarmAction, result: Dict[str, Any]) -> None:
        """Learn from action outcomes.

        When a mesh_detector with experience replay is configured, the
        learn phase pushes the topology snapshot into the buffer and
        periodically triggers fine-tuning.
        """
        action_type = action.action_type
        if action_type not in self._learning_data:
            self._learning_data[action_type] = {
                "total": 0,
                "successful": 0,
            }

        self._learning_data[action_type]["total"] += 1
        if result.get("success"):
            self._learning_data[action_type]["successful"] += 1

        # Push topology snapshot into experience replay buffer
        if self.mesh_detector is not None and self._mesh_topology_cache is not None:
            try:
                mesh = self._mesh_topology_cache
                node_features = mesh.get("node_features", [])
                edge_index = mesh.get("edge_index", [])
                if node_features and edge_index:
                    # Build a minimal snapshot from the cached topology
                    class _LearnSnapshot:
                        def __init__(self, nf, ei):
                            self.node_features = nf
                            self.edge_index = ei
                            num_nodes = len(nf)
                            self.num_nodes = num_nodes
                            # Use the predictions as pseudo-labels when
                            # no ground-truth labels are available
                            self.labels = [0.0] * num_nodes

                    snap = _LearnSnapshot(node_features, edge_index)
                    self.mesh_detector.push_experience(snap)

                    # Periodically fine-tune every 20 successful actions
                    total = self._learning_data[action_type]["total"]
                    if total > 0 and total % 20 == 0 and result.get("success"):
                        hist = self.mesh_detector.fine_tune(verbose=False)
                        if hist.epochs:
                            logger.info(
                                f"Online fine-tune: {len(hist.epochs)} steps, "
                                f"loss {hist.losses[-1]:.4f}, "
                                f"acc {hist.accuracies[-1]:.1%}")
            except Exception as exc:
                logger.warning("Failed to push experience in learn phase: %s", exc)

    def get_success_rate(self, action_type: str) -> float:
        """Get success rate for an action type."""
        data = self._learning_data.get(action_type, {})
        total = data.get("total", 0)
        if total == 0:
            return 0.5  # Unknown
        return data.get("successful", 0) / total

