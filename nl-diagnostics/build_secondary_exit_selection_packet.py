#!/usr/bin/env python3
"""Build a safe provider-selection packet for a future secondary exit.

The packet turns the shortlist into an operator decision order. It does not
create a server, does not store provider credentials or VPN secrets, does not
contact NL/SPB, and does not permit failover.
"""

from __future__ import annotations

import argparse
from datetime import datetime, timezone
import json
from pathlib import Path
from typing import Any


ROOT = Path("/mnt/projects")
DIAGNOSTICS_DIR = ROOT / "nl-diagnostics"
DEFAULT_PROVIDER_SHORTLIST = DIAGNOSTICS_DIR / "secondary-exit-provider-shortlist-2026-05-28.json"
DEFAULT_PROVISIONING_PLAN = DIAGNOSTICS_DIR / "secondary-exit-provisioning-plan-2026-05-28.json"
DEFAULT_CANDIDATE_INTAKE = DIAGNOSTICS_DIR / "secondary-exit-candidate-intake-2026-05-28.json"
DEFAULT_REQUIREMENTS = DIAGNOSTICS_DIR / "secondary-exit-requirements-2026-05-28.json"
DEFAULT_SECONDARY_FLOW = DIAGNOSTICS_DIR / "secondary-exit-flow-2026-05-28.json"
DEFAULT_MANUAL_DRILL = DIAGNOSTICS_DIR / "secondary-exit-manual-drill-2026-05-28.json"
DEFAULT_JSON_OUT = DIAGNOSTICS_DIR / "secondary-exit-selection-packet-2026-05-28.json"
DEFAULT_MARKDOWN_OUT = DIAGNOSTICS_DIR / "secondary-exit-selection-packet-2026-05-28.md"


STOP_CONDITIONS = [
    "selected region is NL, Amsterdam, SPB, or Russia",
    "selected provider/account is the current NL provider/account",
    "public IPv4 or public TCP 443 cannot be confirmed",
    "provider console requires storing API tokens, billing data, SSH private keys, or root passwords in repo",
    "candidate metadata contains raw VPN URI, UUID, private key, bot token, subscription link, NL endpoint, or SPB endpoint",
    "readiness audit does not remain ready_local_with_future_blocks after metadata is added",
]

OPERATOR_CHECKS = [
    "verify provider and account are independent from NL",
    "verify exact region stock in the provider console",
    "verify public IPv4 and inbound TCP 443 before any profile work",
    "record only public metadata in secondary-exit-candidates.example.json",
    "run scorer, refresh, and readiness audit before creating any client test profile",
]


def read_json(path: Path) -> dict[str, Any]:
    try:
        value = json.loads(path.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError):
        return {}
    return value if isinstance(value, dict) else {}


def flag_is_false(payload: dict[str, Any], key: str) -> bool:
    return payload.get(key) is False


def all_safe(*payloads: dict[str, Any]) -> bool:
    return all(
        flag_is_false(payload, "nl_mutation_allowed")
        and flag_is_false(payload, "spb_fallback_allowed")
        and flag_is_false(payload, "automatic_failover_allowed")
        for payload in payloads
    )


def option_is_allowed(row: dict[str, Any]) -> bool:
    country = str(row.get("country") or "").lower()
    region = str(row.get("region") or "").lower()
    label = str(row.get("label") or "").lower()
    combined = " ".join([country, region, label])
    return (
        row.get("status") == "shortlist_ready_no_endpoint"
        and "netherlands" not in combined
        and "amsterdam" not in combined
        and "russia" not in combined
        and "spb" not in combined
    )


def decision_rows(provider_shortlist: dict[str, Any], limit: int = 3) -> list[dict[str, Any]]:
    rows = provider_shortlist.get("shortlist")
    if not isinstance(rows, list):
        return []
    allowed = [row for row in rows if isinstance(row, dict) and option_is_allowed(row)]
    ordered = sorted(allowed, key=lambda row: int(row.get("priority") or 999))
    decisions: list[dict[str, Any]] = []
    for index, row in enumerate(ordered[:limit], start=1):
        if index == 1:
            selection_role = "primary_pick"
        elif index == 2:
            selection_role = "backup_pick"
        else:
            selection_role = "fallback_review"
        decisions.append(
            {
                "rank": index,
                "selection_role": selection_role,
                "label": row.get("label", "missing"),
                "provider": row.get("provider", "missing"),
                "country": row.get("country", "missing"),
                "region": row.get("region", "missing"),
                "region_slugs": row.get("region_slugs") if isinstance(row.get("region_slugs"), list) else [],
                "expected_tcp_ports": (
                    row.get("expected_tcp_ports") if isinstance(row.get("expected_tcp_ports"), list) else []
                ),
                "source_id": row.get("source_id", "missing"),
                "why": row.get("why") if isinstance(row.get("why"), list) else [],
                "risk_notes": row.get("risk_notes") if isinstance(row.get("risk_notes"), list) else [],
                "external_action_required": True,
                "may_create_endpoint_now": False,
            }
        )
    return decisions


def source_urls(provider_shortlist: dict[str, Any]) -> dict[str, str]:
    rows = provider_shortlist.get("provider_sources")
    if not isinstance(rows, list):
        return {}
    return {
        str(row.get("id")): str(row.get("url"))
        for row in rows
        if isinstance(row, dict) and row.get("id") and row.get("url")
    }


def build_payload(
    *,
    provider_shortlist: dict[str, Any],
    provisioning_plan: dict[str, Any],
    candidate_intake: dict[str, Any],
    requirements: dict[str, Any],
    secondary_flow: dict[str, Any],
    manual_drill: dict[str, Any],
) -> dict[str, Any]:
    shortlist_summary = provider_shortlist.get("summary") or {}
    provisioning_summary = provisioning_plan.get("summary") or {}
    intake_summary = candidate_intake.get("summary") or {}
    requirements_summary = requirements.get("summary") or {}
    flow_summary = secondary_flow.get("summary") or {}
    drill_summary = manual_drill.get("summary") or {}
    decisions = decision_rows(provider_shortlist)
    endpoint_count = int(provisioning_summary.get("endpoint_count") or shortlist_summary.get("endpoint_count") or 0)
    safe = all_safe(
        provider_shortlist,
        provisioning_plan,
        candidate_intake,
        requirements,
        secondary_flow,
        manual_drill,
    )
    upstream_ready = (
        provider_shortlist.get("status") == "shortlist_ready_no_endpoint"
        and provisioning_plan.get("status") == "provisioning_plan_ready_no_endpoint"
        and candidate_intake.get("status")
        in {
            "awaiting_public_candidate_metadata",
            "candidate_metadata_needs_fix",
            "candidate_metadata_ready",
        }
        and requirements.get("status")
        in {
            "requirements_ready_no_candidate",
            "requirements_ready_with_candidate",
        }
    )
    no_switch = (
        flow_summary.get("manual_switch_allowed") is False
        and drill_summary.get("bulk_user_switch_allowed") is False
        and drill_summary.get("rollback_required") is True
    )
    if not safe:
        status = "selection_packet_unsafe_flags"
    elif decisions and upstream_ready and endpoint_count == 0 and no_switch:
        status = "selection_packet_ready_no_endpoint"
    elif decisions and upstream_ready:
        status = "selection_packet_ready_review_endpoint"
    else:
        status = "selection_packet_needs_attention"

    primary = decisions[0] if decisions else {}
    backup = decisions[1] if len(decisions) > 1 else {}
    return {
        "schema_version": 1,
        "source": "nl-diagnostics/build_secondary_exit_selection_packet.py",
        "generated_at": datetime.now(timezone.utc).isoformat(),
        "status": status,
        "ok": status in {"selection_packet_ready_no_endpoint", "selection_packet_ready_review_endpoint"},
        "summary": {
            "recommended_label": primary.get("label", "none"),
            "backup_label": backup.get("label", "none"),
            "decision_option_count": len(decisions),
            "endpoint_count": endpoint_count,
            "shortlist_status": provider_shortlist.get("status", "missing"),
            "provisioning_plan_status": provisioning_plan.get("status", "missing"),
            "candidate_intake_status": candidate_intake.get("status", "missing"),
            "requirements_status": requirements.get("status", "missing"),
            "secondary_flow_status": secondary_flow.get("status", "missing"),
            "manual_drill_status": manual_drill.get("status", "missing"),
            "manual_switch_allowed": flow_summary.get("manual_switch_allowed", "missing"),
            "bulk_user_switch_allowed": drill_summary.get("bulk_user_switch_allowed", "missing"),
            "rollback_required": drill_summary.get("rollback_required", "missing"),
            "candidate_file": intake_summary.get(
                "candidate_file",
                str(DIAGNOSTICS_DIR / "secondary-exit-candidates.example.json"),
            ),
            "missing_requirements": requirements_summary.get("missing_items") or [],
            "external_action_required": True,
            "may_create_endpoint_now": False,
            "nl_write_allowed": False,
            "spb_fallback_allowed": False,
            "automatic_failover_allowed": False,
        },
        "operator_decision_order": decisions,
        "source_urls": source_urls(provider_shortlist),
        "operator_checks": OPERATOR_CHECKS,
        "stop_conditions": STOP_CONDITIONS,
        "next_local_commands_after_public_metadata": [
            (
                "TMPDIR=/mnt/projects/.tmp python3 nl-diagnostics/score_secondary_exit_candidates.py "
                "--candidates /mnt/projects/nl-diagnostics/secondary-exit-candidates.example.json"
            ),
            "TMPDIR=/mnt/projects/.tmp python3 nl-diagnostics/refresh_vpn_planning_reports.py",
            "TMPDIR=/mnt/projects/.tmp python3 nl-diagnostics/audit_vpn_plan_readiness.py",
        ],
        "mutation_allowed": False,
        "nl_mutation_allowed": False,
        "spb_fallback_allowed": False,
        "automatic_failover_allowed": False,
    }


def render_markdown(payload: dict[str, Any]) -> str:
    summary = payload["summary"]
    lines = [
        "# Secondary Exit Selection Packet",
        "",
        f"generated_at: `{payload['generated_at']}`",
        f"status: `{payload['status']}`",
        f"ok: `{str(payload['ok']).lower()}`",
        "",
        "## Summary",
        "",
        "```text",
        f"recommended_label={summary.get('recommended_label')}",
        f"backup_label={summary.get('backup_label')}",
        f"decision_option_count={summary.get('decision_option_count')}",
        f"endpoint_count={summary.get('endpoint_count')}",
        f"shortlist_status={summary.get('shortlist_status')}",
        f"provisioning_plan_status={summary.get('provisioning_plan_status')}",
        f"candidate_intake_status={summary.get('candidate_intake_status')}",
        f"requirements_status={summary.get('requirements_status')}",
        f"secondary_flow_status={summary.get('secondary_flow_status')}",
        f"manual_drill_status={summary.get('manual_drill_status')}",
        f"manual_switch_allowed={str(summary.get('manual_switch_allowed')).lower()}",
        f"bulk_user_switch_allowed={str(summary.get('bulk_user_switch_allowed')).lower()}",
        f"rollback_required={str(summary.get('rollback_required')).lower()}",
        f"candidate_file={summary.get('candidate_file')}",
        f"missing_requirements={','.join(summary.get('missing_requirements') or []) or 'none'}",
        f"external_action_required={str(summary.get('external_action_required')).lower()}",
        f"may_create_endpoint_now={str(summary.get('may_create_endpoint_now')).lower()}",
        "nl_write_allowed=false",
        "spb_fallback_allowed=false",
        "automatic_failover_allowed=false",
        "```",
        "",
        "## Decision Order",
        "",
        "| Rank | Role | Label | Provider | Country | Region | Ports | Source |",
        "|---:|---|---|---|---|---|---|---|",
    ]
    source_urls = payload["source_urls"]
    for row in payload["operator_decision_order"]:
        source_id = row.get("source_id", "missing")
        lines.append(
            "| "
            f"{row['rank']} | "
            f"`{row['selection_role']}` | "
            f"`{row['label']}` | "
            f"{row['provider']} | "
            f"{row['country']} | "
            f"{row['region']} | "
            f"`{','.join(str(port) for port in row['expected_tcp_ports'])}` | "
            f"{source_urls.get(source_id, 'missing')} |"
        )
    lines.extend(["", "## Operator Checks", ""])
    lines.extend(f"- {value}" for value in payload["operator_checks"])
    lines.extend(["", "## Stop Conditions", ""])
    lines.extend(f"- {value}" for value in payload["stop_conditions"])
    lines.extend(["", "## Evidence By Option", ""])
    for row in payload["operator_decision_order"]:
        lines.extend([f"### {row['label']}", ""])
        lines.append("Why:")
        lines.extend(f"- {value}" for value in row["why"])
        lines.append("")
        lines.append("Risk notes:")
        lines.extend(f"- {value}" for value in row["risk_notes"])
        lines.append("")
    lines.extend(["## Next Local Commands After Public Metadata", "", "```bash"])
    lines.extend(payload["next_local_commands_after_public_metadata"])
    lines.extend(["```", ""])
    lines.append("No NL or SPB writes were performed by this selection packet.")
    return "\n".join(lines) + "\n"


def main() -> int:
    parser = argparse.ArgumentParser(description="Build secondary exit selection packet")
    parser.add_argument("--provider-shortlist", default=str(DEFAULT_PROVIDER_SHORTLIST))
    parser.add_argument("--provisioning-plan", default=str(DEFAULT_PROVISIONING_PLAN))
    parser.add_argument("--candidate-intake", default=str(DEFAULT_CANDIDATE_INTAKE))
    parser.add_argument("--requirements", default=str(DEFAULT_REQUIREMENTS))
    parser.add_argument("--secondary-flow", default=str(DEFAULT_SECONDARY_FLOW))
    parser.add_argument("--manual-drill", default=str(DEFAULT_MANUAL_DRILL))
    parser.add_argument("--json-out", default=str(DEFAULT_JSON_OUT))
    parser.add_argument("--markdown-out", default=str(DEFAULT_MARKDOWN_OUT))
    args = parser.parse_args()

    payload = build_payload(
        provider_shortlist=read_json(Path(args.provider_shortlist)),
        provisioning_plan=read_json(Path(args.provisioning_plan)),
        candidate_intake=read_json(Path(args.candidate_intake)),
        requirements=read_json(Path(args.requirements)),
        secondary_flow=read_json(Path(args.secondary_flow)),
        manual_drill=read_json(Path(args.manual_drill)),
    )
    if args.json_out:
        Path(args.json_out).write_text(json.dumps(payload, indent=2, ensure_ascii=False) + "\n", encoding="utf-8")
    if args.markdown_out:
        Path(args.markdown_out).write_text(render_markdown(payload), encoding="utf-8")
    if not args.json_out and not args.markdown_out:
        print(json.dumps(payload, indent=2, ensure_ascii=False))
    return 0 if payload["ok"] else 1


if __name__ == "__main__":
    raise SystemExit(main())
