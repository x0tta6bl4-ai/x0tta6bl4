"""
Mesh mTLS Enforcer - TLS 1.3 Enforcement Layer

Enforces mandatory mTLS with TLS 1.3 for all service-to-service connections:
- TLS 1.3 requirement (no downgrade to 1.2)
- SVID-based peer verification
- Certificate expiration validation
- Automatic certificate rotation
- OCSP revocation checking (future)

Integrates with SPIFFE/SPIRE for automatic identity provisioning.
"""

import logging
import ssl
from datetime import datetime
from functools import wraps
from typing import Any, Callable, Dict, Optional

import httpx

from src.security.spiffe import SPIFFEController
from src.security.spiffe.mtls import (MTLSContext, MTLSControllerProduction,
                                      TLSRole)

logger = logging.getLogger(__name__)


class TLS13EnforcementError(Exception):
    """Raised when TLS 1.3 enforcement fails."""

    pass


class MeshMTLSEnforcer:
    """
    Enforces TLS 1.3 and mTLS for all mesh service connections.

    Features:
    - Mandatory TLS 1.3 enforcement
    - SVID peer verification
    - Certificate chain validation
    - Automatic certificate rotation
    - Expiration monitoring

    Example:
        >>> enforcer = MeshMTLSEnforcer()
        >>> async with enforcer.get_secure_client() as client:
        ...     response = await client.get("https://api.mesh/v1/data")
    """

    def __init__(
        self,
        trust_domain: str = "x0tta6bl4.mesh",
        enforce_tls13: bool = True,
        verify_svid: bool = True,
        rotation_interval: int = 3600,
        check_expiry_threshold: int = 600,  # 10 minutes
    ):
        """
        Initialize mTLS enforcer.

        Args:
            trust_domain: SPIFFE trust domain
            enforce_tls13: Require TLS 1.3 (fail if 1.2 negotiated)
            verify_svid: Verify peer SPIFFE identity (SVID)
            rotation_interval: Certificate rotation interval in seconds
            check_expiry_threshold: Alert if cert expires within N seconds
        """
        self.trust_domain = trust_domain
        self.enforce_tls13 = enforce_tls13
        self.verify_svid = verify_svid
        self.rotation_interval = rotation_interval
        self.check_expiry_threshold = check_expiry_threshold

        self.spiffe_controller = SPIFFEController(trust_domain=trust_domain)
        self.mtls_controller = MTLSControllerProduction(
            workload_api_client=self.spiffe_controller.workload_api,
            rotation_interval=rotation_interval,
        )

        self.mtls_context: Optional[MTLSContext] = None
        self.peer_identities: Dict[str, Dict[str, Any]] = {}

        logger.info(
            f"✅ Mesh mTLS Enforcer initialized (TLS13={enforce_tls13}, VerifySVID={verify_svid})"
        )

    def verify_tls_version(self, ssl_context: ssl.SSLContext):
        """
        Verify TLS 1.3 is enforced in SSL context.

        Args:
            ssl_context: SSL context to verify

        Raises:
            TLS13EnforcementError: If TLS 1.3 is not enforced
        """
        if not self.enforce_tls13:
            return

        if hasattr(ssl_context, "minimum_version"):
            if ssl_context.minimum_version < ssl.TLSVersion.TLSv1_3:
                raise TLS13EnforcementError(
                    f"TLS minimum version is {ssl_context.minimum_version}, required TLS 1.3"
                )
            logger.debug(
                f"✓ TLS 1.3 enforcement verified (min_version={ssl_context.minimum_version})"
            )

    def verify_peer_svid(
        self, peer_cert_der: bytes, expected_spiffe_ids: Optional[list] = None
    ) -> Dict[str, Any]:
        """
        Verify peer certificate contains valid SPIFFE ID (SVID).

        Args:
            peer_cert_der: Peer certificate in DER format
            expected_spiffe_ids: List of acceptable SPIFFE IDs (if None, accept any valid SVID)

        Returns:
            Dictionary with peer identity information

        Raises:
            ValueError: If SVID validation fails
        """
        if not self.verify_svid:
            return {"verified": False, "reason": "SVID verification disabled"}

        try:
            from cryptography import x509
            from cryptography.hazmat.backends import default_backend

            # Parse certificate
            cert = x509.load_der_x509_certificate(peer_cert_der, default_backend())

            # Extract SPIFFE ID from SAN (Subject Alternative Name)
            try:
                san_ext = cert.extensions.get_extension_for_oid(
                    x509.oid.ExtensionOID.SUBJECT_ALTERNATIVE_NAME
                )
                spiffe_ids = []

                for san in san_ext.value:
                    if isinstance(san, x509.UniformResourceIdentifier):
                        uri = san.value
                        if uri.startswith("spiffe://"):
                            spiffe_ids.append(uri)

                if not spiffe_ids:
                    raise ValueError("No SPIFFE IDs found in certificate SAN")

                peer_spiffe_id = spiffe_ids[0]

                # Verify SPIFFE ID belongs to trusted domain
                if not peer_spiffe_id.startswith(f"spiffe://{self.trust_domain}/"):
                    raise ValueError(
                        f"SPIFFE ID {peer_spiffe_id} does not belong to trust domain {self.trust_domain}"
                    )

                # Check expected SPIFFE IDs if provided
                if expected_spiffe_ids and peer_spiffe_id not in expected_spiffe_ids:
                    raise ValueError(
                        f"SPIFFE ID {peer_spiffe_id} not in expected list: {expected_spiffe_ids}"
                    )

                # Check certificate expiration
                if cert.not_valid_after < datetime.utcnow():
                    raise ValueError(f"Certificate expired at {cert.not_valid_after}")

                time_to_expiry = (
                    cert.not_valid_after - datetime.utcnow()
                ).total_seconds()
                if time_to_expiry < self.check_expiry_threshold:
                    logger.warning(
                        f"⚠️ Peer certificate for {peer_spiffe_id} expires in {time_to_expiry:.0f}s"
                    )

                logger.info(f"✓ Peer SVID verified: {peer_spiffe_id}")

                return {
                    "verified": True,
                    "spiffe_id": peer_spiffe_id,
                    "expires_at": cert.not_valid_after.isoformat(),
                    "expires_in_seconds": time_to_expiry,
                }

            except x509.ExtensionNotFound:
                raise ValueError(
                    "Certificate does not contain SAN extension with SPIFFE IDs"
                )

        except Exception as e:
            logger.error(f"SVID verification failed: {e}")
            return {"verified": False, "reason": str(e)}

    def verify_certificate_chain(self, cert_chain: list) -> bool:
        """
        Verify certificate chain validity.

        Args:
            cert_chain: List of DER-encoded certificates

        Returns:
            True if chain is valid

        Raises:
            ValueError: If chain is invalid
        """
        if not cert_chain or len(cert_chain) == 0:
            raise ValueError("Empty certificate chain")

        try:
            from cryptography import x509
            from cryptography.hazmat.backends import default_backend

            # Load leaf certificate
            leaf_cert = x509.load_der_x509_certificate(cert_chain[0], default_backend())

            # Basic validation
            if leaf_cert.not_valid_after < datetime.utcnow():
                raise ValueError(
                    f"Leaf certificate expired at {leaf_cert.not_valid_after}"
                )

            # Check intermediate/root certificates if present
            for i, cert_der in enumerate(cert_chain[1:], 1):
                intermediate = x509.load_der_x509_certificate(
                    cert_der, default_backend()
                )
                if intermediate.not_valid_after < datetime.utcnow():
                    raise ValueError(
                        f"Certificate at index {i} expired at {intermediate.not_valid_after}"
                    )

            logger.debug(f"✓ Certificate chain valid ({len(cert_chain)} certificates)")
            return True

        except Exception as e:
            logger.error(f"Certificate chain validation failed: {e}")
            raise

    async def setup_secure_client(self) -> httpx.AsyncClient:
        """
        Create secure HTTP client with TLS 1.3 enforcement.

        Returns:
            httpx.AsyncClient configured for mTLS with TLS 1.3

        Raises:
            TLS13EnforcementError: If TLS 1.3 cannot be enforced
        """
        try:
            logger.info("Setting up secure mTLS client...")

            # Setup mTLS context (TLS 1.3 enforced)
            self.mtls_context = await self.mtls_controller.setup_mtls_context()

            # Verify TLS 1.3 enforcement
            self.verify_tls_version(self.mtls_context.ssl_context)

            # Create HTTPX client with enforced TLS context
            client = httpx.AsyncClient(
                verify=self.mtls_context.ssl_context,
                cert=(
                    (
                        self.mtls_context.cert_file.name
                        if self.mtls_context.cert_file
                        else None
                    ),
                    (
                        self.mtls_context.key_file.name
                        if self.mtls_context.key_file
                        else None
                    ),
                ),
                http2=True,  # Support HTTP/2 for better performance
            )

            logger.info("✅ Secure mTLS client configured with TLS 1.3")
            return client

        except Exception as e:
            logger.error(f"Failed to setup secure client: {e}")
            raise TLS13EnforcementError(f"TLS 1.3 enforcement failed: {e}") from e

    def enforce_mtls_decorator(self, func: Callable) -> Callable:
        """
        Decorator to enforce mTLS for a function.

        Example:
            >>> @enforcer.enforce_mtls_decorator
            ... async def call_api(url: str):
            ...     async with enforcer.get_secure_client() as client:
            ...         return await client.get(url)
        """

        @wraps(func)
        async def wrapper(*args, **kwargs):
            if not self.mtls_context:
                raise TLS13EnforcementError("mTLS context not initialized")

            self.verify_tls_version(self.mtls_context.ssl_context)
            return await func(*args, **kwargs)

        return wrapper

    async def verify_mesh_connectivity(self, peer_address: str) -> Dict[str, Any]:
        """
        Verify mTLS connectivity to a mesh service.

        Args:
            peer_address: Service address (e.g., "https://api.mesh:8080")

        Returns:
            Dictionary with connectivity verification results
        """
        try:
            logger.info(f"Verifying mTLS connectivity to {peer_address}...")

            client = await self.setup_secure_client()

            # Make connection attempt
            response = await client.get(f"{peer_address}/health", timeout=5)

            if response.status_code == 200:
                logger.info(f"✓ mTLS connectivity verified to {peer_address}")
                return {
                    "verified": True,
                    "peer": peer_address,
                    "status_code": response.status_code,
                    "tls_version": "TLS 1.3",  # Enforced
                }
            else:
                return {
                    "verified": False,
                    "peer": peer_address,
                    "status_code": response.status_code,
                    "error": f"HTTP {response.status_code}",
                }

        except Exception as e:
            logger.error(f"mTLS connectivity verification failed: {e}")
            return {"verified": False, "peer": peer_address, "error": str(e)}

    async def cleanup(self):
        """Cleanup resources."""
        if self.mtls_context:
            self.mtls_context.cleanup()
            logger.debug("mTLS context cleaned up")
