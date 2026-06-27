import json
from pathlib import Path

from src.integration.production_input_return_packet import build_report, main


def _write_json(path: Path, payload: dict) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(payload), encoding="utf-8")


def _pipeline(*, ready: bool) -> dict:
    return {
        "status": "VERIFIED HERE",
        "ok": True,
        "ready": ready,
        "pipeline_decision": "READY_FOR_PRODUCTION_CLOSEOUT_REVIEW" if ready else "BLOCKED_INPUT_STAGE",
        "raw_install_results": []
        if ready
        else [
            {
                "collector_id": "zero-trust-pqc",
                "current_status": "LOCAL_OBSERVATION",
                "destination_path": ".tmp/zero-trust-pqc-raw-evidence/operator-manifest.json",
                "errors": ["raw evidence still declares production_ready=false"],
                "evidence_key": "live_spire_mtls",
                "file_name": "operator-manifest.json",
                "raw_id": "zero-trust-pqc/operator-manifest.json",
                "ready_to_stage": False,
                "source_path": ".tmp/integration-spine-production-input-bundle-scaffold/zero-trust-pqc/operator-manifest.json",
                "status": "OPERATOR_INPUT_REQUIRED",
            }
        ],
        "blocking_inputs": []
        if ready
        else [
            {
                "kind": "external_settlement",
                "evidence_key": "external_settlement",
                "destination_path": ".tmp/external-settlement-evidence/settlement-submit.json",
                "errors": ["external settlement receipt missing"],
                "required_action": "submit retained production X0T settlement receipt",
                "status": "OPERATOR_INPUT_REQUIRED",
            }
        ],
        "summary": {
            "blocking_external_inputs": 0 if ready else 1,
            "blocking_path_safety_inputs": 0,
            "external_artifacts_operator_required": 0 if ready else 1,
            "external_settlement_live_rpc_ready": ready,
            "raw_files_expected": 1,
            "raw_files_installed": 1 if ready else 0,
            "raw_files_local_observation": 0 if ready else 1,
            "raw_files_missing": 0,
            "raw_files_ready_to_stage": 1 if ready else 0,
        },
    }


def _completion_gate(*, ready: bool) -> dict:
    return {
        "status": "VERIFIED HERE",
        "ok": True,
        "completion_decision": "COMPLETE" if ready else "NOT_COMPLETE",
        "summary": {"steps_failed_unexpected": 0},
    }


def test_return_packet_marks_operator_actions_as_operator_input_required(tmp_path):
    pipeline = tmp_path / "pipeline.json"
    completion_gate = tmp_path / "completion-gate.json"
    _write_json(pipeline, _pipeline(ready=False))
    _write_json(completion_gate, _completion_gate(ready=False))

    report = build_report(tmp_path, pipeline, completion_gate)

    assert report["decision"] == "RETURN_PACKET_BLOCKED_ON_OPERATOR_EVIDENCE"
    assert report["goal_can_be_marked_complete"] is False
    assert report["summary"]["source_errors_total"] == 0
    assert report["summary"]["blocking_inputs_total"] == 2
    assert report["summary"]["blocking_inputs_operator_input_required"] == 2
    assert report["summary"]["blocking_inputs_generic_operator_required"] == 0
    assert report["summary"]["operator_next_actions_total"] == 2
    assert report["summary"]["operator_next_actions_operator_input_required"] == 2
    assert report["summary"]["operator_next_actions_generic_blocking"] == 0
    assert {item["status"] for item in report["operator_next_actions"]} == {"OPERATOR_INPUT_REQUIRED"}


def test_return_packet_can_report_ready_when_pipeline_and_completion_are_ready(tmp_path):
    pipeline = tmp_path / "pipeline.json"
    completion_gate = tmp_path / "completion-gate.json"
    _write_json(pipeline, _pipeline(ready=True))
    _write_json(completion_gate, _completion_gate(ready=True))

    report = build_report(tmp_path, pipeline, completion_gate)

    assert report["decision"] == "RETURN_PACKET_READY"
    assert report["operator_next_actions"] == []
    assert report["not_verified_yet"] == []
    assert report["summary"]["operator_next_actions_generic_blocking"] == 0


def test_return_packet_source_errors_are_generic_blocking(tmp_path):
    completion_gate = tmp_path / "completion-gate.json"
    _write_json(completion_gate, _completion_gate(ready=False))

    report = build_report(tmp_path, tmp_path / "missing-pipeline.json", completion_gate)

    assert report["decision"] == "RETURN_PACKET_INVALID_SOURCE_ARTIFACTS"
    assert report["summary"]["source_errors_total"] == 1
    assert report["summary"]["operator_next_actions_operator_input_required"] == 0
    assert report["summary"]["operator_next_actions_generic_blocking"] == 0


def test_return_packet_cli_require_ready_returns_two_when_blocked(tmp_path):
    pipeline = tmp_path / "pipeline.json"
    completion_gate = tmp_path / "completion-gate.json"
    output = tmp_path / "return-packet.json"
    _write_json(pipeline, _pipeline(ready=False))
    _write_json(completion_gate, _completion_gate(ready=False))

    exit_code = main(
        [
            "--root",
            str(tmp_path),
            "--pipeline",
            str(pipeline),
            "--completion-gate",
            str(completion_gate),
            "--output-json",
            str(output),
            "--require-ready",
        ]
    )

    payload = json.loads(output.read_text(encoding="utf-8"))
    assert exit_code == 2
    assert payload["decision"] == "RETURN_PACKET_BLOCKED_ON_OPERATOR_EVIDENCE"
    assert payload["summary"]["operator_next_actions_operator_input_required"] == 2
