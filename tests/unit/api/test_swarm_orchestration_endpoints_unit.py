from types import SimpleNamespace
from unittest.mock import AsyncMock

import pytest
from fastapi import FastAPI
from httpx import ASGITransport, AsyncClient

from src.api import swarm_endpoints as swarm_orchestration
from src.api.swarm_endpoints import router


def _build_app() -> FastAPI:
    app = FastAPI()
    app.include_router(router)
    return app


def _fake_orchestrator(agent_count: int = 1):
    agents = {f"agent-{idx}": object() for idx in range(agent_count)}
    return SimpleNamespace(
        status=SimpleNamespace(value="ready"),
        agents=agents,
        tasks={},
        metrics=SimpleNamespace(),
        get_status=lambda: {"status": "ready", "total_agents": len(agents)},
        execute_task=AsyncMock(),
    )


def test_swarm_orchestration_readiness_ready_when_agents_are_available(monkeypatch):
    monkeypatch.setattr(swarm_orchestration, "SWARM_AVAILABLE", True)
    monkeypatch.setattr(
        swarm_orchestration,
        "_orchestrator",
        _fake_orchestrator(agent_count=2),
        raising=False,
    )

    payload = swarm_orchestration._swarm_orchestration_readiness_status()

    assert payload["status"] == "ready"
    assert payload["swarm_orchestration_ready"] is True
    assert payload["swarm_components_ready"] is True
    assert payload["orchestrator_surface_ready"] is True
    assert payload["orchestrator_state_ready"] is True
    assert payload["task_scheduler_ready"] is True
    assert payload["cross_plane_claim_gate"]["allowed"] is False
    assert "traffic_delivery" in payload["cross_plane_claim_gate"]["requested_claim_ids"]
    assert payload["agents_ready"] is True
    assert payload["active_agents"] == 2
    assert payload["tracked_tasks"] == 0
    assert payload["degraded_dependencies"] == []


def test_swarm_orchestration_readiness_degraded_when_orchestrator_is_missing(
    monkeypatch,
):
    monkeypatch.setattr(swarm_orchestration, "SWARM_AVAILABLE", False)
    monkeypatch.setattr(swarm_orchestration, "_orchestrator", None, raising=False)

    payload = swarm_orchestration._swarm_orchestration_readiness_status()

    assert payload["status"] == "degraded"
    assert payload["swarm_orchestration_ready"] is False
    assert payload["active_agents"] is None
    assert payload["tracked_tasks"] is None
    assert payload["degraded_dependencies"] == [
        "swarm_components",
        "orchestrator",
        "orchestrator_runtime_state",
        "agents",
    ]
    assert "global _orchestrator" in payload["backing_state"]["swarm_components"]
    assert "does not start agents" in payload["claim_boundary"]


@pytest.mark.asyncio
async def test_swarm_orchestration_readiness_route_exposes_capacity_boundary():
    transport = ASGITransport(app=_build_app())
    async with AsyncClient(transport=transport, base_url="http://test") as client:
        response = await client.get("/api/v1/swarm/readiness")

    assert response.status_code == 200
    payload = response.json()
    assert payload["swarm_orchestration_ready"] is False
    assert payload["agents_ready"] is False
    assert "agents" in payload["degraded_dependencies"]


@pytest.mark.asyncio
async def test_swarm_orchestration_readiness_marks_degraded_dependencies(
    monkeypatch,
):
    monkeypatch.setattr(swarm_orchestration, "SWARM_AVAILABLE", True)
    monkeypatch.setattr(
        swarm_orchestration,
        "_orchestrator",
        _fake_orchestrator(agent_count=0),
        raising=False,
    )
    request = SimpleNamespace(state=SimpleNamespace())

    payload = await swarm_orchestration.swarm_orchestration_readiness(request)

    assert payload["status"] == "degraded"
    assert request.state.degraded_dependencies == {"agents"}
