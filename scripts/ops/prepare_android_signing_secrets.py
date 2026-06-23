#!/usr/bin/env python3
"""Prepare Android release signing material without printing private values."""

from __future__ import annotations

import argparse
import base64
import json
import os
import secrets
import shutil
import stat
import subprocess
import sys
from collections.abc import Callable, Mapping, Sequence
from datetime import datetime, timezone
from pathlib import Path
from typing import Any


SCHEMA = "x0tta6bl4.android_signing_setup.v1"
DEFAULT_REPO = "x0tta6bl4-ai/x0tta6bl4"
DEFAULT_KEYSTORE = ".tmp/native-signing/android/release.keystore"
DEFAULT_ALIAS = "x0tta6bl4_release"
DEFAULT_DNAME = "CN=x0tta6bl4,O=x0tta6bl4,L=Internet,ST=NA,C=US"
DEFAULT_LOCAL_ENV = ".tmp/native-signing/android/android-signing.env"


def _utc_now() -> str:
    return datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")


def _random_password() -> str:
    return secrets.token_urlsafe(36)


def _chmod_owner_only(path: Path) -> None:
    path.chmod(stat.S_IRUSR | stat.S_IWUSR)


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


def _generate_keystore(
    *,
    keystore: Path,
    alias: str,
    dname: str,
    validity_days: int,
    force: bool,
    store_password: str,
    key_password: str,
    runner: Callable[..., subprocess.CompletedProcess[str]] = subprocess.run,
) -> tuple[bool, str | None]:
    if keystore.exists() and not force:
        return False, "keystore_exists"

    keytool = shutil.which("keytool")
    if not keytool:
        return False, "keytool_missing"

    keystore.parent.mkdir(parents=True, exist_ok=True)
    if keystore.exists() and force:
        keystore.unlink()

    result = _run(
        [
            keytool,
            "-genkeypair",
            "-v",
            "-storetype",
            "PKCS12",
            "-keystore",
            str(keystore),
            "-alias",
            alias,
            "-keyalg",
            "RSA",
            "-keysize",
            "4096",
            "-validity",
            str(validity_days),
            "-storepass",
            store_password,
            "-keypass",
            key_password,
            "-dname",
            dname,
        ],
        runner=runner,
    )
    if result.returncode != 0:
        return False, "keytool_failed"

    _chmod_owner_only(keystore)
    return True, None


def _write_local_env(
    *,
    path: Path,
    keystore: Path,
    alias: str,
    store_password: str,
    key_password: str,
) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(
        "\n".join(
            [
                f"ANDROID_KEYSTORE_PATH={keystore.resolve()}",
                f"ANDROID_KEYSTORE_PASSWORD={store_password}",
                f"ANDROID_KEY_ALIAS={alias}",
                f"ANDROID_KEY_PASSWORD={key_password}",
            ]
        )
        + "\n",
        encoding="utf-8",
    )
    _chmod_owner_only(path)


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


def _set_github_secrets(
    *,
    repo: str,
    keystore: Path,
    alias: str,
    store_password: str,
    key_password: str,
    runner: Callable[..., subprocess.CompletedProcess[str]] = subprocess.run,
) -> dict[str, bool]:
    encoded_keystore = base64.b64encode(keystore.read_bytes()).decode("ascii")
    values = {
        "X0T_ANDROID_KEYSTORE_BASE64": encoded_keystore,
        "X0T_ANDROID_KEYSTORE_PASSWORD": store_password,
        "X0T_ANDROID_KEY_ALIAS": alias,
        "X0T_ANDROID_KEY_PASSWORD": key_password,
    }
    return {
        name: _set_github_secret(repo=repo, name=name, value=value, runner=runner)
        for name, value in values.items()
    }


def _redacted_env_preview(path: Path) -> list[str]:
    return [
        f"ANDROID_KEYSTORE_PATH={path.resolve()}",
        "ANDROID_KEYSTORE_PASSWORD=<redacted>",
        "ANDROID_KEY_ALIAS=<redacted>",
        "ANDROID_KEY_PASSWORD=<redacted>",
    ]


def build_plan(args: argparse.Namespace) -> dict[str, Any]:
    keystore = Path(args.keystore)
    return {
        "schema": SCHEMA,
        "generated_at_utc": _utc_now(),
        "status": "PLAN",
        "repo": args.repo,
        "keystore_path": str(keystore),
        "alias": args.alias,
        "validity_days": args.validity_days,
        "will_generate_keystore": args.generate,
        "will_write_local_env": bool(args.write_local_env),
        "will_set_github_secrets": args.set_github_secrets,
        "github_secret_names": [
            "X0T_ANDROID_KEYSTORE_BASE64",
            "X0T_ANDROID_KEYSTORE_PASSWORD",
            "X0T_ANDROID_KEY_ALIAS",
            "X0T_ANDROID_KEY_PASSWORD",
        ],
        "local_env_preview": _redacted_env_preview(keystore),
        "claim_boundary": {
            "android_release_signing_material_prepared": False,
            "android_play_app_signing_validated": False,
            "google_play_upload_validated": False,
            "private_values_redacted": True,
        },
    }


def run(
    args: argparse.Namespace,
    *,
    runner: Callable[..., subprocess.CompletedProcess[str]] = subprocess.run,
    password_factory: Callable[[], str] = _random_password,
) -> dict[str, Any]:
    report = build_plan(args)
    if not args.generate:
        return report

    keystore = Path(args.keystore)
    store_password = password_factory()
    # Android Gradle reads PKCS12 keys most reliably when the key password
    # matches the store password. Separate key passwords can produce
    # "Given final block not properly padded" at packageRelease time.
    key_password = store_password
    generated, error = _generate_keystore(
        keystore=keystore,
        alias=args.alias,
        dname=args.dname,
        validity_days=args.validity_days,
        force=args.force,
        store_password=store_password,
        key_password=key_password,
        runner=runner,
    )
    report["status"] = "GENERATED" if generated else "FAILED"
    report["keystore_generated"] = generated
    report["keystore_exists"] = keystore.exists()
    report["key_password_matches_store_password"] = True
    if keystore.exists():
        report["keystore_size_bytes"] = keystore.stat().st_size
    if error:
        report["error"] = error
        return report

    if args.write_local_env:
        _write_local_env(
            path=Path(args.write_local_env),
            keystore=keystore,
            alias=args.alias,
            store_password=store_password,
            key_password=key_password,
        )
        report["local_env_written"] = True
        report["local_env_path"] = args.write_local_env

    if args.set_github_secrets:
        secret_results = _set_github_secrets(
            repo=args.repo,
            keystore=keystore,
            alias=args.alias,
            store_password=store_password,
            key_password=key_password,
            runner=runner,
        )
        report["github_secrets_written"] = secret_results
        report["github_secrets_ready"] = all(secret_results.values())

    report["claim_boundary"]["android_release_signing_material_prepared"] = generated
    return report


def parse_args(argv: Sequence[str] | None = None) -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description="Generate Android release signing material and optionally upload GitHub secrets.",
    )
    parser.add_argument("--repo", default=os.environ.get("GH_REPO", DEFAULT_REPO))
    parser.add_argument("--keystore", default=DEFAULT_KEYSTORE)
    parser.add_argument("--alias", default=DEFAULT_ALIAS)
    parser.add_argument("--dname", default=DEFAULT_DNAME)
    parser.add_argument("--validity-days", type=int, default=9125)
    parser.add_argument("--generate", action="store_true")
    parser.add_argument("--force", action="store_true")
    parser.add_argument(
        "--write-local-env",
        nargs="?",
        const=DEFAULT_LOCAL_ENV,
        default=None,
        help="write a chmod 0600 local env file; default path is used if no value is given",
    )
    parser.add_argument("--set-github-secrets", action="store_true")
    parser.add_argument("--require-complete", action="store_true")
    parser.add_argument("--output", help="optional JSON report path")
    parser.add_argument("--json", action="store_true")
    return parser.parse_args(argv)


def _write_output(report: Mapping[str, Any], output: str | None) -> None:
    if not output:
        return
    path = Path(output)
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(report, indent=2, sort_keys=True) + "\n", encoding="utf-8")


def _print_text(report: Mapping[str, Any]) -> None:
    print(f"Android signing setup: {report['status']}")
    print(f"Keystore: {report['keystore_path']}")
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
