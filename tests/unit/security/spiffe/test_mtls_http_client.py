import tempfile
from datetime import datetime, timedelta
from pathlib import Path

import httpx
import pytest
from cryptography import x509
from cryptography.hazmat.primitives import hashes, serialization
from cryptography.hazmat.primitives.asymmetric import rsa
from cryptography.x509.oid import NameOID

from src.security.spiffe.mtls.http_client import SPIFFEHttpClient
from src.security.spiffe.workload.api_client import (  # Import SPIFFE_SDK_AVAILABLE
    SPIFFE_SDK_AVAILABLE, X509SVID, WorkloadAPIClient)


@pytest.mark.skipif(
    SPIFFE_SDK_AVAILABLE, reason="spiffe SDK is installed, skipping mock client tests"
)
@pytest.mark.asyncio
async def test_client_fetches_svid_and_performs_get_post(tmp_path, monkeypatch):
    """Client fetches an SVID and can perform basic GET/POST requests."""

    # Use force mock mode for WorkloadAPIClient
    monkeypatch.setenv("X0TTA6BL4_FORCE_MOCK_SPIFFE", "true")

    # Prepare a mock SPIRE Agent socket so WorkloadAPIClient works in
    # its filesystem-based mock mode.
    sock = tmp_path / "agent.sock"
    sock.write_text("")
    workload = WorkloadAPIClient(socket_path=sock)

    # Create a valid test certificate for mTLS
    from cryptography import x509
    from cryptography.hazmat.primitives import hashes, serialization
    from cryptography.hazmat.primitives.asymmetric import rsa
    from cryptography.x509.oid import NameOID

    # Generate a test certificate
    private_key = rsa.generate_private_key(public_exponent=65537, key_size=2048)
    public_key = private_key.public_key()

    cert = (
        x509.CertificateBuilder()
        .subject_name(
            x509.Name([x509.NameAttribute(NameOID.COMMON_NAME, "test.example.com")])
        )
        .issuer_name(
            x509.Name([x509.NameAttribute(NameOID.COMMON_NAME, "test.example.com")])
        )
        .public_key(public_key)
        .serial_number(x509.random_serial_number())
        .not_valid_before(datetime.utcnow())
        .not_valid_after(datetime.utcnow() + timedelta(days=1))
        .add_extension(
            x509.SubjectAlternativeName(
                [x509.UniformResourceIdentifier("spiffe://test.domain/workload/test")]
            ),
            critical=False,
        )
        .sign(private_key, hashes.SHA256())
    )

    cert_pem = cert.public_bytes(serialization.Encoding.PEM)
    key_pem = private_key.private_bytes(
        encoding=serialization.Encoding.PEM,
        format=serialization.PrivateFormat.PKCS8,
        encryption_algorithm=serialization.NoEncryption(),
    )

    # Create a valid SVID with real certificate
    svid = X509SVID(
        spiffe_id="spiffe://test.domain/workload/test",
        cert_chain=[cert_pem],
        private_key=key_pem,
        expiry=datetime.utcnow() + timedelta(hours=1),
    )

    # Mock fetch_x509_svid to return our valid SVID
    from unittest.mock import patch

    with patch.object(workload, "fetch_x509_svid", return_value=svid):
        # Use httpx.MockTransport to avoid real network calls.
        def handler(request: httpx.Request) -> httpx.Response:
            if request.method == "GET":
                return httpx.Response(200, json={"method": "GET"})
            if request.method == "POST":
                return httpx.Response(201, json={"method": "POST"})
            return httpx.Response(405)

        transport = httpx.MockTransport(handler)

        async with SPIFFEHttpClient(
            workload_api=workload, transport=transport
        ) as client:
            resp_get = await client.get("https://example.test/health")
            assert resp_get.status_code == 200
            assert resp_get.json()["method"] == "GET"

            resp_post = await client.post("https://example.test/items", json={"a": 1})
            assert resp_post.status_code == 201
            assert resp_post.json()["method"] == "POST"

            # SVID must be fetched and cached.
            assert client.identity is not None
            assert client.identity.spiffe_id.startswith("spiffe://")


@pytest.mark.asyncio
async def test_automatic_rotation_on_svid_expiry(tmp_path, monkeypatch):
    """When the cached SVID expires, a new one is fetched before the next request."""

    # Use force mock mode for WorkloadAPIClient
    monkeypatch.setenv("X0TTA6BL4_FORCE_MOCK_SPIFFE", "true")

    sock = tmp_path / "agent.sock"
    sock.write_text("")
    workload = WorkloadAPIClient(socket_path=sock)

    # Create valid test certificates for rotation
    from unittest.mock import patch

    from cryptography import x509
    from cryptography.hazmat.primitives import hashes, serialization
    from cryptography.hazmat.primitives.asymmetric import rsa
    from cryptography.x509.oid import NameOID

    def create_svid(spiffe_id: str, hours: int):
        private_key = rsa.generate_private_key(public_exponent=65537, key_size=2048)
        public_key = private_key.public_key()
        cert = (
            x509.CertificateBuilder()
            .subject_name(
                x509.Name([x509.NameAttribute(NameOID.COMMON_NAME, "test.example.com")])
            )
            .issuer_name(
                x509.Name([x509.NameAttribute(NameOID.COMMON_NAME, "test.example.com")])
            )
            .public_key(public_key)
            .serial_number(x509.random_serial_number())
            .not_valid_before(datetime.utcnow())
            .not_valid_after(datetime.utcnow() + timedelta(days=1))
            .add_extension(
                x509.SubjectAlternativeName(
                    [x509.UniformResourceIdentifier(spiffe_id)]
                ),
                critical=False,
            )
            .sign(private_key, hashes.SHA256())
        )
        cert_pem = cert.public_bytes(serialization.Encoding.PEM)
        key_pem = private_key.private_bytes(
            encoding=serialization.Encoding.PEM,
            format=serialization.PrivateFormat.PKCS8,
            encryption_algorithm=serialization.NoEncryption(),
        )
        return X509SVID(
            spiffe_id=spiffe_id,
            cert_chain=[cert_pem],
            private_key=key_pem,
            expiry=datetime.utcnow() + timedelta(hours=hours),
        )

    # Prepare two distinct SVIDs to observe rotation.
    svid1 = create_svid("spiffe://x0tta6bl4.mesh/node/one", hours=0)
    svid1.expiry = datetime.utcnow() + timedelta(seconds=5)
    svid2 = create_svid("spiffe://x0tta6bl4.mesh/node/two", hours=1)

    with patch.object(
        workload,
        "fetch_x509_svid",
        side_effect=[svid1, svid2],
    ) as fetch_mock:

        def handler(request: httpx.Request) -> httpx.Response:
            return httpx.Response(200, json={"ok": True})

        transport = httpx.MockTransport(handler)

        async with SPIFFEHttpClient(
            workload_api=workload, transport=transport
        ) as client:
            # First request should use the first SVID.
            resp1 = await client.get("https://example.test/one")
            assert resp1.status_code == 200
            assert client.identity is svid1

            # Force expiry to trigger rotation on the next call.
            assert client.identity is not None
            client.identity.expiry = datetime.utcnow() - timedelta(seconds=1)  # type: ignore[assignment]

            resp2 = await client.get("https://example.test/two")
            assert resp2.status_code == 200
            assert client.identity is svid2

        assert fetch_mock.call_count == 2


@pytest.mark.asyncio
async def test_peer_validation_toggle_controls_hook_invocation(tmp_path, monkeypatch):
    """Peer validation hook is only invoked when verification is enabled."""

    # Use force mock mode for WorkloadAPIClient
    monkeypatch.setenv("X0TTA6BL4_FORCE_MOCK_SPIFFE", "true")

    sock = tmp_path / "agent.sock"
    sock.write_text("")
    workload = WorkloadAPIClient(socket_path=sock)

    # Create valid test certificate
    private_key = rsa.generate_private_key(public_exponent=65537, key_size=2048)
    public_key = private_key.public_key()
    cert = (
        x509.CertificateBuilder()
        .subject_name(
            x509.Name([x509.NameAttribute(NameOID.COMMON_NAME, "test.example.com")])
        )
        .issuer_name(
            x509.Name([x509.NameAttribute(NameOID.COMMON_NAME, "test.example.com")])
        )
        .public_key(public_key)
        .serial_number(x509.random_serial_number())
        .not_valid_before(datetime.utcnow())
        .not_valid_after(datetime.utcnow() + timedelta(days=1))
        .add_extension(
            x509.SubjectAlternativeName(
                [x509.UniformResourceIdentifier("spiffe://test.domain/workload/test")]
            ),
            critical=False,
        )
        .sign(private_key, hashes.SHA256())
    )
    cert_pem = cert.public_bytes(serialization.Encoding.PEM)
    key_pem = private_key.private_bytes(
        encoding=serialization.Encoding.PEM,
        format=serialization.PrivateFormat.PKCS8,
        encryption_algorithm=serialization.NoEncryption(),
    )
    svid = X509SVID(
        spiffe_id="spiffe://test.domain/workload/test",
        cert_chain=[cert_pem],
        private_key=key_pem,
        expiry=datetime.utcnow() + timedelta(hours=1),
    )

    from unittest.mock import patch

    with patch.object(workload, "fetch_x509_svid", return_value=svid):

        def handler(request: httpx.Request) -> httpx.Response:
            return httpx.Response(200, json={"ok": True})

        transport = httpx.MockTransport(handler)

        # When verify_peer is enabled, the hook should be called once.
        async with SPIFFEHttpClient(
            workload_api=workload,
            transport=transport,
            expected_peer_id="spiffe://x0tta6bl4.mesh/service/api",
            verify_peer=True,
        ) as client:
            calls = {"count": 0}

            def fake_validate_peer(response: httpx.Response) -> None:  # type: ignore[override]
                calls["count"] += 1

            # Monkeypatch the internal hook.
            client._maybe_validate_peer = fake_validate_peer  # type: ignore[assignment]

            await client.get("https://example.test/validated")
            assert calls["count"] == 1

        # When verify_peer is disabled, the hook should not be called.
        async with SPIFFEHttpClient(
            workload_api=workload,
            transport=transport,
            expected_peer_id="spiffe://x0tta6bl4.mesh/service/api",
            verify_peer=False,
        ) as client:
            calls = {"count": 0}

            def fake_validate_peer_disabled(response: httpx.Response) -> None:  # type: ignore[override]
                calls["count"] += 1

            client._maybe_validate_peer = fake_validate_peer_disabled  # type: ignore[assignment]

            await client.get("https://example.test/not-validated")
            assert calls["count"] == 0


@pytest.mark.asyncio
async def test_context_manager_closes_client(tmp_path, monkeypatch):
    """Context manager should close the underlying HTTP client on exit."""

    # Use force mock mode for WorkloadAPIClient
    monkeypatch.setenv("X0TTA6BL4_FORCE_MOCK_SPIFFE", "true")

    sock = tmp_path / "agent.sock"
    sock.write_text("")
    workload = WorkloadAPIClient(socket_path=sock)

    # Create valid test certificate
    private_key = rsa.generate_private_key(public_exponent=65537, key_size=2048)
    public_key = private_key.public_key()
    cert = (
        x509.CertificateBuilder()
        .subject_name(
            x509.Name([x509.NameAttribute(NameOID.COMMON_NAME, "test.example.com")])
        )
        .issuer_name(
            x509.Name([x509.NameAttribute(NameOID.COMMON_NAME, "test.example.com")])
        )
        .public_key(public_key)
        .serial_number(x509.random_serial_number())
        .not_valid_before(datetime.utcnow())
        .not_valid_after(datetime.utcnow() + timedelta(days=1))
        .add_extension(
            x509.SubjectAlternativeName(
                [x509.UniformResourceIdentifier("spiffe://test.domain/workload/test")]
            ),
            critical=False,
        )
        .sign(private_key, hashes.SHA256())
    )
    cert_pem = cert.public_bytes(serialization.Encoding.PEM)
    key_pem = private_key.private_bytes(
        encoding=serialization.Encoding.PEM,
        format=serialization.PrivateFormat.PKCS8,
        encryption_algorithm=serialization.NoEncryption(),
    )
    svid = X509SVID(
        spiffe_id="spiffe://test.domain/workload/test",
        cert_chain=[cert_pem],
        private_key=key_pem,
        expiry=datetime.utcnow() + timedelta(hours=1),
    )

    from unittest.mock import patch

    with patch.object(workload, "fetch_x509_svid", return_value=svid):

        def handler(request: httpx.Request) -> httpx.Response:
            return httpx.Response(200, json={"ok": True})

        transport = httpx.MockTransport(handler)

        client_ref: SPIFFEHttpClient
        async with SPIFFEHttpClient(
            workload_api=workload, transport=transport
        ) as client:
            client_ref = client
            assert client_ref._closed is False
            resp = await client.get("https://example.test/once")
            assert resp.status_code == 200

        # After context exit, the client should be marked as closed.
        assert client_ref._closed is True


def _create_ca_and_leaf_chain(
    ca_cn: str = "Test CA",
    leaf_spiffe_id: str = "spiffe://test.domain/service",
) -> tuple[bytes, bytes]:
    """Generate a CA certificate and a leaf certificate signed by it."""

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

    leaf_not_before = now - timedelta(minutes=1)
    leaf_not_after = now + timedelta(hours=1)

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


class FakePeerCertTransport(httpx.AsyncBaseTransport):
    """Async transport that always returns a response with a peer cert chain."""

    def __init__(self, peer_cert: bytes) -> None:
        self._peer_cert = peer_cert

    async def handle_async_request(self, request: httpx.Request) -> httpx.Response:  # type: ignore[override]
        return httpx.Response(
            200,
            json={"ok": True},
            extensions={"peer_cert_chain": [self._peer_cert]},
        )


@pytest.mark.asyncio
async def test_peer_validation_with_trust_bundle_success(tmp_path, monkeypatch):
    """Client validates peer certificate against the configured trust bundle."""

    # Use force mock mode for WorkloadAPIClient
    monkeypatch.setenv("X0TTA6BL4_FORCE_MOCK_SPIFFE", "true")

    ca_pem, leaf_pem = _create_ca_and_leaf_chain()

    with tempfile.NamedTemporaryFile(mode="wb", delete=False, suffix=".pem") as f:
        f.write(ca_pem)
        bundle_path = Path(f.name)

    sock = tmp_path / "agent.sock"
    sock.write_text("")
    workload = WorkloadAPIClient(socket_path=sock, trust_bundle_path=bundle_path)

    # Create valid test certificate for client identity
    private_key = rsa.generate_private_key(public_exponent=65537, key_size=2048)
    public_key = private_key.public_key()
    cert = (
        x509.CertificateBuilder()
        .subject_name(
            x509.Name([x509.NameAttribute(NameOID.COMMON_NAME, "test.example.com")])
        )
        .issuer_name(
            x509.Name([x509.NameAttribute(NameOID.COMMON_NAME, "test.example.com")])
        )
        .public_key(public_key)
        .serial_number(x509.random_serial_number())
        .not_valid_before(datetime.utcnow())
        .not_valid_after(datetime.utcnow() + timedelta(days=1))
        .add_extension(
            x509.SubjectAlternativeName(
                [x509.UniformResourceIdentifier("spiffe://test.domain/workload/client")]
            ),
            critical=False,
        )
        .sign(private_key, hashes.SHA256())
    )
    cert_pem = cert.public_bytes(serialization.Encoding.PEM)
    key_pem = private_key.private_bytes(
        encoding=serialization.Encoding.PEM,
        format=serialization.PrivateFormat.PKCS8,
        encryption_algorithm=serialization.NoEncryption(),
    )
    svid = X509SVID(
        spiffe_id="spiffe://test.domain/workload/client",
        cert_chain=[cert_pem],
        private_key=key_pem,
        expiry=datetime.utcnow() + timedelta(hours=1),
    )

    from unittest.mock import patch

    with patch.object(workload, "fetch_x509_svid", return_value=svid):
        transport = FakePeerCertTransport(leaf_pem)

        async with SPIFFEHttpClient(
            workload_api=workload,
            transport=transport,
            expected_peer_id="spiffe://test.domain",
            verify_peer=True,
        ) as client:
            response = await client.get("https://example.test/validated")
            assert response.status_code == 200


@pytest.mark.asyncio
async def test_peer_validation_with_trust_bundle_failure(tmp_path, monkeypatch):
    """Peer certificate signed by an untrusted CA should fail validation."""

    # Use force mock mode for WorkloadAPIClient
    monkeypatch.setenv("X0TTA6BL4_FORCE_MOCK_SPIFFE", "true")

    trusted_ca_pem, _ = _create_ca_and_leaf_chain(ca_cn="Trusted CA")
    _, leaf_pem = _create_ca_and_leaf_chain(ca_cn="Untrusted CA")

    with tempfile.NamedTemporaryFile(mode="wb", delete=False, suffix=".pem") as f:
        f.write(trusted_ca_pem)
        bundle_path = Path(f.name)

    sock = tmp_path / "agent.sock"
    sock.write_text("")
    workload = WorkloadAPIClient(socket_path=sock, trust_bundle_path=bundle_path)

    # Create valid test certificate for client identity
    private_key = rsa.generate_private_key(public_exponent=65537, key_size=2048)
    public_key = private_key.public_key()
    cert = (
        x509.CertificateBuilder()
        .subject_name(
            x509.Name([x509.NameAttribute(NameOID.COMMON_NAME, "test.example.com")])
        )
        .issuer_name(
            x509.Name([x509.NameAttribute(NameOID.COMMON_NAME, "test.example.com")])
        )
        .public_key(public_key)
        .serial_number(x509.random_serial_number())
        .not_valid_before(datetime.utcnow())
        .not_valid_after(datetime.utcnow() + timedelta(days=1))
        .add_extension(
            x509.SubjectAlternativeName(
                [x509.UniformResourceIdentifier("spiffe://test.domain/workload/client")]
            ),
            critical=False,
        )
        .sign(private_key, hashes.SHA256())
    )
    cert_pem = cert.public_bytes(serialization.Encoding.PEM)
    key_pem = private_key.private_bytes(
        encoding=serialization.Encoding.PEM,
        format=serialization.PrivateFormat.PKCS8,
        encryption_algorithm=serialization.NoEncryption(),
    )
    svid = X509SVID(
        spiffe_id="spiffe://test.domain/workload/client",
        cert_chain=[cert_pem],
        private_key=key_pem,
        expiry=datetime.utcnow() + timedelta(hours=1),
    )

    from unittest.mock import patch

    with patch.object(workload, "fetch_x509_svid", return_value=svid):
        transport = FakePeerCertTransport(leaf_pem)

        async with SPIFFEHttpClient(
            workload_api=workload,
            transport=transport,
            expected_peer_id="spiffe://test.domain",
            verify_peer=True,
        ) as client:
            with pytest.raises(httpx.HTTPError):
                await client.get("https://example.test/invalid")
