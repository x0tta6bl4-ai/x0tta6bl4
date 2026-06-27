import importlib.util
import json
from pathlib import Path


ROOT = Path(__file__).resolve().parents[3]


def _load_script():
    spec = importlib.util.spec_from_file_location(
        "apply_operator_bundle_identity_patch",
        ROOT / "scripts/ops/apply_operator_bundle_identity_patch.py",
    )
    assert spec and spec.loader
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


def _write_json(path: Path, payload: dict) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(payload), encoding="utf-8")


def _bundle_file(root: Path) -> Path:
    return root / ".tmp/production-raw-evidence-operator-bundle/zero-trust-pqc/operator-manifest.json"


def _write_identity_fixture(root: Path, *, unsafe: bool = False) -> None:
    target = _bundle_file(root)
    _write_json(
        target,
        {
            "evidence_status": "VERIFIED HERE",
            "raw_id": "zero-trust-pqc/operator-manifest.json",
            "file_name": "operator-manifest.json",
            "production_ready": False,
        },
    )
    operations = [
        {"op": "add", "path": "/collector_id", "value": "zero-trust-pqc"},
    ]
    if unsafe:
        operations.append({"op": "replace", "path": "/production_ready", "value": True})
    _write_json(
        root / ".tmp/validation-shards/integration-spine-operator-bundle-identity-current.json",
        {
            "status": "VERIFIED HERE",
            "decision": "OPERATOR_BUNDLE_IDENTITY_FIX_REQUIRED",
            "identity_update_plan": [
                {
                    "path": ".tmp/production-raw-evidence-operator-bundle/zero-trust-pqc/operator-manifest.json",
                    "available": True,
                    "json_patch_operations": operations,
                }
            ],
            "summary": {
                "identity_patch_entries_total": 1,
                "identity_patch_operations_total": len(operations),
            },
        },
    )


def test_identity_patch_dry_run_does_not_write_bundle(tmp_path):
    wrapper = _load_script()
    _write_identity_fixture(tmp_path)
    output = tmp_path / "patch-report.json"

    exit_code = wrapper.main(["--root", str(tmp_path), "--output-json", str(output)])

    report = json.loads(output.read_text(encoding="utf-8"))
    bundle = json.loads(_bundle_file(tmp_path).read_text(encoding="utf-8"))
    assert exit_code == 0
    assert report["decision"] == "IDENTITY_PATCH_DRY_RUN_READY"
    assert report["mutates_files"] is False
    assert report["summary"]["would_update_files"] == 1
    assert report["summary"]["updated_files"] == 0
    assert "collector_id" not in bundle


def test_identity_patch_apply_updates_only_identity_fields(tmp_path):
    wrapper = _load_script()
    _write_identity_fixture(tmp_path)
    output = tmp_path / "patch-report.json"

    exit_code = wrapper.main(["--root", str(tmp_path), "--output-json", str(output), "--apply", "--require-applied"])

    report = json.loads(output.read_text(encoding="utf-8"))
    bundle = json.loads(_bundle_file(tmp_path).read_text(encoding="utf-8"))
    assert exit_code == 0
    assert report["decision"] == "IDENTITY_PATCH_APPLIED"
    assert report["mutates_files"] is True
    assert report["promotes_production_ready"] is False
    assert report["changes_evidence_status"] is False
    assert report["summary"]["updated_files"] == 1
    assert bundle["collector_id"] == "zero-trust-pqc"
    assert bundle["production_ready"] is False
    assert bundle["evidence_status"] == "VERIFIED HERE"


def test_identity_patch_blocks_unsafe_fields(tmp_path):
    wrapper = _load_script()
    _write_identity_fixture(tmp_path, unsafe=True)
    output = tmp_path / "patch-report.json"

    exit_code = wrapper.main(["--root", str(tmp_path), "--output-json", str(output), "--apply"])

    report = json.loads(output.read_text(encoding="utf-8"))
    bundle = json.loads(_bundle_file(tmp_path).read_text(encoding="utf-8"))
    assert exit_code == 2
    assert report["decision"] == "IDENTITY_PATCH_BLOCKED"
    assert report["summary"]["unsafe_operations_total"] == 1
    assert "collector_id" not in bundle
    assert bundle["production_ready"] is False
