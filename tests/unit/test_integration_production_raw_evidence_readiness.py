import json
from pathlib import Path

from src.integration.production_raw_evidence_readiness import build_report, main


def _write_json(path: Path, payload: dict) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(payload), encoding="utf-8")


def _manifest(root: Path, collector_id: str = "zero-trust-pqc") -> Path:
    path = root / ".tmp/validation-shards/production-raw-evidence-intake-manifest-current.json"
    _write_json(
        path,
        {
            "collectors": [
                {
                    "collector_id": collector_id,
                    "collector_script": f"scripts/ops/collect_{collector_id}.py",
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
    return path


def _raw_payload(*, ready: bool) -> dict:
    payload = {
        "status": "VERIFIED HERE",
        "evidence_status": "VERIFIED HERE",
        "collector_id": "zero-trust-pqc",
        "raw_id": "zero-trust-pqc/operator-manifest.json",
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
    return payload


def test_raw_evidence_readiness_blocks_retained_local_observation(tmp_path):
    manifest = _manifest(tmp_path)
    _write_json(tmp_path / ".tmp/zero-trust-pqc-raw-evidence/operator-manifest.json", _raw_payload(ready=False))

    report = build_report(tmp_path, manifest)

    assert report["raw_evidence_readiness_decision"] == "BLOCKED_ON_OPERATOR_PRODUCTION_EVIDENCE"
    assert report["ready_for_collectors"] is False
    assert report["summary"]["collectors_ready"] == 0
    assert report["summary"]["collectors_blocked"] == 1
    assert report["summary"]["raw_files_ready"] == 0
    assert report["summary"]["raw_files_local_observation"] == 1
    assert report["collectors"][0]["files"][0]["status"] == "LOCAL_OBSERVATION"


def test_raw_evidence_readiness_accepts_production_ready_evidence(tmp_path):
    manifest = _manifest(tmp_path)
    _write_json(tmp_path / ".tmp/zero-trust-pqc-raw-evidence/operator-manifest.json", _raw_payload(ready=True))

    report = build_report(tmp_path, manifest)

    assert report["raw_evidence_readiness_decision"] == "READY_FOR_COLLECTORS"
    assert report["ready_for_collectors"] is True
    assert report["summary"]["collectors_ready"] == 1
    assert report["summary"]["raw_files_ready"] == 1
    assert report["summary"]["raw_files_local_observation"] == 0
    assert report["collectors"][0]["files"][0]["status"] == "READY_FOR_COLLECTOR"


def test_raw_evidence_readiness_allows_domain_status_object(tmp_path):
    manifest = _manifest(tmp_path)
    payload = _raw_payload(ready=True)
    payload["status"] = {"sync": {"status": "Synced"}, "health": {"status": "Healthy"}}
    _write_json(tmp_path / ".tmp/zero-trust-pqc-raw-evidence/operator-manifest.json", payload)

    report = build_report(tmp_path, manifest)

    assert report["ready_for_collectors"] is True
    assert report["summary"]["raw_files_conflicting_status_fields"] == 0
    assert report["summary"]["raw_files_ready"] == 1


def test_raw_evidence_readiness_allows_shell_redirects_in_source_commands(tmp_path):
    manifest = _manifest(tmp_path)
    payload = _raw_payload(ready=True)
    payload["source_commands"] = [
        "sudo dmesg > docs/verification/dmesg_post_tail_2000.txt",
        "gh api repos/x0tta6bl4-ai/x0tta6bl4/actions/jobs/1/logs > .tmp/job.log",
    ]
    _write_json(tmp_path / ".tmp/zero-trust-pqc-raw-evidence/operator-manifest.json", payload)

    report = build_report(tmp_path, manifest)

    assert report["ready_for_collectors"] is True
    assert report["summary"]["raw_files_placeholder_source_commands"] == 0
    assert report["summary"]["raw_files_placeholder_values"] == 0
    assert report["summary"]["raw_files_ready"] == 1


def test_raw_evidence_readiness_rejects_angle_bracket_placeholder_tokens(tmp_path):
    manifest = _manifest(tmp_path)
    payload = _raw_payload(ready=True)
    payload["source_commands"] = ["curl <RPC_URL>"]
    _write_json(tmp_path / ".tmp/zero-trust-pqc-raw-evidence/operator-manifest.json", payload)

    report = build_report(tmp_path, manifest)

    assert report["ready_for_collectors"] is False
    assert report["summary"]["raw_files_placeholder_source_commands"] == 1
    assert report["summary"]["raw_files_placeholder_values"] == 1


def test_raw_evidence_readiness_cli_writes_fail_closed_report(tmp_path):
    exit_code = main(["--root", str(tmp_path), "--require-ready"])

    report = json.loads(
        (tmp_path / ".tmp/validation-shards/production-raw-evidence-readiness-current.json").read_text(
            encoding="utf-8"
        )
    )
    assert exit_code == 2
    assert report["raw_evidence_readiness_decision"] == "BLOCKED_ON_OPERATOR_PRODUCTION_EVIDENCE"
    assert report["source_errors"]
