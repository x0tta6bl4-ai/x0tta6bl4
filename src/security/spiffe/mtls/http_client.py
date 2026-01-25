"""HTTP client with SPIFFE-based mTLS support.

This module provides a small async wrapper around :class:`httpx.AsyncClient`
that integrates SPIFFE X.509 SVIDs obtained from :class:`WorkloadAPIClient`
into a TLS context built via :func:`build_mtls_context`.

The current implementation focuses on the foundation layer:

- fetch an X.509 SVID on first use;
- build a minimal mTLS-capable :class:`ssl.SSLContext` via
  :func:`build_mtls_context`;
- transparently rotate credentials when the SVID expires;
- expose ``request``, ``get`` and ``post`` helpers.

Peer certificate extraction and full SPIFFE ID validation at the TLS
layer are intentionally left for a later hardening phase, where a
custom httpx transport will be introduced.
"""

from __future__ import annotations

import logging
from datetime import datetime, timedelta
from typing import Any, Optional

import httpx

from ..workload import WorkloadAPIClient, X509SVID
from .tls_context import MTLSContext, TLSRole, build_mtls_context

logger = logging.getLogger(__name__)


class SPIFFEPeerCertTransport(httpx.AsyncBaseTransport):
    """Transport wrapper that attaches the peer certificate to responses.

    This transport decorates another :class:`httpx.AsyncBaseTransport`
    instance and, when possible, extracts the TLS peer certificate from
    the underlying network stream. The certificate is exposed via the
    ``"peer_cert_chain"`` entry in the response ``extensions`` mapping
    as a one-element list containing the DER-encoded leaf certificate.
    """

    def __init__(self, inner: httpx.AsyncBaseTransport) -> None:
        self._inner = inner

    async def handle_async_request(self, request: httpx.Request) -> httpx.Response:  # type: ignore[override]
        response = await self._inner.handle_async_request(request)

        # Best-effort extraction based on HTTPX/HTTPCore extensions. If
        # anything here fails we simply skip attaching the certificate
        # and leave validation to higher layers.
        stream = response.extensions.get("network_stream")
        if stream is not None:
            try:
                ssl_obj = stream.get_extra_info("ssl_object")
            except Exception:  # pragma: no cover - very defensive
                ssl_obj = None

            if ssl_obj is not None:
                try:
                    der_cert = ssl_obj.getpeercert(binary_form=True)
                except Exception:  # pragma: no cover - depends on runtime
                    der_cert = None

                if der_cert:
                    # Expose the leaf certificate as a single-element
                    # chain for downstream validation.
                    response.extensions["peer_cert_chain"] = [der_cert]

        return response


class SPIFFEHttpClient:
    """Async HTTP client that integrates SPIFFE identities into mTLS.

    Example::

        async with SPIFFEHttpClient() as client:
            response = await client.get("https://example.test/health")
            assert response.status_code == 200
    """

    def __init__(
        self,
        workload_api: Optional[WorkloadAPIClient] = None,
        *,
        expected_peer_id: Optional[str] = None,
        verify_peer: bool = False,
        timeout: Optional[float] = None,
        transport: Optional[httpx.AsyncBaseTransport] = None,
    ) -> None:
        self._workload_api = workload_api or WorkloadAPIClient()
        self._expected_peer_id = expected_peer_id
        self._verify_peer = verify_peer
        self._timeout = timeout
        # Optional base transport. If not provided, a default
        # AsyncHTTPTransport wrapped in :class:`SPIFFEPeerCertTransport`
        # will be used, wired to the mTLS SSL context.
        self._base_transport = transport

        self._identity: Optional[X509SVID] = None
        self._mtls_ctx: Optional[MTLSContext] = None
        self._client: Optional[httpx.AsyncClient] = None
        self._closed = False

    @property
    def identity(self) -> Optional[X509SVID]:
        """Return the currently cached identity, if any."""

        return self._identity

    @property
    def expected_peer_id(self) -> Optional[str]:
        """Expected peer SPIFFE ID prefix used for validation hooks."""

        return self._expected_peer_id

    @property
    def verify_peer(self) -> bool:
        """Whether peer validation hooks are enabled."""

        return self._verify_peer

    async def __aenter__(self) -> "SPIFFEHttpClient":
        await self._ensure_client()
        return self

    async def __aexit__(self, exc_type, exc, tb) -> None:  # type: ignore[override]
        await self.aclose()

    async def aclose(self) -> None:
        """Close the underlying HTTP client and mark this instance closed."""

        if self._client is not None and not self._closed:
            await self._client.aclose()
            self._closed = True

    async def _ensure_client(self) -> None:
        """Ensure that SVID and HTTP client are initialized and up to date.

        If no identity is cached yet or the current SVID has expired, a
        new one is fetched from the :class:`WorkloadAPIClient` and a new
        :class:`httpx.AsyncClient` is created using an updated TLS
        context.
        """

        if self._closed:
            raise RuntimeError("SPIFFEHttpClient is already closed")

        needs_new_identity = self._identity is None or self._identity.is_expired()
        if needs_new_identity:
            logger.info("Fetching new X.509 SVID for SPIFFE HTTP client")
            self._identity = self._workload_api.fetch_x509_svid()
            self._mtls_ctx = build_mtls_context(self._identity, role=TLSRole.CLIENT)

            if self._client is not None:
                await self._client.aclose()

            # Construct a transport that is aware of the mTLS SSL
            # context. If a custom transport was provided, use it as-is
            # (primarily for tests). Otherwise, wrap an
            # AsyncHTTPTransport so that we can extract the peer
            # certificate from the underlying TLS connection.
            if self._base_transport is not None:
                transport: httpx.AsyncBaseTransport = self._base_transport
            else:
                base = httpx.AsyncHTTPTransport(verify=self._mtls_ctx.ssl_context)
                transport = SPIFFEPeerCertTransport(base)

            self._client = httpx.AsyncClient(
                timeout=self._timeout,
                transport=transport,
            )

    async def request(self, method: str, url: str, **kwargs: Any) -> httpx.Response:
        """Perform an HTTP request with SPIFFE-based TLS configuration.

        Credential rotation is handled transparently based on the
        expiry of the cached SVID. Peer validation hooks are invoked
        after the request when enabled, but do not yet inspect the
        actual TLS peer certificate at this foundation stage.
        """

        await self._ensure_client()
        assert self._client is not None

        response = await self._client.request(method, url, **kwargs)

        if self._verify_peer and self._expected_peer_id:
            self._maybe_validate_peer(response)

        return response

    async def get(self, url: str, **kwargs: Any) -> httpx.Response:
        """Shortcut for HTTP GET requests."""

        return await self.request("GET", url, **kwargs)

    async def post(self, url: str, **kwargs: Any) -> httpx.Response:
        """Shortcut for HTTP POST requests."""

        return await self.request("POST", url, **kwargs)

    def _maybe_validate_peer(self, response: httpx.Response) -> None:
        """Validate the TLS peer certificate against the expected SPIFFE ID.

        This hook expects the response ``extensions`` mapping to contain
        a ``"peer_cert_chain"`` entry with a list of certificate bytes
        (PEM or DER). Only the first element (leaf certificate) is used
        for validation. If no certificate information is available, the
        method logs the condition and returns without raising.
        """

        if not self._expected_peer_id:
            return

        chain = response.extensions.get("peer_cert_chain")
        if not chain:
            logger.info(
                "No peer certificate chain available in response extensions; "
                "skipping SPIFFE peer validation",
            )
            return

        leaf_bytes = chain[0]
        if not isinstance(leaf_bytes, (bytes, bytearray)):
            logger.warning(
                "Peer certificate in extensions is not bytes; skipping SPIFFE "
                "peer validation",
            )
            return

        # Construct a transient X509SVID from the peer certificate. The
        # SVID expiry is set to a future time so that the deeper
        # certificate-level checks drive the validation outcome.
        peer_svid = X509SVID(
            spiffe_id=self._expected_peer_id,
            cert_chain=[bytes(leaf_bytes)],
            private_key=b"",
            expiry=datetime.utcnow() + timedelta(hours=1),
        )

        if not self._workload_api.validate_peer_svid(
            peer_svid, expected_id=self._expected_peer_id
        ):
            raise httpx.HTTPError(
                f"SPIFFE peer validation failed for expected_id={self._expected_peer_id}"
            )
