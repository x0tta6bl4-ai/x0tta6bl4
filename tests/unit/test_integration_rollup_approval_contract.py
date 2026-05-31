import json
from pathlib import Path

from src.integration.rollup_approval_contract import SOURCE_SPECS, build_report, main


def _write_json(root: Path, rel: str, payload: dict) -> None:
    path = root / rel
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(payload), encoding="utf-8")


def _write_text(root: Path, rel: str, text: str = "{}") -> None:
    path = root / rel
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(text, encoding="utf-8")


def _write_current_evidence_context(
    root: Path,
    *,
    current_gaps: list[dict] | None = None,
    next_actions: list[dict] | None = None,
) -> None:
    _write_text(
        root,
        "docs/architecture/CURRENT_ACTIVE_GOAL_GAP_AUDIT.md",
        "# Current Active Goal Gap Audit\n\nStatus: test fixture.\n",
    )
    _write_json(
        root,
        "docs/architecture/CURRENT_CROSS_PLANE_EVIDENCE_MAP.json",
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
    claim_ids = (
        "production_readiness",
        "dataplane_delivery",
        "traffic_delivery",
        "customer_traffic",
        "settlement_finality",
        "dpi_bypass",
    )
    claim_results = [
        {
            "claim_id": claim_id,
            "allowed": allowed,
            "blockers": [] if allowed else [f"{claim_id}_proof_missing"],
        }
        for claim_id in claim_ids
    ]
    _write_json(
        root,
        ".tmp/validation-shards/cross-plane-proof-gate-current.json",
        {
            "schema": "x0tta6bl4.cross_plane_proof_gate.v1",
            "decision": "CROSS_PLANE_CLAIMS_ALLOWED" if allowed else "CROSS_PLANE_CLAIMS_BLOCKED",
            "allowed": allowed,
            "context": {
                "source_artifact_hashes_present": True,
                "map_sha256": "0" * 64,
                "audit_sha256": "1" * 64,
            },
            "claim_results": claim_results,
            "summary": {
                "claims_total": len(claim_results),
                "claims_allowed": len(claim_results) if allowed else 0,
                "claims_blocked": 0 if allowed else len(claim_results),
            },
        },
    )


def _passport_item(spec, *, ready: bool) -> dict:
    rel = f".tmp/{spec.evidence_key}/retained.json"
    return {
        "item_id": f"01:{spec.kind}:{spec.evidence_key}:retained.json",
        "kind": spec.kind,
        "evidence_key": spec.evidence_key,
        "ready": ready,
        "blocks_production": not ready,
        "operator_return_path": rel,
        "retained_destination_path": rel,
    }


def _write_passport(root: Path, *, ready: bool, write_files: bool = True) -> None:
    evidence_specs = [spec for spec in SOURCE_SPECS if spec.kind in {"raw_evidence", "external_settlement"}]
    items = [_passport_item(spec, ready=ready) for spec in evidence_specs]
    for item in items:
        if write_files:
            _write_text(root, item["retained_destination_path"], '{"status":"VERIFIED HERE"}')
    _write_json(
        root,
        "passport.json",
        {
            "status": "VERIFIED HERE",
            "ok": True,
            "decision": "PRODUCTION_EVIDENCE_REPLACEMENT_PASSPORT_CLEAR"
            if ready
            else "PRODUCTION_EVIDENCE_REPLACEMENT_PASSPORT_READY_FOR_OPERATOR",
            "production_ready": ready,
            "required_evidence_files": items,
            "summary": {
                "required_evidence_files_total": len(items),
                "required_evidence_files_ready": len(items) if ready else 0,
            },
        },
    )


def _write_source_reports(root: Path, *, ready: bool) -> None:
    for spec in SOURCE_SPECS:
        decision = spec.expected_decision if ready else "BLOCKED"
        _write_json(
            root,
            spec.path,
            {
                "schema_version": f"test-{spec.label}",
                "status": "VERIFIED HERE",
                "ok": True,
                "decision": decision,
                "entrypoint_decision": decision,
                "ready": ready,
                "production_ready": ready,
                spec.ready_summary_key: ready,
                "not_verified_yet": [] if ready else ["operator evidence required"],
                "summary": {
                    spec.ready_summary_key: ready,
                    "production_ready": ready,
                },
            },
        )
    _write_cross_plane_proof_gate(root, allowed=ready)


def test_rollup_approval_contract_accepts_valid_blocked_sources(tmp_path):
    _write_passport(tmp_path, ready=False)
    _write_source_reports(tmp_path, ready=False)

    report = build_report(tmp_path, tmp_path / "passport.json", "passport.json")

    assert report["status"] == "VERIFIED HERE"
    assert report["ok"] is True
    assert report["ready"] is False
    assert report["decision"] == "ROLLUP_APPROVAL_BLOCKED_ON_OPERATOR_EVIDENCE"
    assert report["goal_can_be_marked_complete"] is False
    assert report["summary"]["source_errors_total"] == 0
    assert report["summary"]["sources_total"] == len(SOURCE_SPECS)
    assert report["summary"]["sources_ready"] == 0
    evidence_specs = [spec for spec in SOURCE_SPECS if spec.kind in {"raw_evidence", "external_settlement"}]
    assert report["summary"]["evidence_files_total"] == len(evidence_specs)
    assert report["summary"]["evidence_files_valid"] == 0
    assert report["summary"]["evidence_files_invalid"] == len(evidence_specs)
    assert report["summary"]["evidence_files_operator_input_required"] == len(evidence_specs)
    assert all(
        item["status"] == "OPERATOR_INPUT_REQUIRED"
        for source in report["source_reports"]
        for item in source["evidence_files"]
    )


def test_rollup_approval_contract_can_be_ready_when_all_sources_and_evidence_are_ready(tmp_path):
    _write_passport(tmp_path, ready=True)
    _write_source_reports(tmp_path, ready=True)
    _write_current_evidence_context(tmp_path)

    report = build_report(tmp_path, tmp_path / "passport.json", "passport.json")

    assert report["ready"] is True
    assert report["decision"] == "ROLLUP_APPROVAL_READY"
    assert report["summary"]["source_errors_total"] == 0
    assert report["summary"]["sources_ready"] == report["summary"]["sources_total"]
    assert report["summary"]["evidence_files_valid"] == report["summary"]["evidence_files_total"]
    assert report["summary"]["evidence_files_operator_input_required"] == 0
    assert report["summary"]["local_sources_ready"] is True
    assert report["summary"]["current_evidence_context_clear"] is True
    assert report["summary"]["cross_plane_proof_gate_allowed"] is True
    assert report["summary"]["cross_plane_proof_gate_source_artifact_hashes_present"] is True
    assert report["current_evidence_context"]["included"] is True
    assert report["current_evidence_context"]["current_gap_count"] == 0
    assert report["cross_plane_proof_gate"]["allowed"] is True
    assert report["cross_plane_claim_gate"]["current_evidence_context_clear"] is True
    assert report["cross_plane_claim_gate"]["cross_plane_proof_gate_required"] is True
    assert report["cross_plane_claim_gate"]["cross_plane_proof_gate_allowed"] is True
    assert report["cross_plane_claim_gate"]["proof_claims"]["production_ready"] is False
    assert report["cross_plane_claim_gate"]["proof_claims"]["live_apply_authorized"] is False
    assert report["current_evidence_context_hash"].startswith("0x")
    assert report["not_verified_yet"] == []


def test_rollup_approval_contract_blocks_ready_without_current_evidence_context(tmp_path):
    _write_passport(tmp_path, ready=True)
    _write_source_reports(tmp_path, ready=True)

    report = build_report(tmp_path, tmp_path / "passport.json", "passport.json")

    assert report["ready"] is False
    assert report["decision"] == "ROLLUP_APPROVAL_BLOCKED_ON_CURRENT_EVIDENCE_CONTEXT"
    assert report["summary"]["local_sources_ready"] is True
    assert report["summary"]["current_evidence_context_included"] is False
    assert report["summary"]["current_evidence_context_clear"] is False
    assert report["summary"]["ready_for_closeout_review_blocked_by_current_evidence"] is True
    assert report["summary"]["ready_for_closeout_review_blocked_by_cross_plane_proof_gate"] is False
    assert report["operator_approval"]["ready_for_closeout_review"] is False
    assert report["current_evidence_context"]["status"] == "missing_current_evidence_context"
    assert "current_evidence_context_missing" in report["cross_plane_claim_gate"]["blocked_reason_ids"]
    assert report["cross_plane_claim_gate"]["ready_for_closeout_review_claim_allowed"] is False
    assert report["cross_plane_claim_gate"]["proof_claims"]["production_ready"] is False


def test_rollup_approval_contract_blocks_ready_on_current_evidence_open_gap(tmp_path):
    _write_passport(tmp_path, ready=True)
    _write_source_reports(tmp_path, ready=True)
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

    report = build_report(tmp_path, tmp_path / "passport.json", "passport.json")

    assert report["ready"] is False
    assert report["decision"] == "ROLLUP_APPROVAL_BLOCKED_ON_CURRENT_EVIDENCE_CONTEXT"
    assert report["summary"]["local_sources_ready"] is True
    assert report["summary"]["current_evidence_open_gaps"] == 1
    assert report["summary"]["current_evidence_next_actions"] == 1
    assert report["current_evidence_context"]["open_gap_ids"] == ["external-dpi-proof-missing"]
    assert report["current_evidence_context"]["next_action_ids"] == ["external-dpi-real-artifact-intake"]
    assert "current_evidence_open_gaps" in report["cross_plane_claim_gate"]["blocked_reason_ids"]
    assert "current_evidence_next_actions_open" in report["cross_plane_claim_gate"]["blocked_reason_ids"]


def test_rollup_approval_contract_blocks_ready_when_cross_plane_proof_gate_blocks(tmp_path):
    _write_passport(tmp_path, ready=True)
    _write_source_reports(tmp_path, ready=True)
    _write_current_evidence_context(tmp_path)
    _write_cross_plane_proof_gate(tmp_path, allowed=False)

    report = build_report(tmp_path, tmp_path / "passport.json", "passport.json")

    assert report["ready"] is False
    assert report["decision"] == "ROLLUP_APPROVAL_BLOCKED_ON_CROSS_PLANE_PROOF_GATE"
    assert report["summary"]["local_sources_ready"] is True
    assert report["summary"]["current_evidence_context_clear"] is True
    assert report["summary"]["cross_plane_proof_gate_allowed"] is False
    assert report["summary"]["ready_for_closeout_review_blocked_by_cross_plane_proof_gate"] is True
    assert report["operator_approval"]["ready_for_closeout_review"] is False
    assert report["cross_plane_claim_gate"]["ready_for_closeout_review_claim_allowed"] is False
    assert "cross_plane_proof_gate_blocked" in report["cross_plane_claim_gate"]["blocked_reason_ids"]
    assert "claim_blocked:dpi_bypass" in report["cross_plane_claim_gate"]["blocked_reason_ids"]
    assert "reusable cross-plane proof gate must allow rollup closeout-review claims" in report["not_verified_yet"]


def test_rollup_approval_contract_reports_missing_source_errors(tmp_path):
    _write_passport(tmp_path, ready=True)

    report = build_report(tmp_path, tmp_path / "passport.json", "passport.json")

    assert report["ready"] is False
    assert report["decision"] == "ROLLUP_APPROVAL_BLOCKED_ON_OPERATOR_EVIDENCE"
    assert report["summary"]["source_errors_total"] == len(SOURCE_SPECS)
    assert report["summary"]["sources_ready"] == 0
    assert report["source_errors"]


def test_rollup_approval_contract_cli_require_ready_returns_two_when_blocked(tmp_path):
    _write_passport(tmp_path, ready=False)
    _write_source_reports(tmp_path, ready=False)
    output_json = tmp_path / "rollup.json"

    exit_code = main([
        "--root",
        str(tmp_path),
        "--passport",
        "passport.json",
        "--output-json",
        str(output_json),
        "--require-ready",
    ])

    payload = json.loads(output_json.read_text(encoding="utf-8"))
    assert exit_code == 2
    assert payload["ready"] is False
    assert payload["summary"]["source_errors_total"] == 0
