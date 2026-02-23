import pytest

from src.api.maas.constants import PQC_DEFAULT_PROFILE, get_pqc_profile
from src.api.maas.mesh_instance import MeshInstance
import src.api.maas.registry as registry


@pytest.fixture(autouse=True)
def _reset_registry_state():
    registry._mesh_registry.clear()
    registry._pending_nodes.clear()
    registry._node_telemetry.clear()
    registry._mesh_policies.clear()
    registry._mesh_audit_log.clear()
    registry._mesh_mapek_events.clear()
    registry._revoked_nodes.clear()
    registry._mesh_reissue_tokens.clear()
    yield
    registry._mesh_registry.clear()
    registry._pending_nodes.clear()
    registry._node_telemetry.clear()
    registry._mesh_policies.clear()
    registry._mesh_audit_log.clear()
    registry._mesh_mapek_events.clear()
    registry._revoked_nodes.clear()
    registry._mesh_reissue_tokens.clear()


def test_get_pqc_profile_known_and_unknown_device_class():
    known = get_pqc_profile("sensor")
    unknown = get_pqc_profile("unknown-device")

    assert known["kem"] == "ML-KEM-512"
    assert known["security_level"] == 1
    assert unknown == PQC_DEFAULT_PROFILE


def test_registry_register_find_and_unregister_mesh():
    mesh = MeshInstance(
        mesh_id="mesh-1",
        name="Test Mesh",
        owner_id="owner-1",
        nodes=1,
    )
    mesh.add_node("node-1")

    registry.register_mesh(mesh)

    assert registry.get_mesh("mesh-1") is mesh
    assert registry.find_mesh_for_node("node-1") == "mesh-1"
    assert registry.unregister_mesh("mesh-1") is True
    assert registry.unregister_mesh("mesh-1") is False


def test_pending_nodes_and_telemetry_are_stored_and_isolated():
    mesh_id = "mesh-1"
    node_id = "node-1"

    registry.add_pending_node(mesh_id, node_id, {"region": "eu-central"})
    pending = registry.get_pending_nodes(mesh_id)
    assert pending[node_id]["region"] == "eu-central"
    removed = registry.remove_pending_node(mesh_id, node_id)
    assert removed == {"region": "eu-central"}

    registry.update_node_telemetry(node_id, {"latency_ms": 11.2})
    assert registry.get_node_telemetry(node_id) == {"latency_ms": 11.2}


@pytest.mark.asyncio
async def test_audit_log_sync_and_async_append_entries():
    registry.audit_sync("mesh-1", "admin", "mesh.created", "created")
    await registry.record_audit_log("mesh-1", "system", "node.approved", "node-1")

    events = registry.get_audit_log("mesh-1")
    assert len(events) == 2
    assert events[0]["event"] == "mesh.created"
    assert events[1]["event"] == "node.approved"


def test_mapek_buffer_trims_to_limit(monkeypatch):
    monkeypatch.setattr(registry, "_MAPEK_EVENT_BUFFER_SIZE", 3)

    for i in range(5):
        registry.add_mapek_event("mesh-1", {"idx": i})

    events = registry.get_mapek_events("mesh-1")
    assert len(events) == 3
    assert [event["idx"] for event in events] == [2, 3, 4]


def test_revocation_and_reissue_token_flows():
    registry.revoke_node("mesh-1", "node-1", {"reason": "compromised"})
    assert registry.is_node_revoked("mesh-1", "node-1") is True
    assert registry.get_revoked_node("mesh-1", "node-1") == {"reason": "compromised"}
    assert registry.unrevoke_node("mesh-1", "node-1") == {"reason": "compromised"}
    assert registry.is_node_revoked("mesh-1", "node-1") is False

    registry.add_reissue_token("mesh-1", "token-1", {"node_id": "node-1", "used": False})
    assert registry.get_reissue_token("mesh-1", "token-1") == {
        "node_id": "node-1",
        "used": False,
    }
