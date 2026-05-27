import json
from pathlib import Path

from src.integration.production_evidence_replacement_passport import (
    PassportInputs,
    build_passport,
    build_verification_report,
    main,
)


def _write_json(path: Path, payload: dict) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(payload), encoding="utf-8")


def _inputs(root: Path, *, include_raw_operator_packet: bool = False) -> PassportInputs:
    return PassportInputs(
        root=root,
        checklist_path=root / "checklist.json",
        coverage_path=root / "coverage.json",
        semantic_replacements_path=root / "semantic.json",
        return_acceptance_path=root / "return-acceptance.json",
        raw_operator_packet_index_path=root / "raw-operator-packet.json" if include_raw_operator_packet else None,
    )


def _coverage_row(row_id: str, *, production_ready: bool) -> dict:
    return {
        "id": row_id,
        "requirement": f"{row_id} requirement",
        "status": "VERIFIED_READY" if production_ready else "VERIFIED_LOCAL_PRODUCTION_GAP",
        "local_ready": True,
        "production_ready": production_ready,
        "blocking_gaps": [] if production_ready else [f"{row_id} blocked"],
    }


def _raw_item(*, ready: bool = False) -> dict:
    return {
        "item_id": "01:raw_evidence:live_spire_mtls:zero-trust-pqc/operator-manifest.json",
        "kind": "raw_evidence",
        "evidence_key": "live_spire_mtls",
        "raw_id": "zero-trust-pqc/operator-manifest.json",
        "ready": ready,
        "current_status": "PRODUCTION_EVIDENCE" if ready else "LOCAL_OBSERVATION",
        "source_path": ".tmp/scaffold/zero-trust-pqc/operator-manifest.json",
        "destination_path": ".tmp/zero-trust-pqc-raw-evidence/operator-manifest.json",
        "collector_raw_destination_path": ".tmp/zero-trust-pqc-raw-evidence/operator-manifest.json",
        "operator_bundle_destination_path": ".tmp/production-raw-evidence-operator-bundle/zero-trust-pqc/operator-manifest.json",
        "required_action": "replace local observation with retained production JSON",
        "errors": [] if ready else ["raw evidence still declares current local verification environment"],
        "required_statuses": ["VERIFIED HERE"],
        "required_operator_provenance_fields": ["collected_at", "collected_by", "source_commands"],
        "required_hash_binding_fields": ["evidence_root", "evidence_files[].sha256"],
        "hash_binding_enforced_by": ["python3 scripts/ops/sync_integration_spine_production_evidence.py --require-complete"],
        "validation_commands": ["python3 scripts/ops/import_production_raw_evidence_bundle.py --require-ready"],
        "coverage_blocking_row_ids": ["goal_audit:production_evidence_import"],
    }


def _external_item(*, ready: bool = False) -> dict:
    return {
        "item_id": "02:external_settlement:external_settlement:external_settlement",
        "kind": "external_settlement",
        "evidence_key": "external_settlement",
        "raw_id": "",
        "ready": ready,
        "current_status": "PRODUCTION_EVIDENCE" if ready else "OPERATOR_REQUIRED",
        "source_path": ".tmp/scaffold/external-settlement/settlement-submit.template.json",
        "destination_path": ".tmp/external-settlement-evidence/settlement-submit.json",
        "operator_bundle_destination_path": ".tmp/external-settlement-evidence/settlement-submit.json",
        "required_action": "replace the settlement template with a submitted X0T transaction receipt",
        "errors": [] if ready else ["external settlement requires a submitted X0T transaction receipt"],
        "required_statuses": ["VERIFIED HERE"],
        "required_operator_provenance_fields": ["transaction_hash", "source_commands"],
        "required_hash_binding_fields": [],
        "validation_commands": ["python3 scripts/ops/verify_x0t_external_settlement_live_rpc.py --require-ready"],
        "coverage_blocking_row_ids": ["goal_audit:external_settlement_submitted"],
    }


def _write_inputs(root: Path, *, ready: bool = False) -> None:
    _write_json(
        root / "checklist.json",
        {
            "status": "VERIFIED HERE",
            "ok": True,
            "items": [_raw_item(ready=ready), _external_item(ready=ready)],
        },
    )
    _write_json(
        root / "coverage.json",
        {
            "status": "VERIFIED HERE",
            "ok": True,
            "summary": {
                "current_raw_files_expected": 1,
                "current_raw_files_installed": 1,
            },
            "prompt_to_artifact_checklist": [
                _coverage_row("goal_audit:production_evidence_import", production_ready=ready),
                _coverage_row("goal_audit:external_settlement_submitted", production_ready=ready),
            ],
        },
    )
    _write_json(
        root / "semantic.json",
        {
            "status": "VERIFIED HERE",
            "ok": True,
            "replacement_groups": [
                {
                    "evidence_key": "live_spire_mtls",
                    "collector_id": "zero-trust-pqc",
                    "raw_id": "zero-trust-pqc/operator-manifest.json",
                    "raw_path": ".tmp/zero-trust-pqc-raw-evidence/operator-manifest.json",
                    "operator_bundle_path": ".tmp/production-raw-evidence-operator-bundle/zero-trust-pqc/operator-manifest.json",
                    "local_validation_command": "python3 scripts/ops/import_production_raw_evidence_bundle.py --require-ready",
                    "collector_command": "python3 scripts/ops/collect_zero_trust_pqc_evidence_bundle.py --require-ready",
                    "verification_command": "python3 scripts/ops/verify_zero_trust_pqc_evidence_gate.py --require-ready",
                    "field_replacements": [
                        {
                            "json_pointer": "/environment",
                            "current_value": "production-like-local-runtime",
                            "production_evidence_requirement": "operator-manifest environment must be production",
                            "blocking_errors": ["operator-manifest environment must be production"],
                            "required_actions": ["replace /environment with retained production evidence"],
                            "blocker_ids": ["live_spire_mtls:001"],
                        }
                    ],
                }
            ],
            "external_replacements": [
                {
                    "evidence_key": "external_settlement",
                    "required_artifact_path": ".tmp/external-settlement-evidence/settlement-submit.json",
                    "operator_action": "submit or locate real X0T settlement",
                    "verification_command": "python3 scripts/ops/verify_x0t_external_settlement_live_rpc.py --require-ready",
                    "scaffold_command": "python3 scripts/ops/scaffold_x0t_external_settlement_evidence.py --write-template-files",
                    "chain_contract": {"base-sepolia": {"chain_id": "84532"}},
                }
            ],
        },
    )
    _write_json(
        root / "return-acceptance.json",
        {
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
        },
    )
    _write_json(
        root / "raw-operator-packet.json",
        {
            "status": "VERIFIED HERE",
            "ok": True,
            "decision": "RAW_EVIDENCE_OPERATOR_PACKET_ACTIONABLE",
            "local_handoff_complete": True,
            "production_ready": ready,
            "packets": [
                {
                    "collector_id": "zero-trust-pqc",
                    "collector_command": "python3 scripts/ops/collect_zero_trust_pqc_evidence_bundle.py --require-ready",
                    "evidence_gate_command": "python3 scripts/ops/verify_zero_trust_pqc_evidence_gate.py --require-ready",
                    "files": [
                        {
                            "raw_id": "zero-trust-pqc/operator-manifest.json",
                            "file_name": "operator-manifest.json",
                            "operator_bundle_path": ".tmp/production-raw-evidence-operator-bundle/zero-trust-pqc/operator-manifest.json",
                            "production_ready": ready,
                            "replacement_required": not ready,
                            "blockers": [] if ready else ["production_ready is not true"],
                        },
                        {
                            "raw_id": "zero-trust-pqc/mtls-fail-closed.json",
                            "file_name": "mtls-fail-closed.json",
                            "operator_bundle_path": ".tmp/production-raw-evidence-operator-bundle/zero-trust-pqc/mtls-fail-closed.json",
                            "production_ready": ready,
                            "replacement_required": not ready,
                            "blockers": [] if ready else ["production_ready is not true"],
                        },
                    ],
                }
            ],
            "summary": {
                "raw_files_total": 2,
                "operator_bundle_files_existing": 2,
                "operator_bundle_files_production_ready": 2 if ready else 0,
                "operator_bundle_files_replacement_required": 0 if ready else 2,
            },
        },
    )


def test_replacement_passport_lists_file_level_contracts_and_semantic_hints(tmp_path):
    _write_inputs(tmp_path, ready=False)

    report = build_passport(_inputs(tmp_path))

    assert report["decision"] == "PRODUCTION_EVIDENCE_REPLACEMENT_PASSPORT_READY_FOR_OPERATOR"
    assert report["production_ready"] is False
    assert report["goal_can_be_marked_complete"] is False
    assert report["summary"]["items_total"] == 2
    assert report["summary"]["items_blocking"] == 2
    assert report["summary"]["raw_evidence_items"] == 1
    assert report["summary"]["external_settlement_items"] == 1
    assert report["summary"]["semantic_field_replacements_total"] == 1
    assert report["summary"]["raw_install_claim_source"] == "return_acceptance"
    assert report["summary"]["current_raw_files_installed"] == 0
    assert report["summary"]["coverage_raw_files_reported_installed"] == 1
    assert report["summary"]["return_acceptance_raw_files_local_observation"] == 1

    raw = next(item for item in report["replacement_items"] if item["kind"] == "raw_evidence")
    assert raw["replacement_status"] == "BLOCKED_LOCAL_OBSERVATION_REPLACEMENT_REQUIRED"
    assert raw["replacement_contract"]["semantic_json_pointers"] == ["/environment"]
    assert raw["replacement_contract"]["final_gate_command"].endswith("verify_zero_trust_pqc_evidence_gate.py --require-ready")
    assert raw["objective_links"][0]["id"] == "goal_audit:production_evidence_import"

    external = next(item for item in report["replacement_items"] if item["kind"] == "external_settlement")
    assert external["replacement_status"] == "BLOCKED_OPERATOR_EVIDENCE_REQUIRED"
    assert external["replacement_contract"]["external_required_artifact_path"] == ".tmp/external-settlement-evidence/settlement-submit.json"


def test_replacement_passport_verification_accepts_honest_blocked_passport(tmp_path):
    _write_inputs(tmp_path, ready=False)
    passport = build_passport(_inputs(tmp_path))

    verification = build_verification_report(passport, "passport.json")

    assert verification["decision"] == "VALID_PRODUCTION_EVIDENCE_REPLACEMENT_PASSPORT_READY_FOR_OPERATOR"
    assert verification["valid"] is True
    assert verification["summary"]["checks_failed"] == 0
    assert verification["summary"]["passport_decision"] == "PRODUCTION_EVIDENCE_REPLACEMENT_PASSPORT_READY_FOR_OPERATOR"
    assert verification["summary"]["items_blocking"] == 2
    assert verification["summary"]["current_raw_files_installed"] == 0


def test_replacement_passport_verification_rejects_inconsistent_counts(tmp_path):
    _write_inputs(tmp_path, ready=False)
    passport = build_passport(_inputs(tmp_path))
    passport["summary"]["items_total"] = 99

    verification = build_verification_report(passport, "passport.json")

    assert verification["decision"] == "INVALID_PRODUCTION_EVIDENCE_REPLACEMENT_PASSPORT"
    assert verification["valid"] is False
    assert verification["summary"]["checks_failed"] > 0
    assert any("items_total" in error for error in verification["errors"])


def test_replacement_passport_can_clear_when_all_required_files_are_ready(tmp_path):
    _write_inputs(tmp_path, ready=True)

    report = build_passport(_inputs(tmp_path))

    assert report["decision"] == "PRODUCTION_EVIDENCE_REPLACEMENT_PASSPORT_CLEAR"
    assert report["production_ready"] is True
    assert report["ready_for_operator_replacement"] is False
    assert report["summary"]["items_ready"] == 2
    assert report["summary"]["items_blocking"] == 0
    assert report["summary"]["current_raw_files_installed"] == 1
    assert report["summary"]["return_acceptance_raw_ready_to_stage"] is True
    assert report["not_verified_yet"] == []


def test_replacement_passport_adds_raw_operator_files_missing_from_checklist(tmp_path):
    _write_inputs(tmp_path, ready=False)

    report = build_passport(_inputs(tmp_path, include_raw_operator_packet=True))

    assert report["decision"] == "PRODUCTION_EVIDENCE_REPLACEMENT_PASSPORT_READY_FOR_OPERATOR"
    assert report["summary"]["items_total"] == 3
    assert report["summary"]["raw_evidence_items"] == 2
    assert report["summary"]["external_settlement_items"] == 1
    assert report["summary"]["raw_operator_packet_files_total"] == 2
    assert report["summary"]["raw_operator_packet_files_covered_by_checklist"] == 1
    assert report["summary"]["raw_operator_packet_files_added_to_passport"] == 1
    added = next(
        item
        for item in report["replacement_items"]
        if item["raw_id"] == "zero-trust-pqc/mtls-fail-closed.json"
    )
    assert added["item_id"] == "raw_operator_packet:raw_evidence:zero-trust-pqc:zero-trust-pqc/mtls-fail-closed.json"
    assert added["replacement_status"] == "BLOCKED_OPERATOR_EVIDENCE_REQUIRED"
    assert added["operator_return_path"].endswith("zero-trust-pqc/mtls-fail-closed.json")
    assert "goal_audit:production_raw_evidence_operator_packet" in [
        link["id"] for link in added["objective_links"]
    ]


def test_replacement_passport_cli_fails_closed_when_operator_evidence_missing(tmp_path):
    _write_inputs(tmp_path, ready=False)
    output_json = tmp_path / "passport.json"
    verification_json = tmp_path / "passport-verification.json"

    exit_code = main([
        "--root",
        str(tmp_path),
        "--checklist",
        "checklist.json",
        "--coverage",
        "coverage.json",
        "--semantic-replacements",
        "semantic.json",
        "--return-acceptance",
        "return-acceptance.json",
        "--raw-operator-packet-index",
        "raw-operator-packet.json",
        "--output-json",
        str(output_json),
        "--verification-output-json",
        str(verification_json),
        "--require-valid",
        "--require-ready",
    ])

    payload = json.loads(output_json.read_text(encoding="utf-8"))
    verification = json.loads(verification_json.read_text(encoding="utf-8"))
    assert exit_code == 2
    assert payload["production_ready"] is False
    assert payload["summary"]["items_blocking"] == 3
    assert verification["valid"] is True
