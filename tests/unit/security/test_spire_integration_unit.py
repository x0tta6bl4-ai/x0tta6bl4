import os

os.environ.setdefault("X0TTA6BL4_PRODUCTION", "false")
os.environ.setdefault("X0TTA6BL4_SPIFFE", "false")
os.environ.setdefault("X0TTA6BL4_FORCE_MOCK_SPIFFE", "true")

from types import SimpleNamespace

import src.security.spire_integration as spire


def test_spire_config_respects_global_availability(monkeypatch) -> None:
    monkeypatch.setattr(spire, "SPIRE_AGENT_AVAILABLE", False)
    cfg = spire.SPIREConfig(enabled=True)
    assert cfg.enabled is False

    monkeypatch.setattr(spire, "SPIRE_AGENT_AVAILABLE", True)
    cfg2 = spire.SPIREConfig(enabled=True)
    assert cfg2.enabled is True


def test_spire_client_initialization_success(monkeypatch) -> None:
    monkeypatch.setattr(spire, "SPIRE_AGENT_AVAILABLE", True)
    fake_client = object()
    monkeypatch.setattr(spire, "WorkloadApiClient", lambda addr: fake_client)
    client = spire.SPIREClient(
        spire.SPIREConfig(agent_address="unix:///x", enabled=True)
    )
    assert client.client is fake_client
    assert client.is_available() is True


def test_spire_client_initialization_failure(monkeypatch) -> None:
    monkeypatch.setattr(spire, "SPIRE_AGENT_AVAILABLE", True)

    def _raise(_addr):
        raise RuntimeError("boom")

    monkeypatch.setattr(spire, "WorkloadApiClient", _raise)
    client = spire.SPIREClient(spire.SPIREConfig(enabled=True))
    assert client.client is None
    assert client.is_available() is False


def test_fetch_x509_context_and_bundle(monkeypatch) -> None:
    monkeypatch.setattr(spire, "SPIRE_AGENT_AVAILABLE", True)
    svid = SimpleNamespace(
        certificate=b"cert", private_key=b"key", trust_bundle=b"bundle"
    )
    workload = SimpleNamespace(
        fetch_x509_svid=lambda: svid,
        fetch_x509_bundle=lambda: b"bundle-2",
    )
    monkeypatch.setattr(spire, "WorkloadApiClient", lambda _addr: workload)
    client = spire.SPIREClient(spire.SPIREConfig(enabled=True))
    ctx = client.fetch_x509_context()
    assert ctx == {"certificate": b"cert", "key": b"key", "bundle": b"bundle"}
    assert client.fetch_x509_bundle() == b"bundle-2"


def test_fetch_x509_context_returns_none_on_unavailable(monkeypatch) -> None:
    monkeypatch.setattr(spire, "SPIRE_AGENT_AVAILABLE", False)
    client = spire.SPIREClient(spire.SPIREConfig(enabled=False))
    assert client.fetch_x509_context() is None
    assert client.fetch_x509_bundle() is None


def test_is_spire_available_socket_paths(monkeypatch) -> None:
    monkeypatch.setattr(spire, "SPIRE_AGENT_AVAILABLE", True)

    class GoodSock:
        def settimeout(self, _t):
            return None

        def connect(self, _path):
            return None

        def close(self):
            return None

    monkeypatch.setattr(spire.socket, "socket", lambda *_a, **_k: GoodSock())
    assert spire.is_spire_available() is True

    class BadSock:
        def settimeout(self, _t):
            return None

        def connect(self, _path):
            raise FileNotFoundError("missing")

        def close(self):
            return None

    monkeypatch.setattr(spire.socket, "socket", lambda *_a, **_k: BadSock())
    assert spire.is_spire_available() is False


def test_wait_for_spire_success_and_timeout(monkeypatch) -> None:
    values = iter([False, False, True])
    monkeypatch.setattr(spire, "is_spire_available", lambda: next(values))
    monkeypatch.setattr(spire.time, "sleep", lambda _s: None)
    assert spire.wait_for_spire(timeout=10, check_interval=0) is True

    # timeout path
    monkeypatch.setattr(spire, "is_spire_available", lambda: False)
    t = {"now": 0}

    def fake_time():
        t["now"] += 1
        return t["now"]

    monkeypatch.setattr(spire.time, "time", fake_time)
    monkeypatch.setattr(spire.time, "sleep", lambda _s: None)
    assert spire.wait_for_spire(timeout=2, check_interval=0) is False


def test_get_spire_client_returns_instance(monkeypatch) -> None:
    monkeypatch.setattr(spire, "SPIRE_AGENT_AVAILABLE", False)
    client = spire.get_spire_client()
    assert isinstance(client, spire.SPIREClient)
