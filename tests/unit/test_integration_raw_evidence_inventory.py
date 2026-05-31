import json
from pathlib import Path

from src.integration.raw_evidence_inventory import InventoryInputs, build_inventory, main


def _write_json(path: Path, payload: dict) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(payload), encoding="utf-8")


def _write_current_evidence_context(
    root: Path,
    *,
    current_gaps: list[dict] | None = None,
    next_actions: list[dict] | None = None,
) -> None:
    audit_path = root / "docs/architecture/CURRENT_ACTIVE_GOAL_GAP_AUDIT.md"
    audit_path.parent.mkdir(parents=True, exist_ok=True)
    audit_path.write_text("# Current Active Goal Gap Audit\n\nStatus: test fixture.\n", encoding="utf-8")
    _write_json(
        root / "docs/architecture/CURRENT_CROSS_PLANE_EVIDENCE_MAP.json",
        {
            "status": "working_map_not_production_completion_proof",
            "planes": {
                "data_plane": {},
                "control_plane": {},
                "trust_plane": {},
                "evidence_plane": {},
                "economy_plane": {},
            },
            "current_gaps": current_gaps or [],
            "next_actions": next_actions or [],
        },
    )


def _write_cross_plane_proof_gate(root: Path, *, allowed: bool) -> None:
    claim_ids = [
        "production_readiness",
        "dataplane_delivery",
        "traffic_delivery",
        "customer_traffic",
        "settlement_finality",
        "dpi_bypass",
    ]
    claim_results = [
        {
            "claim_id": claim_id,
            "allowed": allowed,
            "blockers": [] if allowed else [f"{claim_id}_not_verified"],
        }
        for claim_id in claim_ids
    ]
    _write_json(
        root / ".tmp/validation-shards/cross-plane-proof-gate-current.json",
        {
            "schema": "x0tta6bl4.cross_plane_proof_gate.v1",
            "decision": "CROSS_PLANE_CLAIMS_ALLOWED" if allowed else "CROSS_PLANE_CLAIMS_BLOCKED",
            "allowed": allowed,
            "claim_results": claim_results,
            "context": {
                "source_artifact_hashes_present": True,
                "map_sha256": "0xmap",
                "audit_sha256": "0xaudit",
            },
            "summary": {
                "claims_total": len(claim_results),
                "claims_allowed": len(claim_results) if allowed else 0,
                "claims_blocked": 0 if allowed else len(claim_results),
            },
        },
    )


def _pipeline(path: str) -> dict:
    return {
        "status": "VERIFIED HERE",
        "ok": True,
        "raw_install_results": [
            {
                "collector_id": "live-rollout",
                "destination_path": path,
                "installed": True,
                "raw_id": "live-rollout/operator-manifest.json",
                "status": "INSTALLED",
            }
        ],
        "summary": {
            "raw_files_expected": 1,
            "raw_files_installed": 1,
        },
    }


def _semantic_queue(path: str, *, blocked: bool) -> dict:
    return {
        "status": "VERIFIED HERE",
        "ok": True,
        "blocking_items": [
            {
                "id": "live-rollout:001",
                "collector_id": "live-rollout",
                "raw_evidence_path": path,
                "raw_subject": "operator-manifest",
                "preflight_error": "operator-manifest environment must be production",
            }
        ]
        if blocked
        else [],
        "summary": {"blocking_items_total": 1 if blocked else 0},
    }


def _return_acceptance(*, ready: bool) -> dict:
    return {
        "status": "VERIFIED HERE",
        "ok": True,
        "summary": {
            "raw_files_expected": 1,
            "raw_files_staged": 1 if ready else 0,
            "raw_files_ready_to_stage": 1 if ready else 0,
            "raw_files_destination_existing": 1,
            "raw_files_local_observation": 0 if ready else 1,
            "raw_ready_to_stage": ready,
        },
    }


def test_raw_inventory_classifies_component_evidence_with_semantic_blockers(tmp_path):
    raw_path = ".tmp/live-rollout-raw-evidence/operator-manifest.json"
    _write_json(
        tmp_path / raw_path,
        {
            "status": "VERIFIED HERE",
            "evidence_status": "VERIFIED HERE",
            "environment": "local",
            "production_promotion_blockers": ["not production"],
        },
    )
    pipeline = tmp_path / "pipeline.json"
    semantic = tmp_path / "semantic.json"
    acceptance = tmp_path / "return-acceptance.json"
    _write_json(pipeline, _pipeline(raw_path))
    _write_json(semantic, _semantic_queue(raw_path, blocked=True))
    _write_json(acceptance, _return_acceptance(ready=False))

    report = build_inventory(InventoryInputs(tmp_path, pipeline, semantic, acceptance, "pipeline.json", "semantic.json", "return-acceptance.json"))

    assert report["completion_decision"] == "NOT_COMPLETE"
    assert report["summary"]["files_total"] == 1
    assert report["summary"]["raw_install_claim_source"] == "return_acceptance"
    assert report["summary"]["pipeline_raw_files_reported_installed"] == 1
    assert report["summary"]["return_acceptance_raw_files_staged"] == 0
    assert report["summary"]["return_acceptance_raw_files_local_observation"] == 1
    assert report["summary"]["semantic_blockers_total"] == 1
    assert report["summary"]["classification_counts"] == {"RETAINED_COMPONENT_EVIDENCE_NOT_PRODUCTION_GRADE": 1}
    assert report["records"][0]["usable_for_goal_completion"] is False
    assert report["records"][0]["verified_here_component_evidence"] is True


def test_raw_inventory_accepts_production_grade_zero_blocker_evidence(tmp_path):
    raw_path = ".tmp/live-rollout-raw-evidence/operator-manifest.json"
    _write_json(
        tmp_path / raw_path,
        {
            "status": "VERIFIED HERE",
            "evidence_status": "VERIFIED HERE",
            "environment": "production",
            "production_ready": True,
            "production_promotion_blockers": [],
        },
    )
    pipeline = tmp_path / "pipeline.json"
    semantic = tmp_path / "semantic.json"
    acceptance = tmp_path / "return-acceptance.json"
    _write_json(pipeline, _pipeline(raw_path))
    _write_json(semantic, _semantic_queue(raw_path, blocked=False))
    _write_json(acceptance, _return_acceptance(ready=True))
    _write_current_evidence_context(tmp_path)
    _write_cross_plane_proof_gate(tmp_path, allowed=True)

    report = build_inventory(InventoryInputs(tmp_path, pipeline, semantic, acceptance, "pipeline.json", "semantic.json", "return-acceptance.json"))

    assert report["completion_decision"] == "COMPLETE"
    assert report["goal_can_be_marked_complete"] is True
    assert report["summary"]["local_inventory_clear"] is True
    assert report["summary"]["current_evidence_context_clear"] is True
    assert report["summary"]["cross_plane_proof_gate_allowed"] is True
    assert report["summary"]["cross_plane_proof_gate_source_artifact_hashes_present"] is True
    assert report["current_evidence_context"]["included"] is True
    assert report["current_evidence_context"]["current_gap_count"] == 0
    assert report["cross_plane_proof_gate"]["allowed"] is True
    assert report["cross_plane_claim_gate"]["local_inventory_clear"] is True
    assert report["cross_plane_claim_gate"]["cross_plane_proof_gate_required"] is True
    assert report["cross_plane_claim_gate"]["cross_plane_proof_gate_allowed"] is True
    assert report["cross_plane_claim_gate"]["goal_completion_claim_allowed"] is True
    assert report["cross_plane_claim_gate"]["proof_claims"]["production_ready"] is False
    assert report["cross_plane_claim_gate"]["proof_claims"]["live_apply_authorized"] is False
    assert report["current_evidence_context_hash"].startswith("0x")
    assert report["summary"]["return_acceptance_raw_files_staged"] == 1
    assert report["summary"]["return_acceptance_raw_ready_to_stage"] is True
    assert report["summary"]["usable_for_goal_completion_files"] == 1
    assert report["summary"]["classification_counts"] == {"PRODUCTION_GRADE": 1}


def test_raw_inventory_blocks_complete_when_cross_plane_proof_gate_blocks(tmp_path):
    raw_path = ".tmp/live-rollout-raw-evidence/operator-manifest.json"
    _write_json(
        tmp_path / raw_path,
        {
            "status": "VERIFIED HERE",
            "evidence_status": "VERIFIED HERE",
            "environment": "production",
            "production_ready": True,
            "production_promotion_blockers": [],
        },
    )
    pipeline = tmp_path / "pipeline.json"
    semantic = tmp_path / "semantic.json"
    acceptance = tmp_path / "return-acceptance.json"
    _write_json(pipeline, _pipeline(raw_path))
    _write_json(semantic, _semantic_queue(raw_path, blocked=False))
    _write_json(acceptance, _return_acceptance(ready=True))
    _write_current_evidence_context(tmp_path)
    _write_cross_plane_proof_gate(tmp_path, allowed=False)

    report = build_inventory(InventoryInputs(tmp_path, pipeline, semantic, acceptance, "pipeline.json", "semantic.json", "return-acceptance.json"))

    assert report["completion_decision"] == "BLOCKED_ON_CROSS_PLANE_PROOF_GATE"
    assert report["goal_can_be_marked_complete"] is False
    assert report["summary"]["local_inventory_clear"] is True
    assert report["summary"]["current_evidence_context_clear"] is True
    assert report["summary"]["cross_plane_proof_gate_allowed"] is False
    assert report["summary"]["goal_completion_blocked_by_cross_plane_proof_gate"] is True
    assert report["cross_plane_claim_gate"]["goal_completion_claim_allowed"] is False
    assert "cross_plane_proof_gate_blocked" in report["cross_plane_claim_gate"]["blocked_reason_ids"]
    assert "claim_blocked:dpi_bypass" in report["cross_plane_claim_gate"]["blocked_reason_ids"]
    assert any("cross-plane proof gate" in item for item in report["not_verified_yet"])


def test_raw_inventory_blocks_complete_without_current_evidence_context(tmp_path):
    raw_path = ".tmp/live-rollout-raw-evidence/operator-manifest.json"
    _write_json(
        tmp_path / raw_path,
        {
            "status": "VERIFIED HERE",
            "evidence_status": "VERIFIED HERE",
            "environment": "production",
            "production_ready": True,
            "production_promotion_blockers": [],
        },
    )
    pipeline = tmp_path / "pipeline.json"
    semantic = tmp_path / "semantic.json"
    acceptance = tmp_path / "return-acceptance.json"
    _write_json(pipeline, _pipeline(raw_path))
    _write_json(semantic, _semantic_queue(raw_path, blocked=False))
    _write_json(acceptance, _return_acceptance(ready=True))

    report = build_inventory(InventoryInputs(tmp_path, pipeline, semantic, acceptance, "pipeline.json", "semantic.json", "return-acceptance.json"))

    assert report["completion_decision"] == "BLOCKED_ON_CURRENT_EVIDENCE_CONTEXT"
    assert report["goal_can_be_marked_complete"] is False
    assert report["summary"]["local_inventory_clear"] is True
    assert report["summary"]["current_evidence_context_included"] is False
    assert report["summary"]["current_evidence_context_clear"] is False
    assert report["current_evidence_context"]["status"] == "missing_current_evidence_context"
    assert "current_evidence_context_missing" in report["cross_plane_claim_gate"]["blocked_reason_ids"]
    assert report["cross_plane_claim_gate"]["goal_completion_claim_allowed"] is False


def test_raw_inventory_blocks_complete_on_current_evidence_open_gap(tmp_path):
    raw_path = ".tmp/live-rollout-raw-evidence/operator-manifest.json"
    _write_json(
        tmp_path / raw_path,
        {
            "status": "VERIFIED HERE",
            "evidence_status": "VERIFIED HERE",
            "environment": "production",
            "production_ready": True,
            "production_promotion_blockers": [],
        },
    )
    pipeline = tmp_path / "pipeline.json"
    semantic = tmp_path / "semantic.json"
    acceptance = tmp_path / "return-acceptance.json"
    _write_json(pipeline, _pipeline(raw_path))
    _write_json(semantic, _semantic_queue(raw_path, blocked=False))
    _write_json(acceptance, _return_acceptance(ready=True))
    _write_current_evidence_context(
        tmp_path,
        current_gaps=[
            {
                "id": "external-dpi-proof-missing",
                "blocks_real_readiness": True,
            }
        ],
        next_actions=[{"id": "external-dpi-real-artifact-intake"}],
    )

    report = build_inventory(InventoryInputs(tmp_path, pipeline, semantic, acceptance, "pipeline.json", "semantic.json", "return-acceptance.json"))

    assert report["completion_decision"] == "BLOCKED_ON_CURRENT_EVIDENCE_CONTEXT"
    assert report["goal_can_be_marked_complete"] is False
    assert report["summary"]["local_inventory_clear"] is True
    assert report["summary"]["current_evidence_open_gaps"] == 1
    assert report["summary"]["current_evidence_next_actions"] == 1
    assert report["current_evidence_context"]["open_gap_ids"] == ["external-dpi-proof-missing"]
    assert report["current_evidence_context"]["next_action_ids"] == ["external-dpi-real-artifact-intake"]
    assert "current_evidence_open_gaps" in report["cross_plane_claim_gate"]["blocked_reason_ids"]
    assert "current_evidence_next_actions_open" in report["cross_plane_claim_gate"]["blocked_reason_ids"]


def test_raw_inventory_cli_writes_fail_closed_current_shape(tmp_path):
    exit_code = main(["--root", str(tmp_path), "--require-ready"])

    assert exit_code == 2
    report = json.loads(
        (tmp_path / ".tmp/validation-shards/integration-spine-raw-evidence-inventory-current.json").read_text(
            encoding="utf-8"
        )
    )
    assert report["completion_decision"] == "NOT_COMPLETE"
    assert report["summary"]["source_errors_total"] > 0
