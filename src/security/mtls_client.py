"""
mTLS Client for x0tta6bl4

Provides mTLS support for inter-service communication with:
- Certificate-based authentication
- SPIFFE workload identity integration
- Automatic certificate rotation
- Connection pooling with mTLS
"""

import asyncio
import logging
import os
import ssl
from dataclasses import dataclass, field
from datetime import datetime, timedelta
from pathlib import Path
from typing import Any, Callable, Dict, Optional

import aiohttp
from cryptography import x509
from cryptography.hazmat.backends import default_backend

logger = logging.getLogger(__name__)


@dataclass
class MTLSConfig:
    """mTLS configuration."""

    # Certificate paths
    cert_path: str = "/etc/certs/tls.crt"
    key_path: str = "/etc/certs/tls.key"
    ca_path: str = "/etc/certs/ca.crt"

    # SPIFFE workload API socket
    spiffe_socket: str = "/run/spire/sockets/agent.sock"

    # TLS settings
    min_tls_version: ssl.TLSVersion = ssl.TLSVersion.TLSv1_3
    verify_hostname: bool = True
    check_hostname: bool = True

    # Certificate rotation
    rotation_enabled: bool = True
    rotation_check_interval: int = 300  # 5 minutes
    rotation_threshold: int = 86400  # 24 hours before expiry

    # Connection settings
    connection_timeout: float = 5.0
    read_timeout: float = 30.0
    keepalive_timeout: float = 15.0

    @classmethod
    def from_env(cls) -> "MTLSConfig":
        """Create config from environment variables."""
        return cls(
            cert_path=os.getenv("MTLS_CERT_PATH", "/etc/certs/tls.crt"),
            key_path=os.getenv("MTLS_KEY_PATH", "/etc/certs/tls.key"),
            ca_path=os.getenv("MTLS_CA_PATH", "/etc/certs/ca.crt"),
            spiffe_socket=os.getenv(
                "SPIFFE_ENDPOINT_SOCKET", "/run/spire/sockets/agent.sock"
            ),
            verify_hostname=os.getenv("MTLS_VERIFY_HOSTNAME", "true").lower() == "true",
            rotation_enabled=os.getenv("MTLS_ROTATION_ENABLED", "true").lower()
            == "true",
        )


@dataclass
class CertificateInfo:
    """Certificate information."""

    subject: str
    issuer: str
    not_before: datetime
    not_after: datetime
    serial_number: int
    spiffe_id: Optional[str] = None

    @property
    def is_valid(self) -> bool:
        """Check if certificate is currently valid."""
        now = datetime.utcnow()
        return self.not_before <= now <= self.not_after

    @property
    def expires_in(self) -> timedelta:
        """Time until certificate expires."""
        return self.not_after - datetime.utcnow()

    @property
    def needs_rotation(self) -> bool:
        """Check if certificate needs rotation (< 24 hours)."""
        return self.expires_in < timedelta(hours=24)


class MTLSClient:
    """
    mTLS HTTP client with automatic certificate rotation.

    Usage:
        async with MTLSClient() as client:
            response = await client.get("https://service.internal/api/v1/data")
    """

    def __init__(self, config: Optional[MTLSConfig] = None):
        self.config = config or MTLSConfig.from_env()
        self._session: Optional[aiohttp.ClientSession] = None
        self._ssl_context: Optional[ssl.SSLContext] = None
        self._cert_info: Optional[CertificateInfo] = None
        self._rotation_task: Optional[asyncio.Task] = None
        self._lock = asyncio.Lock()

    async def __aenter__(self) -> "MTLSClient":
        await self._initialize()
        return self

    async def __aexit__(self, exc_type, exc_val, exc_tb):
        await self.close()

    async def _initialize(self):
        """Initialize mTLS client."""
        await self._load_certificates()
        self._session = await self._create_session()

        if self.config.rotation_enabled:
            self._rotation_task = asyncio.create_task(self._rotation_loop())

    async def _load_certificates(self):
        """Load certificates and create SSL context."""
        async with self._lock:
            # Check if files exist
            cert_path = Path(self.config.cert_path)
            key_path = Path(self.config.key_path)
            ca_path = Path(self.config.ca_path)

            if not all(p.exists() for p in [cert_path, key_path, ca_path]):
                logger.warning("Certificate files not found, using SPIFFE workload API")
                await self._load_spiffe_credentials()
                return

            # Create SSL context
            self._ssl_context = ssl.SSLContext(ssl.PROTOCOL_TLS_CLIENT)
            self._ssl_context.minimum_version = self.config.min_tls_version
            self._ssl_context.verify_mode = ssl.CERT_REQUIRED
            self._ssl_context.check_hostname = self.config.check_hostname

            # Load certificates
            self._ssl_context.load_cert_chain(
                certfile=str(cert_path), keyfile=str(key_path)
            )
            self._ssl_context.load_verify_locations(cafile=str(ca_path))

            # Parse certificate info
            self._cert_info = self._parse_certificate(cert_path)

            logger.info(
                f"mTLS certificates loaded: subject={self._cert_info.subject}, "
                f"expires_in={self._cert_info.expires_in}"
            )

    async def _load_spiffe_credentials(self):
        """Load credentials from SPIFFE Workload API."""
        try:
            # Try to use py-spiffe if available
            from pyspiffe.workloadapi.default_workload_api_client import \
                DefaultWorkloadApiClient
            from pyspiffe.workloadapi.x509_context import X509Context

            socket_path = self.config.spiffe_socket
            if not Path(socket_path).exists():
                raise FileNotFoundError(f"SPIFFE socket not found: {socket_path}")

            client = DefaultWorkloadApiClient(socket_path=f"unix://{socket_path}")
            x509_context: X509Context = await asyncio.to_thread(
                client.fetch_x509_context
            )

            # Get first SVID
            svid = x509_context.default_svid()

            # Create SSL context from SPIFFE credentials
            self._ssl_context = ssl.SSLContext(ssl.PROTOCOL_TLS_CLIENT)
            self._ssl_context.minimum_version = self.config.min_tls_version

            # Load from memory (cert chain and key)
            self._ssl_context.load_cert_chain(
                certfile=svid.cert_chain_path, keyfile=svid.private_key_path
            )

            # Load trust bundle
            for bundle in x509_context.x509_bundle_set.bundles.values():
                for cert in bundle.x509_authorities:
                    self._ssl_context.load_verify_locations(cadata=cert.public_bytes())

            # Store SPIFFE ID
            self._cert_info = CertificateInfo(
                subject=str(svid.spiffe_id),
                issuer="SPIFFE",
                not_before=svid.not_before,
                not_after=svid.not_after,
                serial_number=0,
                spiffe_id=str(svid.spiffe_id),
            )

            logger.info(f"SPIFFE credentials loaded: {self._cert_info.spiffe_id}")

        except ImportError:
            logger.error("py-spiffe not installed, cannot use SPIFFE workload API")
            raise
        except Exception as e:
            logger.error(f"Failed to load SPIFFE credentials: {e}")
            raise

    def _parse_certificate(self, cert_path: Path) -> CertificateInfo:
        """Parse X.509 certificate and extract info."""
        with open(cert_path, "rb") as f:
            cert_data = f.read()

        cert = x509.load_pem_x509_certificate(cert_data, default_backend())

        # Extract SPIFFE ID from SAN if present
        spiffe_id = None
        try:
            san = cert.extensions.get_extension_for_oid(
                x509.oid.ExtensionOID.SUBJECT_ALTERNATIVE_NAME
            )
            for name in san.value:
                if isinstance(name, x509.UniformResourceIdentifier):
                    if str(name.value).startswith("spiffe://"):
                        spiffe_id = str(name.value)
                        break
        except x509.ExtensionNotFound:
            pass

        return CertificateInfo(
            subject=cert.subject.rfc4514_string(),
            issuer=cert.issuer.rfc4514_string(),
            not_before=cert.not_valid_before_utc,
            not_after=cert.not_valid_after_utc,
            serial_number=cert.serial_number,
            spiffe_id=spiffe_id,
        )

    async def _create_session(self) -> aiohttp.ClientSession:
        """Create aiohttp session with mTLS."""
        connector = aiohttp.TCPConnector(
            ssl=self._ssl_context,
            limit=100,
            limit_per_host=20,
            keepalive_timeout=self.config.keepalive_timeout,
            enable_cleanup_closed=True,
        )

        timeout = aiohttp.ClientTimeout(
            total=self.config.read_timeout + self.config.connection_timeout,
            connect=self.config.connection_timeout,
            sock_read=self.config.read_timeout,
        )

        return aiohttp.ClientSession(
            connector=connector,
            timeout=timeout,
            headers={
                "User-Agent": "x0tta6bl4-mtls-client/1.0",
            },
        )

    async def _rotation_loop(self):
        """Background loop for certificate rotation."""
        while True:
            try:
                await asyncio.sleep(self.config.rotation_check_interval)

                if self._cert_info and self._cert_info.needs_rotation:
                    logger.info("Certificate rotation needed, reloading...")
                    await self._reload_certificates()

            except asyncio.CancelledError:
                break
            except Exception as e:
                logger.error(f"Certificate rotation check failed: {e}")

    async def _reload_certificates(self):
        """Reload certificates and recreate session."""
        old_session = self._session

        try:
            await self._load_certificates()
            self._session = await self._create_session()

            if old_session:
                await old_session.close()

            logger.info("Certificates rotated successfully")

        except Exception as e:
            logger.error(f"Certificate reload failed: {e}")
            # Keep old session on failure
            self._session = old_session

    async def request(self, method: str, url: str, **kwargs) -> aiohttp.ClientResponse:
        """Make HTTP request with mTLS."""
        if not self._session:
            await self._initialize()

        return await self._session.request(method, url, **kwargs)

    async def get(self, url: str, **kwargs) -> aiohttp.ClientResponse:
        """HTTP GET with mTLS."""
        return await self.request("GET", url, **kwargs)

    async def post(self, url: str, **kwargs) -> aiohttp.ClientResponse:
        """HTTP POST with mTLS."""
        return await self.request("POST", url, **kwargs)

    async def put(self, url: str, **kwargs) -> aiohttp.ClientResponse:
        """HTTP PUT with mTLS."""
        return await self.request("PUT", url, **kwargs)

    async def delete(self, url: str, **kwargs) -> aiohttp.ClientResponse:
        """HTTP DELETE with mTLS."""
        return await self.request("DELETE", url, **kwargs)

    async def close(self):
        """Close client and cleanup resources."""
        if self._rotation_task:
            self._rotation_task.cancel()
            try:
                await self._rotation_task
            except asyncio.CancelledError:
                pass

        if self._session:
            await self._session.close()

    @property
    def certificate_info(self) -> Optional[CertificateInfo]:
        """Get current certificate information."""
        return self._cert_info

    @property
    def is_healthy(self) -> bool:
        """Check if client is healthy."""
        return (
            self._session is not None
            and self._cert_info is not None
            and self._cert_info.is_valid
        )


# Global client instance (lazy initialization)
_mtls_client: Optional[MTLSClient] = None


async def get_mtls_client() -> MTLSClient:
    """Get global mTLS client instance."""
    global _mtls_client
    if _mtls_client is None:
        _mtls_client = MTLSClient()
        await _mtls_client._initialize()
    return _mtls_client


async def close_mtls_client():
    """Close global mTLS client."""
    global _mtls_client
    if _mtls_client:
        await _mtls_client.close()
        _mtls_client = None


# Context manager for easy usage
class mtls_request:
    """Context manager for mTLS requests."""

    def __init__(self, url: str, method: str = "GET", **kwargs):
        self.url = url
        self.method = method
        self.kwargs = kwargs
        self.client: Optional[MTLSClient] = None
        self.response: Optional[aiohttp.ClientResponse] = None

    async def __aenter__(self) -> aiohttp.ClientResponse:
        self.client = await get_mtls_client()
        self.response = await self.client.request(self.method, self.url, **self.kwargs)
        return self.response

    async def __aexit__(self, exc_type, exc_val, exc_tb):
        if self.response:
            self.response.close()
