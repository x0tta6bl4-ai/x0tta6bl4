"""Unit tests for src.agent.headless."""

from __future__ import annotations

import json
from types import SimpleNamespace

import pytest

import src.agent.headless as mod


class _FakeIdentity:
    def __init__(self, node_id: str):
        self.node_id = node_id


class _FakeRouter:
    def __init__(self, node_id: str):
        self.node_id = node_id
        self.updated = []
        self.reinforced = []
        self.started = False
        self.stopped = False

    async def start(self):
        self.started = True

    async def stop(self):
        self.stopped = True

    def reinforce(self, source: str, target: str, success: bool):
        self.reinforced.append((source, target, success))

    def update_policies(self, policies, peer_tags):
        self.updated.append((policies, peer_tags))

    def get_routing_table_snapshot(self):
        return {}


class _FakeDiscovery:
    def __init__(self, node_id: str, service_port: int, identity_manager):
        self.node_id = node_id
        self.service_port = service_port
        self.identity_manager = identity_manager
        self.started = False
        self.stopped = False
        self._callback = None

    def on_peer_discovered(self, fn):
        self._callback = fn
        return fn

    async def start(self):
        self.started = True

    async def stop(self):
        self.stopped = True


@pytest.mark.asyncio
async def test_initialize_generates_identity_and_components(tmp_path, monkeypatch):
    monkeypatch.setattr(mod, "DATA_DIR", tmp_path / "agent_data")
    monkeypatch.setattr(mod, "API_KEY", None)
    monkeypatch.setattr(mod, "PQCNodeIdentity", _FakeIdentity)
    monkeypatch.setattr(mod, "StigmergyRouter", _FakeRouter)
    monkeypatch.setattr(mod, "MeshDiscovery", _FakeDiscovery)

    agent = mod.HeadlessAgent()
    await agent.initialize()

    assert agent.node_id.startswith("node-")
    assert isinstance(agent.identity, _FakeIdentity)
    assert isinstance(agent.router, _FakeRouter)
    assert isinstance(agent.discovery, _FakeDiscovery)

    identity_file = mod.DATA_DIR / "identity.json"
    assert identity_file.exists()
    payload = json.loads(identity_file.read_text(encoding="utf-8"))
    assert payload["node_id"] == agent.node_id


@pytest.mark.asyncio
async def test_initialize_loads_existing_identity(tmp_path, monkeypatch):
    data_dir = tmp_path / "agent_data"
    data_dir.mkdir(parents=True, exist_ok=True)
    (data_dir / "identity.json").write_text(
        json.dumps({"node_id": "node-existing"}),
        encoding="utf-8",
    )

    monkeypatch.setattr(mod, "DATA_DIR", data_dir)
    monkeypatch.setattr(mod, "API_KEY", None)
    monkeypatch.setattr(mod, "PQCNodeIdentity", _FakeIdentity)
    monkeypatch.setattr(mod, "StigmergyRouter", _FakeRouter)
    monkeypatch.setattr(mod, "MeshDiscovery", _FakeDiscovery)

    agent = mod.HeadlessAgent()
    await agent.initialize()
    assert agent.node_id == "node-existing"
    assert agent.identity.node_id == "node-existing"


@pytest.mark.asyncio
async def test_register_with_maas_updates_router_policy(monkeypatch):
    class _Resp:
        def __init__(self, status_code, payload=None):
            self.status_code = status_code
            self._payload = payload or {}

        def json(self):
            return self._payload

    class _AsyncClient:
        async def __aenter__(self):
            return self

        async def __aexit__(self, exc_type, exc, tb):
            return False

        async def get(self, url, headers=None):
            if url.endswith("/me"):
                return _Resp(200)
            return _Resp(200, {"policies": [{"id": "p1"}], "peer_tags": {"a": ["b"]}})

    monkeypatch.setattr(mod.httpx, "AsyncClient", _AsyncClient)
    monkeypatch.setattr(mod, "API_KEY", "k-test")
    monkeypatch.setattr(mod, "MAAS_URL", "http://maas.local/api/v1/maas")
    monkeypatch.setattr(mod.os, "getenv", lambda key, default=None: "mesh-test" if key == "MAAS_MESH_ID" else default)

    agent = mod.HeadlessAgent()
    agent.node_id = "node-1"
    agent.router = _FakeRouter("node-1")
    await agent._register_with_maas()

    assert agent.router.updated == [([{"id": "p1"}], {"a": ["b"]})]


@pytest.mark.asyncio
async def test_register_with_maas_handles_transport_errors(monkeypatch):
    class _AsyncClient:
        async def __aenter__(self):
            return self

        async def __aexit__(self, exc_type, exc, tb):
            return False

        async def get(self, url, headers=None):
            raise RuntimeError("network down")

    monkeypatch.setattr(mod.httpx, "AsyncClient", _AsyncClient)
    monkeypatch.setattr(mod, "API_KEY", "k-test")

    agent = mod.HeadlessAgent()
    agent.node_id = "node-1"
    agent.router = _FakeRouter("node-1")
    await agent._register_with_maas()  # no exception


@pytest.mark.asyncio
async def test_stop_calls_discovery_and_router_stop():
    agent = mod.HeadlessAgent()
    agent.discovery = _FakeDiscovery("node-1", 7777, _FakeIdentity("node-1"))
    agent.router = _FakeRouter("node-1")

    await agent.stop()
    assert agent.discovery.stopped is True
    assert agent.router.stopped is True
