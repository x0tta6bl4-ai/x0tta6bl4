import json
from pathlib import Path

from src.integration.raw_evidence_inventory import InventoryInputs, build_inventory, main


def _write_json(path: Path, payload: dict) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(payload), encoding="utf-8")


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

    report = build_inventory(InventoryInputs(tmp_path, pipeline, semantic, acceptance, "pipeline.json", "semantic.json", "return-acceptance.json"))

    assert report["completion_decision"] == "COMPLETE"
    assert report["goal_can_be_marked_complete"] is True
    assert report["summary"]["return_acceptance_raw_files_staged"] == 1
    assert report["summary"]["return_acceptance_raw_ready_to_stage"] is True
    assert report["summary"]["usable_for_goal_completion_files"] == 1
    assert report["summary"]["classification_counts"] == {"PRODUCTION_GRADE": 1}


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
