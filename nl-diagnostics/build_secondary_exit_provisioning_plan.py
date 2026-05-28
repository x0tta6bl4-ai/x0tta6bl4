#!/usr/bin/env python3
"""Build a safe provisioning plan for a future secondary VPN exit node.

The plan describes the external provider-console work needed before a real
secondary candidate can exist. It does not provision servers, does not run SSH,
does not store secrets, does not contact NL/SPB, and does not enable failover.
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
DEFAULT_CANDIDATE_INTAKE = DIAGNOSTICS_DIR / "secondary-exit-candidate-intake-2026-05-28.json"
DEFAULT_REQUIREMENTS = DIAGNOSTICS_DIR / "secondary-exit-requirements-2026-05-28.json"
DEFAULT_JSON_OUT = DIAGNOSTICS_DIR / "secondary-exit-provisioning-plan-2026-05-28.json"
DEFAULT_MARKDOWN_OUT = DIAGNOSTICS_DIR / "secondary-exit-provisioning-plan-2026-05-28.md"


FORBIDDEN_MATERIAL = [
    "provider API token",
    "billing data",
    "SSH private key",
    "root password",
    "raw VPN URI",
    "UUID",
    "private key",
    "bot token",
    "subscription link",
    "NL endpoint",
    "SPB endpoint",
]

PUBLIC_METADATA = [
    "label",
    "provider",
    "country",
    "region",
    "public host/IP",
    "public TCP ports",
    "non-secret notes",
]


def read_json(path: Path) -> dict[str, Any]:
    try:
        value = json.loads(path.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError):
        return {}
    return value if isinstance(value, dict) else {}


def flag_is_false(payload: dict[str, Any], key: str) -> bool:
    return payload.get(key) is False


def safe_sources(*payloads: dict[str, Any]) -> bool:
    return all(
        flag_is_false(payload, "nl_mutation_allowed")
        and flag_is_false(payload, "spb_fallback_allowed")
        and flag_is_false(payload, "automatic_failover_allowed")
        for payload in payloads
    )


def top_shortlist_labels(provider_shortlist: dict[str, Any], limit: int = 3) -> list[str]:
    rows = provider_shortlist.get("shortlist")
    if not isinstance(rows, list):
        return []
    safe_rows = [
        row
        for row in rows
        if isinstance(row, dict)
        and row.get("status") == "shortlist_ready_no_endpoint"
        and str(row.get("country") or "").strip().lower() != "netherlands"
        and "russia" not in str(row.get("country") or "").lower()
    ]
    ordered = sorted(safe_rows, key=lambda row: int(row.get("priority") or 999))
    return [str(row.get("label") or "missing") for row in ordered[:limit]]


def step(
    *,
    step_id: str,
    title: str,
    status: str,
    evidence: list[str],
    next_step: str,
) -> dict[str, Any]:
    return {
        "id": step_id,
        "title": title,
        "status": status,
        "ok": status in {"ready", "external_required", "blocked"},
        "evidence": evidence,
        "next_step": next_step,
    }


def build_payload(
    *,
    provider_shortlist: dict[str, Any],
    candidate_intake: dict[str, Any],
    requirements: dict[str, Any],
) -> dict[str, Any]:
    shortlist_summary = provider_shortlist.get("summary") or {}
    intake_summary = candidate_intake.get("summary") or {}
    requirements_summary = requirements.get("summary") or {}
    shortlist_count = int(shortlist_summary.get("shortlist_count") or 0)
    endpoint_count = int(shortlist_summary.get("endpoint_count") or 0)
    preferred_labels = top_shortlist_labels(provider_shortlist)
    sources_safe = safe_sources(provider_shortlist, candidate_intake, requirements)
    shortlist_ready = provider_shortlist.get("status") == "shortlist_ready_no_endpoint" and shortlist_count > 0
    intake_ready = candidate_intake.get("status") in {
        "awaiting_public_candidate_metadata",
        "candidate_metadata_needs_fix",
        "candidate_metadata_ready",
    }
    requirements_ready = requirements.get("status") in {
        "requirements_ready_no_candidate",
        "requirements_ready_with_candidate",
    }
    ok = sources_safe and shortlist_ready and intake_ready and requirements_ready and endpoint_count == 0
    status = "provisioning_plan_ready_no_endpoint" if ok else "provisioning_plan_needs_attention"

    steps = [
        step(
            step_id="SELECT-01",
            title="Choose one non-NL/non-SPB shortlist option",
            status="ready" if preferred_labels else "blocked",
            evidence=[
                f"shortlist_status={provider_shortlist.get('status', 'missing')}",
                f"shortlist_count={shortlist_count}",
                f"preferred_labels={','.join(preferred_labels) or 'none'}",
            ],
            next_step="choose one of the first three labels unless provider independence check fails",
        ),
        step(
            step_id="ACCOUNT-01",
            title="Use a separate provider project/account where practical",
            status="external_required",
            evidence=[
                "no provider API token is needed in this repository",
                "billing data must stay outside this repository",
            ],
            next_step="create or select the provider project in the provider console, not in repo",
        ),
        step(
            step_id="SERVER-01",
            title="Provision the smallest suitable server in the selected region",
            status="external_required",
            evidence=[
                f"endpoint_count={endpoint_count}",
                "server provisioning is intentionally outside local automation",
            ],
            next_step="create the server manually, then keep only its public host/IP for local planning",
        ),
        step(
            step_id="NETWORK-01",
            title="Expose only a public TCP health target first",
            status="external_required",
            evidence=[
                "default_health_port=443",
                "profile secret generation remains outside repo",
            ],
            next_step="confirm public TCP 443 is reachable before any client profile test",
        ),
        step(
            step_id="CANDIDATE-01",
            title="Add public endpoint metadata to the local candidate file",
            status="blocked" if endpoint_count == 0 else "ready",
            evidence=[
                f"candidate_file={intake_summary.get('candidate_file', 'missing')}",
                f"candidate_intake_status={candidate_intake.get('status', 'missing')}",
                f"allowed_field_count={intake_summary.get('allowed_field_count', 'missing')}",
            ],
            next_step="after provisioning, fill only label/provider/region/country/host/tcp_ports/notes",
        ),
        step(
            step_id="VALIDATE-01",
            title="Run scorer and refresh before generating a probe config",
            status="blocked" if endpoint_count == 0 else "ready",
            evidence=[
                f"requirements_status={requirements.get('status', 'missing')}",
                f"missing_requirements={','.join(requirements_summary.get('missing_items') or []) or 'none'}",
            ],
            next_step="run candidate scorer, then refresh local reports from the latest snapshot",
        ),
    ]

    return {
        "schema_version": 1,
        "source": "nl-diagnostics/build_secondary_exit_provisioning_plan.py",
        "generated_at": datetime.now(timezone.utc).isoformat(),
        "status": status,
        "ok": ok,
        "summary": {
            "shortlist_status": provider_shortlist.get("status", "missing"),
            "shortlist_count": shortlist_count,
            "preferred_labels": preferred_labels,
            "endpoint_count": endpoint_count,
            "external_action_required": True,
            "candidate_file": intake_summary.get(
                "candidate_file",
                str(DIAGNOSTICS_DIR / "secondary-exit-candidates.example.json"),
            ),
            "candidate_intake_status": candidate_intake.get("status", "missing"),
            "requirements_status": requirements.get("status", "missing"),
            "safe_sources": sources_safe,
            "nl_write_allowed": False,
            "spb_fallback_allowed": False,
            "automatic_failover_allowed": False,
        },
        "public_metadata": PUBLIC_METADATA,
        "forbidden_material": FORBIDDEN_MATERIAL,
        "steps": steps,
        "local_validation_commands": [
            (
                "TMPDIR=/mnt/projects/.tmp python3 nl-diagnostics/score_secondary_exit_candidates.py "
                "--candidates /mnt/projects/nl-diagnostics/secondary-exit-candidates.example.json"
            ),
            (
                "TMPDIR=/mnt/projects/.tmp python3 nl-diagnostics/refresh_vpn_planning_reports.py "
                "--snapshot /mnt/projects/nl-diagnostics/snapshots/20260528T011622Z"
            ),
        ],
        "mutation_allowed": False,
        "nl_mutation_allowed": False,
        "spb_fallback_allowed": False,
        "automatic_failover_allowed": False,
    }


def render_markdown(payload: dict[str, Any]) -> str:
    summary = payload["summary"]
    lines = [
        "# Secondary Exit Provisioning Plan",
        "",
        f"generated_at: `{payload['generated_at']}`",
        f"status: `{payload['status']}`",
        f"ok: `{str(payload['ok']).lower()}`",
        "",
        "## Summary",
        "",
        "```text",
        f"shortlist_status={summary.get('shortlist_status')}",
        f"shortlist_count={summary.get('shortlist_count')}",
        f"preferred_labels={','.join(summary.get('preferred_labels') or []) or 'none'}",
        f"endpoint_count={summary.get('endpoint_count')}",
        f"external_action_required={str(summary.get('external_action_required')).lower()}",
        f"candidate_file={summary.get('candidate_file')}",
        f"candidate_intake_status={summary.get('candidate_intake_status')}",
        f"requirements_status={summary.get('requirements_status')}",
        f"safe_sources={str(summary.get('safe_sources')).lower()}",
        "nl_write_allowed=false",
        "spb_fallback_allowed=false",
        "automatic_failover_allowed=false",
        "```",
        "",
        "## Public Metadata",
        "",
    ]
    lines.extend(f"- {value}" for value in payload["public_metadata"])
    lines.extend(["", "## Forbidden Material", ""])
    lines.extend(f"- {value}" for value in payload["forbidden_material"])
    lines.extend(
        [
            "",
            "## Steps",
            "",
            "| ID | Status | Step | Next Step |",
            "|---|---|---|---|",
        ]
    )
    for row in payload["steps"]:
        lines.append(f"| `{row['id']}` | `{row['status']}` | {row['title']} | {row['next_step']} |")
    lines.extend(["", "## Evidence", ""])
    for row in payload["steps"]:
        lines.extend([f"### {row['id']}", ""])
        lines.extend(f"- {value}" for value in row["evidence"])
        lines.append("")
    lines.extend(["## Local Validation Commands", "", "```bash"])
    lines.extend(payload["local_validation_commands"])
    lines.extend(["```", ""])
    lines.append("No NL or SPB writes were performed by this provisioning plan.")
    return "\n".join(lines) + "\n"


def main() -> int:
    parser = argparse.ArgumentParser(description="Build secondary exit provisioning plan")
    parser.add_argument("--provider-shortlist", default=str(DEFAULT_PROVIDER_SHORTLIST))
    parser.add_argument("--candidate-intake", default=str(DEFAULT_CANDIDATE_INTAKE))
    parser.add_argument("--requirements", default=str(DEFAULT_REQUIREMENTS))
    parser.add_argument("--json-out", default=str(DEFAULT_JSON_OUT))
    parser.add_argument("--markdown-out", default=str(DEFAULT_MARKDOWN_OUT))
    args = parser.parse_args()

    payload = build_payload(
        provider_shortlist=read_json(Path(args.provider_shortlist)),
        candidate_intake=read_json(Path(args.candidate_intake)),
        requirements=read_json(Path(args.requirements)),
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
