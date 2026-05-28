#!/usr/bin/env python3
"""Build a safe symptom-intake checklist for future VPN incidents.

The intake report tells an operator what non-secret user-visible facts to
collect before deciding whether an issue is app blocking, local client trouble,
provider trouble, or an NL service problem. It does not connect to NL/SPB and
does not mutate VPN state.
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
DEFAULT_OPERATOR_CARD = DIAGNOSTICS_DIR / "vpn-operator-card-2026-05-28.json"
DEFAULT_HISTORY = DIAGNOSTICS_DIR / "blocking-probe-history-2026-05-28.json"
DEFAULT_TRANSPORT_PROBE = DIAGNOSTICS_DIR / "nl-transport-probe-2026-05-28.json"
DEFAULT_FAILOVER_READINESS = DIAGNOSTICS_DIR / "manual-failover-readiness-2026-05-28.json"
DEFAULT_JSON_OUT = DIAGNOSTICS_DIR / "vpn-incident-symptom-intake-2026-05-28.json"
DEFAULT_MARKDOWN_OUT = DIAGNOSTICS_DIR / "vpn-incident-symptom-intake-2026-05-28.md"


REQUIRED_FIELDS = [
    "visible_time_local",
    "affected_app_or_site",
    "symptom_text",
    "network_type",
    "isp_or_mobile_operator",
    "device_os",
    "vpn_client_name",
    "profile_label_without_uri",
    "direct_without_vpn_result",
    "vpn_result",
    "telegram_web_calls_media_separately",
    "other_users_affected",
]

FORBIDDEN_MATERIAL = [
    "raw VPN URI",
    "UUID",
    "private key",
    "bot token",
    "subscription link",
    "passwords",
    "provider API token",
    "billing data",
    "personal chats",
    "full screenshots with private data",
    "NL endpoint",
    "SPB endpoint",
]

TRIAGE_GROUPS = [
    "core_transport",
    "app_specific",
    "exit_ip_rejected",
    "local_client",
    "mobile_vs_fixed",
    "provider_host",
]


def read_json(path: Path) -> dict[str, Any]:
    try:
        value = json.loads(path.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError):
        return {}
    return value if isinstance(value, dict) else {}


def flag_is_false(payload: dict[str, Any], key: str) -> bool:
    return payload.get(key) is False


def choose_status(*, safe: bool, decision_name: str, operator_status: str) -> str:
    if not safe:
        return "symptom_intake_unsafe_flags"
    if decision_name == "observe" and operator_status == "observe":
        return "symptom_intake_ready_observe"
    if decision_name in {"provider_ticket", "failover", "nl_readonly_review", "manual_profile_review"}:
        return "symptom_intake_ready_incident"
    return "symptom_intake_ready_review"


def build_payload(
    *,
    decision_report: dict[str, Any],
    operator_card: dict[str, Any],
    blocking_history: dict[str, Any],
    transport_probe: dict[str, Any],
    failover_readiness: dict[str, Any],
) -> dict[str, Any]:
    decision = decision_report.get("decision") or {}
    classification = decision_report.get("classification") or {}
    operator = operator_card.get("operator") or {}
    history_summary = blocking_history.get("summary") or {}
    latest_history = history_summary.get("latest") or {}
    readiness_summary = failover_readiness.get("summary") or {}
    decision_name = str(decision.get("decision") or "missing")
    operator_status = str(operator.get("operator_status") or "missing")
    safe = all(
        [
            flag_is_false(decision_report, "nl_mutation_allowed"),
            flag_is_false(decision_report, "spb_fallback_allowed"),
            flag_is_false(decision_report, "auto_profile_switch_allowed"),
            flag_is_false(decision, "nl_mutation_allowed"),
            flag_is_false(decision, "spb_fallback_allowed"),
            flag_is_false(decision, "auto_profile_switch_allowed"),
            flag_is_false(operator_card, "nl_mutation_allowed"),
            flag_is_false(operator_card, "spb_fallback_allowed"),
            flag_is_false(operator_card, "automatic_failover_allowed"),
            flag_is_false(transport_probe, "nl_mutation_allowed"),
            flag_is_false(transport_probe, "spb_fallback_allowed"),
            flag_is_false(transport_probe, "automatic_failover_allowed"),
            flag_is_false(failover_readiness, "nl_mutation_allowed"),
            flag_is_false(failover_readiness, "spb_fallback_allowed"),
            flag_is_false(failover_readiness, "automatic_failover_allowed"),
            readiness_summary.get("nl_write_allowed") is False,
            readiness_summary.get("automatic_failover_allowed") is False,
        ]
    )
    status = choose_status(safe=safe, decision_name=decision_name, operator_status=operator_status)

    return {
        "schema_version": 1,
        "source": "nl-diagnostics/build_vpn_incident_symptom_intake.py",
        "generated_at": datetime.now(timezone.utc).isoformat(),
        "status": status,
        "ok": safe,
        "summary": {
            "decision": decision_name,
            "operator_status": operator_status,
            "transport_status": classification.get("transport_status", "missing"),
            "failure_domain": classification.get("failure_domain", "missing"),
            "provider_status": classification.get("provider_status", "missing"),
            "blocking_history_trend": history_summary.get("trend", "missing"),
            "blocking_history_snapshot_count": history_summary.get("snapshot_count", 0),
            "latest_blocking_targets_ok": (
                f"{latest_history.get('ok_count', 'missing')}/{latest_history.get('target_count', 'missing')}"
            ),
            "nl_transport_probe_status": transport_probe.get("status", "missing"),
            "manual_failover_readiness_status": failover_readiness.get("status", "missing"),
            "manual_switch_allowed": failover_readiness.get("manual_switch_allowed", "missing"),
            "required_field_count": len(REQUIRED_FIELDS),
            "allowed_field_count": len(REQUIRED_FIELDS),
            "forbidden_material_count": len(FORBIDDEN_MATERIAL),
            "triage_group_count": len(TRIAGE_GROUPS),
            "nl_write_allowed": False,
            "spb_fallback_allowed": False,
            "automatic_failover_allowed": False,
        },
        "required_fields": REQUIRED_FIELDS,
        "allowed_fields": REQUIRED_FIELDS,
        "forbidden_material": FORBIDDEN_MATERIAL,
        "triage_groups": TRIAGE_GROUPS,
        "intake_questions": [
            "When did the visible problem start, in local time?",
            "Which exact app, site, or feature fails?",
            "Does generic HTTPS browsing work through the VPN?",
            "Does the same app/site work without the VPN?",
            "Is the user on mobile data, home Wi-Fi, office network, or another network?",
            "Which ISP or mobile operator is used?",
            "Is the failure limited to Telegram media/calls, Telegram web/API, Russian sites, AI/dev sites, or everything?",
            "Are other users affected at the same time?",
        ],
        "classification_hints": [
            "one app fails while core VPN works -> app_specific_degradation",
            "Russian site rejects VPN but tunnel works -> exit_ip_or_vpn_rejected",
            "mobile fails but fixed-line works -> ISP/path-specific suspicion",
            "direct path works but SOCKS/VPN path fails -> vpn_path_degraded",
            "direct path fails but VPN works -> possible_local_isp_block",
            "NL transport ports fail from outside -> collect fresh read-only snapshot and provider packet",
        ],
        "safe_local_steps": [
            "Collect only the required symptom fields locally; do not paste secrets into chat.",
            "Run VPN_ENABLE_BLOCKING_PROBES=1 /mnt/projects/nl-diagnostics/run_vpn_incident_readonly_refresh.sh",
            "Compare the refreshed decision and operator-card reports.",
            "If only one app or service fails, keep observe and use the blocking/app policy; do not restart NL.",
            "Keep failover blocked unless the readiness audit explicitly allows manual probe and manual switch.",
        ],
        "safe_local_commands": [
            "VPN_ENABLE_BLOCKING_PROBES=1 /mnt/projects/nl-diagnostics/run_vpn_incident_readonly_refresh.sh",
            "sed -n '1,120p' /mnt/projects/nl-diagnostics/vpn-planning-refresh-2026-05-28.md",
            "sed -n '1,160p' /mnt/projects/nl-diagnostics/vpn-operator-card-2026-05-28.md",
        ],
        "blocked_actions": [
            "Do not ask for raw VPN profile URIs, UUIDs, private keys, bot tokens, or subscription links.",
            "Do not restart NL for one-app or Telegram-media-only symptoms.",
            "Do not auto-switch profiles from symptom intake alone.",
            "Do not use SPB while SPB is disabled.",
        ],
        "mutation_allowed": False,
        "nl_mutation_allowed": False,
        "spb_fallback_allowed": False,
        "automatic_failover_allowed": False,
    }


def render_markdown(payload: dict[str, Any]) -> str:
    summary = payload["summary"]
    lines = [
        "# VPN Incident Symptom Intake",
        "",
        f"generated_at: `{payload['generated_at']}`",
        f"status: `{payload['status']}`",
        f"ok: `{str(payload['ok']).lower()}`",
        "",
        "## Summary",
        "",
        "```text",
        f"decision={summary.get('decision')}",
        f"operator_status={summary.get('operator_status')}",
        f"transport_status={summary.get('transport_status')}",
        f"failure_domain={summary.get('failure_domain')}",
        f"provider_status={summary.get('provider_status')}",
        f"blocking_history_trend={summary.get('blocking_history_trend')}",
        f"blocking_history_snapshot_count={summary.get('blocking_history_snapshot_count')}",
        f"latest_blocking_targets_ok={summary.get('latest_blocking_targets_ok')}",
        f"nl_transport_probe_status={summary.get('nl_transport_probe_status')}",
        f"manual_failover_readiness_status={summary.get('manual_failover_readiness_status')}",
        f"manual_switch_allowed={str(summary.get('manual_switch_allowed')).lower()}",
        f"required_field_count={summary.get('required_field_count')}",
        f"allowed_field_count={summary.get('allowed_field_count')}",
        f"forbidden_material_count={summary.get('forbidden_material_count')}",
        f"triage_group_count={summary.get('triage_group_count')}",
        "nl_write_allowed=false",
        "spb_fallback_allowed=false",
        "automatic_failover_allowed=false",
        "```",
        "",
        "## Required Fields",
        "",
    ]
    lines.extend(f"- `{value}`" for value in payload["required_fields"])
    lines.extend(["", "## Forbidden Material", ""])
    lines.extend(f"- {value}" for value in payload["forbidden_material"])
    lines.extend(["", "## Triage Groups", ""])
    lines.extend(f"- `{value}`" for value in payload["triage_groups"])
    lines.extend(["", "## Intake Questions", ""])
    lines.extend(f"- {value}" for value in payload["intake_questions"])
    lines.extend(["", "## Classification Hints", ""])
    lines.extend(f"- {value}" for value in payload["classification_hints"])
    lines.extend(["", "## Safe Local Steps", ""])
    lines.extend(f"- {value}" for value in payload["safe_local_steps"])
    lines.extend(["", "## Safe Local Commands", "", "```bash"])
    lines.extend(payload["safe_local_commands"])
    lines.extend(["```", "", "## Blocked Actions", ""])
    lines.extend(f"- {value}" for value in payload["blocked_actions"])
    lines.extend(["", "No NL or SPB writes were performed by this symptom intake report."])
    return "\n".join(lines) + "\n"


def main() -> int:
    parser = argparse.ArgumentParser(description="Build VPN incident symptom intake checklist")
    parser.add_argument("--decision", default=str(DEFAULT_DECISION))
    parser.add_argument("--operator-card", default=str(DEFAULT_OPERATOR_CARD))
    parser.add_argument("--history", default=str(DEFAULT_HISTORY))
    parser.add_argument("--transport-probe", default=str(DEFAULT_TRANSPORT_PROBE))
    parser.add_argument("--failover-readiness", default=str(DEFAULT_FAILOVER_READINESS))
    parser.add_argument("--json-out", default=str(DEFAULT_JSON_OUT))
    parser.add_argument("--markdown-out", default=str(DEFAULT_MARKDOWN_OUT))
    args = parser.parse_args()

    payload = build_payload(
        decision_report=read_json(Path(args.decision)),
        operator_card=read_json(Path(args.operator_card)),
        blocking_history=read_json(Path(args.history)),
        transport_probe=read_json(Path(args.transport_probe)),
        failover_readiness=read_json(Path(args.failover_readiness)),
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
