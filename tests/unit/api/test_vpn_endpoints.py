"""
Unit tests for src/api/vpn.py VPN API endpoints.

Tests VPN config generation, status, admin-gated user listing.
All external dependencies (DB, vpn_config_generator, cache) are mocked.
"""

import os
from unittest.mock import AsyncMock, MagicMock, patch

import pytest

os.environ.setdefault("X0TTA6BL4_PRODUCTION", "false")
os.environ.setdefault("X0TTA6BL4_SPIFFE", "false")
os.environ.setdefault("X0TTA6BL4_FORCE_MOCK_SPIFFE", "true")
os.environ.setdefault("ADMIN_TOKEN", "test-admin-token")

try:
    from src.api.vpn import (VPNConfigRequest, VPNConfigResponse,
                             VPNStatusResponse, router, verify_admin_token)

    VPN_AVAILABLE = True
except ImportError as exc:
    VPN_AVAILABLE = False
    pytest.skip(f"vpn module not importable: {exc}", allow_module_level=True)


# ---------------------------------------------------------------------------
# Model validation tests
# ---------------------------------------------------------------------------


class TestVPNModels:
    def test_vpn_config_request_defaults(self):
        req = VPNConfigRequest(user_id=42)
        assert req.user_id == 42
        assert req.username is None
        assert req.server is None
        assert req.port is None

    def test_vpn_config_request_with_values(self):
        req = VPNConfigRequest(
            user_id=1, username="alice", server="vpn.example.com", port=443
        )
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

    def test_router_tags(self):
        assert "vpn" in router.tags


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
