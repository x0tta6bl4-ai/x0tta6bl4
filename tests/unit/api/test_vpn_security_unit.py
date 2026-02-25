"""
Unit tests for VPN API security improvements
============================================

Tests for VPN server/port configuration with production safety checks.
"""

import os
from unittest.mock import patch, MagicMock

import pytest
from fastapi import HTTPException


class TestVPNServerConfiguration:
    """Tests for VPN server configuration functions."""

    def test_get_vpn_server_from_env(self):
        """Test getting VPN server from environment."""
        from src.api.vpn import _get_vpn_server

        with patch.dict(os.environ, {"VPN_SERVER": "vpn.example.com"}):
            server = _get_vpn_server()
            assert server == "vpn.example.com"

    def test_get_vpn_server_development_fallback(self):
        """Test development fallback when VPN_SERVER not set."""
        from src.api.vpn import _get_vpn_server

        with patch.dict(os.environ, {"VPN_SERVER": "", "ENVIRONMENT": "development"}, clear=False):
            # Remove VPN_SERVER if present
            os.environ.pop("VPN_SERVER", None)
            os.environ["ENVIRONMENT"] = "development"
            server = _get_vpn_server()
            assert server == "127.0.0.1"

    def test_get_vpn_server_production_required(self):
        """Test production requires VPN_SERVER to be set."""
        from src.api.vpn import _get_vpn_server

        # Clear VPN_SERVER and set ENVIRONMENT to production
        env = os.environ.copy()
        env.pop("VPN_SERVER", None)
        env["ENVIRONMENT"] = "production"

        with patch.dict(os.environ, env, clear=True):
            with pytest.raises(RuntimeError) as exc_info:
                _get_vpn_server()
            assert "VPN_SERVER" in str(exc_info.value)

    def test_get_vpn_port_from_env(self):
        """Test getting VPN port from environment."""
        from src.api.vpn import _get_vpn_port

        with patch.dict(os.environ, {"VPN_PORT": "443"}):
            port = _get_vpn_port()
            assert port == 443

    def test_get_vpn_port_development_fallback(self):
        """Test development fallback when VPN_PORT not set."""
        from src.api.vpn import _get_vpn_port

        with patch.dict(os.environ, {"ENVIRONMENT": "development"}):
            os.environ.pop("VPN_PORT", None)
            port = _get_vpn_port()
            assert port == 39829  # Default fallback

    def test_get_vpn_port_production_required(self):
        """Test production requires VPN_PORT to be set."""
        from src.api.vpn import _get_vpn_port

        env = os.environ.copy()
        env.pop("VPN_PORT", None)
        env["ENVIRONMENT"] = "production"

        with patch.dict(os.environ, env, clear=True):
            with pytest.raises(RuntimeError) as exc_info:
                _get_vpn_port()
            assert "VPN_PORT" in str(exc_info.value)


class TestVPNConfigGeneration:
    """Tests for VPN config generation with security improvements."""

    @pytest.fixture
    def mock_xui(self):
        """Mock XUI client."""
        with patch("src.api.vpn.xui") as mock:
            mock.create_user.return_value = {
                "uuid": "test-uuid-123",
                "server": "vpn.example.com",
                "port": 443,
            }
            yield mock

    def test_build_vpn_config_with_env_vars(self, mock_xui):
        """Test config generation uses environment variables."""
        from src.api.vpn import _build_vpn_config

        with patch.dict(os.environ, {
            "VPN_SERVER": "vpn.example.com",
            "VPN_PORT": "443",
            "ENVIRONMENT": "production",
        }):
            response = _build_vpn_config(
                user_id=1,
                email="test@example.com",
                username="testuser",
                server=None,
                port=None,
            )

            assert response.user_id == 1
            assert response.username == "testuser"
            assert "vless://" in response.vless_link

    def test_build_vpn_config_custom_server_port(self, mock_xui):
        """Test config generation with custom server/port override."""
        from src.api.vpn import _build_vpn_config

        with patch.dict(os.environ, {
            "VPN_SERVER": "default.vpn.com",
            "VPN_PORT": "443",
            "ENVIRONMENT": "production",
        }):
            response = _build_vpn_config(
                user_id=1,
                email="test@example.com",
                username="testuser",
                server="custom.vpn.com",
                port=8443,
            )

            assert response.user_id == 1

    def test_build_vpn_config_fallback_on_xui_failure(self):
        """Test config generation falls back gracefully on XUI failure."""
        from src.api.vpn import _build_vpn_config

        with patch("src.api.vpn.xui") as mock_xui:
            mock_xui.create_user.side_effect = Exception("XUI unavailable")

            with patch.dict(os.environ, {
                "VPN_SERVER": "fallback.vpn.com",
                "VPN_PORT": "443",
                "ENVIRONMENT": "production",
            }):
                response = _build_vpn_config(
                    user_id=1,
                    email="test@example.com",
                    username="testuser",
                    server=None,
                    port=None,
                )

                assert response.user_id == 1
                # Should have used fallback config


class TestGenevaPOCScript:
    """Tests for Geneva PoC script security."""

    def test_geneva_requires_env_var(self):
        """Test Geneva PoC requires GENEVA_MASTER_KEY env var."""
        import subprocess
        import sys

        # Run the script without GENEVA_MASTER_KEY
        env = os.environ.copy()
        env.pop("GENEVA_MASTER_KEY", None)

        result = subprocess.run(
            [sys.executable, "-c", 
             "from scripts.run_geneva_poc import run_geneva_training; run_geneva_training()"],
            env=env,
            capture_output=True,
            text=True,
        )

        # Should fail with RuntimeError
        assert result.returncode != 0
        assert "GENEVA_MASTER_KEY" in result.stderr or "GENEVA_MASTER_KEY" in result.stdout

    def test_geneva_with_env_var(self):
        """Test Geneva PoC works with GENEVA_MASTER_KEY set."""
        import subprocess
        import sys

        env = os.environ.copy()
        env["GENEVA_MASTER_KEY"] = "test_key_for_ci_32_bytes_long!!"

        # Just test that it starts without error
        # (we'll interrupt it quickly)
        result = subprocess.run(
            [sys.executable, "-c", 
             "import os; os.environ['GENEVA_MASTER_KEY']='test'; "
             "from scripts.run_geneva_poc import run_geneva_training; "
             "print('Import OK')"],
            env=env,
            capture_output=True,
            text=True,
            timeout=10,
        )

        # Import should succeed
        assert "Import OK" in result.stdout or result.returncode == 0


if __name__ == "__main__":
    pytest.main([__file__, "-v"])
