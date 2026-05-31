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
from starlette.requests import Request

from src.coordination.events import EventBus, EventType

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
        assert payload["cross_plane_claim_gate"]["allowed"] is False
        assert payload["cross_plane_claim_gate"]["requested_claim_ids"] == [
            "production_readiness",
            "dataplane_delivery",
            "dpi_bypass",
            "customer_traffic",
        ]
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
        assert payload["cross_plane_claim_gate"]["decision"] == "CROSS_PLANE_CLAIMS_BLOCKED"
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


class TestVPNStatusEvidence:
    @pytest.mark.asyncio
    async def test_status_event_links_leak_protector_evidence_and_redacts_raw_values(
        self,
        monkeypatch,
        tmp_path,
    ):
        bus = EventBus(str(tmp_path))
        request = Request(
            {
                "type": "http",
                "method": "GET",
                "path": "/vpn/status",
                "headers": [],
                "client": ("127.0.0.1", 12345),
            }
        )
        request.state.event_bus = bus

        monkeypatch.setenv(
            "VPN_API_STATUS_READ_SPIFFE_ID",
            "spiffe://secret/vpn-api-status",
        )
        monkeypatch.setenv("VPN_API_STATUS_READ_DID", "did:mesh:vpn-api-secret")
        monkeypatch.setenv(
            "VPN_API_STATUS_READ_WALLET_ADDRESS",
            "0xbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbb",
        )

        async def _status_payload():
            return {
                "status": "online",
                "server": "vpn.secret.example",
                "port": 443,
                "protocol": "VLESS+Reality",
                "active_users": 7,
                "uptime": 123.4,
            }

        class _Protector:
            doh_resolver = None
            event_bus = None
            event_project_root = "."

            async def get_status(self):
                return {
                    "protection_enabled": True,
                    "kill_switch_enabled": False,
                    "vpn_interface": "tun-secret",
                    "original_dns_servers": ["10.0.0.2"],
                    "resolver_info": {
                        "current_server": {
                            "name": "SecretResolver",
                            "url": "https://secret-dns.example/query",
                        }
                    },
                }

            def get_last_event_evidence(self):
                return {
                    "event_id": "evt-vpn-leak-status",
                    "source_agent": "vpn-leak-protector",
                    "layer": "network_vpn_leak_protection_observed_state",
                    "operation": "get_status",
                    "stage": "status_read",
                    "status": "success",
                    "observed_state": True,
                    "control_action": False,
                    "claim_boundary": "bounded leak-protector status evidence",
                    "raw_identifiers_redacted": True,
                    "payloads_redacted": True,
                }

        async def _protector():
            return _Protector()

        monkeypatch.setattr(vpn_mod, "_get_vpn_status_cached", _status_payload)
        monkeypatch.setattr(vpn_mod, "get_vpn_protector", _protector)

        response = await vpn_mod.get_vpn_status(
            request=request,
            db=SimpleNamespace(),
        )

        assert response.status == "online"
        events = bus.get_event_history(
            event_type=EventType.PIPELINE_STAGE_END,
            source_agent="vpn-api-status-read",
            limit=10,
        )
        payload = events[-1].data
        payload_text = repr(payload)
        log_path = tmp_path / EventBus.EVENT_LOG
        log_text = log_path.read_text() if log_path.exists() else ""

        assert payload["operation"] == "get_vpn_status"
        assert payload["vpn_status"] == "online"
        assert payload["vpn_server_hash"] == vpn_mod._redacted_sha256_prefix(
            "vpn.secret.example"
        )
        assert payload["active_user_count"] == 7
        leak_evidence = payload["leak_protection_status_evidence"]
        assert leak_evidence["available"] is True
        assert leak_evidence["status_summary"]["protection_enabled"] is True
        assert leak_evidence["status_summary"]["original_dns_server_count"] == 1
        assert leak_evidence["event_reference"]["event_id"] == "evt-vpn-leak-status"
        assert leak_evidence["event_reference"]["source_agent"] == "vpn-leak-protector"
        assert payload["service_identity"]["spiffe_id_present"] is True
        assert payload["raw_identifiers_redacted"] is True
        assert payload["payloads_redacted"] is True

        for raw_value in [
            "vpn.secret.example",
            "tun-secret",
            "10.0.0.2",
            "SecretResolver",
            "https://secret-dns.example/query",
            "spiffe://secret/vpn-api-status",
            "did:mesh:vpn-api-secret",
            "0xbbbbbb",
        ]:
            assert raw_value not in payload_text
            assert raw_value not in log_text


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
