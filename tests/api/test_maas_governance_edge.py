"""
Edge-case tests for MaaS Governance — gaps not covered by test_maas_governance.py.

Uncovered paths targeted:
  _execute_action:
    - rotate_keys action type
    - update_price action type
    - update_config with unsupported key (not global_price_multiplier)
    - unknown / unrecognised action type (returns success=False)

  _resolve_state:
    - "rejected" state: no yes votes or no > yes

  Endpoint edge cases:
    - GET /proposals/{id} → 404 for non-existent id
    - GET /proposals/{id} for active (not-yet-executed) proposal
    - POST /vote without auth → 401
    - POST /execute without auth → 401
    - Vote "abstain"
    - Execute a rejected proposal → 400
"""

import os
import uuid
from datetime import datetime, timedelta

import pytest
from fastapi.testclient import TestClient
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker

from src.core.app import app
from src.database import Base, GovernanceProposal, GovernanceVote, User, get_db

_TEST_DB_PATH = f"./test_gov_edge_{uuid.uuid4().hex}.db"
engine = create_engine(
    f"sqlite:///{_TEST_DB_PATH}", connect_args={"check_same_thread": False}
)
TestingSessionLocal = sessionmaker(autocommit=False, autoflush=False, bind=engine)


def override_get_db():
    db = TestingSessionLocal()
    try:
        yield db
    finally:
        db.close()


@pytest.fixture(scope="module")
def client():
    Base.metadata.create_all(bind=engine)
    app.dependency_overrides[get_db] = override_get_db
    with TestClient(app) as c:
        yield c
    app.dependency_overrides.pop(get_db, None)
    Base.metadata.drop_all(bind=engine)
    if os.path.exists(_TEST_DB_PATH):
        os.remove(_TEST_DB_PATH)


@pytest.fixture(scope="module")
def pro_token(client):
    """Pro-plan user token for creating proposals."""
    email = f"pro-edge-{uuid.uuid4().hex[:8]}@test.com"
    r = client.post("/api/v1/maas/auth/register",
                    json={"email": email, "password": "password123"})
    assert r.status_code == 200, r.text
    token = r.json()["access_token"]

    db = TestingSessionLocal()
    u = db.query(User).filter(User.api_key == token).first()
    u.plan = "pro"
    db.commit()
    db.close()
    return token


@pytest.fixture(scope="module")
def free_token(client):
    """Starter-plan user token for voting."""
    email = f"free-edge-{uuid.uuid4().hex[:8]}@test.com"
    r = client.post("/api/v1/maas/auth/register",
                    json={"email": email, "password": "password123"})
    assert r.status_code == 200, r.text
    return r.json()["access_token"]


def _create_proposal(client, pro_token, duration_hours=1, actions=None) -> str:
    """Helper: create a proposal with given actions and return its id."""
    payload = {
        "title": f"Edge case proposal {uuid.uuid4().hex[:6]}",
        "description": "Testing edge cases in the governance system thoroughly.",
        "duration_hours": duration_hours,
    }
    if actions:
        payload["actions"] = actions
    r = client.post(
        "/api/v1/maas/governance/proposals",
        headers={"X-API-Key": pro_token},
        json=payload,
    )
    assert r.status_code == 200, r.text
    return r.json()["proposal_id"]


def _force_passed(pid: str):
    """Push the proposal end_time into the past so it resolves as passed/rejected."""
    db = TestingSessionLocal()
    prop = db.query(GovernanceProposal).filter(GovernanceProposal.id == pid).first()
    prop.end_time = datetime.utcnow() - timedelta(hours=1)
    db.commit()
    db.close()


# ---------------------------------------------------------------------------
# GET /proposals/{id} edge cases
# ---------------------------------------------------------------------------

class TestGetProposalEdgeCases:
    def test_get_nonexistent_proposal_404(self, client):
        r = client.get("/api/v1/maas/governance/proposals/prop-does-not-exist")
        assert r.status_code == 404

    def test_get_active_proposal_returns_200(self, client, pro_token):
        pid = _create_proposal(client, pro_token, duration_hours=48)
        r = client.get(f"/api/v1/maas/governance/proposals/{pid}")
        assert r.status_code == 200
        data = r.json()
        assert data["state"] == "active"
        assert data["id"] == pid

    def test_get_proposal_has_required_fields(self, client, pro_token):
        pid = _create_proposal(client, pro_token)
        r = client.get(f"/api/v1/maas/governance/proposals/{pid}")
        data = r.json()
        for field in ("id", "title", "description", "state", "votes", "end_time"):
            assert field in data, f"Missing field: {field}"


# ---------------------------------------------------------------------------
# Auth guards
# ---------------------------------------------------------------------------

class TestAuthGuards:
    def test_vote_requires_auth(self, client, pro_token):
        pid = _create_proposal(client, pro_token)
        r = client.post(
            f"/api/v1/maas/governance/proposals/{pid}/vote",
            json={"vote": "yes"},
        )
        assert r.status_code == 401

    def test_execute_requires_auth(self, client, pro_token):
        pid = _create_proposal(client, pro_token)
        r = client.post(f"/api/v1/maas/governance/proposals/{pid}/execute")
        assert r.status_code == 401

    def test_create_proposal_requires_auth(self, client):
        r = client.post(
            "/api/v1/maas/governance/proposals",
            json={
                "title": "Should require authentication to create",
                "description": "This must be rejected without a valid API key.",
                "duration_hours": 1,
            },
        )
        assert r.status_code == 401


# ---------------------------------------------------------------------------
# Abstain vote
# ---------------------------------------------------------------------------

class TestAbstainVote:
    def test_abstain_vote_accepted(self, client, pro_token, free_token):
        pid = _create_proposal(client, pro_token)
        r = client.post(
            f"/api/v1/maas/governance/proposals/{pid}/vote",
            headers={"X-API-Key": free_token},
            json={"vote": "abstain"},
        )
        assert r.status_code == 200, r.text
        assert r.json()["status"] == "accepted"

    def test_abstain_vote_reflected_in_tally(self, client, pro_token, free_token):
        pid = _create_proposal(client, pro_token)
        client.post(
            f"/api/v1/maas/governance/proposals/{pid}/vote",
            headers={"X-API-Key": free_token},
            json={"vote": "abstain"},
        )
        r = client.get(f"/api/v1/maas/governance/proposals/{pid}")
        tally = r.json()["votes"]
        assert tally["abstain"] > 0


# ---------------------------------------------------------------------------
# _resolve_state: rejected path
# ---------------------------------------------------------------------------

class TestRejectedProposal:
    def test_rejected_proposal_cannot_execute(self, client, pro_token, free_token):
        """A proposal where 'no' > 'yes' resolves as 'rejected' → cannot execute."""
        pid = _create_proposal(client, pro_token)

        # Only NO votes — yes=0, no>0 → rejected
        client.post(
            f"/api/v1/maas/governance/proposals/{pid}/vote",
            headers={"X-API-Key": pro_token},
            json={"vote": "no"},
        )
        client.post(
            f"/api/v1/maas/governance/proposals/{pid}/vote",
            headers={"X-API-Key": free_token},
            json={"vote": "no"},
        )
        _force_passed(pid)

        r = client.post(
            f"/api/v1/maas/governance/proposals/{pid}/execute",
            headers={"X-API-Key": pro_token},
        )
        # Should be 400 — state is 'rejected', not 'passed'
        assert r.status_code == 400

    def test_rejected_state_visible_in_get(self, client, pro_token, free_token):
        """After deadline with only no votes, GET shows state=rejected."""
        pid = _create_proposal(client, pro_token)
        client.post(
            f"/api/v1/maas/governance/proposals/{pid}/vote",
            headers={"X-API-Key": pro_token},
            json={"vote": "no"},
        )
        _force_passed(pid)

        r = client.get(f"/api/v1/maas/governance/proposals/{pid}")
        assert r.status_code == 200
        assert r.json()["state"] == "rejected"

    def test_zero_votes_after_deadline_is_rejected(self, client, pro_token):
        """No votes at all → yes=0 is NOT > no=0 → rejected."""
        pid = _create_proposal(client, pro_token)
        _force_passed(pid)
        r = client.get(f"/api/v1/maas/governance/proposals/{pid}")
        assert r.json()["state"] == "rejected"


# ---------------------------------------------------------------------------
# _execute_action coverage (via proposal execution results)
# ---------------------------------------------------------------------------

class TestExecuteActionTypes:
    """
    Test all action types in _execute_action by creating proposals with those
    actions, then executing them and checking the results field.
    """

    def _create_and_execute(self, client, pro_token, free_token, actions):
        """Create proposal with given actions, force-pass it, execute, return results."""
        pid = _create_proposal(client, pro_token, actions=actions)
        # Vote yes with both users to ensure majority
        client.post(
            f"/api/v1/maas/governance/proposals/{pid}/vote",
            headers={"X-API-Key": pro_token},
            json={"vote": "yes"},
        )
        client.post(
            f"/api/v1/maas/governance/proposals/{pid}/vote",
            headers={"X-API-Key": free_token},
            json={"vote": "yes"},
        )
        _force_passed(pid)
        r = client.post(
            f"/api/v1/maas/governance/proposals/{pid}/execute",
            headers={"X-API-Key": pro_token},
        )
        assert r.status_code == 200, r.text
        return r.json()["results"]

    def test_rotate_keys_action_succeeds(self, client, pro_token, free_token):
        results = self._create_and_execute(
            client, pro_token, free_token,
            [{"type": "rotate_keys", "params": {}}],
        )
        assert len(results) == 1
        assert results[0]["action"] == "rotate_keys"
        assert results[0]["success"] is True

    def test_update_price_action_succeeds(self, client, pro_token, free_token):
        results = self._create_and_execute(
            client, pro_token, free_token,
            [{"type": "update_price", "params": {"base_price": 9.99}}],
        )
        assert results[0]["action"] == "update_price"
        assert results[0]["success"] is True

    def test_update_config_unsupported_key_fails(self, client, pro_token, free_token):
        """update_config with a key != global_price_multiplier → success=False."""
        results = self._create_and_execute(
            client, pro_token, free_token,
            [{"type": "update_config", "params": {"key": "unsupported_key", "value": 42}}],
        )
        assert results[0]["action"] == "update_config"
        assert results[0]["success"] is False

    def test_update_config_global_price_multiplier_succeeds(self, client, pro_token, free_token):
        """The known supported config key succeeds."""
        results = self._create_and_execute(
            client, pro_token, free_token,
            [{"type": "update_config", "params": {"key": "global_price_multiplier", "value": 1.2}}],
        )
        assert results[0]["action"] == "update_config"
        assert results[0]["success"] is True

    def test_multiple_actions_all_executed(self, client, pro_token, free_token):
        """Proposal with 2 actions → both are in results."""
        results = self._create_and_execute(
            client, pro_token, free_token,
            [
                {"type": "rotate_keys", "params": {}},
                {"type": "update_price", "params": {"base": 5.0}},
            ],
        )
        assert len(results) == 2

    def test_no_actions_produces_empty_results(self, client, pro_token, free_token):
        """Proposal with no actions → empty results list."""
        results = self._create_and_execute(client, pro_token, free_token, [])
        assert results == []


# ---------------------------------------------------------------------------
# Unit-style tests for governance utility functions (no TestClient needed)
# ---------------------------------------------------------------------------

class TestGovernanceUtilityFunctions:
    """Direct tests for _execute_action, _tally, _resolve_state, get_gov_power.

    These functions are tested without the HTTP layer (no TestClient needed).
    """

    def test_execute_action_unknown_type_returns_failure(self):
        """_execute_action with unhandled type (e.g. restart_node) → success=False."""
        from src.api.maas_governance import _execute_action
        result = _execute_action({"type": "restart_node", "params": {}})
        assert result["success"] is False
        assert "Unknown action type" in result["detail"]

    def test_execute_action_uses_action_type_key_fallback(self):
        """_execute_action reads 'action_type' key as fallback for 'type' missing."""
        from src.api.maas_governance import _execute_action
        result = _execute_action({"action_type": "rotate_keys", "params": {}})
        assert result["success"] is True
        assert result["action"] == "rotate_keys"

    def test_get_gov_power_known_plans(self):
        """get_gov_power returns correct power for each known plan."""
        from src.api.maas_governance import get_gov_power
        from src.database import User
        for plan, expected in [("free", 10.0), ("starter", 100.0), ("pro", 1000.0), ("enterprise", 10000.0)]:
            user = User(plan=plan)
            assert get_gov_power(user) == expected

    def test_get_gov_power_unknown_plan_defaults_to_10(self):
        """get_gov_power falls back to 10.0 for unrecognized plans."""
        from src.api.maas_governance import get_gov_power
        from src.database import User
        user = User(plan="custom-unknown-plan")
        assert get_gov_power(user) == 10.0

    def test_tally_empty_votes(self):
        """_tally with no votes → all zeroes."""
        from src.api.maas_governance import _tally
        proposal = GovernanceProposal(id="p1", title="T", description="D",
                                      state="active", votes=[])
        result = _tally(proposal)
        assert result == {"yes": 0.0, "no": 0.0, "abstain": 0.0}

    def test_tally_with_votes(self):
        """_tally applies quadratic formula: qv = sqrt(tokens / 100)."""
        import math
        from src.api.maas_governance import _tally
        votes = [
            GovernanceVote(voter_id="v1", vote="yes", tokens=10000.0),  # sqrt(100) = 10
            GovernanceVote(voter_id="v2", vote="no", tokens=2500.0),    # sqrt(25) = 5
        ]
        proposal = GovernanceProposal(id="p2", title="T", description="D",
                                      state="active", votes=votes)
        result = _tally(proposal)
        assert math.isclose(result["yes"], 10.0, rel_tol=1e-6)
        assert math.isclose(result["no"], 5.0, rel_tol=1e-6)
        assert result["abstain"] == 0.0

    def test_resolve_state_already_executed(self):
        """_resolve_state returns 'executed' immediately if proposal is already executed."""
        from src.api.maas_governance import _resolve_state
        proposal = GovernanceProposal(
            id="p3", title="T", description="D", state="executed",
            end_time=datetime.utcnow() - timedelta(hours=1), votes=[],
        )
        assert _resolve_state(proposal) == "executed"

    def test_resolve_state_non_active_non_executed_returns_current(self):
        """_resolve_state returns proposal.state for non-active, non-executed states."""
        from src.api.maas_governance import _resolve_state
        for state in ("cancelled", "rejected", "passed"):
            proposal = GovernanceProposal(
                id="px", title="T", description="D", state=state,
                end_time=datetime.utcnow() - timedelta(hours=1), votes=[],
            )
            assert _resolve_state(proposal) == state

    def test_compute_finality_hash_empty_votes_returns_hex_string(self):
        """_compute_finality_hash with no votes returns a 64-char hex SHA-256."""
        from src.api.maas_governance import _compute_finality_hash
        proposal = GovernanceProposal(
            id="fin-p1", title="T", description="D", state="passed", votes=[],
        )
        result = _compute_finality_hash(proposal, [])
        assert isinstance(result, str)
        assert len(result) == 64
        assert all(c in "0123456789abcdef" for c in result)

    def test_compute_finality_hash_is_deterministic(self):
        """Same inputs → same hash (deterministic serialization)."""
        from src.api.maas_governance import _compute_finality_hash
        votes = [
            GovernanceVote(voter_id="v1", vote="yes", tokens=500.0),
            GovernanceVote(voter_id="v2", vote="no", tokens=200.0),
        ]
        proposal = GovernanceProposal(
            id="fin-p2", title="T", description="D", state="passed", votes=votes,
        )
        results = [{"action": "rotate_keys", "success": True}]
        h1 = _compute_finality_hash(proposal, results)
        h2 = _compute_finality_hash(proposal, results)
        assert h1 == h2

    def test_compute_finality_hash_changes_with_different_votes(self):
        """Different vote set → different hash."""
        from src.api.maas_governance import _compute_finality_hash
        proposal_a = GovernanceProposal(
            id="fin-p3", title="T", description="D", state="passed",
            votes=[GovernanceVote(voter_id="v1", vote="yes", tokens=100.0)],
        )
        proposal_b = GovernanceProposal(
            id="fin-p3", title="T", description="D", state="passed",
            votes=[GovernanceVote(voter_id="v1", vote="no", tokens=100.0)],
        )
        assert _compute_finality_hash(proposal_a, []) != _compute_finality_hash(proposal_b, [])

    def test_resolve_state_active_with_future_deadline_stays_active(self):
        """Active proposal with deadline in the future → stays 'active'."""
        from src.api.maas_governance import _resolve_state
        proposal = GovernanceProposal(
            id="pa", title="T", description="D", state="active",
            end_time=datetime.utcnow() + timedelta(hours=24), votes=[],
        )
        assert _resolve_state(proposal) == "active"

    def test_resolve_state_active_past_deadline_yes_wins(self):
        """Active proposal, deadline passed, yes > no → 'passed'."""
        from src.api.maas_governance import _resolve_state
        votes = [
            GovernanceVote(voter_id="v1", vote="yes", tokens=10000.0),
            GovernanceVote(voter_id="v2", vote="no", tokens=100.0),
        ]
        proposal = GovernanceProposal(
            id="pb", title="T", description="D", state="active",
            end_time=datetime.utcnow() - timedelta(minutes=1), votes=votes,
        )
        assert _resolve_state(proposal) == "passed"

    def test_resolve_state_active_past_deadline_no_wins(self):
        """Active proposal, deadline passed, no > yes → 'rejected'."""
        from src.api.maas_governance import _resolve_state
        votes = [
            GovernanceVote(voter_id="v1", vote="yes", tokens=100.0),
            GovernanceVote(voter_id="v2", vote="no", tokens=10000.0),
        ]
        proposal = GovernanceProposal(
            id="pc", title="T", description="D", state="active",
            end_time=datetime.utcnow() - timedelta(minutes=1), votes=votes,
        )
        assert _resolve_state(proposal) == "rejected"

    def test_execute_action_update_config_supported_key_succeeds(self):
        """_execute_action update_config with global_price_multiplier → success=True."""
        from src.api.maas_governance import _execute_action
        result = _execute_action({
            "type": "update_config",
            "params": {"key": "global_price_multiplier", "value": 1.5},
        })
        assert result["success"] is True
        assert result["action"] == "update_config"

    def test_execute_action_update_config_unsupported_key_fails(self):
        """_execute_action update_config with unsupported key → success=False."""
        from src.api.maas_governance import _execute_action
        result = _execute_action({
            "type": "update_config",
            "params": {"key": "unknown_setting", "value": 999},
        })
        assert result["success"] is False
        assert "Unsupported config key" in result["detail"]

    def test_execute_action_update_price_succeeds(self):
        """_execute_action update_price → success=True."""
        from src.api.maas_governance import _execute_action
        result = _execute_action({
            "type": "update_price",
            "params": {"tier": "pro", "price": 99.0},
        })
        assert result["success"] is True
        assert result["action"] == "update_price"

    def test_execute_action_rotate_keys_via_type_key(self):
        """_execute_action rotate_keys via 'type' key → success=True."""
        from src.api.maas_governance import _execute_action
        result = _execute_action({"type": "rotate_keys", "params": {}})
        assert result["success"] is True
        assert "rotation" in result["detail"].lower()

    def test_tally_abstain_vote_counted(self):
        """_tally counts abstain votes via quadratic formula."""
        import math
        from src.api.maas_governance import _tally
        votes = [
            GovernanceVote(voter_id="v1", vote="abstain", tokens=400.0),  # sqrt(4) = 2
        ]
        proposal = GovernanceProposal(id="p5", title="T", description="D",
                                      state="active", votes=votes)
        result = _tally(proposal)
        assert math.isclose(result["abstain"], 2.0, rel_tol=1e-6)
        assert result["yes"] == 0.0
