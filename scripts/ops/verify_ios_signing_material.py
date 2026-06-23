#!/usr/bin/env python3
"""Verify local iOS signing files before uploading GitHub secrets."""

from __future__ import annotations

import argparse
import base64
import hashlib
import json
import os
import plistlib
import shutil
import subprocess
import sys
import tempfile
from collections.abc import Callable, Mapping, Sequence
from datetime import datetime, timezone
from pathlib import Path
from typing import Any


SCHEMA = "x0tta6bl4.ios_signing_material_verification.v1"
DEFAULT_BUNDLE_ID = "net.x0tta6bl4.mesh"


def _utc_now() -> str:
    return datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")


def _run(
    args: Sequence[str],
    *,
    input_bytes: bytes | None = None,
    runner: Callable[..., subprocess.CompletedProcess[bytes]] = subprocess.run,
) -> subprocess.CompletedProcess[bytes]:
    return runner(
        list(args),
        input=input_bytes,
        capture_output=True,
        check=False,
    )


def _check(check_id: str, ok: bool, details: str) -> dict[str, Any]:
    return {"check_id": check_id, "details": details, "ok": ok}


def _looks_like_plist(data: bytes) -> bool:
    stripped = data.lstrip()
    return stripped.startswith(b"<?xml") or stripped.startswith(b"<plist") or data.startswith(
        b"bplist00"
    )


def _normalise_fingerprint(data: bytes) -> str:
    digest = hashlib.sha1(data).hexdigest().upper()
    return ":".join(digest[index : index + 2] for index in range(0, len(digest), 2))


def _pem_certificates_to_der(pem_bytes: bytes) -> list[bytes]:
    certs: list[bytes] = []
    marker_begin = b"-----BEGIN CERTIFICATE-----"
    marker_end = b"-----END CERTIFICATE-----"
    remaining = pem_bytes
    while marker_begin in remaining:
        _, after_begin = remaining.split(marker_begin, 1)
        body, remaining = after_begin.split(marker_end, 1)
        b64 = b"".join(body.strip().splitlines())
        certs.append(base64.b64decode(b64))
    return certs


def _decode_mobileprovision(
    profile: Path,
    *,
    allow_unsigned_plist: bool,
    runner: Callable[..., subprocess.CompletedProcess[bytes]] = subprocess.run,
) -> tuple[dict[str, Any] | None, str | None, bool]:
    data = profile.read_bytes()
    if _looks_like_plist(data):
        if not allow_unsigned_plist:
            return None, "unsigned_plist_not_allowed", True
        return plistlib.loads(data), None, True

    openssl = shutil.which("openssl")
    if not openssl:
        return None, "openssl_missing", False

    with tempfile.TemporaryDirectory(prefix="x0t-ios-profile-") as tmp:
        output = Path(tmp) / "profile.plist"
        commands = [
            [
                openssl,
                "cms",
                "-verify",
                "-inform",
                "DER",
                "-noverify",
                "-in",
                str(profile),
                "-out",
                str(output),
            ],
            [
                openssl,
                "smime",
                "-verify",
                "-inform",
                "DER",
                "-noverify",
                "-in",
                str(profile),
                "-out",
                str(output),
            ],
        ]
        for command in commands:
            result = _run(command, runner=runner)
            if result.returncode == 0 and output.exists():
                return plistlib.loads(output.read_bytes()), None, False
    return None, "mobileprovision_decode_failed", False


def _extract_p12_certificate_fingerprints(
    p12: Path,
    *,
    password: str,
    runner: Callable[..., subprocess.CompletedProcess[bytes]] = subprocess.run,
) -> tuple[list[str], str | None]:
    openssl = shutil.which("openssl")
    if not openssl:
        return [], "openssl_missing"

    result = _run(
        [
            openssl,
            "pkcs12",
            "-in",
            str(p12),
            "-clcerts",
            "-nokeys",
            "-passin",
            "stdin",
        ],
        input_bytes=(password + "\n").encode("utf-8"),
        runner=runner,
    )
    if result.returncode != 0:
        return [], "p12_decode_failed"

    der_certs = _pem_certificates_to_der(result.stdout)
    if not der_certs:
        return [], "p12_certificate_missing"
    return [_normalise_fingerprint(cert) for cert in der_certs], None


def _profile_certificate_fingerprints(profile_data: Mapping[str, Any]) -> list[str]:
    certificates = profile_data.get("DeveloperCertificates") or []
    fingerprints = []
    for cert in certificates:
        if isinstance(cert, bytes):
            fingerprints.append(_normalise_fingerprint(cert))
    return fingerprints


def _profile_expiration(profile_data: Mapping[str, Any]) -> datetime | None:
    expiration = profile_data.get("ExpirationDate")
    if not isinstance(expiration, datetime):
        return None
    if expiration.tzinfo is None:
        expiration = expiration.replace(tzinfo=timezone.utc)
    return expiration


def _profile_summary(profile_data: Mapping[str, Any]) -> dict[str, Any]:
    entitlements = profile_data.get("Entitlements") or {}
    expiration = _profile_expiration(profile_data)
    return {
        "name": profile_data.get("Name"),
        "uuid": profile_data.get("UUID"),
        "team_identifier": profile_data.get("TeamIdentifier"),
        "application_identifier": entitlements.get("application-identifier"),
        "entitlement_team_identifier": entitlements.get(
            "com.apple.developer.team-identifier"
        ),
        "get_task_allow": entitlements.get("get-task-allow"),
        "expiration_date_utc": expiration.strftime("%Y-%m-%dT%H:%M:%SZ")
        if expiration
        else None,
        "developer_certificate_count": len(profile_data.get("DeveloperCertificates") or []),
    }


def build_plan(args: argparse.Namespace) -> dict[str, Any]:
    return {
        "schema": SCHEMA,
        "generated_at_utc": _utc_now(),
        "status": "PLAN",
        "certificate_p12_path": args.certificate_p12,
        "provisioning_profile_path": args.provisioning_profile,
        "team_id_present": bool(args.team_id),
        "bundle_id": args.bundle_id,
        "will_verify": args.verify,
        "claim_boundary": {
            "ios_signing_material_verified": False,
            "p12_private_key_exported": False,
            "p12_password_printed": False,
            "provisioning_profile_validated_by_xcode": False,
            "app_store_notarization_validated": False,
            "private_values_redacted": True,
            "unsigned_plist_allowed": args.allow_unsigned_plist,
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


def _validate_profile(
    *,
    profile_data: Mapping[str, Any],
    p12_fingerprints: Sequence[str],
    team_id: str,
    bundle_id: str,
    allow_wildcard_app_id: bool,
    allow_development_profile: bool,
) -> list[dict[str, Any]]:
    checks: list[dict[str, Any]] = []
    entitlements = profile_data.get("Entitlements") or {}
    profile_teams = profile_data.get("TeamIdentifier") or []
    application_identifier = entitlements.get("application-identifier")
    entitlement_team_id = entitlements.get("com.apple.developer.team-identifier")
    get_task_allow = entitlements.get("get-task-allow")
    expected_app_id = f"{team_id}.{bundle_id}"
    wildcard_app_id = f"{team_id}.*"
    expiration = _profile_expiration(profile_data)
    now = datetime.now(timezone.utc)
    profile_fingerprints = _profile_certificate_fingerprints(profile_data)

    checks.append(
        _check(
            "profile_team_identifier_matches",
            team_id in profile_teams,
            "expected team id is listed in TeamIdentifier",
        )
    )
    checks.append(
        _check(
            "profile_entitlement_team_matches",
            entitlement_team_id == team_id,
            "expected team id matches com.apple.developer.team-identifier",
        )
    )
    app_id_ok = application_identifier == expected_app_id
    if allow_wildcard_app_id:
        app_id_ok = app_id_ok or application_identifier == wildcard_app_id
    checks.append(
        _check(
            "profile_bundle_id_matches",
            app_id_ok,
            f"expected application-identifier {expected_app_id}",
        )
    )
    checks.append(
        _check(
            "profile_not_expired",
            bool(expiration and expiration > now),
            "ExpirationDate must be in the future",
        )
    )
    checks.append(
        _check(
            "profile_distribution_mode",
            allow_development_profile or get_task_allow is False,
            "get-task-allow must be false for release/ad-hoc IPA signing",
        )
    )
    checks.append(
        _check(
            "profile_has_developer_certificate",
            bool(profile_fingerprints),
            "DeveloperCertificates must contain at least one certificate",
        )
    )
    checks.append(
        _check(
            "p12_certificate_in_profile",
            bool(set(p12_fingerprints).intersection(profile_fingerprints)),
            "the .p12 signing certificate must be included in DeveloperCertificates",
        )
    )
    return checks


def run(
    args: argparse.Namespace,
    *,
    runner: Callable[..., subprocess.CompletedProcess[bytes]] = subprocess.run,
) -> dict[str, Any]:
    report = build_plan(args)
    missing = _missing_inputs(args)
    if missing:
        if args.verify:
            report["status"] = "FAILED"
            report["error"] = "missing_required_inputs"
            report["missing_inputs"] = missing
        return report

    if not args.verify:
        return report

    p12 = Path(args.certificate_p12).expanduser()
    profile = Path(args.provisioning_profile).expanduser()
    p12_fingerprints, p12_error = _extract_p12_certificate_fingerprints(
        p12,
        password=args.certificate_password,
        runner=runner,
    )
    if p12_error:
        report["status"] = "FAILED"
        report["error"] = p12_error
        return report

    profile_data, profile_error, unsigned_plist = _decode_mobileprovision(
        profile,
        allow_unsigned_plist=args.allow_unsigned_plist,
        runner=runner,
    )
    if profile_error:
        report["status"] = "FAILED"
        report["error"] = profile_error
        return report
    assert profile_data is not None

    checks = _validate_profile(
        profile_data=profile_data,
        p12_fingerprints=p12_fingerprints,
        team_id=args.team_id,
        bundle_id=args.bundle_id,
        allow_wildcard_app_id=args.allow_wildcard_app_id,
        allow_development_profile=args.allow_development_profile,
    )
    report["profile_summary"] = _profile_summary(profile_data)
    report["certificate_p12_size_bytes"] = p12.stat().st_size
    report["provisioning_profile_size_bytes"] = profile.stat().st_size
    report["p12_certificate_fingerprints_sha1"] = p12_fingerprints
    report["profile_certificate_fingerprints_sha1"] = _profile_certificate_fingerprints(
        profile_data
    )
    report["profile_payload_was_unsigned_plist"] = unsigned_plist
    report["checks"] = checks
    valid = all(check["ok"] for check in checks)
    report["status"] = "VALID" if valid else "INVALID"
    report["claim_boundary"]["ios_signing_material_verified"] = valid
    return report


def parse_args(argv: Sequence[str] | None = None) -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description="Verify iOS .p12 and provisioning profile compatibility.",
    )
    parser.add_argument("--certificate-p12")
    parser.add_argument(
        "--certificate-password",
        default=os.environ.get("X0T_IOS_CERTIFICATE_PASSWORD"),
    )
    parser.add_argument("--provisioning-profile")
    parser.add_argument("--team-id")
    parser.add_argument("--bundle-id", default=DEFAULT_BUNDLE_ID)
    parser.add_argument("--verify", action="store_true")
    parser.add_argument("--require-valid", action="store_true")
    parser.add_argument("--allow-wildcard-app-id", action="store_true")
    parser.add_argument("--allow-development-profile", action="store_true")
    parser.add_argument(
        "--allow-unsigned-plist",
        action="store_true",
        help="test-only mode for raw plist fixtures; real .mobileprovision files are CMS signed",
    )
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
    print(f"iOS signing material verification: {report['status']}")
    if report.get("error"):
        print(f"Error: {report['error']}")
    for check in report.get("checks", []):
        marker = "ok" if check["ok"] else "fail"
        print(f"- {marker}: {check['check_id']} ({check['details']})")
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
    if args.require_valid and report["status"] != "VALID":
        return 2
    return 0


if __name__ == "__main__":
    raise SystemExit(main(sys.argv[1:]))
