import json
from pathlib import Path

from src.integration.evidence_readiness import EvidenceReadinessGate, main


def _write_json(path: Path, payload: dict) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(payload), encoding="utf-8")


def _raw_inventory(*, ready: bool) -> dict:
    records = []
    for idx in range(2):
        records.append(
            {
                "path": f".tmp/raw-{idx}.json",
                "evidence_status": "VERIFIED HERE",
                "usable_for_goal_completion": ready,
                "classification": "PRODUCTION_GRADE" if ready else "RETAINED_COMPONENT_EVIDENCE_NOT_PRODUCTION_GRADE",
                "template_only": False,
                "fake_or_simulated": False,
                "semantic_blockers_total": 0 if ready else 1,
                "semantic_preflight_errors": [] if ready else ["not production"],
            }
        )
    return {
        "status": "VERIFIED HERE",
        "ok": True,
        "summary": {
            "files_total": 2,
            "pipeline_raw_files_expected": 2,
            "pipeline_raw_files_installed": 2,
            "pipeline_raw_files_reported_installed": 2,
            "raw_install_claim_source": "return_acceptance",
            "return_acceptance_raw_files_expected": 2,
            "return_acceptance_raw_files_staged": 2 if ready else 0,
            "return_acceptance_raw_files_ready_to_stage": 2 if ready else 0,
            "return_acceptance_raw_files_destination_existing": 2,
            "return_acceptance_raw_files_local_observation": 0 if ready else 2,
            "return_acceptance_raw_ready_to_stage": ready,
            "template_only_files": 0,
            "fake_or_simulated_files": 0,
            "usable_for_goal_completion_files": 2 if ready else 0,
            "semantic_blockers_total": 0 if ready else 2,
            "classification_counts": {"PRODUCTION_GRADE": 2} if ready else {"RETAINED_COMPONENT_EVIDENCE_NOT_PRODUCTION_GRADE": 2},
        },
        "records": records,
    }


def _semantic_queue(*, ready: bool) -> dict:
    return {
        "status": "VERIFIED HERE",
        "ok": True,
        "completion_decision": "COMPLETE" if ready else "NOT_COMPLETE",
        "goal_can_be_marked_complete": ready,
        "blocking_items": [] if ready else [{"id": "blocker:001"}],
        "priority_order": [] if ready else ["blocker:001"],
        "summary": {
            "blocking_items_total": 0 if ready else 1,
            "semantic_preflight_errors_total": 0 if ready else 1,
            "collector_groups_blocking": 0 if ready else 1,
            "current_external_settlement_ready": ready,
        },
    }


def test_evidence_readiness_blocks_component_evidence_and_semantic_blockers(tmp_path):
    raw = tmp_path / "raw.json"
    semantic = tmp_path / "semantic.json"
    _write_json(raw, _raw_inventory(ready=False))
    _write_json(semantic, _semantic_queue(ready=False))

    report = EvidenceReadinessGate.load(raw, semantic).report()

    assert report["decision"] == "BLOCKED_ON_PRODUCTION_EVIDENCE"
    assert report["summary"]["raw_inventory_ready"] is False
    assert report["summary"]["semantic_queue_ready"] is False
    assert report["raw_inventory_errors"]
    assert report["semantic_queue_errors"]


def test_evidence_readiness_accepts_zero_blocker_production_grade_evidence(tmp_path):
    raw = tmp_path / "raw.json"
    semantic = tmp_path / "semantic.json"
    _write_json(raw, _raw_inventory(ready=True))
    _write_json(semantic, _semantic_queue(ready=True))

    report = EvidenceReadinessGate.load(raw, semantic).report()

    assert report["decision"] == "READY_TO_PROMOTE"
    assert report["summary"]["production_evidence_ready"] is True
    assert report["raw_inventory_errors"] == []
    assert report["semantic_queue_errors"] == []


def test_evidence_readiness_cli_writes_fail_closed_report(tmp_path):
    exit_code = main(["--root", str(tmp_path), "--require-ready"])

    assert exit_code == 2
    report = json.loads(
        (tmp_path / ".tmp/validation-shards/integration-spine-evidence-readiness-current.json").read_text(
            encoding="utf-8"
        )
    )
    assert report["decision"] == "BLOCKED_ON_PRODUCTION_EVIDENCE"
    assert report["summary"]["production_evidence_ready"] is False
