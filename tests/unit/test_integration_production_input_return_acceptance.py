import json
from pathlib import Path

from src.integration.production_input_return_acceptance import build_report, main


def _write_json(root: Path, rel: str, payload: dict) -> None:
    path = root / rel
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(payload), encoding="utf-8")


def _write_text(root: Path, rel: str, text: str = "{}") -> None:
    path = root / rel
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(text, encoding="utf-8")


def _raw_file(*, ready: bool, destination: str = ".tmp/raw/operator-manifest.json") -> dict:
    return {
        "file_name": "operator-manifest.json",
        "install_destination_path": destination,
        "ready": ready,
        "current_status": "VERIFIED HERE" if ready else "LOCAL_OBSERVATION",
        "errors": [] if ready else ["raw evidence still declares production_ready=false"],
        "required_operator_provenance_fields": ["collected_at", "collected_by", "source_commands"],
        "required_status": "VERIFIED HERE",
        "template_rejected": True,
    }


def _write_sources(root: Path, *, ready: bool, staged_raw: bool = False) -> None:
    raw_destination = ".tmp/raw/operator-manifest.json"
    if ready or staged_raw:
        _write_text(root, raw_destination, '{"status":"VERIFIED HERE"}')
    _write_json(
        root,
        "manifest.json",
        {
            "status": "VERIFIED HERE",
            "ok": True,
            "decision": "READY_FOR_PRODUCTION_CLOSEOUT_REVIEW" if ready else "OPERATOR_INPUT_BUNDLE_REQUIRED",
            "input_groups": [
                {
                    "input_kind": "raw_evidence_bundle",
                    "evidence_key": "live_spire_mtls",
                    "raw_files": [_raw_file(ready=ready, destination=raw_destination)],
                },
                {
                    "input_kind": "external_artifact",
                    "evidence_key": "external_settlement",
                    "ready": ready,
                    "artifact_ready": ready,
                    "required_artifact_path": ".tmp/external-settlement-evidence/settlement-submit.json",
                },
            ],
        },
    )
    if ready:
        _write_text(root, ".tmp/external-settlement-evidence/settlement-submit.json", '{"status":"VERIFIED HERE"}')
    _write_json(
        root,
        "live-rpc.json",
        {
            "status": "VERIFIED HERE",
            "ok": True,
            "summary": {
                "evidence_file_found": ready,
                "retained_evidence_ready": ready,
                "live_rpc_checked": ready,
                "x0t_external_settlement_live_rpc_ready": ready,
            },
        },
    )


def test_return_acceptance_accepts_current_valid_blocked_shape(tmp_path):
    _write_sources(tmp_path, ready=False, staged_raw=True)

    report = build_report(tmp_path, tmp_path / "manifest.json", tmp_path / "live-rpc.json")

    assert report["status"] == "VERIFIED HERE"
    assert report["ok"] is True
    assert report["decision"] == "RETURN_ACCEPTANCE_BLOCKED_ON_OPERATOR_EVIDENCE"
    assert report["acceptance_decision"] == "RETURN_ACCEPTANCE_BLOCKED"
    assert report["ready_to_stage"] is False
    assert report["ready_for_pipeline_install"] is False
    assert report["summary"]["source_errors_total"] == 0
    assert report["summary"]["raw_ready_to_stage"] is False
    assert report["summary"]["raw_files_already_staged"] == 0
    assert report["summary"]["raw_files_destination_existing"] == 1
    assert report["summary"]["raw_files_local_observation"] == 1
    assert report["summary"]["external_artifacts_operator_required"] == 1
    assert report["summary"]["external_settlement_live_rpc_ready"] is False
    assert report["summary"]["evidence_status_counts"] == {"OPERATOR_INPUT_REQUIRED": 2}
    assert report["summary"]["evidence_operator_input_required"] == 2
    assert report["summary"]["evidence_generic_operator_required"] == 0
    assert {
        status
        for item in report["evidence_key_acceptance"]
        for status in item["statuses"]
    } == {"OPERATOR_INPUT_REQUIRED"}


def test_return_acceptance_can_be_ready_when_raw_and_external_inputs_are_ready(tmp_path):
    _write_sources(tmp_path, ready=True)

    report = build_report(tmp_path, tmp_path / "manifest.json", tmp_path / "live-rpc.json")

    assert report["decision"] == "RETURN_ACCEPTANCE_READY"
    assert report["acceptance_decision"] == "RETURN_ACCEPTANCE_READY"
    assert report["ready_to_stage"] is True
    assert report["ready_for_pipeline_install"] is True
    assert report["summary"]["external_artifacts_ready_to_stage"] == 1
    assert report["summary"]["evidence_status_counts"] == {"ALREADY_STAGED": 1, "READY_TO_STAGE": 1}
    assert report["not_verified_yet"] == []


def test_return_acceptance_reports_missing_manifest_source_error(tmp_path):
    _write_json(
        tmp_path,
        "live-rpc.json",
        {
            "status": "VERIFIED HERE",
            "ok": True,
            "summary": {
                "evidence_file_found": False,
                "retained_evidence_ready": False,
                "live_rpc_checked": False,
                "x0t_external_settlement_live_rpc_ready": False,
            },
        },
    )

    report = build_report(tmp_path, tmp_path / "missing.json", tmp_path / "live-rpc.json")

    assert report["decision"] == "RETURN_ACCEPTANCE_INVALID_SOURCE_ARTIFACTS"
    assert report["summary"]["source_errors_total"] == 1
    assert report["ready_for_pipeline_install"] is False


def test_return_acceptance_cli_require_ready_returns_two_when_blocked(tmp_path):
    _write_sources(tmp_path, ready=False, staged_raw=True)
    output_json = tmp_path / "acceptance.json"

    exit_code = main([
        "--root",
        str(tmp_path),
        "--input-manifest",
        "manifest.json",
        "--external-settlement-live-rpc",
        "live-rpc.json",
        "--output-json",
        str(output_json),
        "--require-ready",
    ])

    payload = json.loads(output_json.read_text(encoding="utf-8"))
    assert exit_code == 2
    assert payload["decision"] == "RETURN_ACCEPTANCE_BLOCKED_ON_OPERATOR_EVIDENCE"
    assert payload["summary"]["source_errors_total"] == 0
