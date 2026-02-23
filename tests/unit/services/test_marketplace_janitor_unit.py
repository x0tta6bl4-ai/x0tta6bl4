"""Unit tests for src.services.marketplace_janitor."""

from __future__ import annotations

import asyncio
from datetime import datetime, timedelta
from unittest.mock import AsyncMock, MagicMock, call, patch

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
) -> MagicMock:
    esc = MagicMock()
    esc.id = escrow_id
    esc.listing_id = listing_id
    esc.renter_id = renter_id
    esc.status = status
    return esc


def _make_listing(
    listing_id: str = "list-1",
    status: str = "rented",
    renter_id: str = "user-42",
    mesh_id: str = "mesh-1",
) -> MagicMock:
    lst = MagicMock()
    lst.id = listing_id
    lst.status = status
    lst.renter_id = renter_id
    lst.mesh_id = mesh_id
    return lst


def _setup_db(mock_db: MagicMock, escrows, listing=None):
    """Wire the db.query(...).filter(...).all/first return values."""
    query_result = mock_db.query.return_value.filter.return_value
    query_result.all.return_value = escrows
    query_result.first.return_value = listing


# ---------------------------------------------------------------------------
# Module under test (imported locally so patches can be set up at function
# level without fighting module-level imports).
# ---------------------------------------------------------------------------

_MOD = "src.services.marketplace_janitor"


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
async def test_single_expired_escrow_with_listing():
    """Expired escrow refunded and listing set available."""
    mock_db = MagicMock()
    escrow = _make_escrow()
    listing = _make_listing()
    _setup_db(mock_db, escrows=[escrow], listing=listing)

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
