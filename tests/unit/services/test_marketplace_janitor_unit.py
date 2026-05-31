"""Unit tests for src.services.marketplace_janitor."""

from __future__ import annotations

from unittest.mock import AsyncMock, MagicMock, patch

import pytest


# Sentinel to break the infinite while-True loop after one iteration.
class _StopLoop(Exception):
    pass


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

def _make_escrow(
    escrow_id: str = "esc-1",
    listing_id: str = "list-1",
    renter_id: str = "user-42",
    status: str = "held",
    currency: str = "USD",
    amount_cents: int | None = 1000,
    amount_token: float | None = None,
) -> MagicMock:
    esc = MagicMock()
    esc.id = escrow_id
    esc.listing_id = listing_id
    esc.renter_id = renter_id
    esc.status = status
    esc.currency = currency
    esc.amount_cents = amount_cents
    esc.amount_token = amount_token
    return esc


def _make_listing(
    listing_id: str = "list-1",
    status: str = "rented",
    renter_id: str = "user-42",
    mesh_id: str = "mesh-1",
    node_id: str = "node-1",
) -> MagicMock:
    lst = MagicMock()
    lst.id = listing_id
    lst.status = status
    lst.renter_id = renter_id
    lst.mesh_id = mesh_id
    lst.node_id = node_id
    return lst


def _setup_db(mock_db: MagicMock, escrows, listing=None):
    """Wire the db.query(...).filter(...).all/first return values."""
    query_result = mock_db.query.return_value.filter.return_value
    query_result.all.return_value = escrows
    query_result.first.return_value = listing


def _assert_janitor_evidence(
    evidence,
    *,
    bridge_attempted: bool,
    bridge_status: str,
    db_write_attempted: bool,
    db_committed: bool,
    escrow_status_after: str,
    listing_status_after: str | None,
):
    assert evidence["decision_basis"] == "escrow_timeout_without_release"
    assert evidence["source_quality"] == "local_db_expiry_scan_without_heartbeat_event_link"
    assert evidence["dataplane_confirmed"] is False
    assert evidence["threshold_met"] is True
    assert evidence["measurement_window_hours"] == 1
    assert evidence["telemetry_evidence"] == {
        "source_agents": [],
        "event_ids": [],
        "events_total": 0,
        "payloads_redacted": True,
    }
    assert evidence["settlement_action"] == "janitor_refund"
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
    assert evidence["raw_identifiers_redacted"] is True
    assert evidence["payloads_redacted"] is True
    assert "dataplane failure" in evidence["claim_boundary"]


# ---------------------------------------------------------------------------
# Module under test (imported locally so patches can be set up at function
# level without fighting module-level imports).
# ---------------------------------------------------------------------------

_MOD = "src.services.marketplace_janitor"


@pytest.fixture(autouse=True)
def _patch_marketplace_event_publish():
    with patch(f"{_MOD}.publish_marketplace_escrow_event", return_value="evt-janitor") as publisher:
        yield publisher


# ---------------------------------------------------------------------------
# Tests
# ---------------------------------------------------------------------------


@pytest.mark.asyncio
async def test_no_expired_escrows_sleeps_and_exits():
    """With no expired escrows the loop sleeps once then exits."""
    mock_db = MagicMock()
    _setup_db(mock_db, escrows=[])

    with (
        patch(f"{_MOD}.SessionLocal", return_value=mock_db),
        patch(f"{_MOD}.asyncio.sleep", side_effect=_StopLoop),
    ):
        from src.services.marketplace_janitor import marketplace_janitor_loop

        with pytest.raises(_StopLoop):
            await marketplace_janitor_loop()

    mock_db.close.assert_called_once()
    mock_db.commit.assert_not_called()


@pytest.mark.asyncio
async def test_single_expired_escrow_with_listing(monkeypatch, _patch_marketplace_event_publish):
    """Expired escrow refunded and listing set available."""
    mock_db = MagicMock()
    escrow = _make_escrow()
    listing = _make_listing()
    _setup_db(mock_db, escrows=[escrow], listing=listing)
    monkeypatch.setenv("MAAS_JANITOR_SPIFFE_ID", "spiffe://mesh.x0tta6bl4.mesh/workload/janitor")
    monkeypatch.setenv("MAAS_JANITOR_DID", "did:mesh:pqc:janitor")
    monkeypatch.setenv("MAAS_JANITOR_WALLET_ADDRESS", "0xdddddddddddddddddddddddddddddddddddddddd")

    with (
        patch(f"{_MOD}.SessionLocal", return_value=mock_db),
        patch(f"{_MOD}.record_audit_log") as mock_audit,
        patch(f"{_MOD}.asyncio.sleep", side_effect=_StopLoop),
    ):
        from src.services.marketplace_janitor import marketplace_janitor_loop

        with pytest.raises(_StopLoop):
            await marketplace_janitor_loop()

    # Escrow status updated
    assert escrow.status == "refunded"
    # Listing cleared
    assert listing.status == "available"
    assert listing.renter_id is None
    assert listing.mesh_id is None
    # DB committed once per escrow
    mock_db.commit.assert_called_once()
    # Audit log recorded
    mock_audit.assert_called_once()
    _args, _kwargs = mock_audit.call_args
    assert _args[2] == "MARKETPLACE_ESCROW_AUTO_REFUNDED"
    assert _kwargs["user_id"] == "user-42"
    assert _kwargs["payload"]["escrow_id"] == "esc-1"
    assert _kwargs["payload"]["reason"] == "timeout_no_heartbeat"
    _patch_marketplace_event_publish.assert_called_once()
    event_kwargs = _patch_marketplace_event_publish.call_args.kwargs
    assert event_kwargs["spiffe_id"] == "spiffe://mesh.x0tta6bl4.mesh/workload/janitor"
    assert event_kwargs["did"] == "did:mesh:pqc:janitor"
    assert event_kwargs["wallet_address"] == "0xdddddddddddddddddddddddddddddddddddddddd"
    assert event_kwargs["upstream_event_ids"] == []
    assert event_kwargs["upstream_source_agents"] == []
    _assert_janitor_evidence(
        event_kwargs["settlement_evidence"],
        bridge_attempted=False,
        bridge_status="not_required",
        db_write_attempted=True,
        db_committed=True,
        escrow_status_after="refunded",
        listing_status_after="available",
    )


@pytest.mark.asyncio
async def test_expired_escrow_without_listing():
    """Expired escrow refunded even when listing query returns None."""
    mock_db = MagicMock()
    escrow = _make_escrow()
    _setup_db(mock_db, escrows=[escrow], listing=None)

    with (
        patch(f"{_MOD}.SessionLocal", return_value=mock_db),
        patch(f"{_MOD}.record_audit_log"),
        patch(f"{_MOD}.asyncio.sleep", side_effect=_StopLoop),
    ):
        from src.services.marketplace_janitor import marketplace_janitor_loop

        with pytest.raises(_StopLoop):
            await marketplace_janitor_loop()

    assert escrow.status == "refunded"
    mock_db.commit.assert_called_once()


@pytest.mark.asyncio
async def test_multiple_expired_escrows():
    """All expired escrows are processed in a single iteration."""
    mock_db = MagicMock()
    escrows = [_make_escrow(f"esc-{i}", f"list-{i}", f"user-{i}") for i in range(3)]
    listing = _make_listing()
    _setup_db(mock_db, escrows=escrows, listing=listing)

    with (
        patch(f"{_MOD}.SessionLocal", return_value=mock_db),
        patch(f"{_MOD}.record_audit_log") as mock_audit,
        patch(f"{_MOD}.asyncio.sleep", side_effect=_StopLoop),
    ):
        from src.services.marketplace_janitor import marketplace_janitor_loop

        with pytest.raises(_StopLoop):
            await marketplace_janitor_loop()

    for esc in escrows:
        assert esc.status == "refunded"
    assert mock_db.commit.call_count == 3
    assert mock_audit.call_count == 3


@pytest.mark.asyncio
async def test_db_always_closed_on_exception():
    """DB session is closed in finally even if query raises."""
    mock_db = MagicMock()
    mock_db.query.side_effect = RuntimeError("db down")

    with (
        patch(f"{_MOD}.SessionLocal", return_value=mock_db),
        patch(f"{_MOD}.asyncio.sleep", side_effect=_StopLoop),
    ):
        from src.services.marketplace_janitor import marketplace_janitor_loop

        with pytest.raises(_StopLoop):
            await marketplace_janitor_loop()

    mock_db.close.assert_called_once()


@pytest.mark.asyncio
async def test_outer_exception_does_not_crash_loop():
    """Exception in loop body is caught; loop continues to next sleep."""
    call_count = 0

    async def _sleep(_):
        nonlocal call_count
        call_count += 1
        if call_count >= 2:
            raise _StopLoop

    mock_db = MagicMock()
    mock_db.query.side_effect = RuntimeError("transient error")

    with (
        patch(f"{_MOD}.SessionLocal", return_value=mock_db),
        patch(f"{_MOD}.asyncio.sleep", side_effect=_sleep),
    ):
        from src.services.marketplace_janitor import marketplace_janitor_loop

        with pytest.raises(_StopLoop):
            await marketplace_janitor_loop()

    # Loop ran twice — survived the first error
    assert call_count == 2


@pytest.mark.asyncio
async def test_sleep_called_with_600():
    """The loop sleeps for 600 seconds between iterations."""
    mock_db = MagicMock()
    _setup_db(mock_db, escrows=[])

    with (
        patch(f"{_MOD}.SessionLocal", return_value=mock_db),
        patch(f"{_MOD}.asyncio.sleep", side_effect=_StopLoop) as mock_sleep,
    ):
        from src.services.marketplace_janitor import marketplace_janitor_loop

        with pytest.raises(_StopLoop):
            await marketplace_janitor_loop()

    mock_sleep.assert_called_once_with(600)


@pytest.mark.asyncio
async def test_audit_log_status_code_200():
    """Audit log is recorded with status_code=200."""
    mock_db = MagicMock()
    escrow = _make_escrow()
    _setup_db(mock_db, escrows=[escrow], listing=None)

    with (
        patch(f"{_MOD}.SessionLocal", return_value=mock_db),
        patch(f"{_MOD}.record_audit_log") as mock_audit,
        patch(f"{_MOD}.asyncio.sleep", side_effect=_StopLoop),
    ):
        from src.services.marketplace_janitor import marketplace_janitor_loop

        with pytest.raises(_StopLoop):
            await marketplace_janitor_loop()

    _, kwargs = mock_audit.call_args
    assert kwargs["status_code"] == 200


@pytest.mark.asyncio
async def test_x0t_refund_success_links_bridge_evidence(_patch_marketplace_event_publish):
    """Successful X0T janitor refunds include TokenBridge upstream evidence."""
    mock_db = MagicMock()
    escrow = _make_escrow(currency="X0T", amount_cents=None, amount_token=12.5)
    listing = _make_listing(status="escrow")
    bridge = MagicMock()
    bridge.refund_escrow_on_chain = AsyncMock(return_value=True)
    bridge.last_chain_write_event_ids = ["evt-refund-start", "evt-refund-ok"]
    bridge.source_agent = "token-bridge"
    _setup_db(mock_db, escrows=[escrow], listing=listing)

    with (
        patch(f"{_MOD}.SessionLocal", return_value=mock_db),
        patch(f"{_MOD}._get_token_bridge", return_value=bridge),
        patch(f"{_MOD}.record_audit_log") as mock_audit,
        patch(f"{_MOD}.asyncio.sleep", side_effect=_StopLoop),
    ):
        from src.services.marketplace_janitor import marketplace_janitor_loop

        with pytest.raises(_StopLoop):
            await marketplace_janitor_loop()

    bridge.refund_escrow_on_chain.assert_awaited_once_with("esc-1")
    assert escrow.status == "refunded"
    assert listing.status == "available"
    assert listing.renter_id is None
    assert listing.mesh_id is None
    mock_db.commit.assert_called_once()
    mock_audit.assert_called_once()
    _patch_marketplace_event_publish.assert_called_once()
    event_kwargs = _patch_marketplace_event_publish.call_args.kwargs
    assert event_kwargs["transition"] == "refunded"
    assert event_kwargs["reason"] == "timeout_no_heartbeat"
    assert event_kwargs["upstream_event_ids"] == ["evt-refund-start", "evt-refund-ok"]
    assert event_kwargs["upstream_source_agents"] == ["token-bridge"]
    _assert_janitor_evidence(
        event_kwargs["settlement_evidence"],
        bridge_attempted=True,
        bridge_status="refunded",
        db_write_attempted=True,
        db_committed=True,
        escrow_status_after="refunded",
        listing_status_after="available",
    )


@pytest.mark.asyncio
async def test_x0t_refund_rejection_keeps_expired_escrow_held(_patch_marketplace_event_publish):
    """X0T expiry must not update local state until on-chain refund succeeds."""
    mock_db = MagicMock()
    escrow = _make_escrow(currency="X0T")
    listing = _make_listing(status="escrow")
    bridge = MagicMock()
    bridge.refund_escrow_on_chain = AsyncMock(return_value=False)
    bridge.last_chain_write_event_ids = ["evt-refund-start", "evt-refund-rejected"]
    bridge.source_agent = "token-bridge"
    _setup_db(mock_db, escrows=[escrow], listing=listing)

    with (
        patch(f"{_MOD}.SessionLocal", return_value=mock_db),
        patch(f"{_MOD}._get_token_bridge", return_value=bridge),
        patch(f"{_MOD}.record_audit_log") as mock_audit,
        patch(f"{_MOD}.asyncio.sleep", side_effect=_StopLoop),
    ):
        from src.services.marketplace_janitor import marketplace_janitor_loop

        with pytest.raises(_StopLoop):
            await marketplace_janitor_loop()

    bridge.refund_escrow_on_chain.assert_awaited_once_with("esc-1")
    assert escrow.status == "held"
    assert listing.status == "escrow"
    assert listing.renter_id == "user-42"
    assert listing.mesh_id == "mesh-1"
    mock_db.commit.assert_not_called()
    mock_audit.assert_not_called()
    _patch_marketplace_event_publish.assert_called_once()
    event_kwargs = _patch_marketplace_event_publish.call_args.kwargs
    assert event_kwargs["transition"] == "blocked"
    assert event_kwargs["reason"] == "refund_bridge_rejected"
    assert event_kwargs["upstream_event_ids"] == [
        "evt-refund-start",
        "evt-refund-rejected",
    ]
    assert event_kwargs["upstream_source_agents"] == ["token-bridge"]
    _assert_janitor_evidence(
        event_kwargs["settlement_evidence"],
        bridge_attempted=True,
        bridge_status="rejected",
        db_write_attempted=False,
        db_committed=False,
        escrow_status_after="held",
        listing_status_after="escrow",
    )


@pytest.mark.asyncio
async def test_x0t_refund_exception_keeps_expired_escrow_held(_patch_marketplace_event_publish):
    """Bridge errors during X0T expiry leave escrow held for retry."""
    mock_db = MagicMock()
    escrow = _make_escrow(escrow_id="esc-error", currency="X0T")
    listing = _make_listing(status="escrow")
    bridge = MagicMock()
    bridge.refund_escrow_on_chain = AsyncMock(side_effect=RuntimeError("bridge down"))
    bridge.last_chain_write_event_ids = ["evt-refund-start", "evt-refund-error"]
    bridge.source_agent = "token-bridge"
    _setup_db(mock_db, escrows=[escrow], listing=listing)

    with (
        patch(f"{_MOD}.SessionLocal", return_value=mock_db),
        patch(f"{_MOD}._get_token_bridge", return_value=bridge),
        patch(f"{_MOD}.record_audit_log") as mock_audit,
        patch(f"{_MOD}.asyncio.sleep", side_effect=_StopLoop),
    ):
        from src.services.marketplace_janitor import marketplace_janitor_loop

        with pytest.raises(_StopLoop):
            await marketplace_janitor_loop()

    bridge.refund_escrow_on_chain.assert_awaited_once_with("esc-error")
    assert escrow.status == "held"
    assert listing.status == "escrow"
    assert listing.renter_id == "user-42"
    assert listing.mesh_id == "mesh-1"
    mock_db.commit.assert_not_called()
    mock_audit.assert_not_called()
    _patch_marketplace_event_publish.assert_called_once()
    event_kwargs = _patch_marketplace_event_publish.call_args.kwargs
    assert event_kwargs["transition"] == "blocked"
    assert event_kwargs["reason"] == "refund_bridge_error"
    assert event_kwargs["upstream_event_ids"] == [
        "evt-refund-start",
        "evt-refund-error",
    ]
    assert event_kwargs["upstream_source_agents"] == ["token-bridge"]
    _assert_janitor_evidence(
        event_kwargs["settlement_evidence"],
        bridge_attempted=True,
        bridge_status="error",
        db_write_attempted=False,
        db_committed=False,
        escrow_status_after="held",
        listing_status_after="escrow",
    )
