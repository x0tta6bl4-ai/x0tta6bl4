"""
Traffic Obfuscation Module
==========================

Multi-layer traffic obfuscation for bypassing deep packet inspection.
Includes XOR encryption, padding, packet shaping, and timing manipulation.
"""

import hashlib
import logging
import os
import random
import secrets
import struct
import time
from dataclasses import dataclass, field
from enum import Enum
from typing import Any, Callable, Dict, List, Optional, Tuple, Union

logger = logging.getLogger(__name__)


class ObfuscationLayer(Enum):
    """Available obfuscation layers."""
    XOR = "xor"
    PADDING = "padding"
    PACKET_SHAPING = "packet_shaping"
    TIMING = "timing"
    FRAGMENTATION = "fragmentation"
    ENCODING = "encoding"


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
    
    def __init__(self, config: Optional[ObfuscationConfig] = None):
        """
        Initialize traffic obfuscator.
        
        Args:
            config: Obfuscation configuration
        """
        self.config = config or ObfuscationConfig()
        
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
    
    def obfuscate(self, data: bytes) -> Union[bytes, List[bytes]]:
        """
        Apply all enabled obfuscation layers.
        
        Args:
            data: Original data
            
        Returns:
            Obfuscated data (or list of fragments)
        """
        result = data
        
        # Apply encoding first (if enabled)
        if ObfuscationLayer.ENCODING in self._layers:
            result = self._layers[ObfuscationLayer.ENCODING].encode(result)
        
        # Apply XOR encryption
        if ObfuscationLayer.XOR in self._layers:
            result = self._layers[ObfuscationLayer.XOR].encrypt(result)
        
        # Apply padding
        if ObfuscationLayer.PADDING in self._layers:
            result, _ = self._layers[ObfuscationLayer.PADDING].pad(result)
        
        # Apply fragmentation
        if ObfuscationLayer.FRAGMENTATION in self._layers:
            result = self._layers[ObfuscationLayer.FRAGMENTATION].fragment(result)
        
        # Apply packet shaping
        if ObfuscationLayer.PACKET_SHAPING in self._layers:
            if isinstance(result, list):
                # Shape each fragment
                shaped = []
                for frag in result:
                    shaped.extend(self._layers[ObfuscationLayer.PACKET_SHAPING].shape(frag))
                result = shaped
            else:
                result = self._layers[ObfuscationLayer.PACKET_SHAPING].shape(result)
        
        self._packet_count += 1
        
        # Rotate XOR key if needed
        if ObfuscationLayer.XOR in self._layers:
            if self._packet_count % self.config.xor_key_interval == 0:
                self._layers[ObfuscationLayer.XOR].rotate_key()
        
        return result
    
    def deobfuscate(self, data: Union[bytes, List[bytes]]) -> bytes:
        """
        Reverse all obfuscation layers.
        
        Args:
            data: Obfuscated data
            
        Returns:
            Original data
        """
        result = data if isinstance(data, bytes) else b"".join(data)
        
        # Reverse packet shaping (reassembly)
        if ObfuscationLayer.PACKET_SHAPING in self._layers:
            if isinstance(data, list):
                result = self._layers[ObfuscationLayer.PACKET_SHAPING].reshape(data)
        
        # Reverse fragmentation
        if ObfuscationLayer.FRAGMENTATION in self._layers:
            if isinstance(data, list):
                result = self._layers[ObfuscationLayer.FRAGMENTATION].reassemble(data)
        
        # Reverse padding
        if ObfuscationLayer.PADDING in self._layers:
            result = self._layers[ObfuscationLayer.PADDING].unpad(result)
        
        # Reverse XOR
        if ObfuscationLayer.XOR in self._layers:
            result = self._layers[ObfuscationLayer.XOR].decrypt(result)
        
        # Reverse encoding
        if ObfuscationLayer.ENCODING in self._layers:
            result = self._layers[ObfuscationLayer.ENCODING].decode(result)
        
        return result
    
    def get_timing_delay(self) -> float:
        """Get timing delay if timing obfuscation is enabled."""
        if ObfuscationLayer.TIMING in self._layers:
            return self._layers[ObfuscationLayer.TIMING].get_delay()
        return 0.0
    
    def get_stats(self) -> Dict[str, Any]:
        """Get obfuscation statistics."""
        return {
            "enabled_layers": [l.value for l in self.config.enabled_layers],
            "packet_count": self._packet_count,
        }


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
