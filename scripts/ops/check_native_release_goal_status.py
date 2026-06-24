#!/usr/bin/env python3
"""Summarise the native app release goal status for Android, iOS, Windows, Ubuntu."""

from __future__ import annotations

import argparse
import importlib.util
import json
import subprocess
import sys
from collections.abc import Callable, Mapping, Sequence
from datetime import datetime, timezone
from pathlib import Path
from typing import Any


SCHEMA = "x0tta6bl4.native_release_goal_status.v1"
DEFAULT_REPO = "x0tta6bl4-ai/x0tta6bl4"
REQUIRED_PLATFORMS = ("android", "ios", "ubuntu", "windows")
REQUIRED_IOS_SECRET_NAMES = (
    "X0T_IOS_CERTIFICATE_P12_BASE64",
    "X0T_IOS_CERTIFICATE_PASSWORD",
    "X0T_IOS_PROVISIONING_PROFILE_BASE64",
    "X0T_IOS_TEAM_ID",
)


def _utc_now() -> str:
    return datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")


def _load_ios_setup_module() -> Any:
    path = Path(__file__).resolve().with_name("run_ios_signed_release_setup.py")
    spec = importlib.util.spec_from_file_location("x0tta6bl4_ios_release_setup_status", path)
    if spec is None or spec.loader is None:
        raise RuntimeError(f"cannot load {path}")
    module = importlib.util.module_from_spec(spec)
    sys.modules[spec.name] = module
    spec.loader.exec_module(module)
    return module


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


def _load_json(path: str | None) -> tuple[dict[str, Any] | None, str | None]:
    if not path:
        return None, "audit_json_not_provided"
    audit_path = Path(path).expanduser()
    if not audit_path.is_file():
        return None, "audit_json_missing"
    try:
        data = json.loads(audit_path.read_text(encoding="utf-8"))
    except json.JSONDecodeError:
        return None, "audit_json_invalid"
    if not isinstance(data, dict):
        return None, "audit_json_not_object"
    return data, None


def _platform_status(audit: Mapping[str, Any] | None) -> dict[str, Any]:
    statuses: dict[str, Any] = {}
    platforms = audit.get("platforms") if isinstance(audit, Mapping) else None
    platforms = platforms if isinstance(platforms, Mapping) else {}
    for name in REQUIRED_PLATFORMS:
        platform = platforms.get(name)
        if not isinstance(platform, Mapping):
            statuses[name] = {
                "complete": False,
                "artifact_kinds": [],
                "failures": [f"{name}:audit_missing"],
            }
            continue
        statuses[name] = {
            "complete": platform.get("complete") is True,
            "artifact_kinds": list(platform.get("artifact_kinds") or []),
            "failures": list(platform.get("failures") or []),
        }
    return statuses


def _secret_names_from_gh(
    *,
    repo: str,
    runner: Callable[..., subprocess.CompletedProcess[str]] = subprocess.run,
) -> tuple[set[str], str | None]:
    result = _run_text(["gh", "secret", "list", "--repo", repo], runner=runner)
    if result.returncode != 0:
        return set(), "github_secret_list_failed"
    names = {
        line.split()[0]
        for line in result.stdout.splitlines()
        if line.strip() and not line.startswith("#")
    }
    return names, None


def _secret_names_from_file(path: str | None) -> tuple[set[str], str | None]:
    if not path:
        return set(), None
    secret_path = Path(path).expanduser()
    if not secret_path.is_file():
        return set(), "github_secret_names_file_missing"
    names = {
        line.strip().split()[0]
        for line in secret_path.read_text(encoding="utf-8").splitlines()
        if line.strip() and not line.lstrip().startswith("#")
    }
    return names, None


def _ios_plan(args: argparse.Namespace) -> dict[str, Any]:
    module = _load_ios_setup_module()
    argv = [
        "--certificate-cer",
        args.ios_certificate_cer,
        "--private-key",
        args.ios_private_key,
        "--p12-output",
        args.ios_p12_output,
        "--provisioning-profile",
        args.ios_provisioning_profile,
        "--bundle-id",
        args.ios_bundle_id,
        "--export-method",
        args.ios_export_method,
        "--repo",
        args.repo,
        "--ref",
        args.ref,
    ]
    if args.ios_p12_password_present:
        argv.extend(["--p12-password", "<present>"])
    if args.ios_team_id_present:
        argv.extend(["--team-id", "<present>"])
    plan = module.run(module.parse_args(argv))
    plan.pop("generated_at_utc", None)
    return plan


def build_report(
    args: argparse.Namespace,
    *,
    runner: Callable[..., subprocess.CompletedProcess[str]] = subprocess.run,
) -> dict[str, Any]:
    audit, audit_error = _load_json(args.audit_json)
    platforms = _platform_status(audit)
    ios_plan = _ios_plan(args)

    secret_names, secret_error = _secret_names_from_file(args.github_secret_names_file)
    if args.check_github_secrets:
        secret_names, secret_error = _secret_names_from_gh(repo=args.repo, runner=runner)
    missing_ios_secrets = [
        name for name in REQUIRED_IOS_SECRET_NAMES if name not in secret_names
    ] if secret_names or args.check_github_secrets or args.github_secret_names_file else []

    platform_failures = [
        failure
        for platform in platforms.values()
        for failure in platform.get("failures", [])
    ]
    missing_ios_inputs = list(ios_plan.get("missing_inputs") or [])
    audit_complete = bool(audit and audit.get("complete") is True)
    platforms_complete = all(platform["complete"] for platform in platforms.values())
    goal_complete = audit_complete and platforms_complete

    next_actions: list[str] = []
    if audit_error:
        next_actions.append(
            "download native release audit: gh run download <run-id> --name x0tta6bl4-native-release-artifact-audit"
        )
    if missing_ios_inputs:
        next_actions.append(
            "finish local iOS signing intake: provide Apple .cer, .mobileprovision, .p12 password, and Team ID"
        )
    if missing_ios_secrets:
        next_actions.append(
            "write missing iOS GitHub secrets with scripts/ops/run_ios_signed_release_setup.py --prepare --set-github-secrets"
        )
    if "ios:signed_ipa_missing" in platform_failures:
        next_actions.append(
            "trigger Native App Builds with --require-complete-release after iOS secrets are present"
        )
    if not next_actions and not goal_complete:
        next_actions.append("inspect native release audit failures and rebuild the failing platform")

    return {
        "schema": SCHEMA,
        "generated_at_utc": _utc_now(),
        "repo": args.repo,
        "ref": args.ref,
        "goal": "fully working native x0tta6bl4 apps for android, ios, windows, ubuntu",
        "goal_complete": goal_complete,
        "audit": {
            "path": args.audit_json,
            "loaded": audit is not None,
            "error": audit_error,
            "complete": audit_complete,
            "summary": audit.get("summary") if isinstance(audit, Mapping) else {},
        },
        "platforms": platforms,
        "ios_signing": {
            "local_plan_status": ios_plan.get("status"),
            "missing_inputs": missing_ios_inputs,
            "certificate_cer_present": ios_plan.get("certificate_cer_present"),
            "private_key_present": ios_plan.get("private_key_present"),
            "provisioning_profile_present": ios_plan.get("provisioning_profile_present"),
            "p12_password_present": ios_plan.get("p12_password_present"),
            "team_id_present": ios_plan.get("team_id_present"),
            "missing_github_secrets": missing_ios_secrets,
            "github_secret_check_error": secret_error,
        },
        "next_actions": next_actions,
        "claim_boundary": {
            "does_not_create_apple_certificate": True,
            "does_not_create_provisioning_profile": True,
            "does_not_claim_ios_signed_ipa_without_audit": True,
            "private_values_redacted": True,
        },
    }


def parse_args(argv: Sequence[str] | None = None) -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description="Check the current four-platform native app release goal status.",
    )
    parser.add_argument("--repo", default=DEFAULT_REPO)
    parser.add_argument("--ref", default="sync-main-20260529")
    parser.add_argument("--audit-json")
    parser.add_argument("--check-github-secrets", action="store_true")
    parser.add_argument("--github-secret-names-file")
    parser.add_argument(
        "--ios-certificate-cer",
        default=str(Path.home() / ".local/share/x0tta6bl4/ios-signing/apple-distribution.cer"),
    )
    parser.add_argument(
        "--ios-private-key",
        default=str(Path.home() / ".local/share/x0tta6bl4/ios-signing/apple-distribution.key"),
    )
    parser.add_argument(
        "--ios-p12-output",
        default=str(Path.home() / ".local/share/x0tta6bl4/ios-signing/apple-distribution.p12"),
    )
    parser.add_argument(
        "--ios-provisioning-profile",
        default=str(Path.home() / ".local/share/x0tta6bl4/ios-signing/x0tta6bl4.mobileprovision"),
    )
    parser.add_argument("--ios-p12-password-present", action="store_true")
    parser.add_argument("--ios-team-id-present", action="store_true")
    parser.add_argument("--ios-bundle-id", default="net.x0tta6bl4.mesh")
    parser.add_argument("--ios-export-method", default="ad-hoc")
    parser.add_argument("--require-complete", action="store_true")
    parser.add_argument("--output")
    parser.add_argument("--json", action="store_true")
    return parser.parse_args(argv)


def _write_output(report: Mapping[str, Any], output: str | None) -> None:
    if not output:
        return
    path = Path(output)
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(report, indent=2, sort_keys=True) + "\n", encoding="utf-8")  # lgtm[py/clear-text-storage-sensitive-data]  # lgtm[py/clear-text-storage-sensitive-data] - diagnostic report, no secrets


def _print_text(report: Mapping[str, Any]) -> None:
    print(f"Native release goal complete: {report['goal_complete']}")
    for name, platform in report["platforms"].items():
        kinds = ", ".join(platform["artifact_kinds"]) or "none"
        print(f"- {name}: complete={platform['complete']} artifacts={kinds}")
        for failure in platform["failures"]:
            print(f"  failure: {failure}")
    missing_inputs = report["ios_signing"]["missing_inputs"]
    if missing_inputs:
        print("Missing local iOS inputs: " + ", ".join(missing_inputs))
    missing_secrets = report["ios_signing"]["missing_github_secrets"]
    if missing_secrets:
        print("Missing iOS GitHub secrets: " + ", ".join(missing_secrets))
    print("Next actions:")
    for action in report["next_actions"]:
        print(f"- {action}")


def main(argv: Sequence[str] | None = None) -> int:
    args = parse_args(argv)
    report = build_report(args)
    _write_output(report, args.output)
    if args.json:
        print(json.dumps(report, indent=2, sort_keys=True))
    else:
        _print_text(report)
    if args.require_complete and report["goal_complete"] is not True:
        return 2
    return 0


if __name__ == "__main__":
    raise SystemExit(main(sys.argv[1:]))
