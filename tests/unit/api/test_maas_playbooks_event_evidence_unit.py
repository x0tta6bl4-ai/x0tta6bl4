"""Unit tests for MaaS playbook EventBus evidence."""

from __future__ import annotations

import asyncio
import json
from types import SimpleNamespace

import pytest
from fastapi import HTTPException

import src.api.maas_playbooks as playbooks_mod
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


def _clear_state():
    playbooks_mod._playbook_store.clear()
    playbooks_mod._node_queues.clear()
    playbooks_mod._playbook_acks.clear()
    playbooks_mod._playbook_deliveries.clear()


@pytest.fixture(autouse=True)
def _isolated_playbook_state():
    _clear_state()
    yield
    _clear_state()


def _user():
    return SimpleNamespace(
        id="playbook-user-id-secret",
        email="playbook-user-secret@example.test",
        role="admin",
    )


def test_playbook_create_and_poll_publish_redacted_control_evidence(
    monkeypatch,
    tmp_path,
):
    mesh_id = "playbook-create-mesh-secret"
    node_id = "playbook-create-node-secret"
    payload_secret = "playbook-create-payload-secret"
    signature_secret = "playbook-create-signature-secret"
    bus = EventBus(str(tmp_path))
    request = _request(bus)

    monkeypatch.setattr(
        playbooks_mod.token_signer,
        "sign_token",
        lambda payload, mesh: {
            "signature": signature_secret,
            "algorithm": "HMAC-SHA256",
        },
    )
    monkeypatch.setattr(playbooks_mod, "_has_valid_signature", lambda _playbook: True)

    result = asyncio.run(
        playbooks_mod.create_playbook(
            mesh_id,
            playbooks_mod.PlaybookCreateRequest(
                name="playbook-create-name-secret",
                target_nodes=[node_id],
                actions=[
                    playbooks_mod.PlaybookAction(
                        action="exec",
                        params={"cmd": payload_secret},
                    )
                ],
            ),
            current_user=_user(),
            db=SimpleNamespace(),
            request=request,
        )
    )
    polled = asyncio.run(
        playbooks_mod.poll_playbooks(
            mesh_id,
            node_id,
            db=SimpleNamespace(),
            request=request,
        )
    )

    assert result.playbook_id.startswith("pbk-")
    assert polled["playbooks"][0]["playbook_id"] == result.playbook_id
    create_payloads = _payloads(bus, "maas-playbooks-create")
    poll_payloads = _payloads(bus, "maas-playbooks-poll")
    assert len(create_payloads) == 1
    assert len(poll_payloads) == 1
    create_payload = create_payloads[0]
    assert create_payload["operation"] == "maas_playbook_create"
    assert create_payload["service_name"] == "maas-playbooks-create"
    assert create_payload["layer"] == "api_playbook_signed_command_control"
    assert create_payload["mesh_id_hash"] == playbooks_mod._redacted_sha256_prefix(
        mesh_id
    )
    assert create_payload["target_count"] == 1
    assert create_payload["action_counts"]["exec"] == 1
    assert create_payload["algorithm_bucket"] == "HMAC"
    assert create_payload["signature_present"] is True
    assert create_payload["control_action"] is True

    poll_payload = poll_payloads[0]
    assert poll_payload["operation"] == "maas_playbook_poll"
    assert poll_payload["service_name"] == "maas-playbooks-poll"
    assert poll_payload["node_id_hash"] == playbooks_mod._redacted_sha256_prefix(
        node_id
    )
    assert poll_payload["deliverable_count"] == 1
    assert poll_payload["control_action"] is True

    serialized = json.dumps(create_payloads + poll_payloads, sort_keys=True)
    raw_log = (tmp_path / ".agent_coordination" / "events.log").read_text(
        encoding="utf-8"
    )
    for raw_value in (
        _user().id,
        _user().email,
        mesh_id,
        node_id,
        result.playbook_id,
        "playbook-create-name-secret",
        payload_secret,
        signature_secret,
    ):
        assert raw_value not in serialized
        assert raw_value not in raw_log


def test_playbook_ack_publishes_success_and_denied_evidence(tmp_path):
    mesh_id = "playbook-ack-mesh-secret"
    node_id = "playbook-ack-node-secret"
    other_node_id = "playbook-ack-other-node-secret"
    playbook_id = "playbook-ack-id-secret"
    bus = EventBus(str(tmp_path))
    request = _request(bus)
    playbooks_mod._playbook_store[playbook_id] = {
        "playbook_id": playbook_id,
        "mesh_id": mesh_id,
        "name": "playbook-ack-name-secret",
        "payload": '{"secret":"playbook-ack-payload-secret"}',
        "signature": "playbook-ack-signature-secret",
        "algorithm": "HMAC-SHA256",
        "target_nodes": [node_id],
        "expires_at": "2099-01-01T00:00:00",
    }

    result = asyncio.run(
        playbooks_mod.acknowledge_playbook(
            playbook_id,
            node_id,
            status="completed",
            db=SimpleNamespace(),
            request=request,
        )
    )
    with pytest.raises(HTTPException) as exc:
        asyncio.run(
            playbooks_mod.acknowledge_playbook(
                playbook_id,
                other_node_id,
                status="failed",
                db=SimpleNamespace(),
                request=request,
            )
        )

    assert result["status"] == "received"
    assert exc.value.status_code == 403
    payloads = _payloads(bus, "maas-playbooks-ack")
    assert len(payloads) == 2
    assert payloads[0]["status"] == "success"
    assert payloads[0]["ack_status_bucket"] == "completed"
    assert payloads[0]["playbook_id_hash"] == playbooks_mod._redacted_sha256_prefix(
        playbook_id
    )
    assert payloads[1]["status"] == "denied"
    assert payloads[1]["http_status_code"] == 403
    assert payloads[1]["reason"] == "node_not_targeted"

    serialized = json.dumps(payloads, sort_keys=True)
    raw_log = (tmp_path / ".agent_coordination" / "events.log").read_text(
        encoding="utf-8"
    )
    for raw_value in (
        mesh_id,
        node_id,
        other_node_id,
        playbook_id,
        "playbook-ack-name-secret",
        "playbook-ack-payload-secret",
        "playbook-ack-signature-secret",
    ):
        assert raw_value not in serialized
        assert raw_value not in raw_log


def test_playbook_list_and_status_publish_redacted_observed_state(tmp_path):
    mesh_id = "playbook-read-mesh-secret"
    node_id = "playbook-read-node-secret"
    playbook_id = "playbook-read-id-secret"
    bus = EventBus(str(tmp_path))
    request = _request(bus)
    user = _user()
    playbooks_mod._playbook_store[playbook_id] = {
        "playbook_id": playbook_id,
        "mesh_id": mesh_id,
        "name": "playbook-read-name-secret",
        "payload": '{"secret":"playbook-read-payload-secret"}',
        "signature": "playbook-read-signature-secret",
        "algorithm": "HMAC-SHA256",
        "target_nodes": [node_id],
        "expires_at": "2099-01-01T00:00:00",
        "created_at": "2026-05-30T12:00:00",
    }
    playbooks_mod._playbook_acks[playbook_id] = {
        node_id: {"status": "completed", "acknowledged_at": "2026-05-30T12:00:00"}
    }

    listed = asyncio.run(
        playbooks_mod.list_playbooks(
            mesh_id,
            current_user=user,
            db=SimpleNamespace(),
            request=request,
        )
    )
    status = asyncio.run(
        playbooks_mod.get_playbook_status(
            playbook_id,
            current_user=user,
            db=SimpleNamespace(),
            request=request,
        )
    )

    assert listed[0]["playbook_id"] == playbook_id
    assert status["total_acks"] == 1
    list_payloads = _payloads(bus, "maas-playbooks-list-read")
    status_payloads = _payloads(bus, "maas-playbooks-status-read")
    assert len(list_payloads) == 1
    assert len(status_payloads) == 1
    assert list_payloads[0]["operation"] == "maas_playbook_list_read"
    assert list_payloads[0]["playbook_count"] == 1
    assert list_payloads[0]["read_only"] is True
    assert status_payloads[0]["operation"] == "maas_playbook_status_read"
    assert status_payloads[0]["ack_count"] == 1
    assert status_payloads[0]["observed_state"] is True

    serialized = json.dumps(list_payloads + status_payloads, sort_keys=True)
    raw_log = (tmp_path / ".agent_coordination" / "events.log").read_text(
        encoding="utf-8"
    )
    for raw_value in (
        user.id,
        user.email,
        mesh_id,
        node_id,
        playbook_id,
        "playbook-read-name-secret",
        "playbook-read-payload-secret",
        "playbook-read-signature-secret",
    ):
        assert raw_value not in serialized
        assert raw_value not in raw_log
