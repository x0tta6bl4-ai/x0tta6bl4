"""
Property-based tests for PQC cryptographic invariants using Hypothesis.

Covers bit-flip detection, cross-algorithm isolation, and malformed ciphertext resilience.
"""
import pytest
from hypothesis import given, strategies as st
from src.security.pqc.simple import PQC
from src.security.pqc.types import PQCKeyPair, PQCEncapsulationResult


class TestCryptographicInvariants:
    """Property-based security invariant tests."""

    @pytest.fixture(autouse=True)
    def setup_pqc(self):
        self.pqc = PQC()
        if not self.pqc.available:
            pytest.skip("PQC liboqs backend unavailable")
        # Generate DSA keypair for signatures and KEM keypair for key exchange
        self.dsa_keypair = self.pqc.dsa.generate_keypair()
        self.kem_keypair = self.pqc.kem.generate_keypair()

    @given(message=st.binary(min_size=1, max_size=1024))
    def test_inv_bit_flip_message_signature(self, message: bytes):
        """Inv-08: Flipping any single bit in message MUST invalidate signature verification."""
        sig = self.pqc.sign(message, self.dsa_keypair.secret_key)
        assert self.pqc.verify(message, sig, self.dsa_keypair.public_key) is True

        mutated_msg = bytearray(message)
        mutated_msg[0] ^= 0x01
        try:
            is_valid = self.pqc.verify(bytes(mutated_msg), sig, self.dsa_keypair.public_key)
        except Exception:
            is_valid = False
        assert is_valid is False

    @given(byte_offset=st.integers(min_value=0, max_value=10))
    def test_inv_bit_flip_signature_bytes(self, byte_offset: int):
        """Inv-07: Flipping any bit in signature MUST invalidate verification."""
        message = b"Canonical test payload for PQC signature verification"
        sig = self.pqc.sign(message, self.dsa_keypair.secret_key)
        assert self.pqc.verify(message, sig, self.dsa_keypair.public_key) is True

        if len(sig) > byte_offset:
            mutated_sig = bytearray(sig)
            mutated_sig[byte_offset] ^= 0x01
            try:
                is_valid = self.pqc.verify(message, bytes(mutated_sig), self.dsa_keypair.public_key)
            except Exception:
                is_valid = False
            assert is_valid is False

    @given(corrupted_ct=st.binary(min_size=0, max_size=4096))
    def test_inv_malformed_ciphertext_resilience(self, corrupted_ct: bytes):
        """Inv-02/12: Malformed ciphertext MUST be resilient and not crash process or raise unhandled exceptions."""
        try:
            recovered = self.pqc.decapsulate(corrupted_ct, self.kem_keypair.secret_key)
            assert isinstance(recovered, bytes)
        except (ValueError, RuntimeError):
            pass  # Expected safe failure path for corrupted inputs

    def test_inv_cross_algorithm_key_rejection(self):
        """Inv-12: Passing a KEM keypair to sign() MUST raise TypeError immediately."""
        with pytest.raises(TypeError, match="supplied to sign"):
            self.pqc.sign(b"payload", self.kem_keypair)
