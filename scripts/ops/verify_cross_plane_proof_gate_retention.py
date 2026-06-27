#!/usr/bin/env python3
"""Validate the retained cross-plane proof-gate report.

This command is read-only. It checks that the locally retained proof-gate JSON
exists, contains the retention manifest, and still matches the current source
artifact hashes. Passing this validator does not prove production readiness,
live traffic, DPI bypass, or settlement finality.
"""

from __future__ import annotations

import argparse
import hashlib
import json
import sys
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Mapping, Sequence


ROOT = Path(__file__).resolve().parents[2]
SCHEMA = "x0tta6bl4.cross_plane_proof_gate.retention_validator.v1"
PROOF_GATE_SCHEMA = "x0tta6bl4.cross_plane_proof_gate.v1"
RETENTION_SCHEMA = "x0tta6bl4.cross_plane_proof_gate.retention.v1"
DEFAULT_ARTIFACT = Path(".tmp/validation-shards/cross-plane-proof-gate-current.json")
DECISION_VALID = "CROSS_PLANE_PROOF_GATE_RETENTION_VALID"
DECISION_INVALID = "CROSS_PLANE_PROOF_GATE_RETENTION_INVALID"
DEFAULT_MAX_AGE_HOURS = 168
FUTURE_SKEW_TOLERANCE_SECONDS = 300


def utc_now() -> str:
    return datetime.now(timezone.utc).replace(microsecond=0).isoformat().replace(
        "+00:00", "Z"
    )


def parse_args(argv: Sequence[str] | None = None) -> argparse.Namespace:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--root", type=Path, default=ROOT)
    parser.add_argument("--artifact", type=Path, default=DEFAULT_ARTIFACT)
    parser.add_argument("--require-valid", action="store_true")
    parser.add_argument(
        "--max-age-hours",
        type=float,
        default=DEFAULT_MAX_AGE_HOURS,
        help=(
            "Maximum allowed age for the retained proof-gate report timestamp; "
            "default is 168 hours."
        ),
    )
    parser.add_argument("--json", action="store_true")
    return parser.parse_args(argv)


def resolve_path(root: Path, value: str | Path) -> Path:
    path = Path(value)
    return path if path.is_absolute() else root / path


def display_path(root: Path, path: Path) -> str:
    try:
        return path.relative_to(root).as_posix()
    except ValueError:
        return path.as_posix()


def load_json(path: Path) -> dict[str, Any]:
    with path.open("r", encoding="utf-8") as handle:
        payload = json.load(handle)
    if not isinstance(payload, dict):
        raise ValueError("JSON root must be an object")
    return payload


def sha256_file(path: Path) -> str | None:
    if not path.exists() or not path.is_file() or path.is_symlink():
        return None
    digest = hashlib.sha256()
    with path.open("rb") as handle:
        for chunk in iter(lambda: handle.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()


def is_sha256(value: Any) -> bool:
    return (
        isinstance(value, str)
        and len(value) == 64
        and all(ch in "0123456789abcdef" for ch in value)
    )


def parse_utc_datetime(value: Any) -> datetime | None:
    if not isinstance(value, str) or not value.strip():
        return None
    text = value.strip()
    if text.endswith("Z"):
        text = f"{text[:-1]}+00:00"
    try:
        parsed = datetime.fromisoformat(text)
    except ValueError:
        return None
    if parsed.tzinfo is None:
        return None
    return parsed.astimezone(timezone.utc)


def freshness_errors(
    payload: Mapping[str, Any],
    *,
    now_utc: datetime | None = None,
    max_age_hours: float | None = DEFAULT_MAX_AGE_HOURS,
) -> tuple[list[str], int | None]:
    now = (now_utc or datetime.now(timezone.utc)).astimezone(timezone.utc)
    parsed = parse_utc_datetime(payload.get("timestamp_utc"))
    if parsed is None:
        return ["timestamp_utc_missing_or_invalid"], None
    age_seconds = int((now - parsed).total_seconds())
    if age_seconds < -FUTURE_SKEW_TOLERANCE_SECONDS:
        return ["timestamp_utc_too_far_in_future"], age_seconds
    if max_age_hours is not None:
        if max_age_hours <= 0:
            return ["max_age_hours_invalid"], age_seconds
        if age_seconds > int(max_age_hours * 3600):
            return ["retained_proof_gate_artifact_stale"], age_seconds
    return [], age_seconds


def _source_items(value: Any) -> list[Mapping[str, Any]]:
    if not isinstance(value, list):
        return []
    return [item for item in value if isinstance(item, Mapping)]


def source_artifact_failures(root: Path, source_artifacts: Sequence[Mapping[str, Any]]) -> list[str]:
    failures: list[str] = []
    if not source_artifacts:
        return ["source_artifacts_missing"]
    for index, artifact in enumerate(source_artifacts):
        role = str(artifact.get("role") or f"source_artifact_{index}")
        path_text = artifact.get("path")
        expected_sha = artifact.get("sha256")
        if not isinstance(path_text, str) or not path_text:
            failures.append(f"{role}:path_missing")
            continue
        if not is_sha256(expected_sha):
            failures.append(f"{role}:sha256_missing_or_invalid")
            continue
        path = resolve_path(root, path_text)
        if not path.exists():
            failures.append(f"{role}:source_artifact_missing")
            continue
        if not path.is_file():
            failures.append(f"{role}:source_artifact_not_file")
            continue
        if path.is_symlink():
            failures.append(f"{role}:source_artifact_is_symlink")
            continue
        actual_sha = sha256_file(path)
        if actual_sha != expected_sha:
            failures.append(f"{role}:source_artifact_sha256_mismatch")
    return failures


def build_report(
    root: Path,
    artifact: Path = DEFAULT_ARTIFACT,
    *,
    max_age_hours: float | None = DEFAULT_MAX_AGE_HOURS,
) -> dict[str, Any]:
    root = root.resolve()
    artifact_path = resolve_path(root, artifact)
    failures: list[str] = []
    payload: dict[str, Any] = {}

    if not artifact_path.exists():
        failures.append("retained_artifact_missing")
    elif not artifact_path.is_file():
        failures.append("retained_artifact_not_file")
    elif artifact_path.is_symlink():
        failures.append("retained_artifact_is_symlink")
    else:
        try:
            payload = load_json(artifact_path)
        except Exception as exc:
            failures.append(f"retained_artifact_json_invalid:{exc}")

    context = payload.get("context") if isinstance(payload.get("context"), Mapping) else {}
    retention = (
        payload.get("retention_manifest")
        if isinstance(payload.get("retention_manifest"), Mapping)
        else {}
    )
    freshness_failure_ids, age_seconds = freshness_errors(
        payload,
        max_age_hours=max_age_hours,
    )
    failures.extend(freshness_failure_ids)

    if payload.get("schema") != PROOF_GATE_SCHEMA:
        failures.append("proof_gate_schema_invalid")
    if not isinstance(context, Mapping):
        failures.append("context_missing")
    elif context.get("source_artifact_hashes_present") is not True:
        failures.append("context_source_artifact_hashes_missing")
    if not isinstance(retention, Mapping) or not retention:
        failures.append("retention_manifest_missing")
    else:
        if retention.get("schema") != RETENTION_SCHEMA:
            failures.append("retention_manifest_schema_invalid")
        if retention.get("retention_required") is not True:
            failures.append("retention_required_not_true")
        if retention.get("source_artifact_hashes_present") is not True:
            failures.append("retention_source_artifact_hashes_missing")
        if retention.get("mutates_runtime") is not False:
            failures.append("retention_mutates_runtime_not_false")
        if retention.get("collects_live_evidence") is not False:
            failures.append("retention_collects_live_evidence_not_false")
        expected_retained_path = display_path(root, artifact_path)
        if retention.get("retained_artifact_path") != expected_retained_path:
            failures.append("retained_artifact_path_mismatch")
        if retention.get("canonical_artifact_path") != DEFAULT_ARTIFACT.as_posix():
            failures.append("canonical_artifact_path_mismatch")

    retention_sources = _source_items(retention.get("source_artifacts"))
    context_sources = _source_items(context.get("source_artifacts"))
    source_failures = source_artifact_failures(root, retention_sources)
    failures.extend(source_failures)

    retention_roles = {str(item.get("role") or "") for item in retention_sources}
    context_roles = {str(item.get("role") or "") for item in context_sources}
    if retention_roles and context_roles and retention_roles != context_roles:
        failures.append("retention_context_source_artifact_roles_mismatch")

    artifact_sha = sha256_file(artifact_path)
    valid = not failures
    return {
        "schema": SCHEMA,
        "timestamp_utc": utc_now(),
        "artifact_path": display_path(root, artifact_path),
        "artifact_sha256": artifact_sha,
        "artifact_sha256_present": bool(artifact_sha),
        "proof_gate_schema": payload.get("schema"),
        "retention_schema": retention.get("schema") if isinstance(retention, Mapping) else None,
        "retained_artifact_age_seconds": age_seconds,
        "max_age_hours": max_age_hours,
        "source_artifact_count": len(retention_sources),
        "source_artifact_hashes_verified": not source_failures,
        "valid": valid,
        "decision": DECISION_VALID if valid else DECISION_INVALID,
        "failures": failures,
        "claim_boundary": (
            "This validator only proves the local proof-gate report was retained "
            "and its source artifact hashes still match current local files. It "
            "does not prove production readiness, live traffic, DPI bypass, or "
            "settlement finality."
        ),
    }


def main(argv: Sequence[str] | None = None) -> int:
    args = parse_args(argv)
    report = build_report(
        args.root,
        args.artifact,
        max_age_hours=args.max_age_hours,
    )
    if args.json:
        print(json.dumps(report, ensure_ascii=False, indent=2, sort_keys=True))
    else:
        print(report["decision"])
        for failure in report["failures"]:
            print(f"- {failure}")
    return 0 if (report["valid"] is True or not args.require_valid) else 1


if __name__ == "__main__":
    raise SystemExit(main(sys.argv[1:]))
