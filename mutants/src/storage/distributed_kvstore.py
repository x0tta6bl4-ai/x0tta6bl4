"""
Distributed Key-Value Store (P1)
--------------------------------
Local store + Raft-integrated replication facade. Snapshots for recovery.
"""
from __future__ import annotations
from dataclasses import dataclass, field
from typing import Any, Dict, Optional, List, Callable
from datetime import datetime
import json
import logging

logger = logging.getLogger(__name__)

# ---------------------------------------------------------------------------
# Snapshot
# ---------------------------------------------------------------------------
@dataclass
class KVSnapshot:
    term: int
    index: int
    data: Dict[str, Any]
    timestamp: datetime = field(default_factory=datetime.now)

    def to_dict(self) -> Dict[str, Any]:
        return {
            "term": self.term,
            "index": self.index,
            "data": self.data,
            "timestamp": self.timestamp.isoformat(),
        }

# ---------------------------------------------------------------------------
# Local Store
# ---------------------------------------------------------------------------
class DistributedKVStore:
    def __init__(self, node_id: str):
        self.node_id = node_id
        self.store: Dict[str, Any] = {}
        self.versions: Dict[str, int] = {}
        self.last_applied: int = 0
        self.snapshots: List[KVSnapshot] = []
        self.write_callbacks: List[Callable[[Dict[str, Any]], None]] = []
        self.read_callbacks: List[Callable[[Dict[str, Any]], None]] = []

    # Write operations
    def put(self, key: str, value: Any) -> bool:
        self.store[key] = value
        self.versions[key] = self.versions.get(key, 0) + 1
        logger.info(f"[{self.node_id}] PUT {key}={value}")
        for cb in self.write_callbacks:
            cb({"op": "put", "key": key, "value": value})
        return True

    def delete(self, key: str) -> bool:
        if key in self.store:
            del self.store[key]
            self.versions[key] = self.versions.get(key, 0) + 1
            logger.info(f"[{self.node_id}] DELETE {key}")
            for cb in self.write_callbacks:
                cb({"op": "delete", "key": key})
            return True
        return False

    def update(self, key: str, value: Any) -> bool:
        if key in self.store:
            old = self.store[key]
            self.store[key] = value
            self.versions[key] = self.versions.get(key, 0) + 1
            logger.info(f"[{self.node_id}] UPDATE {key}: {old} -> {value}")
            for cb in self.write_callbacks:
                cb({"op": "update", "key": key, "old": old, "new": value})
            return True
        return False

    # Read operations
    def get(self, key: str) -> Optional[Any]:
        val = self.store.get(key)
        for cb in self.read_callbacks:
            cb({"op": "get", "key": key, "found": key in self.store})
        return val

    def get_all(self) -> Dict[str, Any]:
        return self.store.copy()

    def keys(self) -> List[str]:
        return list(self.store.keys())

    # Atomic operations
    def atomic_update(self, key: str, check_value: Any, new_value: Any) -> bool:
        current = self.store.get(key)
        if current == check_value:
            self.store[key] = new_value
            self.versions[key] = self.versions.get(key, 0) + 1
            logger.info(f"[{self.node_id}] CAS {key}: {check_value} -> {new_value}")
            for cb in self.write_callbacks:
                cb({"op": "atomic_update", "key": key, "success": True})
            return True
        logger.warning(f"[{self.node_id}] CAS failed {key}: expected {check_value} got {current}")
        return False

    def batch_put(self, updates: Dict[str, Any]) -> bool:
        try:
            for k, v in updates.items():
                self.store[k] = v
                self.versions[k] = self.versions.get(k, 0) + 1
            logger.info(f"[{self.node_id}] BATCH PUT {len(updates)} keys")
            for cb in self.write_callbacks:
                cb({"op": "batch_put", "count": len(updates)})
            return True
        except Exception as e:  # pragma: no cover
            logger.error(f"Batch put error: {e}")
            return False

    # Snapshots
    def create_snapshot(self, term: int, index: int) -> KVSnapshot:
        snap = KVSnapshot(term=term, index=index, data=self.store.copy())
        self.snapshots.append(snap)
        logger.info(f"[{self.node_id}] Snapshot term={term} index={index}")
        return snap

    def restore_snapshot(self, snapshot: KVSnapshot) -> bool:
        try:
            self.store = snapshot.data.copy()
            self.last_applied = snapshot.index
            logger.info(f"[{self.node_id}] Restored snapshot term={snapshot.term} index={snapshot.index}")
            return True
        except Exception as e:  # pragma: no cover
            logger.error(f"Restore error: {e}")
            return False

    def get_latest_snapshot(self) -> Optional[KVSnapshot]:
        return self.snapshots[-1] if self.snapshots else None

    # Metrics
    def get_stats(self) -> Dict[str, Any]:
        return {
            "node_id": self.node_id,
            "keys": len(self.store),
            "snapshots": len(self.snapshots),
            "last_applied": self.last_applied,
            "versions": dict(sorted(self.versions.items())),
        }

    def size_bytes(self) -> int:
        return len(json.dumps(self.store).encode("utf-8"))

    # Callbacks
    def register_write_callback(self, cb: Callable[[Dict[str, Any]], None]):
        self.write_callbacks.append(cb)

    def register_read_callback(self, cb: Callable[[Dict[str, Any]], None]):
        self.read_callbacks.append(cb)

    def clear(self):
        self.store.clear()
        self.versions.clear()
        logger.info(f"[{self.node_id}] Cleared store")

# ---------------------------------------------------------------------------
# Replicated facade (to be integrated with Raft cluster)
# ---------------------------------------------------------------------------
class ReplicatedKVStore:
    def __init__(self, node_id: str, raft_node: Optional[Any] = None):
        self.node_id = node_id
        self.local_store = DistributedKVStore(node_id)
        self.raft_node: Optional[Any] = raft_node  # consensus backend (RaftNode)
        self.remote_stores: Dict[str, DistributedKVStore] = {}

    def attach_peer_store(self, peer_id: str, store: DistributedKVStore):
        self.remote_stores[peer_id] = store

    def put(self, key: str, value: Any) -> bool:
        if self.raft_node and getattr(self.raft_node, "state", None) and self.raft_node.state.value == "leader":
            command: Dict[str, Any] = {"op": "put", "key": key, "value": value}
            return bool(self.raft_node.append_entry(command))
        logger.warning(f"[{self.node_id}] Reject put: not leader")
        return False

    def get(self, key: str) -> Optional[Any]:
        return self.local_store.get(key)

    def replicate_to_follower(self, peer_id: str):
        if peer_id in self.remote_stores:
            remote = self.remote_stores[peer_id]
            for k, v in self.local_store.get_all().items():
                remote.put(k, v)

