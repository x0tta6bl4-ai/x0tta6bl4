#!/usr/bin/env python3
"""Build the local operating flow for a future secondary VPN exit.

The flow joins candidate scoring, safe probe config generation, endpoint
probing, and manual failover gates. It is planning evidence only: no NL writes,
no SPB fallback, no profile secrets, and no automatic switching.
"""

from __future__ import annotations

import argparse
from datetime import datetime, timezone
import json
from pathlib import Path
from typing import Any


ROOT = Path("/mnt/projects")
DIAGNOSTICS_DIR = ROOT / "nl-diagnostics"
DEFAULT_CANDIDATE_SCORE = DIAGNOSTICS_DIR / "secondary-exit-candidate-score-2026-05-28.json"
DEFAULT_SECONDARY_PROBE = DIAGNOSTICS_DIR / "secondary-exit-probe-template-2026-05-28.json"
DEFAULT_FAILOVER_READINESS = DIAGNOSTICS_DIR / "manual-failover-readiness-2026-05-28.json"
DEFAULT_REQUIREMENTS = DIAGNOSTICS_DIR / "secondary-exit-requirements-2026-05-28.json"
DEFAULT_JSON_OUT = DIAGNOSTICS_DIR / "secondary-exit-flow-2026-05-28.json"
DEFAULT_MARKDOWN_OUT = DIAGNOSTICS_DIR / "secondary-exit-flow-2026-05-28.md"

PASS = "pass"
BLOCKED = "blocked"
WATCH = "watch"


def read_json(path: Path) -> dict[str, Any]:
    try:
        value = json.loads(path.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError):
        return {}
    return value if isinstance(value, dict) else {}


def flag_is_false(payload: dict[str, Any], key: str) -> bool:
    return payload.get(key) is False


def top_viable_candidate(candidate_score: dict[str, Any]) -> dict[str, Any] | None:
    rows = candidate_score.get("candidates")
    if not isinstance(rows, list):
        return None
    viable = [row for row in rows if isinstance(row, dict) and row.get("viable") is True]
    if not viable:
        return None
    return sorted(viable, key=lambda row: (-int(row.get("score") or 0), str(row.get("label") or "")))[0]


def phase(
    *,
    phase_id: str,
    title: str,
    status: str,
    evidence: list[str],
    next_step: str,
) -> dict[str, Any]:
    return {
        "id": phase_id,
        "title": title,
        "status": status,
        "ok": status in {PASS, WATCH, BLOCKED},
        "evidence": evidence,
        "next_step": next_step,
    }


def build_config_command(candidate: dict[str, Any] | None) -> str:
    if not candidate:
        return (
            "python3 nl-diagnostics/create_secondary_exit_config.py "
            "--label <label> --provider <provider> --region <region> "
            "--host <public-host-or-ip> --tcp-port 443 "
            "--out /mnt/projects/.tmp/secondary-exit-probe.json"
        )
    ports = candidate.get("tcp_ports") if isinstance(candidate.get("tcp_ports"), list) else []
    port_args = " ".join(f"--tcp-port {int(port)}" for port in ports) or "--tcp-port 443"
    return (
        "python3 nl-diagnostics/create_secondary_exit_config.py "
        f"--label {candidate.get('label')} "
        f"--provider {candidate.get('provider')} "
        f"--region {candidate.get('region')} "
        f"--host {candidate.get('host')} "
        f"{port_args} "
        "--out /mnt/projects/.tmp/secondary-exit-probe.json"
    )


def choose_status(
    *,
    viable_count: int,
    candidate_configured: bool,
    secondary_status: str,
    manual_probe_allowed: bool,
    manual_switch_allowed: bool,
) -> str:
    if manual_switch_allowed and secondary_status == "healthy":
        return "ready_for_manual_switch"
    if manual_probe_allowed and secondary_status in {"healthy", "endpoint_reachable_profile_unverified"}:
        return "ready_for_manual_profile_test"
    if secondary_status == "endpoint_reachable_profile_unverified":
        return "endpoint_ready_but_no_incident_trigger"
    if candidate_configured and secondary_status not in {"planning_template", "missing"}:
        return "secondary_probe_needs_attention"
    if candidate_configured:
        return "candidate_configured_probe_needed"
    if viable_count > 0:
        return "candidate_ready_probe_config_needed"
    return "blocked_missing_candidate"


def build_payload(
    candidate_score: dict[str, Any],
    secondary_probe: dict[str, Any],
    failover_readiness: dict[str, Any],
    requirements: dict[str, Any],
) -> dict[str, Any]:
    score_summary = candidate_score.get("summary") or {}
    requirements_summary = requirements.get("summary") or {}
    top_candidate = top_viable_candidate(candidate_score)
    viable_count = int(score_summary.get("viable_count") or 0)
    secondary_status = str(secondary_probe.get("status") or "missing")
    candidate_configured = secondary_probe.get("candidate_configured") is True
    manual_probe_allowed = failover_readiness.get("manual_probe_allowed") is True
    manual_switch_allowed = failover_readiness.get("manual_switch_allowed") is True
    safe = all(
        [
            flag_is_false(candidate_score, "nl_mutation_allowed"),
            flag_is_false(candidate_score, "spb_fallback_allowed"),
            flag_is_false(candidate_score, "automatic_failover_allowed"),
            flag_is_false(secondary_probe, "nl_mutation_allowed"),
            flag_is_false(secondary_probe, "spb_fallback_allowed"),
            flag_is_false(secondary_probe, "automatic_failover_allowed"),
            flag_is_false(failover_readiness, "nl_mutation_allowed"),
            flag_is_false(failover_readiness, "spb_fallback_allowed"),
            flag_is_false(failover_readiness, "automatic_failover_allowed"),
            flag_is_false(requirements, "nl_mutation_allowed"),
            flag_is_false(requirements, "spb_fallback_allowed"),
            flag_is_false(requirements, "automatic_failover_allowed"),
            score_summary.get("nl_write_allowed") is False,
            requirements_summary.get("nl_write_allowed") is False,
            requirements_summary.get("spb_fallback_allowed") is False,
            requirements_summary.get("automatic_failover_allowed") is False,
        ]
    )
    status = choose_status(
        viable_count=viable_count,
        candidate_configured=candidate_configured,
        secondary_status=secondary_status,
        manual_probe_allowed=manual_probe_allowed,
        manual_switch_allowed=manual_switch_allowed,
    )
    if not safe:
        status = "unsafe_flags"

    phases = [
        phase(
            phase_id="CANDIDATE-01",
            title="Score non-NL/non-SPB public candidate metadata",
            status=PASS if viable_count > 0 else BLOCKED,
            evidence=[
                f"candidate_score_status={candidate_score.get('status', 'missing')}",
                f"candidate_count={score_summary.get('candidate_count', 'missing')}",
                f"viable_count={viable_count}",
                f"top_candidate_label={(top_candidate or {}).get('label', 'none')}",
            ],
            next_step="fill public metadata for at least one independent non-NL/non-SPB provider candidate",
        ),
        phase(
            phase_id="CONFIG-01",
            title="Generate safe public probe config without profile secrets",
            status=PASS if candidate_configured else BLOCKED if viable_count == 0 else WATCH,
            evidence=[
                f"candidate_configured={str(candidate_configured).lower()}",
                f"secondary_probe_status={secondary_status}",
                f"config_command={build_config_command(top_candidate)}",
            ],
            next_step="generate /mnt/projects/.tmp/secondary-exit-probe.json from the top viable candidate",
        ),
        phase(
            phase_id="PROBE-01",
            title="Verify public TCP endpoint reachability",
            status=PASS if secondary_status in {"endpoint_reachable_profile_unverified", "healthy"} else BLOCKED,
            evidence=[
                f"secondary_probe_status={secondary_status}",
                f"candidate_configured={str(candidate_configured).lower()}",
            ],
            next_step="run probe_secondary_exit.py against the generated public probe config",
        ),
        phase(
            phase_id="CLIENT-01",
            title="Manual test-client profile activation is gated",
            status=PASS if manual_probe_allowed else BLOCKED,
            evidence=[
                f"manual_failover_readiness_status={failover_readiness.get('status', 'missing')}",
                f"manual_probe_allowed={str(manual_probe_allowed).lower()}",
                f"secondary_probe_status={secondary_status}",
            ],
            next_step="activate a test client profile only during a real incident and only after endpoint probe passes",
        ),
        phase(
            phase_id="SWITCH-01",
            title="Manual switch remains blocked until healthy secondary and incident trigger",
            status=PASS if manual_switch_allowed else BLOCKED,
            evidence=[
                f"manual_switch_allowed={str(manual_switch_allowed).lower()}",
                f"secondary_probe_status={secondary_status}",
            ],
            next_step="do not switch users until manual_switch_allowed=true in failover readiness",
        ),
    ]

    return {
        "schema_version": 1,
        "source": "nl-diagnostics/build_secondary_exit_flow.py",
        "generated_at": datetime.now(timezone.utc).isoformat(),
        "status": status,
        "ok": safe,
        "summary": {
            "candidate_score_status": candidate_score.get("status", "missing"),
            "candidate_viable_count": viable_count,
            "top_candidate_label": (top_candidate or {}).get("label", "none"),
            "secondary_probe_status": secondary_status,
            "candidate_configured": candidate_configured,
            "manual_probe_allowed": manual_probe_allowed,
            "manual_switch_allowed": manual_switch_allowed,
            "requirements_status": requirements.get("status", "missing"),
            "missing_requirements": requirements_summary.get("missing_items") or [],
            "safe_flags": safe,
            "nl_write_allowed": False,
            "spb_fallback_allowed": False,
            "automatic_failover_allowed": False,
        },
        "top_viable_candidate": top_candidate or {},
        "phases": phases,
        "safe_commands": {
            "generate_probe_config": build_config_command(top_candidate),
            "run_public_probe": (
                "python3 nl-diagnostics/probe_secondary_exit.py "
                "--config /mnt/projects/.tmp/secondary-exit-probe.json "
                "--json-out /mnt/projects/.tmp/secondary-exit-probe-result.json"
            ),
        },
        "execution_rules": [
            "Do not store raw VPN URIs, UUIDs, private keys, bot tokens, or subscription links.",
            "Do not use NL or SPB as the secondary exit.",
            "Do not run client exit verification until a test client profile is manually activated.",
            "Do not switch users until failover readiness sets manual_switch_allowed=true.",
        ],
        "mutation_allowed": False,
        "nl_mutation_allowed": False,
        "spb_fallback_allowed": False,
        "automatic_failover_allowed": False,
    }


def render_markdown(payload: dict[str, Any]) -> str:
    summary = payload["summary"]
    lines = [
        "# Secondary Exit Flow",
        "",
        f"generated_at: `{payload['generated_at']}`",
        f"status: `{payload['status']}`",
        f"ok: `{str(payload['ok']).lower()}`",
        "",
        "## Summary",
        "",
        "```text",
        f"candidate_score_status={summary.get('candidate_score_status')}",
        f"candidate_viable_count={summary.get('candidate_viable_count')}",
        f"top_candidate_label={summary.get('top_candidate_label')}",
        f"secondary_probe_status={summary.get('secondary_probe_status')}",
        f"candidate_configured={str(summary.get('candidate_configured')).lower()}",
        f"manual_probe_allowed={str(summary.get('manual_probe_allowed')).lower()}",
        f"manual_switch_allowed={str(summary.get('manual_switch_allowed')).lower()}",
        f"requirements_status={summary.get('requirements_status')}",
        f"missing_requirements={','.join(summary.get('missing_requirements') or []) or 'none'}",
        "nl_write_allowed=false",
        "spb_fallback_allowed=false",
        "automatic_failover_allowed=false",
        "```",
        "",
        "## Phases",
        "",
        "| ID | Status | Phase | Next Step |",
        "|---|---|---|---|",
    ]
    for row in payload["phases"]:
        lines.append(f"| `{row['id']}` | `{row['status']}` | {row['title']} | {row['next_step']} |")
    lines.extend(["", "## Safe Commands", "", "```bash"])
    lines.append(payload["safe_commands"]["generate_probe_config"])
    lines.append(payload["safe_commands"]["run_public_probe"])
    lines.extend(["```", "", "## Execution Rules", ""])
    lines.extend(f"- {rule}" for rule in payload["execution_rules"])
    lines.append("")
    lines.append("No NL or SPB writes were performed by this secondary exit flow report.")
    return "\n".join(lines) + "\n"


def main() -> int:
    parser = argparse.ArgumentParser(description="Build secondary exit operating flow")
    parser.add_argument("--candidate-score", default=str(DEFAULT_CANDIDATE_SCORE))
    parser.add_argument("--secondary-probe", default=str(DEFAULT_SECONDARY_PROBE))
    parser.add_argument("--failover-readiness", default=str(DEFAULT_FAILOVER_READINESS))
    parser.add_argument("--requirements", default=str(DEFAULT_REQUIREMENTS))
    parser.add_argument("--json-out", default=str(DEFAULT_JSON_OUT))
    parser.add_argument("--markdown-out", default=str(DEFAULT_MARKDOWN_OUT))
    args = parser.parse_args()

    payload = build_payload(
        read_json(Path(args.candidate_score)),
        read_json(Path(args.secondary_probe)),
        read_json(Path(args.failover_readiness)),
        read_json(Path(args.requirements)),
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
