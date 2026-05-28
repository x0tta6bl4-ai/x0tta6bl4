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
    / "provider-incident-packet-20260528T021824Z.json"
)
DEFAULT_HISTORY = DIAGNOSTICS_DIR / "blocking-probe-history-2026-05-28.json"
DEFAULT_REFRESH = DIAGNOSTICS_DIR / "vpn-planning-refresh-2026-05-28.json"
DEFAULT_OPERATOR_CARD = DIAGNOSTICS_DIR / "vpn-operator-card-2026-05-28.json"
DEFAULT_FAILOVER = DIAGNOSTICS_DIR / "manual-failover-plan-2026-05-28.json"
DEFAULT_FAILOVER_READINESS = DIAGNOSTICS_DIR / "manual-failover-readiness-2026-05-28.json"
DEFAULT_SECONDARY_SCORE = DIAGNOSTICS_DIR / "secondary-exit-candidate-score-2026-05-28.json"
DEFAULT_SECONDARY_REQUIREMENTS = DIAGNOSTICS_DIR / "secondary-exit-requirements-2026-05-28.json"
DEFAULT_SECONDARY_PROVIDER_SHORTLIST = DIAGNOSTICS_DIR / "secondary-exit-provider-shortlist-2026-05-28.json"
DEFAULT_SECONDARY_INTAKE = DIAGNOSTICS_DIR / "secondary-exit-candidate-intake-2026-05-28.json"
DEFAULT_SECONDARY_PROVISIONING_PLAN = DIAGNOSTICS_DIR / "secondary-exit-provisioning-plan-2026-05-28.json"
DEFAULT_SECONDARY_FLOW = DIAGNOSTICS_DIR / "secondary-exit-flow-2026-05-28.json"
DEFAULT_SECONDARY_MANUAL_DRILL = DIAGNOSTICS_DIR / "secondary-exit-manual-drill-2026-05-28.json"
DEFAULT_SECONDARY_SELECTION_PACKET = DIAGNOSTICS_DIR / "secondary-exit-selection-packet-2026-05-28.json"
DEFAULT_LOCAL_ENV = DIAGNOSTICS_DIR / "local-diagnostic-environment-2026-05-28.json"
DEFAULT_LOCAL_CLEANUP_PLAN = DIAGNOSTICS_DIR / "local-root-cleanup-plan-2026-05-28.json"
DEFAULT_LOCAL_CLEANUP_PACKET = DIAGNOSTICS_DIR / "local-root-cleanup-approval-packet-2026-05-28.json"
DEFAULT_INCIDENT_SYMPTOM_INTAKE = DIAGNOSTICS_DIR / "vpn-incident-symptom-intake-2026-05-28.json"
DEFAULT_TRANSPORT_PROBE = DIAGNOSTICS_DIR / "nl-transport-probe-2026-05-28.json"
DEFAULT_TRANSPORT_UPTIME = DIAGNOSTICS_DIR / "nl-transport-uptime-summary-2026-05-28.json"
DEFAULT_SECONDARY = DIAGNOSTICS_DIR / "secondary-exit-probe-template-2026-05-28.json"
DEFAULT_MANIFEST = ROOT / "services" / "nl-server" / "manifest.json"
DEFAULT_PREFLIGHT_VALIDATOR = ROOT / "services" / "nl-server" / "tools" / "validate_preflight_readiness.py"
DEFAULT_APPROVAL_DOC = DIAGNOSTICS_DIR / "nl-deploy-preflight-checklist-2026-05-27.md"
DEFAULT_JSON_OUT = DIAGNOSTICS_DIR / "vpn-plan-readiness-audit-2026-05-28.json"
DEFAULT_MARKDOWN_OUT = DIAGNOSTICS_DIR / "vpn-plan-readiness-audit-2026-05-28.md"

APPROVAL_PHRASE = "approve NL write for health shell split only"
SPB_TRUE_MARKER = re.compile(r"['\"]?spb_fallback_allowed['\"]?\s*[:=]\s*true\b", re.IGNORECASE)
EVIDENCE_MAX_AGE_SECONDS = 3600
FORBIDDEN_SYSTEMD_TEMPLATE_WORDS = re.compile(
    r"\b(ssh|scp|rsync|sudo|systemctl|restart|reload|enable|disable)\b",
    re.IGNORECASE,
)
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


def snapshot_age_seconds(snapshot_name: str, now: datetime | None = None) -> int | None:
    try:
        timestamp = datetime.strptime(snapshot_name, "%Y%m%dT%H%M%SZ").replace(tzinfo=timezone.utc)
    except ValueError:
        return None
    current = now or datetime.now(timezone.utc)
    return max(0, int((current - timestamp).total_seconds()))


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


def audit_snapshot_chain(
    decision: dict[str, Any],
    refresh: dict[str, Any],
    root: Path,
    *,
    now: datetime | None = None,
) -> dict[str, Any]:
    decision_snapshot = str(decision.get("snapshot") or "")
    refresh_snapshot = str(refresh.get("snapshot") or "")
    snapshot_path = resolve_path(decision_snapshot, root)
    latest = latest_snapshot(root / "nl-diagnostics" / "snapshots")
    latest_name = latest.name if latest else "missing"
    same_report_snapshot = bool(decision_snapshot and refresh_snapshot and decision_snapshot == refresh_snapshot)
    same_latest = bool(snapshot_path and latest and snapshot_path.name == latest.name)
    exists = path_exists(decision_snapshot, root)
    age_seconds = snapshot_age_seconds(Path(decision_snapshot).name, now) if decision_snapshot else None
    fresh = age_seconds is not None and age_seconds <= EVIDENCE_MAX_AGE_SECONDS

    if same_report_snapshot and same_latest and exists and fresh:
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
            f"snapshot_age_seconds={age_seconds if age_seconds is not None else 'missing'}",
            f"fresh={str(fresh).lower()}",
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


def audit_local_diagnostic_environment(local_env: dict[str, Any]) -> dict[str, Any]:
    status = str(local_env.get("status") or "missing")
    summary = local_env.get("summary") or {}
    safe = all_false(
        [
            flag_is_false(local_env, "nl_mutation_allowed"),
            flag_is_false(local_env, "spb_fallback_allowed"),
            flag_is_false(local_env, "automatic_failover_allowed"),
            summary.get("nl_write_allowed") is False,
            summary.get("spb_fallback_allowed") is False,
            summary.get("automatic_failover_allowed") is False,
        ]
    )
    tmpdir_writable = summary.get("diagnostic_tmpdir_writable") is True
    if status == "ok" and tmpdir_writable and safe:
        item_status = READY
    elif status in {"watch_root_full_tmpdir_available", "watch_disk_pressure"} and tmpdir_writable and safe:
        item_status = WATCH
    else:
        item_status = MISSING

    return item(
        item_id="LOCALENV-01",
        title="Local diagnostic host has a writable project temp directory",
        status=item_status,
        evidence=[
            f"local_environment_status={status}",
            f"root_status={summary.get('root_status', 'missing')}",
            f"root_used_percent={summary.get('root_used_percent', 'missing')}",
            f"root_free_gib={summary.get('root_free_gib', 'missing')}",
            f"tmp_status={summary.get('tmp_status', 'missing')}",
            f"diagnostic_tmpdir={summary.get('diagnostic_tmpdir', 'missing')}",
            f"diagnostic_tmpdir_writable={str(tmpdir_writable).lower()}",
            f"recommended_tmpdir_prefix={summary.get('recommended_tmpdir_prefix', 'missing')}",
            f"cleanup_required={str(summary.get('cleanup_required')).lower()}",
            f"safe_flags={str(safe).lower()}",
        ],
        next_step="keep using TMPDIR=/mnt/projects/.tmp and clean / only after separate local cleanup approval",
    )


def audit_local_root_cleanup_plan(cleanup_plan: dict[str, Any]) -> dict[str, Any]:
    status = str(cleanup_plan.get("status") or "missing")
    summary = cleanup_plan.get("summary") or {}
    safe = all_false(
        [
            flag_is_false(cleanup_plan, "cleanup_execute_allowed"),
            flag_is_false(cleanup_plan, "nl_mutation_allowed"),
            flag_is_false(cleanup_plan, "spb_fallback_allowed"),
            flag_is_false(cleanup_plan, "automatic_failover_allowed"),
            summary.get("cleanup_execute_allowed") is False,
            summary.get("nl_write_allowed") is False,
            summary.get("spb_fallback_allowed") is False,
            summary.get("automatic_failover_allowed") is False,
        ]
    )
    if status == "no_cleanup_needed" and safe:
        item_status = READY
    elif status in {
        "manual_cleanup_plan_ready",
        "manual_cleanup_plan_low_reclaim",
        "manual_cleanup_plan_no_candidates",
    } and safe:
        item_status = WATCH
    else:
        item_status = MISSING

    return item(
        item_id="LOCALCLEAN-01",
        title="Local root cleanup plan is prepared but execution is blocked",
        status=item_status,
        evidence=[
            f"cleanup_plan_status={status}",
            f"root_status={summary.get('root_status', 'missing')}",
            f"root_free_gib={summary.get('root_free_gib', 'missing')}",
            f"existing_candidate_count={summary.get('existing_candidate_count', 'missing')}",
            f"estimated_reclaim_gib={summary.get('estimated_reclaim_gib', 'missing')}",
            f"top_candidate_id={summary.get('top_candidate_id', 'missing')}",
            f"cleanup_execute_allowed={str(summary.get('cleanup_execute_allowed')).lower()}",
            f"safe_flags={str(safe).lower()}",
        ],
        next_step="review local cleanup candidates and execute cleanup only after separate local approval",
    )


def audit_local_root_cleanup_approval_packet(cleanup_packet: dict[str, Any]) -> dict[str, Any]:
    status = str(cleanup_packet.get("status") or "missing")
    summary = cleanup_packet.get("summary") or {}
    safe = all_false(
        [
            flag_is_false(cleanup_packet, "cleanup_execute_allowed"),
            flag_is_false(cleanup_packet, "nl_mutation_allowed"),
            flag_is_false(cleanup_packet, "spb_fallback_allowed"),
            flag_is_false(cleanup_packet, "automatic_failover_allowed"),
            summary.get("cleanup_execute_allowed") is False,
            summary.get("nl_write_allowed") is False,
            summary.get("spb_fallback_allowed") is False,
            summary.get("automatic_failover_allowed") is False,
            summary.get("commands_executed") == 0,
        ]
    )
    if status == "cleanup_approval_packet_no_cleanup_needed" and safe:
        item_status = READY
    elif status in {
        "cleanup_approval_packet_ready",
        "cleanup_approval_packet_watch_only",
        "cleanup_approval_packet_no_candidates",
    } and safe:
        item_status = READY
    else:
        item_status = MISSING

    return item(
        item_id="LOCALCLEAN-02",
        title="Local cleanup approval packet is prepared without executing commands",
        status=item_status,
        evidence=[
            f"cleanup_approval_packet_status={status}",
            f"first_review_id={summary.get('first_review_id', 'missing')}",
            f"command_preview_count={summary.get('command_preview_count', 'missing')}",
            f"approval_required={str(summary.get('approval_required')).lower()}",
            f"commands_executed={summary.get('commands_executed', 'missing')}",
            f"cleanup_execute_allowed={str(summary.get('cleanup_execute_allowed')).lower()}",
            f"safe_flags={str(safe).lower()}",
        ],
        next_step="run only prechecks now; execute cleanup previews only after separate local cleanup approval",
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


def audit_incident_symptom_intake(symptom_intake: dict[str, Any]) -> dict[str, Any]:
    status = str(symptom_intake.get("status") or "missing")
    summary = symptom_intake.get("summary") or {}
    required_field_count = int(summary.get("required_field_count") or 0)
    forbidden_material_count = int(summary.get("forbidden_material_count") or 0)
    safe = all_false(
        [
            flag_is_false(symptom_intake, "nl_mutation_allowed"),
            flag_is_false(symptom_intake, "spb_fallback_allowed"),
            flag_is_false(symptom_intake, "automatic_failover_allowed"),
            summary.get("nl_write_allowed") is False,
            summary.get("spb_fallback_allowed") is False,
            summary.get("automatic_failover_allowed") is False,
        ]
    )
    ready = (
        safe
        and status in {
            "symptom_intake_ready_observe",
            "symptom_intake_ready_incident",
            "symptom_intake_ready_review",
        }
        and required_field_count > 0
        and forbidden_material_count > 0
    )
    return item(
        item_id="INCIDENT-01",
        title="Incident symptom intake is safe to use without collecting secrets",
        status=READY if ready else MISSING,
        evidence=[
            f"incident_symptom_intake_status={status}",
            f"decision={summary.get('decision', 'missing')}",
            f"operator_status={summary.get('operator_status', 'missing')}",
            f"failure_domain={summary.get('failure_domain', 'missing')}",
            f"transport_status={summary.get('transport_status', 'missing')}",
            f"required_field_count={required_field_count}",
            f"forbidden_material_count={forbidden_material_count}",
            f"safe_flags={str(safe).lower()}",
        ],
        next_step="use this template for user-visible symptoms and reject any pasted VPN secrets",
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
            next_step="choose a new non-NL/non-SPB provider/region before any emergency profile test",
        ),
    ]


def audit_manual_failover_readiness(failover_readiness: dict[str, Any]) -> dict[str, Any]:
    status = str(failover_readiness.get("status") or "missing")
    summary = failover_readiness.get("summary") or {}
    safe = all_false(
        [
            flag_is_false(failover_readiness, "nl_mutation_allowed"),
            flag_is_false(failover_readiness, "spb_fallback_allowed"),
            flag_is_false(failover_readiness, "automatic_failover_allowed"),
            summary.get("nl_write_allowed") is False,
            summary.get("automatic_failover_allowed") is False,
            summary.get("spb_excluded") is True,
        ]
    )
    if status == "missing" or not safe:
        item_status = MISSING
    elif failover_readiness.get("manual_switch_allowed") is True:
        item_status = READY
    else:
        item_status = BLOCKED
    return item(
        item_id="FAILOVER-03",
        title="Manual failover readiness gate blocks unsafe switching",
        status=item_status,
        evidence=[
            f"manual_failover_readiness_status={status}",
            f"manual_probe_allowed={str(failover_readiness.get('manual_probe_allowed')).lower()}",
            f"manual_switch_allowed={str(failover_readiness.get('manual_switch_allowed')).lower()}",
            f"secondary_probe_status={summary.get('secondary_probe_status', 'missing')}",
            f"candidate_configured={str(summary.get('candidate_configured')).lower()}",
            f"spb_excluded={str(summary.get('spb_excluded')).lower()}",
            f"safe_flags={str(safe).lower()}",
        ],
        next_step="keep manual switch blocked until a fresh incident trigger and healthy non-NL/non-SPB secondary exist",
    )


def audit_secondary_exit_requirements(secondary_requirements: dict[str, Any]) -> dict[str, Any]:
    status = str(secondary_requirements.get("status") or "missing")
    summary = secondary_requirements.get("summary") or {}
    missing_items = summary.get("missing_items") if isinstance(summary.get("missing_items"), list) else []
    blocked_items = summary.get("blocked_items") if isinstance(summary.get("blocked_items"), list) else []
    safe = all_false(
        [
            flag_is_false(secondary_requirements, "nl_mutation_allowed"),
            flag_is_false(secondary_requirements, "spb_fallback_allowed"),
            flag_is_false(secondary_requirements, "automatic_failover_allowed"),
            summary.get("nl_write_allowed") is False,
            summary.get("spb_fallback_allowed") is False,
            summary.get("automatic_failover_allowed") is False,
        ]
    )
    ready = safe and status in {"requirements_ready_no_candidate", "requirements_ready_with_candidate"} and not blocked_items
    return item(
        item_id="FAILOVER-04",
        title="Secondary exit requirements are documented without secrets",
        status=READY if ready else MISSING,
        evidence=[
            f"secondary_exit_requirements_status={status}",
            f"candidate_configured={str(summary.get('candidate_configured')).lower()}",
            f"missing_items={','.join(str(value) for value in missing_items) or 'none'}",
            f"blocked_items={','.join(str(value) for value in blocked_items) or 'none'}",
            f"manual_switch_allowed={str(summary.get('manual_switch_allowed')).lower()}",
            f"safe_flags={str(safe).lower()}",
        ],
        next_step="choose a real non-NL/non-SPB provider/region and fill only public endpoint metadata",
    )


def audit_secondary_candidate_score(secondary_score: dict[str, Any]) -> dict[str, Any]:
    status = str(secondary_score.get("status") or "missing")
    summary = secondary_score.get("summary") or {}
    safe = all_false(
        [
            flag_is_false(secondary_score, "nl_mutation_allowed"),
            flag_is_false(secondary_score, "spb_fallback_allowed"),
            flag_is_false(secondary_score, "automatic_failover_allowed"),
            summary.get("nl_write_allowed") is False,
            summary.get("spb_fallback_allowed") is False,
            summary.get("automatic_failover_allowed") is False,
        ]
    )
    ready = safe and status in {"missing_candidates", "candidate_pool_ready", "candidate_pool_no_viable"}
    return item(
        item_id="FAILOVER-05",
        title="Secondary candidate scorer is available before provider choice",
        status=READY if ready else MISSING,
        evidence=[
            f"secondary_candidate_score_status={status}",
            f"candidate_count={summary.get('candidate_count', 'missing')}",
            f"viable_count={summary.get('viable_count', 'missing')}",
            f"rejected_count={summary.get('rejected_count', 'missing')}",
            f"top_candidate_label={summary.get('top_candidate_label', 'missing')}",
            f"safe_flags={str(safe).lower()}",
        ],
        next_step="score only public metadata for non-NL/non-SPB candidates before generating a probe config",
    )


def audit_secondary_candidate_intake(secondary_intake: dict[str, Any]) -> dict[str, Any]:
    status = str(secondary_intake.get("status") or "missing")
    summary = secondary_intake.get("summary") or {}
    safe = all_false(
        [
            flag_is_false(secondary_intake, "nl_mutation_allowed"),
            flag_is_false(secondary_intake, "spb_fallback_allowed"),
            flag_is_false(secondary_intake, "automatic_failover_allowed"),
            summary.get("nl_write_allowed") is False,
            summary.get("spb_fallback_allowed") is False,
            summary.get("automatic_failover_allowed") is False,
        ]
    )
    ready = safe and status in {
        "awaiting_public_candidate_metadata",
        "candidate_metadata_needs_fix",
        "candidate_metadata_ready",
        "candidate_file_needs_secret_cleanup",
    }
    return item(
        item_id="FAILOVER-07",
        title="Secondary candidate intake checklist exists without secrets",
        status=READY if ready else MISSING,
        evidence=[
            f"secondary_candidate_intake_status={status}",
            f"candidate_file={summary.get('candidate_file', 'missing')}",
            f"candidate_count={summary.get('candidate_count', 'missing')}",
            f"viable_count={summary.get('viable_count', 'missing')}",
            f"allowed_field_count={summary.get('allowed_field_count', 'missing')}",
            f"forbidden_material_count={summary.get('forbidden_material_count', 'missing')}",
            f"safe_flags={str(safe).lower()}",
        ],
        next_step="fill only public metadata in the local candidate file, then rerun scorer and refresh",
    )


def audit_secondary_provider_shortlist(provider_shortlist: dict[str, Any]) -> dict[str, Any]:
    status = str(provider_shortlist.get("status") or "missing")
    summary = provider_shortlist.get("summary") or {}
    shortlist_count = int(summary.get("shortlist_count") or 0)
    endpoint_count = int(summary.get("endpoint_count") or 0)
    invalid_source_refs = summary.get("invalid_source_refs") if isinstance(summary.get("invalid_source_refs"), list) else []
    safe = all_false(
        [
            flag_is_false(provider_shortlist, "nl_mutation_allowed"),
            flag_is_false(provider_shortlist, "spb_fallback_allowed"),
            flag_is_false(provider_shortlist, "automatic_failover_allowed"),
            summary.get("nl_write_allowed") is False,
            summary.get("spb_fallback_allowed") is False,
            summary.get("automatic_failover_allowed") is False,
        ]
    )
    ready = (
        safe
        and status == "shortlist_ready_no_endpoint"
        and shortlist_count > 0
        and endpoint_count == 0
        and not invalid_source_refs
    )
    return item(
        item_id="FAILOVER-08",
        title="Secondary provider shortlist exists without endpoint secrets",
        status=READY if ready else MISSING,
        evidence=[
            f"secondary_provider_shortlist_status={status}",
            f"shortlist_count={shortlist_count}",
            f"source_count={summary.get('source_count', 'missing')}",
            f"endpoint_count={endpoint_count}",
            f"candidate_configured={str(summary.get('candidate_configured')).lower()}",
            f"invalid_source_refs={','.join(str(value) for value in invalid_source_refs) or 'none'}",
            f"safe_flags={str(safe).lower()}",
        ],
        next_step="provision one shortlisted non-NL/non-SPB option, then add only public host/IP metadata",
    )


def audit_secondary_provisioning_plan(provisioning_plan: dict[str, Any]) -> dict[str, Any]:
    status = str(provisioning_plan.get("status") or "missing")
    summary = provisioning_plan.get("summary") or {}
    endpoint_count = int(summary.get("endpoint_count") or 0)
    preferred_labels = summary.get("preferred_labels") if isinstance(summary.get("preferred_labels"), list) else []
    safe = all_false(
        [
            flag_is_false(provisioning_plan, "nl_mutation_allowed"),
            flag_is_false(provisioning_plan, "spb_fallback_allowed"),
            flag_is_false(provisioning_plan, "automatic_failover_allowed"),
            summary.get("nl_write_allowed") is False,
            summary.get("spb_fallback_allowed") is False,
            summary.get("automatic_failover_allowed") is False,
            summary.get("safe_sources") is True,
        ]
    )
    ready = (
        safe
        and status == "provisioning_plan_ready_no_endpoint"
        and summary.get("external_action_required") is True
        and endpoint_count == 0
        and bool(preferred_labels)
    )
    return item(
        item_id="FAILOVER-09",
        title="Secondary provisioning plan blocks secrets and automation",
        status=READY if ready else MISSING,
        evidence=[
            f"secondary_provisioning_plan_status={status}",
            f"preferred_labels={','.join(str(value) for value in preferred_labels) or 'none'}",
            f"endpoint_count={endpoint_count}",
            f"external_action_required={str(summary.get('external_action_required')).lower()}",
            f"candidate_file={summary.get('candidate_file', 'missing')}",
            f"safe_sources={str(summary.get('safe_sources')).lower()}",
            f"safe_flags={str(safe).lower()}",
        ],
        next_step="perform the provider-console provisioning step externally, then store only public endpoint metadata",
    )


def audit_secondary_exit_flow(secondary_flow: dict[str, Any]) -> dict[str, Any]:
    status = str(secondary_flow.get("status") or "missing")
    summary = secondary_flow.get("summary") or {}
    safe = all_false(
        [
            flag_is_false(secondary_flow, "nl_mutation_allowed"),
            flag_is_false(secondary_flow, "spb_fallback_allowed"),
            flag_is_false(secondary_flow, "automatic_failover_allowed"),
            summary.get("nl_write_allowed") is False,
            summary.get("spb_fallback_allowed") is False,
            summary.get("automatic_failover_allowed") is False,
            summary.get("safe_flags") is True,
        ]
    )
    if not safe or status == "missing":
        item_status = MISSING
    elif status == "ready_for_manual_switch":
        item_status = READY
    elif status in {
        "blocked_missing_candidate",
        "candidate_ready_probe_config_needed",
        "candidate_configured_probe_needed",
    }:
        item_status = BLOCKED
    else:
        item_status = WATCH

    return item(
        item_id="FAILOVER-06",
        title="Secondary exit operating flow blocks unsafe activation",
        status=item_status,
        evidence=[
            f"secondary_exit_flow_status={status}",
            f"candidate_viable_count={summary.get('candidate_viable_count', 'missing')}",
            f"candidate_configured={str(summary.get('candidate_configured')).lower()}",
            f"secondary_probe_status={summary.get('secondary_probe_status', 'missing')}",
            f"manual_probe_allowed={str(summary.get('manual_probe_allowed')).lower()}",
            f"manual_switch_allowed={str(summary.get('manual_switch_allowed')).lower()}",
            f"safe_flags={str(safe).lower()}",
        ],
        next_step="fill public metadata for a non-NL/non-SPB candidate, then generate and run the safe probe config",
    )


def audit_secondary_manual_drill(secondary_drill: dict[str, Any]) -> dict[str, Any]:
    status = str(secondary_drill.get("status") or "missing")
    summary = secondary_drill.get("summary") or {}
    safe = all_false(
        [
            flag_is_false(secondary_drill, "nl_mutation_allowed"),
            flag_is_false(secondary_drill, "spb_fallback_allowed"),
            flag_is_false(secondary_drill, "automatic_failover_allowed"),
            summary.get("nl_write_allowed") is False,
            summary.get("spb_fallback_allowed") is False,
            summary.get("automatic_failover_allowed") is False,
            summary.get("safe_flags") is True,
            summary.get("bulk_user_switch_allowed") is False,
            summary.get("rollback_required") is True,
        ]
    )
    ready = safe and status in {
        "drill_plan_ready_blocked_no_endpoint",
        "drill_ready_for_test_client_only",
        "drill_ready_for_manual_switch",
    }
    return item(
        item_id="FAILOVER-10",
        title="Secondary manual drill is test-only and rollback-gated",
        status=READY if ready else MISSING,
        evidence=[
            f"secondary_manual_drill_status={status}",
            f"manual_probe_allowed={str(summary.get('manual_probe_allowed')).lower()}",
            f"manual_switch_allowed={str(summary.get('manual_switch_allowed')).lower()}",
            f"test_scope={summary.get('test_scope', 'missing')}",
            f"bulk_user_switch_allowed={str(summary.get('bulk_user_switch_allowed')).lower()}",
            f"rollback_required={str(summary.get('rollback_required')).lower()}",
            f"safe_flags={str(safe).lower()}",
        ],
        next_step="after a secondary endpoint exists, run the drill on one test client and roll back to NL",
    )


def audit_secondary_selection_packet(selection_packet: dict[str, Any]) -> dict[str, Any]:
    status = str(selection_packet.get("status") or "missing")
    summary = selection_packet.get("summary") or {}
    decision_option_count = int(summary.get("decision_option_count") or 0)
    endpoint_count = int(summary.get("endpoint_count") or 0)
    safe = all_false(
        [
            flag_is_false(selection_packet, "nl_mutation_allowed"),
            flag_is_false(selection_packet, "spb_fallback_allowed"),
            flag_is_false(selection_packet, "automatic_failover_allowed"),
            summary.get("nl_write_allowed") is False,
            summary.get("spb_fallback_allowed") is False,
            summary.get("automatic_failover_allowed") is False,
            summary.get("may_create_endpoint_now") is False,
            summary.get("external_action_required") is True,
        ]
    )
    ready = (
        safe
        and status in {"selection_packet_ready_no_endpoint", "selection_packet_ready_review_endpoint"}
        and decision_option_count > 0
    )
    return item(
        item_id="FAILOVER-11",
        title="Secondary provider selection packet gives a safe decision order",
        status=READY if ready else MISSING,
        evidence=[
            f"secondary_selection_packet_status={status}",
            f"recommended_label={summary.get('recommended_label', 'missing')}",
            f"backup_label={summary.get('backup_label', 'missing')}",
            f"decision_option_count={decision_option_count}",
            f"endpoint_count={endpoint_count}",
            f"may_create_endpoint_now={str(summary.get('may_create_endpoint_now')).lower()}",
            f"safe_flags={str(safe).lower()}",
        ],
        next_step="pick the primary label externally, then store only public endpoint metadata after provisioning",
    )


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


def audit_transport_uptime(transport_uptime: dict[str, Any]) -> dict[str, Any]:
    summary = transport_uptime.get("summary") or {}
    status = str(summary.get("status") or "missing")
    sample_count = int(summary.get("sample_count") or 0)
    bad_streak = int(summary.get("consecutive_non_healthy") or 0)
    safe = all_false(
        [
            flag_is_false(transport_uptime, "nl_mutation_allowed"),
            flag_is_false(transport_uptime, "spb_fallback_allowed"),
            flag_is_false(transport_uptime, "automatic_failover_allowed"),
        ]
    )
    if not safe or status == "missing" or sample_count <= 0:
        item_status = MISSING
    elif status == "stable_healthy":
        item_status = READY
    else:
        item_status = WATCH
    return item(
        item_id="UPTIME-01",
        title="Outside-in NL TCP uptime history is recorded locally",
        status=item_status,
        evidence=[
            f"uptime_status={status}",
            f"sample_count={sample_count}",
            f"latest_status={summary.get('latest_status', 'missing')}",
            f"consecutive_non_healthy={bad_streak}",
            f"safe_flags={str(safe).lower()}",
        ],
        next_step="if uptime history becomes watch, collect a fresh read-only snapshot and provider packet",
    )


def audit_scheduler_templates(root: Path) -> dict[str, Any]:
    service = root / "infra/systemd/x0tta-vpn-nl-transport-uptime.service"
    timer = root / "infra/systemd/x0tta-vpn-nl-transport-uptime.timer"
    service_text = read_text(service)
    timer_text = read_text(timer)
    exists = service.exists() and timer.exists()
    expected = (
        "probe_nl_transport_ports.py" in service_text
        and "record_nl_transport_uptime.py" in service_text
        and "Environment=TMPDIR=/mnt/projects/.tmp" in service_text
        and "OnUnitActiveSec=5min" in timer_text
        and "Unit=x0tta-vpn-nl-transport-uptime.service" in timer_text
    )
    forbidden = FORBIDDEN_SYSTEMD_TEMPLATE_WORDS.search(service_text + "\n" + timer_text)
    ready = exists and expected and forbidden is None
    return item(
        item_id="SCHEDULER-01",
        title="Local uptime systemd timer templates are prepared but not installed",
        status=READY if ready else MISSING,
        evidence=[
            f"service_exists={str(service.exists()).lower()}",
            f"timer_exists={str(timer.exists()).lower()}",
            f"expected_commands={str(expected).lower()}",
            f"tmpdir_environment={'Environment=TMPDIR=/mnt/projects/.tmp' if 'Environment=TMPDIR=/mnt/projects/.tmp' in service_text else 'missing'}",
            f"forbidden_word={forbidden.group(1) if forbidden else 'none'}",
        ],
        next_step="install/enable the local timer only after separate local host approval",
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


def build_payload(inputs: dict[str, Any], *, root: Path = ROOT, now: datetime | None = None) -> dict[str, Any]:
    decision = inputs.get("decision") or {}
    boot_gap = inputs.get("boot_gap") or {}
    provider_packet = inputs.get("provider_packet") or {}
    history = inputs.get("history") or {}
    refresh = inputs.get("refresh") or {}
    operator_card = inputs.get("operator_card") or {}
    failover = inputs.get("failover") or {}
    failover_readiness = inputs.get("failover_readiness") or {}
    secondary_score = inputs.get("secondary_score") or {}
    secondary_requirements = inputs.get("secondary_requirements") or {}
    secondary_provider_shortlist = inputs.get("secondary_provider_shortlist") or {}
    secondary_intake = inputs.get("secondary_intake") or {}
    secondary_provisioning_plan = inputs.get("secondary_provisioning_plan") or {}
    secondary_flow = inputs.get("secondary_flow") or {}
    secondary_manual_drill = inputs.get("secondary_manual_drill") or {}
    secondary_selection_packet = inputs.get("secondary_selection_packet") or {}
    local_env = inputs.get("local_env") or {}
    local_cleanup_plan = inputs.get("local_cleanup_plan") or {}
    local_cleanup_packet = inputs.get("local_cleanup_packet") or {}
    symptom_intake = inputs.get("symptom_intake") or {}
    transport_probe = inputs.get("transport_probe") or {}
    transport_uptime = inputs.get("transport_uptime") or {}
    secondary = inputs.get("secondary") or {}
    manifest = inputs.get("manifest") or {}
    preflight = inputs.get("preflight") or {}
    approval_text = str(inputs.get("approval_text") or "")
    report_texts = [str(text) for text in inputs.get("report_texts") or []]

    items: list[dict[str, Any]] = [
        audit_snapshot_chain(decision, refresh, root, now=now),
        audit_decision_guard(decision),
        audit_boot_gap_watch(boot_gap),
        audit_provider_packet(provider_packet, decision),
        audit_blocking_history(history, decision),
        audit_refresh(refresh),
        audit_local_diagnostic_environment(local_env),
        audit_local_root_cleanup_plan(local_cleanup_plan),
        audit_local_root_cleanup_approval_packet(local_cleanup_packet),
        audit_operator_card(operator_card),
        audit_incident_symptom_intake(symptom_intake),
        audit_manual_failover_readiness(failover_readiness),
        audit_secondary_candidate_score(secondary_score),
        audit_secondary_exit_requirements(secondary_requirements),
        audit_secondary_provider_shortlist(secondary_provider_shortlist),
        audit_secondary_candidate_intake(secondary_intake),
        audit_secondary_provisioning_plan(secondary_provisioning_plan),
        audit_secondary_exit_flow(secondary_flow),
        audit_secondary_manual_drill(secondary_manual_drill),
        audit_secondary_selection_packet(secondary_selection_packet),
        audit_transport_probe(transport_probe),
        audit_transport_uptime(transport_uptime),
        audit_scheduler_templates(root),
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
            "manual_failover_readiness_status": failover_readiness.get("status", "missing"),
            "manual_failover_switch_allowed": failover_readiness.get("manual_switch_allowed", "missing"),
            "secondary_candidate_score_status": secondary_score.get("status", "missing"),
            "secondary_exit_requirements_status": secondary_requirements.get("status", "missing"),
            "secondary_provider_shortlist_status": secondary_provider_shortlist.get("status", "missing"),
            "secondary_provider_shortlist_count": (
                secondary_provider_shortlist.get("summary") or {}
            ).get("shortlist_count", "missing"),
            "secondary_provider_shortlist_endpoint_count": (
                secondary_provider_shortlist.get("summary") or {}
            ).get("endpoint_count", "missing"),
            "secondary_candidate_intake_status": secondary_intake.get("status", "missing"),
            "secondary_provisioning_plan_status": secondary_provisioning_plan.get("status", "missing"),
            "secondary_provisioning_external_action_required": (
                secondary_provisioning_plan.get("summary") or {}
            ).get("external_action_required", "missing"),
            "secondary_provisioning_endpoint_count": (
                secondary_provisioning_plan.get("summary") or {}
            ).get("endpoint_count", "missing"),
            "secondary_exit_flow_status": secondary_flow.get("status", "missing"),
            "secondary_exit_flow_candidate_configured": (
                secondary_flow.get("summary") or {}
            ).get("candidate_configured", "missing"),
            "secondary_exit_flow_manual_switch_allowed": (
                secondary_flow.get("summary") or {}
            ).get("manual_switch_allowed", "missing"),
            "secondary_manual_drill_status": secondary_manual_drill.get("status", "missing"),
            "secondary_manual_drill_test_scope": (
                secondary_manual_drill.get("summary") or {}
            ).get("test_scope", "missing"),
            "secondary_manual_drill_rollback_required": (
                secondary_manual_drill.get("summary") or {}
            ).get("rollback_required", "missing"),
            "secondary_selection_packet_status": secondary_selection_packet.get("status", "missing"),
            "secondary_selection_recommended_label": (
                secondary_selection_packet.get("summary") or {}
            ).get("recommended_label", "missing"),
            "secondary_selection_backup_label": (
                secondary_selection_packet.get("summary") or {}
            ).get("backup_label", "missing"),
            "secondary_selection_option_count": (
                secondary_selection_packet.get("summary") or {}
            ).get("decision_option_count", "missing"),
            "secondary_selection_may_create_endpoint_now": (
                secondary_selection_packet.get("summary") or {}
            ).get("may_create_endpoint_now", "missing"),
            "local_diagnostic_environment_status": local_env.get("status", "missing"),
            "local_root_status": (local_env.get("summary") or {}).get("root_status", "missing"),
            "local_tmpdir_writable": (local_env.get("summary") or {}).get("diagnostic_tmpdir_writable", "missing"),
            "local_root_cleanup_plan_status": local_cleanup_plan.get("status", "missing"),
            "local_root_cleanup_estimated_reclaim_gib": (
                local_cleanup_plan.get("summary") or {}
            ).get("estimated_reclaim_gib", "missing"),
            "local_root_cleanup_execute_allowed": (
                local_cleanup_plan.get("summary") or {}
            ).get("cleanup_execute_allowed", "missing"),
            "local_root_cleanup_approval_packet_status": local_cleanup_packet.get("status", "missing"),
            "local_root_cleanup_approval_required": (
                local_cleanup_packet.get("summary") or {}
            ).get("approval_required", "missing"),
            "local_root_cleanup_commands_executed": (
                local_cleanup_packet.get("summary") or {}
            ).get("commands_executed", "missing"),
            "incident_symptom_intake_status": symptom_intake.get("status", "missing"),
            "incident_symptom_required_fields": (
                symptom_intake.get("summary") or {}
            ).get("required_field_count", "missing"),
            "incident_symptom_forbidden_material": (
                symptom_intake.get("summary") or {}
            ).get("forbidden_material_count", "missing"),
            "transport_probe_status": transport_probe.get("status", "missing"),
            "transport_uptime_status": (transport_uptime.get("summary") or {}).get("status", "missing"),
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
        f"manual_failover_readiness_status={summary.get('manual_failover_readiness_status')}",
        f"manual_failover_switch_allowed={summary.get('manual_failover_switch_allowed')}",
        f"secondary_candidate_score_status={summary.get('secondary_candidate_score_status')}",
        f"secondary_exit_requirements_status={summary.get('secondary_exit_requirements_status')}",
        f"secondary_provider_shortlist_status={summary.get('secondary_provider_shortlist_status')}",
        f"secondary_provider_shortlist_count={summary.get('secondary_provider_shortlist_count')}",
        f"secondary_provider_shortlist_endpoint_count={summary.get('secondary_provider_shortlist_endpoint_count')}",
        f"secondary_candidate_intake_status={summary.get('secondary_candidate_intake_status')}",
        f"secondary_provisioning_plan_status={summary.get('secondary_provisioning_plan_status')}",
        f"secondary_provisioning_external_action_required={summary.get('secondary_provisioning_external_action_required')}",
        f"secondary_provisioning_endpoint_count={summary.get('secondary_provisioning_endpoint_count')}",
        f"secondary_exit_flow_status={summary.get('secondary_exit_flow_status')}",
        f"secondary_exit_flow_candidate_configured={summary.get('secondary_exit_flow_candidate_configured')}",
        f"secondary_exit_flow_manual_switch_allowed={summary.get('secondary_exit_flow_manual_switch_allowed')}",
        f"secondary_manual_drill_status={summary.get('secondary_manual_drill_status')}",
        f"secondary_manual_drill_test_scope={summary.get('secondary_manual_drill_test_scope')}",
        f"secondary_manual_drill_rollback_required={summary.get('secondary_manual_drill_rollback_required')}",
        f"secondary_selection_packet_status={summary.get('secondary_selection_packet_status')}",
        f"secondary_selection_recommended_label={summary.get('secondary_selection_recommended_label')}",
        f"secondary_selection_backup_label={summary.get('secondary_selection_backup_label')}",
        f"secondary_selection_option_count={summary.get('secondary_selection_option_count')}",
        f"secondary_selection_may_create_endpoint_now={summary.get('secondary_selection_may_create_endpoint_now')}",
        f"local_diagnostic_environment_status={summary.get('local_diagnostic_environment_status')}",
        f"local_root_status={summary.get('local_root_status')}",
        f"local_tmpdir_writable={summary.get('local_tmpdir_writable')}",
        f"local_root_cleanup_plan_status={summary.get('local_root_cleanup_plan_status')}",
        f"local_root_cleanup_estimated_reclaim_gib={summary.get('local_root_cleanup_estimated_reclaim_gib')}",
        f"local_root_cleanup_execute_allowed={summary.get('local_root_cleanup_execute_allowed')}",
        f"local_root_cleanup_approval_packet_status={summary.get('local_root_cleanup_approval_packet_status')}",
        f"local_root_cleanup_approval_required={summary.get('local_root_cleanup_approval_required')}",
        f"local_root_cleanup_commands_executed={summary.get('local_root_cleanup_commands_executed')}",
        f"incident_symptom_intake_status={summary.get('incident_symptom_intake_status')}",
        f"incident_symptom_required_fields={summary.get('incident_symptom_required_fields')}",
        f"incident_symptom_forbidden_material={summary.get('incident_symptom_forbidden_material')}",
        f"transport_probe_status={summary.get('transport_probe_status')}",
        f"transport_uptime_status={summary.get('transport_uptime_status')}",
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
    parser.add_argument("--failover-readiness", default=str(DEFAULT_FAILOVER_READINESS))
    parser.add_argument("--secondary-score", default=str(DEFAULT_SECONDARY_SCORE))
    parser.add_argument("--secondary-requirements", default=str(DEFAULT_SECONDARY_REQUIREMENTS))
    parser.add_argument("--secondary-provider-shortlist", default=str(DEFAULT_SECONDARY_PROVIDER_SHORTLIST))
    parser.add_argument("--secondary-intake", default=str(DEFAULT_SECONDARY_INTAKE))
    parser.add_argument("--secondary-provisioning-plan", default=str(DEFAULT_SECONDARY_PROVISIONING_PLAN))
    parser.add_argument("--secondary-flow", default=str(DEFAULT_SECONDARY_FLOW))
    parser.add_argument("--secondary-manual-drill", default=str(DEFAULT_SECONDARY_MANUAL_DRILL))
    parser.add_argument("--secondary-selection-packet", default=str(DEFAULT_SECONDARY_SELECTION_PACKET))
    parser.add_argument("--local-env", default=str(DEFAULT_LOCAL_ENV))
    parser.add_argument("--local-cleanup-plan", default=str(DEFAULT_LOCAL_CLEANUP_PLAN))
    parser.add_argument("--local-cleanup-packet", default=str(DEFAULT_LOCAL_CLEANUP_PACKET))
    parser.add_argument("--incident-symptom-intake", default=str(DEFAULT_INCIDENT_SYMPTOM_INTAKE))
    parser.add_argument("--transport-probe", default=str(DEFAULT_TRANSPORT_PROBE))
    parser.add_argument("--transport-uptime", default=str(DEFAULT_TRANSPORT_UPTIME))
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
        Path(args.incident_symptom_intake).with_suffix(".md"),
        Path(args.secondary_selection_packet).with_suffix(".md"),
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
        "failover_readiness": read_json(Path(args.failover_readiness)),
        "secondary_score": read_json(Path(args.secondary_score)),
        "secondary_requirements": read_json(Path(args.secondary_requirements)),
        "secondary_provider_shortlist": read_json(Path(args.secondary_provider_shortlist)),
        "secondary_intake": read_json(Path(args.secondary_intake)),
        "secondary_provisioning_plan": read_json(Path(args.secondary_provisioning_plan)),
        "secondary_flow": read_json(Path(args.secondary_flow)),
        "secondary_manual_drill": read_json(Path(args.secondary_manual_drill)),
        "secondary_selection_packet": read_json(Path(args.secondary_selection_packet)),
        "local_env": read_json(Path(args.local_env)),
        "local_cleanup_plan": read_json(Path(args.local_cleanup_plan)),
        "local_cleanup_packet": read_json(Path(args.local_cleanup_packet)),
        "symptom_intake": read_json(Path(args.incident_symptom_intake)),
        "transport_probe": read_json(Path(args.transport_probe)),
        "transport_uptime": read_json(Path(args.transport_uptime)),
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
