from dataclasses import dataclass, field
from typing import Dict

import pytest

from src.coordination.events import EventBus, EventType
from src.network.ebpf import mesh_integration as mesh_mod
from src.network.ebpf.mesh_integration import (
    EBPF_MESH_INTEGRATION_SERVICE_NAME,
    EBPFTopologyIntegrator,
)


def _events(bus):
    return bus.get_event_history(
        event_type=EventType.PIPELINE_STAGE_END,
        source_agent=EBPF_MESH_INTEGRATION_SERVICE_NAME,
        limit=80,
    )


def _stage_payload(bus, stage):
    for event in reversed(_events(bus)):
        if event.data["stage"] == stage:
            return event.data
    raise AssertionError(f"missing stage {stage}")


@dataclass
class _Node:
    ip_address: str
    hop_count: int = 1
    metrics: Dict[str, int] = field(default_factory=lambda: {"tq": 200})


class _Topology:
    def __init__(self, nodes):
        self._nodes = nodes

    def get_active_nodes(self):
        return list(self._nodes)


class _Loader:
    def __init__(self):
        self.routes = None
        self.cleaned = False

    def update_routes(self, routes):
        self.routes = dict(routes)
        return True

    def get_stats(self):
        return {"dropped_packets": 3, "forwarded_packets": 7}

    def cleanup(self):
        self.cleaned = True


class _Metrics:
    def __init__(self):
        self.values = {}

    def set_gauge(self, name, value):
        self.values[name] = value


def _integrator(tmp_path, *, interface="secret-if0", nodes=None):
    bus = EventBus(project_root=str(tmp_path))
    loader = _Loader()
    metrics = _Metrics()
    integrator = EBPFTopologyIntegrator(
        interface=interface,
        topology_manager=_Topology(nodes or []),
        event_bus=bus,
        loader=loader,
        metrics=metrics,
    )
    return integrator, bus, loader, metrics


def test_local_ip_probe_success_and_ifindex_redact_socket_selectors(
    monkeypatch,
    tmp_path,
):
    integrator, bus, _loader, _metrics = _integrator(tmp_path)

    class _Sock:
        def connect(self, target):
            self.target = target

        def getsockname(self):
            return ("10.23.45.67", 5555)

        def close(self):
            return None

    monkeypatch.setattr(mesh_mod.socket, "socket", lambda *args, **kwargs: _Sock())
    monkeypatch.setattr(mesh_mod.socket, "if_nametoindex", lambda _interface: 42)

    assert integrator._get_local_ip() == "10.23.45.67"
    assert integrator._get_ifindex("secret-if0") == 42

    local_payload = _stage_payload(bus, "ebpf_mesh_local_ip_probe_completed")
    ifindex_payload = _stage_payload(bus, "ebpf_mesh_ifindex_lookup_completed")

    assert local_payload["parsed_summary"]["fallback"] is False
    assert local_payload["local_ip_redacted"] is True
    assert local_payload["probe_target_redacted"] is True
    assert ifindex_payload["parsed_summary"]["ifindex"] == 42
    assert ifindex_payload["requested_interface_redacted"] is True
    payload_text = str(_events(bus))
    assert "10.23.45.67" not in payload_text
    assert "8.8.8.8" not in payload_text
    assert "secret-if0" not in payload_text


def test_local_ip_and_ifindex_fallback_publish_redacted_errors(monkeypatch, tmp_path):
    integrator, bus, _loader, _metrics = _integrator(tmp_path)

    monkeypatch.setattr(
        mesh_mod.socket,
        "socket",
        lambda *args, **kwargs: (_ for _ in ()).throw(
            RuntimeError("secret socket failure")
        ),
    )
    monkeypatch.setattr(
        mesh_mod.socket,
        "if_nametoindex",
        lambda _interface: (_ for _ in ()).throw(
            RuntimeError("secret ifindex failure")
        ),
    )

    assert integrator._get_local_ip() == "127.0.0.1"
    assert integrator._get_ifindex("secret-if0") == 1

    local_payload = _stage_payload(bus, "ebpf_mesh_local_ip_probe_fallback")
    ifindex_payload = _stage_payload(bus, "ebpf_mesh_ifindex_lookup_fallback")

    assert local_payload["status"] == "failure"
    assert local_payload["error"]["message_redacted"] is True
    assert ifindex_payload["parsed_summary"] == {"ifindex": 1, "fallback": True}
    payload_text = str(_events(bus))
    assert "secret socket failure" not in payload_text
    assert "secret ifindex failure" not in payload_text
    assert "secret-if0" not in payload_text


@pytest.mark.asyncio
async def test_route_sync_publishes_redacted_topology_and_loader_evidence(tmp_path):
    nodes = [
        _Node("10.0.0.1", hop_count=0),
        _Node("10.0.0.99", hop_count=2, metrics={"tq": 180}),
    ]
    integrator, bus, loader, _metrics = _integrator(tmp_path, nodes=nodes)
    integrator._get_local_ip = lambda: "10.0.0.1"
    integrator._get_ifindex = lambda _interface: 9

    await integrator._sync_routes()

    assert loader.routes == {str(int(mesh_mod.ipaddress.IPv4Address("10.0.0.99"))): "9"}
    topology_payload = _stage_payload(bus, "ebpf_mesh_topology_routes_collected")
    sync_payload = _stage_payload(bus, "ebpf_mesh_route_sync_completed")

    assert topology_payload["parsed_summary"]["nodes_total"] == 2
    assert topology_payload["parsed_summary"]["routes_total"] == 1
    assert sync_payload["parsed_summary"]["ebpf_routes_total"] == 1
    assert sync_payload["parsed_summary"]["added_count"] == 1
    assert sync_payload["route_selectors_redacted"] is True
    payload_text = str(_events(bus))
    assert "10.0.0.99" not in payload_text
    assert "10.0.0.1" not in payload_text
    assert "secret-if0" not in payload_text


@pytest.mark.asyncio
async def test_collect_metrics_and_shutdown_publish_redacted_evidence(tmp_path):
    node = _Node("10.0.0.50", metrics={"tq": 150})
    integrator, bus, loader, metrics = _integrator(tmp_path, nodes=[node])
    integrator.last_routes = {
        node.ip_address: mesh_mod.MeshRoute(
            dest_ip=node.ip_address,
            next_hop_ip=node.ip_address,
            next_hop_ifindex=3,
            tq_score=150,
            hop_count=1,
        )
    }

    await integrator._collect_metrics()
    await integrator.shutdown()

    metrics_payload = _stage_payload(bus, "ebpf_mesh_metrics_collected")
    shutdown_payload = _stage_payload(bus, "ebpf_mesh_shutdown_completed")

    assert metrics.values["mesh_packet_drops_total"] == 3
    assert metrics.values["mesh_packets_forwarded_total"] == 7
    assert metrics.values["mesh_average_tq_score"] == 150
    assert metrics_payload["parsed_summary"]["dropped_packets"] == 3
    assert metrics_payload["parsed_summary"]["forwarded_packets"] == 7
    assert shutdown_payload["parsed_summary"]["cleanup"] is True
    assert loader.cleaned is True
    assert "secret-if0" not in str(_events(bus))
