import json
from pathlib import Path

from src.integration.production_raw_evidence_semantics import build_report, main


def _write_json(path: Path, payload: dict) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(payload), encoding="utf-8")


def _write_inputs(root: Path, *, ready: bool) -> Path:
    manifest = root / ".tmp/validation-shards/production-raw-evidence-intake-manifest-current.json"
    collectors = []
    for collector_id in ["stable-deploy", "sla-telemetry"]:
        raw_root = f".tmp/{collector_id}-raw-evidence"
        collectors.append(
            {
                "collector_id": collector_id,
                "raw_root": raw_root,
                "raw_files": [
                    {
                        "raw_id": f"{collector_id}/operator-manifest.json",
                        "file_name": "operator-manifest.json",
                        "path": f"{raw_root}/operator-manifest.json",
                        "required_evidence_status": "VERIFIED HERE",
                        "required_operator_provenance_fields": [
                            "collected_at",
                            "collected_by",
                            "source_commands",
                        ],
                        "template_rejected": True,
                    }
                ],
            }
        )
        payload = {
            "status": "VERIFIED HERE",
            "evidence_status": "VERIFIED HERE",
            "collector_id": collector_id,
            "raw_id": f"{collector_id}/operator-manifest.json",
            "file_name": "operator-manifest.json",
            "collected_at": "2026-05-20T00:00:00Z",
            "collected_by": "production-operator-2026-05-20",
            "source_commands": [f"kubectl --context prod get {collector_id} -o json"],
            "production_ready": ready,
            "production_promotion_blockers": [] if ready else ["retained component evidence only"],
            "environment": "production" if ready else "local contract-validation",
        }
        if not ready:
            payload["claim_boundary"] = "Retained local component evidence only, not production evidence."
        _write_json(root / raw_root / "operator-manifest.json", payload)
    _write_json(manifest, {"collectors": collectors})
    return manifest


def test_semantics_blocks_raw_inputs_without_reporting_missing_files(tmp_path):
    manifest = _write_inputs(tmp_path, ready=False)

    report = build_report(tmp_path, manifest)

    assert report["schema_version"].endswith("v2-repo-generated")
    assert report["semantic_readiness_decision"] == "BLOCKED_RAW_INPUTS"
    assert report["runs_semantic_collectors"] is False
    assert report["materializes_evidence"] is False
    assert report["goal_can_be_marked_complete"] is False
    assert report["summary"]["raw_files_total"] == 2
    assert report["summary"]["raw_files_missing"] == 0
    assert report["summary"]["raw_files_local_observation"] == 2
    assert report["summary"]["semantic_collectors_run"] == 0


def test_semantics_runs_dry_run_only_after_raw_files_are_ready(tmp_path):
    manifest = _write_inputs(tmp_path, ready=True)

    report = build_report(tmp_path, manifest)

    assert report["semantic_readiness_decision"] == "READY_FOR_PIPELINE_EXECUTION"
    assert report["runs_semantic_collectors"] is True
    assert report["bundle_writes"] == 0
    assert report["summary"]["semantic_collectors_run"] == 2
    assert report["summary"]["semantic_collectors_ready"] == 2
    assert report["summary"]["semantic_collectors_failed"] == 0
    assert len(report["semantic_results"]) == 2


def test_semantics_cli_writes_fail_closed_report(tmp_path):
    output = tmp_path / "semantics.json"

    exit_code = main(["--root", str(tmp_path), "--output-json", str(output), "--require-ready"])

    report = json.loads(output.read_text(encoding="utf-8"))
    assert exit_code == 2
    assert report["semantic_readiness_decision"] == "INVALID_SOURCE_ARTIFACTS"
    assert report["source_errors"]
