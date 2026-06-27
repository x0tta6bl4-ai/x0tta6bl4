import json
from pathlib import Path

from src.integration.evidence_source_candidates import COLLECTOR_BY_KEY
from src.integration.operator_bundle_gate import build_report, main


def _write_json(path: Path, payload: dict) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(payload), encoding="utf-8")


def _write_manifest(root: Path) -> None:
    _write_json(
        root / ".tmp/validation-shards/production-raw-evidence-intake-manifest-current.json",
        {
            "collectors": [
                {
                    "collector_id": collector_id,
                    "raw_files": [
                        {
                            "raw_id": f"{collector_id}/operator-manifest.json",
                            "file_name": "operator-manifest.json",
                            "path": f".tmp/{collector_id}-raw-evidence/operator-manifest.json",
                        }
                    ],
                }
                for collector_id in sorted(set(COLLECTOR_BY_KEY.values()))
            ]
        },
    )


def _write_semantic_queue(root: Path, *, ready: bool) -> None:
    _write_json(
        root / ".tmp/validation-shards/integration-spine-semantic-production-blocker-queue-current.json",
        {
            "status": "VERIFIED HERE",
            "summary": {
                "by_collector": (
                    {} if ready else {collector_id: 1 for collector_id in sorted(set(COLLECTOR_BY_KEY.values()))}
                ),
            },
        },
    )


def _write_operator_bundle(root: Path, *, ready: bool) -> None:
    for collector_id in sorted(set(COLLECTOR_BY_KEY.values())):
        raw_id = f"{collector_id}/operator-manifest.json"
        payload = {
            "evidence_status": "VERIFIED HERE",
            "collector_id": collector_id,
            "raw_id": raw_id,
            "file_name": "operator-manifest.json",
            "collected_at": "2026-05-20T00:00:00Z",
            "collected_by": "production-operator-2026-05-20",
            "source_commands": [f"kubectl --context prod get {collector_id} -o json"],
            "production_ready": ready,
            "production_promotion_blockers": [],
        }
        if not ready:
            payload.update(
                {
                    "environment": "production-like-local-runtime",
                    "production_promotion_blockers": ["operator bundle still captured from local runtime"],
                    "claim_boundary": "local contract-validation bundle, not production evidence",
                }
            )
        _write_json(
            root / f".tmp/production-raw-evidence-operator-bundle/{collector_id}/operator-manifest.json",
            payload,
        )


def _write_fixture(root: Path, *, ready: bool) -> None:
    _write_manifest(root)
    _write_semantic_queue(root, ready=ready)
    _write_operator_bundle(root, ready=ready)


def test_operator_bundle_gate_blocks_local_bundle(tmp_path):
    _write_fixture(tmp_path, ready=False)

    report = build_report(root=tmp_path, evidence_key="live_spire_mtls")

    assert report["status"] == "VERIFIED HERE"
    assert report["ok"] is True
    assert report["decision"] == "BLOCKED"
    assert report["zero_trust_pqc_decision"] == "BLOCKED"
    assert report["goal_can_be_marked_complete"] is False
    assert report["summary"]["zero_trust_pqc_ready"] is False
    assert report["summary"]["production_ready"] is False
    assert report["summary"]["semantic_blockers_total"] == 1
    assert report["blocking_reasons"]
    assert any("production_ready must be true" in reason for reason in report["blocking_reasons"])


def test_operator_bundle_gate_accepts_ready_bundle(tmp_path):
    _write_fixture(tmp_path, ready=True)

    report = build_report(root=tmp_path, evidence_key="multi_host_mesh")

    assert report["status"] == "VERIFIED HERE"
    assert report["ok"] is True
    assert report["decision"] == "READY_TO_INSTALL"
    assert report["self_healing_pqc_mesh_decision"] == "READY"
    assert report["goal_can_be_marked_complete"] is False
    assert report["summary"]["self_healing_pqc_mesh_ready"] is True
    assert report["summary"]["production_ready"] is True
    assert report["summary"]["semantic_blockers_total"] == 0
    assert report["summary"]["bundle_files_needing_identity_update"] == 0
    assert report["identity_update_plan"] == []
    assert report["blocking_reasons"] == []
    assert report["not_verified_yet"] == []


def test_operator_bundle_gate_reports_manifest_identity_mismatch(tmp_path):
    _write_fixture(tmp_path, ready=True)
    _write_json(
        tmp_path / ".tmp/production-raw-evidence-operator-bundle/zero-trust-pqc/operator-manifest.json",
        {
            "evidence_status": "VERIFIED HERE",
            "collector_id": "zero-trust-pqc",
            "raw_id": "paid-client-serviceability/operator-manifest.json",
            "file_name": "operator-manifest.json",
            "collected_at": "2026-05-20T00:00:00Z",
            "collected_by": "production-operator-2026-05-20",
            "source_commands": ["kubectl --context prod get zero-trust-pqc -o json"],
            "production_ready": True,
            "production_promotion_blockers": [],
        },
    )

    report = build_report(root=tmp_path, evidence_key="live_spire_mtls")

    assert report["decision"] == "BLOCKED"
    assert report["summary"]["bundle_manifest_identity_mismatches_total"] == 1
    assert report["summary"]["bundle_raw_id_mismatches"] == 1
    assert report["summary"]["bundle_files_needing_identity_update"] == 1
    assert "operator_bundle_identity" in report["identity_plan_command"]
    assert report["identity_update_plan"] == [
        {
            "path": ".tmp/production-raw-evidence-operator-bundle/zero-trust-pqc/operator-manifest.json",
            "available": True,
            "suggested_fields": {
                "collector_id": "zero-trust-pqc",
                "raw_id": "zero-trust-pqc/operator-manifest.json",
                "file_name": "operator-manifest.json",
            },
            "current_fields": {
                "collector_id": "zero-trust-pqc",
                "raw_id": "paid-client-serviceability/operator-manifest.json",
                "file_name": "operator-manifest.json",
            },
            "identity_mismatch_fields": ["raw_id"],
            "json_merge_patch": {
                "collector_id": "zero-trust-pqc",
                "raw_id": "zero-trust-pqc/operator-manifest.json",
                "file_name": "operator-manifest.json",
            },
            "json_patch_operations": [
                {"op": "replace", "path": "/raw_id", "value": "zero-trust-pqc/operator-manifest.json"},
            ],
            "read_error": "",
        }
    ]
    assert any("raw_id must match the intake manifest raw_id" in reason for reason in report["blocking_reasons"])


def test_operator_bundle_gate_cli_require_ready_returns_two_when_blocked(tmp_path):
    _write_fixture(tmp_path, ready=False)
    output_json = tmp_path / "paid-client-gate.json"

    exit_code = main([
        "--root",
        str(tmp_path),
        "--evidence-key",
        "paid_client_path",
        "--output-json",
        str(output_json),
        "--require-ready",
    ])

    assert exit_code == 2
    report = json.loads(output_json.read_text(encoding="utf-8"))
    assert report["decision"] == "BLOCKED"
    assert report["paid_client_serviceability_decision"] == "BLOCKED"
    assert report["summary"]["paid_client_serviceability_ready"] is False
    assert report["goal_can_be_marked_complete"] is False
