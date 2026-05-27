#!/usr/bin/env python3
"""Build a manual failover plan for a future second VPN exit node.

This script reads local reports only. It does not connect to NL or SPB and does
not change local or remote VPN runtime state.
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
DEFAULT_BACKLOG = DIAGNOSTICS_DIR / "vpn-improvement-backlog-2026-05-28.json"
DEFAULT_JSON_OUT = DIAGNOSTICS_DIR / "manual-failover-plan-2026-05-28.json"
DEFAULT_MARKDOWN_OUT = DIAGNOSTICS_DIR / "manual-failover-plan-2026-05-28.md"


def read_json(path: Path) -> dict[str, Any]:
    try:
        value = json.loads(path.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError):
        return {}
    return value if isinstance(value, dict) else {}


def summarize_inputs(decision: dict[str, Any], backlog: dict[str, Any]) -> dict[str, Any]:
    decision_data = decision.get("decision") or {}
    classification = decision.get("classification") or {}
    backlog_summary = backlog.get("summary") or {}
    return {
        "current_decision": decision_data.get("decision", "unknown"),
        "decision_confidence": decision_data.get("confidence", "unknown"),
        "overall_status": classification.get("overall_status", "unknown"),
        "transport_status": classification.get("transport_status", "unknown"),
        "failure_domain": classification.get("failure_domain", "unknown"),
        "provider_status": classification.get("provider_status", "unknown"),
        "blocking_history_trend": backlog_summary.get("blocking_history_trend", "unknown"),
        "spb_fallback_allowed": False,
        "automatic_failover_allowed": False,
        "nl_write_allowed": False,
    }


def failover_status(summary: dict[str, Any]) -> str:
    decision = str(summary.get("current_decision") or "unknown")
    failure_domain = str(summary.get("failure_domain") or "unknown")
    if decision == "observe":
        return "planning_not_active"
    if decision in {"provider_ticket", "failover"} or failure_domain == "provider_host":
        return "manual_failover_candidate"
    if decision == "local_fix":
        return "blocked_local_client_first"
    return "manual_review"


def build_payload(decision: dict[str, Any], backlog: dict[str, Any]) -> dict[str, Any]:
    summary = summarize_inputs(decision, backlog)
    status = failover_status(summary)
    candidate_requirements = [
        {
            "id": "NODE-01",
            "requirement": "Use a new secondary exit node, not SPB",
            "acceptance": "provider/region/account are documented and spb_fallback_allowed=false remains true in policy",
        },
        {
            "id": "NODE-02",
            "requirement": "Use a different provider and region from NL",
            "acceptance": "provider outage on NL should not imply outage on the secondary node",
        },
        {
            "id": "NODE-03",
            "requirement": "Keep secrets out of repo and reports",
            "acceptance": "only redacted profile shape or checksums are stored locally; no raw URI/private key/token",
        },
        {
            "id": "NODE-04",
            "requirement": "Expose an independent health check",
            "acceptance": "probe_secondary_exit.py can verify TCP reachability and expected exit IP without touching NL",
        },
        {
            "id": "NODE-05",
            "requirement": "Use a minimal daily/emergency profile split",
            "acceptance": "daily NL profile and emergency secondary profile are distinct; automatic switching remains disabled",
        },
    ]
    activation_gates = [
        {
            "id": "GATE-01",
            "gate": "fresh read-only NL snapshot with blocking probes",
            "pass_condition": "snapshot is current and classifier says provider_ticket/failover or NL transport is critical while local client is healthy",
        },
        {
            "id": "GATE-02",
            "gate": "local client is not the failure domain",
            "pass_condition": "vpn_status shows local route/SOCKS/client are OK; otherwise fix local client first",
        },
        {
            "id": "GATE-03",
            "gate": "secondary node health is independently verified",
            "pass_condition": "probe_secondary_exit.py reports healthy, or endpoint_reachable_profile_unverified before the profile switch test",
        },
        {
            "id": "GATE-04",
            "gate": "explicit manual approval",
            "pass_condition": "operator approves a manual client/profile switch; automatic failover remains false",
        },
        {
            "id": "GATE-05",
            "gate": "SPB remains excluded",
            "pass_condition": "selected emergency profile is not SPB and does not run sync_spb_standalone_clients.py",
        },
    ]
    procedures = {
        "prepare_now": [
            "choose a new provider/region for a future secondary node",
            "define a redacted profile template and health-check contract",
            "prepare local-only health probe config from nl-diagnostics/manual-failover-secondary.example.json",
            "document manual switch and rollback steps without storing secrets",
        ],
        "during_incident": [
            "collect VPN_ENABLE_BLOCKING_PROBES=1 read-only snapshot",
            "build current VPN decision report and provider packet if needed",
            "run python3 nl-diagnostics/probe_secondary_exit.py --config <redacted-secondary-config>",
            "perform client-side manual switch only after explicit approval",
            "record timeline and keep NL unchanged while diagnosing provider/NL state",
        ],
        "rollback": [
            "collect a fresh NL read-only snapshot showing transport healthy/advisory",
            "switch the client back manually to NL daily profile",
            "verify exit IP, route bypass, packet loss, and watchdog metrics",
            "leave secondary profile available but inactive",
        ],
    }
    blocked_actions = [
        "do not use SPB as fallback while SPB is disabled",
        "do not run sync_spb_standalone_clients.py as recovery",
        "do not auto-switch profiles",
        "do not change NL during failover unless a separate NL write approval exists",
        "do not store raw VPN URIs, UUIDs, private keys, or bot tokens in reports",
    ]
    return {
        "schema_version": 1,
        "source": "nl-diagnostics/build_manual_failover_plan.py",
        "generated_at": datetime.now(timezone.utc).isoformat(),
        "status": status,
        "summary": summary,
        "candidate_requirements": candidate_requirements,
        "activation_gates": activation_gates,
        "procedures": procedures,
        "blocked_actions": blocked_actions,
        "local_probe": {
            "script": "nl-diagnostics/probe_secondary_exit.py",
            "example_config": "nl-diagnostics/manual-failover-secondary.example.json",
            "placeholder_status": "planning_template",
        },
        "mutation_allowed": False,
        "nl_mutation_allowed": False,
        "spb_fallback_allowed": False,
        "automatic_failover_allowed": False,
    }


def render_markdown(payload: dict[str, Any]) -> str:
    summary = payload["summary"]
    lines = [
        "# Manual Failover Plan",
        "",
        f"generated_at: `{payload['generated_at']}`",
        "",
        "## Status",
        "",
        "```text",
        f"status={payload['status']}",
        f"current_decision={summary.get('current_decision')}",
        f"decision_confidence={summary.get('decision_confidence')}",
        f"overall_status={summary.get('overall_status')}",
        f"transport_status={summary.get('transport_status')}",
        f"failure_domain={summary.get('failure_domain')}",
        f"provider_status={summary.get('provider_status')}",
        f"spb_fallback_allowed={str(summary.get('spb_fallback_allowed')).lower()}",
        f"automatic_failover_allowed={str(summary.get('automatic_failover_allowed')).lower()}",
        "nl_write_allowed=false",
        "```",
        "",
        "## Candidate Requirements",
        "",
    ]
    for requirement in payload["candidate_requirements"]:
        lines.extend(
            [
                f"### {requirement['id']}",
                "",
                f"Requirement: {requirement['requirement']}",
                "",
                f"Acceptance: {requirement['acceptance']}",
                "",
            ]
        )

    lines.extend(["## Activation Gates", ""])
    for gate in payload["activation_gates"]:
        lines.extend(
            [
                f"### {gate['id']}",
                "",
                f"Gate: {gate['gate']}",
                "",
                f"Pass condition: {gate['pass_condition']}",
                "",
            ]
        )

    lines.extend(["## Procedures", ""])
    for name, steps in payload["procedures"].items():
        lines.extend([f"### {name}", ""])
        lines.extend(f"- {step}" for step in steps)
        lines.append("")

    local_probe = payload.get("local_probe") or {}
    lines.extend(
        [
            "## Local Secondary Probe",
            "",
            "```text",
            f"script={local_probe.get('script')}",
            f"example_config={local_probe.get('example_config')}",
            f"placeholder_status={local_probe.get('placeholder_status')}",
            "mutation_allowed=false",
            "nl_mutation_allowed=false",
            "spb_fallback_allowed=false",
            "```",
            "",
        ]
    )

    lines.extend(["## Blocked Actions", ""])
    lines.extend(f"- {action}" for action in payload["blocked_actions"])
    lines.extend(["", "No NL or SPB writes were performed by this plan builder."])
    return "\n".join(lines) + "\n"


def main() -> int:
    parser = argparse.ArgumentParser(description="Build manual VPN failover plan")
    parser.add_argument("--decision", default=str(DEFAULT_DECISION))
    parser.add_argument("--backlog", default=str(DEFAULT_BACKLOG))
    parser.add_argument("--json-out", default=str(DEFAULT_JSON_OUT))
    parser.add_argument("--markdown-out", default=str(DEFAULT_MARKDOWN_OUT))
    args = parser.parse_args()

    payload = build_payload(read_json(Path(args.decision)), read_json(Path(args.backlog)))
    if args.json_out:
        Path(args.json_out).write_text(json.dumps(payload, indent=2, ensure_ascii=False) + "\n", encoding="utf-8")
    if args.markdown_out:
        Path(args.markdown_out).write_text(render_markdown(payload), encoding="utf-8")
    if not args.json_out and not args.markdown_out:
        print(json.dumps(payload, indent=2, ensure_ascii=False))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
