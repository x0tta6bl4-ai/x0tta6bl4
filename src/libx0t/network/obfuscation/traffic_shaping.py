"""
Traffic Shaping Module for x0tta6bl4 Mesh.
Shapes traffic patterns to mimic popular applications (YouTube, Netflix, etc.)
to evade advanced DPI that analyzes timing and packet size patterns.
"""
from __future__ import annotations

import asyncio
import hashlib
import logging
import random
import time
from dataclasses import dataclass
from enum import Enum
from typing import Any, Callable, Dict, List, Optional

from src.core.thinking.agent_thinking import AgentThinkingCoach

logger = logging.getLogger(__name__)
_SERVICE_AGENT = "libx0t-traffic-shaper"
TRAFFIC_SHAPING_CLAIM_BOUNDARY = (
    "Local libx0t traffic shaping evidence only. It records local shape/unshape, "
    "delay-selection, profile metadata, byte-count buckets, and duration; it does "
    "not expose payload bytes, packet contents, destinations, timing traces, or "
    "prove DPI bypass, censorship bypass, remote reachability, packet delivery, "
    "anonymity, provider health, client installation, or production customer "
    "traffic use."
)


def _sha256_prefix(value: Any) -> Optional[str]:
    text = str(value or "").strip()
    if not text:
        return None
    return hashlib.sha256(text.encode("utf-8", errors="replace")).hexdigest()[:16]


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


def _delay_ms_bucket(delay_seconds: float) -> str:
    delay_ms = max(0.0, float(delay_seconds) * 1000.0)
    if delay_ms == 0:
        return "zero"
    if delay_ms <= 5:
        return "very_low"
    if delay_ms <= 50:
        return "low"
    if delay_ms <= 500:
        return "medium"
    return "high"


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
        self.thinking_coach = AgentThinkingCoach(
            agent_id=_SERVICE_AGENT,
            role="security",
            capabilities=("zero-trust", "ops", "network"),
            extra_techniques=("mape_k", "weighted_decision_matrix"),
        )
        self.last_thinking_context: Dict[str, Any] = {}

        if self.params:
            logger.info(f"Traffic Shaper initialized with profile: {self.params.name}")

    def _profile_metadata(self) -> Dict[str, Any]:
        params = self.params
        return {
            "profile": self.profile.value,
            "profile_hash": _sha256_prefix(self.profile.value),
            "configured": params is not None,
            "pad_to_size_bucket": (
                _byte_count_bucket(params.pad_to_size)
                if params and params.pad_to_size
                else "none"
            ),
            "typical_packet_sizes_count": (
                len(params.typical_packet_sizes) if params else 0
            ),
            "burst_enabled": bool(params and params.burst_probability > 0),
            "raw_profile_values_redacted": True,
        }

    def _prepare_traffic_thinking_context(
        self,
        *,
        task_type: str,
        goal: str,
        extra: Optional[Dict[str, Any]] = None,
    ) -> Dict[str, Any]:
        context: Dict[str, Any] = {
            "task_type": task_type,
            "goal": goal,
            "profile": self._profile_metadata(),
            "burst_state": {
                "in_burst": bool(self._in_burst),
                "counter_bucket": _byte_count_bucket(self._burst_counter),
            },
            "constraints": {
                "redact_payload_bytes": True,
                "redact_timing_trace": True,
                "local_metric_only": True,
                "do_not_claim_dpi_bypass": True,
            },
            "safety_boundary": TRAFFIC_SHAPING_CLAIM_BOUNDARY,
        }
        if extra:
            context.update(extra)
        self.last_thinking_context = self.thinking_coach.prepare_task(context)
        return self.last_thinking_context

    def get_thinking_status(self) -> Dict[str, Any]:
        return {
            "thinking": self.thinking_coach.status(),
            "last_thinking_context": self.last_thinking_context,
            "claim_boundary": TRAFFIC_SHAPING_CLAIM_BOUNDARY,
        }

    def shape_packet(self, data: bytes) -> bytes:
        """
        Shape a packet by padding to match profile's typical sizes.
        """
        self._prepare_traffic_thinking_context(
            task_type="libx0t_traffic_shaping_shape_packet",
            goal="Shape local packet without exposing payload bytes or DPI claims.",
            extra={"input_bytes_bucket": _byte_count_bucket(len(data))},
        )
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
            self._prepare_traffic_thinking_context(
                task_type="libx0t_traffic_shaping_shape_packet_shaped",
                goal="Record local shaped packet metadata without payload bytes.",
                extra={
                    "input_bytes_bucket": _byte_count_bucket(original_size),
                    "output_bytes_bucket": _byte_count_bucket(len(shaped)),
                    "target_size_bucket": _byte_count_bucket(target_size),
                    "padding_applied": True,
                },
            )
            return shaped
        else:
            # No padding needed, just add length prefix
            length_prefix = original_size.to_bytes(2, "big")
            shaped = length_prefix + data
            self._prepare_traffic_thinking_context(
                task_type="libx0t_traffic_shaping_shape_packet_prefixed",
                goal="Record local length-prefix metadata without payload bytes.",
                extra={
                    "input_bytes_bucket": _byte_count_bucket(original_size),
                    "output_bytes_bucket": _byte_count_bucket(len(shaped)),
                    "target_size_bucket": _byte_count_bucket(target_size),
                    "padding_applied": False,
                },
            )
            return shaped

    def unshape_packet(self, data: bytes) -> bytes:
        """Remove shaping (padding) from received packet."""
        self._prepare_traffic_thinking_context(
            task_type="libx0t_traffic_shaping_unshape_packet",
            goal="Unshape local packet without exposing payload bytes.",
            extra={"input_bytes_bucket": _byte_count_bucket(len(data))},
        )
        # NONE profile doesn't add shaping, so return unchanged
        if self.profile == TrafficProfile.NONE or not self.params:
            return data

        if len(data) < 2:
            return data

        original_length = int.from_bytes(data[:2], "big")
        unshaped = data[2 : 2 + original_length]
        self._prepare_traffic_thinking_context(
            task_type="libx0t_traffic_shaping_unshape_packet_done",
            goal="Record local unshaped packet metadata without payload bytes.",
            extra={
                "input_bytes_bucket": _byte_count_bucket(len(data)),
                "declared_length_bucket": _byte_count_bucket(original_length),
                "output_bytes_bucket": _byte_count_bucket(len(unshaped)),
            },
        )
        return unshaped

    def get_send_delay(self) -> float:
        """
        Calculate delay before next packet to match profile timing.
        Returns delay in seconds.
        """
        self._prepare_traffic_thinking_context(
            task_type="libx0t_traffic_shaping_get_send_delay",
            goal="Select local send delay without exposing timing trace.",
        )
        if self.profile == TrafficProfile.NONE or not self.params:
            return 0.0

        # Handle burst mode
        if self._in_burst:
            self._burst_counter -= 1
            if self._burst_counter <= 0:
                self._in_burst = False
            # Minimal delay during burst
            delay = self.params.min_interval_ms / 1000.0
            self._prepare_traffic_thinking_context(
                task_type="libx0t_traffic_shaping_delay_selected",
                goal="Record local burst delay bucket.",
                extra={
                    "delay_ms_bucket": _delay_ms_bucket(delay),
                    "burst_state": "in_burst",
                },
            )
            return delay

        # Check if we should start a burst
        if random.random() < self.params.burst_probability:
            self._in_burst = True
            self._burst_counter = self.params.burst_size
            delay = self.params.min_interval_ms / 1000.0
            self._prepare_traffic_thinking_context(
                task_type="libx0t_traffic_shaping_delay_selected",
                goal="Record local burst-start delay bucket.",
                extra={
                    "delay_ms_bucket": _delay_ms_bucket(delay),
                    "burst_state": "started",
                },
            )
            return delay

        # Normal inter-packet delay with jitter
        delay_ms = random.uniform(
            self.params.min_interval_ms, self.params.max_interval_ms
        )
        delay = delay_ms / 1000.0
        self._prepare_traffic_thinking_context(
            task_type="libx0t_traffic_shaping_delay_selected",
            goal="Record local delay bucket.",
            extra={
                "delay_ms_bucket": _delay_ms_bucket(delay),
                "burst_state": "not_in_burst",
            },
        )
        return delay

    async def send_shaped(self, data: bytes, send_func: Callable[[bytes], None]):
        """
        Send data with traffic shaping applied.
        Adds appropriate delays and padding.
        """
        self._prepare_traffic_thinking_context(
            task_type="libx0t_traffic_shaping_send_shaped",
            goal="Send locally shaped packet without claiming dataplane delivery.",
            extra={"input_bytes_bucket": _byte_count_bucket(len(data))},
        )
        shaped = self.shape_packet(data)
        delay = self.get_send_delay()

        if delay > 0:
            await asyncio.sleep(delay)

        send_func(shaped)
        self._last_send_time = time.time()
        self._prepare_traffic_thinking_context(
            task_type="libx0t_traffic_shaping_send_shaped_done",
            goal="Record local send callback invocation without payload bytes.",
            extra={
                "input_bytes_bucket": _byte_count_bucket(len(data)),
                "output_bytes_bucket": _byte_count_bucket(len(shaped)),
                "delay_ms_bucket": _delay_ms_bucket(delay),
                "send_callback_invoked": True,
            },
        )

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
        self.thinking_coach = AgentThinkingCoach(
            agent_id="libx0t-traffic-analyzer",
            role="monitoring",
            capabilities=("monitoring", "ops"),
            extra_techniques=("causal_analysis",),
        )
        self.last_thinking_context: Dict[str, Any] = {}

    def _prepare_analyzer_thinking_context(
        self,
        *,
        task_type: str,
        goal: str,
        extra: Optional[Dict[str, Any]] = None,
    ) -> Dict[str, Any]:
        context: Dict[str, Any] = {
            "task_type": task_type,
            "goal": goal,
            "packet_count": len(self.packet_sizes),
            "inter_arrival_count": len(self.inter_arrival_times),
            "constraints": {
                "record_sizes_only": True,
                "redact_payload_bytes": True,
                "local_metric_only": True,
            },
            "safety_boundary": TRAFFIC_SHAPING_CLAIM_BOUNDARY,
        }
        if extra:
            context.update(extra)
        self.last_thinking_context = self.thinking_coach.prepare_task(context)
        return self.last_thinking_context

    def get_thinking_status(self) -> Dict[str, Any]:
        return {
            "thinking": self.thinking_coach.status(),
            "last_thinking_context": self.last_thinking_context,
            "claim_boundary": TRAFFIC_SHAPING_CLAIM_BOUNDARY,
        }

    def record_packet(self, size: int):
        """Record a packet for analysis."""
        now = time.time()
        self.packet_sizes.append(size)

        if self._last_packet_time:
            self.inter_arrival_times.append(now - self._last_packet_time)
        self._last_packet_time = now

    def get_statistics(self) -> dict:
        """Get traffic statistics."""
        self._prepare_analyzer_thinking_context(
            task_type="libx0t_traffic_analyzer_get_statistics",
            goal="Calculate local packet-size and interval summary.",
        )
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
        self._prepare_analyzer_thinking_context(
            task_type="libx0t_traffic_analyzer_reset",
            goal="Reset local traffic analyzer metrics.",
        )
        self.packet_sizes = []
        self.inter_arrival_times = []
        self._last_packet_time = None

