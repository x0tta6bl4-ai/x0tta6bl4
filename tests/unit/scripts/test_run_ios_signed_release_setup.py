from __future__ import annotations

import importlib.util
import json
import subprocess
import sys
from pathlib import Path
from typing import Any


ROOT = Path(__file__).resolve().parents[3]
SCRIPT = ROOT / "scripts/ops/run_ios_signed_release_setup.py"


def _load():
    spec = importlib.util.spec_from_file_location(
        "run_ios_signed_release_setup_test",
        SCRIPT,
    )
    assert spec and spec.loader
    module = importlib.util.module_from_spec(spec)
    sys.modules[spec.name] = module
    spec.loader.exec_module(module)
    return module


class _FakeModule:
    def __init__(self, status: str, *, extra: dict[str, Any] | None = None) -> None:
        self.status = status
        self.extra = extra or {}
        self.argv_calls: list[list[str]] = []

    def parse_args(self, argv: list[str]) -> list[str]:
        self.argv_calls.append(list(argv))
        return list(argv)

    def run(self, args: list[str], *, runner: Any) -> dict[str, Any]:
        return {"status": self.status, **self.extra}


def _write_inputs(tmp_path: Path) -> dict[str, Path]:
    files = {
        "cer": tmp_path / "apple-distribution.cer",
        "key": tmp_path / "apple-distribution.key",
        "p12": tmp_path / "apple-distribution.p12",
        "profile": tmp_path / "x0tta6bl4.mobileprovision",
    }
    files["cer"].write_text("certificate\n", encoding="utf-8")
    files["key"].write_text("private-key\n", encoding="utf-8")
    files["profile"].write_text("profile\n", encoding="utf-8")
    return files


def test_plan_redacts_password_and_team_id(tmp_path: Path) -> None:
    module = _load()
    files = _write_inputs(tmp_path)

    args = module.parse_args(
        [
            "--certificate-cer",
            str(files["cer"]),
            "--private-key",
            str(files["key"]),
            "--p12-output",
            str(files["p12"]),
            "--p12-password",
            "p12-secret",
            "--provisioning-profile",
            str(files["profile"]),
            "--team-id",
            "TEAM123456",
            "--json",
        ]
    )

    report = module.run(args)
    rendered = json.dumps(report, sort_keys=True)

    assert report["status"] == "PLAN"
    assert report["p12_password_present"] is True
    assert report["team_id_present"] is True
    assert report["claim_boundary"]["private_values_redacted"] is True
    assert "p12-secret" not in rendered
    assert "TEAM123456" not in rendered


def test_prepare_fails_cleanly_when_apple_files_are_missing(tmp_path: Path) -> None:
    module = _load()

    args = module.parse_args(
        [
            "--prepare",
            "--certificate-cer",
            str(tmp_path / "missing.cer"),
            "--private-key",
            str(tmp_path / "missing.key"),
            "--p12-output",
            str(tmp_path / "out.p12"),
            "--p12-password",
            "p12-secret",
            "--provisioning-profile",
            str(tmp_path / "missing.mobileprovision"),
            "--team-id",
            "TEAM123456",
        ]
    )

    report = module.run(args)
    rendered = json.dumps(report, sort_keys=True)

    assert report["status"] == "FAILED"
    assert report["error"] == "missing_required_inputs"
    assert "certificate_cer_file" in report["missing_inputs"]
    assert "private_key_file" in report["missing_inputs"]
    assert "provisioning_profile_file" in report["missing_inputs"]
    assert "p12-secret" not in rendered
    assert "TEAM123456" not in rendered


def test_prepare_runs_pipeline_and_triggers_complete_release_workflow(
    tmp_path: Path,
) -> None:
    module = _load()
    files = _write_inputs(tmp_path)
    p12_module = _FakeModule("EXPORTED")
    verify_module = _FakeModule(
        "VALID",
        extra={
            "checks": [
                {
                    "check_id": "profile_bundle_id_matches",
                    "ok": True,
                    "details": "expected application-identifier TEAM123456.net.x0tta6bl4.mesh",
                }
            ],
        },
    )
    secrets_module = _FakeModule("PREPARED", extra={"github_secrets_ready": True})
    module.P12_MODULE = p12_module
    module.VERIFY_MODULE = verify_module
    module.SECRETS_MODULE = secrets_module
    text_calls: list[list[str]] = []

    def text_runner(
        args: list[str],
        text: bool,
        capture_output: bool,
        check: bool,
    ) -> subprocess.CompletedProcess[str]:
        text_calls.append(list(args))
        return subprocess.CompletedProcess(args, 0, "queued\n", "")

    args = module.parse_args(
        [
            "--prepare",
            "--certificate-cer",
            str(files["cer"]),
            "--private-key",
            str(files["key"]),
            "--p12-output",
            str(files["p12"]),
            "--p12-password",
            "p12-secret",
            "--provisioning-profile",
            str(files["profile"]),
            "--team-id",
            "TEAM123456",
            "--set-github-secrets",
            "--trigger-workflow",
            "--require-complete-release",
            "--repo",
            "x0tta6bl4-ai/x0tta6bl4",
            "--ref",
            "sync-main-20260529",
        ]
    )

    report = module.run(args, text_runner=text_runner)
    rendered = json.dumps(report, sort_keys=True)

    assert report["status"] == "NATIVE_RELEASE_WORKFLOW_TRIGGERED"
    assert [stage["stage"] for stage in report["stages"]] == [
        "export_p12",
        "verify_signing_material",
        "prepare_github_ios_secrets",
        "trigger_native_release_workflow",
    ]
    assert p12_module.argv_calls[0][:2] == ["--export", "--certificate-cer"]
    assert "--set-github-secrets" in secrets_module.argv_calls[0]
    assert text_calls == [
        [
            "gh",
            "workflow",
            "run",
            "Native App Builds",
            "--repo",
            "x0tta6bl4-ai/x0tta6bl4",
            "--ref",
            "sync-main-20260529",
            "-f",
            "require_complete_release=true",
        ]
    ]
    assert "p12-secret" not in rendered
    assert "TEAM123456" not in rendered


def test_invalid_signing_material_stops_before_secrets_and_workflow(
    tmp_path: Path,
) -> None:
    module = _load()
    files = _write_inputs(tmp_path)
    module.P12_MODULE = _FakeModule("EXPORTED")
    module.VERIFY_MODULE = _FakeModule("INVALID", extra={"checks": []})
    secrets_module = _FakeModule("PREPARED", extra={"github_secrets_ready": True})
    module.SECRETS_MODULE = secrets_module
    text_calls: list[list[str]] = []

    def text_runner(
        args: list[str],
        text: bool,
        capture_output: bool,
        check: bool,
    ) -> subprocess.CompletedProcess[str]:
        text_calls.append(list(args))
        return subprocess.CompletedProcess(args, 0, "", "")

    args = module.parse_args(
        [
            "--prepare",
            "--certificate-cer",
            str(files["cer"]),
            "--private-key",
            str(files["key"]),
            "--p12-output",
            str(files["p12"]),
            "--p12-password",
            "p12-secret",
            "--provisioning-profile",
            str(files["profile"]),
            "--team-id",
            "TEAM123456",
            "--set-github-secrets",
            "--trigger-workflow",
        ]
    )

    report = module.run(args, text_runner=text_runner)

    assert report["status"] == "FAILED"
    assert report["error"] == "ios_signing_material_invalid"
    assert report["failed_stage"] == "verify_signing_material"
    assert secrets_module.argv_calls == []
    assert text_calls == []


def test_cli_plan_is_machine_readable() -> None:
    result = subprocess.run(
        [sys.executable, str(SCRIPT), "--json", "--output", ""],
        cwd=ROOT,
        text=True,
        capture_output=True,
        check=True,
    )

    report = json.loads(result.stdout)
    assert report["schema"] == "x0tta6bl4.ios_signed_release_setup.v1"
    assert report["status"] == "PLAN"
    assert result.stderr == ""
