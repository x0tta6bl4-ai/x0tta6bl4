"""
Unit tests for CRDT GCounter
"""
import pytest
from src.data_sync.crdt import GCounter

def test_gcounter_increment():
    c = GCounter()
    c.increment("n1")
    assert c.value() == 1
    c.increment("n1", 2)
    assert c.value() == 3

def test_gcounter_merge():
    c1 = GCounter()
    c2 = GCounter()
    c1.increment("n1", 2)
    c2.increment("n1", 1)
    c2.increment("n2", 5)
    c1.merge(c2)
    assert c1.value() == 7
