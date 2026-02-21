"""
SPIFFE Controller - High-level Identity Management

Orchestrates SPIFFE/SPIRE components for mesh network:
- Automatic workload identity provisioning
- mTLS connection management
- Trust domain federation
- Policy enforcement

Integrates with x0tta6bl4 mesh control plane.
"""

import logging
import os
from contextlib import contextmanager
from pathlib import Path
from typing import Any, Dict, Iterator, List, Optional

import httpx

from ..agent import AttestationStrategy, SPIREAgentManager, WorkloadEntry
from ..certificate_validator import CertificateValidator
from ..mtls.tls_context import MTLSContext, TLSRole, build_mtls_context
from ..server.client import SPIREServerClient, SPIREServerEntry
from ..workload import X509SVID, WorkloadAPIClient

try:
    from ..optimizations import (MultiRegionConfig, SPIREOptimizations,
                                 SPIREPerformanceConfig)

    OPTIMIZATIONS_AVAILABLE = True
except ImportError:
    OPTIMIZATIONS_AVAILABLE = False
    SPIREOptimizations = None  # type: ignore
    SPIREPerformanceConfig = None  # type: ignore
    MultiRegionConfig = None  # type: ignore

logger = logging.getLogger(__name__)


class SPIFFEController:
    """
    High-level controller for SPIFFE identity management.

    Coordinates:
    - SPIRE Agent lifecycle
    - Workload identity provisioning
    - mTLS certificate rotation
    - Trust bundle updates

    Example:
        >>> controller = SPIFFEController()
        >>> controller.initialize()
        >>> with controller.get_mtls_http_client() as client:
        ...     response = client.get("https://peer.service.mesh")
    """

    def __init__(
        self,
        trust_domain: str = "x0tta6bl4.mesh",
        agent_config: Optional[Path] = None,
        server_address: str = "127.0.0.1:8081",
        enable_optimizations: bool = True,
    ):
        """
        Initialize SPIFFE controller.

        Args:
            trust_domain: SPIFFE trust domain
            agent_config: Path to SPIRE Agent config (auto-detected if None)
            server_address: SPIRE Server address
            enable_optimizations: Enable Paradox Zone optimizations (token caching, multi-region failover)
        """
        self.trust_domain = trust_domain
        self.server_address = server_address

        self.agent = (
            SPIREAgentManager(config_path=agent_config)
            if agent_config
            else SPIREAgentManager()
        )
        self.workload_api = WorkloadAPIClient()

        # Initialize SPIRE Server client for production integration
        self.server_client = SPIREServerClient(server_address=server_address)

        self.current_identity: Optional[X509SVID] = None
        self._auto_renew_task: Optional[Any] = None
        self._renewal_threshold: float = 0.5  # Renew when 50% of TTL remains

        # Initialize optimizations from Paradox Zone
        self.optimizations: Optional[SPIREOptimizations] = None
        if enable_optimizations and OPTIMIZATIONS_AVAILABLE:
            try:
                # Load performance config from environment or use defaults
                perf_config = SPIREPerformanceConfig(
                    max_token_ttl=os.getenv("SPIRE_MAX_TOKEN_TTL", "24h"),
                    token_cache_size=int(os.getenv("SPIRE_TOKEN_CACHE_SIZE", "10000")),
                    jwt_cache_size=int(os.getenv("SPIRE_JWT_CACHE_SIZE", "5000")),
                    concurrent_rpcs=int(os.getenv("SPIRE_CONCURRENT_RPCS", "100")),
                )

                # Load multi-region config
                multi_region = MultiRegionConfig(
                    primary_region=os.getenv("SPIRE_PRIMARY_REGION", "us-east"),
                    fallback_regions=os.getenv(
                        "SPIRE_FALLBACK_REGIONS", "eu-west,asia-pacific"
                    ).split(","),
                )

                self.optimizations = SPIREOptimizations(
                    performance_config=perf_config, multi_region_config=multi_region
                )
                logger.info("✅ SPIFFE/SPIRE optimizations enabled (Paradox Zone)")
            except Exception as e:
                logger.warning(
                    f"⚠️ Failed to initialize optimizations: {e}, continuing without optimizations"
                )

        # Initialize certificate validator
        self.cert_validator = CertificateValidator(trust_domain=trust_domain)

        logger.info(f"SPIFFE Controller initialized for trust domain: {trust_domain}")

    def initialize(
        self,
        attestation_strategy: AttestationStrategy = AttestationStrategy.JOIN_TOKEN,
        **attestation_data,
    ) -> bool:
        """
        Initialize SPIFFE infrastructure.

        Steps:
        1. Start SPIRE Agent
        2. Perform node attestation
        3. Fetch initial identity

        Args:
            attestation_strategy: Node attestation method
            **attestation_data: Strategy-specific parameters

        Returns:
            True if initialization successful
        """
        logger.info("Initializing SPIFFE infrastructure")

        # Start agent
        if not self.agent.start():
            logger.error("Failed to start SPIRE Agent")
            return False

        # Attest node
        if not self.agent.attest_node(attestation_strategy, **attestation_data):
            logger.error("Node attestation failed")
            return False

        # Fetch identity
        try:
            self.current_identity = self.workload_api.fetch_x509_svid()
            logger.info(f"Identity provisioned: {self.current_identity.spiffe_id}")
        except Exception as e:
            logger.error(f"Failed to fetch identity: {e}")
            return False

        return True

    def get_identity(self, auto_renew: bool = True) -> X509SVID:
        """
        Get current workload identity with automatic renewal.

        Args:
            auto_renew: Automatically renew if close to expiry (default: True)

        Returns:
            X509SVID for this workload

        Raises:
            RuntimeError: If identity not yet provisioned
        """
        if not self.current_identity:
            raise RuntimeError("Identity not provisioned. Call initialize() first.")

        # Check if renewal needed
        if auto_renew and self._should_renew():
            logger.info("SVID close to expiry, renewing automatically")
            self._renew_identity()

        # Check if expired (should not happen with auto_renew, but safety check)
        if self.current_identity.is_expired():
            logger.warning("Identity expired, fetching new SVID")
            self._renew_identity()

        return self.current_identity

    def _should_renew(self) -> bool:
        """Check if SVID should be renewed based on TTL threshold"""
        if not self.current_identity:
            return False

        from datetime import datetime, timedelta

        now = datetime.utcnow()
        time_until_expiry = (self.current_identity.expiry - now).total_seconds()

        # Calculate TTL
        if hasattr(self.current_identity, "ttl"):
            ttl_seconds = self.current_identity.ttl
        else:
            # Estimate TTL from expiry time
            ttl_seconds = (self.current_identity.expiry - now).total_seconds()

        # Renew if less than threshold * TTL remains
        threshold_seconds = ttl_seconds * self._renewal_threshold
        return time_until_expiry < threshold_seconds

    def _renew_identity(self):
        """Renew current identity"""
        try:
            new_identity = self.workload_api.fetch_x509_svid()
            if new_identity:
                old_id = (
                    self.current_identity.spiffe_id
                    if self.current_identity
                    else "unknown"
                )
                self.current_identity = new_identity
                logger.info(f"SVID renewed: {old_id} -> {new_identity.spiffe_id}")
        except Exception as e:
            logger.error(f"Failed to renew identity: {e}")

    def start_auto_renewal(self, check_interval: int = 60):
        """
        Start automatic SVID renewal background task.

        Args:
            check_interval: Interval in seconds to check for renewal (default: 60)
        """
        import asyncio

        async def renewal_loop():
            while True:
                try:
                    await asyncio.sleep(check_interval)
                    if self.current_identity and self._should_renew():
                        self._renew_identity()
                except asyncio.CancelledError:
                    break
                except Exception as e:
                    logger.error(f"Error in auto-renewal loop: {e}")

        try:
            loop = asyncio.get_event_loop()
            if loop.is_running():
                self._auto_renew_task = asyncio.create_task(renewal_loop())
            else:
                self._auto_renew_task = asyncio.ensure_future(renewal_loop())
            logger.info(f"✅ Auto-renewal started (check interval: {check_interval}s)")
        except Exception as e:
            logger.warning(f"Failed to start auto-renewal: {e}")

    def stop_auto_renewal(self):
        """Stop automatic SVID renewal"""
        if self._auto_renew_task:
            self._auto_renew_task.cancel()
            logger.info("Auto-renewal stopped")

    def register_workload(
        self,
        spiffe_id: str,
        selectors: Dict[str, str],
        ttl: int = 3600,
        use_server_api: bool = True,
    ) -> bool:
        """
        Register a new workload identity.

        Uses SPIRE Server API directly for production deployments.

        Args:
            spiffe_id: SPIFFE ID for workload
            selectors: Workload selectors (e.g., unix:uid, k8s:pod-name)
            ttl: SVID time-to-live in seconds
            use_server_api: Use SPIRE Server API directly (default: True)

        Returns:
            True if registration successful
        """
        if not self.current_identity:
            raise RuntimeError("Controller not initialized")

        parent_id = self.current_identity.spiffe_id

        # Use SPIRE Server API for production
        if use_server_api:
            entry_id = self.server_client.create_entry(
                spiffe_id=spiffe_id, parent_id=parent_id, selectors=selectors, ttl=ttl
            )
            return entry_id is not None

        # Fallback to agent-based registration
        entry = WorkloadEntry(
            spiffe_id=spiffe_id, parent_id=parent_id, selectors=selectors, ttl=ttl
        )

        return self.agent.register_workload(entry)

    def list_registered_workloads(self) -> List[SPIREServerEntry]:
        """
        List all registered workloads from SPIRE Server.

        Returns:
            List of SPIREServerEntry objects
        """
        return self.server_client.list_entries()

    def get_server_status(self) -> Dict[str, Any]:
        """
        Get SPIRE Server status.

        Returns:
            Dictionary with server status
        """
        return self.server_client.get_server_status()

    @contextmanager
    def get_mtls_http_client(self, **kwargs) -> Iterator[httpx.Client]:
        """
        Provides a configured httpx.Client for mTLS communication.

        This is a context manager that handles the creation and cleanup
        of the SSL context and its temporary certificate files.

        Yields:
            A configured `httpx.Client` instance ready for mTLS.
        """
        identity = self.get_identity()
        mtls_ctx: Optional[MTLSContext] = None
        try:
            mtls_ctx = build_mtls_context(identity, role=TLSRole.CLIENT)

            # If a trust bundle is available, load it for peer verification
            if self.workload_api.trust_bundle_path:
                logger.info(
                    "Loading trust bundle for peer verification from %s",
                    self.workload_api.trust_bundle_path,
                )
                mtls_ctx.ssl_context.load_verify_locations(
                    cafile=str(self.workload_api.trust_bundle_path)
                )

            with httpx.Client(verify=mtls_ctx.ssl_context, **kwargs) as client:
                yield client
        finally:
            if mtls_ctx:
                mtls_ctx.cleanup()

    def validate_peer(
        self, peer_svid: X509SVID, expected_spiffe_id: Optional[str] = None
    ) -> bool:
        """
        Validate peer's SVID using enhanced certificate validator.

        Args:
            peer_svid: Peer's X.509 SVID
            expected_spiffe_id: Expected SPIFFE ID (optional)

        Returns:
            True if peer is trusted
        """
        # Use enhanced certificate validator if certificate chain available
        if peer_svid.cert_chain:
            cert_pem = peer_svid.cert_chain[0]
            trust_bundle = (
                peer_svid.cert_chain[1:] if len(peer_svid.cert_chain) > 1 else None
            )

            is_valid, spiffe_id, error = self.cert_validator.validate_certificate(
                cert_pem, expected_spiffe_id, trust_bundle
            )

            if not is_valid:
                logger.warning(f"Certificate validation failed: {error}")
                return False

            return True

        # Fallback to original validation
        return self.workload_api.validate_peer_svid(
            peer_svid, expected_id=expected_spiffe_id
        )

    def shutdown(self) -> bool:
        """
        Gracefully shutdown SPIFFE components.

        Returns:
            True if shutdown successful
        """
        logger.info("Shutting down SPIFFE Controller")

        # Stop auto-renewal
        self.stop_auto_renewal()

        # Shutdown optimizations
        if self.optimizations:
            try:
                import asyncio

                try:
                    loop = asyncio.get_event_loop()
                    if loop.is_running():
                        asyncio.create_task(self.optimizations.shutdown())
                    else:
                        loop.run_until_complete(self.optimizations.shutdown())
                except RuntimeError:
                    # No event loop, create new one
                    asyncio.run(self.optimizations.shutdown())
            except Exception as e:
                logger.warning(f"Failed to shutdown optimizations: {e}")

        return self.agent.stop()

    def health_check(self) -> Dict[str, bool]:
        """
        Check health of SPIFFE components.

        Returns:
            Dict with component health status
        """
        endpoint = getattr(self.workload_api, "_spiffe_endpoint", None)
        socket_path: Optional[Path] = None
        if isinstance(endpoint, Path):
            socket_path = endpoint
        elif isinstance(endpoint, str):
            endpoint_str = (
                endpoint[len("unix://") :] if endpoint.startswith("unix://") else endpoint
            )
            socket_path = Path(endpoint_str)

        return {
            "agent": self.agent.health_check(),
            "identity_valid": (
                not self.current_identity.is_expired()
                if self.current_identity
                else False
            ),
            "workload_api": bool(socket_path and socket_path.exists()),
        }
