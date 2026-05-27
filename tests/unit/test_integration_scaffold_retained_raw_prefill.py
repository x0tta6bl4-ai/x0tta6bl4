import json
from pathlib import Path

from src.integration.scaffold_retained_raw_prefill import build_report, main


def _write_json(root: Path, rel: str, payload: dict) -> None:
    path = root / rel
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(payload), encoding="utf-8")


def _base_manifest(root: Path, *, ready: bool) -> Path:
    source_a = ".tmp/raw-source/a.json"
    source_b = ".tmp/raw-source/b.json"
    destination_a = ".tmp/raw-dest/a.json"
    destination_b = ".tmp/raw-dest/b.json"
    _write_json(root, source_a, {"status": "VERIFIED HERE"})
    _write_json(root, source_b, {"status": "VERIFIED HERE"})
    if ready:
        _write_json(root, destination_a, {"status": "VERIFIED HERE"})

    current_status = "VERIFIED HERE" if ready else "LOCAL_OBSERVATION"
    item_ready = ready
    item_errors = [] if ready else ["raw evidence still declares production_claim=false"]
    manifest = {
        "input_groups": [
            {
                "collector_id": "collector-a",
                "evidence_key": "raw_identity",
                "input_kind": "raw_evidence_bundle",
                "raw_files": [
                    {
                        "raw_id": "collector-a/a.json",
                        "file_name": "a.json",
                        "source_raw_path": source_a,
                        "install_destination_path": destination_a,
                        "current_status": current_status,
                        "template_rejected": True,
                        "required_operator_provenance_fields": ["operator", "captured_at"],
                        "required_status": "VERIFIED HERE",
                        "ready": item_ready,
                        "errors": item_errors,
                    },
                    {
                        "raw_id": "collector-a/b.json",
                        "file_name": "b.json",
                        "source_raw_path": source_b,
                        "install_destination_path": destination_b,
                        "current_status": current_status,
                        "template_rejected": True,
                        "required_operator_provenance_fields": ["operator", "captured_at"],
                        "required_status": "VERIFIED HERE",
                        "ready": item_ready,
                        "errors": item_errors,
                    },
                ],
            }
        ]
    }
    manifest_path = root / ".tmp/validation-shards/integration-spine-production-input-bundle-manifest-current.json"
    manifest_path.parent.mkdir(parents=True, exist_ok=True)
    manifest_path.write_text(json.dumps(manifest), encoding="utf-8")
    return manifest_path


def test_scaffold_retained_raw_prefill_fails_closed_on_local_observations(tmp_path):
    manifest_path = _base_manifest(tmp_path, ready=False)

    report = build_report(tmp_path, manifest_path)

    assert report["schema_version"].endswith("v4-repo-generated")
    assert "source-restored" not in report["schema_version"]
    assert report["prefill_decision"] == "PREFILL_BLOCKED_ON_RETAINED_RAW_EVIDENCE"
    assert report["ready"] is False
    assert report["goal_can_be_marked_complete"] is False
    assert report["mutates_files"] is False
    assert report["touches_external_settlement"] is False
    assert report["summary"]["raw_files_expected"] == 2
    assert report["summary"]["raw_files_already_filled"] == 0
    assert report["summary"]["raw_files_ready_to_prefill"] == 0
    assert report["summary"]["raw_files_invalid_evidence"] == 2
    assert report["summary"]["raw_files_local_observation"] == 2
    assert report["summary"]["blocking_raw_files"] == 2


def test_scaffold_retained_raw_prefill_allows_valid_retained_sources(tmp_path):
    manifest_path = _base_manifest(tmp_path, ready=True)

    report = build_report(tmp_path, manifest_path)

    assert report["prefill_decision"] == "PREFILL_READY"
    assert report["ready"] is True
    assert report["summary"]["raw_files_expected"] == 2
    assert report["summary"]["raw_files_already_filled"] == 1
    assert report["summary"]["raw_files_ready_to_prefill"] == 1
    assert report["summary"]["raw_files_invalid_evidence"] == 0
    assert report["summary"]["blocking_raw_files"] == 0


def test_scaffold_retained_raw_prefill_cli_require_ready_returns_two_when_blocked(tmp_path):
    manifest_path = _base_manifest(tmp_path, ready=False)
    output_json = tmp_path / "prefill.json"

    exit_code = main(
        [
            "--root",
            str(tmp_path),
            "--input-manifest",
            str(manifest_path),
            "--output-json",
            str(output_json),
            "--require-ready",
        ]
    )

    payload = json.loads(output_json.read_text(encoding="utf-8"))
    assert exit_code == 2
    assert payload["prefill_decision"] == "PREFILL_BLOCKED_ON_RETAINED_RAW_EVIDENCE"
    assert payload["summary"]["raw_files_local_observation"] == 2
