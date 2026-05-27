import json
from pathlib import Path

from src.integration.production_input_pipeline import build_report, main


def _write_json(root: Path, rel: str, payload: dict) -> None:
    path = root / rel
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(payload), encoding="utf-8")


def _return_acceptance(*, ready: bool) -> dict:
    return {
        "schema_version": "test-return-acceptance",
        "status": "VERIFIED HERE",
        "ok": True,
        "decision": "RETURN_ACCEPTANCE_READY" if ready else "RETURN_ACCEPTANCE_BLOCKED_ON_OPERATOR_EVIDENCE",
        "ready_to_stage": ready,
        "ready_for_pipeline_install": ready,
        "goal_can_be_marked_complete": False,
        "evidence_key_acceptance": [
            {
                "evidence_key": "live_spire_mtls",
                "ready_to_stage": ready,
                "files_expected": 2,
                "files_blocked": 0 if ready else 2,
                "errors": [] if ready else ["raw evidence is still a local observation"],
            },
            {
                "evidence_key": "external_settlement",
                "ready_to_stage": ready,
                "files_expected": 1,
                "files_blocked": 0 if ready else 1,
                "errors": [] if ready else ["external settlement live RPC is missing"],
            },
        ],
        "summary": {
            "source_errors_total": 0,
            "evidence_keys_total": 2,
            "evidence_keys_ready_to_stage": 2 if ready else 0,
            "raw_files_expected": 2,
            "raw_files_staged": 2 if ready else 0,
            "raw_files_ready_to_stage": 2 if ready else 0,
            "raw_files_local_observation": 0 if ready else 2,
            "raw_files_missing": 0,
            "raw_files_invalid_json": 0,
            "raw_files_fake_evidence": 0,
            "raw_files_template_only": 0,
            "raw_files_missing_provenance": 0,
            "raw_files_wrong_status": 0,
            "raw_files_destination_existing": 2,
            "raw_ready_to_stage": ready,
            "external_artifacts_ready_to_stage": 1 if ready else 0,
            "external_artifacts_operator_required": 0 if ready else 1,
            "external_settlement_live_rpc_ready": ready,
            "ready_to_stage": ready,
            "ready_for_pipeline_install": ready,
            "secret_scan_source_errors": 0,
        },
    }


def _input_manifest(*, ready: bool) -> dict:
    return {
        "status": "VERIFIED HERE",
        "ok": True,
        "input_groups": [
            {
                "input_kind": "raw_evidence_bundle",
                "collector_id": "zero-trust-pqc",
                "evidence_key": "live_spire_mtls",
                "collector_command": "collect live_spire_mtls",
                "raw_files": [
                    {
                        "file_name": "operator-manifest.json",
                        "raw_id": "zero-trust-pqc/operator-manifest.json",
                        "source_raw_path": ".tmp/source/operator-manifest.json",
                        "install_destination_path": ".tmp/raw/operator-manifest.json",
                        "ready": ready,
                        "current_status": "VERIFIED HERE" if ready else "LOCAL_OBSERVATION",
                        "errors": [] if ready else ["raw evidence is still a local observation"],
                    },
                    {
                        "file_name": "identity.json",
                        "raw_id": "zero-trust-pqc/identity.json",
                        "source_raw_path": ".tmp/source/identity.json",
                        "install_destination_path": ".tmp/raw/identity.json",
                        "ready": ready,
                        "current_status": "VERIFIED HERE" if ready else "LOCAL_OBSERVATION",
                        "errors": [] if ready else ["raw evidence still declares production_ready=false"],
                    },
                ],
            }
        ],
    }


def test_input_pipeline_uses_return_acceptance_staged_count_when_blocked(tmp_path):
    _write_json(tmp_path, "return.json", _return_acceptance(ready=False))
    _write_json(tmp_path, "manifest.json", _input_manifest(ready=False))

    report = build_report(tmp_path, tmp_path / "return.json", tmp_path / "manifest.json")

    assert report["status"] == "VERIFIED HERE"
    assert report["ok"] is True
    assert report["pipeline_decision"] == "PARTIAL_RAW_COLLECTOR_BLOCKED_ON_EVIDENCE"
    assert report["ready"] is False
    assert report["goal_can_be_marked_complete"] is False
    assert report["summary"]["raw_files_installed"] == 0
    assert report["summary"]["raw_files_staged"] == 0
    assert report["summary"]["raw_files_install_claim_source"] == "return_acceptance"
    assert report["summary"]["raw_files_local_observation"] == 2
    assert report["summary"]["blocking_inputs_total"] == 2
    assert report["summary"]["collector_evidence_blockers"] == 2
    assert len(report["raw_install_results"]) == 2
    assert report["blocking_inputs"][0]["status"] == "OPERATOR_INPUT_REQUIRED"
    assert report["summary"]["blocking_inputs_operator_input_required"] == 2
    assert report["summary"]["blocking_inputs_generic_operator_required"] == 0
    assert report["raw_install_results"][0]["status"] == "OPERATOR_INPUT_REQUIRED"
    assert report["summary"]["raw_install_operator_input_required"] == 2
    assert report["summary"]["raw_install_generic_operator_required"] == 0
    assert report["command_results"][0]["preflight_errors"]


def test_input_pipeline_can_be_ready_when_return_acceptance_is_ready(tmp_path):
    _write_json(tmp_path, "return.json", _return_acceptance(ready=True))
    _write_json(tmp_path, "manifest.json", _input_manifest(ready=True))

    report = build_report(tmp_path, tmp_path / "return.json", tmp_path / "manifest.json")

    assert report["pipeline_decision"] == "READY_FOR_PRODUCTION_CLOSEOUT_REVIEW"
    assert report["ready"] is True
    assert report["summary"]["raw_files_installed"] == 2
    assert report["summary"]["raw_files_install_claim_source"] == "return_acceptance"
    assert report["blocking_inputs"] == []
    assert report["raw_install_results"][0]["status"] == "READY_TO_STAGE"
    assert report["not_verified_yet"] == []


def test_input_pipeline_reports_missing_return_acceptance_source_error(tmp_path):
    report = build_report(tmp_path, tmp_path / "missing.json", tmp_path / "missing-manifest.json")

    assert report["pipeline_decision"] == "INPUT_PIPELINE_INVALID_SOURCE_ARTIFACTS"
    assert report["ready"] is False
    assert report["summary"]["source_errors_total"] == 2


def test_input_pipeline_cli_require_ready_returns_two_when_blocked(tmp_path):
    _write_json(tmp_path, "return.json", _return_acceptance(ready=False))
    _write_json(tmp_path, "manifest.json", _input_manifest(ready=False))
    output_json = tmp_path / "pipeline.json"

    exit_code = main([
        "--root",
        str(tmp_path),
        "--return-acceptance",
        "return.json",
        "--input-manifest",
        "manifest.json",
        "--output-json",
        str(output_json),
        "--require-ready",
    ])

    payload = json.loads(output_json.read_text(encoding="utf-8"))
    assert exit_code == 2
    assert payload["pipeline_decision"] == "PARTIAL_RAW_COLLECTOR_BLOCKED_ON_EVIDENCE"
    assert payload["summary"]["raw_files_installed"] == 0
