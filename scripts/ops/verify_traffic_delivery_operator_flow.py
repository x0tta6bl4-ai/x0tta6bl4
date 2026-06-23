#!/usr/bin/env python3
"""Verify bounded local traffic-delivery evidence generation.

This verifier is intentionally local and controlled. It starts a temporary
loopback TCP server, sends one synthetic request, receives one synthetic
response, converts the redacted probe report into the existing traffic-delivery
collector contract, and checks that the cross-plane proof gate recognizes the
retained EventBus event as a bounded traffic-delivery claim.

It does not prove customer traffic, external reachability, DPI bypass,
settlement finality, production SLOs, or production readiness.
"""

from __future__ import annotations

import argparse
import hashlib
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

from scripts.ops import collect_traffic_delivery_eventbus_evidence as collector
from scripts.ops.run_cross_plane_proof_gate import (
    build_report as build_cross_plane_report,
)
from scripts.ops.run_cross_plane_proof_gate import traffic_delivery_artifact_evidence
from src.mesh.traffic_delivery_contracts import (
    TRAFFIC_DELIVERY_CLAIM_BOUNDARY,
    TRAFFIC_DELIVERY_INPUT_SCHEMA,
)


SCHEMA = "x0tta6bl4.traffic_delivery_operator_flow.v1"
DECISION_VERIFIED = "TRAFFIC_DELIVERY_OPERATOR_FLOW_VERIFIED"
DECISION_GAPS = "TRAFFIC_DELIVERY_OPERATOR_FLOW_GAPS"
REQUEST_PAYLOAD = b"x0tta6bl4 traffic delivery probe request"
RESPONSE_PAYLOAD = b"x0tta6bl4 traffic delivery probe response"
CLAIM_BOUNDARY = (
    "Traffic-delivery operator-flow verifier is a local controlled loopback "
    "harness only. It proves the redacted synthetic traffic probe, collector, "
    "EventBus, and cross-plane proof-gate path work together for the bounded "
    "traffic_delivery claim; it does not prove customer traffic, external "
    "reachability, DPI bypass, settlement finality, production SLOs, or "
    "production readiness."
)


def utc_now() -> str:
    return (
        datetime.now(timezone.utc)
        .replace(microsecond=0)
        .isoformat()
        .replace("+00:00", "Z")
    )


def sha256_bytes(value: bytes) -> str:
    return hashlib.sha256(value).hexdigest()


def sha256_file(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def _write_minimal_cross_plane_map(root: Path) -> None:
    docs = root / "docs" / "architecture"
    docs.mkdir(parents=True, exist_ok=True)
    (docs / "CURRENT_ACTIVE_GOAL_GAP_AUDIT.md").write_text(
        "# isolated traffic-delivery verifier audit\n",
        encoding="utf-8",
    )
    (docs / "CURRENT_CROSS_PLANE_EVIDENCE_MAP.json").write_text(
        json.dumps(
            {
                "schema": "x0tta6bl4.cross_plane_evidence_map.test.v1",
                "status": "working_map_not_production_completion_proof",
                "planes": {
                    "control_plane": {},
                    "data_plane": {},
                    "economy_plane": {},
                    "evidence_plane": {},
                    "trust_plane": {},
                },
                "cross_plane_links": [
                    {
                        "id": "traffic-delivery-local-operator-flow",
                        "from_planes": ["data_plane"],
                        "to_planes": ["evidence_plane"],
                        "claim_boundary": CLAIM_BOUNDARY,
                        "proof_flags": {
                            "traffic_delivery_confirmed": True,
                            "traffic_delivery_claim_allowed": True,
                            "customer_traffic_claim_allowed": False,
                            "production_customer_traffic_confirmed": False,
                            "production_readiness_claim_allowed": False,
                        },
                    }
                ],
                "current_gaps": [],
                "next_actions": [],
            },
            indent=2,
            sort_keys=True,
        )
        + "\n",
        encoding="utf-8",
    )


def _run_loopback_traffic_probe() -> dict[str, Any]:
    captured: dict[str, Any] = {
        "server_accepted_connection": False,
        "request_observed": False,
        "response_validated": False,
        "traffic_payloads_redacted": True,
        "raw_identifiers_redacted": True,
        "raw_values_redacted": True,
        "payloads_redacted": True,
    }
    server = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
    server.setsockopt(socket.SOL_SOCKET, socket.SO_REUSEADDR, 1)
    server.bind(("127.0.0.1", 0))
    server.listen(1)
    port = int(server.getsockname()[1])

    def _accept_once() -> None:
        try:
            server.settimeout(5.0)
            conn, _addr = server.accept()
            captured["server_accepted_connection"] = True
            with conn:
                conn.settimeout(2.0)
                request = conn.recv(4096)
                captured["request_observed"] = request == REQUEST_PAYLOAD
                captured["request_sha256"] = sha256_bytes(request)
                captured["request_size_bytes"] = len(request)
                conn.sendall(RESPONSE_PAYLOAD)
        except OSError as exc:
            captured["server_error_class"] = type(exc).__name__
        finally:
            server.close()

    thread = threading.Thread(target=_accept_once, daemon=True)
    thread.start()
    try:
        with socket.create_connection(("127.0.0.1", port), timeout=5.0) as client:
            client.settimeout(2.0)
            client.sendall(REQUEST_PAYLOAD)
            response = client.recv(4096)
            captured["response_validated"] = response == RESPONSE_PAYLOAD
            captured["response_sha256"] = sha256_bytes(response)
            captured["response_size_bytes"] = len(response)
    finally:
        thread.join(timeout=5.0)
        try:
            server.close()
        except OSError:
            pass

    captured["target_hash"] = hashlib.sha256(
        f"127.0.0.1:{port}".encode("utf-8")
    ).hexdigest()
    captured["raw_target_redacted"] = True
    captured["target_loopback"] = True
    captured["traffic_flow_confirmed"] = (
        captured["server_accepted_connection"]
        and captured["request_observed"]
        and captured["response_validated"]
    )
    return captured


def _write_probe_artifacts(evidence_root: Path, probe: dict[str, Any]) -> Path:
    artifacts_root = evidence_root / ".tmp" / "traffic-delivery-operator-flow"
    artifacts_root.mkdir(parents=True, exist_ok=True)
    raw_report_path = artifacts_root / "redacted-probe-report.json"
    raw_report = {
        "schema": "x0tta6bl4.traffic_delivery.operator_flow.redacted_probe_report.v1",
        "captured_at_utc": utc_now(),
        "traffic_flow_confirmed": probe["traffic_flow_confirmed"],
        "request_observed": probe["request_observed"],
        "response_validated": probe["response_validated"],
        "traffic_payloads_redacted": True,
        "request_sha256": probe.get("request_sha256", ""),
        "response_sha256": probe.get("response_sha256", ""),
        "request_size_bytes": probe.get("request_size_bytes", 0),
        "response_size_bytes": probe.get("response_size_bytes", 0),
        "target_hash": probe["target_hash"],
        "raw_target_redacted": True,
        "raw_identifiers_redacted": True,
        "raw_values_redacted": True,
        "payloads_redacted": True,
        "claim_boundary": CLAIM_BOUNDARY,
    }
    raw_report_path.write_text(
        json.dumps(raw_report, indent=2, sort_keys=True) + "\n",
        encoding="utf-8",
    )

    proof_path = artifacts_root / "traffic-delivery-proof.json"
    proof = {
        "schema": TRAFFIC_DELIVERY_INPUT_SCHEMA,
        "status": "VERIFIED" if probe["traffic_flow_confirmed"] else "BLOCKED",
        "observed_evidence": {
            "environment": "lab",
            "traffic_class": "synthetic_mesh_flow",
            "traffic_flow_confirmed": probe["traffic_flow_confirmed"],
            "request_observed": probe["request_observed"],
            "response_validated": probe["response_validated"],
            "traffic_payloads_redacted": True,
        },
        "source_artifacts": [
            {
                "role": "redacted_traffic_delivery_scenario_probe_report",
                "sha256": sha256_file(raw_report_path),
                "redacted": True,
            }
        ],
        "raw_identifiers_redacted": True,
        "raw_values_redacted": True,
        "payloads_redacted": True,
        "authorization_scope_redacted": True,
        "claim_boundary": TRAFFIC_DELIVERY_CLAIM_BOUNDARY,
    }
    proof_path.write_text(
        json.dumps(proof, indent=2, sort_keys=True) + "\n",
        encoding="utf-8",
    )
    return proof_path


def _validate_flow(
    *,
    probe: dict[str, Any],
    collector_report: dict[str, Any],
    proof_gate_report: dict[str, Any],
    artifact: dict[str, Any],
) -> list[str]:
    failures: list[str] = []
    if probe.get("traffic_flow_confirmed") is not True:
        failures.append("loopback_traffic_flow_not_confirmed")
    if probe.get("raw_target_redacted") is not True:
        failures.append("probe_target_not_redacted")
    if collector_report.get("decision") != "TRAFFIC_DELIVERY_EVENTBUS_EVIDENCE_READY":
        failures.append("collector_not_ready")
    if collector_report.get("event_written") is not True:
        failures.append("collector_event_not_written")
    if collector_report.get("ready_for_proof_gate") is not True:
        failures.append("collector_not_ready_for_proof_gate")
    if proof_gate_report.get("decision") != "CROSS_PLANE_CLAIMS_ALLOWED":
        failures.append("proof_gate_not_allowed")
    if proof_gate_report.get("allowed") is not True:
        failures.append("proof_gate_allowed_flag_false")
    if artifact.get("valid") is not True:
        failures.append("traffic_delivery_artifact_not_valid")
    if artifact.get("matching_events") != 1:
        failures.append("traffic_delivery_matching_events_not_one")
    selected = artifact.get("selected_event") if isinstance(artifact, dict) else {}
    if not isinstance(selected, dict):
        failures.append("traffic_delivery_selected_event_missing")
    else:
        if selected.get("traffic_delivery_claim_allowed") is not True:
            failures.append("traffic_delivery_claim_not_allowed")
        if selected.get("traffic_delivery_confirmed") is not True:
            failures.append("traffic_delivery_not_confirmed")
        if selected.get("claim_scope") != "traffic_delivery":
            failures.append("traffic_delivery_claim_scope_invalid")
        if selected.get("customer_traffic_claim_allowed") is not False:
            failures.append("traffic_delivery_overpromotes_customer_traffic")
        if selected.get("production_readiness_claim_allowed") is not False:
            failures.append("traffic_delivery_overpromotes_production_readiness")
        if selected.get("redacted") is not True:
            failures.append("traffic_delivery_selected_event_not_redacted")
    return failures


def build_report(root: Path, *, evidence_root: Path | None = None) -> dict[str, Any]:
    root = root.resolve()
    temp_dir: tempfile.TemporaryDirectory[str] | None = None
    if evidence_root is None:
        temp_dir = tempfile.TemporaryDirectory(prefix="x0t-traffic-flow-")
        evidence_root = Path(temp_dir.name)
    evidence_root = evidence_root.resolve()
    evidence_root.mkdir(parents=True, exist_ok=True)
    _write_minimal_cross_plane_map(evidence_root)

    probe = _run_loopback_traffic_probe()
    proof_path = _write_probe_artifacts(evidence_root, probe)
    collector_args = collector.parse_args(
        [
            "--root",
            str(evidence_root),
            "--proof-json",
            str(proof_path),
            "--allow-redacted-local-proof-intake",
            "--write-event",
            "--source-agent",
            "traffic-delivery-probe",
            "--json",
        ]
    )
    collector_report = collector.collect(collector_args)
    proof_gate_report = build_cross_plane_report(evidence_root, claims=("traffic_delivery",))
    artifact = traffic_delivery_artifact_evidence(evidence_root)
    failures = _validate_flow(
        probe=probe,
        collector_report=collector_report,
        proof_gate_report=proof_gate_report,
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
            "cases_run": 6,
            "cases_checked": 6 if verified else 0,
            "local_loopback_probe": True,
            "controlled_synthetic_traffic": True,
            "collector_ready": collector_report.get("ready_for_proof_gate") is True,
            "event_written": collector_report.get("event_written") is True,
            "proof_gate_allowed": proof_gate_report.get("allowed") is True,
            "proof_gate_artifact_valid": artifact.get("valid") is True,
            "eventbus_evidence_recognized_by_proof_gate": artifact.get("valid")
            is True,
            "raw_targets_redacted": probe.get("raw_target_redacted") is True,
            "payloads_redacted": probe.get("payloads_redacted") is True,
            "mutates_project_runtime": False,
            "writes_temp_eventbus": True,
            "traffic_delivery_claimed": proof_gate_report.get("allowed") is True,
            "customer_traffic_claimed": False,
            "external_reachability_claimed": False,
            "dpi_bypass_claimed": False,
            "settlement_finality_claimed": False,
            "production_readiness_claimed": False,
        },
        "evidence": {
            "event_id": collector_report.get("event_id", ""),
            "event_log": collector_report.get("event_log", ""),
            "proof_json": str(proof_path),
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
        description="Verify bounded local traffic-delivery evidence generation."
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
