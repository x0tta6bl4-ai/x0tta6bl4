#!/usr/bin/env python3
"""Run the safe iOS signed release setup pipeline without printing secrets."""

from __future__ import annotations

import argparse
import importlib.util
import json
import os
import subprocess
import sys
from collections.abc import Callable, Mapping, Sequence
from datetime import datetime, timezone
from pathlib import Path
from typing import Any


SCHEMA = "x0tta6bl4.ios_signed_release_setup.v1"
DEFAULT_REPO = "x0tta6bl4-ai/x0tta6bl4"
DEFAULT_REF = "sync-main-20260529"
DEFAULT_WORKFLOW = "Native App Builds"
DEFAULT_BUNDLE_ID = "net.x0tta6bl4.mesh"
DEFAULT_EXPORT_METHOD = "ad-hoc"
DEFAULT_SIGNING_DIR = Path.home() / ".local/share/x0tta6bl4/ios-signing"
DEFAULT_CERTIFICATE_CER = DEFAULT_SIGNING_DIR / "apple-distribution.cer"
DEFAULT_PRIVATE_KEY = DEFAULT_SIGNING_DIR / "apple-distribution.key"
DEFAULT_P12 = DEFAULT_SIGNING_DIR / "apple-distribution.p12"
DEFAULT_PROFILE = DEFAULT_SIGNING_DIR / "x0tta6bl4.mobileprovision"
DEFAULT_OUTPUT = ".tmp/native-signing/ios/ios-signed-release-setup.json"


def _utc_now() -> str:
    return datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")


def _load_sibling(module_name: str) -> Any:
    path = Path(__file__).resolve().with_name(f"{module_name}.py")
    spec = importlib.util.spec_from_file_location(f"x0tta6bl4_{module_name}", path)
    if spec is None or spec.loader is None:
        raise RuntimeError(f"cannot load {path}")
    module = importlib.util.module_from_spec(spec)
    sys.modules[spec.name] = module
    spec.loader.exec_module(module)
    return module


P12_MODULE = _load_sibling("prepare_ios_distribution_p12")
VERIFY_MODULE = _load_sibling("verify_ios_signing_material")
SECRETS_MODULE = _load_sibling("prepare_ios_signing_secrets")


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


def _path_exists(path: str | None) -> bool:
    return bool(path and Path(path).expanduser().is_file())


def _missing_inputs(args: argparse.Namespace) -> list[str]:
    missing: list[str] = []
    if not _path_exists(args.certificate_cer):
        missing.append("certificate_cer_file")
    if not _path_exists(args.private_key):
        missing.append("private_key_file")
    if not args.p12_password:
        missing.append("p12_password")
    if not _path_exists(args.provisioning_profile):
        missing.append("provisioning_profile_file")
    if not args.team_id:
        missing.append("team_id")
    return missing


def _scrub_private_values(value: Any, private_values: Sequence[str]) -> Any:
    if isinstance(value, str):
        scrubbed = value
        for private_value in private_values:
            if private_value:
                scrubbed = scrubbed.replace(private_value, "<redacted>")
        return scrubbed
    if isinstance(value, list):
        return [_scrub_private_values(item, private_values) for item in value]
    if isinstance(value, tuple):
        return tuple(_scrub_private_values(item, private_values) for item in value)
    if isinstance(value, dict):
        return {
            str(key): _scrub_private_values(item, private_values)
            for key, item in value.items()
        }
    return value


def build_plan(args: argparse.Namespace) -> dict[str, Any]:
    missing = _missing_inputs(args)
    return {
        "schema": SCHEMA,
        "generated_at_utc": _utc_now(),
        "status": "PLAN",
        "repo": args.repo,
        "ref": args.ref,
        "workflow": args.workflow,
        "certificate_cer_path": args.certificate_cer,
        "certificate_cer_present": _path_exists(args.certificate_cer),
        "private_key_path": args.private_key,
        "private_key_present": _path_exists(args.private_key),
        "p12_output_path": args.p12_output,
        "p12_password_present": bool(args.p12_password),
        "provisioning_profile_path": args.provisioning_profile,
        "provisioning_profile_present": _path_exists(args.provisioning_profile),
        "team_id_present": bool(args.team_id),
        "bundle_id": args.bundle_id,
        "export_method": args.export_method,
        "will_prepare": args.prepare,
        "will_set_github_secrets": args.set_github_secrets,
        "will_write_local_env": bool(args.write_local_env),
        "will_trigger_workflow": args.trigger_workflow,
        "require_complete_release": args.require_complete_release,
        "missing_inputs": missing,
        "stages": [],
        "next_verification": [
            "Wait for the Native App Builds workflow to finish.",
            "Download x0tta6bl4-native-release-artifact-audit.",
            "Require native-release-artifact-audit.json complete=true before claiming all platforms are ready.",
        ],
        "claim_boundary": {
            "apple_certificate_created": False,
            "provisioning_profile_created": False,
            "p12_exported": False,
            "ios_signing_material_verified": False,
            "github_ios_secrets_ready": False,
            "native_release_workflow_triggered": False,
            "signed_ipa_created": False,
            "private_values_redacted": True,
            "p12_password_printed": False,
        },
    }


def _append_stage(
    report: dict[str, Any],
    *,
    stage: str,
    status: str,
    details: Mapping[str, Any],
    private_values: Sequence[str],
) -> None:
    report["stages"].append(
        {
            "stage": stage,
            "status": status,
            "details": _scrub_private_values(dict(details), private_values),
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
    ]
    if args.require_complete_release:
        command.extend(["-f", "require_complete_release=true"])

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


def run(
    args: argparse.Namespace,
    *,
    text_runner: Callable[..., subprocess.CompletedProcess[str]] = subprocess.run,
    bytes_runner: Callable[..., subprocess.CompletedProcess[bytes]] = subprocess.run,
) -> dict[str, Any]:
    private_values = [args.p12_password or "", args.team_id or ""]
    report = build_plan(args)
    if not args.prepare:
        return _scrub_private_values(report, private_values)

    if report["missing_inputs"]:
        return _scrub_private_values(
            _fail(report, error="missing_required_inputs"),
            private_values,
        )

    p12_argv = [
        "--export",
        "--certificate-cer",
        args.certificate_cer,
        "--private-key",
        args.private_key,
        "--p12-output",
        args.p12_output,
        "--p12-password",
        args.p12_password,
    ]
    if args.force_p12:
        p12_argv.append("--force")
    p12_report = P12_MODULE.run(
        P12_MODULE.parse_args(p12_argv),
        runner=text_runner,
    )
    _append_stage(
        report,
        stage="export_p12",
        status=p12_report.get("status", "UNKNOWN"),
        details=p12_report,
        private_values=private_values,
    )
    if p12_report.get("status") != "EXPORTED":
        return _scrub_private_values(
            _fail(report, error="p12_export_failed", stage="export_p12"),
            private_values,
        )
    report["claim_boundary"]["p12_exported"] = True

    verify_argv = [
        "--verify",
        "--certificate-p12",
        args.p12_output,
        "--certificate-password",
        args.p12_password,
        "--provisioning-profile",
        args.provisioning_profile,
        "--team-id",
        args.team_id,
        "--bundle-id",
        args.bundle_id,
    ]
    if args.allow_wildcard_app_id:
        verify_argv.append("--allow-wildcard-app-id")
    if args.allow_development_profile:
        verify_argv.append("--allow-development-profile")
    if args.allow_unsigned_plist:
        verify_argv.append("--allow-unsigned-plist")
    verification_report = VERIFY_MODULE.run(
        VERIFY_MODULE.parse_args(verify_argv),
        runner=bytes_runner,
    )
    _append_stage(
        report,
        stage="verify_signing_material",
        status=verification_report.get("status", "UNKNOWN"),
        details=verification_report,
        private_values=private_values,
    )
    if verification_report.get("status") != "VALID":
        return _scrub_private_values(
            _fail(
                report,
                error="ios_signing_material_invalid",
                stage="verify_signing_material",
            ),
            private_values,
        )
    report["claim_boundary"]["ios_signing_material_verified"] = True

    secrets_argv = [
        "--prepare",
        "--certificate-p12",
        args.p12_output,
        "--certificate-password",
        args.p12_password,
        "--provisioning-profile",
        args.provisioning_profile,
        "--team-id",
        args.team_id,
        "--bundle-id",
        args.bundle_id,
        "--export-method",
        args.export_method,
        "--repo",
        args.repo,
    ]
    if args.set_github_secrets:
        secrets_argv.append("--set-github-secrets")
    if args.write_local_env:
        secrets_argv.extend(["--write-local-env", args.write_local_env])
    secrets_report = SECRETS_MODULE.run(
        SECRETS_MODULE.parse_args(secrets_argv),
        runner=text_runner,
    )
    _append_stage(
        report,
        stage="prepare_github_ios_secrets",
        status=secrets_report.get("status", "UNKNOWN"),
        details=secrets_report,
        private_values=private_values,
    )
    if secrets_report.get("status") != "PREPARED":
        return _scrub_private_values(
            _fail(
                report,
                error="github_ios_secret_preparation_failed",
                stage="prepare_github_ios_secrets",
            ),
            private_values,
        )
    if args.set_github_secrets and secrets_report.get("github_secrets_ready") is not True:
        return _scrub_private_values(
            _fail(
                report,
                error="github_ios_secret_write_failed",
                stage="prepare_github_ios_secrets",
            ),
            private_values,
        )
    report["claim_boundary"]["github_ios_secrets_ready"] = bool(
        args.set_github_secrets and secrets_report.get("github_secrets_ready") is True
    )

    report["status"] = "READY_FOR_NATIVE_RELEASE_WORKFLOW"
    if args.trigger_workflow:
        triggered, trigger_report = _trigger_workflow(args, runner=text_runner)
        _append_stage(
            report,
            stage="trigger_native_release_workflow",
            status="TRIGGERED" if triggered else "FAILED",
            details=trigger_report,
            private_values=private_values,
        )
        if not triggered:
            return _scrub_private_values(
                _fail(
                    report,
                    error="native_release_workflow_trigger_failed",
                    stage="trigger_native_release_workflow",
                ),
                private_values,
            )
        report["status"] = "NATIVE_RELEASE_WORKFLOW_TRIGGERED"
        report["claim_boundary"]["native_release_workflow_triggered"] = True

    return _scrub_private_values(report, private_values)


def parse_args(argv: Sequence[str] | None = None) -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description=(
            "Export, verify, upload, and optionally trigger the iOS signed "
            "Native App Builds path without printing private values."
        ),
    )
    parser.add_argument("--repo", default=os.environ.get("GH_REPO", DEFAULT_REPO))
    parser.add_argument("--ref", default=os.environ.get("GH_REF", DEFAULT_REF))
    parser.add_argument("--workflow", default=DEFAULT_WORKFLOW)
    parser.add_argument("--certificate-cer", default=str(DEFAULT_CERTIFICATE_CER))
    parser.add_argument("--private-key", default=str(DEFAULT_PRIVATE_KEY))
    parser.add_argument("--p12-output", default=str(DEFAULT_P12))
    parser.add_argument(
        "--p12-password",
        default=os.environ.get("X0T_IOS_CERTIFICATE_PASSWORD"),
    )
    parser.add_argument("--provisioning-profile", default=str(DEFAULT_PROFILE))
    parser.add_argument("--team-id", default=os.environ.get("X0T_IOS_TEAM_ID"))
    parser.add_argument("--bundle-id", default=DEFAULT_BUNDLE_ID)
    parser.add_argument("--export-method", default=DEFAULT_EXPORT_METHOD)
    parser.add_argument("--prepare", action="store_true")
    parser.add_argument("--force-p12", action="store_true")
    parser.add_argument("--set-github-secrets", action="store_true")
    parser.add_argument(
        "--write-local-env",
        nargs="?",
        const=".tmp/native-signing/ios/ios-signing.env",
        default=None,
    )
    parser.add_argument("--trigger-workflow", action="store_true")
    parser.add_argument("--require-complete-release", action="store_true")
    parser.add_argument("--allow-wildcard-app-id", action="store_true")
    parser.add_argument("--allow-development-profile", action="store_true")
    parser.add_argument(
        "--allow-unsigned-plist",
        action="store_true",
        help="test-only mode; real provisioning profiles are CMS signed",
    )
    parser.add_argument("--require-ready", action="store_true")
    parser.add_argument("--output", default=DEFAULT_OUTPUT)
    parser.add_argument("--json", action="store_true")
    return parser.parse_args(argv)


def _write_output(report: Mapping[str, Any], output: str | None) -> None:
    if not output:
        return
    path = Path(output)
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(report, indent=2, sort_keys=True) + "\n", encoding="utf-8")  # lgtm[py/clear-text-storage-sensitive-data]  # lgtm[py/clear-text-storage-sensitive-data] - diagnostic report, no secrets


def _print_text(report: Mapping[str, Any]) -> None:
    print(f"iOS signed release setup: {report['status']}")
    if report.get("missing_inputs"):
        print("Missing inputs:")
        for item in report["missing_inputs"]:
            print(f"- {item}")
    for stage in report.get("stages", []):
        print(f"- {stage['stage']}: {stage['status']}")
    if report.get("error"):
        print(f"Error: {report['error']}")
    print("Private key, .p12 password, Team ID, and secret values are not printed.")


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
    ready_statuses = {
        "READY_FOR_NATIVE_RELEASE_WORKFLOW",
        "NATIVE_RELEASE_WORKFLOW_TRIGGERED",
    }
    if args.require_ready and report["status"] not in ready_statuses:
        return 2
    return 0


if __name__ == "__main__":
    raise SystemExit(main(sys.argv[1:]))
