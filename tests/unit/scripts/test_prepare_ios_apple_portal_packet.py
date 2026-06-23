from __future__ import annotations

import importlib.util
import json
import stat
import subprocess
import sys
from pathlib import Path


ROOT = Path(__file__).resolve().parents[3]
SCRIPT = ROOT / "scripts/ops/prepare_ios_apple_portal_packet.py"


def _load():
    spec = importlib.util.spec_from_file_location(
        "prepare_ios_apple_portal_packet_test",
        SCRIPT,
    )
    assert spec and spec.loader
    module = importlib.util.module_from_spec(spec)
    sys.modules[spec.name] = module
    spec.loader.exec_module(module)
    return module


def test_plan_redacts_private_key_and_reports_missing_inputs(tmp_path: Path) -> None:
    module = _load()
    key = tmp_path / "apple-distribution.key"
    key.write_text("PRIVATE KEY CONTENT\n", encoding="utf-8")
    key.chmod(0o644)

    args = module.parse_args(
        [
            "--csr",
            str(tmp_path / "missing.csr"),
            "--private-key",
            str(key),
            "--packet-dir",
            str(tmp_path / "packet"),
        ]
    )

    report = module.run(args)
    rendered = json.dumps(report, sort_keys=True)

    assert report["status"] == "PLAN"
    assert report["claim_boundary"]["private_key_copied_to_packet"] is False
    assert report["claim_boundary"]["private_key_printed"] is False
    assert "csr_file" in report["missing_inputs"]
    assert "private_key_mode_owner_only" in report["missing_inputs"]
    assert "PRIVATE KEY CONTENT" not in rendered


def test_write_packet_copies_csr_but_not_private_key(tmp_path: Path) -> None:
    module = _load()
    csr = tmp_path / "apple-distribution.csr"
    key = tmp_path / "apple-distribution.key"
    packet_dir = tmp_path / "packet"
    csr.write_text("CSR CONTENT\n", encoding="utf-8")
    key.write_text("PRIVATE KEY CONTENT\n", encoding="utf-8")
    key.chmod(0o600)

    args = module.parse_args(
        [
            "--write-packet",
            "--csr",
            str(csr),
            "--private-key",
            str(key),
            "--packet-dir",
            str(packet_dir),
            "--expected-certificate-cer",
            str(tmp_path / "apple-distribution.cer"),
            "--expected-provisioning-profile",
            str(tmp_path / "x0tta6bl4.mobileprovision"),
        ]
    )

    report = module.run(args)
    manifest = json.loads((packet_dir / "ios-apple-portal-packet.json").read_text())
    readme = (packet_dir / "README.md").read_text(encoding="utf-8")

    assert report["status"] == "READY"
    assert sorted(report["packet_files"]) == [
        "README.md",
        "apple-distribution.csr",
        "ios-apple-portal-packet.json",
    ]
    assert (packet_dir / "apple-distribution.csr").read_text(encoding="utf-8") == "CSR CONTENT\n"
    assert not (packet_dir / "apple-distribution.key").exists()
    assert manifest["claim_boundary"]["private_key_copied_to_packet"] is False
    assert "PRIVATE KEY CONTENT" not in json.dumps(manifest, sort_keys=True)
    assert "PRIVATE KEY CONTENT" not in readme
    assert "run_native_release_closeout.py" in readme


def test_write_packet_requires_owner_only_private_key(tmp_path: Path) -> None:
    module = _load()
    csr = tmp_path / "apple-distribution.csr"
    key = tmp_path / "apple-distribution.key"
    csr.write_text("CSR CONTENT\n", encoding="utf-8")
    key.write_text("PRIVATE KEY CONTENT\n", encoding="utf-8")
    key.chmod(0o640)

    args = module.parse_args(
        [
            "--write-packet",
            "--csr",
            str(csr),
            "--private-key",
            str(key),
            "--packet-dir",
            str(tmp_path / "packet"),
        ]
    )

    report = module.run(args)

    assert report["status"] == "FAILED"
    assert report["error"] == "missing_required_inputs"
    assert "private_key_mode_owner_only" in report["missing_inputs"]
    assert stat.S_IMODE(key.stat().st_mode) == 0o640


def test_cli_json_is_machine_readable(tmp_path: Path) -> None:
    result = subprocess.run(
        [
            sys.executable,
            str(SCRIPT),
            "--csr",
            str(tmp_path / "missing.csr"),
            "--private-key",
            str(tmp_path / "missing.key"),
            "--json",
        ],
        cwd=ROOT,
        text=True,
        capture_output=True,
        check=True,
    )

    report = json.loads(result.stdout)
    assert report["schema"] == "x0tta6bl4.ios_apple_portal_packet.v1"
    assert report["status"] == "PLAN"
    assert result.stderr == ""
