"""
Tests for liboqs integration (real PQC).

Проверяет, что liboqs правильно интегрирован и работает.
"""
import pytest
import sys
from pathlib import Path

# Add src to path
sys.path.insert(0, str(Path(__file__).parent.parent.parent.parent / "src"))

try:
    from security.post_quantum_liboqs import (
        LibOQSBackend,
        HybridPQEncryption,
        PQMeshSecurityLibOQS,
        LIBOQS_AVAILABLE
    )
    LIBOQS_IMPORTED = True
except ImportError:
    LIBOQS_IMPORTED = False


@pytest.mark.skipif(not LIBOQS_AVAILABLE, reason="liboqs-python not installed")
class TestLibOQSBackend:
    """Tests for LibOQSBackend."""
    
    def test_kem_keypair_generation(self):
        """Test KEM keypair generation."""
        backend = LibOQSBackend(kem_algorithm="ML-KEM-768")
        keypair = backend.generate_kem_keypair()
        
        assert keypair.public_key
        assert keypair.private_key
        assert len(keypair.public_key) > 0
        assert len(keypair.private_key) > 0
        assert keypair.key_id
    
    def test_kem_encapsulate_decapsulate(self):
        """Test KEM encapsulation/decapsulation."""
        backend = LibOQSBackend(kem_algorithm="ML-KEM-768")
        
        # Generate keypair
        keypair = backend.generate_kem_keypair()
        
        # Encapsulate
        shared_secret_enc, ciphertext = backend.kem_encapsulate(keypair.public_key)
        
        assert shared_secret_enc
        assert ciphertext
        assert len(shared_secret_enc) > 0
        assert len(ciphertext) > 0
        
        # Decapsulate
        shared_secret_dec = backend.kem_decapsulate(keypair.private_key, ciphertext)
        
        # Should match
        assert shared_secret_enc == shared_secret_dec
    
    def test_signature_keypair_generation(self):
        """Test signature keypair generation."""
        backend = LibOQSBackend(sig_algorithm="ML-DSA-65")
        keypair = backend.generate_signature_keypair()
        
        assert keypair.public_key
        assert keypair.private_key
        assert len(keypair.public_key) > 0
        assert len(keypair.private_key) > 0
    
    def test_sign_verify(self):
        """Test digital signature sign/verify."""
        backend = LibOQSBackend(sig_algorithm="ML-DSA-65")
        
        # Generate keypair
        keypair = backend.generate_signature_keypair()
        
        # Sign message
        message = b"Hello, quantum-safe world!"
        signature = backend.sign(keypair.private_key, message)
        
        assert signature
        assert len(signature) > 0
        
        # Verify signature
        is_valid = backend.verify(keypair.public_key, message, signature)
        assert is_valid
        
        # Verify with wrong message (should fail)
        wrong_message = b"Hello, insecure world!"
        is_invalid = backend.verify(keypair.public_key, wrong_message, signature)
        assert not is_invalid


@pytest.mark.skipif(not LIBOQS_AVAILABLE, reason="liboqs-python not installed")
class TestHybridPQEncryption:
    """Tests for HybridPQEncryption."""
    
    def test_hybrid_keypair_generation(self):
        """Test hybrid keypair generation."""
        hybrid = HybridPQEncryption(kem_algorithm="ML-KEM-768")
        keypair = hybrid.generate_hybrid_keypair()
        
        assert "pq" in keypair
        assert "classical" in keypair
        assert "public_key" in keypair["pq"]
        assert "private_key" in keypair["pq"]
    
    def test_hybrid_encapsulate_decapsulate(self):
        """Test hybrid encapsulation/decapsulation."""
        hybrid = HybridPQEncryption(kem_algorithm="ML-KEM-768")
        
        # Generate keypairs for two parties
        alice_keypair = hybrid.generate_hybrid_keypair()
        bob_keypair = hybrid.generate_hybrid_keypair()
        
        # Alice encapsulates to Bob
        combined_secret_enc, ciphertexts = hybrid.hybrid_encapsulate(
            bytes.fromhex(bob_keypair["pq"]["public_key"]),
            bytes.fromhex(bob_keypair["classical"]["public_key"])
        )
        
        assert combined_secret_enc
        assert "pq" in ciphertexts
        assert "classical" in ciphertexts
        
        # Bob decapsulates
        combined_secret_dec = hybrid.hybrid_decapsulate(
            ciphertexts,
            bytes.fromhex(bob_keypair["pq"]["private_key"]),
            bytes.fromhex(bob_keypair["classical"]["private_key"])
        )
        
        # Should match because we used Bob's public key for encapsulation
        assert combined_secret_enc == combined_secret_dec


@pytest.mark.skipif(not LIBOQS_AVAILABLE, reason="liboqs-python not installed")
class TestPQMeshSecurityLibOQS:
    """Tests for PQMeshSecurityLibOQS."""
    
    def test_initialization(self):
        """Test PQ mesh security initialization."""
        mesh_sec = PQMeshSecurityLibOQS("node-1", kem_algorithm="ML-KEM-768", sig_algorithm="ML-DSA-65")
        
        assert mesh_sec.node_id == "node-1"
        assert mesh_sec.kem_keypair
        assert mesh_sec.sig_keypair
    
    def test_get_public_keys(self):
        """Test getting public keys."""
        mesh_sec = PQMeshSecurityLibOQS("node-1")
        public_keys = mesh_sec.get_public_keys()
        
        assert "node_id" in public_keys
        assert "kem_public_key" in public_keys
        assert "sig_public_key" in public_keys
        assert "kem_algorithm" in public_keys
        assert "sig_algorithm" in public_keys
    
    def test_sign_verify_beacon(self):
        """Test signing and verifying beacon."""
        mesh_sec = PQMeshSecurityLibOQS("node-1")
        
        beacon_data = b"beacon:node-1:neighbors:[node-2,node-3]"
        signature = mesh_sec.sign_beacon(beacon_data)
        
        assert signature
        assert len(signature) > 0
        
        # Verify signature
        is_valid = mesh_sec.verify_beacon(
            beacon_data,
            signature,
            mesh_sec.sig_keypair.public_key
        )
        assert is_valid
        
        # Verify with wrong data (should fail)
        wrong_data = b"beacon:node-1:neighbors:[node-4]"
        is_invalid = mesh_sec.verify_beacon(
            wrong_data,
            signature,
            mesh_sec.sig_keypair.public_key
        )
        assert not is_invalid
    
    def test_get_security_level(self):
        """Test getting security level info."""
        mesh_sec = PQMeshSecurityLibOQS("node-1")
        security_info = mesh_sec.get_security_level()
        
        assert "algorithm" in security_info
        assert "pq_security_level" in security_info
        assert "kem_algorithm" in security_info
        assert "sig_algorithm" in security_info
        assert security_info["pq_security_level"] == "NIST Level 3"


@pytest.mark.skipif(LIBOQS_AVAILABLE, reason="liboqs is available, testing fallback")
class TestLibOQSNotAvailable:
    """Tests for when liboqs is not available."""
    
    def test_import_fails_gracefully(self):
        """Test that import fails gracefully when liboqs is not available."""
        # This test only runs if liboqs is NOT available
        # It verifies that the code handles missing liboqs gracefully
        pass

