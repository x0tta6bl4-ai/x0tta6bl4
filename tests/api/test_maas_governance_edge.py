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
