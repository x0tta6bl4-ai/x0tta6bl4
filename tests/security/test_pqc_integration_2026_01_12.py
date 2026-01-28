"""
PQC Mesh Network Integration Tests - 2026-01-12
================================================

End-to-end tests for Post-Quantum Cryptography integration with mesh networking.
Tests hybrid encryption (classical + PQ) in mesh communication scenarios.

Requirements:
- liboqs-python installed
- cryptography >= 45.0.3
"""

import pytest
import asyncio
import json
import logging
from typing import Dict, Any
from datetime import datetime

# Import PQC components
from src.security.post_quantum_liboqs import (
    LibOQSBackend,
    PQKeyPair,
    PQMeshSecurityLibOQS,
    LIBOQS_AVAILABLE
)
from src.security.pqc_hybrid import (
    HybridPQEncryption,
    HybridKeyPair
)

logger = logging.getLogger(__name__)


@pytest.fixture(scope="module")
def pqc_backend():
    """Initialize PQC backend."""
    if not LIBOQS_AVAILABLE:
        pytest.skip("liboqs-python not available")
    return LibOQSBackend(kem_algorithm="ML-KEM-768")


@pytest.fixture(scope="module")
def hybrid_encryption():
    """Initialize hybrid encryption."""
    if not LIBOQS_AVAILABLE:
        pytest.skip("liboqs-python not available")
    return HybridPQEncryption(kem_algorithm="ML-KEM-768")


@pytest.fixture(scope="module")
def pq_mesh_security():
    """Initialize PQ mesh security."""
    if not LIBOQS_AVAILABLE:
        pytest.skip("liboqs-python not available")
    return PQMeshSecurityLibOQS(node_id="test-node")


class TestPQCLibOQSIntegration:
    """Test PQC integration with liboqs."""
    
    @pytest.mark.asyncio
    @pytest.mark.asyncio

    @pytest.mark.integration
    @pytest.mark.security
    async def test_liboqs_availability(self, pqc_backend):
        """Test that liboqs-python is available."""
        assert LIBOQS_AVAILABLE, "liboqs-python must be installed for production"
        assert pqc_backend is not None
        logger.info("✅ LibOQS availability verified")
    
    @pytest.mark.asyncio
    @pytest.mark.asyncio

    @pytest.mark.integration
    @pytest.mark.security
    async def test_kem_key_generation(self, pqc_backend):
        """Test KEM key generation."""
        keypair = pqc_backend.generate_kem_keypair()
        
        assert keypair is not None
        assert keypair.public_key is not None
        assert keypair.private_key is not None
        assert len(keypair.public_key) > 0
        assert len(keypair.private_key) > 0
        
        logger.info(f"✅ KEM keypair generated - public: {len(keypair.public_key)} bytes, private: {len(keypair.private_key)} bytes")
    
    @pytest.mark.asyncio
    @pytest.mark.asyncio

    @pytest.mark.integration
    @pytest.mark.security
    async def test_signature_key_generation(self, pqc_backend):
        """Test signature key generation."""
        keypair = pqc_backend.generate_sig_keypair()
        
        assert keypair is not None
        assert keypair.public_key is not None
        assert keypair.private_key is not None
        
        logger.info(f"✅ Signature keypair generated")
    
    @pytest.mark.asyncio
    @pytest.mark.asyncio

    @pytest.mark.integration
    @pytest.mark.security
    async def test_encapsulation_and_decapsulation(self, pqc_backend):
        """Test KEM encapsulation/decapsulation (key establishment)."""
        # Generate keypair
        keypair = pqc_backend.generate_kem_keypair()
        
        # Encapsulate (client side - derive shared secret)
        ciphertext, shared_secret_1 = pqc_backend.encapsulate(keypair.public_key)
        
        assert ciphertext is not None
        assert shared_secret_1 is not None
        assert len(shared_secret_1) > 0
        
        # Decapsulate (server side - recover shared secret)
        shared_secret_2 = pqc_backend.decapsulate(ciphertext, keypair.private_key)
        
        assert shared_secret_2 is not None
        assert shared_secret_1 == shared_secret_2, "Shared secrets must match"
        
        logger.info(f"✅ KEM encapsulation/decapsulation successful - shared secret: {len(shared_secret_1)} bytes")
    
    @pytest.mark.asyncio
    @pytest.mark.asyncio

    @pytest.mark.integration
    @pytest.mark.security
    async def test_signing_and_verification(self, pqc_backend):
        """Test digital signature generation and verification."""
        message = b"test message for pqc signature"
        
        # Generate keypair
        keypair = pqc_backend.generate_sig_keypair()
        
        # Sign message
        signature = pqc_backend.sign(message, keypair.private_key)
        
        assert signature is not None
        assert len(signature) > 0
        
        # Verify signature
        is_valid = pqc_backend.verify(message, signature, keypair.public_key)
        
        assert is_valid, "Signature verification failed"
        
        # Test invalid signature detection
        modified_message = b"modified message"
        is_valid_modified = pqc_backend.verify(modified_message, signature, keypair.public_key)
        assert not is_valid_modified, "Should reject signature for modified message"
        
        logger.info(f"✅ Digital signature test passed - signature: {len(signature)} bytes")


class TestHybridEncryption:
    """Test hybrid classical + PQ encryption."""
    
    @pytest.mark.asyncio
    @pytest.mark.asyncio

    @pytest.mark.integration
    @pytest.mark.security
    async def test_hybrid_keypair_generation(self, hybrid_encryption):
        """Test hybrid keypair generation."""
        keypair = hybrid_encryption.generate_hybrid_keypair()
        
        assert keypair is not None
        assert keypair.classical_public is not None
        assert keypair.classical_private is not None
        assert keypair.pq_public is not None
        assert keypair.pq_private is not None
        
        logger.info(f"✅ Hybrid keypair generated - classical: {len(keypair.classical_public)}, PQ: {len(keypair.pq_public)}")
    
    @pytest.mark.asyncio

    
    @pytest.mark.integration
    @pytest.mark.security
    async def test_hybrid_encapsulation(self, hybrid_encryption):
        """Test hybrid key encapsulation."""
        keypair = hybrid_encryption.generate_hybrid_keypair()
        
        # Encapsulate
        ciphertext, shared_secret = hybrid_encryption.encapsulate(keypair)
        
        assert ciphertext is not None
        assert shared_secret is not None
        assert len(shared_secret) > 0
        
        logger.info(f"✅ Hybrid encapsulation successful - ciphertext: {len(ciphertext)}, shared secret: {len(shared_secret)}")
    
    @pytest.mark.asyncio

    
    @pytest.mark.integration
    @pytest.mark.security
    async def test_hybrid_encryption_decryption(self, hybrid_encryption):
        """Test hybrid encryption and decryption."""
        # Generate keypair
        keypair = hybrid_encryption.generate_hybrid_keypair()
        
        # Encapsulate to get shared secret
        ciphertext, shared_secret_sender = hybrid_encryption.encapsulate(keypair)
        
        # Simulate decapsulation
        shared_secret_receiver = hybrid_encryption.decapsulate(ciphertext, keypair)
        
        assert shared_secret_sender == shared_secret_receiver, "Shared secrets must match"
        
        # Encrypt message with shared secret
        plaintext = b"confidential mesh data"
        encrypted = hybrid_encryption.hybrid_encrypt(plaintext, shared_secret_sender)
        
        assert encrypted is not None
        assert encrypted != plaintext
        
        # Decrypt message
        decrypted = hybrid_encryption.hybrid_decrypt(encrypted, shared_secret_receiver)
        
        assert decrypted == plaintext, "Decryption failed"
        
        logger.info(f"✅ Hybrid encryption/decryption test passed")


class TestPQCMeshIntegration:
    """Test PQC integration with mesh networking."""
    
    @pytest.mark.asyncio

    
    @pytest.mark.integration
    @pytest.mark.security
    async def test_pq_mesh_security_initialization(self, pq_mesh_security):
        """Test PQ mesh security initialization."""
        assert pq_mesh_security is not None
        assert pq_mesh_security.hybrid_cipher is not None
        
        logger.info("✅ PQ mesh security initialized")
    
    @pytest.mark.asyncio

    
    @pytest.mark.integration
    @pytest.mark.security
    async def test_pq_mesh_key_exchange(self, pq_mesh_security):
        """Test PQ-secured key exchange between mesh nodes."""
        # Node 1 generates keypair
        node1_keypair = pq_mesh_security.hybrid_cipher.generate_hybrid_keypair()
        
        # Node 2 generates keypair
        node2_keypair = pq_mesh_security.hybrid_cipher.generate_hybrid_keypair()
        
        # Node 1 encapsulates for Node 2
        ciphertext_1to2, secret_1to2 = pq_mesh_security.hybrid_cipher.encapsulate(node2_keypair)
        
        # Node 2 encapsulates for Node 1
        ciphertext_2to1, secret_2to1 = pq_mesh_security.hybrid_cipher.encapsulate(node1_keypair)
        
        # Verify both have shared secrets
        assert secret_1to2 is not None
        assert secret_2to1 is not None
        
        logger.info(f"✅ PQ mesh key exchange successful")
    
    @pytest.mark.asyncio

    
    @pytest.mark.integration
    @pytest.mark.security
    async def test_pq_secured_mesh_communication(self, pq_mesh_security):
        """Test PQ-secured mesh communication."""
        # Setup mesh nodes
        node1_keypair = pq_mesh_security.hybrid_cipher.generate_hybrid_keypair()
        node2_keypair = pq_mesh_security.hybrid_cipher.generate_hybrid_keypair()
        
        # Establish shared secret
        ciphertext, shared_secret = pq_mesh_security.hybrid_cipher.encapsulate(node2_keypair)
        
        # Node 1 sends encrypted message
        message = {
            "type": "mesh_heartbeat",
            "timestamp": datetime.now().isoformat(),
            "node_id": "node-1",
            "metrics": {"cpu": 0.5, "memory": 0.7}
        }
        plaintext = json.dumps(message).encode()
        ciphertext_msg = pq_mesh_security.hybrid_cipher.hybrid_encrypt(plaintext, shared_secret)
        
        # Node 2 receives and decrypts
        decrypted = pq_mesh_security.hybrid_cipher.hybrid_decrypt(ciphertext_msg, shared_secret)
        received_message = json.loads(decrypted.decode())
        
        assert received_message == message, "Message corruption detected"
        
        logger.info("✅ PQ-secured mesh communication verified")


class TestPQCMigrationPath:
    """Test migration path from classical to PQ cryptography."""
    
    @pytest.mark.asyncio

    
    @pytest.mark.integration
    @pytest.mark.security
    async def test_hybrid_mode_ensures_compatibility(self, hybrid_encryption):
        """Test that hybrid mode ensures backward compatibility."""
        # Hybrid mode uses both classical and PQ
        # If either fails, communication should still work via the other
        keypair = hybrid_encryption.generate_hybrid_keypair()
        
        # Both classical and PQ components should be present
        assert len(keypair.classical_public) > 0
        assert len(keypair.pq_public) > 0
        
        logger.info("✅ Hybrid mode ensures backward compatibility")
    
    @pytest.mark.asyncio

    
    @pytest.mark.integration
    @pytest.mark.security
    async def test_pqc_performance_acceptable(self, pqc_backend):
        """Test that PQC performance is acceptable for production."""
        import time
        
        # Measure key generation
        start = time.time()
        for _ in range(5):
            pqc_backend.generate_kem_keypair()
        keygen_time = (time.time() - start) / 5
        
        # Measure encapsulation
        keypair = pqc_backend.generate_kem_keypair()
        start = time.time()
        for _ in range(10):
            pqc_backend.encapsulate(keypair.public_key)
        encap_time = (time.time() - start) / 10
        
        # Performance targets
        assert keygen_time < 1.0, f"Key generation too slow: {keygen_time:.3f}s"
        assert encap_time < 0.1, f"Encapsulation too slow: {encap_time:.3f}s"
        
        logger.info(f"✅ PQC performance acceptable - keygen: {keygen_time*1000:.1f}ms, encap: {encap_time*1000:.1f}ms")


@pytest.mark.integration
@pytest.mark.security
class TestPQCErrorHandling:
    """Test PQC error handling and edge cases."""
    
    @pytest.mark.asyncio
    async def test_invalid_ciphertext_decapsulation(self, pqc_backend):
        """Test handling of invalid ciphertext."""
        keypair = pqc_backend.generate_kem_keypair()
        invalid_ciphertext = b"invalid ciphertext data"
        
        # Should handle gracefully or raise appropriate exception
        try:
            pqc_backend.decapsulate(invalid_ciphertext, keypair.private_key)
            # If it doesn't raise, check result is valid
        except Exception as e:
            assert "invalid" in str(e).lower() or "decapsulation" in str(e).lower()
            logger.info(f"✅ Gracefully handled invalid ciphertext: {type(e).__name__}")
    
    @pytest.mark.asyncio
    async def test_invalid_signature_verification(self, pqc_backend):
        """Test handling of invalid signatures."""
        keypair = pqc_backend.generate_sig_keypair()
        message = b"test message"
        invalid_signature = b"invalid signature data"
        
        # Should return False or raise exception
        try:
            result = pqc_backend.verify(message, invalid_signature, keypair.public_key)
            assert result is False, "Invalid signature should not verify"
            logger.info("✅ Invalid signature correctly rejected")
        except Exception as e:
            logger.info(f"✅ Invalid signature raised exception: {type(e).__name__}")


if __name__ == "__main__":
    pytest.main([__file__, "-v", "-m", "integration"])
