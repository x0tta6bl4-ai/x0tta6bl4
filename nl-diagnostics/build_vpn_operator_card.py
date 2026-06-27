#!/usr/bin/env python3
"""Build a short operator card for the next VPN incident.

The card reads local planning reports only. It does not SSH to NL/SPB and does
not mutate VPN runtime state.
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
DEFAULT_HISTORY = DIAGNOSTICS_DIR / "blocking-probe-history-2026-05-28.json"
DEFAULT_FAILOVER = DIAGNOSTICS_DIR / "manual-failover-plan-2026-05-28.json"
DEFAULT_SECONDARY = DIAGNOSTICS_DIR / "secondary-exit-probe-template-2026-05-28.json"
DEFAULT_JSON_OUT = DIAGNOSTICS_DIR / "vpn-operator-card-2026-05-28.json"
DEFAULT_MARKDOWN_OUT = DIAGNOSTICS_DIR / "vpn-operator-card-2026-05-28.md"


def read_json(path: Path) -> dict[str, Any]:
    try:
        value = json.loads(path.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError):
        return {}
    return value if isinstance(value, dict) else {}


def choose_action(decision_name: str, failure_domain: str) -> dict[str, str]:
    if decision_name == "observe":
        return {
            "operator_status": "observe",
            "plain_action": "VPN core is healthy. Do not restart NL; collect fresh evidence during the next visible outage.",
            "first_branch": "app_or_external_path_check",
        }
    if decision_name == "local_fix" or failure_domain == "local_client":
        return {
            "operator_status": "local_fix",
            "plain_action": "Fix local route, SOCKS, or client state before testing NL.",
            "first_branch": "local_client_first",
        }
    if decision_name == "provider_ticket" or failure_domain == "provider_host":
        return {
            "operator_status": "provider_ticket",
            "plain_action": "Build a provider packet; do not hide provider symptoms with restarts.",
            "first_branch": "provider_first",
        }
    if decision_name == "manual_profile_review":
        return {
            "operator_status": "manual_profile_review",
            "plain_action": "Review profile switch manually from fresh evidence; automatic switch stays disabled.",
            "first_branch": "manual_review_only",
        }
    if decision_name == "nl_readonly_review":
        return {
            "operator_status": "nl_readonly_review",
            "plain_action": "Inspect NL read-only; server writes require separate approval and backup.",
            "first_branch": "nl_readonly_first",
        }
    return {
        "operator_status": "operator_review",
        "plain_action": "Evidence is mixed. Refresh snapshot and review decision report before action.",
        "first_branch": "review_first",
    }


def build_payload(
    decision_report: dict[str, Any],
    history: dict[str, Any],
    failover: dict[str, Any],
    secondary: dict[str, Any],
) -> dict[str, Any]:
    decision = decision_report.get("decision") or {}
    classification = decision_report.get("classification") or {}
    history_summary = history.get("summary") or {}
    decision_name = str(decision.get("decision") or "unknown")
    failure_domain = str(classification.get("failure_domain") or "unknown")
    action = choose_action(decision_name, failure_domain)

    commands = [
        {
            "id": "incident_readonly_refresh",
            "command": "VPN_ENABLE_BLOCKING_PROBES=1 /mnt/projects/nl-diagnostics/run_vpn_incident_readonly_refresh.sh",
            "expected": "prints snapshot path and refresh report path; vpn-planning-refresh ok=true",
            "writes": "local snapshot and local reports only; NL read-only commands only",
        },
        {
            "id": "read_decision",
            "command": "sed -n '1,120p' /mnt/projects/nl-diagnostics/vpn-planning-refresh-2026-05-28.md",
            "expected": "decision, confidence, blocking trend, failover status",
            "writes": "none",
        },
    ]

    decision_table = [
        {
            "when": "decision=observe",
            "do": "observe; test affected app/media path separately",
            "do_not": "restart x-ui, change NL, auto-switch profile, use SPB",
        },
        {
            "when": "decision=local_fix",
            "do": "fix local route/SOCKS/client first",
            "do_not": "touch NL before local client is healthy",
        },
        {
            "when": "decision=provider_ticket",
            "do": "build provider packet from fresh snapshot",
            "do_not": "restart services to mask provider or host symptoms",
        },
        {
            "when": "decision=manual_profile_review",
            "do": "manual profile review only after fresh evidence and explicit approval",
            "do_not": "automatic profile switch",
        },
        {
            "when": "decision=nl_readonly_review",
            "do": "inspect NL services/listeners read-only and prepare backup/rollback",
            "do_not": "write to NL without separate approval",
        },
    ]

    return {
        "schema_version": 1,
        "source": "nl-diagnostics/build_vpn_operator_card.py",
        "generated_at": datetime.now(timezone.utc).isoformat(),
        "snapshot": decision_report.get("snapshot"),
        "operator": action,
        "current_state": {
            "decision": decision_name,
            "confidence": decision.get("confidence", "unknown"),
            "overall_status": classification.get("overall_status", "unknown"),
            "transport_status": classification.get("transport_status", "unknown"),
            "telegram_media_status": classification.get("telegram_media_status", "unknown"),
            "provider_status": classification.get("provider_status", "unknown"),
            "failure_domain": failure_domain,
            "blocking_history_trend": history_summary.get("trend", "unknown"),
            "blocking_history_snapshot_count": history_summary.get("snapshot_count", 0),
            "manual_failover_status": failover.get("status", "unknown"),
            "secondary_probe_template_status": secondary.get("status", "unknown"),
        },
        "commands": commands,
        "decision_table": decision_table,
        "blocked_actions": [
            "do not restart x-ui from app/blocking evidence alone",
            "do not change NL without explicit write approval",
            "do not auto-switch VPN profile",
            "do not use SPB as fallback while SPB is disabled",
            "do not store raw VPN URIs, UUIDs, private keys, or bot tokens in reports",
        ],
        "mutation_allowed": False,
        "nl_mutation_allowed": False,
        "spb_fallback_allowed": False,
        "automatic_failover_allowed": False,
    }


def render_markdown(payload: dict[str, Any]) -> str:
    state = payload["current_state"]
    operator = payload["operator"]
    lines = [
        "# VPN Operator Card",
        "",
        f"generated_at: `{payload['generated_at']}`",
        f"snapshot: `{payload.get('snapshot')}`",
        "",
        "## Status",
        "",
        "```text",
        f"operator_status={operator.get('operator_status')}",
        f"plain_action={operator.get('plain_action')}",
        f"decision={state.get('decision')}",
        f"confidence={state.get('confidence')}",
        f"overall_status={state.get('overall_status')}",
        f"transport_status={state.get('transport_status')}",
        f"telegram_media_status={state.get('telegram_media_status')}",
        f"provider_status={state.get('provider_status')}",
        f"failure_domain={state.get('failure_domain')}",
        f"blocking_history_trend={state.get('blocking_history_trend')}",
        f"blocking_history_snapshot_count={state.get('blocking_history_snapshot_count')}",
        f"manual_failover_status={state.get('manual_failover_status')}",
        "nl_mutation_allowed=false",
        "spb_fallback_allowed=false",
        "automatic_failover_allowed=false",
        "```",
        "",
        "## First Commands",
        "",
    ]
    for command in payload["commands"]:
        lines.extend(
            [
                f"### {command['id']}",
                "",
                "```bash",
                command["command"],
                "```",
                "",
                f"Expected: {command['expected']}",
                "",
                f"Writes: {command['writes']}",
                "",
            ]
        )

    lines.extend(["## Decision Table", ""])
    lines.append("| When | Do | Do Not |")
    lines.append("|---|---|---|")
    for row in payload["decision_table"]:
        lines.append(f"| `{row['when']}` | {row['do']} | {row['do_not']} |")

    lines.extend(["", "## Blocked Actions", ""])
    lines.extend(f"- {action}" for action in payload["blocked_actions"])
    lines.extend(["", "No NL or SPB writes were performed by this card builder."])
    return "\n".join(lines) + "\n"


def main() -> int:
    parser = argparse.ArgumentParser(description="Build short VPN operator card")
    parser.add_argument("--decision", default=str(DEFAULT_DECISION))
    parser.add_argument("--history", default=str(DEFAULT_HISTORY))
    parser.add_argument("--failover", default=str(DEFAULT_FAILOVER))
    parser.add_argument("--secondary", default=str(DEFAULT_SECONDARY))
    parser.add_argument("--json-out", default=str(DEFAULT_JSON_OUT))
    parser.add_argument("--markdown-out", default=str(DEFAULT_MARKDOWN_OUT))
    args = parser.parse_args()

    payload = build_payload(
        read_json(Path(args.decision)),
        read_json(Path(args.history)),
        read_json(Path(args.failover)),
        read_json(Path(args.secondary)),
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
