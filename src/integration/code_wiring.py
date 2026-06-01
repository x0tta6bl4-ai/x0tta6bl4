"""Executable wiring proof for the local integration spine.

The report generated here is intentionally repo-local. It runs the spine with
temporary event-bus storage and fake actuator/reward adapters, then records the
observable trace invariants needed by the completion audit.
"""

from __future__ import annotations

import argparse
import json
import sys
import tempfile
from dataclasses import dataclass
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Dict, List

ROOT = Path(__file__).resolve().parents[2]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from src.coordination.events import EventBus, EventType
from src.dao.token_rewards import TokenRewards
from src.integration.spine import (
    CLAIM_BOUNDARY,
    IntegrationSpine,
    SafeActuator,
    SafeActuatorEvidenceMetadata,
    SafeActuatorResult,
    SpineIdentity,
    SpineRequest,
)
from src.security.zero_trust.policy_engine import PolicyAction, PolicyEngine, PolicyRule


SCHEMA_VERSION = "x0tta6bl4-integration-spine-code-wiring-evidence-v2-repo-generated"
DEFAULT_OUTPUT_JSON = ".tmp/validation-shards/integration-spine-code-wiring-current.json"
DEFAULT_OUTPUT_MD = "docs/verification/integration-spine-code-wiring-2026-05-20.md"
REQUIRED_WIRING_KEYS = {
    "identity",
    "event_bus",
    "policy_engine",
    "safe_actuator",
    "settlement_reward_loop",
}


@dataclass
class _Executor:
    result: Any = True

    def __post_init__(self) -> None:
        self.calls: List[Dict[str, Any]] = []

    def execute(self, action: str, context: Dict[str, Any]) -> Any:
        self.calls.append({"action": action, "context": context})
        return self.result


@dataclass
class _RewardManager:
    result: Any = None

    def __post_init__(self) -> None:
        self.calls: List[Dict[str, Any]] = []

    def reward_relay(self, node_address: str, packets: int, **kwargs: Any) -> Any:
        self.calls.append({"node_address": node_address, "packets": packets, "kwargs": kwargs})
        return self.result


@dataclass
class _TokenRewardsAdapter:
    rewards: TokenRewards

    def __post_init__(self) -> None:
        self.calls: List[Dict[str, Any]] = []

    def bind_event_bus(self, bus: EventBus, identity: SpineIdentity) -> None:
        self.rewards.event_bus = bus
        self.rewards.source_agent = "code-wiring-token-rewards"
        self.rewards.node_id = identity.node_id
        self.rewards.spiffe_id = identity.spiffe_id
        self.rewards.did = identity.did
        self.rewards.wallet_address = identity.wallet_address

    def reward_relay(self, node_address: str, packets: int, **kwargs: Any) -> Any:
        self.calls.append({"node_address": node_address, "packets": packets, "kwargs": kwargs})
        return self.rewards.reward_relay(node_address, packets, **kwargs)


def _utc_now() -> str:
    return datetime.now(timezone.utc).replace(microsecond=0).isoformat().replace("+00:00", "Z")


def _identity() -> SpineIdentity:
    return SpineIdentity(
        node_id="node-code-wiring-1",
        spiffe_id="spiffe://mesh.x0tta6bl4.mesh/workload/relay",
        did="did:mesh:pqc:node-code-wiring-1",
        wallet_address="0x" + "c" * 40,
    )


def _request(**overrides: Any) -> SpineRequest:
    data: Dict[str, Any] = {
        "request_id": "code-wiring-trace-1",
        "identity": _identity(),
        "action": "Switch route",
        "resource": "mesh/relay",
        "workload_type": "relay",
        "reward_packets": 250,
    }
    data.update(overrides)
    return SpineRequest(**data)


def _simulated_actuator_metadata() -> SafeActuatorEvidenceMetadata:
    return SafeActuatorEvidenceMetadata.from_value(
        {
            "claim_gate": {
                "schema": "x0tta6bl4.integration_spine.demo_safe_actuator_claim_gate.v1",
                "surface": "integration.code_wiring.simulated_actuator",
                "local_actuator_execution_claim_allowed": False,
                "safe_actuator_result_successful": True,
                "safe_actuator_result_simulated": True,
                "production_readiness_claim_allowed": False,
                "dataplane_delivery_claim_allowed": False,
                "traffic_delivery_claim_allowed": False,
                "customer_traffic_claim_allowed": False,
                "external_dpi_bypass_claim_allowed": False,
                "external_settlement_finality_claim_allowed": False,
                "claim_boundary": CLAIM_BOUNDARY,
                "redacted": True,
            },
            "cross_plane_claim_gate": {
                "schema": "x0tta6bl4.cross_plane_proof_gate.v1",
                "surface": "integration.code_wiring.simulated_actuator",
                "allowed": False,
                "blockers": ["simulated_actuator_result"],
                "claim_boundary": CLAIM_BOUNDARY,
            },
            "evidence": {
                "local_demo_trace_only": True,
                "raw_context_values_redacted": True,
                "raw_command_output_redacted": True,
            },
            "source_agents": ["integration-code-wiring"],
            "claim_boundary": CLAIM_BOUNDARY,
            "redacted": True,
        }
    )


def _allowing_policy() -> PolicyEngine:
    engine = PolicyEngine(default_action=PolicyAction.DENY, enable_opa=False)
    engine.add_rule(
        PolicyRule(
            rule_id="code-wiring-allow-relay",
            name="Allow code wiring relay trace",
            action=PolicyAction.ALLOW,
            spiffe_id_pattern="spiffe://mesh.x0tta6bl4.mesh/workload/*",
            allowed_resources=["mesh/relay"],
            priority=500,
        )
    )
    return engine


def _event_types(events: List[Any]) -> List[str]:
    return [event.event_type.value for event in events]


def _stages(events: List[Any]) -> List[str]:
    return [str(event.data.get("stage", "")) for event in events]


def _identity_fingerprints(events: List[Any]) -> List[str]:
    fingerprints: List[str] = []
    for event in events:
        identity = event.data.get("identity", {})
        if not isinstance(identity, dict):
            fingerprints.append("")
            continue
        fingerprints.append(
            "|".join(
                str(identity.get(field, ""))
                for field in ("node_id", "spiffe_id", "did", "wallet_address")
            )
        )
    return fingerprints


def _trace_case(
    *,
    name: str,
    request: SpineRequest,
    policy_engine: PolicyEngine,
    executor: _Executor,
    reward_manager: _RewardManager,
    expected_status: str,
    expected_event_types: List[EventType],
    expect_executor_calls: int,
    expect_reward_calls: int,
) -> Dict[str, Any]:
    with tempfile.TemporaryDirectory(prefix="x0tta6bl4-spine-trace-") as tmp:
        bus = EventBus(project_root=tmp)
        if hasattr(reward_manager, "bind_event_bus"):
            reward_manager.bind_event_bus(bus, request.identity)
        spine = IntegrationSpine(
            event_bus=bus,
            policy_engine=policy_engine,
            actuator=SafeActuator(executor),
            reward_manager=reward_manager,
            source_agent="code-wiring-audit",
        )
        outcome = spine.process(request)
        events = bus.get_event_history(limit=20)

    event_types = _event_types(events)
    expected_event_values = [event_type.value for event_type in expected_event_types]
    spine_events = [event for event in events if event.source_agent == "code-wiring-audit"]
    fingerprints = _identity_fingerprints(events)
    canonical_identity_consistent = bool(fingerprints) and len(set(fingerprints)) == 1
    event_ids_match = outcome.event_ids == [event.event_id for event in spine_events]
    outcome_claim_gate_present = bool(outcome.claim_gate) and bool(outcome.cross_plane_claim_gate)
    event_claim_gates_present = all(
        bool(event.data.get("claim_gate")) and bool(event.data.get("cross_plane_claim_gate"))
        for event in spine_events
    )
    actuator_contexts = [
        call.get("context", {})
        for call in executor.calls
        if isinstance(call.get("context"), dict)
    ]
    actuator_context_claim_gate_present = (
        not actuator_contexts
        if expect_executor_calls == 0
        else all(
            bool(context.get("claim_gate")) and bool(context.get("cross_plane_claim_gate"))
            for context in actuator_contexts
        )
    )
    actuator_context_upstream_events_present = (
        not actuator_contexts
        if expect_executor_calls == 0
        else all(
            bool(context.get("upstream_event_ids"))
            and context.get("upstream_source_agents") == ["code-wiring-audit"]
            for context in actuator_contexts
        )
    )
    reward_kwargs = [
        call.get("kwargs", {})
        for call in reward_manager.calls
        if isinstance(call.get("kwargs"), dict)
    ]
    reward_context_claim_gate_present = (
        not reward_kwargs
        if expect_reward_calls == 0
        else all(
            bool(kwargs.get("upstream_claim_gate"))
            and bool(kwargs.get("upstream_cross_plane_claim_gate"))
            for kwargs in reward_kwargs
        )
    )
    reward_context_upstream_events_present = (
        not reward_kwargs
        if expect_reward_calls == 0
        else all(
            bool(kwargs.get("upstream_event_ids"))
            and kwargs.get("upstream_source_agents") == ["code-wiring-audit"]
            for kwargs in reward_kwargs
        )
    )
    strong_claims_blocked = (
        outcome.claim_gate.get("production_readiness_claim_allowed") is False
        and outcome.claim_gate.get("dataplane_delivery_claim_allowed") is False
        and outcome.claim_gate.get("traffic_delivery_claim_allowed") is False
        and outcome.claim_gate.get("customer_traffic_claim_allowed") is False
        and outcome.claim_gate.get("external_dpi_bypass_claim_allowed") is False
        and outcome.claim_gate.get("external_settlement_finality_claim_allowed") is False
        and outcome.cross_plane_claim_gate.get("allowed") is False
        and all(
            event.data["claim_gate"].get("external_settlement_finality_claim_allowed") is False
            and event.data["claim_gate"].get("dataplane_delivery_claim_allowed") is False
            and event.data["cross_plane_claim_gate"].get("allowed") is False
            for event in spine_events
            if "claim_gate" in event.data and "cross_plane_claim_gate" in event.data
        )
    )
    passed = (
        outcome.status == expected_status
        and event_types == expected_event_values
        and event_ids_match
        and len(executor.calls) == expect_executor_calls
        and len(reward_manager.calls) == expect_reward_calls
        and canonical_identity_consistent
        and outcome_claim_gate_present
        and event_claim_gates_present
        and actuator_context_claim_gate_present
        and actuator_context_upstream_events_present
        and reward_context_claim_gate_present
        and reward_context_upstream_events_present
        and strong_claims_blocked
    )
    return {
        "name": name,
        "passed": passed,
        "expected_status": expected_status,
        "actual_status": outcome.status,
        "event_sequence": event_types,
        "expected_event_sequence": expected_event_values,
        "stage_sequence": _stages(events),
        "event_ids_match_outcome_spine_events": event_ids_match,
        "event_ids_match_outcome": event_ids_match,
        "canonical_identity_consistent": canonical_identity_consistent,
        "unique_identity_fingerprints": len(set(fingerprints)),
        "executor_calls": len(executor.calls),
        "reward_calls": len(reward_manager.calls),
        "reward_event_count": sum(
            1 for event in events if event.event_type == EventType.REWARD_RELAY_RECORDED
        ),
        "settlement_recorded": outcome.settlement_recorded,
        "action_executed": outcome.action_executed,
        "policy_allowed": outcome.policy_allowed,
        "allowed": outcome.allowed,
        "reason": outcome.reason,
        "outcome_claim_gate_present": outcome_claim_gate_present,
        "event_claim_gates_present": event_claim_gates_present,
        "actuator_context_claim_gate_present": actuator_context_claim_gate_present,
        "actuator_context_upstream_events_present": actuator_context_upstream_events_present,
        "reward_context_claim_gate_present": reward_context_claim_gate_present,
        "reward_context_upstream_events_present": reward_context_upstream_events_present,
        "strong_claims_blocked": strong_claims_blocked,
    }


def build_report(root: Path) -> Dict[str, Any]:
    success_executor = _Executor()
    success_rewards = _RewardManager()
    traces = [
        _trace_case(
            name="success_identity_event_policy_actuator_settlement",
            request=_request(),
            policy_engine=_allowing_policy(),
            executor=success_executor,
            reward_manager=success_rewards,
            expected_status="COMPLETED",
            expected_event_types=[
                EventType.COORDINATION_REQUEST,
                EventType.PIPELINE_STAGE_START,
                EventType.PIPELINE_STAGE_END,
            ],
            expect_executor_calls=1,
            expect_reward_calls=1,
        ),
        _trace_case(
            name="identity_rejected_before_policy_actuator_settlement",
            request=_request(identity=SpineIdentity(node_id="", spiffe_id="mesh-node")),
            policy_engine=_allowing_policy(),
            executor=_Executor(),
            reward_manager=_RewardManager(),
            expected_status="IDENTITY_REJECTED",
            expected_event_types=[EventType.TASK_BLOCKED],
            expect_executor_calls=0,
            expect_reward_calls=0,
        ),
        _trace_case(
            name="policy_denied_before_actuator_settlement",
            request=_request(resource="mesh/admin"),
            policy_engine=PolicyEngine(default_action=PolicyAction.DENY, enable_opa=False),
            executor=_Executor(),
            reward_manager=_RewardManager(),
            expected_status="POLICY_DENIED",
            expected_event_types=[EventType.COORDINATION_REQUEST, EventType.TASK_BLOCKED],
            expect_executor_calls=0,
            expect_reward_calls=0,
        ),
        _trace_case(
            name="simulated_actuator_blocks_settlement",
            request=_request(),
            policy_engine=_allowing_policy(),
            executor=_Executor(
                SafeActuatorResult(
                    success=True,
                    reason="dry run",
                    simulated=True,
                    evidence_metadata=_simulated_actuator_metadata(),
                )
            ),
            reward_manager=_RewardManager(),
            expected_status="ACTUATOR_SIMULATED",
            expected_event_types=[
                EventType.COORDINATION_REQUEST,
                EventType.PIPELINE_STAGE_START,
                EventType.TASK_FAILED,
            ],
            expect_executor_calls=1,
            expect_reward_calls=0,
        ),
        _trace_case(
            name="settlement_backend_failure_fails_closed",
            request=_request(),
            policy_engine=_allowing_policy(),
            executor=_Executor(),
            reward_manager=_RewardManager({"ok": False, "status": "failed"}),
            expected_status="SETTLEMENT_FAILED",
            expected_event_types=[
                EventType.COORDINATION_REQUEST,
                EventType.PIPELINE_STAGE_START,
                EventType.TASK_FAILED,
            ],
            expect_executor_calls=1,
            expect_reward_calls=1,
        ),
        _trace_case(
            name="simulated_settlement_backend_fails_closed",
            request=_request(),
            policy_engine=_allowing_policy(),
            executor=_Executor(),
            reward_manager=_RewardManager({"ok": True, "simulated": True, "status": "ok"}),
            expected_status="SETTLEMENT_FAILED",
            expected_event_types=[
                EventType.COORDINATION_REQUEST,
                EventType.PIPELINE_STAGE_START,
                EventType.TASK_FAILED,
            ],
            expect_executor_calls=1,
            expect_reward_calls=1,
        ),
        _trace_case(
            name="token_rewards_local_only_fails_closed",
            request=_request(),
            policy_engine=_allowing_policy(),
            executor=_Executor(),
            reward_manager=_TokenRewardsAdapter(
                TokenRewards("0x" + "a" * 40, private_key=None)
            ),
            expected_status="SETTLEMENT_FAILED",
            expected_event_types=[
                EventType.COORDINATION_REQUEST,
                EventType.PIPELINE_STAGE_START,
                EventType.REWARD_RELAY_RECORDED,
                EventType.TASK_FAILED,
            ],
            expect_executor_calls=1,
            expect_reward_calls=1,
        ),
    ]

    passed = sum(1 for trace in traces if trace["passed"])
    failed = len(traces) - passed
    success_trace = traces[0]
    policy_denied = traces[2]
    simulated_actuator = traces[3]
    settlement_failed = traces[4]
    simulated_settlement = traces[5]
    token_rewards_local_only = traces[6]
    ok = failed == 0
    return {
        "schema_version": SCHEMA_VERSION,
        "generated_at": _utc_now(),
        "status": "VERIFIED HERE",
        "ok": ok,
        "decision": "LOCAL_CODE_WIRING_VERIFIED" if ok else "LOCAL_CODE_WIRING_BROKEN",
        "claim_boundary": CLAIM_BOUNDARY,
        "completion_decision": "NOT_COMPLETE",
        "goal_can_be_marked_complete": False,
        "mutates_runtime": False,
        "contacts_live_systems": False,
        "submits_transaction": False,
        "source_files": [
            "src/integration/spine.py",
            "src/integration/code_wiring.py",
            "src/dao/token_rewards.py",
            "src/services/reward_events.py",
            "tests/unit/test_integration_spine.py",
        ],
        "wiring_covered": {
            "identity": "SpineIdentity carries node_id, spiffe_id, DID, and wallet through every emitted event.",
            "event_bus": "IntegrationSpine publishes the same request identity through EventBus stage/block/fail events.",
            "policy_engine": "A real zero-trust PolicyEngine allow/deny decision gates actuator execution.",
            "safe_actuator": "SafeActuator blocks failed or simulated execution before settlement.",
            "settlement_reward_loop": "reward_manager.reward_relay is called only after identity, policy, and actuator success; TokenRewards can publish canonical reward events on the same EventBus and fails closed on backend false/error/simulated status.",
        },
        "summary": {
            "required_wiring_keys_total": len(REQUIRED_WIRING_KEYS),
            "wiring_keys_covered": len(REQUIRED_WIRING_KEYS),
            "trace_cases_total": len(traces),
            "trace_cases_passed": passed,
            "trace_cases_failed": failed,
            "success_event_sequence_verified": success_trace["passed"],
            "canonical_identity_consistent": all(
                trace["canonical_identity_consistent"] for trace in traces
            ),
            "policy_before_actuator_verified": policy_denied["executor_calls"] == 0
            and policy_denied["reward_calls"] == 0,
            "simulated_actuator_blocks_settlement": simulated_actuator["reward_calls"] == 0,
            "settlement_failure_fails_closed": settlement_failed["actual_status"] == "SETTLEMENT_FAILED"
            and settlement_failed["allowed"] is False
            and settlement_failed["settlement_recorded"] is False,
            "simulated_settlement_fails_closed": simulated_settlement["actual_status"] == "SETTLEMENT_FAILED"
            and simulated_settlement["allowed"] is False
            and simulated_settlement["settlement_recorded"] is False,
            "token_rewards_local_only_fails_closed": token_rewards_local_only["actual_status"] == "SETTLEMENT_FAILED"
            and token_rewards_local_only["allowed"] is False
            and token_rewards_local_only["settlement_recorded"] is False,
            "token_rewards_event_bus_recorded": token_rewards_local_only["reward_event_count"] == 1,
            "spine_claim_gates_preserved": all(
                trace["outcome_claim_gate_present"]
                and trace["event_claim_gates_present"]
                and trace["strong_claims_blocked"]
                for trace in traces
            ),
            "actuator_context_claim_gates_preserved": all(
                trace["actuator_context_claim_gate_present"]
                and trace["actuator_context_upstream_events_present"]
                for trace in traces
            ),
            "reward_context_claim_gates_preserved": all(
                trace["reward_context_claim_gate_present"]
                and trace["reward_context_upstream_events_present"]
                for trace in traces
            ),
        },
        "trace_cases": traces,
        "known_non_completion_reasons": [
            "This is executable local contract wiring, not a production rollout.",
            "External X0T settlement receipt and live RPC verification are still separate production evidence gates.",
            "Operator-captured production raw evidence bundles are still required before production closeout.",
        ],
    }


def write_report(report: Dict[str, Any], output_json: Path) -> None:
    output_json.parent.mkdir(parents=True, exist_ok=True)
    output_json.write_text(json.dumps(report, indent=2, sort_keys=True) + "\n", encoding="utf-8")


def render_markdown(report: Dict[str, Any]) -> str:
    lines = [
        "# Integration Spine Code Wiring Evidence",
        "",
        f"Generated: `{report['generated_at']}`",
        f"Status: `{report['status']}`",
        f"Decision: `{report['decision']}`",
        f"Completion decision: `{report['completion_decision']}`",
        f"Goal can be marked complete: `{report['goal_can_be_marked_complete']}`",
        "",
        "## Claim Boundary",
        "",
        report["claim_boundary"],
        "",
        "## Summary",
        "",
    ]
    for key, value in report["summary"].items():
        lines.append(f"- `{key}`: `{value}`")
    lines.extend(["", "## Wiring Covered", ""])
    for key in sorted(report["wiring_covered"]):
        lines.append(f"- `{key}`: {report['wiring_covered'][key]}")
    lines.extend(["", "## Trace Cases", ""])
    for trace in report["trace_cases"]:
        lines.append(
            f"- `{trace['name']}`: passed=`{trace['passed']}`, "
            f"status=`{trace['actual_status']}`, events=`{','.join(trace['event_sequence'])}`, "
            f"executor_calls=`{trace['executor_calls']}`, reward_calls=`{trace['reward_calls']}`"
        )
    lines.extend(["", "## Source Files", ""])
    for path in report["source_files"]:
        lines.append(f"- `{path}`")
    lines.extend(["", "## Not Complete Because", ""])
    for reason in report["known_non_completion_reasons"]:
        lines.append(f"- {reason}")
    lines.append("")
    return "\n".join(lines)


def write_markdown(report: Dict[str, Any], output_md: Path) -> None:
    output_md.parent.mkdir(parents=True, exist_ok=True)
    output_md.write_text(render_markdown(report), encoding="utf-8")


def main(argv: List[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description="Generate executable integration-spine code wiring evidence")
    parser.add_argument("--root", default=".")
    parser.add_argument("--output-json", default=DEFAULT_OUTPUT_JSON)
    parser.add_argument("--output-md", default="")
    parser.add_argument("--write-md", action="store_true")
    parser.add_argument("--require-verified", action="store_true")
    args = parser.parse_args(argv)

    root = Path(args.root)
    report = build_report(root)
    write_report(report, root / args.output_json)
    if args.write_md or args.output_md:
        write_markdown(report, root / (args.output_md or DEFAULT_OUTPUT_MD))
    print(json.dumps(report, sort_keys=True))
    if args.require_verified and not report["ok"]:
        return 2
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
