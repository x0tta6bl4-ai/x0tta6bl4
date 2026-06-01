from __future__ import annotations

import importlib.util
import json
import stat
import subprocess
import sys
from pathlib import Path


ROOT = Path(__file__).resolve().parents[3]
SCRIPT = ROOT / "scripts/ops/prepare_ios_distribution_p12.py"


def _load():
    spec = importlib.util.spec_from_file_location(
        "prepare_ios_distribution_p12_test",
        SCRIPT,
    )
    assert spec and spec.loader
    module = importlib.util.module_from_spec(spec)
    sys.modules[spec.name] = module
    spec.loader.exec_module(module)
    return module


def test_plan_redacts_private_values_and_does_not_claim_apple_creation(
    tmp_path: Path,
) -> None:
    module = _load()
    cert = tmp_path / "apple-distribution.cer"
    key = tmp_path / "apple-distribution.key"
    p12 = tmp_path / "apple-distribution.p12"

    args = module.parse_args(
        [
            "--certificate-cer",
            str(cert),
            "--private-key",
            str(key),
            "--p12-output",
            str(p12),
            "--p12-password",
            "p12-secret",
        ]
    )

    report = module.run(args)
    rendered = json.dumps(report, sort_keys=True)

    assert report["status"] == "PLAN"
    assert report["claim_boundary"]["apple_certificate_present"] is True
    assert report["claim_boundary"]["apple_certificate_created"] is False
    assert report["claim_boundary"]["p12_exported"] is False
    assert report["claim_boundary"]["private_values_redacted"] is True
    assert "p12-secret" not in rendered


def test_export_requires_existing_certificate_key_and_password(tmp_path: Path) -> None:
    module = _load()

    args = module.parse_args(
        [
            "--export",
            "--certificate-cer",
            str(tmp_path / "missing.cer"),
            "--private-key",
            str(tmp_path / "missing.key"),
            "--p12-output",
            str(tmp_path / "out.p12"),
        ]
    )

    report = module.run(args)

    assert report["status"] == "FAILED"
    assert report["error"] == "missing_required_inputs"
    assert "certificate_cer_file" in report["missing_inputs"]
    assert "private_key_file" in report["missing_inputs"]
    assert "p12_password" in report["missing_inputs"]


def test_export_uses_stdin_for_password_and_writes_owner_only_p12(
    tmp_path: Path,
) -> None:
    module = _load()
    cert = tmp_path / "apple-distribution.cer"
    key = tmp_path / "apple-distribution.key"
    p12 = tmp_path / "apple-distribution.p12"
    cert.write_text("-----BEGIN CERTIFICATE-----\nfake\n-----END CERTIFICATE-----\n")
    key.write_text("PRIVATE KEY CONTENT\n", encoding="utf-8")
    calls: list[tuple[list[str], str | None]] = []

    def runner(
        args: list[str],
        input: str | None,
        text: bool,
        capture_output: bool,
        check: bool,
    ) -> subprocess.CompletedProcess[str]:
        calls.append((list(args), input))
        p12.write_bytes(b"fake-p12")
        return subprocess.CompletedProcess(args, 0, "", "")

    args = module.parse_args(
        [
            "--export",
            "--certificate-cer",
            str(cert),
            "--private-key",
            str(key),
            "--p12-output",
            str(p12),
            "--p12-password",
            "p12-secret",
        ]
    )

    report = module.run(args, runner=runner)
    rendered = json.dumps(report, sort_keys=True)

    assert report["status"] == "EXPORTED"
    assert report["claim_boundary"]["p12_exported"] is True
    assert stat.S_IMODE(p12.stat().st_mode) == 0o600
    assert "p12-secret" not in rendered
    assert "PRIVATE KEY CONTENT" not in rendered
    assert len(calls) == 1
    command, stdin_value = calls[0]
    rendered_command = " ".join(command)
    assert "-passout stdin" in rendered_command
    assert "p12-secret" not in rendered_command
    assert stdin_value == "p12-secret\n"


def test_export_refuses_to_overwrite_without_force(tmp_path: Path) -> None:
    module = _load()
    cert = tmp_path / "apple-distribution.cer"
    key = tmp_path / "apple-distribution.key"
    p12 = tmp_path / "apple-distribution.p12"
    cert.write_text("-----BEGIN CERTIFICATE-----\nfake\n-----END CERTIFICATE-----\n")
    key.write_text("PRIVATE KEY CONTENT\n", encoding="utf-8")
    p12.write_bytes(b"existing-p12")

    args = module.parse_args(
        [
            "--export",
            "--certificate-cer",
            str(cert),
            "--private-key",
            str(key),
            "--p12-output",
            str(p12),
            "--p12-password",
            "p12-secret",
        ]
    )

    report = module.run(args)

    assert report["status"] == "FAILED"
    assert report["error"] == "p12_output_exists"


def test_cli_plan_is_machine_readable() -> None:
    result = subprocess.run(
        [sys.executable, str(SCRIPT), "--json"],
        cwd=ROOT,
        text=True,
        capture_output=True,
        check=True,
    )

    report = json.loads(result.stdout)
    assert report["schema"] == "x0tta6bl4.ios_distribution_p12.v1"
    assert report["status"] == "PLAN"
    assert result.stderr == ""
