"""
Mesh Routing Package.

Provides AODV-like mesh routing with modular components:
- TopologyManager: Node and neighbor management
- RouteTable: Routing table with multi-path support
- PacketHandler: Packet processing and forwarding
- RouteRecovery: Failure detection and healing
- MeshRouter: Main coordinator (facade)
"""

from .topology import TopologyManager, NodeInfo, LinkQuality
from .route_table import RouteTable, RouteEntry
from .packet_handler import PacketHandler, PacketType, RoutingPacket
from .recovery import RouteRecovery
from .router import MeshRouter

__all__ = [
    "MeshRouter",
    "TopologyManager",
    "NodeInfo",
    "LinkQuality",
    "RouteTable",
    "RouteEntry",
    "PacketHandler",
    "PacketType",
    "RoutingPacket",
    "RouteRecovery",
]
