from __future__ import annotations

import base64
import importlib.util
import json
import plistlib
import subprocess
import sys
from datetime import datetime
from pathlib import Path


ROOT = Path(__file__).resolve().parents[3]
SCRIPT = ROOT / "scripts/ops/verify_ios_signing_material.py"
TEAM_ID = "TEAM123456"
BUNDLE_ID = "net.x0tta6bl4.mesh"
CERT_DER = b"fake apple distribution certificate der"
CERT_PEM = (
    b"-----BEGIN CERTIFICATE-----\n"
    + base64.b64encode(CERT_DER)
    + b"\n-----END CERTIFICATE-----\n"
)


def _load():
    spec = importlib.util.spec_from_file_location(
        "verify_ios_signing_material_test",
        SCRIPT,
    )
    assert spec and spec.loader
    module = importlib.util.module_from_spec(spec)
    sys.modules[spec.name] = module
    spec.loader.exec_module(module)
    return module


def _profile_plist(
    *,
    team_id: str = TEAM_ID,
    bundle_id: str = BUNDLE_ID,
    cert_der: bytes = CERT_DER,
    get_task_allow: bool = False,
) -> bytes:
    return plistlib.dumps(
        {
            "Name": "x0tta6bl4 Ad Hoc",
            "UUID": "00000000-0000-0000-0000-000000000000",
            "TeamIdentifier": [team_id],
            "ExpirationDate": datetime(2035, 1, 1, 0, 0, 0),
            "DeveloperCertificates": [cert_der],
            "Entitlements": {
                "application-identifier": f"{team_id}.{bundle_id}",
                "com.apple.developer.team-identifier": team_id,
                "get-task-allow": get_task_allow,
            },
        }
    )


def test_plan_redacts_private_values(tmp_path: Path) -> None:
    module = _load()
    p12 = tmp_path / "ios-distribution.p12"
    profile = tmp_path / "profile.mobileprovision"

    args = module.parse_args(
        [
            "--certificate-p12",
            str(p12),
            "--certificate-password",
            "p12-secret",
            "--provisioning-profile",
            str(profile),
            "--team-id",
            TEAM_ID,
        ]
    )

    report = module.run(args)
    rendered = json.dumps(report, sort_keys=True)

    assert report["status"] == "PLAN"
    assert report["claim_boundary"]["private_values_redacted"] is True
    assert report["claim_boundary"]["p12_password_printed"] is False
    assert "p12-secret" not in rendered
    assert TEAM_ID not in rendered


def test_verify_valid_profile_uses_p12_password_via_stdin(tmp_path: Path) -> None:
    module = _load()
    p12 = tmp_path / "ios-distribution.p12"
    profile = tmp_path / "profile.mobileprovision"
    p12.write_bytes(b"fake-p12")
    profile.write_bytes(_profile_plist())
    calls: list[tuple[list[str], bytes | None]] = []

    def runner(
        args: list[str],
        input: bytes | None,
        capture_output: bool,
        check: bool,
    ) -> subprocess.CompletedProcess[bytes]:
        calls.append((list(args), input))
        return subprocess.CompletedProcess(args, 0, CERT_PEM, b"")

    args = module.parse_args(
        [
            "--verify",
            "--certificate-p12",
            str(p12),
            "--certificate-password",
            "p12-secret",
            "--provisioning-profile",
            str(profile),
            "--team-id",
            TEAM_ID,
            "--bundle-id",
            BUNDLE_ID,
            "--allow-unsigned-plist",
        ]
    )

    report = module.run(args, runner=runner)
    rendered = json.dumps(report, sort_keys=True)

    assert report["status"] == "VALID"
    assert report["claim_boundary"]["ios_signing_material_verified"] is True
    assert "p12-secret" not in rendered
    assert calls
    command, stdin_value = calls[0]
    rendered_command = " ".join(command)
    assert "-passin stdin" in rendered_command
    assert "p12-secret" not in rendered_command
    assert stdin_value == b"p12-secret\n"


def test_verify_rejects_bundle_mismatch(tmp_path: Path) -> None:
    module = _load()
    p12 = tmp_path / "ios-distribution.p12"
    profile = tmp_path / "profile.mobileprovision"
    p12.write_bytes(b"fake-p12")
    profile.write_bytes(_profile_plist(bundle_id="com.example.other"))

    def runner(
        args: list[str],
        input: bytes | None,
        capture_output: bool,
        check: bool,
    ) -> subprocess.CompletedProcess[bytes]:
        return subprocess.CompletedProcess(args, 0, CERT_PEM, b"")

    args = module.parse_args(
        [
            "--verify",
            "--certificate-p12",
            str(p12),
            "--certificate-password",
            "p12-secret",
            "--provisioning-profile",
            str(profile),
            "--team-id",
            TEAM_ID,
            "--bundle-id",
            BUNDLE_ID,
            "--allow-unsigned-plist",
        ]
    )

    report = module.run(args, runner=runner)
    failed = {check["check_id"] for check in report["checks"] if not check["ok"]}

    assert report["status"] == "INVALID"
    assert "profile_bundle_id_matches" in failed


def test_verify_requires_signed_mobileprovision_by_default(tmp_path: Path) -> None:
    module = _load()
    p12 = tmp_path / "ios-distribution.p12"
    profile = tmp_path / "profile.mobileprovision"
    p12.write_bytes(b"fake-p12")
    profile.write_bytes(_profile_plist())

    def runner(
        args: list[str],
        input: bytes | None,
        capture_output: bool,
        check: bool,
    ) -> subprocess.CompletedProcess[bytes]:
        return subprocess.CompletedProcess(args, 0, CERT_PEM, b"")

    args = module.parse_args(
        [
            "--verify",
            "--certificate-p12",
            str(p12),
            "--certificate-password",
            "p12-secret",
            "--provisioning-profile",
            str(profile),
            "--team-id",
            TEAM_ID,
        ]
    )

    report = module.run(args, runner=runner)

    assert report["status"] == "FAILED"
    assert report["error"] == "unsigned_plist_not_allowed"


def test_verify_missing_inputs_fail_closed(tmp_path: Path) -> None:
    module = _load()
    args = module.parse_args(
        [
            "--verify",
            "--certificate-p12",
            str(tmp_path / "missing.p12"),
            "--provisioning-profile",
            str(tmp_path / "missing.mobileprovision"),
        ]
    )

    report = module.run(args)

    assert report["status"] == "FAILED"
    assert report["error"] == "missing_required_inputs"
    assert "certificate_p12_file" in report["missing_inputs"]
    assert "certificate_password" in report["missing_inputs"]
    assert "provisioning_profile_file" in report["missing_inputs"]
    assert "team_id" in report["missing_inputs"]


def test_cli_plan_is_machine_readable() -> None:
    result = subprocess.run(
        [sys.executable, str(SCRIPT), "--json"],
        cwd=ROOT,
        text=True,
        capture_output=True,
        check=True,
    )

    report = json.loads(result.stdout)
    assert report["schema"] == "x0tta6bl4.ios_signing_material_verification.v1"
    assert report["status"] == "PLAN"
    assert result.stderr == ""
