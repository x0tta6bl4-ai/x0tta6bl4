#!/usr/bin/env python3
"""Build read-only pre-apply readiness evidence for first-party VPN rollout.

This packet is intentionally conservative: it proves that the production
rollout remains blocked until an explicit approval phrase exists, and that the
review packet includes a post-apply validation path before any real mutation.
It never SSHes to NL/SPB, never restarts services, and never mutates the host.
"""

from __future__ import annotations

import argparse
from datetime import UTC, datetime
import hashlib
import json
from pathlib import Path
from typing import Any


ROOT = Path("/mnt/projects")
DIAGNOSTICS_DIR = ROOT / "nl-diagnostics"
DEFAULT_MANIFEST = ROOT / "services" / "nl-server" / "manifest.json"
DEPLOYMENT_SOURCE = ROOT / "src" / "network" / "firstparty_vpn" / "deployment.py"
APPLIED_STATE_SOURCE = ROOT / "src" / "network" / "firstparty_vpn" / "applied_state.py"
APPROVAL_PHRASE = "APPLY_FIRSTPARTY_VPN_PRODUCTION_ROLLOUT"
LEGACY_SERVICE_MARKERS = ("x-ui", "xray", "ghost-access")


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


def build_payload(
    *,
    rollout_summary_path: Path,
    manifest_path: Path = DEFAULT_MANIFEST,
    generated_at: str | None = None,
) -> dict[str, Any]:
    generated_at = generated_at or utc_now()
    rollout = read_json(rollout_summary_path)
    manifest = read_json(manifest_path)
    deployment_source = _safe_read_text(DEPLOYMENT_SOURCE)
    applied_state_source = _safe_read_text(APPLIED_STATE_SOURCE)

    server_service_name = str(rollout.get("server_service_name") or "")
    client_service_name = str(rollout.get("client_service_name") or "")
    server_unit_path = str(rollout.get("server_unit_path") or "")
    client_unit_path = str(rollout.get("client_unit_path") or "")
    server_config_target = str(rollout.get("server_config_target") or "")
    client_config_target = str(rollout.get("client_config_target") or "")
    service_names = [server_service_name, client_service_name]
    service_paths = [server_unit_path, client_unit_path]
    config_targets = [server_config_target, client_config_target]
    legacy_findings = _legacy_marker_findings(service_names + service_paths + config_targets)
    source_checks = {
        "build_linux_post_apply_validator": "build_linux_post_apply_validator"
        in deployment_source,
        "executor_requires_post_apply_validation": (
            "deployment post-apply validation is required before OS mutation"
            in deployment_source
        ),
        "collect_linux_applied_state_snapshot": "collect_linux_applied_state_snapshot"
        in applied_state_source,
        "evaluate_linux_applied_state": "evaluate_linux_applied_state"
        in applied_state_source,
        "applied_state_checks_tun_routes_dns_nat": all(
            marker in applied_state_source
            for marker in (
                "full_tunnel_route_observed",
                "tun_dns_servers_observed",
                "kill_switch_table_observed",
                "server_masquerade_observed",
            )
        ),
    }
    source_post_apply_validation_ready = all(source_checks.values())
    checks = {
        "rollout_packet_ok": rollout.get("ok") is True,
        "rollout_packet_mutation_blocked": rollout.get("production_mutation_allowed")
        is False,
        "rollout_packet_no_nl_spb_writes": rollout.get("no_nl_or_spb_writes_performed")
        is True,
        "approval_phrase_expected": rollout.get("approval_phrase_required")
        == APPROVAL_PHRASE,
        "approval_not_present": rollout.get("approval_present") is False,
        "manifest_nl_write_allowed_false": manifest.get("nl_write_allowed") is False,
        "manifest_not_deployable_to_nl": (
            (manifest.get("source_promotion_status") or {}).get("deployable_to_nl")
            is False
        ),
        "firstparty_service_names_unique": (
            server_service_name
            and client_service_name
            and server_service_name != client_service_name
        ),
        "firstparty_service_names_scoped": all(
            name.startswith("x0tta-firstparty-vpn") and name.endswith(".service")
            for name in service_names
        ),
        "firstparty_unit_paths_scoped": all(
            path.startswith("/etc/systemd/system/x0tta-firstparty-vpn")
            and path.endswith(".service")
            for path in service_paths
        ),
        "firstparty_config_targets_scoped": all(
            path.startswith("/etc/x0tta-firstparty-vpn")
            and path.endswith(".json")
            for path in config_targets
        ),
        "firstparty_server_client_targets_distinct": (
            server_unit_path != client_unit_path
            and server_config_target != client_config_target
        ),
        "legacy_service_markers_absent": not legacy_findings,
        "source_post_apply_validation_ready": source_post_apply_validation_ready,
        "preapply_packet_does_not_authorize_mutation": True,
        "os_mutation_not_performed": True,
        "no_nl_or_spb_writes_performed": True,
    }
    failed_checks = sorted(name for name, passed in checks.items() if passed is not True)
    payload = {
        "mode": "firstparty-preapply-readiness-summary",
        "generated_at": generated_at,
        "ok": not failed_checks,
        "approval_phrase_required": APPROVAL_PHRASE,
        "approval_present": False,
        "production_mutation_allowed": False,
        "os_mutation_performed": False,
        "no_nl_or_spb_writes_performed": True,
        "rollout_summary_path": str(rollout_summary_path),
        "manifest_path": str(manifest_path),
        "deployment_epoch": rollout.get("deployment_epoch") or "missing",
        "server_service_name": server_service_name or "missing",
        "client_service_name": client_service_name or "missing",
        "server_unit_path": server_unit_path or "missing",
        "client_unit_path": client_unit_path or "missing",
        "server_config_target": server_config_target or "missing",
        "client_config_target": client_config_target or "missing",
        "legacy_service_findings": legacy_findings,
        "source_checks": source_checks,
        "failed_checks": failed_checks,
        "checks": checks,
        "evidence_hashes": {
            "rollout_summary_sha256": _safe_file_hash(rollout_summary_path),
            "manifest_sha256": _safe_file_hash(manifest_path),
            "deployment_source_sha256": _safe_file_hash(DEPLOYMENT_SOURCE),
            "applied_state_source_sha256": _safe_file_hash(APPLIED_STATE_SOURCE),
        },
    }
    return payload


def render_markdown(payload: dict[str, Any]) -> str:
    lines = [
        "# First-Party VPN Pre-Apply Readiness",
        "",
        f"generated_at: `{payload['generated_at']}`",
        f"ok: `{str(payload['ok']).lower()}`",
        f"deployment_epoch: `{payload['deployment_epoch']}`",
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
    lines.extend(
        [
            "",
            "## Post-Apply Validation Source",
            "",
        ]
    )
    source_checks = (
        payload.get("source_checks")
        if isinstance(payload.get("source_checks"), dict)
        else {}
    )
    for name in sorted(source_checks):
        lines.append(f"- {name}: `{bool_text(source_checks[name])}`")
    lines.extend(
        [
            "",
            "## Evidence",
            "",
            f"- rollout_summary_path: `{payload.get('rollout_summary_path')}`",
            f"- manifest_path: `{payload.get('manifest_path')}`",
            f"- server_service_name: `{payload.get('server_service_name')}`",
            f"- client_service_name: `{payload.get('client_service_name')}`",
            f"- legacy_service_findings: `{compact([str(v) for v in payload.get('legacy_service_findings') or []])}`",
            "",
            "No NL or SPB writes were performed by this pre-apply readiness packet.",
        ]
    )
    return "\n".join(lines) + "\n"


def write_packet(payload: dict[str, Any], *, diagnostics_dir: Path) -> Path:
    stamp = datetime.now(UTC).strftime("%Y%m%dT%H%M%SZ")
    out_dir = diagnostics_dir / f"firstparty-preapply-readiness-{stamp}"
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
        description="Build first-party VPN pre-apply readiness evidence"
    )
    parser.add_argument("--diagnostics-dir", default=str(DIAGNOSTICS_DIR))
    parser.add_argument("--rollout-summary")
    parser.add_argument("--manifest", default=str(DEFAULT_MANIFEST))
    parser.add_argument("--write", action="store_true")
    parser.add_argument("--json", action="store_true")
    args = parser.parse_args()

    diagnostics_dir = Path(args.diagnostics_dir)
    rollout_summary_path = (
        Path(args.rollout_summary)
        if args.rollout_summary
        else latest_summary("firstparty-rollout-packet-*/summary.json", diagnostics_dir)
    )
    if rollout_summary_path is None:
        raise SystemExit("first-party rollout packet summary is missing")
    payload = build_payload(
        rollout_summary_path=rollout_summary_path,
        manifest_path=Path(args.manifest),
    )
    if args.write:
        out_dir = write_packet(payload, diagnostics_dir=diagnostics_dir)
        payload["evidence_dir"] = str(out_dir)
    if args.json or not args.write:
        print(json.dumps(payload, indent=2, sort_keys=True, ensure_ascii=False))
    return 0 if payload.get("ok") is True else 2


def _safe_read_text(path: Path) -> str:
    try:
        return path.read_text(encoding="utf-8")
    except OSError:
        return ""


def _safe_file_hash(path: Path) -> str:
    if not path.exists() or not path.is_file():
        return "missing"
    return file_sha256(path)


def _legacy_marker_findings(values: list[str]) -> list[str]:
    findings: list[str] = []
    for index, value in enumerate(values):
        lowered = value.lower()
        for marker in LEGACY_SERVICE_MARKERS:
            if marker in lowered:
                findings.append(f"value{index}:{marker}")
    return findings


if __name__ == "__main__":
    raise SystemExit(main())
