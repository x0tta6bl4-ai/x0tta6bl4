"""
CRDT Data Synchronization (P1)
Scaffold for conflict-free replicated data types in x0tta6bl4
"""
from typing import Dict, Any
import logging

logger = logging.getLogger(__name__)

class GCounter:
    def __init__(self):
        self.counters: Dict[str, int] = {}
    def increment(self, node_id: str, value: int = 1):
        self.counters[node_id] = self.counters.get(node_id, 0) + value
    def merge(self, other: 'GCounter'):
        for node, val in other.counters.items():
            self.counters[node] = max(self.counters.get(node, 0), val)
    def value(self) -> int:
        return sum(self.counters.values())
