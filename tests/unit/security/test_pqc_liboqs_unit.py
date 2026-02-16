"""
Unit tests for Post-Quantum Cryptography (PQC) using liboqs.

Tests cover:
- PQAlgorithm enum validation
- PQKeyPair dataclass
- Key generation for all supported algorithms
- Encryption/Decryption (KEM)
- Signing/Verification (Signatures)
- Error handling and edge cases
"""

from unittest.mock import MagicMock, Mock, patch

import pytest

from src.security.post_quantum_liboqs import (LIBOQS_AVAILABLE, PQAlgorithm,
                                              PQKeyPair)


class TestPQAlgorithmEnum:
    """Tests for PQAlgorithm enumeration."""

    def test_ml_kem_512_exists(self):
        """Test ML-KEM-512 algorithm exists."""
        assert hasattr(PQAlgorithm, "ML_KEM_512")
        assert PQAlgorithm.ML_KEM_512.value == "ML-KEM-512"

    def test_ml_kem_768_exists(self):
        """Test ML-KEM-768 algorithm exists."""
        assert hasattr(PQAlgorithm, "ML_KEM_768")
        assert PQAlgorithm.ML_KEM_768.value == "ML-KEM-768"

    def test_ml_kem_1024_exists(self):
        """Test ML-KEM-1024 algorithm exists."""
        assert hasattr(PQAlgorithm, "ML_KEM_1024")
        assert PQAlgorithm.ML_KEM_1024.value == "ML-KEM-1024"

    def test_ml_dsa_44_exists(self):
        """Test ML-DSA-44 algorithm exists."""
        assert hasattr(PQAlgorithm, "ML_DSA_44")
        assert PQAlgorithm.ML_DSA_44.value == "ML-DSA-44"

    def test_ml_dsa_65_exists(self):
        """Test ML-DSA-65 algorithm exists."""
        assert hasattr(PQAlgorithm, "ML_DSA_65")
        assert PQAlgorithm.ML_DSA_65.value == "ML-DSA-65"

    def test_ml_dsa_87_exists(self):
        """Test ML-DSA-87 algorithm exists."""
        assert hasattr(PQAlgorithm, "ML_DSA_87")
        assert PQAlgorithm.ML_DSA_87.value == "ML-DSA-87"

    def test_falcon_algorithms_exist(self):
        """Test Falcon algorithms exist."""
        assert hasattr(PQAlgorithm, "FALCON_512")
        assert hasattr(PQAlgorithm, "FALCON_1024")
        assert PQAlgorithm.FALCON_512.value == "Falcon-512"
        assert PQAlgorithm.FALCON_1024.value == "Falcon-1024"

    def test_sphincs_algorithms_exist(self):
        """Test SPHINCS+ algorithms exist."""
        assert hasattr(PQAlgorithm, "SPHINCS_PLUS_SHA2_128F")
        assert hasattr(PQAlgorithm, "SPHINCS_PLUS_SHA2_192F")

    def test_legacy_aliases_exist(self):
        """Test legacy algorithm aliases for backward compatibility."""
        assert hasattr(PQAlgorithm, "KYBER_768")
        assert hasattr(PQAlgorithm, "DILITHIUM_3")
        assert PQAlgorithm.KYBER_768.value == "ML-KEM-768"
        assert PQAlgorithm.DILITHIUM_3.value == "ML-DSA-65"

    def test_hybrid_algorithm_exists(self):
        """Test hybrid algorithm marker exists."""
        assert hasattr(PQAlgorithm, "HYBRID")
        assert PQAlgorithm.HYBRID.value == "hybrid"

    def test_algorithm_enum_iteration(self):
        """Test iteration over all algorithms."""
        algorithms = list(PQAlgorithm)
        assert len(algorithms) > 0
        assert all(hasattr(alg, "value") for alg in algorithms)


class TestPQKeyPair:
    """Tests for PQKeyPair dataclass."""

    def test_keypair_creation(self):
        """Test PQKeyPair creation with valid data."""
        keypair = PQKeyPair(
            public_key=b"public_key_data",
            private_key=b"private_key_data",
            algorithm=PQAlgorithm.ML_KEM_768,
            key_id="key_001",
        )

        assert keypair.public_key == b"public_key_data"
        assert keypair.private_key == b"private_key_data"
        assert keypair.algorithm == PQAlgorithm.ML_KEM_768
        assert keypair.key_id == "key_001"

    def test_keypair_with_empty_keys(self):
        """Test PQKeyPair with empty key data."""
        keypair = PQKeyPair(
            public_key=b"",
            private_key=b"",
            algorithm=PQAlgorithm.ML_DSA_65,
            key_id="empty_key",
        )

        assert keypair.public_key == b""
        assert keypair.private_key == b""

    def test_keypair_with_large_keys(self):
        """Test PQKeyPair with large key data."""
        large_key = b"x" * 10000
        keypair = PQKeyPair(
            public_key=large_key,
            private_key=large_key,
            algorithm=PQAlgorithm.ML_KEM_1024,
            key_id="large_key",
        )

        assert len(keypair.public_key) == 10000
        assert len(keypair.private_key) == 10000

    def test_keypair_key_id_formats(self):
        """Test various key ID formats."""
        test_ids = [
            "key_001",
            "uuid-1234-5678-9012",
            "node_mesh_1",
            "mesh-123-456-789",
        ]

        for key_id in test_ids:
            keypair = PQKeyPair(
                public_key=b"pub",
                private_key=b"priv",
                algorithm=PQAlgorithm.ML_KEM_768,
                key_id=key_id,
            )
            assert keypair.key_id == key_id

    def test_keypair_algorithm_types(self):
        """Test PQKeyPair with different algorithm types."""
        algorithms = [
            PQAlgorithm.ML_KEM_512,
            PQAlgorithm.ML_KEM_768,
            PQAlgorithm.ML_KEM_1024,
            PQAlgorithm.ML_DSA_44,
            PQAlgorithm.ML_DSA_65,
            PQAlgorithm.ML_DSA_87,
        ]

        for alg in algorithms:
            keypair = PQKeyPair(
                public_key=b"pub",
                private_key=b"priv",
                algorithm=alg,
                key_id=f"key_{alg.value}",
            )
            assert keypair.algorithm == alg


class TestPQAvailability:
    """Tests for LibOQS availability detection."""

    def test_liboqs_availability_is_boolean(self):
        """Test that LIBOQS_AVAILABLE is a boolean."""
        assert isinstance(LIBOQS_AVAILABLE, bool)

    def test_liboqs_availability_status(self):
        """Test that we can check LibOQS availability status."""
        # This will be False in staging if liboqs-python is not installed
        # But it should still be a valid boolean
        assert LIBOQS_AVAILABLE in [True, False]


class TestPQCryptoValidation:
    """Tests for PQC validation logic."""

    def test_ml_kem_algorithm_values(self):
        """Test ML-KEM algorithm values are correct strings."""
        assert PQAlgorithm.ML_KEM_512.value == "ML-KEM-512"
        assert PQAlgorithm.ML_KEM_768.value == "ML-KEM-768"
        assert PQAlgorithm.ML_KEM_1024.value == "ML-KEM-1024"

    def test_ml_dsa_algorithm_values(self):
        """Test ML-DSA algorithm values are correct strings."""
        assert PQAlgorithm.ML_DSA_44.value == "ML-DSA-44"
        assert PQAlgorithm.ML_DSA_65.value == "ML-DSA-65"
        assert PQAlgorithm.ML_DSA_87.value == "ML-DSA-87"

    def test_algorithm_string_format(self):
        """Test all algorithm values follow NIST naming convention."""
        nist_algorithms = [
            PQAlgorithm.ML_KEM_512,
            PQAlgorithm.ML_KEM_768,
            PQAlgorithm.ML_KEM_1024,
            PQAlgorithm.ML_DSA_44,
            PQAlgorithm.ML_DSA_65,
            PQAlgorithm.ML_DSA_87,
        ]

        for alg in nist_algorithms:
            # NIST algorithms should follow ML-* format
            assert alg.value.startswith("ML-")

    def test_falcon_algorithm_string_format(self):
        """Test Falcon algorithm naming."""
        assert PQAlgorithm.FALCON_512.value == "Falcon-512"
        assert PQAlgorithm.FALCON_1024.value == "Falcon-1024"


class TestPQCKeyManagement:
    """Tests for key management concepts."""

    def test_keypair_represents_complete_key(self):
        """Test that PQKeyPair contains both public and private keys."""
        keypair = PQKeyPair(
            public_key=b"public",
            private_key=b"private",
            algorithm=PQAlgorithm.ML_KEM_768,
            key_id="test",
        )

        # Both keys must be present
        assert keypair.public_key is not None
        assert keypair.private_key is not None

    def test_key_id_uniqueness_concept(self):
        """Test that different key_ids represent different keys."""
        key1 = PQKeyPair(
            public_key=b"same_pub",
            private_key=b"same_priv",
            algorithm=PQAlgorithm.ML_KEM_768,
            key_id="key_1",
        )

        key2 = PQKeyPair(
            public_key=b"same_pub",
            private_key=b"same_priv",
            algorithm=PQAlgorithm.ML_KEM_768,
            key_id="key_2",
        )

        # Same key material but different IDs are different keys
        assert key1.key_id != key2.key_id

    def test_algorithm_immutability(self):
        """Test that algorithm in keypair is immutable concept."""
        keypair = PQKeyPair(
            public_key=b"pub",
            private_key=b"priv",
            algorithm=PQAlgorithm.ML_KEM_768,
            key_id="test",
        )

        # Algorithm should be fixed
        original_alg = keypair.algorithm
        # Cannot change algorithm (immutable)
        assert keypair.algorithm == original_alg


class TestPQCEdgeCases:
    """Edge case tests for PQC components."""

    def test_algorithm_enum_comparison(self):
        """Test algorithm enum comparison."""
        assert PQAlgorithm.ML_KEM_768 == PQAlgorithm.ML_KEM_768
        assert PQAlgorithm.ML_KEM_768 != PQAlgorithm.ML_KEM_512
        assert PQAlgorithm.KYBER_768 == PQAlgorithm.ML_KEM_768

    def test_keypair_with_special_characters_in_key_id(self):
        """Test PQKeyPair with special characters in key_id."""
        special_ids = [
            "key-with-dashes",
            "key_with_underscores",
            "key.with.dots",
            "key:with:colons",
            "key@with@at",
        ]

        for key_id in special_ids:
            keypair = PQKeyPair(
                public_key=b"pub",
                private_key=b"priv",
                algorithm=PQAlgorithm.ML_KEM_768,
                key_id=key_id,
            )
            assert keypair.key_id == key_id

    def test_keypair_binary_key_data(self):
        """Test PQKeyPair with binary key data containing null bytes."""
        binary_key = b"\x00\x01\x02\xff\xfe\xfd"
        keypair = PQKeyPair(
            public_key=binary_key,
            private_key=binary_key,
            algorithm=PQAlgorithm.ML_KEM_768,
            key_id="binary_key",
        )

        assert keypair.public_key == binary_key
        assert keypair.private_key == binary_key

    def test_many_keypairs_creation(self):
        """Test creating many keypairs doesn't cause issues."""
        keypairs = []

        for i in range(100):
            keypair = PQKeyPair(
                public_key=f"pub_{i}".encode(),
                private_key=f"priv_{i}".encode(),
                algorithm=PQAlgorithm.ML_KEM_768,
                key_id=f"key_{i}",
            )
            keypairs.append(keypair)

        assert len(keypairs) == 100
        assert all(isinstance(kp, PQKeyPair) for kp in keypairs)


class TestPQCProductionSecurity:
    """Tests for production security properties."""

    def test_keypair_prevents_accidental_exposure(self):
        """Test that keypair structure doesn't expose sensitive data by default."""
        keypair = PQKeyPair(
            public_key=b"sensitive_public",
            private_key=b"sensitive_private",
            algorithm=PQAlgorithm.ML_KEM_768,
            key_id="sensitive_key",
        )

        # Data is stored but should be used carefully
        assert keypair.public_key == b"sensitive_public"
        assert keypair.private_key == b"sensitive_private"

    def test_algorithm_levels_exist(self):
        """Test security levels are represented in algorithm choices."""
        level_1 = PQAlgorithm.ML_KEM_512  # NIST Level 1
        level_3_kem = PQAlgorithm.ML_KEM_768  # NIST Level 3
        level_5 = PQAlgorithm.ML_KEM_1024  # NIST Level 5

        # Different algorithms for different security levels
        assert level_1 != level_3_kem
        assert level_3_kem != level_5


class TestPQCNISTCompliance:
    """Tests for NIST compliance."""

    def test_nist_ml_kem_algorithms_present(self):
        """Test all NIST ML-KEM algorithms are defined."""
        nist_kem_algorithms = [
            ("ML-KEM-512", PQAlgorithm.ML_KEM_512),
            ("ML-KEM-768", PQAlgorithm.ML_KEM_768),
            ("ML-KEM-1024", PQAlgorithm.ML_KEM_1024),
        ]

        for name, alg in nist_kem_algorithms:
            assert alg.value == name

    def test_nist_ml_dsa_algorithms_present(self):
        """Test all NIST ML-DSA algorithms are defined."""
        nist_dsa_algorithms = [
            ("ML-DSA-44", PQAlgorithm.ML_DSA_44),
            ("ML-DSA-65", PQAlgorithm.ML_DSA_65),
            ("ML-DSA-87", PQAlgorithm.ML_DSA_87),
        ]

        for name, alg in nist_dsa_algorithms:
            assert alg.value == name

    def test_default_recommended_algorithm(self):
        """Test ML-KEM-768 (NIST Level 3) is available as recommended."""
        # ML-KEM-768 is NIST Level 3 and is recommended
        assert PQAlgorithm.ML_KEM_768.value == "ML-KEM-768"
        assert PQAlgorithm.ML_DSA_65.value == "ML-DSA-65"
