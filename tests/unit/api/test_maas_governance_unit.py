"""Unit tests for src/api/maas_governance.py — pure logic functions and Pydantic models."""

from __future__ import annotations

import hashlib
import json
from datetime import datetime, timedelta
from unittest.mock import MagicMock

import pytest

from src.api.maas_governance import (
    GovernanceAction,
    ProposalCreate,
    VoteRequest,
    _compute_finality_hash,
    _execute_action,
    _resolve_state,
    _tally,
    get_gov_power,
)


# ---------------------------------------------------------------------------
# get_gov_power
# ---------------------------------------------------------------------------


class TestGetGovPower:
    def _user(self, plan: str) -> MagicMock:
        u = MagicMock()
        u.plan = plan
        return u

    def test_free_plan(self):
        assert get_gov_power(self._user("free")) == 10.0

    def test_starter_plan(self):
        assert get_gov_power(self._user("starter")) == 100.0

    def test_pro_plan(self):
        assert get_gov_power(self._user("pro")) == 1000.0

    def test_enterprise_plan(self):
        assert get_gov_power(self._user("enterprise")) == 10000.0

    def test_unknown_plan_defaults_to_free(self):
        assert get_gov_power(self._user("alien")) == 10.0

    def test_power_increases_with_tier(self):
        plans = ["free", "starter", "pro", "enterprise"]
        powers = [get_gov_power(self._user(p)) for p in plans]
        assert powers == sorted(powers)


# ---------------------------------------------------------------------------
# _tally
# ---------------------------------------------------------------------------


class TestTally:
    def _vote(self, v: str, tokens: int) -> MagicMock:
        vote = MagicMock()
        vote.vote = v
        vote.tokens = tokens
        return vote

    def _proposal(self, votes: list) -> MagicMock:
        p = MagicMock()
        p.votes = votes
        return p

    def test_empty_votes_returns_zeros(self):
        p = self._proposal([])
        t = _tally(p)
        assert t == {"yes": 0.0, "no": 0.0, "abstain": 0.0}

    def test_single_yes_vote(self):
        p = self._proposal([self._vote("yes", 100)])
        t = _tally(p)
        # quadratic: (100/100)^0.5 = 1.0
        assert abs(t["yes"] - 1.0) < 1e-9
        assert t["no"] == 0.0
        assert t["abstain"] == 0.0

    def test_quadratic_weighting(self):
        p = self._proposal([self._vote("yes", 400)])
        t = _tally(p)
        # (400/100)^0.5 = 2.0
        assert abs(t["yes"] - 2.0) < 1e-9

    def test_multiple_votes_accumulated(self):
        votes = [self._vote("yes", 100), self._vote("yes", 100), self._vote("no", 100)]
        p = self._proposal(votes)
        t = _tally(p)
        assert abs(t["yes"] - 2.0) < 1e-9
        assert abs(t["no"] - 1.0) < 1e-9

    def test_abstain_counted_separately(self):
        p = self._proposal([self._vote("abstain", 100)])
        t = _tally(p)
        assert abs(t["abstain"] - 1.0) < 1e-9


# ---------------------------------------------------------------------------
# _resolve_state
# ---------------------------------------------------------------------------


class TestResolveState:
    def _proposal(
        self,
        state: str,
        end_time: datetime,
        votes: list | None = None,
    ) -> MagicMock:
        p = MagicMock()
        p.state = state
        p.end_time = end_time
        p.votes = votes or []
        return p

    def test_executed_state_preserved(self):
        p = self._proposal("executed", datetime.utcnow() - timedelta(hours=1))
        assert _resolve_state(p) == "executed"

    def test_cancelled_state_preserved(self):
        p = self._proposal("cancelled", datetime.utcnow() - timedelta(hours=1))
        assert _resolve_state(p) == "cancelled"

    def test_active_before_end_time(self):
        p = self._proposal("active", datetime.utcnow() + timedelta(hours=1))
        assert _resolve_state(p) == "active"

    def test_active_expired_with_majority_yes_is_passed(self):
        vote = MagicMock()
        vote.vote = "yes"
        vote.tokens = 100
        p = self._proposal("active", datetime.utcnow() - timedelta(hours=1), votes=[vote])
        assert _resolve_state(p) == "passed"

    def test_active_expired_with_majority_no_is_rejected(self):
        vote = MagicMock()
        vote.vote = "no"
        vote.tokens = 100
        p = self._proposal("active", datetime.utcnow() - timedelta(hours=1), votes=[vote])
        assert _resolve_state(p) == "rejected"

    def test_active_expired_no_votes_is_rejected(self):
        p = self._proposal("active", datetime.utcnow() - timedelta(hours=1), votes=[])
        assert _resolve_state(p) == "rejected"

    def test_passed_state_preserved_without_re_evaluation(self):
        # Non-"active" non-"executed" states are preserved as-is
        p = self._proposal("passed", datetime.utcnow() - timedelta(hours=1))
        assert _resolve_state(p) == "passed"

    def test_rejected_state_preserved(self):
        p = self._proposal("rejected", datetime.utcnow() - timedelta(hours=1))
        assert _resolve_state(p) == "rejected"


# ---------------------------------------------------------------------------
# _execute_action
# ---------------------------------------------------------------------------


class TestExecuteAction:
    def test_rotate_keys_succeeds(self):
        result = _execute_action({"type": "rotate_keys", "params": {}})
        assert result["success"] is True
        assert result["action"] == "rotate_keys"

    def test_update_price_succeeds(self):
        result = _execute_action({"type": "update_price", "params": {"amount": 5.0}})
        assert result["success"] is True
        assert "5.0" in result["detail"]

    def test_unknown_action_fails(self):
        result = _execute_action({"type": "unknown_type", "params": {}})
        assert result["success"] is False

    def test_update_config_unsupported_key_fails(self):
        result = _execute_action({
            "type": "update_config",
            "params": {"key": "unsupported_key", "value": 42},
        })
        assert result["success"] is False
        assert "unsupported_key" in result["detail"]

    def test_update_config_global_price_multiplier_with_no_db(self):
        # Without a DB, still returns success (no DB write)
        result = _execute_action({
            "type": "update_config",
            "params": {"key": "global_price_multiplier", "value": 1.5},
        })
        assert result["success"] is True

    def test_update_config_global_price_multiplier_with_mock_db(self):
        db = MagicMock()
        config = MagicMock()
        db.query.return_value.filter.return_value.first.return_value = config
        result = _execute_action({
            "type": "update_config",
            "params": {"key": "global_price_multiplier", "value": 2.0},
        }, db=db)
        assert result["success"] is True
        assert db.commit.called

    def test_update_config_global_price_multiplier_creates_when_missing(self):
        db = MagicMock()
        db.query.return_value.filter.return_value.first.return_value = None
        result = _execute_action({
            "type": "update_config",
            "params": {"key": "global_price_multiplier", "value": 3.0},
        }, db=db)
        assert result["success"] is True
        assert db.add.called

    def test_action_type_from_action_type_key(self):
        # Accepts "action_type" key as fallback
        result = _execute_action({"action_type": "rotate_keys", "params": {}})
        assert result["success"] is True


# ---------------------------------------------------------------------------
# _compute_finality_hash
# ---------------------------------------------------------------------------


class TestComputeFinalityHash:
    def _vote(self, voter_id: str, vote: str, tokens: int) -> MagicMock:
        v = MagicMock()
        v.voter_id = voter_id
        v.vote = vote
        v.tokens = tokens
        return v

    def _proposal(self, pid: str, votes: list) -> MagicMock:
        p = MagicMock()
        p.id = pid
        p.votes = votes
        return p

    def test_returns_sha256_hex_string(self):
        p = self._proposal("prop-1", [])
        h = _compute_finality_hash(p, [])
        assert len(h) == 64
        assert all(c in "0123456789abcdef" for c in h)

    def test_deterministic_output(self):
        v = self._vote("voter-1", "yes", 1000)
        p = self._proposal("prop-2", [v])
        results = [{"action": "rotate_keys", "success": True}]
        h1 = _compute_finality_hash(p, results)
        h2 = _compute_finality_hash(p, results)
        assert h1 == h2

    def test_different_votes_different_hash(self):
        v1 = self._vote("voter-A", "yes", 1000)
        v2 = self._vote("voter-B", "no", 500)
        p1 = self._proposal("prop-3", [v1])
        p2 = self._proposal("prop-3", [v2])
        h1 = _compute_finality_hash(p1, [])
        h2 = _compute_finality_hash(p2, [])
        assert h1 != h2

    def test_vote_order_does_not_affect_hash(self):
        """Votes are sorted by voter_id — order of insertion shouldn't matter."""
        v_a = self._vote("voter-A", "yes", 1000)
        v_b = self._vote("voter-B", "no", 500)
        p1 = self._proposal("prop-4", [v_a, v_b])
        p2 = self._proposal("prop-4", [v_b, v_a])
        h1 = _compute_finality_hash(p1, [])
        h2 = _compute_finality_hash(p2, [])
        assert h1 == h2


# ---------------------------------------------------------------------------
# Pydantic models
# ---------------------------------------------------------------------------


class TestGovernanceAction:
    def test_valid_update_config(self):
        a = GovernanceAction(type="update_config", params={"key": "x", "value": 1})
        assert a.type == "update_config"

    def test_valid_rotate_keys(self):
        a = GovernanceAction(type="rotate_keys")
        assert a.params == {}

    def test_valid_restart_node(self):
        a = GovernanceAction(type="restart_node")
        assert a.type == "restart_node"

    def test_valid_update_price(self):
        a = GovernanceAction(type="update_price", params={"amount": 5.0})
        assert a.params["amount"] == 5.0

    def test_invalid_type_raises(self):
        with pytest.raises(Exception):
            GovernanceAction(type="destroy_everything")


class TestProposalCreate:
    def test_valid_proposal(self):
        p = ProposalCreate(
            title="A" * 10,
            description="B" * 20,
            duration_hours=48,
        )
        assert p.duration_hours == 48

    def test_title_too_short_raises(self):
        with pytest.raises(Exception):
            ProposalCreate(title="short", description="B" * 20)

    def test_description_too_short_raises(self):
        with pytest.raises(Exception):
            ProposalCreate(title="A" * 10, description="short")

    def test_duration_below_min_raises(self):
        with pytest.raises(Exception):
            ProposalCreate(title="A" * 10, description="B" * 20, duration_hours=0)

    def test_duration_above_max_raises(self):
        with pytest.raises(Exception):
            ProposalCreate(title="A" * 10, description="B" * 20, duration_hours=200)

    def test_default_duration_is_24(self):
        p = ProposalCreate(title="A" * 10, description="B" * 20)
        assert p.duration_hours == 24

    def test_actions_defaults_to_empty_list(self):
        p = ProposalCreate(title="A" * 10, description="B" * 20)
        assert p.actions == []

    def test_with_actions(self):
        p = ProposalCreate(
            title="A" * 10,
            description="B" * 20,
            actions=[GovernanceAction(type="rotate_keys")],
        )
        assert len(p.actions) == 1


class TestVoteRequest:
    def test_yes_vote(self):
        v = VoteRequest(vote="yes")
        assert v.vote == "yes"

    def test_no_vote(self):
        v = VoteRequest(vote="no")
        assert v.vote == "no"

    def test_abstain_vote(self):
        v = VoteRequest(vote="abstain")
        assert v.vote == "abstain"

    def test_invalid_vote_raises(self):
        with pytest.raises(Exception):
            VoteRequest(vote="maybe")
