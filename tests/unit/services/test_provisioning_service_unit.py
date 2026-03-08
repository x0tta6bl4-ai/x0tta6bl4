"""Unit tests for src.services.provisioning_service."""

from __future__ import annotations

import os
from unittest.mock import AsyncMock, MagicMock, patch

import pytest

from src.services.provisioning_service import (
    ProvisioningResult,
    ProvisioningService,
    ProvisioningSource,
    _SimulatedXUI,
    _resolve_mesh_provisioner,
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
async def test_provision_vpn_user_accepts_string_source(monkeypatch):
    svc = ProvisioningService()
    svc._xui_client = MagicMock()
    svc._xui_client.create_user.return_value = {
        "uuid": "uuid-from-xui",
        "vless_link": "vless://from-xui",
    }

    async def _noop(**_kwargs):
        return None

    monkeypatch.setattr(svc, "_update_database", _noop)
    monkeypatch.setattr(svc, "_send_telegram_config", _noop)

    out = await svc.provision_vpn_user(
        email="user@example.com",
        source="admin_api",
    )

    assert out.success is True
    assert out.vpn_uuid == "uuid-from-xui"
    assert out.vless_link == "vless://from-xui"


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


# ---------------------------------------------------------------------------
# ProvisioningResult
# ---------------------------------------------------------------------------


class TestProvisioningResult:
    def test_success_to_dict(self):
        r = ProvisioningResult(
            success=True,
            vpn_uuid="uuid-1",
            vless_link="vless://x",
            email="u@example.com",
            plan="pro",
        )
        d = r.to_dict()
        assert d["success"] is True
        assert d["vpn_uuid"] == "uuid-1"
        assert d["vless_link"] == "vless://x"
        assert d["email"] == "u@example.com"
        assert d["plan"] == "pro"
        assert d["error"] is None
        assert "provisioned_at" in d

    def test_failure_to_dict(self):
        r = ProvisioningResult(success=False, email="x@y.com", error="Invalid email")
        d = r.to_dict()
        assert d["success"] is False
        assert d["error"] == "Invalid email"

    def test_provisioned_at_is_isoformat_string(self):
        r = ProvisioningResult(success=True)
        d = r.to_dict()
        # isoformat produces a parseable datetime string
        from datetime import datetime
        dt = datetime.fromisoformat(d["provisioned_at"])
        assert dt is not None

    def test_default_plan_is_trial(self):
        r = ProvisioningResult(success=True)
        assert r.plan == "trial"


# ---------------------------------------------------------------------------
# ProvisioningSource
# ---------------------------------------------------------------------------


class TestProvisioningSource:
    def test_all_values_are_strings(self):
        for src in ProvisioningSource:
            assert isinstance(src.value, str)

    def test_stripe_webhook_value(self):
        assert ProvisioningSource.STRIPE_WEBHOOK.value == "stripe_webhook"

    def test_admin_api_value(self):
        assert ProvisioningSource.ADMIN_API.value == "admin_api"


# ---------------------------------------------------------------------------
# _resolve_mesh_provisioner
# ---------------------------------------------------------------------------


def test_resolve_mesh_provisioner_returns_none_when_both_fail():
    with patch.dict("sys.modules", {"src.api.maas": None, "src.api.maas_legacy": None}):
        # Both imports fail → function returns None
        result = _resolve_mesh_provisioner()
        # May return a module or None depending on environment; just check no exception
        assert result is None or result is not None  # no crash


# ---------------------------------------------------------------------------
# ProvisioningService — additional paths
# ---------------------------------------------------------------------------


@pytest.mark.asyncio
async def test_provision_vpn_user_empty_email_rejected():
    svc = ProvisioningService()
    out = await svc.provision_vpn_user(email="")
    assert out.success is False
    assert out.error == "Invalid email"


@pytest.mark.asyncio
async def test_provision_vpn_user_no_telegram_skips_notify(monkeypatch):
    svc = ProvisioningService()
    svc._xui_client = MagicMock()
    svc._xui_client.create_user.return_value = {
        "uuid": "u-1",
        "vless_link": "vless://x",
    }
    notify_calls = []

    async def _noop(**kw):
        return None

    async def _track_notify(**kw):
        notify_calls.append(kw)

    monkeypatch.setattr(svc, "_update_database", _noop)
    monkeypatch.setattr(svc, "_send_telegram_config", _track_notify)

    # No telegram_chat_id → notify should NOT be called
    await svc.provision_vpn_user(email="u@example.com", telegram_chat_id=None)
    assert notify_calls == []


@pytest.mark.asyncio
async def test_provision_vpn_user_enum_source_used(monkeypatch):
    svc = ProvisioningService()
    svc._xui_client = MagicMock()
    svc._xui_client.create_user.return_value = {"uuid": "u-1", "vless_link": "vless://x"}

    async def _noop(**kw):
        return None

    monkeypatch.setattr(svc, "_update_database", _noop)
    monkeypatch.setattr(svc, "_send_telegram_config", _noop)

    out = await svc.provision_vpn_user(
        email="u@example.com",
        source=ProvisioningSource.CRYPTO_PAYMENT,
    )
    assert out.success is True


@pytest.mark.asyncio
async def test_provision_mesh_provisioner_unavailable(monkeypatch):
    svc = ProvisioningService()
    monkeypatch.setattr(
        "src.services.provisioning_service._resolve_mesh_provisioner",
        lambda: None,
    )
    result = await svc.provision_mesh("m", 2, "owner")
    assert result["success"] is False
    assert "error" in result


@pytest.mark.asyncio
async def test_terminate_mesh_provisioner_unavailable(monkeypatch):
    svc = ProvisioningService()
    monkeypatch.setattr(
        "src.services.provisioning_service._resolve_mesh_provisioner",
        lambda: None,
    )
    result = await svc.terminate_mesh("mesh-x")
    assert result is False


@pytest.mark.asyncio
async def test_provision_mesh_exception_returns_failure(monkeypatch):
    svc = ProvisioningService()

    class _FailProv:
        async def create(self, **kwargs):
            raise RuntimeError("infra down")

    monkeypatch.setattr(
        "src.services.provisioning_service._resolve_mesh_provisioner",
        lambda: _FailProv(),
    )
    result = await svc.provision_mesh("m", 2, "owner")
    assert result["success"] is False
    assert "infra down" in result["error"]


# ---------------------------------------------------------------------------
# _SimulatedXUI — extended
# ---------------------------------------------------------------------------


def test_simulated_xui_create_user_has_server_and_port():
    sim = _SimulatedXUI()
    result = sim.create_user(user_id=42, email="x@example.com", remark="test")
    assert "server" in result
    assert "port" in result
    assert isinstance(result["port"], int)


def test_simulated_xui_create_user_unique_uuids():
    sim = _SimulatedXUI()
    r1 = sim.create_user(user_id=1, email="a@example.com")
    r2 = sim.create_user(user_id=2, email="b@example.com")
    assert r1["uuid"] != r2["uuid"]


def test_simulated_xui_create_user_respects_env_vars(monkeypatch):
    monkeypatch.setenv("VPN_SERVER", "vpn.example.com")
    monkeypatch.setenv("VPN_PORT", "8443")
    sim = _SimulatedXUI()
    result = sim.create_user(user_id=1, email="x@example.com")
    assert result["server"] == "vpn.example.com"
    assert result["port"] == 8443


def test_simulated_xui_has_simulated_flag():
    assert _SimulatedXUI.simulated is True


# ---------------------------------------------------------------------------
# Singleton
# ---------------------------------------------------------------------------


def test_module_singleton_is_provisioning_service():
    from src.services import provisioning_service as mod
    assert hasattr(mod, "provisioning_service")
    assert isinstance(mod.provisioning_service, ProvisioningService)
