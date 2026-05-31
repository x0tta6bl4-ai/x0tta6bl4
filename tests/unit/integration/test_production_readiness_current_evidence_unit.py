import importlib.util
import json
import sys
from pathlib import Path


ROOT = Path(__file__).resolve().parents[3]


def _load_module():
    path = ROOT / "tests/integration/production_readiness.py"
    spec = importlib.util.spec_from_file_location("production_readiness_current_evidence", path)
    assert spec and spec.loader
    module = importlib.util.module_from_spec(spec)
    sys.modules[spec.name] = module
    spec.loader.exec_module(module)
    return module


def _write_current_evidence(
    root: Path,
    *,
    gaps: list[dict] | None = None,
    next_actions: list[dict] | None = None,
) -> None:
    architecture = root / "docs/architecture"
    architecture.mkdir(parents=True, exist_ok=True)
    (architecture / "CURRENT_ACTIVE_GOAL_GAP_AUDIT.md").write_text(
        "# Current Active Goal Gap Audit\n",
        encoding="utf-8",
    )
    (architecture / "CURRENT_CROSS_PLANE_EVIDENCE_MAP.json").write_text(
        json.dumps(
            {
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
        ),
        encoding="utf-8",
    )


def _write_cross_plane_proof_gate(
    root: Path,
    *,
    allowed: bool = True,
    blocked_claim_ids: set[str] | None = None,
    missing_claim_ids: set[str] | None = None,
    source_artifact_hashes_present: bool = True,
) -> None:
    blocked_claim_ids = blocked_claim_ids or set()
    missing_claim_ids = missing_claim_ids or set()
    required_claim_ids = (
        "production_readiness",
        "dataplane_delivery",
        "traffic_delivery",
        "customer_traffic",
        "settlement_finality",
        "dpi_bypass",
    )
    claim_results = []
    for claim_id in required_claim_ids:
        if claim_id in missing_claim_ids:
            continue
        claim_allowed = allowed and claim_id not in blocked_claim_ids
        claim_results.append(
            {
                "claim_id": claim_id,
                "allowed": claim_allowed,
                "blockers": [] if claim_allowed else ["test_blocker"],
            }
        )

    gate_allowed = allowed and not blocked_claim_ids and not missing_claim_ids
    path = root / ".tmp/validation-shards/cross-plane-proof-gate-current.json"
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(
        json.dumps(
            {
                "schema": "x0tta6bl4.cross_plane_proof_gate.v1",
                "decision": (
                    "CROSS_PLANE_CLAIMS_ALLOWED"
                    if gate_allowed
                    else "CROSS_PLANE_CLAIMS_BLOCKED"
                ),
                "allowed": gate_allowed,
                "claim_results": claim_results,
                "current_evidence_context": {
                    "source_artifact_hashes_present": source_artifact_hashes_present,
                },
            }
        ),
        encoding="utf-8",
    )


def _all_pass_validator(module, root: Path):
    validator = module.ProductionReadinessValidator(current_evidence_root=root)
    for item in validator.items:
        validator.set_item_status(item.name, module.ReadinessStatus.PASS)
    return validator


def test_production_readiness_checklist_blocks_without_current_evidence(tmp_path):
    module = _load_module()
    result = _all_pass_validator(module, tmp_path).validate()

    assert result["raw_checklist_ready"] is True
    assert result["current_evidence_gate_clear"] is False
    assert result["cross_plane_proof_gate_clear"] is False
    assert result["is_production_ready"] is False
    assert result["current_evidence_context"]["status"] == "missing_current_evidence_context"
    assert "cross_plane_proof_gate_missing" in result["cross_plane_proof_gate"]["blocker_ids"]


def test_production_readiness_checklist_blocks_on_open_current_evidence(tmp_path):
    module = _load_module()
    _write_current_evidence(
        tmp_path,
        gaps=[{"id": "external-dpi-proof-missing"}],
        next_actions=[{"id": "external-dpi-real-artifact-intake"}],
    )

    result = _all_pass_validator(module, tmp_path).validate()

    assert result["raw_checklist_ready"] is True
    assert result["current_evidence_gate_clear"] is False
    assert result["cross_plane_proof_gate_clear"] is False
    assert result["is_production_ready"] is False
    assert result["current_evidence_context"]["open_gap_ids"] == [
        "external-dpi-proof-missing"
    ]


def test_production_readiness_checklist_allows_ready_only_with_clear_current_evidence(
    tmp_path,
):
    module = _load_module()
    _write_current_evidence(tmp_path)
    _write_cross_plane_proof_gate(tmp_path)

    result = _all_pass_validator(module, tmp_path).validate()

    assert result["raw_checklist_ready"] is True
    assert result["current_evidence_gate_clear"] is True
    assert result["cross_plane_proof_gate_clear"] is True
    assert result["is_production_ready"] is True
    assert result["cross_plane_claim_gate"]["production_readiness_claim_allowed"] is True
    assert result["cross_plane_claim_gate"]["cross_plane_proof_gate_allowed"] is True
    assert result["not_verified_yet"] == []


def test_production_readiness_checklist_allows_non_blocking_tracked_gap(
    tmp_path,
):
    module = _load_module()
    _write_current_evidence(
        tmp_path,
        gaps=[{"id": "tracked-local-risk", "blocks_real_readiness": False}],
    )
    _write_cross_plane_proof_gate(tmp_path)

    result = _all_pass_validator(module, tmp_path).validate()

    assert result["current_evidence_gate_clear"] is True
    assert result["cross_plane_proof_gate_clear"] is True
    assert result["is_production_ready"] is True
    assert result["current_evidence_context"]["current_gap_count"] == 0
    assert result["current_evidence_context"]["tracked_gap_count"] == 1


def test_production_readiness_checklist_blocks_when_cross_plane_proof_gate_blocks(
    tmp_path,
):
    module = _load_module()
    _write_current_evidence(tmp_path)
    _write_cross_plane_proof_gate(tmp_path, allowed=False, blocked_claim_ids={"dpi_bypass"})

    result = _all_pass_validator(module, tmp_path).validate()

    assert result["raw_checklist_ready"] is True
    assert result["current_evidence_gate_clear"] is True
    assert result["cross_plane_proof_gate_clear"] is False
    assert result["is_production_ready"] is False
    assert (
        result["cross_plane_claim_gate"]["production_readiness_claim_allowed"] is False
    )
    assert "cross_plane_proof_gate_blocked" in result["cross_plane_claim_gate"]["blocked_reason_ids"]
    assert "claim_blocked:dpi_bypass" in result["cross_plane_claim_gate"]["blocked_reason_ids"]
    assert any("Reusable cross-plane proof gate" in item for item in result["not_verified_yet"])


def test_production_readiness_checklist_blocks_when_proof_gate_lacks_source_hashes(
    tmp_path,
):
    module = _load_module()
    _write_current_evidence(tmp_path)
    _write_cross_plane_proof_gate(tmp_path, source_artifact_hashes_present=False)

    result = _all_pass_validator(module, tmp_path).validate()

    assert result["raw_checklist_ready"] is True
    assert result["current_evidence_gate_clear"] is True
    assert result["cross_plane_proof_gate_clear"] is False
    assert result["is_production_ready"] is False
    assert (
        "cross_plane_proof_gate_source_artifact_hashes_missing"
        in result["cross_plane_claim_gate"]["blocked_reason_ids"]
    )
