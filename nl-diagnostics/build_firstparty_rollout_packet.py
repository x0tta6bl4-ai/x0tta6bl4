#!/usr/bin/env python3
"""Build a guarded first-party VPN production rollout packet.

This script reads local evidence only. It does not SSH to NL/SPB, does not
restart services, and does not mutate the host network stack.
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
APPROVAL_PHRASE = "APPLY_FIRSTPARTY_VPN_PRODUCTION_ROLLOUT"
FORBIDDEN_LEGACY_MARKERS = (
    "xray",
    "vless",
    "vmess",
    "trojan",
    "shadowsocks",
    "wireguard",
    "openvpn",
    "hiddify",
    "happ",
    "warp",
)


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


def contains_legacy_markers(*texts: str) -> list[str]:
    findings: list[str] = []
    for marker in FORBIDDEN_LEGACY_MARKERS:
        needle = marker.lower()
        for index, text in enumerate(texts):
            if needle in str(text or "").lower():
                findings.append(f"text{index}:{marker}")
                break
    return findings


def build_payload(
    *,
    staging_dir: Path,
    production_readiness_dir: Path,
    canary_dir: Path,
    generated_at: str | None = None,
) -> dict[str, Any]:
    generated_at = generated_at or utc_now()
    staging_summary_path = staging_dir / "summary.json"
    production_readiness_summary_path = production_readiness_dir / "summary.json"
    canary_summary_path = canary_dir / "summary.json"

    staging = read_json(staging_summary_path)
    production_readiness = read_json(production_readiness_summary_path)
    canary = read_json(canary_summary_path)
    server_service_plan = read_json(staging_dir / "server-service-plan.raw.json")
    client_service_plan = read_json(staging_dir / "client-service-plan.raw.json")
    server_apply_dry_run = read_json(staging_dir / "apply-server-config-dry-run.raw.json")
    client_apply_dry_run = read_json(staging_dir / "apply-client-config-dry-run.raw.json")
    verify_client_kits = read_json(staging_dir / "verify-client-kits.raw.json")
    export_client_kits = read_json(staging_dir / "export-client-kits.raw.json")

    server_unit = str(server_service_plan.get("unit_content") or "")
    client_unit = str(client_service_plan.get("unit_content") or "")
    legacy_findings = contains_legacy_markers(server_unit, client_unit)
    verified_exports = (
        verify_client_kits.get("exports")
        if isinstance(verify_client_kits.get("exports"), list)
        else []
    )
    all_verified_kits_ok = bool(verified_exports) and all(
        isinstance(item, dict)
        and item.get("ok") is True
        and item.get("signature_present") is True
        and isinstance(item.get("readiness"), dict)
        and item["readiness"].get("ok") is True
        and item.get("server_secrets_included") is False
        for item in verified_exports
    )

    checks = {
        "staging_ok": staging.get("ok") is True,
        "production_readiness_ok": production_readiness.get("ok") is True
        and production_readiness.get("decision_allowed") is True,
        "canary_ok": canary.get("ok") is True,
        "server_service_plan_ok": server_service_plan.get("ok") is True,
        "client_service_plan_ok": client_service_plan.get("ok") is True,
        "server_unit_starts_firstparty_server_tun": (
            " server-tun " in f" {server_unit} "
            and "x0vpn_node.py" in server_unit
            and "--allow-os-mutation" in server_unit
            and "--uplink-interface" in server_unit
        ),
        "client_unit_starts_firstparty_client_tun": (
            " client-tun " in f" {client_unit} "
            and "x0vpn_node.py" in client_unit
            and "--allow-os-mutation" in client_unit
            and "--apply-client-policy" in client_unit
            and "--enable-kill-switch" in client_unit
        ),
        "client_unit_has_rollback_exec_stop": (
            "ExecStopPost=" in client_unit
            and "client-policy-rollback" in client_unit
            and "--enable-kill-switch" in client_unit
        ),
        "server_apply_dry_run_ok": _dry_run_apply_ok(server_apply_dry_run),
        "client_apply_dry_run_ok": _dry_run_apply_ok(client_apply_dry_run),
        "server_config_hash_matches_staging": (
            server_apply_dry_run.get("candidate_hash")
            == staging.get("server_candidate_hash")
        ),
        "client_config_hash_matches_staging": (
            client_apply_dry_run.get("candidate_hash")
            == staging.get("client_candidate_hash")
        ),
        "client_kits_verified": verify_client_kits.get("ok") is True
        and verify_client_kits.get("require_signature") is True
        and verify_client_kits.get("readiness_required") is True
        and all_verified_kits_ok,
        "client_kits_exported_without_server_secrets": export_client_kits.get("ok") is True
        and export_client_kits.get("server_secrets_included") is False,
        "no_raw_secret_material_in_evidence": staging.get(
            "raw_secret_material_stored_in_evidence"
        )
        is False,
        "kit_material_not_persisted_in_repo": staging.get("kit_material_persisted_in_repo")
        is False,
        "legacy_protocol_markers_absent": not legacy_findings,
        "approval_required": True,
        "production_mutation_blocked": True,
        "os_mutation_not_performed": True,
        "no_nl_or_spb_writes_performed": True,
    }
    failed_checks = sorted(name for name, passed in checks.items() if passed is not True)
    evidence_hashes = {
        "staging_summary_sha256": _safe_file_hash(staging_summary_path),
        "production_readiness_summary_sha256": _safe_file_hash(
            production_readiness_summary_path
        ),
        "canary_summary_sha256": _safe_file_hash(canary_summary_path),
        "server_service_plan_sha256": _safe_file_hash(
            staging_dir / "server-service-plan.raw.json"
        ),
        "client_service_plan_sha256": _safe_file_hash(
            staging_dir / "client-service-plan.raw.json"
        ),
        "server_apply_dry_run_sha256": _safe_file_hash(
            staging_dir / "apply-server-config-dry-run.raw.json"
        ),
        "client_apply_dry_run_sha256": _safe_file_hash(
            staging_dir / "apply-client-config-dry-run.raw.json"
        ),
        "verify_client_kits_sha256": _safe_file_hash(
            staging_dir / "verify-client-kits.raw.json"
        ),
    }
    payload = {
        "mode": "firstparty-rollout-packet-summary",
        "generated_at": generated_at,
        "ok": not failed_checks,
        "approval_phrase_required": APPROVAL_PHRASE,
        "approval_present": False,
        "production_mutation_allowed": False,
        "os_mutation_performed": False,
        "no_nl_or_spb_writes_performed": True,
        "staging_summary_path": str(staging_summary_path),
        "production_readiness_summary_path": str(production_readiness_summary_path),
        "canary_summary_path": str(canary_summary_path),
        "deployment_epoch": staging.get("deployment_epoch") or "missing",
        "server_service_name": server_service_plan.get("service_name") or "missing",
        "client_service_name": client_service_plan.get("service_name") or "missing",
        "server_unit_path": server_service_plan.get("unit_path") or "missing",
        "client_unit_path": client_service_plan.get("unit_path") or "missing",
        "server_config_target": server_apply_dry_run.get("installed_config")
        or "missing",
        "client_config_target": client_apply_dry_run.get("installed_config")
        or "missing",
        "server_candidate_hash": server_apply_dry_run.get("candidate_hash")
        or "missing",
        "client_candidate_hash": client_apply_dry_run.get("candidate_hash")
        or "missing",
        "client_kit_count": verify_client_kits.get("kit_count") or 0,
        "verified_kit_count": len(verified_exports),
        "legacy_protocol_findings": legacy_findings,
        "failed_checks": failed_checks,
        "checks": checks,
        "evidence_hashes": evidence_hashes,
    }
    return payload


def _dry_run_apply_ok(payload: dict[str, Any]) -> bool:
    return (
        payload.get("ok") is True
        and payload.get("dry_run") is True
        and payload.get("file_mutation_performed") is False
        and payload.get("os_mutation_performed") is False
        and payload.get("service_restart_performed") is False
        and payload.get("rollback_on_failure") is True
        and payload.get("rollback_performed") is False
    )


def _safe_file_hash(path: Path) -> str:
    if not path.exists() or not path.is_file():
        return "missing"
    return file_sha256(path)


def render_markdown(payload: dict[str, Any]) -> str:
    lines = [
        "# First-Party VPN Rollout Packet",
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
            "## Evidence",
            "",
            f"- staging_summary_path: `{payload.get('staging_summary_path')}`",
            f"- production_readiness_summary_path: `{payload.get('production_readiness_summary_path')}`",
            f"- canary_summary_path: `{payload.get('canary_summary_path')}`",
            f"- server_service_name: `{payload.get('server_service_name')}`",
            f"- client_service_name: `{payload.get('client_service_name')}`",
            f"- client_kit_count: `{payload.get('client_kit_count')}`",
            f"- verified_kit_count: `{payload.get('verified_kit_count')}`",
            f"- legacy_protocol_findings: `{compact([str(v) for v in payload.get('legacy_protocol_findings') or []])}`",
            "",
            "No NL or SPB writes were performed by this rollout packet.",
        ]
    )
    return "\n".join(lines) + "\n"


def write_packet(payload: dict[str, Any], *, diagnostics_dir: Path) -> Path:
    stamp = datetime.now(UTC).strftime("%Y%m%dT%H%M%SZ")
    out_dir = diagnostics_dir / f"firstparty-rollout-packet-{stamp}"
    out_dir.mkdir(parents=True, exist_ok=False)
    summary_path = out_dir / "summary.json"
    payload = dict(payload)
    payload["evidence_dir"] = str(out_dir)
    summary_path.write_text(
        json.dumps(payload, indent=2, sort_keys=True, ensure_ascii=False) + "\n",
        encoding="utf-8",
    )
    (out_dir / "summary.md").write_text(render_markdown(payload), encoding="utf-8")
    return out_dir


def main() -> int:
    parser = argparse.ArgumentParser(
        description="Build guarded first-party VPN production rollout packet"
    )
    parser.add_argument("--diagnostics-dir", default=str(DIAGNOSTICS_DIR))
    parser.add_argument("--staging-dir")
    parser.add_argument("--production-readiness-dir")
    parser.add_argument("--canary-dir")
    parser.add_argument("--write", action="store_true")
    parser.add_argument("--json", action="store_true")
    args = parser.parse_args()

    diagnostics_dir = Path(args.diagnostics_dir)
    staging_dir = (
        Path(args.staging_dir)
        if args.staging_dir
        else _summary_parent(
            latest_summary("firstparty-staging-packet-*/summary.json", diagnostics_dir)
        )
    )
    production_readiness_dir = (
        Path(args.production_readiness_dir)
        if args.production_readiness_dir
        else _summary_parent(
            latest_summary(
                "firstparty-production-readiness-*/summary.json",
                diagnostics_dir,
            )
        )
    )
    canary_dir = (
        Path(args.canary_dir)
        if args.canary_dir
        else _summary_parent(
            latest_summary("firstparty-live-canary-*/summary.json", diagnostics_dir)
        )
    )
    payload = build_payload(
        staging_dir=staging_dir,
        production_readiness_dir=production_readiness_dir,
        canary_dir=canary_dir,
    )
    if args.write:
        out_dir = write_packet(payload, diagnostics_dir=diagnostics_dir)
        payload["evidence_dir"] = str(out_dir)
    if args.json or not args.write:
        print(json.dumps(payload, indent=2, sort_keys=True, ensure_ascii=False))
    return 0 if payload.get("ok") is True else 2


def _summary_parent(path: Path | None) -> Path:
    if path is None:
        raise SystemExit("required first-party evidence summary is missing")
    return path.parent


if __name__ == "__main__":
    raise SystemExit(main())
