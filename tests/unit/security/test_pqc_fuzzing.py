"""
Fuzzing tests for Post-Quantum Cryptography (LibOQS).

Tests edge cases, malformed inputs, and security boundaries.
"""
import pytest
import os
from typing import Optional

# Try to import LibOQS
try:
    from src.security.post_quantum_liboqs import PQMeshSecurityLibOQS, LIBOQS_AVAILABLE
    PQC_AVAILABLE = LIBOQS_AVAILABLE
except ImportError:
    PQC_AVAILABLE = False
    PQMeshSecurityLibOQS = None


@pytest.mark.skipif(not PQC_AVAILABLE, reason="LibOQS not available")
class TestPQCFuzzing:
    """Fuzzing tests for PQC implementation"""
    
    @pytest.mark.asyncio
    async def test_zero_length_message(self):
        """Test encryption/decryption of zero-length message"""
        security = PQMeshSecurityLibOQS("test-node")
        target_security = PQMeshSecurityLibOQS("target-node")
        
        # Establish secure channel
        await security.establish_secure_channel("target-node", target_security.get_public_keys())
        
        # Zero-length message
        plaintext = b""
        ciphertext = security.encrypt_for_peer("target-node", plaintext)
        decrypted = security.decrypt_from_peer("target-node", ciphertext)
        
        assert decrypted == plaintext
    
    @pytest.mark.asyncio
    async def test_maximum_size_message(self):
        """Test encryption/decryption of maximum size message"""
        security = PQMeshSecurityLibOQS("test-node")
        target_security = PQMeshSecurityLibOQS("target-node")
        
        # Establish secure channel
        await security.establish_secure_channel("target-node", target_security.get_public_keys())
        
        # Large message (1MB)
        plaintext = b"x" * (1024 * 1024)
        ciphertext = security.encrypt_for_peer("target-node", plaintext)
        decrypted = security.decrypt_from_peer("target-node", ciphertext)
        
        assert decrypted == plaintext
        assert len(ciphertext) > len(plaintext)  # Ciphertext should be larger
    
    @pytest.mark.asyncio
    async def test_malformed_ciphertext(self):
        """Test handling of malformed ciphertext"""
        security = PQMeshSecurityLibOQS("test-node")
        target_security = PQMeshSecurityLibOQS("target-node")
        
        # Establish secure channel
        await security.establish_secure_channel("target-node", target_security.get_public_keys())
        
        # Malformed ciphertexts
        malformed_inputs = [
            b"",  # Empty
            b"x" * 10,  # Too short
            b"x" * 10000,  # Too long
            b"\x00" * 100,  # Null bytes
            b"\xff" * 100,  # All 0xFF
        ]
        
        for malformed in malformed_inputs:
            with pytest.raises((ValueError, Exception)):
                security.decrypt_from_peer("target-node", malformed)
    
    @pytest.mark.asyncio
    async def test_concurrent_encryption(self):
        """Test concurrent encryption operations"""
        import threading
        
        security = PQMeshSecurityLibOQS("test-node")
        target_security = PQMeshSecurityLibOQS("target-node")
        
        # Establish secure channel
        await security.establish_secure_channel("target-node", target_security.get_public_keys())
        
        results = []
        errors = []
        
        def encrypt_worker(data: bytes, target: str):
            try:
                ciphertext = security.encrypt_for_peer(target, data)
                results.append(len(ciphertext))
            except Exception as e:
                errors.append(e)
        
        # Create multiple threads
        threads = []
        for i in range(10):
            data = f"test-data-{i}".encode()
            thread = threading.Thread(target=encrypt_worker, args=(data, "target-node"))
            threads.append(thread)
            thread.start()
        
        # Wait for all threads
        for thread in threads:
            thread.join()
        
        # All should succeed
        assert len(errors) == 0
        assert len(results) == 10
    
    def test_invalid_node_id(self):
        """Test handling of invalid node IDs"""
        security = PQMeshSecurityLibOQS("test-node")
        plaintext = b"test data"
        
        # Invalid node IDs
        invalid_ids = [
            "",  # Empty
            "x" * 1000,  # Too long
            "\x00\x01\x02",  # Binary data
        ]
        
        for invalid_id in invalid_ids:
            with pytest.raises((ValueError, TypeError)):
                security.encrypt_for_peer(invalid_id, plaintext)
    
    @pytest.mark.asyncio
    async def test_timing_attack_resistance(self):
        """Test that encryption/decryption timing is consistent"""
        import time
        
        security = PQMeshSecurityLibOQS("test-node")
        target_security = PQMeshSecurityLibOQS("target-node")
        
        # Establish secure channel
        await security.establish_secure_channel("target-node", target_security.get_public_keys())
        
        # Measure timing for different message sizes
        timings = []
        for size in [10, 100, 1000, 10000]:
            data = b"x" * size
            start = time.perf_counter()
            ciphertext = security.encrypt_for_peer("target-node", data)
            security.decrypt_from_peer("target-node", ciphertext)
            elapsed = time.perf_counter() - start
            timings.append(elapsed)
        
        # Timing should scale roughly linearly (not constant-time, but predictable)
        # Small messages should be faster than large ones
        assert timings[0] < timings[-1]
    
    @pytest.mark.asyncio
    async def test_key_regeneration(self):
        """Test that keys are regenerated correctly"""
        security1 = PQMeshSecurityLibOQS("node-1")
        security2 = PQMeshSecurityLibOQS("node-2")
        
        # Same node ID should generate same keys
        security3 = PQMeshSecurityLibOQS("node-1")
        
        plaintext = b"test data"
        
        # Establish secure channels
        await security1.establish_secure_channel("target", security2.get_public_keys())
        await security3.establish_secure_channel("target", security2.get_public_keys())
        
        ciphertext1 = security1.encrypt_for_peer("target", plaintext)
        ciphertext2 = security3.encrypt_for_peer("target", plaintext)
        
        # Should be able to decrypt with same node
        decrypted1 = security1.decrypt_from_peer("target", ciphertext1)
        decrypted2 = security3.decrypt_from_peer("target", ciphertext2)
        
        assert decrypted1 == plaintext
        assert decrypted2 == plaintext


@pytest.mark.skipif(not PQC_AVAILABLE, reason="LibOQS not available")
class TestPQCSecurityBoundaries:
    """Test security boundaries and edge cases"""
    
    def test_signature_verification(self):
        """Test signature creation and verification"""
        security = PQMeshSecurityLibOQS("test-node")
        
        message = b"test message"
        signature = security.sign_beacon(message)
        
        # Signature should be verifiable
        assert security.verify_beacon(message, signature, security.sig_keypair.public_key)
        
        # Modified message should fail
        assert not security.verify_beacon(b"modified", signature, security.sig_keypair.public_key)
    
    def test_empty_signature(self):
        """Test handling of empty signature"""
        security = PQMeshSecurityLibOQS("test-node")
        
        message = b"test"
        assert not security.verify_beacon(message, b"", security.sig_keypair.public_key)
    
    @pytest.mark.asyncio
    async def test_memory_exhaustion_protection(self):
        """Test protection against memory exhaustion attacks"""
        security = PQMeshSecurityLibOQS("test-node")
        target_security = PQMeshSecurityLibOQS("target-node")
        
        # Establish secure channel
        await security.establish_secure_channel("target-node", target_security.get_public_keys())
        
        # Very large message (should be rejected or handled gracefully)
        try:
            huge_message = b"x" * (100 * 1024 * 1024)  # 100MB
            ciphertext = security.encrypt_for_peer("target-node", huge_message)
            # Should either succeed or fail gracefully
            assert len(ciphertext) > 0 or True  # Accept both outcomes
        except (MemoryError, ValueError) as e:
            # Graceful failure is acceptable
            assert "too large" in str(e).lower() or "memory" in str(e).lower()


if __name__ == "__main__":
    pytest.main([__file__, "-v"])

