#!/usr/bin/env python3
"""Build final pre-approval evidence for first-party VPN production apply.

This packet does not authorize mutation. It proves that the production endpoint,
dry-run apply packet, private handoff, rollout packet, and post-apply readiness
are mutually bound and still blocked until the explicit approval phrase exists.
It performs only local file/hash/mode checks and never SSHes to NL/SPB.
"""

from __future__ import annotations

import argparse
from datetime import UTC, datetime
import hashlib
import json
import os
from pathlib import Path
from typing import Any


ROOT = Path("/mnt/projects")
DIAGNOSTICS_DIR = ROOT / "nl-diagnostics"
APPROVAL_PHRASE = "APPLY_FIRSTPARTY_VPN_PRODUCTION_ROLLOUT"
DEFAULT_MAX_EVIDENCE_AGE_HOURS = 24


def utc_now() -> str:
    return datetime.now(UTC).replace(microsecond=0).isoformat().replace("+00:00", "Z")


def read_json(path: Path) -> dict[str, Any]:
    try:
        payload = json.loads(path.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError):
        return {}
    return payload if isinstance(payload, dict) else {}


def latest_summary(pattern: str, diagnostics_dir: Path = DIAGNOSTICS_DIR) -> Path | None:
    candidates = sorted(diagnostics_dir.glob(pattern))
    return candidates[-1] if candidates else None


def file_sha256(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def safe_file_sha256(path: Path) -> str:
    try:
        return file_sha256(path)
    except OSError:
        return "missing"


def file_mode(path: Path) -> str:
    try:
        return f"{path.stat().st_mode & 0o777:04o}"
    except OSError:
        return "missing"


def bool_text(value: Any) -> str:
    if isinstance(value, bool):
        return str(value).lower()
    if value is None:
        return "missing"
    return str(value)


def compact(values: list[str], *, limit: int = 8) -> str:
    if not values:
        return "none"
    head = values[:limit]
    if len(values) > limit:
        head.append(f"...+{len(values) - limit}")
    return ", ".join(head)


def parse_utc(value: object) -> datetime | None:
    if not isinstance(value, str) or not value:
        return None
    try:
        return datetime.fromisoformat(value.replace("Z", "+00:00")).astimezone(UTC)
    except ValueError:
        return None


def evidence_is_fresh(
    payload: dict[str, Any],
    *,
    now: datetime,
    max_age_hours: int,
) -> bool:
    generated_at = parse_utc(payload.get("generated_at"))
    if generated_at is None:
        return False
    age_seconds = (now - generated_at).total_seconds()
    return 0 <= age_seconds <= max_age_hours * 3600


def is_under_path(path: Path, root: Path) -> bool:
    try:
        path.resolve().relative_to(root.resolve())
        return True
    except ValueError:
        return False


def endpoint_tuple(payload: dict[str, Any]) -> tuple[Any, Any, Any, Any]:
    return (
        payload.get("host"),
        payload.get("bind_host"),
        payload.get("port"),
        payload.get("transport"),
    )


def approval_blocked(payload: dict[str, Any]) -> bool:
    return (
        payload.get("approval_phrase_required") == APPROVAL_PHRASE
        and payload.get("approval_present") is False
        and payload.get("production_mutation_allowed") is False
    )


def no_mutation(payload: dict[str, Any]) -> bool:
    return (
        payload.get("os_mutation_performed") is False
        and payload.get("no_nl_or_spb_writes_performed") is True
    )


def build_payload(
    *,
    endpoint_summary_path: Path,
    apply_packet_summary_path: Path,
    handoff_summary_path: Path,
    rollout_summary_path: Path,
    preapply_summary_path: Path,
    generated_at: str | None = None,
    max_evidence_age_hours: int = DEFAULT_MAX_EVIDENCE_AGE_HOURS,
) -> dict[str, Any]:
    generated_at = generated_at or utc_now()
    now = parse_utc(generated_at) or datetime.now(UTC)
    endpoint = read_json(endpoint_summary_path)
    apply_packet = read_json(apply_packet_summary_path)
    handoff = read_json(handoff_summary_path)
    rollout = read_json(rollout_summary_path)
    preapply = read_json(preapply_summary_path)

    handoff_dir = Path(str(handoff.get("handoff_dir") or ""))
    handoff_archive = Path(str(handoff.get("handoff_archive") or ""))
    handoff_manifest = Path(str(handoff.get("handoff_manifest") or ""))

    endpoint_fields_match = (
        endpoint_tuple(endpoint) == endpoint_tuple(apply_packet) == endpoint_tuple(handoff)
    )
    handoff_archive_hash = safe_file_sha256(handoff_archive)
    handoff_manifest_hash = safe_file_sha256(handoff_manifest)
    evidence_payloads = {
        "endpoint": endpoint,
        "apply_packet": apply_packet,
        "handoff": handoff,
        "rollout": rollout,
        "preapply": preapply,
    }
    freshness = {
        name: evidence_is_fresh(
            payload,
            now=now,
            max_age_hours=max_evidence_age_hours,
        )
        for name, payload in evidence_payloads.items()
    }
    checks = {
        "endpoint_summary_ok": endpoint.get("ok") is True,
        "apply_packet_ok": apply_packet.get("ok") is True,
        "secure_handoff_ok": handoff.get("ok") is True,
        "rollout_packet_ok": rollout.get("ok") is True,
        "preapply_readiness_ok": preapply.get("ok") is True,
        "endpoint_fields_match_apply_and_handoff": endpoint_fields_match,
        "approval_blocked_apply_packet": approval_blocked(apply_packet),
        "approval_blocked_handoff": approval_blocked(handoff),
        "approval_blocked_rollout": approval_blocked(rollout),
        "approval_blocked_preapply": approval_blocked(preapply),
        "mutation_blocked_all_packets": all(
            no_mutation(payload)
            for payload in (endpoint, apply_packet, handoff, rollout, preapply)
        ),
        "post_apply_validation_required": (
            apply_packet.get("post_apply_validation_required") is True
            and (
                preapply.get("checks")
                if isinstance(preapply.get("checks"), dict)
                else {}
            ).get("source_post_apply_validation_ready")
            is True
        ),
        "secure_material_handoff_required": (
            apply_packet.get("secure_material_handoff_required") is True
            and (
                handoff.get("checks") if isinstance(handoff.get("checks"), dict) else {}
            ).get("apply_packet_requires_secure_handoff")
            is True
        ),
        "handoff_dir_exists": handoff_dir.is_dir(),
        "handoff_archive_exists": handoff_archive.is_file(),
        "handoff_manifest_exists": handoff_manifest.is_file(),
        "handoff_dir_outside_repo": handoff_dir.is_absolute()
        and not is_under_path(handoff_dir, ROOT),
        "handoff_archive_outside_repo": handoff_archive.is_absolute()
        and not is_under_path(handoff_archive, ROOT),
        "handoff_manifest_outside_repo": handoff_manifest.is_absolute()
        and not is_under_path(handoff_manifest, ROOT),
        "handoff_dir_private": file_mode(handoff_dir) == "0700",
        "handoff_archive_private": file_mode(handoff_archive) == "0600",
        "handoff_manifest_private": file_mode(handoff_manifest) == "0600",
        "handoff_archive_hash_matches_summary": handoff_archive_hash
        == handoff.get("archive_sha256"),
        "handoff_manifest_hash_matches_summary": handoff_manifest_hash
        == handoff.get("manifest_sha256"),
        "handoff_summary_secret_free": (
            handoff.get("raw_secret_material_stored_in_evidence") is False
            and handoff.get("repo_material_persisted") is False
            and (
                handoff.get("checks") if isinstance(handoff.get("checks"), dict) else {}
            ).get("manifest_secret_free")
            is True
        ),
        "all_evidence_fresh": all(freshness.values()),
        "manual_approval_still_required": True,
        "os_mutation_not_performed": True,
        "no_nl_or_spb_writes_performed": True,
    }
    failed_checks = sorted(name for name, passed in checks.items() if passed is not True)
    payload = {
        "mode": "firstparty-production-authorization-summary",
        "generated_at": generated_at,
        "ok": not failed_checks,
        "approval_phrase_required": APPROVAL_PHRASE,
        "approval_present": False,
        "production_mutation_allowed": False,
        "manual_approval_still_required": True,
        "os_mutation_performed": False,
        "no_nl_or_spb_writes_performed": True,
        "max_evidence_age_hours": max_evidence_age_hours,
        "endpoint": {
            "host": endpoint.get("host") or "missing",
            "bind_host": endpoint.get("bind_host") or "missing",
            "port": endpoint.get("port") if endpoint.get("port") is not None else "missing",
            "transport": endpoint.get("transport") or "missing",
        },
        "evidence_paths": {
            "endpoint_summary_path": str(endpoint_summary_path),
            "apply_packet_summary_path": str(apply_packet_summary_path),
            "handoff_summary_path": str(handoff_summary_path),
            "rollout_summary_path": str(rollout_summary_path),
            "preapply_summary_path": str(preapply_summary_path),
            "handoff_dir": str(handoff_dir),
            "handoff_archive": str(handoff_archive),
            "handoff_manifest": str(handoff_manifest),
        },
        "evidence_hashes": {
            "endpoint_summary_sha256": safe_file_sha256(endpoint_summary_path),
            "apply_packet_summary_sha256": safe_file_sha256(apply_packet_summary_path),
            "handoff_summary_sha256": safe_file_sha256(handoff_summary_path),
            "rollout_summary_sha256": safe_file_sha256(rollout_summary_path),
            "preapply_summary_sha256": safe_file_sha256(preapply_summary_path),
            "handoff_archive_sha256": handoff_archive_hash,
            "handoff_manifest_sha256": handoff_manifest_hash,
        },
        "evidence_freshness": freshness,
        "handoff_dir_mode": file_mode(handoff_dir),
        "handoff_archive_mode": file_mode(handoff_archive),
        "handoff_manifest_mode": file_mode(handoff_manifest),
        "failed_checks": failed_checks,
        "checks": checks,
    }
    return payload


def render_markdown(payload: dict[str, Any]) -> str:
    endpoint = payload.get("endpoint") if isinstance(payload.get("endpoint"), dict) else {}
    lines = [
        "# First-Party VPN Production Authorization",
        "",
        f"generated_at: `{payload['generated_at']}`",
        f"ok: `{str(payload['ok']).lower()}`",
        f"endpoint: `{endpoint.get('transport')}://{endpoint.get('host')}:{endpoint.get('port')}`",
        f"approval_phrase_required: `{payload['approval_phrase_required']}`",
        f"production_mutation_allowed: `{str(payload['production_mutation_allowed']).lower()}`",
        "",
        "## Checks",
        "",
        "| Check | Passed |",
        "|---|---|",
    ]
    checks = payload.get("checks") if isinstance(payload.get("checks"), dict) else {}
    for name in sorted(checks):
        lines.append(f"| `{name}` | `{bool_text(checks[name])}` |")
    failed = payload.get("failed_checks") if isinstance(payload.get("failed_checks"), list) else []
    lines.extend(["", "## Failed Checks", ""])
    if failed:
        lines.extend(f"- {value}" for value in failed)
    else:
        lines.append("- none")
    lines.extend(["", "## Evidence", ""])
    paths = payload.get("evidence_paths") if isinstance(payload.get("evidence_paths"), dict) else {}
    for name in sorted(paths):
        lines.append(f"- {name}: `{paths[name]}`")
    lines.extend(
        [
            "",
            "This packet is read-only and does not authorize copying or applying the handoff.",
            "A real production apply still requires the explicit approval phrase and post-apply validation.",
        ]
    )
    return "\n".join(lines) + "\n"


def write_packet(payload: dict[str, Any], *, diagnostics_dir: Path) -> Path:
    stamp = datetime.now(UTC).strftime("%Y%m%dT%H%M%SZ")
    out_dir = diagnostics_dir / f"firstparty-production-authorization-{stamp}"
    out_dir.mkdir(parents=True, exist_ok=False)
    payload = dict(payload)
    payload["evidence_dir"] = str(out_dir)
    (out_dir / "summary.json").write_text(
        json.dumps(payload, indent=2, sort_keys=True, ensure_ascii=False) + "\n",
        encoding="utf-8",
    )
    (out_dir / "summary.md").write_text(render_markdown(payload), encoding="utf-8")
    return out_dir


def main() -> int:
    parser = argparse.ArgumentParser(
        description="Build first-party VPN production authorization evidence"
    )
    parser.add_argument("--diagnostics-dir", default=str(DIAGNOSTICS_DIR))
    parser.add_argument("--endpoint-summary")
    parser.add_argument("--apply-packet-summary")
    parser.add_argument("--handoff-summary")
    parser.add_argument("--rollout-summary")
    parser.add_argument("--preapply-summary")
    parser.add_argument(
        "--max-evidence-age-hours",
        type=int,
        default=DEFAULT_MAX_EVIDENCE_AGE_HOURS,
    )
    parser.add_argument("--write", action="store_true")
    parser.add_argument("--json", action="store_true")
    args = parser.parse_args()

    diagnostics_dir = Path(args.diagnostics_dir)
    endpoint_summary = Path(args.endpoint_summary) if args.endpoint_summary else latest_summary(
        "firstparty-production-endpoint-*/summary.json",
        diagnostics_dir,
    )
    apply_packet_summary = (
        Path(args.apply_packet_summary)
        if args.apply_packet_summary
        else latest_summary("firstparty-production-apply-packet-*/summary.json", diagnostics_dir)
    )
    handoff_summary = Path(args.handoff_summary) if args.handoff_summary else latest_summary(
        "firstparty-secure-material-handoff-*/summary.json",
        diagnostics_dir,
    )
    rollout_summary = Path(args.rollout_summary) if args.rollout_summary else latest_summary(
        "firstparty-rollout-packet-*/summary.json",
        diagnostics_dir,
    )
    preapply_summary = Path(args.preapply_summary) if args.preapply_summary else latest_summary(
        "firstparty-preapply-readiness-*/summary.json",
        diagnostics_dir,
    )
    missing = [
        name
        for name, value in (
            ("endpoint-summary", endpoint_summary),
            ("apply-packet-summary", apply_packet_summary),
            ("handoff-summary", handoff_summary),
            ("rollout-summary", rollout_summary),
            ("preapply-summary", preapply_summary),
        )
        if value is None
    ]
    if missing:
        raise SystemExit(f"missing required summaries: {', '.join(missing)}")
    payload = build_payload(
        endpoint_summary_path=endpoint_summary,
        apply_packet_summary_path=apply_packet_summary,
        handoff_summary_path=handoff_summary,
        rollout_summary_path=rollout_summary,
        preapply_summary_path=preapply_summary,
        max_evidence_age_hours=args.max_evidence_age_hours,
    )
    if args.write:
        out_dir = write_packet(payload, diagnostics_dir=diagnostics_dir)
        payload = read_json(out_dir / "summary.json")
    if args.json:
        print(json.dumps(payload, indent=2, sort_keys=True, ensure_ascii=False))
    elif not args.write:
        print(render_markdown(payload))
    return 0 if payload.get("ok") is True else 1


if __name__ == "__main__":
    raise SystemExit(main())
