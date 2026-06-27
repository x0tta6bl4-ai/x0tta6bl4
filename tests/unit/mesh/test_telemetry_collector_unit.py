"""Unit tests for MeshTelemetryCollector (telemetry_collector.py)."""
import pytest
import asyncio
from unittest.mock import MagicMock, patch

from src.coordination.events import EventBus, EventType
from src.network.yggdrasil_client import YGGDRASIL_OBSERVED_STATE_CLAIM_BOUNDARY


class _AdminMetricProvider:
    def __init__(self, bus):
        self.bus = bus

    async def get_peers(self):
        self.bus.publish(
            EventType.PIPELINE_STAGE_END,
            "real-network-adapter",
            {
                "operation": "yggdrasil_admin_request",
                "observed_state": True,
                "peer": "10.0.0.1",
            },
        )
        return [
            {
                "address": "10.0.0.1",
                "estimated_metrics": {
                    "latency_ms": 24.0,
                    "bandwidth_mbps": 8.5,
                    "sources": {
                        "latency_ms": {
                            "source": "admin_estimate",
                            "field": "coords",
                        },
                        "bandwidth_mbps": {
                            "source": "admin_estimate",
                            "field": "bytes_sent+bytes_recvd/uptime",
                        },
                    },
                },
            }
        ]


class _DataplaneProbeProvider:
    def __init__(self, bus):
        self.bus = bus
        self.targets = []

    async def probe_peer(self, target):
        self.targets.append(target)
        event = self.bus.publish(
            EventType.PIPELINE_STAGE_END,
            "real-network-adapter",
            {
                "operation": "dataplane_ping_probe",
                "observed_state": True,
                "target": target,
            },
        )
        return {
            "status": "ok",
            "latency_ms": 12.5,
            "packet_loss_percent": 2.5,
            "jitter_ms": 1.5,
            "sources": {
                "latency_ms": {
                    "source": "dataplane_probe",
                    "field": "ping_avg_rtt_ms",
                },
                "packet_loss_percent": {
                    "source": "dataplane_probe",
                    "field": "ping_packet_loss_percent",
                },
                "jitter_ms": {
                    "source": "dataplane_probe",
                    "field": "ping_mdev_ms",
                },
            },
            "evidence": {
                "source_agents": ["real-network-adapter"],
                "event_ids": [event.event_id],
                "events_total": 1,
                "redacted": True,
            },
            "redacted": True,
        }


@pytest.fixture(autouse=True)
def mock_deps():
    with patch("src.mesh.telemetry_collector.get_optimizer") as mock_opt, \
         patch("src.mesh.telemetry_collector.get_yggdrasil_peers") as mock_peers, \
         patch("src.mesh.telemetry_collector.get_yggdrasil_status") as mock_status:
        mock_opt.return_value = MagicMock(_routes={})
        mock_peers.return_value = {"status": "ok", "peers": []}
        mock_status.return_value = {}
        yield mock_opt, mock_peers, mock_status


class TestMeshTelemetryCollectorInit:
    def test_default_interval(self, mock_deps):
        from src.mesh.telemetry_collector import MeshTelemetryCollector
        c = MeshTelemetryCollector()
        assert c.interval == 15

    def test_custom_interval(self, mock_deps):
        from src.mesh.telemetry_collector import MeshTelemetryCollector
        c = MeshTelemetryCollector(interval_seconds=30)
        assert c.interval == 30

    def test_not_running_on_init(self, mock_deps):
        from src.mesh.telemetry_collector import MeshTelemetryCollector
        c = MeshTelemetryCollector()
        assert c._running is False

    def test_stop_sets_running_false(self, mock_deps):
        from src.mesh.telemetry_collector import MeshTelemetryCollector
        c = MeshTelemetryCollector()
        c._running = True
        c.stop()
        assert c._running is False


class TestCollectOnce:
    def test_skips_when_peers_status_not_ok(self, mock_deps):
        mock_opt, mock_peers, _ = mock_deps
        mock_peers.return_value = {"status": "error"}
        optimizer = mock_opt.return_value

        from src.mesh.telemetry_collector import MeshTelemetryCollector
        c = MeshTelemetryCollector()

        asyncio.run(c._collect_once())
        optimizer.update_route_metrics.assert_not_called()

    def test_updates_route_for_each_peer(self, mock_deps):
        mock_opt, mock_peers, _ = mock_deps
        mock_peers.return_value = {
            "status": "ok",
            "peers": [
                {"remote": "tls://10.0.0.1:9000"},
                {"remote": "tls://10.0.0.2:9000"},
            ],
        }
        optimizer = mock_opt.return_value
        optimizer._routes = {}
        optimizer.optimize_routes.return_value = {"recommendations": []}

        from src.mesh.telemetry_collector import MeshTelemetryCollector
        c = MeshTelemetryCollector()

        asyncio.run(c._collect_once())
        assert optimizer.update_route_metrics.call_count == 2

    def test_registers_new_routes(self, mock_deps):
        mock_opt, mock_peers, _ = mock_deps
        mock_peers.return_value = {
            "status": "ok",
            "peers": [{"remote": "tls://10.0.0.1:9000"}],
        }
        optimizer = mock_opt.return_value
        optimizer._routes = {}  # Empty — route is new
        optimizer.optimize_routes.return_value = {"recommendations": []}

        from src.mesh.telemetry_collector import MeshTelemetryCollector
        c = MeshTelemetryCollector()

        asyncio.run(c._collect_once())
        optimizer.register_route.assert_called_once()

    def test_skips_peers_without_remote(self, mock_deps):
        mock_opt, mock_peers, _ = mock_deps
        mock_peers.return_value = {
            "status": "ok",
            "peers": [{"remote": None}, {"remote": ""}],
        }
        optimizer = mock_opt.return_value
        optimizer.optimize_routes.return_value = {"recommendations": []}

        from src.mesh.telemetry_collector import MeshTelemetryCollector
        c = MeshTelemetryCollector()

        asyncio.run(c._collect_once())
        optimizer.update_route_metrics.assert_not_called()

    def test_existing_route_not_re_registered(self, mock_deps):
        mock_opt, mock_peers, _ = mock_deps
        mock_peers.return_value = {
            "status": "ok",
            "peers": [{"remote": "tls://10.0.0.1:9000"}],
        }
        optimizer = mock_opt.return_value
        optimizer._routes = {"direct-tls://10.0.0.1:9000": MagicMock()}
        optimizer.optimize_routes.return_value = {"recommendations": []}

        from src.mesh.telemetry_collector import MeshTelemetryCollector
        c = MeshTelemetryCollector()

        asyncio.run(c._collect_once())
        optimizer.register_route.assert_not_called()

    def test_publishes_redacted_observed_state_with_yggdrasil_evidence(
        self,
        mock_deps,
        tmp_path,
    ):
        mock_opt, mock_peers, _ = mock_deps
        bus = EventBus(project_root=str(tmp_path))
        optimizer = mock_opt.return_value
        optimizer._routes = {}
        optimizer.update_route_metrics.return_value = None
        optimizer.optimize_routes.return_value = {
            "recommendations": [
                {
                    "action": "refresh",
                    "route_id": "direct-tls://10.0.0.1:9000",
                }
            ]
        }

        def fake_get_yggdrasil_peers(**kwargs):
            event = kwargs["event_bus"].publish(
                EventType.PIPELINE_STAGE_END,
                "yggdrasil-client",
                {
                    "operation": "get_peers",
                    "observed_state": True,
                    "remote": "tls://10.0.0.1:9000",
                    "claim_gate": {
                        "schema": (
                            "x0tta6bl4.yggdrasil_observed_state.claim_gate.v1"
                        ),
                        "decision": "LOCAL_YGGDRASIL_OBSERVED_STATE_ONLY",
                        "local_observed_state_claim_allowed": True,
                        "real_yggdrasil_daemon_observed": True,
                        "remote_peer_authenticity_claim_allowed": False,
                        "live_packet_reachability_claim_allowed": False,
                        "customer_traffic_claim_allowed": False,
                        "production_readiness_claim_allowed": False,
                        "blockers": [],
                        "claim_boundary": YGGDRASIL_OBSERVED_STATE_CLAIM_BOUNDARY,
                        "redacted": True,
                    },
                },
            )
            return {
                "status": "ok",
                "count": 1,
                "peers": [{"remote": "tls://10.0.0.1:9000"}],
                "evidence": {
                    "source_agents": ["yggdrasil-client"],
                    "event_ids": [event.event_id],
                    "events_total": 1,
                    "claim_boundary": YGGDRASIL_OBSERVED_STATE_CLAIM_BOUNDARY,
                    "redacted": True,
                },
            }

        mock_peers.side_effect = fake_get_yggdrasil_peers

        from src.mesh.telemetry_collector import MeshTelemetryCollector

        c = MeshTelemetryCollector(event_bus=bus, event_project_root=str(tmp_path))
        asyncio.run(c._collect_once())

        events = bus.get_event_history(
            EventType.PIPELINE_STAGE_END,
            source_agent="mesh-telemetry-collector",
            limit=10,
        )
        assert events
        data = events[-1].data
        event_text = str(data)

        assert data["operation"] == "collect_once"
        assert data["service_name"] == "mesh-telemetry-collector"
        assert data["layer"] == "mesh_telemetry_collector_observed_state"
        assert data["observed_state"] is True
        assert data["control_action"] is False
        assert data["status"] == "success"
        assert data["yggdrasil"]["peer_count"] == 1
        assert data["yggdrasil"]["peer_uri_hashes_total"] == 1
        assert data["optimizer"]["route_update_attempts"] == 1
        assert data["optimizer"]["routes_updated"] == 0
        assert data["optimizer"]["routes_registered"] == 1
        assert (
            data["optimizer"]["metric_sources"]["latency_ms"][
                "fallback_default"
            ]
            == 1
        )
        assert (
            data["optimizer"]["metric_sources"]["packet_loss_percent"][
                "fallback_default"
            ]
            == 1
        )
        assert data["optimizer"]["metric_sources"]["fallback_values_used"] is True
        assert (
            data["optimizer"]["recommendations"]["action_counts"]
            == {"refresh": 1}
        )
        assert data["downstream_evidence"]["source_agents"] == ["yggdrasil-client"]
        assert data["downstream_evidence"]["events_total"] == 1
        assert data["downstream_evidence"]["claim_boundaries"] == [
            YGGDRASIL_OBSERVED_STATE_CLAIM_BOUNDARY
        ]
        assert data["downstream_evidence"]["claim_boundaries_total"] == 1
        assert data["downstream_claim_gates"]["present"] is True
        assert data["downstream_claim_gates"]["claim_gates_total"] == 1
        downstream_gate = data["downstream_claim_gates"]["claim_gates"][0]
        assert downstream_gate["source_agent"] == "yggdrasil-client"
        assert downstream_gate["schema"] == (
            "x0tta6bl4.yggdrasil_observed_state.claim_gate.v1"
        )
        assert downstream_gate["flags"][
            "local_observed_state_claim_allowed"
        ] is True
        assert downstream_gate["flags"][
            "remote_peer_authenticity_claim_allowed"
        ] is False
        assert downstream_gate["flags"][
            "live_packet_reachability_claim_allowed"
        ] is False
        assert downstream_gate["flags"][
            "production_readiness_claim_allowed"
        ] is False
        assert "10.0.0.1" not in event_text

        route_arg = optimizer.register_route.call_args.args[0]
        assert route_arg.next_hop == "tls://10.0.0.1:9000"
        assert route_arg.latency_ms == 50.0
        assert route_arg.packet_loss == 0.0

    def test_uses_observed_peer_metrics_when_available(
        self,
        mock_deps,
        tmp_path,
    ):
        mock_opt, mock_peers, _ = mock_deps
        bus = EventBus(project_root=str(tmp_path))
        optimizer = mock_opt.return_value
        optimizer._routes = {"direct-tls://10.0.0.1:9000": MagicMock()}
        optimizer.update_route_metrics.return_value = optimizer._routes[
            "direct-tls://10.0.0.1:9000"
        ]
        optimizer.optimize_routes.return_value = {"recommendations": []}
        mock_peers.return_value = {
            "status": "ok",
            "count": 1,
            "peers": [
                {
                    "remote": "tls://10.0.0.1:9000",
                    "latency_ms": "23.5ms",
                    "packet_loss_percent": "1.25%",
                    "bandwidth_mbps": "42.0",
                    "jitter_ms": 3,
                    "hop_count": 2,
                }
            ],
        }

        from src.mesh.telemetry_collector import MeshTelemetryCollector

        c = MeshTelemetryCollector(event_bus=bus, event_project_root=str(tmp_path))
        asyncio.run(c._collect_once())

        optimizer.update_route_metrics.assert_called_once_with(
            route_id="direct-tls://10.0.0.1:9000",
            latency_ms=23.5,
            packet_loss=1.25,
            bandwidth_mbps=42.0,
            jitter_ms=3.0,
        )
        optimizer.register_route.assert_not_called()

        events = bus.get_event_history(
            EventType.PIPELINE_STAGE_END,
            source_agent="mesh-telemetry-collector",
            limit=10,
        )
        data = events[-1].data
        metric_sources = data["optimizer"]["metric_sources"]
        event_text = str(data)

        assert data["optimizer"]["routes_updated"] == 1
        assert metric_sources["latency_ms"]["observed"] == 1
        assert metric_sources["latency_ms"]["fallback_default"] == 0
        assert metric_sources["packet_loss_percent"]["observed"] == 1
        assert metric_sources["bandwidth_mbps"]["observed"] == 1
        assert metric_sources["jitter_ms"]["observed"] == 1
        assert metric_sources["hop_count"]["observed"] == 1
        assert metric_sources["fallback_values_used"] is False
        assert "10.0.0.1" not in event_text

    def test_links_optimizer_evidence_when_report_carries_event_id(
        self,
        mock_deps,
        tmp_path,
    ):
        mock_opt, mock_peers, _ = mock_deps
        bus = EventBus(project_root=str(tmp_path))
        optimizer = mock_opt.return_value
        optimizer._routes = {"direct-tls://10.0.0.1:9000": MagicMock()}
        optimizer.update_route_metrics.return_value = optimizer._routes[
            "direct-tls://10.0.0.1:9000"
        ]
        optimizer_event = bus.publish(
            EventType.PIPELINE_STAGE_END,
            "mesh-yggdrasil-optimizer",
            {
                "operation": "optimize_routes",
                "observed_state": True,
                "route": "tls://10.0.0.1:9000",
            },
        )
        optimizer.optimize_routes.return_value = {
            "recommendations": [],
            "evidence": {
                "source_agents": ["mesh-yggdrasil-optimizer"],
                "event_ids": [optimizer_event.event_id],
                "events_total": 1,
                "redacted": True,
            },
        }
        mock_peers.return_value = {
            "status": "ok",
            "count": 1,
            "peers": [{"remote": "tls://10.0.0.1:9000", "latency_ms": 12.0}],
        }

        from src.mesh.telemetry_collector import MeshTelemetryCollector

        c = MeshTelemetryCollector(event_bus=bus, event_project_root=str(tmp_path))
        asyncio.run(c._collect_once())

        events = bus.get_event_history(
            EventType.PIPELINE_STAGE_END,
            source_agent="mesh-telemetry-collector",
            limit=10,
        )
        data = events[-1].data

        assert "mesh-yggdrasil-optimizer" in data["downstream_evidence"][
            "source_agents"
        ]
        assert optimizer_event.event_id in data["downstream_evidence"]["event_ids"]
        assert "10.0.0.1" not in str(data)

    def test_uses_admin_estimates_when_enabled_and_peer_fields_missing(
        self,
        mock_deps,
        tmp_path,
    ):
        mock_opt, mock_peers, _ = mock_deps
        bus = EventBus(project_root=str(tmp_path))
        optimizer = mock_opt.return_value
        optimizer._routes = {"direct-tls://10.0.0.1:9000": MagicMock()}
        optimizer.update_route_metrics.return_value = optimizer._routes[
            "direct-tls://10.0.0.1:9000"
        ]
        optimizer.optimize_routes.return_value = {"recommendations": []}

        def fake_get_yggdrasil_peers(**kwargs):
            event = kwargs["event_bus"].publish(
                EventType.PIPELINE_STAGE_END,
                "yggdrasil-client",
                {
                    "operation": "get_peers",
                    "observed_state": True,
                    "remote": "tls://10.0.0.1:9000",
                },
            )
            return {
                "status": "ok",
                "count": 1,
                "peers": [{"remote": "tls://10.0.0.1:9000"}],
                "evidence": {
                    "source_agents": ["yggdrasil-client"],
                    "event_ids": [event.event_id],
                    "events_total": 1,
                    "redacted": True,
                },
            }

        mock_peers.side_effect = fake_get_yggdrasil_peers

        from src.mesh.telemetry_collector import MeshTelemetryCollector

        c = MeshTelemetryCollector(
            event_bus=bus,
            event_project_root=str(tmp_path),
            enable_admin_metric_enrichment=True,
            admin_metric_provider=_AdminMetricProvider(bus),
        )
        asyncio.run(c._collect_once())

        optimizer.update_route_metrics.assert_called_once_with(
            route_id="direct-tls://10.0.0.1:9000",
            latency_ms=24.0,
            packet_loss=0.0,
            bandwidth_mbps=8.5,
            jitter_ms=None,
        )

        events = bus.get_event_history(
            EventType.PIPELINE_STAGE_END,
            source_agent="mesh-telemetry-collector",
            limit=10,
        )
        data = events[-1].data
        metric_sources = data["optimizer"]["metric_sources"]
        enrichment = data["optimizer"]["metric_enrichment"]
        event_text = str(data)

        assert metric_sources["latency_ms"]["estimated"] == 1
        assert metric_sources["latency_ms"]["fallback_default"] == 0
        assert metric_sources["bandwidth_mbps"]["estimated"] == 1
        assert metric_sources["packet_loss_percent"]["fallback_default"] == 1
        assert enrichment["status"] == "success"
        assert enrichment["source"] == "yggdrasil_admin_api"
        assert enrichment["admin_peer_count"] == 1
        assert enrichment["estimated_peer_count"] == 1
        assert enrichment["matched_peer_count"] == 1
        assert set(data["downstream_evidence"]["source_agents"]) == {
            "real-network-adapter",
            "yggdrasil-client",
        }
        assert data["downstream_evidence"]["events_total"] == 2
        assert "10.0.0.1" not in event_text

    def test_dataplane_probe_overrides_admin_estimate_when_enabled(
        self,
        mock_deps,
        tmp_path,
    ):
        mock_opt, mock_peers, _ = mock_deps
        bus = EventBus(project_root=str(tmp_path))
        optimizer = mock_opt.return_value
        optimizer._routes = {"direct-tls://10.0.0.1:9000": MagicMock()}
        optimizer.update_route_metrics.return_value = optimizer._routes[
            "direct-tls://10.0.0.1:9000"
        ]
        optimizer.optimize_routes.return_value = {"recommendations": []}
        probe_provider = _DataplaneProbeProvider(bus)
        mock_peers.return_value = {
            "status": "ok",
            "count": 1,
            "peers": [{"remote": "tls://10.0.0.1:9000"}],
        }

        from src.mesh.telemetry_collector import MeshTelemetryCollector

        c = MeshTelemetryCollector(
            event_bus=bus,
            event_project_root=str(tmp_path),
            enable_admin_metric_enrichment=True,
            admin_metric_provider=_AdminMetricProvider(bus),
            enable_dataplane_probe=True,
            dataplane_probe_provider=probe_provider,
            max_dataplane_probe_peers=1,
        )
        asyncio.run(c._collect_once())

        optimizer.update_route_metrics.assert_called_once_with(
            route_id="direct-tls://10.0.0.1:9000",
            latency_ms=12.5,
            packet_loss=2.5,
            bandwidth_mbps=8.5,
            jitter_ms=1.5,
        )
        assert probe_provider.targets == ["10.0.0.1"]

        events = bus.get_event_history(
            EventType.PIPELINE_STAGE_END,
            source_agent="mesh-telemetry-collector",
            limit=10,
        )
        data = events[-1].data
        metric_sources = data["optimizer"]["metric_sources"]
        dataplane_probe = data["optimizer"]["dataplane_probe"]
        event_text = str(data)

        assert metric_sources["latency_ms"]["probed"] == 1
        assert metric_sources["latency_ms"]["estimated"] == 0
        assert metric_sources["packet_loss_percent"]["probed"] == 1
        assert metric_sources["jitter_ms"]["probed"] == 1
        assert metric_sources["bandwidth_mbps"]["estimated"] == 1
        assert dataplane_probe["status"] == "success"
        assert dataplane_probe["source"] == "icmp_ping"
        assert dataplane_probe["attempts"] == 1
        assert dataplane_probe["successes"] == 1
        assert dataplane_probe["matched_peer_count"] == 1
        assert "real-network-adapter" in data["downstream_evidence"]["source_agents"]
        assert data["downstream_evidence"]["events_total"] == 2
        assert "10.0.0.1" not in event_text

    def test_publishes_skipped_event_when_yggdrasil_status_not_ok(
        self,
        mock_deps,
        tmp_path,
    ):
        mock_opt, mock_peers, _ = mock_deps
        bus = EventBus(project_root=str(tmp_path))
        mock_peers.return_value = {"status": "error", "count": 0, "peers": []}
        optimizer = mock_opt.return_value

        from src.mesh.telemetry_collector import MeshTelemetryCollector

        c = MeshTelemetryCollector(event_bus=bus, event_project_root=str(tmp_path))
        asyncio.run(c._collect_once())

        events = bus.get_event_history(
            EventType.PIPELINE_STAGE_END,
            source_agent="mesh-telemetry-collector",
            limit=10,
        )
        assert events
        data = events[-1].data

        assert data["status"] == "skipped"
        assert data["yggdrasil"]["status"] == "error"
        assert data["optimizer"]["routes_updated"] == 0
        optimizer.update_route_metrics.assert_not_called()
