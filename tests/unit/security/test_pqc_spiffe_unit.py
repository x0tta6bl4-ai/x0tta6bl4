"""
Unit tests for PQC-SPIFFE Bridge module
=======================================

Tests for PQC-SVID verification and SPIRE integration.
"""

import pytest
from unittest.mock import MagicMock, patch
from datetime import datetime, timedelta

from cryptography import x509
from cryptography.hazmat.primitives import hashes, serialization
from cryptography.hazmat.primitives.asymmetric import rsa
from cryptography.x509.oid import NameOID

from src.security.pqc_spiffe import PQCSpiffeBridge


def _certificate_pair(spiffe_id: str, trust_domain: str = "test.mesh"):
    ca_key = rsa.generate_private_key(public_exponent=65537, key_size=2048)
    ca_subject = x509.Name(
        [x509.NameAttribute(NameOID.COMMON_NAME, f"{trust_domain} test CA")]
    )
    ca_cert = (
        x509.CertificateBuilder()
        .subject_name(ca_subject)
        .issuer_name(ca_subject)
        .public_key(ca_key.public_key())
        .serial_number(x509.random_serial_number())
        .not_valid_before(datetime.utcnow() - timedelta(minutes=1))
        .not_valid_after(datetime.utcnow() + timedelta(days=1))
        .add_extension(x509.BasicConstraints(ca=True, path_length=None), critical=True)
        .sign(ca_key, hashes.SHA256())
    )

    leaf_key = rsa.generate_private_key(public_exponent=65537, key_size=2048)
    leaf_subject = x509.Name(
        [x509.NameAttribute(NameOID.COMMON_NAME, "pqc-spiffe-test-node")]
    )
    leaf_cert = (
        x509.CertificateBuilder()
        .subject_name(leaf_subject)
        .issuer_name(ca_subject)
        .public_key(leaf_key.public_key())
        .serial_number(x509.random_serial_number())
        .not_valid_before(datetime.utcnow() - timedelta(minutes=1))
        .not_valid_after(datetime.utcnow() + timedelta(hours=1))
        .add_extension(
            x509.SubjectAlternativeName([x509.UniformResourceIdentifier(spiffe_id)]),
            critical=False,
        )
        .sign(ca_key, hashes.SHA256())
    )

    return (
        leaf_cert.public_bytes(serialization.Encoding.PEM),
        ca_cert.public_bytes(serialization.Encoding.PEM),
    )


class TestPQCSpiffeBridge:
    """Tests for PQCSpiffeBridge."""

    @pytest.fixture
    def bridge(self):
        """Create a bridge instance."""
        with patch("src.security.pqc_spiffe.SPIREClient") as mock_spire:
            mock_spire.return_value = MagicMock()
            bridge = PQCSpiffeBridge(node_id="test-node-001", trust_domain="test.mesh")
            return bridge

    def test_init(self, bridge):
        """Test bridge initialization."""
        assert bridge.node_id == "test-node-001"
        assert bridge.spire_config.trust_domain == "test.mesh"
        assert bridge.pqc_identity is not None
        assert bridge.zkp_attestor is not None

    def test_get_pqc_svid(self, bridge):
        """Test PQC-SVID bundle generation."""
        bundle = bridge.get_pqc_svid()

        assert "spiffe_id" in bundle
        assert "test.mesh" in bundle["spiffe_id"]
        assert "pqc_public_keys" in bundle
        assert "pqc_did" in bundle
        assert "zkp_attestation" in bundle
        assert bundle["attestation"] == "spire-zkp-verified"

    def test_verify_pqc_svid_valid_bundle(self, bridge):
        """Test verification of valid PQC-SVID bundle."""
        # Generate a valid bundle
        bundle = bridge.get_pqc_svid()

        is_valid = bridge.verify_pqc_svid(bundle)

        assert is_valid is True

    def test_verify_pqc_svid_missing_pqc_keys(self, bridge):
        """Test verification fails without PQC keys."""
        bundle = {
            "spiffe_id": "spiffe://test.mesh/node/test-node",
            "pqc_did": "did:example:123",
            # Missing pqc_public_keys
        }

        is_valid = bridge.verify_pqc_svid(bundle)

        assert is_valid is False

    def test_verify_pqc_svid_missing_did(self, bridge):
        """Test verification fails without PQC DID."""
        bundle = {
            "spiffe_id": "spiffe://test.mesh/node/test-node",
            "pqc_public_keys": {"ml_dsa": "key123"},
            # Missing pqc_did
        }

        is_valid = bridge.verify_pqc_svid(bundle)

        assert is_valid is False

    def test_verify_pqc_svid_wrong_trust_domain(self, bridge):
        """Test verification fails with wrong trust domain."""
        bundle = {
            "spiffe_id": "spiffe://wrong.domain/node/test-node",
            "pqc_public_keys": {"ml_dsa": "key123"},
            "pqc_did": "did:example:123",
        }

        is_valid = bridge.verify_pqc_svid(bundle)

        assert is_valid is False

    def test_verify_pqc_svid_invalid_zkp(self, bridge):
        """Test verification fails with invalid ZKP attestation."""
        bundle = bridge.get_pqc_svid()
        # Tamper with ZKP proof
        bundle["zkp_attestation"]["response"] = 0

        is_valid = bridge.verify_pqc_svid(bundle)

        assert is_valid is False

    def test_verify_pqc_svid_without_zkp(self, bridge):
        """Test verification passes without ZKP attestation (optional)."""
        bundle = {
            "spiffe_id": "spiffe://test.mesh/node/test-node",
            "pqc_public_keys": {"ml_dsa": "key123"},
            "pqc_did": "did:example:123",
            # No zkp_attestation
        }

        is_valid = bridge.verify_pqc_svid(bundle)

        assert is_valid is True

    def test_verify_pqc_svid_full_x509_missing_context_fails_closed(self, bridge):
        """Test full verification fails closed without X.509 context."""
        bundle = bridge.get_pqc_svid()

        is_valid = bridge.verify_pqc_svid_full(bundle, verify_x509=True)

        assert is_valid is False

    def test_verify_pqc_svid_full_x509_valid_context(self, bridge):
        """Test full verification binds X.509 SAN and trust bundle."""
        bundle = bridge.get_pqc_svid()
        leaf_pem, ca_pem = _certificate_pair(bundle["spiffe_id"])
        bundle["x509_context"] = {
            "spiffe_id": bundle["spiffe_id"],
            "certificate": leaf_pem,
            "bundle": ca_pem,
        }

        is_valid = bridge.verify_pqc_svid_full(bundle, verify_x509=True)

        assert is_valid is True

    def test_verify_pqc_svid_full_x509_wrong_san_fails(self, bridge):
        """Test full verification rejects a certificate bound to another SPIFFE ID."""
        bundle = bridge.get_pqc_svid()
        leaf_pem, ca_pem = _certificate_pair("spiffe://test.mesh/node/other-node")
        bundle["x509_context"] = {
            "spiffe_id": bundle["spiffe_id"],
            "certificate": leaf_pem,
            "bundle": ca_pem,
        }

        is_valid = bridge.verify_pqc_svid_full(bundle, verify_x509=True)

        assert is_valid is False

    def test_verify_pqc_svid_full_without_x509(self, bridge):
        """Test full verification without X.509 check."""
        bundle = bridge.get_pqc_svid()

        is_valid = bridge.verify_pqc_svid_full(bundle, verify_x509=False)

        assert is_valid is True

    def test_create_secure_payload(self, bridge):
        """Test secure payload creation."""
        data = {"action": "relay", "target": "node-002"}

        payload = bridge.create_secure_payload(data)

        assert "manifest" in payload or "data" in payload or "signature" in payload


class TestPQCSpiffeBridgeIntegration:
    """Integration tests for PQC-SPIFFE bridge."""

    def test_cross_node_verification(self):
        """Test verification between two different nodes."""
        with patch("src.security.pqc_spiffe.SPIREClient") as mock_spire:
            mock_spire.return_value = MagicMock()

            # Node 1 creates a bundle
            bridge1 = PQCSpiffeBridge(node_id="node-001", trust_domain="mesh.local")
            bundle = bridge1.get_pqc_svid()

            # Node 2 verifies the bundle
            bridge2 = PQCSpiffeBridge(node_id="node-002", trust_domain="mesh.local")
            is_valid = bridge2.verify_pqc_svid(bundle)

            assert is_valid is True

    def test_cross_domain_verification_fails(self):
        """Test verification fails across different trust domains."""
        with patch("src.security.pqc_spiffe.SPIREClient") as mock_spire:
            mock_spire.return_value = MagicMock()

            # Node in domain A creates a bundle
            bridge_a = PQCSpiffeBridge(node_id="node-001", trust_domain="domain-a.local")
            bundle = bridge_a.get_pqc_svid()

            # Node in domain B tries to verify
            bridge_b = PQCSpiffeBridge(node_id="node-002", trust_domain="domain-b.local")
            is_valid = bridge_b.verify_pqc_svid(bundle)

            assert is_valid is False


if __name__ == "__main__":
    pytest.main([__file__, "-v"])
