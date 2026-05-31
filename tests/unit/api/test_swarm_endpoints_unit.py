from types import SimpleNamespace
from unittest.mock import AsyncMock

import pytest
from fastapi import FastAPI
from httpx import ASGITransport, AsyncClient

from src.api import swarm as swarm_api
from src.api.swarm import router


def _build_app() -> FastAPI:
    app = FastAPI()
    app.include_router(router)
    return app


def _fake_swarm(
    name: str = "swarm-a", status: str = "running", created_at: float = 1.0
):
    return SimpleNamespace(
        config=SimpleNamespace(name=name, enable_vision=True),
        status=SimpleNamespace(value=status),
        created_at=created_at,
        agents={},
        terminate=AsyncMock(),
        get_status=lambda: {"status": status},
    )


def _force_swarm_dependencies_ready(monkeypatch):
    monkeypatch.setenv("ADMIN_TOKEN", "expected-token")
    monkeypatch.setattr(swarm_api, "_swarm_orchestrator_available", lambda: True)
    monkeypatch.setattr(swarm_api, "_swarm_task_model_available", lambda: True)
    monkeypatch.setattr(swarm_api, "_swarm_vision_engine_available", lambda: True)


@pytest.mark.asyncio
async def test_verify_admin_token_requires_configuration(monkeypatch):
    monkeypatch.delenv("ADMIN_TOKEN", raising=False)

    with pytest.raises(swarm_api.HTTPException) as exc_info:
        await swarm_api.verify_admin_token("token")

    assert exc_info.value.status_code == 500
    assert exc_info.value.detail == "Admin token not configured"


@pytest.mark.asyncio
async def test_verify_admin_token_rejects_invalid_token(monkeypatch):
    monkeypatch.setenv("ADMIN_TOKEN", "expected-token")

    with pytest.raises(swarm_api.HTTPException) as exc_info:
        await swarm_api.verify_admin_token("wrong-token")

    assert exc_info.value.status_code == 403
    assert exc_info.value.detail == "Admin access required"


@pytest.mark.asyncio
async def test_get_swarm_status_returns_404_for_missing_swarm(monkeypatch):
    monkeypatch.setattr(swarm_api, "_swarms", {})

    transport = ASGITransport(app=_build_app())
    async with AsyncClient(transport=transport, base_url="http://test") as client:
        response = await client.get("/api/v3/swarm/missing-id/status")

    assert response.status_code == 404
    assert response.json()["detail"] == "Swarm not found: missing-id"


@pytest.mark.asyncio
async def test_list_swarms_applies_filter_and_pagination(monkeypatch):
    running = _fake_swarm(name="running-swarm", status="running")
    paused = _fake_swarm(name="paused-swarm", status="paused")
    monkeypatch.setattr(swarm_api, "_swarms", {"run": running, "pause": paused})

    transport = ASGITransport(app=_build_app())
    async with AsyncClient(transport=transport, base_url="http://test") as client:
        response = await client.get(
            "/api/v3/swarm",
            params={"status_filter": "running", "limit": 1, "offset": 0},
        )

    assert response.status_code == 200
    payload = response.json()
    assert payload["total"] == 1
    assert len(payload["swarms"]) == 1
    assert payload["swarms"][0]["name"] == "running-swarm"
    assert payload["swarms"][0]["status"] == "running"


@pytest.mark.asyncio
async def test_terminate_swarm_removes_registry_entry(monkeypatch):
    monkeypatch.setenv("ADMIN_TOKEN", "expected-token")
    target_swarm = _fake_swarm(name="to-terminate", status="running")
    swarms = {"s-1": target_swarm}
    monkeypatch.setattr(swarm_api, "_swarms", swarms)

    transport = ASGITransport(app=_build_app())
    async with AsyncClient(transport=transport, base_url="http://test") as client:
        response = await client.request(
            "DELETE",
            "/api/v3/swarm/s-1",
            headers={"x-admin-token": "expected-token"},
            json={"graceful": False},
        )

    assert response.status_code == 200
    assert response.json()["status"] == "terminated"
    assert "s-1" not in swarms
    target_swarm.terminate.assert_awaited_once_with(graceful=False)


def test_swarm_readiness_ready_when_core_dependencies_are_available(monkeypatch):
    _force_swarm_dependencies_ready(monkeypatch)
    monkeypatch.setattr(swarm_api, "_swarms", {"s-1": _fake_swarm()})

    payload = swarm_api._swarm_readiness_status()

    assert payload["status"] == "healthy"
    assert payload["swarm_runtime_ready"] is True
    assert payload["registry_ready"] is True
    assert payload["admin_token_ready"] is True
    assert payload["rate_limiter_ready"] is True
    assert payload["orchestrator_ready"] is True
    assert payload["task_model_ready"] is True
    assert payload["vision_engine_ready"] is True
    assert payload["active_swarms"] == 1
    assert payload["total_agents"] == 0
    assert payload["cross_plane_claim_gate"]["allowed"] is False
    assert "production_readiness" in payload["cross_plane_claim_gate"]["requested_claim_ids"]
    assert payload["degraded_dependencies"] == []


def test_swarm_readiness_degraded_when_dependencies_are_missing(monkeypatch):
    monkeypatch.delenv("ADMIN_TOKEN", raising=False)
    monkeypatch.setattr(swarm_api, "_swarms", [])
    monkeypatch.setattr(swarm_api, "_swarm_lock", SimpleNamespace())
    monkeypatch.setattr(swarm_api, "limiter", SimpleNamespace(limit=None))
    monkeypatch.setattr(swarm_api, "_swarm_orchestrator_available", lambda: False)
    monkeypatch.setattr(swarm_api, "_swarm_task_model_available", lambda: False)
    monkeypatch.setattr(swarm_api, "_swarm_vision_engine_available", lambda: False)

    payload = swarm_api._swarm_readiness_status()

    assert payload["status"] == "degraded"
    assert payload["swarm_runtime_ready"] is False
    assert payload["active_swarms"] is None
    assert payload["total_agents"] is None
    assert payload["degraded_dependencies"] == [
        "registry",
        "admin_token",
        "rate_limiter",
        "orchestrator",
        "task_model",
        "vision_engine",
    ]
    assert "in-memory _swarms registry" in payload["backing_state"]["registry"]
    assert "does not create a swarm" in payload["claim_boundary"]


@pytest.mark.asyncio
async def test_swarm_health_marks_degraded_dependencies(monkeypatch):
    _force_swarm_dependencies_ready(monkeypatch)
    monkeypatch.setattr(swarm_api, "_swarms", [])
    monkeypatch.setattr(swarm_api, "_swarm_lock", SimpleNamespace())
    request = SimpleNamespace(state=SimpleNamespace())

    payload = await swarm_api.swarm_health(request)

    assert payload["status"] == "degraded"
    assert request.state.degraded_dependencies == {"registry"}
