from datetime import datetime, timedelta
import os
import tempfile
from pathlib import Path

from cryptography import x509
from cryptography.hazmat.primitives import hashes, serialization
from cryptography.hazmat.primitives.asymmetric import rsa
from cryptography.x509.oid import NameOID

from src.security.spiffe.workload.api_client import WorkloadAPIClient, X509SVID


def _create_test_certificate(
    spiffe_id: str,
    *,
    valid: bool = True,
    add_spiffe_san: bool = True,
) -> X509SVID:
    """Create an in-memory self-signed certificate for testing.

    The generated certificate uses a URI SAN for the given SPIFFE ID
    when ``add_spiffe_san`` is True.
    """

    key = rsa.generate_private_key(public_exponent=65537, key_size=2048)

    subject = issuer = x509.Name(
        [
            x509.NameAttribute(NameOID.COUNTRY_NAME, "US"),
            x509.NameAttribute(NameOID.ORGANIZATION_NAME, "x0tta6bl4"),
            x509.NameAttribute(NameOID.COMMON_NAME, "test-cert"),
        ]
    )

    now = datetime.utcnow()
    # Ensure that not_valid_after is always after not_valid_before to
    # satisfy cryptography.x509 constraints, while placing the full
    # validity window in the past when ``valid`` is False.
    if valid:
        not_before = now - timedelta(minutes=1)
        not_after = now + timedelta(hours=1)
    else:
        not_before = now - timedelta(hours=2)
        not_after = now - timedelta(hours=1)

    builder = (
        x509.CertificateBuilder()
        .subject_name(subject)
        .issuer_name(issuer)
        .public_key(key.public_key())
        .serial_number(x509.random_serial_number())
        .not_valid_before(not_before)
        .not_valid_after(not_after)
    )

    san_entries = []
    if add_spiffe_san:
        san_entries.append(x509.UniformResourceIdentifier(spiffe_id))

    if san_entries:
        builder = builder.add_extension(
            x509.SubjectAlternativeName(san_entries),
            critical=False,
        )

    cert = builder.sign(private_key=key, algorithm=hashes.SHA256())
    cert_pem = cert.public_bytes(serialization.Encoding.PEM)

    return X509SVID(
        spiffe_id=spiffe_id,
        cert_chain=[cert_pem],
        private_key=b"TEST_KEY",
        expiry=not_after,
    )


def test_validate_peer_svid_valid_with_expected_prefix(tmp_path):
    """A valid certificate with matching SPIFFE ID prefix is accepted."""

    client = WorkloadAPIClient(socket_path=tmp_path / "agent.sock")
    svid = _create_test_certificate(
        "spiffe://x0tta6bl4.mesh/service/api",
        valid=True,
        add_spiffe_san=True,
    )

    assert client.validate_peer_svid(svid, expected_id="spiffe://x0tta6bl4.mesh/service") is True


def test_validate_peer_svid_expired_svid_rejected(tmp_path):
    """Expired SVID is rejected before certificate-level checks."""

    client = WorkloadAPIClient(socket_path=tmp_path / "agent.sock")
    svid = _create_test_certificate(
        "spiffe://x0tta6bl4.mesh/service/api",
        valid=False,
        add_spiffe_san=True,
    )

    assert client.validate_peer_svid(svid, expected_id="spiffe://x0tta6bl4.mesh") is False


def test_validate_peer_svid_missing_san_fails_when_expected_id(tmp_path):
    """Certificate without SPIFFE URI SAN fails when expected_id is set."""

    client = WorkloadAPIClient(socket_path=tmp_path / "agent.sock")
    svid = _create_test_certificate(
        "spiffe://x0tta6bl4.mesh/service/api",
        valid=True,
        add_spiffe_san=False,
    )

    assert client.validate_peer_svid(svid, expected_id="spiffe://x0tta6bl4.mesh") is False


def test_validate_peer_svid_san_mismatch_fails(tmp_path):
    """Certificate with non-matching SPIFFE URI in SAN is rejected."""

    client = WorkloadAPIClient(socket_path=tmp_path / "agent.sock")
    svid = _create_test_certificate(
        "spiffe://x0tta6bl4.mesh/service/api",
        valid=True,
        add_spiffe_san=True,
    )

    assert client.validate_peer_svid(svid, expected_id="spiffe://other.mesh/") is False


def _create_ca_and_leaf_chain(
    ca_cn: str = "Test CA",
    leaf_spiffe_id: str = "spiffe://test.domain/service",
    leaf_valid: bool = True,
) -> tuple[bytes, bytes]:
    """Generate a simple CA certificate and a leaf certificate signed by it."""

    ca_key = rsa.generate_private_key(public_exponent=65537, key_size=2048)
    ca_subject = x509.Name([x509.NameAttribute(NameOID.COMMON_NAME, ca_cn)])

    now = datetime.utcnow()
    ca_builder = (
        x509.CertificateBuilder()
        .subject_name(ca_subject)
        .issuer_name(ca_subject)
        .public_key(ca_key.public_key())
        .serial_number(x509.random_serial_number())
        .not_valid_before(now - timedelta(minutes=1))
        .not_valid_after(now + timedelta(days=365))
        .add_extension(x509.BasicConstraints(ca=True, path_length=None), critical=True)
    )
    ca_cert = ca_builder.sign(private_key=ca_key, algorithm=hashes.SHA256())
    ca_pem = ca_cert.public_bytes(serialization.Encoding.PEM)

    leaf_key = rsa.generate_private_key(public_exponent=65537, key_size=2048)
    leaf_subject = x509.Name([x509.NameAttribute(NameOID.COMMON_NAME, "Test Leaf")])

    if leaf_valid:
        leaf_not_before = now - timedelta(minutes=1)
        leaf_not_after = now + timedelta(hours=1)
    else:
        leaf_not_before = now - timedelta(hours=2)
        leaf_not_after = now - timedelta(hours=1)

    leaf_builder = (
        x509.CertificateBuilder()
        .subject_name(leaf_subject)
        .issuer_name(ca_cert.subject)
        .public_key(leaf_key.public_key())
        .serial_number(x509.random_serial_number())
        .not_valid_before(leaf_not_before)
        .not_valid_after(leaf_not_after)
        .add_extension(
            x509.SubjectAlternativeName(
                [x509.UniformResourceIdentifier(leaf_spiffe_id)]
            ),
            critical=False,
        )
    )

    leaf_cert = leaf_builder.sign(private_key=ca_key, algorithm=hashes.SHA256())
    leaf_pem = leaf_cert.public_bytes(serialization.Encoding.PEM)
    return ca_pem, leaf_pem


def test_validate_peer_svid_with_trust_bundle_valid():
    """Valid certificate signed by a trusted CA should be accepted."""

    ca_pem, leaf_pem = _create_ca_and_leaf_chain()

    with tempfile.NamedTemporaryFile(mode="wb", delete=False, suffix=".pem") as f:
        f.write(ca_pem)
        bundle_path = f.name

    try:
        client = WorkloadAPIClient(trust_bundle_path=Path(bundle_path))
        svid = X509SVID(
            spiffe_id="spiffe://test.domain/service",
            cert_chain=[leaf_pem],
            private_key=b"KEY",
            expiry=datetime.utcnow() + timedelta(hours=1),
        )

        assert client.validate_peer_svid(svid, expected_id="spiffe://test.domain") is True
    finally:
        os.unlink(bundle_path)


def test_validate_peer_svid_with_trust_bundle_wrong_ca():
    """Certificate signed by an untrusted CA should be rejected."""

    trusted_ca_pem, _ = _create_ca_and_leaf_chain(ca_cn="Trusted CA")
    _, leaf_pem = _create_ca_and_leaf_chain(ca_cn="Untrusted CA")

    with tempfile.NamedTemporaryFile(mode="wb", delete=False, suffix=".pem") as f:
        f.write(trusted_ca_pem)
        bundle_path = f.name

    try:
        client = WorkloadAPIClient(trust_bundle_path=Path(bundle_path))
        svid = X509SVID(
            spiffe_id="spiffe://test.domain/service",
            cert_chain=[leaf_pem],
            private_key=b"KEY",
            expiry=datetime.utcnow() + timedelta(hours=1),
        )

        assert client.validate_peer_svid(svid, expected_id="spiffe://test.domain") is False
    finally:
        os.unlink(bundle_path)


def test_validate_peer_svid_no_trust_bundle_falls_back():
    """Without a trust bundle configured, validation falls back to basic checks."""

    _, leaf_pem = _create_ca_and_leaf_chain()

    client = WorkloadAPIClient()
    svid = X509SVID(
        spiffe_id="spiffe://test.domain/service",
        cert_chain=[leaf_pem],
        private_key=b"KEY",
        expiry=datetime.utcnow() + timedelta(hours=1),
    )

    assert client.validate_peer_svid(svid, expected_id="spiffe://test.domain") is True
