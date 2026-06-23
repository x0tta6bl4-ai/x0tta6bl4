from __future__ import annotations

import socket

from src.coordination.events import EventBus, EventType
from src.network.obfuscation.base import ObfuscationTransport, TransportManager


class _DummyTransport(ObfuscationTransport):
    def __init__(self, **kwargs):
        self.kwargs = kwargs

    def wrap_socket(self, sock: socket.socket) -> socket.socket:
        return sock

    def obfuscate(self, data: bytes) -> bytes:
        return data

    def deobfuscate(self, data: bytes) -> bytes:
        return data


def _events(bus: EventBus):
    return bus.get_event_history(source_agent="network-obfuscation-transport")


def test_transport_create_evidence_redacts_custom_name_and_secret_kwargs(tmp_path):
    bus = EventBus(project_root=str(tmp_path))
    original_transports = dict(TransportManager._transports)
    try:
        TransportManager.register("secret-method-name", _DummyTransport)

        transport = TransportManager.create(
            "secret-method-name",
            key="raw-key-secret",
            password="raw-password-secret",
            uuid="raw-uuid-secret",
            sni="secret.example.internal",
            event_bus=bus,
        )
    finally:
        TransportManager._transports = original_transports

    assert isinstance(transport, _DummyTransport)

    events = _events(bus)
    assert len(events) == 1
    event = events[0]
    payload = event.data

    assert event.event_type == EventType.PIPELINE_STAGE_END
    assert payload["status"] == "created"
    assert payload["local_transport_constructed"] is True
    assert payload["transport_registered"] is True
    assert payload["transport"]["name_bucket"] == "custom"
    assert payload["transport"]["name_hash"]
    assert payload["transport"]["raw_name_redacted"] is True
    assert payload["constructor"]["secret_material_present"] is True
    assert payload["constructor"]["network_selector_present"] is True
    assert payload["constructor"]["raw_values_redacted"] is True
    assert payload["constructor"]["field_names_redacted"] is True
    assert payload["dataplane_confirmed"] is False
    assert payload["dpi_bypass_confirmed"] is False
    assert payload["bypass_confirmed"] is False
    assert payload["thinking"]["profile"]["role"] == "security"
    assert "zero_trust_review" in payload["thinking"]["techniques"]
    assert (
        payload["last_thinking_context"]["applied"]["framing"]["problem"]
        == "obfuscation_transport_created"
    )

    rendered = repr(payload)
    assert "secret-method-name" not in rendered
    assert "raw-key-secret" not in rendered
    assert "raw-password-secret" not in rendered
    assert "raw-uuid-secret" not in rendered
    assert "secret.example.internal" not in rendered
    assert "bypass_confirmed': True" not in rendered


def test_transport_create_unknown_evidence_is_blocked_not_bypass_proof(tmp_path):
    bus = EventBus(project_root=str(tmp_path))

    transport = TransportManager.create(
        "secret-missing-method",
        password="raw-password-secret",
        event_bus=bus,
    )

    assert transport is None

    events = _events(bus)
    assert len(events) == 1
    event = events[0]
    payload = event.data

    assert event.event_type == EventType.TASK_BLOCKED
    assert payload["status"] == "not_found"
    assert payload["local_transport_constructed"] is False
    assert payload["transport_registered"] is False
    assert payload["transport"]["name_bucket"] == "custom"
    assert payload["dataplane_confirmed"] is False
    assert payload["dpi_bypass_confirmed"] is False
    assert (
        payload["last_thinking_context"]["applied"]["framing"]["problem"]
        == "obfuscation_transport_not_found"
    )
    assert payload["claim_boundary"]
    assert "secret-missing-method" not in repr(payload)
    assert "raw-password-secret" not in repr(payload)
