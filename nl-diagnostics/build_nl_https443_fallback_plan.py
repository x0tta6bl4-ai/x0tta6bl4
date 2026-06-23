#!/usr/bin/env python3
"""Build a local plan for a standard HTTPS 443 VPN fallback.

This plan reacts to the current NL shape where raw Reality owns public 443 and
XHTTP/WS fallbacks are published on 8443. It records why another port rotation
is not enough after a user reports that every configured port failed.

The script is planning evidence only: it does not contact NL, does not restart
services, does not write x-ui/nginx/systemd, and does not store VPN secrets.
"""

from __future__ import annotations

import argparse
from datetime import datetime, timezone
import json
from pathlib import Path
import re
from typing import Any


ROOT = Path("/mnt/projects")
DIAGNOSTICS_DIR = ROOT / "nl-diagnostics"
PROFILE_ROOT = DIAGNOSTICS_DIR / "nl-server-profile"
DEFAULT_ROLLOUT = DIAGNOSTICS_DIR / "nl-anti-block-rollout-2026-06-01.md"
DEFAULT_PRODUCTION_AUDIT = DIAGNOSTICS_DIR / "nl-anti-block-production-audit-2026-06-02.json"
DEFAULT_TRANSPORT_PROBE = DIAGNOSTICS_DIR / "nl-transport-probe-2026-06-02-now.json"
DEFAULT_SECONDARY_PROVISIONING_PLAN = DIAGNOSTICS_DIR / "secondary-exit-provisioning-plan-2026-05-28.json"
DEFAULT_JSON_OUT = DIAGNOSTICS_DIR / "nl-https443-fallback-plan-2026-06-02.json"
DEFAULT_MARKDOWN_OUT = DIAGNOSTICS_DIR / "nl-https443-fallback-plan-2026-06-02.md"

CONFIRM_TOKEN = "APPLY_HTTPS443_FALLBACK_PLAN"
PASS = "pass"
BLOCKED = "blocked"
READY = "ready"


def latest_profile_dir(root: Path = PROFILE_ROOT) -> Path | None:
    if not root.exists():
        return None
    candidates = [path for path in root.iterdir() if path.is_dir() and path.name[:8].isdigit()]
    return sorted(candidates)[-1] if candidates else None


def read_text(path: Path) -> str:
    try:
        return path.read_text(encoding="utf-8")
    except OSError:
        return ""


def read_jsonish(path: Path) -> dict[str, Any]:
    text = read_text(path).strip()
    if not text:
        return {}
    decoder = json.JSONDecoder()
    for index, char in enumerate(text):
        if char in "{[":
            try:
                value, end = decoder.raw_decode(text[index:])
            except json.JSONDecodeError:
                continue
            next_char_index = index + end
            if next_char_index < len(text) and not text[next_char_index].isspace():
                continue
            return value if isinstance(value, dict) else {"items": value}
    return {}


def public_inbounds(config_summary: dict[str, Any]) -> list[dict[str, Any]]:
    rows = config_summary.get("inbounds")
    if not isinstance(rows, list):
        return []
    return [
        row
        for row in rows
        if isinstance(row, dict)
        and row.get("listen") != "127.0.0.1"
        and isinstance(row.get("port"), int)
    ]


def has_reality_443(config_summary: dict[str, Any]) -> bool:
    return any(
        row.get("port") == 443
        and row.get("protocol") == "vless"
        and row.get("network") == "tcp"
        and row.get("security") == "reality"
        for row in public_inbounds(config_summary)
    )


def listener_owner_for_port(listeners_text: str, port: int) -> str:
    pattern = re.compile(rf"(?:^|\s)(?:\*|0\.0\.0\.0|\[::\]):{port}(?:\s|$)")
    for line in listeners_text.splitlines():
        if pattern.search(line) and "LISTEN" in line:
            if 'users:(("nginx"' in line:
                return "nginx"
            if 'users:(("xray' in line or 'users:(("xray-linux' in line:
                return "xray"
            if 'users:(("x-ui"' in line:
                return "x-ui"
            return "other"
    return "missing"


def audit_required_port(production_audit: dict[str, Any]) -> int | None:
    matrix = production_audit.get("client_compatibility_matrix") or {}
    session = matrix.get("current_evidence_session") or {}
    port = session.get("required_port")
    return port if isinstance(port, int) else None


def audit_required_transport(production_audit: dict[str, Any]) -> str:
    matrix = production_audit.get("client_compatibility_matrix") or {}
    session = matrix.get("current_evidence_session") or {}
    return str(session.get("required_transport") or "missing")


def transport_probe_ports(transport_probe: dict[str, Any]) -> list[int]:
    ports: list[int] = []
    rows = transport_probe.get("ports")
    if isinstance(rows, list):
        for row in rows:
            if isinstance(row, int):
                ports.append(row)
            elif isinstance(row, dict) and isinstance(row.get("port"), int):
                ports.append(row["port"])
    if not ports and isinstance(transport_probe.get("results"), list):
        for row in transport_probe["results"]:
            if isinstance(row, dict) and isinstance(row.get("port"), int):
                ports.append(row["port"])
    return ports


def transport_probe_status(transport_probe: dict[str, Any]) -> str:
    summary = transport_probe.get("summary") or {}
    return str(transport_probe.get("status") or summary.get("status") or "missing")


def make_gate(
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
        "ok": status in {PASS, READY, BLOCKED},
        "evidence": evidence,
        "next_step": next_step,
    }


def build_payload(
    *,
    profile_dir: Path | None,
    config_summary: dict[str, Any],
    listeners_text: str,
    rollout_text: str,
    production_audit: dict[str, Any],
    transport_probe: dict[str, Any],
    secondary_provisioning_plan: dict[str, Any],
    user_report_all_config_ports_failed: bool,
) -> dict[str, Any]:
    public_443_owner = listener_owner_for_port(listeners_text, 443)
    nginx_8443_owner = listener_owner_for_port(listeners_text, 8443)
    reality_443 = has_reality_443(config_summary)
    required_port = audit_required_port(production_audit)
    required_transport = audit_required_transport(production_audit)
    current_fallback_8443 = required_port == 8443 and required_transport == "xhttp"
    rollout_has_xhttp_8443 = "VLESS over TLS XHTTP" in rollout_text and "8443" in rollout_text
    rollout_has_ws_8443 = "VLESS over TLS WebSocket" in rollout_text and "8443" in rollout_text
    secondary_status = str(secondary_provisioning_plan.get("status") or "missing")
    secondary_endpoint_count = int((secondary_provisioning_plan.get("summary") or {}).get("endpoint_count") or 0)

    server_state_verified = bool(profile_dir and config_summary and listeners_text)
    current_gap_verified = all(
        [
            server_state_verified,
            reality_443,
            public_443_owner == "xray",
            nginx_8443_owner == "nginx",
            current_fallback_8443,
            rollout_has_xhttp_8443,
        ]
    )
    needs_443_fallback = current_gap_verified and user_report_all_config_ports_failed

    if needs_443_fallback:
        decision = "HTTPS443_FALLBACK_REQUIRED"
        status = "ready_to_prepare_secondary_https443_endpoint"
    elif current_gap_verified:
        decision = "RESTRICTED_NETWORK_EVIDENCE_REQUIRED"
        status = "collect_work_wifi_result_first"
    else:
        decision = "CURRENT_STATE_NEEDS_RECHECK"
        status = "blocked_missing_current_state_evidence"

    gates = [
        make_gate(
            "STATE-01",
            "Current NL 443 owner is known",
            PASS if server_state_verified and public_443_owner != "missing" else BLOCKED,
            [
                f"profile_dir={profile_dir or 'missing'}",
                f"public_443_owner={public_443_owner}",
                f"reality_443={str(reality_443).lower()}",
                f"nginx_8443_owner={nginx_8443_owner}",
            ],
            "refresh the read-only NL profile before any future staging",
        ),
        make_gate(
            "FALLBACK-01",
            "Existing fallback is on 8443, not standard 443",
            PASS if current_fallback_8443 and rollout_has_xhttp_8443 else BLOCKED,
            [
                f"audit_required_transport={required_transport}",
                f"audit_required_port={required_port or 'missing'}",
                f"rollout_has_xhttp_8443={str(rollout_has_xhttp_8443).lower()}",
                f"rollout_has_ws_8443={str(rollout_has_ws_8443).lower()}",
            ],
            "stop treating additional port tries as the main fix",
        ),
        make_gate(
            "USER-01",
            "User reports every configured port failed",
            PASS if user_report_all_config_ports_failed else BLOCKED,
            [
                f"user_report_all_config_ports_failed={str(user_report_all_config_ports_failed).lower()}",
                f"local_transport_probe_status={transport_probe_status(transport_probe)}",
                f"local_transport_probe_ports={','.join(map(str, transport_probe_ports(transport_probe))) or 'missing'}",
            ],
            "treat the work-network cause as unverified but stop relying on current ports",
        ),
        make_gate(
            "BLAST-01",
            "In-place 443 move would affect existing Reality users",
            BLOCKED if reality_443 and public_443_owner == "xray" else PASS,
            [
                f"public_443_owner={public_443_owner}",
                f"reality_443={str(reality_443).lower()}",
                "safe_in_place_move=false" if reality_443 else "safe_in_place_move=unknown",
            ],
            "do not move public 443 from Reality to nginx until a tested replacement path exists",
        ),
        make_gate(
            "SECONDARY-01",
            "Independent HTTPS 443 endpoint is the low-blast-radius path",
            READY if secondary_status == "provisioning_plan_ready_no_endpoint" and secondary_endpoint_count == 0 else BLOCKED,
            [
                f"secondary_provisioning_status={secondary_status}",
                f"secondary_endpoint_count={secondary_endpoint_count}",
                "required_public_port=443",
            ],
            "provision and validate a non-NL/non-SPB endpoint with public HTTPS 443 before user migration",
        ),
    ]

    return {
        "schema_version": 1,
        "source": "nl-diagnostics/build_nl_https443_fallback_plan.py",
        "generated_at": datetime.now(timezone.utc).isoformat(),
        "decision": decision,
        "status": status,
        "ok": current_gap_verified,
        "summary": {
            "profile_dir": str(profile_dir) if profile_dir else "missing",
            "server_state_verified": server_state_verified,
            "current_gap_verified": current_gap_verified,
            "user_report_all_config_ports_failed": user_report_all_config_ports_failed,
            "work_network_cause_verified": False,
            "verified_gap": "no XHTTP/WS fallback on public standard HTTPS 443" if current_gap_verified else "missing",
            "public_443_owner": public_443_owner,
            "public_443_protocol": "VLESS Reality TCP" if reality_443 else "missing_or_other",
            "fallback_public_port": required_port,
            "fallback_transport": required_transport,
            "nginx_https_port": 8443 if nginx_8443_owner == "nginx" else None,
            "local_transport_probe_status": transport_probe_status(transport_probe),
            "secondary_provisioning_status": secondary_status,
            "recommended_primary_path": "new_or_independent_https443_endpoint",
            "in_place_nl_443_change_allowed_now": False,
            "nl_write_allowed": False,
            "spb_fallback_allowed": False,
            "automatic_failover_allowed": False,
        },
        "recommended_path": [
            {
                "id": "PREP-01",
                "title": "Keep current NL Reality 443 alive during preparation",
                "reason": "public 443 currently serves existing Reality clients",
                "mutation_allowed": False,
            },
            {
                "id": "EDGE-01",
                "title": "Prepare an independent public HTTPS 443 fallback endpoint",
                "reason": "this avoids moving the current NL 443 listener before replacement is proven",
                "minimum_endpoint_shape": {
                    "public_tcp_port": 443,
                    "tls_terminator": "nginx_or_equivalent",
                    "fallback_transports": ["xhttp", "ws"],
                    "paths": ["/ghost-xhttp", "/ghost-ws"],
                    "profile_secret_storage_in_repo": False,
                },
            },
            {
                "id": "CANARY-01",
                "title": "Canary with one admin client before subscription promotion",
                "required_evidence": [
                    "tcp_443_reachable_from_non-server_network",
                    "xhttp_dataplane_ok",
                    "ws_dataplane_ok",
                    "work_wifi_or_restricted_wifi_pass",
                    "mobile_network_pass",
                ],
            },
            {
                "id": "SUBSCRIPTION-01",
                "title": "Promote HTTPS 443 fallback first only after canary passes",
                "resulting_order": ["xhttp:443", "ws:443", "reality:443", "reality:2083", "reality:39829"],
            },
        ],
        "rejected_shortcuts": [
            "try more current ports",
            "move NL public 443 from Reality to nginx without tested replacement",
            "enable automatic failover",
            "use SPB fallback",
            "store raw VPN URIs or UUIDs in local reports",
        ],
        "approval_gate": {
            "required_for_any_nl_write": True,
            "confirm_token": CONFIRM_TOKEN,
            "allowed_before_confirm": [
                "local plan generation",
                "read-only NL profile refresh",
                "public TCP probe of a non-secret candidate endpoint",
            ],
            "forbidden_before_confirm": [
                "restart x-ui",
                "reload nginx",
                "edit x-ui database",
                "edit /usr/local/x-ui/bin/config.json",
                "change systemd units on NL",
                "change bot subscription delivery on NL",
            ],
        },
        "acceptance_criteria": [
            "public HTTPS 443 fallback endpoint exists and is not the current raw Reality listener",
            "XHTTP and WebSocket dataplane tests pass through public 443",
            "subscription output contains xhttp:443 before legacy Reality entries",
            "at least one work/restricted Wi-Fi client passes",
            "at least one mobile network client passes",
            "rollback keeps the old NL Reality 443 profile available",
        ],
        "gates": gates,
        "mutation_allowed": False,
        "nl_mutation_allowed": False,
        "spb_fallback_allowed": False,
        "automatic_failover_allowed": False,
    }


def render_markdown(payload: dict[str, Any]) -> str:
    summary = payload["summary"]
    lines = [
        "# NL HTTPS 443 Fallback Plan",
        "",
        f"generated_at: `{payload['generated_at']}`",
        f"decision: `{payload['decision']}`",
        f"status: `{payload['status']}`",
        f"ok: `{str(payload['ok']).lower()}`",
        "",
        "## Summary",
        "",
        "```text",
        f"profile_dir={summary.get('profile_dir')}",
        f"server_state_verified={str(summary.get('server_state_verified')).lower()}",
        f"current_gap_verified={str(summary.get('current_gap_verified')).lower()}",
        f"user_report_all_config_ports_failed={str(summary.get('user_report_all_config_ports_failed')).lower()}",
        f"work_network_cause_verified={str(summary.get('work_network_cause_verified')).lower()}",
        f"verified_gap={summary.get('verified_gap')}",
        f"public_443_owner={summary.get('public_443_owner')}",
        f"public_443_protocol={summary.get('public_443_protocol')}",
        f"fallback_transport={summary.get('fallback_transport')}",
        f"fallback_public_port={summary.get('fallback_public_port')}",
        f"local_transport_probe_status={summary.get('local_transport_probe_status')}",
        f"recommended_primary_path={summary.get('recommended_primary_path')}",
        f"in_place_nl_443_change_allowed_now={str(summary.get('in_place_nl_443_change_allowed_now')).lower()}",
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

    lines.extend(["", "## Recommended Path", ""])
    for row in payload["recommended_path"]:
        lines.append(f"- `{row['id']}` {row['title']}")

    lines.extend(["", "## Rejected Shortcuts", ""])
    lines.extend(f"- {value}" for value in payload["rejected_shortcuts"])

    gate = payload["approval_gate"]
    lines.extend(
        [
            "",
            "## Approval Gate",
            "",
            f"required_for_any_nl_write={str(gate['required_for_any_nl_write']).lower()}",
            f"confirm_token=`{gate['confirm_token']}`",
            "",
            "Forbidden before confirm:",
        ]
    )
    lines.extend(f"- {value}" for value in gate["forbidden_before_confirm"])

    lines.extend(["", "## Acceptance Criteria", ""])
    lines.extend(f"- {value}" for value in payload["acceptance_criteria"])

    lines.extend(["", "## Evidence", ""])
    for row in payload["gates"]:
        lines.extend([f"### {row['id']}", ""])
        lines.extend(f"- {value}" for value in row["evidence"])
        lines.append("")

    lines.append("No NL or SPB writes were performed by this plan.")
    return "\n".join(lines) + "\n"


def main() -> int:
    parser = argparse.ArgumentParser(description="Build NL HTTPS 443 fallback plan")
    parser.add_argument("--profile-dir")
    parser.add_argument("--rollout", default=str(DEFAULT_ROLLOUT))
    parser.add_argument("--production-audit", default=str(DEFAULT_PRODUCTION_AUDIT))
    parser.add_argument("--transport-probe", default=str(DEFAULT_TRANSPORT_PROBE))
    parser.add_argument("--secondary-provisioning-plan", default=str(DEFAULT_SECONDARY_PROVISIONING_PLAN))
    parser.add_argument("--user-report-all-config-ports-failed", action="store_true")
    parser.add_argument("--json-out", default=str(DEFAULT_JSON_OUT))
    parser.add_argument("--markdown-out", default=str(DEFAULT_MARKDOWN_OUT))
    args = parser.parse_args()

    profile_dir = Path(args.profile_dir) if args.profile_dir else latest_profile_dir()
    config_summary = read_jsonish(profile_dir / "xui" / "config-summary.json") if profile_dir else {}
    listeners_text = read_text(profile_dir / "network" / "listeners.txt") if profile_dir else ""

    payload = build_payload(
        profile_dir=profile_dir,
        config_summary=config_summary,
        listeners_text=listeners_text,
        rollout_text=read_text(Path(args.rollout)),
        production_audit=read_jsonish(Path(args.production_audit)),
        transport_probe=read_jsonish(Path(args.transport_probe)),
        secondary_provisioning_plan=read_jsonish(Path(args.secondary_provisioning_plan)),
        user_report_all_config_ports_failed=args.user_report_all_config_ports_failed,
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
