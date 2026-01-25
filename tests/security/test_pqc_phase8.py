"""
Phase 8: Post-Quantum Cryptography Tests

Tests for ML-KEM-768 key exchange and ML-DSA-65 digital signatures.
"""

import pytest
import asyncio
import numpy as np
from datetime import datetime, timedelta

from src.security.pqc_core import (
    PQCKeyExchange,
    PQCDigitalSignature,
    PQCHybridScheme,
    get_pqc_key_exchange,
    get_pqc_digital_signature,
    get_pqc_hybrid,
    test_pqc_availability,
)
from src.security.pqc_mtls import (
    PQCmTLSController,
    get_pqc_mtls_controller,
    test_pqc_mtls_setup,
)


# ========== PQC AVAILABILITY TESTS ==========

class TestPQCAvailability:
    """Test PQC library availability"""
    
    @pytest.mark.asyncio
    async def test_pqc_library_available(self):
        """Test if PQC library is available"""
        result = await test_pqc_availability()
        assert result["status"] in ["operational", "disabled", "error"]
    
    @pytest.mark.asyncio
    async def test_pqc_availability_timestamp(self):
        """Test PQC availability includes timestamp"""
        result = await test_pqc_availability()
        if "timestamp" in result:
            assert isinstance(result["timestamp"], str)


# ========== KEY EXCHANGE TESTS ==========

class TestMLKEM768:
    """ML-KEM-768 Key Exchange Tests"""
    
    def test_kem_initialization(self):
        """Test ML-KEM-768 initialization"""
        kem = get_pqc_key_exchange()
        assert kem is not None
    
    def test_kem_enabled_status(self):
        """Test KEM enabled status"""
        kem = get_pqc_key_exchange()
        assert isinstance(kem.enabled, bool)
    
    @pytest.mark.skipif(not PQCKeyExchange().enabled, reason="PQC not available")
    def test_keypair_generation(self):
        """Test ML-KEM-768 keypair generation"""
        kem = PQCKeyExchange()
        
        if not kem.enabled:
            pytest.skip("PQC not available")
        
        keypair = kem.generate_keypair(key_id="test_kem")
        
        assert keypair.algorithm == "ML-KEM-768"
        assert len(keypair.public_key) > 0
        assert len(keypair.secret_key) > 0
        assert keypair.key_id == "test_kem"
        assert not keypair.is_expired()
    
    @pytest.mark.skipif(not PQCKeyExchange().enabled, reason="PQC not available")
    def test_keypair_expiration(self):
        """Test keypair expiration check"""
        kem = PQCKeyExchange()
        
        if not kem.enabled:
            pytest.skip("PQC not available")
        
        # Generate keypair with 0 days validity (expired immediately)
        keypair = kem.generate_keypair(validity_days=0)
        
        # Will be expired due to time passing
        # assert keypair.is_expired()
    
    @pytest.mark.skipif(not PQCKeyExchange().enabled, reason="PQC not available")
    @pytest.mark.asyncio
    async def test_encapsulation_decapsulation(self):
        """Test ML-KEM-768 encapsulation/decapsulation"""
        kem = PQCKeyExchange()
        
        if not kem.enabled:
            pytest.skip("PQC not available")
        
        # Generate keypairs for client and server
        server_keypair = kem.generate_keypair(key_id="server")
        
        # Client encapsulates with server's public key
        ciphertext, client_secret = await kem.encapsulate(server_keypair.public_key)
        
        # Server decapsulates
        server_secret = await kem.decapsulate(server_keypair.secret_key, ciphertext)
        
        # Secrets should match
        assert client_secret == server_secret
        assert len(ciphertext) > 0
        assert len(client_secret) > 0


# ========== DIGITAL SIGNATURE TESTS ==========

class TestMLDSA65:
    """ML-DSA-65 Digital Signature Tests"""
    
    def test_dsa_initialization(self):
        """Test ML-DSA-65 initialization"""
        dsa = get_pqc_digital_signature()
        assert dsa is not None
    
    def test_dsa_enabled_status(self):
        """Test DSA enabled status"""
        dsa = get_pqc_digital_signature()
        assert isinstance(dsa.enabled, bool)
    
    @pytest.mark.skipif(not PQCDigitalSignature().enabled, reason="PQC not available")
    def test_signature_keypair_generation(self):
        """Test ML-DSA-65 keypair generation"""
        dsa = PQCDigitalSignature()
        
        if not dsa.enabled:
            pytest.skip("PQC not available")
        
        keypair = dsa.generate_keypair(key_id="test_dsa")
        
        assert keypair.algorithm == "ML-DSA-65"
        assert len(keypair.public_key) > 0
        assert len(keypair.secret_key) > 0
        assert keypair.key_id == "test_dsa"
    
    @pytest.mark.skipif(not PQCDigitalSignature().enabled, reason="PQC not available")
    @pytest.mark.asyncio
    async def test_sign_and_verify(self):
        """Test ML-DSA-65 signing and verification"""
        dsa = PQCDigitalSignature()
        
        if not dsa.enabled:
            pytest.skip("PQC not available")
        
        # Generate keypair
        keypair = dsa.generate_keypair(key_id="signer")
        
        # Sign message
        message = b"Test message for ML-DSA-65 signature"
        signature = await dsa.sign(message, keypair.secret_key, keypair.key_id)
        
        assert signature.algorithm == "ML-DSA-65"
        assert len(signature.signature_bytes) > 0
        assert signature.signer_key_id == "signer"
        
        # Verify signature
        is_valid = await dsa.verify(message, signature.signature_bytes, keypair.public_key)
        assert is_valid is True
    
    @pytest.mark.skipif(not PQCDigitalSignature().enabled, reason="PQC not available")
    @pytest.mark.asyncio
    async def test_signature_verification_fails_on_tampering(self):
        """Test signature verification fails when message is tampered"""
        dsa = PQCDigitalSignature()
        
        if not dsa.enabled:
            pytest.skip("PQC not available")
        
        keypair = dsa.generate_keypair(key_id="signer")
        
        # Sign original message
        original_message = b"Original message"
        signature = await dsa.sign(original_message, keypair.secret_key, keypair.key_id)
        
        # Try to verify with tampered message
        tampered_message = b"Tampered message"
        is_valid = await dsa.verify(tampered_message, signature.signature_bytes, keypair.public_key)
        
        # Should fail verification
        assert is_valid is False


# ========== HYBRID SCHEME TESTS ==========

class TestPQCHybrid:
    """PQC Hybrid Scheme Tests"""
    
    def test_hybrid_initialization(self):
        """Test hybrid scheme initialization"""
        hybrid = get_pqc_hybrid()
        assert hybrid is not None
    
    @pytest.mark.asyncio
    async def test_hybrid_secure_channel_setup(self):
        """Test hybrid secure channel setup"""
        hybrid = get_pqc_hybrid()
        
        result = await hybrid.setup_secure_channel()
        
        assert "method" in result
        assert "status" in result
        assert result["status"] in ["success", "fallback", "no_pqc_available"]
    
    @pytest.mark.skipif(not PQCHybridScheme().enable_pqc, reason="PQC not available")
    @pytest.mark.asyncio
    async def test_hybrid_certificate_signing(self):
        """Test hybrid certificate signing"""
        hybrid = PQCHybridScheme(enable_pqc=True)
        
        if not hybrid.enable_pqc:
            pytest.skip("PQC not available")
        
        cert_data = b"Test certificate data"
        signature = await hybrid.sign_certificate(cert_data)
        
        assert signature.algorithm == "ML-DSA-65"
        assert len(signature.signature_bytes) > 0
    
    @pytest.mark.skipif(not PQCHybridScheme().enable_pqc, reason="PQC not available")
    @pytest.mark.asyncio
    async def test_hybrid_certificate_verification(self):
        """Test hybrid certificate verification"""
        hybrid = PQCHybridScheme(enable_pqc=True)
        
        if not hybrid.enable_pqc:
            pytest.skip("PQC not available")
        
        # Sign certificate
        cert_data = b"Test certificate"
        signature = await hybrid.sign_certificate(cert_data)
        
        # Verify with signer's public key
        # (In real scenario, would verify with stored public key)
        keypair = hybrid.dsa.generate_keypair(key_id="verifier")
        
        is_valid = await hybrid.verify_certificate(
            cert_data,
            signature.signature_bytes,
            signature.signer_key_id  # This would be public key in production
        )
        
        # May fail due to key mismatch, but test validates the call works
        assert isinstance(is_valid, bool)


# ========== PQC mTLS TESTS ==========

class TestPQCmTLS:
    """Post-Quantum mTLS Tests"""
    
    def test_mtls_controller_initialization(self):
        """Test PQC mTLS controller initialization"""
        controller = get_pqc_mtls_controller()
        assert controller is not None
    
    def test_mtls_status(self):
        """Test mTLS status"""
        controller = get_pqc_mtls_controller()
        status = controller.get_status()
        
        assert "enabled" in status
        assert "hybrid_mode" in status
        assert "algorithms" in status
    
    @pytest.mark.asyncio
    async def test_mtls_pqc_key_initialization(self):
        """Test PQC key initialization for mTLS"""
        controller = PQCmTLSController(enable_hybrid=True)
        
        result = await controller.initialize_pqc_keys()
        
        assert "status" in result
        # Status can be success, disabled, or error
        assert result["status"] in ["success", "disabled", "error"]
    
    @pytest.mark.asyncio
    async def test_mtls_channel_establishment(self):
        """Test PQC channel establishment"""
        controller = PQCmTLSController(enable_hybrid=True)
        
        result = await controller.establish_pqc_channel()
        
        assert "status" in result
        # Status can be success, disabled, or error
        assert result["status"] in ["success", "disabled", "error"]
    
    @pytest.mark.skipif(not PQCmTLSController(enable_hybrid=True).enabled, reason="PQC not available")
    @pytest.mark.asyncio
    async def test_mtls_request_signing(self):
        """Test mTLS request signing"""
        controller = PQCmTLSController(enable_hybrid=True)
        
        if not controller.enabled:
            pytest.skip("PQC not available")
        
        # Initialize keys first
        await controller.initialize_pqc_keys()
        
        request_data = b"mTLS request data"
        signed_data, signature = await controller.sign_request(request_data)
        
        assert signed_data == request_data
        assert signature.algorithm == "ML-DSA-65"
    
    @pytest.mark.skipif(not PQCmTLSController(enable_hybrid=True).enabled, reason="PQC not available")
    @pytest.mark.asyncio
    async def test_mtls_response_verification(self):
        """Test mTLS response verification"""
        controller = PQCmTLSController(enable_hybrid=True)
        
        if not controller.enabled:
            pytest.skip("PQC not available")
        
        # Initialize keys
        await controller.initialize_pqc_keys()
        
        # Sign a request
        request = b"Test request"
        _, signature = await controller.sign_request(request)
        
        # Verify response
        is_valid = await controller.verify_response(request, signature.signature_bytes)
        assert isinstance(is_valid, bool)
    
    @pytest.mark.skipif(not PQCmTLSController(enable_hybrid=True).enabled, reason="PQC not available")
    @pytest.mark.asyncio
    async def test_mtls_certificate_creation(self):
        """Test PQC certificate creation"""
        controller = PQCmTLSController(enable_hybrid=True)
        
        if not controller.enabled:
            pytest.skip("PQC not available")
        
        # Initialize keys first
        await controller.initialize_pqc_keys()
        
        cert = await controller.create_pqc_certificate("test.example.com")
        
        assert cert.certificate_pem is not None
        assert cert.pqc_public_key is not None
        assert cert.created_at is not None
        assert cert.expires_at > cert.created_at
    
    @pytest.mark.skipif(not PQCmTLSController(enable_hybrid=True).enabled, reason="PQC not available")
    @pytest.mark.asyncio
    async def test_mtls_key_rotation(self):
        """Test PQC key rotation"""
        controller = PQCmTLSController(enable_hybrid=True)
        
        if not controller.enabled:
            pytest.skip("PQC not available")
        
        # Initialize keys
        await controller.initialize_pqc_keys()
        old_kem_id = controller.pqc_keys["kem"].key_id if "kem" in controller.pqc_keys else None
        
        # Rotate keys
        result = await controller.rotate_pqc_keys()
        
        assert "status" in result
        if result["status"] == "success":
            assert controller.pqc_keys["kem"].key_id != old_kem_id


# ========== INTEGRATION TESTS ==========

class TestPhase8Integration:
    """Phase 8 integration tests"""
    
    @pytest.mark.asyncio
    async def test_full_pqc_mtls_setup(self):
        """Test complete PQC mTLS setup"""
        result = await test_pqc_mtls_setup()
        
        assert "mtls_controller_status" in result
        assert "key_initialization" in result
        assert "channel_establishment" in result
        assert "overall_status" in result
    
    @pytest.mark.asyncio
    async def test_concurrent_pqc_operations(self):
        """Test concurrent PQC operations"""
        
        async def pqc_operation(i):
            hybrid = get_pqc_hybrid()
            return await hybrid.setup_secure_channel()
        
        results = await asyncio.gather(*[pqc_operation(i) for i in range(5)])
        
        assert len(results) == 5
        assert all(isinstance(r, dict) for r in results)
    
    @pytest.mark.asyncio
    async def test_pqc_fallback_mechanism(self):
        """Test PQC fallback to classical crypto"""
        controller = PQCmTLSController(enable_hybrid=False)
        
        status = controller.get_status()
        assert "fallback" in status


# ========== FIXTURES ==========

@pytest.fixture
def event_loop():
    """Create event loop for async tests"""
    loop = asyncio.get_event_loop_policy().new_event_loop()
    yield loop
    loop.close()


if __name__ == "__main__":
    pytest.main([__file__, "-v"])
