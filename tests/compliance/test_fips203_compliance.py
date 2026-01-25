"""
FIPS 203/204 Compliance Tests

Проверяет соответствие NIST FIPS 203 (ML-KEM) и FIPS 204 (ML-DSA) стандартам.

FIPS 203 (ML-KEM):
- ML-KEM-512 (NIST Level 1)
- ML-KEM-768 (NIST Level 3) - recommended
- ML-KEM-1024 (NIST Level 5)

FIPS 204 (ML-DSA):
- ML-DSA-44 (NIST Level 2)
- ML-DSA-65 (NIST Level 3) - recommended
- ML-DSA-87 (NIST Level 5)

Standard finalized: August 2024
"""
import pytest
import sys
from pathlib import Path

# Add src to path
sys.path.insert(0, str(Path(__file__).parent.parent.parent.parent / "src"))

try:
    from oqs import KeyEncapsulation, Signature
    from security.post_quantum_liboqs import (
        LibOQSBackend,
        PQAlgorithm,
        LIBOQS_AVAILABLE
    )
    LIBOQS_IMPORTED = True
except ImportError:
    LIBOQS_IMPORTED = False
    LIBOQS_AVAILABLE = False


@pytest.mark.skipif(not LIBOQS_AVAILABLE, reason="liboqs-python not installed")
class TestFIPS203Compliance:
    """Tests for FIPS 203 (ML-KEM) compliance."""
    
    def test_ml_kem_768_supported(self):
        """Test that ML-KEM-768 (FIPS 203 Level 3) is supported."""
        try:
            # Check if algorithm is available
            if hasattr(KeyEncapsulation, 'get_enabled_kem_mechanisms'):
                mechanisms = KeyEncapsulation.get_enabled_kem_mechanisms()
                assert "ML-KEM-768" in mechanisms or "Kyber768" in mechanisms, \
                    "ML-KEM-768 not supported by liboqs"
        except AttributeError:
            # If method doesn't exist, try to use it directly
            pass
        
        # Try to create KEM instance
        kem = KeyEncapsulation("ML-KEM-768")
        assert kem is not None
    
    def test_ml_kem_768_key_generation(self):
        """Test ML-KEM-768 key generation (FIPS 203)."""
        backend = LibOQSBackend(kem_algorithm="ML-KEM-768")
        keypair = backend.generate_kem_keypair()
        
        assert keypair is not None
        assert keypair.public_key is not None
        assert keypair.private_key is not None
        assert len(keypair.public_key) > 0
        assert len(keypair.private_key) > 0
        assert keypair.algorithm == PQAlgorithm.ML_KEM_768
        
        # FIPS 203 ML-KEM-768 key sizes (approximate)
        # Public key: ~1184 bytes
        # Private key: ~2400 bytes
        assert len(keypair.public_key) >= 1000, "Public key too small"
        assert len(keypair.private_key) >= 2000, "Private key too small"
    
    def test_ml_kem_768_encapsulation(self):
        """Test ML-KEM-768 encapsulation/decapsulation."""
        backend = LibOQSBackend(kem_algorithm="ML-KEM-768")
        
        # Generate keypair
        keypair = backend.generate_kem_keypair()
        
        # Encapsulate
        shared_secret, ciphertext = backend.kem_encapsulate(keypair.public_key)
        
        assert shared_secret is not None
        assert ciphertext is not None
        assert len(shared_secret) > 0
        assert len(ciphertext) > 0
        
        # FIPS 203 ML-KEM-768 ciphertext size: ~1088 bytes
        assert len(ciphertext) >= 1000, "Ciphertext too small"
        
        # Decapsulate
        recovered_secret = backend.kem_decapsulate(ciphertext, keypair.private_key)
        
        # Secrets should match
        assert shared_secret == recovered_secret, "Decapsulation failed"
    
    def test_ml_kem_768_algorithm_name(self):
        """Test that ML-KEM-768 uses correct NIST name."""
        backend = LibOQSBackend(kem_algorithm="ML-KEM-768")
        assert backend.kem_algorithm == "ML-KEM-768"
        
        # Test legacy name compatibility
        backend_legacy = LibOQSBackend(kem_algorithm="Kyber768")
        # Should work (legacy name support)
        keypair = backend_legacy.generate_kem_keypair()
        assert keypair is not None


@pytest.mark.skipif(not LIBOQS_AVAILABLE, reason="liboqs-python not installed")
class TestFIPS204Compliance:
    """Tests for FIPS 204 (ML-DSA) compliance."""
    
    def test_ml_dsa_65_supported(self):
        """Test that ML-DSA-65 (FIPS 204 Level 3) is supported."""
        try:
            # Check if algorithm is available
            if hasattr(Signature, 'get_enabled_sig_mechanisms'):
                mechanisms = Signature.get_enabled_sig_mechanisms()
                assert "ML-DSA-65" in mechanisms or "Dilithium3" in mechanisms, \
                    "ML-DSA-65 not supported by liboqs"
        except AttributeError:
            # If method doesn't exist, try to use it directly
            pass
        
        # Try to create Signature instance
        sig = Signature("ML-DSA-65")
        assert sig is not None
    
    def test_ml_dsa_65_key_generation(self):
        """Test ML-DSA-65 key generation (FIPS 204)."""
        backend = LibOQSBackend(sig_algorithm="ML-DSA-65")
        keypair = backend.generate_signature_keypair()
        
        assert keypair is not None
        assert keypair.public_key is not None
        assert keypair.private_key is not None
        assert len(keypair.public_key) > 0
        assert len(keypair.private_key) > 0
        assert keypair.algorithm == PQAlgorithm.ML_DSA_65
        
        # FIPS 204 ML-DSA-65 key sizes (approximate)
        # Public key: ~1952 bytes
        # Private key: ~4000 bytes
        assert len(keypair.public_key) >= 1500, "Public key too small"
        assert len(keypair.private_key) >= 3000, "Private key too small"
    
    def test_ml_dsa_65_sign_verify(self):
        """Test ML-DSA-65 signature generation and verification (FIPS 204)."""
        backend = LibOQSBackend(sig_algorithm="ML-DSA-65")
        
        # Generate keypair
        keypair = backend.generate_signature_keypair()
        
        # Sign message
        message = b"FIPS 204 ML-DSA-65 test message"
        signature = backend.sign(message, keypair.private_key)
        
        assert signature is not None
        assert len(signature) > 0
        
        # FIPS 204 ML-DSA-65 signature size: ~3293 bytes
        assert len(signature) >= 3000, "Signature too small"
        
        # Verify signature
        is_valid = backend.verify(message, signature, keypair.public_key)
        assert is_valid, "Signature verification failed"
        
        # Verify with wrong message (should fail)
        wrong_message = b"Wrong message"
        is_invalid = backend.verify(wrong_message, signature, keypair.public_key)
        assert not is_invalid, "Signature verification should fail for wrong message"
    
    def test_ml_dsa_65_algorithm_name(self):
        """Test that ML-DSA-65 uses correct NIST name."""
        backend = LibOQSBackend(sig_algorithm="ML-DSA-65")
        assert backend.sig_algorithm == "ML-DSA-65"
        
        # Test legacy name compatibility
        backend_legacy = LibOQSBackend(sig_algorithm="Dilithium3")
        # Should work (legacy name support)
        keypair = backend_legacy.generate_signature_keypair()
        assert keypair is not None


@pytest.mark.skipif(not LIBOQS_AVAILABLE, reason="liboqs-python not installed")
class TestFIPS203204Integration:
    """Integration tests for FIPS 203/204 compliance."""
    
    def test_default_algorithms_comply(self):
        """Test that default algorithms are FIPS 203/204 compliant."""
        backend = LibOQSBackend()
        
        # Default should be ML-KEM-768 and ML-DSA-65
        assert backend.kem_algorithm == "ML-KEM-768", \
            "Default KEM algorithm should be ML-KEM-768 (FIPS 203)"
        assert backend.sig_algorithm == "ML-DSA-65", \
            "Default signature algorithm should be ML-DSA-65 (FIPS 204)"
    
    def test_fips_compliant_workflow(self):
        """Test complete FIPS 203/204 compliant workflow."""
        # Initialize with FIPS 203/204 algorithms
        backend = LibOQSBackend(
            kem_algorithm="ML-KEM-768",
            sig_algorithm="ML-DSA-65"
        )
        
        # Generate KEM keypair (FIPS 203)
        kem_keypair = backend.generate_kem_keypair()
        assert kem_keypair.algorithm == PQAlgorithm.ML_KEM_768
        
        # Generate signature keypair (FIPS 204)
        sig_keypair = backend.generate_signature_keypair()
        assert sig_keypair.algorithm == PQAlgorithm.ML_DSA_65
        
        # Test KEM workflow
        shared_secret, ciphertext = backend.kem_encapsulate(kem_keypair.public_key)
        recovered_secret = backend.kem_decapsulate(ciphertext, kem_keypair.private_key)
        assert shared_secret == recovered_secret
        
        # Test signature workflow
        message = b"FIPS 203/204 compliant message"
        signature = backend.sign(message, sig_keypair.private_key)
        is_valid = backend.verify(message, signature, sig_keypair.public_key)
        assert is_valid


@pytest.mark.skipif(not LIBOQS_AVAILABLE, reason="liboqs-python not installed")
class TestLibOQSVersion:
    """Tests to verify liboqs version compatibility."""
    
    def test_liboqs_version_info(self):
        """Test that we can get liboqs version information."""
        try:
            import oqs
            # Try to get version if available
            if hasattr(oqs, '__version__'):
                version = oqs.__version__
                print(f"liboqs-python version: {version}")
                # Version should be >= 0.14.1 (as per requirements.txt)
                assert version is not None
        except AttributeError:
            # Version info not available, but that's OK
            pass
    
    def test_algorithm_availability(self):
        """Test that required algorithms are available."""
        # Try to create instances of required algorithms
        try:
            kem = KeyEncapsulation("ML-KEM-768")
            assert kem is not None
        except Exception as e:
            # If ML-KEM-768 not available, try legacy name
            try:
                kem = KeyEncapsulation("Kyber768")
                assert kem is not None
                pytest.skip("ML-KEM-768 not available, using legacy Kyber768")
            except Exception:
                pytest.fail(f"Neither ML-KEM-768 nor Kyber768 available: {e}")
        
        try:
            sig = Signature("ML-DSA-65")
            assert sig is not None
        except Exception as e:
            # If ML-DSA-65 not available, try legacy name
            try:
                sig = Signature("Dilithium3")
                assert sig is not None
                pytest.skip("ML-DSA-65 not available, using legacy Dilithium3")
            except Exception:
                pytest.fail(f"Neither ML-DSA-65 nor Dilithium3 available: {e}")

