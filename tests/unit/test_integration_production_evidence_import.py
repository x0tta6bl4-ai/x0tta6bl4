import json
from pathlib import Path

from src.integration.production_evidence_import import build_reports, main
from src.integration.production_evidence_intake import REQUIRED_EVIDENCE_KEYS
from src.integration.production_gap_index import ProductionGapIndexGate


def _write_json(path: Path, payload: dict) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(payload), encoding="utf-8")


def _route(key: str, *, ready: bool = False, exists: bool = True) -> dict:
    is_external = key == "external_settlement"
    source_path = (
        ".tmp/external-settlement-evidence/settlement-submit.json"
        if is_external
        else f".tmp/production-raw-evidence-operator-bundle/{key}/operator-manifest.json"
    )
    candidate = {
        "source_id": "required_artifact:external_settlement" if is_external else f"operator_bundle:{key}",
        "classification": "READY_SOURCE_CANDIDATE" if ready else "OPERATOR_REQUIRED",
        "available": exists,
        "production_artifact": ready,
        "matches_raw_contract": ready,
        "status": "VERIFIED HERE" if ready else "NOT VERIFIED YET",
        "decision": "READY_TO_INSTALL" if ready else "BLOCKED",
        "not_ready_reasons": [] if ready else [f"{key} production evidence missing"],
    }
    if is_external:
        candidate["artifact_path"] = source_path
        candidate["required_artifacts"] = [
            {
                "artifact_path": ".tmp/validation-shards/x0t-external-settlement-live-rpc-current.json",
                "available": ready,
                "ready": ready,
            }
        ]
    else:
        candidate["artifact_paths"] = [source_path]
    return {
        "evidence_key": key,
        "kind": "external_settlement" if is_external else "raw_evidence",
        "collector_id": "external-settlement" if is_external else key,
        "route_classification": "READY_TO_INSTALL" if ready else "PARTIAL_CONTEXT_ONLY",
        "required_artifact_exists": exists if is_external else None,
        "required_artifact_path": source_path if is_external else None,
        "required_operator_action": f"provide production evidence for {key}",
        "collector_command": "" if is_external else f"collect {key}",
        "verification_command": f"verify {key}",
        "raw_paths": [] if is_external else [f".tmp/{key}-raw-evidence/operator-manifest.json"],
        "operator_bundle_paths": [] if is_external else [source_path],
        "semantic_blockers_total": 0 if ready else 1,
        "source_candidates": [candidate],
    }


def _source_candidate(*, ready: bool = False) -> dict:
    return {
        "status": "VERIFIED HERE",
        "ok": True,
        "summary": {
            "required_inputs_total": len(REQUIRED_EVIDENCE_KEYS),
            "required_inputs_ready": len(REQUIRED_EVIDENCE_KEYS) if ready else 0,
            "ready_source_candidates_total": len(REQUIRED_EVIDENCE_KEYS) if ready else 0,
        },
        "evidence_source_routes": [_route(key, ready=ready, exists=key != "external_settlement" or ready) for key in sorted(REQUIRED_EVIDENCE_KEYS)],
    }


def _completion_audit(*, ready: bool = False) -> dict:
    return {
        "status": "VERIFIED HERE",
        "ok": True,
        "completion_decision": "COMPLETE" if ready else "NOT_COMPLETE",
        "goal_can_be_marked_complete": ready,
        "summary": {
            "checklist_total": 48,
            "checklist_passed": 48 if ready else 40,
            "checklist_blocking": 0 if ready else 8,
            "local_wiring_passed": True,
            "production_readiness_passed": ready,
        },
    }


def test_production_evidence_import_builds_all_required_keys_fail_closed(tmp_path):
    source = tmp_path / "source.json"
    _write_json(source, _source_candidate(ready=False))

    next_report, import_report = build_reports(tmp_path, source, "source.json")

    assert import_report["production_evidence_import_decision"] == "BLOCKED_PRODUCTION_EVIDENCE"
    assert import_report["materializes_evidence"] is False
    assert import_report["summary"]["source_artifacts_total"] == len(REQUIRED_EVIDENCE_KEYS)
    assert import_report["summary"]["source_artifacts_ready"] == 0
    assert len(import_report["source_results"]) == len(REQUIRED_EVIDENCE_KEYS)
    assert next_report["decision"] == "BLOCKED_PRODUCTION_INPUTS"
    assert next_report["summary"]["required_inputs_total"] == len(REQUIRED_EVIDENCE_KEYS)
    assert next_report["summary"]["required_inputs_ready"] == 0
    assert {item["evidence_key"] for item in next_report["required_inputs"]} == REQUIRED_EVIDENCE_KEYS


def test_production_evidence_import_clears_route_missing_for_gap_index(tmp_path):
    source = tmp_path / "source.json"
    next_path = tmp_path / "next.json"
    import_path = tmp_path / "import.json"
    audit_path = tmp_path / "audit.json"
    _write_json(source, _source_candidate(ready=False))
    next_report, import_report = build_reports(tmp_path, source, "source.json")
    _write_json(next_path, next_report)
    _write_json(import_path, import_report)
    _write_json(audit_path, _completion_audit(ready=False))

    report = ProductionGapIndexGate.load(next_path, import_path, audit_path).report()

    assert report["decision"] == "BLOCKED_ON_OPERATOR_EVIDENCE"
    assert report["summary"]["route_missing"] == 0
    assert report["summary"]["pending_evidence_keys"] == len(REQUIRED_EVIDENCE_KEYS)
    assert set(report["blocking_evidence_keys"]) == REQUIRED_EVIDENCE_KEYS


def test_production_evidence_import_cli_writes_both_artifacts(tmp_path):
    _write_json(
        tmp_path / ".tmp/validation-shards/integration-spine-evidence-source-candidate-audit-current.json",
        _source_candidate(ready=False),
    )

    exit_code = main(["--root", str(tmp_path), "--require-ready"])

    assert exit_code == 2
    next_report = json.loads(
        (tmp_path / ".tmp/validation-shards/integration-spine-production-next-inputs-current.json").read_text(
            encoding="utf-8"
        )
    )
    import_report = json.loads(
        (tmp_path / ".tmp/validation-shards/integration-spine-production-evidence-import-current.json").read_text(
            encoding="utf-8"
        )
    )
    assert next_report["summary"]["required_inputs_total"] == len(REQUIRED_EVIDENCE_KEYS)
    assert import_report["summary"]["source_artifacts_total"] == len(REQUIRED_EVIDENCE_KEYS)
