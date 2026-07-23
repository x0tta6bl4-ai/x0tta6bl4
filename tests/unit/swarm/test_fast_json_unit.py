"""
Unit test for fast_json adapter module.
"""
from __future__ import annotations

from src.swarm.fast_json import HAS_ORJSON, dumps, loads


def test_fast_json_dumps_and_loads():
    payload = {"node_id": "node-1", "value": 42, "status": "active"}
    serialized = dumps(payload)
    assert isinstance(serialized, str)
    deserialized = loads(serialized)
    assert deserialized == payload


def test_fast_json_has_orjson_flag():
    assert isinstance(HAS_ORJSON, bool)
