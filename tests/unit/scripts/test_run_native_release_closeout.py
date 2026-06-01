from __future__ import annotations

import importlib.util
import json
import subprocess
import sys
from pathlib import Path
from typing import Any


ROOT = Path(__file__).resolve().parents[3]
SCRIPT = ROOT / "scripts/ops/run_native_release_closeout.py"


def _load():
    spec = importlib.util.spec_from_file_location(
        "run_native_release_closeout_test",
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


def test_no_run_selected_is_plan_like_state() -> None:
    module = _load()
    args = module.parse_args([])

    report = module.run(args)

    assert report["status"] == "NO_RUN_SELECTED"
    assert report["goal_status"] is None
    assert "pass --run-id" in report["next_action"]


def test_trigger_wait_download_reports_incomplete_ios_gap(tmp_path: Path) -> None:
    module = _load()
    calls: list[list[str]] = []

    def runner(
        args: list[str],
        text: bool,
        capture_output: bool,
        check: bool,
    ) -> subprocess.CompletedProcess[str]:
        calls.append(list(args))
        if args[:3] == ["gh", "workflow", "run"]:
            return subprocess.CompletedProcess(args, 0, "queued\n", "")
        if args[:3] == ["gh", "run", "list"]:
            return subprocess.CompletedProcess(
                args,
                0,
                json.dumps(
                    [
                        {
                            "databaseId": 123,
                            "status": "in_progress",
                            "conclusion": "",
                            "createdAt": "2026-06-01T00:00:00Z",
                        }
                    ]
                ),
                "",
            )
        if args[:3] == ["gh", "run", "view"]:
            return subprocess.CompletedProcess(
                args,
                0,
                json.dumps(
                    {
                        "status": "completed",
                        "conclusion": "success",
                        "headSha": "abc123",
                        "url": "https://example.test/run/123",
                    }
                ),
                "",
            )
        if args[:3] == ["gh", "run", "download"]:
            audit_dir = Path(args[args.index("--dir") + 1])
            audit_dir.mkdir(parents=True, exist_ok=True)
            _audit(audit_dir / "native-release-artifact-audit.json", ios_complete=False)
            return subprocess.CompletedProcess(args, 0, "", "")
        if args[:3] == ["gh", "secret", "list"]:
            return subprocess.CompletedProcess(args, 0, "X0T_ANDROID_KEYSTORE_BASE64\tdate\n", "")
        raise AssertionError(f"unexpected command: {args}")

    args = module.parse_args(
        [
            "--trigger-workflow",
            "--wait",
            "--download-audit",
            "--check-github-secrets",
            "--download-dir",
            str(tmp_path / "closeout"),
            "--discovery-delay-seconds",
            "0",
            "--poll-interval-seconds",
            "0",
            "--timeout-seconds",
            "5",
        ]
    )

    report = module.run(args, runner=runner, sleeper=lambda _: None)

    assert report["status"] == "INCOMPLETE"
    assert report["run_id"] == 123
    assert [stage["stage"] for stage in report["stages"]] == [
        "trigger_native_app_builds",
        "select_native_app_builds_run",
        "wait_native_app_builds_run",
        "download_native_release_audit",
        "check_native_release_goal_status",
    ]
    assert report["goal_status"]["platforms"]["ios"]["failures"] == [
        "ios:artifact_kind_missing:signed_ipa",
        "ios:signed_ipa_missing",
    ]
    assert report["goal_status"]["ios_signing"]["missing_github_secrets"] == [
        "X0T_IOS_CERTIFICATE_P12_BASE64",
        "X0T_IOS_CERTIFICATE_PASSWORD",
        "X0T_IOS_PROVISIONING_PROFILE_BASE64",
        "X0T_IOS_TEAM_ID",
    ]
    workflow_command = calls[0]
    assert workflow_command[-2:] == ["-f", "require_complete_release=true"]


def test_existing_complete_audit_closes_goal(tmp_path: Path) -> None:
    module = _load()
    audit = _audit(tmp_path / "native-release-artifact-audit.json", ios_complete=True)

    def runner(
        args: list[str],
        text: bool,
        capture_output: bool,
        check: bool,
    ) -> subprocess.CompletedProcess[str]:
        if args[:3] == ["gh", "run", "view"]:
            return subprocess.CompletedProcess(
                args,
                0,
                json.dumps({"status": "completed", "conclusion": "success"}),
                "",
            )
        raise AssertionError(f"unexpected command: {args}")

    args = module.parse_args(["--run-id", "456", "--audit-json", str(audit)])

    report = module.run(args, runner=runner)

    assert report["status"] == "COMPLETE"
    assert report["goal_status"]["goal_complete"] is True
    assert report["goal_status"]["platforms"]["ios"]["artifact_kinds"][-1] == "signed_ipa"


def test_wait_timeout_fails_closed() -> None:
    module = _load()

    def runner(
        args: list[str],
        text: bool,
        capture_output: bool,
        check: bool,
    ) -> subprocess.CompletedProcess[str]:
        if args[:3] == ["gh", "run", "view"]:
            return subprocess.CompletedProcess(
                args,
                0,
                json.dumps({"status": "in_progress", "conclusion": ""}),
                "",
            )
        raise AssertionError(f"unexpected command: {args}")

    args = module.parse_args(
        ["--run-id", "789", "--wait", "--timeout-seconds", "0"],
    )

    report = module.run(args, runner=runner, sleeper=lambda _: None)

    assert report["status"] == "FAILED"
    assert report["error"] == "native_app_builds_wait_failed"
    assert report["failed_stage"] == "wait_native_app_builds_run"


def test_cli_json_is_machine_readable() -> None:
    result = subprocess.run(
        [sys.executable, str(SCRIPT), "--json"],
        cwd=ROOT,
        text=True,
        capture_output=True,
        check=True,
    )

    report = json.loads(result.stdout)
    assert report["schema"] == "x0tta6bl4.native_release_closeout.v1"
    assert report["status"] == "NO_RUN_SELECTED"
    assert result.stderr == ""
