"""
Digital Stigmergy Routing Module.
Implements 'Pheromone-based' routing logic for x0tta6bl4 MaaS.

Concept:
- Packets leave 'digital pheromones' (scores) on successful transmission.
- Routes with higher scores are preferred.
- Scores decay over time (evaporation), allowing the network to adapt to changes.
"""

import logging
import time
import asyncio
from typing import Dict, Optional, List
from dataclasses import dataclass

logger = logging.getLogger(__name__)

# Config
PHEROMONE_DECAY_RATE = 0.9  # Multiply score by this every tick
PHEROMONE_BOOST = 10.0      # Add this to score on success
PHEROMONE_MIN = 1.0         # Minimum score to keep a route 'alive'
DECAY_INTERVAL = 1.0        # Seconds

@dataclass
class RoutePheromone:
    peer_id: str
    score: float = PHEROMONE_MIN
    last_updated: float = 0.0

class StigmergyRouter:
    """
    Manages routing scores (pheromones) for mesh peers with ACL enforcement.
    """
    def __init__(self, node_id: str):
        self.node_id = node_id
        # Map: Destination_Node_ID -> { Next_Hop_Peer_ID -> Score }
        self._pheromones: Dict[str, Dict[str, RoutePheromone]] = {}
        self._running = False
        self._decay_task: Optional[asyncio.Task] = None
        
        # ACL State
        self.my_tags: List[str] = ["default"]
        self.peer_tags: Dict[str, List[str]] = {} # node_id -> [tags]
        self.policies: List[Dict] = [] # Allowed tag-to-tag connections

    def update_policies(self, policies: List[Dict], peer_tags: Dict[str, List[str]]):
        """Update local ACL state from Control Plane."""
        self.policies = policies
        self.peer_tags = peer_tags
        logger.info(f"🛡️ Router ACL updated: {len(policies)} rules active.")

    def _is_allowed(self, target_id: str) -> bool:
        """Check if communication with target is allowed by policies."""
        if not self.policies:
            return True # Default allow if no policies (Dev mode)
            
        target_tags = self.peer_tags.get(target_id, ["default"])
        
        for policy in self.policies:
            # Check if any of my tags match source_tag AND any of target tags match target_tag
            src_match = policy["source_tag"] == "*" or policy["source_tag"] in self.my_tags
            dst_match = policy["target_tag"] == "*" or policy["target_tag"] in target_tags
            
            if src_match and dst_match:
                return policy["action"] == "allow"
                
        return False # Zero-Trust: Default deny if no matching policy found

    def reinforce(self, dest_id: str, next_hop: str, success: bool = True):
        """
        Reinforce a path, but only if ACL allows it.
        """
        if not self._is_allowed(dest_id):
            # logger.warning(f"🚫 ACL Deny: Dropping pheromone reinforcement for {dest_id}")
            return

        now = time.time()
        
        if dest_id not in self._pheromones:
            self._pheromones[dest_id] = {}
        
        if next_hop not in self._pheromones[dest_id]:
            self._pheromones[dest_id][next_hop] = RoutePheromone(peer_id=next_hop, last_updated=now)

        route = self._pheromones[dest_id][next_hop]
        
        if success:
            # Add pheromone (linear boost)
            route.score += PHEROMONE_BOOST
            # Cap score to prevent infinity? Maybe logic sigmoid later.
            # For now simple linear is fine for MVP.
        else:
            # Punish heavily (negative reinforcement)
            route.score *= 0.5 
        
        route.last_updated = now
        # logger.debug(f"Pheromone update: {dest_id} via {next_hop} = {route.score:.2f}")

    def get_best_route(self, dest_id: str) -> Optional[str]:
        """Get the next hop with the highest pheromone score."""
        paths = self.get_redundant_paths(dest_id, limit=1)
        return paths[0] if paths else None

    def get_redundant_paths(self, dest_id: str, limit: int = 3) -> List[str]:
        """
        Returns top-N next hops for a destination.
        Enables 'Make-Make-Never-Break' multi-path logic.
        """
        if dest_id not in self._pheromones:
            return []
        
        routes = self._pheromones[dest_id]
        if not routes:
            return []
            
        # Sort by score descending and filter dead routes
        sorted_routes = sorted(
            [r for r in routes.values() if r.score >= PHEROMONE_MIN],
            key=lambda r: r.score,
            reverse=True
        )
        
        return [r.peer_id for r in sorted_routes[:limit]]

    async def _evaporation_loop(self):
        """
        Periodically decays all scores.
        Simulates nature: paths not used eventually disappear.
        """
        while self._running:
            await asyncio.sleep(DECAY_INTERVAL)
            self._evaporate()

    def _evaporate(self):
        """Apply decay function to all scores."""
        empty_dests = []
        
        for dest_id, routes in self._pheromones.items():
            dead_routes = []
            for hop, route in routes.items():
                route.score *= PHEROMONE_DECAY_RATE
                
                # If score drops below baseline, it effectively disappears
                if route.score < PHEROMONE_MIN:
                    # Don't delete immediately, maybe keep as "known but bad"
                    # But for memory efficiency, we can prune very low scores
                    if route.score < 0.1:
                        dead_routes.append(hop)
            
            for hop in dead_routes:
                del routes[hop]
                
            if not routes:
                empty_dests.append(dest_id)
                
        for dest in empty_dests:
            del self._pheromones[dest]

    def get_routing_table_snapshot(self) -> Dict:
        """Return raw data for visualization/debugging."""
        snapshot = {}
        for dest, routes in self._pheromones.items():
            snapshot[dest] = {
                hop: round(r.score, 2) for hop, r in routes.items()
            }
        return snapshot
