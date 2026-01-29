"""
CRDT Synchronization (P1)
------------------------
Implements several CRDT types and a lightweight sync manager abstraction.
Designed for integration with mesh networking layer in later phases.
"""
from __future__ import annotations
from dataclasses import dataclass, field
from typing import Any, Dict, Set, Callable
from datetime import datetime
from abc import ABC, abstractmethod
import logging

logger = logging.getLogger(__name__)

# ---------------------------------------------------------------------------
# Base Interface
# ---------------------------------------------------------------------------
class CRDT(ABC):
    @abstractmethod
    def merge(self, other: "CRDT"):
        pass

    @abstractmethod
    def value(self) -> Any:
        pass

# ---------------------------------------------------------------------------
# LWW Register
# ---------------------------------------------------------------------------
@dataclass
class LWWRegister(CRDT):
    value_data: Any = None
    timestamp: datetime = field(default_factory=datetime.now)
    node_id: str = ""

    def set(self, value: Any, node_id: str):
        now = datetime.now()
        # last-writer-wins: higher timestamp or tie-break by node id
        if (now > self.timestamp) or (now == self.timestamp and node_id > self.node_id):
            self.value_data = value
            self.timestamp = now
            self.node_id = node_id
            logger.debug(f"LWWRegister updated value={value} node={node_id}")

    def merge(self, other: "CRDT"):
        # Accept any CRDT; only merge if compatible type
        if isinstance(other, LWWRegister):
            if (other.timestamp > self.timestamp) or (
                other.timestamp == self.timestamp and other.node_id > self.node_id
            ):
                self.value_data = other.value_data
                self.timestamp = other.timestamp
                self.node_id = other.node_id

    def value(self) -> Any:
        return self.value_data

    def to_dict(self) -> Dict[str, Any]:
        """Convert to JSON-serializable dict."""
        return {
            "value_data": self.value_data,
            "timestamp": self.timestamp.isoformat() if self.timestamp else None,
            "node_id": self.node_id
        }

# ---------------------------------------------------------------------------
# Counter (G-Counter style - grow only, merge by max per node then sum)
# ---------------------------------------------------------------------------
@dataclass
class Counter(CRDT):
    values: Dict[str, int] = field(default_factory=lambda: {})  # Dict[str,int]

    def increment(self, node_id: str, amount: int = 1):
        self.values[node_id] = self.values.get(node_id, 0) + amount
        logger.debug(f"Counter increment node={node_id} amount={amount}")

    def merge(self, other: "CRDT"):
        if isinstance(other, Counter):
            for nid, val in other.values.items():
                if nid not in self.values:
                    self.values[nid] = val
                else:
                    self.values[nid] = max(self.values[nid], val)

    def value(self) -> int:
        return sum(self.values.values())

# ---------------------------------------------------------------------------
# OR-Set (Observed-Remove Set)
# ---------------------------------------------------------------------------
@dataclass
class ORSet(CRDT):
    elements: Dict[Any, Set[str]] = field(default_factory=lambda: {})  # element -> set[str]
    tombstones: Set[str] = field(default_factory=lambda: set())

    def add(self, element: Any, tag_id: str):
        if element not in self.elements:
            self.elements[element] = set()
        self.elements[element].add(tag_id)
        logger.debug(f"ORSet add element={element} tag={tag_id}")

    def remove(self, element: Any):
        if element in self.elements:
            # tombstone all tags for that element
            self.tombstones.update(self.elements[element])
            del self.elements[element]
            logger.debug(f"ORSet remove element={element}")

    def merge(self, other: "CRDT"):
        if isinstance(other, ORSet):
            # merge additions
            for element, tags in other.elements.items():
                if element not in self.elements:
                    self.elements[element] = set()
                self.elements[element].update(tags)
            # merge tombstones
            self.tombstones.update(other.tombstones)
            # purge fully tombstoned elements
            for element in list(self.elements.keys()):
                if self.elements[element].issubset(self.tombstones):
                    del self.elements[element]

    def value(self) -> Set[Any]:
        return set(self.elements.keys())

# ---------------------------------------------------------------------------
# Sync Manager
# ---------------------------------------------------------------------------
class CRDTSync:
    def __init__(self, node_id: str):
        self.node_id = node_id
        self.crdts: Dict[str, CRDT] = {}
        self.sync_callbacks: Set[Callable[[Dict[str, Any]], None]] = set()

    def register_crdt(self, key: str, crdt: CRDT):
        self.crdts[key] = crdt
        logger.info(f"[{self.node_id}] Registered CRDT key={key} type={crdt.__class__.__name__}")

    def merge_from_peer(self, peer_id: str, updates: Dict[str, CRDT]):
        logger.info(f"[{self.node_id}] Merge from peer={peer_id} keys={list(updates.keys())}")
        for key, peer_crdt in updates.items():
            if key in self.crdts:
                self.crdts[key].merge(peer_crdt)

    def get_crdt_state(self) -> Dict[str, Any]:
        return {key: crdt.value() for key, crdt in self.crdts.items()}

    def broadcast(self):
        state = self.get_crdt_state()
        logger.debug(f"[{self.node_id}] Broadcast state={state}")
        for cb in list(self.sync_callbacks):
            try:
                cb(state)
            except Exception as e:  # pragma: no cover
                logger.error(f"Sync callback error: {e}")

    def register_sync_callback(self, cb: Callable[[Dict[str, Any]], None]):
        self.sync_callbacks.add(cb)

