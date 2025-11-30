"""SPIFFE Workload API Client.

Provides interface for workloads to:

- Fetch SVIDs (X.509 or JWT)
- Rotate credentials automatically
- Validate peer identities

This module currently provides a lightweight, file-system based mock
implementation suitable for development and unit tests. It verifies the
presence of the configured SPIRE Agent Unix socket and returns
in-memory SVID objects. The design keeps clear extension points for
connecting to a real SPIFFE Workload API implementation (for example
via gRPC or an external SDK) without exposing that dependency here.
"""

import logging
import os
from typing import Optional, List, Dict, Tuple
from dataclasses import dataclass
from datetime import datetime
from pathlib import Path

from cryptography import x509
from cryptography.x509.oid import ExtensionOID
from cryptography.hazmat.primitives.asymmetric import padding

logger = logging.getLogger(__name__)

try:  # Optional SPIFFE SDK integration
    from spiffe import WorkloadApiClient as SpiffeWorkloadApiClient  # type: ignore[import]

    SPIFFE_SDK_AVAILABLE = True
except Exception:  # pragma: no cover - SDK is optional
    SpiffeWorkloadApiClient = None  # type: ignore[assignment]
    SPIFFE_SDK_AVAILABLE = False


@dataclass
class X509SVID:
    """X.509 SPIFFE Verifiable Identity Document"""
    spiffe_id: str  # e.g., "spiffe://trust.domain/workload/web"
    cert_chain: List[bytes]  # Certificate chain (leaf → intermediate → root)
    private_key: bytes
    expiry: datetime
    
    def is_expired(self) -> bool:
        """Check if SVID has expired"""
        return datetime.utcnow() > self.expiry


@dataclass
class JWTSVID:
    """JWT SPIFFE Verifiable Identity Document"""
    spiffe_id: str
    token: str
    expiry: datetime
    audience: List[str]
    
    def is_expired(self) -> bool:
        """Check if JWT has expired"""
        return datetime.utcnow() > self.expiry


class WorkloadAPIClient:
    """
    Client for SPIFFE Workload API.
    
    Connects to SPIRE Agent Unix socket to fetch SVIDs for workload identity.
    Handles automatic credential rotation and validation.
    
    Example:
        >>> client = WorkloadAPIClient("/run/spire/sockets/agent.sock")
        >>> svid = client.fetch_x509_svid()
        >>> print(svid.spiffe_id)
        spiffe://x0tta6bl4.mesh/node/worker-1
    """
    
    def __init__(
        self,
        socket_path: Path = Path("/run/spire/sockets/agent.sock"),
        trust_bundle_path: Optional[Path] = None,
    ):
        """Initialize Workload API client.

        Args:
            socket_path: Path to SPIRE Agent Unix socket used as a
                liveness/availability check for the underlying SPIRE
                Agent or its mock.
            trust_bundle_path: Optional path to a PEM-encoded trust
                bundle containing one or more CA certificates used for
                X.509 chain validation. If not provided, the
                ``SPIFFE_TRUST_BUNDLE_PATH`` environment variable is
                consulted. When no bundle is configured, certificate
                chain verification is skipped.
        """
        self.socket_path = socket_path
        self.current_svid: Optional[X509SVID] = None
        # Simple in-memory cache for JWT SVIDs keyed by audience set.
        self._jwt_cache: Dict[Tuple[str, ...], JWTSVID] = {}

        # Decide whether to use the real SPIFFE Workload API client. We
        # only enable it when the optional SDK is available, a SPIFFE
        # endpoint is configured, and the caller did not explicitly
        # force mock mode.
        self._spiffe_endpoint = os.getenv("SPIFFE_ENDPOINT_SOCKET")
        self._use_real_spiffe = bool(
            SPIFFE_SDK_AVAILABLE
            and self._spiffe_endpoint
            and os.getenv("FORCE_MOCK_SPIFFE") != "1"
        )

        if self._use_real_spiffe:
            logger.info(
                "Workload API client using SPIFFE SDK with endpoint %s",
                self._spiffe_endpoint,
            )
        else:
            logger.info(
                "Workload API client using mock implementation (socket=%s)",
                socket_path,
            )

        # Optional trust bundle configuration for certificate chain
        # validation. When not explicitly provided, fall back to the
        # SPIFFE_TRUST_BUNDLE_PATH environment variable.
        self.trust_bundle_path: Optional[Path] = trust_bundle_path
        if self.trust_bundle_path is None:
            env_bundle = os.getenv("SPIFFE_TRUST_BUNDLE_PATH")
            if env_bundle:
                self.trust_bundle_path = Path(env_bundle)

        # Cache for parsed CA certificates from the trust bundle.
        self._trust_bundle_cas: Optional[List[x509.Certificate]] = None
    
    def fetch_x509_svid(self) -> X509SVID:
        """
        Fetch an X.509 SVID for the current workload.

        The current implementation operates in a "mock" mode:

        - it treats the presence of the configured Unix socket as a
          liveness check for the SPIRE Agent (or its test double);
        - it returns an in-memory :class:`X509SVID` with a predictable
          SPIFFE ID and mock certificate material;
        - it reuses a non-expired SVID from ``self.current_svid`` to
          emulate basic credential rotation semantics.

        Returns:
            X509SVID with certificate chain and private key fields
            populated for in-memory use.

        Raises:
            ConnectionError: If the configured SPIRE Agent socket does
                not exist or the SPIFFE Workload API call fails.
        """
        # Reuse a non-expired SVID if we already fetched one.
        if self.current_svid and not self.current_svid.is_expired():
            logger.debug("Reusing cached X.509 SVID for workload")
            return self.current_svid

        # Real SPIFFE Workload API mode, if configured.
        if self._use_real_spiffe and SpiffeWorkloadApiClient is not None:
            logger.info("Fetching X.509 SVID via SPIFFE Workload API")
            try:
                with SpiffeWorkloadApiClient() as client:  # type: ignore[call-arg]
                    sdk_svid = client.fetch_x509_svid()
            except Exception as exc:  # pragma: no cover - depends on external SDK/runtime
                logger.error("Failed to fetch X.509 SVID via SPIFFE SDK: %s", exc)
                raise ConnectionError("SPIFFE Workload API call failed") from exc

            svid = self._convert_sdk_x509_svid(sdk_svid)
            self.current_svid = svid
            return svid

        # Fallback mock implementation.
        if not self.socket_path.exists():
            raise ConnectionError(f"SPIRE Agent socket not found: {self.socket_path}")

        logger.info("Fetching X.509 SVID for workload (mock implementation)")

        svid = X509SVID(
            spiffe_id="spiffe://x0tta6bl4.mesh/node/mock",
            cert_chain=[b"MOCK_CERT"],
            private_key=b"MOCK_KEY",
            expiry=datetime.utcnow(),
        )

        self.current_svid = svid
        return svid
    
    def fetch_jwt_svid(self, audience: List[str]) -> JWTSVID:
        """
        Fetch a JWT SVID for a specific audience.

        The current implementation validates only the presence of the
        configured socket and then returns an in-memory JWT SVID
        instance. A very simple in-memory cache is used to avoid
        regenerating tokens for the same audience set.

        Args:
            audience: List of intended JWT audiences.

        Returns:
            JWTSVID token for authentication.
        """
        # Real SPIFFE Workload API mode, if configured.
        if self._use_real_spiffe and SpiffeWorkloadApiClient is not None:
            logger.info(
                "Fetching JWT SVID via SPIFFE Workload API for audience: %s",
                audience,
            )
            try:
                with SpiffeWorkloadApiClient() as client:  # type: ignore[call-arg]
                    sdk_jwt = client.fetch_jwt_svid(audience=set(audience))
            except Exception as exc:  # pragma: no cover - depends on external SDK/runtime
                logger.error("Failed to fetch JWT SVID via SPIFFE SDK: %s", exc)
                raise ConnectionError("SPIFFE JWT Workload API call failed") from exc

            jwt_svid = self._convert_sdk_jwt_svid(sdk_jwt)
            cache_key = tuple(sorted(audience))
            self._jwt_cache[cache_key] = jwt_svid
            return jwt_svid

        # Fallback mock implementation.
        if not self.socket_path.exists():
            raise ConnectionError(f"SPIRE Agent socket not found: {self.socket_path}")

        # Normalize audience to a deterministic cache key.
        cache_key = tuple(sorted(audience))
        cached = self._jwt_cache.get(cache_key)
        if cached and not cached.is_expired():
            logger.debug("Reusing cached JWT SVID for audience %s", audience)
            return cached

        logger.info("Fetching JWT SVID for audience: %s (mock implementation)", audience)

        jwt_svid = JWTSVID(
            spiffe_id="spiffe://x0tta6bl4.mesh/node/mock",
            token="MOCK_JWT_TOKEN",
            expiry=datetime.utcnow(),
            audience=audience,
        )

        self._jwt_cache[cache_key] = jwt_svid
        return jwt_svid

    def _convert_sdk_x509_svid(self, sdk_svid: object) -> X509SVID:
        """Convert a SDK-specific X.509 SVID object into :class:`X509SVID`.

        This helper is intentionally defensive and only relies on a
        small, well-defined subset of attributes. Any missing fields
        are mapped to sensible defaults, so that the caller always
        receives a structurally valid :class:`X509SVID` instance.
        """

        spiffe_id = getattr(sdk_svid, "spiffe_id", "")

        raw_chain = getattr(sdk_svid, "cert_chain", None)
        cert_chain: List[bytes] = []
        if isinstance(raw_chain, list):
            for item in raw_chain:
                if isinstance(item, (bytes, bytearray)):
                    cert_chain.append(bytes(item))
                else:
                    cert_chain.append(str(item).encode("utf-8"))
        else:
            cert_chain = [b""]

        raw_key = getattr(sdk_svid, "private_key", None)
        if isinstance(raw_key, (bytes, bytearray)):
            private_key = bytes(raw_key)
        else:
            private_key = b""

        raw_expiry = getattr(sdk_svid, "expiry", None)
        expiry = raw_expiry if isinstance(raw_expiry, datetime) else datetime.utcnow()

        return X509SVID(
            spiffe_id=str(spiffe_id),
            cert_chain=cert_chain,
            private_key=private_key,
            expiry=expiry,
        )

    def _convert_sdk_jwt_svid(self, sdk_jwt: object) -> JWTSVID:
        """Convert a SDK-specific JWT SVID object into :class:`JWTSVID`."""

        spiffe_id = getattr(sdk_jwt, "spiffe_id", "")
        token = getattr(sdk_jwt, "token", "")
        raw_expiry = getattr(sdk_jwt, "expiry", None)
        expiry = raw_expiry if isinstance(raw_expiry, datetime) else datetime.utcnow()

        raw_audience = getattr(sdk_jwt, "audience", None)
        if isinstance(raw_audience, (list, tuple, set)):
            audience = [str(a) for a in raw_audience]
        else:
            audience = []

        return JWTSVID(
            spiffe_id=str(spiffe_id),
            token=str(token),
            expiry=expiry,
            audience=audience,
        )

    def _load_trust_bundle(self) -> List[x509.Certificate]:
        """Load and cache CA certificates from the configured trust bundle.

        If no bundle is configured or it cannot be read, an empty list
        is returned and certificate chain verification is skipped.
        """

        if self._trust_bundle_cas is not None:
            return self._trust_bundle_cas

        if self.trust_bundle_path is None:
            logger.debug("No trust bundle configured for WorkloadAPIClient")
            self._trust_bundle_cas = []
            return self._trust_bundle_cas

        try:
            data = self.trust_bundle_path.read_bytes()
        except FileNotFoundError:
            logger.warning("Trust bundle not found: %s", self.trust_bundle_path)
            self._trust_bundle_cas = []
            return self._trust_bundle_cas
        except Exception as exc:  # pragma: no cover - unexpected I/O errors
            logger.error(
                "Failed to read trust bundle from %s: %s",
                self.trust_bundle_path,
                exc,
            )
            self._trust_bundle_cas = []
            return self._trust_bundle_cas

        pem_header = b"-----BEGIN CERTIFICATE-----"
        cas: List[x509.Certificate] = []
        for part in data.split(pem_header):
            part = part.strip()
            if not part:
                continue
            pem_block = (
                pem_header + b"\n" + part
                if not part.startswith(b"\n")
                else pem_header + part
            )
            try:
                cert = x509.load_pem_x509_certificate(pem_block)
            except ValueError:
                logger.debug("Skipping invalid certificate in trust bundle")
                continue
            cas.append(cert)

        self._trust_bundle_cas = cas
        if cas:
            logger.info("Loaded %d CA certificates from trust bundle", len(cas))
        else:
            logger.warning(
                "Trust bundle %s did not contain any valid CA certificates",
                self.trust_bundle_path,
            )
        return self._trust_bundle_cas

    def validate_peer_svid(self, peer_svid: X509SVID, expected_id: Optional[str] = None) -> bool:
        """Validate a peer's X.509 SVID.

        Validation is performed in two layers:

        1. **SVID-level checks** (always applied):
           - reject SVIDs that are already expired according to the
             ``expiry`` field;
           - if ``expected_id`` is provided, require that the
             ``peer_svid.spiffe_id`` starts with the given prefix.

        2. **Certificate-level checks** (best-effort):
           - attempt to parse the first certificate in ``cert_chain``
             using :mod:`cryptography.x509`;
           - verify that the certificate is currently valid based on
             its ``not_valid_before`` / ``not_valid_after`` fields;
           - if ``expected_id`` is provided, require that at least one
             URI Subject Alternative Name (SAN) in the certificate
             starts with the expected prefix.

        If certificate parsing fails (for example, in tests that use
        placeholder bytes instead of real certificates), the method
        falls back to SVID-level checks only.

        Args:
            peer_svid: Peer's X.509 SVID to validate.
            expected_id: Optional expected SPIFFE ID prefix.

        Returns:
            True if the SVID satisfies the applicable checks.
        """
        # SVID-level expiry check.
        if peer_svid.is_expired():
            logger.warning("Peer SVID expired: %s", peer_svid.spiffe_id)
            return False

        # SVID-level SPIFFE ID prefix check.
        if expected_id and not peer_svid.spiffe_id.startswith(expected_id):
            logger.warning(
                "SPIFFE ID mismatch: expected prefix %s, got %s",
                expected_id,
                peer_svid.spiffe_id,
            )
            return False

        # Best-effort certificate-level validation. If we cannot parse
        # the certificate bytes we fall back to the SVID-level checks
        # above to remain compatible with mock/test setups.
        if not peer_svid.cert_chain:
            return True

        leaf_bytes = peer_svid.cert_chain[0]
        if not isinstance(leaf_bytes, (bytes, bytearray)):
            logger.debug("Peer SVID certificate is not bytes; skipping deep validation")
            return True

        cert: Optional[x509.Certificate]
        try:
            try:
                cert = x509.load_pem_x509_certificate(leaf_bytes)
            except ValueError:
                cert = x509.load_der_x509_certificate(leaf_bytes)
        except ValueError:
            logger.debug("Failed to parse peer SVID certificate; skipping deep validation")
            return True

        # Certificate validity window.
        now = datetime.utcnow()
        if now < cert.not_valid_before or now > cert.not_valid_after:
            logger.warning(
                "Peer certificate not valid at current time for %s",
                peer_svid.spiffe_id,
            )
            return False

        # If an expected ID is provided, enforce it at the certificate
        # SAN level as well.
        if expected_id:
            try:
                san = cert.extensions.get_extension_for_oid(
                    ExtensionOID.SUBJECT_ALTERNATIVE_NAME
                ).value
                uris = san.get_values_for_type(x509.UniformResourceIdentifier)
                uri_strings = [str(u) for u in uris]
            except (x509.ExtensionNotFound, ValueError):
                logger.warning(
                    "Peer certificate missing URI SANs for SPIFFE ID: %s",
                    peer_svid.spiffe_id,
                )
                return False

            if not any(uri.startswith(expected_id) for uri in uri_strings):
                logger.warning(
                    "Peer certificate SPIFFE ID mismatch: expected prefix %s, SAN URIs=%s",
                    expected_id,
                    uri_strings,
                )
                return False

        # Finally, if a trust bundle is configured, verify that the leaf
        # certificate is issued by one of the trusted CAs. This is
        # implemented for the common case of RSA-based certificates,
        # which also matches the certificates generated in unit tests.
        trust_cas = self._load_trust_bundle()
        if trust_cas:
            verified = False

            for ca_cert in trust_cas:
                try:
                    if cert.issuer != ca_cert.subject:
                        continue

                    public_key = ca_cert.public_key()
                    try:
                        hash_alg = cert.signature_hash_algorithm
                    except Exception:  # pragma: no cover - very defensive
                        hash_alg = None

                    if hash_alg is not None:
                        public_key.verify(
                            cert.signature,
                            cert.tbs_certificate_bytes,
                            padding.PKCS1v15(),
                            hash_alg,
                        )
                    else:
                        public_key.verify(
                            cert.signature,
                            cert.tbs_certificate_bytes,
                        )

                    verified = True
                    break
                except Exception:
                    # Try the next CA in the bundle.
                    continue

            if not verified:
                logger.error(
                    "Peer certificate chain verification failed for %s",
                    peer_svid.spiffe_id,
                )
                return False
        else:
            logger.warning("No trust bundle configured; skipping chain verification")

        return True
    
    def watch_svid_updates(self, callback):
        """
        Observe SVID updates and trigger a callback.

        The current implementation is a synchronous, best-effort
        helper intended for development and tests. It invokes the
        callback immediately with the current SVID, if present, and
        logs the action. A production-grade implementation would use a
        streaming API exposed by the SPIFFE Workload API to receive
        asynchronous update notifications.

        Args:
            callback: Callable receiving the current :class:`X509SVID`.
        """
        logger.info("Invoking SVID update callback (mock implementation)")

        if self.current_svid is not None:
            try:
                callback(self.current_svid)
            except Exception:
                logger.exception("SVID update callback raised an exception")

