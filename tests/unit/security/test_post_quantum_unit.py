"""Comprehensive unit tests for src/security/post_quantum.py.

Uses the REAL oqs library (installed) for crypto operations.
Only mocks LIBOQS_AVAILABLE for error-path tests.
"""

import hashlib
import os
import secrets
from cryptography.hazmat.primitives import serialization

os.environ.setdefault("X0TTA6BL4_PRODUCTION", "false")
os.environ.setdefault("X0TTA6BL4_SPIFFE", "false")
os.environ.setdefault("X0TTA6BL4_FORCE_MOCK_SPIFFE", "true")

from unittest.mock import MagicMock, patch

import pytest

from src.security.post_quantum import (
    LIBOQS_AVAILABLE,
    HybridPQEncryption,
    LibOQSBackend,
    PQAlgorithm,
    PQCiphertext,
    PQKeyPair,
    PQMeshSecurityLibOQS,
)

# Skip all tests if oqs is not available
pytestmark = pytest.mark.skipif(
    not LIBOQS_AVAILABLE, reason="liboqs not installed"
)


# ---------------------------------------------------------------------------
# PQAlgorithm enum
# ---------------------------------------------------------------------------


class TestPQAlgorithm:
    def test_kem_algorithms(self):
        assert PQAlgorithm.ML_KEM_512.value == "ML-KEM-512"
        assert PQAlgorithm.ML_KEM_768.value == "ML-KEM-768"
        assert PQAlgorithm.ML_KEM_1024.value == "ML-KEM-1024"

    def test_sig_algorithms(self):
        assert PQAlgorithm.ML_DSA_44.value == "ML-DSA-44"
        assert PQAlgorithm.ML_DSA_65.value == "ML-DSA-65"
        assert PQAlgorithm.ML_DSA_87.value == "ML-DSA-87"

    def test_legacy_aliases(self):
        assert PQAlgorithm.KYBER_768.value == PQAlgorithm.ML_KEM_768.value
        assert PQAlgorithm.DILITHIUM_3.value == PQAlgorithm.ML_DSA_65.value

    def test_alternative_sig_algorithms(self):
        assert PQAlgorithm.FALCON_512.value == "Falcon-512"
        assert PQAlgorithm.FALCON_1024.value == "Falcon-1024"
        assert PQAlgorithm.SPHINCS_PLUS_SHA2_128F.value == "SPHINCS+-SHA2-128f-simple"

    def test_hybrid_value(self):
        assert PQAlgorithm.HYBRID.value == "hybrid"


# ---------------------------------------------------------------------------
# PQKeyPair / PQCiphertext dataclasses
# ---------------------------------------------------------------------------


class TestDataclasses:
    def test_pq_keypair(self):
        kp = PQKeyPair(
            public_key=b"pub",
            private_key=b"priv",
            algorithm=PQAlgorithm.ML_KEM_768,
            key_id="abc123",
        )
        assert kp.public_key == b"pub"
        assert kp.private_key == b"priv"
        assert kp.algorithm == PQAlgorithm.ML_KEM_768
        assert kp.key_id == "abc123"

    def test_pq_ciphertext(self):
        ct = PQCiphertext(
            ciphertext=b"ct",
            encapsulated_key=b"key",
            algorithm=PQAlgorithm.ML_KEM_768,
        )
        assert ct.ciphertext == b"ct"
        assert ct.encapsulated_key == b"key"


# ---------------------------------------------------------------------------
# LibOQSBackend (real oqs)
# ---------------------------------------------------------------------------


class TestLibOQSBackend:
    def test_init_raises_when_liboqs_unavailable(self):
        with patch("src.security.post_quantum.LIBOQS_AVAILABLE", False):
            with pytest.raises(ImportError, match="liboqs-python not installed"):
                LibOQSBackend()

    def test_init_stores_algorithms(self):
        backend = LibOQSBackend()
        assert backend.kem_algorithm == "ML-KEM-768"
        assert backend.sig_algorithm == "ML-DSA-65"

    # --- generate_kem_keypair ---

    def test_generate_kem_keypair_default(self):
        backend = LibOQSBackend()
        kp = backend.generate_kem_keypair()
        assert isinstance(kp, PQKeyPair)
        assert isinstance(kp.public_key, bytes)
        assert len(kp.public_key) > 0
        assert isinstance(kp.private_key, bytes)
        assert len(kp.private_key) > 0
        assert kp.algorithm == PQAlgorithm.ML_KEM_768
        assert kp.key_id == hashlib.sha256(kp.public_key).hexdigest()[:32]

    def test_generate_kem_keypair_ml_kem_512(self):
        backend = LibOQSBackend(kem_algorithm="ML-KEM-512")
        kp = backend.generate_kem_keypair()
        assert kp.algorithm == PQAlgorithm.ML_KEM_512

    def test_generate_kem_keypair_ml_kem_1024(self):
        backend = LibOQSBackend(kem_algorithm="ML-KEM-1024")
        kp = backend.generate_kem_keypair()
        assert kp.algorithm == PQAlgorithm.ML_KEM_1024

    def test_generate_kem_keypair_legacy_kyber768(self):
        backend = LibOQSBackend(kem_algorithm="Kyber768")
        kp = backend.generate_kem_keypair()
        # Kyber768 maps to ML-KEM-768 in value
        assert kp.algorithm == PQAlgorithm.ML_KEM_768

    def test_generate_kem_keypair_unknown_fallback(self):
        """Unknown algorithm falls back to ML-KEM-768."""
        backend = LibOQSBackend.__new__(LibOQSBackend)
        backend.kem_algorithm = "UnknownKEM-999"
        backend.sig_algorithm = "ML-DSA-65"
        # Can't actually generate keys with unknown algo, but we can test the enum mapping
        # by patching KeyEncapsulation to return bytes
        from unittest.mock import MagicMock
        mock_kem = MagicMock()
        mock_kem.generate_keypair.return_value = (b"\x01" * 32, b"\x02" * 32)
        with patch("src.security.post_quantum.KeyEncapsulation", return_value=mock_kem):
            kp = backend.generate_kem_keypair()
        assert kp.algorithm == PQAlgorithm.ML_KEM_768

    # --- kem_encapsulate / kem_decapsulate ---

    def test_kem_encapsulate_decapsulate_roundtrip(self):
        backend = LibOQSBackend()
        kp = backend.generate_kem_keypair()

        shared_enc, ciphertext = backend.kem_encapsulate(kp.public_key)
        assert isinstance(shared_enc, bytes)
        assert len(shared_enc) > 0
        assert isinstance(ciphertext, bytes)
        assert len(ciphertext) > 0

        shared_dec = backend.kem_decapsulate(kp.private_key, ciphertext)
        assert shared_dec == shared_enc

    def test_encapsulate_alias(self):
        backend = LibOQSBackend()
        kp = backend.generate_kem_keypair()

        ct, shared = backend.encapsulate(kp.public_key)
        assert isinstance(ct, bytes)
        assert isinstance(shared, bytes)

    def test_decapsulate_alias(self):
        backend = LibOQSBackend()
        kp = backend.generate_kem_keypair()
        shared_enc, ciphertext = backend.kem_encapsulate(kp.public_key)

        shared_dec = backend.decapsulate(ciphertext, kp.private_key)
        assert shared_dec == shared_enc

    # --- generate_signature_keypair ---

    def test_generate_signature_keypair_default(self):
        backend = LibOQSBackend()
        kp = backend.generate_signature_keypair()
        assert isinstance(kp, PQKeyPair)
        assert isinstance(kp.public_key, bytes)
        assert isinstance(kp.private_key, bytes)
        assert kp.algorithm == PQAlgorithm.ML_DSA_65
        assert kp.key_id == hashlib.sha256(kp.public_key).hexdigest()[:32]

    def test_generate_signature_keypair_ml_dsa_44(self):
        backend = LibOQSBackend(sig_algorithm="ML-DSA-44")
        kp = backend.generate_signature_keypair()
        assert kp.algorithm == PQAlgorithm.ML_DSA_44

    def test_generate_signature_keypair_ml_dsa_87(self):
        backend = LibOQSBackend(sig_algorithm="ML-DSA-87")
        kp = backend.generate_signature_keypair()
        assert kp.algorithm == PQAlgorithm.ML_DSA_87

    def test_generate_signature_keypair_legacy_dilithium3(self):
        backend = LibOQSBackend(sig_algorithm="Dilithium3")
        kp = backend.generate_signature_keypair()
        assert kp.algorithm == PQAlgorithm.ML_DSA_65

    def test_generate_signature_keypair_legacy_dilithium2(self):
        backend = LibOQSBackend(sig_algorithm="Dilithium2")
        kp = backend.generate_signature_keypair()
        assert kp.algorithm == PQAlgorithm.ML_DSA_44

    def test_generate_signature_keypair_legacy_dilithium5(self):
        backend = LibOQSBackend(sig_algorithm="Dilithium5")
        kp = backend.generate_signature_keypair()
        assert kp.algorithm == PQAlgorithm.ML_DSA_87

    def test_generate_sig_keypair_alias(self):
        backend = LibOQSBackend()
        kp = backend.generate_sig_keypair()
        assert kp.public_key is not None

    def test_generate_signature_keypair_unknown_fallback(self):
        backend = LibOQSBackend.__new__(LibOQSBackend)
        backend.kem_algorithm = "ML-KEM-768"
        backend.sig_algorithm = "UnknownSig-999"
        mock_sig = MagicMock()
        mock_sig.generate_keypair.return_value = b"\x01" * 32
        mock_sig.export_secret_key.return_value = b"\x02" * 32
        with patch("src.security.post_quantum.Signature", return_value=mock_sig):
            kp = backend.generate_signature_keypair()
        assert kp.algorithm == PQAlgorithm.ML_DSA_65

    # --- sign / verify ---

    def test_sign_and_verify(self):
        backend = LibOQSBackend()
        kp = backend.generate_signature_keypair()
        message = b"Hello, post-quantum world!"

        signature = backend.sign(message, kp.private_key)
        assert isinstance(signature, bytes)
        assert len(signature) > 0

        assert backend.verify(message, signature, kp.public_key) is True

    def test_verify_invalid_signature(self):
        backend = LibOQSBackend()
        kp = backend.generate_signature_keypair()
        message = b"Hello"
        signature = backend.sign(message, kp.private_key)

        # Tamper with the signature
        bad_sig = bytearray(signature)
        bad_sig[0] ^= 0xFF
        assert backend.verify(message, bytes(bad_sig), kp.public_key) is False

    def test_verify_wrong_message(self):
        backend = LibOQSBackend()
        kp = backend.generate_signature_keypair()
        signature = backend.sign(b"original", kp.private_key)
        assert backend.verify(b"tampered", signature, kp.public_key) is False


# ---------------------------------------------------------------------------
# HybridPQEncryption (real oqs)
# ---------------------------------------------------------------------------


class TestHybridPQEncryption:
    def test_init_raises_when_liboqs_unavailable(self):
        with patch("src.security.post_quantum.LIBOQS_AVAILABLE", False):
            with pytest.raises(ImportError, match="liboqs-python required"):
                HybridPQEncryption()

    def test_generate_hybrid_keypair(self):
        hybrid = HybridPQEncryption(kem_algorithm="ML-KEM-768")
        kp = hybrid.generate_hybrid_keypair()
        assert kp["type"] == "hybrid_keypair"
        assert "pq" in kp
        assert "classical" in kp
        assert len(kp["pq"]["public_key"]) > 0
        assert len(kp["pq"]["private_key"]) > 0
        assert len(kp["classical"]["public_key"]) == 64  # 32 bytes hex
        assert len(kp["classical"]["private_key"]) == 64
        assert "key_id" in kp

    def test_hybrid_encrypt_decrypt_roundtrip(self):
        hybrid = HybridPQEncryption(kem_algorithm="ML-KEM-768")
        shared_secret = secrets.token_bytes(32)
        plaintext = b"Hello, post-quantum world!"

        ciphertext = hybrid.hybrid_encrypt(plaintext, shared_secret)
        assert ciphertext != plaintext
        assert len(ciphertext) >= 12 + len(plaintext) + 16

        recovered = hybrid.hybrid_decrypt(ciphertext, shared_secret)
        assert recovered == plaintext

    def test_hybrid_decrypt_wrong_key_fails(self):
        hybrid = HybridPQEncryption(kem_algorithm="ML-KEM-768")
        shared_secret = secrets.token_bytes(32)
        wrong_secret = secrets.token_bytes(32)
        plaintext = b"secret data"

        ciphertext = hybrid.hybrid_encrypt(plaintext, shared_secret)
        with pytest.raises(Exception):
            hybrid.hybrid_decrypt(ciphertext, wrong_secret)

    def test_hybrid_encapsulate_decapsulate(self):
        hybrid = HybridPQEncryption(kem_algorithm="ML-KEM-768")
        kp = hybrid.generate_hybrid_keypair()

        pq_pub = bytes.fromhex(kp["pq"]["public_key"])
        pq_priv = bytes.fromhex(kp["pq"]["private_key"])
        classical_pub = bytes.fromhex(kp["classical"]["public_key"])
        classical_priv = bytes.fromhex(kp["classical"]["private_key"])

        combined_enc, ciphertexts = hybrid.hybrid_encapsulate(pq_pub, classical_pub)
        assert isinstance(combined_enc, bytes)
        assert len(combined_enc) == 32
        assert "pq" in ciphertexts
        assert "classical" in ciphertexts

        combined_dec = hybrid.hybrid_decapsulate(ciphertexts, pq_priv, classical_priv)
        assert isinstance(combined_dec, bytes)
        assert len(combined_dec) == 32
        assert combined_dec == combined_enc

    def test_encapsulate_backward_compat(self):
        hybrid = HybridPQEncryption(kem_algorithm="ML-KEM-768")
        keypair = hybrid.generate_hybrid_keypair()
        ciphertext, shared_secret = hybrid.encapsulate(keypair)
        assert isinstance(ciphertext, bytes)
        assert isinstance(shared_secret, bytes)

    def test_decapsulate_backward_compat(self):
        hybrid = HybridPQEncryption(kem_algorithm="ML-KEM-768")
        keypair = hybrid.generate_hybrid_keypair()
        ciphertext, shared_enc = hybrid.encapsulate(keypair)
        shared_dec = hybrid.decapsulate(ciphertext, keypair)
        assert isinstance(shared_dec, bytes)
        assert shared_dec == shared_enc

    def test_classical_encrypt_decrypt_roundtrip(self):
        from cryptography.hazmat.primitives.asymmetric import x25519
        hybrid = HybridPQEncryption(kem_algorithm="ML-KEM-768")
        private_key = x25519.X25519PrivateKey.generate()
        private_bytes = private_key.private_bytes(
            encoding=serialization.Encoding.Raw,
            format=serialization.PrivateFormat.Raw,
            encryption_algorithm=serialization.NoEncryption(),
        )
        public_key = private_key.public_key().public_bytes(
            encoding=serialization.Encoding.Raw, format=serialization.PublicFormat.Raw
        )
        message = b"Classical secret message"
        ct = hybrid._classical_encrypt(message, public_key)
        recovered = hybrid._classical_decrypt(ct, private_bytes)
        assert recovered == message

    def test_classical_decrypt_wrong_key_fails(self):
        from cryptography.hazmat.primitives.asymmetric import x25519
        hybrid = HybridPQEncryption(kem_algorithm="ML-KEM-768")
        private_key = x25519.X25519PrivateKey.generate()
        private_bytes = private_key.private_bytes(
            encoding=serialization.Encoding.Raw,
            format=serialization.PrivateFormat.Raw,
            encryption_algorithm=serialization.NoEncryption(),
        )
        public_key = private_key.public_key().public_bytes(
            encoding=serialization.Encoding.Raw, format=serialization.PublicFormat.Raw
        )
        wrong_private = x25519.X25519PrivateKey.generate()
        wrong_bytes = wrong_private.private_bytes(
            encoding=serialization.Encoding.Raw,
            format=serialization.PrivateFormat.Raw,
            encryption_algorithm=serialization.NoEncryption(),
        )

        message = b"Secret"
        ct = hybrid._classical_encrypt(message, public_key)
        with pytest.raises(Exception):
            hybrid._classical_decrypt(ct, wrong_bytes)

    def test_full_hybrid_flow(self):
        """End-to-end: generate keypair, encapsulate, encrypt, decrypt, decapsulate."""
        hybrid = HybridPQEncryption(kem_algorithm="ML-KEM-768")
        kp = hybrid.generate_hybrid_keypair()

        # Encapsulate
        ct, shared = hybrid.encapsulate(kp)
        assert isinstance(shared, bytes)

        # Encrypt with shared secret
        plaintext = b"Full hybrid flow test!"
        encrypted = hybrid.hybrid_encrypt(plaintext, shared)

        # Decapsulate on receiver side
        shared_dec = hybrid.decapsulate(ct, kp)
        assert shared_dec == shared

        # Decrypt
        decrypted = hybrid.hybrid_decrypt(encrypted, shared_dec)
        assert decrypted == plaintext


# ---------------------------------------------------------------------------
# PQMeshSecurityLibOQS (real oqs)
# ---------------------------------------------------------------------------


class TestPQMeshSecurityLibOQS:
    def test_init_raises_when_liboqs_unavailable(self):
        with patch("src.security.post_quantum.LIBOQS_AVAILABLE", False):
            with pytest.raises(RuntimeError, match="liboqs not available"):
                PQMeshSecurityLibOQS("node-1")

    def test_init_stores_node_id(self):
        ms = PQMeshSecurityLibOQS("test-node")
        assert ms.node_id == "test-node"

    def test_init_creates_keypairs(self):
        ms = PQMeshSecurityLibOQS("node-1")
        assert ms.kem_keypair is not None
        assert ms.sig_keypair is not None
        assert isinstance(ms.kem_keypair.public_key, bytes)
        assert isinstance(ms.sig_keypair.public_key, bytes)

    def test_init_legacy_kem_name_mapping(self):
        ms = PQMeshSecurityLibOQS("node-1", kem_algorithm="Kyber768")
        assert ms.pq_backend.kem_algorithm == "ML-KEM-768"

    def test_init_legacy_sig_name_mapping(self):
        ms = PQMeshSecurityLibOQS("node-1", sig_algorithm="Dilithium3")
        assert ms.pq_backend.sig_algorithm == "ML-DSA-65"

    def test_init_all_legacy_mappings(self):
        for legacy, nist in [("Kyber512", "ML-KEM-512"), ("Kyber1024", "ML-KEM-1024")]:
            ms = PQMeshSecurityLibOQS("n", kem_algorithm=legacy)
            assert ms.pq_backend.kem_algorithm == nist
        for legacy, nist in [("Dilithium2", "ML-DSA-44"), ("Dilithium5", "ML-DSA-87")]:
            ms = PQMeshSecurityLibOQS("n", sig_algorithm=legacy)
            assert ms.pq_backend.sig_algorithm == nist

    def test_get_public_keys(self):
        ms = PQMeshSecurityLibOQS("node-abc")
        keys = ms.get_public_keys()
        assert keys["node_id"] == "node-abc"
        assert "kem_public_key" in keys
        assert "sig_public_key" in keys
        assert "kem_algorithm" in keys
        assert "sig_algorithm" in keys
        assert "key_id" in keys

    def test_generate_kem_keypair_rotates(self):
        ms = PQMeshSecurityLibOQS("node-1")
        old_pub = ms.kem_keypair.public_key
        new_pub = ms.generate_kem_keypair()
        assert isinstance(new_pub, bytes)
        # New key should be different (with overwhelming probability)
        assert new_pub != old_pub

    def test_kem_encapsulate_decapsulate(self):
        ms = PQMeshSecurityLibOQS("node-1")
        shared_enc, ct = ms.kem_encapsulate(ms.kem_keypair.public_key)
        shared_dec = ms.kem_decapsulate(ct)
        assert shared_dec == shared_enc

    def test_kem_decapsulate_bad_ciphertext(self):
        ms = PQMeshSecurityLibOQS("node-1")
        # With bad ciphertext, oqs may return garbage or None depending on version
        result = ms.kem_decapsulate(b"\x00" * 1088)  # ML-KEM-768 ciphertext size
        # Result is either None (exception caught) or some bytes (implicit reject)
        assert result is None or isinstance(result, bytes)

    def test_sign_and_verify(self):
        ms = PQMeshSecurityLibOQS("node-1")
        message = b"beacon_data"
        signature = ms.sign(message)
        assert isinstance(signature, bytes)
        assert ms.verify(message, signature) is True

    def test_sign_none_raises(self):
        ms = PQMeshSecurityLibOQS("node-1")
        with pytest.raises(TypeError):
            ms.sign(None)

    def test_verify_none_raises(self):
        ms = PQMeshSecurityLibOQS("node-1")
        with pytest.raises(TypeError):
            ms.verify(None, b"sig")
        with pytest.raises(TypeError):
            ms.verify(b"msg", None)

    def test_sign_beacon(self):
        ms = PQMeshSecurityLibOQS("node-1")
        sig = ms.sign_beacon(b"beacon")
        assert isinstance(sig, bytes)

    def test_verify_beacon_valid(self):
        ms = PQMeshSecurityLibOQS("node-1")
        sig = ms.sign_beacon(b"data")
        assert ms.verify_beacon(b"data", sig, ms.sig_keypair.public_key) is True

    def test_verify_beacon_invalid(self):
        ms = PQMeshSecurityLibOQS("node-1")
        sig = ms.sign_beacon(b"data")
        bad_sig = bytearray(sig)
        bad_sig[0] ^= 0xFF
        assert ms.verify_beacon(b"data", bytes(bad_sig), ms.sig_keypair.public_key) is False

    def test_encrypt_for_peer_no_key_raises(self):
        ms = PQMeshSecurityLibOQS("node-1")
        with pytest.raises(ValueError, match="No shared key"):
            ms.encrypt_for_peer("unknown-peer", b"data")

    def test_decrypt_from_peer_no_key_raises(self):
        ms = PQMeshSecurityLibOQS("node-1")
        with pytest.raises(ValueError, match="No shared key"):
            ms.decrypt_from_peer("unknown-peer", b"data")

    def test_encrypt_decrypt_for_peer_roundtrip(self):
        ms = PQMeshSecurityLibOQS("node-1")
        shared_key = secrets.token_bytes(32)
        ms._peer_keys["peer-1"] = shared_key

        plaintext = b"Hello from node-1 to peer-1"
        ct = ms.encrypt_for_peer("peer-1", plaintext)
        assert ct != plaintext
        assert len(ct) >= 12 + len(plaintext) + 16

        recovered = ms.decrypt_from_peer("peer-1", ct)
        assert recovered == plaintext

    def test_encrypt_decrypt_peer_wrong_key_fails(self):
        ms = PQMeshSecurityLibOQS("node-1")
        ms._peer_keys["peer-1"] = secrets.token_bytes(32)
        ct = ms.encrypt_for_peer("peer-1", b"secret")

        ms._peer_keys["peer-1"] = secrets.token_bytes(32)
        with pytest.raises(Exception):
            ms.decrypt_from_peer("peer-1", ct)

    def test_get_security_level(self):
        ms = PQMeshSecurityLibOQS("node-1")
        level = ms.get_security_level()
        assert "algorithm" in level
        assert level["pq_security_level"] == "NIST Level 3"
        assert level["key_exchange"] == "quantum_safe"
        assert level["peers_with_pq"] == 0

    def test_get_security_level_with_peers(self):
        ms = PQMeshSecurityLibOQS("node-1")
        ms._peer_keys["p1"] = b"key1"
        ms._peer_keys["p2"] = b"key2"
        level = ms.get_security_level()
        assert level["peers_with_pq"] == 2

    def test_hybrid_cipher_attribute(self):
        ms = PQMeshSecurityLibOQS("node-1")
        assert ms.hybrid_cipher is ms.hybrid

    @pytest.mark.asyncio
    async def test_establish_secure_channel(self):
        ms = PQMeshSecurityLibOQS("node-1")
        peer = PQMeshSecurityLibOQS("node-2")
        peer_keys = peer.get_public_keys()
        shared = await ms.establish_secure_channel("peer-1", peer_keys)
        assert isinstance(shared, bytes)
        assert len(shared) == 32
        assert "peer-1" in ms._peer_keys

    @pytest.mark.asyncio
    async def test_establish_secure_channel_no_classical_key(self):
        ms = PQMeshSecurityLibOQS("node-1")
        peer = PQMeshSecurityLibOQS("node-2")
        peer_keys = {"kem_public_key": peer.get_public_keys()["kem_public_key"]}
        shared = await ms.establish_secure_channel("peer-2", peer_keys)
        assert isinstance(shared, bytes)

    @pytest.mark.asyncio
    async def test_establish_channel_then_encrypt_decrypt(self):
        ms = PQMeshSecurityLibOQS("node-1")
        peer = PQMeshSecurityLibOQS("node-2")
        peer_keys = peer.get_public_keys()
        await ms.establish_secure_channel("peer-e2e", peer_keys)

        plaintext = b"end-to-end test payload"
        ct = ms.encrypt_for_peer("peer-e2e", plaintext)
        recovered = ms.decrypt_from_peer("peer-e2e", ct)
        assert recovered == plaintext

    def test_verify_with_explicit_public_key(self):
        ms = PQMeshSecurityLibOQS("node-1")
        message = b"test message"
        sig = ms.sign(message)
        assert ms.verify(message, sig, ms.sig_keypair.public_key) is True

    def test_two_nodes_cross_verify(self):
        """Node A signs, Node B verifies with A's public key."""
        node_a = PQMeshSecurityLibOQS("node-a")
        node_b = PQMeshSecurityLibOQS("node-b")

        message = b"cross-node verification"
        sig = node_a.sign(message)
        assert node_b.verify(message, sig, node_a.sig_keypair.public_key) is True
        assert node_b.verify(b"tampered", sig, node_a.sig_keypair.public_key) is False
