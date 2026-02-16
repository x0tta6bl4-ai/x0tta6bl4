"""
Traffic Shaping Module for x0tta6bl4 Mesh.
Shapes traffic patterns to mimic popular applications (YouTube, Netflix, etc.)
to evade advanced DPI that analyzes timing and packet size patterns.
"""

import asyncio
import logging
import random
import time
from dataclasses import dataclass
from enum import Enum
from typing import Callable, List, Optional

logger = logging.getLogger(__name__)


class TrafficProfile(Enum):
    """Predefined traffic profiles mimicking popular applications."""

    NONE = "none"
    VIDEO_STREAMING = "video_streaming"  # YouTube/Netflix-like
    VOICE_CALL = "voice_call"  # WhatsApp/Signal-like
    WEB_BROWSING = "web_browsing"  # Regular HTTPS browsing
    FILE_DOWNLOAD = "file_download"  # Large file transfer
    GAMING = "gaming"  # Low-latency game traffic


@dataclass
class ProfileParameters:
    """Parameters that define a traffic profile."""

    name: str
    # Packet size parameters
    min_packet_size: int
    max_packet_size: int
    typical_packet_sizes: List[int]  # Common sizes for this app
    # Timing parameters (milliseconds)
    min_interval_ms: float
    max_interval_ms: float
    burst_probability: float  # Probability of burst transmission
    burst_size: int  # Number of packets in a burst
    # Padding
    pad_to_size: Optional[int]  # Pad all packets to this size (None = variable)


# Predefined profiles based on real application analysis
TRAFFIC_PROFILES = {
    TrafficProfile.VIDEO_STREAMING: ProfileParameters(
        name="Video Streaming (YouTube/Netflix)",
        min_packet_size=1200,
        max_packet_size=1460,  # MTU-typical
        typical_packet_sizes=[1316, 1328, 1460],  # Common video chunk sizes
        min_interval_ms=5,
        max_interval_ms=50,
        burst_probability=0.7,
        burst_size=10,
        pad_to_size=1460,
    ),
    TrafficProfile.VOICE_CALL: ProfileParameters(
        name="Voice Call (WhatsApp/Signal)",
        min_packet_size=100,
        max_packet_size=200,
        typical_packet_sizes=[160, 180],  # Opus codec typical
        min_interval_ms=20,
        max_interval_ms=20,  # Very regular timing
        burst_probability=0.0,
        burst_size=1,
        pad_to_size=200,
    ),
    TrafficProfile.WEB_BROWSING: ProfileParameters(
        name="Web Browsing (HTTPS)",
        min_packet_size=200,
        max_packet_size=1460,
        typical_packet_sizes=[512, 1024, 1460],
        min_interval_ms=50,
        max_interval_ms=500,
        burst_probability=0.3,
        burst_size=5,
        pad_to_size=None,  # Variable
    ),
    TrafficProfile.FILE_DOWNLOAD: ProfileParameters(
        name="File Download",
        min_packet_size=1460,
        max_packet_size=1460,
        typical_packet_sizes=[1460],
        min_interval_ms=1,
        max_interval_ms=5,
        burst_probability=0.9,
        burst_size=20,
        pad_to_size=1460,
    ),
    TrafficProfile.GAMING: ProfileParameters(
        name="Gaming (Low Latency)",
        min_packet_size=50,
        max_packet_size=300,
        typical_packet_sizes=[64, 128, 256],
        min_interval_ms=10,
        max_interval_ms=33,  # ~30-100 Hz
        burst_probability=0.1,
        burst_size=2,
        pad_to_size=None,
    ),
}


class TrafficShaper:
    """
    Shapes outgoing traffic to match a specified application profile.
    """

    def __init__(self, profile: TrafficProfile = TrafficProfile.VIDEO_STREAMING):
        self.profile = profile
        self.params = TRAFFIC_PROFILES.get(profile)
        self._last_send_time = 0
        self._burst_counter = 0
        self._in_burst = False

        if self.params:
            logger.info(f"Traffic Shaper initialized with profile: {self.params.name}")

    def shape_packet(self, data: bytes) -> bytes:
        """
        Shape a packet by padding to match profile's typical sizes.
        """
        if self.profile == TrafficProfile.NONE or not self.params:
            return data

        original_size = len(data)

        # Determine target size
        if self.params.pad_to_size:
            target_size = self.params.pad_to_size
        else:
            # Choose a typical size that's >= original
            suitable_sizes = [
                s for s in self.params.typical_packet_sizes if s >= original_size
            ]
            if suitable_sizes:
                target_size = random.choice(suitable_sizes)
            else:
                target_size = self.params.max_packet_size

        # Pad if needed
        if original_size < target_size:
            # Use random padding to avoid fingerprinting
            padding = bytes(
                [random.randint(0, 255) for _ in range(target_size - original_size)]
            )
            # Prepend length of original data (2 bytes) so receiver can unpad
            length_prefix = original_size.to_bytes(2, "big")
            shaped = length_prefix + data + padding
            return shaped
        else:
            # No padding needed, just add length prefix
            length_prefix = original_size.to_bytes(2, "big")
            return length_prefix + data

    def unshape_packet(self, data: bytes) -> bytes:
        """Remove shaping (padding) from received packet."""
        # NONE profile doesn't add shaping, so return unchanged
        if self.profile == TrafficProfile.NONE or not self.params:
            return data

        if len(data) < 2:
            return data

        original_length = int.from_bytes(data[:2], "big")
        return data[2 : 2 + original_length]

    def get_send_delay(self) -> float:
        """
        Calculate delay before next packet to match profile timing.
        Returns delay in seconds.
        """
        if self.profile == TrafficProfile.NONE or not self.params:
            return 0.0

        # Handle burst mode
        if self._in_burst:
            self._burst_counter -= 1
            if self._burst_counter <= 0:
                self._in_burst = False
            # Minimal delay during burst
            return self.params.min_interval_ms / 1000.0

        # Check if we should start a burst
        if random.random() < self.params.burst_probability:
            self._in_burst = True
            self._burst_counter = self.params.burst_size
            return self.params.min_interval_ms / 1000.0

        # Normal inter-packet delay with jitter
        delay_ms = random.uniform(
            self.params.min_interval_ms, self.params.max_interval_ms
        )
        return delay_ms / 1000.0

    async def send_shaped(self, data: bytes, send_func: Callable[[bytes], None]):
        """
        Send data with traffic shaping applied.
        Adds appropriate delays and padding.
        """
        shaped = self.shape_packet(data)
        delay = self.get_send_delay()

        if delay > 0:
            await asyncio.sleep(delay)

        send_func(shaped)
        self._last_send_time = time.time()

    def get_profile_info(self) -> dict:
        """Return current profile information."""
        if not self.params:
            return {"profile": "none"}
        return {
            "profile": self.profile.value,
            "name": self.params.name,
            "packet_sizes": self.params.typical_packet_sizes,
            "timing_range_ms": [
                self.params.min_interval_ms,
                self.params.max_interval_ms,
            ],
            "burst_enabled": self.params.burst_probability > 0,
        }


class TrafficAnalyzer:
    """
    Analyzes traffic patterns for metrics and debugging.
    Useful for verifying shaping is working correctly.
    """

    def __init__(self):
        self.packet_sizes: List[int] = []
        self.inter_arrival_times: List[float] = []
        self._last_packet_time: Optional[float] = None

    def record_packet(self, size: int):
        """Record a packet for analysis."""
        now = time.time()
        self.packet_sizes.append(size)

        if self._last_packet_time:
            self.inter_arrival_times.append(now - self._last_packet_time)
        self._last_packet_time = now

    def get_statistics(self) -> dict:
        """Get traffic statistics."""
        if not self.packet_sizes:
            return {"packets": 0}

        avg_size = sum(self.packet_sizes) / len(self.packet_sizes)
        avg_interval = (
            sum(self.inter_arrival_times) / len(self.inter_arrival_times)
            if self.inter_arrival_times
            else 0
        )

        return {
            "packets": len(self.packet_sizes),
            "avg_size": avg_size,
            "min_size": min(self.packet_sizes),
            "max_size": max(self.packet_sizes),
            "avg_interval_ms": avg_interval * 1000,
            "throughput_pps": 1.0 / avg_interval if avg_interval > 0 else 0,
        }

    def reset(self):
        """Reset statistics."""
        self.packet_sizes = []
        self.inter_arrival_times = []
        self._last_packet_time = None
