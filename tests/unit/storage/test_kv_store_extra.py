from src.storage.kv_store import KVStore


def test_kv_store_basic_cycle():
    s = KVStore()
    s.put("a", 1)
    assert s.get("a") == 1
    s.put("a", 2)
    assert s.get("a") == 2
    s.delete("a")
    assert s.get("a") is None
