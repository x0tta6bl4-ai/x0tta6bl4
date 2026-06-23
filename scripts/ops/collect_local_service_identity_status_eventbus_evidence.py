#!/usr/bin/env python3
"""Collect redacted local service identity configuration inventory evidence.

This collector records whether known event-producing services have identity
configuration hints present. It does not read raw SPIFFE IDs, DIDs, wallet
addresses, private keys, SPIRE sockets, or chain state, and it does not prove
trust finality.
"""

from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path
from typing import Any

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT))

from src.coordination.events import EventBus, EventType
from src.services.service_identity_registry import (
    IDENTITY_STATUS_CLAIM_BOUNDARY,
    service_identity_registry_status,
)


SCHEMA = "x0tta6bl4.local_service_identity_status_collector.v1"
EVENTBUS_SCHEMA = "x0tta6bl4.local_service_identity_status.eventbus_evidence.v1"
CLAIM_BOUNDARY = (
    "Local service identity configuration inventory only. This records redacted "
    "counts for configured SPIFFE/DID/wallet fields across known event-producing "
    "services. It does not prove live SPIFFE SVID issuance, DID ownership, "
    "wallet control, chain identity finality, dataplane delivery, customer "
    "traffic, settlement finality, production SLOs, or production readiness."
)


def parse_args(argv: list[str] | None = None) -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description="Collect redacted local service identity status EventBus evidence."
    )
    parser.add_argument("--root", type=Path, default=Path("."))
    parser.add_argument("--write-event", action="store_true")
    parser.add_argument("--json", action="store_true")
    return parser.parse_args(argv)


def _field_counts(status: dict[str, Any]) -> dict[str, int]:
    counts = {"spiffe_id": 0, "did": 0, "wallet_address": 0}
    services = status.get("services")
    if not isinstance(services, list):
        return counts
    for service in services:
        if not isinstance(service, dict):
            continue
        fields = service.get("fields")
        if not isinstance(fields, dict):
            continue
        for field in counts:
            field_status = fields.get(field)
            if isinstance(field_status, dict) and field_status.get("configured") is True:
                counts[field] += 1
    return counts


def build_event_data(status: dict[str, Any]) -> dict[str, Any]:
    services_total = int(status.get("services_total") or 0)
    services_with_any_identity = int(status.get("services_with_any_identity") or 0)
    services_complete = int(status.get("services_complete") or 0)
    configured_field_counts = _field_counts(status)
    claim_gate = {
        "schema": "x0tta6bl4.local_service_identity_status.claim_gate.v1",
        "local_service_identity_status_claim_allowed": services_total > 0,
        "services_total": services_total,
        "services_with_any_identity": services_with_any_identity,
        "services_complete": services_complete,
        "configured_field_counts": configured_field_counts,
        "raw_identity_values_redacted": True,
        "payloads_redacted": True,
        "live_spiffe_svid_claim_allowed": False,
        "did_ownership_claim_allowed": False,
        "wallet_control_claim_allowed": False,
        "chain_identity_finality_claim_allowed": False,
        "dataplane_delivery_claim_allowed": False,
        "customer_traffic_claim_allowed": False,
        "settlement_finality_claim_allowed": False,
        "production_readiness_claim_allowed": False,
        "claim_boundary": CLAIM_BOUNDARY,
        "redacted": True,
    }
    return {
        "schema": EVENTBUS_SCHEMA,
        "component": "local_service_identity_status_collector",
        "operation": "service_identity_status_inventory",
        "status": "success" if services_total > 0 else "blocked",
        "services_total": services_total,
        "services_with_any_identity": services_with_any_identity,
        "services_complete": services_complete,
        "configured_field_counts": configured_field_counts,
        "identity_fields": list(status.get("identity_fields") or []),
        "registry_claim_boundary": status.get("claim_boundary")
        or IDENTITY_STATUS_CLAIM_BOUNDARY,
        "raw_identity_values_redacted": True,
        "raw_identifiers_redacted": True,
        "payloads_redacted": True,
        "live_spiffe_svid_confirmed": False,
        "live_spire_svid_confirmed": False,
        "did_ownership_confirmed": False,
        "wallet_control_confirmed": False,
        "chain_identity_finality_confirmed": False,
        "dataplane_confirmed": False,
        "production_readiness_claim_allowed": False,
        "claim_gate": claim_gate,
        "service_identity_status_claim_gate": claim_gate,
        "claim_boundary": CLAIM_BOUNDARY,
        "redacted": True,
    }


def collect(args: argparse.Namespace) -> dict[str, Any]:
    root = args.root.resolve()
    status = service_identity_registry_status()
    event_data = build_event_data(status)
    event_written = False
    event_id = ""
    if args.write_event:
        event = EventBus(project_root=str(root)).publish(
            EventType.PIPELINE_STAGE_END,
            "service-identity-status",
            event_data,
            priority=5,
        )
        event_written = True
        event_id = event.event_id
    ready = event_written and event_data["services_total"] > 0
    return {
        "schema": SCHEMA,
        "decision": (
            "LOCAL_SERVICE_IDENTITY_STATUS_EVENTBUS_EVIDENCE_READY"
            if ready
            else "LOCAL_SERVICE_IDENTITY_STATUS_EVENT_NOT_READY"
        ),
        "event_written": event_written,
        "event_id": event_id,
        "event_log": str(root / EventBus.EVENT_LOG),
        "ready_for_proof_gate": ready,
        "services_total": event_data["services_total"],
        "services_with_any_identity": event_data["services_with_any_identity"],
        "services_complete": event_data["services_complete"],
        "raw_identity_values_redacted": True,
        "claim_boundary": CLAIM_BOUNDARY,
        "proof_gate_command": [
            "python3",
            "scripts/ops/run_cross_plane_proof_gate.py",
            "--claim",
            "local_service_identity_status",
            "--json",
        ],
    }


def main(argv: list[str] | None = None) -> int:
    args = parse_args(argv)
    report = collect(args)
    if args.json:
        print(json.dumps(report, indent=2, sort_keys=True))
    else:
        print(report["decision"])
    return 0 if report.get("ready_for_proof_gate") else 1


if __name__ == "__main__":
    raise SystemExit(main())
