import json
from pathlib import Path

from src.integration.semantic_production_blocker_queue import QueueInputs, build_queue, main


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


def _coverage() -> dict:
    return {
        "status": "VERIFIED HERE",
        "ok": True,
        "summary": {
            "current_collector_evidence_blockers": 1,
            "current_external_settlement_ready": False,
            "current_raw_files_expected": 1,
            "current_raw_files_installed": 1,
        },
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


def test_semantic_queue_builds_external_and_collector_blockers(tmp_path):
    pipeline = tmp_path / "pipeline.json"
    coverage = tmp_path / "coverage.json"
    acceptance = tmp_path / "return-acceptance.json"
    _write_json(
        pipeline,
        {
            "status": "VERIFIED HERE",
            "ok": True,
            "blocking_inputs": [
                {
                    "kind": "external_settlement",
                    "evidence_key": "external_settlement",
                    "destination_path": ".tmp/external-settlement-evidence/settlement-submit.json",
                    "errors": ["receipt missing"],
                }
            ],
            "command_results": [
                {
                    "collector_id": "live-rollout",
                    "preflight_errors": ["operator-manifest environment must be production"],
                    "stdout_json": {
                        "raw_files": [
                            {
                                "name": "operator-manifest.json",
                                "path": ".tmp/live-rollout-raw-evidence/operator-manifest.json",
                            }
                        ]
                    },
                }
            ],
            "summary": {
                "collector_evidence_blockers": 1,
                "external_settlement_ready": False,
                "raw_files_expected": 1,
                "raw_files_installed": 1,
            },
        },
    )
    _write_json(coverage, _coverage())
    _write_json(acceptance, _return_acceptance(ready=False))

    report = build_queue(QueueInputs(tmp_path, pipeline, coverage, acceptance, "pipeline.json", "coverage.json", "return-acceptance.json"))

    assert report["completion_decision"] == "NOT_COMPLETE"
    assert report["goal_can_be_marked_complete"] is False
    assert report["summary"]["blocking_items_total"] == 2
    assert report["summary"]["blocking_items_operator_input_required"] == 2
    assert report["summary"]["blocking_items_generic_blocking"] == 0
    assert report["summary"]["current_raw_files_installed"] == 0
    assert report["summary"]["pipeline_raw_files_reported_installed"] == 1
    assert report["summary"]["raw_install_claim_source"] == "return_acceptance"
    assert report["summary"]["return_acceptance_raw_files_local_observation"] == 1
    assert report["summary"]["external_settlement_blockers"] == 1
    assert report["summary"]["semantic_preflight_errors_total"] == 1
    assert {item["status"] for item in report["blocking_items"]} == {"OPERATOR_INPUT_REQUIRED"}
    assert report["blocking_items"][1]["raw_subject"] == "operator-manifest"
    assert report["blocking_items"][1]["raw_evidence_path"].endswith("operator-manifest.json")


def test_semantic_queue_can_report_complete_when_no_blockers(tmp_path):
    pipeline = tmp_path / "pipeline.json"
    coverage = tmp_path / "coverage.json"
    acceptance = tmp_path / "return-acceptance.json"
    _write_json(
        pipeline,
        {
            "status": "VERIFIED HERE",
            "ok": True,
            "blocking_inputs": [],
            "command_results": [{"collector_id": "live-rollout", "preflight_errors": [], "stdout_json": {"raw_files": []}}],
            "summary": {"external_settlement_ready": True, "collector_evidence_blockers": 0},
        },
    )
    _write_json(coverage, _coverage())
    _write_json(acceptance, _return_acceptance(ready=True))
    _write_current_evidence_context(tmp_path)
    _write_cross_plane_proof_gate(tmp_path, allowed=True)

    report = build_queue(QueueInputs(tmp_path, pipeline, coverage, acceptance, "pipeline.json", "coverage.json", "return-acceptance.json"))

    assert report["completion_decision"] == "COMPLETE"
    assert report["goal_can_be_marked_complete"] is True
    assert report["summary"]["local_queue_clear"] is True
    assert report["summary"]["current_evidence_context_clear"] is True
    assert report["summary"]["cross_plane_proof_gate_allowed"] is True
    assert report["summary"]["cross_plane_proof_gate_source_artifact_hashes_present"] is True
    assert report["current_evidence_context"]["included"] is True
    assert report["current_evidence_context"]["current_gap_count"] == 0
    assert report["cross_plane_proof_gate"]["allowed"] is True
    assert report["cross_plane_claim_gate"]["local_queue_clear"] is True
    assert report["cross_plane_claim_gate"]["cross_plane_proof_gate_required"] is True
    assert report["cross_plane_claim_gate"]["cross_plane_proof_gate_allowed"] is True
    assert report["cross_plane_claim_gate"]["goal_completion_claim_allowed"] is True
    assert report["cross_plane_claim_gate"]["proof_claims"]["production_ready"] is False
    assert report["cross_plane_claim_gate"]["proof_claims"]["live_apply_authorized"] is False
    assert report["current_evidence_context_hash"].startswith("0x")
    assert report["summary"]["current_raw_files_installed"] == 1
    assert report["summary"]["return_acceptance_raw_ready_to_stage"] is True
    assert report["summary"]["blocking_items_operator_input_required"] == 0
    assert report["summary"]["blocking_items_generic_blocking"] == 0
    assert report["blocking_items"] == []
    assert report["priority_order"] == []


def test_semantic_queue_blocks_complete_when_cross_plane_proof_gate_blocks(tmp_path):
    pipeline = tmp_path / "pipeline.json"
    coverage = tmp_path / "coverage.json"
    acceptance = tmp_path / "return-acceptance.json"
    _write_json(
        pipeline,
        {
            "status": "VERIFIED HERE",
            "ok": True,
            "blocking_inputs": [],
            "command_results": [{"collector_id": "live-rollout", "preflight_errors": [], "stdout_json": {"raw_files": []}}],
            "summary": {"external_settlement_ready": True, "collector_evidence_blockers": 0},
        },
    )
    _write_json(coverage, _coverage())
    _write_json(acceptance, _return_acceptance(ready=True))
    _write_current_evidence_context(tmp_path)
    _write_cross_plane_proof_gate(tmp_path, allowed=False)

    report = build_queue(QueueInputs(tmp_path, pipeline, coverage, acceptance, "pipeline.json", "coverage.json", "return-acceptance.json"))

    assert report["completion_decision"] == "BLOCKED_ON_CROSS_PLANE_PROOF_GATE"
    assert report["goal_can_be_marked_complete"] is False
    assert report["summary"]["local_queue_clear"] is True
    assert report["summary"]["current_evidence_context_clear"] is True
    assert report["summary"]["cross_plane_proof_gate_allowed"] is False
    assert report["summary"]["goal_completion_blocked_by_cross_plane_proof_gate"] is True
    assert report["cross_plane_claim_gate"]["goal_completion_claim_allowed"] is False
    assert "cross_plane_proof_gate_blocked" in report["cross_plane_claim_gate"]["blocked_reason_ids"]
    assert "claim_blocked:dpi_bypass" in report["cross_plane_claim_gate"]["blocked_reason_ids"]
    assert any("cross-plane proof gate" in item for item in report["not_verified_yet"])


def test_semantic_queue_blocks_complete_without_current_evidence_context(tmp_path):
    pipeline = tmp_path / "pipeline.json"
    coverage = tmp_path / "coverage.json"
    acceptance = tmp_path / "return-acceptance.json"
    _write_json(
        pipeline,
        {
            "status": "VERIFIED HERE",
            "ok": True,
            "blocking_inputs": [],
            "command_results": [{"collector_id": "live-rollout", "preflight_errors": [], "stdout_json": {"raw_files": []}}],
            "summary": {"external_settlement_ready": True, "collector_evidence_blockers": 0},
        },
    )
    _write_json(coverage, _coverage())
    _write_json(acceptance, _return_acceptance(ready=True))

    report = build_queue(QueueInputs(tmp_path, pipeline, coverage, acceptance, "pipeline.json", "coverage.json", "return-acceptance.json"))

    assert report["completion_decision"] == "BLOCKED_ON_CURRENT_EVIDENCE_CONTEXT"
    assert report["goal_can_be_marked_complete"] is False
    assert report["summary"]["local_queue_clear"] is True
    assert report["summary"]["current_evidence_context_included"] is False
    assert report["summary"]["current_evidence_context_clear"] is False
    assert report["current_evidence_context"]["status"] == "missing_current_evidence_context"
    assert "current_evidence_context_missing" in report["cross_plane_claim_gate"]["blocked_reason_ids"]
    assert report["cross_plane_claim_gate"]["goal_completion_claim_allowed"] is False


def test_semantic_queue_blocks_complete_on_current_evidence_open_gap(tmp_path):
    pipeline = tmp_path / "pipeline.json"
    coverage = tmp_path / "coverage.json"
    acceptance = tmp_path / "return-acceptance.json"
    _write_json(
        pipeline,
        {
            "status": "VERIFIED HERE",
            "ok": True,
            "blocking_inputs": [],
            "command_results": [{"collector_id": "live-rollout", "preflight_errors": [], "stdout_json": {"raw_files": []}}],
            "summary": {"external_settlement_ready": True, "collector_evidence_blockers": 0},
        },
    )
    _write_json(coverage, _coverage())
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

    report = build_queue(QueueInputs(tmp_path, pipeline, coverage, acceptance, "pipeline.json", "coverage.json", "return-acceptance.json"))

    assert report["completion_decision"] == "BLOCKED_ON_CURRENT_EVIDENCE_CONTEXT"
    assert report["goal_can_be_marked_complete"] is False
    assert report["summary"]["local_queue_clear"] is True
    assert report["summary"]["current_evidence_open_gaps"] == 1
    assert report["summary"]["current_evidence_next_actions"] == 1
    assert report["current_evidence_context"]["open_gap_ids"] == ["external-dpi-proof-missing"]
    assert report["current_evidence_context"]["next_action_ids"] == ["external-dpi-real-artifact-intake"]
    assert "current_evidence_open_gaps" in report["cross_plane_claim_gate"]["blocked_reason_ids"]
    assert "current_evidence_next_actions_open" in report["cross_plane_claim_gate"]["blocked_reason_ids"]


def test_semantic_queue_cli_writes_fail_closed_current_shape(tmp_path):
    exit_code = main(["--root", str(tmp_path), "--require-clear"])

    assert exit_code == 2
    report = json.loads(
        (tmp_path / ".tmp/validation-shards/integration-spine-semantic-production-blocker-queue-current.json").read_text(
            encoding="utf-8"
        )
    )
    assert report["completion_decision"] == "NOT_COMPLETE"
    assert report["summary"]["source_errors_total"] > 0
    assert report["summary"]["blocking_items_operator_input_required"] == 0
    assert report["summary"]["blocking_items_generic_blocking"] == 0
