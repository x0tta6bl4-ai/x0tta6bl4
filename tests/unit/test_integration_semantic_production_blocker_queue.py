import json
from pathlib import Path

from src.integration.semantic_production_blocker_queue import QueueInputs, build_queue, main


def _write_json(path: Path, payload: dict) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(payload), encoding="utf-8")


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

    report = build_queue(QueueInputs(tmp_path, pipeline, coverage, acceptance, "pipeline.json", "coverage.json", "return-acceptance.json"))

    assert report["completion_decision"] == "COMPLETE"
    assert report["goal_can_be_marked_complete"] is True
    assert report["summary"]["current_raw_files_installed"] == 1
    assert report["summary"]["return_acceptance_raw_ready_to_stage"] is True
    assert report["summary"]["blocking_items_operator_input_required"] == 0
    assert report["summary"]["blocking_items_generic_blocking"] == 0
    assert report["blocking_items"] == []
    assert report["priority_order"] == []


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
