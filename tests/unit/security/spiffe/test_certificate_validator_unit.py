from datetime import datetime, timedelta

import pytest
from cryptography import x509


def _make_cert(now=None, not_before=None, not_after=None, serial=123):
    now = now or datetime.utcnow()

    class _Extensions:
        def __init__(self):
            self._get = None

        def get_extension_for_oid(self, oid):
            if self._get:
                return self._get(oid)
            raise x509.ExtensionNotFound("missing", oid)

    class _Cert:
        def __init__(self):
            self.not_valid_before = not_before or (now - timedelta(minutes=1))
            self.not_valid_after = not_after or (now + timedelta(hours=1))
            self.serial_number = serial
            self.extensions = _Extensions()

        def verify_directly_issued_by(self, ca):
            return True

    return _Cert()


def test_validate_certificate_not_yet_valid(monkeypatch):
    from src.security.spiffe import certificate_validator as mod

    now = datetime.utcnow()
    cert = _make_cert(now=now, not_before=now + timedelta(minutes=5))

    monkeypatch.setattr(
        mod.x509, "load_pem_x509_certificate", lambda pem, backend: cert
    )

    v = mod.CertificateValidator()
    ok, spiffe_id, err = v.validate_certificate(b"pem")
    assert ok is False
    assert spiffe_id is None
    assert "not yet valid" in err.lower()


def test_validate_certificate_expired(monkeypatch):
    from src.security.spiffe import certificate_validator as mod

    now = datetime.utcnow()
    cert = _make_cert(now=now, not_after=now - timedelta(seconds=1))

    monkeypatch.setattr(
        mod.x509, "load_pem_x509_certificate", lambda pem, backend: cert
    )

    v = mod.CertificateValidator()
    ok, spiffe_id, err = v.validate_certificate(b"pem")
    assert ok is False
    assert spiffe_id is None
    assert "expired" in err.lower()


def test_validate_certificate_missing_spiffe_id(monkeypatch):
    from src.security.spiffe import certificate_validator as mod

    cert = _make_cert()
    monkeypatch.setattr(
        mod.x509, "load_pem_x509_certificate", lambda pem, backend: cert
    )
    monkeypatch.setattr(
        mod.CertificateValidator, "_extract_spiffe_id", lambda self, c: None
    )

    v = mod.CertificateValidator()
    ok, spiffe_id, err = v.validate_certificate(b"pem")
    assert ok is False
    assert spiffe_id is None
    assert "no spiffe" in err.lower()


def test_validate_certificate_trust_domain_and_expected_id(monkeypatch):
    from src.security.spiffe import certificate_validator as mod

    cert = _make_cert()
    monkeypatch.setattr(
        mod.x509, "load_pem_x509_certificate", lambda pem, backend: cert
    )

    v = mod.CertificateValidator(trust_domain="td")

    # wrong trust domain
    monkeypatch.setattr(
        mod.CertificateValidator,
        "_extract_spiffe_id",
        lambda self, c: "spiffe://other/x",
    )
    ok, spiffe_id, err = v.validate_certificate(b"pem")
    assert ok is False
    assert spiffe_id == "spiffe://other/x"
    assert "trust domain" in err.lower()

    # expected mismatch
    monkeypatch.setattr(
        mod.CertificateValidator, "_extract_spiffe_id", lambda self, c: "spiffe://td/a"
    )
    ok2, spiffe_id2, err2 = v.validate_certificate(
        b"pem", expected_spiffe_id="spiffe://td/b"
    )
    assert ok2 is False
    assert spiffe_id2 == "spiffe://td/a"
    assert "mismatch" in err2.lower()


def test_validate_certificate_chain_pinning_and_revocation(monkeypatch):
    from src.security.spiffe import certificate_validator as mod

    cert = _make_cert()
    monkeypatch.setattr(
        mod.x509, "load_pem_x509_certificate", lambda pem, backend: cert
    )
    monkeypatch.setattr(
        mod.CertificateValidator,
        "_extract_spiffe_id",
        lambda self, c: "spiffe://x0tta6bl4.mesh/a",
    )

    # Force chain validation fail
    monkeypatch.setattr(
        mod.CertificateValidator,
        "_validate_certificate_chain",
        lambda self, c, b: False,
    )

    v = mod.CertificateValidator(trust_domain="x0tta6bl4.mesh")
    ok, spiffe_id, err = v.validate_certificate(b"pem", trust_bundle=[b"ca"])
    assert ok is False
    assert spiffe_id
    assert "chain" in err.lower()

    # Pinning mismatch
    monkeypatch.setattr(
        mod.CertificateValidator, "_validate_certificate_chain", lambda self, c, b: True
    )
    monkeypatch.setattr(
        mod.CertificateValidator, "_get_certificate_fingerprint", lambda self, p: "fp"
    )

    v2 = mod.CertificateValidator(enable_pinning=True, pinned_certs={"other"})
    ok2, spiffe_id2, err2 = v2.validate_certificate(b"pem")
    assert ok2 is False
    assert "pinned" in err2.lower()

    # Revoked
    v3 = mod.CertificateValidator(check_revocation=True)
    monkeypatch.setattr(
        mod.CertificateValidator, "_check_revocation", lambda self, c, p: (True, "bad")
    )
    ok3, spiffe_id3, err3 = v3.validate_certificate(b"pem")
    assert ok3 is False
    assert "revoked" in err3.lower()


def test_validate_certificate_auto_returns_bool(monkeypatch):
    from src.security.spiffe.certificate_validator import CertificateValidator

    v = CertificateValidator()
    monkeypatch.setattr(
        v,
        "validate_certificate",
        lambda *a, **k: (True, "spiffe://x0tta6bl4.mesh/a", None),
    )
    assert v.validate_certificate_auto(b"pem") is True

    monkeypatch.setattr(
        v,
        "validate_certificate",
        lambda *a, **k: (False, "spiffe://x0tta6bl4.mesh/a", "err"),
    )
    assert v.validate_certificate_auto(b"pem") is False
