"""
Tests for mTLS Client module.
"""

import asyncio
import os
import ssl
import tempfile
from datetime import datetime, timedelta
from pathlib import Path
from unittest.mock import AsyncMock, MagicMock, Mock, patch

import pytest

from src.security.mtls_client import (CertificateInfo, MTLSClient, MTLSConfig,
                                      close_mtls_client, get_mtls_client,
                                      mtls_request)


class TestMTLSConfig:
    """Tests for MTLSConfig."""

    def test_default_config(self):
        """Test default configuration values."""
        config = MTLSConfig()

        assert config.cert_path == "/etc/certs/tls.crt"
        assert config.key_path == "/etc/certs/tls.key"
        assert config.ca_path == "/etc/certs/ca.crt"
        assert config.min_tls_version == ssl.TLSVersion.TLSv1_3
        assert config.verify_hostname is True
        assert config.rotation_enabled is True

    def test_config_from_env(self):
        """Test configuration from environment variables."""
        with patch.dict(
            os.environ,
            {
                "MTLS_CERT_PATH": "/custom/cert.pem",
                "MTLS_KEY_PATH": "/custom/key.pem",
                "MTLS_CA_PATH": "/custom/ca.pem",
                "MTLS_VERIFY_HOSTNAME": "false",
                "MTLS_ROTATION_ENABLED": "false",
            },
        ):
            config = MTLSConfig.from_env()

            assert config.cert_path == "/custom/cert.pem"
            assert config.key_path == "/custom/key.pem"
            assert config.ca_path == "/custom/ca.pem"
            assert config.verify_hostname is False
            assert config.rotation_enabled is False


class TestCertificateInfo:
    """Tests for CertificateInfo."""

    def test_is_valid_true(self):
        """Test is_valid returns True for valid certificate."""
        cert_info = CertificateInfo(
            subject="CN=test",
            issuer="CN=ca",
            not_before=datetime.utcnow() - timedelta(days=1),
            not_after=datetime.utcnow() + timedelta(days=30),
            serial_number=123456,
        )

        assert cert_info.is_valid is True

    def test_is_valid_false_expired(self):
        """Test is_valid returns False for expired certificate."""
        cert_info = CertificateInfo(
            subject="CN=test",
            issuer="CN=ca",
            not_before=datetime.utcnow() - timedelta(days=60),
            not_after=datetime.utcnow() - timedelta(days=1),
            serial_number=123456,
        )

        assert cert_info.is_valid is False

    def test_is_valid_false_not_yet_valid(self):
        """Test is_valid returns False for not-yet-valid certificate."""
        cert_info = CertificateInfo(
            subject="CN=test",
            issuer="CN=ca",
            not_before=datetime.utcnow() + timedelta(days=1),
            not_after=datetime.utcnow() + timedelta(days=30),
            serial_number=123456,
        )

        assert cert_info.is_valid is False

    def test_expires_in(self):
        """Test expires_in calculation."""
        expiry = datetime.utcnow() + timedelta(hours=48)
        cert_info = CertificateInfo(
            subject="CN=test",
            issuer="CN=ca",
            not_before=datetime.utcnow() - timedelta(days=1),
            not_after=expiry,
            serial_number=123456,
        )

        # Should be approximately 48 hours
        expires_in = cert_info.expires_in
        assert timedelta(hours=47) < expires_in < timedelta(hours=49)

    def test_needs_rotation_true(self):
        """Test needs_rotation returns True when < 24 hours remaining."""
        cert_info = CertificateInfo(
            subject="CN=test",
            issuer="CN=ca",
            not_before=datetime.utcnow() - timedelta(days=1),
            not_after=datetime.utcnow() + timedelta(hours=12),
            serial_number=123456,
        )

        assert cert_info.needs_rotation is True

    def test_needs_rotation_false(self):
        """Test needs_rotation returns False when > 24 hours remaining."""
        cert_info = CertificateInfo(
            subject="CN=test",
            issuer="CN=ca",
            not_before=datetime.utcnow() - timedelta(days=1),
            not_after=datetime.utcnow() + timedelta(days=30),
            serial_number=123456,
        )

        assert cert_info.needs_rotation is False


class TestMTLSClient:
    """Tests for MTLSClient."""

    @pytest.fixture
    def mock_config(self):
        """Create mock config."""
        return MTLSConfig(
            cert_path="/tmp/test_cert.pem",
            key_path="/tmp/test_key.pem",
            ca_path="/tmp/test_ca.pem",
            rotation_enabled=False,
        )

    @pytest.mark.asyncio
    async def test_client_initialization_no_certs(self, mock_config):
        """Test client initialization when certificates don't exist."""
        client = MTLSClient(config=mock_config)

        with patch.object(
            client, "_load_spiffe_credentials", new_callable=AsyncMock
        ) as mock_spiffe:
            mock_spiffe.side_effect = FileNotFoundError("SPIFFE socket not found")

            with pytest.raises(FileNotFoundError):
                await client._initialize()

    @pytest.mark.asyncio
    async def test_client_is_healthy_false_no_init(self):
        """Test is_healthy returns False when not initialized."""
        client = MTLSClient()

        assert client.is_healthy is False

    @pytest.mark.asyncio
    async def test_client_is_healthy_true_after_init(self):
        """Test is_healthy returns True after proper initialization."""
        client = MTLSClient()

        # Mock the certificate info
        client._cert_info = CertificateInfo(
            subject="CN=test",
            issuer="CN=ca",
            not_before=datetime.utcnow() - timedelta(days=1),
            not_after=datetime.utcnow() + timedelta(days=30),
            serial_number=123456,
        )
        client._session = Mock()

        assert client.is_healthy is True

    @pytest.mark.asyncio
    async def test_client_context_manager(self):
        """Test client as context manager."""
        with patch.object(MTLSClient, "_initialize", new_callable=AsyncMock):
            with patch.object(
                MTLSClient, "close", new_callable=AsyncMock
            ) as mock_close:
                async with MTLSClient() as client:
                    assert client is not None

                mock_close.assert_called_once()

    @pytest.mark.asyncio
    async def test_close_cancels_rotation_task(self):
        """Test that close cancels rotation task."""
        client = MTLSClient()
        client._session = AsyncMock()
        client._rotation_task = asyncio.create_task(asyncio.sleep(1000))

        await client.close()

        assert client._rotation_task.cancelled()

    @pytest.mark.asyncio
    async def test_request_initializes_if_needed(self):
        """Test that request initializes client if needed."""
        client = MTLSClient()
        client._session = None

        mock_session = AsyncMock()
        mock_session.request = AsyncMock(return_value=Mock())

        async def init_side_effect():
            client._session = mock_session

        with patch.object(client, "_initialize", new_callable=AsyncMock) as mock_init:
            mock_init.side_effect = init_side_effect

            await client.request("GET", "https://test.local/api")

            mock_init.assert_called_once()

    @pytest.mark.asyncio
    async def test_http_methods(self):
        """Test HTTP method shortcuts."""
        client = MTLSClient()
        mock_session = AsyncMock()
        client._session = mock_session

        # Test GET
        await client.get("https://test.local/api")
        mock_session.request.assert_called_with("GET", "https://test.local/api")

        # Test POST
        await client.post("https://test.local/api", json={"data": "test"})
        mock_session.request.assert_called_with(
            "POST", "https://test.local/api", json={"data": "test"}
        )

        # Test PUT
        await client.put("https://test.local/api", json={"data": "update"})
        mock_session.request.assert_called_with(
            "PUT", "https://test.local/api", json={"data": "update"}
        )

        # Test DELETE
        await client.delete("https://test.local/api")
        mock_session.request.assert_called_with("DELETE", "https://test.local/api")

    @pytest.mark.asyncio
    async def test_certificate_info_property(self):
        """Test certificate_info property."""
        client = MTLSClient()

        # No cert info initially
        assert client.certificate_info is None

        # Set cert info
        cert_info = CertificateInfo(
            subject="CN=test",
            issuer="CN=ca",
            not_before=datetime.utcnow(),
            not_after=datetime.utcnow() + timedelta(days=30),
            serial_number=123456,
            spiffe_id="spiffe://x0tta6bl4.mesh/test",
        )
        client._cert_info = cert_info

        assert client.certificate_info == cert_info
        assert client.certificate_info.spiffe_id == "spiffe://x0tta6bl4.mesh/test"


class TestGlobalClient:
    """Tests for global client functions."""

    @pytest.fixture(autouse=True)
    async def cleanup(self):
        """Cleanup global client after each test."""
        yield
        await close_mtls_client()

    @pytest.mark.asyncio
    async def test_get_mtls_client_creates_instance(self):
        """Test get_mtls_client creates singleton instance."""
        with patch.object(MTLSClient, "_initialize", new_callable=AsyncMock):
            client1 = await get_mtls_client()
            client2 = await get_mtls_client()

            assert client1 is client2

    @pytest.mark.asyncio
    async def test_close_mtls_client(self):
        """Test close_mtls_client closes and clears global client."""
        with patch.object(MTLSClient, "_initialize", new_callable=AsyncMock):
            with patch.object(
                MTLSClient, "close", new_callable=AsyncMock
            ) as mock_close:
                client = await get_mtls_client()

                await close_mtls_client()

                mock_close.assert_called_once()


class TestMTLSRequestContextManager:
    """Tests for mtls_request context manager."""

    @pytest.fixture(autouse=True)
    async def cleanup(self):
        """Cleanup global client after each test."""
        yield
        await close_mtls_client()

    @pytest.mark.asyncio
    async def test_mtls_request_context_manager(self):
        """Test mtls_request context manager."""
        mock_response = AsyncMock()
        mock_response.close = Mock()

        with patch(
            "src.security.mtls_client.get_mtls_client", new_callable=AsyncMock
        ) as mock_get_client:
            mock_client = AsyncMock()
            mock_client.request = AsyncMock(return_value=mock_response)
            mock_get_client.return_value = mock_client

            async with mtls_request(
                "https://test.local/api", method="POST", json={"data": "test"}
            ) as response:
                assert response == mock_response
                mock_client.request.assert_called_once_with(
                    "POST", "https://test.local/api", json={"data": "test"}
                )

            # Response should be closed after context
            mock_response.close.assert_called_once()


class TestCertificateRotation:
    """Tests for certificate rotation."""

    @pytest.mark.asyncio
    async def test_rotation_loop_reloads_when_needed(self):
        """Test rotation loop reloads certificates when needed."""
        client = MTLSClient(
            config=MTLSConfig(
                rotation_enabled=True, rotation_check_interval=1  # 1 second for testing
            )
        )

        # Set up cert that needs rotation
        client._cert_info = CertificateInfo(
            subject="CN=test",
            issuer="CN=ca",
            not_before=datetime.utcnow() - timedelta(days=1),
            not_after=datetime.utcnow() + timedelta(hours=12),  # < 24 hours
            serial_number=123456,
        )
        client._session = AsyncMock()

        with patch.object(
            client, "_reload_certificates", new_callable=AsyncMock
        ) as mock_reload:
            # Start rotation loop
            task = asyncio.create_task(client._rotation_loop())

            # Wait for one check
            await asyncio.sleep(1.5)

            # Cancel loop
            task.cancel()
            try:
                await task
            except asyncio.CancelledError:
                pass

            # Should have called reload
            mock_reload.assert_called()

    @pytest.mark.asyncio
    async def test_rotation_loop_skips_when_not_needed(self):
        """Test rotation loop skips reload when not needed."""
        client = MTLSClient(
            config=MTLSConfig(rotation_enabled=True, rotation_check_interval=1)
        )

        # Set up cert that doesn't need rotation
        client._cert_info = CertificateInfo(
            subject="CN=test",
            issuer="CN=ca",
            not_before=datetime.utcnow() - timedelta(days=1),
            not_after=datetime.utcnow() + timedelta(days=30),  # > 24 hours
            serial_number=123456,
        )
        client._session = AsyncMock()

        with patch.object(
            client, "_reload_certificates", new_callable=AsyncMock
        ) as mock_reload:
            task = asyncio.create_task(client._rotation_loop())

            await asyncio.sleep(1.5)

            task.cancel()
            try:
                await task
            except asyncio.CancelledError:
                pass

            # Should NOT have called reload
            mock_reload.assert_not_called()


if __name__ == "__main__":
    pytest.main([__file__, "-v"])
