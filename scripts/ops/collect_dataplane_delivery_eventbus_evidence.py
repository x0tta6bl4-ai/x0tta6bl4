#!/usr/bin/env python3
"""Collect bounded local post-action dataplane EventBus evidence.

This collector is intentionally narrow: it can only make a local restored
dataplane subclaim after an explicit local TCP probe succeeds. It does not prove
customer traffic, external reachability, DPI bypass, settlement finality,
production SLOs, or production readiness.
"""

from __future__ import annotations

import argparse
import hashlib
import ipaddress
import json
import socket
import sys
import uuid
from pathlib import Path
from typing import Any, Callable

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT))

from src.coordination.events import EventBus, EventType


SCHEMA = "x0tta6bl4.dataplane_delivery_eventbus_evidence_collector.v1"
DEFAULT_SOURCE_AGENT = "dataplane-delivery-local-collector"
CLAIM_BOUNDARY = (
    "Bounded local TCP probe evidence for restored dataplane only. This does "
    "not prove customer traffic, external reachability, DPI bypass, settlement "
    "finality, production SLOs, or production readiness."
)

Connector = Callable[[str, int, float], None]


def sha256_text(value: str) -> str:
    return hashlib.sha256(value.encode("utf-8")).hexdigest()


def parse_args(argv: list[str] | None = None) -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description="Collect bounded local post-action dataplane EventBus evidence."
    )
    parser.add_argument("--root", type=Path, default=Path("."))
    parser.add_argument("--host", default="127.0.0.1")
    parser.add_argument("--port", type=int, required=True)
    parser.add_argument("--timeout-s", type=float, default=2.0)
    parser.add_argument("--source-agent", default=DEFAULT_SOURCE_AGENT)
    parser.add_argument(
        "--allow-local-probe",
        action="store_true",
        help="Required before the collector opens a local TCP connection.",
    )
    parser.add_argument(
        "--write-event",
        action="store_true",
        help="Append the bounded probe result to .agent_coordination/events.log.",
    )
    parser.add_argument("--json", action="store_true")
    return parser.parse_args(argv)


def is_localish_target(host: str) -> bool:
    normalized = host.strip().lower()
    if normalized == "localhost":
        return True
    try:
        address = ipaddress.ip_address(normalized)
    except ValueError:
        return False
    return address.is_loopback or address.is_private or address.is_link_local


def default_connector(host: str, port: int, timeout_s: float) -> None:
    with socket.create_connection((host, port), timeout=timeout_s):
        return None


def run_probe(
    host: str,
    port: int,
    timeout_s: float,
    connector: Connector = default_connector,
) -> dict[str, Any]:
    metadata = {
        "host_hash": sha256_text(host.strip()),
        "port": int(port),
        "timeout_s": float(timeout_s),
        "target_is_localish": is_localish_target(host),
        "raw_target_redacted": True,
    }
    try:
        connector(host, port, timeout_s)
    except Exception as exc:  # noqa: BLE001 - error type is the bounded output.
        return {
            "status": "FAIL",
            "dataplane_confirmed": False,
            "error_type": type(exc).__name__,
            "target": metadata,
        }
    return {
        "status": "PASS",
        "dataplane_confirmed": True,
        "claim_boundary": CLAIM_BOUNDARY,
        "error_type": "",
        "target": metadata,
    }


def build_event_data(probe: dict[str, Any], *, source_agent: str) -> dict[str, Any]:
    confirmed = probe.get("dataplane_confirmed") is True
    blockers = [] if confirmed else ["bounded_local_tcp_probe_failed"]
    probe_event_id = f"local-probe-{uuid.uuid4()}"
    claim_gate = {
        "schema": "x0tta6bl4.post_action_dataplane_claim_gate.v1",
        "restored_dataplane_claim_allowed": confirmed,
        "redacted": True,
        "blockers": blockers,
        "observed_evidence": {
            "probe_attempted": True,
            "dataplane_confirmed": confirmed,
            "target_hash": probe.get("target", {}).get("host_hash"),
            "raw_target_redacted": True,
        },
        "claim_boundary": CLAIM_BOUNDARY,
    }
    revalidation = {
        "schema": "x0tta6bl4.post_action_dataplane_revalidation.v1",
        "status": "success" if confirmed else "failed",
        "reason": (
            "bounded_local_tcp_probe_succeeded"
            if confirmed
            else "bounded_local_tcp_probe_failed"
        ),
        "probe_attempted": True,
        "dataplane_confirmed": confirmed,
        "post_action_dataplane_revalidated": confirmed,
        "restored_dataplane_claim_allowed": confirmed,
        "redacted": True,
        "claim_boundary": CLAIM_BOUNDARY,
        "claim_gate": claim_gate,
        "evidence": {
            "source_agents": [source_agent],
            "source_agents_count": 1,
            "event_ids": [probe_event_id],
            "event_ids_count": 1,
            "events_total": 1,
            "claim_boundaries": [CLAIM_BOUNDARY],
            "claim_boundaries_total": 1,
            "redacted": True,
        },
    }
    return {
        "schema": SCHEMA,
        "component": "post_action_dataplane_local_collector",
        "stage": "bounded_local_tcp_probe",
        "operation": "post_action_dataplane_revalidation",
        "probe_status": probe.get("status"),
        "probe_error_type": probe.get("error_type", ""),
        "probe_target": probe.get("target", {}),
        "dataplane_confirmed": confirmed,
        "post_action_dataplane_revalidated": confirmed,
        "restored_dataplane_claim_allowed": confirmed,
        "traffic_delivery_claim_allowed": False,
        "customer_traffic_claim_allowed": False,
        "production_readiness_claim_allowed": False,
        "external_reachability_claim_allowed": False,
        "dpi_bypass_claim_allowed": False,
        "settlement_finality_claim_allowed": False,
        "post_action_dataplane_revalidation": revalidation,
        "claim_boundary": CLAIM_BOUNDARY,
    }


def collect(
    args: argparse.Namespace,
    *,
    connector: Connector = default_connector,
) -> dict[str, Any]:
    root = args.root.resolve()
    if not args.allow_local_probe:
        return {
            "schema": SCHEMA,
            "decision": "BLOCKED_LOCAL_PROBE_NOT_AUTHORIZED",
            "event_written": False,
            "ready_for_proof_gate": False,
            "claim_boundary": CLAIM_BOUNDARY,
            "blockers": ["allow_local_probe_required"],
        }
    if not is_localish_target(args.host):
        return {
            "schema": SCHEMA,
            "decision": "BLOCKED_NON_LOCAL_TARGET",
            "event_written": False,
            "ready_for_proof_gate": False,
            "claim_boundary": CLAIM_BOUNDARY,
            "blockers": ["target_must_be_loopback_private_or_link_local"],
        }

    probe = run_probe(args.host, args.port, args.timeout_s, connector=connector)
    event_data = build_event_data(probe, source_agent=args.source_agent)
    event_written = False
    event_id = ""
    if args.write_event:
        event = EventBus(project_root=str(root)).publish(
            EventType.PIPELINE_STAGE_END,
            args.source_agent,
            event_data,
            priority=6,
        )
        event_written = True
        event_id = event.event_id

    ready = probe.get("dataplane_confirmed") is True and event_written
    return {
        "schema": SCHEMA,
        "decision": "DATAPLANE_EVENTBUS_EVIDENCE_READY" if ready else "DATAPLANE_PROBE_FAILED",
        "event_written": event_written,
        "event_id": event_id,
        "event_log": str(root / EventBus.EVENT_LOG),
        "ready_for_proof_gate": ready,
        "probe": probe,
        "claim_boundary": CLAIM_BOUNDARY,
        "proof_gate_command": [
            "python3",
            "scripts/ops/run_cross_plane_proof_gate.py",
            "--claim",
            "dataplane_delivery",
            "--json",
        ],
    }


def main(argv: list[str] | None = None) -> int:
    args = parse_args(argv)
    report = collect(args)
    if args.json:
        print(json.dumps(report, ensure_ascii=False, indent=2, sort_keys=True))
    else:
        print(f"decision={report['decision']}")
        print(f"ready_for_proof_gate={report['ready_for_proof_gate']}")
        print(f"event_written={report['event_written']}")
        if report.get("event_id"):
            print(f"event_id={report['event_id']}")
    return 0 if report.get("decision") != "DATAPLANE_PROBE_FAILED" else 1


if __name__ == "__main__":
    raise SystemExit(main())
