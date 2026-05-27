import json
from pathlib import Path

from src.integration.operator_bundle_identity import build_report, main


def _write_json(path: Path, payload: dict) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(payload), encoding="utf-8")


def _write_manifest(root: Path) -> None:
    _write_json(
        root / ".tmp/validation-shards/production-raw-evidence-intake-manifest-current.json",
        {
            "collectors": [
                {
                    "collector_id": "zero-trust-pqc",
                    "raw_files": [
                        {
                            "raw_id": "zero-trust-pqc/operator-manifest.json",
                            "file_name": "operator-manifest.json",
                        },
                        {
                            "raw_id": "zero-trust-pqc/mtls-fail-closed.json",
                            "file_name": "mtls-fail-closed.json",
                        },
                    ],
                }
            ]
        },
    )


def _write_bundle_file(root: Path, file_name: str, payload: dict) -> None:
    _write_json(root / f".tmp/production-raw-evidence-operator-bundle/zero-trust-pqc/{file_name}", payload)


def test_operator_bundle_identity_accepts_manifest_aligned_files(tmp_path):
    _write_manifest(tmp_path)
    for file_name in ["operator-manifest.json", "mtls-fail-closed.json"]:
        _write_bundle_file(
            tmp_path,
            file_name,
            {
                "collector_id": "zero-trust-pqc",
                "raw_id": f"zero-trust-pqc/{file_name}",
                "file_name": file_name,
                "evidence_status": "VERIFIED HERE",
            },
        )

    report = build_report(root=tmp_path, evidence_key="live_spire_mtls")

    assert report["decision"] == "OPERATOR_BUNDLE_IDENTITY_CLEAN"
    assert report["summary"]["files_clean"] == 2
    assert report["summary"]["manifest_identity_mismatches_total"] == 0
    assert report["goal_can_be_marked_complete"] is False


def test_operator_bundle_identity_reports_suggested_manifest_fields(tmp_path):
    _write_manifest(tmp_path)
    _write_bundle_file(
        tmp_path,
        "operator-manifest.json",
        {
            "raw_id": "zero-trust-pqc/operator-manifest.json",
            "file_name": "operator-manifest.json",
            "evidence_status": "VERIFIED HERE",
        },
    )
    _write_bundle_file(
        tmp_path,
        "mtls-fail-closed.json",
        {
            "collector_id": "wrong-collector",
            "raw_id": "wrong/raw.json",
            "file_name": "wrong.json",
            "evidence_status": "VERIFIED HERE",
        },
    )

    report = build_report(root=tmp_path, evidence_key="live_spire_mtls")

    assert report["decision"] == "OPERATOR_BUNDLE_IDENTITY_FIX_REQUIRED"
    assert report["summary"]["files_needing_identity_update"] == 2
    assert report["summary"]["manifest_identity_mismatches_total"] == 4
    assert report["summary"]["collector_id_mismatches"] == 2
    assert report["summary"]["raw_id_mismatches"] == 1
    assert report["summary"]["file_name_mismatches"] == 1
    missing_collector = report["file_reports"][0]
    assert missing_collector["identity_mismatch_fields"] == ["collector_id"]
    assert missing_collector["suggested_fields"] == {
        "collector_id": "zero-trust-pqc",
        "raw_id": "zero-trust-pqc/operator-manifest.json",
        "file_name": "operator-manifest.json",
    }
    assert missing_collector["json_merge_patch"] == {
        "collector_id": "zero-trust-pqc",
        "raw_id": "zero-trust-pqc/operator-manifest.json",
        "file_name": "operator-manifest.json",
    }
    assert missing_collector["json_patch_operations"] == [
        {"op": "add", "path": "/collector_id", "value": "zero-trust-pqc"}
    ]
    assert report["summary"]["identity_patch_entries_total"] == 2
    assert report["summary"]["identity_patch_operations_total"] == 4
    assert report["identity_update_plan"][0]["path"] == (
        ".tmp/production-raw-evidence-operator-bundle/zero-trust-pqc/operator-manifest.json"
    )
    assert report["identity_update_plan"][0]["json_patch_operations"] == [
        {"op": "add", "path": "/collector_id", "value": "zero-trust-pqc"}
    ]
    assert "does not make local" in report["operator_safe_patch_note"]


def test_operator_bundle_identity_cli_writes_fail_closed_report(tmp_path):
    _write_manifest(tmp_path)
    output = tmp_path / "identity.json"

    exit_code = main([
        "--root",
        str(tmp_path),
        "--evidence-key",
        "live_spire_mtls",
        "--output-json",
        str(output),
        "--require-clean",
    ])

    report = json.loads(output.read_text(encoding="utf-8"))
    assert exit_code == 2
    assert report["decision"] == "OPERATOR_BUNDLE_IDENTITY_FIX_REQUIRED"
    assert report["summary"]["files_missing_or_unreadable"] == 2
