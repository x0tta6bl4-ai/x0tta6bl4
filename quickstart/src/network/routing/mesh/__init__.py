"""
Mesh Router Package

A modular AODV-like mesh routing protocol implementation with:
- Reactive route discovery (RREQ/RREP)
- Multi-hop forwarding
- Route maintenance with RERR
- Loop prevention via TTL and sequence numbers
- Multi-path support (k-disjoint routes)
- HMAC packet authentication
- CRDT synchronization support

Example:
    >>> from src.network.routing.mesh import MeshRouter
    >>> router = MeshRouter("node_1", shared_secret=b"secret")
    >>> await router.start()
    >>> router.add_neighbor("node_2")
    >>> await router.send("node_3", b"Hello")

Modules:
    - models: Packet types and data structures
    - security: HMAC packet authentication
    - routing_table: Route management
    - forwarding: Packet forwarding and broadcast
    - statistics: Stats tracking and MAPE-K metrics
    - router: Main MeshRouter class
"""
from __future__ import annotations

from typing import Any

# Public API
__all__ = [
    # Main class
    "MeshRouter",
    # Models
    "PacketType",
    "RouteEntry",
    "RoutingPacket",
    # Components
    "RoutingTable",
    "PacketSecurity",
    "RouterStatistics",
    "PacketForwarder",
    "DeduplicationManager",
]


def __getattr__(name: str) -> Any:
    """
    Lazy loading for memory efficiency.
    
    Modules are only imported when their contents are accessed.
    """
    # Main class
    if name == "MeshRouter":
        from .router import MeshRouter
        return MeshRouter
    
    # Models
    if name in ("PacketType", "RouteEntry", "RoutingPacket"):
        from . import models
        return getattr(models, name)
    
    # Components
    if name == "RoutingTable":
        from .routing_table import RoutingTable
        return RoutingTable
    
    if name == "PacketSecurity":
        from .security import PacketSecurity
        return PacketSecurity
    
    if name == "RouterStatistics":
        from .statistics import RouterStatistics
        return RouterStatistics
    
    if name in ("PacketForwarder", "DeduplicationManager"):
        from . import forwarding
        return getattr(forwarding, name)
    
    raise AttributeError(f"module {__name__!r} has no attribute {name!r}")


# Package metadata
__version__ = "2.0.0"
__author__ = "MaaS Team"

