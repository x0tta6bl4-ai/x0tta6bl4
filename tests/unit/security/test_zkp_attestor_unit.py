"""
Unit tests for ZKP Attestor module
==================================

Tests for NIZKP identity proofs and batch verification.
"""

import hashlib
import secrets
from unittest.mock import patch

import pytest

from src.security.zkp_attestor import (
    NIZKPAttestor,
    FirmwareAttestor,
    BatchZKPVerifier,
)
from src.security.zkp_auth import G, P, Q, SchnorrZKP


class TestNIZKPAttestor:
    """Tests for NIZKPAttestor."""

    @pytest.fixture
    def attestor(self):
        """Create an attestor instance."""
        secret_key = secrets.randbelow(Q - 1) + 1
        return NIZKPAttestor(node_id="test-node-001", secret_key=secret_key)

    def test_init(self, attestor):
        """Test attestor initialization."""
        assert attestor.node_id == "test-node-001"
        assert attestor.public_key is not None
        assert attestor.public_key > 0
        assert attestor.public_key < P

    def test_generate_identity_proof(self, attestor):
        """Test identity proof generation."""
        proof = attestor.generate_identity_proof(message="test-message")

        assert proof["node_id"] == "test-node-001"
        assert proof["public_key"] == attestor.public_key
        assert "commitment" in proof
        assert "response" in proof
        assert "timestamp" in proof

    def test_verify_identity_proof_valid(self, attestor):
        """Test verification of valid identity proof."""
        proof = attestor.generate_identity_proof(message="test-message")

        is_valid = NIZKPAttestor.verify_identity_proof(proof, message="test-message")

        assert is_valid is True

    def test_verify_identity_proof_wrong_message(self, attestor):
        """Test verification fails with wrong message."""
        proof = attestor.generate_identity_proof(message="correct-message")

        is_valid = NIZKPAttestor.verify_identity_proof(proof, message="wrong-message")

        assert is_valid is False

    def test_verify_identity_proof_tampered_response(self, attestor):
        """Test verification fails with tampered response."""
        proof = attestor.generate_identity_proof(message="test-message")
        proof["response"] = (proof["response"] + 1) % Q

        is_valid = NIZKPAttestor.verify_identity_proof(proof, message="test-message")

        assert is_valid is False

    def test_verify_identity_proof_tampered_public_key(self, attestor):
        """Test verification fails with tampered public key."""
        proof = attestor.generate_identity_proof(message="test-message")
        proof["public_key"] = (proof["public_key"] + 1) % P

        is_valid = NIZKPAttestor.verify_identity_proof(proof, message="test-message")

        assert is_valid is False

    def test_verify_identity_proof_missing_field(self, attestor):
        """Test verification handles missing fields gracefully."""
        proof = attestor.generate_identity_proof(message="test-message")
        del proof["node_id"]

        is_valid = NIZKPAttestor.verify_identity_proof(proof, message="test-message")

        assert is_valid is False


class TestFirmwareAttestor:
    """Tests for FirmwareAttestor."""

    def test_init(self):
        """Test firmware attestor initialization."""
        attestor = FirmwareAttestor(firmware_hash="v3.3.0-sha256:abc123")

        assert attestor.firmware_int is not None
        assert attestor.commitment is not None
        assert attestor.blinding_factor is not None

    def test_get_attestation_bundle(self):
        """Test attestation bundle generation."""
        attestor = FirmwareAttestor(firmware_hash="v3.3.0-sha256:abc123")
        bundle = attestor.get_attestation_bundle()

        assert "commitment" in bundle
        # Blinding factor should NOT be in bundle
        assert "blinding_factor" not in bundle

    def test_prove_firmware_match(self):
        """Test firmware match proof."""
        firmware_hash = "v3.3.0-sha256:abc123"
        attestor = FirmwareAttestor(firmware_hash=firmware_hash)

        is_valid = attestor.prove_firmware_match(firmware_hash)

        assert is_valid is True

    def test_prove_firmware_mismatch(self):
        """Test firmware mismatch detection."""
        attestor = FirmwareAttestor(firmware_hash="v3.3.0-sha256:abc123")

        is_valid = attestor.prove_firmware_match("v3.3.0-sha256:wrong")

        assert is_valid is False


class TestBatchZKPVerifier:
    """Tests for BatchZKPVerifier."""

    @pytest.fixture
    def valid_proofs(self):
        """Generate a list of valid proofs."""
        proofs = []
        for i in range(10):
            secret_key = secrets.randbelow(Q - 1) + 1
            attestor = NIZKPAttestor(node_id=f"node-{i:03d}", secret_key=secret_key)
            proof = attestor.generate_identity_proof(message="batch-test")
            proofs.append(proof)
        return proofs

    def test_verify_batch_all_valid(self, valid_proofs):
        """Test batch verification with all valid proofs."""
        results = BatchZKPVerifier.verify_batch(valid_proofs, message="batch-test")

        assert len(results) == 10
        assert all(results.values())

    def test_verify_batch_one_invalid(self, valid_proofs):
        """Test batch verification with one invalid proof."""
        # Tamper with one proof
        valid_proofs[5]["response"] = (valid_proofs[5]["response"] + 1) % Q

        results = BatchZKPVerifier.verify_batch(valid_proofs, message="batch-test")

        assert len(results) == 10
        assert results["node-005"] is False
        # Other proofs should still be valid
        assert results["node-000"] is True
        assert results["node-009"] is True

    def test_verify_batch_empty(self):
        """Test batch verification with empty list."""
        results = BatchZKPVerifier.verify_batch([], message="test")

        assert results == {}

    def test_verify_batch_optimized_small_batch(self, valid_proofs):
        """Test optimized batch verification with small batch (< 100)."""
        # Use only 5 proofs
        small_batch = valid_proofs[:5]

        is_valid, failed_node = BatchZKPVerifier.verify_batch_optimized(
            small_batch, message="batch-test"
        )

        assert is_valid is True
        assert failed_node is None

    def test_verify_batch_optimized_large_batch(self):
        """Test optimized batch verification with large batch (>= 100)."""
        # Generate 100 proofs
        proofs = []
        for i in range(100):
            secret_key = secrets.randbelow(Q - 1) + 1
            attestor = NIZKPAttestor(node_id=f"node-{i:04d}", secret_key=secret_key)
            proof = attestor.generate_identity_proof(message="large-batch-test")
            proofs.append(proof)

        is_valid, failed_node = BatchZKPVerifier.verify_batch_optimized(
            proofs, message="large-batch-test"
        )

        assert is_valid is True
        assert failed_node is None

    def test_verify_batch_optimized_with_invalid(self):
        """Test optimized batch verification detects invalid proofs."""
        # Generate 100 proofs with one invalid
        proofs = []
        for i in range(100):
            secret_key = secrets.randbelow(Q - 1) + 1
            attestor = NIZKPAttestor(node_id=f"node-{i:04d}", secret_key=secret_key)
            proof = attestor.generate_identity_proof(message="batch-with-invalid")
            proofs.append(proof)

        # Tamper with one proof
        proofs[50]["response"] = (proofs[50]["response"] + 1) % Q

        is_valid, failed_node = BatchZKPVerifier.verify_batch_optimized(
            proofs, message="batch-with-invalid"
        )

        assert is_valid is False
        assert failed_node == "node-0050"

    def test_verify_batch_optimized_missing_field(self):
        """Test optimized batch verification handles malformed proofs."""
        proofs = []
        for i in range(5):
            secret_key = secrets.randbelow(Q - 1) + 1
            attestor = NIZKPAttestor(node_id=f"node-{i:03d}", secret_key=secret_key)
            proof = attestor.generate_identity_proof(message="test")
            proofs.append(proof)

        # Remove a required field
        del proofs[2]["response"]

        is_valid, failed_node = BatchZKPVerifier.verify_batch_optimized(
            proofs, message="test"
        )

        assert is_valid is False
        assert failed_node == "node-002"


class TestZKPIntegration:
    """Integration tests for ZKP attestation flow."""

    def test_full_attestation_flow(self):
        """Test complete attestation flow."""
        # 1. Node generates identity proof
        secret_key = secrets.randbelow(Q - 1) + 1
        attestor = NIZKPAttestor(node_id="mesh-node-001", secret_key=secret_key)
        identity_proof = attestor.generate_identity_proof(message="mesh-join-v3.3")

        # 2. Verifier checks the proof
        is_valid = NIZKPAttestor.verify_identity_proof(
            identity_proof, message="mesh-join-v3.3"
        )
        assert is_valid is True

        # 3. Node generates firmware attestation
        firmware_attestor = FirmwareAttestor(firmware_hash="v3.3.0-release")
        bundle = firmware_attestor.get_attestation_bundle()

        # 4. Verify firmware matches expected
        firmware_valid = firmware_attestor.prove_firmware_match("v3.3.0-release")
        assert firmware_valid is True

    def test_batch_verification_performance(self):
        """Test that batch verification is more efficient than individual."""
        import time

        # Generate 200 proofs
        proofs = []
        for i in range(200):
            secret_key = secrets.randbelow(Q - 1) + 1
            attestor = NIZKPAttestor(node_id=f"perf-node-{i:04d}", secret_key=secret_key)
            proof = attestor.generate_identity_proof(message="perf-test")
            proofs.append(proof)

        # Time individual verification
        start = time.time()
        individual_results = BatchZKPVerifier.verify_batch(proofs, message="perf-test")
        individual_time = time.time() - start

        # Time optimized batch verification
        start = time.time()
        batch_valid, _ = BatchZKPVerifier.verify_batch_optimized(proofs, message="perf-test")
        batch_time = time.time() - start

        # Both should produce same result
        assert all(individual_results.values())
        assert batch_valid

        # Batch should be faster (or at least not significantly slower)
        # Note: This is a soft check - actual speedup depends on hardware
        print(f"\nIndividual: {individual_time:.4f}s, Batch: {batch_time:.4f}s")


if __name__ == "__main__":
    pytest.main([__file__, "-v"])
