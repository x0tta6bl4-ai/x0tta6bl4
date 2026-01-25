import pytest
from src.storage.distributed_kvstore import DistributedKVStore, ReplicatedKVStore


def test_kv_put_get():
    store = DistributedKVStore("n1")
    store.put("k1", "v1")
    assert store.get("k1") == "v1"


def test_kv_update_delete():
    store = DistributedKVStore("n1")
    store.put("k1", "v1")
    store.update("k1", "v2")
    assert store.get("k1") == "v2"
    store.delete("k1")
    assert store.get("k1") is None


def test_atomic_update():
    store = DistributedKVStore("n1")
    store.put("flag", "old")
    ok = store.atomic_update("flag", "old", "new")
    assert ok is True
    assert store.get("flag") == "new"


def test_batch_put_and_snapshot():
    store = DistributedKVStore("n1")
    data = {"a": 1, "b": 2}
    assert store.batch_put(data)
    snap = store.create_snapshot(term=1, index=5)
    assert snap.data["a"] == 1
    restored = DistributedKVStore("n2")
    assert restored.restore_snapshot(snap)
    assert restored.get("b") == 2


def test_stats_and_size():
    store = DistributedKVStore("n1")
    store.put("a", "x")
    stats = store.get_stats()
    assert stats["keys"] == 1
    assert store.size_bytes() > 0


def test_replicated_put_not_leader():
    replicated = ReplicatedKVStore("n1", raft_node=None)
    ok = replicated.put("k", "v")
    assert ok is False
