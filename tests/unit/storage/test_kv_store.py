"""
Unit tests for distributed KVStore
"""

import pytest

from src.storage.kv_store import KVStore


def test_kv_put_get():
    kv = KVStore()
    kv.put("foo", 123)
    assert kv.get("foo") == 123


def test_kv_delete():
    kv = KVStore()
    kv.put("bar", "baz")
    kv.delete("bar")
    assert kv.get("bar") is None
