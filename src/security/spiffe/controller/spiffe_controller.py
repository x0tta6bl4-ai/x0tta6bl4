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
from contextlib import contextmanager
from typing import Optional, Dict, Iterator
from pathlib import Path

import httpx

from ..workload import WorkloadAPIClient, X509SVID
from ..agent import SPIREAgentManager, WorkloadEntry, AttestationStrategy
from ..mtls.tls_context import MTLSContext, TLSRole, build_mtls_context

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
        server_address: str = "127.0.0.1:8081"
    ):
        """
        Initialize SPIFFE controller.
        
        Args:
            trust_domain: SPIFFE trust domain
            agent_config: Path to SPIRE Agent config (auto-detected if None)
            server_address: SPIRE Server address
        """
        self.trust_domain = trust_domain
        self.server_address = server_address
        
        self.agent = SPIREAgentManager(config_path=agent_config) if agent_config else SPIREAgentManager()
        self.workload_api = WorkloadAPIClient()
        
        self.current_identity: Optional[X509SVID] = None
        
        logger.info(f"SPIFFE Controller initialized for trust domain: {trust_domain}")
    
    def initialize(
        self,
        attestation_strategy: AttestationStrategy = AttestationStrategy.JOIN_TOKEN,
        **attestation_data
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
    
    def get_identity(self) -> X509SVID:
        """
        Get current workload identity.
        
        Returns:
            X509SVID for this workload
        
        Raises:
            RuntimeError: If identity not yet provisioned
        """
        if not self.current_identity:
            raise RuntimeError("Identity not provisioned. Call initialize() first.")
        
        # Check if rotation needed
        if self.current_identity.is_expired():
            logger.warning("Identity expired, fetching new SVID")
            self.current_identity = self.workload_api.fetch_x509_svid()
        
        return self.current_identity
    
    def register_workload(
        self,
        spiffe_id: str,
        selectors: Dict[str, str],
        ttl: int = 3600
    ) -> bool:
        """
        Register a new workload identity.
        
        Args:
            spiffe_id: SPIFFE ID for workload
            selectors: Workload selectors (e.g., unix:uid, k8s:pod-name)
            ttl: SVID time-to-live in seconds
        
        Returns:
            True if registration successful
        """
        if not self.current_identity:
            raise RuntimeError("Controller not initialized")
        
        entry = WorkloadEntry(
            spiffe_id=spiffe_id,
            parent_id=self.current_identity.spiffe_id,
            selectors=selectors,
            ttl=ttl
        )
        
        return self.agent.register_workload(entry)
    
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
                    self.workload_api.trust_bundle_path
                )
                mtls_ctx.ssl_context.load_verify_locations(
                    cafile=str(self.workload_api.trust_bundle_path)
                )

            with httpx.Client(verify=mtls_ctx.ssl_context, **kwargs) as client:
                yield client
        finally:
            if mtls_ctx:
                mtls_ctx.cleanup()
    
    def validate_peer(self, peer_svid: X509SVID) -> bool:
        """
        Validate peer's SVID.
        
        Args:
            peer_svid: Peer's X.509 SVID
        
        Returns:
            True if peer is trusted
        """
        return self.workload_api.validate_peer_svid(peer_svid)
    
    def shutdown(self) -> bool:
        """
        Gracefully shutdown SPIFFE components.
        
        Returns:
            True if shutdown successful
        """
        logger.info("Shutting down SPIFFE Controller")
        return self.agent.stop()
    
    def health_check(self) -> Dict[str, bool]:
        """
        Check health of SPIFFE components.
        
        Returns:
            Dict with component health status
        """
        return {
            "agent": self.agent.health_check(),
            "identity_valid": not self.current_identity.is_expired() if self.current_identity else False,
            "workload_api": self.workload_api.socket_path.exists()
        }
