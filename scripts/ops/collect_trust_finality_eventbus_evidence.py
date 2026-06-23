#!/usr/bin/env python3
"""Collect bounded redacted trust-finality EventBus evidence.

This collector intentionally does not inspect raw SPIFFE IDs, DID documents,
wallet addresses, chain payloads, or private keys. It accepts a local redacted
proof JSON, validates the proof shape, and writes only sanitized EventBus
metadata. It cannot prove dataplane delivery, customer traffic, settlement, or
production readiness.
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
from src.mesh.trust_finality_contracts import (
    TRUST_FINALITY_CLAIM_BOUNDARY,
    TRUST_FINALITY_INPUT_SCHEMA,
    TRUST_FINALITY_SOURCE_AGENTS,
    TrustFinalityLocalEvidenceInput,
    build_trust_finality_event_data,
    trust_finality_input_blockers,
)


SCHEMA = "x0tta6bl4.trust_finality_eventbus_evidence_collector.v1"
DEFAULT_SOURCE_AGENT = "spiffe-workload-api"


def parse_args(argv: list[str] | None = None) -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description="Collect bounded redacted trust-finality EventBus evidence."
    )
    parser.add_argument("--root", type=Path, default=Path("."))
    parser.add_argument("--proof-json", type=Path)
    parser.add_argument(
        "--source-agent",
        default=DEFAULT_SOURCE_AGENT,
        choices=TRUST_FINALITY_SOURCE_AGENTS,
    )
    parser.add_argument(
        "--allow-redacted-local-proof-intake",
        action="store_true",
        help="Required before the collector reads a local redacted proof JSON.",
    )
    parser.add_argument(
        "--write-event",
        action="store_true",
        help="Append sanitized trust evidence to .agent_coordination/events.log.",
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
        "schema": TRUST_FINALITY_INPUT_SCHEMA,
        "status": "VERIFIED",
        "observed_evidence": {
            "live_spiffe_svid_confirmed": False,
            "did_ownership_confirmed": False,
            "wallet_control_confirmed": False,
            "chain_identity_finality_confirmed": False,
        },
        "source_artifacts": [
            {
                "role": "redacted_local_trust_probe_report",
                "sha256": "<64 lowercase hex sha256>",
                "redacted": True,
            }
        ],
        "raw_identity_values_redacted": True,
        "payloads_redacted": True,
        "claim_boundary": TRUST_FINALITY_CLAIM_BOUNDARY,
    }


def _read_json(path: Path) -> tuple[dict[str, Any] | None, list[str]]:
    try:
        raw = path.read_text(encoding="utf-8")
    except OSError:
        return None, ["trust_finality_input_file_unreadable"]
    try:
        payload = json.loads(raw)
    except json.JSONDecodeError:
        return None, ["trust_finality_input_json_invalid"]
    if not isinstance(payload, dict):
        return None, ["trust_finality_input_json_not_object"]
    return payload, []


def _parse_proof(path: Path) -> tuple[TrustFinalityLocalEvidenceInput | None, list[str]]:
    payload, blockers = _read_json(path)
    if payload is None:
        return None, blockers
    try:
        proof = TrustFinalityLocalEvidenceInput.model_validate(payload)
    except ValidationError:
        return None, ["trust_finality_input_schema_validation_failed"]
    return proof, trust_finality_input_blockers(proof)


def collect(args: argparse.Namespace) -> dict[str, Any]:
    root = args.root.resolve()
    if args.print_template:
        return {
            "schema": SCHEMA,
            "decision": "TRUST_FINALITY_TEMPLATE",
            "event_written": False,
            "ready_for_proof_gate": False,
            "template": proof_template(),
            "claim_boundary": TRUST_FINALITY_CLAIM_BOUNDARY,
        }

    if not args.allow_redacted_local_proof_intake:
        return {
            "schema": SCHEMA,
            "decision": "BLOCKED_PROOF_INTAKE_NOT_AUTHORIZED",
            "event_written": False,
            "ready_for_proof_gate": False,
            "claim_boundary": TRUST_FINALITY_CLAIM_BOUNDARY,
            "blockers": ["allow_redacted_local_proof_intake_required"],
        }

    if args.proof_json is None:
        return {
            "schema": SCHEMA,
            "decision": "BLOCKED_PROOF_JSON_MISSING",
            "event_written": False,
            "ready_for_proof_gate": False,
            "claim_boundary": TRUST_FINALITY_CLAIM_BOUNDARY,
            "blockers": ["proof_json_required"],
        }

    proof, blockers = _parse_proof(args.proof_json)
    if proof is None:
        return {
            "schema": SCHEMA,
            "decision": "BLOCKED_INVALID_PROOF_JSON",
            "event_written": False,
            "ready_for_proof_gate": False,
            "claim_boundary": TRUST_FINALITY_CLAIM_BOUNDARY,
            "blockers": blockers,
        }

    event_data = build_trust_finality_event_data(
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
            "TRUST_FINALITY_EVENTBUS_EVIDENCE_READY"
            if ready
            else "TRUST_FINALITY_PROOF_NOT_READY"
        ),
        "event_written": event_written,
        "event_id": event_id,
        "event_log": str(root / EventBus.EVENT_LOG),
        "ready_for_proof_gate": ready,
        "blockers": blockers,
        "claim_boundary": TRUST_FINALITY_CLAIM_BOUNDARY,
        "proof_gate_command": [
            "python3",
            "scripts/ops/run_cross_plane_proof_gate.py",
            "--claim",
            "trust_finality",
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
