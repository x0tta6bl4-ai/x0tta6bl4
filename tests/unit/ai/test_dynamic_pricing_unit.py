"""Unit tests for src.ai.dynamic_pricing."""

from __future__ import annotations

from types import SimpleNamespace
from unittest.mock import MagicMock

from src.ai.dynamic_pricing import PricingAgent


def _db_with_counts(total: int, rented: int):
    total_query = MagicMock()
    total_query.count.return_value = total

    rented_query = MagicMock()
    rented_query.filter.return_value = rented_query
    rented_query.count.return_value = rented

    db = MagicMock()
    db.query.side_effect = [total_query, rented_query]
    return db


def test_analyze_and_propose_high_utilization_triggers_increase(monkeypatch):
    agent = PricingAgent(target_utilization=0.7)
    called = []
    monkeypatch.setattr(
        agent,
        "_create_dao_proposal",
        lambda title, description, change_pct: called.append((title, change_pct)),
    )

    db = _db_with_counts(total=100, rented=90)
    agent.analyze_and_propose(db)

    assert called == [("Dynamic Price Adjustment: INCREASE", 10.0)]


def test_analyze_and_propose_low_utilization_triggers_decrease(monkeypatch):
    agent = PricingAgent(target_utilization=0.7)
    called = []
    monkeypatch.setattr(
        agent,
        "_create_dao_proposal",
        lambda title, description, change_pct: called.append((title, change_pct)),
    )

    db = _db_with_counts(total=20, rented=2)
    agent.analyze_and_propose(db)

    assert called == [("Dynamic Price Adjustment: DECREASE", -10.0)]


def test_analyze_and_propose_low_listing_volume_no_proposal(monkeypatch):
    agent = PricingAgent(target_utilization=0.7)
    called = []
    monkeypatch.setattr(
        agent,
        "_create_dao_proposal",
        lambda title, description, change_pct: called.append((title, change_pct)),
    )

    db = _db_with_counts(total=8, rented=1)
    agent.analyze_and_propose(db)

    assert called == []


def test_create_dao_proposal_skips_duplicate_active_title(monkeypatch):
    agent = PricingAgent()
    fake_engine = MagicMock()
    active = SimpleNamespace(title="Dynamic Price Adjustment: INCREASE", state=SimpleNamespace(value="active"))
    fake_engine.proposals = {"p1": active}
    monkeypatch.setattr("src.ai.dynamic_pricing._gov_engine", fake_engine)

    agent._create_dao_proposal("Dynamic Price Adjustment: INCREASE", "desc", 10.0)
    fake_engine.create_proposal.assert_not_called()


def test_create_dao_proposal_creates_expected_action(monkeypatch):
    agent = PricingAgent()
    fake_engine = MagicMock()
    fake_engine.proposals = {}
    monkeypatch.setattr("src.ai.dynamic_pricing._gov_engine", fake_engine)

    agent._create_dao_proposal("Dynamic Price Adjustment: DECREASE", "desc", -10.0)

    kwargs = fake_engine.create_proposal.call_args.kwargs
    assert kwargs["title"] == "Dynamic Price Adjustment: DECREASE"
    assert kwargs["duration_seconds"] == 3600 * 12
    assert kwargs["actions"] == [
        {
            "type": "update_config",
            "key": "global_price_multiplier",
            "value": 0.9,
        }
    ]
