#!/usr/bin/env python3
"""Verify downloaded native app build artifacts and release completeness."""

from __future__ import annotations

import argparse
import hashlib
import json
import sys
from collections.abc import Iterable, Mapping, Sequence
from datetime import datetime, timezone
from pathlib import Path
from typing import Any


SCHEMA = "x0tta6bl4.native_release_artifact_audit.v1"
MANIFEST_SCHEMA = "x0tta6bl4.native_build_manifest.v1"

DEFAULT_ARTIFACT_ROOT = ".tmp/native-release-artifacts"
DEFAULT_OUTPUT = ".tmp/native-release-audit/native-release-artifact-audit.json"

REQUIRED_KINDS: dict[str, set[str]] = {
    "android": {"debug_apk", "release_apk", "release_aab"},
    "ios": {"simulator_app_file", "unsigned_device_app_file", "signed_ipa"},
    "windows": {"msi"},
    "ubuntu": {"deb", "appimage"},
}

MANIFEST_DIRS: dict[str, str] = {
    "android": "x0tta6bl4-android-manifest",
    "ios": "x0tta6bl4-ios-manifest",
    "windows": "x0tta6bl4-windows-manifest",
    "ubuntu": "x0tta6bl4-ubuntu-manifest",
}

ARTIFACT_DIRS: dict[str, tuple[str, ...]] = {
    "android": ("x0tta6bl4-android-apks", "x0tta6bl4-android-release-aab"),
    "ios": (
        "x0tta6bl4-ios-simulator-app",
        "x0tta6bl4-ios-device-unsigned-app",
        "x0tta6bl4-ios-signed-ipa",
    ),
    "windows": ("x0tta6bl4-windows-msi",),
    "ubuntu": ("x0tta6bl4-ubuntu-desktop",),
}


def _utc_now() -> str:
    return datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")


def _sha256_file(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as handle:
        for chunk in iter(lambda: handle.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()


def _load_json(path: Path) -> dict[str, Any]:
    try:
        payload = json.loads(path.read_text(encoding="utf-8"))
    except FileNotFoundError:
        raise
    except json.JSONDecodeError as exc:
        raise ValueError(f"{path} is not valid JSON: {exc}") from exc
    if not isinstance(payload, dict):
        raise ValueError(f"{path} must contain a JSON object")
    return payload


def _artifact_files(root: Path, platform: str) -> list[Path]:
    files: list[Path] = []
    for dirname in ARTIFACT_DIRS[platform]:
        artifact_dir = root / dirname
        if artifact_dir.exists():
            files.extend(path for path in artifact_dir.rglob("*") if path.is_file())
    return files


def _candidate_paths(root: Path, platform: str, manifest_path: str) -> list[Path]:
    source = Path(manifest_path)
    basename = source.name

    if platform == "ios":
        text = source.as_posix()
        if "Debug-iphonesimulator/App.app/" in text:
            relative = text.split("Debug-iphonesimulator/App.app/", 1)[1]
            return [root / "x0tta6bl4-ios-simulator-app" / relative]
        if "Release-iphoneos/App.app/" in text:
            relative = text.split("Release-iphoneos/App.app/", 1)[1]
            return [root / "x0tta6bl4-ios-device-unsigned-app" / relative]
        if "/build/ipa/" in text:
            return [root / "x0tta6bl4-ios-signed-ipa" / basename]

    return [path for path in _artifact_files(root, platform) if path.name == basename]


def _verify_artifact_hashes(
    *,
    root: Path,
    platform: str,
    artifacts: Sequence[Mapping[str, Any]],
) -> tuple[list[dict[str, Any]], list[str]]:
    checks: list[dict[str, Any]] = []
    failures: list[str] = []

    for artifact in artifacts:
        manifest_path = str(artifact.get("path", ""))
        expected_sha256 = str(artifact.get("sha256", ""))
        candidates = _candidate_paths(root, platform, manifest_path)
        existing = [candidate for candidate in candidates if candidate.exists()]

        if not existing:
            checks.append(
                {
                    "manifest_path": manifest_path,
                    "found": False,
                    "sha256_match": False,
                }
            )
            failures.append(f"{platform}:artifact_missing:{manifest_path}")
            continue

        actual_path = existing[0]
        actual_sha256 = _sha256_file(actual_path)
        sha256_match = actual_sha256 == expected_sha256
        checks.append(
            {
                "manifest_path": manifest_path,
                "downloaded_path": actual_path.relative_to(root).as_posix(),
                "found": True,
                "sha256_match": sha256_match,
                "size_bytes": actual_path.stat().st_size,
            }
        )
        if not sha256_match:
            failures.append(f"{platform}:sha256_mismatch:{manifest_path}")

    return checks, failures


def _platform_report(root: Path, platform: str) -> dict[str, Any]:
    manifest_path = root / MANIFEST_DIRS[platform] / "native-build-manifest.json"
    if not manifest_path.exists():
        return {
            "platform": platform,
            "manifest_present": False,
            "complete": False,
            "failures": [f"{platform}:manifest_missing"],
        }

    manifest = _load_json(manifest_path)
    artifacts = manifest.get("artifacts", [])
    if not isinstance(artifacts, list):
        artifacts = []

    artifact_kinds = {
        str(item.get("kind"))
        for item in artifacts
        if isinstance(item, Mapping) and item.get("kind")
    }
    required_kinds = REQUIRED_KINDS[platform]
    missing_kinds = sorted(required_kinds - artifact_kinds)

    failures: list[str] = []
    if manifest.get("schema") != MANIFEST_SCHEMA:
        failures.append(f"{platform}:manifest_schema_invalid")
    if manifest.get("platform") != platform:
        failures.append(f"{platform}:manifest_platform_mismatch")
    failures.extend(f"{platform}:artifact_kind_missing:{kind}" for kind in missing_kinds)

    signing = manifest.get("signing") if isinstance(manifest.get("signing"), dict) else {}
    if platform == "android" and signing.get("signed_release_present") is not True:
        failures.append("android:signed_release_missing")
    if platform == "ios" and signing.get("signed_ipa_present") is not True:
        failures.append("ios:signed_ipa_missing")

    hash_checks, hash_failures = _verify_artifact_hashes(
        root=root,
        platform=platform,
        artifacts=[item for item in artifacts if isinstance(item, Mapping)],
    )
    failures.extend(hash_failures)

    return {
        "platform": platform,
        "manifest_present": True,
        "manifest_path": manifest_path.relative_to(root).as_posix(),
        "manifest_schema": manifest.get("schema"),
        "commit": manifest.get("commit"),
        "run_id": manifest.get("run_id"),
        "artifact_count": len(artifacts),
        "artifact_kinds": sorted(artifact_kinds),
        "required_kinds": sorted(required_kinds),
        "missing_kinds": missing_kinds,
        "signing": signing,
        "hash_checks_total": len(hash_checks),
        "hash_checks_failed": len(hash_failures),
        "hash_checks": hash_checks,
        "complete": not failures,
        "failures": failures,
    }


def build_report(
    *,
    artifact_root: Path,
    platforms: Iterable[str] = REQUIRED_KINDS.keys(),
) -> dict[str, Any]:
    root = artifact_root.expanduser()
    platform_reports = {
        platform: _platform_report(root, platform) for platform in platforms
    }
    commits = sorted(
        {
            str(report["commit"])
            for report in platform_reports.values()
            if report.get("commit")
        }
    )
    failures = [
        failure
        for report in platform_reports.values()
        for failure in report.get("failures", [])
    ]
    if len(commits) > 1:
        failures.append("cross_platform_commit_mismatch")

    complete = not failures and all(
        report.get("complete") is True for report in platform_reports.values()
    )
    return {
        "schema": SCHEMA,
        "generated_at_utc": _utc_now(),
        "artifact_root": root.as_posix(),
        "complete": complete,
        "commits": commits,
        "platforms": platform_reports,
        "summary": {
            "platforms_total": len(platform_reports),
            "platforms_complete": sum(
                1 for report in platform_reports.values() if report.get("complete")
            ),
            "failures_total": len(failures),
            "failure_ids": failures,
        },
        "claim_boundary": {
            "verifies_downloaded_artifacts_against_manifests": True,
            "requires_signed_ios_ipa_for_complete_release": True,
            "does_not_install_or_runtime_launch_apps": True,
            "does_not_validate_app_store_or_notarization": True,
        },
    }


def parse_args(argv: Sequence[str] | None = None) -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description="Verify native app build artifacts and release completeness.",
    )
    parser.add_argument("--artifact-root", default=DEFAULT_ARTIFACT_ROOT)
    parser.add_argument(
        "--platform",
        action="append",
        choices=tuple(REQUIRED_KINDS),
        help="platform to verify; repeatable; defaults to all",
    )
    parser.add_argument("--require-complete", action="store_true")
    parser.add_argument("--output", default=DEFAULT_OUTPUT)
    parser.add_argument("--json", action="store_true")
    return parser.parse_args(argv)


def run(args: argparse.Namespace) -> dict[str, Any]:
    platforms = args.platform or list(REQUIRED_KINDS)
    report = build_report(
        artifact_root=Path(args.artifact_root),
        platforms=platforms,
    )
    output = Path(args.output)
    output.parent.mkdir(parents=True, exist_ok=True)
    output.write_text(json.dumps(report, indent=2, sort_keys=True) + "\n", encoding="utf-8")
    return report


def main(argv: Sequence[str] | None = None) -> int:
    args = parse_args(argv)
    try:
        report = run(args)
    except Exception as exc:
        print(f"native release artifact audit failed: {exc}", file=sys.stderr)
        return 1
    if args.json:
        print(json.dumps(report, indent=2, sort_keys=True))
    if args.require_complete and not report["complete"]:
        return 2
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
