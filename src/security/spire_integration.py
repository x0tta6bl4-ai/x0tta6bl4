"""
SPIRE (SPIFFE Runtime Environment) Integration Module

Provides utilities for mTLS and workload identity management using SPIRE.
Supports local testing with Docker and production deployment with SPIRE agent.
"""

import logging
import os
import socket
import time
from typing import Any, Dict, Optional

logger = logging.getLogger(__name__)

SPIRE_AGENT_AVAILABLE = False

try:
    import grpc
    try:
        # Legacy package name used in earlier revisions.
        from pyspiffe.workload import WorkloadApiClient  # type: ignore
    except ImportError:
        # Current PyPI package exports WorkloadApiClient here.
        from spiffe.workloadapi.workload_api_client import WorkloadApiClient  # type: ignore
    SPIRE_AGENT_AVAILABLE = True
except ImportError:
    logger.debug("pyspiffe not available - SPIRE integration disabled")
    WorkloadApiClient = None


class SPIREConfig:
    """Configuration for SPIRE integration"""

    def __init__(
        self,
        agent_address: str = "unix:///tmp/spire-agent/public/api.sock",
        trust_domain: str = "example.com",
        enabled: bool = True,
    ):
        self.agent_address = agent_address
        self.trust_domain = trust_domain
        # Effective enablement respects runtime capability, but still allows
        # explicit client injection/mocking when WorkloadApiClient is patched.
        self.enabled = bool(enabled and (SPIRE_AGENT_AVAILABLE or WorkloadApiClient))


class SPIREClient:
    """Client for SPIRE workload identity"""

    def __init__(self, config: Optional[SPIREConfig] = None):
        self.config = config or SPIREConfig()
        self.client: Optional[WorkloadApiClient] = None
        self._connected = False

        if self.config.enabled and SPIRE_AGENT_AVAILABLE:
            self._initialize_client()

    def _initialize_client(self):
        """Initialize SPIRE workload API client"""
        if not SPIRE_AGENT_AVAILABLE:
            logger.warning("pyspiffe not available, SPIRE integration disabled")
            return

        try:
            self.client = WorkloadApiClient(self.config.agent_address)
            self._connected = True
            logger.info(f"SPIRE client initialized at {self.config.agent_address}")
        except Exception as e:
            logger.warning(f"Failed to initialize SPIRE client: {e}")
            self._connected = False

    def is_available(self) -> bool:
        """Check if SPIRE agent is available"""
        if not self.config.enabled:
            return False

        return self._connected

    def fetch_x509_context(self) -> Optional[Dict[str, Any]]:
        """
        Fetch X.509 SVID and trust bundle from SPIRE.

        Returns:
            Dictionary with certificates and keys, or None if unavailable
        """
        if not self.is_available() or not self.client:
            return None

        try:
            svid = self.client.fetch_x509_svid()
            if svid:
                cert_bytes = self._extract_certificate_bytes(svid)
                key_bytes = self._extract_private_key_bytes(svid)
                bundle_bytes = self._extract_trust_bundle_bytes(svid) or self.fetch_x509_bundle()
                return {
                    "certificate": cert_bytes,
                    "key": key_bytes,
                    "bundle": bundle_bytes or b"",
                }
        except Exception as e:
            logger.error(f"Failed to fetch X.509 context from SPIRE: {e}")

        return None

    def fetch_x509_bundle(self) -> Optional[bytes]:
        """Fetch X.509 trust bundle from SPIRE"""
        if not self.is_available() or not self.client:
            return None

        try:
            if hasattr(self.client, "fetch_x509_bundle"):
                bundle = self.client.fetch_x509_bundle()
            elif hasattr(self.client, "fetch_x509_bundles"):
                bundle = self.client.fetch_x509_bundles()
            else:
                return None
            return self._extract_bundle_bytes(bundle)
        except Exception as e:
            logger.error(f"Failed to fetch X.509 bundle from SPIRE: {e}")

        return None

    @staticmethod
    def _extract_certificate_bytes(svid: Any) -> bytes:
        """Normalize SVID cert representation to bytes."""
        # pyspiffe-style object
        if hasattr(svid, "certificate") and isinstance(svid.certificate, (bytes, bytearray)):
            return bytes(svid.certificate)

        # spiffe package object with cert_chain (cryptography cert objects)
        cert_chain = getattr(svid, "cert_chain", None)
        if cert_chain:
            from cryptography.hazmat.primitives import serialization

            return b"".join(
                cert.public_bytes(serialization.Encoding.PEM) for cert in cert_chain
            )

        return b""

    @staticmethod
    def _extract_private_key_bytes(svid: Any) -> bytes:
        """Normalize SVID private key representation to bytes."""
        # pyspiffe-style object
        if hasattr(svid, "private_key") and isinstance(svid.private_key, (bytes, bytearray)):
            return bytes(svid.private_key)

        # spiffe package object with cryptography private key
        private_key = getattr(svid, "private_key", None)
        if private_key is not None:
            from cryptography.hazmat.primitives import serialization

            return private_key.private_bytes(
                encoding=serialization.Encoding.PEM,
                format=serialization.PrivateFormat.PKCS8,
                encryption_algorithm=serialization.NoEncryption(),
            )

        return b""

    @staticmethod
    def _extract_bundle_bytes(bundle: Any) -> Optional[bytes]:
        """Normalize bundle representation to bytes."""
        if bundle is None:
            return None
        if isinstance(bundle, (bytes, bytearray)):
            return bytes(bundle)

        # spiffe X509BundleSet / X509Bundle objects
        authorities = []
        bundles = getattr(bundle, "bundles", None)
        if bundles:
            for bundle_item in bundles:
                authorities.extend(list(getattr(bundle_item, "x509_authorities", []) or []))
        else:
            authorities.extend(list(getattr(bundle, "x509_authorities", []) or []))

        if authorities:
            from cryptography.hazmat.primitives import serialization

            return b"".join(
                cert.public_bytes(serialization.Encoding.PEM) for cert in authorities
            )
        return None

    @staticmethod
    def _extract_trust_bundle_bytes(svid: Any) -> Optional[bytes]:
        """Extract inline trust bundle when provided directly by client object."""
        trust_bundle = getattr(svid, "trust_bundle", None)
        if isinstance(trust_bundle, (bytes, bytearray)):
            return bytes(trust_bundle)
        return None


def is_spire_available() -> bool:
    """Check if SPIRE agent is available for testing"""
    if not SPIRE_AGENT_AVAILABLE:
        return False

    # Check if socket exists
    socket_path = "/tmp/spire-agent/public/api.sock"  # nosec B108
    try:
        sock = socket.socket(socket.AF_UNIX, socket.SOCK_STREAM)
        sock.settimeout(1)
        sock.connect(socket_path)
        sock.close()
        return True
    except (FileNotFoundError, ConnectionRefusedError, socket.timeout):
        return False
    except Exception:
        return False


def wait_for_spire(timeout: int = 30, check_interval: int = 1) -> bool:
    """
    Wait for SPIRE agent to become available.

    Args:
        timeout: Maximum time to wait in seconds
        check_interval: Interval between checks in seconds

    Returns:
        True if SPIRE became available, False if timeout
    """
    start = time.time()
    while time.time() - start < timeout:
        if is_spire_available():
            logger.info("SPIRE agent is available")
            return True
        time.sleep(check_interval)

    logger.warning(f"SPIRE agent not available after {timeout}s")
    return False


def get_spire_client(config: Optional[SPIREConfig] = None) -> SPIREClient:
    """Get or create SPIRE client instance"""
    return SPIREClient(config)
