#!/usr/bin/env python3
"""
Advanced VPN Obfuscation Manager for x0tta6bl4
Manages multiple obfuscation techniques and implements rotating parameters
for better block bypass and anonymity.
"""

import logging
import os
import random
import time
from enum import Enum
from typing import Any, Dict, List, Optional

from .obfuscation.base import ObfuscationTransport, TransportManager
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

    def __init__(self, master_key: Optional[bytes] = None):
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

        logger.info("VPNObfuscationManager initialized")
        logger.debug(f"Initial SNI: {self.current_sni}")
        logger.debug(f"Initial fingerprint: {self.current_fingerprint}")
        logger.debug(f"Initial SpiderX: {self.current_spiderx}")

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
        # Check if rotation is needed
        if self._should_rotate():
            self.rotate_parameters()

        # Apply traffic shaping first
        shaped_data = self.traffic_shaper.shape_packet(data)

        # Apply obfuscation
        if self.current_method == ObfuscationMethod.FAKETLS:
            return self.faketls.obfuscate(shaped_data)
        elif self.current_method == ObfuscationMethod.SHADOWSOCKS:
            return self.shadowsocks.obfuscate(shaped_data)
        elif self.current_method == ObfuscationMethod.DOMAIN_FRONTING:
            return self._domain_fronting_obfuscate(shaped_data)
        elif self.current_method == ObfuscationMethod.STEGOMESH:
            if self.stegomesh is None:
                logger.warning(
                    "STEGOMESH not available, returning shaped data unchanged"
                )
                return shaped_data
            return self.stegomesh.encode_packet(shaped_data)
        elif self.current_method == ObfuscationMethod.HYBRID:
            return self._hybrid_obfuscate(shaped_data)
        else:
            return shaped_data

    def deobfuscate(self, data: bytes) -> bytes:
        """
        Deobfuscate data using the current method.

        Args:
            data: Obfuscated data

        Returns:
            Deobfuscated data
        """
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
        return self.traffic_shaper.unshape_packet(deobfuscated)

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

        return metrics

    def optimize_parameters_for_dpi_evasion(self):
        """Optimize parameters for maximum DPI evasion based on test data."""
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

        return metrics


# Global obfuscation manager instance
_global_obfuscator: Optional[VPNObfuscationManager] = None


def get_vpn_obfuscator(master_key: Optional[bytes] = None) -> VPNObfuscationManager:
    """Get or create the global VPN obfuscation manager instance."""
    global _global_obfuscator
    if _global_obfuscator is None:
        _global_obfuscator = VPNObfuscationManager(master_key)
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
