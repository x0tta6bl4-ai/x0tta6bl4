#!/usr/bin/env python3
"""Report native Android/iOS release signing readiness without printing secrets."""

from __future__ import annotations

import argparse
import json
import os
import subprocess
import sys
from collections.abc import Mapping, Sequence
from dataclasses import dataclass
from datetime import datetime, timezone
from pathlib import Path
from typing import Any


SCHEMA = "x0tta6bl4.native_signing_readiness.v1"
DEFAULT_REPO = "x0tta6bl4-ai/x0tta6bl4"


@dataclass(frozen=True)
class SecretRequirement:
    name: str
    purpose: str
    file_must_exist: bool = False


ENV_CI_REQUIREMENTS: dict[str, tuple[SecretRequirement, ...]] = {
    "android": (
        SecretRequirement("ANDROID_KEYSTORE_BASE64", "base64 encoded Android release keystore"),
        SecretRequirement("ANDROID_KEYSTORE_PASSWORD", "Android keystore password"),
        SecretRequirement("ANDROID_KEY_ALIAS", "Android release key alias"),
        SecretRequirement("ANDROID_KEY_PASSWORD", "Android release key password"),
    ),
    "ios": (
        SecretRequirement("X0T_IOS_CERTIFICATE_P12_BASE64", "base64 encoded Apple .p12 certificate"),
        SecretRequirement("X0T_IOS_CERTIFICATE_PASSWORD", "Apple certificate password"),
        SecretRequirement(
            "X0T_IOS_PROVISIONING_PROFILE_BASE64",
            "base64 encoded Apple provisioning profile",
        ),
        SecretRequirement("X0T_IOS_TEAM_ID", "Apple Developer Team ID"),
    ),
}

ENV_LOCAL_REQUIREMENTS: dict[str, tuple[SecretRequirement, ...]] = {
    "android": (
        SecretRequirement("ANDROID_KEYSTORE_PATH", "local Android release keystore path", True),
        SecretRequirement("ANDROID_KEYSTORE_PASSWORD", "Android keystore password"),
        SecretRequirement("ANDROID_KEY_ALIAS", "Android release key alias"),
        SecretRequirement("ANDROID_KEY_PASSWORD", "Android release key password"),
    ),
    "ios": ENV_CI_REQUIREMENTS["ios"],
}

GITHUB_SECRET_REQUIREMENTS: dict[str, tuple[SecretRequirement, ...]] = {
    "android": (
        SecretRequirement("X0T_ANDROID_KEYSTORE_BASE64", "base64 encoded Android release keystore"),
        SecretRequirement("X0T_ANDROID_KEYSTORE_PASSWORD", "Android keystore password"),
        SecretRequirement("X0T_ANDROID_KEY_ALIAS", "Android release key alias"),
        SecretRequirement("X0T_ANDROID_KEY_PASSWORD", "Android release key password"),
    ),
    "ios": ENV_CI_REQUIREMENTS["ios"],
}

OPTIONAL_GITHUB_SECRETS: dict[str, tuple[str, ...]] = {
    "ios": ("X0T_IOS_BUNDLE_ID", "X0T_IOS_EXPORT_METHOD"),
}


def _utc_now() -> str:
    return datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")


def _is_present(value: str | None) -> bool:
    return bool(value and value.strip())


def _env_secret_state(
    requirement: SecretRequirement,
    environ: Mapping[str, str],
) -> dict[str, Any]:
    present = _is_present(environ.get(requirement.name))
    state: dict[str, Any] = {
        "name": requirement.name,
        "present": present,
        "purpose": requirement.purpose,
    }
    if requirement.file_must_exist:
        value = environ.get(requirement.name)
        file_exists = bool(value and Path(value).expanduser().exists())
        state["file_exists"] = file_exists
        state["ready"] = present and file_exists
    else:
        state["ready"] = present
    return state


def _platform_report_from_requirements(
    platform: str,
    requirements: Sequence[SecretRequirement],
    states: Sequence[dict[str, Any]],
) -> dict[str, Any]:
    missing = [state["name"] for state in states if not state["ready"]]
    return {
        "platform": platform,
        "ready": not missing,
        "required_total": len(requirements),
        "ready_total": len(requirements) - len(missing),
        "missing": missing,
        "checks": list(states),
    }


def build_env_report(
    *,
    source: str,
    platforms: Sequence[str],
    environ: Mapping[str, str] | None = None,
) -> dict[str, Any]:
    if source == "env-ci":
        requirements_by_platform = ENV_CI_REQUIREMENTS
    elif source == "env-local":
        requirements_by_platform = ENV_LOCAL_REQUIREMENTS
    else:
        raise ValueError(f"unsupported env source: {source}")

    env = os.environ if environ is None else environ
    platform_reports = {}
    for platform in platforms:
        requirements = requirements_by_platform[platform]
        states = [_env_secret_state(requirement, env) for requirement in requirements]
        platform_reports[platform] = _platform_report_from_requirements(
            platform,
            requirements,
            states,
        )

    ready = all(item["ready"] for item in platform_reports.values())
    return _base_report(source=source, platforms=platform_reports, ready=ready)


def _parse_gh_secret_names(stdout: str) -> set[str]:
    try:
        payload = json.loads(stdout)
    except json.JSONDecodeError:
        return {line.split()[0] for line in stdout.splitlines() if line.strip()}

    if not isinstance(payload, list):
        return set()
    names = set()
    for item in payload:
        if isinstance(item, dict) and isinstance(item.get("name"), str):
            names.add(item["name"])
    return names


def build_github_report(
    *,
    repo: str,
    platforms: Sequence[str],
    runner=subprocess.run,
) -> dict[str, Any]:
    result = runner(
        ["gh", "secret", "list", "--repo", repo, "--json", "name"],
        check=False,
        capture_output=True,
        text=True,
    )
    if result.returncode != 0:
        report = _base_report(
            source="github",
            platforms={},
            ready=False,
            repo=repo,
            source_error="gh secret list failed",
        )
        report["source_error_stderr_present"] = bool(result.stderr.strip())
        return report

    present_names = _parse_gh_secret_names(result.stdout)
    platform_reports = {}
    for platform in platforms:
        requirements = GITHUB_SECRET_REQUIREMENTS[platform]
        states = [
            {
                "name": requirement.name,
                "present": requirement.name in present_names,
                "ready": requirement.name in present_names,
                "purpose": requirement.purpose,
            }
            for requirement in requirements
        ]
        platform_report = _platform_report_from_requirements(platform, requirements, states)
        optional = OPTIONAL_GITHUB_SECRETS.get(platform, ())
        if optional:
            platform_report["optional"] = [
                {"name": name, "present": name in present_names} for name in optional
            ]
        platform_reports[platform] = platform_report

    ready = all(item["ready"] for item in platform_reports.values())
    return _base_report(source="github", platforms=platform_reports, ready=ready, repo=repo)


def _base_report(
    *,
    source: str,
    platforms: Mapping[str, Any],
    ready: bool,
    repo: str | None = None,
    source_error: str | None = None,
) -> dict[str, Any]:
    report: dict[str, Any] = {
        "schema": SCHEMA,
        "generated_at_utc": _utc_now(),
        "source": source,
        "ready": ready,
        "platforms": dict(platforms),
        "claim_boundary": {
            "checks_presence_only": True,
            "secret_values_redacted": True,
            "certificate_trust_chain_validated": False,
            "app_store_notarization_validated": False,
            "production_release_claim": False,
        },
    }
    if repo:
        report["repo"] = repo
    if source_error:
        report["source_error"] = source_error
    return report


def parse_args(argv: Sequence[str] | None = None) -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description="Check native Android/iOS signing readiness without printing secrets.",
    )
    parser.add_argument(
        "--source",
        choices=("env-ci", "env-local", "github"),
        default="env-local",
        help="where signing material should be checked",
    )
    parser.add_argument("--repo", default=os.environ.get("GH_REPO", DEFAULT_REPO))
    parser.add_argument(
        "--platform",
        action="append",
        choices=("android", "ios"),
        help="platform to check; repeatable; defaults to both",
    )
    parser.add_argument("--require-ready", action="store_true")
    parser.add_argument("--json", action="store_true")
    parser.add_argument("--output", help="optional JSON output path")
    return parser.parse_args(argv)


def run(args: argparse.Namespace) -> dict[str, Any]:
    platforms = args.platform or ["android", "ios"]
    if args.source == "github":
        return build_github_report(repo=args.repo, platforms=platforms)
    return build_env_report(source=args.source, platforms=platforms)


def _write_output(report: Mapping[str, Any], output: str | None) -> None:
    if not output:
        return
    path = Path(output)
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(report, indent=2, sort_keys=True) + "\n", encoding="utf-8")


def _print_text(report: Mapping[str, Any]) -> None:
    print(f"Native signing readiness: {'READY' if report['ready'] else 'BLOCKED'}")
    print(f"Source: {report['source']}")
    for platform, item in report["platforms"].items():
        status = "READY" if item["ready"] else "BLOCKED"
        print(f"- {platform}: {status} ({item['ready_total']}/{item['required_total']})")
        if item["missing"]:
            print("  missing: " + ", ".join(item["missing"]))
    if report.get("source_error"):
        print(f"Source error: {report['source_error']}")
    print("Secret values are not printed.")


def main(argv: Sequence[str] | None = None) -> int:
    args = parse_args(argv)
    report = run(args)
    _write_output(report, args.output)
    if args.json:
        print(json.dumps(report, indent=2, sort_keys=True))
    else:
        _print_text(report)

    if report.get("source_error"):
        return 1
    if args.require_ready and not report["ready"]:
        return 2
    return 0


if __name__ == "__main__":
    raise SystemExit(main(sys.argv[1:]))
