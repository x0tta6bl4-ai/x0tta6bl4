import json
import logging
from dataclasses import dataclass
from datetime import datetime
from pathlib import Path
from typing import Any

try:
    from src.api.cross_plane_claim_gate import readiness_cross_plane_claim_gate_metadata
except Exception:  # pragma: no cover - runtime images may omit ops scripts
    readiness_cross_plane_claim_gate_metadata = None

logger = logging.getLogger(__name__)

CURRENT_CROSS_PLANE_MAP = Path("docs/architecture/CURRENT_CROSS_PLANE_EVIDENCE_MAP.json")
CURRENT_ACTIVE_AUDIT = Path("docs/architecture/CURRENT_ACTIVE_GOAL_GAP_AUDIT.md")
REQUIRED_CROSS_PLANE_PLANES = {
    "data_plane",
    "control_plane",
    "trust_plane",
    "evidence_plane",
    "economy_plane",
}
PRODUCTION_SYSTEM_CROSS_PLANE_CLAIMS = (
    "production_readiness",
    "dataplane_delivery",
    "traffic_delivery",
    "customer_traffic",
    "trust_finality",
    "settlement_finality",
    "dpi_bypass",
)
PRODUCTION_SYSTEM_CLAIM_BOUNDARY = (
    "ProductionSystem readiness is a local health/control-plane signal only. "
    "It may not claim production readiness unless the current cross-plane "
    "evidence map and active goal audit are present, all required planes are "
    "covered, there are zero current gaps or next actions, and the reusable "
    "cross-plane proof gate allows the requested strong claims."
)


@dataclass
class ProductionMetrics:
    timestamp: datetime
    uptime_seconds: float
    request_count: int
    error_count: int
    avg_latency_ms: float
    cardinality_health: float
    circuit_breaker_state: str
    memory_usage_mb: float
    active_connections: int


class ProductionSystem:
    def __init__(self, current_evidence_root=None):
        self.start_time = datetime.utcnow()
        self.request_count = 0
        self.error_count = 0
        self.latency_sum = 0.0
        self.current_evidence_root = Path(current_evidence_root or ".")

        self._import_components()

    def _import_components(self):
        try:
            from src.optimization.performance_tuner import get_performance_tuner
            from src.optimization.prometheus_cardinality_optimizer import get_cardinality_optimizer
            from src.resilience.advanced_patterns import get_resilient_executor
            from src.security.production_hardening import get_hardening_manager

            self.cardinality_optimizer = get_cardinality_optimizer()
            self.performance_tuner = get_performance_tuner()
            self.hardening_manager = get_hardening_manager()
            self.resilient_executor = get_resilient_executor()

            logger.info("All production components initialized")
        except Exception as e:
            logger.error(f"Failed to initialize components: {e}")
            raise

    def record_request(
        self,
        method: str,
        path: str,
        status_code: int,
        duration_ms: float,
        labels: dict[str, str],
    ) -> None:
        self.request_count += 1
        self.latency_sum += duration_ms

        if status_code >= 400:
            self.error_count += 1

        self.cardinality_optimizer.record_metric_sample(
            f"http_{method.lower()}", labels
        )

        self.performance_tuner.latency_tracker.record(
            f"request_{method}_{path}", duration_ms, metadata={"status": status_code}
        )

        self.hardening_manager.request_auditor.log_request(
            method, path, labels.get("client_ip", "unknown"), status_code, duration_ms
        )

    def get_system_health(self) -> dict[str, Any]:
        uptime = (datetime.utcnow() - self.start_time).total_seconds()

        self.performance_tuner.analyze_performance()
        cardinality_report = self.cardinality_optimizer.get_cardinality_report()
        security_status = self.hardening_manager.get_security_status()
        executor_stats = self.resilient_executor.get_stats()

        error_rate = (
            self.error_count / self.request_count if self.request_count > 0 else 0
        )

        avg_latency = (
            self.latency_sum / self.request_count if self.request_count > 0 else 0
        )

        health_score = self._calculate_health_score(
            error_rate,
            cardinality_report["total_cardinality"],
            executor_stats.get("success_rate", 1.0),
        )

        return {
            "timestamp": datetime.utcnow().isoformat(),
            "uptime_seconds": uptime,
            "health_score": health_score,
            "requests": {
                "total": self.request_count,
                "errors": self.error_count,
                "error_rate": error_rate,
                "avg_latency_ms": avg_latency,
            },
            "cardinality": {
                "total_metrics": cardinality_report["total_unique_metrics"],
                "total_cardinality": cardinality_report["total_cardinality"],
                "status": (
                    "healthy"
                    if cardinality_report["total_cardinality"] < 50000
                    else "warning"
                ),
            },
            "resilience": {
                "circuit_breaker_state": executor_stats.get("circuit_breaker_state"),
                "success_rate": executor_stats.get("success_rate", 1.0),
                "bulkhead_utilization": executor_stats.get("bulkhead_status", {}).get(
                    "utilization", 0
                ),
            },
            "security": {
                "suspicious_patterns": len(
                    security_status.get("suspicious_patterns", [])
                )
            },
        }

    def _calculate_health_score(
        self, error_rate: float, cardinality: int, success_rate: float
    ) -> float:
        error_penalty = min(error_rate * 100, 30)
        cardinality_penalty = min((cardinality / 50000) * 20, 20)
        resilience_bonus = max(success_rate * 10, 0)

        base_score = 100.0
        final_score = (
            base_score - error_penalty - cardinality_penalty + resilience_bonus
        )

        return max(0, min(100, final_score))

    def get_production_readiness_report(self) -> dict[str, Any]:
        health = self.get_system_health()
        raw_readiness_level = self._get_readiness_level(health["health_score"])
        current_evidence = self._current_evidence_context()
        current_evidence_allows = self._current_evidence_allows_production_claim(
            current_evidence
        )
        cross_plane_proof_gate = self._cross_plane_proof_gate_context()
        cross_plane_proof_gate_allows = (
            cross_plane_proof_gate.get("allowed") is True
        )
        production_claim_allowed = (
            raw_readiness_level == "PRODUCTION_READY"
            and current_evidence_allows
            and cross_plane_proof_gate_allows
        )
        readiness_level = raw_readiness_level
        if raw_readiness_level == "PRODUCTION_READY" and not production_claim_allowed:
            if not current_evidence_allows:
                readiness_level = "PRODUCTION_READY_BLOCKED_BY_CURRENT_EVIDENCE"
            else:
                readiness_level = "PRODUCTION_READY_BLOCKED_BY_CROSS_PLANE_PROOF_GATE"
        gaps_remaining = (
            [
                "Fine-grained SLA tracking",
                "Advanced ML-based anomaly detection",
                "Distributed tracing optimization",
            ]
            if health["health_score"] < 95
            else []
        )
        if not current_evidence_allows:
            gaps_remaining.append(
                "Current cross-plane evidence context is missing, incomplete, or still has open gaps/next actions"
            )
        if not cross_plane_proof_gate_allows:
            gaps_remaining.append(
                "Cross-plane proof gate did not allow production-readiness promotion"
            )

        return {
            "timestamp": datetime.utcnow().isoformat(),
            "overall_score": health["health_score"],
            "claim_boundary": PRODUCTION_SYSTEM_CLAIM_BOUNDARY,
            "components": {
                "cardinality_management": (
                    "operational"
                    if health["cardinality"]["status"] == "healthy"
                    else "warning"
                ),
                "performance_monitoring": "operational",
                "security_controls": "operational",
                "resilience_patterns": "operational",
            },
            "metrics": health,
            "raw_health_readiness_level": raw_readiness_level,
            "readiness_level": readiness_level,
            "production_readiness_claim_allowed": production_claim_allowed,
            "current_evidence_context": current_evidence,
            "cross_plane_proof_gate": cross_plane_proof_gate,
            "gaps_remaining": gaps_remaining,
        }

    def _get_readiness_level(self, score: float) -> str:
        if score >= 95:
            return "PRODUCTION_READY"
        elif score >= 85:
            return "NEAR_PRODUCTION"
        elif score >= 70:
            return "STAGING_READY"
        else:
            return "DEVELOPMENT"

    def _current_evidence_context(self) -> dict[str, Any]:
        root = self.current_evidence_root
        map_path = root / CURRENT_CROSS_PLANE_MAP
        audit_path = root / CURRENT_ACTIVE_AUDIT
        context: dict[str, Any] = {
            "included": map_path.exists() and audit_path.exists(),
            "source": "docs/architecture",
            "cross_plane_map": str(CURRENT_CROSS_PLANE_MAP),
            "active_goal_audit": str(CURRENT_ACTIVE_AUDIT),
            "claim_boundary": (
                "ProductionSystem requires current cross-plane evidence context "
                "before allowing a production-readiness claim. This context is "
                "a gate, not production proof by itself."
            ),
        }
        if not map_path.exists() or not audit_path.exists():
            context.update(
                {
                    "status": "missing_current_evidence_context",
                    "current_gap_count": None,
                    "next_action_count": None,
                    "open_gap_ids": [],
                    "next_action_ids": [],
                    "required_planes_present": False,
                    "plane_ids": [],
                }
            )
            return context
        try:
            data = json.loads(map_path.read_text(encoding="utf-8"))
        except Exception as exc:
            context.update(
                {
                    "status": "invalid_current_evidence_map",
                    "error": str(exc),
                    "current_gap_count": None,
                    "next_action_count": None,
                    "open_gap_ids": [],
                    "next_action_ids": [],
                    "required_planes_present": False,
                    "plane_ids": [],
                }
            )
            return context

        gaps = data.get("current_gaps")
        if not isinstance(gaps, list):
            gaps = []
        blocking_gaps = [
            item
            for item in gaps
            if isinstance(item, dict) and item.get("blocks_real_readiness") is not False
        ]
        non_blocking_gaps = [
            item
            for item in gaps
            if isinstance(item, dict) and item.get("blocks_real_readiness") is False
        ]
        next_actions = data.get("next_actions")
        if not isinstance(next_actions, list):
            next_actions = []
        planes = data.get("planes")
        plane_ids = set(planes) if isinstance(planes, dict) else set()
        context.update(
            {
                "status": data.get("status"),
                "current_gap_count": len(blocking_gaps),
                "tracked_gap_count": len([item for item in gaps if isinstance(item, dict)]),
                "non_blocking_gap_count": len(non_blocking_gaps),
                "next_action_count": len(next_actions),
                "open_gap_ids": [
                    item.get("id")
                    for item in blocking_gaps
                    if item.get("id")
                ],
                "non_blocking_gap_ids": [
                    item.get("id")
                    for item in non_blocking_gaps
                    if item.get("id")
                ],
                "next_action_ids": [
                    item.get("id")
                    for item in next_actions
                    if isinstance(item, dict) and item.get("id")
                ],
                "required_planes_present": REQUIRED_CROSS_PLANE_PLANES.issubset(
                    plane_ids
                ),
                "plane_ids": sorted(plane_ids),
            }
        )
        return context

    def _current_evidence_allows_production_claim(
        self, context: dict[str, Any]
    ) -> bool:
        return bool(
            context.get("included") is True
            and context.get("status") == "working_map_not_production_completion_proof"
            and context.get("required_planes_present") is True
            and context.get("current_gap_count") == 0
            and context.get("next_action_count") == 0
        )

    def _cross_plane_proof_gate_context(self) -> dict[str, Any]:
        requested_claims = list(PRODUCTION_SYSTEM_CROSS_PLANE_CLAIMS)
        surface = "production_system.readiness"
        if readiness_cross_plane_claim_gate_metadata is None:
            return {
                "schema": "x0tta6bl4.cross_plane_proof_gate.v1",
                "decision": "CROSS_PLANE_CLAIMS_BLOCKED",
                "allowed": False,
                "available": False,
                "surface": surface,
                "requested_claim_ids": requested_claims,
                "blockers": ["cross_plane_proof_gate_unavailable"],
                "claim_boundary": (
                    "Cross-plane proof gate unavailable; ProductionSystem must "
                    "not promote local health as production readiness."
                ),
            }
        try:
            gate = readiness_cross_plane_claim_gate_metadata(
                surface=surface,
                root=self.current_evidence_root,
                claims=PRODUCTION_SYSTEM_CROSS_PLANE_CLAIMS,
            )
        except Exception as exc:
            return {
                "schema": "x0tta6bl4.cross_plane_proof_gate.v1",
                "decision": "CROSS_PLANE_CLAIMS_BLOCKED",
                "allowed": False,
                "available": False,
                "surface": surface,
                "requested_claim_ids": requested_claims,
                "blockers": [f"cross_plane_proof_gate_error:{type(exc).__name__}"],
                "claim_boundary": (
                    "Cross-plane proof gate failed closed; ProductionSystem must "
                    "not promote local health as production readiness."
                ),
            }
        if not isinstance(gate, dict):
            return {
                "schema": "x0tta6bl4.cross_plane_proof_gate.v1",
                "decision": "CROSS_PLANE_CLAIMS_BLOCKED",
                "allowed": False,
                "available": False,
                "surface": surface,
                "requested_claim_ids": requested_claims,
                "blockers": ["cross_plane_proof_gate_invalid_response"],
                "claim_boundary": (
                    "Cross-plane proof gate returned invalid metadata; "
                    "ProductionSystem must not promote local health as production "
                    "readiness."
                ),
            }
        gate.setdefault("surface", surface)
        gate.setdefault("requested_claim_ids", requested_claims)
        gate.setdefault(
            "claim_boundary",
            (
                "ProductionSystem uses the reusable cross-plane proof gate before "
                "allowing production-readiness promotion from local health."
            ),
        )
        return gate


_system = None


def get_production_system() -> ProductionSystem:
    global _system
    if _system is None:
        _system = ProductionSystem()
    return _system


__all__ = [
    "ProductionMetrics",
    "ProductionSystem",
    "get_production_system",
]
