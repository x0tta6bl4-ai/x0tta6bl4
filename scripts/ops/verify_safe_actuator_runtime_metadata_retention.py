#!/usr/bin/env python3
"""Verify runtime retention of SafeActuator metadata in local smoke cases.

This is a local smoke verifier. It executes representative policy-gated SPIRE
control paths with mocked local binaries and checks that the EventBus payloads
and bounded script results retain typed, redacted SafeActuator evidence
metadata. Passing this verifier does not prove live SPIFFE/SPIRE trust,
dataplane delivery, settlement finality, customer traffic, production SLOs, or
production readiness.
"""

from __future__ import annotations

import argparse
import asyncio
import contextlib
import io
import json
import os
import sys
import tempfile
from datetime import datetime, timezone
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from pathlib import Path
from threading import Thread
from types import SimpleNamespace
from typing import Any, Iterable, Mapping, Sequence
from unittest.mock import MagicMock, patch


ROOT = Path(__file__).resolve().parents[2]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from src.coordination.events import Event, EventBus, EventType
from src.api.maas.endpoints.governance import _execute_action as execute_governance_action
from src.dao.executor_webhook import DAOExecutor
from src.dao.governance import ActionDispatcher
from src.dao.governance_contract import GovernanceContract
from src.dao.proposal_executor_webhook import ExecutorConfig, HelmRunner
from src.dao.token_bridge import BridgeConfig, TokenBridge
from src.deployment.canary_deployment import CanaryDeployment, DeploymentConfig
from src.deployment.multi_cloud_deployment import (
    CloudProvider as MultiCloudProvider,
    DeploymentConfig as MultiCloudDeploymentConfig,
    MultiCloudDeployment,
)
from src.integration.spine import (
    SafeActuator,
    SafeActuatorEvidenceMetadata,
    SafeActuatorResult,
)
from src.mesh.action_enforcer import MeshActionEnforcer
from src.mesh.metric_evidence_policy import build_mesh_metric_evidence_policy
from src.network.mptcp_manager import MPTCPManager
from src.security.spiffe.agent.manager import SPIREAgentManager
from src.security.spiffe.server.client import SPIREServerClient
from src.security.zero_trust.policy_engine import PolicyAction, PolicyEngine, PolicyRule
from src.server.ghost_server import GhostL3Server
from src.services.pqc_rotator_service import PQCRotatorService
from src.self_healing.mape_k import SelfHealingManager
from src.swarm.consensus_integration import ConsensusMode
from src.swarm.intelligence import (
    DecisionContext,
    DecisionPriority,
    DecisionResult,
    MAPEKIntegration,
    SwarmAction,
)
from src.swarm.pbft import PBFTMessage, PBFTNode, PBFTPhase
from scripts import auto_rollback as ops_auto_rollback
from scripts import canary_deployment as ops_canary_deployment
from scripts.deploy import production_deploy as ops_production_deploy
from scripts import production_monitor as ops_production_monitor


SCHEMA = "x0tta6bl4.safe_actuator_runtime_metadata_retention.v1"
DECISION_RETAINED = "SAFE_ACTUATOR_RUNTIME_METADATA_RETAINED"
DECISION_GAPS = "SAFE_ACTUATOR_RUNTIME_METADATA_GAPS"
SAFE_ACTUATOR_METADATA_SCHEMA = "x0tta6bl4.safe_actuator.evidence_metadata.v1"
CLAIM_BOUNDARY = (
    "SafeActuator runtime metadata retention verifier is a local simulated "
    "EventBus/result-metadata smoke test only. It proves representative local "
    "control paths retain typed redacted metadata at runtime; it does not prove live "
    "SPIFFE/SPIRE trust, mTLS dataplane delivery, customer traffic, settlement "
    "finality, deployment traffic shifting, production SLOs, or production readiness."
)
SPIRE_SERVER_SPIFFE_ID = "spiffe://x0tta6bl4.mesh/workload/spire-server-client"
SPIRE_AGENT_SPIFFE_ID = "spiffe://x0tta6bl4.mesh/workload/spire-agent-manager"
TOKEN_BRIDGE_SPIFFE_ID = "spiffe://x0tta6bl4.mesh/workload/token-bridge"
DAO_EXECUTOR_SPIFFE_ID = "spiffe://x0tta6bl4.mesh/workload/dao-executor"
DAO_PROPOSAL_EXECUTOR_SPIFFE_ID = (
    "spiffe://x0tta6bl4.mesh/workload/dao-proposal-executor"
)
DAO_GOVERNANCE_DISPATCHER_SPIFFE_ID = "spiffe://x0tta6bl4.mesh/workload/dao-governance"
GOVERNANCE_CONTRACT_SPIFFE_ID = (
    "spiffe://x0tta6bl4.mesh/workload/governance-contract"
)
MAAS_GOVERNANCE_SPIFFE_ID = "spiffe://x0tta6bl4.mesh/workload/maas-governance"
PQC_ROTATOR_SPIFFE_ID = "spiffe://x0tta6bl4.mesh/workload/pqc-rotator"
MPTCP_MANAGER_SPIFFE_ID = "spiffe://x0tta6bl4.mesh/workload/mptcp-manager"
SWARM_PBFT_SPIFFE_ID = "spiffe://x0tta6bl4.mesh/workload/swarm-pbft"
SWARM_MAPEK_SPIFFE_ID = "spiffe://x0tta6bl4.mesh/workload/swarm-mapek"
EBPF_SAFE_ACTUATOR_CLAIM_BOUNDARY = (
    "eBPF runtime verifier SafeActuator metadata proves only a local simulated "
    "route-weight recovery action. It does not prove restored dataplane delivery, "
    "route convergence, kernel forwarding correctness, customer traffic, "
    "settlement finality, production SLOs, or production readiness."
)
STRONG_CLAIM_KEYS = (
    "live_spire_mtls_claim_allowed",
    "workload_svid_possession_claim_allowed",
    "workload_identity_trust_finality_claim_allowed",
    "node_attestation_finality_claim_allowed",
    "external_settlement_finality_claim_allowed",
    "live_token_settlement_finality_claim_allowed",
    "dao_governance_finality_claim_allowed",
    "restored_dataplane_claim_allowed",
    "dataplane_delivery_claim_allowed",
    "traffic_delivery_claim_allowed",
    "traffic_shift_claim_allowed",
    "live_customer_traffic_confirmed",
    "live_customer_traffic_claim_allowed",
    "customer_traffic_claim_allowed",
    "external_reachability_claim_allowed",
    "kernel_forwarding_correctness_claim_allowed",
    "revenue_recognition_claim_allowed",
    "external_dpi_bypass_confirmed",
    "settlement_finality_confirmed",
    "production_governance_execution_claim_allowed",
    "production_rollout_claim_allowed",
    "production_action_applied_claim_allowed",
    "production_slo_claim_allowed",
    "production_identity_readiness_claim_allowed",
    "production_readiness_claim_allowed",
)


def utc_now() -> str:
    return (
        datetime.now(timezone.utc)
        .replace(microsecond=0)
        .isoformat()
        .replace("+00:00", "Z")
    )


def _allow_policy(spiffe_id: str, resource: str) -> PolicyEngine:
    policy = PolicyEngine(default_action=PolicyAction.DENY, enable_opa=False)
    policy.add_rule(
        PolicyRule(
            rule_id=f"allow-{resource}",
            name=f"Allow {resource}",
            action=PolicyAction.ALLOW,
            spiffe_id_pattern=spiffe_id,
            allowed_resources=[resource],
            priority=1000,
        )
    )
    return policy


def _metadata_for(payload: Mapping[str, Any]) -> Mapping[str, Any]:
    value = payload.get("safe_actuator_evidence_metadata")
    return value if isinstance(value, Mapping) else {}


def _claim_gate_for(metadata: Mapping[str, Any]) -> Mapping[str, Any]:
    value = metadata.get("claim_gate")
    return value if isinstance(value, Mapping) else {}


def _evidence_for(metadata: Mapping[str, Any]) -> Mapping[str, Any]:
    value = metadata.get("evidence")
    return value if isinstance(value, Mapping) else {}


@contextlib.contextmanager
def _local_monitor_http_target(*, error_rate: float = 0.0) -> Iterable[str]:
    class Handler(BaseHTTPRequestHandler):
        def do_GET(self) -> None:  # noqa: N802 - stdlib handler API
            if self.path == "/health":
                body = b"ok"
                self.send_response(200)
                self.send_header("Content-Type", "text/plain")
                self.send_header("Content-Length", str(len(body)))
                self.end_headers()
                self.wfile.write(body)
                return
            if self.path == "/metrics":
                body = f"production_error_rate {error_rate}\n".encode("utf-8")
                self.send_response(200)
                self.send_header("Content-Type", "text/plain")
                self.send_header("Content-Length", str(len(body)))
                self.end_headers()
                self.wfile.write(body)
                return
            self.send_error(404)

        def log_message(self, _format: str, *_args: Any) -> None:
            return

    server = ThreadingHTTPServer(("127.0.0.1", 0), Handler)
    thread = Thread(target=server.serve_forever, daemon=True)
    thread.start()
    try:
        host, port = server.server_address
        yield f"http://{host}:{port}"
    finally:
        server.shutdown()
        server.server_close()
        thread.join(timeout=2)


@contextlib.contextmanager
def _without_proxy_env_for_loopback() -> Iterable[None]:
    """Keep local loopback smoke independent from host proxy configuration."""

    proxy_keys = (
        "ALL_PROXY",
        "all_proxy",
        "HTTP_PROXY",
        "http_proxy",
        "HTTPS_PROXY",
        "https_proxy",
        "FTP_PROXY",
        "ftp_proxy",
        "NO_PROXY",
        "no_proxy",
    )
    saved = {key: os.environ.get(key) for key in proxy_keys}
    try:
        for key in proxy_keys:
            os.environ.pop(key, None)
        os.environ["NO_PROXY"] = "127.0.0.1,localhost,::1"
        os.environ["no_proxy"] = "127.0.0.1,localhost,::1"
        yield
    finally:
        for key, value in saved.items():
            if value is None:
                os.environ.pop(key, None)
            else:
                os.environ[key] = value


def validate_event_payload(
    event: Event,
    *,
    expected_source_agent: str,
    expected_resource: str,
) -> list[str]:
    """Return validation failures for one retained EventBus payload."""

    failures: list[str] = []
    payload = event.data if isinstance(event.data, Mapping) else {}
    metadata = _metadata_for(payload)
    claim_gate = _claim_gate_for(metadata)
    evidence = _evidence_for(metadata)

    if event.source_agent != expected_source_agent:
        failures.append(f"source_agent_mismatch:{event.source_agent}")
    if payload.get("resource") != expected_resource:
        failures.append(f"resource_mismatch:{payload.get('resource')}")
    if "safe_actuator" in payload and payload.get("safe_actuator") is not True:
        failures.append("safe_actuator_flag_missing")
    if metadata.get("schema") != SAFE_ACTUATOR_METADATA_SCHEMA:
        failures.append("metadata_schema_invalid")
    if metadata.get("redacted") is not True:
        failures.append("metadata_not_redacted")
    if not metadata.get("claim_boundary"):
        failures.append("metadata_claim_boundary_missing")
    if not claim_gate:
        failures.append("claim_gate_missing")
    if claim_gate.get("safe_actuator_result_recorded") is not True:
        failures.append("safe_actuator_result_not_recorded")
    if claim_gate.get("redacted") is not True:
        failures.append("claim_gate_not_redacted")
    if evidence.get("raw_context_values_redacted") is not True:
        failures.append("raw_context_redaction_not_recorded")
    if not (
        evidence.get("raw_command_output_redacted") is True
        or evidence.get("raw_result_values_redacted") is True
    ):
        failures.append("raw_output_or_result_redaction_not_recorded")
    if evidence.get("resource") != expected_resource:
        failures.append(f"evidence_resource_mismatch:{evidence.get('resource')}")

    for claim_key in STRONG_CLAIM_KEYS:
        if claim_key in claim_gate and claim_gate.get(claim_key) is not False:
            failures.append(f"overpromoted_claim:{claim_key}")
    return failures


def validate_result_metadata(
    metadata: Mapping[str, Any],
    *,
    expected_component: str,
    expected_action: str,
) -> list[str]:
    failures: list[str] = []
    claim_gate = _claim_gate_for(metadata)
    evidence = _evidence_for(metadata)
    cross_plane = metadata.get("cross_plane_claim_gate")
    if not isinstance(cross_plane, Mapping):
        cross_plane = {}

    if metadata.get("schema") != SAFE_ACTUATOR_METADATA_SCHEMA:
        failures.append("metadata_schema_invalid")
    if metadata.get("redacted") is not True:
        failures.append("metadata_not_redacted")
    if not metadata.get("claim_boundary"):
        failures.append("metadata_claim_boundary_missing")
    if not claim_gate:
        failures.append("claim_gate_missing")
    if claim_gate.get("redacted") is not True:
        failures.append("claim_gate_not_redacted")
    if cross_plane.get("allowed") is not False:
        failures.append("cross_plane_gate_not_fail_closed")
    if evidence.get("component") != expected_component:
        failures.append(f"evidence_component_mismatch:{evidence.get('component')}")
    if evidence.get("action") != expected_action:
        failures.append(f"evidence_action_mismatch:{evidence.get('action')}")
    if evidence.get("raw_output_redacted") is not True:
        failures.append("raw_output_redaction_not_recorded")

    for claim_key in STRONG_CLAIM_KEYS:
        if claim_key in claim_gate and claim_gate.get(claim_key) is not False:
            failures.append(f"overpromoted_claim:{claim_key}")
    return failures


def _last_completed_event(
    event_bus: EventBus,
    *,
    source_agent: str,
    resource: str,
) -> Event | None:
    events = event_bus.get_event_history(
        event_type=EventType.PIPELINE_STAGE_END,
        source_agent=source_agent,
        limit=50,
    )
    for event in reversed(events):
        if event.data.get("stage") == "actuator_completed" and (
            event.data.get("resource") == resource
        ):
            return event
    return None


def _run_spire_server_case(root: Path) -> dict[str, Any]:
    event_bus = EventBus(str(root / "server-eventbus"))
    resource = "identity:spire_server:create_entry"
    client = SPIREServerClient(
        spire_server_bin="spire-server",
        event_bus=event_bus,
        policy_engine=_allow_policy(SPIRE_SERVER_SPIFFE_ID, resource),
        require_policy=True,
        source_agent="spire-server-client",
        node_id="node-spire-server-runtime",
        spiffe_id=SPIRE_SERVER_SPIFFE_ID,
        did="did:mesh:identity:spire-server-runtime",
        wallet_address="0xspireserverruntime",
    )

    with patch(
        "src.security.spiffe.server.client.subprocess.run",
        return_value=SimpleNamespace(
            returncode=0,
            stdout="Entry created: runtime-eid\n",
            stderr="",
        ),
    ):
        result = client.create_entry(
            "spiffe://x0tta6bl4.mesh/workload/runtime-api",
            "spiffe://x0tta6bl4.mesh/node/runtime-worker",
            {"unix:uid": "1000"},
            ttl=60,
            admin=False,
        )

    event = _last_completed_event(
        event_bus,
        source_agent="spire-server-client",
        resource=resource,
    )
    failures: list[str] = []
    if result != "runtime-eid":
        failures.append("spire_server_create_entry_result_mismatch")
    if event is None:
        failures.append("spire_server_completed_event_missing")
    else:
        failures.extend(
            validate_event_payload(
                event,
                expected_source_agent="spire-server-client",
                expected_resource=resource,
            )
        )
    return {
        "case": "spire_server_create_entry",
        "source_agent": "spire-server-client",
        "resource": resource,
        "event_id": event.event_id if event is not None else "",
        "metadata_retained": event is not None and not failures,
        "failures": failures,
    }


def _run_spire_agent_case(root: Path) -> dict[str, Any]:
    case_root = root / "agent-runtime"
    case_root.mkdir(parents=True, exist_ok=True)
    config_path = case_root / "agent.conf"
    socket_path = case_root / "agent.sock"
    config_path.write_text("agent {}", encoding="utf-8")
    socket_path.write_text("", encoding="utf-8")

    event_bus = EventBus(str(root / "agent-eventbus"))
    resource = "identity:spire_agent:start_agent"
    with patch(
        "src.security.spiffe.agent.manager.shutil.which",
        side_effect=lambda binary: f"/usr/bin/{binary}",
    ):
        manager = SPIREAgentManager(
            config_path=config_path,
            socket_path=socket_path,
            event_bus=event_bus,
            policy_engine=_allow_policy(SPIRE_AGENT_SPIFFE_ID, resource),
            require_policy=True,
            source_agent="spire-agent-manager",
            node_id="node-spire-agent-runtime",
            spiffe_id=SPIRE_AGENT_SPIFFE_ID,
            did="did:mesh:identity:spire-agent-runtime",
            wallet_address="0xspireagentruntime",
        )

    process = MagicMock()
    process.pid = 424242
    process.poll.return_value = None
    with patch(
        "src.security.spiffe.agent.manager.subprocess.Popen",
        return_value=process,
    ):
        result = manager.start()

    event = _last_completed_event(
        event_bus,
        source_agent="spire-agent-manager",
        resource=resource,
    )
    failures: list[str] = []
    if result is not True:
        failures.append("spire_agent_start_result_mismatch")
    if event is None:
        failures.append("spire_agent_completed_event_missing")
    else:
        failures.extend(
            validate_event_payload(
                event,
                expected_source_agent="spire-agent-manager",
                expected_resource=resource,
            )
        )
    return {
        "case": "spire_agent_start",
        "source_agent": "spire-agent-manager",
        "resource": resource,
        "event_id": event.event_id if event is not None else "",
        "metadata_retained": event is not None and not failures,
        "failures": failures,
    }


def _configure_token_bridge_reward_success(bridge: TokenBridge) -> None:
    bridge._init_web3 = MagicMock(return_value=True)
    bridge.contract = MagicMock()
    bridge.account = MagicMock()
    bridge.account.address = "0xBridgeRuntime"
    bridge.web3 = MagicMock()
    bridge.contract.functions.canDistributeRewards.return_value.call.return_value = True
    bridge._address_mapping = {"node-runtime": "0xNodeRuntime"}

    tx_hash = MagicMock()
    tx_hash.hex.return_value = "0xtokenruntime"
    bridge.web3.eth.send_raw_transaction.return_value = tx_hash

    receipt = MagicMock()
    receipt.status = 1
    receipt.blockNumber = 4242
    bridge.web3.eth.wait_for_transaction_receipt.return_value = receipt


async def _run_token_bridge_case_async(root: Path) -> dict[str, Any]:
    event_bus = EventBus(str(root / "token-bridge-eventbus"))
    resource = "dao:token_bridge:push_rewards_to_chain"
    mesh_token = MagicMock()
    mesh_token.balance_of.return_value = 0.0
    bridge = TokenBridge(
        mesh_token,
        BridgeConfig(
            rpc_url="https://sepolia.base.org",
            contract_address="0x1234567890abcdef1234567890abcdef12345678",
            private_key="0xdeadbeef",
        ),
        node_id="token-bridge-runtime",
        event_bus=event_bus,
        policy_engine=_allow_policy(TOKEN_BRIDGE_SPIFFE_ID, resource),
        require_policy=True,
        source_agent="token-bridge",
        spiffe_id=TOKEN_BRIDGE_SPIFFE_ID,
        did="did:mesh:token:bridge-runtime",
        wallet_address="0xbridgeruntime",
    )
    _configure_token_bridge_reward_success(bridge)

    result = await bridge.push_rewards_to_chain(
        {"node-runtime": 12.5},
        uptimes={"node-runtime": 99},
    )
    event = _last_completed_event(
        event_bus,
        source_agent="token-bridge",
        resource=resource,
    )
    failures: list[str] = []
    if result != "0xtokenruntime":
        failures.append("token_bridge_reward_result_mismatch")
    if event is None:
        failures.append("token_bridge_completed_event_missing")
    else:
        failures.extend(
            validate_event_payload(
                event,
                expected_source_agent="token-bridge",
                expected_resource=resource,
            )
        )
        payload = event.data if isinstance(event.data, Mapping) else {}
        metadata = _metadata_for(payload)
        claim_gate = _claim_gate_for(metadata)
        if claim_gate.get("pending_chain_submission_claim_allowed") is not True:
            failures.append("pending_chain_submission_claim_not_recorded")
        if payload.get("submitted_transaction") is not True:
            failures.append("submitted_transaction_not_recorded")
        if not payload.get("transaction_hash_hash"):
            failures.append("transaction_hash_hash_missing")
    reward_events = event_bus.get_event_history(
        event_type=EventType.REWARD_RELAY_RECORDED,
        source_agent="token-bridge",
        limit=10,
    )
    if not reward_events:
        failures.append("reward_relay_recorded_event_missing")
    elif event is not None:
        upstream = reward_events[-1].data.get("upstream_evidence", {})
        event_ids = upstream.get("event_ids") if isinstance(upstream, Mapping) else []
        if event.event_id not in event_ids:
            failures.append("reward_relay_upstream_event_id_missing")
    return {
        "case": "token_bridge_push_rewards_to_chain",
        "source_agent": "token-bridge",
        "resource": resource,
        "event_id": event.event_id if event is not None else "",
        "metadata_retained": event is not None and not failures,
        "failures": failures,
    }


def _run_token_bridge_case(root: Path) -> dict[str, Any]:
    return asyncio.run(_run_token_bridge_case_async(root))


def _run_dao_executor_release_script_case(root: Path) -> dict[str, Any]:
    event_bus = EventBus(str(root / "dao-executor-eventbus"))
    resource = "dao:executor:release_script"
    executor = DAOExecutor.__new__(DAOExecutor)
    executor.event_bus = event_bus
    executor.policy_engine = _allow_policy(DAO_EXECUTOR_SPIFFE_ID, resource)
    executor.require_policy = True
    executor.source_agent = "dao-executor"
    executor.event_project_root = "."
    executor.identity = {
        "node_id": "dao-executor-runtime",
        "spiffe_id": DAO_EXECUTOR_SPIFFE_ID,
        "did": "did:mesh:dao:executor-runtime",
        "wallet_address": "0xdaoexecutorruntime",
    }
    executor.safe_actuator = SafeActuator(executor._execute_release_through_actuator)
    executor._last_upgrade_success = None
    executor._last_release_return_code = None
    executor._last_release_duration_ms = None

    process = MagicMock()
    process.returncode = 0
    process.communicate.return_value = ("release ok private deployment detail\n", "")
    with patch("src.dao.executor_webhook.os.path.exists", return_value=True), patch(
        "src.dao.executor_webhook.subprocess.Popen",
        return_value=process,
    ):
        result = executor.trigger_upgrade(
            7701,
            "HELM_UPGRADE: runtime release secret-token",
        )

    event = _last_completed_event(
        event_bus,
        source_agent="dao-executor",
        resource=resource,
    )
    failures: list[str] = []
    if result is not True:
        failures.append("dao_executor_release_script_result_mismatch")
    if event is None:
        failures.append("dao_executor_completed_event_missing")
    else:
        failures.extend(
            validate_event_payload(
                event,
                expected_source_agent="dao-executor",
                expected_resource=resource,
            )
        )
        payload = event.data if isinstance(event.data, Mapping) else {}
        metadata = _metadata_for(payload)
        claim_gate = _claim_gate_for(metadata)
        evidence = _evidence_for(metadata)
        if claim_gate.get("local_release_script_execution_claim_allowed") is not True:
            failures.append("local_dao_release_script_execution_not_recorded")
        if claim_gate.get("production_rollout_claim_allowed") is not False:
            failures.append("dao_executor_production_rollout_not_blocked")
        if claim_gate.get("production_readiness_claim_allowed") is not False:
            failures.append("dao_executor_production_readiness_not_blocked")
        if claim_gate.get("dataplane_delivery_claim_allowed") is not False:
            failures.append("dao_executor_dataplane_not_blocked")
        if claim_gate.get("customer_traffic_claim_allowed") is not False:
            failures.append("dao_executor_customer_traffic_not_blocked")
        if claim_gate.get("external_settlement_finality_claim_allowed") is not False:
            failures.append("dao_executor_settlement_finality_not_blocked")
        if evidence.get("return_code") != 0:
            failures.append("dao_executor_return_code_not_recorded")
        if evidence.get("raw_context_values_redacted") is not True:
            failures.append("dao_executor_raw_context_redaction_missing")
        if evidence.get("raw_command_output_redacted") is not True:
            failures.append("dao_executor_raw_command_redaction_missing")
        if "secret-token" in str(payload):
            failures.append("dao_executor_secret_leaked")
        if "scripts/release_to_main.sh" in str(payload):
            failures.append("dao_executor_script_path_leaked")
        if "private deployment detail" in str(payload):
            failures.append("dao_executor_command_output_leaked")
    return {
        "case": "dao_executor_release_script",
        "source_agent": "dao-executor",
        "resource": resource,
        "event_id": event.event_id if event is not None else "",
        "metadata_retained": event is not None and not failures,
        "failures": failures,
    }


def _run_dao_proposal_executor_helm_case(root: Path) -> dict[str, Any]:
    event_bus = EventBus(str(root / "dao-proposal-executor-eventbus"))
    resource = "dao:proposal_executor:helm_upgrade"
    runner = HelmRunner(
        ExecutorConfig(
            rpc_url="http://localhost:8545",
            governance_address="0x" + "a" * 40,
            helm_release="mesh-op-runtime",
            helm_chart="charts/x0tta-mesh-operator/",
            helm_namespace="default",
            helm_extra_args=[],
            poll_interval=1,
            start_block_offset=10,
            processed_file=root / "dao-proposal-executor-runtime" / "processed.json",
            ledger_path=root / "dao-proposal-executor-runtime" / "audit.jsonl",
            dry_run=False,
        ),
        event_bus=event_bus,
        policy_engine=_allow_policy(DAO_PROPOSAL_EXECUTOR_SPIFFE_ID, resource),
        require_policy=True,
        source_agent="dao-proposal-executor",
        spiffe_id=DAO_PROPOSAL_EXECUTOR_SPIFFE_ID,
        did="did:mesh:dao:proposal-executor-runtime",
        wallet_address="0xdaoproposalexecutorruntime",
    )

    with patch(
        "src.dao.proposal_executor_webhook.subprocess.run",
        return_value=SimpleNamespace(
            returncode=0,
            stdout="helm upgraded private rollout detail\n",
            stderr="",
        ),
    ):
        result = runner.upgrade(
            8801,
            extra_set={
                "api_token": "secret-token",
                "image.tag": "runtime-retention",
            },
        )

    event = _last_completed_event(
        event_bus,
        source_agent="dao-proposal-executor",
        resource=resource,
    )
    failures: list[str] = []
    if result.success is not True:
        failures.append("dao_proposal_executor_helm_result_mismatch")
    if event is None:
        failures.append("dao_proposal_executor_completed_event_missing")
    else:
        failures.extend(
            validate_event_payload(
                event,
                expected_source_agent="dao-proposal-executor",
                expected_resource=resource,
            )
        )
        payload = event.data if isinstance(event.data, Mapping) else {}
        metadata = _metadata_for(payload)
        claim_gate = _claim_gate_for(metadata)
        evidence = _evidence_for(metadata)
        if claim_gate.get("local_helm_command_execution_claim_allowed") is not True:
            failures.append("local_dao_proposal_helm_execution_not_recorded")
        if claim_gate.get("production_rollout_claim_allowed") is not False:
            failures.append("dao_proposal_production_rollout_not_blocked")
        if claim_gate.get("production_readiness_claim_allowed") is not False:
            failures.append("dao_proposal_production_readiness_not_blocked")
        if claim_gate.get("dataplane_delivery_claim_allowed") is not False:
            failures.append("dao_proposal_dataplane_not_blocked")
        if claim_gate.get("customer_traffic_claim_allowed") is not False:
            failures.append("dao_proposal_customer_traffic_not_blocked")
        if claim_gate.get("external_settlement_finality_claim_allowed") is not False:
            failures.append("dao_proposal_settlement_finality_not_blocked")
        if claim_gate.get("traffic_shift_claim_allowed") is not False:
            failures.append("dao_proposal_traffic_shift_not_blocked")
        if evidence.get("return_code") != 0:
            failures.append("dao_proposal_return_code_not_recorded")
        if evidence.get("raw_context_values_redacted") is not True:
            failures.append("dao_proposal_raw_context_redaction_missing")
        if evidence.get("raw_command_output_redacted") is not True:
            failures.append("dao_proposal_raw_command_redaction_missing")
        if "secret-token" in str(payload):
            failures.append("dao_proposal_secret_leaked")
        if "api_token=secret-token" in str(payload):
            failures.append("dao_proposal_command_secret_leaked")
        if "private rollout detail" in str(payload):
            failures.append("dao_proposal_command_output_leaked")
    return {
        "case": "dao_proposal_executor_helm_upgrade",
        "source_agent": "dao-proposal-executor",
        "resource": resource,
        "event_id": event.event_id if event is not None else "",
        "metadata_retained": event is not None and not failures,
        "failures": failures,
    }


def _run_dao_governance_dispatch_case(root: Path) -> dict[str, Any]:
    event_bus = EventBus(str(root / "dao-governance-eventbus"))
    resource = "dao:governance:update_config"
    dispatcher = ActionDispatcher(
        node_id="dao-governance-runtime",
        event_bus=event_bus,
        policy_engine=_allow_policy(DAO_GOVERNANCE_DISPATCHER_SPIFFE_ID, resource),
        require_policy=True,
        source_agent="dao-governance",
        spiffe_id=DAO_GOVERNANCE_DISPATCHER_SPIFFE_ID,
        did="did:mesh:dao:governance-runtime",
        wallet_address="0xdaogovernanceruntime",
    )

    result = dispatcher.dispatch(
        {
            "type": "update_config",
            "key": "runtime.retention",
            "value": "enabled",
            "api_token": "secret-token",
        }
    )
    event = _last_completed_event(
        event_bus,
        source_agent="dao-governance",
        resource=resource,
    )
    failures: list[str] = []
    if result.success is not True:
        failures.append("dao_governance_dispatch_result_mismatch")
    if event is None:
        failures.append("dao_governance_completed_event_missing")
    else:
        failures.extend(
            validate_event_payload(
                event,
                expected_source_agent="dao-governance",
                expected_resource=resource,
            )
        )
        payload = event.data if isinstance(event.data, Mapping) else {}
        metadata = _metadata_for(payload)
        claim_gate = _claim_gate_for(metadata)
        evidence = _evidence_for(metadata)
        if claim_gate.get("local_handler_execution_claim_allowed") is not True:
            failures.append("local_dao_governance_handler_execution_not_recorded")
        if claim_gate.get("governance_execution_finality_claim_allowed") is not False:
            failures.append("dao_governance_finality_not_blocked")
        if claim_gate.get("production_governance_execution_claim_allowed") is not False:
            failures.append("dao_governance_production_execution_not_blocked")
        if claim_gate.get("dataplane_delivery_claim_allowed") is not False:
            failures.append("dao_governance_dataplane_not_blocked")
        if evidence.get("raw_context_values_redacted") is not True:
            failures.append("dao_governance_raw_context_redaction_missing")
        if evidence.get("raw_result_values_redacted") is not True:
            failures.append("dao_governance_raw_result_redaction_missing")
        if "secret-token" in str(payload):
            failures.append("dao_governance_secret_leaked")
    return {
        "case": "dao_governance_dispatch_update_config",
        "source_agent": "dao-governance",
        "resource": resource,
        "event_id": event.event_id if event is not None else "",
        "metadata_retained": event is not None and not failures,
        "failures": failures,
    }


def _run_governance_contract_create_proposal_case(root: Path) -> dict[str, Any]:
    event_bus = EventBus(str(root / "governance-contract-eventbus"))
    resource = "dao:governance_contract:create_proposal"
    contract = GovernanceContract.__new__(GovernanceContract)
    contract.contract_address = "0x1111111111111111111111111111111111111111"
    contract.token_address = "0x2222222222222222222222222222222222222222"
    contract.rpc_url = "https://sepolia.base.org"
    contract.private_key = "0xprivate"
    contract.node_id = "governance-contract-runtime"
    contract.source_agent = "governance-contract"
    contract.event_project_root = "."
    contract.event_bus = event_bus
    contract.policy_engine = _allow_policy(GOVERNANCE_CONTRACT_SPIFFE_ID, resource)
    contract.require_policy = True
    contract.identity = {
        "node_id": "governance-contract-runtime",
        "spiffe_id": GOVERNANCE_CONTRACT_SPIFFE_ID,
        "did": "did:mesh:governance:contract-runtime",
        "wallet_address": "0xgovernancecontractruntime",
    }
    contract.safe_actuator = SafeActuator(contract._execute_chain_write_through_actuator)
    contract._last_chain_write_result = None
    contract._last_chain_write_exception = None
    contract.account = MagicMock()

    def create_proposal_internal(
        _title: str,
        _description: str,
        _duration_seconds: int,
    ) -> dict[str, Any]:
        return {"proposal_id": 77, "tx_hash": "0xgovernancecontractruntime"}

    contract._create_proposal_internal = create_proposal_internal

    result = contract.create_proposal(
        "Runtime retention proposal",
        "Verify bounded chain-write metadata retention",
        60,
    )
    event = _last_completed_event(
        event_bus,
        source_agent="governance-contract",
        resource=resource,
    )
    failures: list[str] = []
    if result != 77:
        failures.append("governance_contract_create_proposal_result_mismatch")
    if event is None:
        failures.append("governance_contract_completed_event_missing")
    else:
        failures.extend(
            validate_event_payload(
                event,
                expected_source_agent="governance-contract",
                expected_resource=resource,
            )
        )
        payload = event.data if isinstance(event.data, Mapping) else {}
        metadata = _metadata_for(payload)
        claim_gate = _claim_gate_for(metadata)
        evidence = _evidence_for(metadata)
        if claim_gate.get("local_transaction_submission_claim_allowed") is not True:
            failures.append("local_governance_contract_submission_not_recorded")
        if claim_gate.get("transaction_hash_observed_claim_allowed") is not True:
            failures.append("governance_contract_transaction_hash_not_recorded")
        if claim_gate.get("external_settlement_finality_claim_allowed") is not False:
            failures.append("governance_contract_settlement_finality_not_blocked")
        if claim_gate.get("governance_execution_finality_claim_allowed") is not False:
            failures.append("governance_contract_governance_finality_not_blocked")
        if claim_gate.get("dataplane_delivery_claim_allowed") is not False:
            failures.append("governance_contract_dataplane_not_blocked")
        if evidence.get("raw_context_values_redacted") is not True:
            failures.append("governance_contract_raw_context_redaction_missing")
        if evidence.get("raw_result_values_redacted") is not True:
            failures.append("governance_contract_raw_result_redaction_missing")
        if "0xprivate" in str(payload):
            failures.append("governance_contract_private_key_leaked")
        if "0xgovernancecontractruntime" in str(metadata):
            failures.append("governance_contract_tx_hash_leaked_in_metadata")
    return {
        "case": "governance_contract_create_proposal",
        "source_agent": "governance-contract",
        "resource": resource,
        "event_id": event.event_id if event is not None else "",
        "metadata_retained": event is not None and not failures,
        "failures": failures,
    }


def _run_ghost_l3_case(root: Path) -> dict[str, Any]:
    event_bus = EventBus(str(root / "ghost-l3-eventbus"))
    resource = "server:ghost_l3:setup_tun"
    server = GhostL3Server(
        master_key=b"0" * 32,
        event_bus=event_bus,
        node_id="ghost-l3-runtime",
        source_agent="ghost-l3-server",
        spiffe_id="spiffe://x0tta6bl4.mesh/workload/ghost-l3-server",
        did="did:mesh:ghost:runtime",
        wallet_address="0xghostruntime",
    )
    with patch("src.server.ghost_server.os.open", return_value=42), patch(
        "src.server.ghost_server.fcntl.ioctl",
        return_value=0,
    ), patch(
        "src.server.ghost_server.subprocess.run",
        return_value=MagicMock(returncode=0),
    ), patch.object(
        server,
        "_enable_ip_forward",
        return_value=None,
    ):
        result = server.setup_tun()

    event = _last_completed_event(
        event_bus,
        source_agent="ghost-l3-server",
        resource=resource,
    )
    failures: list[str] = []
    if result is not True:
        failures.append("ghost_l3_setup_tun_result_mismatch")
    if event is None:
        failures.append("ghost_l3_completed_event_missing")
    else:
        failures.extend(
            validate_event_payload(
                event,
                expected_source_agent="ghost-l3-server",
                expected_resource=resource,
            )
        )
        metadata = _metadata_for(event.data if isinstance(event.data, Mapping) else {})
        claim_gate = _claim_gate_for(metadata)
        if claim_gate.get("local_tun_nat_setup_claim_allowed") is not True:
            failures.append("local_tun_nat_setup_claim_not_recorded")
    return {
        "case": "ghost_l3_setup_tun",
        "source_agent": "ghost-l3-server",
        "resource": resource,
        "event_id": event.event_id if event is not None else "",
        "metadata_retained": event is not None and not failures,
        "failures": failures,
    }


def _run_ebpf_recovery_case(root: Path) -> dict[str, Any]:
    from src.self_healing.ebpf_anomaly_detector import EBPFExecutor

    event_bus = EventBus(str(root / "ebpf-eventbus"))
    resource = "self_healing:ebpf:adjust_route_weights"
    loader = MagicMock()

    def _ebpf_safe_actuator_result(
        _action: str,
        _context: Mapping[str, Any],
    ) -> SafeActuatorResult:
        return SafeActuatorResult(
            success=True,
            evidence_metadata=SafeActuatorEvidenceMetadata(
                claim_gate={
                    "schema": "x0tta6bl4.self_healing.ebpf.safe_actuator_claim_gate.v1",
                    "surface": "self_healing.ebpf.execute",
                    "action_type": "adjust_route_weights",
                    "action_resource": "adjust_route_weights",
                    "local_ebpf_recovery_action_recorded": True,
                    "local_ebpf_recovery_action_succeeded": True,
                    "local_policy_decision_recorded": True,
                    "safe_actuator_result_recorded": True,
                    "local_safe_actuator_success": True,
                    "restored_dataplane_claim_allowed": False,
                    "route_convergence_claim_allowed": False,
                    "kernel_forwarding_correctness_claim_allowed": False,
                    "dataplane_delivery_claim_allowed": False,
                    "traffic_delivery_claim_allowed": False,
                    "live_customer_traffic_confirmed": False,
                    "customer_traffic_claim_allowed": False,
                    "external_dpi_bypass_confirmed": False,
                    "settlement_finality_confirmed": False,
                    "external_settlement_finality_claim_allowed": False,
                    "production_slo_claim_allowed": False,
                    "production_readiness_claim_allowed": False,
                    "claim_boundary": EBPF_SAFE_ACTUATOR_CLAIM_BOUNDARY,
                    "payloads_redacted": True,
                    "redacted": True,
                },
                evidence={
                    "component": "safe_actuator_runtime_metadata_retention",
                    "resource": resource,
                    "action_type": "adjust_route_weights",
                    "raw_context_values_redacted": True,
                    "raw_command_output_redacted": True,
                    "payloads_redacted": True,
                    "redacted": True,
                },
                source_agents=["ebpf-self-healing"],
                claim_boundary=EBPF_SAFE_ACTUATOR_CLAIM_BOUNDARY,
                redacted=True,
            ),
        )

    executor = EBPFExecutor(
        loader,
        event_bus=event_bus,
        node_id="ebpf-runtime",
        source_agent="ebpf-self-healing",
        spiffe_id="spiffe://x0tta6bl4.mesh/workload/ebpf-self-healing",
        did="did:mesh:ebpf:runtime",
        wallet_address="0xebpfruntime",
        safe_actuator=SafeActuator(_ebpf_safe_actuator_result),
    )
    result = executor.execute(
        {
            "action": "adjust_route_weights",
            "interface": "eth0",
            "api_token": "secret-token",
        }
    )
    event = _last_completed_event(
        event_bus,
        source_agent="ebpf-self-healing",
        resource=resource,
    )
    failures: list[str] = []
    if result is not True:
        failures.append("ebpf_recovery_action_result_mismatch")
    if event is None:
        failures.append("ebpf_recovery_completed_event_missing")
    else:
        failures.extend(
            validate_event_payload(
                event,
                expected_source_agent="ebpf-self-healing",
                expected_resource=resource,
            )
        )
        metadata = _metadata_for(event.data if isinstance(event.data, Mapping) else {})
        claim_gate = _claim_gate_for(metadata)
        if claim_gate.get("local_ebpf_recovery_action_succeeded") is not True:
            failures.append("local_ebpf_recovery_action_not_recorded")
    return {
        "case": "ebpf_adjust_route_weights",
        "source_agent": "ebpf-self-healing",
        "resource": resource,
        "event_id": event.event_id if event is not None else "",
        "metadata_retained": event is not None and not failures,
        "failures": failures,
    }


def _run_maas_governance_case(root: Path) -> dict[str, Any]:
    event_bus = EventBus(str(root / "maas-governance-eventbus"))
    resource = "api:maas_governance:rotate_keys"
    result = execute_governance_action(
        {
            "type": "rotate_keys",
            "params": {
                "scope": "runtime-retention-smoke",
                "api_token": "secret-token",
            },
        },
        None,
        event_bus=event_bus,
        policy_engine=_allow_policy(MAAS_GOVERNANCE_SPIFFE_ID, resource),
        require_policy=True,
        source_agent="maas-governance",
        spiffe_id=MAAS_GOVERNANCE_SPIFFE_ID,
        did="did:mesh:maas:governance-runtime",
        wallet_address="0xgovernanceruntime",
        proposal_id="prop-runtime",
        user_id="user-runtime",
    )
    event = _last_completed_event(
        event_bus,
        source_agent="maas-governance",
        resource=resource,
    )
    failures: list[str] = []
    if result.get("success") is not True:
        failures.append("maas_governance_action_result_mismatch")
    if event is None:
        failures.append("maas_governance_completed_event_missing")
    else:
        failures.extend(
            validate_event_payload(
                event,
                expected_source_agent="maas-governance",
                expected_resource=resource,
            )
        )
        metadata = _metadata_for(event.data if isinstance(event.data, Mapping) else {})
        claim_gate = _claim_gate_for(metadata)
        if claim_gate.get("local_maas_governance_action_succeeded") is not True:
            failures.append("local_maas_governance_action_not_recorded")
        if claim_gate.get("dao_governance_finality_claim_allowed") is not False:
            failures.append("dao_governance_finality_not_blocked")
    return {
        "case": "maas_governance_rotate_keys",
        "source_agent": "maas-governance",
        "resource": resource,
        "event_id": event.event_id if event is not None else "",
        "metadata_retained": event is not None and not failures,
        "failures": failures,
    }


class _FakePQCSignerProcess:
    def __init__(self, returncode: int):
        self.returncode = returncode

    async def wait(self) -> int:
        return self.returncode


async def _run_pqc_rotator_case_async(root: Path) -> dict[str, Any]:
    event_bus = EventBus(str(root / "pqc-rotator-eventbus"))
    resource = "services:pqc_rotator:rotate_identity"
    identity_file = root / "pqc-rotator-runtime" / "identity.txt"
    temp_identity_file = root / "pqc-rotator-runtime" / "identity.new"

    async def _process_factory(*_cmd: str, stdout: Any = None, stderr: Any = None) -> Any:
        if stdout is not None:
            stdout.write(b"Private Key (hex): 00\n")
            stdout.flush()
        return _FakePQCSignerProcess(0)

    service = PQCRotatorService(
        identity_file=identity_file,
        temp_identity_file=temp_identity_file,
        signer_cmd=("python3", "pqc_signer.py", "--api-token", "secret-token"),
        process_factory=_process_factory,
        report_generator=lambda: None,
        event_bus=event_bus,
        policy_engine=_allow_policy(PQC_ROTATOR_SPIFFE_ID, resource),
        require_policy=True,
        source_agent="pqc-rotator",
        spiffe_id=PQC_ROTATOR_SPIFFE_ID,
        did="did:mesh:pqc:rotator-runtime",
        wallet_address="0xpqcrotatorruntime",
    )

    result = await service.rotate_once()
    event = _last_completed_event(
        event_bus,
        source_agent="pqc-rotator",
        resource=resource,
    )
    failures: list[str] = []
    if result.get("success") is not True:
        failures.append("pqc_rotator_result_mismatch")
    if event is None:
        failures.append("pqc_rotator_completed_event_missing")
    else:
        failures.extend(
            validate_event_payload(
                event,
                expected_source_agent="pqc-rotator",
                expected_resource=resource,
            )
        )
        payload = event.data if isinstance(event.data, Mapping) else {}
        metadata = _metadata_for(payload)
        claim_gate = _claim_gate_for(metadata)
        if claim_gate.get("local_pqc_identity_rotation_claim_allowed") is not True:
            failures.append("local_pqc_identity_rotation_claim_not_recorded")
        if claim_gate.get("live_pqc_trust_finality_claim_allowed") is not False:
            failures.append("live_pqc_trust_finality_not_blocked")
        if "secret-token" in str(payload):
            failures.append("pqc_rotator_secret_leaked")
    return {
        "case": "pqc_rotator_rotate_identity",
        "source_agent": "pqc-rotator",
        "resource": resource,
        "event_id": event.event_id if event is not None else "",
        "metadata_retained": event is not None and not failures,
        "failures": failures,
    }


def _run_pqc_rotator_case(root: Path) -> dict[str, Any]:
    return asyncio.run(_run_pqc_rotator_case_async(root))


def _run_mptcp_manager_case(root: Path) -> dict[str, Any]:
    event_bus = EventBus(str(root / "mptcp-manager-eventbus"))
    resource = "network:mptcp:enable_mptcp"

    with patch(
        "src.network.mptcp_manager.subprocess.run",
        return_value=MagicMock(returncode=0, stdout="", stderr=""),
    ):
        result = MPTCPManager.enable_mptcp(
            True,
            event_bus=event_bus,
            policy_engine=_allow_policy(MPTCP_MANAGER_SPIFFE_ID, resource),
            require_policy=True,
            source_agent="mptcp-manager",
            node_id="mptcp-manager-runtime",
            spiffe_id=MPTCP_MANAGER_SPIFFE_ID,
            did="did:mesh:mptcp:runtime",
            wallet_address="0xmptcpruntime",
        )

    event = _last_completed_event(
        event_bus,
        source_agent="mptcp-manager",
        resource=resource,
    )
    failures: list[str] = []
    if result is not True:
        failures.append("mptcp_manager_enable_result_mismatch")
    if event is None:
        failures.append("mptcp_manager_completed_event_missing")
    else:
        failures.extend(
            validate_event_payload(
                event,
                expected_source_agent="mptcp-manager",
                expected_resource=resource,
            )
        )
        metadata = _metadata_for(event.data if isinstance(event.data, Mapping) else {})
        claim_gate = _claim_gate_for(metadata)
        evidence = _evidence_for(metadata)
        if claim_gate.get("local_mptcp_configuration_claim_allowed") is not True:
            failures.append("local_mptcp_configuration_claim_not_recorded")
        if claim_gate.get("local_kernel_setting_claim_allowed") is not True:
            failures.append("local_kernel_setting_claim_not_recorded")
        if claim_gate.get("traffic_delivery_claim_allowed") is not False:
            failures.append("mptcp_traffic_delivery_not_blocked")
        if claim_gate.get("production_slo_claim_allowed") is not False:
            failures.append("mptcp_production_slo_not_blocked")
        if evidence.get("raw_context_values_redacted") is not True:
            failures.append("mptcp_raw_context_redaction_missing")
        if evidence.get("raw_command_output_redacted") is not True:
            failures.append("mptcp_raw_command_redaction_missing")
    return {
        "case": "mptcp_manager_enable_mptcp",
        "source_agent": "mptcp-manager",
        "resource": resource,
        "event_id": event.event_id if event is not None else "",
        "metadata_retained": event is not None and not failures,
        "failures": failures,
    }


def _run_mesh_action_enforcer_case(root: Path) -> dict[str, Any]:
    event_bus = EventBus(str(root / "mesh-action-enforcer-eventbus"))
    resource = "mesh:action_enforcer:recommendations"
    enforcer = MeshActionEnforcer(event_bus=event_bus)

    def fake_run(command: Sequence[str], **_kwargs: Any) -> SimpleNamespace:
        return SimpleNamespace(
            returncode=0,
            stdout=f"ok {' '.join(command)} private peer detail\n",
            stderr="",
        )

    metric_policy = build_mesh_metric_evidence_policy(
        {
            "mesh_metric_source_available": 1.0,
            "mesh_metric_dataplane_samples": 1.0,
            "mesh_metric_estimated_samples": 0.0,
            "mesh_metric_fallback_samples": 0.0,
        }
    )
    with patch.dict(
        "os.environ",
        {"X0TTA6BL4_MESH_ACTION_ENFORCER_APPLY": "1"},
        clear=False,
    ), patch(
        "src.mesh.action_enforcer._find_yggdrasilctl",
        return_value="/usr/bin/yggdrasilctl",
    ), patch(
        "src.mesh.action_enforcer.subprocess.run",
        side_effect=fake_run,
    ):
        result = enforcer.enforce_recommendations(
            [
                {
                    "action": "refresh",
                    "route_id": "direct-runtime-route",
                    "peer_uri": "tcp://10.0.0.1:9000",
                }
            ],
            metric_evidence_policy=metric_policy,
        )

    events = event_bus.get_event_history(
        event_type=EventType.PIPELINE_STAGE_END,
        source_agent="mesh-action-enforcer",
        limit=20,
    )
    event = next(
        (
            candidate
            for candidate in reversed(events)
            if candidate.data.get("stage") == "action_completed"
            and candidate.data.get("resource") == resource
        ),
        None,
    )
    failures: list[str] = []
    if result.get("success") is not True:
        failures.append("mesh_action_enforcer_result_mismatch")
    if event is None:
        failures.append("mesh_action_enforcer_completed_event_missing")
    else:
        payload = event.data if isinstance(event.data, Mapping) else {}
        if event.source_agent != "mesh-action-enforcer":
            failures.append(f"source_agent_mismatch:{event.source_agent}")
        if payload.get("resource") != resource:
            failures.append(f"resource_mismatch:{payload.get('resource')}")
        if payload.get("safe_actuator") is not True:
            failures.append("mesh_action_enforcer_safe_actuator_flag_missing")
        event_result = payload.get("result") if isinstance(payload.get("result"), Mapping) else {}
        metadata_items = event_result.get("safe_actuator_evidence_metadata")
        if not isinstance(metadata_items, list) or not metadata_items:
            failures.append("mesh_action_enforcer_safe_actuator_metadata_missing")
            metadata = {}
        else:
            metadata = metadata_items[-1] if isinstance(metadata_items[-1], Mapping) else {}
        claim_gate = _claim_gate_for(metadata)
        evidence = _evidence_for(metadata)
        if metadata.get("schema") != SAFE_ACTUATOR_METADATA_SCHEMA:
            failures.append("metadata_schema_invalid")
        if metadata.get("redacted") is not True:
            failures.append("metadata_not_redacted")
        if claim_gate.get("safe_actuator_result_recorded") is not True:
            failures.append("safe_actuator_result_not_recorded")
        if claim_gate.get("resource") != resource:
            failures.append(f"claim_gate_resource_mismatch:{claim_gate.get('resource')}")
        if claim_gate.get("local_command_execution_claim_allowed") is not True:
            failures.append("mesh_action_enforcer_local_command_not_recorded")
        if claim_gate.get("local_yggdrasil_reconfiguration_claim_allowed") is not True:
            failures.append("mesh_action_enforcer_yggdrasil_reconfiguration_not_recorded")
        if evidence.get("resource") != resource:
            failures.append(f"evidence_resource_mismatch:{evidence.get('resource')}")
        if evidence.get("raw_context_values_redacted") is not True:
            failures.append("mesh_action_enforcer_raw_context_redaction_missing")
        if evidence.get("raw_command_output_redacted") is not True:
            failures.append("mesh_action_enforcer_raw_command_redaction_missing")
        if evidence.get("outputs_redacted") is not True:
            failures.append("mesh_action_enforcer_outputs_redaction_missing")
        if event_result.get("command_attempts") != 2:
            failures.append("mesh_action_enforcer_command_attempts_mismatch")
        if event_result.get("command_successes") != 2:
            failures.append("mesh_action_enforcer_command_successes_mismatch")
        if payload.get("dataplane_confirmed") is not False:
            failures.append("mesh_action_enforcer_dataplane_overpromoted")
        if payload.get("restored_dataplane_claim_allowed") is not False:
            failures.append("mesh_action_enforcer_restored_dataplane_overpromoted")
        for claim_key in STRONG_CLAIM_KEYS:
            if claim_key in claim_gate and claim_gate.get(claim_key) is not False:
                failures.append(f"overpromoted_claim:{claim_key}")
        payload_text = str(payload)
        if "10.0.0.1" in payload_text:
            failures.append("mesh_action_enforcer_peer_uri_leaked")
        if "private peer detail" in payload_text:
            failures.append("mesh_action_enforcer_command_output_leaked")
    return {
        "case": "mesh_action_enforcer_yggdrasil_restart",
        "source_agent": "mesh-action-enforcer",
        "resource": resource,
        "event_id": event.event_id if event is not None else "",
        "metadata_retained": event is not None and not failures,
        "failures": failures,
    }


def _run_self_healing_mapek_case(root: Path) -> dict[str, Any]:
    event_bus = EventBus(str(root / "self-healing-mapek-eventbus"))
    resource = "self_healing:mapek:execute"
    manager = SelfHealingManager(
        node_id="self-healing-mapek-runtime",
        event_bus=event_bus,
        action_cooldown_seconds=0.0,
    )

    def publish_downstream_recovery_event(_action: str, _context: Mapping[str, Any]) -> bool:
        event_bus.publish(
            EventType.PIPELINE_STAGE_END,
            "recovery-action-executor",
            {
                "stage": "actuator_completed",
                "resource": "self_healing:recovery:restart_service",
                "claim_gate": {
                    "schema": "x0tta6bl4.recovery.claim_gate.v1",
                    "dataplane_confirmed": False,
                    "post_action_dataplane_revalidated": False,
                    "restored_dataplane_claim_allowed": False,
                    "traffic_delivery_claim_allowed": False,
                    "customer_traffic_claim_allowed": False,
                    "production_readiness_claim_allowed": False,
                    "claim_boundary": "bounded recovery executor evidence only",
                    "redacted": True,
                },
                "raw_payload_redacted": True,
            },
        )
        return True

    with (
        patch.object(manager.monitor, "check", return_value=True),
        patch.object(manager.analyzer, "analyze", return_value="High CPU"),
        patch.object(manager.planner, "plan", return_value="Restart service"),
        patch.object(
            manager.executor,
            "execute",
            side_effect=publish_downstream_recovery_event,
        ),
    ):
        manager.run_cycle(
            {
                "cpu_percent": 95,
                "node_id": "raw-node-id",
                "api_token": "secret-token",
            }
        )

    events = event_bus.get_event_history(
        event_type=EventType.PIPELINE_STAGE_END,
        source_agent="self-healing-mapek",
        limit=20,
    )
    event = next(
        (
            candidate
            for candidate in reversed(events)
            if candidate.data.get("stage") == "execute_completed"
            and candidate.data.get("resource") == resource
        ),
        None,
    )
    failures: list[str] = []
    if event is None:
        failures.append("self_healing_mapek_execute_event_missing")
    else:
        failures.extend(
            validate_event_payload(
                event,
                expected_source_agent="self-healing-mapek",
                expected_resource=resource,
            )
        )
        payload = event.data if isinstance(event.data, Mapping) else {}
        metadata = _metadata_for(payload)
        claim_gate = _claim_gate_for(metadata)
        evidence = _evidence_for(metadata)
        if claim_gate.get("local_control_action_claim_allowed") is not True:
            failures.append("self_healing_mapek_local_control_action_not_recorded")
        if claim_gate.get("downstream_recovery_evidence_present") is not True:
            failures.append("self_healing_mapek_downstream_evidence_missing")
        if claim_gate.get("downstream_recovery_claim_gate_present") is not True:
            failures.append("self_healing_mapek_downstream_claim_gate_missing")
        if claim_gate.get("restored_dataplane_claim_allowed") is not False:
            failures.append("self_healing_mapek_restored_dataplane_overpromoted")
        if claim_gate.get("traffic_delivery_claim_allowed") is not False:
            failures.append("self_healing_mapek_traffic_delivery_overpromoted")
        if claim_gate.get("customer_traffic_claim_allowed") is not False:
            failures.append("self_healing_mapek_customer_traffic_overpromoted")
        if claim_gate.get("production_readiness_claim_allowed") is not False:
            failures.append("self_healing_mapek_production_overpromoted")
        if evidence.get("raw_context_values_redacted") is not True:
            failures.append("self_healing_mapek_raw_context_redaction_missing")
        if evidence.get("raw_result_values_redacted") is not True:
            failures.append("self_healing_mapek_raw_result_redaction_missing")
        payload_text = str(payload)
        if "raw-node-id" in payload_text:
            failures.append("self_healing_mapek_node_id_leaked")
        if "secret-token" in payload_text:
            failures.append("self_healing_mapek_secret_leaked")
    return {
        "case": "self_healing_mapek_execute",
        "source_agent": "self-healing-mapek",
        "resource": resource,
        "event_id": event.event_id if event is not None else "",
        "metadata_retained": event is not None and not failures,
        "failures": failures,
    }


def _run_pbft_execute_case(root: Path) -> dict[str, Any]:
    event_bus = EventBus(str(root / "swarm-pbft-eventbus"))
    resource = "swarm:pbft:execute"
    node = PBFTNode(
        node_id="node-pbft-runtime",
        peers={"node-pbft-2", "node-pbft-3", "node-pbft-4"},
        f=1,
        event_bus=event_bus,
        policy_engine=_allow_policy(SWARM_PBFT_SPIFFE_ID, resource),
        require_policy=True,
        source_agent="swarm-pbft",
        spiffe_id=SWARM_PBFT_SPIFFE_ID,
        did="did:mesh:swarm:pbft-runtime",
        wallet_address="0xpbftruntime",
    )
    node.set_callbacks(
        on_execute=lambda operation: {
            "success": True,
            "status": "executed",
            "operation_type": str((operation or {}).get("type", "")),
        }
    )
    entry = node._get_or_create_entry(1)
    entry.phase = PBFTPhase.PREPARE
    entry.view = 0
    entry.digest = "runtime-digest"
    entry.pre_prepare_msg = PBFTMessage(
        msg_type="pre_prepare",
        view=0,
        sequence=1,
        digest="runtime-digest",
        sender_id="node-pbft-runtime",
        request={
            "operation": {
                "type": "runtime-retention",
                "api_token": "secret-token",
            }
        },
    )

    node._execute(entry)

    event = _last_completed_event(
        event_bus,
        source_agent="swarm-pbft",
        resource=resource,
    )
    failures: list[str] = []
    if not isinstance(entry.result, Mapping) or entry.result.get("success") is not True:
        failures.append("pbft_execute_result_mismatch")
    if event is None:
        failures.append("pbft_completed_event_missing")
    else:
        failures.extend(
            validate_event_payload(
                event,
                expected_source_agent="swarm-pbft",
                expected_resource=resource,
            )
        )
        payload = event.data if isinstance(event.data, Mapping) else {}
        metadata = _metadata_for(payload)
        claim_gate = _claim_gate_for(metadata)
        evidence = _evidence_for(metadata)
        if claim_gate.get("local_pbft_callback_execution_claim_allowed") is not True:
            failures.append("local_pbft_callback_execution_not_recorded")
        if claim_gate.get("cluster_consensus_finality_claim_allowed") is not False:
            failures.append("pbft_cluster_consensus_finality_not_blocked")
        if claim_gate.get("production_readiness_claim_allowed") is not False:
            failures.append("pbft_production_readiness_not_blocked")
        if evidence.get("operation_type") != "runtime-retention":
            failures.append("pbft_operation_type_not_recorded")
        if "secret-token" in str(payload):
            failures.append("pbft_secret_leaked")
    return {
        "case": "pbft_execute_callback",
        "source_agent": "swarm-pbft",
        "resource": resource,
        "event_id": event.event_id if event is not None else "",
        "metadata_retained": event is not None and not failures,
        "failures": failures,
    }


class _RuntimeSwarm:
    node_id = "node-mapek-runtime"

    async def propose_action(self, action: SwarmAction) -> DecisionResult:
        return DecisionResult(
            decision_id="decision-mapek-runtime",
            approved=True,
            context=DecisionContext(
                topic=action.action_type,
                description=action.description,
                data=action.parameters,
                priority=action.priority,
            ),
            consensus_mode=ConsensusMode.SIMPLE,
            latency_ms=1.0,
            participation_rate=1.0,
            votes_for=1,
            votes_against=0,
            votes_abstain=0,
            reason="approved",
        )


async def _run_swarm_mapek_case_async(root: Path) -> dict[str, Any]:
    event_bus = EventBus(str(root / "swarm-mapek-eventbus"))
    resource = "swarm:mapek:healing"
    mapek = MAPEKIntegration(
        _RuntimeSwarm(),
        event_bus=event_bus,
        policy_engine=_allow_policy(SWARM_MAPEK_SPIFFE_ID, resource),
        require_policy=True,
        source_agent="swarm-mapek",
        spiffe_id=SWARM_MAPEK_SPIFFE_ID,
        did="did:mesh:swarm:mapek-runtime",
        wallet_address="0xmapekruntime",
    )
    action = SwarmAction(
        action_type="healing",
        description="Runtime metadata retention healing",
        parameters={
            "node_id": "node-mapek-target",
            "api_token": "secret-token",
        },
        proposer_id="node-mapek-runtime",
        priority=DecisionPriority.HIGH,
    )

    result = await mapek.execute(action)

    event = _last_completed_event(
        event_bus,
        source_agent="swarm-mapek",
        resource=resource,
    )
    failures: list[str] = []
    if result.get("success") is not True:
        failures.append("swarm_mapek_execute_result_mismatch")
    if event is None:
        failures.append("swarm_mapek_completed_event_missing")
    else:
        failures.extend(
            validate_event_payload(
                event,
                expected_source_agent="swarm-mapek",
                expected_resource=resource,
            )
        )
        payload = event.data if isinstance(event.data, Mapping) else {}
        metadata = _metadata_for(payload)
        claim_gate = _claim_gate_for(metadata)
        evidence = _evidence_for(metadata)
        if claim_gate.get("local_swarm_action_observed_claim_allowed") is not True:
            failures.append("local_swarm_action_not_recorded")
        if claim_gate.get("local_swarm_decision_result_claim_allowed") is not True:
            failures.append("local_swarm_decision_not_recorded")
        if claim_gate.get("cluster_wide_consensus_finality_claim_allowed") is not False:
            failures.append("swarm_mapek_cluster_consensus_finality_not_blocked")
        if claim_gate.get("production_action_applied_claim_allowed") is not False:
            failures.append("swarm_mapek_production_action_not_blocked")
        if claim_gate.get("production_readiness_claim_allowed") is not False:
            failures.append("swarm_mapek_production_readiness_not_blocked")
        if evidence.get("decision_approved") is not True:
            failures.append("swarm_mapek_decision_approval_not_recorded")
        if evidence.get("resource") != resource:
            failures.append("swarm_mapek_resource_not_recorded")
        if "secret-token" in str(payload):
            failures.append("swarm_mapek_secret_leaked")
    return {
        "case": "swarm_mapek_healing_execute",
        "source_agent": "swarm-mapek",
        "resource": resource,
        "event_id": event.event_id if event is not None else "",
        "metadata_retained": event is not None and not failures,
        "failures": failures,
    }


def _run_swarm_mapek_case(root: Path) -> dict[str, Any]:
    return asyncio.run(_run_swarm_mapek_case_async(root))


def _run_canary_deployment_case(root: Path) -> dict[str, Any]:
    event_bus = EventBus(str(root / "canary-deployment-eventbus"))
    resource = "deployment:canary:deploy_canary_version"
    canary = CanaryDeployment(
        config=DeploymentConfig(allow_live_actions=True),
        event_bus=event_bus,
        source_agent="canary-deployment",
        node_id="canary-deployment-runtime",
    )

    with patch(
        "src.deployment.canary_deployment.subprocess.run",
        return_value=SimpleNamespace(
            returncode=0,
            stdout="helm upgrade ok private rollout detail\n",
            stderr="",
        ),
    ):
        result = canary._deploy_canary_version("v-runtime")

    event = _last_completed_event(
        event_bus,
        source_agent="canary-deployment",
        resource=resource,
    )
    failures: list[str] = []
    if result is not True:
        failures.append("canary_deployment_result_mismatch")
    if event is None:
        failures.append("canary_deployment_completed_event_missing")
    else:
        failures.extend(
            validate_event_payload(
                event,
                expected_source_agent="canary-deployment",
                expected_resource=resource,
            )
        )
        payload = event.data if isinstance(event.data, Mapping) else {}
        metadata = _metadata_for(payload)
        claim_gate = _claim_gate_for(metadata)
        evidence = _evidence_for(metadata)
        if claim_gate.get("local_canary_rollout_attempt_claim_allowed") is not True:
            failures.append("local_canary_rollout_attempt_claim_not_recorded")
        if claim_gate.get("local_canary_rollout_action_succeeded") is not True:
            failures.append("local_canary_rollout_success_not_recorded")
        if claim_gate.get("traffic_shift_claim_allowed") is not False:
            failures.append("canary_traffic_shift_not_blocked")
        if claim_gate.get("live_customer_traffic_claim_allowed") is not False:
            failures.append("canary_customer_traffic_not_blocked")
        if claim_gate.get("production_slo_claim_allowed") is not False:
            failures.append("canary_production_slo_not_blocked")
        if evidence.get("raw_context_values_redacted") is not True:
            failures.append("canary_raw_context_redaction_missing")
        if evidence.get("raw_command_output_redacted") is not True:
            failures.append("canary_raw_command_redaction_missing")
        if "private rollout detail" in str(payload):
            failures.append("canary_command_output_leaked")
    return {
        "case": "canary_deployment_rollout",
        "source_agent": "canary-deployment",
        "resource": resource,
        "event_id": event.event_id if event is not None else "",
        "metadata_retained": event is not None and not failures,
        "failures": failures,
    }


def _run_multi_cloud_deployment_case(root: Path) -> dict[str, Any]:
    event_bus = EventBus(str(root / "multi-cloud-deployment-eventbus"))
    resource = "deployment:multi_cloud:deploy"
    deployment = MultiCloudDeployment(
        MultiCloudDeploymentConfig(
            provider=MultiCloudProvider.AWS,
            region="us-east-1",
            cluster_name="runtime-cluster",
            image_tag="v-runtime",
            allow_live_actions=True,
        ),
        event_bus=event_bus,
        source_agent="multi-cloud-deployment",
        node_id="multi-cloud-deployment-runtime",
    )

    with (
        patch.object(
            deployment,
            "_build_and_push_image",
            return_value="registry.example/private/image:v-runtime",
        ),
        patch.object(deployment, "_deploy_to_cluster", return_value=True),
        patch.object(deployment, "_health_check", return_value=True),
    ):
        result = deployment.deploy()

    event = _last_completed_event(
        event_bus,
        source_agent="multi-cloud-deployment",
        resource=resource,
    )
    failures: list[str] = []
    if result.success is not True:
        failures.append("multi_cloud_deployment_result_mismatch")
    if event is None:
        failures.append("multi_cloud_deployment_completed_event_missing")
    else:
        failures.extend(
            validate_event_payload(
                event,
                expected_source_agent="multi-cloud-deployment",
                expected_resource=resource,
            )
        )
        payload = event.data if isinstance(event.data, Mapping) else {}
        metadata = _metadata_for(payload)
        claim_gate = _claim_gate_for(metadata)
        evidence = _evidence_for(metadata)
        if claim_gate.get("local_deployment_command_attempt_claim_allowed") is not True:
            failures.append("local_multi_cloud_deployment_attempt_claim_not_recorded")
        if claim_gate.get("local_deployment_command_succeeded") is not True:
            failures.append("local_multi_cloud_deployment_success_not_recorded")
        if claim_gate.get("traffic_shift_claim_allowed") is not False:
            failures.append("multi_cloud_traffic_shift_not_blocked")
        if claim_gate.get("live_customer_traffic_claim_allowed") is not False:
            failures.append("multi_cloud_customer_traffic_not_blocked")
        if claim_gate.get("production_slo_claim_allowed") is not False:
            failures.append("multi_cloud_production_slo_not_blocked")
        if evidence.get("raw_context_values_redacted") is not True:
            failures.append("multi_cloud_raw_context_redaction_missing")
        if evidence.get("raw_command_output_redacted") is not True:
            failures.append("multi_cloud_raw_command_redaction_missing")
        if "registry.example/private/image" in str(payload):
            failures.append("multi_cloud_image_url_leaked")
    return {
        "case": "multi_cloud_deployment_rollout",
        "source_agent": "multi-cloud-deployment",
        "resource": resource,
        "event_id": event.event_id if event is not None else "",
        "metadata_retained": event is not None and not failures,
        "failures": failures,
    }


def _run_ops_canary_rollout_script_result_case(root: Path) -> dict[str, Any]:
    with contextlib.redirect_stdout(io.StringIO()):
        result = asyncio.run(
            ops_canary_deployment.deploy_canary(
                percentage=5.0,
                duration_minutes=0,
            )
        )
    metadata = result.get("safe_actuator_evidence_metadata")
    if not isinstance(metadata, Mapping):
        metadata = {}

    failures = validate_result_metadata(
        metadata,
        expected_component="scripts.canary_deployment",
        expected_action="deploy_canary_observation",
    )
    claim_gate = _claim_gate_for(metadata)
    evidence = _evidence_for(metadata)
    if claim_gate.get("local_requested_rollout_observation_claim_allowed") is not True:
        failures.append("ops_canary_requested_rollout_observation_not_recorded")
    if claim_gate.get("traffic_shift_claim_allowed") is not False:
        failures.append("ops_canary_traffic_shift_not_blocked")
    if claim_gate.get("live_customer_traffic_claim_allowed") is not False:
        failures.append("ops_canary_customer_traffic_not_blocked")
    if claim_gate.get("production_slo_claim_allowed") is not False:
        failures.append("ops_canary_production_slo_not_blocked")
    if claim_gate.get("production_readiness_claim_allowed") is not False:
        failures.append("ops_canary_production_readiness_not_blocked")
    if evidence.get("requested_rollout_percentage") != 5.0:
        failures.append("ops_canary_requested_percentage_not_recorded")
    if result.get("traffic_shift_claim_allowed") is not False:
        failures.append("ops_canary_result_traffic_shift_not_blocked")
    if result.get("production_readiness_claim_allowed") is not False:
        failures.append("ops_canary_result_production_readiness_not_blocked")

    return {
        "case": "ops_canary_rollout_script_result_metadata",
        "source_agent": "canary-rollout-script",
        "resource": "ops:canary_rollout:deploy_canary_observation",
        "event_id": "",
        "metadata_retained": bool(metadata) and not failures,
        "result_metadata_retained": bool(metadata) and not failures,
        "failures": failures,
    }


def _run_ops_production_monitor_health_result_case(root: Path) -> dict[str, Any]:
    with _without_proxy_env_for_loopback(), _local_monitor_http_target() as base_url:
        monitor = ops_production_monitor.ProductionMonitor(base_url=base_url)
        result = asyncio.run(monitor.check_health())
    metadata = result.get("safe_actuator_evidence_metadata")
    if not isinstance(metadata, Mapping):
        metadata = {}

    failures = validate_result_metadata(
        metadata,
        expected_component="scripts.production_monitor",
        expected_action="check_health",
    )
    claim_gate = _claim_gate_for(metadata)
    evidence = _evidence_for(metadata)
    if claim_gate.get("local_http_health_observation_claim_allowed") is not True:
        failures.append("ops_production_monitor_health_observation_not_recorded")
    if claim_gate.get("local_http_metrics_observation_claim_allowed") is not False:
        failures.append("ops_production_monitor_metrics_observation_overclaimed")
    if claim_gate.get("traffic_shift_claim_allowed") is not False:
        failures.append("ops_production_monitor_traffic_shift_not_blocked")
    if claim_gate.get("live_customer_traffic_claim_allowed") is not False:
        failures.append("ops_production_monitor_customer_traffic_not_blocked")
    if claim_gate.get("production_slo_claim_allowed") is not False:
        failures.append("ops_production_monitor_production_slo_not_blocked")
    if claim_gate.get("production_readiness_claim_allowed") is not False:
        failures.append("ops_production_monitor_production_readiness_not_blocked")
    if evidence.get("health_observed") is not True:
        failures.append("ops_production_monitor_evidence_health_not_recorded")
    if result.get("healthy") is not True:
        failures.append("ops_production_monitor_health_result_not_healthy")
    if result.get("production_readiness_claim_allowed") is not False:
        failures.append("ops_production_monitor_result_readiness_not_blocked")
    if result.get("production_slo_claim_allowed") is not False:
        failures.append("ops_production_monitor_result_slo_not_blocked")
    if result.get("traffic_shift_claim_allowed") is not False:
        failures.append("ops_production_monitor_result_traffic_shift_not_blocked")
    if result.get("live_customer_traffic_proven") is not False:
        failures.append("ops_production_monitor_result_customer_traffic_not_blocked")

    return {
        "case": "ops_production_monitor_health_result_metadata",
        "source_agent": "production-monitor-script",
        "resource": "ops:production_monitor:check_health_observation",
        "event_id": "",
        "metadata_retained": bool(metadata) and not failures,
        "result_metadata_retained": bool(metadata) and not failures,
        "failures": failures,
    }


def _run_ops_auto_rollback_recommendation_result_case(root: Path) -> dict[str, Any]:
    async def _run_case() -> tuple[Mapping[str, Any], Mapping[str, Any], bool, str]:
        with (
            _without_proxy_env_for_loopback(),
            _local_monitor_http_target(error_rate=0.12) as base_url,
        ):
            rollback = ops_auto_rollback.AutoRollback(
                base_url=base_url,
                allow_live_rollback=False,
            )
            metrics_result = await rollback.check_metrics()
            should_rollback, reason = rollback.should_rollback(metrics_result)
            with contextlib.redirect_stdout(io.StringIO()):
                rollback_result = (
                    await rollback.execute_rollback() if should_rollback else {}
                )
            return metrics_result, rollback_result, should_rollback, reason

    metrics_result, rollback_result, should_rollback, reason = asyncio.run(_run_case())
    metrics_metadata = metrics_result.get("safe_actuator_evidence_metadata")
    if not isinstance(metrics_metadata, Mapping):
        metrics_metadata = {}
    rollback_metadata = rollback_result.get("safe_actuator_evidence_metadata")
    if not isinstance(rollback_metadata, Mapping):
        rollback_metadata = {}

    failures = [
        f"metrics:{failure}"
        for failure in validate_result_metadata(
            metrics_metadata,
            expected_component="scripts.auto_rollback",
            expected_action="check_metrics",
        )
    ]
    failures.extend(
        f"rollback:{failure}"
        for failure in validate_result_metadata(
            rollback_metadata,
            expected_component="scripts.auto_rollback",
            expected_action="execute_rollback",
        )
    )

    metrics_claim_gate = _claim_gate_for(metrics_metadata)
    metrics_evidence = _evidence_for(metrics_metadata)
    rollback_claim_gate = _claim_gate_for(rollback_metadata)
    rollback_evidence = _evidence_for(rollback_metadata)

    if metrics_claim_gate.get("local_health_observation_claim_allowed") is not True:
        failures.append("auto_rollback_health_observation_not_recorded")
    if metrics_claim_gate.get("local_metrics_observation_claim_allowed") is not True:
        failures.append("auto_rollback_metrics_observation_not_recorded")
    if metrics_claim_gate.get("live_rollback_execution_claim_allowed") is not False:
        failures.append("auto_rollback_metrics_live_execution_not_blocked")
    if metrics_evidence.get("health_observed") is not True:
        failures.append("auto_rollback_evidence_health_not_recorded")
    if metrics_evidence.get("metrics_observed") is not True:
        failures.append("auto_rollback_evidence_metrics_not_recorded")
    if metrics_result.get("healthy") is not True:
        failures.append("auto_rollback_health_result_not_healthy")
    if metrics_result.get("error_rate") != 0.12:
        failures.append("auto_rollback_error_rate_not_recorded")
    if metrics_result.get("production_readiness_claim_allowed") is not False:
        failures.append("auto_rollback_metrics_result_readiness_not_blocked")
    if metrics_result.get("production_slo_claim_allowed") is not False:
        failures.append("auto_rollback_metrics_result_slo_not_blocked")
    if metrics_result.get("traffic_shift_claim_allowed") is not False:
        failures.append("auto_rollback_metrics_result_traffic_shift_not_blocked")
    if metrics_result.get("live_customer_traffic_proven") is not False:
        failures.append("auto_rollback_metrics_result_customer_traffic_not_blocked")
    if should_rollback is not True:
        failures.append("auto_rollback_recommendation_not_triggered")
    if "Error rate too high" not in reason:
        failures.append("auto_rollback_recommendation_reason_missing")

    if (
        rollback_claim_gate.get("local_rollback_recommendation_claim_allowed")
        is not True
    ):
        failures.append("auto_rollback_recommendation_claim_not_recorded")
    if rollback_claim_gate.get("live_rollback_execution_claim_allowed") is not False:
        failures.append("auto_rollback_live_execution_not_blocked")
    if rollback_claim_gate.get("rollback_command_adapter_configured") is not False:
        failures.append("auto_rollback_command_adapter_not_blocked")
    if rollback_evidence.get("rollback_recommended") is not True:
        failures.append("auto_rollback_evidence_recommendation_not_recorded")
    if rollback_evidence.get("live_rollback_authorized") is not False:
        failures.append("auto_rollback_evidence_live_authorization_not_blocked")
    if rollback_result.get("rollback_recommended") is not True:
        failures.append("auto_rollback_result_recommendation_not_recorded")
    if rollback_result.get("rollback_executed") is not False:
        failures.append("auto_rollback_result_live_execution_not_blocked")
    if rollback_result.get("live_rollback_authorized") is not False:
        failures.append("auto_rollback_result_live_authorization_not_blocked")
    if rollback_result.get("live_rollback_executed") is not False:
        failures.append("auto_rollback_result_live_rollback_not_blocked")
    if rollback_result.get("production_readiness_claim_allowed") is not False:
        failures.append("auto_rollback_result_readiness_not_blocked")
    if rollback_result.get("production_slo_claim_allowed") is not False:
        failures.append("auto_rollback_result_slo_not_blocked")
    if rollback_result.get("traffic_shift_claim_allowed") is not False:
        failures.append("auto_rollback_result_traffic_shift_not_blocked")
    if rollback_result.get("live_customer_traffic_proven") is not False:
        failures.append("auto_rollback_result_customer_traffic_not_blocked")

    retained = bool(metrics_metadata) and bool(rollback_metadata) and not failures
    return {
        "case": "ops_auto_rollback_recommendation_result_metadata",
        "source_agent": "auto-rollback-script",
        "resource": "ops:auto_rollback:recommendation_observation",
        "event_id": "",
        "metadata_retained": retained,
        "result_metadata_retained": retained,
        "failures": failures,
    }


def _run_ops_production_deploy_blocked_preflight_result_case(
    root: Path,
) -> dict[str, Any]:
    async def _blocked_prerequisites() -> bool:
        raise AssertionError("production deploy prerequisites should remain blocked")

    config = ops_production_deploy.DeploymentConfig(allow_live_deploy=False)
    orchestrator = ops_production_deploy.DeploymentOrchestrator(config)
    orchestrator.deployer.check_prerequisites = _blocked_prerequisites

    def _blocked_subprocess(*_args: Any, **_kwargs: Any) -> Any:
        raise AssertionError("production deploy subprocess should remain blocked")

    with patch.object(ops_production_deploy.subprocess, "run", _blocked_subprocess):
        result = asyncio.run(orchestrator.execute_deployment())

    metadata = orchestrator.last_claim_gate.get("safe_actuator_evidence_metadata")
    if not isinstance(metadata, Mapping):
        metadata = {}

    failures = validate_result_metadata(
        metadata,
        expected_component="scripts.deploy.production_deploy",
        expected_action="deploy",
    )
    claim_gate = _claim_gate_for(metadata)
    evidence = _evidence_for(metadata)
    claim_state = orchestrator.last_claim_gate

    if result is not False:
        failures.append("production_deploy_blocked_preflight_result_mismatch")
    if claim_state.get("live_action_authorized") is not False:
        failures.append("production_deploy_live_authorization_not_blocked")
    if claim_state.get("real_readiness_checked") is not False:
        failures.append("production_deploy_real_readiness_unexpectedly_checked")
    if claim_state.get("real_readiness_passed") is not False:
        failures.append("production_deploy_real_readiness_unexpectedly_passed")
    if claim_state.get("production_readiness_claim_allowed") is not False:
        failures.append("production_deploy_claim_state_readiness_not_blocked")
    if claim_state.get("production_slo_claim_allowed") is not False:
        failures.append("production_deploy_claim_state_slo_not_blocked")
    if claim_state.get("traffic_shift_claim_allowed") is not False:
        failures.append("production_deploy_claim_state_traffic_shift_not_blocked")
    if claim_state.get("live_customer_traffic_proven") is not False:
        failures.append("production_deploy_claim_state_customer_traffic_not_blocked")

    if (
        claim_gate.get("local_deployment_command_attempt_claim_allowed")
        is not False
    ):
        failures.append("production_deploy_local_command_attempt_overclaimed")
    if claim_gate.get("local_deployment_command_succeeded") is not False:
        failures.append("production_deploy_local_command_success_overclaimed")
    if (
        claim_gate.get("local_real_readiness_preflight_claim_allowed")
        is not False
    ):
        failures.append("production_deploy_readiness_preflight_overclaimed")
    if claim_gate.get("local_real_readiness_preflight_passed") is not False:
        failures.append("production_deploy_readiness_preflight_passed_overclaimed")
    if claim_gate.get("traffic_shift_claim_allowed") is not False:
        failures.append("production_deploy_traffic_shift_not_blocked")
    if claim_gate.get("live_customer_traffic_claim_allowed") is not False:
        failures.append("production_deploy_customer_traffic_not_blocked")
    if claim_gate.get("production_slo_claim_allowed") is not False:
        failures.append("production_deploy_production_slo_not_blocked")
    if claim_gate.get("production_readiness_claim_allowed") is not False:
        failures.append("production_deploy_production_readiness_not_blocked")
    if evidence.get("live_action_authorized") is not False:
        failures.append("production_deploy_evidence_live_authorization_not_blocked")
    if evidence.get("live_action_executed") is not False:
        failures.append("production_deploy_evidence_live_execution_not_blocked")
    if evidence.get("real_readiness_checked") is not False:
        failures.append("production_deploy_evidence_readiness_unexpectedly_checked")
    if evidence.get("real_readiness_passed") is not False:
        failures.append("production_deploy_evidence_readiness_unexpectedly_passed")

    retained = bool(metadata) and not failures
    return {
        "case": "ops_production_deploy_blocked_preflight_result_metadata",
        "source_agent": "production-deploy-script",
        "resource": "ops:production_deploy:blocked_preflight",
        "event_id": "",
        "metadata_retained": retained,
        "result_metadata_retained": retained,
        "failures": failures,
    }


def build_report(root: Path) -> dict[str, Any]:
    root = root.resolve()
    root.mkdir(parents=True, exist_ok=True)
    cases = [
        _run_spire_server_case(root),
        _run_spire_agent_case(root),
        _run_token_bridge_case(root),
        _run_dao_executor_release_script_case(root),
        _run_dao_proposal_executor_helm_case(root),
        _run_dao_governance_dispatch_case(root),
        _run_governance_contract_create_proposal_case(root),
        _run_ghost_l3_case(root),
        _run_ebpf_recovery_case(root),
        _run_maas_governance_case(root),
        _run_pqc_rotator_case(root),
        _run_mptcp_manager_case(root),
        _run_mesh_action_enforcer_case(root),
        _run_self_healing_mapek_case(root),
        _run_pbft_execute_case(root),
        _run_swarm_mapek_case(root),
        _run_canary_deployment_case(root),
        _run_multi_cloud_deployment_case(root),
        _run_ops_canary_rollout_script_result_case(root),
        _run_ops_production_monitor_health_result_case(root),
        _run_ops_auto_rollback_recommendation_result_case(root),
        _run_ops_production_deploy_blocked_preflight_result_case(root),
    ]
    failures = [
        f"{case['case']}:{failure}"
        for case in cases
        for failure in case.get("failures", [])
    ]
    events_checked = sum(1 for case in cases if case.get("event_id"))
    metadata_events = sum(1 for case in cases if case.get("metadata_retained"))
    result_metadata_cases = sum(
        1 for case in cases if case.get("result_metadata_retained")
    )
    valid = (
        not failures
        and metadata_events == len(cases)
        and events_checked + result_metadata_cases == len(cases)
    )
    return {
        "schema": SCHEMA,
        "status": "VERIFIED HERE" if valid else "BLOCKED",
        "ok": valid,
        "decision": DECISION_RETAINED if valid else DECISION_GAPS,
        "generated_at_utc": utc_now(),
        "claim_boundary": CLAIM_BOUNDARY,
        "summary": {
            "cases_run": len(cases),
            "events_checked": events_checked,
            "result_metadata_cases_checked": result_metadata_cases,
            "metadata_events": metadata_events,
            "claim_gates_fail_closed": valid,
            "local_simulated_harness": True,
            "live_spire_or_dataplane_claimed": False,
            "production_readiness_claimed": False,
        },
        "cases": cases,
        "failures": failures,
    }


def parse_args(argv: Sequence[str] | None = None) -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description="Verify runtime retention of SafeActuator EventBus/result metadata."
    )
    parser.add_argument(
        "--root",
        type=Path,
        default=None,
        help="Temporary verifier root. Defaults to an isolated temp directory.",
    )
    parser.add_argument("--json", action="store_true", help="Write JSON to stdout")
    parser.add_argument(
        "--require-retained",
        action="store_true",
        help="Exit 2 when metadata is not retained in representative smoke cases.",
    )
    parser.add_argument(
        "--output-json",
        default="",
        help="Optional path to write the JSON report.",
    )
    return parser.parse_args(argv)


def _write_output(path_text: str, report: Mapping[str, Any]) -> None:
    output_path = Path(path_text)
    output_path.parent.mkdir(parents=True, exist_ok=True)
    output_path.write_text(
        json.dumps(report, ensure_ascii=True, indent=2) + "\n",
        encoding="utf-8",
    )


def _build_report_for_args(args: argparse.Namespace) -> dict[str, Any]:
    if args.root is not None:
        return build_report(args.root)
    with tempfile.TemporaryDirectory(prefix="x0t-safe-actuator-runtime-") as temp_root:
        return build_report(Path(temp_root))


def main(argv: Sequence[str] | None = None) -> int:
    args = parse_args(argv)
    report = _build_report_for_args(args)
    if args.output_json:
        _write_output(args.output_json, report)
    if args.json or not args.output_json:
        print(json.dumps(report, ensure_ascii=True, indent=2))
    if args.require_retained and not report.get("ok"):
        return 2
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
