#!/usr/bin/env python3
"""Prepare iOS device signing secrets without printing private values."""

from __future__ import annotations

import argparse
import base64
import json
import os
import stat
import subprocess
import sys
from collections.abc import Callable, Mapping, Sequence
from datetime import datetime, timezone
from pathlib import Path
from typing import Any


SCHEMA = "x0tta6bl4.ios_signing_setup.v1"
DEFAULT_REPO = "x0tta6bl4-ai/x0tta6bl4"
DEFAULT_BUNDLE_ID = "net.x0tta6bl4.mesh"
DEFAULT_EXPORT_METHOD = "ad-hoc"
DEFAULT_LOCAL_ENV = ".tmp/native-signing/ios/ios-signing.env"


def _utc_now() -> str:
    return datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")


def _chmod_owner_only(path: Path) -> None:
    path.chmod(stat.S_IRUSR | stat.S_IWUSR)


def _encode_file(path: Path) -> str:
    return base64.b64encode(path.read_bytes()).decode("ascii")


def _run(
    args: Sequence[str],
    *,
    input_text: str | None = None,
    runner: Callable[..., subprocess.CompletedProcess[str]] = subprocess.run,
) -> subprocess.CompletedProcess[str]:
    return runner(
        list(args),
        input=input_text,
        text=True,
        capture_output=True,
        check=False,
    )


def _set_github_secret(
    *,
    repo: str,
    name: str,
    value: str,
    runner: Callable[..., subprocess.CompletedProcess[str]] = subprocess.run,
) -> bool:
    result = _run(
        ["gh", "secret", "set", name, "--repo", repo],
        input_text=value,
        runner=runner,
    )
    return result.returncode == 0


def _redacted_env_preview() -> list[str]:
    return [
        "X0T_IOS_CERTIFICATE_P12_BASE64=<redacted>",
        "X0T_IOS_CERTIFICATE_PASSWORD=<redacted>",
        "X0T_IOS_PROVISIONING_PROFILE_BASE64=<redacted>",
        "X0T_IOS_TEAM_ID=<redacted>",
        "X0T_IOS_BUNDLE_ID=<redacted>",
        "X0T_IOS_EXPORT_METHOD=<redacted>",
    ]


def _secret_names(include_optional: bool) -> list[str]:
    names = [
        "X0T_IOS_CERTIFICATE_P12_BASE64",
        "X0T_IOS_CERTIFICATE_PASSWORD",
        "X0T_IOS_PROVISIONING_PROFILE_BASE64",
        "X0T_IOS_TEAM_ID",
    ]
    if include_optional:
        names.extend(["X0T_IOS_BUNDLE_ID", "X0T_IOS_EXPORT_METHOD"])
    return names


def build_plan(args: argparse.Namespace) -> dict[str, Any]:
    include_optional = bool(args.bundle_id or args.export_method)
    return {
        "schema": SCHEMA,
        "generated_at_utc": _utc_now(),
        "status": "PLAN",
        "repo": args.repo,
        "certificate_p12_path": args.certificate_p12,
        "provisioning_profile_path": args.provisioning_profile,
        "team_id_present": bool(args.team_id),
        "bundle_id_present": bool(args.bundle_id),
        "export_method_present": bool(args.export_method),
        "will_write_local_env": bool(args.write_local_env),
        "will_set_github_secrets": args.set_github_secrets,
        "github_secret_names": _secret_names(include_optional),
        "local_env_preview": _redacted_env_preview(),
        "claim_boundary": {
            "ios_device_signing_material_prepared": False,
            "apple_certificate_generated": False,
            "certificate_trust_chain_validated": False,
            "provisioning_profile_validated_by_xcode": False,
            "app_store_notarization_validated": False,
            "private_values_redacted": True,
        },
    }


def _missing_inputs(args: argparse.Namespace) -> list[str]:
    missing = []
    if not args.certificate_p12:
        missing.append("certificate_p12")
    elif not Path(args.certificate_p12).expanduser().is_file():
        missing.append("certificate_p12_file")
    if not args.certificate_password:
        missing.append("certificate_password")
    if not args.provisioning_profile:
        missing.append("provisioning_profile")
    elif not Path(args.provisioning_profile).expanduser().is_file():
        missing.append("provisioning_profile_file")
    if not args.team_id:
        missing.append("team_id")
    return missing


def _secret_values(args: argparse.Namespace) -> dict[str, str]:
    values = {
        "X0T_IOS_CERTIFICATE_P12_BASE64": _encode_file(
            Path(args.certificate_p12).expanduser()
        ),
        "X0T_IOS_CERTIFICATE_PASSWORD": args.certificate_password,
        "X0T_IOS_PROVISIONING_PROFILE_BASE64": _encode_file(
            Path(args.provisioning_profile).expanduser()
        ),
        "X0T_IOS_TEAM_ID": args.team_id,
    }
    if args.bundle_id:
        values["X0T_IOS_BUNDLE_ID"] = args.bundle_id
    if args.export_method:
        values["X0T_IOS_EXPORT_METHOD"] = args.export_method
    return values


def _write_local_env(path: Path, values: Mapping[str, str]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    payload = "\n".join(f"{name}={value}" for name, value in values.items()) + "\n"
    path.write_text(payload, encoding="utf-8")
    _chmod_owner_only(path)


def run(
    args: argparse.Namespace,
    *,
    runner: Callable[..., subprocess.CompletedProcess[str]] = subprocess.run,
) -> dict[str, Any]:
    report = build_plan(args)
    missing = _missing_inputs(args)
    if missing:
        if args.prepare:
            report["status"] = "FAILED"
            report["error"] = "missing_required_inputs"
            report["missing_inputs"] = missing
        return report

    if not args.prepare:
        return report

    values = _secret_values(args)
    report["status"] = "PREPARED"
    report["certificate_p12_size_bytes"] = Path(args.certificate_p12).expanduser().stat().st_size
    report["provisioning_profile_size_bytes"] = (
        Path(args.provisioning_profile).expanduser().stat().st_size
    )

    if args.write_local_env:
        _write_local_env(Path(args.write_local_env), values)
        report["local_env_written"] = True
        report["local_env_path"] = args.write_local_env

    if args.set_github_secrets:
        secret_results = {
            name: _set_github_secret(
                repo=args.repo,
                name=name,
                value=value,
                runner=runner,
            )
            for name, value in values.items()
        }
        report["github_secrets_written"] = secret_results
        report["github_secrets_ready"] = all(secret_results.values())

    report["claim_boundary"]["ios_device_signing_material_prepared"] = True
    return report


def parse_args(argv: Sequence[str] | None = None) -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description="Prepare iOS signing secrets from local Apple signing files.",
    )
    parser.add_argument("--repo", default=os.environ.get("GH_REPO", DEFAULT_REPO))
    parser.add_argument("--certificate-p12")
    parser.add_argument("--certificate-password")
    parser.add_argument("--provisioning-profile")
    parser.add_argument("--team-id")
    parser.add_argument("--bundle-id", default=None)
    parser.add_argument("--export-method", default=None)
    parser.add_argument("--prepare", action="store_true")
    parser.add_argument("--set-github-secrets", action="store_true")
    parser.add_argument(
        "--write-local-env",
        nargs="?",
        const=DEFAULT_LOCAL_ENV,
        default=None,
        help="write a chmod 0600 local env file; default path is used if no value is given",
    )
    parser.add_argument("--require-complete", action="store_true")
    parser.add_argument("--output", help="optional JSON report path")
    parser.add_argument("--json", action="store_true")
    return parser.parse_args(argv)


def _write_output(report: Mapping[str, Any], output: str | None) -> None:
    if not output:
        return
    path = Path(output)
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(report, indent=2, sort_keys=True) + "\n", encoding="utf-8")  # lgtm[py/clear-text-storage-sensitive-data] - diagnostic report, no secrets


def _print_text(report: Mapping[str, Any]) -> None:
    print(f"iOS signing setup: {report['status']}")
    print("GitHub secrets:")
    for name in report["github_secret_names"]:
        print(f"- {name}")
    if report.get("error"):
        print(f"Error: {report['error']}")
    print("Private values are not printed.")


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
    if args.require_complete and not report.get("github_secrets_ready", False):
        return 2
    return 0


if __name__ == "__main__":
    raise SystemExit(main(sys.argv[1:]))
