import json
from pathlib import Path

from src.integration.production_raw_evidence_entrypoint import build_report, main_for_collector


def _write_json(path: Path, payload: dict) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(payload), encoding="utf-8")


def _write_inputs(root: Path, *, collector_id: str = "stable-deploy", ready: bool) -> Path:
    manifest = root / ".tmp/validation-shards/production-raw-evidence-intake-manifest-current.json"
    raw_path = root / f".tmp/{collector_id}-raw-evidence/operator-manifest.json"
    _write_json(
        manifest,
        {
            "collectors": [
                {
                    "collector_id": collector_id,
                    "collector_script": f"scripts/ops/collect_{collector_id.replace('-', '_')}_evidence_bundle.py",
                    "raw_root": f".tmp/{collector_id}-raw-evidence",
                    "raw_files": [
                        {
                            "raw_id": f"{collector_id}/operator-manifest.json",
                            "file_name": "operator-manifest.json",
                            "path": f".tmp/{collector_id}-raw-evidence/operator-manifest.json",
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
            ],
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
        "source_commands": ["kubectl --context prod get deploy -o json"],
        "production_ready": ready,
        "production_promotion_blockers": [] if ready else ["retained component evidence only"],
        "environment": "production" if ready else "local contract-validation",
    }
    if not ready:
        payload["claim_boundary"] = "Retained local component evidence only, not production evidence."
    _write_json(raw_path, payload)
    return manifest


def test_raw_evidence_entrypoint_blocks_local_observation(tmp_path):
    manifest = _write_inputs(tmp_path, ready=False)

    report = build_report(
        tmp_path,
        "stable-deploy",
        "collector",
        manifest,
        raw_root=".tmp/stable-deploy-raw-evidence",
    )

    assert report["schema_version"].endswith("v1-repo-generated")
    assert report["entrypoint_decision"] == "RAW_EVIDENCE_COLLECTOR_BLOCKED"
    assert report["ready_for_entrypoint_execution"] is False
    assert report["materializes_evidence"] is False
    assert report["mutates_files"] is False
    assert report["goal_can_be_marked_complete"] is False
    assert report["summary"]["selected_raw_files_local_observation"] == 1


def test_raw_evidence_entrypoint_reports_ready_without_running_gate(tmp_path):
    manifest = _write_inputs(tmp_path, ready=True)

    report = build_report(
        tmp_path,
        "stable-deploy",
        "gate",
        manifest,
        raw_root=".tmp/stable-deploy-raw-evidence",
    )

    assert report["entrypoint_decision"] == "RAW_EVIDENCE_GATE_READY"
    assert report["ready_for_entrypoint_execution"] is True
    assert report["runs_evidence_gate"] is False
    assert report["summary"]["selected_raw_files_ready"] == 1


def test_raw_evidence_entrypoint_cli_fails_closed_for_missing_collector(tmp_path):
    manifest = _write_inputs(tmp_path, ready=True)
    output = tmp_path / "entrypoint.json"

    exit_code = main_for_collector(
        "missing-collector",
        "collector",
        str(output),
        [
            "--root",
            str(tmp_path),
            "--intake-manifest",
            str(manifest),
            "--output-json",
            str(output),
            "--require-ready",
        ],
    )

    report = json.loads(output.read_text(encoding="utf-8"))
    assert exit_code == 2
    assert report["entrypoint_decision"] == "RAW_EVIDENCE_COLLECTOR_UNKNOWN_COLLECTOR"
    assert report["ready_for_entrypoint_execution"] is False
    assert report["summary"]["selected_collectors_total"] == 0
