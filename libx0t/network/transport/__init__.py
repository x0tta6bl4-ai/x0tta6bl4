"""
Транспортный слой x0tta6bl4.
Реализует сетевые протоколы с интегрированным шейпингом и обфускацией.
"""

from .udp_shaped import (PacketType, PeerInfo, ShapedUDPTransport,
                         UDPHolePuncher, UDPPacket)
from .websocket_shaped import (ConnectionState, ShapedMessage,
                               ShapedWebSocketClient, ShapedWebSocketServer)

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
