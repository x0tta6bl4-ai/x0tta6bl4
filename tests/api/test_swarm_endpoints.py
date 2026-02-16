import hmac
import os
from datetime import datetime
from unittest.mock import AsyncMock, MagicMock

import pytest
from httpx import ASGITransport, AsyncClient


@pytest.fixture
def admin_token():
    token = "test-admin-token"
    os.environ["ADMIN_TOKEN"] = token
    return token


@pytest.fixture
def mock_swarm_orchestrator(monkeypatch):
    mock_orchestrator = MagicMock()
    mock_orchestrator.swarm_id = "test-swarm"
    mock_orchestrator.created_at = datetime.now().timestamp()  # Use a real timestamp

    mock_config = MagicMock()
    mock_config.name = "test-swarm"
    mock_orchestrator.config = mock_config

    mock_status = MagicMock()
    mock_status.value = "ready"  # Set to 'ready' to match initialization
    mock_orchestrator.status = mock_status

    mock_orchestrator.get_status.return_value = {
        "status": "ready"
    }  # Return 'ready' here too

    mock_agent = MagicMock()
    mock_agent.get_status.return_value = {"state": "idle"}
    mock_orchestrator.agents = {"agent-1": mock_agent}  # At least one agent

    mock_orchestrator.initialize = AsyncMock()
    mock_orchestrator.scale = AsyncMock()
    mock_orchestrator.terminate = AsyncMock()
    mock_orchestrator.submit_task = AsyncMock(return_value="test-task-id")
    mock_orchestrator.get_task_status = AsyncMock(return_value={"status": "completed"})

    monkeypatch.setattr(
        "src.swarm.orchestrator.SwarmOrchestrator",
        MagicMock(return_value=mock_orchestrator),
    )
    return mock_orchestrator


@pytest.fixture
def app(monkeypatch):
    from src.api.swarm import router
    from src.core.app import app

    app.include_router(router)
    # Ensure swarms are cleared before each test
    monkeypatch.setattr("src.api.swarm._swarms", {})
    yield app


@pytest.fixture
def mock_active_swarm(mock_swarm_orchestrator, monkeypatch):
    # This fixture sets up an already existing swarm in the _swarms registry
    swarms_dict = {mock_swarm_orchestrator.swarm_id: mock_swarm_orchestrator}
    monkeypatch.setattr("src.api.swarm._swarms", swarms_dict)
    return mock_swarm_orchestrator.swarm_id


@pytest.mark.asyncio
async def test_create_swarm(app, admin_token, mock_swarm_orchestrator):
    transport = ASGITransport(app=app)
    async with AsyncClient(transport=transport, base_url="http://test") as client:
        headers = {"x-admin-token": admin_token}
        response = await client.post(
            "/api/v3/swarm/create",
            headers=headers,
            json={"name": "test-swarm", "num_agents": 5},
        )
        assert response.status_code == 200
        data = response.json()
        assert data["name"] == "test-swarm"
        assert data["num_agents"] == 1  # From mock
        assert data["status"] == "ready"  # Assert against 'ready'
        mock_swarm_orchestrator.initialize.assert_called_once()


@pytest.mark.asyncio
async def test_get_swarm_status(app, mock_active_swarm, mock_swarm_orchestrator):
    transport = ASGITransport(app=app)
    async with AsyncClient(transport=transport, base_url="http://test") as client:
        status_response = await client.get(f"/api/v3/swarm/{mock_active_swarm}/status")
        assert status_response.status_code == 200
        data = status_response.json()
        assert data["status"] == "ready"  # Assert against 'ready'
        mock_swarm_orchestrator.get_status.assert_called_once()


@pytest.mark.asyncio
async def test_submit_task(
    app, mock_active_swarm, admin_token, mock_swarm_orchestrator
):
    transport = ASGITransport(app=app)
    async with AsyncClient(transport=transport, base_url="http://test") as client:
        headers = {"x-admin-token": admin_token}
        task_data = {"task_type": "test", "payload": {"data": "test"}}
        task_response = await client.post(
            f"/api/v3/swarm/{mock_active_swarm}/tasks", headers=headers, json=task_data
        )
        assert task_response.status_code == 200
        data = task_response.json()
        assert data["task_id"] == "test-task-id"
        mock_swarm_orchestrator.submit_task.assert_called_once()


@pytest.mark.asyncio
async def test_get_task_status(app, mock_active_swarm, mock_swarm_orchestrator):
    transport = ASGITransport(app=app)
    async with AsyncClient(transport=transport, base_url="http://test") as client:
        task_id = "test-task-id"
        status_response = await client.get(
            f"/api/v3/swarm/{mock_active_swarm}/tasks/{task_id}"
        )
        assert status_response.status_code == 200
        data = status_response.json()
        assert data["status"] == "completed"
        mock_swarm_orchestrator.get_task_status.assert_called_once_with(task_id)


@pytest.mark.asyncio
async def test_list_agents(app, mock_active_swarm, mock_swarm_orchestrator):
    transport = ASGITransport(app=app)
    async with AsyncClient(transport=transport, base_url="http://test") as client:
        agents_response = await client.get(f"/api/v3/swarm/{mock_active_swarm}/agents")
        assert agents_response.status_code == 200
        data = agents_response.json()
        assert data["total_agents"] == 1
        assert len(data["agents"]) == 1
        assert data["agents"][0]["state"] == "idle"


@pytest.mark.asyncio
async def test_scale_swarm(
    app, mock_active_swarm, admin_token, mock_swarm_orchestrator
):
    transport = ASGITransport(app=app)
    async with AsyncClient(transport=transport, base_url="http://test") as client:
        headers = {"x-admin-token": admin_token}
        scale_data = {"action": "scale_up", "num_agents": 2}
        scale_response = await client.post(
            f"/api/v3/swarm/{mock_active_swarm}/scale", headers=headers, json=scale_data
        )
        assert scale_response.status_code == 200
        data = scale_response.json()
        assert data["action"] == "scale_up"
        mock_swarm_orchestrator.scale.assert_called_once_with(
            mock_swarm_orchestrator.agents.values().__len__() + scale_data["num_agents"]
        )


@pytest.mark.asyncio
async def test_terminate_swarm(
    app, mock_active_swarm, admin_token, mock_swarm_orchestrator
):
    transport = ASGITransport(app=app)
    async with AsyncClient(transport=transport, base_url="http://test") as client:
        headers = {"x-admin-token": admin_token}
        terminate_response = await client.delete(
            f"/api/v3/swarm/{mock_active_swarm}", headers=headers
        )
        assert terminate_response.status_code == 200
        data = terminate_response.json()
        assert data["status"] == "terminated"
        mock_swarm_orchestrator.terminate.assert_called_once()


@pytest.mark.asyncio
async def test_list_swarms(app, mock_active_swarm):
    transport = ASGITransport(app=app)
    async with AsyncClient(transport=transport, base_url="http://test") as client:
        list_response = await client.get("/api/v3/swarm")
        assert list_response.status_code == 200
        data = list_response.json()
        assert data["total"] == 1
        assert len(data["swarms"]) == 1
        assert data["swarms"][0]["name"] == "test-swarm"
