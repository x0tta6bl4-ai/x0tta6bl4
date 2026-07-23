"""
Traffic Obfuscation Module
==========================

Multi-layer traffic obfuscation for bypassing deep packet inspection.
Includes XOR encryption, padding, packet shaping, and timing manipulation.
"""
from __future__ import annotations

import hashlib
import logging
import random
import secrets
import struct
import time
from dataclasses import dataclass, field
from enum import Enum
from typing import Any, Dict, List, Optional, Tuple, Union

from src.coordination.events import EventBus, EventType, get_event_bus
from src.services.service_event_identity import service_event_identity

logger = logging.getLogger(__name__)


class ObfuscationLayer(Enum):
    """Available obfuscation layers."""
    XOR = "xor"
    PADDING = "padding"
    PACKET_SHAPING = "packet_shaping"
    TIMING = "timing"
    FRAGMENTATION = "fragmentation"
    ENCODING = "encoding"


_SERVICE_AGENT = "anti-censorship-traffic-obfuscator"
_SERVICE_LAYER = "anti_censorship_traffic_obfuscation_local_evidence"
TRAFFIC_OBFUSCATION_CLAIM_BOUNDARY = (
    "Local traffic-obfuscation coordinator evidence only. It records local "
    "layer application, reverse-layer application, timing-delay reads, stats "
    "reads, duration, layer buckets, byte-count buckets, packet-count buckets, "
    "key/configuration presence, and service identity presence; it does not "
    "expose payload bytes, XOR keys, padding bytes, fragments, shaped packets, "
    "encoded payloads, timing traces, generated random bytes, or prove DPI "
    "bypass, censorship bypass, remote reachability, packet delivery, "
    "anonymity, provider health, client installation, or production customer "
    "traffic use."
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


def _packet_count_bucket(value: Any) -> str:
    if not isinstance(value, int) or value <= 0:
        return "zero"
    if value == 1:
        return "single"
    if value <= 4:
        return "few"
    if value <= 16:
        return "many"
    return "very_many"


def _layer_names(layers: List[ObfuscationLayer]) -> List[str]:
    return [layer.value for layer in layers if isinstance(layer, ObfuscationLayer)]


def _result_shape(value: Union[bytes, List[bytes]]) -> Dict[str, Any]:
    if isinstance(value, list):
        total = sum(len(item) for item in value if isinstance(item, bytes))
        return {
            "kind": "packet_list",
            "packets_count": len(value),
            "packet_count_bucket": _packet_count_bucket(len(value)),
            "bytes_bucket": _byte_count_bucket(total),
            "raw_packets_redacted": True,
        }
    return {
        "kind": "bytes",
        "packets_count": 1 if value else 0,
        "packet_count_bucket": "single" if value else "zero",
        "bytes_bucket": _byte_count_bucket(len(value)),
        "raw_packets_redacted": True,
    }


@dataclass
class ObfuscationConfig:
    """Configuration for traffic obfuscation."""
    enabled_layers: List[ObfuscationLayer] = field(default_factory=lambda: [
        ObfuscationLayer.XOR,
        ObfuscationLayer.PADDING,
    ])

    # XOR settings
    xor_key: Optional[bytes] = None
    xor_key_rotation: bool = True
    xor_key_interval: int = 1000  # Rotate key every N packets

    # Padding settings
    min_packet_size: int = 64
    max_packet_size: int = 1500
    padding_strategy: str = "random"  # random, fixed, variable

    # Packet shaping settings
    target_packet_size: int = 1400
    mtu: int = 1500

    # Timing settings
    timing_jitter_ms: int = 50
    timing_delay_ms: int = 10

    # Fragmentation settings
    fragment_size: int = 512
    fragment_delay_ms: int = 5

    # Encoding settings
    encoding_type: str = "base64"  # base64, hex, none


class XORObfuscator:
    """
    XOR-based obfuscation layer.

    Simple but effective against pattern-based DPI.
    """

    def __init__(self, key: Optional[bytes] = None, rotate: bool = True):
        self.key = key or secrets.token_bytes(32)
        self.rotate = rotate
        self._counter = 0
        self._current_key = self.key

    def _get_stream_key(self, length: int) -> bytes:
        """Generate a stream key for XOR operation."""
        # Use SHA-256 in counter mode as stream cipher
        result = b""
        counter = self._counter

        while len(result) < length:
            data = self._current_key + struct.pack(">Q", counter)
            result += hashlib.sha256(data).digest()
            counter += 1

        return result[:length]

    def encrypt(self, data: bytes) -> bytes:
        """XOR encrypt data."""
        stream = self._get_stream_key(len(data))
        result = bytes(a ^ b for a, b in zip(data, stream))
        self._counter += 1
        return result

    def decrypt(self, data: bytes) -> bytes:
        """XOR decrypt data (same as encrypt for XOR)."""
        return self.encrypt(data)

    def rotate_key(self) -> None:
        """Rotate the encryption key."""
        if self.rotate:
            self._current_key = hashlib.sha256(
                self._current_key + secrets.token_bytes(16)
            ).digest()
            self._counter = 0


class PaddingObfuscator:
    """
    Packet padding for size obfuscation.

    Prevents traffic analysis based on packet sizes.
    """

    def __init__(
        self,
        min_size: int = 64,
        max_size: int = 1500,
        strategy: str = "random",
    ):
        self.min_size = min_size
        self.max_size = max_size
        self.strategy = strategy

    def pad(self, data: bytes) -> Tuple[bytes, int]:
        """
        Add padding to data.

        Returns:
            Tuple of (padded_data, padding_length)
        """
        current_size = len(data)

        if current_size >= self.max_size:
            return data, 0

        if self.strategy == "random":
            target_size = random.randint(
                max(self.min_size, current_size),
                self.max_size
            )
        elif self.strategy == "fixed":
            target_size = self.max_size
        else:  # variable
            # Pad to next multiple of a random block size
            block = random.choice([64, 128, 256, 512])
            target_size = ((current_size // block) + 1) * block
            target_size = min(target_size, self.max_size)

        padding_length = target_size - current_size
        padding = secrets.token_bytes(padding_length)

        # Prepend padding length (2 bytes) + padding + data
        result = struct.pack(">H", padding_length) + padding + data

        return result, padding_length

    def unpad(self, data: bytes) -> bytes:
        """Remove padding from data."""
        if len(data) < 2:
            return data

        padding_length = struct.unpack(">H", data[:2])[0]

        if padding_length > len(data) - 2:
            return data  # Invalid padding, return as-is

        return data[2 + padding_length:]


class PacketShaper:
    """
    Packet shaping for MTU and size normalization.

    Makes traffic look like standard protocols.
    """

    # Common protocol packet sizes for mimicry
    PROTOCOL_SIZES = {
        "http": [1400, 1420, 1440, 1460],
        "dns": [64, 128, 256],
        "tls": [1280, 1400, 1420],
        "quic": [1200, 1350, 1450],
    }

    def __init__(
        self,
        target_size: int = 1400,
        mtu: int = 1500,
        mimic_protocol: str = "http",
    ):
        self.target_size = target_size
        self.mtu = mtu
        self.mimic_protocol = mimic_protocol

    def shape(self, data: bytes) -> List[bytes]:
        """
        Shape data into packets of appropriate sizes.

        Returns:
            List of shaped packets
        """
        packets = []
        sizes = self.PROTOCOL_SIZES.get(
            self.mimic_protocol,
            [self.target_size]
        )

        offset = 0
        while offset < len(data):
            # Choose a realistic packet size
            chunk_size = random.choice(sizes)
            chunk_size = min(chunk_size, self.mtu - 40)  # Account for headers

            chunk = data[offset:offset + chunk_size]

            # Pad to target size if needed
            if len(chunk) < chunk_size:
                chunk += secrets.token_bytes(chunk_size - len(chunk))

            packets.append(chunk)
            offset += chunk_size

        return packets

    def reshape(self, packets: List[bytes]) -> bytes:
        """Reassemble shaped packets."""
        return b"".join(packets)


class TimingObfuscator:
    """
    Timing manipulation for traffic analysis resistance.

    Adds jitter and delays to prevent timing-based fingerprinting.
    """

    def __init__(
        self,
        jitter_ms: int = 50,
        base_delay_ms: int = 10,
    ):
        self.jitter_ms = jitter_ms
        self.base_delay_ms = base_delay_ms

    def get_delay(self) -> float:
        """Get a randomized delay in seconds."""
        jitter = random.uniform(-self.jitter_ms, self.jitter_ms)
        delay = self.base_delay_ms + jitter
        return max(0, delay) / 1000.0

    async def wait(self) -> None:
        """Asynchronously wait with jitter."""
        delay = self.get_delay()
        if delay > 0:
            await asyncio.sleep(delay)

    def wait_sync(self) -> None:
        """Synchronously wait with jitter."""
        delay = self.get_delay()
        if delay > 0:
            time.sleep(delay)


class FragmentationObfuscator:
    """
    Packet fragmentation for DPI evasion.

    Fragments packets to bypass signature detection.
    """

    def __init__(
        self,
        fragment_size: int = 512,
        delay_ms: int = 5,
    ):
        self.fragment_size = fragment_size
        self.delay_ms = delay_ms

    def fragment(self, data: bytes) -> List[bytes]:
        """
        Fragment data into smaller pieces.

        Returns:
            List of fragments with headers
        """
        fragments = []
        total_size = len(data)
        offset = 0
        fragment_id = secrets.randbits(16)

        while offset < total_size:
            chunk = data[offset:offset + self.fragment_size]
            is_last = (offset + len(chunk)) >= total_size

            # Fragment header: ID (2) + offset (4) + flags (1) + length (2)
            flags = 0 if is_last else 1  # More fragments flag
            header = struct.pack(
                ">HIBH",
                fragment_id,
                offset,
                flags,
                len(chunk),
            )

            fragments.append(header + chunk)
            offset += len(chunk)

        return fragments

    def reassemble(self, fragments: List[bytes]) -> bytes:
        """Reassemble fragments into original data."""
        if not fragments:
            return b""

        # Parse headers and sort by offset
        parsed = []
        for frag in fragments:
            if len(frag) < 9:
                continue

            header = frag[:9]
            data = frag[9:]
            fragment_id, offset, flags, length = struct.unpack(">HIBH", header)
            parsed.append((offset, data))

        # Sort and concatenate
        parsed.sort(key=lambda x: x[0])
        return b"".join(d for _, d in parsed)


class EncodingObfuscator:
    """
    Encoding-based obfuscation.

    Encodes data to bypass content inspection.
    """

    import base64

    def __init__(self, encoding_type: str = "base64"):
        self.encoding_type = encoding_type

    def encode(self, data: bytes) -> bytes:
        """Encode data."""
        if self.encoding_type == "base64":
            return self.base64.b64encode(data)
        elif self.encoding_type == "hex":
            return data.hex().encode()
        else:
            return data

    def decode(self, data: bytes) -> bytes:
        """Decode data."""
        if self.encoding_type == "base64":
            return self.base64.b64decode(data)
        elif self.encoding_type == "hex":
            return bytes.fromhex(data.decode())
        else:
            return data


class TrafficObfuscator:
    """
    Multi-layer traffic obfuscation coordinator.

    Combines multiple obfuscation techniques for maximum effectiveness.
    """

    def __init__(
        self,
        config: Optional[ObfuscationConfig] = None,
        *,
        event_bus: Optional[EventBus] = None,
        event_project_root: Optional[str] = None,
    ):
        """
        Initialize traffic obfuscator.

        Args:
            config: Obfuscation configuration
        """
        self.config = config or ObfuscationConfig()
        self.event_bus = event_bus
        self.event_project_root = event_project_root

        # Initialize layers
        self._layers: Dict[ObfuscationLayer, Any] = {}

        if ObfuscationLayer.XOR in self.config.enabled_layers:
            self._layers[ObfuscationLayer.XOR] = XORObfuscator(
                key=self.config.xor_key,
                rotate=self.config.xor_key_rotation,
            )

        if ObfuscationLayer.PADDING in self.config.enabled_layers:
            self._layers[ObfuscationLayer.PADDING] = PaddingObfuscator(
                min_size=self.config.min_packet_size,
                max_size=self.config.max_packet_size,
                strategy=self.config.padding_strategy,
            )

        if ObfuscationLayer.PACKET_SHAPING in self.config.enabled_layers:
            self._layers[ObfuscationLayer.PACKET_SHAPING] = PacketShaper(
                target_size=self.config.target_packet_size,
                mtu=self.config.mtu,
            )

        if ObfuscationLayer.TIMING in self.config.enabled_layers:
            self._layers[ObfuscationLayer.TIMING] = TimingObfuscator(
                jitter_ms=self.config.timing_jitter_ms,
                base_delay_ms=self.config.timing_delay_ms,
            )

        if ObfuscationLayer.FRAGMENTATION in self.config.enabled_layers:
            self._layers[ObfuscationLayer.FRAGMENTATION] = FragmentationObfuscator(
                fragment_size=self.config.fragment_size,
                delay_ms=self.config.fragment_delay_ms,
            )

        if ObfuscationLayer.ENCODING in self.config.enabled_layers:
            self._layers[ObfuscationLayer.ENCODING] = EncodingObfuscator(
                encoding_type=self.config.encoding_type,
            )

        self._packet_count = 0

    def _event_bus_or_none(self) -> Optional[EventBus]:
        if self.event_bus is not None:
            return self.event_bus
        if self.event_project_root is None:
            return None
        try:
            self.event_bus = get_event_bus(self.event_project_root)
            return self.event_bus
        except Exception as exc:
            logger.error("Failed to initialize traffic-obfuscation EventBus: %s", exc)
            return None

    def _identity_presence(self) -> Dict[str, bool]:
        identity = service_event_identity(service_name=_SERVICE_AGENT)
        return {
            "spiffe_id_present": bool(identity.get("spiffe_id")),
            "did_present": bool(identity.get("did")),
            "wallet_address_present": bool(identity.get("wallet_address")),
            "raw_identity_redacted": True,
        }

    def _config_metadata(self) -> Dict[str, Any]:
        return {
            "enabled_layers": _layer_names(self.config.enabled_layers),
            "active_layers": _layer_names(list(self._layers.keys())),
            "xor_key_present": bool(self.config.xor_key),
            "xor_key_rotation": bool(self.config.xor_key_rotation),
            "xor_key_interval_bucket": _packet_count_bucket(
                self.config.xor_key_interval
            ),
            "padding_strategy": str(self.config.padding_strategy)[:32],
            "min_packet_size_bucket": _byte_count_bucket(self.config.min_packet_size),
            "max_packet_size_bucket": _byte_count_bucket(self.config.max_packet_size),
            "target_packet_size_bucket": _byte_count_bucket(
                self.config.target_packet_size
            ),
            "mtu_bucket": _byte_count_bucket(self.config.mtu),
            "fragment_size_bucket": _byte_count_bucket(self.config.fragment_size),
            "encoding_type": str(self.config.encoding_type)[:32],
            "raw_xor_key_redacted": True,
        }

    def _publish_evidence(
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
            "component": "anti_censorship.obfuscation",
            "operation": operation,
            "service_name": _SERVICE_AGENT,
            "source_alias": _SERVICE_AGENT,
            "layer": _SERVICE_LAYER,
            "status": status_value,
            "duration_ms": round((time.monotonic() - started_at) * 1000.0, 3),
            "config": self._config_metadata(),
            "service_identity": self._identity_presence(),
            "control_action": False,
            "observed_state": True,
            "payloads_redacted": True,
            "raw_packets_redacted": True,
            "raw_fragments_redacted": True,
            "raw_timing_trace_redacted": True,
            "crypto_material_redacted": True,
            "raw_identifiers_redacted": True,
            "dataplane_confirmed": False,
            "dpi_bypass_confirmed": False,
            "bypass_confirmed": False,
            "external_dpi_tested": False,
            "claim_boundary": TRAFFIC_OBFUSCATION_CLAIM_BOUNDARY,
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
            if status_value.endswith("failed")
            else EventType.PIPELINE_STAGE_END
        )
        try:
            event = bus.publish(event_type, _SERVICE_AGENT, payload, priority=4)
            return event.event_id
        except Exception as exc:
            logger.error("Failed to publish traffic-obfuscation evidence: %s", exc)
            return None

    def obfuscate(self, data: bytes) -> Union[bytes, List[bytes]]:
        """
        Apply all enabled obfuscation layers.

        Args:
            data: Original data

        Returns:
            Obfuscated data (or list of fragments)
        """
        started_at = time.monotonic()
        applied_layers: List[str] = []
        xor_key_rotated = False
        try:
            result = data

            # Apply encoding first (if enabled)
            if ObfuscationLayer.ENCODING in self._layers:
                result = self._layers[ObfuscationLayer.ENCODING].encode(result)
                applied_layers.append(ObfuscationLayer.ENCODING.value)

            # Apply XOR encryption
            if ObfuscationLayer.XOR in self._layers:
                result = self._layers[ObfuscationLayer.XOR].encrypt(result)
                applied_layers.append(ObfuscationLayer.XOR.value)

            # Apply padding
            if ObfuscationLayer.PADDING in self._layers:
                result, _ = self._layers[ObfuscationLayer.PADDING].pad(result)
                applied_layers.append(ObfuscationLayer.PADDING.value)

            # Apply fragmentation
            if ObfuscationLayer.FRAGMENTATION in self._layers:
                result = self._layers[ObfuscationLayer.FRAGMENTATION].fragment(result)
                applied_layers.append(ObfuscationLayer.FRAGMENTATION.value)

            # Apply packet shaping
            if ObfuscationLayer.PACKET_SHAPING in self._layers:
                if isinstance(result, list):
                    # Shape each fragment
                    shaped = []
                    for frag in result:
                        shaped.extend(
                            self._layers[ObfuscationLayer.PACKET_SHAPING].shape(frag)
                        )
                    result = shaped
                else:
                    result = self._layers[ObfuscationLayer.PACKET_SHAPING].shape(result)
                applied_layers.append(ObfuscationLayer.PACKET_SHAPING.value)

            self._packet_count += 1

            # Rotate XOR key if needed
            if ObfuscationLayer.XOR in self._layers:
                if self._packet_count % self.config.xor_key_interval == 0:
                    self._layers[ObfuscationLayer.XOR].rotate_key()
                    xor_key_rotated = True
        except Exception as exc:
            self._publish_evidence(
                operation="obfuscate",
                status_value="obfuscate_failed",
                started_at=started_at,
                metadata={
                    "input_bytes_bucket": _byte_count_bucket(
                        len(data) if hasattr(data, "__len__") else -1
                    ),
                    "applied_layers": applied_layers,
                    "packet_count": self._packet_count,
                    "packet_count_bucket": _packet_count_bucket(self._packet_count),
                },
                error_type=type(exc).__name__,
            )
            raise

        self._publish_evidence(
            operation="obfuscate",
            status_value="obfuscated",
            started_at=started_at,
            metadata={
                "input_bytes_bucket": _byte_count_bucket(len(data)),
                "result_shape": _result_shape(result),
                "applied_layers": applied_layers,
                "xor_key_rotated": xor_key_rotated,
                "packet_count": self._packet_count,
                "packet_count_bucket": _packet_count_bucket(self._packet_count),
            },
        )
        return result

    def deobfuscate(self, data: Union[bytes, List[bytes]]) -> bytes:
        """
        Reverse all obfuscation layers.

        Args:
            data: Obfuscated data

        Returns:
            Original data
        """
        started_at = time.monotonic()
        reversed_layers: List[str] = []
        try:
            result = data if isinstance(data, bytes) else b"".join(data)

            # Reverse packet shaping (reassembly)
            if ObfuscationLayer.PACKET_SHAPING in self._layers:
                if isinstance(data, list):
                    result = self._layers[ObfuscationLayer.PACKET_SHAPING].reshape(data)
                reversed_layers.append(ObfuscationLayer.PACKET_SHAPING.value)

            # Reverse fragmentation
            if ObfuscationLayer.FRAGMENTATION in self._layers:
                if isinstance(data, list):
                    result = self._layers[ObfuscationLayer.FRAGMENTATION].reassemble(data)
                reversed_layers.append(ObfuscationLayer.FRAGMENTATION.value)

            # Reverse padding
            if ObfuscationLayer.PADDING in self._layers:
                result = self._layers[ObfuscationLayer.PADDING].unpad(result)
                reversed_layers.append(ObfuscationLayer.PADDING.value)

            # Reverse XOR
            if ObfuscationLayer.XOR in self._layers:
                result = self._layers[ObfuscationLayer.XOR].decrypt(result)
                reversed_layers.append(ObfuscationLayer.XOR.value)

            # Reverse encoding
            if ObfuscationLayer.ENCODING in self._layers:
                result = self._layers[ObfuscationLayer.ENCODING].decode(result)
                reversed_layers.append(ObfuscationLayer.ENCODING.value)
        except Exception as exc:
            self._publish_evidence(
                operation="deobfuscate",
                status_value="deobfuscate_failed",
                started_at=started_at,
                metadata={
                    "input_shape": _result_shape(data),
                    "reversed_layers": reversed_layers,
                },
                error_type=type(exc).__name__,
            )
            raise

        self._publish_evidence(
            operation="deobfuscate",
            status_value="deobfuscated",
            started_at=started_at,
            metadata={
                "input_shape": _result_shape(data),
                "output_bytes_bucket": _byte_count_bucket(len(result)),
                "reversed_layers": reversed_layers,
            },
        )
        return result

    def get_timing_delay(self) -> float:
        """Get timing delay if timing obfuscation is enabled."""
        started_at = time.monotonic()
        if ObfuscationLayer.TIMING in self._layers:
            delay = self._layers[ObfuscationLayer.TIMING].get_delay()
            self._publish_evidence(
                operation="get_timing_delay",
                status_value="measured",
                started_at=started_at,
                metadata={
                    "timing_enabled": True,
                    "delay_ms_bucket": _byte_count_bucket(round(delay * 1000)),
                    "raw_timing_trace_redacted": True,
                },
            )
            return delay
        self._publish_evidence(
            operation="get_timing_delay",
            status_value="not_configured",
            started_at=started_at,
            metadata={
                "timing_enabled": False,
                "delay_ms_bucket": "zero",
                "raw_timing_trace_redacted": True,
            },
        )
        return 0.0

    def get_stats(self) -> Dict[str, Any]:
        """Get obfuscation statistics."""
        started_at = time.monotonic()
        stats = {
            "enabled_layers": [layer.value for layer in self.config.enabled_layers],
            "packet_count": self._packet_count,
        }
        self._publish_evidence(
            operation="get_stats",
            status_value="read",
            started_at=started_at,
            metadata={
                "enabled_layers": list(stats["enabled_layers"]),
                "packet_count": self._packet_count,
                "packet_count_bucket": _packet_count_bucket(self._packet_count),
            },
        )
        return stats


# Import asyncio for async timing
import asyncio


__all__ = [
    "ObfuscationLayer",
    "ObfuscationConfig",
    "XORObfuscator",
    "PaddingObfuscator",
    "PacketShaper",
    "TimingObfuscator",
    "FragmentationObfuscator",
    "EncodingObfuscator",
    "TrafficObfuscator",
]

