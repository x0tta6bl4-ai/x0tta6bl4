#!/usr/bin/env python3
"""Generate an Apple Distribution CSR without printing private key material."""

from __future__ import annotations

import argparse
import json
import os
import shutil
import stat
import subprocess
import sys
from collections.abc import Callable, Mapping, Sequence
from datetime import datetime, timezone
from pathlib import Path
from typing import Any


SCHEMA = "x0tta6bl4.ios_distribution_certificate_request.v1"
DEFAULT_KEY_DIR = Path.home() / ".local/share/x0tta6bl4/ios-signing"
DEFAULT_PRIVATE_KEY = DEFAULT_KEY_DIR / "apple-distribution.key"
DEFAULT_CSR = DEFAULT_KEY_DIR / "apple-distribution.csr"
DEFAULT_COMMON_NAME = "x0tta6bl4 Apple Distribution"
DEFAULT_COUNTRY = "US"


def _utc_now() -> str:
    return datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")


def _chmod_owner_only(path: Path) -> None:
    path.chmod(stat.S_IRUSR | stat.S_IWUSR)


def _run(
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


def _subject(*, common_name: str, email_address: str | None, country: str) -> str:
    parts = [f"/CN={common_name}", f"/C={country}"]
    if email_address:
        parts.append(f"/emailAddress={email_address}")
    return "".join(parts)


def build_plan(args: argparse.Namespace) -> dict[str, Any]:
    private_key = Path(args.private_key).expanduser()
    csr = Path(args.csr).expanduser()
    return {
        "schema": SCHEMA,
        "generated_at_utc": _utc_now(),
        "status": "PLAN",
        "private_key_path": str(private_key),
        "csr_path": str(csr),
        "common_name": args.common_name,
        "country": args.country,
        "email_address_present": bool(args.email_address),
        "will_generate": args.generate,
        "force": args.force,
        "claim_boundary": {
            "csr_ready_for_apple_developer_portal": False,
            "apple_certificate_created": False,
            "p12_exported": False,
            "provisioning_profile_created": False,
            "github_ios_secrets_ready": False,
            "private_key_printed": False,
            "private_values_redacted": True,
        },
        "next_actions": [
            "Upload the CSR file to Apple Developer Certificates and create an Apple Distribution certificate.",
            "Export a .p12 containing that certificate and the generated private key from a secure Apple/macOS keychain.",
            "Create or update an iOS provisioning profile for net.x0tta6bl4.mesh.",
            "Run scripts/ops/prepare_ios_signing_secrets.py to set GitHub iOS signing secrets.",
        ],
    }


def _generate_csr(
    *,
    private_key: Path,
    csr: Path,
    common_name: str,
    email_address: str | None,
    country: str,
    force: bool,
    runner: Callable[..., subprocess.CompletedProcess[str]] = subprocess.run,
) -> tuple[bool, str | None]:
    if (private_key.exists() or csr.exists()) and not force:
        return False, "output_exists"

    openssl = shutil.which("openssl")
    if not openssl:
        return False, "openssl_missing"

    private_key.parent.mkdir(parents=True, exist_ok=True)
    csr.parent.mkdir(parents=True, exist_ok=True)
    if force:
        private_key.unlink(missing_ok=True)
        csr.unlink(missing_ok=True)

    result = _run(
        [
            openssl,
            "req",
            "-new",
            "-newkey",
            "rsa:2048",
            "-nodes",
            "-keyout",
            str(private_key),
            "-out",
            str(csr),
            "-subj",
            _subject(
                common_name=common_name,
                email_address=email_address,
                country=country,
            ),
        ],
        runner=runner,
    )
    if result.returncode != 0:
        return False, "openssl_failed"

    _chmod_owner_only(private_key)
    return True, None


def run(
    args: argparse.Namespace,
    *,
    runner: Callable[..., subprocess.CompletedProcess[str]] = subprocess.run,
) -> dict[str, Any]:
    report = build_plan(args)
    if not args.generate:
        return report

    private_key = Path(args.private_key).expanduser()
    csr = Path(args.csr).expanduser()
    generated, error = _generate_csr(
        private_key=private_key,
        csr=csr,
        common_name=args.common_name,
        email_address=args.email_address,
        country=args.country,
        force=args.force,
        runner=runner,
    )
    report["status"] = "GENERATED" if generated else "FAILED"
    report["private_key_exists"] = private_key.exists()
    report["csr_exists"] = csr.exists()
    if private_key.exists():
        report["private_key_mode"] = oct(stat.S_IMODE(private_key.stat().st_mode))
        report["private_key_size_bytes"] = private_key.stat().st_size
    if csr.exists():
        report["csr_size_bytes"] = csr.stat().st_size
    if error:
        report["error"] = error
        return report

    report["claim_boundary"]["csr_ready_for_apple_developer_portal"] = True
    return report


def parse_args(argv: Sequence[str] | None = None) -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description="Generate an Apple Distribution certificate signing request.",
    )
    parser.add_argument("--private-key", default=str(DEFAULT_PRIVATE_KEY))
    parser.add_argument("--csr", default=str(DEFAULT_CSR))
    parser.add_argument("--common-name", default=DEFAULT_COMMON_NAME)
    parser.add_argument("--email-address", default=os.environ.get("X0T_IOS_CERT_EMAIL"))
    parser.add_argument("--country", default=DEFAULT_COUNTRY)
    parser.add_argument("--generate", action="store_true")
    parser.add_argument("--force", action="store_true")
    parser.add_argument("--require-generated", action="store_true")
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
    print(f"iOS distribution CSR setup: {report['status']}")
    print(f"CSR: {report['csr_path']}")
    print(f"Private key: {report['private_key_path']}")
    if report.get("error"):
        print(f"Error: {report['error']}")
    print("Private key contents are not printed.")


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
    if args.require_generated and report["status"] != "GENERATED":
        return 2
    return 0


if __name__ == "__main__":
    raise SystemExit(main(sys.argv[1:]))
