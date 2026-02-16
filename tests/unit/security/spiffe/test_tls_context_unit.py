"""Unit tests for SPIFFE mTLS TLS context helpers."""

from datetime import datetime, timedelta

import pytest

from src.security.spiffe.mtls.tls_context import TLSRole, build_mtls_context
from src.security.spiffe.workload import X509SVID


class _FakeSSLContext:
    def __init__(self):
        self.minimum_version = None
        self.check_hostname = True
        self.verify_mode = None
        self.load_calls = []

    def load_cert_chain(self, certfile, keyfile):
        self.load_calls.append((certfile, keyfile))


def _sample_svid() -> X509SVID:
    return X509SVID(
        spiffe_id="spiffe://x0tta6bl4.mesh/node/test",
        cert_chain=[
            b"-----BEGIN CERTIFICATE-----",
            b"MOCK-CERT",
            b"-----END CERTIFICATE-----",
        ],
        private_key=b"-----BEGIN PRIVATE KEY-----\nMOCK\n-----END PRIVATE KEY-----",
        expiry=datetime.utcnow() + timedelta(hours=1),
    )


def test_build_mtls_context_configures_client_context(monkeypatch):
    fake_ctx = _FakeSSLContext()
    purposes = []

    def _fake_create_default_context(*, purpose):
        purposes.append(purpose)
        return fake_ctx

    monkeypatch.setattr(
        "src.security.spiffe.mtls.tls_context.ssl.create_default_context",
        _fake_create_default_context,
    )

    mtls = build_mtls_context(_sample_svid(), role=TLSRole.CLIENT)

    assert mtls.role == TLSRole.CLIENT
    assert mtls.spiffe_id == "spiffe://x0tta6bl4.mesh/node/test"
    assert mtls.ssl_context is fake_ctx
    assert purposes
    assert fake_ctx.check_hostname is False
    assert fake_ctx.verify_mode is not None
    assert len(fake_ctx.load_calls) == 1

    cert_file, key_file = fake_ctx.load_calls[0]
    assert cert_file
    assert key_file
    mtls.cleanup()
    assert mtls.cert_file.closed is True
    assert mtls.key_file.closed is True


def test_build_mtls_context_uses_server_purpose(monkeypatch):
    fake_ctx = _FakeSSLContext()
    purpose_used = {"value": None}

    def _fake_create_default_context(*, purpose):
        purpose_used["value"] = purpose
        return fake_ctx

    monkeypatch.setattr(
        "src.security.spiffe.mtls.tls_context.ssl.create_default_context",
        _fake_create_default_context,
    )

    mtls = build_mtls_context(_sample_svid(), role=TLSRole.SERVER)
    assert mtls.role == TLSRole.SERVER
    assert purpose_used["value"] is not None
    mtls.cleanup()


def test_build_mtls_context_wraps_failures_as_ioerror(monkeypatch):
    class _FailingSSLContext(_FakeSSLContext):
        def load_cert_chain(self, certfile, keyfile):
            raise ValueError("bad cert material")

    def _fake_create_default_context(*, purpose):
        return _FailingSSLContext()

    monkeypatch.setattr(
        "src.security.spiffe.mtls.tls_context.ssl.create_default_context",
        _fake_create_default_context,
    )

    with pytest.raises(IOError, match="Failed to build mTLS context"):
        build_mtls_context(_sample_svid(), role=TLSRole.CLIENT)
