"""Unit tests for legacy MaaS token and policy lifecycle EventBus evidence."""

import asyncio
import json
from datetime import datetime, timedelta
from types import SimpleNamespace

import pytest
from fastapi import HTTPException

import src.api.maas_legacy as legacy_mod
from src.coordination.events import EventBus, EventType


class _Provisioner:
    def __init__(self, instances):
        self.instances = {instance.mesh_id: instance for instance in instances}

    def get(self, mesh_id):
        return self.instances.get(mesh_id)


class _Mesh:
    def __init__(self, *, mesh_id: str, owner_id: str, join_token: str):
        self.mesh_id = mesh_id
        self.owner_id = owner_id
        self.join_token = join_token
        self.join_token_issued_at = datetime.utcnow()
        self.join_token_expires_at = datetime.utcnow() + timedelta(hours=1)
        self.join_token_ttl_sec = 3600
        self.node_instances = {}


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


def _install_state(monkeypatch, instance: _Mesh):
    monkeypatch.setattr(legacy_mod, "mesh_provisioner", _Provisioner([instance]))
    monkeypatch.setattr(legacy_mod, "_mesh_policies", {})
    monkeypatch.setattr(legacy_mod, "_mesh_audit_log", {})


def test_legacy_join_token_rotation_publishes_redacted_lifecycle_evidence(
    monkeypatch,
    tmp_path,
):
    mesh_id = "mesh-secret-token-rotate"
    owner_id = "owner-secret-token-rotate"
    old_token = "old-join-token-secret"
    new_token = "new-join-token-secret"
    bus = EventBus(str(tmp_path))
    request = _request(bus)
    instance = _Mesh(mesh_id=mesh_id, owner_id=owner_id, join_token=old_token)
    _install_state(monkeypatch, instance)
    monkeypatch.setattr(legacy_mod.secrets, "token_urlsafe", lambda _n: new_token)

    result = legacy_mod.rotate_join_token(
        mesh_id,
        ttl_seconds=7200,
        current_user=SimpleNamespace(id=owner_id, role="admin"),
        request=request,
    )

    assert result.join_token == new_token
    assert instance.join_token == new_token

    payloads = _payloads(bus, "maas-legacy-token-lifecycle")
    assert len(payloads) == 1
    payload = payloads[0]
    assert payload["operation"] == "legacy_join_token_rotate"
    assert payload["service_name"] == "maas-legacy-token-lifecycle"
    assert payload["source_alias"] == "maas-legacy-token-lifecycle"
    assert payload["layer"] == "api_legacy_token_lifecycle_control_action"
    assert payload["stage"] == "rotated"
    assert payload["status"] == "success"
    assert payload["mesh_id_hash"] == legacy_mod._redacted_sha256_prefix(mesh_id)
    assert payload["owner_id_hash"] == legacy_mod._redacted_sha256_prefix(owner_id)
    assert payload["request_summary"]["ttl_seconds"] == 7200
    assert payload["token_rotated"] is True
    assert payload["join_token_issued"] is True
    assert payload["control_action"] is True
    assert payload["raw_identifiers_redacted"] is True

    serialized = json.dumps(payloads, sort_keys=True)
    raw_log = (tmp_path / ".agent_coordination" / "events.log").read_text(
        encoding="utf-8"
    )
    for raw_value in (mesh_id, owner_id, old_token, new_token):
        assert raw_value not in serialized
        assert raw_value not in raw_log


def test_legacy_policy_create_publishes_redacted_lifecycle_evidence(
    monkeypatch,
    tmp_path,
):
    mesh_id = "mesh-secret-policy-create"
    owner_id = "owner-secret-policy-create"
    source_tag = "robot-secret-tag"
    target_tag = "gateway-secret-tag"
    bus = EventBus(str(tmp_path))
    request = _request(bus)
    instance = _Mesh(
        mesh_id=mesh_id,
        owner_id=owner_id,
        join_token="policy-join-token-secret",
    )
    _install_state(monkeypatch, instance)
    monkeypatch.setattr(
        legacy_mod.uuid,
        "uuid4",
        lambda: SimpleNamespace(hex="policysecret123456"),
    )

    result = asyncio.run(
        legacy_mod.create_policy(
            mesh_id,
            legacy_mod.PolicyRequest(
                source_tag=source_tag,
                target_tag=target_tag,
                action="deny",
            ),
            SimpleNamespace(id=owner_id, role="admin"),
            request=request,
        )
    )

    assert result.policy_id == "policy-policyse"
    assert result.source_tag == source_tag
    assert legacy_mod._mesh_policies[mesh_id][0]["target_tag"] == target_tag

    payloads = _payloads(bus, "maas-legacy-policy-lifecycle")
    assert len(payloads) == 1
    payload = payloads[0]
    assert payload["operation"] == "legacy_policy_create"
    assert payload["service_name"] == "maas-legacy-policy-lifecycle"
    assert payload["source_alias"] == "maas-legacy-policy-lifecycle"
    assert payload["layer"] == "api_legacy_policy_lifecycle_control_action"
    assert payload["stage"] == "created"
    assert payload["status"] == "success"
    assert payload["mesh_id_hash"] == legacy_mod._redacted_sha256_prefix(mesh_id)
    assert payload["owner_id_hash"] == legacy_mod._redacted_sha256_prefix(owner_id)
    assert payload["request_summary"]["policy_id_hash"] == (
        legacy_mod._redacted_sha256_prefix(result.policy_id)
    )
    assert payload["request_summary"]["source_tag_hash"] == (
        legacy_mod._redacted_sha256_prefix(source_tag)
    )
    assert payload["request_summary"]["target_tag_hash"] == (
        legacy_mod._redacted_sha256_prefix(target_tag)
    )
    assert payload["request_summary"]["action"] == "deny"
    assert payload["policy_registry_mutated"] is True
    assert payload["audit_recorded"] is True
    assert payload["control_action"] is True
    assert payload["raw_identifiers_redacted"] is True

    serialized = json.dumps(payloads, sort_keys=True)
    raw_log = (tmp_path / ".agent_coordination" / "events.log").read_text(
        encoding="utf-8"
    )
    for raw_value in (mesh_id, owner_id, result.policy_id, source_tag, target_tag):
        assert raw_value not in serialized
        assert raw_value not in raw_log


def test_legacy_policy_create_denial_publishes_redacted_evidence(
    monkeypatch,
    tmp_path,
):
    mesh_id = "mesh-secret-policy-denied"
    owner_id = "owner-secret-policy-denied"
    source_tag = "sensor-secret-tag"
    target_tag = "server-secret-tag"
    bus = EventBus(str(tmp_path))
    request = _request(bus)

    from src.api.maas import registry as modular_registry

    monkeypatch.setattr(legacy_mod, "mesh_provisioner", _Provisioner([]))
    monkeypatch.setattr(modular_registry, "get_mesh", lambda _mesh_id: None)

    with pytest.raises(HTTPException) as exc:
        asyncio.run(
            legacy_mod.create_policy(
                mesh_id,
                legacy_mod.PolicyRequest(
                    source_tag=source_tag,
                    target_tag=target_tag,
                    action="allow",
                ),
                SimpleNamespace(id=owner_id, role="admin"),
                request=request,
            )
        )

    assert exc.value.status_code == 404

    payloads = _payloads(bus, "maas-legacy-policy-lifecycle")
    assert len(payloads) == 1
    payload = payloads[0]
    assert payload["operation"] == "legacy_policy_create"
    assert payload["stage"] == "access_denied"
    assert payload["status"] == "denied"
    assert payload["reason"] == "mesh_not_found_or_forbidden"
    assert payload["policy_registry_mutated"] is False
    assert payload["mesh_id_hash"] == legacy_mod._redacted_sha256_prefix(mesh_id)
    assert payload["actor_user_id_hash"] == legacy_mod._redacted_sha256_prefix(owner_id)

    serialized = json.dumps(payloads, sort_keys=True)
    raw_log = (tmp_path / ".agent_coordination" / "events.log").read_text(
        encoding="utf-8"
    )
    for raw_value in (mesh_id, owner_id, source_tag, target_tag):
        assert raw_value not in serialized
        assert raw_value not in raw_log


def test_legacy_policy_list_publishes_redacted_read_evidence(
    monkeypatch,
    tmp_path,
):
    mesh_id = "mesh-secret-policy-list"
    owner_id = "owner-secret-policy-list"
    source_tag = "frontend-secret-tag"
    target_tag = "backend-secret-tag"
    policy_id = "policy-secret-list"
    bus = EventBus(str(tmp_path))
    request = _request(bus)
    instance = _Mesh(
        mesh_id=mesh_id,
        owner_id=owner_id,
        join_token="policy-list-token-secret",
    )
    _install_state(monkeypatch, instance)
    legacy_mod._mesh_policies[mesh_id] = [
        {
            "id": policy_id,
            "source_tag": source_tag,
            "target_tag": target_tag,
            "action": "allow",
            "created_at": datetime.utcnow().isoformat(),
        }
    ]

    result = asyncio.run(
        legacy_mod.legacy_list_policies_route(
            mesh_id=mesh_id,
            request=request,
            current_user=SimpleNamespace(id=owner_id, role="admin"),
        )
    )

    assert result["policies"][0]["id"] == policy_id
    assert result["policies"][0]["source_tag"] == source_tag

    payloads = _payloads(bus, "maas-legacy-policy-read")
    assert len(payloads) == 1
    payload = payloads[0]
    assert payload["operation"] == "legacy_policy_list_read"
    assert payload["service_name"] == "maas-legacy-policy-read"
    assert payload["source_alias"] == "maas-legacy-policy-read"
    assert payload["layer"] == "api_legacy_policy_observed_state"
    assert payload["stage"] == "policy_list_read"
    assert payload["status"] == "success"
    assert payload["mesh_id_hash"] == legacy_mod._redacted_sha256_prefix(mesh_id)
    assert payload["owner_id_hash"] == legacy_mod._redacted_sha256_prefix(owner_id)
    assert payload["result_summary"]["policy_count"] == 1
    assert payload["result_summary"]["action_counts"] == {"allow": 1}
    assert payload["read_only"] is True
    assert payload["control_action"] is False
    assert payload["raw_identifiers_redacted"] is True

    serialized = json.dumps(payloads, sort_keys=True)
    raw_log = (tmp_path / ".agent_coordination" / "events.log").read_text(
        encoding="utf-8"
    )
    for raw_value in (mesh_id, owner_id, policy_id, source_tag, target_tag):
        assert raw_value not in serialized
        assert raw_value not in raw_log


def test_legacy_node_config_publishes_redacted_policy_read_evidence(
    monkeypatch,
    tmp_path,
):
    mesh_id = "mesh-secret-node-config"
    owner_id = "owner-secret-node-config"
    source_node = "node-secret-robot"
    allowed_node = "node-secret-server"
    denied_node = "node-secret-camera"
    source_tag = "robot-secret-config-tag"
    allowed_tag = "server-secret-config-tag"
    denied_tag = "camera-secret-config-tag"
    policy_id = "policy-secret-node-config"
    bus = EventBus(str(tmp_path))
    request = _request(bus)
    instance = _Mesh(
        mesh_id=mesh_id,
        owner_id=owner_id,
        join_token="node-config-token-secret",
    )
    instance.node_instances = {
        source_node: {"status": "healthy", "tags": [source_tag]},
        allowed_node: {"status": "healthy", "tags": [allowed_tag]},
        denied_node: {"status": "healthy", "tags": [denied_tag]},
    }
    _install_state(monkeypatch, instance)
    legacy_mod._mesh_policies[mesh_id] = [
        {
            "id": policy_id,
            "source_tag": source_tag,
            "target_tag": allowed_tag,
            "action": "allow",
        }
    ]

    result = legacy_mod.get_node_config(
        mesh_id,
        source_node,
        request=request,
        current_user=SimpleNamespace(id=owner_id, role="admin"),
    )

    assert allowed_node in result["allowed_peers"]
    assert denied_node in result["denied_peers"]
    assert result["policy_decisions"][allowed_node]["policy_id"] == policy_id

    payloads = _payloads(bus, "maas-legacy-policy-read")
    assert len(payloads) == 1
    payload = payloads[0]
    assert payload["operation"] == "legacy_node_config_read"
    assert payload["stage"] == "node_config_read"
    assert payload["status"] == "success"
    assert payload["mesh_id_hash"] == legacy_mod._redacted_sha256_prefix(mesh_id)
    assert payload["node_id_hash"] == legacy_mod._redacted_sha256_prefix(source_node)
    assert payload["result_summary"]["allowed_peer_count"] == 1
    assert payload["result_summary"]["denied_peer_count"] == 1
    assert payload["result_summary"]["decision_count"] == 2
    assert payload["result_summary"]["explicit_policy_decision_count"] == 1
    assert payload["read_only"] is True
    assert payload["control_action"] is False

    serialized = json.dumps(payloads, sort_keys=True)
    raw_log = (tmp_path / ".agent_coordination" / "events.log").read_text(
        encoding="utf-8"
    )
    for raw_value in (
        mesh_id,
        owner_id,
        source_node,
        allowed_node,
        denied_node,
        source_tag,
        allowed_tag,
        denied_tag,
        policy_id,
    ):
        assert raw_value not in serialized
        assert raw_value not in raw_log


def test_legacy_policy_list_denial_publishes_redacted_read_evidence(
    monkeypatch,
    tmp_path,
):
    mesh_id = "mesh-secret-policy-list-denied"
    owner_id = "owner-secret-policy-list-denied"
    bus = EventBus(str(tmp_path))
    request = _request(bus)

    from src.api.maas import registry as modular_registry

    monkeypatch.setattr(legacy_mod, "mesh_provisioner", _Provisioner([]))
    monkeypatch.setattr(modular_registry, "get_mesh", lambda _mesh_id: None)

    with pytest.raises(HTTPException) as exc:
        asyncio.run(
            legacy_mod.legacy_list_policies_route(
                mesh_id=mesh_id,
                request=request,
                current_user=SimpleNamespace(id=owner_id, role="admin"),
            )
        )

    assert exc.value.status_code == 404

    payloads = _payloads(bus, "maas-legacy-policy-read")
    assert len(payloads) == 1
    payload = payloads[0]
    assert payload["operation"] == "legacy_policy_list_read"
    assert payload["stage"] == "access_denied"
    assert payload["status"] == "denied"
    assert payload["reason"] == "mesh_not_found_or_forbidden"
    assert payload["mesh_id_hash"] == legacy_mod._redacted_sha256_prefix(mesh_id)
    assert payload["actor_user_id_hash"] == legacy_mod._redacted_sha256_prefix(owner_id)

    serialized = json.dumps(payloads, sort_keys=True)
    raw_log = (tmp_path / ".agent_coordination" / "events.log").read_text(
        encoding="utf-8"
    )
    for raw_value in (mesh_id, owner_id):
        assert raw_value not in serialized
        assert raw_value not in raw_log
