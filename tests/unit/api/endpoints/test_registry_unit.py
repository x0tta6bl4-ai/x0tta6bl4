"""Unit tests for src/api/maas/registry.py."""

import asyncio
from types import SimpleNamespace
from unittest.mock import patch

import pytest

import src.api.maas.registry as reg


# ---------------------------------------------------------------------------
# Fixture: изолированное состояние реестра для каждого теста
# ---------------------------------------------------------------------------


@pytest.fixture(autouse=True)
def _clean_registry():
    """Очищает глобальные словари реестра до и после каждого теста."""
    stores = [
        "_mesh_registry",
        "_pending_nodes",
        "_node_telemetry",
        "_mesh_policies",
        "_mesh_audit_log",
        "_mesh_mapek_events",
        "_revoked_nodes",
        "_mesh_reissue_tokens",
    ]
    for s in stores:
        getattr(reg, s).clear()
    yield
    for s in stores:
        getattr(reg, s).clear()


def _make_instance(mesh_id="mesh-1", owner_id="owner-1", nodes=2):
    """Создаёт минимальный MeshInstance-подобный объект."""
    inst = SimpleNamespace(
        mesh_id=mesh_id,
        owner_id=owner_id,
        node_instances={},
        plan="pro",
        region="us-east-1",
    )
    return inst


# ---------------------------------------------------------------------------
# Mesh registry
# ---------------------------------------------------------------------------


def test_register_and_get_mesh():
    inst = _make_instance()
    reg.register_mesh(inst)
    assert reg.get_mesh("mesh-1") is inst


def test_get_mesh_missing_returns_none():
    assert reg.get_mesh("nonexistent") is None


def test_get_all_meshes_returns_copy():
    inst = _make_instance()
    reg.register_mesh(inst)
    all_m = reg.get_all_meshes()
    assert "mesh-1" in all_m
    # Модификация копии не влияет на реестр
    all_m.pop("mesh-1")
    assert reg.get_mesh("mesh-1") is inst


def test_unregister_mesh_returns_true_when_found():
    reg.register_mesh(_make_instance())
    assert reg.unregister_mesh("mesh-1") is True
    assert reg.get_mesh("mesh-1") is None


def test_unregister_mesh_returns_false_when_not_found():
    assert reg.unregister_mesh("ghost") is False


def test_register_multiple_meshes():
    for i in range(3):
        reg.register_mesh(_make_instance(mesh_id=f"mesh-{i}"))
    assert len(reg.get_all_meshes()) == 3


# ---------------------------------------------------------------------------
# Pending nodes
# ---------------------------------------------------------------------------


def test_add_and_get_pending_node():
    reg.add_pending_node("mesh-1", "node-7", {"ip": "10.0.0.7"})
    pending = reg.get_pending_nodes("mesh-1")
    assert "node-7" in pending
    assert pending["node-7"]["ip"] == "10.0.0.7"


def test_get_pending_nodes_empty_for_unknown_mesh():
    assert reg.get_pending_nodes("unknown") == {}


def test_get_pending_nodes_returns_copy():
    reg.add_pending_node("mesh-1", "n1", {"x": 1})
    copy = reg.get_pending_nodes("mesh-1")
    copy.pop("n1")
    assert "n1" in reg.get_pending_nodes("mesh-1")


def test_remove_pending_node_returns_data():
    reg.add_pending_node("mesh-1", "n1", {"val": 42})
    removed = reg.remove_pending_node("mesh-1", "n1")
    assert removed == {"val": 42}
    assert "n1" not in reg.get_pending_nodes("mesh-1")


def test_remove_pending_node_missing_returns_none():
    assert reg.remove_pending_node("mesh-1", "ghost") is None


# ---------------------------------------------------------------------------
# Telemetry
# ---------------------------------------------------------------------------


def test_update_and_get_node_telemetry():
    reg.update_node_telemetry("node-1", {"cpu": 55.0, "mem": 44.0})
    t = reg.get_node_telemetry("node-1")
    assert t["cpu"] == 55.0


def test_get_node_telemetry_missing_returns_none():
    assert reg.get_node_telemetry("ghost") is None


def test_update_telemetry_overwrites():
    reg.update_node_telemetry("node-1", {"cpu": 10.0})
    reg.update_node_telemetry("node-1", {"cpu": 99.0})
    assert reg.get_node_telemetry("node-1")["cpu"] == 99.0


# ---------------------------------------------------------------------------
# ACL Policies
# ---------------------------------------------------------------------------


def test_add_and_get_mesh_policies():
    reg.add_mesh_policy("mesh-1", {"effect": "allow", "principal": "user-1"})
    policies = reg.get_mesh_policies("mesh-1")
    assert len(policies) == 1
    assert policies[0]["principal"] == "user-1"


def test_get_mesh_policies_empty_for_unknown():
    assert reg.get_mesh_policies("missing") == []


def test_get_mesh_policies_returns_copy():
    reg.add_mesh_policy("mesh-1", {"p": 1})
    copy = reg.get_mesh_policies("mesh-1")
    copy.clear()
    assert len(reg.get_mesh_policies("mesh-1")) == 1


# ---------------------------------------------------------------------------
# Audit log
# ---------------------------------------------------------------------------


def test_audit_sync_appends_entry():
    reg.audit_sync("mesh-1", "admin", "CREATE_MESH", "Mesh created")
    log = reg.get_audit_log("mesh-1")
    assert len(log) == 1
    entry = log[0]
    assert entry["actor"] == "admin"
    assert entry["event"] == "CREATE_MESH"
    assert entry["details"] == "Mesh created"
    assert "timestamp" in entry


def test_audit_sync_multiple_entries_ordered():
    for i in range(3):
        reg.audit_sync("mesh-1", "actor", f"EVENT_{i}", "")
    log = reg.get_audit_log("mesh-1")
    assert len(log) == 3
    events = [e["event"] for e in log]
    assert events == ["EVENT_0", "EVENT_1", "EVENT_2"]


def test_audit_sync_separate_mesh_logs():
    reg.audit_sync("mesh-1", "a", "EV1", "")
    reg.audit_sync("mesh-2", "b", "EV2", "")
    assert len(reg.get_audit_log("mesh-1")) == 1
    assert len(reg.get_audit_log("mesh-2")) == 1


def test_get_audit_log_empty_for_unknown():
    assert reg.get_audit_log("unknown") == []


@pytest.mark.asyncio
async def test_record_audit_log_async():
    await reg.record_audit_log("mesh-1", "system", "BOOT", "started")
    log = reg.get_audit_log("mesh-1")
    assert len(log) == 1
    assert log[0]["event"] == "BOOT"


# ---------------------------------------------------------------------------
# MAPE-K events
# ---------------------------------------------------------------------------


def test_add_and_get_mapek_events():
    reg.add_mapek_event("mesh-1", {"type": "analyze", "score": 0.9})
    events = reg.get_mapek_events("mesh-1")
    assert len(events) == 1
    assert events[0]["type"] == "analyze"


def test_mapek_event_buffer_trimmed_at_1000():
    for i in range(1010):
        reg.add_mapek_event("mesh-1", {"i": i})
    events = reg.get_mapek_events("mesh-1")
    assert len(events) == 1000
    # Старые события вытеснены — первое из буфера соответствует i=10
    assert events[0]["i"] == 10


def test_get_mapek_events_empty_for_unknown():
    assert reg.get_mapek_events("unknown") == []


# ---------------------------------------------------------------------------
# Node revocation
# ---------------------------------------------------------------------------


def test_revoke_and_is_node_revoked():
    reg.revoke_node("mesh-1", "node-7", {"reason": "compromised"})
    assert reg.is_node_revoked("mesh-1", "node-7") is True


def test_is_node_revoked_false_for_clean_node():
    assert reg.is_node_revoked("mesh-1", "clean-node") is False


def test_get_revoked_node_returns_metadata():
    meta = {"reason": "test", "by": "admin"}
    reg.revoke_node("mesh-1", "node-bad", meta)
    assert reg.get_revoked_node("mesh-1", "node-bad") == meta


def test_get_revoked_node_missing_returns_none():
    assert reg.get_revoked_node("mesh-1", "ghost") is None


def test_unrevoke_node_removes_revocation():
    reg.revoke_node("mesh-1", "n1", {"r": "x"})
    returned = reg.unrevoke_node("mesh-1", "n1")
    assert returned == {"r": "x"}
    assert reg.is_node_revoked("mesh-1", "n1") is False


def test_unrevoke_node_missing_returns_none():
    assert reg.unrevoke_node("mesh-1", "ghost") is None


# ---------------------------------------------------------------------------
# Reissue tokens
# ---------------------------------------------------------------------------


def test_add_and_get_reissue_token():
    reg.add_reissue_token("mesh-1", "tok-abc", {"node_id": "n1", "used": False})
    data = reg.get_reissue_token("mesh-1", "tok-abc")
    assert data["node_id"] == "n1"
    assert data["used"] is False


def test_get_reissue_token_missing_returns_none():
    assert reg.get_reissue_token("mesh-1", "nonexistent") is None


def test_multiple_tokens_per_mesh():
    reg.add_reissue_token("mesh-1", "t1", {"node_id": "n1"})
    reg.add_reissue_token("mesh-1", "t2", {"node_id": "n2"})
    assert reg.get_reissue_token("mesh-1", "t1")["node_id"] == "n1"
    assert reg.get_reissue_token("mesh-1", "t2")["node_id"] == "n2"


# ---------------------------------------------------------------------------
# find_mesh_for_node
# ---------------------------------------------------------------------------


def test_find_mesh_for_node_found():
    inst = _make_instance("mesh-42")
    inst.node_instances["node-X"] = {"ip": "10.0.0.1"}
    reg.register_mesh(inst)
    assert reg.find_mesh_for_node("node-X") == "mesh-42"


def test_find_mesh_for_node_not_found():
    inst = _make_instance("mesh-99")
    inst.node_instances["node-A"] = {}
    reg.register_mesh(inst)
    assert reg.find_mesh_for_node("node-Z") is None


def test_find_mesh_for_node_empty_registry():
    assert reg.find_mesh_for_node("any") is None
