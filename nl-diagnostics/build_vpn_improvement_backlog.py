#!/usr/bin/env python3
"""Build a local VPN improvement backlog from current evidence.

This script reads local reports only. It does not connect to NL and does not
change local or remote VPN runtime state.
"""

from __future__ import annotations

import argparse
from datetime import datetime, timezone
import json
from pathlib import Path
from typing import Any


ROOT = Path("/mnt/projects")
DIAGNOSTICS_DIR = ROOT / "nl-diagnostics"
DEFAULT_DECISION = DIAGNOSTICS_DIR / "current-vpn-decision-2026-05-28.json"
DEFAULT_BLOCKING_HISTORY = DIAGNOSTICS_DIR / "blocking-probe-history-2026-05-28.json"
DEFAULT_MANIFEST = ROOT / "services" / "nl-server" / "manifest.json"
DEFAULT_JSON_OUT = DIAGNOSTICS_DIR / "vpn-improvement-backlog-2026-05-28.json"
DEFAULT_MARKDOWN_OUT = DIAGNOSTICS_DIR / "vpn-improvement-backlog-2026-05-28.md"


def read_json(path: Path) -> dict[str, Any]:
    try:
        value = json.loads(path.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError):
        return {}
    return value if isinstance(value, dict) else {}


def current_summary(decision: dict[str, Any], history: dict[str, Any], manifest: dict[str, Any]) -> dict[str, Any]:
    decision_data = decision.get("decision") or {}
    classification = decision.get("classification") or {}
    history_summary = history.get("summary") or {}
    gap_summary = manifest.get("gap_summary") or {}
    source_status = manifest.get("source_promotion_status") or {}
    return {
        "decision": decision_data.get("decision", "unknown"),
        "decision_confidence": decision_data.get("confidence", "unknown"),
        "overall_status": classification.get("overall_status", "unknown"),
        "transport_status": classification.get("transport_status", "unknown"),
        "telegram_media_status": classification.get("telegram_media_status", "unknown"),
        "provider_status": classification.get("provider_status", "unknown"),
        "failure_domain": classification.get("failure_domain", "unknown"),
        "blocking_history_trend": history_summary.get("trend", "unknown"),
        "blocking_history_snapshot_count": history_summary.get("snapshot_count", 0),
        "source_gap_summary": gap_summary,
        "promoted_source_count": source_status.get("promoted_count", 0),
        "nl_write_allowed": bool(manifest.get("nl_write_allowed", False)),
        "deployable_to_nl": bool(source_status.get("deployable_to_nl", False)),
        "spb_fallback_allowed": False,
    }


def item(
    *,
    task_id: str,
    phase: str,
    priority: str,
    title: str,
    status: str,
    allowed_now: bool,
    nl_write_required: bool,
    reason: str,
    evidence: list[str],
    next_steps: list[str],
    acceptance: list[str],
) -> dict[str, Any]:
    return {
        "id": task_id,
        "phase": phase,
        "priority": priority,
        "title": title,
        "status": status,
        "allowed_now": allowed_now,
        "mutation_allowed": False,
        "nl_mutation_allowed": False,
        "nl_write_required": nl_write_required,
        "spb_fallback_allowed": False,
        "reason": reason,
        "evidence": evidence,
        "next_steps": next_steps,
        "acceptance": acceptance,
    }


def build_items(summary: dict[str, Any]) -> list[dict[str, Any]]:
    decision = str(summary.get("decision"))
    transport = str(summary.get("transport_status"))
    blocking_trend = str(summary.get("blocking_history_trend"))
    provider = str(summary.get("provider_status"))
    promoted_count = int(summary.get("promoted_source_count") or 0)

    local_status = "ready"
    if decision not in {"observe", "operator_review"}:
        local_status = "watch"

    items = [
        item(
            task_id="LOCAL-01",
            phase="local_now",
            priority="P0",
            title="Keep one-command read-only evidence collection as the first response",
            status=local_status,
            allowed_now=True,
            nl_write_required=False,
            reason="Fresh evidence prevents restarting NL for app-only or provider symptoms.",
            evidence=[
                f"decision={decision}",
                f"transport_status={transport}",
                "collector=nl-diagnostics/collect_vpn_readonly_snapshot.sh",
            ],
            next_steps=[
                "run VPN_ENABLE_BLOCKING_PROBES=1 nl-diagnostics/collect_vpn_readonly_snapshot.sh during the next visible outage",
                "classify the new snapshot before any heal/restart decision",
                "rebuild nl-diagnostics/current-vpn-decision-2026-05-28.md from the new snapshot",
            ],
            acceptance=[
                "snapshot exists under nl-diagnostics/snapshots/",
                "classification has mutation_allowed=false and nl_mutation_allowed=false",
                "decision report says observe/local_fix/provider_ticket/operator_review with explicit blocked actions",
            ],
        ),
        item(
            task_id="LOCAL-02",
            phase="local_now",
            priority="P0",
            title="Keep blocking/app probes as trend evidence, not restart triggers",
            status="ready" if blocking_trend == "stable_no_probe_evidence" else "watch",
            allowed_now=True,
            nl_write_required=False,
            reason="Current app/path probe history does not prove an x-ui outage.",
            evidence=[
                f"blocking_history_trend={blocking_trend}",
                f"blocking_history_snapshot_count={summary.get('blocking_history_snapshot_count')}",
            ],
            next_steps=[
                "keep nl-diagnostics/blocking_probe_targets.json as the default target set",
                "add only non-secret public targets when a user reports a new app-specific failure",
                "do not restart x-ui from direct-vs-SOCKS probe results alone",
            ],
            acceptance=[
                "history report includes the latest snapshot",
                "degraded targets are grouped by service/path",
                "policy still blocks automatic profile switch and NL mutation",
            ],
        ),
        item(
            task_id="LOCAL-03",
            phase="local_now",
            priority="P1",
            title="Keep NL source reconciliation local and deploy-blocked",
            status="ready" if promoted_count else "watch",
            allowed_now=True,
            nl_write_required=False,
            reason="Local source must match or explain current NL before any future deploy.",
            evidence=[
                f"promoted_source_count={promoted_count}",
                f"nl_write_allowed={summary.get('nl_write_allowed')}",
                f"deployable_to_nl={summary.get('deployable_to_nl')}",
            ],
            next_steps=[
                "continue using services/nl-server as reviewed local source only",
                "keep accepted local deltas marked non-deployable until separately reviewed",
                "run services/nl-server/tools/validate_preflight_readiness.py before any maintenance window",
            ],
            acceptance=[
                "manifest JSON is valid",
                "validate_preflight_readiness reports local_ready_but_deploy_blocked",
                "source gap summary has no unexplained missing_local_source or local_name_drift",
            ],
        ),
        item(
            task_id="LOCAL-04",
            phase="local_now",
            priority="P1",
            title="Treat provider boot gaps as watch evidence until transport degrades",
            status="watch" if provider == "recent_boot_gap" else "ready",
            allowed_now=True,
            nl_write_required=False,
            reason="A boot gap with current healthy transport is a provider-watch signal, not a restart signal.",
            evidence=[
                f"provider_status={provider}",
                f"failure_domain={summary.get('failure_domain')}",
            ],
            next_steps=[
                "build a provider packet if transport becomes degraded or critical",
                "keep boot gap warning in current-vpn-decision report",
                "avoid local hard heal when provider guard blocks on stale/provider evidence",
            ],
            acceptance=[
                "provider packet can be generated from a fresh snapshot",
                "current decision stays observe while transport is healthy",
                "provider_ticket is used only when current evidence points to provider/host failure",
            ],
        ),
        item(
            task_id="NL-FUTURE-01",
            phase="future_nl_write",
            priority="P0",
            title="First approved NL write: stage dry-run health shell split only",
            status="blocked_waiting_approval",
            allowed_now=False,
            nl_write_required=True,
            reason="This is the safest first server-side improvement, but NL is read-only now.",
            evidence=[
                "preflight checklist=nl-diagnostics/nl-deploy-preflight-checklist-2026-05-27.md",
                "target files=health_check_readonly.sh, health_action_policy.py, health_heal_xui.sh",
            ],
            next_steps=[
                "wait for exact operator approval: approve NL write for health shell split only",
                "take fresh read-only snapshot and fresh server profile",
                "create backup, stage files under .staged-<timestamp>, validate, then promote without service restart",
            ],
            acceptance=[
                "old health_check.sh remains unchanged",
                "no systemd reload and no x-ui restart during first write",
                "post-write read-only verification still reports transport healthy/advisory",
            ],
        ),
        item(
            task_id="NL-FUTURE-02",
            phase="future_nl_write",
            priority="P1",
            title="Port runtime status semantics to NL only after shell split proves safe",
            status="blocked_waiting_approval",
            allowed_now=False,
            nl_write_required=True,
            reason="Local semantic fix is prepared, but changing NL runtime behavior is a later server write.",
            evidence=[
                "local behavior: Telegram media degraded + healthy transport -> advisory/observe",
                "accepted local delta: services/nl-server/mesh-runtime/vps_build_runtime_state.py",
            ],
            next_steps=[
                "prepare a separate diff review for vps_build_runtime_state.py",
                "require fresh snapshot/profile and rollback commands",
                "deploy only after the read-only health wrappers are already staged and verified",
            ],
            acceptance=[
                "NL runtime exposes transport_status separately from telegram_media_status",
                "Telegram-only degradation no longer makes the whole VPN look critical",
                "classifier and NL runtime use matching state-contract language",
            ],
        ),
        item(
            task_id="FUTURE-RESILIENCE-01",
            phase="future_resilience",
            priority="P2",
            title="Prepare second exit node and manual failover, but keep SPB disabled",
            status="requirements_documented",
            allowed_now=True,
            nl_write_required=False,
            reason="Provider/host gaps need resilience, but the current SPB path is disabled and not a fallback.",
            evidence=[
                "spb_fallback_allowed=false",
                "provider_status=recent_boot_gap",
                "manual_failover_plan=nl-diagnostics/manual-failover-plan-2026-05-28.md",
                "secondary_probe_template=nl-diagnostics/manual-failover-secondary.example.json",
            ],
            next_steps=[
                "choose a new secondary provider/region that is not SPB",
                "copy the secondary probe example outside git and fill only public endpoint metadata",
                "run probe_secondary_exit.py before any manual profile switch",
                "define a manual profile switch checklist that requires fresh evidence",
                "do not reuse disabled SPB as emergency fallback",
            ],
            acceptance=[
                "manual failover document exists",
                "secondary node health check is separate from NL",
                "automatic switching remains disabled until manual process is tested",
            ],
        ),
    ]
    return items


def build_payload(decision: dict[str, Any], history: dict[str, Any], manifest: dict[str, Any]) -> dict[str, Any]:
    summary = current_summary(decision, history, manifest)
    items = build_items(summary)
    return {
        "schema_version": 1,
        "source": "nl-diagnostics/build_vpn_improvement_backlog.py",
        "generated_at": datetime.now(timezone.utc).isoformat(),
        "summary": summary,
        "items": items,
        "mutation_allowed": False,
        "nl_mutation_allowed": False,
        "auto_profile_switch_allowed": False,
        "spb_fallback_allowed": False,
    }


def render_markdown(payload: dict[str, Any]) -> str:
    summary = payload["summary"]
    lines = [
        "# VPN Improvement Backlog",
        "",
        f"generated_at: `{payload['generated_at']}`",
        "",
        "## Current Evidence",
        "",
        "```text",
        f"decision={summary.get('decision')}",
        f"decision_confidence={summary.get('decision_confidence')}",
        f"overall_status={summary.get('overall_status')}",
        f"transport_status={summary.get('transport_status')}",
        f"telegram_media_status={summary.get('telegram_media_status')}",
        f"provider_status={summary.get('provider_status')}",
        f"failure_domain={summary.get('failure_domain')}",
        f"blocking_history_trend={summary.get('blocking_history_trend')}",
        f"blocking_history_snapshot_count={summary.get('blocking_history_snapshot_count')}",
        f"promoted_source_count={summary.get('promoted_source_count')}",
        "nl_write_allowed=false",
        "spb_fallback_allowed=false",
        "```",
        "",
        "## Items",
        "",
    ]
    for backlog_item in payload["items"]:
        lines.extend(
            [
                f"### {backlog_item['id']}: {backlog_item['title']}",
                "",
                "```text",
                f"phase={backlog_item['phase']}",
                f"priority={backlog_item['priority']}",
                f"status={backlog_item['status']}",
                f"allowed_now={str(backlog_item['allowed_now']).lower()}",
                f"nl_write_required={str(backlog_item['nl_write_required']).lower()}",
                "mutation_allowed=false",
                "nl_mutation_allowed=false",
                "spb_fallback_allowed=false",
                "```",
                "",
                f"Reason: {backlog_item['reason']}",
                "",
                "Evidence:",
            ]
        )
        lines.extend(f"- {value}" for value in backlog_item["evidence"])
        lines.extend(["", "Next steps:"])
        lines.extend(f"- {value}" for value in backlog_item["next_steps"])
        lines.extend(["", "Acceptance:"])
        lines.extend(f"- {value}" for value in backlog_item["acceptance"])
        lines.append("")

    lines.append("No NL or SPB writes were performed by this backlog builder.")
    return "\n".join(lines) + "\n"


def main() -> int:
    parser = argparse.ArgumentParser(description="Build VPN improvement backlog")
    parser.add_argument("--decision", default=str(DEFAULT_DECISION))
    parser.add_argument("--blocking-history", default=str(DEFAULT_BLOCKING_HISTORY))
    parser.add_argument("--manifest", default=str(DEFAULT_MANIFEST))
    parser.add_argument("--json-out", default=str(DEFAULT_JSON_OUT))
    parser.add_argument("--markdown-out", default=str(DEFAULT_MARKDOWN_OUT))
    args = parser.parse_args()

    payload = build_payload(
        read_json(Path(args.decision)),
        read_json(Path(args.blocking_history)),
        read_json(Path(args.manifest)),
    )
    if args.json_out:
        Path(args.json_out).write_text(json.dumps(payload, indent=2, ensure_ascii=False) + "\n", encoding="utf-8")
    if args.markdown_out:
        Path(args.markdown_out).write_text(render_markdown(payload), encoding="utf-8")
    if not args.json_out and not args.markdown_out:
        print(json.dumps(payload, indent=2, ensure_ascii=False))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
