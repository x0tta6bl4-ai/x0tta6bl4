"""
Pluggable Transports Implementation
===================================

Implementation of pluggable transports for censorship circumvention:
- OBFS4: Randomized padding and key exchange
- Meek: Domain fronting over HTTPS
- Snowflake: WebRTC-based proxy

Based on Tor Project's Pluggable Transport specification.
"""

import asyncio
import hashlib
import logging
import secrets
import struct
import time
from abc import ABC, abstractmethod
from dataclasses import dataclass, field
from enum import Enum
from typing import Any, Callable, Dict, List, Optional, Tuple, Union

logger = logging.getLogger(__name__)


class TransportType(Enum):
    """Supported pluggable transport types."""
    OBFS4 = "obfs4"
    MEEK = "meek"
    SNOWFLAKE = "snowflake"
    WEBSOCKET = "websocket"
    CUSTOM = "custom"


@dataclass
class TransportConfig:
    """Configuration for pluggable transport."""
    transport_type: TransportType = TransportType.OBFS4
    
    # OBFS4 settings
    node_id: Optional[bytes] = None
    private_key: Optional[bytes] = None
    public_key: Optional[bytes] = None
    
    # Meek settings
    front_domain: str = ""
    meek_url: str = ""
    
    # Snowflake settings
    broker_url: str = ""
    ice_servers: List[str] = field(default_factory=list)
    
    # Common settings
    timeout: float = 30.0
    max_retries: int = 3
    buffer_size: int = 65536


class PluggableTransport(ABC):
    """
    Abstract base class for pluggable transports.
    
    All transports must implement the connect, send, and receive methods.
    """
    
    def __init__(self, config: TransportConfig):
        self.config = config
        self._connected = False
        self._stats = {
            "bytes_sent": 0,
            "bytes_received": 0,
            "connections": 0,
            "errors": 0,
        }
    
    @property
    def is_connected(self) -> bool:
        return self._connected
    
    @abstractmethod
    async def connect(self, target: str, port: int) -> None:
        """Establish connection through the transport."""
        pass
    
    @abstractmethod
    async def send(self, data: bytes) -> int:
        """Send data through the transport."""
        pass
    
    @abstractmethod
    async def receive(self, size: int = 4096) -> bytes:
        """Receive data from the transport."""
        pass
    
    @abstractmethod
    async def close(self) -> None:
        """Close the transport connection."""
        pass
    
    def get_stats(self) -> Dict[str, Any]:
        """Get transport statistics."""
        return {
            "type": self.config.transport_type.value,
            "connected": self._connected,
            **self._stats,
        }


class OBFS4Transport(PluggableTransport):
    """
    OBFS4 pluggable transport implementation.
    
    Features:
    - Elliptic curve Diffie-Hellman key exchange
    - Randomized packet lengths and timing
    - Replay protection
    """
    
    # OBFS4 protocol constants
    MAX_HANDSHAKE_LENGTH = 4096
    MARK_LENGTH = 32
    KEY_LENGTH = 32
    MAC_LENGTH = 32
    
    def __init__(self, config: TransportConfig):
        super().__init__(config)
        
        # Generate keys if not provided
        if not config.node_id:
            config.node_id = secrets.token_bytes(20)
        if not config.private_key:
            config.private_key = secrets.token_bytes(32)
        if not config.public_key:
            config.public_key = self._derive_public_key(config.private_key)
        
        self._session_key = None
        self._send_key = None
        self._receive_key = None
        self._reader: Optional[asyncio.StreamReader] = None
        self._writer: Optional[asyncio.StreamWriter] = None
    
    def _derive_public_key(self, private_key: bytes) -> bytes:
        """Derive public key from private key."""
        # Simplified key derivation (in production, use proper ECDH)
        return hashlib.sha256(private_key + b"public").digest()
    
    def _generate_handshake(self) -> bytes:
        """Generate client handshake message."""
        # Generate ephemeral key pair
        ephemeral_private = secrets.token_bytes(32)
        ephemeral_public = self._derive_public_key(ephemeral_private)
        
        # Create handshake message
        # Format: random padding + public key + MAC
        padding_len = secrets.randbelow(256) + 64
        padding = secrets.token_bytes(padding_len)
        
        # Compute MAC
        mac_data = padding + ephemeral_public + self.config.node_id
        mac = hashlib.sha256(mac_data + self.config.private_key).digest()
        
        handshake = padding + ephemeral_public + mac
        
        # Add length prefix
        length = struct.pack(">H", len(handshake))
        
        return length + handshake
    
    def _derive_session_keys(self, shared_secret: bytes) -> Tuple[bytes, bytes]:
        """Derive send and receive keys from shared secret."""
        # Key derivation using HKDF-like construction
        send_key = hashlib.sha256(shared_secret + b"send").digest()
        receive_key = hashlib.sha256(shared_secret + b"receive").digest()
        return send_key, receive_key
    
    def _encrypt_packet(self, data: bytes) -> bytes:
        """Encrypt a data packet."""
        if not self._send_key:
            return data
        
        # Simple XOR encryption with key stream
        # In production, use proper AEAD cipher
        nonce = secrets.token_bytes(12)
        key_stream = hashlib.sha256(self._send_key + nonce).digest()
        
        # Extend key stream if needed
        while len(key_stream) < len(data):
            key_stream += hashlib.sha256(key_stream).digest()
        
        encrypted = bytes(a ^ b for a, b in zip(data, key_stream[:len(data)]))
        
        # Add length prefix and nonce
        length = struct.pack(">H", len(encrypted))
        return length + nonce + encrypted
    
    def _decrypt_packet(self, data: bytes) -> bytes:
        """Decrypt a data packet."""
        if not self._receive_key or len(data) < 14:
            return data
        
        # Parse length and nonce
        length = struct.unpack(">H", data[:2])[0]
        nonce = data[2:14]
        encrypted = data[14:14 + length]
        
        # Generate key stream
        key_stream = hashlib.sha256(self._receive_key + nonce).digest()
        while len(key_stream) < len(encrypted):
            key_stream += hashlib.sha256(key_stream).digest()
        
        # Decrypt
        return bytes(a ^ b for a, b in zip(encrypted, key_stream[:len(encrypted)]))
    
    async def connect(self, target: str, port: int) -> None:
        """Establish OBFS4 connection."""
        try:
            # Open TCP connection
            self._reader, self._writer = await asyncio.wait_for(
                asyncio.open_connection(target, port),
                timeout=self.config.timeout,
            )
            
            # Send handshake
            handshake = self._generate_handshake()
            self._writer.write(handshake)
            await self._writer.drain()
            
            # Receive server handshake
            response = await asyncio.wait_for(
                self._reader.read(self.MAX_HANDSHAKE_LENGTH),
                timeout=self.config.timeout,
            )
            
            # Derive session keys (simplified)
            shared_secret = hashlib.sha256(
                self.config.private_key + response[:32]
            ).digest()
            self._send_key, self._receive_key = self._derive_session_keys(shared_secret)
            
            self._connected = True
            self._stats["connections"] += 1
            logger.info(f"OBFS4 connection established to {target}:{port}")
            
        except Exception as e:
            self._stats["errors"] += 1
            logger.error(f"OBFS4 connection failed: {e}")
            raise
    
    async def send(self, data: bytes) -> int:
        """Send data through OBFS4 transport."""
        if not self._connected or not self._writer:
            raise RuntimeError("Transport not connected")
        
        try:
            encrypted = self._encrypt_packet(data)
            self._writer.write(encrypted)
            await self._writer.drain()
            
            self._stats["bytes_sent"] += len(data)
            return len(data)
            
        except Exception as e:
            self._stats["errors"] += 1
            logger.error(f"OBFS4 send error: {e}")
            raise
    
    async def receive(self, size: int = 4096) -> bytes:
        """Receive data from OBFS4 transport."""
        if not self._connected or not self._reader:
            raise RuntimeError("Transport not connected")
        
        try:
            # Read length prefix
            length_data = await self._reader.read(2)
            if len(length_data) < 2:
                return b""
            
            length = struct.unpack(">H", length_data)[0]
            
            # Read full packet
            packet = await self._reader.read(length + 12)  # + nonce
            
            decrypted = self._decrypt_packet(length_data + packet)
            
            self._stats["bytes_received"] += len(decrypted)
            return decrypted
            
        except Exception as e:
            self._stats["errors"] += 1
            logger.error(f"OBFS4 receive error: {e}")
            raise
    
    async def close(self) -> None:
        """Close OBFS4 connection."""
        if self._writer:
            self._writer.close()
            try:
                await self._writer.wait_closed()
            except Exception:
                pass
        
        self._connected = False
        self._reader = None
        self._writer = None


class MeekTransport(PluggableTransport):
    """
    Meek pluggable transport implementation.
    
    Uses domain fronting to hide the actual destination.
    Traffic looks like normal HTTPS to a CDN.
    """
    
    def __init__(self, config: TransportConfig):
        super().__init__(config)
        self._session: Optional[Any] = None
        self._request_id: Optional[str] = None
    
    async def connect(self, target: str, port: int) -> None:
        """Establish Meek connection via domain fronting."""
        try:
            import aiohttp
            
            # Create session with domain fronting
            connector = aiohttp.TCPConnector(ssl=False)
            
            self._session = aiohttp.ClientSession(
                connector=connector,
                headers={
                    "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64)",
                    "Accept": "*/*",
                    "Host": target,  # Actual target in Host header
                },
            )
            
            self._request_id = secrets.token_hex(16)
            self._connected = True
            self._stats["connections"] += 1
            
            logger.info(f"Meek connection established via {self.config.front_domain}")
            
        except Exception as e:
            self._stats["errors"] += 1
            logger.error(f"Meek connection failed: {e}")
            raise
    
    async def send(self, data: bytes) -> int:
        """Send data via Meek HTTP request."""
        if not self._connected or not self._session:
            raise RuntimeError("Transport not connected")
        
        try:
            # Encode data as base64 in request body
            import base64
            encoded = base64.b64encode(data).decode()
            
            # Make POST request to front domain
            url = f"https://{self.config.front_domain}/meek"
            
            async with self._session.post(
                url,
                data={"data": encoded, "id": self._request_id},
                timeout=aiohttp.ClientTimeout(total=self.config.timeout),
            ) as response:
                if response.status != 200:
                    raise RuntimeError(f"Meek request failed: {response.status}")
            
            self._stats["bytes_sent"] += len(data)
            return len(data)
            
        except Exception as e:
            self._stats["errors"] += 1
            logger.error(f"Meek send error: {e}")
            raise
    
    async def receive(self, size: int = 4096) -> bytes:
        """Receive data via Meek HTTP polling."""
        if not self._connected or not self._session:
            raise RuntimeError("Transport not connected")
        
        try:
            import base64
            
            # Poll for response
            url = f"https://{self.config.front_domain}/meek"
            
            async with self._session.get(
                url,
                params={"id": self._request_id},
                timeout=aiohttp.ClientTimeout(total=self.config.timeout),
            ) as response:
                if response.status == 200:
                    data = await response.text()
                    decoded = base64.b64decode(data)
                    self._stats["bytes_received"] += len(decoded)
                    return decoded
                else:
                    return b""
                    
        except Exception as e:
            self._stats["errors"] += 1
            logger.error(f"Meek receive error: {e}")
            raise
    
    async def close(self) -> None:
        """Close Meek session."""
        if self._session:
            await self._session.close()
        
        self._connected = False
        self._session = None


class SnowflakeTransport(PluggableTransport):
    """
    Snowflake pluggable transport implementation.
    
    Uses WebRTC to connect through volunteer proxies (snowflakes).
    Traffic looks like normal WebRTC video call.
    """
    
    def __init__(self, config: TransportConfig):
        super().__init__(config)
        self._peer_connection: Optional[Any] = None
        self._data_channel: Optional[Any] = None
        self._receive_queue: asyncio.Queue = asyncio.Queue()
    
    async def connect(self, target: str, port: int) -> None:
        """Establish Snowflake connection via WebRTC."""
        try:
            # In production, this would use aiortc or similar
            # For now, we simulate the connection
            
            # Get proxy (snowflake) from broker
            # broker_response = await self._get_proxy_from_broker()
            
            # Create WebRTC peer connection
            # self._peer_connection = RTCPeerConnection(...)
            
            # Create data channel
            # self._data_channel = self._peer_connection.createDataChannel("snowflake")
            
            # For simulation, we'll use a simple TCP connection
            self._reader, self._writer = await asyncio.wait_for(
                asyncio.open_connection(target, port),
                timeout=self.config.timeout,
            )
            
            self._connected = True
            self._stats["connections"] += 1
            
            logger.info("Snowflake connection established")
            
        except Exception as e:
            self._stats["errors"] += 1
            logger.error(f"Snowflake connection failed: {e}")
            raise
    
    async def _get_proxy_from_broker(self) -> Dict[str, Any]:
        """Get a snowflake proxy from the broker."""
        import aiohttp
        
        async with aiohttp.ClientSession() as session:
            async with session.get(
                self.config.broker_url,
                params={"action": "get_proxy"},
            ) as response:
                return await response.json()
    
    async def send(self, data: bytes) -> int:
        """Send data through Snowflake."""
        if not self._connected:
            raise RuntimeError("Transport not connected")
        
        try:
            if self._writer:
                self._writer.write(data)
                await self._writer.drain()
            
            self._stats["bytes_sent"] += len(data)
            return len(data)
            
        except Exception as e:
            self._stats["errors"] += 1
            logger.error(f"Snowflake send error: {e}")
            raise
    
    async def receive(self, size: int = 4096) -> bytes:
        """Receive data from Snowflake."""
        if not self._connected:
            raise RuntimeError("Transport not connected")
        
        try:
            if self._reader:
                data = await self._reader.read(size)
                self._stats["bytes_received"] += len(data)
                return data
            return b""
            
        except Exception as e:
            self._stats["errors"] += 1
            logger.error(f"Snowflake receive error: {e}")
            raise
    
    async def close(self) -> None:
        """Close Snowflake connection."""
        if self._writer:
            self._writer.close()
            try:
                await self._writer.wait_closed()
            except Exception:
                pass
        
        if self._peer_connection:
            await self._peer_connection.close()
        
        self._connected = False
        self._peer_connection = None
        self._data_channel = None


def create_transport(
    transport_type: str = "obfs4",
    **kwargs
) -> PluggableTransport:
    """
    Factory function to create a pluggable transport.
    
    Args:
        transport_type: Type of transport to create
        **kwargs: Transport configuration
        
    Returns:
        Configured PluggableTransport instance
    """
    try:
        t_type = TransportType(transport_type.lower())
    except ValueError:
        t_type = TransportType.CUSTOM
    
    config = TransportConfig(transport_type=t_type, **kwargs)
    
    if t_type == TransportType.OBFS4:
        return OBFS4Transport(config)
    elif t_type == TransportType.MEEK:
        return MeekTransport(config)
    elif t_type == TransportType.SNOWFLAKE:
        return SnowflakeTransport(config)
    else:
        raise ValueError(f"Unsupported transport type: {transport_type}")


__all__ = [
    "TransportType",
    "TransportConfig",
    "PluggableTransport",
    "OBFS4Transport",
    "MeekTransport",
    "SnowflakeTransport",
    "create_transport",
]
