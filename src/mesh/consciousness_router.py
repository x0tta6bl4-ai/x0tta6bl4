import asyncio
from dataclasses import dataclass
from typing import Dict, List, Optional

from ..core.consciousness import ConsciousnessMetrics, ConsciousnessState


@dataclass
class MeshPeer:
    peer_id: str
    latency_ms: float
    packet_loss: float
    bandwidth_mbps: float
    consciousness_state: ConsciousnessState
    phi_ratio: float
    trust_score: float  # Zero-Trust validation


class ConsciousnessBasedRouter:
    """
    Mesh routing that prioritizes peers based on consciousness state.

    Philosophy: "Euphoric" nodes (φ > 1.4) receive priority routing.
    This creates positive feedback: healthy nodes get more traffic,
    allowing struggling nodes time to heal.
    """

    def __init__(self):
        self.peers: Dict[str, MeshPeer] = {}
        self.routing_table: Dict[str, List[str]] = {}

        # Latency penalty configuration
        self.latency_penalty_curve = 2.0  # Exponential penalty
        self.fast_reroute_threshold = 150  # ms - trigger immediate reroute

    def update_peer_consciousness(self, peer_id: str, metrics: ConsciousnessMetrics):
        """Update peer's consciousness state"""
        if peer_id in self.peers:
            peer = self.peers[peer_id]
            peer.consciousness_state = metrics.state
            peer.phi_ratio = metrics.phi_ratio

    def calculate_route_score(self, peer: MeshPeer) -> float:
        """
        Calculate routing score based on consciousness state.

        Scoring:
        - EUPHORIC: 1.0x multiplier (φ > 1.4)
        - HARMONIC: 0.8x multiplier (φ > 1.0)
        - CONTEMPLATIVE: 0.5x multiplier (φ > 0.8)
        - MYSTICAL: 0.2x multiplier (φ < 0.8) - minimal traffic for healing
        """
        state_multipliers = {
            ConsciousnessState.EUPHORIC: 1.0,
            ConsciousnessState.HARMONIC: 0.8,
            ConsciousnessState.CONTEMPLATIVE: 0.5,
            ConsciousnessState.MYSTICAL: 0.2,
        }

        multiplier = state_multipliers.get(peer.consciousness_state, 0.5)

        # Aggressive latency penalty logic
        if peer.latency_ms > self.fast_reroute_threshold:
            # Exponential penalty for high latency
            latency_score = 1.0 / (
                1.0 + (peer.latency_ms / 100.0) ** self.latency_penalty_curve
            )
        else:
            # Standard calculation for acceptable latency
            latency_score = 1.0 / (1.0 + peer.latency_ms / 100.0)

        loss_score = max(0.0, 1.0 - peer.packet_loss / 10.0)
        bandwidth_score = min(1.0, peer.bandwidth_mbps / 100.0)
        trust_score = peer.trust_score

        # Increased weight for latency in critical situations
        if peer.latency_ms > self.fast_reroute_threshold:
            base_score = (
                latency_score * 0.6  # Increased from 0.3 for better agility
                + loss_score * 0.2
                + bandwidth_score * 0.1
                + trust_score * 0.1
            )
        else:
            base_score = (
                latency_score * 0.3
                + loss_score * 0.3
                + bandwidth_score * 0.2
                + trust_score * 0.2
            )

        # Apply consciousness multiplier
        final_score = base_score * multiplier

        return final_score

    def select_best_route(
        self, destination: str, exclude_peers: Optional[List[str]] = None
    ) -> Optional[str]:
        """
        Select best peer for routing based on consciousness-aware scoring.
        """
        if exclude_peers is None:
            exclude_peers = []

        eligible_peers = [
            (peer_id, peer)
            for peer_id, peer in self.peers.items()
            if peer_id not in exclude_peers
        ]

        if not eligible_peers:
            return None

        # Score all eligible peers
        scored_peers = [
            (peer_id, self.calculate_route_score(peer))
            for peer_id, peer in eligible_peers
        ]

        # Sort by score (descending)
        scored_peers.sort(key=lambda x: x[1], reverse=True)

        # Return best peer
        return scored_peers[0][0] if scored_peers else None
