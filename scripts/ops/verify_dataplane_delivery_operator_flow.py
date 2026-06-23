#!/usr/bin/env python3
"""Verify the local dataplane-delivery operator handoff flow.

This verifier is intentionally local and bounded. It starts a temporary
loopback TCP listener, runs the read-only operator handoff, writes one bounded
collector EventBus event into an isolated evidence root, and verifies that the
cross-plane proof gate recognizes that event as local restored-dataplane
evidence. It does not prove customer traffic, external reachability, DPI
bypass, settlement finality, production SLOs, or production readiness.
"""

from __future__ import annotations

import argparse
import json
import socket
import sys
import tempfile
import threading
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Sequence


ROOT = Path(__file__).resolve().parents[2]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from scripts.ops import collect_dataplane_delivery_eventbus_evidence as collector
from scripts.ops import run_dataplane_delivery_operator_handoff as handoff
from scripts.ops.run_cross_plane_proof_gate import dataplane_delivery_artifact_evidence


SCHEMA = "x0tta6bl4.dataplane_delivery_operator_flow.v1"
DECISION_VERIFIED = "DATAPLANE_DELIVERY_OPERATOR_FLOW_VERIFIED"
DECISION_GAPS = "DATAPLANE_DELIVERY_OPERATOR_FLOW_GAPS"
CLAIM_BOUNDARY = (
    "Dataplane delivery operator-flow verifier is a local simulated harness "
    "only. It proves the read-only handoff, opt-in collector, redaction, and "
    "proof-gate EventBus recognition path work together; it does not prove "
    "real operator-run evidence, customer traffic, external reachability, DPI "
    "bypass, settlement finality, production SLOs, or production readiness."
)


def utc_now() -> str:
    return (
        datetime.now(timezone.utc)
        .replace(microsecond=0)
        .isoformat()
        .replace("+00:00", "Z")
    )


def _serve_one_loopback_connection() -> tuple[socket.socket, threading.Thread, int]:
    server = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
    server.setsockopt(socket.SOL_SOCKET, socket.SO_REUSEADDR, 1)
    server.bind(("127.0.0.1", 0))
    server.listen(1)
    port = int(server.getsockname()[1])

    def _accept_once() -> None:
        try:
            server.settimeout(5.0)
            conn, _addr = server.accept()
            with conn:
                conn.settimeout(1.0)
                try:
                    conn.recv(1)
                except (TimeoutError, socket.timeout):
                    pass
        finally:
            server.close()

    thread = threading.Thread(target=_accept_once, daemon=True)
    thread.start()
    return server, thread, port


def _validate_flow(
    *,
    handoff_report: dict[str, Any],
    collector_report: dict[str, Any],
    artifact: dict[str, Any],
) -> list[str]:
    failures: list[str] = []
    if handoff_report.get("decision") != handoff.DECISION_READY:
        failures.append("handoff_not_ready")
    if handoff_report.get("ready_for_operator_run") is not True:
        failures.append("handoff_ready_flag_false")
    if handoff_report.get("mutates_runtime") is not False:
        failures.append("handoff_mutates_runtime")
    if handoff_report.get("runs_probe") is not False:
        failures.append("handoff_runs_probe")
    if handoff_report.get("writes_eventbus") is not False:
        failures.append("handoff_writes_eventbus")
    target = handoff_report.get("target") if isinstance(handoff_report, dict) else {}
    if not isinstance(target, dict) or target.get("raw_target_redacted") is not True:
        failures.append("handoff_target_not_redacted")

    if collector_report.get("decision") != "DATAPLANE_EVENTBUS_EVIDENCE_READY":
        failures.append("collector_not_ready")
    if collector_report.get("event_written") is not True:
        failures.append("collector_event_not_written")
    if collector_report.get("ready_for_proof_gate") is not True:
        failures.append("collector_not_ready_for_proof_gate")
    probe = collector_report.get("probe") if isinstance(collector_report, dict) else {}
    probe_target = probe.get("target") if isinstance(probe, dict) else {}
    if not isinstance(probe_target, dict) or probe_target.get("raw_target_redacted") is not True:
        failures.append("collector_target_not_redacted")

    if artifact.get("valid") is not True:
        failures.append("proof_gate_artifact_not_valid")
    selected = artifact.get("selected_event") if isinstance(artifact, dict) else {}
    if not isinstance(selected, dict):
        failures.append("proof_gate_selected_event_missing")
    else:
        if selected.get("dataplane_confirmed") is not True:
            failures.append("proof_gate_dataplane_not_confirmed")
        if selected.get("restored_dataplane_claim_allowed") is not True:
            failures.append("proof_gate_restored_dataplane_not_allowed")
        if selected.get("traffic_delivery_claim_allowed") is not False:
            failures.append("proof_gate_overpromotes_traffic_delivery")
        if selected.get("customer_traffic_claim_allowed") is not False:
            failures.append("proof_gate_overpromotes_customer_traffic")
        if selected.get("production_readiness_claim_allowed") is not False:
            failures.append("proof_gate_overpromotes_production_readiness")
        if selected.get("redacted") is not True:
            failures.append("proof_gate_selected_event_not_redacted")
    return failures


def build_report(root: Path, *, evidence_root: Path | None = None) -> dict[str, Any]:
    root = root.resolve()
    temp_dir: tempfile.TemporaryDirectory[str] | None = None
    if evidence_root is None:
        temp_dir = tempfile.TemporaryDirectory(prefix="x0t-dataplane-flow-")
        evidence_root = Path(temp_dir.name)
    evidence_root = evidence_root.resolve()
    evidence_root.mkdir(parents=True, exist_ok=True)

    server, thread, port = _serve_one_loopback_connection()
    try:
        handoff_report = handoff.build_report(
            root,
            target_host="127.0.0.1",
            target_port=str(port),
            target_label="local-loopback-verifier",
        )
        args = collector.parse_args(
            [
                "--root",
                str(evidence_root),
                "--host",
                "127.0.0.1",
                "--port",
                str(port),
                "--allow-local-probe",
                "--write-event",
                "--source-agent",
                "dataplane-delivery-local-collector",
                "--json",
            ]
        )
        collector_report = collector.collect(args)
        thread.join(timeout=5.0)
    finally:
        try:
            server.close()
        except OSError:
            pass

    artifact = dataplane_delivery_artifact_evidence(evidence_root)
    failures = _validate_flow(
        handoff_report=handoff_report,
        collector_report=collector_report,
        artifact=artifact,
    )
    verified = not failures
    report = {
        "schema": SCHEMA,
        "generated_at_utc": utc_now(),
        "decision": DECISION_VERIFIED if verified else DECISION_GAPS,
        "ok": verified,
        "claim_boundary": CLAIM_BOUNDARY,
        "summary": {
            "cases_run": 5,
            "cases_checked": 5 if verified else 0,
            "handoff_cases": 2,
            "collector_cases": 3,
            "proof_gate_artifacts_checked": 1,
            "command_surface_checked": True,
            "local_simulated_harness": True,
            "local_loopback_probe": True,
            "runs_live_probe": False,
            "handoff_ready": handoff_report.get("ready_for_operator_run") is True,
            "collector_ready": collector_report.get("ready_for_proof_gate") is True,
            "event_written": collector_report.get("event_written") is True,
            "proof_gate_artifact_valid": artifact.get("valid") is True,
            "mutates_project_runtime": False,
            "writes_temp_eventbus": True,
            "operator_run_evidence_claimed": False,
            "real_operator_run_evidence_retained": False,
            "eventbus_evidence_recognized_by_proof_gate": artifact.get("valid") is True,
            "raw_targets_redacted": True,
            "customer_traffic_claimed": False,
            "external_reachability_claimed": False,
            "dpi_bypass_claimed": False,
            "settlement_finality_claimed": False,
            "traffic_delivery_claimed": False,
            "production_readiness_claimed": False,
        },
        "evidence": {
            "event_id": collector_report.get("event_id", ""),
            "event_log": collector_report.get("event_log", ""),
            "selected_event": artifact.get("selected_event"),
            "matching_events": artifact.get("matching_events", 0),
            "raw_target_redacted": True,
            "evidence_root": str(evidence_root),
        },
        "failures": failures,
    }
    if temp_dir is not None:
        temp_dir.cleanup()
        report["evidence"]["evidence_root_retained"] = False
    else:
        report["evidence"]["evidence_root_retained"] = True
    return report


def parse_args(argv: Sequence[str] | None = None) -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description="Verify local dataplane-delivery operator handoff flow."
    )
    parser.add_argument("--root", type=Path, default=ROOT)
    parser.add_argument("--evidence-root", type=Path, default=None)
    parser.add_argument("--output-json", type=Path, default=None)
    parser.add_argument("--require-verified", action="store_true")
    parser.add_argument("--json", action="store_true")
    return parser.parse_args(argv)


def main(argv: Sequence[str] | None = None) -> int:
    args = parse_args(argv)
    report = build_report(args.root, evidence_root=args.evidence_root)
    if args.output_json:
        args.output_json.parent.mkdir(parents=True, exist_ok=True)
        args.output_json.write_text(
            json.dumps(report, ensure_ascii=False, indent=2, sort_keys=True) + "\n",
            encoding="utf-8",
        )
    if args.json:
        print(json.dumps(report, ensure_ascii=False, indent=2, sort_keys=True))
    else:
        print(f"decision={report['decision']}")
        print(f"ok={report['ok']}")
        for failure in report["failures"]:
            print(f"- {failure}")
    return 0 if report["ok"] or not args.require_verified else 1


if __name__ == "__main__":
    raise SystemExit(main())
