from __future__ import annotations

import importlib.util
import json
import subprocess
import sys
from pathlib import Path
from typing import Any


ROOT = Path(__file__).resolve().parents[3]
SCRIPT = ROOT / "scripts/ops/check_native_signing_readiness.py"


def _load():
    spec = importlib.util.spec_from_file_location(
        "check_native_signing_readiness_test",
        SCRIPT,
    )
    assert spec and spec.loader
    module = importlib.util.module_from_spec(spec)
    sys.modules[spec.name] = module
    spec.loader.exec_module(module)
    return module


def test_env_ci_report_redacts_missing_secret_values() -> None:
    module = _load()

    report = module.build_env_report(source="env-ci", platforms=["android", "ios"], environ={})
    rendered = json.dumps(report, sort_keys=True)

    assert report["ready"] is False
    assert report["claim_boundary"]["secret_values_redacted"] is True
    assert report["platforms"]["android"]["missing"] == [
        "ANDROID_KEYSTORE_BASE64",
        "ANDROID_KEYSTORE_PASSWORD",
        "ANDROID_KEY_ALIAS",
        "ANDROID_KEY_PASSWORD",
    ]
    assert "secret-value" not in rendered
    assert "password123" not in rendered


def test_env_local_android_requires_keystore_file(tmp_path: Path) -> None:
    module = _load()
    missing_path = tmp_path / "missing.keystore"
    env = {
        "ANDROID_KEYSTORE_PATH": str(missing_path),
        "ANDROID_KEYSTORE_PASSWORD": "secret-value",
        "ANDROID_KEY_ALIAS": "x0t",
        "ANDROID_KEY_PASSWORD": "key-secret",
    }

    report = module.build_env_report(source="env-local", platforms=["android"], environ=env)

    assert report["ready"] is False
    assert report["platforms"]["android"]["missing"] == ["ANDROID_KEYSTORE_PATH"]
    path_check = report["platforms"]["android"]["checks"][0]
    assert path_check["present"] is True
    assert path_check["file_exists"] is False

    missing_path.write_bytes(b"keystore bytes")
    ready_report = module.build_env_report(source="env-local", platforms=["android"], environ=env)

    assert ready_report["ready"] is True
    assert ready_report["platforms"]["android"]["missing"] == []
    rendered = json.dumps(ready_report, sort_keys=True)
    assert "secret-value" not in rendered
    assert "key-secret" not in rendered


def test_github_secret_list_json_reports_optional_ios_secrets() -> None:
    module = _load()

    def runner(
        args: list[str],
        check: bool,
        capture_output: bool,
        text: bool,
    ) -> subprocess.CompletedProcess[str]:
        assert args[:4] == ["gh", "secret", "list", "--repo"]
        assert check is False
        assert capture_output is True
        assert text is True
        payload: list[dict[str, Any]] = [
            {"name": "X0T_ANDROID_KEYSTORE_BASE64"},
            {"name": "X0T_ANDROID_KEYSTORE_PASSWORD"},
            {"name": "X0T_ANDROID_KEY_ALIAS"},
            {"name": "X0T_ANDROID_KEY_PASSWORD"},
            {"name": "X0T_IOS_CERTIFICATE_P12_BASE64"},
            {"name": "X0T_IOS_CERTIFICATE_PASSWORD"},
            {"name": "X0T_IOS_PROVISIONING_PROFILE_BASE64"},
            {"name": "X0T_IOS_TEAM_ID"},
            {"name": "X0T_IOS_BUNDLE_ID"},
        ]
        return subprocess.CompletedProcess(args, 0, json.dumps(payload), "")

    report = module.build_github_report(
        repo="x0tta6bl4-ai/x0tta6bl4",
        platforms=["android", "ios"],
        runner=runner,
    )

    assert report["ready"] is True
    assert report["platforms"]["android"]["missing"] == []
    assert report["platforms"]["ios"]["missing"] == []
    assert report["platforms"]["ios"]["optional"] == [
        {"name": "X0T_IOS_BUNDLE_ID", "present": True},
        {"name": "X0T_IOS_EXPORT_METHOD", "present": False},
    ]


def test_cli_require_ready_exits_two_when_signing_is_missing() -> None:
    result = subprocess.run(
        [
            sys.executable,
            str(SCRIPT),
            "--source",
            "env-ci",
            "--require-ready",
            "--json",
        ],
        cwd=ROOT,
        text=True,
        capture_output=True,
        check=False,
        env={},
    )

    report = json.loads(result.stdout)
    assert result.returncode == 2
    assert report["ready"] is False
    assert "ANDROID_KEYSTORE_BASE64" in report["platforms"]["android"]["missing"]
    assert result.stderr == ""
