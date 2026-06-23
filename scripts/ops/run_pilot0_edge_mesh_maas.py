#!/usr/bin/env python3
"""Run Pilot 0: Edge Mesh MaaS and write an operator evidence report.

Pilot 0 is a local/lab handoff wrapper around the real Go-agent MaaS verifier.
It starts a temporary MaaS API, connects a locally built Go agent, observes
node-config, heartbeat, and operator heal evidence, then writes JSON/Markdown
artifacts that explicitly block production/customer/external claims.
"""

from __future__ import annotations

import argparse
import hashlib
import json
import re
import sys
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Mapping, Sequence


ROOT = Path(__file__).resolve().parents[2]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from scripts.ops import verify_maas_real_agent_control_loop as real_agent


SCHEMA = "x0tta6bl4.pilot0_edge_mesh_maas.v1"
READY_DECISION = "PILOT0_EDGE_MESH_MAAS_READY"
BLOCKED_DECISION = "PILOT0_EDGE_MESH_MAAS_BLOCKED"
DEFAULT_OUTPUT_DIR = ROOT / "docs/operations"
DEFAULT_WORK_ROOT = ROOT / ".tmp/pilot0-edge-mesh-maas"
RUNBOOK_PATH = "docs/runbooks/PILOT0_EDGE_MESH_MAAS.md"
CLAIM_BOUNDARY = (
    "Pilot 0 Edge Mesh MaaS is a local/lab operator scenario. It proves that "
    "a temporary MaaS API can start, a locally built Go agent can register, be "
    "approved, fetch node-config, send heartbeat telemetry, and exercise a "
    "bounded operator heal path with redacted evidence. It does not prove live "
    "customer traffic, external reachability, external DPI bypass, settlement "
    "finality, production SLOs, durable infrastructure convergence, or "
    "production readiness."
)

REQUIRED_STAGES = {
    "local_maas_api_started",
    "mesh_deploy",
    "go_agent_build",
    "go_agent_started",
    "agent_registration_pending",
    "agent_node_runtime_credential_metadata_stored",
    "operator_approved_agent_node",
    "agent_node_config_fetch_observed",
    "agent_heartbeat_persisted",
    "agent_node_marked_offline_for_local_heal",
    "operator_heal_after_real_agent_heartbeat",
}

BLOCKED_STRONG_CLAIMS = {
    "traffic_delivery_claim_allowed",
    "customer_traffic_claim_allowed",
    "external_reachability_claim_allowed",
    "production_slo_claim_allowed",
    "production_readiness_claim_allowed",
}

REPORT_STRONG_CLAIMS = (
    "traffic_delivery_claim_allowed",
    "customer_traffic_claim_allowed",
    "external_reachability_claim_allowed",
    "external_dpi_bypass_claim_allowed",
    "settlement_finality_claim_allowed",
    "production_slo_claim_allowed",
    "production_readiness_claim_allowed",
)


def utc_now() -> str:
    return (
        datetime.now(timezone.utc)
        .replace(microsecond=0)
        .isoformat()
        .replace("+00:00", "Z")
    )


def timestamp_tag(value: str | None = None) -> str:
    raw = value or utc_now()
    return raw.replace("-", "").replace(":", "").replace("+00:00", "Z")


def _sha256_text(value: str) -> str:
    return hashlib.sha256(value.encode("utf-8", errors="replace")).hexdigest()


def _redact_text(value: str, raw_values: Sequence[str]) -> str:
    redacted = value
    for raw in raw_values:
        if raw:
            redacted = redacted.replace(raw, "<redacted>")
    redacted = re.sub(r"x0tn_[A-Za-z0-9_=-]+", "<redacted-node-credential>", redacted)
    return redacted


def _redact_obj(value: Any, raw_values: Sequence[str]) -> Any:
    if isinstance(value, str):
        return _redact_text(value, raw_values)
    if isinstance(value, list):
        return [_redact_obj(item, raw_values) for item in value]
    if isinstance(value, tuple):
        return [_redact_obj(item, raw_values) for item in value]
    if isinstance(value, Mapping):
        return {
            str(key): _redact_obj(item, raw_values)
            for key, item in value.items()
        }
    return value


def _stage_map(agent_report: Mapping[str, Any]) -> dict[str, Mapping[str, Any]]:
    stages = agent_report.get("stages", [])
    if not isinstance(stages, list):
        return {}
    result: dict[str, Mapping[str, Any]] = {}
    for stage in stages:
        if not isinstance(stage, Mapping):
            continue
        name = str(stage.get("name") or "")
        if name:
            result[name] = stage
    return result


def _stage_ok(stages: Mapping[str, Mapping[str, Any]], name: str) -> bool:
    return stages.get(name, {}).get("ok") is True


def _validate_agent_report(agent_report: Mapping[str, Any]) -> list[str]:
    failures: list[str] = []
    if agent_report.get("ready") is not True:
        failures.append("real_agent_report_not_ready")
    if agent_report.get("decision") != real_agent.READY_DECISION:
        failures.append("real_agent_decision_not_ready")

    stages = _stage_map(agent_report)
    for name in sorted(REQUIRED_STAGES):
        if not _stage_ok(stages, name):
            failures.append(f"stage_not_ok:{name}")

    agent = agent_report.get("agent", {})
    if not isinstance(agent, Mapping):
        failures.append("agent_summary_missing")
        agent = {}
    for key in (
        "binary_built",
        "process_started",
        "node_runtime_credential_hash_stored",
        "node_runtime_credential_expiry_stored",
        "node_config_fetch_observed",
        "heartbeat_observed",
        "operator_heal_observed",
    ):
        if agent.get(key) is not True:
            failures.append(f"agent_flag_not_true:{key}")
    if agent.get("raw_node_runtime_credential_redacted") is not True:
        failures.append("agent_runtime_credential_not_redacted")

    target = agent_report.get("dataplane_probe_target", {})
    if not isinstance(target, Mapping):
        failures.append("dataplane_target_summary_missing")
        target = {}
    if target.get("raw_value_redacted") is not True:
        failures.append("dataplane_target_not_redacted")
    if target.get("requested_raw_value_redacted") is not True:
        failures.append("requested_dataplane_target_not_redacted")

    healing = agent_report.get("healing_surface", {})
    if not isinstance(healing, Mapping):
        failures.append("healing_surface_missing")
        healing = {}
    for key in (
        "observed",
        "post_action_revalidation_present",
        "dataplane_confirmed",
        "post_action_dataplane_revalidated",
        "restored_dataplane_claim_allowed",
        "raw_target_redacted",
    ):
        if healing.get(key) is not True:
            failures.append(f"healing_flag_not_true:{key}")
    for key in sorted(BLOCKED_STRONG_CLAIMS):
        if healing.get(key) is not False:
            failures.append(f"healing_overclaim:{key}")
    return failures


def build_report(
    agent_report: Mapping[str, Any],
    *,
    requested_dataplane_probe_target: str,
    generated_at_utc: str | None = None,
) -> dict[str, Any]:
    generated_at = generated_at_utc or utc_now()
    clean_agent_report = _redact_obj(agent_report, [requested_dataplane_probe_target])
    failures = _validate_agent_report(clean_agent_report)
    stages = _stage_map(clean_agent_report)
    healing = clean_agent_report.get("healing_surface", {})
    if not isinstance(healing, Mapping):
        healing = {}

    ready = not failures
    claim_gate = {
        "local_maas_api_started_claim_allowed": _stage_ok(
            stages, "local_maas_api_started"
        ),
        "local_mesh_deploy_claim_allowed": _stage_ok(stages, "mesh_deploy"),
        "real_go_agent_build_claim_allowed": _stage_ok(stages, "go_agent_build"),
        "real_go_agent_connected_claim_allowed": _stage_ok(
            stages, "agent_registration_pending"
        )
        and _stage_ok(stages, "agent_node_config_fetch_observed"),
        "local_heartbeat_persisted_claim_allowed": _stage_ok(
            stages, "agent_heartbeat_persisted"
        ),
        "local_heal_control_action_claim_allowed": _stage_ok(
            stages, "operator_heal_after_real_agent_heartbeat"
        ),
        "bounded_restored_dataplane_claim_allowed": (
            healing.get("restored_dataplane_claim_allowed") is True
        ),
        "traffic_delivery_claim_allowed": False,
        "customer_traffic_claim_allowed": False,
        "external_reachability_claim_allowed": False,
        "external_dpi_bypass_claim_allowed": False,
        "settlement_finality_claim_allowed": False,
        "production_slo_claim_allowed": False,
        "production_readiness_claim_allowed": False,
        "requires_separate_external_evidence_for_strong_claims": True,
        "raw_targets_redacted": True,
        "raw_credentials_redacted": True,
    }

    operator_visible = {
        "maas_api_started": _stage_ok(stages, "local_maas_api_started"),
        "mesh_deployed": _stage_ok(stages, "mesh_deploy"),
        "agent_node_registered": _stage_ok(stages, "agent_registration_pending"),
        "agent_node_approved": _stage_ok(stages, "operator_approved_agent_node"),
        "node_config_seen": _stage_ok(stages, "agent_node_config_fetch_observed"),
        "heartbeat_seen": _stage_ok(stages, "agent_heartbeat_persisted"),
        "heal_seen": _stage_ok(stages, "operator_heal_after_real_agent_heartbeat"),
        "evidence_report_generated": True,
        "production_overclaim_blocked": not any(
            claim_gate[key] for key in (
                "traffic_delivery_claim_allowed",
                "customer_traffic_claim_allowed",
                "external_reachability_claim_allowed",
                "external_dpi_bypass_claim_allowed",
                "settlement_finality_claim_allowed",
                "production_slo_claim_allowed",
                "production_readiness_claim_allowed",
            )
        ),
    }

    target_summary = clean_agent_report.get("dataplane_probe_target", {})
    report = {
        "schema": SCHEMA,
        "generated_at_utc": generated_at,
        "decision": READY_DECISION if ready else BLOCKED_DECISION,
        "ready": ready,
        "pilot": {
            "name": "Pilot 0: Edge Mesh MaaS",
            "scenario": "local_or_lab_real_agent_control_loop",
            "operator_runbook": RUNBOOK_PATH,
            "local_or_lab_only": True,
        },
        "summary": {
            "required_stages_total": len(REQUIRED_STAGES),
            "required_stages_passed": sum(
                1 for name in REQUIRED_STAGES if _stage_ok(stages, name)
            ),
            "agent_report_ready": clean_agent_report.get("ready") is True,
            "agent_report_decision": clean_agent_report.get("decision"),
            **operator_visible,
        },
        "operator_visible_results": operator_visible,
        "claim_gate": claim_gate,
        "claim_boundary": CLAIM_BOUNDARY,
        "dataplane_probe_target": target_summary,
        "evidence": {
            "source_verifier": "scripts/ops/verify_maas_real_agent_control_loop.py",
            "source_schema": clean_agent_report.get("schema"),
            "source_decision": clean_agent_report.get("decision"),
            "source_ready": clean_agent_report.get("ready") is True,
            "source_duration_ms": clean_agent_report.get("duration_ms"),
            "event_project_root": clean_agent_report.get("event_project_root"),
            "temporary_database": clean_agent_report.get("database"),
            "checked_stages": sorted(REQUIRED_STAGES),
            "all_stage_names": sorted(stages),
            "entities": clean_agent_report.get("entities", {}),
            "agent": clean_agent_report.get("agent", {}),
            "healing_surface": healing,
            "source_failure": clean_agent_report.get("failure"),
        },
        "blocked_strong_claims": [
            key for key in REPORT_STRONG_CLAIMS if claim_gate.get(key) is False
        ],
        "failures": failures,
        "artifacts": {},
    }

    rendered = json.dumps(report, sort_keys=True)
    if requested_dataplane_probe_target and requested_dataplane_probe_target in rendered:
        report["ready"] = False
        report["decision"] = BLOCKED_DECISION
        report["failures"].append("requested_dataplane_target_leaked")
    return report


def render_markdown(report: Mapping[str, Any]) -> str:
    summary = report.get("summary", {})
    if not isinstance(summary, Mapping):
        summary = {}
    claim_gate = report.get("claim_gate", {})
    if not isinstance(claim_gate, Mapping):
        claim_gate = {}
    evidence = report.get("evidence", {})
    if not isinstance(evidence, Mapping):
        evidence = {}
    artifacts = report.get("artifacts", {})
    if not isinstance(artifacts, Mapping):
        artifacts = {}

    def status(value: Any) -> str:
        return "PASS" if value is True else "FAIL"

    lines = [
        "# Pilot 0: Edge Mesh MaaS Report",
        "",
        f"- Decision: `{report.get('decision')}`",
        f"- Ready: `{str(report.get('ready')).lower()}`",
        f"- Generated: `{report.get('generated_at_utc')}`",
        f"- Source verifier: `{evidence.get('source_verifier')}`",
        f"- Runbook: `{report.get('pilot', {}).get('operator_runbook') if isinstance(report.get('pilot'), Mapping) else RUNBOOK_PATH}`",
        "",
        "## Operator-visible result",
        "",
        "| Check | Status |",
        "|---|---|",
        f"| MaaS API started | {status(summary.get('maas_api_started'))} |",
        f"| Mesh deployed | {status(summary.get('mesh_deployed'))} |",
        f"| Agent node registered | {status(summary.get('agent_node_registered'))} |",
        f"| Agent node approved | {status(summary.get('agent_node_approved'))} |",
        f"| Node config observed | {status(summary.get('node_config_seen'))} |",
        f"| Heartbeat observed | {status(summary.get('heartbeat_seen'))} |",
        f"| Heal observed | {status(summary.get('heal_seen'))} |",
        f"| Production overclaim blocked | {status(summary.get('production_overclaim_blocked'))} |",
        "",
        "## Claim boundary",
        "",
        str(report.get("claim_boundary")),
        "",
        "## Strong claims intentionally blocked",
        "",
    ]
    blocked = report.get("blocked_strong_claims", [])
    if isinstance(blocked, list):
        for item in blocked:
            lines.append(f"- `{item}`")
    lines.extend(
        [
            "",
            "## Local/lab claims allowed by this report",
            "",
            f"- Local MaaS API start: `{claim_gate.get('local_maas_api_started_claim_allowed') is True}`",
            f"- Real Go agent connected: `{claim_gate.get('real_go_agent_connected_claim_allowed') is True}`",
            f"- Heartbeat persisted locally: `{claim_gate.get('local_heartbeat_persisted_claim_allowed') is True}`",
            f"- Bounded heal path observed: `{claim_gate.get('local_heal_control_action_claim_allowed') is True}`",
            "",
            "## Evidence",
            "",
            f"- Source decision: `{evidence.get('source_decision')}`",
            f"- Source duration ms: `{evidence.get('source_duration_ms')}`",
            f"- Event project root: `{evidence.get('event_project_root')}`",
            f"- JSON artifact: `{artifacts.get('json')}`",
            f"- Markdown artifact: `{artifacts.get('markdown')}`",
            "",
            "## Reproduce",
            "",
            "```bash",
            "PYTHONPATH=. python3 scripts/ops/run_pilot0_edge_mesh_maas.py --require-ready --output-dir docs/operations",
            "```",
        ]
    )
    failures = report.get("failures", [])
    if failures:
        lines.extend(["", "## Failures", ""])
        for failure in failures if isinstance(failures, list) else [failures]:
            lines.append(f"- `{failure}`")
    lines.append("")
    return "\n".join(lines)


def write_artifacts(
    report: dict[str, Any],
    *,
    output_dir: Path,
    tag: str,
) -> dict[str, Path]:
    output_dir.mkdir(parents=True, exist_ok=True)
    json_path = output_dir / f"pilot0_edge_mesh_maas_{tag}.json"
    md_path = output_dir / f"pilot0_edge_mesh_maas_{tag}.md"
    latest_json_path = output_dir / "pilot0_edge_mesh_maas_latest.json"
    latest_md_path = output_dir / "pilot0_edge_mesh_maas_latest.md"
    report["artifacts"] = {
        "json": str(json_path),
        "markdown": str(md_path),
        "latest_json": str(latest_json_path),
        "latest_markdown": str(latest_md_path),
    }
    json_text = json.dumps(report, indent=2, sort_keys=True) + "\n"
    md_text = render_markdown(report)
    json_path.write_text(json_text, encoding="utf-8")
    latest_json_path.write_text(json_text, encoding="utf-8")
    md_path.write_text(md_text, encoding="utf-8")
    latest_md_path.write_text(md_text, encoding="utf-8")
    return {
        "json": json_path,
        "markdown": md_path,
        "latest_json": latest_json_path,
        "latest_markdown": latest_md_path,
    }


def run_pilot0(
    *,
    work_dir: Path,
    output_dir: Path,
    dataplane_probe_target: str,
    timeout_seconds: float,
    use_local_listener_target: bool,
    generated_at_utc: str | None = None,
) -> dict[str, Any]:
    generated_at = generated_at_utc or utc_now()
    tag = timestamp_tag(generated_at)
    agent_report = real_agent.run_verification(
        work_dir=str(work_dir),
        dataplane_probe_target=dataplane_probe_target,
        timeout_seconds=timeout_seconds,
        use_local_listener_target=use_local_listener_target,
    )
    report = build_report(
        agent_report,
        requested_dataplane_probe_target=dataplane_probe_target,
        generated_at_utc=generated_at,
    )
    write_artifacts(report, output_dir=output_dir, tag=tag)
    return report


def parse_args(argv: Sequence[str] | None = None) -> argparse.Namespace:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument(
        "--work-dir",
        default="",
        help=(
            "Working directory for temporary API DB, EventBus, and agent binary. "
            "Defaults under .tmp/pilot0-edge-mesh-maas/<timestamp>."
        ),
    )
    parser.add_argument(
        "--output-dir",
        default=str(DEFAULT_OUTPUT_DIR),
        help="Directory for Pilot 0 JSON/Markdown report artifacts.",
    )
    parser.add_argument("--dataplane-probe-target", default="127.0.0.1")
    parser.add_argument(
        "--use-supplied-dataplane-target",
        action="store_false",
        dest="use_local_listener_target",
        help=(
            "Use --dataplane-probe-target directly. Default uses a temporary "
            "loopback listener while keeping the requested target redacted."
        ),
    )
    parser.set_defaults(use_local_listener_target=True)
    parser.add_argument("--timeout-seconds", type=float, default=180.0)
    parser.add_argument(
        "--require-ready",
        action="store_true",
        help="Return non-zero when the Pilot 0 report is not ready.",
    )
    parser.add_argument("--json", action="store_true", help="Print full JSON report.")
    return parser.parse_args(argv)


def main(argv: Sequence[str] | None = None) -> int:
    args = parse_args(argv)
    generated_at = utc_now()
    tag = timestamp_tag(generated_at)
    work_dir = Path(args.work_dir) if args.work_dir else DEFAULT_WORK_ROOT / tag
    report = run_pilot0(
        work_dir=work_dir,
        output_dir=Path(args.output_dir),
        dataplane_probe_target=args.dataplane_probe_target,
        timeout_seconds=args.timeout_seconds,
        use_local_listener_target=args.use_local_listener_target,
        generated_at_utc=generated_at,
    )
    if args.json:
        print(json.dumps(report, indent=2, sort_keys=True))
    else:
        artifacts = report.get("artifacts", {})
        print(f"decision={report.get('decision')}")
        print(f"ready={str(report.get('ready')).lower()}")
        if isinstance(artifacts, Mapping):
            print(f"json={artifacts.get('json')}")
            print(f"markdown={artifacts.get('markdown')}")
    if args.require_ready and report.get("ready") is not True:
        return 1
    return 0 if report.get("ready") is True else 1


if __name__ == "__main__":
    raise SystemExit(main())
