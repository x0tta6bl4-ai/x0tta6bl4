"""Unit tests for MaaS DB-backed policy EventBus evidence."""

from __future__ import annotations

import asyncio
import json
from datetime import datetime
from types import SimpleNamespace

import pytest
from fastapi import HTTPException

import src.api.maas_policies as policies_mod
from src.coordination.events import EventBus, EventType


def _request(bus: EventBus):
    return SimpleNamespace(state=SimpleNamespace(event_bus=bus))


def _payloads(bus: EventBus, source_agent: str):
    return [
        event.data
        for event in bus.get_event_history(
            event_type=EventType.PIPELINE_STAGE_END,
            source_agent=source_agent,
            limit=10,
        )
    ]


class _Query:
    def __init__(self, *, all_results=None, first_result=None):
        self._all_results = list(all_results or [])
        self._first_result = first_result

    def filter(self, *_args, **_kwargs):
        return self

    def all(self):
        return list(self._all_results)

    def first(self):
        return self._first_result


class _PolicyDb:
    def __init__(self, *, policies=None, first_policy=None):
        self.policies = list(policies or [])
        self.first_policy = first_policy
        self.added = []
        self.deleted = []
        self.commits = 0

    def query(self, _model):
        return _Query(all_results=self.policies, first_result=self.first_policy)

    def add(self, policy):
        self.added.append(policy)

    def delete(self, policy):
        self.deleted.append(policy)

    def commit(self):
        self.commits += 1

    def refresh(self, _policy):
        return None


def test_db_policy_list_publishes_redacted_observed_state(tmp_path):
    email = "policy-list-secret@example.test"
    user_id = "policy-list-user-secret"
    mesh_id = "policy-list-mesh-secret"
    policy_id = "policy-list-id-secret"
    source_tag = "policy-list-source-tag-secret"
    target_tag = "policy-list-target-tag-secret"
    bus = EventBus(str(tmp_path))
    request = _request(bus)
    user = SimpleNamespace(id=user_id, email=email, role="operator")
    policy = SimpleNamespace(
        id=policy_id,
        mesh_id=mesh_id,
        source_tag=source_tag,
        target_tag=target_tag,
        action="deny",
        created_at=datetime(2026, 5, 30, 12, 0, 0),
    )
    db = _PolicyDb(policies=[policy])

    result = policies_mod.list_policies(
        mesh_id,
        request,
        current_user=user,
        db=db,
    )

    assert result == [policy]
    payloads = _payloads(bus, "maas-policies-list-read")
    assert len(payloads) == 1
    payload = payloads[0]
    assert payload["operation"] == "maas_policies_list_read"
    assert payload["service_name"] == "maas-policies-list-read"
    assert payload["layer"] == "api_policy_acl_observed_state"
    assert payload["actor_user_id_hash"] == policies_mod._redacted_sha256_prefix(user_id)
    assert payload["mesh_id_hash"] == policies_mod._redacted_sha256_prefix(mesh_id)
    assert payload["policies_count"] == 1
    assert payload["policy_action_counts"]["deny"] == 1
    assert payload["route_shadowed_by_legacy"] is True
    assert payload["read_only"] is True
    assert payload["observed_state"] is True
    assert payload["control_action"] is False

    serialized = json.dumps(payloads, sort_keys=True)
    raw_log = (tmp_path / ".agent_coordination" / "events.log").read_text(
        encoding="utf-8"
    )
    for raw_value in (
        email,
        user_id,
        mesh_id,
        policy_id,
        source_tag,
        target_tag,
    ):
        assert raw_value not in serialized
        assert raw_value not in raw_log


def test_db_policy_create_publishes_redacted_control_evidence(tmp_path):
    email = "policy-create-secret@example.test"
    user_id = "policy-create-user-secret"
    mesh_id = "policy-create-mesh-secret"
    source_tag = "policy-create-source-tag-secret"
    target_tag = "policy-create-target-tag-secret"
    bus = EventBus(str(tmp_path))
    request = _request(bus)
    user = SimpleNamespace(id=user_id, email=email, role="admin")
    db = _PolicyDb()

    result = asyncio.run(
        policies_mod.create_policy(
            mesh_id,
            policies_mod.PolicyRequest(
                source_tag=source_tag,
                target_tag=target_tag,
                action="allow",
            ),
            request,
            current_user=user,
            db=db,
        )
    )

    assert result in db.added
    assert db.commits == 1
    payloads = _payloads(bus, "maas-policies-create")
    assert len(payloads) == 1
    payload = payloads[0]
    assert payload["operation"] == "maas_policies_create"
    assert payload["service_name"] == "maas-policies-create"
    assert payload["layer"] == "api_policy_acl_control_action"
    assert payload["mesh_id_hash"] == policies_mod._redacted_sha256_prefix(mesh_id)
    assert payload["policy_id_hash"] == policies_mod._redacted_sha256_prefix(result.id)
    assert payload["action_bucket"] == "allow"
    assert payload["route_shadowed_by_legacy"] is True
    assert payload["control_action"] is True
    assert payload["read_only"] is False

    serialized = json.dumps(payloads, sort_keys=True)
    raw_log = (tmp_path / ".agent_coordination" / "events.log").read_text(
        encoding="utf-8"
    )
    for raw_value in (
        email,
        user_id,
        mesh_id,
        result.id,
        source_tag,
        target_tag,
    ):
        assert raw_value not in serialized
        assert raw_value not in raw_log


def test_db_policy_delete_publishes_success_and_not_found_evidence(tmp_path):
    email = "policy-delete-secret@example.test"
    user_id = "policy-delete-user-secret"
    mesh_id = "policy-delete-mesh-secret"
    policy_id = "policy-delete-id-secret"
    missing_policy_id = "policy-delete-missing-secret"
    source_tag = "policy-delete-source-tag-secret"
    target_tag = "policy-delete-target-tag-secret"
    bus = EventBus(str(tmp_path))
    request = _request(bus)
    user = SimpleNamespace(id=user_id, email=email, role="admin")
    policy = SimpleNamespace(
        id=policy_id,
        mesh_id=mesh_id,
        source_tag=source_tag,
        target_tag=target_tag,
        action="deny",
    )
    db = _PolicyDb(first_policy=policy)

    result = asyncio.run(
        policies_mod.delete_policy(
            mesh_id,
            policy_id,
            request,
            current_user=user,
            db=db,
        )
    )

    assert result == {"status": "deleted", "policy_id": policy_id}
    assert db.deleted == [policy]
    payloads = _payloads(bus, "maas-policies-delete")
    assert len(payloads) == 1
    success_payload = payloads[0]
    assert success_payload["operation"] == "maas_policies_delete"
    assert success_payload["status"] == "success"
    assert success_payload["policy_id_hash"] == policies_mod._redacted_sha256_prefix(
        policy_id
    )
    assert success_payload["action_bucket"] == "deny"
    assert success_payload["route_shadowed_by_legacy"] is False
    assert success_payload["control_action"] is True

    with pytest.raises(HTTPException) as exc:
        asyncio.run(
            policies_mod.delete_policy(
                mesh_id,
                missing_policy_id,
                request,
                current_user=user,
                db=_PolicyDb(first_policy=None),
            )
        )
    assert exc.value.status_code == 404
    payloads = _payloads(bus, "maas-policies-delete")
    assert len(payloads) == 2
    denied_payload = payloads[1]
    assert denied_payload["status"] == "denied"
    assert denied_payload["http_status_code"] == 404
    assert denied_payload["reason"] == "policy_not_found"

    serialized = json.dumps(payloads, sort_keys=True)
    raw_log = (tmp_path / ".agent_coordination" / "events.log").read_text(
        encoding="utf-8"
    )
    for raw_value in (
        email,
        user_id,
        mesh_id,
        policy_id,
        missing_policy_id,
        source_tag,
        target_tag,
    ):
        assert raw_value not in serialized
        assert raw_value not in raw_log
