"""Unit tests for interactive demo session manager."""

import pytest
from fastapi import HTTPException

from src.core import demo_interactive


@pytest.mark.asyncio
async def test_create_session_builds_nodes_and_links():
    manager = demo_interactive.InteractiveDemo()
    session_id = manager.create_session(num_nodes=4)

    session = manager.sessions[session_id]
    assert len(session.nodes) == 4
    assert len(session.links) > 0


@pytest.mark.asyncio
async def test_destroy_node_raises_for_unknown_session():
    manager = demo_interactive.InteractiveDemo()
    with pytest.raises(HTTPException) as exc:
        await manager.destroy_node("missing", "node-1")
    assert exc.value.status_code == 404


@pytest.mark.asyncio
async def test_destroy_node_runs_recovery_flow(monkeypatch):
    async def _fast_sleep(_seconds):
        return None

    monkeypatch.setattr(demo_interactive.asyncio, "sleep", _fast_sleep)

    manager = demo_interactive.InteractiveDemo()
    session_id = manager.create_session(num_nodes=3)

    result = await manager.destroy_node(session_id, "node-1")
    session = manager.sessions[session_id]

    assert result["status"] == "recovered"
    assert session.nodes["node-1"].status == demo_interactive.NodeStatus.HEALTHY
    assert any(e["type"] == "node_recovered" for e in session.events)


@pytest.mark.asyncio
async def test_get_metrics_counts_failures_and_recoveries(monkeypatch):
    async def _fast_sleep(_seconds):
        return None

    monkeypatch.setattr(demo_interactive.asyncio, "sleep", _fast_sleep)

    manager = demo_interactive.InteractiveDemo()
    session_id = manager.create_session(num_nodes=3)
    await manager.destroy_node(session_id, "node-1")

    # Call endpoint function using module-level manager
    old = demo_interactive.demo_manager
    demo_interactive.demo_manager = manager
    try:
        metrics = await demo_interactive.get_metrics(session_id)
    finally:
        demo_interactive.demo_manager = old

    assert metrics["total_failures"] == 1
    assert metrics["total_recoveries"] == 1
