"""Unit tests for marketplace settlement fail-closed bridge handling."""

from types import SimpleNamespace
from unittest.mock import AsyncMock, MagicMock, patch
import sys

import pytest

from src.coordination.events import EventBus, EventType
from src.services import marketplace_settlement as settlement


class _FakeQuery:
    def __init__(self, rows):
        self._rows = rows

    def filter(self, *args, **kwargs):
        return self

    def all(self):
        return list(self._rows)

    def first(self):
        return self._rows[0] if self._rows else None


class _FakeDb:
    def __init__(self, escrow, listing):
        self.escrow = escrow
        self.listing = listing
        self.commits = 0
        self.closed = False

    def query(self, model):
        if model is settlement.MarketplaceEscrow:
            return _FakeQuery([self.escrow])
        if model is settlement.MarketplaceListing:
            return _FakeQuery([self.listing])
        return _FakeQuery([])

    def commit(self):
        self.commits += 1

    def close(self):
        self.closed = True


async def _stop_after_one_iteration(_seconds):
    raise StopAsyncIteration


def _settings_module():
    return SimpleNamespace(
        settings=SimpleNamespace(
            rpc_url="",
            contract_address="",
            operator_private_key="",
        )
    )


def _assert_settlement_runtime_evidence(
    evidence,
    *,
    action: str,
    bridge_attempted: bool,
    bridge_status: str,
    db_write_attempted: bool,
    db_committed: bool,
    escrow_status_after: str,
    listing_status_after: str,
):
    assert evidence["settlement_action"] == action
    assert evidence["duration_ms"] >= 0
    assert evidence["bridge_evidence"] == {
        "attempted": bridge_attempted,
        "status": bridge_status,
        "source_agent": "token-bridge" if bridge_attempted else None,
        "payloads_redacted": True,
    }
    assert evidence["db_write_evidence"] == {
        "storage_backend": "sqlalchemy",
        "attempted": db_write_attempted,
        "committed": db_committed,
        "payloads_redacted": True,
    }
    assert evidence["output_summary"] == {
        "escrow_status_after": escrow_status_after,
        "listing_status_after": listing_status_after,
        "raw_identifiers_redacted": True,
        "payloads_redacted": True,
    }
    local_lifecycle_claim_allowed = bool(
        db_committed and action in {"release", "refund"}
    )
    assert evidence["claim_gate"] == {
        "decision": (
            "local_escrow_lifecycle_only"
            if local_lifecycle_claim_allowed
            else "blocked_or_uncommitted"
        ),
        "local_escrow_lifecycle_claim_allowed": local_lifecycle_claim_allowed,
        "traffic_delivery_claim_allowed": False,
        "dataplane_delivery_claim_allowed": False,
        "external_settlement_finality_claim_allowed": False,
        "production_readiness_claim_allowed": False,
        "requires_dataplane_evidence_for_delivery_claim": True,
        "requires_external_finality_evidence_for_settlement_claim": True,
        "requires_cross_plane_proof_gate_for_high_risk_claims": True,
        "upstream_high_risk_claims_present": False,
        "blocker_reason_ids": list(
            settlement._SETTLEMENT_HIGH_RISK_BLOCKER_REASON_IDS
        ),
        "bridge_status": bridge_status,
        "raw_identifiers_redacted": True,
        "payloads_redacted": True,
        "claim_boundary": settlement._SETTLEMENT_CLAIM_GATE_BOUNDARY,
    }
    assert evidence["raw_identifiers_redacted"] is True
    assert evidence["payloads_redacted"] is True


def test_settlement_runtime_evidence_never_promotes_high_risk_claims():
    evidence = settlement._settlement_runtime_evidence(
        {
            "dataplane_confirmed": True,
            "traffic_delivery_claim_allowed": True,
            "chain_finality_confirmed": True,
            "external_settlement_finality_claim_allowed": True,
            "payloads_redacted": True,
            "raw_identifiers_redacted": True,
        },
        action="release",
        started_at=0.0,
        bridge_attempted=True,
        bridge_status="released",
        db_write_attempted=True,
        db_committed=True,
        escrow_status_after="released",
        listing_status_after="rented",
    )

    claim_gate = evidence["claim_gate"]
    assert claim_gate["local_escrow_lifecycle_claim_allowed"] is True
    assert claim_gate["traffic_delivery_claim_allowed"] is False
    assert claim_gate["dataplane_delivery_claim_allowed"] is False
    assert claim_gate["external_settlement_finality_claim_allowed"] is False
    assert claim_gate["production_readiness_claim_allowed"] is False
    assert claim_gate["requires_cross_plane_proof_gate_for_high_risk_claims"] is True
    assert claim_gate["upstream_high_risk_claims_present"] is True
    assert claim_gate["blocker_reason_ids"] == list(
        settlement._SETTLEMENT_HIGH_RISK_BLOCKER_REASON_IDS
    )


@pytest.fixture(autouse=True)
def _reset_token_bridge_cache(monkeypatch):
    monkeypatch.setattr(settlement, "_token_bridge", None)


@pytest.mark.asyncio
async def test_x0t_release_rejection_keeps_escrow_held(monkeypatch):
    escrow = SimpleNamespace(
        id="escrow-x0t-release",
        listing_id="listing-1",
        renter_id="renter-1",
        currency="X0T",
        status="held",
        released_at=None,
    )
    listing = SimpleNamespace(
        id="listing-1",
        node_id="node-1",
        status="escrow",
        renter_id="renter-1",
    )
    db = _FakeDb(escrow, listing)
    bridge = SimpleNamespace(
        release_escrow_on_chain=AsyncMock(return_value=False),
        refund_escrow_on_chain=AsyncMock(return_value=True),
        last_chain_write_event_ids=["evt-bridge-release-request", "evt-bridge-release-failed"],
        source_agent="token-bridge",
    )
    publish_event = MagicMock(return_value="evt-blocked-release")

    monkeypatch.setattr(settlement, "SessionLocal", lambda: db)
    monkeypatch.setattr(settlement, "TokenBridge", MagicMock(return_value=bridge))
    monkeypatch.setattr(settlement, "MeshToken", MagicMock())
    monkeypatch.setattr(settlement, "BridgeConfig", MagicMock())
    monkeypatch.setattr(settlement.uptime_tracker, "get_uptime_percent", lambda _node_id: 1.0)
    monkeypatch.setattr(settlement, "publish_marketplace_escrow_event", publish_event)
    monkeypatch.setattr(settlement, "record_audit_log", MagicMock())
    monkeypatch.setattr(settlement.asyncio, "sleep", _stop_after_one_iteration)
    monkeypatch.setenv("MAAS_SETTLEMENT_SPIFFE_ID", "spiffe://mesh.x0tta6bl4.mesh/workload/settlement")
    monkeypatch.setenv("MAAS_SETTLEMENT_DID", "did:mesh:pqc:settlement")
    monkeypatch.setenv("MAAS_SETTLEMENT_WALLET_ADDRESS", "0xbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbb")

    with patch.dict(sys.modules, {"src.core.settings": _settings_module()}):
        with pytest.raises(StopAsyncIteration):
            await settlement.marketplace_settlement_loop()

    bridge.release_escrow_on_chain.assert_awaited_once_with("escrow-x0t-release")
    assert escrow.status == "held"
    assert escrow.released_at is None
    assert listing.status == "escrow"
    assert db.commits == 0
    assert db.closed is True
    publish_event.assert_called_once()
    assert publish_event.call_args.kwargs["transition"] == "blocked"
    assert publish_event.call_args.kwargs["reason"] == "release_bridge_rejected"
    assert publish_event.call_args.kwargs["spiffe_id"] == "spiffe://mesh.x0tta6bl4.mesh/workload/settlement"
    assert publish_event.call_args.kwargs["did"] == "did:mesh:pqc:settlement"
    assert publish_event.call_args.kwargs["wallet_address"] == "0xbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbb"
    assert publish_event.call_args.kwargs["upstream_event_ids"] == [
        "evt-bridge-release-request",
        "evt-bridge-release-failed",
    ]
    assert publish_event.call_args.kwargs["upstream_source_agents"] == ["token-bridge"]
    _assert_settlement_runtime_evidence(
        publish_event.call_args.kwargs["settlement_evidence"],
        action="release",
        bridge_attempted=True,
        bridge_status="rejected",
        db_write_attempted=False,
        db_committed=False,
        escrow_status_after="held",
        listing_status_after="escrow",
    )


@pytest.mark.asyncio
async def test_x0t_release_bridge_init_error_keeps_escrow_held(monkeypatch):
    escrow = SimpleNamespace(
        id="escrow-x0t-init-error",
        listing_id="listing-1",
        renter_id="renter-1",
        currency="X0T",
        status="held",
        released_at=None,
    )
    listing = SimpleNamespace(
        id="listing-1",
        node_id="node-1",
        status="escrow",
        renter_id="renter-1",
    )
    db = _FakeDb(escrow, listing)
    publish_event = MagicMock(return_value="evt-blocked-init-error")

    monkeypatch.setattr(settlement, "SessionLocal", lambda: db)
    monkeypatch.setattr(settlement, "TokenBridge", MagicMock(side_effect=RuntimeError("bridge config invalid")))
    monkeypatch.setattr(settlement, "MeshToken", MagicMock())
    monkeypatch.setattr(settlement, "BridgeConfig", MagicMock())
    monkeypatch.setattr(settlement.uptime_tracker, "get_uptime_percent", lambda _node_id: 1.0)
    monkeypatch.setattr(settlement, "publish_marketplace_escrow_event", publish_event)
    monkeypatch.setattr(settlement, "record_audit_log", MagicMock())
    monkeypatch.setattr(settlement.asyncio, "sleep", _stop_after_one_iteration)

    with patch.dict(sys.modules, {"src.core.settings": _settings_module()}):
        with pytest.raises(StopAsyncIteration):
            await settlement.marketplace_settlement_loop()

    assert escrow.status == "held"
    assert escrow.released_at is None
    assert listing.status == "escrow"
    assert db.commits == 0
    assert db.closed is True
    publish_event.assert_called_once()
    assert publish_event.call_args.kwargs["transition"] == "blocked"
    assert publish_event.call_args.kwargs["reason"] == "release_bridge_error"
    _assert_settlement_runtime_evidence(
        publish_event.call_args.kwargs["settlement_evidence"],
        action="release",
        bridge_attempted=True,
        bridge_status="error",
        db_write_attempted=False,
        db_committed=False,
        escrow_status_after="held",
        listing_status_after="escrow",
    )


@pytest.mark.asyncio
async def test_x0t_refund_rejection_keeps_escrow_held(monkeypatch):
    escrow = SimpleNamespace(
        id="escrow-x0t-refund",
        listing_id="listing-1",
        renter_id="renter-1",
        currency="X0T",
        status="held",
        released_at=None,
    )
    listing = SimpleNamespace(
        id="listing-1",
        node_id="node-1",
        status="escrow",
        renter_id="renter-1",
    )
    db = _FakeDb(escrow, listing)
    bridge = SimpleNamespace(
        release_escrow_on_chain=AsyncMock(return_value=True),
        refund_escrow_on_chain=AsyncMock(return_value=False),
        last_chain_write_event_ids=["evt-bridge-refund-request", "evt-bridge-refund-failed"],
        source_agent="token-bridge",
    )
    publish_event = MagicMock(return_value="evt-blocked-refund")

    monkeypatch.setattr(settlement, "SessionLocal", lambda: db)
    monkeypatch.setattr(settlement, "TokenBridge", MagicMock(return_value=bridge))
    monkeypatch.setattr(settlement, "MeshToken", MagicMock())
    monkeypatch.setattr(settlement, "BridgeConfig", MagicMock())
    monkeypatch.setattr(settlement.uptime_tracker, "get_uptime_percent", lambda _node_id: 0.0)
    monkeypatch.setattr(settlement, "publish_marketplace_escrow_event", publish_event)
    monkeypatch.setattr(settlement, "record_audit_log", MagicMock())
    monkeypatch.setattr(settlement.asyncio, "sleep", _stop_after_one_iteration)

    with patch.dict(sys.modules, {"src.core.settings": _settings_module()}):
        with pytest.raises(StopAsyncIteration):
            await settlement.marketplace_settlement_loop()

    bridge.refund_escrow_on_chain.assert_awaited_once_with("escrow-x0t-refund")
    assert escrow.status == "held"
    assert listing.status == "escrow"
    assert listing.renter_id == "renter-1"
    assert db.commits == 0
    assert db.closed is True
    publish_event.assert_called_once()
    assert publish_event.call_args.kwargs["transition"] == "blocked"
    assert publish_event.call_args.kwargs["reason"] == "refund_bridge_rejected"
    assert publish_event.call_args.kwargs["upstream_event_ids"] == [
        "evt-bridge-refund-request",
        "evt-bridge-refund-failed",
    ]
    assert publish_event.call_args.kwargs["upstream_source_agents"] == ["token-bridge"]
    _assert_settlement_runtime_evidence(
        publish_event.call_args.kwargs["settlement_evidence"],
        action="refund",
        bridge_attempted=True,
        bridge_status="rejected",
        db_write_attempted=False,
        db_committed=False,
        escrow_status_after="held",
        listing_status_after="escrow",
    )


@pytest.mark.asyncio
async def test_x0t_release_success_links_bridge_evidence_to_settlement_event(monkeypatch):
    escrow = SimpleNamespace(
        id="escrow-x0t-release-ok",
        listing_id="listing-1",
        renter_id="renter-1",
        currency="X0T",
        status="held",
        released_at=None,
        amount_cents=None,
        amount_token=12.5,
    )
    listing = SimpleNamespace(
        id="listing-1",
        node_id="node-1",
        status="escrow",
        renter_id="renter-1",
        mesh_id="mesh-1",
    )
    db = _FakeDb(escrow, listing)
    bridge = SimpleNamespace(
        release_escrow_on_chain=AsyncMock(return_value=True),
        refund_escrow_on_chain=AsyncMock(return_value=False),
        last_chain_write_event_ids=["evt-bridge-release-end", "evt-bridge-marketplace"],
        source_agent="token-bridge",
    )
    publish_event = MagicMock(return_value="evt-settlement-release")

    monkeypatch.setattr(settlement, "SessionLocal", lambda: db)
    monkeypatch.setattr(settlement, "TokenBridge", MagicMock(return_value=bridge))
    monkeypatch.setattr(settlement, "MeshToken", MagicMock())
    monkeypatch.setattr(settlement, "BridgeConfig", MagicMock())
    monkeypatch.setattr(settlement.uptime_tracker, "get_uptime_percent", lambda _node_id: 1.0)
    monkeypatch.setattr(settlement, "publish_marketplace_escrow_event", publish_event)
    monkeypatch.setattr(settlement, "record_audit_log", MagicMock())
    monkeypatch.setattr(settlement.asyncio, "sleep", _stop_after_one_iteration)

    with patch.dict(sys.modules, {"src.core.settings": _settings_module()}):
        with pytest.raises(StopAsyncIteration):
            await settlement.marketplace_settlement_loop()

    bridge.release_escrow_on_chain.assert_awaited_once_with("escrow-x0t-release-ok")
    assert escrow.status == "released"
    assert listing.status == "rented"
    assert db.commits == 1
    publish_event.assert_called_once()
    kwargs = publish_event.call_args.kwargs
    assert kwargs["transition"] == "released"
    assert kwargs["reason"] == "uptime_threshold_met"
    assert kwargs["amount_token"] == 12.5
    assert kwargs["upstream_event_ids"] == [
        "evt-bridge-release-end",
        "evt-bridge-marketplace",
    ]
    assert kwargs["upstream_source_agents"] == ["token-bridge"]
    _assert_settlement_runtime_evidence(
        kwargs["settlement_evidence"],
        action="release",
        bridge_attempted=True,
        bridge_status="released",
        db_write_attempted=True,
        db_committed=True,
        escrow_status_after="released",
        listing_status_after="rented",
    )


@pytest.mark.asyncio
async def test_usd_release_success_publishes_settlement_event(monkeypatch):
    escrow = SimpleNamespace(
        id="escrow-usd-release",
        listing_id="listing-1",
        renter_id="renter-1",
        currency="USD",
        status="held",
        released_at=None,
        amount_cents=1000,
        amount_token=None,
    )
    listing = SimpleNamespace(
        id="listing-1",
        node_id="node-1",
        status="escrow",
        renter_id="renter-1",
        mesh_id="mesh-1",
    )
    db = _FakeDb(escrow, listing)
    publish_event = MagicMock(return_value="evt-settlement-release")
    token_bridge_ctor = MagicMock()

    monkeypatch.setattr(settlement, "SessionLocal", lambda: db)
    monkeypatch.setattr(settlement, "TokenBridge", token_bridge_ctor)
    monkeypatch.setattr(settlement, "MeshToken", MagicMock())
    monkeypatch.setattr(settlement, "BridgeConfig", MagicMock())
    monkeypatch.setattr(settlement.uptime_tracker, "get_uptime_percent", lambda _node_id: 1.0)
    monkeypatch.setattr(settlement, "publish_marketplace_escrow_event", publish_event)
    monkeypatch.setattr(settlement, "record_audit_log", MagicMock())
    monkeypatch.setattr(settlement.asyncio, "sleep", _stop_after_one_iteration)
    monkeypatch.setenv("MAAS_SETTLEMENT_SPIFFE_ID", "spiffe://mesh.x0tta6bl4.mesh/workload/settlement")
    monkeypatch.setenv("MAAS_SETTLEMENT_DID", "did:mesh:pqc:settlement")
    monkeypatch.setenv("MAAS_SETTLEMENT_WALLET_ADDRESS", "0xbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbb")

    with patch.dict(sys.modules, {"src.core.settings": _settings_module()}):
        with pytest.raises(StopAsyncIteration):
            await settlement.marketplace_settlement_loop()

    assert escrow.status == "released"
    assert listing.status == "rented"
    assert db.commits == 1
    token_bridge_ctor.assert_not_called()
    publish_event.assert_called_once()
    kwargs = publish_event.call_args.kwargs
    assert kwargs["transition"] == "released"
    assert kwargs["source_agent"] == "maas-settlement"
    assert kwargs["escrow_id"] == "escrow-usd-release"
    assert kwargs["listing_id"] == "listing-1"
    assert kwargs["renter_id"] == "renter-1"
    assert kwargs["reason"] == "uptime_threshold_met"
    assert kwargs["spiffe_id"] == "spiffe://mesh.x0tta6bl4.mesh/workload/settlement"
    assert kwargs["did"] == "did:mesh:pqc:settlement"
    assert kwargs["wallet_address"] == "0xbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbb"
    _assert_settlement_runtime_evidence(
        kwargs["settlement_evidence"],
        action="release",
        bridge_attempted=False,
        bridge_status="not_required",
        db_write_attempted=True,
        db_committed=True,
        escrow_status_after="released",
        listing_status_after="rented",
    )


@pytest.mark.asyncio
async def test_usd_release_links_telemetry_evidence_to_settlement_event(monkeypatch, tmp_path):
    bus = EventBus(project_root=str(tmp_path))
    telemetry_event = bus.publish(
        EventType.PIPELINE_STAGE_END,
        "maas-telemetry",
        {
            "operation": "telemetry_snapshot_write",
            "node_id_hash": settlement._redacted_sha256_prefix("node-telemetry-1"),
        },
    )
    escrow = SimpleNamespace(
        id="escrow-usd-release-telemetry",
        listing_id="listing-telemetry-1",
        renter_id="renter-telemetry-1",
        currency="USD",
        status="held",
        released_at=None,
        amount_cents=1000,
        amount_token=None,
    )
    listing = SimpleNamespace(
        id="listing-telemetry-1",
        node_id="node-telemetry-1",
        status="escrow",
        renter_id="renter-telemetry-1",
        mesh_id="mesh-telemetry-1",
    )
    db = _FakeDb(escrow, listing)
    publish_event = MagicMock(return_value="evt-settlement-release")
    token_bridge_ctor = MagicMock()

    monkeypatch.setattr(settlement, "SessionLocal", lambda: db)
    monkeypatch.setattr(settlement, "TokenBridge", token_bridge_ctor)
    monkeypatch.setattr(settlement, "MeshToken", MagicMock())
    monkeypatch.setattr(settlement, "BridgeConfig", MagicMock())
    monkeypatch.setattr(settlement.uptime_tracker, "get_uptime_percent", lambda _node_id: 1.0)
    monkeypatch.setattr(settlement, "get_event_bus", lambda project_root=".": bus)
    monkeypatch.setattr(settlement, "publish_marketplace_escrow_event", publish_event)
    monkeypatch.setattr(settlement, "record_audit_log", MagicMock())
    monkeypatch.setattr(settlement.asyncio, "sleep", _stop_after_one_iteration)

    with patch.dict(sys.modules, {"src.core.settings": _settings_module()}):
        with pytest.raises(StopAsyncIteration):
            await settlement.marketplace_settlement_loop()

    token_bridge_ctor.assert_not_called()
    publish_event.assert_called_once()
    kwargs = publish_event.call_args.kwargs
    evidence = kwargs["settlement_evidence"]

    assert kwargs["transition"] == "released"
    assert kwargs["reason"] == "uptime_threshold_met"
    assert kwargs["upstream_event_ids"] == [telemetry_event.event_id]
    assert kwargs["upstream_source_agents"] == ["maas-telemetry"]
    assert evidence["decision_basis"] == "uptime_tracker_cached_window"
    assert evidence["source_quality"] == "telemetry_eventbus_linked_uptime_tracker"
    assert evidence["dataplane_confirmed"] is False
    assert evidence["threshold_met"] is True
    assert evidence["uptime_percent"] == 1.0
    assert evidence["uptime_threshold"] == settlement.SETTLEMENT_UPTIME_THRESHOLD
    assert evidence["telemetry_evidence"]["event_ids"] == [telemetry_event.event_id]
    assert evidence["telemetry_evidence"]["source_agents"] == ["maas-telemetry"]
    _assert_settlement_runtime_evidence(
        evidence,
        action="release",
        bridge_attempted=False,
        bridge_status="not_required",
        db_write_attempted=True,
        db_committed=True,
        escrow_status_after="released",
        listing_status_after="rented",
    )
    assert "node-telemetry-1" not in str(evidence)
    assert "mesh-telemetry-1" not in str(evidence)


@pytest.mark.asyncio
async def test_usd_refund_success_publishes_settlement_event(monkeypatch):
    escrow = SimpleNamespace(
        id="escrow-usd-refund",
        listing_id="listing-1",
        renter_id="renter-1",
        currency="USD",
        status="held",
        released_at=None,
        amount_cents=1000,
        amount_token=None,
    )
    listing = SimpleNamespace(
        id="listing-1",
        node_id="node-1",
        status="escrow",
        renter_id="renter-1",
        mesh_id="mesh-1",
    )
    db = _FakeDb(escrow, listing)
    publish_event = MagicMock(return_value="evt-settlement-refund")
    token_bridge_ctor = MagicMock()

    monkeypatch.setattr(settlement, "SessionLocal", lambda: db)
    monkeypatch.setattr(settlement, "TokenBridge", token_bridge_ctor)
    monkeypatch.setattr(settlement, "MeshToken", MagicMock())
    monkeypatch.setattr(settlement, "BridgeConfig", MagicMock())
    monkeypatch.setattr(settlement.uptime_tracker, "get_uptime_percent", lambda _node_id: 0.0)
    monkeypatch.setattr(settlement, "publish_marketplace_escrow_event", publish_event)
    monkeypatch.setattr(settlement, "record_audit_log", MagicMock())
    monkeypatch.setattr(settlement.asyncio, "sleep", _stop_after_one_iteration)

    with patch.dict(sys.modules, {"src.core.settings": _settings_module()}):
        with pytest.raises(StopAsyncIteration):
            await settlement.marketplace_settlement_loop()

    assert escrow.status == "refunded"
    assert listing.status == "available"
    assert listing.renter_id is None
    assert db.commits == 1
    token_bridge_ctor.assert_not_called()
    publish_event.assert_called_once()
    kwargs = publish_event.call_args.kwargs
    assert kwargs["transition"] == "refunded"
    assert kwargs["source_agent"] == "maas-settlement"
    assert kwargs["escrow_id"] == "escrow-usd-refund"
    assert kwargs["listing_id"] == "listing-1"
    assert kwargs["renter_id"] == "renter-1"
    assert kwargs["reason"] == "uptime_threshold_failed"
    _assert_settlement_runtime_evidence(
        kwargs["settlement_evidence"],
        action="refund",
        bridge_attempted=False,
        bridge_status="not_required",
        db_write_attempted=True,
        db_committed=True,
        escrow_status_after="refunded",
        listing_status_after="available",
    )
