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
