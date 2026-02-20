"""
Digital Immune System — Distributed Ban List
============================================

Gossip-based ban propagation with optional eBPF XDP enforcement.

    from src.network.immune import DistributedBanList, BanEntry, BanReason

    ban_list = DistributedBanList(node_id="node-1")
    ban_list.ban("10.0.0.99", reason=BanReason.DOS_ATTACK, ttl=300)
    # Propagate ban to neighbours via serialise_for_gossip()
    # and apply_gossip_update() on the receiving side.
"""

from .ban_list import BanEntry, BanReason, DistributedBanList

__all__ = ["BanEntry", "BanReason", "DistributedBanList"]
