#!/usr/bin/env python3
"""Audit whether manual VPN failover is allowed from local evidence.

This gate reads local reports only. It does not connect to NL or SPB, does not
switch profiles, and does not mutate VPN runtime state.
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
DEFAULT_FAILOVER = DIAGNOSTICS_DIR / "manual-failover-plan-2026-05-28.json"
DEFAULT_SECONDARY = DIAGNOSTICS_DIR / "secondary-exit-probe-template-2026-05-28.json"
DEFAULT_JSON_OUT = DIAGNOSTICS_DIR / "manual-failover-readiness-2026-05-28.json"
DEFAULT_MARKDOWN_OUT = DIAGNOSTICS_DIR / "manual-failover-readiness-2026-05-28.md"


PASS = "pass"
BLOCKED = "blocked"


def read_json(path: Path) -> dict[str, Any]:
    try:
        value = json.loads(path.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError):
        return {}
    return value if isinstance(value, dict) else {}


def is_false(payload: dict[str, Any], key: str) -> bool:
    return payload.get(key) is False


def spb_marker_absent(value: Any) -> bool:
    text = json.dumps(value, ensure_ascii=False, sort_keys=True).lower()
    return "spb" not in text


def gate(
    *,
    gate_id: str,
    title: str,
    status: str,
    evidence: list[str],
    next_step: str,
) -> dict[str, Any]:
    return {
        "id": gate_id,
        "title": title,
        "status": status,
        "ok": status == PASS,
        "evidence": evidence,
        "next_step": next_step,
    }


def choose_status(
    *,
    decision_name: str,
    failure_domain: str,
    candidate_configured: bool,
    secondary_status: str,
    manual_switch_allowed: bool,
    manual_probe_allowed: bool,
) -> str:
    if manual_switch_allowed:
        return "ready_for_manual_switch"
    if manual_probe_allowed:
        return "ready_for_profile_test_only"
    if decision_name == "observe":
        return "blocked_no_incident_trigger"
    if decision_name == "local_fix" or failure_domain == "local_client":
        return "blocked_local_client_first"
    if not candidate_configured:
        return "blocked_missing_secondary"
    if secondary_status != "healthy":
        return "blocked_secondary_not_healthy"
    return "blocked_manual_review"


def build_payload(
    decision_report: dict[str, Any],
    failover_plan: dict[str, Any],
    secondary_probe: dict[str, Any],
) -> dict[str, Any]:
    decision = decision_report.get("decision") or {}
    classification = decision_report.get("classification") or {}
    failover_summary = failover_plan.get("summary") or {}
    secondary_candidate = secondary_probe.get("candidate") or {}

    decision_name = str(decision.get("decision") or "unknown")
    failure_domain = str(classification.get("failure_domain") or "unknown")
    transport_status = str(classification.get("transport_status") or "unknown")
    provider_status = str(classification.get("provider_status") or "unknown")
    failover_status = str(failover_plan.get("status") or "unknown")
    secondary_status = str(secondary_probe.get("status") or "unknown")
    candidate_configured = secondary_probe.get("candidate_configured") is True

    incident_trigger = decision_name in {"provider_ticket", "manual_profile_review", "failover"} or failure_domain == "provider_host"
    local_client_ok = failure_domain != "local_client" and decision_name != "local_fix"
    secondary_profile_test_ok = secondary_status in {"healthy", "endpoint_reachable_profile_unverified"}
    secondary_switch_ok = secondary_status == "healthy"
    spb_ok = (
        is_false(failover_plan, "spb_fallback_allowed")
        and is_false(secondary_probe, "spb_fallback_allowed")
        and failover_summary.get("spb_fallback_allowed") is False
        and (not candidate_configured or spb_marker_absent(secondary_candidate))
    )
    auto_ok = (
        is_false(failover_plan, "automatic_failover_allowed")
        and is_false(secondary_probe, "automatic_failover_allowed")
        and failover_summary.get("automatic_failover_allowed") is False
    )
    nl_write_ok = is_false(failover_plan, "nl_mutation_allowed") and is_false(secondary_probe, "nl_mutation_allowed")

    manual_probe_allowed = (
        incident_trigger
        and local_client_ok
        and candidate_configured
        and secondary_profile_test_ok
        and spb_ok
        and auto_ok
        and nl_write_ok
    )
    manual_switch_allowed = manual_probe_allowed and secondary_switch_ok
    status = choose_status(
        decision_name=decision_name,
        failure_domain=failure_domain,
        candidate_configured=candidate_configured,
        secondary_status=secondary_status,
        manual_switch_allowed=manual_switch_allowed,
        manual_probe_allowed=manual_probe_allowed,
    )

    gates = [
        gate(
            gate_id="TRIGGER-01",
            title="Incident evidence justifies considering failover",
            status=PASS if incident_trigger else BLOCKED,
            evidence=[
                f"decision={decision_name}",
                f"failure_domain={failure_domain}",
                f"transport_status={transport_status}",
                f"provider_status={provider_status}",
            ],
            next_step="stay on observe while NL transport is healthy and no incident trigger exists",
        ),
        gate(
            gate_id="LOCAL-01",
            title="Local client is not the failure domain",
            status=PASS if local_client_ok else BLOCKED,
            evidence=[f"decision={decision_name}", f"failure_domain={failure_domain}"],
            next_step="fix local route/SOCKS/client before any failover work",
        ),
        gate(
            gate_id="SECONDARY-01",
            title="Secondary exit candidate is configured",
            status=PASS if candidate_configured else BLOCKED,
            evidence=[
                f"secondary_status={secondary_status}",
                f"candidate_configured={str(candidate_configured).lower()}",
                f"candidate_label={secondary_candidate.get('label', 'missing')}",
                f"candidate_provider={secondary_candidate.get('provider', 'missing')}",
                f"candidate_region={secondary_candidate.get('region', 'missing')}",
            ],
            next_step="choose a new non-SPB provider/region and generate a safe public probe config",
        ),
        gate(
            gate_id="SECONDARY-02",
            title="Secondary exit health is verified enough for the requested action",
            status=PASS if secondary_profile_test_ok else BLOCKED,
            evidence=[f"secondary_status={secondary_status}"],
            next_step="run probe_secondary_exit.py against the secondary public endpoint before any profile test",
        ),
        gate(
            gate_id="SPB-01",
            title="SPB is excluded from failover",
            status=PASS if spb_ok else BLOCKED,
            evidence=[
                f"failover_spb_fallback_allowed={str(failover_plan.get('spb_fallback_allowed')).lower()}",
                f"secondary_spb_fallback_allowed={str(secondary_probe.get('spb_fallback_allowed')).lower()}",
                f"candidate_configured={str(candidate_configured).lower()}",
                f"candidate_has_spb_marker={str(candidate_configured and not spb_marker_absent(secondary_candidate)).lower()}",
            ],
            next_step="do not use SPB or SPB sync scripts as emergency recovery",
        ),
        gate(
            gate_id="MANUAL-01",
            title="Failover remains manual and NL read-only",
            status=PASS if auto_ok and nl_write_ok else BLOCKED,
            evidence=[
                f"automatic_failover_allowed={str(failover_plan.get('automatic_failover_allowed')).lower()}",
                f"nl_mutation_allowed={str(failover_plan.get('nl_mutation_allowed')).lower()}",
                f"secondary_automatic_failover_allowed={str(secondary_probe.get('automatic_failover_allowed')).lower()}",
                f"secondary_nl_mutation_allowed={str(secondary_probe.get('nl_mutation_allowed')).lower()}",
            ],
            next_step="keep switching manual-only and keep NL unchanged during failover diagnosis",
        ),
    ]

    return {
        "schema_version": 1,
        "source": "nl-diagnostics/audit_manual_failover_readiness.py",
        "generated_at": datetime.now(timezone.utc).isoformat(),
        "status": status,
        "manual_probe_allowed": manual_probe_allowed,
        "manual_switch_allowed": manual_switch_allowed,
        "summary": {
            "decision": decision_name,
            "decision_confidence": decision.get("confidence", "unknown"),
            "overall_status": classification.get("overall_status", "unknown"),
            "transport_status": transport_status,
            "failure_domain": failure_domain,
            "provider_status": provider_status,
            "manual_failover_status": failover_status,
            "secondary_probe_status": secondary_status,
            "candidate_configured": candidate_configured,
            "spb_excluded": spb_ok,
            "automatic_failover_allowed": False,
            "nl_write_allowed": False,
        },
        "gates": gates,
        "mutation_allowed": False,
        "nl_mutation_allowed": False,
        "spb_fallback_allowed": False,
        "automatic_failover_allowed": False,
    }


def render_markdown(payload: dict[str, Any]) -> str:
    summary = payload["summary"]
    lines = [
        "# Manual Failover Readiness",
        "",
        f"generated_at: `{payload['generated_at']}`",
        "",
        "## Status",
        "",
        "```text",
        f"status={payload['status']}",
        f"manual_probe_allowed={str(payload.get('manual_probe_allowed')).lower()}",
        f"manual_switch_allowed={str(payload.get('manual_switch_allowed')).lower()}",
        f"decision={summary.get('decision')}",
        f"transport_status={summary.get('transport_status')}",
        f"failure_domain={summary.get('failure_domain')}",
        f"provider_status={summary.get('provider_status')}",
        f"manual_failover_status={summary.get('manual_failover_status')}",
        f"secondary_probe_status={summary.get('secondary_probe_status')}",
        f"candidate_configured={str(summary.get('candidate_configured')).lower()}",
        f"spb_excluded={str(summary.get('spb_excluded')).lower()}",
        "nl_write_allowed=false",
        "automatic_failover_allowed=false",
        "```",
        "",
        "## Gates",
        "",
        "| ID | Status | Gate | Next Step |",
        "|---|---|---|---|",
    ]
    for row in payload["gates"]:
        lines.append(f"| `{row['id']}` | `{row['status']}` | {row['title']} | {row['next_step']} |")

    lines.extend(["", "## Evidence", ""])
    for row in payload["gates"]:
        lines.extend([f"### {row['id']}", ""])
        lines.extend(f"- {value}" for value in row["evidence"])
        lines.append("")

    lines.append("No NL or SPB writes were performed by this failover readiness gate.")
    return "\n".join(lines) + "\n"


def main() -> int:
    parser = argparse.ArgumentParser(description="Audit manual VPN failover readiness")
    parser.add_argument("--decision", default=str(DEFAULT_DECISION))
    parser.add_argument("--failover", default=str(DEFAULT_FAILOVER))
    parser.add_argument("--secondary", default=str(DEFAULT_SECONDARY))
    parser.add_argument("--json-out", default=str(DEFAULT_JSON_OUT))
    parser.add_argument("--markdown-out", default=str(DEFAULT_MARKDOWN_OUT))
    args = parser.parse_args()

    payload = build_payload(
        read_json(Path(args.decision)),
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
