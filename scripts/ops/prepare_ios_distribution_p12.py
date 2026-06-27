#!/usr/bin/env python3
"""Build an iOS signing .p12 from an Apple certificate and private key."""

from __future__ import annotations

import argparse
import json
import os
import shutil
import stat
import subprocess
import sys
import tempfile
from collections.abc import Callable, Mapping, Sequence
from datetime import datetime, timezone
from pathlib import Path
from typing import Any


SCHEMA = "x0tta6bl4.ios_distribution_p12.v1"
DEFAULT_KEY = Path.home() / ".local/share/x0tta6bl4/ios-signing/apple-distribution.key"
DEFAULT_P12 = Path.home() / ".local/share/x0tta6bl4/ios-signing/apple-distribution.p12"


def _utc_now() -> str:
    return datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")


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


def _is_pem_certificate(path: Path) -> bool:
    try:
        head = path.read_bytes()[:128]
    except FileNotFoundError:
        return False
    return b"-----BEGIN CERTIFICATE-----" in head


def build_plan(args: argparse.Namespace) -> dict[str, Any]:
    certificate = Path(args.certificate_cer).expanduser() if args.certificate_cer else None
    private_key = Path(args.private_key).expanduser()
    p12 = Path(args.p12_output).expanduser()
    return {
        "schema": SCHEMA,
        "generated_at_utc": _utc_now(),
        "status": "PLAN",
        "certificate_cer_path": str(certificate) if certificate else None,
        "private_key_path": str(private_key),
        "p12_output_path": str(p12),
        "password_present": bool(args.p12_password),
        "will_export": args.export,
        "force": args.force,
        "claim_boundary": {
            "p12_exported": False,
            "apple_certificate_present": bool(certificate),
            "apple_certificate_created": False,
            "provisioning_profile_created": False,
            "github_ios_secrets_ready": False,
            "certificate_trust_chain_validated": False,
            "private_key_printed": False,
            "password_printed": False,
            "private_values_redacted": True,
        },
    }


def _missing_inputs(args: argparse.Namespace) -> list[str]:
    missing = []
    if not args.certificate_cer:
        missing.append("certificate_cer")
    elif not Path(args.certificate_cer).expanduser().is_file():
        missing.append("certificate_cer_file")
    if not Path(args.private_key).expanduser().is_file():
        missing.append("private_key_file")
    if not args.p12_password:
        missing.append("p12_password")
    return missing


def _convert_certificate_to_pem(
    *,
    certificate: Path,
    pem_path: Path,
    runner: Callable[..., subprocess.CompletedProcess[str]] = subprocess.run,
) -> tuple[Path | None, str | None]:
    openssl = shutil.which("openssl")
    if not openssl:
        return None, "openssl_missing"

    if _is_pem_certificate(certificate):
        return certificate, None

    result = _run(
        [
            openssl,
            "x509",
            "-inform",
            "DER",
            "-in",
            str(certificate),
            "-out",
            str(pem_path),
        ],
        runner=runner,
    )
    if result.returncode != 0:
        return None, "certificate_conversion_failed"
    return pem_path, None


def _export_p12(
    *,
    certificate: Path,
    private_key: Path,
    p12_output: Path,
    p12_password: str,
    force: bool,
    runner: Callable[..., subprocess.CompletedProcess[str]] = subprocess.run,
) -> tuple[bool, str | None]:
    if p12_output.exists() and not force:
        return False, "p12_output_exists"

    openssl = shutil.which("openssl")
    if not openssl:
        return False, "openssl_missing"

    p12_output.parent.mkdir(parents=True, exist_ok=True)
    if force:
        p12_output.unlink(missing_ok=True)

    with tempfile.TemporaryDirectory(prefix="x0t-ios-p12-") as tmp:
        pem_path, error = _convert_certificate_to_pem(
            certificate=certificate,
            pem_path=Path(tmp) / "certificate.pem",
            runner=runner,
        )
        if error:
            return False, error
        assert pem_path is not None

        result = _run(
            [
                openssl,
                "pkcs12",
                "-export",
                "-inkey",
                str(private_key),
                "-in",
                str(pem_path),
                "-out",
                str(p12_output),
                "-passout",
                "stdin",
            ],
            input_text=p12_password + "\n",
            runner=runner,
        )
        if result.returncode != 0:
            return False, "p12_export_failed"

    _chmod_owner_only(p12_output)
    return True, None


def run(
    args: argparse.Namespace,
    *,
    runner: Callable[..., subprocess.CompletedProcess[str]] = subprocess.run,
) -> dict[str, Any]:
    report = build_plan(args)
    missing = _missing_inputs(args)
    if missing:
        if args.export:
            report["status"] = "FAILED"
            report["error"] = "missing_required_inputs"
            report["missing_inputs"] = missing
        return report

    if not args.export:
        return report

    certificate = Path(args.certificate_cer).expanduser()
    private_key = Path(args.private_key).expanduser()
    p12_output = Path(args.p12_output).expanduser()
    exported, error = _export_p12(
        certificate=certificate,
        private_key=private_key,
        p12_output=p12_output,
        p12_password=args.p12_password,
        force=args.force,
        runner=runner,
    )
    report["status"] = "EXPORTED" if exported else "FAILED"
    report["certificate_cer_size_bytes"] = certificate.stat().st_size
    report["private_key_size_bytes"] = private_key.stat().st_size
    report["p12_exists"] = p12_output.exists()
    if p12_output.exists():
        report["p12_size_bytes"] = p12_output.stat().st_size
        report["p12_mode"] = oct(stat.S_IMODE(p12_output.stat().st_mode))
    if error:
        report["error"] = error
        return report

    report["claim_boundary"]["p12_exported"] = True
    return report


def parse_args(argv: Sequence[str] | None = None) -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description="Export an iOS Apple Distribution .p12 from certificate and private key.",
    )
    parser.add_argument("--certificate-cer")
    parser.add_argument("--private-key", default=str(DEFAULT_KEY))
    parser.add_argument("--p12-output", default=str(DEFAULT_P12))
    parser.add_argument("--p12-password", default=os.environ.get("X0T_IOS_CERTIFICATE_PASSWORD"))
    parser.add_argument("--export", action="store_true")
    parser.add_argument("--force", action="store_true")
    parser.add_argument("--require-exported", action="store_true")
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
    print(f"iOS distribution .p12 setup: {report['status']}")
    print(f"Certificate: {report['certificate_cer_path']}")
    print(f"Private key: {report['private_key_path']}")
    print(f"P12 output: {report['p12_output_path']}")
    if report.get("error"):
        print(f"Error: {report['error']}")
    print("Private key and password contents are not printed.")


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
    if args.require_exported and report["status"] != "EXPORTED":
        return 2
    return 0


if __name__ == "__main__":
    raise SystemExit(main(sys.argv[1:]))
