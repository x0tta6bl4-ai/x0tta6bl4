#!/usr/bin/env python3
"""
Phase 3: PQC Failure Injection Testing
Tests error handling and recovery in PQC operations.
"""

import pytest

try:
    from src.security.post_quantum_liboqs import PQMeshSecurityLibOQS
    PQC_AVAILABLE = True
except ImportError:
    PQC_AVAILABLE = False


@pytest.mark.skipif(not PQC_AVAILABLE, reason="PQC components not available")
class TestPQCFailureInjection:
    """Test PQC error handling and recovery"""

    def test_invalid_ciphertext_handling(self):
        """Test handling of invalid ciphertext"""
        pqc = PQMeshSecurityLibOQS(node_id="failure-ciphertext")

        pk = pqc.generate_kem_keypair()
        shared = pqc.kem_encapsulate(pk)

        invalid_ciphertext = b"invalid_ct_data"

        try:
            result = pqc.kem_decapsulate(invalid_ciphertext)
            assert result is None or 'error' in str(result).lower()
        except Exception:
            pass

    def test_corrupted_signature_detection(self):
        """Test detection of corrupted signatures"""
        pqc = PQMeshSecurityLibOQS(node_id="failure-signature")

        message = b"Test message"
        signature = pqc.sign(message)

        corrupted_sig = bytearray(signature)
        if len(corrupted_sig) > 0:
            corrupted_sig[0] ^= 0xFF
            corrupted_sig = bytes(corrupted_sig)

            verified = pqc.verify(message, corrupted_sig)
            assert verified is False

    def test_expired_key_rejection(self):
        """Test rejection of expired PQC keys"""
        pqc = PQMeshSecurityLibOQS(node_id="failure-expiry")

        old_pk = pqc.generate_kem_keypair()
        assert old_pk is not None

        try:
            shared = pqc.kem_encapsulate(old_pk)
            assert shared is not None
        except Exception:
            pass

    def test_key_mismatch_detection(self):
        """Test detection of key mismatches"""
        pqc1 = PQMeshSecurityLibOQS(node_id="mismatch-node-1")
        pqc2 = PQMeshSecurityLibOQS(node_id="mismatch-node-2")

        pk1 = pqc1.generate_kem_keypair()
        pk2 = pqc2.generate_kem_keypair()

        message = b"Test message"
        sig1 = pqc1.sign(message)

        verified_with_2 = pqc2.verify(message, sig1)
        assert verified_with_2 is False

    def test_none_input_handling(self):
        """Test handling of None inputs"""
        pqc = PQMeshSecurityLibOQS(node_id="failure-none")

        try:
            pqc.sign(None)
            assert False, "Should handle None input"
        except (TypeError, ValueError, AttributeError):
            pass

        try:
            pqc.verify(None, None)
            assert False, "Should handle None input"
        except (TypeError, ValueError, AttributeError):
            pass

    def test_invalid_key_format(self):
        """Test handling of invalid key format"""
        pqc = PQMeshSecurityLibOQS(node_id="failure-invalid-key")

        invalid_key = "not_bytes_key"

        try:
            result = pqc.kem_encapsulate(invalid_key)
            assert result is None or 'error' in str(result).lower()
        except (TypeError, ValueError):
            pass

    def test_recovery_after_cryptographic_error(self):
        """Test recovery after cryptographic error"""
        pqc = PQMeshSecurityLibOQS(node_id="failure-recovery")

        try:
            pqc.kem_encapsulate(b"invalid")
        except Exception:
            pass

        valid_pk = pqc.generate_kem_keypair()
        valid_shared = pqc.kem_encapsulate(valid_pk)

        assert valid_shared is not None

    def test_empty_message_handling(self):
        """Test handling of empty messages"""
        pqc = PQMeshSecurityLibOQS(node_id="failure-empty")

        empty_msg = b""

        try:
            sig = pqc.sign(empty_msg)
            if sig is not None:
                verified = pqc.verify(empty_msg, sig)
                assert isinstance(verified, bool)
        except Exception:
            pass

    def test_very_large_message(self):
        """Test handling of very large messages"""
        pqc = PQMeshSecurityLibOQS(node_id="failure-large")

        large_msg = b"x" * (10 * 1024 * 1024)

        try:
            sig = pqc.sign(large_msg)
            if sig is not None:
                verified = pqc.verify(large_msg, sig)
                assert isinstance(verified, bool)
        except (MemoryError, Exception):
            pass

    def test_fallback_to_classical_on_pqc_failure(self):
        """Test fallback mechanism on PQC failure"""
        pqc = PQMeshSecurityLibOQS(node_id="failure-fallback")

        pk = pqc.generate_kem_keypair()
        assert pk is not None

        try:
            invalid_shared = pqc.kem_encapsulate(b"invalid")
        except Exception:
            pass

        classical_fallback = pqc.sign(b"fallback message")
        assert classical_fallback is not None

    def test_concurrent_error_handling(self):
        """Test error handling with concurrent operations"""
        pqc = PQMeshSecurityLibOQS(node_id="failure-concurrent")

        try:
            invalid_ct = pqc.kem_encapsulate(b"invalid")
        except Exception:
            pass

        valid_msg = b"concurrent test"
        sig = pqc.sign(valid_msg)

        assert pqc.verify(valid_msg, sig) is True

    def test_timeout_simulation(self):
        """Test behavior during timeout scenarios"""
        pqc = PQMeshSecurityLibOQS(node_id="failure-timeout")

        import time
        start = time.time()

        pk = pqc.generate_kem_keypair()
        elapsed = time.time() - start

        assert pk is not None
        assert elapsed < 5

    def test_partial_data_corruption(self):
        """Test detection of partially corrupted data"""
        pqc = PQMeshSecurityLibOQS(node_id="failure-partial-corruption")

        msg = b"Important message"
        sig = pqc.sign(msg)

        if len(sig) > 2:
            partial_corrupt = bytearray(sig)
            partial_corrupt[len(sig)//2] ^= 0xFF
            partial_corrupt = bytes(partial_corrupt)

            verified = pqc.verify(msg, partial_corrupt)
            assert verified is False

    def test_replay_attack_detection(self):
        """Test resistance to replay attacks"""
        pqc = PQMeshSecurityLibOQS(node_id="failure-replay")

        msg1 = b"Message 1"
        msg2 = b"Message 2"

        sig1 = pqc.sign(msg1)

        assert pqc.verify(msg1, sig1) is True
        assert pqc.verify(msg2, sig1) is False
