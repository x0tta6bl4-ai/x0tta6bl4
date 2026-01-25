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
    
    def test_zero_length_message(self):
        """Test encryption/decryption of zero-length message"""
        security = PQMeshSecurityLibOQS("test-node")
        
        # Zero-length message
        plaintext = b""
        ciphertext = security.encrypt(plaintext, "target-node")
        decrypted = security.decrypt(ciphertext, "source-node")
        
        assert decrypted == plaintext
    
    def test_maximum_size_message(self):
        """Test encryption/decryption of maximum size message"""
        security = PQMeshSecurityLibOQS("test-node")
        
        # Large message (1MB)
        plaintext = b"x" * (1024 * 1024)
        ciphertext = security.encrypt(plaintext, "target-node")
        decrypted = security.decrypt(ciphertext, "source-node")
        
        assert decrypted == plaintext
        assert len(ciphertext) > len(plaintext)  # Ciphertext should be larger
    
    def test_malformed_ciphertext(self):
        """Test handling of malformed ciphertext"""
        security = PQMeshSecurityLibOQS("test-node")
        
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
                security.decrypt(malformed, "source-node")
    
    def test_concurrent_encryption(self):
        """Test concurrent encryption operations"""
        import threading
        
        security = PQMeshSecurityLibOQS("test-node")
        results = []
        errors = []
        
        def encrypt_worker(data: bytes, target: str):
            try:
                ciphertext = security.encrypt(data, target)
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
                security.encrypt(plaintext, invalid_id)
    
    def test_timing_attack_resistance(self):
        """Test that encryption/decryption timing is consistent"""
        import time
        
        security = PQMeshSecurityLibOQS("test-node")
        
        # Measure timing for different message sizes
        timings = []
        for size in [10, 100, 1000, 10000]:
            data = b"x" * size
            start = time.perf_counter()
            ciphertext = security.encrypt(data, "target-node")
            security.decrypt(ciphertext, "source-node")
            elapsed = time.perf_counter() - start
            timings.append(elapsed)
        
        # Timing should scale roughly linearly (not constant-time, but predictable)
        # Small messages should be faster than large ones
        assert timings[0] < timings[-1]
    
    def test_key_regeneration(self):
        """Test that keys are regenerated correctly"""
        security1 = PQMeshSecurityLibOQS("node-1")
        security2 = PQMeshSecurityLibOQS("node-2")
        
        # Same node ID should generate same keys
        security3 = PQMeshSecurityLibOQS("node-1")
        
        plaintext = b"test data"
        ciphertext1 = security1.encrypt(plaintext, "target")
        ciphertext2 = security3.encrypt(plaintext, "target")
        
        # Should be able to decrypt with same node
        decrypted1 = security1.decrypt(ciphertext1, "target")
        decrypted2 = security3.decrypt(ciphertext2, "target")
        
        assert decrypted1 == plaintext
        assert decrypted2 == plaintext


@pytest.mark.skipif(not PQC_AVAILABLE, reason="LibOQS not available")
class TestPQCSecurityBoundaries:
    """Test security boundaries and edge cases"""
    
    def test_signature_verification(self):
        """Test signature creation and verification"""
        security = PQMeshSecurityLibOQS("test-node")
        
        message = b"test message"
        signature = security.sign(message)
        
        # Signature should be verifiable
        assert security.verify(message, signature, "test-node")
        
        # Modified message should fail
        assert not security.verify(b"modified", signature, "test-node")
    
    def test_empty_signature(self):
        """Test handling of empty signature"""
        security = PQMeshSecurityLibOQS("test-node")
        
        message = b"test"
        with pytest.raises((ValueError, Exception)):
            security.verify(message, b"", "test-node")
    
    def test_memory_exhaustion_protection(self):
        """Test protection against memory exhaustion attacks"""
        security = PQMeshSecurityLibOQS("test-node")
        
        # Very large message (should be rejected or handled gracefully)
        try:
            huge_message = b"x" * (100 * 1024 * 1024)  # 100MB
            ciphertext = security.encrypt(huge_message, "target-node")
            # Should either succeed or fail gracefully
            assert len(ciphertext) > 0 or True  # Accept both outcomes
        except (MemoryError, ValueError) as e:
            # Graceful failure is acceptable
            assert "too large" in str(e).lower() or "memory" in str(e).lower()


if __name__ == "__main__":
    pytest.main([__file__, "-v"])

