import os
import socket

import pytest

os.environ.setdefault("X0TTA6BL4_PRODUCTION", "false")
os.environ.setdefault("X0TTA6BL4_SPIFFE", "false")
os.environ.setdefault("X0TTA6BL4_FORCE_MOCK_SPIFFE", "true")

from src.network.obfuscation.base import ObfuscationTransport, TransportManager


class _DummyTransport(ObfuscationTransport):
    def __init__(self, marker: str = "x"):
        self.marker = marker

    def wrap_socket(self, sock: socket.socket) -> socket.socket:
        return sock

    def obfuscate(self, data: bytes) -> bytes:
        return data + self.marker.encode()

    def deobfuscate(self, data: bytes) -> bytes:
        suffix = self.marker.encode()
        return data[: -len(suffix)] if data.endswith(suffix) else data


@pytest.fixture(autouse=True)
def _restore_registry():
    snapshot = dict(TransportManager._transports)
    try:
        yield
    finally:
        TransportManager._transports = snapshot


def test_create_unknown_transport_returns_none():
    assert TransportManager.create("__missing_transport__") is None


def test_register_and_create_transport_with_kwargs():
    TransportManager.register("dummy", _DummyTransport)
    created = TransportManager.create("dummy", marker="ok")
    assert isinstance(created, _DummyTransport)
    assert created.marker == "ok"
    assert created.deobfuscate(created.obfuscate(b"payload")) == b"payload"


def test_register_overrides_existing_transport_name():
    class _DummyA(_DummyTransport):
        pass

    class _DummyB(_DummyTransport):
        pass

    TransportManager.register("dummy", _DummyA)
    TransportManager.register("dummy", _DummyB)
    created = TransportManager.create("dummy")
    assert isinstance(created, _DummyB)
