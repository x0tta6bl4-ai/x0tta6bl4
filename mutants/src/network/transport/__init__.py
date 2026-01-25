"""
Транспортный слой x0tta6bl4.
Реализует сетевые протоколы с интегрированным шейпингом и обфускацией.
"""

from .websocket_shaped import (
    ShapedWebSocketClient,
    ShapedWebSocketServer,
    ConnectionState,
    ShapedMessage
)

from .udp_shaped import (
    ShapedUDPTransport,
    UDPHolePuncher,
    UDPPacket,
    PacketType,
    PeerInfo
)

__all__ = [
    # WebSocket
    "ShapedWebSocketClient",
    "ShapedWebSocketServer",
    "ConnectionState",
    "ShapedMessage",
    # UDP
    "ShapedUDPTransport",
    "UDPHolePuncher",
    "UDPPacket",
    "PacketType",
    "PeerInfo",
]
