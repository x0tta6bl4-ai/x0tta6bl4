#!/usr/bin/env python3
"""Prepare the Apple Developer Portal packet needed for signed iOS IPA setup."""

from __future__ import annotations

import argparse
import json
import shutil
import stat
import sys
from collections.abc import Mapping, Sequence
from datetime import datetime, timezone
from pathlib import Path
from typing import Any


SCHEMA = "x0tta6bl4.ios_apple_portal_packet.v1"
DEFAULT_SIGNING_DIR = Path.home() / ".local/share/x0tta6bl4/ios-signing"
DEFAULT_CSR = DEFAULT_SIGNING_DIR / "apple-distribution.csr"
DEFAULT_PRIVATE_KEY = DEFAULT_SIGNING_DIR / "apple-distribution.key"
DEFAULT_CERTIFICATE_CER = DEFAULT_SIGNING_DIR / "apple-distribution.cer"
DEFAULT_PROFILE = DEFAULT_SIGNING_DIR / "x0tta6bl4.mobileprovision"
DEFAULT_PACKET_DIR = ".tmp/native-signing/ios/apple-portal-packet"
DEFAULT_BUNDLE_ID = "net.x0tta6bl4.mesh"
DEFAULT_PROFILE_NAME = "x0tta6bl4 Ad Hoc"
DEFAULT_EXPORT_METHOD = "ad-hoc"


def _utc_now() -> str:
    return datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")


def _mode(path: Path) -> str | None:
    if not path.exists():
        return None
    return oct(stat.S_IMODE(path.stat().st_mode))


def _owner_only(path: Path) -> bool:
    return _mode(path) == "0o600"


def _missing_inputs(args: argparse.Namespace) -> list[str]:
    missing: list[str] = []
    csr = Path(args.csr).expanduser()
    private_key = Path(args.private_key).expanduser()
    if not csr.is_file():
        missing.append("csr_file")
    if not private_key.is_file():
        missing.append("private_key_file")
    elif not _owner_only(private_key):
        missing.append("private_key_mode_owner_only")
    return missing


def _after_download_commands(args: argparse.Namespace) -> list[str]:
    return [
        f"install -m 0644 /path/from/apple/apple-distribution.cer {args.expected_certificate_cer}",
        f"install -m 0644 /path/from/apple/x0tta6bl4.mobileprovision {args.expected_provisioning_profile}",
        "read -rsp 'iOS .p12 password: ' X0T_IOS_CERTIFICATE_PASSWORD; echo",
        "export X0T_IOS_CERTIFICATE_PASSWORD",
        "read -rp 'Apple Team ID: ' X0T_IOS_TEAM_ID",
        "export X0T_IOS_TEAM_ID",
        "python3 scripts/ops/run_ios_signed_release_setup.py --prepare --set-github-secrets --trigger-workflow --require-complete-release --json",
        "python3 scripts/ops/run_native_release_closeout.py --use-latest-run --wait --download-audit --check-github-secrets --require-complete --json",
    ]


def _portal_steps(args: argparse.Namespace) -> list[str]:
    return [
        "Open Apple Developer Portal with the Apple Developer team that owns the target app.",
        f"Create or confirm the App ID / Bundle ID: {args.bundle_id}.",
        "Create an Apple Distribution certificate by uploading apple-distribution.csr from this packet.",
        f"Download the certificate as apple-distribution.cer and save it to {args.expected_certificate_cer}.",
        f"Create a provisioning profile named '{args.profile_name}' for bundle id {args.bundle_id}.",
        "Select the Apple Distribution certificate created from this CSR when building the provisioning profile.",
        f"Download the provisioning profile and save it to {args.expected_provisioning_profile}.",
        "Return to the repository and run the after_download_commands from ios-apple-portal-packet.json.",
    ]


def build_plan(args: argparse.Namespace) -> dict[str, Any]:
    csr = Path(args.csr).expanduser()
    private_key = Path(args.private_key).expanduser()
    packet_dir = Path(args.packet_dir)
    missing = _missing_inputs(args)
    private_key_mode = _mode(private_key)
    return {
        "schema": SCHEMA,
        "generated_at_utc": _utc_now(),
        "status": "PLAN",
        "packet_dir": str(packet_dir),
        "csr_path": str(csr),
        "csr_present": csr.is_file(),
        "csr_size_bytes": csr.stat().st_size if csr.is_file() else None,
        "private_key_path": str(private_key),
        "private_key_present": private_key.is_file(),
        "private_key_mode": private_key_mode,
        "private_key_mode_owner_only": private_key_mode == "0o600",
        "bundle_id": args.bundle_id,
        "profile_name": args.profile_name,
        "export_method": args.export_method,
        "expected_certificate_cer": args.expected_certificate_cer,
        "expected_provisioning_profile": args.expected_provisioning_profile,
        "will_write_packet": args.write_packet,
        "missing_inputs": missing,
        "portal_steps": _portal_steps(args),
        "after_download_commands": _after_download_commands(args),
        "claim_boundary": {
            "apple_certificate_created": False,
            "provisioning_profile_created": False,
            "p12_exported": False,
            "github_ios_secrets_ready": False,
            "private_key_copied_to_packet": False,
            "private_key_printed": False,
            "private_values_redacted": True,
            "signed_ipa_created": False,
        },
    }


def _readme(report: Mapping[str, Any]) -> str:
    commands = "\n".join(report["after_download_commands"])
    steps = "\n".join(f"{index}. {step}" for index, step in enumerate(report["portal_steps"], 1))
    return f"""# x0tta6bl4 iOS Apple Developer Portal Packet

This packet is for creating the real Apple signing material required for a signed iOS IPA.

## Claim Boundary

- This packet does not create an Apple certificate.
- This packet does not create a provisioning profile.
- This packet does not include or print the private key.
- Completion is proven only after `run_native_release_closeout.py` reports `COMPLETE`.

## Apple Portal Steps

{steps}

## Expected Local Downloads

- Apple certificate: `{report["expected_certificate_cer"]}`
- Provisioning profile: `{report["expected_provisioning_profile"]}`

## Commands After Download

```bash
{commands}
```
"""


def _write_packet(args: argparse.Namespace, report: dict[str, Any]) -> None:
    packet_dir = Path(args.packet_dir)
    packet_dir.mkdir(parents=True, exist_ok=True)
    csr = Path(args.csr).expanduser()
    shutil.copyfile(csr, packet_dir / "apple-distribution.csr")
    (packet_dir / "README.md").write_text(_readme(report), encoding="utf-8")
    (packet_dir / "ios-apple-portal-packet.json").write_text(
        json.dumps(report, indent=2, sort_keys=True) + "\n",
        encoding="utf-8",
    )


def run(args: argparse.Namespace) -> dict[str, Any]:
    report = build_plan(args)
    if report["missing_inputs"]:
        if args.write_packet:
            report["status"] = "FAILED"
            report["error"] = "missing_required_inputs"
        return report

    if not args.write_packet:
        return report

    _write_packet(args, report)
    packet_dir = Path(args.packet_dir)
    report["status"] = "READY"
    report["packet_files"] = sorted(path.name for path in packet_dir.iterdir() if path.is_file())
    report["packet_manifest"] = str(packet_dir / "ios-apple-portal-packet.json")
    report["packet_readme"] = str(packet_dir / "README.md")
    report["packet_csr"] = str(packet_dir / "apple-distribution.csr")
    return report


def parse_args(argv: Sequence[str] | None = None) -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description="Prepare the safe Apple Developer Portal packet for iOS signing.",
    )
    parser.add_argument("--csr", default=str(DEFAULT_CSR))
    parser.add_argument("--private-key", default=str(DEFAULT_PRIVATE_KEY))
    parser.add_argument("--packet-dir", default=DEFAULT_PACKET_DIR)
    parser.add_argument("--bundle-id", default=DEFAULT_BUNDLE_ID)
    parser.add_argument("--profile-name", default=DEFAULT_PROFILE_NAME)
    parser.add_argument("--export-method", default=DEFAULT_EXPORT_METHOD)
    parser.add_argument("--expected-certificate-cer", default=str(DEFAULT_CERTIFICATE_CER))
    parser.add_argument("--expected-provisioning-profile", default=str(DEFAULT_PROFILE))
    parser.add_argument("--write-packet", action="store_true")
    parser.add_argument("--require-ready", action="store_true")
    parser.add_argument("--output-json")
    parser.add_argument("--json", action="store_true")
    return parser.parse_args(argv)


def _write_output(report: Mapping[str, Any], output: str | None) -> None:
    if not output:
        return
    path = Path(output)
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(report, indent=2, sort_keys=True) + "\n", encoding="utf-8")


def _print_text(report: Mapping[str, Any]) -> None:
    print(f"iOS Apple portal packet: {report['status']}")
    print(f"Packet dir: {report['packet_dir']}")
    if report.get("missing_inputs"):
        print("Missing inputs: " + ", ".join(report["missing_inputs"]))
    if report.get("error"):
        print(f"Error: {report['error']}")
    print("Private key contents are not copied or printed.")


def main(argv: Sequence[str] | None = None) -> int:
    args = parse_args(argv)
    report = run(args)
    _write_output(report, args.output_json)
    if args.json:
        print(json.dumps(report, indent=2, sort_keys=True))
    else:
        _print_text(report)

    if report["status"] == "FAILED":
        return 1
    if args.require_ready and report["status"] != "READY":
        return 2
    return 0


if __name__ == "__main__":
    raise SystemExit(main(sys.argv[1:]))
