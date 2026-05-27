import json
from pathlib import Path

from src.integration.production_evidence_intake import (
    REQUIRED_EVIDENCE_KEYS,
    ProductionEvidenceIntakeGate,
    main,
)


def _write_json(path: Path, payload: dict) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(payload), encoding="utf-8")


def _route(key: str, *, ready: bool, file_report_summary: dict | None = None) -> dict:
    source_id = f"candidate:{key}"
    if file_report_summary is not None:
        source_id = f"operator_bundle:{key}"
    candidate = {
        "source_id": source_id,
        "classification": "READY_SOURCE_CANDIDATE" if ready else "OPERATOR_REQUIRED",
        "available": True,
        "production_artifact": ready,
        "matches_raw_contract": ready,
        "status": "VERIFIED HERE" if ready else "blocked",
        "decision": "READY" if ready else "BLOCKED",
        "artifact_path": f".tmp/{key}/raw.json",
        "not_ready_reasons": [] if ready else ["operator evidence missing"],
    }
    if file_report_summary is not None:
        candidate["file_report_summary"] = file_report_summary
    return {
        "evidence_key": key,
        "kind": "raw_evidence" if key != "external_settlement" else "external_settlement",
        "route_classification": "READY_TO_INSTALL" if ready else "PARTIAL_CONTEXT_ONLY",
        "semantic_blockers_total": 0 if ready else 3,
        "required_artifact_exists": True if key == "external_settlement" and ready else None,
        "required_artifact_path": ".tmp/external-settlement-evidence/settlement-submit.json",
        "required_operator_action": "replace retained component evidence with production evidence",
        "raw_paths": [f".tmp/{key}/raw.json"],
        "operator_bundle_paths": [f".tmp/production-raw-evidence-operator-bundle/{key}/raw.json"],
        "source_candidates": [candidate],
    }


def _source_candidate(*, ready: bool) -> dict:
    return {
        "status": "VERIFIED HERE",
        "ok": True,
        "summary": {
            "required_inputs_ready": len(REQUIRED_EVIDENCE_KEYS) if ready else 0,
            "required_inputs_total": len(REQUIRED_EVIDENCE_KEYS),
            "ready_source_candidates_total": len(REQUIRED_EVIDENCE_KEYS) if ready else 0,
        },
        "evidence_source_routes": [_route(key, ready=ready) for key in sorted(REQUIRED_EVIDENCE_KEYS)],
    }


def _production_import(*, ready: bool) -> dict:
    return {
        "status": "VERIFIED HERE",
        "summary": {
            "production_evidence_complete": ready,
            "source_artifacts_ready": len(REQUIRED_EVIDENCE_KEYS) if ready else 0,
            "source_artifacts_total": len(REQUIRED_EVIDENCE_KEYS),
        },
    }


def _raw_readiness(*, ready: bool) -> dict:
    return {
        "status": "VERIFIED HERE",
        "summary": {
            "collectors_blocked": 0 if ready else 1,
            "collectors_ready": 1 if ready else 0,
            "collectors_total": 1,
            "raw_files_conflicting_status_fields": 0,
            "raw_files_invalid_json": 0,
            "raw_files_ready": 63 if ready else 0,
            "raw_files_local_observation": 0 if ready else 63,
            "raw_files_missing": 0,
            "raw_files_placeholder_collected_by": 0,
            "raw_files_placeholder_source_commands": 0,
            "raw_files_placeholder_values": 0,
            "raw_files_total": 63,
        },
    }


def test_production_evidence_intake_blocks_when_operator_candidates_are_not_ready(tmp_path):
    source = tmp_path / "source.json"
    import_path = tmp_path / "import.json"
    raw = tmp_path / "raw.json"
    _write_json(source, _source_candidate(ready=False))
    _write_json(import_path, _production_import(ready=False))
    _write_json(raw, _raw_readiness(ready=True))

    report = ProductionEvidenceIntakeGate.load(source, import_path, raw).report()

    assert report["decision"] == "BLOCKED_OPERATOR_EVIDENCE_REQUIRED"
    assert report["summary"]["required_evidence_keys_ready"] == 0
    assert report["summary"]["raw_operator_bundle_structure_ready"] is True
    assert report["summary"]["raw_operator_bundle_production_content_ready"] is True
    assert set(report["pending_evidence_keys"]) == REQUIRED_EVIDENCE_KEYS
    assert report["blocking_reasons"]


def test_production_evidence_intake_accepts_complete_ready_source_candidates(tmp_path):
    source = tmp_path / "source.json"
    import_path = tmp_path / "import.json"
    raw = tmp_path / "raw.json"
    _write_json(source, _source_candidate(ready=True))
    _write_json(import_path, _production_import(ready=True))
    _write_json(raw, _raw_readiness(ready=True))

    report = ProductionEvidenceIntakeGate.load(source, import_path, raw).report()

    assert report["decision"] == "READY_FOR_INSTALL"
    assert report["summary"]["ready_for_install"] is True
    assert report["summary"]["raw_operator_bundle_structure_ready"] is True
    assert report["summary"]["raw_operator_bundle_production_content_ready"] is True
    assert set(report["ready_evidence_keys"]) == REQUIRED_EVIDENCE_KEYS
    assert report["blocking_reasons"] == []


def test_production_evidence_intake_separates_structure_from_production_content(tmp_path):
    source = tmp_path / "source.json"
    import_path = tmp_path / "import.json"
    raw = tmp_path / "raw.json"
    _write_json(source, _source_candidate(ready=False))
    _write_json(import_path, _production_import(ready=False))
    _write_json(raw, _raw_readiness(ready=False))

    report = ProductionEvidenceIntakeGate.load(source, import_path, raw).report()

    assert report["decision"] == "BLOCKED_OPERATOR_EVIDENCE_REQUIRED"
    assert report["summary"]["raw_operator_bundle_syntax_ready"] is True
    assert report["summary"]["raw_operator_bundle_structure_ready"] is True
    assert report["summary"]["raw_operator_bundle_identity_ready"] is True
    assert report["summary"]["raw_operator_bundle_production_content_ready"] is False
    assert "raw evidence operator bundle is structurally ready but not production-grade" in report["blocking_reasons"]


def test_production_evidence_intake_cli_writes_fail_closed_report(tmp_path):
    exit_code = main(["--root", str(tmp_path), "--require-ready"])

    assert exit_code == 2
    report = json.loads(
        (tmp_path / ".tmp/validation-shards/integration-spine-production-evidence-intake-current.json").read_text(
            encoding="utf-8"
        )
    )
    assert report["decision"] == "BLOCKED_OPERATOR_EVIDENCE_REQUIRED"
    assert report["summary"]["ready_for_install"] is False


def test_production_evidence_intake_preserves_operator_bundle_identity_mismatch_counts(tmp_path):
    source = tmp_path / "source.json"
    import_path = tmp_path / "import.json"
    raw = tmp_path / "raw.json"
    file_report_summary = {
        "files_total": 2,
        "files_available": 2,
        "manifest_identity_mismatches_total": 2,
        "collector_id_mismatches": 1,
        "raw_id_mismatches": 1,
        "file_name_mismatches": 0,
    }
    source_candidate = _source_candidate(ready=False)
    source_candidate["evidence_source_routes"] = [
        _route("external_settlement", ready=False),
        _route("live_spire_mtls", ready=False, file_report_summary=file_report_summary),
        *[_route(key, ready=False) for key in sorted(REQUIRED_EVIDENCE_KEYS - {"external_settlement", "live_spire_mtls"})],
    ]
    _write_json(source, source_candidate)
    _write_json(import_path, _production_import(ready=False))
    _write_json(raw, _raw_readiness(ready=True))

    report = ProductionEvidenceIntakeGate.load(source, import_path, raw).report()

    assert report["decision"] == "BLOCKED_OPERATOR_EVIDENCE_REQUIRED"
    assert report["summary"]["bundle_manifest_identity_mismatches_total"] == 2
    assert report["summary"]["bundle_collector_id_mismatches"] == 1
    assert report["summary"]["bundle_raw_id_mismatches"] == 1
    assert report["summary"]["raw_operator_bundle_syntax_ready"] is False
    assert report["summary"]["raw_operator_bundle_structure_ready"] is False
    assert report["summary"]["raw_operator_bundle_identity_ready"] is False
    status = next(item for item in report["evidence_key_statuses"] if item["evidence_key"] == "live_spire_mtls")
    assert status["operator_bundle_file_report_summary"] == file_report_summary
    assert status["rejected_or_context_sources"][0]["file_report_summary"] == file_report_summary
