"""Unit tests for src.services.provisioning_service."""

from __future__ import annotations

import types
from datetime import datetime
from unittest.mock import MagicMock

import pytest

from src.services.provisioning_service import (
    ProvisioningResult,
    ProvisioningService,
    _SimulatedXUI,
)


@pytest.mark.asyncio
async def test_provision_vpn_user_rejects_invalid_email():
    svc = ProvisioningService()
    out = await svc.provision_vpn_user(email="invalid-email")
    assert out.success is False
    assert out.error == "Invalid email"


@pytest.mark.asyncio
async def test_provision_vpn_user_success_path_with_xui_uuid(monkeypatch):
    svc = ProvisioningService()
    svc._xui_client = MagicMock()
    svc._xui_client.create_user.return_value = {
        "uuid": "uuid-from-xui",
        "vless_link": "vless://from-xui",
    }
    update_calls = []
    notify_calls = []

    async def _update(**kwargs):
        update_calls.append(kwargs)

    async def _notify(**kwargs):
        notify_calls.append(kwargs)

    monkeypatch.setattr(svc, "_update_database", _update)
    monkeypatch.setattr(svc, "_send_telegram_config", _notify)

    out = await svc.provision_vpn_user(
        email="user@example.com",
        plan="pro",
        user_id="u-1",
        telegram_chat_id=123,
    )

    assert out.success is True
    assert out.vpn_uuid == "uuid-from-xui"
    assert out.vless_link == "vless://from-xui"
    assert update_calls and update_calls[0]["email"] == "user@example.com"
    assert notify_calls and notify_calls[0]["chat_id"] == 123


@pytest.mark.asyncio
async def test_provision_vpn_user_xui_failure_uses_fallback_link(monkeypatch):
    svc = ProvisioningService()
    svc._xui_client = MagicMock()
    svc._xui_client.create_user.side_effect = RuntimeError("xui down")
    svc._xray_manager = MagicMock()
    svc._xray_manager.generate_vless_link.return_value = "vless://from-xray"
    monkeypatch.setattr(svc, "_update_database", lambda **kwargs: None)
    monkeypatch.setattr(svc, "_send_telegram_config", lambda **kwargs: None)

    async def _noop(*args, **kwargs):
        return None

    monkeypatch.setattr(svc, "_update_database", _noop)
    monkeypatch.setattr(svc, "_send_telegram_config", _noop)

    out = await svc.provision_vpn_user(email="user@example.com")
    assert out.success is True
    assert out.vless_link.startswith("vless://")


@pytest.mark.asyncio
async def test_revoke_vpn_user_variants():
    svc = ProvisioningService()
    assert await svc.revoke_vpn_user("") is False

    svc._xui_client = MagicMock()
    svc._xui_client.delete_user.return_value = True
    assert await svc.revoke_vpn_user("a@b.com") is True

    svc._xui_client.delete_user.side_effect = RuntimeError("boom")
    assert await svc.revoke_vpn_user("a@b.com") is False


@pytest.mark.asyncio
async def test_provision_and_terminate_mesh_paths(monkeypatch):
    svc = ProvisioningService()

    class _Instance:
        mesh_id = "mesh-1"
        status = "active"
        node_instances = [1, 2]

    class _Prov:
        async def create(self, **kwargs):
            return _Instance()

        async def terminate(self, mesh_id):
            return mesh_id == "mesh-1"

    monkeypatch.setattr("src.services.provisioning_service._resolve_mesh_provisioner", lambda: _Prov())

    created = await svc.provision_mesh("m", 2, "owner")
    assert created == {"success": True, "mesh_id": "mesh-1", "status": "active", "nodes": 2}

    assert await svc.terminate_mesh("mesh-1") is True
    assert await svc.terminate_mesh("mesh-x") is False


def test_simulated_xui_helpers():
    sim = _SimulatedXUI()
    created = sim.create_user(user_id=1, email="u@example.com")
    assert "uuid" in created and created["uuid"]
    assert sim.delete_user("u@example.com") is True
    assert sim.get_active_users_count() == 0
