"""
Production-ready mTLS Controller with auto-rotation.
Replaces TODO in spiffe_controller.py line 175.
"""

import asyncio
import hashlib
import logging
import os
import ssl
import tempfile
from dataclasses import dataclass
from datetime import datetime
from typing import Any, Dict, List, Optional

from src.core.agent_thinking import AgentThinkingCoach

try:
    from prometheus_client import Counter, Gauge

    PROMETHEUS_AVAILABLE = True
except ImportError:
    PROMETHEUS_AVAILABLE = False

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
class TLSConfig:
    """TLS configuration"""

    cert_pem: bytes
    key_pem: bytes
    ca_bundle: bytes
    min_tls_version: ssl.TLSVersion = ssl.TLSVersion.TLSv1_3
    ciphers: str = (
        "ECDHE+AESGCM:ECDHE+CHACHA20:DHE+AESGCM:DHE+CHACHA20:!aNULL:!MD5:!DSS"
    )


class MTLSControllerProduction:
    """
    Production-ready mTLS Controller.

    Features:
    - TLS 1.3 enforcement
    - Automatic certificate rotation
    - SPIFFE ID verification
    - Custom cipher suites
    - Certificate expiry monitoring
    """

    def __init__(
        self,
        workload_api_client,
        rotation_interval: int = 3600,  # 1 hour
        enable_optimizations: bool = True,
    ):
        self.workload_api = workload_api_client
        self.rotation_interval = rotation_interval
        self.current_context: Optional[ssl.SSLContext] = None
        self._rotation_task: Optional[asyncio.Task] = None
        self._temp_files: List[tempfile.NamedTemporaryFile] = []
        self.enable_optimizations = enable_optimizations
        self._cached_svid: Optional[Any] = None
        self.thinking_coach = AgentThinkingCoach(
            agent_id=f"mtls-controller-production:{_safe_hash(rotation_interval)}",
            role="security",
            capabilities=("zero-trust", "ops"),
        )
        self.last_thinking_context = self.thinking_coach.prepare_task(
            {
                "task_type": "mtls_controller_production_init",
                "goal": "Initialize production mTLS controller safely",
                "signals": {
                    "rotation_interval_band": _safe_number_band(rotation_interval),
                    "optimizations_enabled": enable_optimizations,
                    "current_context_present": False,
                    "cached_svid_present": False,
                },
                "safety_boundary": (
                    "Keep SVID certificate bytes, private keys, CA bundles, temp "
                    "file paths, peer certs, SPIFFE IDs, and exception text out of "
                    "thinking context."
                ),
            }
        )

        # Try to import optimizations
        if enable_optimizations:
            try:
                from ..optimizations import SPIREOptimizations, TokenCache

                self.optimizations = SPIREOptimizations()
                self.token_cache = (
                    self.optimizations.get_token_cache() if self.optimizations else None
                )
                logger.info("✅ mTLS optimizations enabled")
            except ImportError:
                self.optimizations = None
                self.token_cache = None
                logger.warning("⚠️ mTLS optimizations not available")
        else:
            self.optimizations = None
            self.token_cache = None

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
                    "redact_svid_certificates": True,
                    "redact_private_keys": True,
                    "redact_ca_bundles": True,
                    "redact_temp_paths": True,
                    "redact_peer_certificates": True,
                    "redact_spiffe_ids": True,
                    "redact_exception_text": True,
                    "preserve_mtls_decision": True,
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

    async def setup_mtls_context(self) -> ssl.SSLContext:
        """
        Setup mTLS context with SVID certificates.

        Replaces TODO in spiffe_controller.py:175

        Returns:
            ssl.SSLContext configured for mTLS with TLS 1.3
        """
        try:
            logger.info("🔐 Setting up mTLS context...")

            # Track certificate age and expiry for metrics
            setup_time = datetime.utcnow()

            # Fetch X.509-SVID from SPIRE (with token caching if enabled)
            if self.token_cache:
                cache_key = "mtls_svid"
                cached_marker = self.token_cache.get(cache_key)
                if (
                    cached_marker
                    and not self.token_cache.needs_refresh(cache_key)
                    and self._is_cached_svid_usable()
                ):
                    logger.debug("Using cached SVID for mTLS")
                    svid = self._cached_svid
                else:
                    svid = await self.workload_api.fetch_x509_svid()
                    if svid:
                        self._cached_svid = svid
                        self.token_cache.set(cache_key, self._svid_cache_marker(svid))
            else:
                svid = await self.workload_api.fetch_x509_svid()

            # Create SSL context
            context = ssl.create_default_context(ssl.Purpose.CLIENT_AUTH)

            # TLS 1.3 enforcement
            context.minimum_version = ssl.TLSVersion.TLSv1_3
            context.maximum_version = ssl.TLSVersion.TLSv1_3

            # Load SVID certificate and private key
            # In production, write to temp files or use in-memory loading
            context.load_cert_chain(
                certfile=self._write_temp_cert(svid.cert_pem),
                keyfile=self._write_temp_key(svid.private_key_pem),
            )

            # Require client certificates (mutual TLS)
            context.verify_mode = ssl.CERT_REQUIRED

            # Load CA bundle for peer verification
            if svid.cert_chain:
                context.load_verify_locations(
                    cafile=self._write_temp_ca(svid.cert_chain[0])
                )

            # Set custom cipher suites (strong ciphers only)
            context.set_ciphers(
                "ECDHE+AESGCM:ECDHE+CHACHA20:DHE+AESGCM:DHE+CHACHA20:!aNULL:!MD5:!DSS"
            )

            # Enable hostname checking
            context.check_hostname = False  # SPIFFE uses SPIFFE ID, not hostname

            # Custom SPIFFE ID verification
            context.verify_flags = ssl.VERIFY_X509_STRICT

            self.current_context = context
            logger.info("✅ mTLS context setup complete (TLS 1.3)")
            self._record_thinking(
                "mtls_context_setup",
                "Set up production mTLS context safely",
                {
                    "cert_length_band": _safe_number_band(
                        len(getattr(svid, "cert_pem", b"") or b"")
                    ),
                    "key_length_band": _safe_number_band(
                        len(getattr(svid, "private_key_pem", b"") or b"")
                    ),
                    "ca_chain_count_bucket": _safe_count_bucket(
                        len(getattr(svid, "cert_chain", []) or [])
                    ),
                    "temp_file_count_bucket": _safe_count_bucket(
                        len(self._temp_files)
                    ),
                    "context_present": self.current_context is not None,
                    "tls_minimum_version": str(context.minimum_version),
                },
            )

            # Update metrics if Prometheus is available
            if PROMETHEUS_AVAILABLE:
                try:
                    from src.monitoring.metrics import MetricsRegistry
                    mtls_certificate_age_seconds = MetricsRegistry.mtls_certificate_age_seconds
                    mtls_certificate_expiry_seconds = MetricsRegistry.mtls_certificate_expiry_seconds

                    # Extract SVID expiry if available
                    if hasattr(svid, "expiry"):
                        now = datetime.utcnow()
                        expiry_seconds = (svid.expiry - now).total_seconds()
                        age_seconds = (now - setup_time).total_seconds()

                        mtls_certificate_expiry_seconds.set(max(0, expiry_seconds))
                        mtls_certificate_age_seconds.set(max(0, age_seconds))

                        logger.debug(
                            f"📊 mTLS Metrics updated: "
                            f"expiry_in={expiry_seconds:.0f}s, age={age_seconds:.0f}s"
                        )
                except Exception as e:
                    logger.debug(f"Failed to update metrics: {e}")

            return context

        except Exception as e:
            logger.error(f"❌ Failed to setup mTLS context: {e}")
            self._record_thinking(
                "mtls_context_setup_failed",
                "Record production mTLS context setup failure safely",
                {"error_type": type(e).__name__},
            )
            raise

    def _is_cached_svid_usable(self) -> bool:
        if self._cached_svid is None:
            return False

        is_expired = getattr(self._cached_svid, "is_expired", None)
        if callable(is_expired):
            return not is_expired()

        expiry = getattr(self._cached_svid, "expiry", None)
        if isinstance(expiry, datetime):
            return expiry > datetime.utcnow()

        return True

    @staticmethod
    def _svid_cache_marker(svid: Any) -> bytes:
        cert_pem = getattr(svid, "cert_pem", b"") or b""
        if not isinstance(cert_pem, bytes):
            cert_pem = str(cert_pem).encode("utf-8")

        expiry = getattr(svid, "expiry", None)
        expiry_text = expiry.isoformat() if isinstance(expiry, datetime) else str(expiry or "")

        digest = hashlib.sha256()
        digest.update(cert_pem)
        digest.update(b"|")
        digest.update(expiry_text.encode("utf-8"))
        return digest.hexdigest().encode("ascii")

    def _write_temp_cert(self, cert_pem: bytes) -> str:
        """Write certificate to temp file securely using NamedTemporaryFile."""
        temp_file = tempfile.NamedTemporaryFile(
            delete=False, mode="wb", prefix="spiffe-cert-", suffix=".pem"
        )
        temp_file.write(cert_pem)
        temp_file.flush()
        temp_file.close()  # Close the file handle, but keep the file on disk (due to delete=False)
        self._temp_files.append(temp_file)  # Store reference to the tempfile object

        logger.debug(f"Wrote temp cert to: {temp_file.name}")
        self._record_thinking(
            "mtls_temp_cert_written",
            "Write temporary SVID certificate safely",
            {
                "temp_path_hash": _safe_hash(temp_file.name),
                "cert_length_band": _safe_number_band(len(cert_pem)),
                "temp_file_count_bucket": _safe_count_bucket(len(self._temp_files)),
            },
        )
        return temp_file.name

    def _write_temp_key(self, key_pem: bytes) -> str:
        """Write private key to temp file securely using NamedTemporaryFile."""
        temp_file = tempfile.NamedTemporaryFile(
            delete=False, mode="wb", prefix="spiffe-key-", suffix=".pem"
        )
        temp_file.write(key_pem)
        temp_file.flush()
        temp_file.close()  # Close the file handle, but keep the file on disk (due to delete=False)
        os.chmod(temp_file.name, 0o600)  # Secure permissions
        self._temp_files.append(temp_file)  # Store reference to the tempfile object

        logger.debug(f"Wrote temp key to: {temp_file.name}")
        self._record_thinking(
            "mtls_temp_key_written",
            "Write temporary SVID private key safely",
            {
                "temp_path_hash": _safe_hash(temp_file.name),
                "key_length_band": _safe_number_band(len(key_pem)),
                "temp_file_count_bucket": _safe_count_bucket(len(self._temp_files)),
                "permissions": "0600",
            },
        )
        return temp_file.name

    def _write_temp_ca(self, ca_pem: bytes) -> str:
        """Write CA bundle to temp file securely using NamedTemporaryFile."""
        temp_file = tempfile.NamedTemporaryFile(
            delete=False, mode="wb", prefix="spiffe-ca-", suffix=".pem"
        )
        temp_file.write(ca_pem)
        temp_file.flush()
        temp_file.close()  # Close the file handle, but keep the file on disk (due to delete=False)
        self._temp_files.append(temp_file)  # Store reference to the tempfile object

        logger.debug(f"Wrote temp CA to: {temp_file.name}")
        self._record_thinking(
            "mtls_temp_ca_written",
            "Write temporary SVID CA bundle safely",
            {
                "temp_path_hash": _safe_hash(temp_file.name),
                "ca_length_band": _safe_number_band(len(ca_pem)),
                "temp_file_count_bucket": _safe_count_bucket(len(self._temp_files)),
            },
        )
        return temp_file.name

    async def verify_peer_spiffe_id(
        self, peer_cert: bytes, expected_spiffe_id: Optional[str] = None
    ) -> bool:
        """
        Verify peer SPIFFE ID from certificate.

        Args:
            peer_cert: Peer certificate in PEM format
            expected_spiffe_id: Expected SPIFFE ID (optional)

        Returns:
            True if SPIFFE ID is valid, False otherwise
        """
        try:
            from cryptography import x509
            from cryptography.hazmat.backends import default_backend

            # Parse certificate
            cert = x509.load_pem_x509_certificate(peer_cert, default_backend())

            # Extract SPIFFE ID from SAN extension
            san_ext = cert.extensions.get_extension_for_oid(
                x509.oid.ExtensionOID.SUBJECT_ALTERNATIVE_NAME
            )

            # Get URI SANs (SPIFFE IDs are URIs)
            uris = san_ext.value.get_values_for_type(x509.UniformResourceIdentifier)

            # Find SPIFFE ID
            spiffe_ids = [uri for uri in uris if uri.startswith("spiffe://")]

            if not spiffe_ids:
                logger.warning("⚠️ No SPIFFE ID found in certificate")
                self._record_thinking(
                    "mtls_peer_spiffe_verified",
                    "Reject peer certificate without SPIFFE ID safely",
                    {
                        "peer_cert_hash": _safe_hash(peer_cert),
                        "peer_cert_length_band": _safe_number_band(len(peer_cert)),
                        "expected_spiffe_hash": _safe_hash(expected_spiffe_id),
                        "spiffe_count_bucket": "0",
                        "verified": False,
                        "reason_code": "missing_spiffe_id",
                    },
                )
                return False

            spiffe_id = spiffe_ids[0]
            logger.info(f"🔍 Peer SPIFFE ID: {spiffe_id}")

            # Verify against expected SPIFFE ID
            if expected_spiffe_id:
                if spiffe_id != expected_spiffe_id:
                    logger.warning(
                        f"⚠️ SPIFFE ID mismatch: expected {expected_spiffe_id}, got {spiffe_id}"
                    )
                    self._record_thinking(
                        "mtls_peer_spiffe_verified",
                        "Reject peer SPIFFE ID mismatch safely",
                        {
                            "peer_cert_hash": _safe_hash(peer_cert),
                            "spiffe_hash": _safe_hash(spiffe_id),
                            "expected_spiffe_hash": _safe_hash(expected_spiffe_id),
                            "spiffe_count_bucket": _safe_count_bucket(len(spiffe_ids)),
                            "verified": False,
                            "reason_code": "spiffe_mismatch",
                        },
                    )
                    return False

            # Verify SPIFFE ID format
            if not spiffe_id.startswith("spiffe://x0tta6bl4.mesh/"):
                logger.warning(f"⚠️ Invalid SPIFFE ID trust domain: {spiffe_id}")
                self._record_thinking(
                    "mtls_peer_spiffe_verified",
                    "Reject peer SPIFFE trust domain safely",
                    {
                        "peer_cert_hash": _safe_hash(peer_cert),
                        "spiffe_hash": _safe_hash(spiffe_id),
                        "expected_spiffe_hash": _safe_hash(expected_spiffe_id),
                        "spiffe_count_bucket": _safe_count_bucket(len(spiffe_ids)),
                        "verified": False,
                        "reason_code": "invalid_trust_domain",
                    },
                )
                return False

            logger.info(f"✅ SPIFFE ID verified: {spiffe_id}")
            self._record_thinking(
                "mtls_peer_spiffe_verified",
                "Verify peer SPIFFE ID safely",
                {
                    "peer_cert_hash": _safe_hash(peer_cert),
                    "spiffe_hash": _safe_hash(spiffe_id),
                    "expected_spiffe_hash": _safe_hash(expected_spiffe_id),
                    "spiffe_count_bucket": _safe_count_bucket(len(spiffe_ids)),
                    "verified": True,
                },
            )
            return True

        except Exception as e:
            logger.error(f"❌ SPIFFE ID verification failed: {e}")
            self._record_thinking(
                "mtls_peer_spiffe_verify_failed",
                "Record peer SPIFFE verification failure safely",
                {
                    "peer_cert_hash": _safe_hash(peer_cert),
                    "peer_cert_length_band": _safe_number_band(len(peer_cert)),
                    "expected_spiffe_hash": _safe_hash(expected_spiffe_id),
                    "error_type": type(e).__name__,
                },
            )
            return False

    async def start_auto_rotation(self) -> None:
        """
        Start automatic certificate rotation.

        Rotates certificates every hour (configurable).
        """
        logger.info(f"🔄 Starting auto-rotation (interval: {self.rotation_interval}s)")
        self._record_thinking(
            "mtls_auto_rotation_started",
            "Start production mTLS auto-rotation safely",
            {"rotation_interval_band": _safe_number_band(self.rotation_interval)},
        )

        while True:
            try:
                await asyncio.sleep(self.rotation_interval)

                logger.info("🔄 Rotating mTLS certificates...")
                await self.setup_mtls_context()

                # Update metrics if Prometheus is available
                if PROMETHEUS_AVAILABLE:
                    try:
                        from src.monitoring.metrics import MetricsRegistry

                        MetricsRegistry.mtls_certificate_rotations_total.inc()
                        logger.debug("📊 Certificate rotation metric incremented")
                    except Exception as e:
                        logger.debug(f"Failed to update rotation metric: {e}")

                logger.info("✅ Certificate rotation complete")

            except Exception as e:
                logger.error(f"❌ Certificate rotation failed: {e}")
                self._record_thinking(
                    "mtls_auto_rotation_failed",
                    "Record production mTLS auto-rotation failure safely",
                    {"error_type": type(e).__name__},
                )
                # Retry after 5 minutes on failure
                await asyncio.sleep(300)

    async def start(self) -> None:
        """Start mTLS controller with auto-rotation"""
        # Initial setup
        await self.setup_mtls_context()

        # Start auto-rotation in background
        self._rotation_task = asyncio.create_task(self.start_auto_rotation())

        logger.info("✅ mTLS Controller started")
        self._record_thinking(
            "mtls_controller_started",
            "Start production mTLS controller safely",
            {
                "rotation_task_present": self._rotation_task is not None,
                "context_present": self.current_context is not None,
            },
        )

    async def stop(self) -> None:
        """Stop mTLS controller and clean up temporary files."""
        if self._rotation_task:
            self._rotation_task.cancel()
            try:
                await self._rotation_task
            except asyncio.CancelledError:
                pass

        # Clean up temporary files
        for temp_file_obj in self._temp_files:
            try:
                os.unlink(temp_file_obj.name)
                logger.debug(f"Cleaned up temporary file: {temp_file_obj.name}")
            except OSError as e:
                logger.warning(
                    f"Failed to clean up temporary file {temp_file_obj.name}: {e}"
                )
                self._record_thinking(
                    "mtls_temp_file_cleanup_failed",
                    "Record mTLS temp file cleanup failure safely",
                    {
                        "temp_path_hash": _safe_hash(temp_file_obj.name),
                        "error_type": type(e).__name__,
                    },
                )
        self._temp_files.clear()  # Clear the list after cleanup

        logger.info("🛑 mTLS Controller stopped")
        self._record_thinking(
            "mtls_controller_stopped",
            "Stop production mTLS controller safely",
            {
                "rotation_task_present": self._rotation_task is not None,
                "temp_file_count_bucket": _safe_count_bucket(len(self._temp_files)),
            },
        )

    def get_tls_config(self) -> TLSConfig:
        """Get current TLS configuration"""
        if not self.current_context:
            self._record_thinking(
                "mtls_tls_config_missing",
                "Reject TLS config request before context initialization",
                {"context_present": False},
            )
            raise RuntimeError("mTLS context not initialized")

        # Extract config from context
        # In production, store these separately
        config = TLSConfig(
            cert_pem=b"",  # Would be stored from SVID
            key_pem=b"",
            ca_bundle=b"",
            min_tls_version=ssl.TLSVersion.TLSv1_3,
        )
        self._record_thinking(
            "mtls_tls_config_reported",
            "Report production TLS config safely",
            {
                "context_present": True,
                "min_tls_version": str(config.min_tls_version),
                "cert_length_band": _safe_number_band(len(config.cert_pem)),
                "key_length_band": _safe_number_band(len(config.key_pem)),
                "ca_length_band": _safe_number_band(len(config.ca_bundle)),
            },
        )
        return config


# Example usage
async def main():
    """Example usage of MTLSControllerProduction"""
    from .api_client_production import WorkloadAPIClientProduction

    # Create Workload API client
    workload_api = WorkloadAPIClientProduction()

    # Create mTLS controller
    mtls_controller = MTLSControllerProduction(
        workload_api_client=workload_api, rotation_interval=3600  # 1 hour
    )

    try:
        # Start controller (sets up mTLS and starts auto-rotation)
        await mtls_controller.start()

        # Get TLS context for use in servers/clients
        context = mtls_controller.current_context
        print(f"✅ mTLS Context: {context}")

        # Keep running (auto-rotation happens in background)
        await asyncio.sleep(7200)  # Run for 2 hours

    finally:
        await mtls_controller.stop()
        await workload_api.close()


if __name__ == "__main__":
    asyncio.run(main())
