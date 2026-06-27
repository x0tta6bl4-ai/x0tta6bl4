"""
Tests for liboqs integration (real PQC).

Проверяет, что liboqs правильно интегрирован и работает.
"""

import sys
from pathlib import Path

import pytest

# Add src to path
sys.path.insert(0, str(Path(__file__).parent.parent.parent.parent / "src"))

try:
    from security.pqc import (LIBOQS_AVAILABLE,
                              HybridPQEncryption,
                              LibOQSBackend,
                              PQMeshSecurityLibOQS)

    LIBOQS_IMPORTED = True
except ImportError:
    LIBOQS_IMPORTED = False


@pytest.mark.skipif(not LIBOQS_AVAILABLE, reason="liboqs-python not installed")
class TestLibOQSBackend:
    """Tests for LibOQSBackend."""

    def test_kem_keypair_generation(self):
        """Test KEM keypair generation."""
        backend = LibOQSBackend()
        kp = backend.generate_kem_keypair()
        assert kp is not None
        assert len(kp.public_key) > 0
        assert len(kp.private_key) > 0

    def test_kem_encapsulation(self):
        """Test KEM encapsulation."""
        backend = LibOQSBackend()
        kp = backend.generate_kem_keypair()
        ss, ct = backend.kem_encapsulate(kp.public_key)
        assert len(ss) > 0
        assert len(ct) > 0

    def test_kem_decapsulation(self):
        """Test KEM decapsulation."""
        backend = LibOQSBackend()
        kp = backend.generate_kem_keypair()
        ss_enc, ct = backend.kem_encapsulate(kp.public_key)
        ss_dec = backend.kem_decapsulate(kp.private_key, ct)
        assert ss_enc == ss_dec


@pytest.mark.skipif(not LIBOQS_AVAILABLE, reason="liboqs-python not installed")
class TestHybridPQEncryption:
    """Tests for HybridPQEncryption."""

    def test_hybrid_encryption_available(self):
        """Test that hybrid encryption is available."""
        assert LIBOQS_AVAILABLE
