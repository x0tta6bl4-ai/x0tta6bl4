import json
from pathlib import Path

from src.integration.rollup_approval_contract import SOURCE_SPECS, build_report, main


def _write_json(root: Path, rel: str, payload: dict) -> None:
    path = root / rel
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(payload), encoding="utf-8")


def _write_text(root: Path, rel: str, text: str = "{}") -> None:
    path = root / rel
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(text, encoding="utf-8")


def _passport_item(spec, *, ready: bool) -> dict:
    rel = f".tmp/{spec.evidence_key}/retained.json"
    return {
        "item_id": f"01:{spec.kind}:{spec.evidence_key}:retained.json",
        "kind": spec.kind,
        "evidence_key": spec.evidence_key,
        "ready": ready,
        "blocks_production": not ready,
        "operator_return_path": rel,
        "retained_destination_path": rel,
    }


def _write_passport(root: Path, *, ready: bool, write_files: bool = True) -> None:
    evidence_specs = [spec for spec in SOURCE_SPECS if spec.kind in {"raw_evidence", "external_settlement"}]
    items = [_passport_item(spec, ready=ready) for spec in evidence_specs]
    for item in items:
        if write_files:
            _write_text(root, item["retained_destination_path"], '{"status":"VERIFIED HERE"}')
    _write_json(
        root,
        "passport.json",
        {
            "status": "VERIFIED HERE",
            "ok": True,
            "decision": "PRODUCTION_EVIDENCE_REPLACEMENT_PASSPORT_CLEAR"
            if ready
            else "PRODUCTION_EVIDENCE_REPLACEMENT_PASSPORT_READY_FOR_OPERATOR",
            "production_ready": ready,
            "required_evidence_files": items,
            "summary": {
                "required_evidence_files_total": len(items),
                "required_evidence_files_ready": len(items) if ready else 0,
            },
        },
    )


def _write_source_reports(root: Path, *, ready: bool) -> None:
    for spec in SOURCE_SPECS:
        decision = spec.expected_decision if ready else "BLOCKED"
        _write_json(
            root,
            spec.path,
            {
                "schema_version": f"test-{spec.label}",
                "status": "VERIFIED HERE",
                "ok": True,
                "decision": decision,
                "entrypoint_decision": decision,
                "ready": ready,
                "production_ready": ready,
                spec.ready_summary_key: ready,
                "not_verified_yet": [] if ready else ["operator evidence required"],
                "summary": {
                    spec.ready_summary_key: ready,
                    "production_ready": ready,
                },
            },
        )


def test_rollup_approval_contract_accepts_valid_blocked_sources(tmp_path):
    _write_passport(tmp_path, ready=False)
    _write_source_reports(tmp_path, ready=False)

    report = build_report(tmp_path, tmp_path / "passport.json", "passport.json")

    assert report["status"] == "VERIFIED HERE"
    assert report["ok"] is True
    assert report["ready"] is False
    assert report["decision"] == "ROLLUP_APPROVAL_BLOCKED_ON_OPERATOR_EVIDENCE"
    assert report["goal_can_be_marked_complete"] is False
    assert report["summary"]["source_errors_total"] == 0
    assert report["summary"]["sources_total"] == len(SOURCE_SPECS)
    assert report["summary"]["sources_ready"] == 0
    evidence_specs = [spec for spec in SOURCE_SPECS if spec.kind in {"raw_evidence", "external_settlement"}]
    assert report["summary"]["evidence_files_total"] == len(evidence_specs)
    assert report["summary"]["evidence_files_valid"] == 0
    assert report["summary"]["evidence_files_invalid"] == len(evidence_specs)
    assert report["summary"]["evidence_files_operator_input_required"] == len(evidence_specs)
    assert all(
        item["status"] == "OPERATOR_INPUT_REQUIRED"
        for source in report["source_reports"]
        for item in source["evidence_files"]
    )


def test_rollup_approval_contract_can_be_ready_when_all_sources_and_evidence_are_ready(tmp_path):
    _write_passport(tmp_path, ready=True)
    _write_source_reports(tmp_path, ready=True)

    report = build_report(tmp_path, tmp_path / "passport.json", "passport.json")

    assert report["ready"] is True
    assert report["decision"] == "ROLLUP_APPROVAL_READY"
    assert report["summary"]["source_errors_total"] == 0
    assert report["summary"]["sources_ready"] == report["summary"]["sources_total"]
    assert report["summary"]["evidence_files_valid"] == report["summary"]["evidence_files_total"]
    assert report["summary"]["evidence_files_operator_input_required"] == 0
    assert report["not_verified_yet"] == []


def test_rollup_approval_contract_reports_missing_source_errors(tmp_path):
    _write_passport(tmp_path, ready=True)

    report = build_report(tmp_path, tmp_path / "passport.json", "passport.json")

    assert report["ready"] is False
    assert report["decision"] == "ROLLUP_APPROVAL_BLOCKED_ON_OPERATOR_EVIDENCE"
    assert report["summary"]["source_errors_total"] == len(SOURCE_SPECS)
    assert report["summary"]["sources_ready"] == 0
    assert report["source_errors"]


def test_rollup_approval_contract_cli_require_ready_returns_two_when_blocked(tmp_path):
    _write_passport(tmp_path, ready=False)
    _write_source_reports(tmp_path, ready=False)
    output_json = tmp_path / "rollup.json"

    exit_code = main([
        "--root",
        str(tmp_path),
        "--passport",
        "passport.json",
        "--output-json",
        str(output_json),
        "--require-ready",
    ])

    payload = json.loads(output_json.read_text(encoding="utf-8"))
    assert exit_code == 2
    assert payload["ready"] is False
    assert payload["summary"]["source_errors_total"] == 0
