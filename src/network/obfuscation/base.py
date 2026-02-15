"""
Obfuscation Layer for x0tta6bl4 Mesh Network.
Provides pluggable transport obfuscation to bypass DPI (Deep Packet Inspection).
"""

import socket
from abc import ABC, abstractmethod
from typing import Optional, Tuple


class ObfuscationTransport(ABC):
    """Abstract base class for obfuscation transports."""

    @abstractmethod
    def wrap_socket(self, sock: socket.socket) -> socket.socket:
        """Wrap a socket with obfuscation layer."""
        pass

    @abstractmethod
    def obfuscate(self, data: bytes) -> bytes:
        """Obfuscate data packet."""
        pass

    @abstractmethod
    def deobfuscate(self, data: bytes) -> bytes:
        """De-obfuscate data packet."""
        pass


class TransportManager:
    """Factory for creating and managing obfuscation transports."""

    _transports = {}

    @classmethod
    def register(cls, name: str, transport_class):
        cls._transports[name] = transport_class

    @classmethod
    def create(cls, name: str, **kwargs) -> Optional[ObfuscationTransport]:
        if name not in cls._transports:
            return None
        return cls._transports[name](**kwargs)
