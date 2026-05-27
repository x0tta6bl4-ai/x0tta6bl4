from __future__ import annotations

from types import SimpleNamespace

import pytest


class _DummyTaskDistributor:
    def __init__(self, *_args, **_kwargs):
        self.shutdown_called = False

    def get_stats(self) -> dict:
        return {}

    async def shutdown(self) -> None:
        self.shutdown_called = True


class _DummyEdgeCache:
    def __init__(self, *_args, **_kwargs):
        pass

    def get_stats(self) -> dict:
        return {}


class _DummyProjectionManager:
    def __init__(self, *_args, **_kwargs):
        self.stop_all_called = False

    async def stop_all(self) -> None:
        self.stop_all_called = True


@pytest.mark.asyncio
async def test_edge_health_distinguishes_route_reachable_from_startup_hook(monkeypatch):
    import src.edge.api as edge_api

    monkeypatch.setattr(edge_api, "EdgeNodeManager", lambda: SimpleNamespace(list_nodes=lambda: []))
    monkeypatch.setattr(edge_api, "TaskDistributor", _DummyTaskDistributor)
    monkeypatch.setattr(edge_api, "EdgeCache", _DummyEdgeCache)

    edge_api._node_manager = None
    edge_api._task_distributor = None
    edge_api._edge_cache = None
    edge_api._startup_hook_completed = False

    health_before = await edge_api.get_edge_health()
    assert health_before.startup_hook_completed is False

    await edge_api.edge_startup()
    health_after = await edge_api.get_edge_health()
    assert health_after.startup_hook_completed is True

    await edge_api.edge_shutdown()
    assert edge_api._startup_hook_completed is False


@pytest.mark.asyncio
async def test_event_sourcing_health_distinguishes_route_reachable_from_startup_hook(monkeypatch):
    import src.event_sourcing.api as event_api

    monkeypatch.setattr(event_api, "EventStore", lambda: SimpleNamespace(_backend_type="test"))
    monkeypatch.setattr(event_api, "CommandBus", lambda: object())
    monkeypatch.setattr(event_api, "QueryBus", lambda: object())
    monkeypatch.setattr(event_api, "ProjectionManager", _DummyProjectionManager)

    event_api._event_store = None
    event_api._command_bus = None
    event_api._query_bus = None
    event_api._projection_manager = None
    event_api._startup_hook_completed = False

    health_before = await event_api.health_check()
    assert health_before["startup_hook_completed"] is False

    await event_api.event_sourcing_startup()
    health_after = await event_api.health_check()
    assert health_after["startup_hook_completed"] is True

    await event_api.event_sourcing_shutdown()
    assert event_api._startup_hook_completed is False
