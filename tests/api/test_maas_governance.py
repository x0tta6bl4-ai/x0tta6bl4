"""
Integration tests for MaaS Governance (DB-backed persistence + finality hash).
"""

import os
import uuid
import pytest
from fastapi.testclient import TestClient
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker

from src.core.app import app
from src.database import Base, get_db, User, GovernanceProposal, GovernanceVote

_TEST_DB_PATH = f"./test_gov_{uuid.uuid4().hex}.db"
SQLALCHEMY_DATABASE_URL = f"sqlite:///{_TEST_DB_PATH}"
engine = create_engine(SQLALCHEMY_DATABASE_URL, connect_args={"check_same_thread": False})
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
    """Register a 'pro' plan user and return their token."""
    email = f"pro-gov-{uuid.uuid4().hex}@test.com"
    r = client.post("/api/v1/maas/auth/register",
                    json={"email": email, "password": "password123"})
    assert r.status_code == 200
    token = r.json()["access_token"]

    # Upgrade to pro plan in DB
    db = TestingSessionLocal()
    u = db.query(User).filter(User.api_key == token).first()
    u.plan = "pro"
    db.commit()
    db.close()
    return token


@pytest.fixture(scope="module")
def free_token(client):
    email = f"free-gov-{uuid.uuid4().hex}@test.com"
    r = client.post("/api/v1/maas/auth/register",
                    json={"email": email, "password": "password123"})
    assert r.status_code == 200
    return r.json()["access_token"]


# ─────────────────────────────────────────────
# Proposal creation
# ─────────────────────────────────────────────

class TestProposalCreation:
    def test_pro_can_create_proposal(self, client, pro_token):
        r = client.post(
            "/api/v1/maas/governance/proposals",
            headers={"X-API-Key": pro_token},
            json={
                "title": "Set global price multiplier to 1.5",
                "description": "Increase infrastructure pricing by 50% to reflect demand.",
                "duration_hours": 1,
                "actions": [
                    {"type": "update_config", "params": {"key": "global_price_multiplier", "value": 1.5}}
                ],
            },
        )
        assert r.status_code == 200, r.text
        data = r.json()
        assert "proposal_id" in data
        assert data["status"] == "active"
        assert "expires_at" in data

    def test_free_user_cannot_create_proposal(self, client, free_token):
        r = client.post(
            "/api/v1/maas/governance/proposals",
            headers={"X-API-Key": free_token},
            json={
                "title": "Unauthorized proposal attempt by free user",
                "description": "This should be rejected by the governance system.",
                "duration_hours": 1,
            },
        )
        assert r.status_code == 403

    def test_proposal_persisted_to_db(self, client, pro_token):
        r = client.post(
            "/api/v1/maas/governance/proposals",
            headers={"X-API-Key": pro_token},
            json={
                "title": "Proposal that must survive server restart",
                "description": "Verifying DB persistence by checking ORM directly.",
                "duration_hours": 2,
            },
        )
        pid = r.json()["proposal_id"]

        db = TestingSessionLocal()
        row = db.query(GovernanceProposal).filter(GovernanceProposal.id == pid).first()
        db.close()
        assert row is not None
        assert row.title == "Proposal that must survive server restart"
        assert row.state == "active"

    def test_list_proposals_returns_created(self, client, pro_token):
        r_create = client.post(
            "/api/v1/maas/governance/proposals",
            headers={"X-API-Key": pro_token},
            json={
                "title": "Proposal to test listing endpoint",
                "description": "Should appear in GET /proposals response list.",
                "duration_hours": 1,
            },
        )
        pid = r_create.json()["proposal_id"]

        r_list = client.get("/api/v1/maas/governance/proposals")
        assert r_list.status_code == 200
        ids = [p["id"] for p in r_list.json()["proposals"]]
        assert pid in ids


# ─────────────────────────────────────────────
# Voting
# ─────────────────────────────────────────────

class TestVoting:
    def _create_proposal(self, client, pro_token) -> str:
        r = client.post(
            "/api/v1/maas/governance/proposals",
            headers={"X-API-Key": pro_token},
            json={
                "title": "Vote test proposal unique title here",
                "description": "A proposal created specifically to test voting mechanics.",
                "duration_hours": 1,
            },
        )
        assert r.status_code == 200
        return r.json()["proposal_id"]

    def test_vote_yes(self, client, pro_token, free_token):
        pid = self._create_proposal(client, pro_token)

        r = client.post(
            f"/api/v1/maas/governance/proposals/{pid}/vote",
            headers={"X-API-Key": free_token},
            json={"vote": "yes"},
        )
        assert r.status_code == 200, r.text
        data = r.json()
        assert data["status"] == "accepted"
        # Default plan at registration is "starter" (100.0 power)
        assert data["voting_power_used"] == 100.0
        assert abs(data["quadratic_weight"] - 100.0 ** 0.5) < 0.01

    def test_vote_persisted_to_db(self, client, pro_token, free_token):
        pid = self._create_proposal(client, pro_token)

        client.post(
            f"/api/v1/maas/governance/proposals/{pid}/vote",
            headers={"X-API-Key": free_token},
            json={"vote": "no"},
        )

        db = TestingSessionLocal()
        vote = db.query(GovernanceVote).filter(GovernanceVote.proposal_id == pid).first()
        db.close()
        assert vote is not None
        assert vote.vote == "no"

    def test_no_double_vote(self, client, pro_token, free_token):
        pid = self._create_proposal(client, pro_token)

        client.post(
            f"/api/v1/maas/governance/proposals/{pid}/vote",
            headers={"X-API-Key": free_token},
            json={"vote": "yes"},
        )
        r2 = client.post(
            f"/api/v1/maas/governance/proposals/{pid}/vote",
            headers={"X-API-Key": free_token},
            json={"vote": "no"},
        )
        assert r2.status_code == 409

    def test_vote_on_nonexistent_proposal(self, client, free_token):
        r = client.post(
            "/api/v1/maas/governance/proposals/prop-nonexistent/vote",
            headers={"X-API-Key": free_token},
            json={"vote": "yes"},
        )
        assert r.status_code == 404


# ─────────────────────────────────────────────
# Execution & finality hash
# ─────────────────────────────────────────────

class TestExecution:
    def _create_and_pass_proposal(self, client, pro_token, free_token) -> str:
        """Create a proposal that immediately 'passes' (0-hour duration for instant expiry)."""
        r = client.post(
            "/api/v1/maas/governance/proposals",
            headers={"X-API-Key": pro_token},
            json={
                "title": "Execute price multiplier change immediately",
                "description": "A proposal with 1-hour window to test execution flow.",
                "duration_hours": 1,
                "actions": [
                    {"type": "update_config",
                     "params": {"key": "global_price_multiplier", "value": 2.0}}
                ],
            },
        )
        pid = r.json()["proposal_id"]

        # Both users vote yes to guarantee majority
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

        # Force state to 'passed' in DB (simulating deadline expiry)
        db = TestingSessionLocal()
        from datetime import timedelta
        prop = db.query(GovernanceProposal).filter(GovernanceProposal.id == pid).first()
        prop.end_time = prop.end_time - timedelta(hours=2)  # Push deadline into the past
        db.commit()
        db.close()
        return pid

    def test_execute_passed_proposal(self, client, pro_token, free_token):
        pid = self._create_and_pass_proposal(client, pro_token, free_token)

        r = client.post(
            f"/api/v1/maas/governance/proposals/{pid}/execute",
            headers={"X-API-Key": pro_token},
        )
        assert r.status_code == 200, r.text
        data = r.json()
        assert data["status"] == "executed"
        assert "finality_hash" in data
        assert len(data["finality_hash"]) == 64  # SHA-256 hex digest

    def test_finality_hash_persisted(self, client, pro_token, free_token):
        pid = self._create_and_pass_proposal(client, pro_token, free_token)
        r = client.post(
            f"/api/v1/maas/governance/proposals/{pid}/execute",
            headers={"X-API-Key": pro_token},
        )
        fh = r.json()["finality_hash"]

        db = TestingSessionLocal()
        prop = db.query(GovernanceProposal).filter(GovernanceProposal.id == pid).first()
        db.close()
        assert prop.execution_hash == fh
        assert prop.executed_at is not None
        assert prop.state == "executed"

    def test_cannot_execute_twice(self, client, pro_token, free_token):
        pid = self._create_and_pass_proposal(client, pro_token, free_token)
        client.post(
            f"/api/v1/maas/governance/proposals/{pid}/execute",
            headers={"X-API-Key": pro_token},
        )
        r2 = client.post(
            f"/api/v1/maas/governance/proposals/{pid}/execute",
            headers={"X-API-Key": pro_token},
        )
        assert r2.status_code == 400
        assert "already executed" in r2.json()["detail"].lower()

    def test_cannot_execute_active_proposal(self, client, pro_token, free_token):
        r = client.post(
            "/api/v1/maas/governance/proposals",
            headers={"X-API-Key": pro_token},
            json={
                "title": "Active proposal cannot be executed yet",
                "description": "This proposal has a future deadline and must not execute.",
                "duration_hours": 48,
            },
        )
        pid = r.json()["proposal_id"]

        r_exec = client.post(
            f"/api/v1/maas/governance/proposals/{pid}/execute",
            headers={"X-API-Key": pro_token},
        )
        assert r_exec.status_code == 400

    def test_get_proposal_details(self, client, pro_token, free_token):
        pid = self._create_and_pass_proposal(client, pro_token, free_token)
        client.post(
            f"/api/v1/maas/governance/proposals/{pid}/execute",
            headers={"X-API-Key": pro_token},
        )

        r = client.get(f"/api/v1/maas/governance/proposals/{pid}")
        assert r.status_code == 200
        data = r.json()
        assert data["state"] == "executed"
        assert data["execution_hash"] is not None
        assert data["executed_at"] is not None
        assert data["votes"]["yes"] > 0

    def test_finality_hash_is_deterministic(self, client, pro_token, free_token):
        """Same votes + results must produce the same hash."""
        pid = self._create_and_pass_proposal(client, pro_token, free_token)
        r = client.post(
            f"/api/v1/maas/governance/proposals/{pid}/execute",
            headers={"X-API-Key": pro_token},
        )
        fh1 = r.json()["finality_hash"]

        # Re-compute manually using the same function
        import hashlib, json
        db = TestingSessionLocal()
        prop = db.query(GovernanceProposal).filter(GovernanceProposal.id == pid).first()
        db.refresh(prop)
        vote_records = sorted(
            [(v.voter_id, v.vote, v.tokens) for v in prop.votes],
            key=lambda x: x[0],
        )
        actions = json.loads(prop.actions_json) if prop.actions_json else []
        # Replicate execution results
        results = [{"action": "update_config", "success": True,
                    "detail": "Multiplier 2.0 applied"}]
        payload = json.dumps(
            {"proposal_id": pid, "votes": vote_records, "results": results},
            sort_keys=True,
        ).encode()
        fh2 = hashlib.sha256(payload).hexdigest()
        db.close()

        assert fh1 == fh2
