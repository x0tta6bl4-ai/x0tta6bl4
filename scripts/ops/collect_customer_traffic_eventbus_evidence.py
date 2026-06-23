#!/usr/bin/env python3
"""Collect bounded redacted end-to-end customer traffic EventBus evidence.

This collector is intentionally an intake validator. It does not infer customer
traffic from local TCP probes, mesh peer visibility, billing events, or recovery
events. Operators feed it a redacted local proof JSON produced by an authorized
end-to-end customer-path probe, and it writes only sanitized EventBus metadata.
"""

from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path
from typing import Any

from pydantic import ValidationError

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT))

from src.coordination.events import EventBus, EventType
from src.mesh.customer_traffic_contracts import (
    CUSTOMER_TRAFFIC_CLAIM_BOUNDARY,
    CUSTOMER_TRAFFIC_INPUT_SCHEMA,
    CUSTOMER_TRAFFIC_SOURCE_AGENTS,
    CustomerTrafficLocalEvidenceInput,
    build_customer_traffic_event_data,
    customer_traffic_input_blockers,
)


SCHEMA = "x0tta6bl4.customer_traffic_eventbus_evidence_collector.v1"
DEFAULT_SOURCE_AGENT = "customer-traffic-probe"


def parse_args(argv: list[str] | None = None) -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description="Collect bounded redacted customer-traffic EventBus evidence."
    )
    parser.add_argument("--root", type=Path, default=Path("."))
    parser.add_argument("--proof-json", type=Path)
    parser.add_argument(
        "--source-agent",
        default=DEFAULT_SOURCE_AGENT,
        choices=CUSTOMER_TRAFFIC_SOURCE_AGENTS,
    )
    parser.add_argument(
        "--allow-redacted-local-proof-intake",
        action="store_true",
        help="Required before the collector reads a local redacted proof JSON.",
    )
    parser.add_argument(
        "--write-event",
        action="store_true",
        help="Append sanitized customer traffic evidence to EventBus.",
    )
    parser.add_argument(
        "--print-template",
        action="store_true",
        help="Print a redacted proof JSON template and do not write an event.",
    )
    parser.add_argument("--json", action="store_true")
    return parser.parse_args(argv)


def proof_template() -> dict[str, Any]:
    return {
        "schema": CUSTOMER_TRAFFIC_INPUT_SCHEMA,
        "status": "VERIFIED",
        "observed_evidence": {
            "environment": "production",
            "end_to_end_customer_path_confirmed": False,
            "customer_request_observed": False,
            "customer_response_validated": False,
            "customer_payloads_redacted": True,
        },
        "source_artifacts": [
            {
                "role": "redacted_end_to_end_customer_path_probe_report",
                "sha256": "<64 lowercase hex sha256>",
                "redacted": True,
            }
        ],
        "raw_identifiers_redacted": True,
        "raw_values_redacted": True,
        "payloads_redacted": True,
        "authorization_scope_redacted": True,
        "claim_boundary": CUSTOMER_TRAFFIC_CLAIM_BOUNDARY,
    }


def _read_json(path: Path) -> tuple[dict[str, Any] | None, list[str]]:
    try:
        raw = path.read_text(encoding="utf-8")
    except OSError:
        return None, ["customer_traffic_input_file_unreadable"]
    try:
        payload = json.loads(raw)
    except json.JSONDecodeError:
        return None, ["customer_traffic_input_json_invalid"]
    if not isinstance(payload, dict):
        return None, ["customer_traffic_input_json_not_object"]
    return payload, []


def _parse_proof(
    path: Path,
) -> tuple[CustomerTrafficLocalEvidenceInput | None, list[str]]:
    payload, blockers = _read_json(path)
    if payload is None:
        return None, blockers
    try:
        proof = CustomerTrafficLocalEvidenceInput.model_validate(payload)
    except ValidationError:
        return None, ["customer_traffic_input_schema_validation_failed"]
    return proof, customer_traffic_input_blockers(proof)


def collect(args: argparse.Namespace) -> dict[str, Any]:
    root = args.root.resolve()
    if args.print_template:
        return {
            "schema": SCHEMA,
            "decision": "CUSTOMER_TRAFFIC_TEMPLATE",
            "event_written": False,
            "ready_for_proof_gate": False,
            "template": proof_template(),
            "claim_boundary": CUSTOMER_TRAFFIC_CLAIM_BOUNDARY,
        }

    if not args.allow_redacted_local_proof_intake:
        return {
            "schema": SCHEMA,
            "decision": "BLOCKED_PROOF_INTAKE_NOT_AUTHORIZED",
            "event_written": False,
            "ready_for_proof_gate": False,
            "claim_boundary": CUSTOMER_TRAFFIC_CLAIM_BOUNDARY,
            "blockers": ["allow_redacted_local_proof_intake_required"],
        }

    if args.proof_json is None:
        return {
            "schema": SCHEMA,
            "decision": "BLOCKED_PROOF_JSON_MISSING",
            "event_written": False,
            "ready_for_proof_gate": False,
            "claim_boundary": CUSTOMER_TRAFFIC_CLAIM_BOUNDARY,
            "blockers": ["proof_json_required"],
        }

    proof, blockers = _parse_proof(args.proof_json)
    if proof is None:
        return {
            "schema": SCHEMA,
            "decision": "BLOCKED_INVALID_PROOF_JSON",
            "event_written": False,
            "ready_for_proof_gate": False,
            "claim_boundary": CUSTOMER_TRAFFIC_CLAIM_BOUNDARY,
            "blockers": blockers,
        }

    event_data = build_customer_traffic_event_data(
        proof,
        source_agent=args.source_agent,
        blockers=blockers,
    )
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

    ready = not blockers and event_written
    return {
        "schema": SCHEMA,
        "decision": (
            "CUSTOMER_TRAFFIC_EVENTBUS_EVIDENCE_READY"
            if ready
            else "CUSTOMER_TRAFFIC_PROOF_NOT_READY"
        ),
        "event_written": event_written,
        "event_id": event_id,
        "event_log": str(root / EventBus.EVENT_LOG),
        "ready_for_proof_gate": ready,
        "blockers": blockers,
        "claim_boundary": CUSTOMER_TRAFFIC_CLAIM_BOUNDARY,
        "proof_gate_command": [
            "python3",
            "scripts/ops/run_cross_plane_proof_gate.py",
            "--claim",
            "customer_traffic",
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
    return 0 if report.get("ready_for_proof_gate") or args.print_template else 1


if __name__ == "__main__":
    raise SystemExit(main())
