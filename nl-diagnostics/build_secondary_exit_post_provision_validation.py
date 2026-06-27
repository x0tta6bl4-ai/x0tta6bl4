#!/usr/bin/env python3
"""Build the post-provision validation plan for a future secondary exit.

This report starts after a server is created externally. It tells the operator
how to validate public metadata, generate a safe probe config, and run public
TCP checks before any client-profile test. It does not provision servers, does
not store VPN secrets, does not contact NL/SPB, and does not enable failover.
"""

from __future__ import annotations

import argparse
from datetime import datetime, timezone
import json
from pathlib import Path
from typing import Any


ROOT = Path("/mnt/projects")
DIAGNOSTICS_DIR = ROOT / "nl-diagnostics"
DEFAULT_PUBLIC_TEMPLATE = DIAGNOSTICS_DIR / "secondary-exit-public-metadata-template-2026-05-28.json"
DEFAULT_CANDIDATE_SCORE = DIAGNOSTICS_DIR / "secondary-exit-candidate-score-2026-05-28.json"
DEFAULT_SECONDARY_PROBE = DIAGNOSTICS_DIR / "secondary-exit-probe-template-2026-05-28.json"
DEFAULT_FAILOVER_READINESS = DIAGNOSTICS_DIR / "manual-failover-readiness-2026-05-28.json"
DEFAULT_SECONDARY_FLOW = DIAGNOSTICS_DIR / "secondary-exit-flow-2026-05-28.json"
DEFAULT_MANUAL_DRILL = DIAGNOSTICS_DIR / "secondary-exit-manual-drill-2026-05-28.json"
DEFAULT_CANDIDATE_FILE = DIAGNOSTICS_DIR / "secondary-exit-candidates.example.json"
DEFAULT_JSON_OUT = DIAGNOSTICS_DIR / "secondary-exit-post-provision-validation-2026-05-28.json"
DEFAULT_MARKDOWN_OUT = DIAGNOSTICS_DIR / "secondary-exit-post-provision-validation-2026-05-28.md"

PROBE_CONFIG_PATH = "/mnt/projects/.tmp/secondary-exit-probe.json"


def read_json(path: Path) -> dict[str, Any]:
    try:
        value = json.loads(path.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError):
        return {}
    return value if isinstance(value, dict) else {}


def flag_is_false(payload: dict[str, Any], key: str) -> bool:
    return payload.get(key) is False


def all_false_flags(*payloads: dict[str, Any]) -> bool:
    return all(
        flag_is_false(payload, "nl_mutation_allowed")
        and flag_is_false(payload, "spb_fallback_allowed")
        and flag_is_false(payload, "automatic_failover_allowed")
        for payload in payloads
    )


def first_template_candidate(public_template: dict[str, Any]) -> dict[str, Any]:
    candidate_file_template = public_template.get("candidate_file_template")
    if not isinstance(candidate_file_template, dict):
        return {}
    candidates = candidate_file_template.get("candidates")
    if not isinstance(candidates, list):
        return {}
    for candidate in candidates:
        if isinstance(candidate, dict):
            return candidate
    return {}


def top_viable_candidate(candidate_score: dict[str, Any]) -> dict[str, Any]:
    rows = candidate_score.get("candidates")
    if not isinstance(rows, list):
        return {}
    viable = [row for row in rows if isinstance(row, dict) and row.get("viable") is True]
    if not viable:
        return {}
    return sorted(viable, key=lambda row: (-int(row.get("score") or 0), str(row.get("label") or "")))[0]


def build_config_command(candidate: dict[str, Any], template_candidate: dict[str, Any]) -> str:
    source = candidate or template_candidate
    label = source.get("label", "<label>")
    provider = source.get("provider", "<provider>")
    region = source.get("region", "<region>")
    host = candidate.get("host") if candidate else "<public-host-or-ip>"
    raw_ports = source.get("tcp_ports") if isinstance(source.get("tcp_ports"), list) else [443]
    port_args = " ".join(f"--tcp-port {int(port)}" for port in raw_ports if str(port).isdigit()) or "--tcp-port 443"
    return (
        "TMPDIR=/mnt/projects/.tmp python3 nl-diagnostics/create_secondary_exit_config.py "
        f"--label {label} "
        f"--provider {provider} "
        f"--region {region} "
        f"--host {host} "
        f"{port_args} "
        f"--out {PROBE_CONFIG_PATH}"
    )


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
        "ok": status in {"ready", "blocked", "watch", "external_required"},
        "evidence": evidence,
        "next_step": next_step,
    }


def choose_status(
    *,
    safe: bool,
    endpoint_count: int,
    viable_count: int,
    secondary_probe_status: str,
    candidate_configured: bool,
    manual_probe_allowed: bool,
    manual_switch_allowed: bool,
) -> str:
    if not safe:
        return "post_provision_validation_unsafe_flags"
    if manual_switch_allowed and secondary_probe_status == "healthy":
        return "post_provision_validation_manual_switch_ready"
    if manual_probe_allowed and secondary_probe_status in {"healthy", "endpoint_reachable_profile_unverified"}:
        return "post_provision_validation_test_client_ready"
    if secondary_probe_status == "endpoint_reachable_profile_unverified":
        return "post_provision_validation_endpoint_ready_no_incident"
    if candidate_configured:
        return "post_provision_validation_public_probe_needed"
    if viable_count > 0:
        return "post_provision_validation_ready_for_probe_config"
    if endpoint_count > 0:
        return "post_provision_validation_score_public_metadata"
    return "post_provision_validation_ready_waiting_endpoint"


def build_payload(
    *,
    public_template: dict[str, Any],
    candidate_score: dict[str, Any],
    secondary_probe: dict[str, Any],
    failover_readiness: dict[str, Any],
    secondary_flow: dict[str, Any],
    manual_drill: dict[str, Any],
    candidate_file: Path,
) -> dict[str, Any]:
    public_summary = public_template.get("summary") or {}
    score_summary = candidate_score.get("summary") or {}
    flow_summary = secondary_flow.get("summary") or {}
    drill_summary = manual_drill.get("summary") or {}
    template_candidate = first_template_candidate(public_template)
    top_candidate = top_viable_candidate(candidate_score)
    endpoint_count = int(public_summary.get("endpoint_count") or 0)
    candidate_count = int(score_summary.get("candidate_count") or 0)
    viable_count = int(score_summary.get("viable_count") or 0)
    secondary_probe_status = str(secondary_probe.get("status") or "missing")
    candidate_configured = secondary_probe.get("candidate_configured") is True
    manual_probe_allowed = failover_readiness.get("manual_probe_allowed") is True
    manual_switch_allowed = failover_readiness.get("manual_switch_allowed") is True
    safe = all(
        [
            all_false_flags(public_template, candidate_score, secondary_probe, failover_readiness, secondary_flow, manual_drill),
            public_summary.get("nl_write_allowed") is False,
            public_summary.get("spb_fallback_allowed") is False,
            public_summary.get("automatic_failover_allowed") is False,
            score_summary.get("nl_write_allowed") is False,
            score_summary.get("spb_fallback_allowed") is False,
            score_summary.get("automatic_failover_allowed") is False,
            flow_summary.get("nl_write_allowed") is False,
            flow_summary.get("spb_fallback_allowed") is False,
            flow_summary.get("automatic_failover_allowed") is False,
            drill_summary.get("nl_write_allowed") is False,
            drill_summary.get("spb_fallback_allowed") is False,
            drill_summary.get("automatic_failover_allowed") is False,
            drill_summary.get("bulk_user_switch_allowed") is False,
        ]
    )
    status = choose_status(
        safe=safe,
        endpoint_count=endpoint_count,
        viable_count=viable_count,
        secondary_probe_status=secondary_probe_status,
        candidate_configured=candidate_configured,
        manual_probe_allowed=manual_probe_allowed,
        manual_switch_allowed=manual_switch_allowed,
    )
    can_generate_probe_config = viable_count > 0 and safe
    can_run_public_probe = candidate_configured and safe

    phases = [
        phase(
            phase_id="ENDPOINT-01",
            title="Provision one selected server outside the repository",
            status="external_required" if endpoint_count == 0 else "ready",
            evidence=[
                f"selected_label={public_summary.get('selected_label', 'missing')}",
                f"endpoint_count={endpoint_count}",
            ],
            next_step="create the selected VPS externally and keep provider credentials out of repo",
        ),
        phase(
            phase_id="METADATA-01",
            title="Add only public endpoint metadata to candidate file",
            status="blocked" if endpoint_count == 0 else "ready",
            evidence=[
                f"candidate_file={candidate_file}",
                f"candidate_file_update_allowed={str(public_summary.get('candidate_file_update_allowed')).lower()}",
                f"template_label={template_candidate.get('label', 'missing')}",
            ],
            next_step="replace only host with public IPv4/DNS after the endpoint exists",
        ),
        phase(
            phase_id="SCORE-01",
            title="Score candidate metadata before generating probe config",
            status="ready" if viable_count > 0 else "blocked",
            evidence=[
                f"candidate_score_status={candidate_score.get('status', 'missing')}",
                f"candidate_count={candidate_count}",
                f"viable_count={viable_count}",
                f"top_candidate_label={score_summary.get('top_candidate_label', 'none')}",
            ],
            next_step="run score_secondary_exit_candidates.py after public metadata is saved",
        ),
        phase(
            phase_id="CONFIG-01",
            title="Generate safe public probe config in project tmpdir",
            status="ready" if can_generate_probe_config else "blocked",
            evidence=[
                f"probe_config_path={PROBE_CONFIG_PATH}",
                f"can_generate_probe_config={str(can_generate_probe_config).lower()}",
            ],
            next_step="generate the probe config only from a viable public candidate",
        ),
        phase(
            phase_id="PROBE-01",
            title="Run public TCP endpoint probe",
            status="ready" if can_run_public_probe else "blocked",
            evidence=[
                f"secondary_probe_status={secondary_probe_status}",
                f"candidate_configured={str(candidate_configured).lower()}",
            ],
            next_step="run probe_secondary_exit.py against the generated config",
        ),
        phase(
            phase_id="TESTCLIENT-01",
            title="Test-client profile remains gated",
            status="ready" if manual_probe_allowed else "blocked",
            evidence=[
                f"manual_probe_allowed={str(manual_probe_allowed).lower()}",
                f"manual_failover_readiness_status={failover_readiness.get('status', 'missing')}",
            ],
            next_step="activate a test-client profile only during a real incident after endpoint probe passes",
        ),
        phase(
            phase_id="SWITCH-01",
            title="User switch remains manual and blocked",
            status="ready" if manual_switch_allowed else "blocked",
            evidence=[
                f"manual_switch_allowed={str(manual_switch_allowed).lower()}",
                f"secondary_flow_status={secondary_flow.get('status', 'missing')}",
            ],
            next_step="do not switch users until readiness explicitly allows manual switch",
        ),
    ]

    return {
        "schema_version": 1,
        "source": "nl-diagnostics/build_secondary_exit_post_provision_validation.py",
        "generated_at": datetime.now(timezone.utc).isoformat(),
        "status": status,
        "ok": safe,
        "summary": {
            "selected_label": public_summary.get("selected_label", "missing"),
            "candidate_file": str(candidate_file),
            "endpoint_count": endpoint_count,
            "candidate_score_status": candidate_score.get("status", "missing"),
            "candidate_count": candidate_count,
            "viable_count": viable_count,
            "top_candidate_label": score_summary.get("top_candidate_label", "none"),
            "secondary_probe_status": secondary_probe_status,
            "candidate_configured": candidate_configured,
            "manual_probe_allowed": manual_probe_allowed,
            "manual_switch_allowed": manual_switch_allowed,
            "can_generate_probe_config": can_generate_probe_config,
            "can_run_public_probe": can_run_public_probe,
            "test_client_allowed": manual_probe_allowed,
            "probe_config_path": PROBE_CONFIG_PATH,
            "safe_flags": safe,
            "nl_write_allowed": False,
            "spb_fallback_allowed": False,
            "automatic_failover_allowed": False,
        },
        "phases": phases,
        "safe_commands": {
            "validate_candidate_json": f"python3 -m json.tool {candidate_file} >/dev/null",
            "score_candidates": (
                "TMPDIR=/mnt/projects/.tmp python3 nl-diagnostics/score_secondary_exit_candidates.py "
                f"--candidates {candidate_file}"
            ),
            "generate_probe_config": build_config_command(top_candidate, template_candidate),
            "run_public_probe": (
                "TMPDIR=/mnt/projects/.tmp python3 nl-diagnostics/probe_secondary_exit.py "
                f"--config {PROBE_CONFIG_PATH} --json-out /mnt/projects/.tmp/secondary-exit-probe-result.json"
            ),
            "refresh_reports": "TMPDIR=/mnt/projects/.tmp python3 nl-diagnostics/refresh_vpn_planning_reports.py",
            "audit_readiness": "TMPDIR=/mnt/projects/.tmp python3 nl-diagnostics/audit_vpn_plan_readiness.py",
        },
        "blocked_actions": [
            "Do not store VPN profile URI, UUID, private key, bot token, subscription link, or provider credentials.",
            "Do not enable client probe until one test client is manually configured during a real incident.",
            "Do not switch users while manual_switch_allowed=false.",
            "Do not use SPB while SPB is disabled.",
            "Do not write to NL from this workflow.",
        ],
        "mutation_allowed": False,
        "nl_mutation_allowed": False,
        "spb_fallback_allowed": False,
        "automatic_failover_allowed": False,
    }


def render_markdown(payload: dict[str, Any]) -> str:
    summary = payload["summary"]
    lines = [
        "# Secondary Exit Post-Provision Validation",
        "",
        f"generated_at: `{payload['generated_at']}`",
        f"status: `{payload['status']}`",
        f"ok: `{str(payload['ok']).lower()}`",
        "",
        "## Summary",
        "",
        "```text",
        f"selected_label={summary.get('selected_label')}",
        f"candidate_file={summary.get('candidate_file')}",
        f"endpoint_count={summary.get('endpoint_count')}",
        f"candidate_score_status={summary.get('candidate_score_status')}",
        f"candidate_count={summary.get('candidate_count')}",
        f"viable_count={summary.get('viable_count')}",
        f"top_candidate_label={summary.get('top_candidate_label')}",
        f"secondary_probe_status={summary.get('secondary_probe_status')}",
        f"candidate_configured={str(summary.get('candidate_configured')).lower()}",
        f"manual_probe_allowed={str(summary.get('manual_probe_allowed')).lower()}",
        f"manual_switch_allowed={str(summary.get('manual_switch_allowed')).lower()}",
        f"can_generate_probe_config={str(summary.get('can_generate_probe_config')).lower()}",
        f"can_run_public_probe={str(summary.get('can_run_public_probe')).lower()}",
        f"test_client_allowed={str(summary.get('test_client_allowed')).lower()}",
        f"probe_config_path={summary.get('probe_config_path')}",
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
    lines.extend(payload["safe_commands"].values())
    lines.extend(["```", "", "## Blocked Actions", ""])
    lines.extend(f"- {value}" for value in payload["blocked_actions"])
    lines.append("")
    lines.append("No NL or SPB writes were performed by this post-provision validation report.")
    return "\n".join(lines) + "\n"


def main() -> int:
    parser = argparse.ArgumentParser(description="Build secondary exit post-provision validation plan")
    parser.add_argument("--public-template", default=str(DEFAULT_PUBLIC_TEMPLATE))
    parser.add_argument("--candidate-score", default=str(DEFAULT_CANDIDATE_SCORE))
    parser.add_argument("--secondary-probe", default=str(DEFAULT_SECONDARY_PROBE))
    parser.add_argument("--failover-readiness", default=str(DEFAULT_FAILOVER_READINESS))
    parser.add_argument("--secondary-flow", default=str(DEFAULT_SECONDARY_FLOW))
    parser.add_argument("--manual-drill", default=str(DEFAULT_MANUAL_DRILL))
    parser.add_argument("--candidate-file", default=str(DEFAULT_CANDIDATE_FILE))
    parser.add_argument("--json-out", default=str(DEFAULT_JSON_OUT))
    parser.add_argument("--markdown-out", default=str(DEFAULT_MARKDOWN_OUT))
    args = parser.parse_args()

    payload = build_payload(
        public_template=read_json(Path(args.public_template)),
        candidate_score=read_json(Path(args.candidate_score)),
        secondary_probe=read_json(Path(args.secondary_probe)),
        failover_readiness=read_json(Path(args.failover_readiness)),
        secondary_flow=read_json(Path(args.secondary_flow)),
        manual_drill=read_json(Path(args.manual_drill)),
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
