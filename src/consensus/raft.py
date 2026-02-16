"""
Raft Consensus Algorithm (P1)
Scaffold for distributed consensus in x0tta6bl4 mesh
"""

import logging
from typing import Dict, List, Optional

logger = logging.getLogger(__name__)


class RaftNode:
    def __init__(self, node_id: str):
        self.node_id = node_id
        self.state = "follower"
        self.term = 0
        self.voted_for = None
        self.log: List[Dict] = []

    def become_leader(self):
        self.state = "leader"
        logger.info(f"Node {self.node_id} became leader")

    def become_follower(self):
        self.state = "follower"
        logger.info(f"Node {self.node_id} became follower")

    def append_entry(self, entry: Dict):
        self.log.append(entry)
        logger.info(f"Node {self.node_id} appended entry: {entry}")
