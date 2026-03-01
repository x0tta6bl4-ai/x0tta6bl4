"""Unit tests for src.api.maas_agent_mesh router."""

from __future__ import annotations

from fastapi import FastAPI
from fastapi.testclient import TestClient

from src.api import maas_agent_mesh as mod


class _StubBot:
    def __init__(self):
        self.calls = []

    def run_once(self, *, auto_heal: bool, dry_run: bool):
        self.calls.append((auto_heal, dry_run))
        return {
            "status": "healthy",
            "auto_heal": auto_heal,
            "dry_run": dry_run,
            "engine": "local-rule-engine",
            "external_ai_providers_used": False,
        }

    def history(self, limit: int = 20):
        return [{"status": "healthy", "limit": limit}]


def _build_client(monkeypatch):
    app = FastAPI()
    stub = _StubBot()
    monkeypatch.setattr(mod, "_health_bot", stub)
    app.dependency_overrides[mod.get_current_user_from_maas] = lambda: {"id": "u-test"}
    app.include_router(mod.router)
    return TestClient(app), stub


def test_health_status_endpoint_runs_in_read_only_mode(monkeypatch):
    client, stub = _build_client(monkeypatch)

    response = client.get("/api/v1/maas/agents/health/status")
    assert response.status_code == 200
    assert response.json()["external_ai_providers_used"] is False
    assert stub.calls[-1] == (False, True)


def test_health_run_allows_dry_run_without_token(monkeypatch):
    client, stub = _build_client(monkeypatch)

    response = client.post(
        "/api/v1/maas/agents/health/run",
        json={"auto_heal": True, "dry_run": True},
    )
    assert response.status_code == 200
    assert stub.calls[-1] == (True, True)


def test_health_run_blocks_exec_without_configured_token(monkeypatch):
    client, _stub = _build_client(monkeypatch)
    monkeypatch.delenv("MAAS_AGENT_BOT_TOKEN", raising=False)

    response = client.post(
        "/api/v1/maas/agents/health/run",
        json={"auto_heal": True, "dry_run": False},
    )
    assert response.status_code == 503
    assert "MAAS_AGENT_BOT_TOKEN" in response.text


def test_health_run_blocks_exec_with_wrong_token(monkeypatch):
    client, _stub = _build_client(monkeypatch)
    monkeypatch.setenv("MAAS_AGENT_BOT_TOKEN", "expected-token")

    response = client.post(
        "/api/v1/maas/agents/health/run",
        json={"auto_heal": True, "dry_run": False},
        headers={"X-Agent-Token": "wrong-token"},
    )
    assert response.status_code == 403


def test_health_run_exec_with_valid_token(monkeypatch):
    client, stub = _build_client(monkeypatch)
    monkeypatch.setenv("MAAS_AGENT_BOT_TOKEN", "expected-token")

    response = client.post(
        "/api/v1/maas/agents/health/run",
        json={"auto_heal": True, "dry_run": False},
        headers={"X-Agent-Token": "expected-token"},
    )
    assert response.status_code == 200
    assert stub.calls[-1] == (True, False)


def test_health_history_endpoint(monkeypatch):
    client, _stub = _build_client(monkeypatch)

    response = client.get("/api/v1/maas/agents/health/history?limit=7")
    assert response.status_code == 200
    payload = response.json()
    assert "items" in payload
    assert payload["items"][0]["limit"] == 7


def test_health_status_requires_auth_when_dependency_not_overridden(monkeypatch):
    app = FastAPI()
    stub = _StubBot()
    monkeypatch.setattr(mod, "_health_bot", stub)
    app.include_router(mod.router)
    client = TestClient(app)

    response = client.get("/api/v1/maas/agents/health/status")
    assert response.status_code == 401
