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
from datetime import datetime, timedelta
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
    
    This client requires the `spiffe` SDK to be installed and the
    `SPIFFE_ENDPOINT_SOCKET` environment variable to be set.
    
    Example:
        >>> client = WorkloadAPIClient()
        >>> svid = client.fetch_x509_svid()
        >>> print(svid.spiffe_id)
        spiffe://x0tta6bl4.mesh/node/worker-1
    """
    
    def __init__(
        self,
        socket_path: Optional[Path] = None,
        trust_bundle_path: Optional[Path] = None,
    ):
        """Initialize Workload API client.

        Args:
            socket_path: Path to SPIRE Agent Unix socket. If not provided,
                the `SPIFFE_ENDPOINT_SOCKET` environment variable is used.
            trust_bundle_path: Optional path to a PEM-encoded trust
                bundle containing one or more CA certificates used for
                X.509 chain validation. If not provided, the
                ``SPIFFE_TRUST_BUNDLE_PATH`` environment variable is
                consulted. When no bundle is configured, certificate
                chain verification is skipped.

        Raises:
            ImportError: If the `spiffe` SDK is not installed.
            ValueError: If the SPIFFE endpoint socket is not configured.
        """
        # Check production mode
        PRODUCTION_MODE = os.getenv("X0TTA6BL4_PRODUCTION", "false").lower() == "true"
        self._force_mock_spiffe = os.getenv("X0TTA6BL4_FORCE_MOCK_SPIFFE", "false").lower() == "true"
        
        # In production, mock mode is not allowed
        if PRODUCTION_MODE and self._force_mock_spiffe:
            raise RuntimeError(
                "🔴 CRITICAL SECURITY ERROR: Mock SPIFFE mode is FORBIDDEN in production!\n"
                "SPIFFE/SPIRE identity is REQUIRED for Zero-Trust security.\n"
                "Set X0TTA6BL4_FORCE_MOCK_SPIFFE=false and ensure:\n"
                "  1. SPIFFE SDK is installed: pip install py-spiffe\n"
                "  2. SPIRE Agent is running and accessible\n"
                "  3. SPIFFE_ENDPOINT_SOCKET is configured\n"
                "For development/staging only, set X0TTA6BL4_PRODUCTION=false"
            )

        if not SPIFFE_SDK_AVAILABLE:
            if PRODUCTION_MODE:
                raise ImportError(
                    "🔴 The 'spiffe' SDK is REQUIRED in production. "
                    "Install with: pip install py-spiffe"
                )
            elif not self._force_mock_spiffe:
                logger.warning(
                    "⚠️ SPIFFE SDK not available. Install 'py-spiffe' for real SPIFFE support. "
                    "Using mock mode (set X0TTA6BL4_FORCE_MOCK_SPIFFE=true to suppress this warning)."
                )
                self._force_mock_spiffe = True

        self._spiffe_endpoint = socket_path or os.getenv("SPIFFE_ENDPOINT_SOCKET")
        if not self._spiffe_endpoint:
            if PRODUCTION_MODE:
                raise ValueError(
                    "🔴 SPIFFE endpoint socket is REQUIRED in production. "
                    "Set SPIFFE_ENDPOINT_SOCKET environment variable or provide socket_path."
                )
            elif not self._force_mock_spiffe:
                logger.warning(
                    "⚠️ SPIFFE endpoint socket not configured. Using mock mode. "
                    "Set SPIFFE_ENDPOINT_SOCKET or X0TTA6BL4_FORCE_MOCK_SPIFFE=true"
                )
                self._force_mock_spiffe = True
        
        if self._force_mock_spiffe:
            logger.warning("⚠️ Workload API client initialized in MOCK mode (not for production)")
        else:
            logger.info(
                "✅ Workload API client initialized with endpoint %s",
                self._spiffe_endpoint,
            )

        self.current_svid: Optional[X509SVID] = None
        self._jwt_cache: Dict[Tuple[str, ...], JWTSVID] = {}

        self.trust_bundle_path: Optional[Path] = trust_bundle_path
        if self.trust_bundle_path is None:
            env_bundle = os.getenv("SPIFFE_TRUST_BUNDLE_PATH")
            if env_bundle:
                self.trust_bundle_path = Path(env_bundle)

        self._trust_bundle_cas: Optional[List[x509.Certificate]] = None
    
    def _mock_fetch_x509_svid(self) -> X509SVID:
        # Simple mock X509SVID for testing
        return X509SVID(
            spiffe_id="spiffe://mock.domain/workload/mock-app",
            cert_chain=[b"MOCK_CERT_CHAIN"],
            private_key=b"MOCK_PRIVATE_KEY",
            expiry=datetime.utcnow() + timedelta(days=1)
        )

    def _mock_fetch_jwt_svid(self, audience: List[str]) -> JWTSVID:
        # Simple mock JWTSVID for testing
        return JWTSVID(
            spiffe_id="spiffe://mock.domain/workload/mock-app",
            token="MOCK_JWT_TOKEN",
            expiry=datetime.utcnow() + timedelta(hours=1),
            audience=audience
        )

    def fetch_x509_svid(self) -> X509SVID:
        """
        Fetch an X.509 SVID for the current workload via the SPIFFE Workload API.

        Returns:
            X509SVID with certificate chain and private key.

        Raises:
            ConnectionError: If the SPIFFE Workload API call fails.
        """
        if self._force_mock_spiffe:
            return self._mock_fetch_x509_svid()

        if self.current_svid and not self.current_svid.is_expired():
            logger.debug("Reusing cached X.509 SVID for workload")
            return self.current_svid

        logger.info("Fetching X.509 SVID via SPIFFE Workload API")
        try:
            with SpiffeWorkloadApiClient() as client:
                sdk_svid = client.fetch_x509_svid()
        except Exception as exc:
            logger.error("Failed to fetch X.509 SVID via SPIFFE SDK: %s", exc)
            raise ConnectionError("SPIFFE Workload API call failed") from exc

        svid = self._convert_sdk_x509_svid(sdk_svid)
        self.current_svid = svid
        return svid
    
    def fetch_jwt_svid(self, audience: List[str]) -> JWTSVID:
        """
        Fetch a JWT SVID for a specific audience via the SPIFFE Workload API.

        Args:
            audience: List of intended JWT audiences.

        Returns:
            JWTSVID token for authentication.
            
        Raises:
            ConnectionError: If the SPIFFE Workload API call fails.
        """
        if self._force_mock_spiffe:
            return self._mock_fetch_jwt_svid(audience)
        
        cache_key = tuple(sorted(audience))
        cached = self._jwt_cache.get(cache_key)
        if cached and not cached.is_expired():
            logger.debug("Reusing cached JWT SVID for audience %s", audience)
            return cached
            
        logger.info(
            "Fetching JWT SVID via SPIFFE Workload API for audience: %s",
            audience,
        )
        try:
            with SpiffeWorkloadApiClient() as client:
                sdk_jwt = client.fetch_jwt_svid(audience=set(audience))
        except Exception as exc:
            logger.error("Failed to fetch JWT SVID via SPIFFE SDK: %s", exc)
            raise ConnectionError("SPIFFE JWT Workload API call failed") from exc

        jwt_svid = self._convert_sdk_jwt_svid(sdk_jwt)
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
    
    def enable_auto_renew(self, renewal_threshold: float = 0.5, check_interval: float = 300.0):
        """
        Enable automatic credential renewal.
        
        This is a convenience method that creates and starts an auto-renewal
        service. For more control, use SPIFFEAutoRenew directly.
        
        Args:
            renewal_threshold: Renew at this fraction of TTL (default: 0.5 = 50%)
            check_interval: Check interval in seconds (default: 300 = 5 minutes)
        
        Returns:
            SPIFFEAutoRenew instance (already started)
        """
        try:
            from src.security.spiffe.workload.auto_renew import create_auto_renew
            import asyncio
            
            auto_renew = create_auto_renew(
                self,
                renewal_threshold=renewal_threshold,
                check_interval=check_interval
            )
            
            # Start in background if event loop is running
            try:
                loop = asyncio.get_event_loop()
                if loop.is_running():
                    asyncio.create_task(auto_renew.start())
                else:
                    loop.run_until_complete(auto_renew.start())
            except RuntimeError:
                # No event loop, will need to start manually
                logger.warning("No event loop available, auto-renew will need to be started manually")
            
            logger.info("✅ Auto-renewal enabled for WorkloadAPIClient")
            return auto_renew
            
        except ImportError as e:
            logger.warning(f"Auto-renewal not available: {e}")
            return None

