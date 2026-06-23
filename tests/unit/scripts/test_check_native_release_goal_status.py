from __future__ import annotations

import importlib.util
import json
import subprocess
import sys
from pathlib import Path
from typing import Any


ROOT = Path(__file__).resolve().parents[3]
SCRIPT = ROOT / "scripts/ops/check_native_release_goal_status.py"


def _load():
    spec = importlib.util.spec_from_file_location(
        "check_native_release_goal_status_test",
        SCRIPT,
    )
    assert spec and spec.loader
    module = importlib.util.module_from_spec(spec)
    sys.modules[spec.name] = module
    spec.loader.exec_module(module)
    return module


def _audit(path: Path, *, ios_complete: bool) -> Path:
    platforms: dict[str, dict[str, Any]] = {
        "android": {
            "complete": True,
            "artifact_kinds": ["debug_apk", "release_apk", "release_aab"],
            "failures": [],
        },
        "ios": {
            "complete": ios_complete,
            "artifact_kinds": ["simulator_app_file", "unsigned_device_app_file"]
            + (["signed_ipa"] if ios_complete else []),
            "failures": []
            if ios_complete
            else ["ios:artifact_kind_missing:signed_ipa", "ios:signed_ipa_missing"],
        },
        "ubuntu": {
            "complete": True,
            "artifact_kinds": ["appimage", "deb"],
            "failures": [],
        },
        "windows": {"complete": True, "artifact_kinds": ["msi"], "failures": []},
    }
    path.write_text(
        json.dumps(
            {
                "schema": "x0tta6bl4.native_release_artifact_audit.v1",
                "complete": all(platform["complete"] for platform in platforms.values()),
                "summary": {
                    "platforms_complete": sum(
                        1 for platform in platforms.values() if platform["complete"]
                    ),
                    "platforms_total": 4,
                },
                "platforms": platforms,
            }
        ),
        encoding="utf-8",
    )
    return path


def test_reports_current_ios_signed_ipa_gap(tmp_path: Path) -> None:
    module = _load()
    audit = _audit(tmp_path / "audit.json", ios_complete=False)
    key = tmp_path / "apple-distribution.key"
    key.write_text("private-key\n", encoding="utf-8")
    secret_names = tmp_path / "secrets.txt"
    secret_names.write_text("X0T_ANDROID_KEYSTORE_BASE64\n", encoding="utf-8")

    args = module.parse_args(
        [
            "--audit-json",
            str(audit),
            "--ios-private-key",
            str(key),
            "--ios-certificate-cer",
            str(tmp_path / "missing.cer"),
            "--ios-provisioning-profile",
            str(tmp_path / "missing.mobileprovision"),
            "--github-secret-names-file",
            str(secret_names),
        ]
    )

    report = module.build_report(args)

    assert report["goal_complete"] is False
    assert report["platforms"]["android"]["complete"] is True
    assert report["platforms"]["ios"]["complete"] is False
    assert "ios:signed_ipa_missing" in report["platforms"]["ios"]["failures"]
    assert "certificate_cer_file" in report["ios_signing"]["missing_inputs"]
    assert "provisioning_profile_file" in report["ios_signing"]["missing_inputs"]
    assert report["ios_signing"]["missing_github_secrets"] == [
        "X0T_IOS_CERTIFICATE_P12_BASE64",
        "X0T_IOS_CERTIFICATE_PASSWORD",
        "X0T_IOS_PROVISIONING_PROFILE_BASE64",
        "X0T_IOS_TEAM_ID",
    ]
    assert any("trigger Native App Builds" in action for action in report["next_actions"])


def test_complete_audit_proves_goal_even_when_local_signing_files_are_absent(
    tmp_path: Path,
) -> None:
    module = _load()
    audit = _audit(tmp_path / "audit.json", ios_complete=True)

    args = module.parse_args(["--audit-json", str(audit)])
    report = module.build_report(args)

    assert report["goal_complete"] is True
    assert report["platforms"]["ios"]["artifact_kinds"] == [
        "simulator_app_file",
        "unsigned_device_app_file",
        "signed_ipa",
    ]


def test_github_secret_check_uses_names_only(tmp_path: Path) -> None:
    module = _load()
    audit = _audit(tmp_path / "audit.json", ios_complete=False)
    calls: list[list[str]] = []

    def runner(
        args: list[str],
        text: bool,
        capture_output: bool,
        check: bool,
    ) -> subprocess.CompletedProcess[str]:
        calls.append(list(args))
        return subprocess.CompletedProcess(
            args,
            0,
            "X0T_IOS_CERTIFICATE_P12_BASE64\t2026-06-01T00:00:00Z\n",
            "",
        )

    args = module.parse_args(
        [
            "--audit-json",
            str(audit),
            "--check-github-secrets",
            "--repo",
            "x0tta6bl4-ai/x0tta6bl4",
        ]
    )

    report = module.build_report(args, runner=runner)
    rendered = json.dumps(report, sort_keys=True)

    assert calls == [["gh", "secret", "list", "--repo", "x0tta6bl4-ai/x0tta6bl4"]]
    assert report["ios_signing"]["missing_github_secrets"] == [
        "X0T_IOS_CERTIFICATE_PASSWORD",
        "X0T_IOS_PROVISIONING_PROFILE_BASE64",
        "X0T_IOS_TEAM_ID",
    ]
    assert "2026-06-01T00:00:00Z" not in rendered


def test_cli_json_is_machine_readable(tmp_path: Path) -> None:
    audit = _audit(tmp_path / "audit.json", ios_complete=False)

    result = subprocess.run(
        [sys.executable, str(SCRIPT), "--audit-json", str(audit), "--json"],
        cwd=ROOT,
        text=True,
        capture_output=True,
        check=True,
    )

    report = json.loads(result.stdout)
    assert report["schema"] == "x0tta6bl4.native_release_goal_status.v1"
    assert report["goal_complete"] is False
    assert result.stderr == ""
