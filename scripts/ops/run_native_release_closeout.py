#!/usr/bin/env python3
"""Trigger, wait for, and verify the four-platform native release goal."""

from __future__ import annotations

import argparse
import importlib.util
import json
import subprocess
import sys
import time
from collections.abc import Callable, Mapping, Sequence
from datetime import datetime, timezone
from pathlib import Path
from typing import Any


SCHEMA = "x0tta6bl4.native_release_closeout.v1"
DEFAULT_REPO = "x0tta6bl4-ai/x0tta6bl4"
DEFAULT_REF = "sync-main-20260529"
DEFAULT_WORKFLOW = "Native App Builds"
DEFAULT_AUDIT_ARTIFACT = "x0tta6bl4-native-release-artifact-audit"
DEFAULT_CLOSEOUT_DIR = ".tmp/native-release-closeout"


def _utc_now() -> str:
    return datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")


def _load_goal_status_module() -> Any:
    path = Path(__file__).resolve().with_name("check_native_release_goal_status.py")
    spec = importlib.util.spec_from_file_location("x0tta6bl4_native_goal_status", path)
    if spec is None or spec.loader is None:
        raise RuntimeError(f"cannot load {path}")
    module = importlib.util.module_from_spec(spec)
    sys.modules[spec.name] = module
    spec.loader.exec_module(module)
    return module


GOAL_STATUS_MODULE = _load_goal_status_module()


def _run_text(
    args: Sequence[str],
    *,
    runner: Callable[..., subprocess.CompletedProcess[str]] = subprocess.run,
) -> subprocess.CompletedProcess[str]:
    return runner(
        list(args),
        text=True,
        capture_output=True,
        check=False,
    )


def _parse_json(stdout: str) -> tuple[Any | None, str | None]:
    try:
        return json.loads(stdout), None
    except json.JSONDecodeError:
        return None, "invalid_json"


def _stage(
    report: dict[str, Any],
    *,
    name: str,
    status: str,
    details: Mapping[str, Any] | None = None,
) -> None:
    report["stages"].append(
        {
            "stage": name,
            "status": status,
            "details": dict(details or {}),
        }
    )


def _fail(
    report: dict[str, Any],
    *,
    error: str,
    stage: str | None = None,
) -> dict[str, Any]:
    report["status"] = "FAILED"
    report["error"] = error
    if stage:
        report["failed_stage"] = stage
    return report


def _trigger_workflow(
    args: argparse.Namespace,
    *,
    runner: Callable[..., subprocess.CompletedProcess[str]] = subprocess.run,
) -> tuple[bool, dict[str, Any]]:
    command = [
        "gh",
        "workflow",
        "run",
        args.workflow,
        "--repo",
        args.repo,
        "--ref",
        args.ref,
        "-f",
        "require_complete_release=true",
    ]
    result = _run_text(command, runner=runner)
    return (
        result.returncode == 0,
        {
            "command": command,
            "returncode": result.returncode,
            "stdout": result.stdout.strip(),
            "stderr": result.stderr.strip(),
        },
    )


def _latest_run(
    args: argparse.Namespace,
    *,
    runner: Callable[..., subprocess.CompletedProcess[str]] = subprocess.run,
) -> tuple[int | None, dict[str, Any]]:
    command = [
        "gh",
        "run",
        "list",
        "--repo",
        args.repo,
        "--workflow",
        args.workflow,
        "--branch",
        args.ref,
        "--limit",
        "10",
        "--json",
        "databaseId,status,conclusion,createdAt,headSha,event,displayTitle",
    ]
    result = _run_text(command, runner=runner)
    details: dict[str, Any] = {
        "command": command,
        "returncode": result.returncode,
        "stderr": result.stderr.strip(),
    }
    if result.returncode != 0:
        return None, details
    runs, error = _parse_json(result.stdout)
    if error:
        details["error"] = error
        return None, details
    details["runs_considered"] = len(runs) if isinstance(runs, list) else 0
    if not isinstance(runs, list) or not runs:
        details["error"] = "no_runs_found"
        return None, details
    run = runs[0]
    details["selected_run"] = run
    return int(run["databaseId"]), details


def _view_run(
    *,
    repo: str,
    run_id: int,
    runner: Callable[..., subprocess.CompletedProcess[str]] = subprocess.run,
) -> tuple[dict[str, Any] | None, dict[str, Any]]:
    command = [
        "gh",
        "run",
        "view",
        str(run_id),
        "--repo",
        repo,
        "--json",
        "status,conclusion,headSha,url,createdAt,updatedAt",
    ]
    result = _run_text(command, runner=runner)
    details: dict[str, Any] = {
        "command": command,
        "returncode": result.returncode,
        "stderr": result.stderr.strip(),
    }
    if result.returncode != 0:
        return None, details
    payload, error = _parse_json(result.stdout)
    if error or not isinstance(payload, dict):
        details["error"] = error or "run_view_not_object"
        return None, details
    details["run"] = payload
    return payload, details


def _wait_run(
    args: argparse.Namespace,
    *,
    run_id: int,
    runner: Callable[..., subprocess.CompletedProcess[str]] = subprocess.run,
    sleeper: Callable[[float], None] = time.sleep,
) -> tuple[dict[str, Any] | None, dict[str, Any]]:
    deadline = time.monotonic() + args.timeout_seconds
    polls = 0
    last_details: dict[str, Any] = {}
    while True:
        polls += 1
        payload, details = _view_run(repo=args.repo, run_id=run_id, runner=runner)
        last_details = details
        if payload and payload.get("status") == "completed":
            details["polls"] = polls
            return payload, details
        if time.monotonic() >= deadline:
            last_details["polls"] = polls
            last_details["error"] = "timeout"
            return payload, last_details
        sleeper(args.poll_interval_seconds)


def _download_audit(
    args: argparse.Namespace,
    *,
    run_id: int,
    runner: Callable[..., subprocess.CompletedProcess[str]] = subprocess.run,
) -> tuple[Path | None, dict[str, Any]]:
    closeout_dir = Path(args.download_dir)
    audit_dir = closeout_dir / str(run_id) / "audit"
    audit_dir.mkdir(parents=True, exist_ok=True)
    command = [
        "gh",
        "run",
        "download",
        str(run_id),
        "--repo",
        args.repo,
        "--name",
        args.audit_artifact_name,
        "--dir",
        str(audit_dir),
    ]
    result = _run_text(command, runner=runner)
    details: dict[str, Any] = {
        "command": command,
        "returncode": result.returncode,
        "stdout": result.stdout.strip(),
        "stderr": result.stderr.strip(),
        "audit_dir": str(audit_dir),
    }
    if result.returncode != 0:
        return None, details
    candidates = sorted(audit_dir.rglob("native-release-artifact-audit.json"))
    if not candidates:
        details["error"] = "native_release_artifact_audit_missing"
        return None, details
    details["audit_json"] = str(candidates[0])
    return candidates[0], details


def _goal_status(
    args: argparse.Namespace,
    *,
    audit_json: Path,
    runner: Callable[..., subprocess.CompletedProcess[str]] = subprocess.run,
) -> dict[str, Any]:
    argv = [
        "--repo",
        args.repo,
        "--ref",
        args.ref,
        "--audit-json",
        str(audit_json),
    ]
    if args.check_github_secrets:
        argv.append("--check-github-secrets")
    if args.github_secret_names_file:
        argv.extend(["--github-secret-names-file", args.github_secret_names_file])
    if args.ios_p12_password_present:
        argv.append("--ios-p12-password-present")
    if args.ios_team_id_present:
        argv.append("--ios-team-id-present")
    return GOAL_STATUS_MODULE.build_report(
        GOAL_STATUS_MODULE.parse_args(argv),
        runner=runner,
    )


def build_plan(args: argparse.Namespace) -> dict[str, Any]:
    return {
        "schema": SCHEMA,
        "generated_at_utc": _utc_now(),
        "status": "PLAN",
        "repo": args.repo,
        "ref": args.ref,
        "workflow": args.workflow,
        "run_id": args.run_id,
        "will_trigger_workflow": args.trigger_workflow,
        "will_use_latest_run": args.use_latest_run,
        "will_wait": args.wait,
        "will_download_audit": args.download_audit,
        "will_check_github_secrets": args.check_github_secrets,
        "require_complete": args.require_complete,
        "download_dir": args.download_dir,
        "stages": [],
        "goal_status": None,
        "claim_boundary": {
            "does_not_create_apple_certificate": True,
            "does_not_create_provisioning_profile": True,
            "does_not_print_private_values": True,
            "does_not_claim_completion_without_native_audit": True,
        },
    }


def run(
    args: argparse.Namespace,
    *,
    runner: Callable[..., subprocess.CompletedProcess[str]] = subprocess.run,
    sleeper: Callable[[float], None] = time.sleep,
) -> dict[str, Any]:
    report = build_plan(args)
    run_id = args.run_id

    if args.trigger_workflow:
        ok, details = _trigger_workflow(args, runner=runner)
        _stage(
            report,
            name="trigger_native_app_builds",
            status="TRIGGERED" if ok else "FAILED",
            details=details,
        )
        if not ok:
            return _fail(report, error="workflow_trigger_failed", stage="trigger_native_app_builds")
        if args.discovery_delay_seconds:
            sleeper(args.discovery_delay_seconds)

    if run_id is None and (args.trigger_workflow or args.use_latest_run):
        run_id, details = _latest_run(args, runner=runner)
        _stage(
            report,
            name="select_native_app_builds_run",
            status="SELECTED" if run_id is not None else "FAILED",
            details=details,
        )
        if run_id is None:
            return _fail(report, error="native_app_builds_run_not_found", stage="select_native_app_builds_run")

    if run_id is None:
        report["status"] = "NO_RUN_SELECTED"
        report["next_action"] = (
            "pass --run-id, --use-latest-run, or --trigger-workflow to verify a native release run"
        )
        return report

    report["run_id"] = run_id
    run_payload: dict[str, Any] | None = None
    if args.wait:
        run_payload, details = _wait_run(args, run_id=run_id, runner=runner, sleeper=sleeper)
        _stage(
            report,
            name="wait_native_app_builds_run",
            status="COMPLETED" if run_payload and run_payload.get("status") == "completed" else "FAILED",
            details=details,
        )
        if not run_payload or run_payload.get("status") != "completed":
            return _fail(report, error="native_app_builds_wait_failed", stage="wait_native_app_builds_run")
        if run_payload.get("conclusion") != "success":
            return _fail(report, error="native_app_builds_run_failed", stage="wait_native_app_builds_run")
    else:
        run_payload, details = _view_run(repo=args.repo, run_id=run_id, runner=runner)
        _stage(
            report,
            name="view_native_app_builds_run",
            status="LOADED" if run_payload else "FAILED",
            details=details,
        )
        if not run_payload:
            return _fail(report, error="native_app_builds_run_view_failed", stage="view_native_app_builds_run")

    audit_json: Path | None = Path(args.audit_json).expanduser() if args.audit_json else None
    if args.download_audit:
        audit_json, details = _download_audit(args, run_id=run_id, runner=runner)
        _stage(
            report,
            name="download_native_release_audit",
            status="DOWNLOADED" if audit_json else "FAILED",
            details=details,
        )
        if audit_json is None:
            return _fail(report, error="native_release_audit_download_failed", stage="download_native_release_audit")

    if audit_json is None:
        report["status"] = "RUN_READY_NO_AUDIT"
        report["next_action"] = "pass --download-audit or --audit-json to verify four-platform completion"
        return report

    goal_status = _goal_status(args, audit_json=audit_json, runner=runner)
    report["goal_status"] = goal_status
    _stage(
        report,
        name="check_native_release_goal_status",
        status="COMPLETE" if goal_status.get("goal_complete") is True else "INCOMPLETE",
        details={
            "goal_complete": goal_status.get("goal_complete"),
            "audit_summary": goal_status.get("audit", {}).get("summary", {}),
            "ios_failures": goal_status.get("platforms", {}).get("ios", {}).get("failures", []),
            "missing_ios_inputs": goal_status.get("ios_signing", {}).get("missing_inputs", []),
            "missing_ios_secrets": goal_status.get("ios_signing", {}).get("missing_github_secrets", []),
        },
    )

    report["status"] = "COMPLETE" if goal_status.get("goal_complete") is True else "INCOMPLETE"
    if args.require_complete and report["status"] != "COMPLETE":
        report["error"] = "native_release_goal_incomplete"
    return report


def parse_args(argv: Sequence[str] | None = None) -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description="Close out the Android/iOS/Ubuntu/Windows native release goal.",
    )
    parser.add_argument("--repo", default=DEFAULT_REPO)
    parser.add_argument("--ref", default=DEFAULT_REF)
    parser.add_argument("--workflow", default=DEFAULT_WORKFLOW)
    parser.add_argument("--run-id", type=int)
    parser.add_argument("--use-latest-run", action="store_true")
    parser.add_argument("--trigger-workflow", action="store_true")
    parser.add_argument("--wait", action="store_true")
    parser.add_argument("--timeout-seconds", type=float, default=45 * 60)
    parser.add_argument("--poll-interval-seconds", type=float, default=20)
    parser.add_argument("--discovery-delay-seconds", type=float, default=5)
    parser.add_argument("--download-audit", action="store_true")
    parser.add_argument("--audit-artifact-name", default=DEFAULT_AUDIT_ARTIFACT)
    parser.add_argument("--audit-json")
    parser.add_argument("--download-dir", default=DEFAULT_CLOSEOUT_DIR)
    parser.add_argument("--check-github-secrets", action="store_true")
    parser.add_argument("--github-secret-names-file")
    parser.add_argument("--ios-p12-password-present", action="store_true")
    parser.add_argument("--ios-team-id-present", action="store_true")
    parser.add_argument("--require-complete", action="store_true")
    parser.add_argument("--output")
    parser.add_argument("--json", action="store_true")
    return parser.parse_args(argv)


def _write_output(report: Mapping[str, Any], output: str | None) -> None:
    if not output:
        return
    path = Path(output)
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(report, indent=2, sort_keys=True) + "\n", encoding="utf-8")


def _print_text(report: Mapping[str, Any]) -> None:
    print(f"Native release closeout: {report['status']}")
    if report.get("run_id") is not None:
        print(f"Run ID: {report['run_id']}")
    goal_status = report.get("goal_status") or {}
    if goal_status:
        print(f"Goal complete: {goal_status.get('goal_complete')}")
        ios = goal_status.get("platforms", {}).get("ios", {})
        if ios.get("failures"):
            print("iOS failures: " + ", ".join(ios["failures"]))
    if report.get("error"):
        print(f"Error: {report['error']}")
    print("Private signing values are not printed.")


def main(argv: Sequence[str] | None = None) -> int:
    args = parse_args(argv)
    report = run(args)
    _write_output(report, args.output)
    if args.json:
        print(json.dumps(report, indent=2, sort_keys=True))
    else:
        _print_text(report)
    if report["status"] == "FAILED":
        return 1
    if args.require_complete and report["status"] != "COMPLETE":
        return 2
    return 0


if __name__ == "__main__":
    raise SystemExit(main(sys.argv[1:]))
