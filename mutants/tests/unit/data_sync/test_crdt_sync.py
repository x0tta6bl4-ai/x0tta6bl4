import pytest
from src.data_sync.crdt_sync import LWWRegister, Counter, ORSet, CRDTSync


def test_lww_register_basic():
    reg = LWWRegister()
    reg.set("v1", "n1")
    assert reg.value() == "v1"
    reg.set("v2", "n2")
    assert reg.value() == "v2"


def test_lww_merge():
    a = LWWRegister(value_data="a", node_id="n1")
    b = LWWRegister(value_data="b", node_id="n2")
    # force timestamp ordering
    b.timestamp = a.timestamp.replace(microsecond=a.timestamp.microsecond + 10)
    a.merge(b)
    assert a.value() == "b"


def test_counter_increment_merge():
    c1 = Counter()
    c1.increment("n1", 5)
    c2 = Counter()
    c2.increment("n2", 7)
    c1.merge(c2)
    assert c1.value() == 12


def test_orset_add_remove():
    s = ORSet()
    s.add("apple", "tag1")
    s.add("banana", "tag2")
    assert "apple" in s.value()
    s.remove("apple")
    assert "apple" not in s.value()


def test_orset_merge():
    s1 = ORSet()
    s2 = ORSet()
    s1.add("x", "t1")
    s2.add("x", "t2")
    s1.merge(s2)
    assert "x" in s1.value()


def test_crdt_sync_register_and_broadcast():
    sync = CRDTSync("n1")
    counter = Counter()
    sync.register_crdt("counter", counter)
    counter.increment("n1", 3)
    state = sync.get_crdt_state()
    assert state["counter"] == 3
