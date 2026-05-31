"""Unit tests for src/api/maas/endpoints/pilot.py evidence behavior."""

from datetime import datetime
import json
from types import SimpleNamespace

import pytest
from fastapi import HTTPException

from src.api.maas.auth import UserContext
from src.api.maas.endpoints import pilot as pilot_module
from src.coordination.events import EventBus
from src.database import MeshInstance, User


class _Request:
    def __init__(self, bus: EventBus):
        self.state = SimpleNamespace(event_bus=bus)


class _Query:
    def __init__(self, value):
        self._value = value

    def filter(self, *_args, **_kwargs):
        return self

    def first(self):
        return self._value


class _FakeDb:
    def __init__(self, *, user=None, mesh=None, fail_commit=False):
        self.user = user
        self.mesh = mesh
        self.fail_commit = fail_commit
        self.added = []
        self.commit_count = 0
        self.rollback_count = 0

    def query(self, model):
        if model is User:
            return _Query(self.user)
        if model is MeshInstance:
            return _Query(self.mesh)
        return _Query(None)

    def add(self, value):
        self.added.append(value)
        if isinstance(value, User):
            self.user = value
        if isinstance(value, MeshInstance):
            self.mesh = value

    def commit(self):
        self.commit_count += 1
        if self.fail_commit:
            raise RuntimeError("private database failure")

    def rollback(self):
        self.rollback_count += 1


def _payloads(bus: EventBus, source_agent: str):
    return [
        event.data
        for event in bus.get_event_history(source_agent=source_agent, limit=20)
    ]


def test_activate_pilot_route_description_is_not_production_readiness_claim():
    route = next(
        route
        for route in pilot_module.router.routes
        if getattr(route, "path", "") == "/pilot/{pilot_id}/activate"
    )

    assert "ready for production use" not in (route.description or "")
    assert "not production readiness" in (route.description or "")


@pytest.mark.asyncio
async def test_pilot_signup_publishes_redacted_evidence(tmp_path):
    bus = EventBus(str(tmp_path))
    db = _FakeDb()
    request = pilot_module.PilotSignupRequest(
        email="pilot-secret@example.com",
        company="Private Pilot Company",
        contact_name="Private Pilot Contact",
        expected_users=7,
        use_case="Private mesh rollout details",
        region="eu",
    )

    response = await pilot_module.pilot_signup(
        request,
        http_request=_Request(bus),
        db=db,
    )
    payload = _payloads(bus, "maas-modular-pilot-signup")[-1]

    assert response.status == "pending_setup"
    assert payload["operation"] == "modular_pilot_signup"
    assert payload["service_name"] == "maas-modular-pilot-signup"
    assert payload["layer"] == "api_modular_pilot_signup_control_action"
    assert payload["status"] == "success"
    assert payload["http_status_code"] == 201
    assert payload["request_summary"]["email_hash"] == (
        pilot_module._redacted_sha256_prefix("pilot-secret@example.com")
    )
    assert payload["request_summary"]["expected_users"] == 7
    assert payload["request_summary"]["region"] == "eu"
    assert payload["db_evidence"]["commit_succeeded"] is True
    assert payload["mesh_summary"]["join_token_present"] is True
    assert payload["onboarding_url_present"] is True
    assert payload["billing_setup_url_present"] is True
    assert payload["claim_gate"]["local_api_db_lifecycle_claim_allowed"] is True
    assert payload["claim_gate"]["production_readiness_claim_allowed"] is False
    assert payload["claim_gate"]["production_customer_usage_claim_allowed"] is False
    assert payload["claim_gate"]["mesh_dataplane_reachability_claim_allowed"] is False

    raw_log = (tmp_path / ".agent_coordination" / "events.log").read_text(
        encoding="utf-8"
    )
    serialized = json.dumps(payload, sort_keys=True)
    raw_values = (
        "pilot-secret@example.com",
        "Private Pilot Company",
        "Private Pilot Contact",
        "Private mesh rollout details",
        response.pilot_id,
        response.user_id,
        response.mesh_id,
        response.onboarding_url,
        response.billing_setup_url,
        getattr(db.mesh, "join_token"),
    )
    for value in raw_values:
        assert value not in serialized
        assert value not in raw_log


@pytest.mark.asyncio
async def test_pilot_status_and_activate_publish_redacted_evidence(tmp_path):
    bus = EventBus(str(tmp_path))
    pilot_id = "private-pilot-id"
    user_id = f"pilot-{pilot_id}"
    mesh_id = "private-mesh-id"
    db_user = SimpleNamespace(
        id=user_id,
        stripe_subscription_id=None,
        stripe_customer_id="private-stripe-customer",
        created_at=datetime(2026, 5, 30, 12, 0, 0),
    )
    mesh = SimpleNamespace(
        id=mesh_id,
        owner_id=user_id,
        status="setup",
        nodes=11,
        join_token="private-join-token",
    )
    db = _FakeDb(user=db_user, mesh=mesh)
    actor = UserContext(user_id=user_id, plan="pilot")
    actor.role = "user"
    admin = UserContext(user_id="admin-secret", plan="enterprise")
    admin.role = "admin"

    status_response = await pilot_module.get_pilot_status(
        pilot_id,
        http_request=_Request(bus),
        user=actor,
        db=db,
    )
    activate_response = await pilot_module.activate_pilot(
        pilot_id,
        http_request=_Request(bus),
        user=admin,
        db=db,
    )

    status_payload = _payloads(bus, "maas-modular-pilot-status-read")[-1]
    activate_payload = _payloads(bus, "maas-modular-pilot-activate")[-1]

    assert status_response.billing_status == "customer_created"
    assert activate_response["mesh_id"] == mesh_id
    assert activate_response["claim_gate"]["local_api_db_lifecycle_claim_allowed"] is True
    assert activate_response["claim_gate"]["production_readiness_claim_allowed"] is False
    assert "production customer usage" in activate_response["claim_boundary"]
    assert mesh.status == "active"
    assert status_payload["observed_state"] is True
    assert status_payload["billing_status"] == "customer_created"
    assert status_payload["claim_gate"]["local_api_db_lifecycle_claim_allowed"] is True
    assert status_payload["claim_gate"]["production_readiness_claim_allowed"] is False
    assert status_payload["db_evidence"]["mesh_found"] is True
    assert activate_payload["control_action"] is True
    assert activate_payload["stage"] == "pilot_activated"
    assert activate_payload["db_evidence"]["commit_succeeded"] is True
    assert activate_payload["mesh_summary"]["status"] == "active"
    assert activate_payload["claim_gate"]["local_api_db_lifecycle_claim_allowed"] is True
    assert activate_payload["claim_gate"]["onboarding_delivery_claim_allowed"] is False
    assert activate_payload["claim_gate"]["billing_setup_claim_allowed"] is False
    assert activate_payload["claim_gate"]["production_customer_usage_claim_allowed"] is False
    assert activate_payload["claim_gate"]["production_readiness_claim_allowed"] is False

    all_payloads = [status_payload, activate_payload]
    raw_log = (tmp_path / ".agent_coordination" / "events.log").read_text(
        encoding="utf-8"
    )
    serialized = json.dumps(all_payloads, sort_keys=True)
    for value in (
        pilot_id,
        user_id,
        mesh_id,
        "admin-secret",
        "private-stripe-customer",
        "private-join-token",
    ):
        assert value not in serialized
        assert value not in raw_log


@pytest.mark.asyncio
async def test_pilot_blocked_paths_publish_redacted_evidence(tmp_path):
    bus = EventBus(str(tmp_path))
    pilot_id = "blocked-pilot-secret"
    db = _FakeDb(user=SimpleNamespace(id=f"pilot-{pilot_id}"), mesh=None)
    non_owner = UserContext(user_id="not-owner-secret", plan="pilot")
    non_owner.role = "user"

    with pytest.raises(HTTPException) as status_error:
        await pilot_module.get_pilot_status(
            pilot_id,
            http_request=_Request(bus),
            user=non_owner,
            db=db,
        )
    with pytest.raises(HTTPException) as activate_error:
        await pilot_module.activate_pilot(
            pilot_id,
            http_request=_Request(bus),
            user=non_owner,
            db=db,
        )

    status_payload = _payloads(bus, "maas-modular-pilot-status-read")[-1]
    activate_payload = _payloads(bus, "maas-modular-pilot-activate")[-1]

    assert status_error.value.status_code == 403
    assert activate_error.value.status_code == 403
    assert status_payload["stage"] == "status_access_denied"
    assert status_payload["reason"] == "access_denied"
    assert status_payload["claim_gate"]["local_api_db_lifecycle_claim_allowed"] is False
    assert status_payload["claim_gate"]["production_readiness_claim_allowed"] is False
    assert activate_payload["stage"] == "activate_access_denied"
    assert activate_payload["reason"] == "admin_required"
    assert activate_payload["claim_gate"]["local_api_db_lifecycle_claim_allowed"] is False
    assert activate_payload["claim_gate"]["production_readiness_claim_allowed"] is False

    raw_log = (tmp_path / ".agent_coordination" / "events.log").read_text(
        encoding="utf-8"
    )
    serialized = json.dumps([status_payload, activate_payload], sort_keys=True)
    for value in (pilot_id, f"pilot-{pilot_id}", "not-owner-secret"):
        assert value not in serialized
        assert value not in raw_log
