import json

import pytest

from src.mesh.recovery_policy import RecoveryPolicyManager
from src.network.routing.topology import LinkQuality, TopologyManager
from src.services.node_manager_service import NodeManagerService, UserNode
from src.vision.topology_analyzer import MeshTopologyAnalyzer


def _status_text(status):
    return json.dumps(status, sort_keys=True, default=str)


def _assert_redacted(status, *raw_values):
    text = _status_text(status)
    for raw_value in raw_values:
        assert str(raw_value) not in text


def test_recovery_policy_thinking_status_redacts_incident_keys():
    now = 1000.0

    def clock():
        return now

    manager = RecoveryPolicyManager(cooldown_seconds=600, clock=clock)

    assert manager.check_policy("incident-secret-key").allowed is True
    manager.record_action("incident-secret-key")
    assert manager.check_policy("incident-secret-key").allowed is False

    status = manager.get_thinking_status()
    assert status["thinking"]["profile"]["role"] == "healing"
    _assert_redacted(status, "incident-secret-key")


def test_topology_manager_thinking_status_redacts_node_ids_and_links():
    manager = TopologyManager("local-secret-node")

    manager.add_node(
        "remote-secret-node",
        is_neighbor=True,
        hop_count=2,
        link_quality=LinkQuality(latency_ms=12, throughput_mbps=25, loss_rate=0.1),
    )
    manager.update_link_quality(
        "local-secret-node",
        "remote-secret-node",
        LinkQuality(latency_ms=40, throughput_mbps=10, loss_rate=0.2),
    )
    manager.get_topology_stats()
    manager.build_adjacency()

    status = manager.get_thinking_status()
    assert status["thinking"]["profile"]["role"] == "monitoring"
    _assert_redacted(status, "local-secret-node", "remote-secret-node")


class _FakeMeshConfig:
    port = 6200


class _FakeMeshNode:
    config = _FakeMeshConfig()

    def __init__(self):
        self.stopped = False

    async def stop(self):
        self.stopped = True

    def get_stats(self):
        return {
            "running": True,
            "routing": {"peers_count": 1, "routes_cached": 1},
        }

    def get_peers(self):
        return ["secret-peer-node"]

    def get_routes(self):
        return {"secret-route-destination": "secret-next-hop"}


@pytest.mark.asyncio
async def test_node_manager_service_thinking_status_redacts_runtime_identifiers():
    service = NodeManagerService(base_port=6200)
    user_id = 987654321
    mesh_node = _FakeMeshNode()
    service.user_nodes[user_id] = UserNode(
        user_id=user_id,
        node_id="secret-user-node",
        mesh_node=mesh_node,
    )
    service.connections["secret-connection-id"] = {
        "user_id": user_id,
        "target": "secret-target-node",
    }

    network_status = await service.get_network_status(user_id)
    assert network_status["success"] is True
    status = service.get_thinking_status()
    assert status["thinking"]["profile"]["role"] == "coordinator"
    _assert_redacted(
        status,
        user_id,
        "secret-user-node",
        "secret-peer-node",
        "secret-route-destination",
        "secret-next-hop",
        "secret-connection-id",
        "secret-target-node",
    )

    await service.close_connection(user_id, "secret-connection-id")
    status = service.get_thinking_status()
    _assert_redacted(status, user_id, "secret-connection-id")

    service.connections["secret-connection-id-2"] = {"user_id": user_id}
    await service.stop_node(user_id)
    status = service.get_thinking_status()
    _assert_redacted(status, user_id, "secret-user-node", "secret-connection-id-2")
    assert mesh_node.stopped is True


class _FakeVisionProcessor:
    async def process_image(self, image_data):
        assert image_data == b"vision-image-secret"
        return {
            "objects_detected": [{"id": "vision-secret-node"}],
            "links": [
                {
                    "source": "vision-secret-node",
                    "target": "vision-secret-peer",
                    "latency_ms": 5,
                }
            ],
            "findings": {"secret-finding-key": "secret finding value"},
            "proposed_plan": ["secret recommendation text"],
        }


@pytest.mark.asyncio
async def test_vision_topology_analyzer_thinking_status_redacts_image_and_findings():
    analyzer = MeshTopologyAnalyzer(vision_processor=_FakeVisionProcessor())

    result = await analyzer.analyze_bytes(b"vision-image-secret")

    assert result["status"] == "success"
    status = analyzer.get_thinking_status()
    assert status["thinking"]["profile"]["role"] == "monitoring"
    _assert_redacted(
        status,
        "vision-image-secret",
        "vision-secret-node",
        "vision-secret-peer",
        "secret-finding-key",
        "secret finding value",
        "secret recommendation text",
    )
