#!/usr/bin/env python3
"""Build a safe public-metadata template for the selected secondary exit.

The template is an operator aid for filling secondary-exit-candidates.example.json
after an external server has been provisioned. It does not provision servers,
does not write the candidate file, does not store VPN secrets, and does not
contact NL/SPB.
"""

from __future__ import annotations

import argparse
from datetime import datetime, timezone
import json
from pathlib import Path
from typing import Any


ROOT = Path("/mnt/projects")
DIAGNOSTICS_DIR = ROOT / "nl-diagnostics"
DEFAULT_SELECTION_PACKET = DIAGNOSTICS_DIR / "secondary-exit-selection-packet-2026-05-28.json"
DEFAULT_CANDIDATE_INTAKE = DIAGNOSTICS_DIR / "secondary-exit-candidate-intake-2026-05-28.json"
DEFAULT_CANDIDATE_FILE = DIAGNOSTICS_DIR / "secondary-exit-candidates.example.json"
DEFAULT_JSON_OUT = DIAGNOSTICS_DIR / "secondary-exit-public-metadata-template-2026-05-28.json"
DEFAULT_MARKDOWN_OUT = DIAGNOSTICS_DIR / "secondary-exit-public-metadata-template-2026-05-28.md"


FORBIDDEN_MATERIAL = [
    "raw VPN URI",
    "UUID",
    "private key",
    "provider API token",
    "bot token",
    "subscription link",
    "SSH private key",
    "root password",
    "billing data",
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


def select_primary(selection_packet: dict[str, Any]) -> dict[str, Any]:
    rows = selection_packet.get("operator_decision_order")
    if not isinstance(rows, list):
        return {}
    for row in rows:
        if isinstance(row, dict) and row.get("selection_role") == "primary_pick":
            return row
    for row in rows:
        if isinstance(row, dict):
            return row
    return {}


def candidate_template(primary: dict[str, Any]) -> dict[str, Any]:
    return {
        "label": primary.get("label", "FILL_SELECTED_LABEL"),
        "provider": primary.get("provider", "FILL_PUBLIC_PROVIDER_NAME"),
        "country": primary.get("country", "FILL_PUBLIC_COUNTRY"),
        "region": primary.get("region", "FILL_PUBLIC_REGION"),
        "host": "FILL_PUBLIC_IPV4_OR_HOST_AFTER_PROVISIONING",
        "tcp_ports": primary.get("expected_tcp_ports") if isinstance(primary.get("expected_tcp_ports"), list) else [443],
        "notes": "public metadata only; no VPN URI, UUID, private key, token, password, or subscription link",
    }


def safe_selection(selection_packet: dict[str, Any], candidate_intake: dict[str, Any]) -> bool:
    summary = selection_packet.get("summary") or {}
    intake_summary = candidate_intake.get("summary") or {}
    return all(
        [
            flag_is_false(selection_packet, "nl_mutation_allowed"),
            flag_is_false(selection_packet, "spb_fallback_allowed"),
            flag_is_false(selection_packet, "automatic_failover_allowed"),
            flag_is_false(candidate_intake, "nl_mutation_allowed"),
            flag_is_false(candidate_intake, "spb_fallback_allowed"),
            flag_is_false(candidate_intake, "automatic_failover_allowed"),
            summary.get("nl_write_allowed") is False,
            summary.get("spb_fallback_allowed") is False,
            summary.get("automatic_failover_allowed") is False,
            summary.get("may_create_endpoint_now") is False,
            intake_summary.get("nl_write_allowed") is False,
            intake_summary.get("spb_fallback_allowed") is False,
            intake_summary.get("automatic_failover_allowed") is False,
        ]
    )


def build_payload(
    *,
    selection_packet: dict[str, Any],
    candidate_intake: dict[str, Any],
    candidate_file: Path,
) -> dict[str, Any]:
    primary = select_primary(selection_packet)
    selection_summary = selection_packet.get("summary") or {}
    intake_summary = candidate_intake.get("summary") or {}
    endpoint_count = int(selection_summary.get("endpoint_count") or 0)
    safe = safe_selection(selection_packet, candidate_intake)
    has_primary = bool(primary)
    if not safe:
        status = "public_metadata_template_unsafe_flags"
    elif has_primary and endpoint_count == 0:
        status = "public_metadata_template_ready_no_endpoint"
    elif has_primary:
        status = "public_metadata_template_ready_for_public_metadata"
    else:
        status = "public_metadata_template_needs_selection"
    template = candidate_template(primary)

    return {
        "schema_version": 1,
        "source": "nl-diagnostics/build_secondary_exit_public_metadata_template.py",
        "generated_at": datetime.now(timezone.utc).isoformat(),
        "status": status,
        "ok": safe and has_primary,
        "summary": {
            "selected_label": template["label"],
            "selected_provider": template["provider"],
            "selected_country": template["country"],
            "selected_region": template["region"],
            "endpoint_count": endpoint_count,
            "candidate_file": str(candidate_file),
            "candidate_intake_status": candidate_intake.get("status", "missing"),
            "candidate_score_status": intake_summary.get("candidate_score_status", "missing"),
            "template_candidate_count": 1 if has_primary else 0,
            "forbidden_material_count": len(FORBIDDEN_MATERIAL),
            "candidate_file_update_allowed": endpoint_count > 0 and safe and has_primary,
            "external_action_required": True,
            "nl_write_allowed": False,
            "spb_fallback_allowed": False,
            "automatic_failover_allowed": False,
        },
        "candidate_file_template": {
            "schema_version": 1,
            "purpose": "Public metadata only for future secondary exit scoring. No secrets.",
            "candidates": [template] if has_primary else [],
        },
        "forbidden_material": FORBIDDEN_MATERIAL,
        "safe_local_steps": [
            "Provision the selected server externally first; do not store provider credentials in repo.",
            "Replace only host with the public IPv4 or DNS name after provisioning.",
            f"Save public metadata locally in {candidate_file} only after the endpoint exists.",
            "Run the candidate scorer, refresh, and readiness audit before any probe config or client test.",
            "Keep VPN profile secrets outside repository and outside diagnostic reports.",
        ],
        "validation_commands": [
            f"TMPDIR=/mnt/projects/.tmp python3 nl-diagnostics/score_secondary_exit_candidates.py --candidates {candidate_file}",
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
        "# Secondary Exit Public Metadata Template",
        "",
        f"generated_at: `{payload['generated_at']}`",
        f"status: `{payload['status']}`",
        f"ok: `{str(payload['ok']).lower()}`",
        "",
        "## Summary",
        "",
        "```text",
        f"selected_label={summary.get('selected_label')}",
        f"selected_provider={summary.get('selected_provider')}",
        f"selected_country={summary.get('selected_country')}",
        f"selected_region={summary.get('selected_region')}",
        f"endpoint_count={summary.get('endpoint_count')}",
        f"candidate_file={summary.get('candidate_file')}",
        f"candidate_intake_status={summary.get('candidate_intake_status')}",
        f"candidate_score_status={summary.get('candidate_score_status')}",
        f"template_candidate_count={summary.get('template_candidate_count')}",
        f"forbidden_material_count={summary.get('forbidden_material_count')}",
        f"candidate_file_update_allowed={str(summary.get('candidate_file_update_allowed')).lower()}",
        f"external_action_required={str(summary.get('external_action_required')).lower()}",
        "nl_write_allowed=false",
        "spb_fallback_allowed=false",
        "automatic_failover_allowed=false",
        "```",
        "",
        "## Candidate File Template",
        "",
        "```json",
        json.dumps(payload["candidate_file_template"], indent=2, ensure_ascii=False),
        "```",
        "",
        "## Forbidden Material",
        "",
    ]
    lines.extend(f"- {value}" for value in payload["forbidden_material"])
    lines.extend(["", "## Safe Local Steps", ""])
    lines.extend(f"- {value}" for value in payload["safe_local_steps"])
    lines.extend(["", "## Validation Commands", "", "```bash"])
    lines.extend(payload["validation_commands"])
    lines.extend(["```", ""])
    lines.append("No candidate file update, NL write, or SPB fallback was performed by this template.")
    return "\n".join(lines) + "\n"


def main() -> int:
    parser = argparse.ArgumentParser(description="Build secondary exit public metadata template")
    parser.add_argument("--selection-packet", default=str(DEFAULT_SELECTION_PACKET))
    parser.add_argument("--candidate-intake", default=str(DEFAULT_CANDIDATE_INTAKE))
    parser.add_argument("--candidate-file", default=str(DEFAULT_CANDIDATE_FILE))
    parser.add_argument("--json-out", default=str(DEFAULT_JSON_OUT))
    parser.add_argument("--markdown-out", default=str(DEFAULT_MARKDOWN_OUT))
    args = parser.parse_args()

    payload = build_payload(
        selection_packet=read_json(Path(args.selection_packet)),
        candidate_intake=read_json(Path(args.candidate_intake)),
        candidate_file=Path(args.candidate_file),
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
