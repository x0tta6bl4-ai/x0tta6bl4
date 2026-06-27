"""
Unit tests for Agent Integrity Verification.
"""

import pytest
import re
from unittest.mock import patch, AsyncMock
from src.network.mesh_node_complete import CompleteMeshNode, MeshConfig
from src.network.integrity import calculate_binary_hash, verify_integrity

class TestAgentIntegrity:
    @pytest.mark.asyncio
    async def test_calculate_binary_hash_returns_sha256(self):
        h = calculate_binary_hash()
        assert h.startswith("sha256:")
        assert len(h) == 7 + 64

    def test_calculate_binary_hash_fallback_is_sha256_not_placeholder(self, monkeypatch):
        import src.network.integrity as integrity

        monkeypatch.setattr(
            integrity.sys.modules["__main__"],
            "__file__",
            "/missing/x0tta-agent.py",
            raising=False,
        )
        monkeypatch.setattr(integrity.sys, "executable", "/missing/python")

        h = calculate_binary_hash()

        assert re.fullmatch(r"sha256:[0-9a-f]{64}", h)
        assert h != "sha256:abc1234567890"

    @patch("src.network.integrity.httpx")
    @pytest.mark.asyncio
    async def test_verify_integrity_success(self, mock_httpx):
        # Mock successful SBOM fetch and verification report
        mock_client = AsyncMock()
        mock_client.__aenter__.return_value = mock_client
        mock_client.get.return_value = AsyncMock(status_code=200, json=lambda: {
            "checksum_sha256": calculate_binary_hash(),
            "pqc_signature": "mock-sig"
        })
        mock_client.post.return_value = AsyncMock(status_code=200)
        mock_httpx.AsyncClient.return_value = mock_client

        result = await verify_integrity("test-node", "v3.4.0-alpha")
        assert result is True
        mock_client.get.assert_called_once()
        # Verify it reported success
        assert mock_client.post.call_count == 1

    @patch("src.network.integrity.httpx")
    @pytest.mark.asyncio
    async def test_verify_integrity_requires_pqc_signature_when_configured(self, mock_httpx, monkeypatch):
        monkeypatch.setenv("X0TTA6BL4_REQUIRE_SBOM_PQC_SIGNATURE", "true")
        mock_client = AsyncMock()
        mock_client.__aenter__.return_value = mock_client
        mock_client.get.return_value = AsyncMock(status_code=200, json=lambda: {
            "checksum_sha256": calculate_binary_hash(),
            "pqc_signature": "00",
        })
        mock_client.post.return_value = AsyncMock(status_code=200)
        mock_httpx.AsyncClient.return_value = mock_client

        result = await verify_integrity("test-node", "v3.4.0-alpha")

        assert result is False
        mock_client.post.assert_not_called()

    @patch("src.network.integrity.httpx")
    @pytest.mark.asyncio
    async def test_verify_integrity_remote_error_fails_closed_by_default(self, mock_httpx, monkeypatch):
        monkeypatch.delenv("X0TTA6BL4_INTEGRITY_FAIL_OPEN", raising=False)
        mock_httpx.AsyncClient.side_effect = RuntimeError("supply-chain unavailable")

        result = await verify_integrity("test-node", "v3.4.0-alpha")

        assert result is False

    @patch("src.network.integrity.httpx")
    @pytest.mark.asyncio
    async def test_verify_integrity_mismatch(self, mock_httpx):
        # Mock checksum mismatch
        mock_client = AsyncMock()
        mock_client.__aenter__.return_value = mock_client
        mock_client.get.return_value = AsyncMock(status_code=200, json=lambda: {
            "checksum_sha256": "sha256:wrong-hash",
            "pqc_signature": "mock-sig"
        })
        mock_client.post.return_value = AsyncMock(status_code=200)
        mock_httpx.AsyncClient.return_value = mock_client

        result = await verify_integrity("test-node", "v3.4.0-alpha")
        assert result is False
        # Verify it reported mismatch
        mock_client.post.assert_called_once()

    @patch("src.network.mesh_node_complete.verify_integrity")
    @pytest.mark.asyncio
    async def test_node_start_integrity_failure_strict(self, mock_verify):
        mock_verify.return_value = False
        config = MeshConfig(node_id="strict-node", strict_integrity=True)
        node = CompleteMeshNode(config)
        
        with pytest.raises(RuntimeError, match="Integrity check failed"):
            await node.start()

        @patch("src.network.mesh_node_complete.verify_integrity")
        @pytest.mark.asyncio
        async def test_node_start_integrity_failure_non_strict(self, mock_verify):
            mock_verify.return_value = False
            config = MeshConfig(node_id="lax-node", strict_integrity=False)
            node = CompleteMeshNode(config)
        
            # Should not raise exception
            with patch("src.network.mesh_node_complete.ShapedUDPTransport") as mock_transport, \
                 patch("src.network.mesh_node_complete.MeshRouter"), \
                 patch("src.network.mesh_node_complete.MeshDiscovery"):
                
                mock_transport.return_value.start = AsyncMock()
                mock_transport.return_value.stop = AsyncMock()
                
                await node.start()
                await node.stop()
