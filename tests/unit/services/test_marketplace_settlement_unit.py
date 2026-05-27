"""Unit tests for marketplace settlement fail-closed bridge handling."""

from types import SimpleNamespace
from unittest.mock import AsyncMock, MagicMock, patch
import sys

import pytest

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
