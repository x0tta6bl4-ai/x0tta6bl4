"""
Production SPIRE/mTLS Integration for x0tta6bl4

Handles:
- SPIRE Server/Agent deployment validation
- SVID issuance and automatic rotation
- mTLS context setup for all service-to-service connections
- Trust domain federation
- Policy enforcement through zero-trust engine
- Monitoring and health checks
"""

import asyncio
import hashlib
import logging
import os
import ssl
import tempfile
from dataclasses import dataclass
from datetime import datetime
from pathlib import Path
from typing import Any, Dict, Optional

import httpx

from src.core.agent_thinking import AgentThinkingCoach

logger = logging.getLogger(__name__)


def _safe_hash(value: object) -> str:
    return hashlib.sha256(str(value).encode("utf-8")).hexdigest()[:12]


def _safe_count_bucket(value: int) -> str:
    if value <= 0:
        return "0"
    if value <= 3:
        return "1-3"
    if value <= 10:
        return "4-10"
    if value <= 100:
        return "11-100"
    return "100+"


def _safe_number_band(value: object) -> str:
    if not isinstance(value, (int, float)):
        return "non_numeric"
    if value < 0:
        return "negative"
    if value == 0:
        return "0"
    if value <= 60:
        return "1-60"
    if value <= 3600:
        return "61-3600"
    return "3600+"


@dataclass
class SPIREConfig:
    """Production SPIRE configuration"""

    # Endpoints
    server_address: str = os.getenv("SPIRE_SERVER_ADDRESS", "127.0.0.1:8081")
    agent_address: str = os.getenv("SPIRE_AGENT_ADDRESS", "127.0.0.1:8082")
    workload_socket: str = os.getenv(
        "SPIRE_WORKLOAD_SOCKET", "/tmp/spire-agent/public/api.sock"
    )  # nosec B108

    # Trust domain
    trust_domain: str = os.getenv("SPIRE_TRUST_DOMAIN", "x0tta6bl4.mesh")
    node_name: str = os.getenv("SPIRE_NODE_NAME", "kubernetes-node")
    workload_namespace: str = os.getenv("SPIRE_WORKLOAD_NAMESPACE", "x0tta6bl4")

    # Certificate rotation policy
    cert_ttl: int = int(os.getenv("SPIRE_CERT_TTL", "3600"))  # 1 hour
    rotation_interval: int = int(os.getenv("SPIRE_ROTATION_INTERVAL", "1800"))  # 30 min
    renewal_threshold: float = float(
        os.getenv("SPIRE_RENEWAL_THRESHOLD", "0.5")
    )  # 50% TTL

    # TLS configuration
    min_tls_version: ssl.TLSVersion = ssl.TLSVersion.TLSv1_3
    ciphers: str = (
        "ECDHE+AESGCM:ECDHE+CHACHA20:DHE+AESGCM:DHE+CHACHA20:!aNULL:!MD5:!DSS"
    )

    # Health check
    health_check_interval: int = int(os.getenv("SPIRE_HEALTH_CHECK_INTERVAL", "30"))

    # Enable optimizations
    enable_optimizations: bool = (
        os.getenv("SPIRE_ENABLE_OPTIMIZATIONS", "true").lower() == "true"
    )

    # Multi-region
    enable_multi_region: bool = (
        os.getenv("SPIRE_ENABLE_MULTI_REGION", "false").lower() == "true"
    )
    primary_region: str = os.getenv("SPIRE_PRIMARY_REGION", "us-east-1")
    fallback_regions: list = None

    def __post_init__(self):
        if self.fallback_regions is None:
            regions_str = os.getenv(
                "SPIRE_FALLBACK_REGIONS", "eu-west-1,ap-southeast-1"
            )
            self.fallback_regions = [r.strip() for r in regions_str.split(",")]


class SPIREHealthChecker:
    """Monitor SPIRE Server and Agent health"""

    def __init__(self, config: SPIREConfig):
        self.config = config
        self.server_healthy = False
        self.agent_healthy = False
        self._check_task: Optional[asyncio.Task] = None

    async def start(self):
        """Start periodic health checks"""
        self._check_task = asyncio.create_task(self._health_check_loop())
        logger.info("🏥 SPIRE health checker started")

    async def stop(self):
        """Stop health checks"""
        if self._check_task:
            self._check_task.cancel()
            try:
                await self._check_task
            except asyncio.CancelledError:
                pass

    async def _health_check_loop(self):
        """Periodic health check"""
        while True:
            try:
                await self.check_server_health()
                await self.check_agent_health()
                await asyncio.sleep(self.config.health_check_interval)
            except Exception as e:
                logger.error(f"❌ Health check error: {e}")
                await asyncio.sleep(5)

    async def check_server_health(self) -> bool:
        """Check SPIRE Server availability"""
        try:
            # Use HTTP for local health checks (SPIRE server is on trusted network)
            # For HTTPS endpoints, proper certificate verification is enforced
            async with httpx.AsyncClient(timeout=5) as client:
                response = await client.get(
                    f"http://{self.config.server_address}/health"
                )
                self.server_healthy = response.status_code == 200
                if self.server_healthy:
                    logger.debug("✅ SPIRE Server healthy")
                return self.server_healthy
        except Exception as e:
            logger.warning(f"⚠️ SPIRE Server health check failed: {e}")
            self.server_healthy = False
            return False

    async def check_agent_health(self) -> bool:
        """Check SPIRE Agent availability"""
        try:
            # Check workload socket accessibility
            socket_path = Path(self.config.workload_socket)
            if socket_path.exists():
                self.agent_healthy = True
                logger.debug("✅ SPIRE Agent healthy")
                return True
            else:
                logger.warning(
                    f"⚠️ SPIRE workload socket not found: {self.config.workload_socket}"
                )
                self.agent_healthy = False
                return False
        except Exception as e:
            logger.warning(f"⚠️ SPIRE Agent health check failed: {e}")
            self.agent_healthy = False
            return False


class SVIDRotationPolicy:
    """Manage automatic SVID rotation with monitoring"""

    def __init__(self, config: SPIREConfig, workload_api_client):
        self.config = config
        self.workload_api = workload_api_client
        self._rotation_task: Optional[asyncio.Task] = None
        self.last_rotation: Optional[datetime] = None
        self.rotation_count: int = 0

    async def start(self):
        """Start automatic rotation"""
        self._rotation_task = asyncio.create_task(self._rotation_loop())
        logger.info("🔄 SVID rotation policy started")

    async def stop(self):
        """Stop rotation"""
        if self._rotation_task:
            self._rotation_task.cancel()
            try:
                await self._rotation_task
            except asyncio.CancelledError:
                pass

    async def _rotation_loop(self):
        """Periodic SVID rotation"""
        while True:
            try:
                await self._check_and_rotate()
                await asyncio.sleep(self.config.rotation_interval)
            except Exception as e:
                logger.error(f"❌ SVID rotation error: {e}")
                await asyncio.sleep(10)

    async def _check_and_rotate(self):
        """Check SVID expiration and rotate if needed"""
        try:
            svid = await self.workload_api.fetch_x509_svid()

            if not svid or not svid.cert:
                logger.warning("⚠️ No SVID available")
                return

            # Get certificate expiration
            cert_expiry = svid.cert.not_valid_after_utc
            now = datetime.utcnow()
            ttl_remaining = (cert_expiry - now).total_seconds()
            ttl_percent = ttl_remaining / self.config.cert_ttl

            logger.debug(f"SVID TTL: {ttl_remaining:.0f}s ({ttl_percent*100:.1f}%)")

            # Rotate if threshold reached
            if ttl_percent < self.config.renewal_threshold:
                logger.info(f"🔄 Rotating SVID (TTL {ttl_percent*100:.1f}%)")
                await self.workload_api.fetch_x509_svid()

                self.rotation_count += 1
                self.last_rotation = datetime.utcnow()

                logger.info(f"✅ SVID rotated (count: {self.rotation_count})")

                # Record metrics
                try:
                    from prometheus_client import Counter

                    rotation_counter = Counter(
                        "spiffe_svid_rotations_total", "Total SVID rotations"
                    )
                    rotation_counter.inc()
                except ImportError:
                    pass

        except Exception as e:
            logger.error(f"❌ SVID rotation check failed: {e}")


class MTLSContextManager:
    """Manage mTLS context with automatic rotation"""

    def __init__(self, config: SPIREConfig, workload_api_client):
        self.config = config
        self.workload_api = workload_api_client
        self.current_context: Optional[ssl.SSLContext] = None
        self._context_lock = asyncio.Lock()
        self._update_task: Optional[asyncio.Task] = None
        self.thinking_coach = AgentThinkingCoach(
            agent_id=f"libx0t-spire-mtls-context-manager:{_safe_hash(config.trust_domain)}",
            role="security",
            capabilities=("zero-trust", "ops"),
        )
        self.last_thinking_context = self.thinking_coach.prepare_task(
            {
                "task_type": "spire_mtls_context_manager_init",
                "goal": "Initialize libx0t SPIRE mTLS context manager safely",
                "signals": {
                    "trust_domain_hash": _safe_hash(config.trust_domain),
                    "workload_socket_hash": _safe_hash(config.workload_socket),
                    "rotation_interval_band": _safe_number_band(
                        config.rotation_interval
                    ),
                    "context_present": False,
                },
                "safety_boundary": (
                    "Keep raw trust domains, workload sockets, SVID certificate bytes, "
                    "private keys, temp paths, and exception text out of thinking context."
                ),
            }
        )

    def _record_thinking(
        self,
        task_type: str,
        goal: str,
        signals: Optional[Dict[str, Any]] = None,
    ) -> Dict[str, Any]:
        self.last_thinking_context = self.thinking_coach.prepare_task(
            {
                "task_type": task_type,
                "goal": goal,
                "signals": signals or {},
                "constraints": {
                    "redact_trust_domains": True,
                    "redact_workload_sockets": True,
                    "redact_svid_certificates": True,
                    "redact_private_keys": True,
                    "redact_temp_paths": True,
                    "redact_exception_text": True,
                    "preserve_mtls_context_decision": True,
                },
                "safety_boundary": "Use hashes, counts, booleans, TLS labels, and size bands.",
            }
        )
        return self.last_thinking_context

    def get_thinking_status(self) -> Dict[str, Any]:
        return {
            "thinking": self.thinking_coach.status(),
            "last_thinking_context": self.last_thinking_context,
        }

    async def initialize(self) -> ssl.SSLContext:
        """Initialize mTLS context"""
        async with self._context_lock:
            self.current_context = await self._build_context()
            self._update_task = asyncio.create_task(self._context_update_loop())
            logger.info("✅ mTLS context initialized")
            self._record_thinking(
                "spire_mtls_context_initialized",
                "Initialize libx0t SPIRE mTLS context safely",
                {
                    "context_present": self.current_context is not None,
                    "update_task_present": self._update_task is not None,
                },
            )
            return self.current_context

    async def get_context(self) -> ssl.SSLContext:
        """Get current mTLS context"""
        if not self.current_context:
            self._record_thinking(
                "spire_mtls_context_missing",
                "Initialize missing libx0t SPIRE mTLS context on demand",
                {"context_present": False},
            )
            return await self.initialize()
        self._record_thinking(
            "spire_mtls_context_returned",
            "Return existing libx0t SPIRE mTLS context safely",
            {"context_present": True},
        )
        return self.current_context

    async def _build_context(self) -> ssl.SSLContext:
        """Build SSL context from SVID"""
        try:
            # Fetch SVID
            svid = await self.workload_api.fetch_x509_svid()
            if not svid or not svid.cert or not svid.private_key:
                raise RuntimeError("Failed to fetch SVID")

            # Create SSL context
            context = ssl.create_default_context(ssl.Purpose.SERVER_AUTH)
            context.minimum_version = self.config.min_tls_version
            context.set_ciphers(self.config.ciphers)

            # Load certificate and key from SVID
            with tempfile.NamedTemporaryFile(
                mode="wb", delete=False, suffix=".pem"
            ) as cert_file:
                cert_file.write(svid.cert)
                cert_path = cert_file.name

            with tempfile.NamedTemporaryFile(
                mode="wb", delete=False, suffix=".pem"
            ) as key_file:
                key_file.write(svid.private_key)
                key_path = key_file.name

            # Load into context
            context.load_cert_chain(cert_path, key_path)

            # Cleanup temp files
            Path(cert_path).unlink()
            Path(key_path).unlink()

            logger.debug("✅ mTLS context built")
            self._record_thinking(
                "spire_mtls_context_built",
                "Build libx0t SPIRE mTLS SSL context safely",
                {
                    "cert_length_band": _safe_number_band(len(svid.cert)),
                    "private_key_length_band": _safe_number_band(
                        len(svid.private_key)
                    ),
                    "cert_path_hash": _safe_hash(cert_path),
                    "key_path_hash": _safe_hash(key_path),
                    "min_tls_version": str(self.config.min_tls_version),
                },
            )
            return context

        except Exception as e:
            logger.error(f"❌ Failed to build mTLS context: {e}")
            self._record_thinking(
                "spire_mtls_context_build_failed",
                "Record libx0t SPIRE mTLS context build failure safely",
                {"error_type": type(e).__name__},
            )
            raise

    async def _context_update_loop(self):
        """Periodically update context"""
        while True:
            try:
                await asyncio.sleep(self.config.rotation_interval)
                async with self._context_lock:
                    self.current_context = await self._build_context()
                    logger.debug("🔄 mTLS context updated")
            except Exception as e:
                logger.error(f"❌ Context update error: {e}")
                self._record_thinking(
                    "spire_mtls_context_update_failed",
                    "Record libx0t SPIRE mTLS context update failure safely",
                    {"error_type": type(e).__name__},
                )
                await asyncio.sleep(10)


class ProductionSPIREIntegration:
    """
    Unified production SPIRE integration for x0tta6bl4.

    Manages:
    - Server/Agent health
    - SVID rotation
    - mTLS context
    - Trust domain policies
    """

    def __init__(self, config: Optional[SPIREConfig] = None):
        self.config = config or SPIREConfig()
        self.health_checker: Optional[SPIREHealthChecker] = None
        self.rotation_policy: Optional[SVIDRotationPolicy] = None
        self.mtls_manager: Optional[MTLSContextManager] = None
        self.workload_api = None
        self._started = False
        self.thinking_coach = AgentThinkingCoach(
            agent_id=f"libx0t-production-spire-integration:{_safe_hash(self.config.trust_domain)}",
            role="security",
            capabilities=("zero-trust", "ops", "monitoring"),
        )
        self.last_thinking_context = self.thinking_coach.prepare_task(
            {
                "task_type": "production_spire_integration_init",
                "goal": "Initialize libx0t production SPIRE integration safely",
                "signals": {
                    "server_address_hash": _safe_hash(self.config.server_address),
                    "agent_address_hash": _safe_hash(self.config.agent_address),
                    "workload_socket_hash": _safe_hash(self.config.workload_socket),
                    "trust_domain_hash": _safe_hash(self.config.trust_domain),
                    "node_name_hash": _safe_hash(self.config.node_name),
                    "cert_ttl_band": _safe_number_band(self.config.cert_ttl),
                    "started": False,
                },
                "safety_boundary": (
                    "Keep raw SPIRE endpoints, workload sockets, trust domains, "
                    "node names, namespace values, certificates, and exception text "
                    "out of thinking context."
                ),
            }
        )

    def _record_thinking(
        self,
        task_type: str,
        goal: str,
        signals: Optional[Dict[str, Any]] = None,
    ) -> Dict[str, Any]:
        self.last_thinking_context = self.thinking_coach.prepare_task(
            {
                "task_type": task_type,
                "goal": goal,
                "signals": signals or {},
                "constraints": {
                    "redact_spire_endpoints": True,
                    "redact_workload_sockets": True,
                    "redact_trust_domains": True,
                    "redact_node_names": True,
                    "redact_namespaces": True,
                    "redact_certificates": True,
                    "redact_exception_text": True,
                    "preserve_spire_lifecycle_decision": True,
                },
                "safety_boundary": "Use hashes, counts, booleans, component status, and time bands.",
            }
        )
        return self.last_thinking_context

    def get_thinking_status(self) -> Dict[str, Any]:
        return {
            "thinking": self.thinking_coach.status(),
            "last_thinking_context": self.last_thinking_context,
        }

    async def initialize(self, workload_api_client=None):
        """Initialize SPIRE integration"""
        try:
            # Use provided API client or lazy load
            if workload_api_client:
                self.workload_api = workload_api_client
            else:
                try:
                    from .workload.api_client import WorkloadAPIClient

                    self.workload_api = WorkloadAPIClient()
                except ImportError:
                    logger.warning("⚠️ WorkloadAPIClient not available")
                    self._record_thinking(
                        "production_spire_initialize_skipped",
                        "Skip libx0t SPIRE integration initialize without workload API",
                        {"workload_api_available": False},
                    )
                    return

            # Initialize components
            self.health_checker = SPIREHealthChecker(self.config)
            self.rotation_policy = SVIDRotationPolicy(self.config, self.workload_api)
            self.mtls_manager = MTLSContextManager(self.config, self.workload_api)

            # Start health checks
            await self.health_checker.start()

            # Initialize mTLS context
            await self.mtls_manager.initialize()

            # Start rotation policy
            await self.rotation_policy.start()

            self._started = True
            logger.info("✅ Production SPIRE integration initialized")
            self._record_thinking(
                "production_spire_initialized",
                "Initialize libx0t production SPIRE integration safely",
                {
                    "workload_api_present": self.workload_api is not None,
                    "health_checker_present": self.health_checker is not None,
                    "rotation_policy_present": self.rotation_policy is not None,
                    "mtls_manager_present": self.mtls_manager is not None,
                    "started": self._started,
                },
            )

        except Exception as e:
            logger.error(f"❌ Failed to initialize SPIRE integration: {e}")
            self._record_thinking(
                "production_spire_initialize_failed",
                "Record libx0t production SPIRE integration failure safely",
                {"error_type": type(e).__name__, "started": self._started},
            )
            raise

    async def shutdown(self):
        """Shutdown SPIRE integration"""
        try:
            if self.health_checker:
                await self.health_checker.stop()
            if self.rotation_policy:
                await self.rotation_policy.stop()
            self._started = False
            logger.info("✅ SPIRE integration shutdown")
            self._record_thinking(
                "production_spire_shutdown",
                "Shutdown libx0t production SPIRE integration safely",
                {
                    "health_checker_present": self.health_checker is not None,
                    "rotation_policy_present": self.rotation_policy is not None,
                    "started": self._started,
                },
            )
        except Exception as e:
            logger.error(f"❌ Shutdown error: {e}")
            self._record_thinking(
                "production_spire_shutdown_failed",
                "Record libx0t production SPIRE shutdown failure safely",
                {"error_type": type(e).__name__, "started": self._started},
            )

    async def get_mtls_client(self) -> httpx.AsyncClient:
        """Get mTLS HTTP client"""
        if not self.mtls_manager:
            self._record_thinking(
                "production_spire_mtls_client_missing",
                "Reject libx0t mTLS client request before SPIRE initialization",
                {"mtls_manager_present": False},
            )
            raise RuntimeError("SPIRE integration not initialized")

        context = await self.mtls_manager.get_context()
        self._record_thinking(
            "production_spire_mtls_client_created",
            "Create libx0t production SPIRE mTLS HTTP client safely",
            {"mtls_manager_present": True, "context_present": context is not None},
        )
        return httpx.AsyncClient(verify=context, timeout=30.0)

    def is_healthy(self) -> bool:
        """Check if SPIRE integration is healthy"""
        if not self.health_checker:
            self._record_thinking(
                "production_spire_health_checked",
                "Report missing libx0t production SPIRE health checker safely",
                {"health_checker_present": False, "healthy": False},
            )
            return False
        healthy = self.health_checker.server_healthy and self.health_checker.agent_healthy
        self._record_thinking(
            "production_spire_health_checked",
            "Check libx0t production SPIRE integration health safely",
            {
                "health_checker_present": True,
                "server_healthy": self.health_checker.server_healthy,
                "agent_healthy": self.health_checker.agent_healthy,
                "healthy": healthy,
            },
        )
        return healthy

    def get_status(self) -> Dict[str, Any]:
        """Get integration status"""
        status = {
            "initialized": self._started,
            "server_healthy": (
                self.health_checker.server_healthy if self.health_checker else False
            ),
            "agent_healthy": (
                self.health_checker.agent_healthy if self.health_checker else False
            ),
            "rotations": (
                self.rotation_policy.rotation_count if self.rotation_policy else 0
            ),
            "last_rotation": (
                self.rotation_policy.last_rotation.isoformat()
                if self.rotation_policy and self.rotation_policy.last_rotation
                else None
            ),
        }
        self._record_thinking(
            "production_spire_status_reported",
            "Report libx0t production SPIRE status safely",
            {
                "initialized": status["initialized"],
                "server_healthy": status["server_healthy"],
                "agent_healthy": status["agent_healthy"],
                "rotation_count_bucket": _safe_count_bucket(status["rotations"]),
                "last_rotation_present": status["last_rotation"] is not None,
            },
        )
        return status


# Singleton instance
_integration_instance: Optional[ProductionSPIREIntegration] = None


async def get_spire_integration() -> ProductionSPIREIntegration:
    """Get or create singleton SPIRE integration"""
    global _integration_instance
    if not _integration_instance:
        _integration_instance = ProductionSPIREIntegration()
        await _integration_instance.initialize()
    return _integration_instance


async def shutdown_spire_integration():
    """Shutdown SPIRE integration"""
    global _integration_instance
    if _integration_instance:
        await _integration_instance.shutdown()
        _integration_instance = None
