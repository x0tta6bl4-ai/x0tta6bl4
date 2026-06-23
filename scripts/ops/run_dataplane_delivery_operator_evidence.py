#!/usr/bin/env python3
"""Run a bounded dataplane-delivery operator evidence collection.

This command is for an authorized local operator. By default it is read-only
and only reports whether the target metadata is ready. With
``--allow-operator-probe`` it opens one TCP connection to a loopback, private,
or link-local target, writes a redacted EventBus evidence event, writes a local
proof-gate report, and writes this runner report. It does not prove customer
traffic, external reachability, DPI bypass, settlement finality, production
SLOs, or production readiness.
"""

from __future__ import annotations

import argparse
import json
import os
import sys
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Mapping, Sequence


ROOT = Path(__file__).resolve().parents[2]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from scripts.ops import collect_dataplane_delivery_eventbus_evidence as collector
from scripts.ops import run_cross_plane_proof_gate as proof_gate
from scripts.ops import run_dataplane_delivery_operator_handoff as handoff


SCHEMA = "x0tta6bl4.dataplane_delivery_operator_evidence_run.v1"
DECISION_INPUT_REQUIRED = "DATAPLANE_OPERATOR_EVIDENCE_INPUT_REQUIRED"
DECISION_PROBE_NOT_AUTHORIZED = "DATAPLANE_OPERATOR_EVIDENCE_PROBE_NOT_AUTHORIZED"
DECISION_RETAINED = "DATAPLANE_OPERATOR_EVIDENCE_RETAINED"
DECISION_FAILED = "DATAPLANE_OPERATOR_EVIDENCE_FAILED"
DEFAULT_OUTPUT_JSON = Path(
    ".tmp/validation-shards/dataplane-delivery-operator-evidence-current.json"
)
DEFAULT_PROOF_GATE_OUTPUT_JSON = Path(
    ".tmp/validation-shards/cross-plane-proof-gate-current.json"
)
CLAIM_BOUNDARY = (
    "Bounded operator-run dataplane evidence collection. A successful run can "
    "retain one redacted local/private TCP probe EventBus event and a local "
    "proof-gate report for dataplane-delivery evidence context; it does not "
    "prove customer traffic, external reachability, DPI bypass, settlement "
    "finality, production SLOs, or production readiness."
)
# Contract marker for readiness static scan: does not prove customer traffic.


def utc_now() -> str:
    return (
        datetime.now(timezone.utc)
        .replace(microsecond=0)
        .isoformat()
        .replace("+00:00", "Z")
    )


def _mapping(value: Any) -> Mapping[str, Any]:
    return value if isinstance(value, Mapping) else {}


def _claim_result(report: Mapping[str, Any], claim_id: str) -> Mapping[str, Any]:
    for item in report.get("claim_results") or []:
        if isinstance(item, Mapping) and item.get("claim_id") == claim_id:
            return item
    return {}


def _write_json(path: Path, payload: Mapping[str, Any]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(
        json.dumps(payload, ensure_ascii=False, indent=2, sort_keys=True) + "\n",
        encoding="utf-8",
    )


def _base_report(
    *,
    root: Path,
    target_label: str,
    target_host: str,
    target_port: Any,
    timeout_s: float,
    output_json: Path,
    proof_gate_output_json: Path,
) -> dict[str, Any]:
    handoff_report = handoff.build_report(
        root,
        target_host=target_host,
        target_port=target_port,
        target_label=target_label,
    )
    target = _mapping(handoff_report.get("target"))
    return {
        "schema": SCHEMA,
        "generated_at_utc": utc_now(),
        "decision": DECISION_INPUT_REQUIRED,
        "ok": False,
        "claim_boundary": CLAIM_BOUNDARY,
        "root": str(root),
        "target": {
            "label": str(target_label or "operator-target"),
            "host_hash": target.get("host_hash"),
            "host_present": target.get("host_present") is True,
            "port": target.get("port"),
            "target_is_localish": target.get("target_is_localish") is True,
            "raw_target_redacted": True,
        },
        "summary": {
            "handoff_ready": handoff_report.get("ready_for_operator_run") is True,
            "probe_authorized": False,
            "probe_attempted": False,
            "event_written": False,
            "proof_gate_report_written": False,
            "proof_gate_artifact_valid": False,
            "operator_run_evidence_retained": False,
            "eventbus_evidence_recognized_by_proof_gate": False,
            "writes_eventbus": False,
            "writes_validation_artifacts": False,
            "opens_socket": False,
            "mutates_services": False,
            "raw_targets_redacted": True,
            "customer_traffic_claimed": False,
            "external_reachability_claimed": False,
            "dpi_bypass_claimed": False,
            "settlement_finality_claimed": False,
            "traffic_delivery_claimed": False,
            "production_readiness_claimed": False,
        },
        "handoff": {
            "decision": handoff_report.get("decision"),
            "ready_for_operator_run": handoff_report.get("ready_for_operator_run"),
            "blockers": list(handoff_report.get("blockers") or []),
            "operator_env_vars": list(handoff_report.get("operator_env_vars") or []),
            "operator_commands": list(handoff_report.get("operator_commands") or []),
        },
        "collector": None,
        "proof_gate": None,
        "artifacts": {
            "event_log": str(root / collector.EventBus.EVENT_LOG),
            "output_json": str(output_json),
            "proof_gate_output_json": str(proof_gate_output_json),
        },
        "safe_local_input_steps": [
            "Set X0T_DATAPLANE_PROBE_HOST locally to a loopback, private, or link-local target.",
            "Set X0T_DATAPLANE_PROBE_PORT locally to the TCP port to probe.",
            "Run this command with --allow-operator-probe only inside an authorized environment.",
            "Do not paste private targets, tokens, packet captures, or subscriber data into chat.",
        ],
        "blockers": list(handoff_report.get("blockers") or []),
        "timeout_s": float(timeout_s),
    }


def build_report(
    root: Path,
    *,
    target_host: str = "",
    target_port: Any = "",
    target_label: str = "operator-target",
    timeout_s: float = 2.0,
    allow_operator_probe: bool = False,
    output_json: Path = DEFAULT_OUTPUT_JSON,
    proof_gate_output_json: Path = DEFAULT_PROOF_GATE_OUTPUT_JSON,
) -> dict[str, Any]:
    root = root.resolve()
    output_json = output_json if output_json.is_absolute() else root / output_json
    proof_gate_output_json = (
        proof_gate_output_json
        if proof_gate_output_json.is_absolute()
        else root / proof_gate_output_json
    )
    report = _base_report(
        root=root,
        target_label=target_label,
        target_host=target_host,
        target_port=target_port,
        timeout_s=timeout_s,
        output_json=output_json,
        proof_gate_output_json=proof_gate_output_json,
    )
    if report["blockers"]:
        return report
    if not allow_operator_probe:
        report["decision"] = DECISION_PROBE_NOT_AUTHORIZED
        report["blockers"] = ["allow_operator_probe_required"]
        return report

    args = collector.parse_args(
        [
            "--root",
            str(root),
            "--host",
            str(target_host),
            "--port",
            str(target_port),
            "--timeout-s",
            str(timeout_s),
            "--source-agent",
            collector.DEFAULT_SOURCE_AGENT,
            "--allow-local-probe",
            "--write-event",
            "--json",
        ]
    )
    collector_report = collector.collect(args)
    report["collector"] = {
        "decision": collector_report.get("decision"),
        "event_written": collector_report.get("event_written") is True,
        "event_id": collector_report.get("event_id", ""),
        "event_log": collector_report.get("event_log", ""),
        "ready_for_proof_gate": collector_report.get("ready_for_proof_gate") is True,
        "probe_status": _mapping(collector_report.get("probe")).get("status"),
        "probe_error_type": _mapping(collector_report.get("probe")).get("error_type", ""),
        "raw_target_redacted": _mapping(
            _mapping(collector_report.get("probe")).get("target")
        ).get("raw_target_redacted")
        is True,
    }
    report["summary"]["probe_authorized"] = True
    report["summary"]["probe_attempted"] = True
    report["summary"]["opens_socket"] = True
    report["summary"]["writes_eventbus"] = True
    report["summary"]["writes_validation_artifacts"] = True
    report["summary"]["event_written"] = collector_report.get("event_written") is True

    if collector_report.get("ready_for_proof_gate") is not True:
        report["decision"] = DECISION_FAILED
        report["blockers"] = ["dataplane_operator_probe_failed"]
        _write_json(output_json, report)
        return report

    proof_report = proof_gate.build_report(
        root,
        output_json=proof_gate_output_json.relative_to(root)
        if proof_gate_output_json.is_relative_to(root)
        else proof_gate_output_json,
        claims=("dataplane_delivery",),
    )
    proof_gate.atomic_write_json(proof_gate_output_json, proof_report)
    dataplane_result = _claim_result(proof_report, "dataplane_delivery")
    artifact = _mapping(dataplane_result.get("required_artifact_evidence"))
    selected_event = _mapping(artifact.get("selected_event"))
    artifact_valid = artifact.get("valid") is True

    report["proof_gate"] = {
        "decision": proof_report.get("decision"),
        "allowed": proof_report.get("allowed") is True,
        "dataplane_claim_allowed": dataplane_result.get("allowed") is True,
        "dataplane_claim_blockers": list(dataplane_result.get("blockers") or []),
        "artifact_valid": artifact_valid,
        "matching_events": artifact.get("matching_events", 0),
        "selected_event": {
            "event_id": selected_event.get("event_id", ""),
            "source_agent": selected_event.get("source_agent", ""),
            "scan_source": selected_event.get("scan_source", ""),
            "dataplane_confirmed": selected_event.get("dataplane_confirmed") is True,
            "restored_dataplane_claim_allowed": (
                selected_event.get("restored_dataplane_claim_allowed") is True
            ),
            "traffic_delivery_claim_allowed": (
                selected_event.get("traffic_delivery_claim_allowed") is True
            ),
            "customer_traffic_claim_allowed": (
                selected_event.get("customer_traffic_claim_allowed") is True
            ),
            "production_readiness_claim_allowed": (
                selected_event.get("production_readiness_claim_allowed") is True
            ),
            "redacted": selected_event.get("redacted") is True,
        },
    }
    report["summary"]["proof_gate_report_written"] = True
    report["summary"]["proof_gate_artifact_valid"] = artifact_valid
    report["summary"]["eventbus_evidence_recognized_by_proof_gate"] = artifact_valid
    report["summary"]["operator_run_evidence_retained"] = artifact_valid
    report["ok"] = artifact_valid
    report["decision"] = DECISION_RETAINED if artifact_valid else DECISION_FAILED
    report["blockers"] = [] if artifact_valid else ["dataplane_eventbus_artifact_not_verified"]
    _write_json(output_json, report)
    return report


def parse_args(argv: Sequence[str] | None = None) -> argparse.Namespace:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--root", type=Path, default=ROOT)
    parser.add_argument(
        "--target-host",
        default=os.environ.get("X0T_DATAPLANE_PROBE_HOST", ""),
        help="Private, loopback, or link-local target host. Defaults to env.",
    )
    parser.add_argument(
        "--target-port",
        default=os.environ.get("X0T_DATAPLANE_PROBE_PORT", ""),
        help="Target TCP port. Defaults to env.",
    )
    parser.add_argument(
        "--target-label",
        default=os.environ.get("X0T_DATAPLANE_PROBE_LABEL", "operator-target"),
    )
    parser.add_argument("--timeout-s", type=float, default=2.0)
    parser.add_argument("--allow-operator-probe", action="store_true")
    parser.add_argument("--require-retained", action="store_true")
    parser.add_argument("--output-json", type=Path, default=DEFAULT_OUTPUT_JSON)
    parser.add_argument(
        "--proof-gate-output-json",
        type=Path,
        default=DEFAULT_PROOF_GATE_OUTPUT_JSON,
    )
    parser.add_argument("--json", action="store_true")
    return parser.parse_args(argv)


def main(argv: Sequence[str] | None = None) -> int:
    args = parse_args(argv)
    report = build_report(
        args.root,
        target_host=args.target_host,
        target_port=args.target_port,
        target_label=args.target_label,
        timeout_s=args.timeout_s,
        allow_operator_probe=args.allow_operator_probe,
        output_json=args.output_json,
        proof_gate_output_json=args.proof_gate_output_json,
    )
    if args.json:
        print(json.dumps(report, ensure_ascii=False, indent=2, sort_keys=True))
    else:
        print(f"decision={report['decision']}")
        print(f"ok={report['ok']}")
        for blocker in report["blockers"]:
            print(f"- {blocker}")
    return 0 if report["ok"] or not args.require_retained else 1


if __name__ == "__main__":
    raise SystemExit(main())
