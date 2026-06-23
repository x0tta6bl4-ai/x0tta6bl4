"""Unit tests for Yggdrasil route optimizer recommendation evidence shape."""

from datetime import datetime, timedelta

from src.coordination.events import EventBus, EventType
from src.mesh.yggdrasil_optimizer import (
    OptimizationConfig,
    RouteMetrics,
    YggdrasilOptimizer,
)


def test_refresh_recommendation_includes_peer_uri_when_next_hop_is_uri():
    optimizer = YggdrasilOptimizer(
        OptimizationConfig(min_samples=1, route_timeout_seconds=1)
    )
    route = RouteMetrics(
        route_id="direct-tcp://10.0.0.1:9000",
        destination="tcp://10.0.0.1:9000",
        next_hop="tcp://10.0.0.1:9000",
        latency_ms=50.0,
        packet_loss=0.0,
        last_updated=datetime.utcnow() - timedelta(seconds=10),
    )
    optimizer.register_route(route)

    result = optimizer.optimize_routes()
    refresh = [
        item for item in result["recommendations"] if item["action"] == "refresh"
    ][0]

    assert refresh["peer_uri"] == "tcp://10.0.0.1:9000"
    assert refresh["route_id"] == "direct-tcp://10.0.0.1:9000"


def test_recommendation_omits_peer_uri_for_non_uri_next_hop():
    optimizer = YggdrasilOptimizer(
        OptimizationConfig(min_samples=1, route_timeout_seconds=1)
    )
    route = RouteMetrics(
        route_id="direct-node-1",
        destination="node-1",
        next_hop="node-1",
        latency_ms=250.0,
        packet_loss=12.0,
        last_updated=datetime.utcnow() - timedelta(seconds=10),
    )
    optimizer.register_route(route)

    result = optimizer.optimize_routes()

    assert result["recommendations"]
    assert all("peer_uri" not in item for item in result["recommendations"])


def test_optimize_routes_publishes_redacted_optimizer_evidence(tmp_path):
    bus = EventBus(project_root=str(tmp_path))
    optimizer = YggdrasilOptimizer(
        OptimizationConfig(min_samples=1, route_timeout_seconds=1)
    )
    route = RouteMetrics(
        route_id="direct-tcp://10.0.0.1:9000",
        destination="tcp://10.0.0.1:9000",
        next_hop="tcp://10.0.0.1:9000",
        latency_ms=250.0,
        packet_loss=12.0,
        last_updated=datetime.utcnow() - timedelta(seconds=10),
    )
    optimizer.register_route(route)

    result = optimizer.optimize_routes(
        event_bus=bus,
        event_project_root=str(tmp_path),
        include_evidence=True,
    )
    events = bus.get_event_history(
        EventType.PIPELINE_STAGE_END,
        source_agent="mesh-yggdrasil-optimizer",
        limit=10,
    )

    assert events
    assert result["evidence"]["source_agents"] == ["mesh-yggdrasil-optimizer"]
    assert result["evidence"]["events_total"] == 1
    assert result["evidence"]["event_ids"] == [events[-1].event_id]

    data = events[-1].data
    event_text = str(data)
    assert data["operation"] == "optimize_routes"
    assert data["resource"] == "mesh:yggdrasil_optimizer:optimize_routes"
    assert data["service_name"] == "mesh-yggdrasil-optimizer"
    assert data["layer"] == "mesh_yggdrasil_optimizer_observed_state"
    assert data["observed_state"] is True
    assert data["control_action"] is False
    assert data["recommendations"]["action_counts"] == {
        "investigate": 1,
        "refresh": 1,
    }
    assert data["recommendations"]["route_id_hashes_total"] == 2
    assert data["recommendations"]["peer_uri_hashes_total"] == 2
    assert data["recommendations"]["values_redacted"] is True
    assert "10.0.0.1" not in event_text
    assert "tcp://10.0.0.1:9000" not in event_text
