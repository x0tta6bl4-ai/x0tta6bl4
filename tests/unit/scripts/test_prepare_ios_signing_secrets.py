from __future__ import annotations

import importlib.util
import json
import stat
import subprocess
import sys
from pathlib import Path


ROOT = Path(__file__).resolve().parents[3]
SCRIPT = ROOT / "scripts/ops/prepare_ios_signing_secrets.py"


def _load():
    spec = importlib.util.spec_from_file_location(
        "prepare_ios_signing_secrets_test",
        SCRIPT,
    )
    assert spec and spec.loader
    module = importlib.util.module_from_spec(spec)
    sys.modules[spec.name] = module
    spec.loader.exec_module(module)
    return module


def test_plan_redacts_private_values(tmp_path: Path) -> None:
    module = _load()
    cert = tmp_path / "ios-cert.p12"
    profile = tmp_path / "profile.mobileprovision"

    args = module.parse_args(
        [
            "--certificate-p12",
            str(cert),
            "--certificate-password",
            "cert-secret",
            "--provisioning-profile",
            str(profile),
            "--team-id",
            "TEAM123456",
        ]
    )

    report = module.run(args)
    rendered = json.dumps(report, sort_keys=True)

    assert report["status"] == "PLAN"
    assert report["claim_boundary"]["private_values_redacted"] is True
    assert report["claim_boundary"]["apple_certificate_generated"] is False
    assert "<redacted>" in "\n".join(report["local_env_preview"])
    assert "cert-secret" not in rendered
    assert "TEAM123456" not in rendered


def test_prepare_requires_existing_apple_files(tmp_path: Path) -> None:
    module = _load()
    args = module.parse_args(
        [
            "--prepare",
            "--certificate-p12",
            str(tmp_path / "missing.p12"),
            "--certificate-password",
            "cert-secret",
            "--provisioning-profile",
            str(tmp_path / "missing.mobileprovision"),
            "--team-id",
            "TEAM123456",
        ]
    )

    report = module.run(args)

    assert report["status"] == "FAILED"
    assert report["error"] == "missing_required_inputs"
    assert "certificate_p12_file" in report["missing_inputs"]
    assert "provisioning_profile_file" in report["missing_inputs"]


def test_prepare_writes_owner_only_env_without_printing_values(tmp_path: Path) -> None:
    module = _load()
    cert = tmp_path / "ios-cert.p12"
    profile = tmp_path / "profile.mobileprovision"
    env_path = tmp_path / "ios-signing.env"
    cert.write_bytes(b"fake-p12")
    profile.write_bytes(b"fake-profile")

    args = module.parse_args(
        [
            "--prepare",
            "--certificate-p12",
            str(cert),
            "--certificate-password",
            "cert-secret",
            "--provisioning-profile",
            str(profile),
            "--team-id",
            "TEAM123456",
            "--bundle-id",
            "net.x0tta6bl4.mesh",
            "--export-method",
            "ad-hoc",
            "--write-local-env",
            str(env_path),
        ]
    )

    report = module.run(args)
    rendered = json.dumps(report, sort_keys=True)
    env_text = env_path.read_text(encoding="utf-8")

    assert report["status"] == "PREPARED"
    assert report["local_env_written"] is True
    assert stat.S_IMODE(env_path.stat().st_mode) == 0o600
    assert "cert-secret" not in rendered
    assert "fake-p12" not in rendered
    assert "X0T_IOS_CERTIFICATE_P12_BASE64=ZmFrZS1wMTI=" in env_text
    assert "X0T_IOS_PROVISIONING_PROFILE_BASE64=ZmFrZS1wcm9maWxl" in env_text
    assert "X0T_IOS_CERTIFICATE_PASSWORD=cert-secret" in env_text


def test_set_github_secrets_uses_stdin_not_command_args(tmp_path: Path) -> None:
    module = _load()
    cert = tmp_path / "ios-cert.p12"
    profile = tmp_path / "profile.mobileprovision"
    cert.write_bytes(b"fake-p12")
    profile.write_bytes(b"fake-profile")
    calls: list[tuple[list[str], str | None]] = []

    def runner(
        args: list[str],
        input: str | None,
        text: bool,
        capture_output: bool,
        check: bool,
    ) -> subprocess.CompletedProcess[str]:
        calls.append((list(args), input))
        return subprocess.CompletedProcess(args, 0, "", "")

    args = module.parse_args(
        [
            "--prepare",
            "--certificate-p12",
            str(cert),
            "--certificate-password",
            "cert-secret",
            "--provisioning-profile",
            str(profile),
            "--team-id",
            "TEAM123456",
            "--bundle-id",
            "net.x0tta6bl4.mesh",
            "--set-github-secrets",
            "--repo",
            "x0tta6bl4-ai/x0tta6bl4",
        ]
    )

    report = module.run(args, runner=runner)
    gh_calls = [call for call in calls if call[0][:3] == ["gh", "secret", "set"]]

    assert report["github_secrets_ready"] is True
    assert len(gh_calls) == 5
    for command, stdin_value in gh_calls:
        rendered_command = " ".join(command)
        assert "--repo x0tta6bl4-ai/x0tta6bl4" in rendered_command
        assert "cert-secret" not in rendered_command
        assert "TEAM123456" not in rendered_command
        assert stdin_value


def test_cli_plan_is_machine_readable() -> None:
    result = subprocess.run(
        [sys.executable, str(SCRIPT), "--json"],
        cwd=ROOT,
        text=True,
        capture_output=True,
        check=True,
    )

    report = json.loads(result.stdout)
    assert report["schema"] == "x0tta6bl4.ios_signing_setup.v1"
    assert report["status"] == "PLAN"
    assert result.stderr == ""
