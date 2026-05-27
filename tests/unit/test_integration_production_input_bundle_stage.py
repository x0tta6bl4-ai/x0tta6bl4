import json
from pathlib import Path

from src.integration.production_input_bundle_stage import build_report, main


def _write_json(root: Path, rel: str, payload: dict) -> None:
    path = root / rel
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(payload), encoding="utf-8")


def _base_sources(root: Path, *, ready: bool) -> None:
    raw_expected = 2
    raw_staged = raw_expected if ready else 0
    raw_ready = raw_expected if ready else 0
    _write_json(
        root,
        ".tmp/validation-shards/integration-spine-production-input-return-acceptance-current.json",
        {
            "status": "VERIFIED HERE",
            "ok": True,
            "decision": "RETURN_ACCEPTANCE_READY" if ready else "RETURN_ACCEPTANCE_BLOCKED_ON_OPERATOR_EVIDENCE",
            "ready_to_stage": ready,
            "ready_for_pipeline_install": ready,
            "summary": {
                "raw_files_expected": raw_expected,
                "raw_files_staged": raw_staged,
                "raw_files_ready_to_stage": raw_ready,
                "raw_files_local_observation": 0 if ready else raw_expected,
                "raw_ready_to_stage": ready,
                "ready_for_pipeline_install": ready,
                "external_artifacts_expected": 1,
                "external_artifacts_staged": 1 if ready else 0,
                "external_artifacts_ready_to_stage": 1 if ready else 0,
                "external_artifacts_operator_required": 0 if ready else 1,
                "external_settlement_live_rpc_ready": ready,
                "external_settlement_live_rpc_checked": ready,
                "secret_scan_decision": "OPERATOR_BUNDLE_SECRET_SCAN_CLEAR",
                "secret_scan_findings": 0,
                "secret_scan_source_errors": 0,
            },
            "evidence_key_acceptance": [
                {
                    "evidence_key": "raw_identity",
                    "files_expected": raw_expected,
                    "files_staged": raw_staged,
                    "files_ready_to_stage": raw_ready,
                    "files_operator_required": 0 if ready else raw_expected,
                    "files_blocked": 0 if ready else raw_expected,
                    "ready_to_stage": ready,
                    "statuses": {"ALREADY_STAGED" if ready else "OPERATOR_INPUT_REQUIRED": raw_expected},
                    "errors": [] if ready else ["raw evidence is still a local observation"],
                },
                {
                    "evidence_key": "external_settlement",
                    "files_expected": 1,
                    "files_staged": 1 if ready else 0,
                    "files_ready_to_stage": 1 if ready else 0,
                    "files_operator_required": 0 if ready else 1,
                    "files_blocked": 0 if ready else 1,
                    "ready_to_stage": ready,
                    "errors": [] if ready else ["external settlement requires live RPC receipt"],
                },
            ],
        },
    )
    _write_json(
        root,
        ".tmp/validation-shards/integration-spine-production-input-pipeline-current.json",
        {
            "status": "VERIFIED HERE",
            "ok": True,
            "pipeline_decision": "READY_FOR_PRODUCTION_CLOSEOUT_REVIEW" if ready else "PARTIAL_RAW_COLLECTOR_BLOCKED_ON_EVIDENCE",
            "ready": ready,
            "summary": {
                "raw_files_installed": raw_staged,
                "raw_files_staged": raw_staged,
            },
        },
    )


def test_stage_gate_fails_closed_without_operator_evidence(tmp_path):
    _base_sources(tmp_path, ready=False)

    report = build_report(
        tmp_path,
        tmp_path / ".tmp/validation-shards/integration-spine-production-input-return-acceptance-current.json",
        tmp_path / ".tmp/validation-shards/integration-spine-production-input-pipeline-current.json",
    )

    assert report["schema_version"].endswith("v4-repo-generated")
    assert "source-restored" not in report["schema_version"]
    assert report["stage_decision"] == "SCOPED_INPUT_BUNDLE_BLOCKED"
    assert report["ready_to_stage"] is False
    assert report["goal_can_be_marked_complete"] is False
    assert report["mutates_files"] is False
    assert report["summary"]["raw_files_staged"] == 0
    assert report["summary"]["raw_files_ready_to_stage"] == 0
    assert report["summary"]["raw_files_local_observation"] == 2
    assert report["summary"]["raw_files_operator_required"] == 2
    assert report["summary"]["external_settlement_live_rpc_ready"] is False
    assert report["summary"]["blocking_inputs_total"] == 2
    assert report["blocking_inputs"][0]["status"] == "OPERATOR_INPUT_REQUIRED"
    assert report["summary"]["blocking_inputs_operator_input_required"] == 2
    assert report["summary"]["blocking_inputs_generic_operator_required"] == 0


def test_stage_gate_can_complete_when_return_acceptance_and_pipeline_are_ready(tmp_path):
    _base_sources(tmp_path, ready=True)

    report = build_report(
        tmp_path,
        tmp_path / ".tmp/validation-shards/integration-spine-production-input-return-acceptance-current.json",
        tmp_path / ".tmp/validation-shards/integration-spine-production-input-pipeline-current.json",
    )

    assert report["stage_decision"] == "SCOPED_INPUT_BUNDLE_READY"
    assert report["ready_to_stage"] is True
    assert report["summary"]["raw_files_staged"] == 2
    assert report["summary"]["external_settlement_live_rpc_ready"] is True


def test_stage_gate_cli_require_ready_returns_two_when_blocked(tmp_path):
    _base_sources(tmp_path, ready=False)
    output_json = tmp_path / "stage.json"

    exit_code = main(["--root", str(tmp_path), "--output-json", str(output_json), "--require-ready"])

    payload = json.loads(output_json.read_text(encoding="utf-8"))
    assert exit_code == 2
    assert payload["stage_decision"] == "SCOPED_INPUT_BUNDLE_BLOCKED"
    assert payload["summary"]["raw_files_staged"] == 0
