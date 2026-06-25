#!/usr/bin/env python3
"""
Advanced VPN Obfuscation Manager for x0tta6bl4
Manages multiple obfuscation techniques and implements rotating parameters
for better block bypass and anonymity.
"""

import logging
import hashlib
import os
import random
import time
from enum import Enum
from typing import Any, Dict, Optional

from src.coordination.events import EventBus, EventType, get_event_bus
from src.core.thinking.agent_thinking import AgentThinkingCoach
from src.services.service_event_identity import service_event_identity
from .obfuscation.domain_fronting import DomainFrontingTransport
from .obfuscation.faketls import FakeTLSTransport
from .obfuscation.shadowsocks import ShadowsocksTransport
from .obfuscation.traffic_shaping import TrafficProfile, TrafficShaper

try:
    from src.anti_censorship.stego_mesh import StegoMeshProtocol

    STEGO_MESH_AVAILABLE = True
except ImportError:
    STEGO_MESH_AVAILABLE = False
    logger = logging.getLogger(__name__)
    logger.warning("StegoMeshProtocol not available, STEGOMESH obfuscation disabled")

logger = logging.getLogger(__name__)

# Environment variable for master key
OBFUSCATION_MASTER_KEY_ENV = "VPN_OBFUSCATION_MASTER_KEY"
_SERVICE_AGENT = "vpn-obfuscation-manager"
_SERVICE_LAYER = "network_vpn_obfuscation_local_evidence"
VPN_OBFUSCATION_MANAGER_CLAIM_BOUNDARY = (
    "Local VPN obfuscation manager evidence only. It records local method "
    "selection, rotation, payload-size buckets, local entropy/size metrics, "
    "duration, and redacted service identity presence; it does not expose "
    "payload bytes, SNI/domain parameters, master keys, or prove DPI bypass, "
    "censorship bypass, anonymity, remote reachability, packet delivery, "
    "provider health, client installation, or production customer traffic use."
)


def _byte_count_bucket(value: Any) -> str:
    if not isinstance(value, int) or value <= 0:
        return "zero"
    if value <= 64:
        return "tiny"
    if value <= 512:
        return "small"
    if value <= 1500:
        return "mtu"
    if value <= 8192:
        return "chunk"
    return "large"


def _sha256_prefix(value: Any) -> Optional[str]:
    text = str(value or "").strip()
    if not text:
        return None
    return hashlib.sha256(text.encode("utf-8", errors="replace")).hexdigest()[:16]


class ObfuscationMethod(Enum):
    """Available obfuscation methods for VPN."""

    NONE = "none"
    FAKETLS = "faketls"
    SHADOWSOCKS = "shadowsocks"
    DOMAIN_FRONTING = "domain_fronting"
    STEGOMESH = "stegomesh"
    HYBRID = "hybrid"  # Combination of multiple methods


class RotationStrategy(Enum):
    """Parameter rotation strategies."""

    FIXED = "fixed"
    RANDOM = "random"
    ROUND_ROBIN = "round_robin"
    TIME_BASED = "time_based"


# Rotating SNI options (popular CDN and trusted domains)
# NOTE: Google/YouTube domains excluded to prevent conflicts with Google Cloud API
ROTATING_SNI_OPTIONS = [
    "www.cloudflare.com",
    "www.microsoft.com",
    "www.apple.com",
    "www.amazon.com",
    "www.netflix.com",
    "www.reddit.com",
    "www.twitter.com",
    "www.linkedin.com",
    "www.github.com",
    "www.gitlab.com",
    "www.bitbucket.org",
    "www.dropbox.com",
    "www.box.com",
    "www.icloud.com",
    "www.onedrive.com",
    "www.office.com",
    "www.spotify.com",  # Added for Spotify compatibility
    "www.scdn.co",  # Spotify CDN
    "open.spotify.com",  # Spotify web player
    "api.spotify.com",  # Spotify API
    "www.cloudflare.net",
    "www.akamai.com",
    "www.fastly.com",
]  # Excluded: google.com, youtube.com, drive.google.com (conflict with Google Cloud)

# Rotating TLS fingerprints options (mimic real browsers)
ROTATING_FINGERPRINT_OPTIONS = [
    "chrome",
    "firefox",
    "safari",
    "edge",
    "ios",
    "android",
    "random",
]

# Rotating SpiderX paths (legitimate-looking HTTP paths)
ROTATING_SPIDERX_OPTIONS = [
    "/",
    "/index.html",
    "/about",
    "/contact",
    "/blog",
    "/products",
    "/pricing",
    "/download",
    "/support",
    "/docs",
    "/api/v1/health",
    "/api/v1/status",
    "/cdn-cgi/trace",
    "/robots.txt",
    "/sitemap.xml",
    "/favicon.ico",
    "/static/css/main.css",
    "/static/js/app.js",
    "/images/banner.jpg",
    "/watch?v=dQw4w9WgXcQ",  # Rick Astley classic
]


class VPNObfuscationManager:
    """
    Advanced VPN obfuscation manager with rotating parameter support.
    """

    def __init__(
        self,
        master_key: Optional[bytes] = None,
        event_bus: Optional[EventBus] = None,
        event_project_root: Optional[str] = None,
    ):
        self.event_bus = event_bus
        self.event_project_root = event_project_root

        # Get master key from environment or parameter
        env_key = os.getenv(OBFUSCATION_MASTER_KEY_ENV, "")
        if master_key:
            self.master_key = master_key
        elif env_key:
            self.master_key = env_key.encode("utf-8")
        else:
            # Development fallback - generate random key
            if os.getenv("ENVIRONMENT") == "production":
                raise ValueError(
                    f"{OBFUSCATION_MASTER_KEY_ENV} must be set in production environment"
                )
            import secrets

            self.master_key = secrets.token_bytes(32)
            logger.warning(
                f"⚠️ Using random master key for development. "
                f"Set {OBFUSCATION_MASTER_KEY_ENV} for consistent obfuscation."
            )

        self.current_method = ObfuscationMethod.FAKETLS
        self.rotation_strategy = RotationStrategy.TIME_BASED
        self.rotation_interval = 300  # 5 minutes

        # Current parameters
        self.current_sni = random.choice(ROTATING_SNI_OPTIONS)
        self.current_fingerprint = random.choice(ROTATING_FINGERPRINT_OPTIONS)
        self.current_spiderx = random.choice(ROTATING_SPIDERX_OPTIONS)
        self.last_rotation_time = time.time()

        # Traffic shaping
        self.traffic_shaper = TrafficShaper(TrafficProfile.WEB_BROWSING)

        # Obfuscation transports
        self.faketls = FakeTLSTransport(sni=self.current_sni)
        self.shadowsocks = ShadowsocksTransport()

        # Initialize StegoMesh only if available
        if STEGO_MESH_AVAILABLE:
            self.stegomesh = StegoMeshProtocol(self.master_key)
        else:
            self.stegomesh = None

        self.thinking_coach = AgentThinkingCoach(
            agent_id=_SERVICE_AGENT,
            role="security",
            capabilities=("zero-trust", "ops", "network"),
        )
        self.last_thinking_context: Dict[str, Any] = {}

        logger.info("VPNObfuscationManager initialized")
        logger.debug(f"Initial SNI: {self.current_sni}")
        logger.debug(f"Initial fingerprint: {self.current_fingerprint}")
        logger.debug(f"Initial SpiderX: {self.current_spiderx}")

    def _event_bus_or_none(self) -> Optional[EventBus]:
        if self.event_bus is not None:
            return self.event_bus
        if self.event_project_root is None:
            return None
        try:
            self.event_bus = get_event_bus(self.event_project_root)
            return self.event_bus
        except Exception as exc:
            logger.error("Failed to initialize VPN obfuscation EventBus: %s", exc)
            return None

    def _service_identity_presence(self) -> Dict[str, bool]:
        identity = service_event_identity(service_name=_SERVICE_AGENT)
        return {
            "spiffe_id_present": bool(identity.get("spiffe_id")),
            "did_present": bool(identity.get("did")),
            "wallet_address_present": bool(identity.get("wallet_address")),
            "raw_identity_redacted": True,
        }

    def _parameter_presence_metadata(self) -> Dict[str, Any]:
        return {
            "sni_present": bool(self.current_sni),
            "sni_hash": _sha256_prefix(self.current_sni),
            "fingerprint_present": bool(self.current_fingerprint),
            "fingerprint_hash": _sha256_prefix(self.current_fingerprint),
            "spiderx_present": bool(self.current_spiderx),
            "spiderx_hash": _sha256_prefix(self.current_spiderx),
            "raw_parameters_redacted": True,
        }

    def _prepare_obfuscation_thinking_context(
        self,
        *,
        task_type: str,
        goal: str,
        extra: Optional[Dict[str, Any]] = None,
    ) -> Dict[str, Any]:
        """Prepare redacted thinking context for local obfuscation decisions."""
        context: Dict[str, Any] = {
            "type": task_type,
            "goal": goal,
            "method_bucket": self.current_method.value,
            "rotation_strategy": self.rotation_strategy.value,
            "rotation_interval_seconds": int(self.rotation_interval),
            "stegomesh_available": self.stegomesh is not None,
            "parameter_presence": self._parameter_presence_metadata(),
            "constraints": {
                "redact_payload_bytes": True,
                "redact_master_key": True,
                "redact_raw_obfuscation_parameters": True,
                "local_metric_only": True,
            },
            "safety_boundary": (
                "Do not claim DPI bypass, anonymity, remote reachability, or dataplane "
                "delivery from local obfuscation metrics."
            ),
        }
        if extra:
            context.update(extra)
        self.last_thinking_context = self.thinking_coach.prepare_task(context)
        return self.last_thinking_context

    def _publish_local_evidence(
        self,
        *,
        operation: str,
        status_value: str,
        started_at: float,
        metadata: Optional[Dict[str, Any]] = None,
        error_type: Optional[str] = None,
    ) -> Optional[str]:
        bus = self._event_bus_or_none()
        if bus is None:
            return None

        payload: Dict[str, Any] = {
            "component": "network.vpn_obfuscation_manager",
            "operation": operation,
            "service_name": _SERVICE_AGENT,
            "source_alias": _SERVICE_AGENT,
            "layer": _SERVICE_LAYER,
            "status": status_value,
            "duration_ms": round((time.monotonic() - started_at) * 1000.0, 3),
            "method_bucket": self.current_method.value,
            "rotation_strategy": self.rotation_strategy.value,
            "parameter_presence": self._parameter_presence_metadata(),
            "service_identity": self._service_identity_presence(),
            "control_action": operation
            in {
                "rotate_parameters",
                "optimize_parameters_for_dpi_evasion",
            },
            "observed_state": operation
            in {
                "obfuscate",
                "deobfuscate",
                "test_obfuscation_effectiveness",
            },
            "raw_identifiers_redacted": True,
            "payloads_redacted": True,
            "raw_parameters_redacted": True,
            "master_key_redacted": True,
            "dataplane_confirmed": False,
            "dpi_bypass_confirmed": False,
            "bypass_confirmed": False,
            "claim_boundary": VPN_OBFUSCATION_MANAGER_CLAIM_BOUNDARY,
            "thinking": self.thinking_coach.status(),
            "last_thinking_context": self.last_thinking_context,
        }
        if metadata:
            payload.update(metadata)
        if error_type:
            payload["error"] = {
                "type": error_type,
                "message_redacted": True,
            }

        event_type = (
            EventType.TASK_FAILED
            if status_value == "failed"
            else EventType.PIPELINE_STAGE_END
        )
        try:
            event = bus.publish(event_type, _SERVICE_AGENT, payload, priority=4)
            return event.event_id
        except Exception as exc:
            logger.error("Failed to publish VPN obfuscation evidence: %s", exc)
            return None

    def set_obfuscation_method(self, method: ObfuscationMethod):
        """Set the active obfuscation method."""
        self.current_method = method
        logger.info(f"Obfuscation method changed to: {method.value}")

    def set_rotation_strategy(self, strategy: RotationStrategy):
        """Set the parameter rotation strategy."""
        self.rotation_strategy = strategy
        logger.info(f"Rotation strategy changed to: {strategy.value}")

    def set_rotation_interval(self, interval: int):
        """Set rotation interval in seconds."""
        self.rotation_interval = interval
        logger.info(f"Rotation interval set to: {interval} seconds")

    def _should_rotate(self) -> bool:
        """Check if it's time to rotate parameters."""
        if self.rotation_strategy == RotationStrategy.TIME_BASED:
            return time.time() - self.last_rotation_time >= self.rotation_interval
        return False

    def rotate_parameters(self):
        """Rotate obfuscation parameters based on strategy."""
        started_at = time.monotonic()
        previous_sni = self.current_sni
        previous_fingerprint = self.current_fingerprint
        previous_spiderx = self.current_spiderx
        try:
            if self.rotation_strategy == RotationStrategy.RANDOM:
                self.current_sni = random.choice(ROTATING_SNI_OPTIONS)
                self.current_fingerprint = random.choice(ROTATING_FINGERPRINT_OPTIONS)
                self.current_spiderx = random.choice(ROTATING_SPIDERX_OPTIONS)
            elif self.rotation_strategy == RotationStrategy.ROUND_ROBIN:
                # Simple round-robin implementation
                sni_index = (ROTATING_SNI_OPTIONS.index(self.current_sni) + 1) % len(
                    ROTATING_SNI_OPTIONS
                )
                fp_index = (
                    ROTATING_FINGERPRINT_OPTIONS.index(self.current_fingerprint) + 1
                ) % len(ROTATING_FINGERPRINT_OPTIONS)
                spx_index = (
                    ROTATING_SPIDERX_OPTIONS.index(self.current_spiderx) + 1
                ) % len(ROTATING_SPIDERX_OPTIONS)

                self.current_sni = ROTATING_SNI_OPTIONS[sni_index]
                self.current_fingerprint = ROTATING_FINGERPRINT_OPTIONS[fp_index]
                self.current_spiderx = ROTATING_SPIDERX_OPTIONS[spx_index]

            self.last_rotation_time = time.time()

            # Update faketls transport with new SNI
            self.faketls = FakeTLSTransport(sni=self.current_sni)
        except Exception as exc:
            self._prepare_obfuscation_thinking_context(
                task_type="vpn_obfuscation_parameter_rotation",
                goal="rotate local obfuscation parameters without exposing raw values",
                extra={
                    "status": "failed",
                    "sni_changed": self.current_sni != previous_sni,
                    "fingerprint_changed": (
                        self.current_fingerprint != previous_fingerprint
                    ),
                    "spiderx_changed": self.current_spiderx != previous_spiderx,
                },
            )
            self._publish_local_evidence(
                operation="rotate_parameters",
                status_value="failed",
                started_at=started_at,
                metadata={
                    "rotation": {
                        "strategy": self.rotation_strategy.value,
                        "sni_changed": self.current_sni != previous_sni,
                        "fingerprint_changed": (
                            self.current_fingerprint != previous_fingerprint
                        ),
                        "spiderx_changed": self.current_spiderx != previous_spiderx,
                    },
                },
                error_type=type(exc).__name__,
            )
            raise

        self._prepare_obfuscation_thinking_context(
            task_type="vpn_obfuscation_parameter_rotation",
            goal="rotate local obfuscation parameters without exposing raw values",
            extra={
                "status": "rotated",
                "sni_changed": self.current_sni != previous_sni,
                "fingerprint_changed": (
                    self.current_fingerprint != previous_fingerprint
                ),
                "spiderx_changed": self.current_spiderx != previous_spiderx,
            },
        )
        self._publish_local_evidence(
            operation="rotate_parameters",
            status_value="rotated",
            started_at=started_at,
            metadata={
                "rotation": {
                    "strategy": self.rotation_strategy.value,
                    "sni_changed": self.current_sni != previous_sni,
                    "fingerprint_changed": (
                        self.current_fingerprint != previous_fingerprint
                    ),
                    "spiderx_changed": self.current_spiderx != previous_spiderx,
                    "raw_parameters_redacted": True,
                },
            },
        )

        logger.info("Parameters rotated")
        logger.debug(f"New SNI: {self.current_sni}")
        logger.debug(f"New fingerprint: {self.current_fingerprint}")
        logger.debug(f"New SpiderX: {self.current_spiderx}")

    def obfuscate(self, data: bytes) -> bytes:
        """
        Obfuscate data using the current method.

        Args:
            data: Raw data to obfuscate

        Returns:
            Obfuscated data
        """
        started_at = time.monotonic()
        rotation_triggered = False
        shaped_data = b""
        try:
            # Check if rotation is needed
            rotation_triggered = self._should_rotate()
            if rotation_triggered:
                self.rotate_parameters()

            # Apply traffic shaping first
            shaped_data = self.traffic_shaper.shape_packet(data)

            # Apply obfuscation
            if self.current_method == ObfuscationMethod.FAKETLS:
                result = self.faketls.obfuscate(shaped_data)
            elif self.current_method == ObfuscationMethod.SHADOWSOCKS:
                result = self.shadowsocks.obfuscate(shaped_data)
            elif self.current_method == ObfuscationMethod.DOMAIN_FRONTING:
                result = self._domain_fronting_obfuscate(shaped_data)
            elif self.current_method == ObfuscationMethod.STEGOMESH:
                if self.stegomesh is None:
                    logger.warning(
                        "STEGOMESH not available, returning shaped data unchanged"
                    )
                    result = shaped_data
                else:
                    result = self.stegomesh.encode_packet(shaped_data)
            elif self.current_method == ObfuscationMethod.HYBRID:
                result = self._hybrid_obfuscate(shaped_data)
            else:
                result = shaped_data
        except Exception as exc:
            self._prepare_obfuscation_thinking_context(
                task_type="vpn_obfuscation_encode",
                goal="obfuscate payload bytes while keeping diagnostics redacted",
                extra={
                    "status": "failed",
                    "input_bytes_bucket": _byte_count_bucket(len(data)),
                    "shaped_bytes_bucket": _byte_count_bucket(len(shaped_data)),
                    "rotation_triggered": rotation_triggered,
                },
            )
            self._publish_local_evidence(
                operation="obfuscate",
                status_value="failed",
                started_at=started_at,
                metadata={
                    "input_bytes_bucket": _byte_count_bucket(len(data)),
                    "shaped_bytes_bucket": _byte_count_bucket(len(shaped_data)),
                    "rotation_triggered": rotation_triggered,
                },
                error_type=type(exc).__name__,
            )
            raise

        self._prepare_obfuscation_thinking_context(
            task_type="vpn_obfuscation_encode",
            goal="obfuscate payload bytes while keeping diagnostics redacted",
            extra={
                "status": "obfuscated",
                "input_bytes_bucket": _byte_count_bucket(len(data)),
                "shaped_bytes_bucket": _byte_count_bucket(len(shaped_data)),
                "output_bytes_bucket": _byte_count_bucket(len(result)),
                "rotation_triggered": rotation_triggered,
            },
        )
        self._publish_local_evidence(
            operation="obfuscate",
            status_value="obfuscated",
            started_at=started_at,
            metadata={
                "input_bytes_bucket": _byte_count_bucket(len(data)),
                "shaped_bytes_bucket": _byte_count_bucket(len(shaped_data)),
                "output_bytes_bucket": _byte_count_bucket(len(result)),
                "rotation_triggered": rotation_triggered,
            },
        )
        return result

    def deobfuscate(self, data: bytes) -> bytes:
        """
        Deobfuscate data using the current method.

        Args:
            data: Obfuscated data

        Returns:
            Deobfuscated data
        """
        started_at = time.monotonic()
        deobfuscated = b""
        try:
            # Deobfuscate
            if self.current_method == ObfuscationMethod.FAKETLS:
                deobfuscated = self.faketls.deobfuscate(data)
            elif self.current_method == ObfuscationMethod.SHADOWSOCKS:
                deobfuscated = self.shadowsocks.deobfuscate(data)
            elif self.current_method == ObfuscationMethod.DOMAIN_FRONTING:
                deobfuscated = self._domain_fronting_deobfuscate(data)
            elif self.current_method == ObfuscationMethod.STEGOMESH:
                if self.stegomesh is None:
                    logger.warning("STEGOMESH not available, returning data unchanged")
                    deobfuscated = data
                else:
                    deobfuscated = self.stegomesh.decode_packet(data)
            elif self.current_method == ObfuscationMethod.HYBRID:
                deobfuscated = self._hybrid_deobfuscate(data)
            else:
                deobfuscated = data

            # Remove traffic shaping
            result = self.traffic_shaper.unshape_packet(deobfuscated)
        except Exception as exc:
            self._prepare_obfuscation_thinking_context(
                task_type="vpn_obfuscation_decode",
                goal="deobfuscate payload bytes while keeping diagnostics redacted",
                extra={
                    "status": "failed",
                    "input_bytes_bucket": _byte_count_bucket(len(data)),
                    "deobfuscated_bytes_bucket": _byte_count_bucket(len(deobfuscated)),
                },
            )
            self._publish_local_evidence(
                operation="deobfuscate",
                status_value="failed",
                started_at=started_at,
                metadata={
                    "input_bytes_bucket": _byte_count_bucket(len(data)),
                    "deobfuscated_bytes_bucket": _byte_count_bucket(len(deobfuscated)),
                },
                error_type=type(exc).__name__,
            )
            raise

        self._prepare_obfuscation_thinking_context(
            task_type="vpn_obfuscation_decode",
            goal="deobfuscate payload bytes while keeping diagnostics redacted",
            extra={
                "status": "deobfuscated",
                "input_bytes_bucket": _byte_count_bucket(len(data)),
                "deobfuscated_bytes_bucket": _byte_count_bucket(len(deobfuscated)),
                "output_bytes_bucket": _byte_count_bucket(len(result)),
            },
        )
        self._publish_local_evidence(
            operation="deobfuscate",
            status_value="deobfuscated",
            started_at=started_at,
            metadata={
                "input_bytes_bucket": _byte_count_bucket(len(data)),
                "deobfuscated_bytes_bucket": _byte_count_bucket(len(deobfuscated)),
                "output_bytes_bucket": _byte_count_bucket(len(result)),
            },
        )
        return result

    def _domain_fronting_obfuscate(self, data: bytes) -> bytes:
        """Domain fronting obfuscation (requires transport instance)."""
        # Domain fronting requires specific front/backend domains
        # For this implementation, we'll use random CDN front domains
        front_domains = ["www.cloudflare.com", "www.cloudflare.net", "www.cf-cdn.com"]

        backend_domains = [
            "api.x0tta6bl4.org",
            "gateway.x0tta6bl4.network",
            "proxy.x0tta6bl4.io",
        ]

        front = random.choice(front_domains)
        backend = random.choice(backend_domains)

        transport = DomainFrontingTransport(front, backend)
        return transport.obfuscate(data)

    def _domain_fronting_deobfuscate(self, data: bytes) -> bytes:
        """Domain fronting deobfuscation."""
        # This is a simplified implementation
        front = random.choice(["www.cloudflare.com", "www.cloudflare.net"])
        backend = random.choice(["api.x0tta6bl4.org", "gateway.x0tta6bl4.network"])

        transport = DomainFrontingTransport(front, backend)
        return transport.deobfuscate(data)

    def _hybrid_obfuscate(self, data: bytes) -> bytes:
        """
        Hybrid obfuscation: Combine multiple techniques for maximum protection.
        Example: StegoMesh + FakeTLS
        """
        # First apply StegoMesh (protocol mimicry)
        if self.stegomesh is None:
            logger.warning("STEGOMESH not available for hybrid obfuscation")
            stego_data = data
        else:
            stego_data = self.stegomesh.encode_packet(data)

        # Then apply FakeTLS (TLS 1.3 wrapper)
        return self.faketls.obfuscate(stego_data)

    def _hybrid_deobfuscate(self, data: bytes) -> bytes:
        """Hybrid deobfuscation."""
        # First remove FakeTLS wrapper
        tls_data = self.faketls.deobfuscate(data)

        # Then decode StegoMesh
        if self.stegomesh is None:
            logger.warning("STEGOMESH not available for hybrid deobfuscation")
            return tls_data
        return self.stegomesh.decode_packet(tls_data)

    def set_traffic_profile(self, profile: TrafficProfile):
        """Set the traffic shaping profile."""
        self.traffic_shaper = TrafficShaper(profile)
        logger.info(f"Traffic profile set to: {profile.value}")

    def get_traffic_statistics(self) -> Dict:
        """Get traffic shaping statistics."""
        return self.traffic_shaper.get_profile_info()

    def get_current_parameters(self) -> Dict:
        """Get current obfuscation parameters."""
        return {
            "method": self.current_method.value,
            "rotation_strategy": self.rotation_strategy.value,
            "rotation_interval": self.rotation_interval,
            "last_rotation": self.last_rotation_time,
            "next_rotation": self.last_rotation_time + self.rotation_interval,
            "sni": self.current_sni,
            "fingerprint": self.current_fingerprint,
            "spiderx": self.current_spiderx,
            "traffic_profile": self.traffic_shaper.get_profile_info(),
        }

    def test_obfuscation_effectiveness(self, data: bytes) -> Dict[str, float]:
        """
        Test obfuscation effectiveness using simple metrics.

        Args:
            data: Test data to analyze

        Returns:
            Dictionary of effectiveness metrics
        """
        started_at = time.monotonic()
        metrics = {}

        # Test each obfuscation method
        for method in ObfuscationMethod:
            if method == ObfuscationMethod.NONE:
                continue

            original = data
            self.set_obfuscation_method(method)

            try:
                obfuscated = self.obfuscate(original)

                # Simple effectiveness metric: entropy change
                import math
                from collections import Counter

                def calculate_entropy(data: bytes) -> float:
                    """Calculate Shannon entropy of bytes."""
                    if not data:
                        return 0.0

                    counter = Counter(data)
                    total = len(data)
                    entropy = 0.0

                    for count in counter.values():
                        probability = count / total
                        entropy -= probability * math.log2(probability)

                    return entropy

                original_entropy = calculate_entropy(original)
                obfuscated_entropy = calculate_entropy(obfuscated)

                metrics[method.value] = {
                    "entropy_change": obfuscated_entropy - original_entropy,
                    "size_increase": len(obfuscated) - len(original),
                    "compression_ratio": len(obfuscated) / len(original),
                    "success": True,
                }

                logger.debug(
                    f"Obfuscation test {method.value}: "
                    f"Entropy change: {metrics[method.value]['entropy_change']:.2f}, "
                    f"Size increase: {metrics[method.value]['size_increase']} bytes"
                )

            except Exception as e:
                logger.warning(f"Obfuscation test failed for {method.value}: {e}")
                metrics[method.value] = {"error": str(e), "success": False}

        success_count = sum(
            1
            for result in metrics.values()
            if isinstance(result, dict) and result.get("success")
        )
        self._prepare_obfuscation_thinking_context(
            task_type="vpn_obfuscation_metric_test",
            goal="compare local entropy and size metrics without claiming DPI bypass",
            extra={
                "input_bytes_bucket": _byte_count_bucket(len(data)),
                "methods_tested": len(metrics),
                "methods_successful": success_count,
                "metrics_scope": "local_entropy_and_size_only",
            },
        )
        self._publish_local_evidence(
            operation="test_obfuscation_effectiveness",
            status_value="measured",
            started_at=started_at,
            metadata={
                "input_bytes_bucket": _byte_count_bucket(len(data)),
                "methods_tested": len(metrics),
                "methods_successful": success_count,
                "metrics_scope": "local_entropy_and_size_only",
                "local_metric_only": True,
            },
        )
        return metrics

    def optimize_parameters_for_dpi_evasion(self):
        """Optimize parameters for maximum DPI evasion based on test data."""
        started_at = time.monotonic()
        # For this implementation, we'll use pre-configured optimal parameters
        logger.info("Optimizing parameters for DPI evasion...")

        # Test various configurations and select best performer
        test_data = b"Test payload for DPI evasion analysis - this should look like normal traffic"
        metrics = self.test_obfuscation_effectiveness(test_data)

        # Find the most effective method
        best_method = None
        best_score = -float("inf")

        for method, result in metrics.items():
            if result.get("success"):
                score = result["entropy_change"] - (result["compression_ratio"] * 0.1)
                if score > best_score:
                    best_score = score
                    best_method = method

        if best_method:
            self.set_obfuscation_method(ObfuscationMethod(best_method))
            logger.info(
                f"Selected best obfuscation method: {best_method} (score: {best_score:.2f})"
            )

        self._prepare_obfuscation_thinking_context(
            task_type="vpn_obfuscation_parameter_optimization",
            goal="select a local obfuscation method from bounded local metrics",
            extra={
                "methods_evaluated": len(metrics),
                "best_method_bucket": best_method or "none",
                "best_score_bucket": (
                    "positive"
                    if best_score > 0
                    else "zero" if best_score == 0 else "negative_or_missing"
                ),
                "selection_basis": "local_entropy_minus_size_ratio_only",
            },
        )
        self._publish_local_evidence(
            operation="optimize_parameters_for_dpi_evasion",
            status_value="selected" if best_method else "no_selection",
            started_at=started_at,
            metadata={
                "methods_evaluated": len(metrics),
                "best_method_bucket": best_method or "none",
                "best_score_bucket": (
                    "positive"
                    if best_score > 0
                    else "zero" if best_score == 0 else "negative_or_missing"
                ),
                "selection_basis": "local_entropy_minus_size_ratio_only",
                "local_metric_only": True,
            },
        )
        return metrics

    def get_thinking_status(self) -> Dict[str, Any]:
        """Expose thinking profile and latest redacted obfuscation context."""
        return {
            "thinking": self.thinking_coach.status(),
            "last_thinking_context": self.last_thinking_context,
        }


# Global obfuscation manager instance
_global_obfuscator: Optional[VPNObfuscationManager] = None


def get_vpn_obfuscator(
    master_key: Optional[bytes] = None,
    event_bus: Optional[EventBus] = None,
    event_project_root: Optional[str] = None,
) -> VPNObfuscationManager:
    """Get or create the global VPN obfuscation manager instance."""
    global _global_obfuscator
    if _global_obfuscator is None:
        _global_obfuscator = VPNObfuscationManager(
            master_key,
            event_bus=event_bus,
            event_project_root=event_project_root,
        )
    elif event_bus is not None:
        _global_obfuscator.event_bus = event_bus
    elif (
        event_project_root is not None and _global_obfuscator.event_project_root is None
    ):
        _global_obfuscator.event_project_root = event_project_root
    return _global_obfuscator


def test_obfuscation():
    """Test VPN obfuscation functionality."""
    logging.basicConfig(level=logging.DEBUG)

    obfuscator = VPNObfuscationManager()

    print("Testing VPN Obfuscation Manager...")
    print(f"Initial parameters: {obfuscator.get_current_parameters()}")

    test_data = b"X0TTA6BL4 VPN traffic that needs to bypass DPI"

    # Test all obfuscation methods
    for method in ObfuscationMethod:
        if method == ObfuscationMethod.NONE:
            continue

        print(f"\n=== Testing {method.value} ===")
        try:
            obfuscator.set_obfuscation_method(method)
            obfuscated = obfuscator.obfuscate(test_data)
            deobfuscated = obfuscator.deobfuscate(obfuscated)

            print(f"  Original: {len(test_data)} bytes")
            print(f"  Obfuscated: {len(obfuscated)} bytes")
            print(f"  Deobfuscated: {len(deobfuscated)} bytes")
            print(f"  Decryption successful: {test_data == deobfuscated}")

        except Exception as e:
            print(f"  Error: {e}")

    # Test parameter rotation
    print("\n=== Testing parameter rotation ===")
    initial_params = obfuscator.get_current_parameters()
    print(f"  Initial SNI: {initial_params['sni']}")

    obfuscator.rotate_parameters()
    rotated_params = obfuscator.get_current_parameters()
    print(f"  Rotated SNI: {rotated_params['sni']}")
    print(f"  SNI changed: {initial_params['sni'] != rotated_params['sni']}")

    # Test traffic shaping
    print("\n=== Testing traffic shaping ===")
    for profile in TrafficProfile:
        if profile == TrafficProfile.NONE:
            continue

        obfuscator.set_traffic_profile(profile)
        shaped = obfuscator.traffic_shaper.shape_packet(test_data)

        print(f"  {profile.value}: {len(test_data)} -> {len(shaped)} bytes")

    # Test optimization
    print("\n=== Testing parameter optimization ===")
    metrics = obfuscator.optimize_parameters_for_dpi_evasion()

    print("\n=== Obfuscation Effectiveness Metrics ===")
    for method, result in metrics.items():
        if result.get("success"):
            print(f"  {method}:")
            print(f"    Entropy change: {result['entropy_change']:.2f} bits")
            print(f"    Size increase: {result['size_increase']} bytes")
            print(f"    Compression ratio: {result['compression_ratio']:.2f}x")

    print("\nTest completed!")


if __name__ == "__main__":
    test_obfuscation()
