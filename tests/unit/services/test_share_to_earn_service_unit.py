"""Unit tests for share-to-earn reward event publication."""

import sqlite3
from decimal import Decimal

import pytest

from src.services import share_to_earn_service as service


def test_publish_share_to_earn_reward_event_attaches_identity(monkeypatch):
    calls = []

    def _publish(**kwargs):
        calls.append(kwargs)
        return "evt-share-to-earn"

    monkeypatch.setenv("SHARE_TO_EARN_SPIFFE_ID", "spiffe://mesh.x0tta6bl4.mesh/workload/share-to-earn")
    monkeypatch.setenv("SHARE_TO_EARN_DID", "did:mesh:pqc:share-to-earn")
    monkeypatch.setenv("SHARE_TO_EARN_WALLET_ADDRESS", "0xeeeeeeeeeeeeeeeeeeeeeeeeeeeeeeeeeeeeeeee")
    monkeypatch.setattr(service, "publish_reward_settlement_event", _publish)

    event_id = service.publish_share_to_earn_reward_event(
        node_id="node-earn-1",
        node_address="0xffffffffffffffffffffffffffffffffffffffff",
        amount=Decimal("0.05"),
        packets=500,
        simulation_enabled=True,
        status="SIMULATED_EARNING",
    )

    assert event_id == "evt-share-to-earn"
    assert len(calls) == 1
    payload = calls[0]
    assert payload["transition"] == "recorded"
    assert payload["source_agent"] == "share-to-earn"
    assert payload["node_id"] == "node-earn-1"
    assert payload["node_address"] == "0xffffffffffffffffffffffffffffffffffffffff"
    assert payload["spiffe_id"] == "spiffe://mesh.x0tta6bl4.mesh/workload/share-to-earn"
    assert payload["did"] == "did:mesh:pqc:share-to-earn"
    assert payload["wallet_address"] == "0xeeeeeeeeeeeeeeeeeeeeeeeeeeeeeeeeeeeeeeee"
    assert payload["packets"] == 500
    assert payload["amount"] == "0.05"
    assert payload["submitted_transaction"] is False
    assert payload["simulated"] is True
    assert payload["settlement_recorded"] is False
    assert payload["local_accounting_recorded"] is True


def test_publish_share_to_earn_reward_event_falls_back_to_reward_address(monkeypatch):
    calls = []

    monkeypatch.delenv("SHARE_TO_EARN_WALLET_ADDRESS", raising=False)
    monkeypatch.delenv("X0TTA6BL4_SERVICE_WALLET_ADDRESS", raising=False)
    monkeypatch.delenv("SERVICE_WALLET_ADDRESS", raising=False)
    monkeypatch.delenv("GHOST_WALLET_ADDRESS", raising=False)
    monkeypatch.setattr(service, "publish_reward_settlement_event", lambda **kwargs: calls.append(kwargs) or "evt")

    service.publish_share_to_earn_reward_event(
        node_id="node-earn-1",
        node_address="0xffffffffffffffffffffffffffffffffffffffff",
        amount=Decimal("0.01"),
        packets=100,
        simulation_enabled=True,
        status="SIMULATED_EARNING",
    )

    assert calls[0]["wallet_address"] == "0xffffffffffffffffffffffffffffffffffffffff"


def test_publish_share_to_earn_reward_event_skips_zero_amount(monkeypatch):
    calls = []
    monkeypatch.setattr(service, "publish_reward_settlement_event", lambda **kwargs: calls.append(kwargs))

    event_id = service.publish_share_to_earn_reward_event(
        node_id="node-earn-1",
        node_address="0xffffffffffffffffffffffffffffffffffffffff",
        amount=Decimal("0"),
        packets=0,
        simulation_enabled=False,
        status="OBSERVE_ONLY",
    )

    assert event_id is None
    assert calls == []


def test_configured_user_id_requires_explicit_positive_integer(monkeypatch):
    monkeypatch.delenv("GHOST_USER_ID", raising=False)
    with pytest.raises(RuntimeError, match="GHOST_USER_ID is required"):
        service._configured_user_id()

    monkeypatch.setenv("GHOST_USER_ID", "not-an-int")
    with pytest.raises(RuntimeError, match="must be an integer"):
        service._configured_user_id()

    monkeypatch.setenv("GHOST_USER_ID", "0")
    with pytest.raises(RuntimeError, match="positive integer"):
        service._configured_user_id()

    monkeypatch.setenv("GHOST_USER_ID", "42")
    assert service._configured_user_id() == 42


def test_configured_node_address_requires_env_or_identity(monkeypatch):
    monkeypatch.delenv("GHOST_WALLET_ADDRESS", raising=False)
    with pytest.raises(RuntimeError, match="wallet address is required"):
        service._configured_node_address({"wallet_address": None})

    assert service._configured_node_address(
        {"wallet_address": "0xaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaa"}
    ) == "0xaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaa"

    monkeypatch.setenv(
        "GHOST_WALLET_ADDRESS",
        "0xbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbb",
    )
    assert service._configured_node_address(
        {"wallet_address": "0xaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaa"}
    ) == "0xbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbb"


def test_referral_count_for_user_reads_database(tmp_path):
    db_path = tmp_path / "access.db"
    with sqlite3.connect(db_path) as conn:
        conn.execute(
            "CREATE TABLE referrals (referrer_user_id INTEGER NOT NULL)"
        )
        conn.executemany(
            "INSERT INTO referrals (referrer_user_id) VALUES (?)",
            [(7,), (7,), (8,)],
        )

    assert service.referral_count_for_user(7, str(db_path)) == 2
    assert service.referral_count_for_user(9, str(db_path)) == 0
