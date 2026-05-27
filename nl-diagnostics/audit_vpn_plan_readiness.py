#!/usr/bin/env python3
"""Audit whether the local VPN improvement plan is ready to operate.

The audit reads local reports only. It does not SSH to NL/SPB and does not
mutate VPN runtime state.
"""

from __future__ import annotations

import argparse
from collections import Counter
from datetime import datetime, timezone
import json
from pathlib import Path
import re
import subprocess
import sys
from typing import Any


ROOT = Path("/mnt/projects")
DIAGNOSTICS_DIR = ROOT / "nl-diagnostics"
DEFAULT_DECISION = DIAGNOSTICS_DIR / "current-vpn-decision-2026-05-28.json"
DEFAULT_BOOT_GAP = DIAGNOSTICS_DIR / "boot-gap-watch-2026-05-28.json"
DEFAULT_PROVIDER_PACKET = (
    DIAGNOSTICS_DIR
    / "provider-incident-packets"
    / "provider-incident-packet-20260527T230246Z.json"
)
DEFAULT_HISTORY = DIAGNOSTICS_DIR / "blocking-probe-history-2026-05-28.json"
DEFAULT_REFRESH = DIAGNOSTICS_DIR / "vpn-planning-refresh-2026-05-28.json"
DEFAULT_OPERATOR_CARD = DIAGNOSTICS_DIR / "vpn-operator-card-2026-05-28.json"
DEFAULT_FAILOVER = DIAGNOSTICS_DIR / "manual-failover-plan-2026-05-28.json"
DEFAULT_TRANSPORT_PROBE = DIAGNOSTICS_DIR / "nl-transport-probe-2026-05-28.json"
DEFAULT_SECONDARY = DIAGNOSTICS_DIR / "secondary-exit-probe-template-2026-05-28.json"
DEFAULT_MANIFEST = ROOT / "services" / "nl-server" / "manifest.json"
DEFAULT_PREFLIGHT_VALIDATOR = ROOT / "services" / "nl-server" / "tools" / "validate_preflight_readiness.py"
DEFAULT_APPROVAL_DOC = DIAGNOSTICS_DIR / "nl-deploy-preflight-checklist-2026-05-27.md"
DEFAULT_JSON_OUT = DIAGNOSTICS_DIR / "vpn-plan-readiness-audit-2026-05-28.json"
DEFAULT_MARKDOWN_OUT = DIAGNOSTICS_DIR / "vpn-plan-readiness-audit-2026-05-28.md"

APPROVAL_PHRASE = "approve NL write for health shell split only"
SPB_TRUE_MARKER = re.compile(r"['\"]?spb_fallback_allowed['\"]?\s*[:=]\s*true\b", re.IGNORECASE)
READY = "ready_local"
BLOCKED = "blocked_future_approval"
WATCH = "watch"
MISSING = "missing"


def read_json(path: Path) -> dict[str, Any]:
    try:
        value = json.loads(path.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError):
        return {}
    return value if isinstance(value, dict) else {}


def read_text(path: Path) -> str:
    try:
        return path.read_text(encoding="utf-8")
    except OSError:
        return ""


def resolve_path(value: str | None, root: Path = ROOT) -> Path | None:
    if not value:
        return None
    path = Path(value)
    return path if path.is_absolute() else root / path


def path_exists(value: str | None, root: Path = ROOT) -> bool:
    path = resolve_path(value, root)
    return bool(path and path.exists())


def latest_snapshot(snapshots_dir: Path) -> Path | None:
    if not snapshots_dir.is_dir():
        return None
    candidates = [path for path in snapshots_dir.iterdir() if path.is_dir()]
    if not candidates:
        return None
    return sorted(candidates, key=lambda path: path.name)[-1]


def flag_is_false(payload: dict[str, Any], key: str) -> bool:
    return payload.get(key) is False


def all_false(checks: list[bool]) -> bool:
    return all(check is True for check in checks)


def item(
    *,
    item_id: str,
    title: str,
    status: str,
    evidence: list[str],
    next_step: str,
    ok: bool | None = None,
) -> dict[str, Any]:
    if ok is None:
        ok = status in {READY, BLOCKED, WATCH}
    return {
        "id": item_id,
        "title": title,
        "status": status,
        "ok": ok,
        "evidence": evidence,
        "next_step": next_step,
    }


def audit_snapshot_chain(decision: dict[str, Any], refresh: dict[str, Any], root: Path) -> dict[str, Any]:
    decision_snapshot = str(decision.get("snapshot") or "")
    refresh_snapshot = str(refresh.get("snapshot") or "")
    snapshot_path = resolve_path(decision_snapshot, root)
    latest = latest_snapshot(root / "nl-diagnostics" / "snapshots")
    latest_name = latest.name if latest else "missing"
    same_report_snapshot = bool(decision_snapshot and refresh_snapshot and decision_snapshot == refresh_snapshot)
    same_latest = bool(snapshot_path and latest and snapshot_path.name == latest.name)
    exists = path_exists(decision_snapshot, root)

    if same_report_snapshot and same_latest and exists:
        status = READY
    elif decision_snapshot and exists:
        status = WATCH
    else:
        status = MISSING

    return item(
        item_id="EVIDENCE-01",
        title="Latest read-only snapshot is the shared evidence anchor",
        status=status,
        evidence=[
            f"decision_snapshot={decision_snapshot or 'missing'}",
            f"refresh_snapshot={refresh_snapshot or 'missing'}",
            f"latest_snapshot={latest_name}",
            f"snapshot_exists={str(exists).lower()}",
        ],
        next_step="collect a fresh read-only snapshot during the next visible outage",
    )


def audit_decision_guard(decision: dict[str, Any]) -> dict[str, Any]:
    decision_data = decision.get("decision") or {}
    classification = decision.get("classification") or {}
    safe = all_false(
        [
            flag_is_false(decision, "mutation_allowed"),
            flag_is_false(decision, "nl_mutation_allowed"),
            flag_is_false(decision, "auto_profile_switch_allowed"),
            flag_is_false(decision, "spb_fallback_allowed"),
            flag_is_false(decision_data, "mutation_allowed"),
            flag_is_false(decision_data, "nl_mutation_allowed"),
            flag_is_false(decision_data, "auto_profile_switch_allowed"),
            flag_is_false(decision_data, "spb_fallback_allowed"),
        ]
    )
    decision_name = str(decision_data.get("decision") or "missing")
    transport = str(classification.get("transport_status") or "missing")
    failure_domain = str(classification.get("failure_domain") or "missing")

    if not safe or decision_name == "missing":
        status = MISSING
    elif decision_name == "observe":
        status = READY
    else:
        status = WATCH

    return item(
        item_id="DECISION-01",
        title="Current decision blocks mutation and automatic profile changes",
        status=status,
        evidence=[
            f"decision={decision_name}",
            f"transport_status={transport}",
            f"failure_domain={failure_domain}",
            f"safe_flags={str(safe).lower()}",
        ],
        next_step="keep decision=observe unless a fresh snapshot changes the failure domain",
    )


def audit_blocking_history(history: dict[str, Any], decision: dict[str, Any]) -> dict[str, Any]:
    summary = history.get("summary") or {}
    latest = summary.get("latest") or {}
    decision_snapshot = Path(str(decision.get("snapshot") or "")).name
    latest_snapshot_name = str(latest.get("snapshot") or "missing")
    snapshot_count = int(summary.get("snapshot_count") or 0)
    trend = str(summary.get("trend") or "missing")
    target_count = int(latest.get("target_count") or 0)
    ok_count = int(latest.get("ok_count") or 0)

    if snapshot_count <= 0:
        status = MISSING
    elif trend == "stable_no_probe_evidence" and latest_snapshot_name == decision_snapshot:
        status = READY
    else:
        status = WATCH

    return item(
        item_id="EVIDENCE-02",
        title="Blocking/app probe history is available as trend evidence",
        status=status,
        evidence=[
            f"snapshot_count={snapshot_count}",
            f"trend={trend}",
            f"latest_probe_snapshot={latest_snapshot_name}",
            f"latest_targets_ok={ok_count}/{target_count}",
        ],
        next_step="use probes as app/path evidence, not as an x-ui restart trigger",
    )


def audit_boot_gap_watch(boot_gap: dict[str, Any]) -> dict[str, Any]:
    status = str(boot_gap.get("status") or "missing")
    classification = boot_gap.get("classification") or {}
    safe = all_false(
        [
            flag_is_false(boot_gap, "nl_mutation_allowed"),
            flag_is_false(boot_gap, "spb_fallback_allowed"),
            flag_is_false(boot_gap, "automatic_failover_allowed"),
        ]
    )
    if not safe or status == "missing":
        item_status = MISSING
    elif status == "normal":
        item_status = READY
    else:
        item_status = WATCH
    return item(
        item_id="BOOT-01",
        title="Boot-gap provider signal is tracked separately from restart decisions",
        status=item_status,
        evidence=[
            f"boot_gap_watch_status={status}",
            f"boot_gap_seconds={boot_gap.get('boot_gap_seconds', 'missing')}",
            f"provider_status={classification.get('provider_status', 'missing')}",
            f"transport_status={classification.get('transport_status', 'missing')}",
            f"safe_flags={str(safe).lower()}",
        ],
        next_step="keep provider boot gap on watch while current transport remains healthy/advisory",
    )


def audit_provider_packet(
    provider_packet: dict[str, Any],
    decision: dict[str, Any],
) -> dict[str, Any]:
    packet_type = str(provider_packet.get("packet_type") or "missing")
    stale = provider_packet.get("snapshot_stale")
    packet_snapshot = str(provider_packet.get("snapshot_dir") or "")
    decision_snapshot = str(decision.get("snapshot") or "")
    same_snapshot = bool(
        packet_snapshot
        and decision_snapshot
        and Path(packet_snapshot).name == Path(decision_snapshot).name
    )
    safe = all_false(
        [
            provider_packet.get("nl_write_performed") is False,
            flag_is_false(provider_packet, "mutation_allowed"),
            flag_is_false(provider_packet, "nl_mutation_allowed"),
            flag_is_false(provider_packet, "spb_fallback_allowed"),
            flag_is_false(provider_packet, "automatic_failover_allowed"),
        ]
    )
    if not safe or packet_type == "missing" or not same_snapshot:
        status = MISSING
    elif stale is True:
        status = WATCH
    else:
        status = READY
    return item(
        item_id="PROVIDER-01",
        title="Provider packet is generated from the same read-only snapshot",
        status=status,
        evidence=[
            f"provider_packet_type={packet_type}",
            f"snapshot_stale={str(stale).lower()}",
            f"packet_snapshot={packet_snapshot or 'missing'}",
            f"decision_snapshot={decision_snapshot or 'missing'}",
            f"same_snapshot={str(same_snapshot).lower()}",
            f"safe_flags={str(safe).lower()}",
        ],
        next_step="use the packet for provider questions only when fresh evidence points to provider or host failure",
    )


def audit_refresh(refresh: dict[str, Any]) -> dict[str, Any]:
    summary = refresh.get("summary") or {}
    safe = all_false(
        [
            flag_is_false(refresh, "nl_mutation_allowed"),
            flag_is_false(refresh, "spb_fallback_allowed"),
            flag_is_false(refresh, "automatic_failover_allowed"),
            summary.get("nl_mutation_allowed") is False,
            summary.get("spb_fallback_allowed") is False,
            summary.get("automatic_failover_allowed") is False,
        ]
    )
    ok = refresh.get("ok") is True
    status = READY if ok and safe else MISSING
    return item(
        item_id="REFRESH-01",
        title="One refresh command rebuilds the local planning reports",
        status=status,
        evidence=[
            f"refresh_ok={str(ok).lower()}",
            f"operator_status={summary.get('operator_status', 'missing')}",
            f"manual_failover_status={summary.get('manual_failover_status', 'missing')}",
            f"safe_flags={str(safe).lower()}",
        ],
        next_step="run refresh after every new snapshot before deciding on action",
    )


def audit_operator_card(operator_card: dict[str, Any]) -> dict[str, Any]:
    operator = operator_card.get("operator") or {}
    state = operator_card.get("current_state") or {}
    operator_status = str(operator.get("operator_status") or "missing")
    safe = all_false(
        [
            flag_is_false(operator_card, "nl_mutation_allowed"),
            flag_is_false(operator_card, "spb_fallback_allowed"),
            flag_is_false(operator_card, "automatic_failover_allowed"),
        ]
    )
    if not safe or operator_status == "missing":
        status = MISSING
    elif operator_status == "observe":
        status = READY
    else:
        status = WATCH
    return item(
        item_id="OPERATOR-01",
        title="Short incident card exists for the next outage",
        status=status,
        evidence=[
            f"operator_status={operator_status}",
            f"plain_action={operator.get('plain_action', 'missing')}",
            f"blocking_history_trend={state.get('blocking_history_trend', 'missing')}",
            f"safe_flags={str(safe).lower()}",
        ],
        next_step="start incidents from the operator card, then collect fresh evidence",
    )


def audit_failover_plan(failover: dict[str, Any], secondary: dict[str, Any]) -> list[dict[str, Any]]:
    summary = failover.get("summary") or {}
    failover_safe = all_false(
        [
            flag_is_false(failover, "nl_mutation_allowed"),
            flag_is_false(failover, "spb_fallback_allowed"),
            flag_is_false(failover, "automatic_failover_allowed"),
            summary.get("spb_fallback_allowed") is False,
            summary.get("automatic_failover_allowed") is False,
        ]
    )
    failover_status = str(failover.get("status") or "missing")
    plan_status = READY if failover_status == "planning_not_active" and failover_safe else MISSING

    secondary_status = str(secondary.get("status") or "missing")
    secondary_configured = bool(secondary.get("candidate_configured"))
    secondary_safe = all_false(
        [
            flag_is_false(secondary, "nl_mutation_allowed"),
            flag_is_false(secondary, "spb_fallback_allowed"),
            flag_is_false(secondary, "automatic_failover_allowed"),
        ]
    )
    if secondary_status == "planning_template" and not secondary_configured and secondary_safe:
        secondary_item_status = BLOCKED
    elif secondary_safe:
        secondary_item_status = WATCH
    else:
        secondary_item_status = MISSING

    return [
        item(
            item_id="FAILOVER-01",
            title="Manual failover is documented but inactive",
            status=plan_status,
            evidence=[
                f"manual_failover_status={failover_status}",
                f"spb_fallback_allowed={str(summary.get('spb_fallback_allowed')).lower()}",
                f"automatic_failover_allowed={str(summary.get('automatic_failover_allowed')).lower()}",
                f"safe_flags={str(failover_safe).lower()}",
            ],
            next_step="keep failover manual-only and require fresh evidence before any client switch",
        ),
        item(
            item_id="FAILOVER-02",
            title="Secondary exit probe is only a safe template until a new node exists",
            status=secondary_item_status,
            evidence=[
                f"secondary_probe_status={secondary_status}",
                f"candidate_configured={str(secondary_configured).lower()}",
                f"spb_fallback_allowed={str(secondary.get('spb_fallback_allowed')).lower()}",
                f"automatic_failover_allowed={str(secondary.get('automatic_failover_allowed')).lower()}",
            ],
            next_step="choose a new non-SPB provider/region before any emergency profile test",
        ),
    ]


def audit_transport_probe(transport_probe: dict[str, Any]) -> dict[str, Any]:
    status = str(transport_probe.get("status") or "missing")
    ok_count = transport_probe.get("ok_count", "missing")
    port_count = transport_probe.get("port_count", "missing")
    safe = all_false(
        [
            flag_is_false(transport_probe, "nl_mutation_allowed"),
            flag_is_false(transport_probe, "spb_fallback_allowed"),
            flag_is_false(transport_probe, "automatic_failover_allowed"),
        ]
    )
    if not safe or status == "missing":
        item_status = MISSING
    elif status == "healthy":
        item_status = READY
    else:
        item_status = WATCH
    return item(
        item_id="TRANSPORT-01",
        title="Outside-in NL TCP port probe is available",
        status=item_status,
        evidence=[
            f"transport_probe_status={status}",
            f"transport_probe_ok_count={ok_count}/{port_count}",
            f"failure_domain_hint={transport_probe.get('failure_domain_hint', 'missing')}",
            f"safe_flags={str(safe).lower()}",
        ],
        next_step="if any public NL port fails, collect a fresh read-only snapshot and compare listeners",
    )


def audit_source_reconciliation(manifest: dict[str, Any]) -> dict[str, Any]:
    gap = manifest.get("gap_summary") or {}
    source = manifest.get("source_promotion_status") or {}
    missing_local_source = int(gap.get("missing_local_source") or 0)
    local_name_drift = int(gap.get("local_name_drift") or 0)
    accepted_local_delta = int(gap.get("accepted_local_delta") or 0)
    nl_write_allowed = manifest.get("nl_write_allowed")
    deployable = source.get("deployable_to_nl")

    ready = (
        nl_write_allowed is False
        and deployable is False
        and missing_local_source == 0
        and local_name_drift == 0
    )
    return item(
        item_id="SOURCE-01",
        title="NL source reconciliation is locally closed and deploy-blocked",
        status=READY if ready else MISSING,
        evidence=[
            f"nl_write_allowed={str(nl_write_allowed).lower()}",
            f"deployable_to_nl={str(deployable).lower()}",
            f"missing_local_source={missing_local_source}",
            f"local_name_drift={local_name_drift}",
            f"accepted_local_delta={accepted_local_delta}",
        ],
        next_step="keep services/nl-server as reviewed local source until a separate NL write approval exists",
    )


def audit_preflight(preflight: dict[str, Any]) -> dict[str, Any]:
    ok = preflight.get("ok") is True
    deploy_status = str(preflight.get("deploy_status") or "missing")
    nl_write_allowed = preflight.get("nl_write_allowed")
    ready = ok and deploy_status == "local_ready_but_deploy_blocked" and nl_write_allowed is False
    return item(
        item_id="PREFLIGHT-01",
        title="Preflight validator passes while deploy remains blocked",
        status=READY if ready else MISSING,
        evidence=[
            f"preflight_ok={str(ok).lower()}",
            f"deploy_status={deploy_status}",
            f"nl_write_allowed={str(nl_write_allowed).lower()}",
            f"check_count={len(preflight.get('checks') or [])}",
        ],
        next_step="run preflight again before any maintenance window",
    )


def audit_future_write_gate(manifest: dict[str, Any], preflight: dict[str, Any], approval_text: str) -> dict[str, Any]:
    phrase_present = APPROVAL_PHRASE in approval_text
    nl_write_allowed = manifest.get("nl_write_allowed")
    deploy_status = str(preflight.get("deploy_status") or "missing")
    ready = phrase_present and nl_write_allowed is False and deploy_status == "local_ready_but_deploy_blocked"
    return item(
        item_id="GATE-01",
        title="Future NL write is blocked until the exact approval phrase",
        status=BLOCKED if ready else MISSING,
        evidence=[
            f"approval_phrase_present={str(phrase_present).lower()}",
            f"required_phrase={APPROVAL_PHRASE}",
            f"nl_write_allowed={str(nl_write_allowed).lower()}",
            f"deploy_status={deploy_status}",
        ],
        next_step="do not stage files to NL before the exact approval phrase is given",
    )


def audit_spb_exclusion(
    decision: dict[str, Any],
    refresh: dict[str, Any],
    failover: dict[str, Any],
    secondary: dict[str, Any],
    manifest: dict[str, Any],
    report_texts: list[str],
) -> dict[str, Any]:
    decision_data = decision.get("decision") or {}
    refresh_summary = refresh.get("summary") or {}
    failover_summary = failover.get("summary") or {}
    inactive_integrations = manifest.get("inactive_integrations") or []
    spb = next(
        (
            row
            for row in inactive_integrations
            if isinstance(row, dict) and row.get("name") == "spb_standalone_xray"
        ),
        {},
    )
    no_true_marker = SPB_TRUE_MARKER.search("\n".join(report_texts)) is None
    ready = all_false(
        [
            flag_is_false(decision, "spb_fallback_allowed"),
            flag_is_false(decision_data, "spb_fallback_allowed"),
            flag_is_false(refresh, "spb_fallback_allowed"),
            refresh_summary.get("spb_fallback_allowed") is False,
            flag_is_false(failover, "spb_fallback_allowed"),
            failover_summary.get("spb_fallback_allowed") is False,
            flag_is_false(secondary, "spb_fallback_allowed"),
            spb.get("enabled") is False,
            no_true_marker,
        ]
    )
    return item(
        item_id="SPB-01",
        title="SPB remains excluded from recovery",
        status=READY if ready else MISSING,
        evidence=[
            f"decision_spb_fallback_allowed={str(decision.get('spb_fallback_allowed')).lower()}",
            f"refresh_spb_fallback_allowed={str(refresh.get('spb_fallback_allowed')).lower()}",
            f"manual_failover_spb_fallback_allowed={str(failover.get('spb_fallback_allowed')).lower()}",
            f"secondary_spb_fallback_allowed={str(secondary.get('spb_fallback_allowed')).lower()}",
            f"manifest_spb_enabled={str(spb.get('enabled')).lower()}",
            f"plain_true_marker_absent={str(no_true_marker).lower()}",
        ],
        next_step="keep SPB disabled until it has its own explicit reactivation plan",
    )


def run_preflight_validator(path: Path) -> dict[str, Any]:
    if not path.exists():
        return {"ok": False, "deploy_status": "validator_missing", "nl_write_allowed": None, "checks": []}
    completed = subprocess.run(
        [sys.executable, str(path)],
        cwd=str(ROOT),
        stdout=subprocess.PIPE,
        stderr=subprocess.PIPE,
        text=True,
        check=False,
    )
    try:
        payload = json.loads(completed.stdout)
    except json.JSONDecodeError:
        payload = {}
    if not isinstance(payload, dict):
        payload = {}
    payload.setdefault("ok", completed.returncode == 0)
    payload["validator_exit_code"] = completed.returncode
    if completed.stderr:
        payload["validator_stderr_tail"] = completed.stderr[-1000:]
    return payload


def build_payload(inputs: dict[str, Any], *, root: Path = ROOT) -> dict[str, Any]:
    decision = inputs.get("decision") or {}
    boot_gap = inputs.get("boot_gap") or {}
    provider_packet = inputs.get("provider_packet") or {}
    history = inputs.get("history") or {}
    refresh = inputs.get("refresh") or {}
    operator_card = inputs.get("operator_card") or {}
    failover = inputs.get("failover") or {}
    transport_probe = inputs.get("transport_probe") or {}
    secondary = inputs.get("secondary") or {}
    manifest = inputs.get("manifest") or {}
    preflight = inputs.get("preflight") or {}
    approval_text = str(inputs.get("approval_text") or "")
    report_texts = [str(text) for text in inputs.get("report_texts") or []]

    items: list[dict[str, Any]] = [
        audit_snapshot_chain(decision, refresh, root),
        audit_decision_guard(decision),
        audit_boot_gap_watch(boot_gap),
        audit_provider_packet(provider_packet, decision),
        audit_blocking_history(history, decision),
        audit_refresh(refresh),
        audit_operator_card(operator_card),
        audit_transport_probe(transport_probe),
        audit_source_reconciliation(manifest),
        audit_preflight(preflight),
        audit_future_write_gate(manifest, preflight, approval_text),
        audit_spb_exclusion(decision, refresh, failover, secondary, manifest, report_texts),
    ]
    items.extend(audit_failover_plan(failover, secondary))

    counts = Counter(str(row["status"]) for row in items)
    missing = [row["id"] for row in items if row["status"] == MISSING]
    watch = [row["id"] for row in items if row["status"] == WATCH]
    blocked = [row["id"] for row in items if row["status"] == BLOCKED]
    overall_status = "missing_evidence" if missing else "ready_local_with_future_blocks"

    return {
        "schema_version": 1,
        "source": "nl-diagnostics/audit_vpn_plan_readiness.py",
        "generated_at": datetime.now(timezone.utc).isoformat(),
        "overall_status": overall_status,
        "ok": not missing,
        "summary": {
            "ready_local": counts.get(READY, 0),
            "blocked_future_approval": counts.get(BLOCKED, 0),
            "watch": counts.get(WATCH, 0),
            "missing": counts.get(MISSING, 0),
            "missing_items": missing,
            "watch_items": watch,
            "blocked_items": blocked,
            "operator_status": (operator_card.get("operator") or {}).get("operator_status", "missing"),
            "decision": (decision.get("decision") or {}).get("decision", "missing"),
            "boot_gap_watch_status": boot_gap.get("status", "missing"),
            "provider_packet_type": provider_packet.get("packet_type", "missing"),
            "provider_packet_stale": provider_packet.get("snapshot_stale", "missing"),
            "transport_probe_status": transport_probe.get("status", "missing"),
            "nl_write_allowed": False,
            "spb_fallback_allowed": False,
            "automatic_failover_allowed": False,
        },
        "items": items,
        "mutation_allowed": False,
        "nl_mutation_allowed": False,
        "spb_fallback_allowed": False,
        "automatic_failover_allowed": False,
    }


def render_markdown(payload: dict[str, Any]) -> str:
    summary = payload["summary"]
    lines = [
        "# VPN Plan Readiness Audit",
        "",
        f"generated_at: `{payload['generated_at']}`",
        f"overall_status: `{payload['overall_status']}`",
        f"ok: `{str(payload['ok']).lower()}`",
        "",
        "## Summary",
        "",
        "```text",
        f"ready_local={summary.get('ready_local')}",
        f"blocked_future_approval={summary.get('blocked_future_approval')}",
        f"watch={summary.get('watch')}",
        f"missing={summary.get('missing')}",
        f"decision={summary.get('decision')}",
        f"operator_status={summary.get('operator_status')}",
        f"boot_gap_watch_status={summary.get('boot_gap_watch_status')}",
        f"provider_packet_type={summary.get('provider_packet_type')}",
        f"provider_packet_stale={summary.get('provider_packet_stale')}",
        f"transport_probe_status={summary.get('transport_probe_status')}",
        "nl_write_allowed=false",
        "spb_fallback_allowed=false",
        "automatic_failover_allowed=false",
        "```",
        "",
        "## Readiness Matrix",
        "",
        "| ID | Status | Area | Next Step |",
        "|---|---|---|---|",
    ]
    for row in payload["items"]:
        lines.append(f"| `{row['id']}` | `{row['status']}` | {row['title']} | {row['next_step']} |")

    lines.extend(["", "## Evidence", ""])
    for row in payload["items"]:
        lines.extend([f"### {row['id']}", ""])
        lines.extend(f"- {value}" for value in row["evidence"])
        lines.append("")

    lines.append("No NL or SPB writes were performed by this readiness audit.")
    return "\n".join(lines) + "\n"


def main() -> int:
    parser = argparse.ArgumentParser(description="Audit local VPN plan readiness")
    parser.add_argument("--decision", default=str(DEFAULT_DECISION))
    parser.add_argument("--boot-gap", default=str(DEFAULT_BOOT_GAP))
    parser.add_argument("--provider-packet", default=str(DEFAULT_PROVIDER_PACKET))
    parser.add_argument("--history", default=str(DEFAULT_HISTORY))
    parser.add_argument("--refresh", default=str(DEFAULT_REFRESH))
    parser.add_argument("--operator-card", default=str(DEFAULT_OPERATOR_CARD))
    parser.add_argument("--failover", default=str(DEFAULT_FAILOVER))
    parser.add_argument("--transport-probe", default=str(DEFAULT_TRANSPORT_PROBE))
    parser.add_argument("--secondary", default=str(DEFAULT_SECONDARY))
    parser.add_argument("--manifest", default=str(DEFAULT_MANIFEST))
    parser.add_argument("--preflight-validator", default=str(DEFAULT_PREFLIGHT_VALIDATOR))
    parser.add_argument("--approval-doc", default=str(DEFAULT_APPROVAL_DOC))
    parser.add_argument("--json-out", default=str(DEFAULT_JSON_OUT))
    parser.add_argument("--markdown-out", default=str(DEFAULT_MARKDOWN_OUT))
    args = parser.parse_args()

    report_text_paths = [
        Path(args.refresh).with_suffix(".md"),
        Path(args.operator_card).with_suffix(".md"),
        Path(args.failover).with_suffix(".md"),
    ]
    inputs = {
        "decision": read_json(Path(args.decision)),
        "boot_gap": read_json(Path(args.boot_gap)),
        "provider_packet": read_json(Path(args.provider_packet)),
        "history": read_json(Path(args.history)),
        "refresh": read_json(Path(args.refresh)),
        "operator_card": read_json(Path(args.operator_card)),
        "failover": read_json(Path(args.failover)),
        "transport_probe": read_json(Path(args.transport_probe)),
        "secondary": read_json(Path(args.secondary)),
        "manifest": read_json(Path(args.manifest)),
        "preflight": run_preflight_validator(Path(args.preflight_validator)),
        "approval_text": read_text(Path(args.approval_doc)),
        "report_texts": [read_text(path) for path in report_text_paths],
    }
    payload = build_payload(inputs)
    if args.json_out:
        Path(args.json_out).write_text(json.dumps(payload, indent=2, ensure_ascii=False) + "\n", encoding="utf-8")
    if args.markdown_out:
        Path(args.markdown_out).write_text(render_markdown(payload), encoding="utf-8")
    if not args.json_out and not args.markdown_out:
        print(json.dumps(payload, indent=2, ensure_ascii=False))
    return 0 if payload["ok"] else 1


if __name__ == "__main__":
    raise SystemExit(main())
