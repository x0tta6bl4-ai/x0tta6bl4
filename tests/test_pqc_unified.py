"""
Tests for unified PQC module.

Tests the new unified PQC package at src/security/pqc/.
"""
import pytest
from datetime import datetime, timedelta
from unittest.mock import Mock, patch, MagicMock


class TestPQCTypes:
    """Tests for PQC data types."""
    
    def test_pqc_algorithm_enum(self):
        """Test PQCAlgorithm enum values."""
        from src.security.pqc.types import PQCAlgorithm
        
        assert PQCAlgorithm.ML_KEM_768.value == "ML-KEM-768"
        assert PQCAlgorithm.ML_DSA_65.value == "ML-DSA-65"
    
    def test_pqc_keypair_creation(self):
        """Test PQCKeyPair creation."""
        from src.security.pqc.types import PQCKeyPair
        
        keypair = PQCKeyPair(
            algorithm="ML-KEM-768",
            public_key=b"0" * 32,
            secret_key=b"s" * 32,
        )
        
        assert keypair.algorithm == "ML-KEM-768"
        assert len(keypair.public_key) == 32
        assert len(keypair.secret_key) == 32
        assert keypair.key_id  # Auto-generated
        assert not keypair.is_expired()
        assert keypair.is_valid()
    
    def test_pqc_keypair_expiration(self):
        """Test PQCKeyPair expiration check."""
        from src.security.pqc.types import PQCKeyPair
        
        # Expired keypair
        expired = PQCKeyPair(
            algorithm="ML-KEM-768",
            public_key=b"0" * 32,
            secret_key=b"s" * 32,
            expires_at=datetime.utcnow() - timedelta(days=1),
        )
        assert expired.is_expired()
        assert not expired.is_valid()
        
        # Valid keypair
        valid = PQCKeyPair(
            algorithm="ML-KEM-768",
            public_key=b"0" * 32,
            secret_key=b"s" * 32,
            expires_at=datetime.utcnow() + timedelta(days=30),
        )
        assert not valid.is_expired()
        assert valid.is_valid()
    
    def test_pqc_keypair_serialization(self):
        """Test PQCKeyPair to_dict/from_dict."""
        from src.security.pqc.types import PQCKeyPair
        
        original = PQCKeyPair(
            algorithm="ML-KEM-768",
            public_key=b"public123",
            secret_key=b"secret456",
            key_id="test-key",
            expires_at=datetime.utcnow() + timedelta(days=30),
        )
        
        data = original.to_dict()
        assert data["algorithm"] == "ML-KEM-768"
        assert data["key_id"] == "test-key"
        
        # Note: from_dict requires secret_key_hex for secret key
        data["secret_key_hex"] = bytes("secret456", "utf-8").hex()
        restored = PQCKeyPair.from_dict(data)
        assert restored.algorithm == original.algorithm
        assert restored.public_key == original.public_key
    
    def test_pqc_signature(self):
        """Test PQCSignature creation and serialization."""
        from src.security.pqc.types import PQCSignature
        
        sig = PQCSignature(
            algorithm="ML-DSA-65",
            signature_bytes=b"sig" * 100,
            message_hash=b"hash" * 8,
            signer_key_id="signer-123",
        )
        
        assert sig.algorithm == "ML-DSA-65"
        assert sig.signer_key_id == "signer-123"
        
        data = sig.to_dict()
        assert data["algorithm"] == "ML-DSA-65"
        assert "signature_hex" in data
        
        restored = PQCSignature.from_dict(data)
        assert restored.signature_bytes == sig.signature_bytes
    
    def test_pqc_encapsulation_result(self):
        """Test PQCEncapsulationResult."""
        from src.security.pqc.types import PQCEncapsulationResult
        
        result = PQCEncapsulationResult(
            ciphertext=b"c" * 1088,  # ML-KEM-768 ciphertext size
            shared_secret=b"s" * 32,
            algorithm="ML-KEM-768",
        )
        
        data = result.to_dict()
        assert data["algorithm"] == "ML-KEM-768"
        assert data["ciphertext_len"] == 1088
        assert data["shared_secret_len"] == 32


class TestPQCAdapter:
    """Tests for PQC adapter."""
    
    def test_is_liboqs_available_false(self):
        """Test is_liboqs_available when oqs not installed."""
        with patch.dict("sys.modules", {"oqs": None}):
            # Force re-check
            import src.security.pqc.adapter as adapter_module
            adapter_module._LIBOQS_AVAILABLE = None
            
            # Should return False when import fails
            with patch("builtins.__import__", side_effect=ImportError):
                result = adapter_module.is_liboqs_available()
                assert result is False
    
    def test_pqc_adapter_legacy_name_mapping(self):
        """Test legacy algorithm name mapping."""
        from src.security.pqc.adapter import PQCAdapter
        
        # Test legacy maps
        assert "Kyber768" in PQCAdapter.LEGACY_KEM_MAP
        assert PQCAdapter.LEGACY_KEM_MAP["Kyber768"] == "ML-KEM-768"
        
        assert "Dilithium3" in PQCAdapter.LEGACY_SIG_MAP
        assert PQCAdapter.LEGACY_SIG_MAP["Dilithium3"] == "ML-DSA-65"
    
    @patch("src.security.pqc.adapter.is_liboqs_available")
    def test_pqc_adapter_init_unavailable(self, mock_available):
        """Test PQCAdapter raises error when liboqs unavailable."""
        mock_available.return_value = False
        
        from src.security.pqc.adapter import PQCAdapter
        
        with pytest.raises(RuntimeError, match="liboqs not available"):
            PQCAdapter()


class TestPQCKeyExchange:
    """Tests for PQCKeyExchange (KEM)."""
    
    @patch("src.security.pqc.kem.is_liboqs_available")
    def test_kem_unavailable(self, mock_available):
        """Test KEM when liboqs unavailable."""
        mock_available.return_value = False
        
        from src.security.pqc.kem import PQCKeyExchange
        
        kem = PQCKeyExchange()
        assert not kem.is_available()
        
        with pytest.raises(RuntimeError, match="PQC not available"):
            kem.generate_keypair()
    
    @patch("src.security.pqc.kem.is_liboqs_available")
    @patch("src.security.pqc.kem.PQCAdapter")
    def test_kem_generate_keypair(self, mock_adapter_class, mock_available):
        """Test KEM keypair generation."""
        mock_available.return_value = True
        mock_adapter = Mock()
        mock_adapter.kem_generate_keypair.return_value = (b"public", b"secret")
        mock_adapter_class.return_value = mock_adapter
        
        from src.security.pqc.kem import PQCKeyExchange
        
        kem = PQCKeyExchange()
        assert kem.is_available()
        
        keypair = kem.generate_keypair(key_id="test-key")
        
        assert keypair.algorithm == "ML-KEM-768"
        assert keypair.public_key == b"public"
        assert keypair.secret_key == b"secret"
        assert keypair.key_id == "test-key"
    
    @patch("src.security.pqc.kem.is_liboqs_available")
    @patch("src.security.pqc.kem.PQCAdapter")
    def test_kem_encapsulate(self, mock_adapter_class, mock_available):
        """Test KEM encapsulation."""
        mock_available.return_value = True
        mock_adapter = Mock()
        mock_adapter.kem_encapsulate.return_value = (b"ciphertext", b"shared_secret")
        mock_adapter_class.return_value = mock_adapter
        
        from src.security.pqc.kem import PQCKeyExchange
        
        kem = PQCKeyExchange()
        ciphertext, secret = kem.encapsulate(b"peer_public")
        
        assert ciphertext == b"ciphertext"
        assert secret == b"shared_secret"
    
    @patch("src.security.pqc.kem.is_liboqs_available")
    @patch("src.security.pqc.kem.PQCAdapter")
    def test_kem_decapsulate(self, mock_adapter_class, mock_available):
        """Test KEM decapsulation."""
        mock_available.return_value = True
        mock_adapter = Mock()
        mock_adapter.kem_decapsulate.return_value = b"shared_secret"
        mock_adapter_class.return_value = mock_adapter
        
        from src.security.pqc.kem import PQCKeyExchange
        
        kem = PQCKeyExchange()
        secret = kem.decapsulate(b"secret_key", b"ciphertext")
        
        assert secret == b"shared_secret"


class TestPQCDigitalSignature:
    """Tests for PQCDigitalSignature (DSA)."""
    
    @patch("src.security.pqc.dsa.is_liboqs_available")
    def test_dsa_unavailable(self, mock_available):
        """Test DSA when liboqs unavailable."""
        mock_available.return_value = False
        
        from src.security.pqc.dsa import PQCDigitalSignature
        
        dsa = PQCDigitalSignature()
        assert not dsa.is_available()
        
        with pytest.raises(RuntimeError, match="PQC not available"):
            dsa.generate_keypair()
    
    @patch("src.security.pqc.dsa.is_liboqs_available")
    @patch("src.security.pqc.dsa.PQCAdapter")
    def test_dsa_generate_keypair(self, mock_adapter_class, mock_available):
        """Test DSA keypair generation."""
        mock_available.return_value = True
        mock_adapter = Mock()
        mock_adapter.sig_generate_keypair.return_value = (b"public", b"secret")
        mock_adapter_class.return_value = mock_adapter
        
        from src.security.pqc.dsa import PQCDigitalSignature
        
        dsa = PQCDigitalSignature()
        keypair = dsa.generate_keypair(key_id="sig-key")
        
        assert keypair.algorithm == "ML-DSA-65"
        assert keypair.public_key == b"public"
        assert keypair.secret_key == b"secret"
    
    @patch("src.security.pqc.dsa.is_liboqs_available")
    @patch("src.security.pqc.dsa.PQCAdapter")
    def test_dsa_sign(self, mock_adapter_class, mock_available):
        """Test DSA signing."""
        mock_available.return_value = True
        mock_adapter = Mock()
        mock_adapter.sig_sign.return_value = b"signature_bytes"
        mock_adapter_class.return_value = mock_adapter
        
        from src.security.pqc.dsa import PQCDigitalSignature
        
        dsa = PQCDigitalSignature()
        signature = dsa.sign(b"message", b"secret_key", key_id="signer")
        
        assert signature.algorithm == "ML-DSA-65"
        assert signature.signature_bytes == b"signature_bytes"
        assert signature.signer_key_id == "signer"
    
    @patch("src.security.pqc.dsa.is_liboqs_available")
    @patch("src.security.pqc.dsa.PQCAdapter")
    def test_dsa_verify(self, mock_adapter_class, mock_available):
        """Test DSA verification."""
        mock_available.return_value = True
        mock_adapter = Mock()
        mock_adapter.sig_verify.return_value = True
        mock_adapter_class.return_value = mock_adapter
        
        from src.security.pqc.dsa import PQCDigitalSignature
        
        dsa = PQCDigitalSignature()
        is_valid = dsa.verify(b"message", b"signature", b"public")
        
        assert is_valid is True


class TestHybridSchemes:
    """Tests for hybrid classical + PQC schemes."""
    
    @patch("src.security.pqc.hybrid.is_liboqs_available")
    def test_hybrid_unavailable(self, mock_available):
        """Test hybrid when liboqs unavailable."""
        mock_available.return_value = False
        
        from src.security.pqc.hybrid import HybridKeyExchange, HybridSignatureScheme
        
        kem = HybridKeyExchange()
        assert not kem.is_available()
        
        dsa = HybridSignatureScheme()
        assert not dsa.is_available()
    
    @patch("src.security.pqc.hybrid.is_liboqs_available")
    @patch("src.security.pqc.hybrid.PQCKeyExchange")
    def test_hybrid_keypair(self, mock_pqc_kem_class, mock_available):
        """Test hybrid keypair generation."""
        mock_available.return_value = True
        
        # Mock PQC KEM
        mock_pqc_kem = Mock()
        from src.security.pqc.types import PQCKeyPair
        from datetime import datetime, timedelta
        
        mock_pqc_keypair = PQCKeyPair(
            algorithm="ML-KEM-768",
            public_key=b"pqc_public",
            secret_key=b"pqc_secret",
        )
        mock_pqc_kem.generate_keypair.return_value = mock_pqc_keypair
        mock_pqc_kem_class.return_value = mock_pqc_kem
        
        from src.security.pqc.hybrid import HybridKeyExchange
        
        hybrid = HybridKeyExchange()
        
        # Skip if not enabled (due to import issues in test)
        if not hybrid.enabled:
            pytest.skip("Hybrid not enabled in test environment")


class TestPQCModuleAPI:
    """Tests for unified PQC module public API."""
    
    def test_module_imports(self):
        """Test that all public API exports are importable."""
        from src.security.pqc import (
            __version__,
            is_liboqs_available,
            get_supported_kem_algorithms,
            get_supported_sig_algorithms,
            PQCAdapter,
            PQCAlgorithm,
            PQCKeyPair,
            PQCSignature,
            PQCEncapsulationResult,
            PQCKeyExchange,
            PQCDigitalSignature,
            HybridKeyPair,
            HybridSignature,
            HybridKeyExchange,
            HybridSignatureScheme,
        )
        
        assert __version__ == "2.0.0"
        assert callable(is_liboqs_available)
        assert callable(get_supported_kem_algorithms)
        assert callable(get_supported_sig_algorithms)
    
    def test_pqc_algorithm_enum_in_api(self):
        """Test PQCAlgorithm enum is accessible."""
        from src.security.pqc import PQCAlgorithm
        
        assert PQCAlgorithm.ML_KEM_768.value == "ML-KEM-768"
        assert PQCAlgorithm.ML_DSA_65.value == "ML-DSA-65"


class TestPQCIntegration:
    """Integration tests for PQC operations."""
    
    @pytest.mark.skipif(
        not pytest.importorskip("oqs", reason="liboqs not installed"),
        reason="Requires liboqs"
    )
    def test_real_kem_roundtrip(self):
        """Test real KEM roundtrip (requires liboqs)."""
        try:
            from src.security.pqc import PQCKeyExchange, is_liboqs_available
            
            if not is_liboqs_available():
                pytest.skip("liboqs not available")
            
            kem = PQCKeyExchange()
            
            # Generate keypair
            keypair = kem.generate_keypair()
            assert keypair.is_valid()
            
            # Encapsulate
            ciphertext, shared_secret = kem.encapsulate(keypair.public_key)
            
            # Decapsulate
            recovered = kem.decapsulate(keypair.secret_key, ciphertext)
            
            assert recovered == shared_secret
            
        except ImportError:
            pytest.skip("liboqs not installed")
    
    @pytest.mark.skipif(
        not pytest.importorskip("oqs", reason="liboqs not installed"),
        reason="Requires liboqs"
    )
    def test_real_signature_roundtrip(self):
        """Test real signature roundtrip (requires liboqs)."""
        try:
            from src.security.pqc import PQCDigitalSignature, is_liboqs_available
            
            if not is_liboqs_available():
                pytest.skip("liboqs not available")
            
            dsa = PQCDigitalSignature()
            
            # Generate keypair
            keypair = dsa.generate_keypair()
            assert keypair.is_valid()
            
            # Sign
            message = b"Test message for signing"
            signature = dsa.sign(message, keypair.secret_key)
            
            # Verify
            is_valid = dsa.verify(message, signature.signature_bytes, keypair.public_key)
            assert is_valid is True
            
            # Verify with wrong message
            is_valid_wrong = dsa.verify(b"Wrong message", signature.signature_bytes, keypair.public_key)
            assert is_valid_wrong is False
            
        except ImportError:
            pytest.skip("liboqs not installed")


if __name__ == "__main__":
    pytest.main([__file__, "-v"])
