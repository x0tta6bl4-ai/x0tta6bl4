#!/usr/bin/env python3
"""Smoke EventBus trace indexing through the Ledger API citation path.

This is a local, no-network smoke scenario. It exercises the FastAPI router
in-memory, writes EventBus history to a temporary directory, indexes the
redacted trace into LedgerRAGSearch, and verifies that /ledger/search returns
an event-backed citation with event_id/source_agent/layer metadata.
"""

from __future__ import annotations

import argparse
import asyncio
import contextlib
import io
import json
import logging
import os
import sys
import tempfile
import warnings
from decimal import Decimal
from pathlib import Path
from types import SimpleNamespace
from typing import Any


ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT))

from fastapi import FastAPI
from httpx import ASGITransport, AsyncClient

from src.api import ledger_endpoints
from src.coordination.events import EventBus, EventType
from src.dao.executor_webhook import DAOExecutor
from src.dao.token_rewards import TokenRewards
from src.integration.spine import (
    AsyncSafeActuator,
    SafeActuator,
    SafeActuatorResult,
)
from src.ledger.rag_search import LedgerRAGSearch
from src.network.mptcp_manager import MPTCPManager
from src.security.spiffe.server.client import SPIREServerClient
from src.security.zero_trust.policy_engine import PolicyAction, PolicyEngine, PolicyRule
from src.self_healing.recovery import (
    RecoveryActionExecutor,
    RecoveryActionType,
    RecoveryResult,
)
from src.services.marketplace_events import publish_marketplace_escrow_event
from src.services.pqc_rotator_service import PQCRotatorService
from src.services.share_to_earn_service import publish_share_to_earn_reward_event


SWARM_SERVICE_NAME = "swarm-pbft"
SWARM_SERVICE_LAYER = "swarm_consensus_to_control_plane"
MARKETPLACE_SERVICE_NAME = "maas-settlement"
MARKETPLACE_SERVICE_LAYER = "commerce_settlement_to_events"
DAO_SERVICE_NAME = "dao-executor"
DAO_SERVICE_LAYER = "dao_to_control_plane"
RECOVERY_SERVICE_NAME = "recovery-action-executor"
RECOVERY_SERVICE_LAYER = "self_healing_to_control_plane"
MESH_REWARD_SERVICE_NAME = "mesh-vpn-bridge"
MESH_REWARD_SERVICE_LAYER = "network_to_rewards"
SHARE_TO_EARN_SERVICE_NAME = "share-to-earn"
SHARE_TO_EARN_SERVICE_LAYER = "network_usage_to_rewards"
MPTCP_SERVICE_NAME = "mptcp-manager"
MPTCP_SERVICE_LAYER = "network_to_control_plane"
MPTCP_ENABLE_RESOURCE = "network:mptcp:enable_mptcp"
SPIRE_SERVER_SERVICE_NAME = "spire-server-client"
SPIRE_SERVER_SERVICE_LAYER = "security_identity_to_control_plane"
SPIRE_SERVER_CREATE_ENTRY_RESOURCE = "identity:spire_server:create_entry"
PQC_ROTATOR_SERVICE_NAME = "pqc-rotator"
PQC_ROTATOR_SERVICE_LAYER = "security_service_to_control_plane"
PQC_ROTATOR_ROTATE_RESOURCE = "services:pqc_rotator:rotate_identity"
PQC_HEALER_SERVICE_NAME = "pqc-zero-trust-executor"
PQC_HEALER_SOURCE_AGENT = "pqc-zero-trust-healer"
PQC_HEALER_SERVICE_LAYER = "self_healing_pqc_identity"
PQC_HEALER_HEALTH_RESOURCE = "self_healing:pqc:perform_health_check"
SEARCH_QUERY = (
    "swarm-pbft maas-settlement dao-executor recovery-action-executor "
    "mesh-vpn-bridge share-to-earn mptcp-manager spire-server-client "
    "pqc-rotator pqc-zero-trust-executor pqc-zero-trust-healer event trace"
)
SECRET_VALUES = (
    "spiffe://secret/workload",
    "did:mesh:secret",
    "0xffffffffffffffffffffffffffffffffffffffff",
)


class _SmokeRAG:
    def __init__(self) -> None:
        self.documents: list[dict[str, Any]] = []

    def add_document(
        self,
        text: str,
        document_id: str,
        metadata: dict[str, Any],
    ) -> list[str]:
        chunk_id = f"{document_id}:chunk-0"
        self.documents.append(
            {
                "text": text,
                "document_id": document_id,
                "metadata": {
                    **metadata,
                    "document_id": document_id,
                    "chunk_id": chunk_id,
                },
            }
        )
        return [chunk_id]

    def retrieve(self, _question: str, top_k: int = 1) -> Any:
        selected = self.documents[:top_k]
        return SimpleNamespace(
            retrieved_chunks=[
                SimpleNamespace(text=document["text"], metadata=document["metadata"])
                for document in selected
            ],
            scores=[1.0 for _document in selected],
            retrieval_time_ms=0.0,
            rerank_time_ms=0.0,
        )


def _build_ledger(temp_root: Path) -> LedgerRAGSearch:
    ledger = LedgerRAGSearch.__new__(LedgerRAGSearch)
    ledger.continuity_file = temp_root / "CONTINUITY.md"
    ledger.verification_root = temp_root / "docs" / "verification"
    ledger.top_k = 30
    ledger.rag = _SmokeRAG()
    ledger._indexed = True
    ledger._verification_indexed = False
    ledger._verification_indexed_files = 0
    ledger._verification_indexed_chunks = 0
    ledger._event_trace_indexed = False
    ledger._event_trace_indexed_events = 0
    ledger._event_trace_indexed_chunks = 0
    ledger._event_trace_indexed_event_ids = set()
    return ledger


def _allow_policy(spiffe_id: str, resource: str) -> PolicyEngine:
    policy = PolicyEngine(default_action=PolicyAction.DENY, enable_opa=False)
    policy.add_rule(
        PolicyRule(
            rule_id=f"allow-{resource}-smoke",
            name=f"Allow {resource} smoke",
            action=PolicyAction.ALLOW,
            spiffe_id_pattern=spiffe_id,
            allowed_resources=[resource],
            priority=1000,
        )
    )
    return policy


def _pqc_zero_trust_executor_class() -> Any:
    oqs_logger = logging.getLogger("oqs.oqs")
    previous_oqs_disabled = oqs_logger.disabled
    oqs_logger.disabled = True
    with (
        warnings.catch_warnings(),
        contextlib.redirect_stdout(io.StringIO()),
        contextlib.redirect_stderr(io.StringIO()),
    ):
        try:
            warnings.filterwarnings(
                "ignore",
                message=r"liboqs version .* differs from liboqs-python version .*",
                category=UserWarning,
                append=False,
            )
            from src.self_healing.pqc_zero_trust_healer import PQCZeroTrustExecutor
        finally:
            oqs_logger.disabled = previous_oqs_disabled

    return PQCZeroTrustExecutor


async def _publish_trace_events(
    bus: EventBus,
    temp_root: Path,
) -> dict[str, dict[str, str]]:
    event = bus.publish(
        EventType.PIPELINE_STAGE_START,
        SWARM_SERVICE_NAME,
        {
            "stage": "consensus",
            "spiffe_id": SECRET_VALUES[0],
            "did": SECRET_VALUES[1],
            "wallet_address": SECRET_VALUES[2],
            "nested": {"spiffe_id": SECRET_VALUES[0]},
        },
    )
    marketplace_event_id = publish_marketplace_escrow_event(
        transition="released",
        source_agent=MARKETPLACE_SERVICE_NAME,
        escrow_id="escrow-smoke-1",
        listing_id="listing-smoke-1",
        renter_id="renter-smoke-1",
        actor_id="settlement-worker",
        currency="X0T",
        status="released",
        spiffe_id=SECRET_VALUES[0],
        did=SECRET_VALUES[1],
        wallet_address=SECRET_VALUES[2],
        amount_token="12.5",
        reason="ledger event trace citation smoke",
        event_bus=bus,
    )
    assert marketplace_event_id is not None

    dao_executor = DAOExecutor.__new__(DAOExecutor)
    dao_executor.event_bus = bus
    dao_executor.source_agent = DAO_SERVICE_NAME
    dao_executor.require_policy = True
    dao_executor.policy_engine = None
    dao_executor.identity = {
        "node_id": DAO_SERVICE_NAME,
        "spiffe_id": SECRET_VALUES[0],
        "did": SECRET_VALUES[1],
        "wallet_address": SECRET_VALUES[2],
    }
    dao_event_id = dao_executor._publish_release_event(
        EventType.TASK_BLOCKED,
        stage="policy_denied",
        context={
            "proposal_id": 404,
            "title": "HELM_UPGRADE smoke denied",
            "script_path": "scripts/release_to_main.sh",
            "api_token": "secret-value-that-must-not-leak",
        },
        success=False,
        reason="policy denied in ledger event trace citation smoke",
        simulated=False,
    )
    assert dao_event_id is not None

    recovery_executor = RecoveryActionExecutor.__new__(RecoveryActionExecutor)
    recovery_executor.event_bus = bus
    recovery_executor.source_agent = RECOVERY_SERVICE_NAME
    recovery_executor.require_policy = True
    recovery_executor.policy_engine = None
    recovery_executor.identity = {
        "node_id": RECOVERY_SERVICE_NAME,
        "spiffe_id": SECRET_VALUES[0],
        "did": SECRET_VALUES[1],
        "wallet_address": SECRET_VALUES[2],
    }
    recovery_result = RecoveryResult(
        success=False,
        action_type=RecoveryActionType.QUARANTINE_NODE,
        duration_seconds=0.0,
        error_message="policy denied in ledger event trace citation smoke",
    )
    recovery_event_id = recovery_executor._publish_recovery_event(
        EventType.TASK_BLOCKED,
        action="Quarantine node",
        action_type=RecoveryActionType.QUARANTINE_NODE,
        context={
            "node_id": "node-smoke-1",
            "reason": "ledger event trace citation smoke",
            "api_token": "secret-value-that-must-not-leak",
        },
        stage="policy_denied",
        result=recovery_result,
        reason=recovery_result.error_message or "",
    )
    assert recovery_event_id is not None

    mesh_rewards = TokenRewards(
        contract_address="0x" + "0" * 40,
        event_bus=bus,
        source_agent=MESH_REWARD_SERVICE_NAME,
        node_id=MESH_REWARD_SERVICE_NAME,
        spiffe_id=SECRET_VALUES[0],
        did=SECRET_VALUES[1],
        wallet_address=SECRET_VALUES[2],
    )
    mesh_reward_result = mesh_rewards.reward_relay(
        node_address="0x1111111111111111111111111111111111111111",
        packets=100,
    )
    mesh_reward_event_id = mesh_reward_result.get("event_id")
    assert mesh_reward_event_id is not None

    env_backup = {
        "SHARE_TO_EARN_SPIFFE_ID": os.environ.get("SHARE_TO_EARN_SPIFFE_ID"),
        "SHARE_TO_EARN_DID": os.environ.get("SHARE_TO_EARN_DID"),
        "SHARE_TO_EARN_WALLET_ADDRESS": os.environ.get(
            "SHARE_TO_EARN_WALLET_ADDRESS"
        ),
    }
    try:
        os.environ["SHARE_TO_EARN_SPIFFE_ID"] = SECRET_VALUES[0]
        os.environ["SHARE_TO_EARN_DID"] = SECRET_VALUES[1]
        os.environ["SHARE_TO_EARN_WALLET_ADDRESS"] = SECRET_VALUES[2]
        share_to_earn_event_id = publish_share_to_earn_reward_event(
            node_id=SHARE_TO_EARN_SERVICE_NAME,
            node_address="0x2222222222222222222222222222222222222222",
            amount=Decimal("0.05"),
            packets=500,
            simulation_enabled=True,
            status="SIMULATED_EARNING",
            event_bus=bus,
        )
    finally:
        for name, value in env_backup.items():
            if value is None:
                os.environ.pop(name, None)
            else:
                os.environ[name] = value
    assert share_to_earn_event_id is not None

    mptcp_result = MPTCPManager.enable_mptcp(
        True,
        event_bus=bus,
        policy_engine=_allow_policy(SECRET_VALUES[0], MPTCP_ENABLE_RESOURCE),
        require_policy=True,
        safe_actuator=SafeActuator(
            lambda _action, _context: SafeActuatorResult(
                success=True,
                reason="ledger event trace citation smoke",
                simulated=False,
            )
        ),
        source_agent=MPTCP_SERVICE_NAME,
        node_id=MPTCP_SERVICE_NAME,
        spiffe_id=SECRET_VALUES[0],
        did=SECRET_VALUES[1],
        wallet_address=SECRET_VALUES[2],
    )
    assert mptcp_result is True
    mptcp_events = bus.get_event_history(
        event_type=EventType.PIPELINE_STAGE_END,
        source_agent=MPTCP_SERVICE_NAME,
    )
    assert mptcp_events
    mptcp_event_id = mptcp_events[-1].event_id

    spire_server = SPIREServerClient(
        spire_server_bin="spire-server",
        event_bus=bus,
        policy_engine=_allow_policy(
            SECRET_VALUES[0],
            SPIRE_SERVER_CREATE_ENTRY_RESOURCE,
        ),
        require_policy=True,
        safe_actuator=SafeActuator(
            lambda _action, _context: SafeActuatorResult(
                success=True,
                reason="ledger event trace citation smoke",
                simulated=False,
            )
        ),
        source_agent=SPIRE_SERVER_SERVICE_NAME,
        node_id=SPIRE_SERVER_SERVICE_NAME,
        spiffe_id=SECRET_VALUES[0],
        did=SECRET_VALUES[1],
        wallet_address=SECRET_VALUES[2],
    )
    spire_server.create_entry(
        "spiffe://x0tta6bl4.mesh/workload/ledger-smoke",
        "spiffe://x0tta6bl4.mesh/node/ledger-smoke",
        {"unix:uid": "1000"},
        ttl=60,
        admin=False,
    )
    spire_events = bus.get_event_history(
        event_type=EventType.PIPELINE_STAGE_END,
        source_agent=SPIRE_SERVER_SERVICE_NAME,
    )
    assert spire_events
    spire_server_event_id = spire_events[-1].event_id

    pqc_rotator = PQCRotatorService(
        identity_file=temp_root / "pqc_identity.txt",
        temp_identity_file=temp_root / "pqc_identity.new",
        signer_cmd=(
            "pqc_signer",
            "--private-key",
            "secret-value-that-must-not-leak",
        ),
        report_generator=None,
        event_bus=bus,
        policy_engine=_allow_policy(SECRET_VALUES[0], PQC_ROTATOR_ROTATE_RESOURCE),
        require_policy=True,
        safe_actuator=AsyncSafeActuator(
            lambda _action, _context: SafeActuatorResult(
                success=True,
                reason="ledger event trace citation smoke",
                simulated=False,
            )
        ),
        source_agent=PQC_ROTATOR_SERVICE_NAME,
        spiffe_id=SECRET_VALUES[0],
        did=SECRET_VALUES[1],
        wallet_address=SECRET_VALUES[2],
    )
    pqc_rotator_result = await pqc_rotator.rotate_once()
    assert pqc_rotator_result["success"] is True
    pqc_rotator_events = bus.get_event_history(
        event_type=EventType.PIPELINE_STAGE_END,
        source_agent=PQC_ROTATOR_SERVICE_NAME,
    )
    assert pqc_rotator_events
    pqc_rotator_event_id = pqc_rotator_events[-1].event_id

    pqc_zero_trust_executor = _pqc_zero_trust_executor_class()
    pqc_healer = pqc_zero_trust_executor(
        pqc_gateway=SimpleNamespace(sessions={}),
        event_bus=bus,
        policy_engine=_allow_policy(SECRET_VALUES[0], PQC_HEALER_HEALTH_RESOURCE),
        require_policy=True,
        source_agent=PQC_HEALER_SOURCE_AGENT,
        node_id=PQC_HEALER_SOURCE_AGENT,
        spiffe_id=SECRET_VALUES[0],
        did=SECRET_VALUES[1],
        wallet_address=SECRET_VALUES[2],
    )
    pqc_healer_result = await pqc_healer.execute(
        {
            "actions": ["full health check"],
            "priority": "medium",
            "estimated_duration": 5,
            "plan_data": {"api_token": "secret-value-that-must-not-leak"},
        }
    )
    assert pqc_healer_result["success"] is True
    pqc_healer_events = bus.get_event_history(
        event_type=EventType.PIPELINE_STAGE_END,
        source_agent=PQC_HEALER_SOURCE_AGENT,
    )
    assert pqc_healer_events
    pqc_healer_event_id = pqc_healer_events[-1].event_id

    return {
        SWARM_SERVICE_NAME: {
            "event_id": event.event_id,
            "layer": SWARM_SERVICE_LAYER,
            "event_type": EventType.PIPELINE_STAGE_START.value,
        },
        MARKETPLACE_SERVICE_NAME: {
            "event_id": marketplace_event_id,
            "layer": MARKETPLACE_SERVICE_LAYER,
            "event_type": EventType.MARKETPLACE_ESCROW_RELEASED.value,
        },
        DAO_SERVICE_NAME: {
            "event_id": dao_event_id,
            "layer": DAO_SERVICE_LAYER,
            "event_type": EventType.TASK_BLOCKED.value,
        },
        RECOVERY_SERVICE_NAME: {
            "event_id": recovery_event_id,
            "layer": RECOVERY_SERVICE_LAYER,
            "event_type": EventType.TASK_BLOCKED.value,
        },
        MESH_REWARD_SERVICE_NAME: {
            "event_id": mesh_reward_event_id,
            "layer": MESH_REWARD_SERVICE_LAYER,
            "event_type": EventType.REWARD_RELAY_RECORDED.value,
        },
        SHARE_TO_EARN_SERVICE_NAME: {
            "event_id": share_to_earn_event_id,
            "layer": SHARE_TO_EARN_SERVICE_LAYER,
            "event_type": EventType.REWARD_RELAY_RECORDED.value,
        },
        MPTCP_SERVICE_NAME: {
            "event_id": mptcp_event_id,
            "layer": MPTCP_SERVICE_LAYER,
            "event_type": EventType.PIPELINE_STAGE_END.value,
        },
        SPIRE_SERVER_SERVICE_NAME: {
            "event_id": spire_server_event_id,
            "layer": SPIRE_SERVER_SERVICE_LAYER,
            "event_type": EventType.PIPELINE_STAGE_END.value,
        },
        PQC_ROTATOR_SERVICE_NAME: {
            "event_id": pqc_rotator_event_id,
            "layer": PQC_ROTATOR_SERVICE_LAYER,
            "event_type": EventType.PIPELINE_STAGE_END.value,
        },
        PQC_HEALER_SOURCE_AGENT: {
            "event_id": pqc_healer_event_id,
            "layer": PQC_HEALER_SERVICE_LAYER,
            "event_type": EventType.PIPELINE_STAGE_END.value,
            "service_name": PQC_HEALER_SERVICE_NAME,
        },
    }


def _patch_ledger_endpoint_dependencies(
    *,
    ledger: LedgerRAGSearch,
    bus: EventBus,
) -> tuple[Any, Any]:
    original_get_ledger_rag = ledger_endpoints.get_ledger_rag
    original_event_bus = ledger_endpoints.EventBus
    ledger_endpoints.get_ledger_rag = lambda: ledger
    ledger_endpoints.EventBus = lambda project_root=".": bus
    return original_get_ledger_rag, original_event_bus


def _restore_ledger_endpoint_dependencies(
    original_get_ledger_rag: Any,
    original_event_bus: Any,
) -> None:
    ledger_endpoints.get_ledger_rag = original_get_ledger_rag
    ledger_endpoints.EventBus = original_event_bus


async def run_smoke(temp_root: Path | None = None) -> dict[str, Any]:
    with tempfile.TemporaryDirectory(prefix="ledger-event-trace-smoke-") as tmp:
        root = temp_root or Path(tmp)
        root.mkdir(parents=True, exist_ok=True)

        bus = EventBus(project_root=str(root))
        expected_events = await _publish_trace_events(bus, root)
        ledger = _build_ledger(root)
        original_get_ledger_rag, original_event_bus = _patch_ledger_endpoint_dependencies(
            ledger=ledger,
            bus=bus,
        )

        app = FastAPI()
        app.include_router(ledger_endpoints.router)

        try:
            async with AsyncClient(
                transport=ASGITransport(app=app),
                base_url="http://ledger-smoke.local",
            ) as client:
                index_response = await client.post(
                    "/api/v1/ledger/event-traces/index",
                    params={"limit": 40},
                )
                index_response.raise_for_status()

                search_response = await client.post(
                    "/api/v1/ledger/search",
                    json={"query": SEARCH_QUERY, "top_k": 30},
                )
                search_response.raise_for_status()
        finally:
            _restore_ledger_endpoint_dependencies(
                original_get_ledger_rag,
                original_event_bus,
            )

        index_body = index_response.json()
        search_body = search_response.json()
        citations = search_body.get("metadata", {}).get("citations") or []
        citations_by_service = {
            citation.get("source_agent"): citation for citation in citations
        }
        response_text = json.dumps(search_body, sort_keys=True)

        assertions = {
            "indexed_successfully": index_body.get("status") == "success",
            "citations_present": len(citations_by_service) >= 10,
            "swarm_event_id_matches": (
                citations_by_service.get(SWARM_SERVICE_NAME, {}).get("event_id")
                == expected_events[SWARM_SERVICE_NAME]["event_id"]
            ),
            "swarm_layer_matches": (
                citations_by_service.get(SWARM_SERVICE_NAME, {}).get("layer")
                == SWARM_SERVICE_LAYER
            ),
            "marketplace_event_id_matches": (
                citations_by_service.get(MARKETPLACE_SERVICE_NAME, {}).get("event_id")
                == expected_events[MARKETPLACE_SERVICE_NAME]["event_id"]
            ),
            "marketplace_layer_matches": (
                citations_by_service.get(MARKETPLACE_SERVICE_NAME, {}).get("layer")
                == MARKETPLACE_SERVICE_LAYER
            ),
            "dao_event_id_matches": (
                citations_by_service.get(DAO_SERVICE_NAME, {}).get("event_id")
                == expected_events[DAO_SERVICE_NAME]["event_id"]
            ),
            "dao_layer_matches": (
                citations_by_service.get(DAO_SERVICE_NAME, {}).get("layer")
                == DAO_SERVICE_LAYER
            ),
            "recovery_event_id_matches": (
                citations_by_service.get(RECOVERY_SERVICE_NAME, {}).get("event_id")
                == expected_events[RECOVERY_SERVICE_NAME]["event_id"]
            ),
            "recovery_layer_matches": (
                citations_by_service.get(RECOVERY_SERVICE_NAME, {}).get("layer")
                == RECOVERY_SERVICE_LAYER
            ),
            "mesh_reward_event_id_matches": (
                citations_by_service.get(MESH_REWARD_SERVICE_NAME, {}).get("event_id")
                == expected_events[MESH_REWARD_SERVICE_NAME]["event_id"]
            ),
            "mesh_reward_layer_matches": (
                citations_by_service.get(MESH_REWARD_SERVICE_NAME, {}).get("layer")
                == MESH_REWARD_SERVICE_LAYER
            ),
            "share_to_earn_event_id_matches": (
                citations_by_service.get(SHARE_TO_EARN_SERVICE_NAME, {}).get(
                    "event_id"
                )
                == expected_events[SHARE_TO_EARN_SERVICE_NAME]["event_id"]
            ),
            "share_to_earn_layer_matches": (
                citations_by_service.get(SHARE_TO_EARN_SERVICE_NAME, {}).get("layer")
                == SHARE_TO_EARN_SERVICE_LAYER
            ),
            "mptcp_event_id_matches": (
                citations_by_service.get(MPTCP_SERVICE_NAME, {}).get("event_id")
                == expected_events[MPTCP_SERVICE_NAME]["event_id"]
            ),
            "mptcp_layer_matches": (
                citations_by_service.get(MPTCP_SERVICE_NAME, {}).get("layer")
                == MPTCP_SERVICE_LAYER
            ),
            "spire_server_event_id_matches": (
                citations_by_service.get(SPIRE_SERVER_SERVICE_NAME, {}).get("event_id")
                == expected_events[SPIRE_SERVER_SERVICE_NAME]["event_id"]
            ),
            "spire_server_layer_matches": (
                citations_by_service.get(SPIRE_SERVER_SERVICE_NAME, {}).get("layer")
                == SPIRE_SERVER_SERVICE_LAYER
            ),
            "pqc_rotator_event_id_matches": (
                citations_by_service.get(PQC_ROTATOR_SERVICE_NAME, {}).get("event_id")
                == expected_events[PQC_ROTATOR_SERVICE_NAME]["event_id"]
            ),
            "pqc_rotator_layer_matches": (
                citations_by_service.get(PQC_ROTATOR_SERVICE_NAME, {}).get("layer")
                == PQC_ROTATOR_SERVICE_LAYER
            ),
            "pqc_healer_event_id_matches": (
                citations_by_service.get(PQC_HEALER_SOURCE_AGENT, {}).get("event_id")
                == expected_events[PQC_HEALER_SOURCE_AGENT]["event_id"]
            ),
            "pqc_healer_layer_matches": (
                citations_by_service.get(PQC_HEALER_SOURCE_AGENT, {}).get("layer")
                == PQC_HEALER_SERVICE_LAYER
            ),
            "pqc_healer_service_name_matches": (
                citations_by_service.get(PQC_HEALER_SOURCE_AGENT, {}).get(
                    "service_name"
                )
                == PQC_HEALER_SERVICE_NAME
            ),
            "source_class_matches": all(
                citation.get("source_class") == "event_trace"
                for citation in citations_by_service.values()
            ),
            "redacted_true": all(
                citation.get("redacted") is True
                for citation in citations_by_service.values()
            ),
            "secret_values_absent": all(
                secret not in response_text for secret in SECRET_VALUES
            ),
        }

        return {
            "status": "PASS" if all(assertions.values()) else "FAIL",
            "scenario": "eventbus_multi_layer_trace_to_ledger_rag_citation",
            "query": SEARCH_QUERY,
            "events": expected_events,
            "event_log": str(bus.event_log_path),
            "index": index_body,
            "citations": citations,
            "citations_by_service": citations_by_service,
            "assertions": assertions,
        }


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(
        description="Smoke EventBus trace indexing through Ledger API citations."
    )
    parser.add_argument(
        "--json",
        action="store_true",
        help="Print machine-readable JSON output.",
    )
    args = parser.parse_args(argv)
    if args.json:
        logging.getLogger().setLevel(logging.ERROR)

    payload = asyncio.run(run_smoke())
    if args.json:
        print(json.dumps(payload, indent=2, sort_keys=True))
    else:
        print(f"status={payload['status']}")
        print(f"events={json.dumps(payload['events'], sort_keys=True)}")
        print(
            "citations_by_service="
            f"{json.dumps(payload['citations_by_service'], sort_keys=True)}"
        )

    return 0 if payload["status"] == "PASS" else 1


if __name__ == "__main__":
    raise SystemExit(main())
