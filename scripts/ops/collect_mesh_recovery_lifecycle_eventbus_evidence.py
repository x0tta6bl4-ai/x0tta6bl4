#!/usr/bin/env python3
"""Collect bounded mesh recovery lifecycle EventBus evidence.

This collector runs the real MeshRecoveryOrchestrator with local simulated node
state and a no-op restart action. It proves only the safe-automation evidence
contract: policy decision, observed state, return code, duration, redaction, and
safe-mode/escalation behavior. It does not mutate live mesh state or prove
dataplane delivery/customer traffic.
"""

from __future__ import annotations

import argparse
import json
import sys
import uuid
from pathlib import Path
from typing import Any

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT))

from src.coordination.events import EventBus
from src.mesh.recovery_contracts import NodeState
from src.mesh.recovery_orchestrator import (
    MESH_RECOVERY_SOURCE_AGENT,
    MeshRecoveryOrchestrator,
)
from src.mesh.recovery_policy import RecoveryPolicyManager


SCHEMA = "x0tta6bl4.mesh_recovery_lifecycle_eventbus_evidence_collector.v1"
CLAIM_BOUNDARY = (
    "Bounded local mesh recovery lifecycle smoke evidence only. This proves the "
    "safe-automation evidence contract for observed state, policy, return code, "
    "duration, redaction, and safe-mode/escalation boundaries. It does not prove "
    "live mesh healing, dataplane delivery, customer traffic, trust finality, "
    "settlement finality, production SLOs, or production readiness."
)


class FakeClock:
    def __init__(self) -> None:
        self.now = 1000.0

    def __call__(self) -> float:
        return self.now

    def advance(self, seconds: float) -> None:
        self.now += max(0.0, float(seconds))


def parse_args(argv: list[str] | None = None) -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description="Collect bounded mesh recovery lifecycle EventBus evidence."
    )
    parser.add_argument("--root", type=Path, default=Path("."))
    parser.add_argument("--source-agent", default=MESH_RECOVERY_SOURCE_AGENT)
    parser.add_argument("--incident-id", default="local-mesh-recovery-smoke")
    parser.add_argument("--incident-key", default="local-mesh-recovery-smoke")
    parser.add_argument(
        "--node-id",
        default="local-mesh-recovery-smoke-node",
        help="Local node id used only to produce a redacted HMAC hash.",
    )
    parser.add_argument(
        "--simulate-action-failure",
        action="store_true",
        help="Exercise the fail-closed evidence path without mutating live state.",
    )
    parser.add_argument(
        "--allow-local-simulation",
        action="store_true",
        help="Required before running the local no-op recovery lifecycle smoke.",
    )
    parser.add_argument(
        "--write-event",
        action="store_true",
        help="Append the bounded lifecycle event to .agent_coordination/events.log.",
    )
    parser.add_argument("--json", action="store_true")
    return parser.parse_args(argv)


def degraded_state() -> NodeState:
    return NodeState(
        local_health="Degraded",
        packet_loss_pct=18.4,
        yggdrasil_status="Peers down",
    )


def healthy_state() -> NodeState:
    return NodeState(
        local_health="OK",
        packet_loss_pct=0.1,
        yggdrasil_status="Peers visible",
    )


def collect(args: argparse.Namespace) -> dict[str, Any]:
    root = args.root.resolve()
    if not args.allow_local_simulation:
        return {
            "schema": SCHEMA,
            "decision": "BLOCKED_LOCAL_SIMULATION_NOT_AUTHORIZED",
            "event_written": False,
            "ready_for_proof_gate": False,
            "claim_boundary": CLAIM_BOUNDARY,
            "blockers": ["allow_local_simulation_required"],
        }
    if not args.write_event:
        return {
            "schema": SCHEMA,
            "decision": "BLOCKED_EVENT_WRITE_NOT_REQUESTED",
            "event_written": False,
            "ready_for_proof_gate": False,
            "claim_boundary": CLAIM_BOUNDARY,
            "blockers": ["write_event_required"],
        }

    clock = FakeClock()
    states = [degraded_state(), degraded_state()]
    if not args.simulate_action_failure:
        states = [degraded_state(), healthy_state()]

    def get_node_state() -> NodeState:
        if states:
            return states.pop(0)
        return healthy_state()

    def restart_action() -> int:
        if args.simulate_action_failure:
            raise RuntimeError("simulated_local_restart_failure")
        return 0

    event_bus = EventBus(project_root=str(root))
    orchestrator = MeshRecoveryOrchestrator(
        node_id=args.node_id,
        local_audit_secret=f"local-mesh-recovery-smoke-{uuid.uuid4()}",
        policy_manager=RecoveryPolicyManager(cooldown_seconds=600, clock=clock),
        restart_action=restart_action,
        get_node_state=get_node_state,
        event_bus=event_bus,
        source_agent=args.source_agent,
        post_action_wait_seconds=0.0,
        sleeper=lambda seconds: clock.advance(seconds),
        clock=clock,
    )
    evidence = orchestrator.run_recovery_flow(
        incident_id=args.incident_id,
        incident_key=args.incident_key,
    )
    events = event_bus.get_event_history(source_agent=args.source_agent)
    event = events[-1] if events else None
    event_id = event.event_id if event is not None else ""
    ready = event is not None
    return {
        "schema": SCHEMA,
        "decision": (
            "MESH_RECOVERY_LIFECYCLE_EVENTBUS_EVIDENCE_READY"
            if ready
            else "MESH_RECOVERY_LIFECYCLE_EVENTBUS_EVIDENCE_MISSING"
        ),
        "event_written": ready,
        "event_id": event_id,
        "event_log": str(root / EventBus.EVENT_LOG),
        "ready_for_proof_gate": ready,
        "action": evidence.action,
        "return_code": evidence.return_code,
        "action_error": evidence.action_error,
        "escalation_required": evidence.escalation_required,
        "post_action_safe_mode_required": evidence.post_action_safe_mode_required,
        "raw_values_redacted": evidence.raw_values_redacted,
        "claim_boundary": CLAIM_BOUNDARY,
        "proof_gate_command": [
            "python3",
            "scripts/ops/run_cross_plane_proof_gate.py",
            "--claim",
            "mesh_recovery_lifecycle",
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
    return 0 if report.get("ready_for_proof_gate") is True else 1


if __name__ == "__main__":
    raise SystemExit(main())
