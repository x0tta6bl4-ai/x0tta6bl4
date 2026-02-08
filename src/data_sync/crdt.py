"""
CRDT Data Synchronization for x0tta6bl4 Mesh Network

Conflict-Free Replicated Data Types (CRDTs) for eventually consistent
state synchronization across decentralized mesh nodes without coordination.

Implements state-based (CvRDT) variants:
- GCounter: grow-only counter
- PNCounter: positive-negative counter (increment + decrement)
- LWWRegister: last-writer-wins register with Lamport timestamps
- GSet: grow-only set
- ORSet: observed-remove set with unique tags
- LWWMap: last-writer-wins map (key -> LWWRegister)
"""
from __future__ import annotations

import time
import uuid
import logging
from typing import Dict, Set, Tuple, Any, Optional, FrozenSet
from dataclasses import dataclass, field

logger = logging.getLogger(__name__)


class GCounter:
    """Grow-only counter. Each node maintains its own count; total is the sum."""

    def __init__(self):
        self.counters: Dict[str, int] = {}

    def increment(self, node_id: str, value: int = 1):
        if value < 0:
            raise ValueError("GCounter only supports non-negative increments")
        self.counters[node_id] = self.counters.get(node_id, 0) + value

    def merge(self, other: GCounter):
        for node, val in other.counters.items():
            self.counters[node] = max(self.counters.get(node, 0), val)

    def value(self) -> int:
        return sum(self.counters.values())

    def to_dict(self) -> Dict[str, int]:
        return dict(self.counters)

    @classmethod
    def from_dict(cls, data: Dict[str, int]) -> GCounter:
        c = cls()
        c.counters = dict(data)
        return c


class PNCounter:
    """
    Positive-Negative counter supporting both increment and decrement.
    Internally uses two GCounters: one for increments (P), one for decrements (N).
    Value = P.value() - N.value()
    """

    def __init__(self):
        self.p = GCounter()
        self.n = GCounter()

    def increment(self, node_id: str, value: int = 1):
        if value < 0:
            raise ValueError("Use decrement() for negative values")
        self.p.increment(node_id, value)

    def decrement(self, node_id: str, value: int = 1):
        if value < 0:
            raise ValueError("Decrement value must be non-negative")
        self.n.increment(node_id, value)

    def merge(self, other: PNCounter):
        self.p.merge(other.p)
        self.n.merge(other.n)

    def value(self) -> int:
        return self.p.value() - self.n.value()

    def to_dict(self) -> Dict[str, Any]:
        return {"p": self.p.to_dict(), "n": self.n.to_dict()}

    @classmethod
    def from_dict(cls, data: Dict[str, Any]) -> PNCounter:
        c = cls()
        c.p = GCounter.from_dict(data["p"])
        c.n = GCounter.from_dict(data["n"])
        return c


class LWWRegister:
    """
    Last-Writer-Wins Register. Stores a single value with a Lamport timestamp.
    On merge, the value with the higher timestamp wins.
    Ties are broken by comparing values lexicographically (deterministic).
    """

    def __init__(self, value: Any = None, timestamp: float = 0.0):
        self._value = value
        self._timestamp = timestamp

    @property
    def value(self) -> Any:
        return self._value

    @property
    def timestamp(self) -> float:
        return self._timestamp

    def set(self, value: Any, timestamp: Optional[float] = None):
        ts = timestamp if timestamp is not None else time.monotonic()
        if ts > self._timestamp:
            self._value = value
            self._timestamp = ts
        elif ts == self._timestamp:
            # Deterministic tie-break: higher value wins
            if str(value) > str(self._value):
                self._value = value
                self._timestamp = ts

    def merge(self, other: LWWRegister):
        if other._timestamp > self._timestamp:
            self._value = other._value
            self._timestamp = other._timestamp
        elif other._timestamp == self._timestamp:
            if str(other._value) > str(self._value):
                self._value = other._value
                self._timestamp = other._timestamp

    def to_dict(self) -> Dict[str, Any]:
        return {"value": self._value, "timestamp": self._timestamp}

    @classmethod
    def from_dict(cls, data: Dict[str, Any]) -> LWWRegister:
        return cls(value=data["value"], timestamp=data["timestamp"])


class GSet:
    """Grow-only set. Elements can be added but never removed."""

    def __init__(self):
        self._elements: Set[Any] = set()

    def add(self, element: Any):
        self._elements.add(element)

    def contains(self, element: Any) -> bool:
        return element in self._elements

    def merge(self, other: GSet):
        self._elements |= other._elements

    def value(self) -> FrozenSet[Any]:
        return frozenset(self._elements)

    def __len__(self) -> int:
        return len(self._elements)

    def to_dict(self) -> list:
        return sorted(str(e) for e in self._elements)

    @classmethod
    def from_dict(cls, data: list) -> GSet:
        s = cls()
        s._elements = set(data)
        return s


class ORSet:
    """
    Observed-Remove Set (OR-Set).

    Supports both add and remove operations without conflicts.
    Each add generates a unique tag. Remove only removes observed tags,
    so concurrent add + remove results in the element being present
    (add-wins semantics).
    """

    def __init__(self):
        # element -> set of unique tags
        self._adds: Dict[Any, Set[str]] = {}
        # set of removed tags (tombstones)
        self._removes: Set[str] = set()

    def add(self, element: Any, node_id: str = ""):
        tag = f"{node_id}:{uuid.uuid4().hex[:12]}"
        if element not in self._adds:
            self._adds[element] = set()
        self._adds[element].add(tag)

    def remove(self, element: Any):
        if element in self._adds:
            # Observe all current tags for this element and tombstone them
            self._removes |= self._adds[element]
            del self._adds[element]

    def contains(self, element: Any) -> bool:
        if element not in self._adds:
            return False
        alive_tags = self._adds[element] - self._removes
        return len(alive_tags) > 0

    def merge(self, other: ORSet):
        # Merge adds: union of all tags per element
        for elem, tags in other._adds.items():
            if elem not in self._adds:
                self._adds[elem] = set()
            self._adds[elem] |= tags
        # Merge removes: union of tombstones
        self._removes |= other._removes
        # Clean up: remove elements where all tags are tombstoned
        empty = []
        for elem, tags in self._adds.items():
            alive = tags - self._removes
            if not alive:
                empty.append(elem)
            else:
                self._adds[elem] = alive
        for elem in empty:
            del self._adds[elem]

    def value(self) -> FrozenSet[Any]:
        result = set()
        for elem, tags in self._adds.items():
            alive = tags - self._removes
            if alive:
                result.add(elem)
        return frozenset(result)

    def __len__(self) -> int:
        return len(self.value())

    def to_dict(self) -> Dict[str, Any]:
        return {
            "adds": {str(k): sorted(v) for k, v in self._adds.items()},
            "removes": sorted(self._removes),
        }

    @classmethod
    def from_dict(cls, data: Dict[str, Any]) -> ORSet:
        s = cls()
        s._adds = {k: set(v) for k, v in data["adds"].items()}
        s._removes = set(data["removes"])
        return s


class LWWMap:
    """
    Last-Writer-Wins Map. Maps keys to values using LWWRegister per key
    with an ORSet tracking which keys are alive.

    Supports set(key, value) and delete(key) with LWW conflict resolution.
    """

    def __init__(self):
        self._registers: Dict[str, LWWRegister] = {}
        self._keys = ORSet()
        self._node_id = uuid.uuid4().hex[:8]

    def set(self, key: str, value: Any, timestamp: Optional[float] = None):
        ts = timestamp if timestamp is not None else time.monotonic()
        if key not in self._registers:
            self._registers[key] = LWWRegister()
        self._registers[key].set(value, ts)
        self._keys.add(key, self._node_id)

    def get(self, key: str) -> Optional[Any]:
        if not self._keys.contains(key):
            return None
        reg = self._registers.get(key)
        return reg.value if reg else None

    def delete(self, key: str):
        self._keys.remove(key)

    def merge(self, other: LWWMap):
        for key, reg in other._registers.items():
            if key not in self._registers:
                self._registers[key] = LWWRegister()
            self._registers[key].merge(reg)
        self._keys.merge(other._keys)

    def keys(self) -> FrozenSet[str]:
        return self._keys.value()

    def to_dict(self) -> Dict[str, Any]:
        return {k: self.get(k) for k in self.keys()}

    def __len__(self) -> int:
        return len(self.keys())
