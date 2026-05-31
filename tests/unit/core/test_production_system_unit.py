"""Unit tests for production system orchestration."""

import json
from types import SimpleNamespace

from src.core import production_system
from src.libx0t.core import production_system as libx0t_production_system


class _FakeCardinality:
    def record_metric_sample(self, *_args, **_kwargs):
        return None

    def get_cardinality_report(self):
        return {"total_unique_metrics": 10, "total_cardinality": 1000}


class _FakeLatencyTracker:
    def record(self, *_args, **_kwargs):
        return None


class _FakePerfTuner:
    latency_tracker = _FakeLatencyTracker()

    def analyze_performance(self):
        return {"ok": True}


class _FakeHardening:
    request_auditor = SimpleNamespace(log_request=lambda *a, **k: None)

    def get_security_status(self):
        return {"suspicious_patterns": []}


class _FakeResilientExecutor:
    def get_stats(self):
        return {
            "success_rate": 0.95,
            "circuit_breaker_state": "closed",
            "bulkhead_status": {"utilization": 0.1},
        }


def _inject_fakes(self):
    self.cardinality_optimizer = _FakeCardinality()
    self.performance_tuner = _FakePerfTuner()
    self.hardening_manager = _FakeHardening()
    self.resilient_executor = _FakeResilientExecutor()


def _write_current_evidence(root, *, gaps=None, next_actions=None):
    architecture = root / "docs" / "architecture"
    architecture.mkdir(parents=True, exist_ok=True)
    (architecture / "CURRENT_ACTIVE_GOAL_GAP_AUDIT.md").write_text(
        "# Current Active Goal Gap Audit\n",
        encoding="utf-8",
    )
    payload = {
        "status": "working_map_not_production_completion_proof",
        "planes": {
            "data_plane": {},
            "control_plane": {},
            "trust_plane": {},
            "evidence_plane": {},
            "economy_plane": {},
        },
        "current_gaps": gaps or [],
        "next_actions": next_actions or [],
    }
    (architecture / "CURRENT_CROSS_PLANE_EVIDENCE_MAP.json").write_text(
        json.dumps(payload),
        encoding="utf-8",
    )


def _allowed_cross_plane_gate(*, surface, root, claims):
    return {
        "schema": "x0tta6bl4.cross_plane_proof_gate.v1",
        "decision": "CROSS_PLANE_CLAIMS_ALLOWED",
        "allowed": True,
        "available": True,
        "surface": surface,
        "requested_claim_ids": list(claims),
        "claim_results": [
            {"claim_id": claim_id, "allowed": True} for claim_id in claims
        ],
        "claim_boundary": "test cross-plane gate",
    }


def _blocked_cross_plane_gate(*, surface, root, claims):
    return {
        "schema": "x0tta6bl4.cross_plane_proof_gate.v1",
        "decision": "CROSS_PLANE_CLAIMS_BLOCKED",
        "allowed": False,
        "available": True,
        "surface": surface,
        "requested_claim_ids": list(claims),
        "blockers": ["production_readiness_imported_artifact_not_verified"],
        "claim_results": [
            {
                "claim_id": "production_readiness",
                "allowed": False,
                "blockers": ["production_readiness_imported_artifact_not_verified"],
            }
        ],
        "claim_boundary": "test cross-plane gate blocked",
    }


def test_record_request_updates_counters(monkeypatch):
    monkeypatch.setattr(
        production_system.ProductionSystem, "_import_components", _inject_fakes
    )
    ps = production_system.ProductionSystem()

    ps.record_request("GET", "/health", 200, 20.0, {"client_ip": "127.0.0.1"})
    ps.record_request("POST", "/x", 500, 30.0, {"client_ip": "127.0.0.2"})

    assert ps.request_count == 2
    assert ps.error_count == 1
    assert ps.latency_sum == 50.0


def test_get_system_health_contains_expected_sections(monkeypatch):
    monkeypatch.setattr(
        production_system.ProductionSystem, "_import_components", _inject_fakes
    )
    ps = production_system.ProductionSystem()
    ps.record_request("GET", "/health", 200, 20.0, {"client_ip": "127.0.0.1"})

    health = ps.get_system_health()

    assert "health_score" in health
    assert health["requests"]["total"] == 1
    assert health["cardinality"]["status"] == "healthy"
    assert health["resilience"]["circuit_breaker_state"] == "closed"


def test_get_readiness_level_thresholds(monkeypatch):
    monkeypatch.setattr(
        production_system.ProductionSystem, "_import_components", _inject_fakes
    )
    ps = production_system.ProductionSystem()

    assert ps._get_readiness_level(96) == "PRODUCTION_READY"
    assert ps._get_readiness_level(90) == "NEAR_PRODUCTION"
    assert ps._get_readiness_level(70) == "STAGING_READY"
    assert ps._get_readiness_level(50) == "DEVELOPMENT"


def test_readiness_report_blocks_production_claim_with_open_current_evidence(
    monkeypatch, tmp_path
):
    monkeypatch.setattr(
        production_system.ProductionSystem, "_import_components", _inject_fakes
    )
    monkeypatch.setattr(
        production_system,
        "readiness_cross_plane_claim_gate_metadata",
        _allowed_cross_plane_gate,
    )
    _write_current_evidence(
        tmp_path,
        gaps=[{"id": "dataplane-proof-missing"}],
        next_actions=[{"id": "collect-dataplane-proof"}],
    )
    ps = production_system.ProductionSystem(current_evidence_root=tmp_path)

    report = ps.get_production_readiness_report()

    assert report["raw_health_readiness_level"] == "PRODUCTION_READY"
    assert report["readiness_level"] == (
        "PRODUCTION_READY_BLOCKED_BY_CURRENT_EVIDENCE"
    )
    assert report["production_readiness_claim_allowed"] is False
    assert report["current_evidence_context"]["included"] is True
    assert report["current_evidence_context"]["current_gap_count"] == 1
    assert report["current_evidence_context"]["next_action_count"] == 1
    assert report["current_evidence_context"]["open_gap_ids"] == [
        "dataplane-proof-missing"
    ]
    assert report["cross_plane_proof_gate"]["allowed"] is True
    assert report["claim_boundary"] == production_system.PRODUCTION_SYSTEM_CLAIM_BOUNDARY
    assert report["gaps_remaining"]


def test_readiness_report_allows_production_claim_only_with_clear_current_evidence(
    monkeypatch, tmp_path
):
    monkeypatch.setattr(
        production_system.ProductionSystem, "_import_components", _inject_fakes
    )
    monkeypatch.setattr(
        production_system,
        "readiness_cross_plane_claim_gate_metadata",
        _allowed_cross_plane_gate,
    )
    _write_current_evidence(tmp_path)
    ps = production_system.ProductionSystem(current_evidence_root=tmp_path)

    report = ps.get_production_readiness_report()

    assert report["raw_health_readiness_level"] == "PRODUCTION_READY"
    assert report["readiness_level"] == "PRODUCTION_READY"
    assert report["production_readiness_claim_allowed"] is True
    assert report["current_evidence_context"]["current_gap_count"] == 0
    assert report["current_evidence_context"]["next_action_count"] == 0
    assert report["cross_plane_proof_gate"]["allowed"] is True
    assert report["cross_plane_proof_gate"]["surface"] == "production_system.readiness"
    assert report["gaps_remaining"] == []


def test_readiness_report_allows_production_claim_with_non_blocking_tracked_gap(
    monkeypatch, tmp_path
):
    monkeypatch.setattr(
        production_system.ProductionSystem, "_import_components", _inject_fakes
    )
    monkeypatch.setattr(
        production_system,
        "readiness_cross_plane_claim_gate_metadata",
        _allowed_cross_plane_gate,
    )
    _write_current_evidence(
        tmp_path,
        gaps=[{"id": "tracked-local-risk", "blocks_real_readiness": False}],
    )
    ps = production_system.ProductionSystem(current_evidence_root=tmp_path)

    report = ps.get_production_readiness_report()

    assert report["readiness_level"] == "PRODUCTION_READY"
    assert report["production_readiness_claim_allowed"] is True
    assert report["current_evidence_context"]["current_gap_count"] == 0
    assert report["current_evidence_context"]["tracked_gap_count"] == 1
    assert report["current_evidence_context"]["non_blocking_gap_ids"] == [
        "tracked-local-risk"
    ]


def test_readiness_report_blocks_production_claim_when_cross_plane_gate_blocks(
    monkeypatch, tmp_path
):
    monkeypatch.setattr(
        production_system.ProductionSystem, "_import_components", _inject_fakes
    )
    monkeypatch.setattr(
        production_system,
        "readiness_cross_plane_claim_gate_metadata",
        _blocked_cross_plane_gate,
    )
    _write_current_evidence(tmp_path)
    ps = production_system.ProductionSystem(current_evidence_root=tmp_path)

    report = ps.get_production_readiness_report()

    assert report["raw_health_readiness_level"] == "PRODUCTION_READY"
    assert report["readiness_level"] == (
        "PRODUCTION_READY_BLOCKED_BY_CROSS_PLANE_PROOF_GATE"
    )
    assert report["production_readiness_claim_allowed"] is False
    assert report["current_evidence_context"]["current_gap_count"] == 0
    assert report["cross_plane_proof_gate"]["allowed"] is False
    assert "production_readiness_imported_artifact_not_verified" in (
        report["cross_plane_proof_gate"]["blockers"]
    )
    assert report["gaps_remaining"] == [
        "Cross-plane proof gate did not allow production-readiness promotion"
    ]


def test_libx0t_readiness_report_uses_same_current_evidence_gate(monkeypatch, tmp_path):
    monkeypatch.setattr(
        libx0t_production_system.ProductionSystem,
        "_import_components",
        _inject_fakes,
    )
    monkeypatch.setattr(
        libx0t_production_system,
        "readiness_cross_plane_claim_gate_metadata",
        _allowed_cross_plane_gate,
    )
    _write_current_evidence(
        tmp_path,
        gaps=[{"id": "namespace-production-claim-gate"}],
    )
    ps = libx0t_production_system.ProductionSystem(current_evidence_root=tmp_path)

    report = ps.get_production_readiness_report()

    assert report["readiness_level"] == (
        "PRODUCTION_READY_BLOCKED_BY_CURRENT_EVIDENCE"
    )
    assert report["production_readiness_claim_allowed"] is False
    assert report["cross_plane_proof_gate"]["allowed"] is True
    assert report["claim_boundary"] == (
        libx0t_production_system.PRODUCTION_SYSTEM_CLAIM_BOUNDARY
    )


def test_get_production_system_singleton(monkeypatch):
    monkeypatch.setattr(
        production_system.ProductionSystem, "_import_components", _inject_fakes
    )
    production_system._system = None

    s1 = production_system.get_production_system()
    s2 = production_system.get_production_system()

    assert s1 is s2
