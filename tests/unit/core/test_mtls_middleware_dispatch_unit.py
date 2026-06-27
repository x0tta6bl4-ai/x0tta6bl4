"""Dispatch-level tests for src/core/mtls_middleware.py."""

from __future__ import annotations

import json
from datetime import datetime, timedelta
from unittest.mock import AsyncMock

import pytest
from cryptography import x509
from cryptography.hazmat.primitives import hashes
from cryptography.hazmat.primitives.asymmetric import rsa
from cryptography.x509.oid import NameOID
from starlette.requests import Request
from starlette.responses import JSONResponse

from src.core.mtls_middleware import MTLSMiddleware


def _make_request(path: str = "/secure") -> Request:
    scope = {
        "type": "http",
        "method": "GET",
        "path": path,
        "headers": [],
        "query_string": b"",
        "client": ("127.0.0.1", 12345),
    }
    return Request(scope)


def _build_cert(
    *,
    spiffe_uri: str = "spiffe://x0tta6bl4.mesh/node/test",
    expired: bool = False,
) -> x509.Certificate:
    key = rsa.generate_private_key(public_exponent=65537, key_size=2048)
    subject = x509.Name([x509.NameAttribute(NameOID.COMMON_NAME, "mtls-test")])
    not_valid_before = datetime.utcnow() - timedelta(days=2)
    not_valid_after = (
        datetime.utcnow() - timedelta(days=1)
        if expired
        else datetime.utcnow() + timedelta(days=30)
    )
    builder = (
        x509.CertificateBuilder()
        .subject_name(subject)
        .issuer_name(subject)
        .public_key(key.public_key())
        .serial_number(x509.random_serial_number())
        .not_valid_before(not_valid_before)
        .not_valid_after(not_valid_after)
    )
    builder = builder.add_extension(
        x509.SubjectAlternativeName([x509.UniformResourceIdentifier(spiffe_uri)]),
        critical=False,
    )
    return builder.sign(private_key=key, algorithm=hashes.SHA256())


async def _echo_state_response(request: Request):
    return JSONResponse(
        {
            "spiffe_id": getattr(request.state, "spiffe_id", None),
            "cert_expiry": getattr(request.state, "cert_expiry", None),
        }
    )


@pytest.mark.asyncio
async def test_dispatch_rejects_tls_validation_failure():
    mw = MTLSMiddleware(app=AsyncMock(), require_mtls=False, enforce_tls_13=True)
    request = _make_request()
    mw.validator.validate_tls_version = lambda _request: (False, "TLSv1.2 below TLSv1.3")

    response = await mw.dispatch(request, AsyncMock(return_value=JSONResponse({"ok": True})))

    assert response.status_code == 400
    assert response.body
    assert b"TLS 1.3 required" in response.body


@pytest.mark.asyncio
async def test_dispatch_rejects_missing_client_certificate():
    mw = MTLSMiddleware(app=AsyncMock(), require_mtls=True, enforce_tls_13=False)
    request = _make_request()
    mw.validator.extract_client_cert_from_request = lambda _request: None

    response = await mw.dispatch(request, AsyncMock(return_value=JSONResponse({"ok": True})))

    assert response.status_code == 403
    assert b"Client certificate required" in response.body


@pytest.mark.asyncio
async def test_dispatch_rejects_unexpected_certificate_object_type():
    mw = MTLSMiddleware(app=AsyncMock(), require_mtls=True, enforce_tls_13=False)
    request = _make_request()
    mw.validator.extract_client_cert_from_request = lambda _request: object()

    response = await mw.dispatch(request, AsyncMock(return_value=JSONResponse({"ok": True})))

    assert response.status_code == 403
    assert b"mTLS authentication failed" in response.body


@pytest.mark.asyncio
async def test_dispatch_rejects_invalid_spiffe_domain():
    mw = MTLSMiddleware(app=AsyncMock(), require_mtls=True, enforce_tls_13=False)
    request = _make_request()
    mw.validator.extract_client_cert_from_request = lambda _request: _build_cert(
        spiffe_uri="spiffe://evil.mesh/node/test"
    )

    response = await mw.dispatch(request, AsyncMock(return_value=JSONResponse({"ok": True})))

    assert response.status_code == 403
    assert b"Invalid SPIFFE SVID" in response.body


@pytest.mark.asyncio
async def test_dispatch_rejects_expired_certificate():
    mw = MTLSMiddleware(app=AsyncMock(), require_mtls=True, enforce_tls_13=False)
    request = _make_request()
    mw.validator.extract_client_cert_from_request = lambda _request: _build_cert(expired=True)

    response = await mw.dispatch(request, AsyncMock(return_value=JSONResponse({"ok": True})))

    assert response.status_code == 403
    assert b"Certificate validation failed" in response.body


@pytest.mark.asyncio
async def test_dispatch_accepts_valid_certificate_and_sets_request_state():
    mw = MTLSMiddleware(app=AsyncMock(), require_mtls=True, enforce_tls_13=False)
    request = _make_request()
    cert = _build_cert()
    mw.validator.extract_client_cert_from_request = lambda _request: cert

    response = await mw.dispatch(request, _echo_state_response)

    assert response.status_code == 200
    payload = json.loads(response.body)
    assert payload["spiffe_id"] == "spiffe://x0tta6bl4.mesh/node/test"
    assert isinstance(payload["cert_expiry"], str)
    assert "expires in" in payload["cert_expiry"]
    assert response.headers["Strict-Transport-Security"].startswith("max-age=")
    assert response.headers["X-Content-Type-Options"] == "nosniff"
    assert response.headers["X-Frame-Options"] == "DENY"
