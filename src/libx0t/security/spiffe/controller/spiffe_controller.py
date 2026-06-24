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
import hashlib
from contextlib import contextmanager
from pathlib import Path
from typing import Any, Dict, Iterator, List, Optional

import httpx

from src.core.agent_thinking import AgentThinkingCoach

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


def _safe_hash(value: Any) -> Optional[str]:
    if value is None:
        return None
    return hashlib.sha256(str(value).encode("utf-8")).hexdigest()


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
        self.thinking_coach = AgentThinkingCoach(
            agent_id=f"libx0t-spiffe-controller:{_safe_hash(trust_domain)}",
            role="security",
            capabilities=("zero-trust", "ops"),
        )
        self.last_thinking_context: Dict[str, Any] = {}

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
        self._record_thinking(
            "libx0t_spiffe_controller_initialized",
            "track SPIFFE controller lifecycle without exposing raw trust context",
            {
                "trust_domain_hash": _safe_hash(trust_domain),
                "server_address_hash": _safe_hash(server_address),
                "optimizations_enabled": self.optimizations is not None,
            },
        )

        logger.info(f"SPIFFE Controller initialized for trust domain: {trust_domain}")

    def _record_thinking(
        self,
        task_type: str,
        goal: str,
        extra: Optional[Dict[str, Any]] = None,
    ) -> Dict[str, Any]:
        context: Dict[str, Any] = {
            "type": task_type,
            "goal": goal,
            "identity_present": self.current_identity is not None,
            "optimizations_enabled": self.optimizations is not None,
            "trust_domain_hash": _safe_hash(self.trust_domain),
            "server_address_hash": _safe_hash(self.server_address),
            "workload_api_mock_mode": bool(
                getattr(self.workload_api, "_force_mock_spiffe", False)
            ),
            "workload_api_real_socket_verified": bool(
                getattr(self.workload_api, "_real_socket_verified", False)
            ),
            "constraints": {
                "require_real_spire_for_readiness": True,
                "mock_is_not_spire_evidence": True,
                "redact_raw_spiffe_ids": True,
                "redact_certificate_payloads": True,
                "redact_raw_paths": True,
            },
            "safety_boundary": (
                "Controller-local state is not proof of workload SVID trust "
                "finality, mTLS dataplane delivery, customer traffic, or "
                "production readiness."
            ),
        }
        if extra:
            context.update(extra)
        self.last_thinking_context = self.thinking_coach.prepare_task(context)
        return self.last_thinking_context

    def get_thinking_status(self) -> Dict[str, Any]:
        """Expose thinking profile and latest redacted controller context."""
        return {
            "thinking": self.thinking_coach.status(),
            "last_thinking_context": self.last_thinking_context,
        }


    def _prepare_thinking_context(
        self,
        task_type: str,
        goal: str,
        extra: Optional[Dict[str, Any]] = None,
    ) -> None:
        safe_extra = {}
        if extra:
            for k, v in extra.items():
                if isinstance(v, (str, int, float, bool)):
                    safe_extra[k] = v
                else:
                    safe_extra[k] = str(type(v).__name__)
        self.last_thinking_context = self.thinking_coach.prepare_task(
            {
                "task_type": task_type,
                "goal": goal,
                "extra": safe_extra or {},
                "constraints": {
                    "redact_svid_certificates": True,
                    "redact_private_keys": True,
                    "redact_ca_bundles": True,
                    "redact_temp_paths": True,
                    "redact_spiffe_ids": True,
                    "redact_exception_text": True,
                },
            }
        )

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
        self._record_thinking(
            "libx0t_spiffe_controller_initialize",
            "start SPIRE agent, attest node, and fetch workload identity safely",
            {
                "attestation_strategy": attestation_strategy.value,
                "attestation_fields": sorted(str(key) for key in attestation_data),
            },
        )

        # Start agent
        if not self.agent.start():
            self._record_thinking(
                "libx0t_spiffe_controller_initialize",
                "record SPIRE agent start failure before identity provisioning",
                {"status": "agent_start_failed"},
            )
            logger.error("Failed to start SPIRE Agent")
            return False

        # Attest node
        if not self.agent.attest_node(attestation_strategy, **attestation_data):
            self._record_thinking(
                "libx0t_spiffe_controller_initialize",
                "record node attestation failure before fetching SVID",
                {
                    "status": "attestation_failed",
                    "attestation_strategy": attestation_strategy.value,
                },
            )
            logger.error("Node attestation failed")
            return False

        # Fetch identity
        try:
            self.current_identity = self.workload_api.fetch_x509_svid()
            self._record_thinking(
                "libx0t_spiffe_controller_initialize",
                "record local identity provisioning without raw SVID material",
                {
                    "status": "identity_provisioned",
                    "identity_hash": _safe_hash(
                        getattr(self.current_identity, "spiffe_id", None)
                    ),
                    "cert_chain_count": len(
                        getattr(self.current_identity, "cert_chain", []) or []
                    ),
                },
            )
            logger.info(f"Identity provisioned: {self.current_identity.spiffe_id}")
        except Exception as e:
            self._record_thinking(
                "libx0t_spiffe_controller_initialize",
                "record identity fetch failure without exposing error text",
                {"status": "identity_fetch_failed", "error_type": type(e).__name__},
            )
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
            self._record_thinking(
                "libx0t_spiffe_controller_get_identity",
                "reject identity access before provisioning",
                {"status": "identity_missing", "auto_renew": bool(auto_renew)},
            )
            raise RuntimeError("Identity not provisioned. Call initialize() first.")

        # Check if renewal needed
        if auto_renew and self._should_renew():
            logger.info("SVID close to expiry, renewing automatically")
            self._renew_identity()

        # Check if expired (should not happen with auto_renew, but safety check)
        if self.current_identity.is_expired():
            logger.warning("Identity expired, fetching new SVID")
            self._renew_identity()

        self._record_thinking(
            "libx0t_spiffe_controller_get_identity",
            "return current identity after renewal checks without raw SVID material",
            {
                "status": "identity_available",
                "auto_renew": bool(auto_renew),
                "identity_hash": _safe_hash(
                    getattr(self.current_identity, "spiffe_id", None)
                ),
                "identity_expired": bool(self.current_identity.is_expired()),
            },
        )
        return self.current_identity

    def _should_renew(self) -> bool:
        """Check if SVID should be renewed based on TTL threshold"""
        if not self.current_identity:
            return False

        from datetime import datetime

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
                self._record_thinking(
                    "libx0t_spiffe_controller_renew_identity",
                    "record identity renewal without exposing old or new SPIFFE ID",
                    {
                        "status": "renewed",
                        "old_identity_hash": _safe_hash(old_id),
                        "new_identity_hash": _safe_hash(new_identity.spiffe_id),
                    },
                )
                logger.info(f"SVID renewed: {old_id} -> {new_identity.spiffe_id}")
        except Exception as e:
            self._record_thinking(
                "libx0t_spiffe_controller_renew_identity",
                "record identity renewal failure without exposing error text",
                {"status": "renewal_failed", "error_type": type(e).__name__},
            )
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
            self._record_thinking(
                "libx0t_spiffe_controller_auto_renewal",
                "start identity renewal loop with bounded check interval",
                {"status": "started", "check_interval_seconds": int(check_interval)},
            )
            logger.info(f"✅ Auto-renewal started (check interval: {check_interval}s)")
        except Exception as e:
            self._record_thinking(
                "libx0t_spiffe_controller_auto_renewal",
                "record auto-renewal startup failure without exposing error text",
                {"status": "start_failed", "error_type": type(e).__name__},
            )
            logger.warning(f"Failed to start auto-renewal: {e}")

    def stop_auto_renewal(self):
        """Stop automatic SVID renewal"""
        if self._auto_renew_task:
            self._auto_renew_task.cancel()
            self._record_thinking(
                "libx0t_spiffe_controller_auto_renewal",
                "stop identity renewal loop",
                {"status": "stopped"},
            )
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
            self._record_thinking(
                "libx0t_spiffe_controller_register_workload",
                "reject workload registration before controller identity exists",
                {"status": "controller_not_initialized"},
            )
            raise RuntimeError("Controller not initialized")

        parent_id = self.current_identity.spiffe_id
        self._record_thinking(
            "libx0t_spiffe_controller_register_workload",
            "register workload identity without raw SPIFFE IDs or selectors in status",
            {
                "spiffe_id_hash": _safe_hash(spiffe_id),
                "parent_id_hash": _safe_hash(parent_id),
                "selector_count": len(selectors),
                "ttl_seconds": int(ttl),
                "use_server_api": bool(use_server_api),
            },
        )

        # Use SPIRE Server API for production
        if use_server_api:
            entry_id = self.server_client.create_entry(
                spiffe_id=spiffe_id, parent_id=parent_id, selectors=selectors, ttl=ttl
            )
            self._record_thinking(
                "libx0t_spiffe_controller_register_workload",
                "record SPIRE server API workload registration result",
                {"status": "registered" if entry_id is not None else "failed"},
            )
            return entry_id is not None

        # Fallback to agent-based registration
        entry = WorkloadEntry(
            spiffe_id=spiffe_id, parent_id=parent_id, selectors=selectors, ttl=ttl
        )

        registered = self.agent.register_workload(entry)
        self._record_thinking(
            "libx0t_spiffe_controller_register_workload",
            "record SPIRE agent CLI workload registration result",
            {"status": "registered" if registered else "failed"},
        )
        return registered

    def list_registered_workloads(self) -> List[SPIREServerEntry]:
        """
        List all registered workloads from SPIRE Server.

        Returns:
            List of SPIREServerEntry objects
        """
        entries = self.server_client.list_entries()
        self._record_thinking(
            "libx0t_spiffe_controller_list_workloads",
            "list registered workloads without exposing raw SPIFFE IDs",
            {"status": "listed", "workload_count": len(entries)},
        )
        return entries

    def get_server_status(self) -> Dict[str, Any]:
        """
        Get SPIRE Server status.

        Returns:
            Dictionary with server status
        """
        status = self.server_client.get_server_status()
        self._record_thinking(
            "libx0t_spiffe_controller_server_status",
            "record SPIRE server status keys without exposing endpoint details",
            {"status_keys": sorted(str(key) for key in status)},
        )
        return status

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
            self._record_thinking(
                "libx0t_spiffe_controller_mtls_client",
                "build mTLS client context without exposing certificate payloads",
                {
                    "identity_hash": _safe_hash(getattr(identity, "spiffe_id", None)),
                    "extra_option_count": len(kwargs),
                },
            )
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
        self._record_thinking(
            "libx0t_spiffe_controller_validate_peer",
            "validate peer SVID without exposing peer certificate or SPIFFE ID",
            {
                "peer_spiffe_id_hash": _safe_hash(
                    getattr(peer_svid, "spiffe_id", None)
                ),
                "expected_spiffe_id_hash": _safe_hash(expected_spiffe_id),
                "expected_spiffe_id_present": bool(expected_spiffe_id),
                "cert_chain_count": len(peer_svid.cert_chain or []),
            },
        )
        if peer_svid.cert_chain:
            cert_pem = peer_svid.cert_chain[0]
            trust_bundle = (
                peer_svid.cert_chain[1:] if len(peer_svid.cert_chain) > 1 else None
            )

            is_valid, spiffe_id, error = self.cert_validator.validate_certificate(
                cert_pem, expected_spiffe_id, trust_bundle
            )

            if not is_valid:
                self._record_thinking(
                    "libx0t_spiffe_controller_validate_peer",
                    "record certificate validator rejection",
                    {"status": "invalid_certificate"},
                )
                logger.warning(f"Certificate validation failed: {error}")
                return False

            self._record_thinking(
                "libx0t_spiffe_controller_validate_peer",
                "record certificate validator acceptance",
                {"status": "valid_certificate"},
            )
            return True

        # Fallback to original validation
        valid = self.workload_api.validate_peer_svid(
            peer_svid, expected_id=expected_spiffe_id
        )
        self._record_thinking(
            "libx0t_spiffe_controller_validate_peer",
            "record workload API peer SVID validation result",
            {"status": "valid" if valid else "invalid"},
        )
        return valid

    def shutdown(self) -> bool:
        """
        Gracefully shutdown SPIFFE components.

        Returns:
            True if shutdown successful
        """
        logger.info("Shutting down SPIFFE Controller")
        self._record_thinking(
            "libx0t_spiffe_controller_shutdown",
            "stop renewal and SPIRE agent lifecycle without readiness overclaiming",
            {"auto_renew_task_present": self._auto_renew_task is not None},
        )

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

        stopped = self.agent.stop()
        self._record_thinking(
            "libx0t_spiffe_controller_shutdown",
            "record SPIRE agent shutdown result",
            {"status": "stopped" if stopped else "failed"},
        )
        return stopped

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

        workload_api_real = (
            not bool(getattr(self.workload_api, "_force_mock_spiffe", False))
            and bool(getattr(self.workload_api, "_real_socket_verified", False))
        )
        result = {
            "agent": self.agent.health_check(),
            "identity_valid": (
                not self.current_identity.is_expired()
                if self.current_identity
                else False
            ),
            "workload_api": workload_api_real,
            "workload_api_socket_observed": bool(socket_path and socket_path.exists()),
            "workload_api_real": workload_api_real,
        }
        self._record_thinking(
            "libx0t_spiffe_controller_health_check",
            "summarize local SPIFFE health with explicit real Workload API flag",
            {"status": dict(result)},
        )
        return result
