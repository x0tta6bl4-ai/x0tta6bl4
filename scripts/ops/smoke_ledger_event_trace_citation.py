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
import hashlib
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
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker

from src.api import ledger_endpoints
from src.api import maas_billing as maas_billing_api
from src.api import maas_marketplace as maas_marketplace_api
from src.api.maas_governance import _execute_action as execute_maas_governance_action
from src.coordination.events import EventBus, EventType
from src.database import Base, User
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
MARKETPLACE_API_SERVICE_NAME = "maas-marketplace"
MARKETPLACE_API_SERVICE_LAYER = "api_to_commerce"
MAAS_GOVERNANCE_SERVICE_NAME = "maas-governance"
MAAS_GOVERNANCE_SERVICE_LAYER = "api_to_control_plane"
MAAS_GOVERNANCE_UPDATE_CONFIG_RESOURCE = "api:maas_governance:update_config"
MAAS_BILLING_SERVICE_NAME = "maas-billing"
MAAS_BILLING_SERVICE_LAYER = "billing_webhook_to_commerce_bridge"
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
    "swarm-pbft maas-settlement maas-marketplace maas-governance maas-billing "
    "dao-executor recovery-action-executor mesh-vpn-bridge share-to-earn "
    "mptcp-manager spire-server-client "
    "pqc-rotator pqc-zero-trust-executor pqc-zero-trust-healer event trace"
)
CLAIM_BOUNDARY_REQUIRED_SERVICES = frozenset(
    {
        MARKETPLACE_SERVICE_NAME,
        MARKETPLACE_API_SERVICE_NAME,
        MAAS_GOVERNANCE_SERVICE_NAME,
        MAAS_BILLING_SERVICE_NAME,
        DAO_SERVICE_NAME,
        RECOVERY_SERVICE_NAME,
        MESH_REWARD_SERVICE_NAME,
        SHARE_TO_EARN_SERVICE_NAME,
        MPTCP_SERVICE_NAME,
        SPIRE_SERVER_SERVICE_NAME,
        PQC_ROTATOR_SERVICE_NAME,
        PQC_HEALER_SOURCE_AGENT,
    }
)
ECONOMY_SUMMARY_REQUIRED_SERVICES = frozenset(
    {
        MARKETPLACE_SERVICE_NAME,
        MARKETPLACE_API_SERVICE_NAME,
        MAAS_BILLING_SERVICE_NAME,
        MESH_REWARD_SERVICE_NAME,
        SHARE_TO_EARN_SERVICE_NAME,
    }
)
SECRET_VALUES = (
    "spiffe://secret/workload",
    "did:mesh:secret",
    "0xffffffffffffffffffffffffffffffffffffffff",
)
LEAK_SENTINEL = "secret-value-that-must-not-leak"
MARKETPLACE_API_IDEMPOTENCY_KEY = "idem-marketplace-api-smoke-secret"
REDACTION_SENTINELS = (*SECRET_VALUES, LEAK_SENTINEL, MARKETPLACE_API_IDEMPOTENCY_KEY)


def _hash_value(value: Any) -> str | None:
    if value is None:
        return None
    normalized = str(value).strip()
    if not normalized:
        return None
    return hashlib.sha256(normalized.encode("utf-8")).hexdigest()


def _citation_summary_metadata_present(citation: dict[str, Any]) -> bool:
    return (
        isinstance(citation.get("claim_boundary_summary"), dict)
        and isinstance(citation.get("cross_plane_evidence_profile"), dict)
        and isinstance(citation.get("economy_finality_summary"), dict)
    )


def _claim_boundary_summary_is_bounded(citation: dict[str, Any]) -> bool:
    summary = citation.get("claim_boundary_summary")
    if not isinstance(summary, dict):
        return False
    boundaries = summary.get("claim_boundaries")
    limit = summary.get("claim_boundaries_limit")
    total = summary.get("claim_boundaries_total")
    return (
        summary.get("redacted") is True
        and isinstance(boundaries, list)
        and isinstance(limit, int)
        and 0 <= limit <= 8
        and isinstance(total, int)
        and total >= len(boundaries)
        and len(boundaries) <= limit
    )


def _cross_plane_summary_is_fail_closed(citation: dict[str, Any]) -> bool:
    summary = citation.get("cross_plane_evidence_profile")
    if not isinstance(summary, dict):
        return False
    return (
        isinstance(summary.get("primary_status"), str)
        and summary.get("dataplane_confirmed") is False
        and summary.get("settlement_confirmed") is False
        and summary.get("production_ready_candidate") is False
        and summary.get("external_dpi_tested") is False
        and summary.get("dpi_bypass_confirmed") is False
    )


def _economy_summary_is_fail_closed(citation: dict[str, Any]) -> bool:
    summary = citation.get("economy_finality_summary")
    if not isinstance(summary, dict):
        return False
    high_risk_gate = summary.get("high_risk_claim_gate")
    if not isinstance(high_risk_gate, dict):
        return False
    return (
        summary.get("dataplane_confirmed") is False
        and summary.get("settlement_confirmed") is False
        and summary.get("production_ready_candidate") is False
        and high_risk_gate.get("dataplane_delivery_claim_allowed") is False
        and high_risk_gate.get("traffic_delivery_claim_allowed") is False
        and high_risk_gate.get("external_settlement_finality_claim_allowed") is False
        and high_risk_gate.get("token_settlement_finality_claim_allowed") is False
        and high_risk_gate.get("production_readiness_claim_allowed") is False
    )


def _required_services_have_claim_boundaries(
    citations_by_service: dict[str, dict[str, Any]],
) -> bool:
    for service_name in CLAIM_BOUNDARY_REQUIRED_SERVICES:
        summary = citations_by_service.get(service_name, {}).get(
            "claim_boundary_summary"
        )
        if not isinstance(summary, dict) or summary.get("present") is not True:
            return False
    return True


def _required_economy_services_have_local_only_gates(
    citations_by_service: dict[str, dict[str, Any]],
) -> bool:
    for service_name in ECONOMY_SUMMARY_REQUIRED_SERVICES:
        summary = citations_by_service.get(service_name, {}).get(
            "economy_finality_summary"
        )
        if not isinstance(summary, dict):
            return False
        high_risk_gate = summary.get("high_risk_claim_gate")
        if not isinstance(high_risk_gate, dict):
            return False
        if summary.get("present") is not True:
            return False
        if summary.get("local_or_pending_only") is not True:
            return False
        if high_risk_gate.get("present") is not True:
            return False
        if high_risk_gate.get("local_or_pending_economy_claim_allowed") is not True:
            return False
        if not _economy_summary_is_fail_closed(citations_by_service[service_name]):
            return False
    return True


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


class _SmokeGovernanceDB:
    def __init__(self) -> None:
        self.added: list[Any] = []
        self.commits = 0

    def query(self, _model: Any) -> "_SmokeGovernanceDB":
        return self

    def filter(self, *_args: Any, **_kwargs: Any) -> "_SmokeGovernanceDB":
        return self

    def first(self) -> None:
        return None

    def add(self, item: Any) -> None:
        self.added.append(item)

    def commit(self) -> None:
        self.commits += 1


class _SmokeBillingRequest:
    def __init__(self, event_bus: EventBus) -> None:
        self.headers = {"stripe-signature": "smoke-signature"}
        self.state = SimpleNamespace(event_bus=event_bus)
        self.method = "POST"
        self.url = SimpleNamespace(path="/api/v1/maas/billing/webhook/stripe")
        self.client = SimpleNamespace(host="127.0.0.1")

    async def body(self) -> bytes:
        return b"{}"


class _SmokeBillingToken:
    def __init__(self) -> None:
        self.calls: list[tuple[str, float, str]] = []

    def mint(self, account: str, amount: float, reason: str) -> None:
        self.calls.append((account, amount, reason))


class _SmokeBillingBridge:
    def __init__(self) -> None:
        self.mesh_token = _SmokeBillingToken()


def _build_ledger(temp_root: Path) -> LedgerRAGSearch:
    ledger = LedgerRAGSearch.__new__(LedgerRAGSearch)
    ledger.continuity_file = temp_root / "CONTINUITY.md"
    ledger.verification_root = temp_root / "docs" / "verification"
    ledger.current_evidence_root = temp_root / "docs" / "architecture"
    ledger.top_k = 30
    ledger.rag = _SmokeRAG()
    ledger._indexed = True
    ledger._verification_indexed = False
    ledger._verification_indexed_files = 0
    ledger._verification_indexed_chunks = 0
    ledger._current_evidence_indexed = False
    ledger._current_evidence_indexed_files = 0
    ledger._current_evidence_indexed_chunks = 0
    ledger._event_trace_indexed = False
    ledger._event_trace_indexed_events = 0
    ledger._event_trace_indexed_chunks = 0
    ledger._event_trace_indexed_event_ids = set()
    return ledger


def _build_billing_session(temp_root: Path) -> Any:
    db_path = temp_root / "billing_smoke.sqlite3"
    engine = create_engine(f"sqlite:///{db_path}")
    Base.metadata.create_all(bind=engine)
    session_factory = sessionmaker(bind=engine)
    return session_factory()


def _create_billing_user(db: Any) -> User:
    user = User(
        id="billing-smoke-user",
        email="billing-smoke@test.local",
        password_hash="test-hash",
        api_key="billing-smoke-api-key",
        role="user",
        plan="free",
    )
    db.add(user)
    db.commit()
    return user


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
    marketplace_api_event_id = publish_marketplace_escrow_event(
        transition="held",
        source_agent=MARKETPLACE_API_SERVICE_NAME,
        escrow_id="escrow-api-smoke-1",
        listing_id="listing-api-smoke-1",
        renter_id="renter-api-smoke-1",
        actor_id="request-user",
        currency="USD",
        status="held",
        node_id="node-api-smoke-1",
        mesh_id="mesh-api-smoke-1",
        spiffe_id=SECRET_VALUES[0],
        did=SECRET_VALUES[1],
        wallet_address=SECRET_VALUES[2],
        amount_cents=2500,
        request_evidence={
            "action": "rent_node",
            "route": "POST /rent/{listing_id}",
            "actor_role": "user",
            "request_scope_hash": _hash_value(
                "listing-api-smoke-1:mesh-api-smoke-1:1"
            ),
            "idempotency_key_present": True,
            "idempotency_key_hash": _hash_value(MARKETPLACE_API_IDEMPOTENCY_KEY),
            "idempotency_key": MARKETPLACE_API_IDEMPOTENCY_KEY,
            "db_write_ready": True,
            "listing_status": "available",
            "currency": "USD",
            "hours": 1,
            "renter_matches_listing": False,
            "admin_override": False,
            "service_identity_present": {
                "spiffe_id": True,
                "did": True,
                "wallet_address": True,
            },
            "listing_id": "listing-api-smoke-1",
        },
        reason="route-only marketplace API event trace citation smoke",
        event_bus=bus,
    )
    assert marketplace_api_event_id is not None

    governance_db = _SmokeGovernanceDB()
    governance_result = execute_maas_governance_action(
        {
            "type": "update_config",
            "params": {
                "key": "global_price_multiplier",
                "value": 1.25,
                "api_token": LEAK_SENTINEL,
            },
        },
        governance_db,
        event_bus=bus,
        policy_engine=_allow_policy(
            SECRET_VALUES[0],
            MAAS_GOVERNANCE_UPDATE_CONFIG_RESOURCE,
        ),
        require_policy=True,
        spiffe_id=SECRET_VALUES[0],
        did=SECRET_VALUES[1],
        wallet_address=SECRET_VALUES[2],
        proposal_id="proposal-smoke-1",
        user_id="user-smoke-1",
    )
    assert governance_result["success"] is True
    assert governance_db.commits == 1
    governance_events = bus.get_event_history(
        event_type=EventType.PIPELINE_STAGE_END,
        source_agent=MAAS_GOVERNANCE_SERVICE_NAME,
    )
    assert governance_events
    governance_event_id = governance_events[-1].event_id

    billing_db = _build_billing_session(temp_root)
    billing_bind = billing_db.get_bind()
    billing_bridge = _SmokeBillingBridge()
    original_webhook_secret = maas_billing_api.STRIPE_WEBHOOK_SECRET
    original_construct_event = maas_billing_api.stripe.Webhook.construct_event
    original_token_bridge = maas_marketplace_api._get_token_bridge
    try:
        billing_user = _create_billing_user(billing_db)
        billing_event = {
            "id": "evt-billing-smoke-1",
            "type": "checkout.session.completed",
            "data": {
                "object": {
                    "id": "cs-billing-smoke-1",
                    "mode": "subscription",
                    "payment_status": "paid",
                    "subscription": "sub-billing-smoke-1",
                    "currency": "usd",
                    "amount_total": 1300,
                    "metadata": {
                        "user_id": billing_user.id,
                        "plan": "starter",
                        "bridge_x0t": "true",
                    },
                },
            },
        }
        maas_billing_api.STRIPE_WEBHOOK_SECRET = "whsec_smoke"
        maas_billing_api.stripe.Webhook.construct_event = (
            lambda *_args, **_kwargs: billing_event
        )
        maas_marketplace_api._get_token_bridge = lambda: billing_bridge
        billing_result = await maas_billing_api.stripe_webhook(
            _SmokeBillingRequest(bus),
            billing_db,
        )
    finally:
        maas_billing_api.STRIPE_WEBHOOK_SECRET = original_webhook_secret
        maas_billing_api.stripe.Webhook.construct_event = original_construct_event
        maas_marketplace_api._get_token_bridge = original_token_bridge
        billing_db.close()
        billing_bind.dispose()
    assert billing_result["status"] == "success"
    assert billing_bridge.mesh_token.calls == [
        ("billing-smoke-user", 1300.0, "stripe_payment_cs-billing-smoke-1")
    ]
    billing_events = bus.get_event_history(
        event_type=EventType.PIPELINE_STAGE_END,
        source_agent=MAAS_BILLING_SERVICE_NAME,
    )
    assert billing_events
    billing_event_id = billing_events[-1].event_id

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
            "api_token": LEAK_SENTINEL,
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
    recovery_executor._post_action_probe_config_source = "constructor"
    recovery_executor.enable_post_action_dataplane_probe = False
    recovery_executor.post_action_dataplane_probe_provider = None
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
            "api_token": LEAK_SENTINEL,
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
    mesh_relay_evidence = bus.publish(
        EventType.PIPELINE_STAGE_END,
        MESH_REWARD_SERVICE_NAME,
        {
            "component": "network.mesh_vpn_bridge",
            "stage": "relay_reward_observed",
            "operation": "network_usage_reward",
            "operation_resource": "relay_packet_threshold",
            "resource": "network:mesh_vpn_bridge:relay_packet_threshold",
            "node_id": MESH_REWARD_SERVICE_NAME,
            "spiffe_id": SECRET_VALUES[0],
            "did": SECRET_VALUES[1],
            "wallet_address": SECRET_VALUES[2],
            "identity": {
                "node_id": MESH_REWARD_SERVICE_NAME,
                "spiffe_id": SECRET_VALUES[0],
                "did": SECRET_VALUES[1],
                "wallet_address": SECRET_VALUES[2],
            },
            "direction": "upstream",
            "peer_id_hash": _hash_value("mesh-smoke-peer"),
            "peer_id_redacted": True,
            "reward_packets": 100,
            "packet_threshold": 100,
            "packets_relayed_total": 100,
            "bytes_relayed_total": 4096,
            "last_chunk_bytes": 4096,
            "routing_mode": "mesh_peer",
            "reward_address_hash": _hash_value(
                "0x1111111111111111111111111111111111111111"
            ),
            "payloads_redacted": True,
            "safe_observation": True,
            "claim_boundary": (
                "Mesh VPN bridge relay reward observation only. It records a "
                "bounded local packet-threshold observation used as upstream "
                "evidence for TokenRewards; it does not prove customer traffic, "
                "external reachability, or live token settlement."
            ),
        },
    )
    mesh_reward_result = mesh_rewards.reward_relay(
        node_address="0x1111111111111111111111111111111111111111",
        packets=100,
        upstream_event_ids=[mesh_relay_evidence.event_id],
        upstream_source_agents=[MESH_REWARD_SERVICE_NAME],
    )
    mesh_reward_event_id = mesh_reward_result.get("event_id")
    assert mesh_reward_event_id is not None
    mesh_reward_event = [
        event
        for event in bus.get_event_history(
            event_type=EventType.REWARD_RELAY_RECORDED,
            source_agent=MESH_REWARD_SERVICE_NAME,
            limit=20,
        )
        if event.event_id == mesh_reward_event_id
    ][0]
    mesh_reward_upstream = mesh_reward_event.data.get("upstream_evidence", {})

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
            LEAK_SENTINEL,
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
            "plan_data": {"api_token": LEAK_SENTINEL},
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
        MARKETPLACE_API_SERVICE_NAME: {
            "event_id": marketplace_api_event_id,
            "layer": MARKETPLACE_API_SERVICE_LAYER,
            "event_type": EventType.MARKETPLACE_ESCROW_HELD.value,
        },
        MAAS_GOVERNANCE_SERVICE_NAME: {
            "event_id": governance_event_id,
            "layer": MAAS_GOVERNANCE_SERVICE_LAYER,
            "event_type": EventType.PIPELINE_STAGE_END.value,
        },
        MAAS_BILLING_SERVICE_NAME: {
            "event_id": billing_event_id,
            "layer": MAAS_BILLING_SERVICE_LAYER,
            "event_type": EventType.PIPELINE_STAGE_END.value,
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
            "upstream_event_id": mesh_relay_evidence.event_id,
            "upstream_event_linked": (
                mesh_relay_evidence.event_id
                in mesh_reward_upstream.get("event_ids", [])
            ),
            "upstream_source_agent_linked": (
                MESH_REWARD_SERVICE_NAME
                in mesh_reward_upstream.get("source_agents", [])
            ),
            "upstream_payloads_redacted": (
                mesh_reward_upstream.get("payloads_redacted") is True
            ),
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


def _prepare_smoke_root(root: Path) -> None:
    root.mkdir(parents=True, exist_ok=True)
    event_log = root / ".agent_coordination" / "events.log"
    event_log.unlink(missing_ok=True)


async def run_smoke(temp_root: Path | None = None) -> dict[str, Any]:
    with tempfile.TemporaryDirectory(
        prefix="ledger-event-trace-smoke-",
        ignore_cleanup_errors=True,
    ) as tmp:
        root = temp_root or Path(tmp)
        _prepare_smoke_root(root)

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
            "citations_present": len(citations_by_service) >= 13,
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
            "marketplace_api_event_id_matches": (
                citations_by_service.get(MARKETPLACE_API_SERVICE_NAME, {}).get(
                    "event_id"
                )
                == expected_events[MARKETPLACE_API_SERVICE_NAME]["event_id"]
            ),
            "marketplace_api_layer_matches": (
                citations_by_service.get(MARKETPLACE_API_SERVICE_NAME, {}).get("layer")
                == MARKETPLACE_API_SERVICE_LAYER
            ),
            "marketplace_api_evidence_summary_request_present": (
                citations_by_service.get(MARKETPLACE_API_SERVICE_NAME, {})
                .get("evidence_summary", {})
                .get("request_evidence", {})
                .get("present")
                is True
            ),
            "marketplace_api_evidence_summary_idempotency_present": (
                citations_by_service.get(MARKETPLACE_API_SERVICE_NAME, {})
                .get("evidence_summary", {})
                .get("request_evidence", {})
                .get("idempotency_key_present")
                is True
            ),
            "marketplace_api_evidence_summary_identity_present": (
                citations_by_service.get(MARKETPLACE_API_SERVICE_NAME, {})
                .get("evidence_summary", {})
                .get("request_evidence", {})
                .get("service_identity_present")
                == {
                    "spiffe_id": True,
                    "did": True,
                    "wallet_address": True,
                }
            ),
            "maas_governance_event_id_matches": (
                citations_by_service.get(MAAS_GOVERNANCE_SERVICE_NAME, {}).get(
                    "event_id"
                )
                == expected_events[MAAS_GOVERNANCE_SERVICE_NAME]["event_id"]
            ),
            "maas_governance_layer_matches": (
                citations_by_service.get(MAAS_GOVERNANCE_SERVICE_NAME, {}).get("layer")
                == MAAS_GOVERNANCE_SERVICE_LAYER
            ),
            "maas_billing_event_id_matches": (
                citations_by_service.get(MAAS_BILLING_SERVICE_NAME, {}).get(
                    "event_id"
                )
                == expected_events[MAAS_BILLING_SERVICE_NAME]["event_id"]
            ),
            "maas_billing_layer_matches": (
                citations_by_service.get(MAAS_BILLING_SERVICE_NAME, {}).get("layer")
                == MAAS_BILLING_SERVICE_LAYER
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
            "mesh_reward_upstream_event_id_matches": expected_events[
                MESH_REWARD_SERVICE_NAME
            ]["upstream_event_linked"],
            "mesh_reward_upstream_source_agent_matches": expected_events[
                MESH_REWARD_SERVICE_NAME
            ]["upstream_source_agent_linked"],
            "mesh_reward_upstream_payloads_redacted": expected_events[
                MESH_REWARD_SERVICE_NAME
            ]["upstream_payloads_redacted"],
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
            "citation_summary_metadata_present": all(
                _citation_summary_metadata_present(citation)
                for citation in citations_by_service.values()
            ),
            "claim_boundary_summaries_bounded": all(
                _claim_boundary_summary_is_bounded(citation)
                for citation in citations_by_service.values()
            ),
            "claim_boundaries_present_for_bounded_services": (
                _required_services_have_claim_boundaries(citations_by_service)
            ),
            "cross_plane_summaries_fail_closed": all(
                _cross_plane_summary_is_fail_closed(citation)
                for citation in citations_by_service.values()
            ),
            "economy_summaries_fail_closed": all(
                _economy_summary_is_fail_closed(citation)
                for citation in citations_by_service.values()
            ),
            "economy_services_have_local_only_gates": (
                _required_economy_services_have_local_only_gates(
                    citations_by_service
                )
            ),
            "secret_values_absent": all(
                secret not in response_text for secret in REDACTION_SENTINELS
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
