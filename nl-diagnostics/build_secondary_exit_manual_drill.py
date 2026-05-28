#!/usr/bin/env python3
"""Build a manual drill and rollback plan for a future secondary VPN exit.

The drill plan is local planning only. It does not activate client profiles,
does not store VPN secrets, does not connect to NL/SPB, and does not enable
automatic or manual failover by itself.
"""

from __future__ import annotations

import argparse
from datetime import datetime, timezone
import json
from pathlib import Path
from typing import Any


ROOT = Path("/mnt/projects")
DIAGNOSTICS_DIR = ROOT / "nl-diagnostics"
DEFAULT_FAILOVER_READINESS = DIAGNOSTICS_DIR / "manual-failover-readiness-2026-05-28.json"
DEFAULT_SECONDARY_FLOW = DIAGNOSTICS_DIR / "secondary-exit-flow-2026-05-28.json"
DEFAULT_PROVISIONING_PLAN = DIAGNOSTICS_DIR / "secondary-exit-provisioning-plan-2026-05-28.json"
DEFAULT_JSON_OUT = DIAGNOSTICS_DIR / "secondary-exit-manual-drill-2026-05-28.json"
DEFAULT_MARKDOWN_OUT = DIAGNOSTICS_DIR / "secondary-exit-manual-drill-2026-05-28.md"


FORBIDDEN_MATERIAL = [
    "raw VPN URI",
    "UUID",
    "private key",
    "bot token",
    "subscription link",
    "provider API token",
    "SSH private key",
    "NL endpoint",
    "SPB endpoint",
]


def read_json(path: Path) -> dict[str, Any]:
    try:
        value = json.loads(path.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError):
        return {}
    return value if isinstance(value, dict) else {}


def flag_is_false(payload: dict[str, Any], key: str) -> bool:
    return payload.get(key) is False


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
        "ok": status in {"pass", "blocked", "ready_when_allowed"},
        "evidence": evidence,
        "next_step": next_step,
    }


def choose_status(
    *,
    safe: bool,
    manual_probe_allowed: bool,
    manual_switch_allowed: bool,
    flow_status: str,
    provisioning_status: str,
) -> str:
    if not safe:
        return "unsafe_flags"
    if manual_switch_allowed and flow_status == "ready_for_manual_switch":
        return "drill_ready_for_manual_switch"
    if manual_probe_allowed:
        return "drill_ready_for_test_client_only"
    if provisioning_status == "provisioning_plan_ready_no_endpoint":
        return "drill_plan_ready_blocked_no_endpoint"
    return "drill_plan_blocked"


def build_payload(
    *,
    failover_readiness: dict[str, Any],
    secondary_flow: dict[str, Any],
    provisioning_plan: dict[str, Any],
) -> dict[str, Any]:
    readiness_summary = failover_readiness.get("summary") or {}
    flow_summary = secondary_flow.get("summary") or {}
    provisioning_summary = provisioning_plan.get("summary") or {}
    manual_probe_allowed = failover_readiness.get("manual_probe_allowed") is True
    manual_switch_allowed = failover_readiness.get("manual_switch_allowed") is True
    candidate_configured = flow_summary.get("candidate_configured") is True
    endpoint_count = int(provisioning_summary.get("endpoint_count") or 0)
    flow_status = str(secondary_flow.get("status") or "missing")
    provisioning_status = str(provisioning_plan.get("status") or "missing")
    safe = all(
        [
            flag_is_false(failover_readiness, "nl_mutation_allowed"),
            flag_is_false(failover_readiness, "spb_fallback_allowed"),
            flag_is_false(failover_readiness, "automatic_failover_allowed"),
            flag_is_false(secondary_flow, "nl_mutation_allowed"),
            flag_is_false(secondary_flow, "spb_fallback_allowed"),
            flag_is_false(secondary_flow, "automatic_failover_allowed"),
            flag_is_false(provisioning_plan, "nl_mutation_allowed"),
            flag_is_false(provisioning_plan, "spb_fallback_allowed"),
            flag_is_false(provisioning_plan, "automatic_failover_allowed"),
            readiness_summary.get("nl_write_allowed") is False,
            readiness_summary.get("automatic_failover_allowed") is False,
            flow_summary.get("nl_write_allowed") is False,
            flow_summary.get("spb_fallback_allowed") is False,
            flow_summary.get("automatic_failover_allowed") is False,
            provisioning_summary.get("nl_write_allowed") is False,
            provisioning_summary.get("spb_fallback_allowed") is False,
            provisioning_summary.get("automatic_failover_allowed") is False,
        ]
    )
    status = choose_status(
        safe=safe,
        manual_probe_allowed=manual_probe_allowed,
        manual_switch_allowed=manual_switch_allowed,
        flow_status=flow_status,
        provisioning_status=provisioning_status,
    )

    gates = [
        gate(
            gate_id="DRILL-01",
            title="Use one manually controlled test client only",
            status="blocked" if not manual_probe_allowed else "pass",
            evidence=[
                f"manual_probe_allowed={str(manual_probe_allowed).lower()}",
                "test_scope=single_client",
                "bulk_user_switch_allowed=false",
            ],
            next_step="keep drill blocked until failover readiness permits a test-client profile check",
        ),
        gate(
            gate_id="DRILL-02",
            title="Public secondary endpoint exists before profile testing",
            status="pass" if candidate_configured and endpoint_count > 0 else "blocked",
            evidence=[
                f"candidate_configured={str(candidate_configured).lower()}",
                f"endpoint_count={endpoint_count}",
                f"secondary_flow_status={flow_status}",
            ],
            next_step="provision the secondary endpoint and add only public metadata before testing",
        ),
        gate(
            gate_id="DRILL-03",
            title="Probe endpoint before touching any client profile",
            status="pass" if flow_summary.get("secondary_probe_status") in {"endpoint_reachable_profile_unverified", "healthy"} else "blocked",
            evidence=[
                f"secondary_probe_status={flow_summary.get('secondary_probe_status', 'missing')}",
                "probe_config_path=/mnt/projects/.tmp/secondary-exit-probe.json",
            ],
            next_step="run the public TCP probe after a candidate endpoint exists",
        ),
        gate(
            gate_id="DRILL-04",
            title="Manual switch remains test-only and reversible",
            status="ready_when_allowed" if manual_probe_allowed else "blocked",
            evidence=[
                f"manual_switch_allowed={str(manual_switch_allowed).lower()}",
                "automatic_failover_allowed=false",
                "rollback_required=true",
            ],
            next_step="activate only the test client, then immediately verify rollback to NL daily profile",
        ),
        gate(
            gate_id="DRILL-05",
            title="Return-to-NL rollback is mandatory",
            status="pass",
            evidence=[
                "rollback_target=NL daily profile",
                "secondary_profile_final_state=inactive",
                "nl_write_allowed=false",
            ],
            next_step="after the drill, switch the test client back to NL and record the result",
        ),
    ]

    return {
        "schema_version": 1,
        "source": "nl-diagnostics/build_secondary_exit_manual_drill.py",
        "generated_at": datetime.now(timezone.utc).isoformat(),
        "status": status,
        "ok": safe,
        "summary": {
            "manual_probe_allowed": manual_probe_allowed,
            "manual_switch_allowed": manual_switch_allowed,
            "candidate_configured": candidate_configured,
            "endpoint_count": endpoint_count,
            "secondary_flow_status": flow_status,
            "secondary_probe_status": flow_summary.get("secondary_probe_status", "missing"),
            "provisioning_plan_status": provisioning_status,
            "test_scope": "single_client",
            "bulk_user_switch_allowed": False,
            "rollback_required": True,
            "safe_flags": safe,
            "nl_write_allowed": False,
            "spb_fallback_allowed": False,
            "automatic_failover_allowed": False,
        },
        "gates": gates,
        "test_client_steps": [
            "Collect a fresh read-only incident snapshot first.",
            "Run the secondary public endpoint probe from local diagnostics.",
            "Activate the emergency secondary profile on exactly one test client only.",
            "Verify basic connectivity and expected exit behavior on that test client.",
            "Switch the test client back to the NL daily profile.",
            "Record pass/fail evidence in the local incident timeline.",
        ],
        "rollback_checks": [
            "test client uses NL daily profile again",
            "secondary profile is inactive",
            "no bulk user profile change was made",
            "NL was not changed",
            "SPB was not used",
        ],
        "forbidden_material": FORBIDDEN_MATERIAL,
        "mutation_allowed": False,
        "nl_mutation_allowed": False,
        "spb_fallback_allowed": False,
        "automatic_failover_allowed": False,
    }


def render_markdown(payload: dict[str, Any]) -> str:
    summary = payload["summary"]
    lines = [
        "# Secondary Exit Manual Drill",
        "",
        f"generated_at: `{payload['generated_at']}`",
        f"status: `{payload['status']}`",
        f"ok: `{str(payload['ok']).lower()}`",
        "",
        "## Summary",
        "",
        "```text",
        f"manual_probe_allowed={str(summary.get('manual_probe_allowed')).lower()}",
        f"manual_switch_allowed={str(summary.get('manual_switch_allowed')).lower()}",
        f"candidate_configured={str(summary.get('candidate_configured')).lower()}",
        f"endpoint_count={summary.get('endpoint_count')}",
        f"secondary_flow_status={summary.get('secondary_flow_status')}",
        f"secondary_probe_status={summary.get('secondary_probe_status')}",
        f"provisioning_plan_status={summary.get('provisioning_plan_status')}",
        f"test_scope={summary.get('test_scope')}",
        f"bulk_user_switch_allowed={str(summary.get('bulk_user_switch_allowed')).lower()}",
        f"rollback_required={str(summary.get('rollback_required')).lower()}",
        f"safe_flags={str(summary.get('safe_flags')).lower()}",
        "nl_write_allowed=false",
        "spb_fallback_allowed=false",
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
    lines.extend(["## Test Client Steps", ""])
    lines.extend(f"- {value}" for value in payload["test_client_steps"])
    lines.extend(["", "## Rollback Checks", ""])
    lines.extend(f"- {value}" for value in payload["rollback_checks"])
    lines.extend(["", "## Forbidden Material", ""])
    lines.extend(f"- {value}" for value in payload["forbidden_material"])
    lines.extend(["", "No NL or SPB writes were performed by this manual drill plan."])
    return "\n".join(lines) + "\n"


def main() -> int:
    parser = argparse.ArgumentParser(description="Build secondary exit manual drill plan")
    parser.add_argument("--failover-readiness", default=str(DEFAULT_FAILOVER_READINESS))
    parser.add_argument("--secondary-flow", default=str(DEFAULT_SECONDARY_FLOW))
    parser.add_argument("--provisioning-plan", default=str(DEFAULT_PROVISIONING_PLAN))
    parser.add_argument("--json-out", default=str(DEFAULT_JSON_OUT))
    parser.add_argument("--markdown-out", default=str(DEFAULT_MARKDOWN_OUT))
    args = parser.parse_args()

    payload = build_payload(
        failover_readiness=read_json(Path(args.failover_readiness)),
        secondary_flow=read_json(Path(args.secondary_flow)),
        provisioning_plan=read_json(Path(args.provisioning_plan)),
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
