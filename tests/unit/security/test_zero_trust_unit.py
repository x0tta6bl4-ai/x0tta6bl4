import os
import pytest
from cryptography import x509
from cryptography.hazmat.primitives import hashes, serialization
from cryptography.hazmat.primitives.asymmetric import rsa
from cryptography.x509.oid import NameOID
import datetime

from src.security.ebpf_pqc_gateway import EBPFPQCGateway, PQCSession
from src.security.spiffe.certificate_validator import CertificateValidator


def _create_ca_and_signed_cert(spiffe_uri: str = None, not_valid_after=None, not_valid_before=None):
    # Create CA key
    ca_key = rsa.generate_private_key(public_exponent=65537, key_size=2048)
    subject = issuer = x509.Name([
        x509.NameAttribute(NameOID.COMMON_NAME, u"Test CA"),
    ])
    ca_cert = (
        x509.CertificateBuilder()
        .subject_name(subject)
        .issuer_name(issuer)
        .public_key(ca_key.public_key())
        .serial_number(x509.random_serial_number())
        .not_valid_before(not_valid_before or datetime.datetime.utcnow() - datetime.timedelta(days=1))
        .not_valid_after(not_valid_after or (datetime.datetime.utcnow() + datetime.timedelta(days=365)))
        .add_extension(x509.BasicConstraints(ca=True, path_length=None), critical=True)
        .sign(ca_key, hashes.SHA256())
    )

    # Leaf key and cert
    leaf_key = rsa.generate_private_key(public_exponent=65537, key_size=2048)
    leaf_subject = x509.Name([x509.NameAttribute(NameOID.COMMON_NAME, u"leaf")])
    builder = (
        x509.CertificateBuilder()
        .subject_name(leaf_subject)
        .issuer_name(ca_cert.subject)
        .public_key(leaf_key.public_key())
        .serial_number(x509.random_serial_number())
        .not_valid_before(not_valid_before or datetime.datetime.utcnow() - datetime.timedelta(hours=1))
        .not_valid_after(not_valid_after or (datetime.datetime.utcnow() + datetime.timedelta(days=90)))
    )

    if spiffe_uri:
        builder = builder.add_extension(
            x509.SubjectAlternativeName([x509.UniformResourceIdentifier(spiffe_uri)]), critical=False
        )

    leaf_cert = builder.sign(private_key=ca_key, algorithm=hashes.SHA256())

    ca_pem = ca_cert.public_bytes(serialization.Encoding.PEM)
    leaf_pem = leaf_cert.public_bytes(serialization.Encoding.PEM)
    return ca_pem, leaf_pem


def test_certificate_chain_validation_success():
    ca_pem, leaf_pem = _create_ca_and_signed_cert(spiffe_uri="spiffe://x0tta6bl4.mesh/service")
    cv = CertificateValidator()
    valid, spiffe_id, err = cv.validate_certificate(leaf_pem, expected_spiffe_id=None, trust_bundle=[ca_pem])
    assert valid is True
    assert spiffe_id and spiffe_id.startswith("spiffe://")
    assert err is None


def test_certificate_missing_spiffe_fails():
    _, leaf_pem = _create_ca_and_signed_cert(spiffe_uri=None)
    cv = CertificateValidator()
    valid, spiffe_id, err = cv.validate_certificate(leaf_pem)
    assert valid is False
    assert "No SPIFFE ID" in err


def test_ebpf_aes_encrypt_decrypt_roundtrip():
    # Bypass __init__ as liboqs may not be available
    gw = object.__new__(EBPFPQCGateway)
    gw.sessions = {}

    session = PQCSession(
        session_id="s1",
        peer_id="p1",
        kem_public_key=b"",
        dsa_public_key=b"",
        aes_key=os.urandom(32),
        verified=True,
        created_at=0,
        last_used=0,
    )
    gw.sessions[session.session_id] = session

    plaintext = b"hello world" * 10
    encrypted = gw.encrypt_payload(session.session_id, plaintext)
    assert encrypted is not None

    decrypted = gw.decrypt_payload(session.session_id, encrypted)
    assert decrypted == plaintext


def test_ebpf_decrypt_tampered_returns_none():
    gw = object.__new__(EBPFPQCGateway)
    gw.sessions = {}

    session = PQCSession(
        session_id="s2",
        peer_id="p2",
        kem_public_key=b"",
        dsa_public_key=b"",
        aes_key=os.urandom(32),
        verified=True,
        created_at=0,
        last_used=0,
    )
    gw.sessions[session.session_id] = session

    plaintext = b"some payload to protect"
    encrypted = gw.encrypt_payload(session.session_id, plaintext)
    assert encrypted is not None

    # Tamper with ciphertext (flip a byte)
    tampered = bytearray(encrypted)
    tampered[-1] ^= 0x01
    assert gw.decrypt_payload(session.session_id, bytes(tampered)) is None


def test_ebpf_encrypt_unverified_session_returns_none():
    gw = object.__new__(EBPFPQCGateway)
    gw.sessions = {}
    session = PQCSession(
        session_id="s3", peer_id="p3",
        kem_public_key=b"", dsa_public_key=b"",
        aes_key=os.urandom(32), verified=False,
        created_at=0, last_used=0,
    )
    gw.sessions[session.session_id] = session
    assert gw.encrypt_payload("s3", b"data") is None


def test_ebpf_decrypt_too_short_returns_none():
    gw = object.__new__(EBPFPQCGateway)
    gw.sessions = {}
    session = PQCSession(
        session_id="s4", peer_id="p4",
        kem_public_key=b"", dsa_public_key=b"",
        aes_key=os.urandom(32), verified=True,
        created_at=0, last_used=0,
    )
    gw.sessions[session.session_id] = session
    assert gw.decrypt_payload("s4", b"short") is None


# ---------------------------------------------------------------------------
# ZeroTrustValidator tests (mock WorkloadAPIClient)
# ---------------------------------------------------------------------------
from unittest.mock import patch, MagicMock


class TestZeroTrustValidator:
    @patch("src.security.zero_trust.validator.WorkloadAPIClient")
    def test_init_default_trust_domain(self, mock_client):
        from src.security.zero_trust import ZeroTrustValidator
        ztv = ZeroTrustValidator()
        assert ztv.trust_domain == "x0tta6bl4.mesh"

    @patch("src.security.zero_trust.validator.WorkloadAPIClient")
    def test_validates_same_trust_domain(self, mock_client):
        from src.security.zero_trust import ZeroTrustValidator
        ztv = ZeroTrustValidator()
        result = ztv.validate_connection("spiffe://x0tta6bl4.mesh/svc-a")
        assert result is True

    @patch("src.security.zero_trust.validator.WorkloadAPIClient")
    def test_rejects_different_trust_domain(self, mock_client):
        from src.security.zero_trust import ZeroTrustValidator
        ztv = ZeroTrustValidator()
        result = ztv.validate_connection("spiffe://evil.domain/svc")
        assert result is False

    @patch("src.security.zero_trust.validator.WorkloadAPIClient")
    def test_stats_tracking(self, mock_client):
        from src.security.zero_trust import ZeroTrustValidator
        ztv = ZeroTrustValidator()
        ztv.validate_connection("spiffe://x0tta6bl4.mesh/ok")
        ztv.validate_connection("spiffe://bad.domain/nope")
        stats = ztv.get_validation_stats()
        assert stats["total_attempts"] == 2
        assert stats["successes"] == 1
        assert stats["failures"] == 1

    @patch("src.security.zero_trust.validator.WorkloadAPIClient")
    def test_stats_zero_attempts(self, mock_client):
        from src.security.zero_trust import ZeroTrustValidator
        ztv = ZeroTrustValidator()
        stats = ztv.get_validation_stats()
        assert stats["total_attempts"] == 0
        assert stats["success_rate"] == 1.0


# ---------------------------------------------------------------------------
# DeviceAttestor tests
# ---------------------------------------------------------------------------

class TestDeviceAttestor:
    def test_create_fingerprint_structure(self):
        from src.security.device_attestation import DeviceAttestor
        da = DeviceAttestor(secret_salt="test-salt")
        fp = da.create_fingerprint()
        assert fp.fingerprint_hash
        assert fp.platform_type
        assert fp.arch_type
        assert fp.nonce
        assert fp.attestation_time > 0

    def test_fingerprint_same_salt_same_hash(self):
        from src.security.device_attestation import DeviceAttestor
        da1 = DeviceAttestor(secret_salt="stable-salt")
        da2 = DeviceAttestor(secret_salt="stable-salt")
        assert da1.create_fingerprint().fingerprint_hash == da2.create_fingerprint().fingerprint_hash

    def test_create_attestation_has_signature(self):
        from src.security.device_attestation import DeviceAttestor, AttestationType
        da = DeviceAttestor(secret_salt="sig-salt")
        claim = da.create_attestation(AttestationType.COMPOSITE)
        assert claim.signature
        assert claim.claim_id
        assert claim.evidence

    def test_verify_valid_attestation(self):
        from src.security.device_attestation import DeviceAttestor
        da = DeviceAttestor(secret_salt="verify-salt")
        claim = da.create_attestation()
        valid, reason = da.verify_attestation(claim)
        assert valid is True
        assert reason == "Valid"

    def test_verify_tampered_signature(self):
        from src.security.device_attestation import DeviceAttestor
        da = DeviceAttestor(secret_salt="tamper-salt")
        claim = da.create_attestation()
        claim.signature = "tampered" + claim.signature[8:]
        valid, reason = da.verify_attestation(claim)
        assert valid is False
        assert "Invalid signature" in reason


# ---------------------------------------------------------------------------
# TrustScore tests
# ---------------------------------------------------------------------------

class TestTrustScore:
    def test_update_weighted_average(self):
        from src.security.device_attestation import TrustScore, TrustLevel
        ts = TrustScore(device_id="d1", score=0.5, level=TrustLevel.MEDIUM,
                        factors={}, last_updated=0)
        ts.update(1.0)
        # 0.7 * 1.0 + 0.3 * 0.5 = 0.85
        assert abs(ts.score - 0.85) < 0.01

    def test_level_boundaries(self):
        from src.security.device_attestation import TrustScore, TrustLevel
        ts = TrustScore(device_id="d2", score=0.95, level=TrustLevel.VERIFIED,
                        factors={}, last_updated=0)
        assert ts._calculate_level() == TrustLevel.VERIFIED
        ts.score = 0.75
        assert ts._calculate_level() == TrustLevel.HIGH
        ts.score = 0.55
        assert ts._calculate_level() == TrustLevel.MEDIUM
        ts.score = 0.35
        assert ts._calculate_level() == TrustLevel.LOW
        ts.score = 0.1
        assert ts._calculate_level() == TrustLevel.UNTRUSTED


# ---------------------------------------------------------------------------
# AdaptiveTrustManager tests
# ---------------------------------------------------------------------------

class TestAdaptiveTrustManager:
    def test_default_score_is_medium(self):
        from src.security.device_attestation import AdaptiveTrustManager, TrustLevel
        atm = AdaptiveTrustManager()
        ts = atm.get_trust_score("new-device")
        assert ts.score == 0.5
        assert ts.level == TrustLevel.MEDIUM

    def test_is_trusted_default(self):
        from src.security.device_attestation import AdaptiveTrustManager, TrustLevel
        atm = AdaptiveTrustManager()
        assert atm.is_trusted("dev1", TrustLevel.MEDIUM) is True
        assert atm.is_trusted("dev1", TrustLevel.VERIFIED) is False


# ---------------------------------------------------------------------------
# PolicyEngine Attribute & Condition tests
# ---------------------------------------------------------------------------

class TestPolicyAttributes:
    def test_attribute_matches_wildcard(self):
        from src.security.policy_engine import Attribute, AttributeType
        attr = Attribute(type=AttributeType.SUBJECT, name="id", value="anything")
        assert attr.matches("*") is True

    def test_attribute_matches_regex(self):
        from src.security.policy_engine import Attribute, AttributeType
        attr = Attribute(type=AttributeType.SUBJECT, name="id", value="node-123")
        assert attr.matches("regex:node-\\d+") is True
        assert attr.matches("regex:service-\\d+") is False

    def test_attribute_matches_list(self):
        from src.security.policy_engine import Attribute, AttributeType
        attr = Attribute(type=AttributeType.ACTION, name="method", value="GET")
        assert attr.matches(["GET", "POST"]) is True
        assert attr.matches(["PUT", "DELETE"]) is False

    def test_attribute_matches_dict_comparison(self):
        from src.security.policy_engine import Attribute, AttributeType
        attr = Attribute(type=AttributeType.ENVIRONMENT, name="score", value=75)
        assert attr.matches({"gt": 50}) is True
        assert attr.matches({"lt": 50}) is False
        assert attr.matches({"gte": 75}) is True
        assert attr.matches({"lte": 74}) is False
