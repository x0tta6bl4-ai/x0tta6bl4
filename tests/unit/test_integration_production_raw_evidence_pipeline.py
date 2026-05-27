import json
from pathlib import Path

from src.integration.production_raw_evidence_pipeline import build_report, main


def _write_json(path: Path, payload: dict) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(payload), encoding="utf-8")


def _write_entrypoints(root: Path, collector_id: str) -> None:
    stem = collector_id.replace("-", "_")
    for path in (
        root / "scripts/ops/collect_zero_trust_pqc_evidence_bundle.py",
        root / f"scripts/ops/verify_{stem}_evidence_gate.py",
    ):
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text("# stub entrypoint\n", encoding="utf-8")


def _write_inputs(root: Path, *, ready: bool, semantic_ready: bool = True) -> tuple[Path, Path]:
    collector_id = "zero-trust-pqc"
    _write_entrypoints(root, collector_id)
    manifest = root / ".tmp/validation-shards/production-raw-evidence-intake-manifest-current.json"
    semantic = root / ".tmp/validation-shards/production-raw-evidence-semantics-current.json"
    _write_json(
        manifest,
        {
            "collectors": [
                {
                    "collector_id": collector_id,
                    "collector_script": "scripts/ops/collect_zero_trust_pqc_evidence_bundle.py",
                    "collector_command": (
                        "python3 scripts/ops/collect_zero_trust_pqc_evidence_bundle.py "
                        "--raw-root .tmp/zero-trust-pqc-raw-evidence"
                    ),
                    "raw_root": ".tmp/zero-trust-pqc-raw-evidence",
                    "raw_files": [
                        {
                            "raw_id": f"{collector_id}/operator-manifest.json",
                            "file_name": "operator-manifest.json",
                            "path": f".tmp/{collector_id}-raw-evidence/operator-manifest.json",
                            "required_evidence_status": "VERIFIED HERE",
                            "required_operator_provenance_fields": ["collected_at", "collected_by", "source_commands"],
                            "template_rejected": True,
                        }
                    ],
                }
            ],
        },
    )
    _write_json(
        semantic,
        {
            "semantic_readiness_decision": "READY_FOR_PIPELINE_EXECUTION" if semantic_ready else "BLOCKED_RAW_INPUTS",
            "summary": {
                "collectors_ready": 1 if semantic_ready else 0,
                "collectors_total": 1,
                "semantic_collectors_ready": 1 if semantic_ready else 0,
                "semantic_collectors_run": 0,
                "semantic_collectors_failed": 0,
                "bundle_writes": 0,
            },
        },
    )
    payload = {
        "status": "VERIFIED HERE",
        "evidence_status": "VERIFIED HERE",
        "collector_id": collector_id,
        "raw_id": f"{collector_id}/operator-manifest.json",
        "file_name": "operator-manifest.json",
        "collected_at": "2026-05-20T00:00:00Z",
        "collected_by": "production-operator-2026-05-20",
        "source_commands": ["kubectl --context prod get spire-server -o json"],
        "production_ready": ready,
        "production_promotion_blockers": [] if ready else ["retained component evidence only"],
        "environment": "production" if ready else "local contract-validation",
    }
    if not ready:
        payload["claim_boundary"] = "Retained local component evidence only, not production customer-path evidence."
    _write_json(root / f".tmp/{collector_id}-raw-evidence/operator-manifest.json", payload)
    return manifest, semantic


def test_raw_evidence_pipeline_blocks_on_local_observation(tmp_path):
    manifest, semantic = _write_inputs(tmp_path, ready=False)

    report = build_report(tmp_path, manifest, semantic)

    assert report["schema_version"].endswith("v2-repo-generated")
    assert report["pipeline_decision"] == "BLOCKED_RAW_INPUTS"
    assert report["ready_for_collector_execution"] is False
    assert report["runs_collectors"] is False
    assert report["summary"]["raw_files_ready"] == 0
    assert report["summary"]["raw_files_local_observation"] == 1
    assert report["summary"]["planned_steps_total"] == 1
    assert report["summary"]["missing_entrypoints"] == 0
    assert report["planned_steps"][0]["collector_id"] == "zero-trust-pqc"
    assert report["planned_steps"][0]["collector_command"].endswith("--require-ready")


def test_raw_evidence_pipeline_reports_ready_plan_when_raw_and_semantic_are_ready(tmp_path):
    manifest, semantic = _write_inputs(tmp_path, ready=True, semantic_ready=True)

    report = build_report(tmp_path, manifest, semantic)

    assert report["pipeline_decision"] == "READY_FOR_COLLECTOR_EXECUTION"
    assert report["ready_for_collector_execution"] is True
    assert report["summary"]["raw_files_ready"] == 1
    assert report["summary"]["raw_files_local_observation"] == 0
    assert report["summary"]["missing_entrypoints"] == 0
    assert report["goal_can_be_marked_complete"] is False


def test_raw_evidence_pipeline_blocks_when_entrypoints_are_missing(tmp_path):
    manifest, semantic = _write_inputs(tmp_path, ready=True, semantic_ready=True)
    (tmp_path / "scripts/ops/verify_zero_trust_pqc_evidence_gate.py").unlink()

    report = build_report(tmp_path, manifest, semantic)

    assert report["pipeline_decision"] == "BLOCKED_MISSING_ENTRYPOINTS"
    assert report["ready_for_collector_execution"] is False
    assert report["entrypoints_ready_for_pipeline_execution"] is False
    assert report["summary"]["missing_entrypoints"] == 1


def test_raw_evidence_pipeline_cli_writes_fail_closed_report(tmp_path):
    output = tmp_path / "pipeline.json"

    exit_code = main(["--root", str(tmp_path), "--output-json", str(output), "--require-ready"])

    report = json.loads(output.read_text(encoding="utf-8"))
    assert exit_code == 2
    assert report["pipeline_decision"] == "PIPELINE_INVALID_SOURCE_ARTIFACTS"
    assert report["ready_for_collector_execution"] is False
    assert report["source_errors"]
