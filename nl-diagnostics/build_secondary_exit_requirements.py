#!/usr/bin/env python3
"""Build local requirements for a future secondary VPN exit node.

This document is planning evidence only. It does not choose a provider, does
not store secrets, does not connect to NL/SPB, and does not mutate VPN state.
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
DEFAULT_FAILOVER_READINESS = DIAGNOSTICS_DIR / "manual-failover-readiness-2026-05-28.json"
DEFAULT_SECONDARY = DIAGNOSTICS_DIR / "secondary-exit-probe-template-2026-05-28.json"
DEFAULT_CANDIDATE_SCORE = DIAGNOSTICS_DIR / "secondary-exit-candidate-score-2026-05-28.json"
DEFAULT_JSON_OUT = DIAGNOSTICS_DIR / "secondary-exit-requirements-2026-05-28.json"
DEFAULT_MARKDOWN_OUT = DIAGNOSTICS_DIR / "secondary-exit-requirements-2026-05-28.md"


def read_json(path: Path) -> dict[str, Any]:
    try:
        value = json.loads(path.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError):
        return {}
    return value if isinstance(value, dict) else {}


def requirement(
    *,
    req_id: str,
    group: str,
    title: str,
    status: str,
    acceptance: str,
    evidence: list[str],
    next_step: str,
) -> dict[str, Any]:
    return {
        "id": req_id,
        "group": group,
        "title": title,
        "status": status,
        "acceptance": acceptance,
        "evidence": evidence,
        "next_step": next_step,
    }


def build_requirements(
    decision_report: dict[str, Any],
    failover_readiness: dict[str, Any],
    secondary_probe: dict[str, Any],
    candidate_score: dict[str, Any],
) -> list[dict[str, Any]]:
    decision = decision_report.get("decision") or {}
    classification = decision_report.get("classification") or {}
    readiness_summary = failover_readiness.get("summary") or {}
    candidate = secondary_probe.get("candidate") or {}
    candidate_configured = secondary_probe.get("candidate_configured") is True
    secondary_status = str(secondary_probe.get("status") or "missing")
    spb_excluded = readiness_summary.get("spb_excluded") is True
    candidate_score_summary = candidate_score.get("summary") or {}
    candidate_score_status = str(candidate_score.get("status") or "missing")
    viable_count = int(candidate_score_summary.get("viable_count") or 0)

    return [
        requirement(
            req_id="SEL-01",
            group="selection",
            title="Use a new provider and region, not NL and not SPB",
            status="ready_requirement" if spb_excluded else "blocked_policy_gap",
            acceptance="candidate provider, region, account, and host are documented as non-NL/non-SPB public metadata",
            evidence=[
                f"decision={decision.get('decision', 'missing')}",
                f"failure_domain={classification.get('failure_domain', 'missing')}",
                f"spb_excluded={str(spb_excluded).lower()}",
            ],
            next_step="choose a provider/region/account that is independent from NL and does not reuse SPB",
        ),
        requirement(
            req_id="SEL-02",
            group="selection",
            title="Use a small, boring daily/emergency profile split",
            status="ready_requirement",
            acceptance="daily NL profile remains separate from emergency secondary profile; automatic switching stays disabled",
            evidence=[
                "automatic_failover_allowed=false",
                f"manual_switch_allowed={str(failover_readiness.get('manual_switch_allowed')).lower()}",
            ],
            next_step="document the secondary as an emergency profile only until manual process is tested",
        ),
        requirement(
            req_id="SEL-03",
            group="selection",
            title="Score candidate metadata before choosing a secondary",
            status="ready_no_candidates" if candidate_score_status == "missing_candidates" else "ready_requirement" if viable_count > 0 else "blocked_candidate_score",
            acceptance="candidate scorer exists and rejects NL, SPB, placeholders, private addresses, and secret-like material",
            evidence=[
                f"candidate_score_status={candidate_score_status}",
                f"candidate_count={candidate_score_summary.get('candidate_count', 'missing')}",
                f"viable_count={candidate_score_summary.get('viable_count', 'missing')}",
                f"top_candidate_label={candidate_score_summary.get('top_candidate_label', 'missing')}",
            ],
            next_step="fill secondary-exit-candidates.example.json with public metadata for non-NL/non-SPB candidates",
        ),
        requirement(
            req_id="SEC-01",
            group="security",
            title="Do not store VPN secrets in repo or reports",
            status="ready_requirement",
            acceptance="only public endpoint metadata is stored; no raw URI, UUID, private key, or bot token",
            evidence=[
                "config_generator=nl-diagnostics/create_secondary_exit_config.py",
                "probe=nl-diagnostics/probe_secondary_exit.py",
            ],
            next_step="generate the future probe config from public metadata only",
        ),
        requirement(
            req_id="NET-01",
            group="network",
            title="Expose an independent public TCP health target",
            status="missing_candidate" if not candidate_configured else "ready_candidate",
            acceptance="probe_secondary_exit.py can reach at least one configured TCP port without touching NL",
            evidence=[
                f"secondary_probe_status={secondary_status}",
                f"candidate_configured={str(candidate_configured).lower()}",
                f"candidate_label={candidate.get('label', 'missing')}",
                f"candidate_tcp_ports={candidate.get('tcp_ports', [])}",
            ],
            next_step="configure a non-secret TCP probe target such as the future public 443 endpoint",
        ),
        requirement(
            req_id="NET-02",
            group="network",
            title="Verify exit IP only after manual test-client activation",
            status="ready_requirement",
            acceptance="client exit probe is disabled until a manual test profile is activated on a client",
            evidence=[
                "client probe uses local SOCKS only after manual activation",
                "raw profile secrets remain outside reports",
            ],
            next_step="after secondary exists, enable client_probe only on a test client and compare expected exit IP",
        ),
        requirement(
            req_id="OPS-01",
            group="operations",
            title="Keep failover manual and reversible",
            status="ready_requirement",
            acceptance="manual approval, rollback path, and return-to-NL verification are documented before any switch",
            evidence=[
                f"manual_failover_readiness_status={failover_readiness.get('status', 'missing')}",
                f"manual_probe_allowed={str(failover_readiness.get('manual_probe_allowed')).lower()}",
                f"manual_switch_allowed={str(failover_readiness.get('manual_switch_allowed')).lower()}",
            ],
            next_step="write the exact client-side switch and rollback checklist after a real secondary endpoint exists",
        ),
        requirement(
            req_id="OPS-02",
            group="operations",
            title="Use project-local temp space for diagnostic commands",
            status="ready_requirement",
            acceptance="commands that need temporary files can run with TMPDIR=/mnt/projects/.tmp while / is full",
            evidence=[
                "local_root_filesystem_full=true",
                "recommended_tmpdir=/mnt/projects/.tmp",
            ],
            next_step="prefix long local diagnostic/test commands with TMPDIR=/mnt/projects/.tmp until root disk is cleaned",
        ),
    ]


def build_payload(
    decision_report: dict[str, Any],
    failover_readiness: dict[str, Any],
    secondary_probe: dict[str, Any],
    candidate_score: dict[str, Any],
) -> dict[str, Any]:
    requirements = build_requirements(decision_report, failover_readiness, secondary_probe, candidate_score)
    missing = [row["id"] for row in requirements if row["status"].startswith("missing")]
    blocked = [row["id"] for row in requirements if row["status"].startswith("blocked")]
    status = "requirements_ready_no_candidate" if missing == ["NET-01"] and not blocked else "requirements_need_attention"
    if not missing and not blocked:
        status = "requirements_ready_with_candidate"
    return {
        "schema_version": 1,
        "source": "nl-diagnostics/build_secondary_exit_requirements.py",
        "generated_at": datetime.now(timezone.utc).isoformat(),
        "status": status,
        "summary": {
            "requirement_count": len(requirements),
            "missing_items": missing,
            "blocked_items": blocked,
            "candidate_configured": secondary_probe.get("candidate_configured") is True,
            "secondary_probe_status": secondary_probe.get("status", "missing"),
            "manual_failover_readiness_status": failover_readiness.get("status", "missing"),
            "manual_switch_allowed": failover_readiness.get("manual_switch_allowed", False),
            "candidate_score_status": candidate_score.get("status", "missing"),
            "candidate_viable_count": (candidate_score.get("summary") or {}).get("viable_count", "missing"),
            "spb_fallback_allowed": False,
            "automatic_failover_allowed": False,
            "nl_write_allowed": False,
        },
        "requirements": requirements,
        "allowed_metadata": [
            "label",
            "provider name",
            "region",
            "public host/IP",
            "public TCP probe ports",
            "expected exit IP only after manual test-client activation",
        ],
        "forbidden_material": [
            "raw VPN URI",
            "UUID",
            "private key",
            "bot token",
            "subscription link",
            "NL endpoint",
            "SPB endpoint",
        ],
        "mutation_allowed": False,
        "nl_mutation_allowed": False,
        "spb_fallback_allowed": False,
        "automatic_failover_allowed": False,
    }


def render_markdown(payload: dict[str, Any]) -> str:
    summary = payload["summary"]
    lines = [
        "# Secondary Exit Requirements",
        "",
        f"generated_at: `{payload['generated_at']}`",
        "",
        "## Status",
        "",
        "```text",
        f"status={payload['status']}",
        f"requirement_count={summary.get('requirement_count')}",
        f"candidate_configured={str(summary.get('candidate_configured')).lower()}",
        f"secondary_probe_status={summary.get('secondary_probe_status')}",
        f"manual_failover_readiness_status={summary.get('manual_failover_readiness_status')}",
        f"manual_switch_allowed={str(summary.get('manual_switch_allowed')).lower()}",
        f"missing_items={','.join(summary.get('missing_items') or []) or 'none'}",
        f"blocked_items={','.join(summary.get('blocked_items') or []) or 'none'}",
        "nl_write_allowed=false",
        "spb_fallback_allowed=false",
        "automatic_failover_allowed=false",
        "```",
        "",
        "## Requirements",
        "",
        "| ID | Status | Group | Requirement | Next Step |",
        "|---|---|---|---|---|",
    ]
    for row in payload["requirements"]:
        lines.append(
            f"| `{row['id']}` | `{row['status']}` | `{row['group']}` | {row['title']} | {row['next_step']} |"
        )

    lines.extend(["", "## Evidence", ""])
    for row in payload["requirements"]:
        lines.extend([f"### {row['id']}", "", f"Acceptance: {row['acceptance']}", ""])
        lines.extend(f"- {value}" for value in row["evidence"])
        lines.append("")

    lines.extend(["## Allowed Metadata", ""])
    lines.extend(f"- {value}" for value in payload["allowed_metadata"])
    lines.extend(["", "## Forbidden Material", ""])
    lines.extend(f"- {value}" for value in payload["forbidden_material"])
    lines.extend(["", "No NL or SPB writes were performed by this requirements builder."])
    return "\n".join(lines) + "\n"


def main() -> int:
    parser = argparse.ArgumentParser(description="Build secondary exit node requirements")
    parser.add_argument("--decision", default=str(DEFAULT_DECISION))
    parser.add_argument("--failover-readiness", default=str(DEFAULT_FAILOVER_READINESS))
    parser.add_argument("--secondary", default=str(DEFAULT_SECONDARY))
    parser.add_argument("--candidate-score", default=str(DEFAULT_CANDIDATE_SCORE))
    parser.add_argument("--json-out", default=str(DEFAULT_JSON_OUT))
    parser.add_argument("--markdown-out", default=str(DEFAULT_MARKDOWN_OUT))
    args = parser.parse_args()

    payload = build_payload(
        read_json(Path(args.decision)),
        read_json(Path(args.failover_readiness)),
        read_json(Path(args.secondary)),
        read_json(Path(args.candidate_score)),
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
