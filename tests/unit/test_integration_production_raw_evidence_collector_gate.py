import json
from pathlib import Path

from src.integration.production_raw_evidence_collector_gate import build_report, main


def _write_json(path: Path, payload: dict) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(payload), encoding="utf-8")


def _write_inputs(root: Path, *, collector_id: str = "stable-deploy", ready: bool = False) -> Path:
    raw_root = f".tmp/{collector_id}-raw-evidence"
    manifest = root / ".tmp/validation-shards/production-raw-evidence-intake-manifest-current.json"
    _write_json(
        manifest,
        {
            "collectors": [
                {
                    "collector_id": collector_id,
                    "raw_root": raw_root,
                    "raw_files": [
                        {
                            "raw_id": f"{collector_id}/operator-manifest.json",
                            "file_name": "operator-manifest.json",
                            "path": f"{raw_root}/operator-manifest.json",
                            "required_evidence_status": "VERIFIED HERE",
                            "required_operator_provenance_fields": ["collected_at", "collected_by", "source_commands"],
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
        "source_commands": [f"kubectl --context prod get {collector_id} -o json"],
        "production_ready": ready,
        "production_promotion_blockers": [] if ready else ["retained component evidence only"],
        "environment": "production" if ready else "local contract-validation",
    }
    if not ready:
        payload["claim_boundary"] = "Retained local component evidence only, not production evidence."
    _write_json(root / raw_root / "operator-manifest.json", payload)
    return manifest


def test_collector_gate_fails_closed_for_retained_local_raw_evidence(tmp_path):
    manifest = _write_inputs(tmp_path, ready=False)

    report = build_report(
        root=tmp_path,
        collector_id="stable-deploy",
        intake_manifest=manifest,
        raw_root=".tmp/stable-deploy-raw-evidence",
    )

    assert report["schema_version"].endswith("collector-gate-v1")
    assert report["status"] == "VERIFIED HERE"
    assert report["decision"] == "BLOCKED"
    assert report["ready"] is False
    assert report["materializes_evidence"] is False
    assert report["mutates_vpn_runtime"] is False
    assert report["summary"]["raw_files_local_observation"] == 1
    assert report["goal_can_be_marked_complete"] is False


def test_collector_gate_reports_ready_for_production_raw_evidence(tmp_path):
    manifest = _write_inputs(tmp_path, collector_id="sla-telemetry", ready=True)

    report = build_report(
        root=tmp_path,
        collector_id="sla-telemetry",
        intake_manifest=manifest,
    )

    assert report["decision"] == "READY"
    assert report["ready"] is True
    assert report["summary"]["raw_files_ready"] == 1
    assert report["summary"]["source_errors_total"] == 0


def test_collector_gate_cli_writes_report_and_returns_two_when_blocked(tmp_path):
    manifest = _write_inputs(tmp_path, ready=False)
    output = tmp_path / "collector-report.json"

    exit_code = main([
        "--root",
        str(tmp_path),
        "--collector-id",
        "stable-deploy",
        "--intake-manifest",
        str(manifest),
        "--output-json",
        str(output),
        "--require-ready",
    ])

    report = json.loads(output.read_text(encoding="utf-8"))
    assert exit_code == 2
    assert report["decision"] == "BLOCKED"
    assert report["summary"]["collector_ready"] is False


def test_collector_gate_reports_missing_manifest_collector(tmp_path):
    manifest = _write_inputs(tmp_path, collector_id="stable-deploy", ready=True)

    report = build_report(
        root=tmp_path,
        collector_id="billing-provisioning",
        intake_manifest=manifest,
    )

    assert report["decision"] == "BLOCKED"
    assert report["summary"]["source_errors_total"] == 1
    assert "billing-provisioning" in report["source_errors"][0]
