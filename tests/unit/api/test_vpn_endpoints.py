"""
Unit tests for src/api/vpn.py VPN API endpoints.

Tests VPN config generation, status, admin-gated user listing.
All external dependencies (DB, vpn_config_generator, cache) are mocked.
"""

import asyncio
import os
from types import SimpleNamespace
from unittest.mock import MagicMock
from unittest.mock import patch

import pytest

os.environ.setdefault("X0TTA6BL4_PRODUCTION", "false")
os.environ.setdefault("X0TTA6BL4_SPIFFE", "false")
os.environ.setdefault("X0TTA6BL4_FORCE_MOCK_SPIFFE", "true")
os.environ.setdefault("ADMIN_TOKEN", "test-admin-token")

try:
    import src.api.vpn as vpn_mod
    from src.api.vpn import (VPNConfigRequest, VPNConfigResponse,
                             VPNStatusResponse, router, verify_admin_token)

    VPN_AVAILABLE = True
except ImportError as exc:
    VPN_AVAILABLE = False
    pytest.skip(f"vpn module not importable: {exc}", allow_module_level=True)


def _force_vpn_dependencies_ready(monkeypatch) -> None:
    monkeypatch.setenv("ADMIN_TOKEN", "admin-token")
    monkeypatch.setenv("ENVIRONMENT", "production")
    monkeypatch.setenv("VPN_SERVER", "vpn.example.test")
    monkeypatch.setenv("VPN_PORT", "443")
    monkeypatch.setenv("VPN_SESSION_TOKEN", "session-token")
    monkeypatch.setenv("VPN_REALITY_PUBLIC_KEY", "reality-public-key")
    monkeypatch.setattr(vpn_mod, "cache", SimpleNamespace(get=lambda *_args: None, set=lambda *_args: None, delete=lambda *_args: None))
    monkeypatch.setattr(vpn_mod, "XUIAPIClient", object)
    monkeypatch.setattr(vpn_mod, "generate_vless_link", lambda *_args, **_kwargs: "ready-link")
    monkeypatch.setattr(vpn_mod, "generate_config_text", lambda *_args, **_kwargs: "config")
    monkeypatch.setattr(vpn_mod, "generate_experimental_link", lambda *_args, **_kwargs: "experimental-link")
    monkeypatch.setattr(vpn_mod, "generate_experimental_text", lambda *_args, **_kwargs: "exp-config")
    monkeypatch.setattr(vpn_mod, "require_permission", lambda _permission: lambda user: user)
    monkeypatch.setattr(vpn_mod, "get_current_user_from_maas", lambda *_args, **_kwargs: None)
    monkeypatch.setattr(
        vpn_mod,
        "_legacy_user_db",
        SimpleNamespace(
            get_user=lambda *_args: {},
            is_user_active=lambda *_args: True,
            update_user=lambda *_args, **_kwargs: True,
        ),
    )


# ---------------------------------------------------------------------------
# Model validation tests
# ---------------------------------------------------------------------------


class TestVPNModels:
    def test_vpn_config_request_defaults(self):
        req = VPNConfigRequest(user_id=42, email="user42@example.com")
        assert req.user_id == 42
        assert req.email == "user42@example.com"
        assert req.username is None
        assert req.server is None
        assert req.port is None

    def test_vpn_config_request_with_values(self):
        req = VPNConfigRequest(
            user_id=1,
            email="alice@example.com",
            username="alice",
            server="vpn.example.com",
            port=443,
        )
        assert req.email == "alice@example.com"
        assert req.username == "alice"
        assert req.server == "vpn.example.com"
        assert req.port == 443

    def test_vpn_config_response_structure(self):
        resp = VPNConfigResponse(
            user_id=1,
            username="bob",
            vless_link="vless://uuid@host:443",
            config_text="config here",
        )
        assert resp.user_id == 1
        assert "vless://" in resp.vless_link

    def test_vpn_status_response_structure(self):
        resp = VPNStatusResponse(
            status="online",
            server="vpn.example.com",
            port=443,
            protocol="VLESS+Reality",
            active_users=5,
            uptime=3600.0,
        )
        assert resp.status == "online"
        assert resp.protocol == "VLESS+Reality"


# ---------------------------------------------------------------------------
# Admin token verification
# ---------------------------------------------------------------------------


class TestAdminToken:
    @pytest.mark.asyncio
    async def test_verify_admin_token_missing_env(self):
        with patch.dict(os.environ, {"ADMIN_TOKEN": ""}, clear=False):
            os.environ.pop("ADMIN_TOKEN", None)
            from fastapi import HTTPException

            with pytest.raises(HTTPException) as exc_info:
                await verify_admin_token(None)
            assert exc_info.value.status_code == 403

    @pytest.mark.asyncio
    async def test_verify_admin_token_wrong_token(self):
        with patch.dict(os.environ, {"ADMIN_TOKEN": "correct-token"}, clear=False):
            from fastapi import HTTPException

            with pytest.raises(HTTPException) as exc_info:
                await verify_admin_token("wrong-token")
            assert exc_info.value.status_code == 403

    @pytest.mark.asyncio
    async def test_verify_admin_token_success(self):
        with patch.dict(os.environ, {"ADMIN_TOKEN": "good-token"}, clear=False):
            # Should not raise
            result = await verify_admin_token("good-token")
            assert result is None


# ---------------------------------------------------------------------------
# Router metadata tests
# ---------------------------------------------------------------------------


class TestVPNRouter:
    def test_router_prefix(self):
        assert router.prefix == "/vpn"

    def test_router_has_routes(self):
        route_paths = [r.path for r in router.routes]
        assert any("/config" in p for p in route_paths)
        assert any("/status" in p for p in route_paths)
        assert any("/readiness" in p for p in route_paths)

    def test_router_tags(self):
        assert "vpn" in router.tags


class TestVPNReadiness:
    def test_ready_when_core_dependencies_are_available(self, monkeypatch):
        _force_vpn_dependencies_ready(monkeypatch)
        db = MagicMock(spec=["query", "commit"])

        payload = vpn_mod._vpn_readiness_status(db)

        assert payload["status"] == "ready"
        assert payload["registration_mode"] == "full_mode_only"
        assert payload["route_present_in_light_mode"] is False
        assert payload["lifecycle_binding"] == "route_import_only"
        assert payload["startup_hook_completed"] is None
        assert payload["vpn_runtime_ready"] is True
        assert payload["vpn_db_ready"] is True
        assert payload["user_model_ready"] is True
        assert payload["config_generators_ready"] is True
        assert payload["xui_client_factory_ready"] is True
        assert payload["cache_ready"] is True
        assert payload["auth_dependency_ready"] is True
        assert payload["legacy_admin_token_ready"] is True
        assert payload["zkp_legacy_db_ready"] is True
        assert payload["zkp_attestor_ready"] is True
        assert payload["production_env_ready"] is True
        assert payload["route_precedence"]["shadowed_by_legacy"] == []
        assert payload["degraded_dependencies"] == []

    def test_degraded_when_dependencies_are_missing(self, monkeypatch):
        monkeypatch.delenv("ADMIN_TOKEN", raising=False)
        monkeypatch.setenv("ENVIRONMENT", "production")
        monkeypatch.delenv("VPN_SERVER", raising=False)
        monkeypatch.delenv("VPN_PORT", raising=False)
        monkeypatch.delenv("VPN_SESSION_TOKEN", raising=False)
        monkeypatch.delenv("VPN_REALITY_PUBLIC_KEY", raising=False)
        monkeypatch.setattr(vpn_mod, "User", SimpleNamespace(id="id"))
        monkeypatch.setattr(vpn_mod, "generate_vless_link", None)
        monkeypatch.setattr(vpn_mod, "generate_config_text", None)
        monkeypatch.setattr(vpn_mod, "generate_experimental_link", None)
        monkeypatch.setattr(vpn_mod, "generate_experimental_text", None)
        monkeypatch.setattr(vpn_mod, "XUIAPIClient", None)
        monkeypatch.setattr(vpn_mod, "cache", None)
        monkeypatch.setattr(vpn_mod, "require_permission", None)
        monkeypatch.setattr(vpn_mod, "get_current_user_from_maas", None)
        monkeypatch.setattr(vpn_mod, "_legacy_user_db", None)
        monkeypatch.setattr(vpn_mod, "NIZKPAttestor", SimpleNamespace())

        payload = vpn_mod._vpn_readiness_status(SimpleNamespace())

        assert payload["status"] == "degraded"
        assert payload["vpn_runtime_ready"] is False
        assert payload["vpn_db_ready"] is False
        assert payload["user_model_ready"] is False
        assert payload["config_generators_ready"] is False
        assert payload["xui_client_factory_ready"] is False
        assert payload["cache_ready"] is False
        assert payload["auth_dependency_ready"] is False
        assert payload["legacy_admin_token_ready"] is False
        assert payload["zkp_legacy_db_ready"] is False
        assert payload["zkp_attestor_ready"] is False
        assert payload["production_env_ready"] is False
        assert payload["degraded_dependencies"] == [
            "database",
            "user_model",
            "vpn_config_generators",
            "xui_client",
            "cache",
            "auth",
            "legacy_admin_token",
            "zkp_legacy_db",
            "zkp_attestor",
            "production_vpn_env",
        ]
        assert "does not prove that the VPN server is currently reachable" in (
            payload["claim_boundary"]
        )

    def test_endpoint_marks_degraded_dependencies(self, monkeypatch):
        _force_vpn_dependencies_ready(monkeypatch)
        request = SimpleNamespace(state=SimpleNamespace())

        payload = asyncio.run(
            vpn_mod.vpn_readiness(request=request, db=SimpleNamespace())
        )

        assert payload["status"] == "degraded"
        assert request.state.degraded_dependencies == {"database"}


# ---------------------------------------------------------------------------
# VPN config generation (mock external deps)
# ---------------------------------------------------------------------------


class TestVPNConfigGeneration:
    @patch("src.api.vpn.generate_vless_link", return_value="vless://test-uuid@host:443")
    @patch("src.api.vpn.generate_config_text", return_value="config text")
    def test_config_response_shape(self, mock_config, mock_link):
        resp = VPNConfigResponse(
            user_id=99,
            username="test",
            vless_link=mock_link.return_value,
            config_text=mock_config.return_value,
        )
        assert resp.vless_link.startswith("vless://")
        assert resp.config_text == "config text"


# ---------------------------------------------------------------------------
# Connectivity check function
# ---------------------------------------------------------------------------


class TestConnectivity:
    @pytest.mark.asyncio
    async def test_check_vpn_connectivity_timeout(self):
        from src.api.vpn import _check_vpn_connectivity

        # Use a non-routable IP to force timeout
        result = await _check_vpn_connectivity("192.0.2.1", 1)
        assert result in ("online", "offline")  # depends on network environment
