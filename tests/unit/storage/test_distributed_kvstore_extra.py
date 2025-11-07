from src.storage.distributed_kvstore import DistributedKVStore, KVSnapshot


def test_snapshot_restore_and_clear():
    store = DistributedKVStore('node1')
    store.put('a', 1)
    store.put('b', 2)
    snap = store.create_snapshot(term=1, index=5)
    assert snap.data == {'a':1,'b':2}
    store.put('a', 99)
    assert store.get('a') == 99
    store.restore_snapshot(snap)
    assert store.get('a') == 1
    stats = store.get_stats()
    assert stats['keys'] == 2
    size = store.size_bytes()
    assert size > 0
    store.clear()
    assert store.get('a') is None
    assert store.get_stats()['keys'] == 0


def test_atomic_update_and_versions():
    store = DistributedKVStore('node2')
    store.put('x', 10)
    ok = store.atomic_update('x', 10, 11)
    assert ok is True
    fail = store.atomic_update('x', 10, 12)
    assert fail is False
    snap2 = store.create_snapshot(term=2, index=7)
    assert isinstance(snap2, KVSnapshot)
