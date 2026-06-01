from __future__ import annotations

import importlib.util
import json
import stat
import subprocess
import sys
from pathlib import Path


ROOT = Path(__file__).resolve().parents[3]
SCRIPT = ROOT / "scripts/ops/prepare_ios_distribution_certificate_request.py"


def _load():
    spec = importlib.util.spec_from_file_location(
        "prepare_ios_distribution_certificate_request_test",
        SCRIPT,
    )
    assert spec and spec.loader
    module = importlib.util.module_from_spec(spec)
    sys.modules[spec.name] = module
    spec.loader.exec_module(module)
    return module


def test_plan_does_not_claim_certificate_or_print_key(tmp_path: Path) -> None:
    module = _load()
    key = tmp_path / "apple-distribution.key"
    csr = tmp_path / "apple-distribution.csr"

    args = module.parse_args(
        [
            "--private-key",
            str(key),
            "--csr",
            str(csr),
            "--email-address",
            "ops@example.test",
        ]
    )

    report = module.run(args)
    rendered = json.dumps(report, sort_keys=True)

    assert report["status"] == "PLAN"
    assert report["claim_boundary"]["private_key_printed"] is False
    assert report["claim_boundary"]["apple_certificate_created"] is False
    assert report["claim_boundary"]["csr_ready_for_apple_developer_portal"] is False
    assert "PRIVATE KEY" not in rendered
    assert "ops@example.test" not in rendered


def test_generate_csr_writes_owner_only_private_key(tmp_path: Path) -> None:
    module = _load()
    key = tmp_path / "apple-distribution.key"
    csr = tmp_path / "apple-distribution.csr"
    calls: list[list[str]] = []

    def runner(
        args: list[str],
        text: bool,
        capture_output: bool,
        check: bool,
    ) -> subprocess.CompletedProcess[str]:
        calls.append(list(args))
        key.write_text("PRIVATE KEY CONTENT\n", encoding="utf-8")
        csr.write_text("CSR CONTENT\n", encoding="utf-8")
        return subprocess.CompletedProcess(args, 0, "", "")

    args = module.parse_args(
        [
            "--generate",
            "--private-key",
            str(key),
            "--csr",
            str(csr),
            "--common-name",
            "x0tta6bl4 Apple Distribution",
            "--email-address",
            "ops@example.test",
        ]
    )

    report = module.run(args, runner=runner)
    rendered = json.dumps(report, sort_keys=True)

    assert report["status"] == "GENERATED"
    assert report["claim_boundary"]["csr_ready_for_apple_developer_portal"] is True
    assert report["claim_boundary"]["apple_certificate_created"] is False
    assert stat.S_IMODE(key.stat().st_mode) == 0o600
    assert csr.exists()
    assert "PRIVATE KEY CONTENT" not in rendered
    assert calls and calls[0][0].endswith("openssl")
    assert "-subj" in calls[0]


def test_generate_refuses_to_overwrite_without_force(tmp_path: Path) -> None:
    module = _load()
    key = tmp_path / "apple-distribution.key"
    csr = tmp_path / "apple-distribution.csr"
    key.write_text("existing key", encoding="utf-8")
    csr.write_text("existing csr", encoding="utf-8")

    args = module.parse_args(
        [
            "--generate",
            "--private-key",
            str(key),
            "--csr",
            str(csr),
        ]
    )

    report = module.run(args)

    assert report["status"] == "FAILED"
    assert report["error"] == "output_exists"


def test_cli_plan_is_machine_readable() -> None:
    result = subprocess.run(
        [sys.executable, str(SCRIPT), "--json"],
        cwd=ROOT,
        text=True,
        capture_output=True,
        check=True,
    )

    report = json.loads(result.stdout)
    assert report["schema"] == "x0tta6bl4.ios_distribution_certificate_request.v1"
    assert report["status"] == "PLAN"
    assert result.stderr == ""
