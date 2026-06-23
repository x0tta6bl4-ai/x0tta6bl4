"""Unit tests for legacy MaaS node lifecycle EventBus evidence."""

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
        self.join_token_expires_at = datetime.utcnow() + timedelta(hours=1)
        self.node_instances = {}


def _request(bus: EventBus):
    return SimpleNamespace(state=SimpleNamespace(event_bus=bus))


def _payloads(bus: EventBus):
    return [
        event.data
        for event in bus.get_event_history(
            event_type=EventType.PIPELINE_STAGE_END,
            source_agent="maas-legacy-node-lifecycle",
            limit=10,
        )
    ]


def _install_state(monkeypatch, instance: _Mesh):
    monkeypatch.setattr(legacy_mod, "mesh_provisioner", _Provisioner([instance]))
    monkeypatch.setattr(legacy_mod, "_pending_nodes", {})
    monkeypatch.setattr(legacy_mod, "_revoked_nodes", {})
    monkeypatch.setattr(legacy_mod, "_mesh_reissue_tokens", {})
    monkeypatch.setattr(legacy_mod, "_mesh_audit_log", {})


def test_legacy_node_register_publishes_redacted_lifecycle_evidence(
    monkeypatch,
    tmp_path,
):
    mesh_id = "mesh-secret-node-register"
    node_id = "node-secret-register"
    owner_id = "owner-secret-node-register"
    join_token = "join-token-secret-register"
    bus = EventBus(str(tmp_path))
    request = _request(bus)
    instance = _Mesh(mesh_id=mesh_id, owner_id=owner_id, join_token=join_token)
    _install_state(monkeypatch, instance)

    result = asyncio.run(
        legacy_mod.register_node(
            mesh_id,
            legacy_mod.NodeRegisterRequest(
                node_id=node_id,
                enrollment_token=join_token,
                device_class="robot",
                labels={"private": "label-secret-value"},
                public_keys={"ml_dsa": "public-key-secret-value"},
                hardware_id="hardware-secret-value",
                attestation_data={"quote": "attestation-secret-value"},
                enclave_enabled=True,
            ),
            request=request,
        )
    )

    assert result.node_id == node_id
    assert node_id in legacy_mod._pending_nodes[mesh_id]

    payloads = _payloads(bus)
    assert len(payloads) == 1
    payload = payloads[0]
    assert payload["operation"] == "legacy_node_register"
    assert payload["service_name"] == "maas-legacy-node-lifecycle"
    assert payload["source_alias"] == "maas-legacy-node-lifecycle"
    assert payload["layer"] == "api_legacy_node_lifecycle_control_action"
    assert payload["stage"] == "registration_pending"
    assert payload["status"] == "success"
    assert payload["mesh_id_hash"] == legacy_mod._redacted_sha256_prefix(mesh_id)
    assert payload["node_id_hash"] == legacy_mod._redacted_sha256_prefix(node_id)
    assert payload["owner_id_hash"] == legacy_mod._redacted_sha256_prefix(owner_id)
    assert payload["request_summary"]["device_class"] == "robot"
    assert payload["request_summary"]["label_count"] == 1
    assert payload["request_summary"]["public_key_count"] == 1
    assert payload["pending_registry_mutated"] is True
    assert payload["audit_recorded"] is True
    assert payload["control_action"] is True
    assert payload["raw_identifiers_redacted"] is True

    serialized = json.dumps(payloads, sort_keys=True)
    raw_log = (tmp_path / ".agent_coordination" / "events.log").read_text(
        encoding="utf-8"
    )
    for raw_value in (
        mesh_id,
        node_id,
        owner_id,
        join_token,
        "label-secret-value",
        "public-key-secret-value",
        "hardware-secret-value",
        "attestation-secret-value",
    ):
        assert raw_value not in serialized
        assert raw_value not in raw_log


def test_legacy_node_approve_publishes_redacted_lifecycle_evidence(
    monkeypatch,
    tmp_path,
):
    mesh_id = "mesh-secret-node-approve"
    node_id = "node-secret-approve"
    owner_id = "owner-secret-node-approve"
    bus = EventBus(str(tmp_path))
    request = _request(bus)
    instance = _Mesh(
        mesh_id=mesh_id,
        owner_id=owner_id,
        join_token="join-token-secret-approve",
    )
    _install_state(monkeypatch, instance)
    legacy_mod._pending_nodes.setdefault(mesh_id, {})[node_id] = {
        "node_id": node_id,
        "device_class": "gateway",
        "labels": {"private": "pending-label-secret"},
        "public_keys": {"ml_dsa": "pending-public-key-secret"},
        "hardware_id": "pending-hardware-secret",
        "enclave_enabled": True,
    }
    monkeypatch.setattr(legacy_mod.secrets, "token_urlsafe", lambda _n: "approve-token-secret")
    monkeypatch.setattr(
        legacy_mod,
        "token_signer",
        SimpleNamespace(
            sign_token=lambda token, mesh: {
                "token": token,
                "signature": f"signature-for-{mesh}",
            }
        ),
    )

    result = asyncio.run(
        legacy_mod.approve_node(
            mesh_id,
            node_id,
            legacy_mod.NodeApproveRequest(
                acl_profile="strict",
                tags=["robot", "secret-tag-value"],
            ),
            SimpleNamespace(id=owner_id, role="admin"),
            request=request,
        )
    )

    assert result.node_id == node_id
    assert result.join_token["token"] == "approve-token-secret"
    assert instance.node_instances[node_id]["status"] == "healthy"

    payloads = _payloads(bus)
    assert len(payloads) == 1
    payload = payloads[0]
    assert payload["operation"] == "legacy_node_approve"
    assert payload["stage"] == "approved"
    assert payload["status"] == "success"
    assert payload["node_registry_mutated"] is True
    assert payload["pending_registry_mutated"] is True
    assert payload["join_token_issued"] is True
    assert payload["request_summary"]["acl_profile"] == "strict"
    assert payload["request_summary"]["tag_count"] == 2
    assert payload["request_summary"]["pending_device_class"] == "gateway"

    serialized = json.dumps(payloads, sort_keys=True)
    raw_log = (tmp_path / ".agent_coordination" / "events.log").read_text(
        encoding="utf-8"
    )
    for raw_value in (
        mesh_id,
        node_id,
        owner_id,
        "approve-token-secret",
        "pending-label-secret",
        "pending-public-key-secret",
        "pending-hardware-secret",
        "secret-tag-value",
    ):
        assert raw_value not in serialized
        assert raw_value not in raw_log


def test_legacy_node_revoke_and_reissue_publish_redacted_lifecycle_evidence(
    monkeypatch,
    tmp_path,
):
    mesh_id = "mesh-secret-node-revoke"
    node_id = "node-secret-revoke"
    owner_id = "owner-secret-node-revoke"
    revoke_reason = "compromised secret operator note"
    bus = EventBus(str(tmp_path))
    request = _request(bus)
    instance = _Mesh(
        mesh_id=mesh_id,
        owner_id=owner_id,
        join_token="join-token-secret-revoke",
    )
    instance.node_instances[node_id] = {"status": "healthy"}
    _install_state(monkeypatch, instance)
    monkeypatch.setattr(legacy_mod.secrets, "token_urlsafe", lambda _n: "reissue-token-secret")
    monkeypatch.setattr(
        legacy_mod,
        "token_signer",
        SimpleNamespace(
            sign_token=lambda token, mesh: {
                "token": token,
                "signature": f"signature-for-{mesh}",
            }
        ),
    )

    revoked = asyncio.run(
        legacy_mod.revoke_node(
            mesh_id,
            node_id,
            legacy_mod.NodeRevokeRequest(reason=revoke_reason),
            SimpleNamespace(id=owner_id, role="admin"),
            request=request,
        )
    )
    reissued = asyncio.run(
        legacy_mod.reissue_node_token(
            mesh_id,
            node_id,
            legacy_mod.NodeReissueTokenRequest(ttl_seconds=600),
            SimpleNamespace(id=owner_id, role="admin"),
            request=request,
        )
    )

    assert revoked.status == "revoked"
    assert reissued.join_token["token"] == "reissue-token-secret"

    payloads = _payloads(bus)
    assert [payload["operation"] for payload in payloads] == [
        "legacy_node_revoke",
        "legacy_node_reissue_token",
    ]
    revoke_payload, reissue_payload = payloads
    assert revoke_payload["stage"] == "revoked"
    assert revoke_payload["node_registry_mutated"] is True
    assert revoke_payload["revoked_registry_mutated"] is True
    assert revoke_payload["request_summary"]["reason_length"] == len(revoke_reason)
    assert reissue_payload["stage"] == "reissue_token_issued"
    assert reissue_payload["reissue_token_mutated"] is True
    assert reissue_payload["join_token_issued"] is True
    assert reissue_payload["request_summary"]["ttl_seconds"] == 600

    serialized = json.dumps(payloads, sort_keys=True)
    raw_log = (tmp_path / ".agent_coordination" / "events.log").read_text(
        encoding="utf-8"
    )
    for raw_value in (
        mesh_id,
        node_id,
        owner_id,
        revoke_reason,
        "reissue-token-secret",
    ):
        assert raw_value not in serialized
        assert raw_value not in raw_log


def test_legacy_node_register_denial_publishes_redacted_evidence(
    monkeypatch,
    tmp_path,
):
    mesh_id = "mesh-secret-node-denied"
    node_id = "node-secret-denied"
    owner_id = "owner-secret-node-denied"
    invalid_token = "invalid-token-secret-denied"
    bus = EventBus(str(tmp_path))
    request = _request(bus)
    instance = _Mesh(
        mesh_id=mesh_id,
        owner_id=owner_id,
        join_token="join-token-secret-denied",
    )
    _install_state(monkeypatch, instance)

    with pytest.raises(HTTPException) as exc:
        asyncio.run(
            legacy_mod.register_node(
                mesh_id,
                legacy_mod.NodeRegisterRequest(
                    node_id=node_id,
                    enrollment_token=invalid_token,
                ),
                request=request,
            )
        )

    assert exc.value.status_code == 401

    payloads = _payloads(bus)
    assert len(payloads) == 1
    payload = payloads[0]
    assert payload["operation"] == "legacy_node_register"
    assert payload["stage"] == "registration_denied"
    assert payload["status"] == "denied"
    assert payload["reason"] == "invalid_enrollment_token"
    assert payload["pending_registry_mutated"] is False
    assert payload["mesh_id_hash"] == legacy_mod._redacted_sha256_prefix(mesh_id)
    assert payload["node_id_hash"] == legacy_mod._redacted_sha256_prefix(node_id)

    serialized = json.dumps(payloads, sort_keys=True)
    raw_log = (tmp_path / ".agent_coordination" / "events.log").read_text(
        encoding="utf-8"
    )
    for raw_value in (mesh_id, node_id, owner_id, invalid_token):
        assert raw_value not in serialized
        assert raw_value not in raw_log
