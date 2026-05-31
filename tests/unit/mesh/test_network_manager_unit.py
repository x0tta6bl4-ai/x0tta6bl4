"""Unit tests for MeshNetworkManager."""

from unittest.mock import AsyncMock, MagicMock

import pytest

from src.coordination.events import EventBus, EventType
from src.mesh.network_manager import (
    MeshNetworkManager,
    NodeVerificationError,
    NodeVerificationResult,
    VerificationMode,
)
from src.network import yggdrasil_client
from src.services.service_event_trace import service_event_trace_history


def _latest_mesh_manager_event(bus: EventBus):
    events = bus.get_event_history(
        EventType.PIPELINE_STAGE_END,
        source_agent="mesh-network-manager",
        limit=20,
    )
    assert events
    return events[-1]


class TestMeshNetworkManagerInit:
    def test_default_init(self):
        mgr = MeshNetworkManager()
        assert mgr.node_id == "local"
        assert mgr._router is None
        assert mgr._route_preference == "balanced"

    def test_custom_node_id(self):
        mgr = MeshNetworkManager(node_id="node-a")
        assert mgr.node_id == "node-a"


class TestGetStatistics:
    @pytest.mark.asyncio
    async def test_returns_expected_keys(self):
        mgr = MeshNetworkManager(node_id="test")
        stats = await mgr.get_statistics()
        assert "active_peers" in stats
        assert "avg_latency_ms" in stats
        assert "packet_loss_percent" in stats
        assert "mttr_minutes" in stats

    @pytest.mark.asyncio
    async def test_with_mocked_router(self):
        mgr = MeshNetworkManager(node_id="test")
        mock_router = MagicMock()
        mock_router.get_mape_k_metrics = AsyncMock(
            return_value={
                "packet_drop_rate": 0.05,
                "total_routes_known": 3,
                "avg_route_hop_count": 2.0,
            }
        )
        mgr._router = mock_router

        stats = await mgr.get_statistics()
        assert stats["packet_loss_percent"] == pytest.approx(5.0)
        assert stats["active_peers"] >= 3
        assert stats["avg_latency_ms"] == pytest.approx(30.0)

    @pytest.mark.asyncio
    async def test_router_failure_graceful(self):
        mgr = MeshNetworkManager(node_id="test")
        mock_router = MagicMock()
        mock_router.get_mape_k_metrics = AsyncMock(side_effect=RuntimeError("down"))
        mgr._router = mock_router

        stats = await mgr.get_statistics()
        # Router metrics default to 0, but Yggdrasil may still contribute peers
        assert stats["packet_loss_percent"] == 0.0
        assert isinstance(stats["active_peers"], (int, float))

    @pytest.mark.asyncio
    async def test_publishes_bounded_observed_state(
        self,
        monkeypatch,
        tmp_path,
    ):
        bus = EventBus(project_root=str(tmp_path))
        mgr = MeshNetworkManager(node_id="test", event_bus=bus)
        mock_router = MagicMock()
        mock_router.get_mape_k_metrics = AsyncMock(
            return_value={
                "packet_drop_rate": 0.05,
                "total_routes_known": 3,
                "avg_route_hop_count": 2.0,
            }
        )
        mgr._router = mock_router

        def _fake_get_yggdrasil_peers(**kwargs):
            assert kwargs["include_evidence"] is True
            event = kwargs["event_bus"].publish(
                EventType.PIPELINE_STAGE_END,
                "yggdrasil-client",
                {
                    "operation": "get_peers",
                    "read_only": True,
                    "observed_state": True,
                    "remote": "10.0.0.1",
                },
            )
            return {
                "status": "ok",
                "count": 5,
                "peers": [{"remote": "10.0.0.1"}],
                "evidence": {
                    "source_agents": ["yggdrasil-client"],
                    "event_ids": [event.event_id],
                    "events_total": 1,
                    "claim_boundary": (
                        yggdrasil_client.YGGDRASIL_OBSERVED_STATE_CLAIM_BOUNDARY
                    ),
                    "redacted": True,
                },
            }

        monkeypatch.setattr(
            yggdrasil_client,
            "get_yggdrasil_peers",
            _fake_get_yggdrasil_peers,
        )

        stats = await mgr.get_statistics()
        event = _latest_mesh_manager_event(bus)
        data = event.data
        event_text = str(data)

        assert stats["active_peers"] == 5
        assert stats["packet_loss_percent"] == pytest.approx(5.0)
        assert data["resource"] == "mesh:network_manager:statistics"
        assert data["operation"] == "get_statistics"
        assert data["service_name"] == "mesh-network-manager"
        assert data["layer"] == "mesh_network_manager_observed_state"
        assert data["read_only"] is True
        assert data["observed_state"] is True
        assert data["safe_actuator"] is False
        assert data["status"] == "success"
        assert data["stats"]["active_peers"] == 5.0
        assert data["sources"]["router"]["status"] == "success"
        assert data["sources"]["yggdrasil"] == {
            "status": "ok",
            "peer_count": 5,
            "peer_values_redacted": True,
        }
        assert data["downstream_evidence"]["events_total"] == 1
        assert data["downstream_evidence"]["source_agents"] == ["yggdrasil-client"]
        assert data["downstream_evidence"]["claim_boundaries"] == [
            yggdrasil_client.YGGDRASIL_OBSERVED_STATE_CLAIM_BOUNDARY
        ]
        assert data["downstream_evidence"]["claim_boundaries_total"] == 1
        assert "10.0.0.1" not in event_text

    @pytest.mark.asyncio
    async def test_failure_event_redacts_router_and_yggdrasil_errors(
        self,
        monkeypatch,
        tmp_path,
    ):
        bus = EventBus(project_root=str(tmp_path))
        mgr = MeshNetworkManager(node_id="test", event_bus=bus)
        mock_router = MagicMock()
        mock_router.get_mape_k_metrics = AsyncMock(
            side_effect=RuntimeError("router failed for 10.0.0.1")
        )
        mgr._router = mock_router

        def _fake_get_yggdrasil_peers(**kwargs):
            raise RuntimeError("yggdrasil peer failure 200:dead:beef::1")

        monkeypatch.setattr(
            yggdrasil_client,
            "get_yggdrasil_peers",
            _fake_get_yggdrasil_peers,
        )

        stats = await mgr.get_statistics()
        event = _latest_mesh_manager_event(bus)
        data = event.data
        event_text = str(data)

        assert stats["packet_loss_percent"] == 0.0
        assert data["status"] == "partial"
        assert data["sources"]["router"]["status"] == "failed"
        assert data["sources"]["router"]["error_redacted"] is True
        assert data["sources"]["router"]["error_sha256"]
        assert data["sources"]["yggdrasil"]["status"] == "failed"
        assert data["sources"]["yggdrasil"]["error_redacted"] is True
        assert data["errors"] == [{"type": "RuntimeError", "message_redacted": True}]
        assert "10.0.0.1" not in event_text
        assert "200:dead:beef" not in event_text
        assert "router failed" not in event_text
        assert "yggdrasil peer failure" not in event_text

    @pytest.mark.asyncio
    async def test_observed_state_trace_is_registered(self, monkeypatch, tmp_path):
        bus = EventBus(project_root=str(tmp_path))
        mgr = MeshNetworkManager(node_id="test", event_bus=bus)
        monkeypatch.setattr(
            yggdrasil_client,
            "get_yggdrasil_peers",
            lambda **_kwargs: {"status": "ok", "count": 0, "peers": []},
        )

        await mgr.get_statistics()
        trace = service_event_trace_history(
            bus,
            service_name="mesh-network-manager",
            event_type=EventType.PIPELINE_STAGE_END,
            limit=10,
        )

        assert trace["events_total"] == 1
        assert trace["filter"]["services"][0]["layer"] == (
            "mesh_network_manager_observed_state"
        )
        assert trace["events"][0]["source_agent"] == "mesh-network-manager"


class TestVerifyNodeStateEvidence:
    @pytest.mark.asyncio
    async def test_verify_node_state_publishes_redacted_observed_state_event(
        self,
        monkeypatch,
        tmp_path,
    ):
        bus = EventBus(project_root=str(tmp_path))
        mgr = MeshNetworkManager(event_bus=bus)
        monkeypatch.setattr(
            mgr,
            "_verify_ping",
            AsyncMock(
                return_value=NodeVerificationResult(
                    node_id="node-secret-1",
                    is_healthy=True,
                    verification_mode=VerificationMode.PING,
                    latency_ms=12.3456,
                )
            ),
        )

        result = await mgr.verify_node_state(
            "node-secret-1",
            mode=VerificationMode.PING,
            expected_config_hash="raw-config-secret",
        )
        event = _latest_mesh_manager_event(bus)
        data = event.data
        event_text = str(data)

        assert result.is_healthy is True
        assert result.evidence_event_id == event.event_id
        assert data["operation"] == "verify_node_state"
        assert data["resource"] == "mesh:network_manager:node_verification"
        assert data["service_name"] == "mesh-network-manager"
        assert data["layer"] == "mesh_network_manager_observed_state"
        assert data["read_only"] is True
        assert data["observed_state"] is True
        assert data["control_action"] is False
        assert data["safe_actuator"] is False
        assert data["status"] == "success"
        assert data["context"]["node_id_redacted"] is True
        assert data["context"]["node_id_sha256"]
        assert data["context"]["expected_config_hash_redacted"] is True
        assert data["result"]["flags"]["is_healthy"] is True
        assert data["result"]["numeric"]["latency_ms"] == pytest.approx(12.346)
        assert data["retry"]["attempts_used"] == 1
        assert data["retry"]["cache_written"] is True
        assert data["bounded_output"]["raw_node_id_redacted"] is True
        assert "node-secret-1" not in event_text
        assert "raw-config-secret" not in event_text

    @pytest.mark.asyncio
    async def test_verify_node_state_none_guard_publishes_failed_event(
        self,
        monkeypatch,
        tmp_path,
    ):
        monkeypatch.delenv(
            MeshNetworkManager.UNVERIFIED_RESTORE_ENV_VAR,
            raising=False,
        )
        bus = EventBus(project_root=str(tmp_path))
        mgr = MeshNetworkManager(event_bus=bus)

        with pytest.raises(NodeVerificationError):
            await mgr.verify_node_state("node-secret-1", mode=VerificationMode.NONE)

        events = bus.get_event_history(
            EventType.TASK_FAILED,
            source_agent="mesh-network-manager",
            limit=10,
        )
        assert events
        data = events[-1].data

        assert events[-1].event_id
        assert data["operation"] == "verify_node_state"
        assert data["status"] == "blocked"
        assert data["context"]["verification_mode"] == "none"
        assert data["retry"]["bypassed"] is True
        assert data["errors"] == [
            {"type": "NodeVerificationError", "message_redacted": True}
        ]
        assert "node-secret-1" not in str(data)

    @pytest.mark.asyncio
    async def test_verify_node_state_exhausted_retries_redacts_error_metadata(
        self,
        monkeypatch,
        tmp_path,
    ):
        bus = EventBus(project_root=str(tmp_path))
        mgr = MeshNetworkManager(event_bus=bus, verification_retries=1)
        monkeypatch.setattr(
            mgr,
            "_verify_ping",
            AsyncMock(side_effect=RuntimeError("endpoint 10.0.0.1 node-secret-1")),
        )

        result = await mgr.verify_node_state(
            "node-secret-1",
            mode=VerificationMode.PING,
        )
        event = _latest_mesh_manager_event(bus)
        data = event.data
        event_text = str(data)

        assert result.is_healthy is False
        assert result.evidence_event_id == event.event_id
        assert data["operation"] == "verify_node_state"
        assert data["status"] == "unhealthy"
        assert data["result"]["flags"]["is_healthy"] is False
        assert data["result"]["flags"]["error_message_redacted"] is True
        assert data["result"]["error_sha256"]
        assert data["retry"]["attempts_used"] == 1
        assert data["retry"]["cache_written"] is False
        assert data["errors"] == [{"type": "RuntimeError", "message_redacted": True}]
        assert "10.0.0.1" not in event_text
        assert "node-secret-1" not in event_text
        assert "endpoint 10.0.0.1" not in event_text


class TestSetRoutePreference:
    @pytest.mark.asyncio
    async def test_valid_preferences(self):
        mgr = MeshNetworkManager()
        for pref in ("low_latency", "reliability", "balanced"):
            assert await mgr.set_route_preference(pref) is True
            assert mgr._route_preference == pref

    @pytest.mark.asyncio
    async def test_invalid_preference(self):
        mgr = MeshNetworkManager()
        assert await mgr.set_route_preference("invalid") is False
        assert mgr._route_preference == "balanced"

    @pytest.mark.asyncio
    async def test_valid_preference_publishes_control_action_event(self, tmp_path):
        bus = EventBus(project_root=str(tmp_path))
        mgr = MeshNetworkManager(event_bus=bus)

        assert await mgr.set_route_preference("low_latency") is True
        event = _latest_mesh_manager_event(bus)
        data = event.data

        assert data["operation"] == "set_route_preference"
        assert data["resource"] == "mesh:network_manager:route_preference"
        assert data["read_only"] is False
        assert data["observed_state"] is False
        assert data["control_action"] is True
        assert data["safe_actuator"] is False
        assert data["success"] is True
        assert data["context"]["route_preference"] == "low_latency"
        assert data["downstream_evidence"]["events_total"] == 0

    @pytest.mark.asyncio
    async def test_invalid_preference_event_redacts_raw_value(self, tmp_path):
        bus = EventBus(project_root=str(tmp_path))
        mgr = MeshNetworkManager(event_bus=bus)

        assert await mgr.set_route_preference("node-secret-1") is False
        events = bus.get_event_history(
            EventType.TASK_FAILED,
            source_agent="mesh-network-manager",
            limit=10,
        )
        assert events
        data = events[-1].data

        assert data["operation"] == "set_route_preference"
        assert data["status"] == "invalid"
        assert data["success"] is False
        assert data["context"]["route_preference"] == "[redacted]"
        assert data["context"]["route_preference_redacted"] is True
        assert data["context"]["route_preference_sha256"]
        assert "node-secret-1" not in str(data)


class TestAggressiveHealing:
    @pytest.mark.asyncio
    async def test_no_router_returns_zero(self):
        mgr = MeshNetworkManager()
        # _get_router will fail to import, returns None
        healed = await mgr.trigger_aggressive_healing()
        assert healed == 0

    @pytest.mark.asyncio
    async def test_healing_logs_entry(self):
        mgr = MeshNetworkManager()
        mock_router = MagicMock()
        mock_router.get_routes.return_value = {}
        mock_router.ROUTE_TIMEOUT = 60.0
        mgr._router = mock_router

        await mgr.trigger_aggressive_healing()
        assert len(mgr._healing_log) == 1
        assert "healed" in mgr._healing_log[0]

    @pytest.mark.asyncio
    async def test_healing_publishes_control_action_event(self, tmp_path):
        bus = EventBus(project_root=str(tmp_path))
        mgr = MeshNetworkManager(event_bus=bus)
        mock_router = MagicMock()
        mock_router.get_routes.return_value = {}
        mock_router.ROUTE_TIMEOUT = 60.0
        mgr._router = mock_router

        healed = await mgr.trigger_aggressive_healing()
        event = _latest_mesh_manager_event(bus)
        data = event.data

        assert healed == 0
        assert data["operation"] == "trigger_aggressive_healing"
        assert data["resource"] == "mesh:network_manager:aggressive_healing"
        assert data["control_action"] is True
        assert data["success"] is True
        assert data["context"]["healing_mode"] == "aggressive"
        assert data["result"]["numeric"]["healed"] == 0.0
        gate = data["claim_gate"]
        assert gate["decision"] == "LOCAL_HEALING_LIFECYCLE_ONLY"
        assert gate["local_healing_lifecycle_claim_allowed"] is True
        assert gate["local_node_verification_claim_allowed"] is False
        assert gate["dataplane_confirmed"] is False
        assert gate["restored_dataplane_claim_allowed"] is False
        assert gate["traffic_delivery_claim_allowed"] is False
        assert gate["production_readiness_claim_allowed"] is False
        assert gate["requires_post_action_dataplane_revalidation"] is True
        assert gate["blockers"] == ["no_bounded_post_action_dataplane_probe_attached"]
        assert "does not prove restored dataplane behavior" in gate["claim_boundary"]

    @pytest.mark.asyncio
    async def test_healing_links_verification_evidence_event(
        self,
        monkeypatch,
        tmp_path,
    ):
        import src.database as database_mod

        bus = EventBus(project_root=str(tmp_path))
        mgr = MeshNetworkManager(event_bus=bus)
        mock_router = MagicMock()
        mock_router.get_routes.return_value = {}
        mock_router.ROUTE_TIMEOUT = 60.0
        mgr._router = mock_router
        offline_node = MagicMock()
        offline_node.id = "node-secret-1"
        offline_node.status = "offline"
        offline_node.last_seen = None

        class FakeMeshNode:
            status = "offline"

        class FakeQuery:
            def filter(self, *_args, **_kwargs):
                return self

            def all(self):
                return [offline_node]

        class FakeDB:
            committed = False

            def query(self, _model):
                return FakeQuery()

            def commit(self):
                self.committed = True

        class FakeSession:
            def __init__(self, db):
                self.db = db

            def __enter__(self):
                return self.db

            def __exit__(self, *_args):
                return False

        fake_db = FakeDB()
        monkeypatch.setattr(database_mod, "MeshNode", FakeMeshNode)
        monkeypatch.setattr(database_mod, "SessionLocal", lambda: FakeSession(fake_db))
        monkeypatch.setattr(
            mgr,
            "_verify_full",
            AsyncMock(
                return_value=NodeVerificationResult(
                    node_id="node-secret-1",
                    is_healthy=True,
                    verification_mode=VerificationMode.FULL,
                    latency_ms=8.0,
                )
            ),
        )

        healed = await mgr.trigger_aggressive_healing(auto_restore_nodes=True)
        action_event = _latest_mesh_manager_event(bus)
        action_data = action_event.data
        verification_events = [
            event
            for event in bus.get_event_history(
                EventType.PIPELINE_STAGE_END,
                source_agent="mesh-network-manager",
                limit=20,
            )
            if event.data.get("operation") == "verify_node_state"
        ]

        assert healed == 1
        assert offline_node.status == "healthy"
        assert fake_db.committed is True
        assert len(verification_events) == 1
        assert action_data["operation"] == "trigger_aggressive_healing"
        assert action_data["result"]["numeric"]["verification_results"] == 1.0
        assert action_data["result"]["numeric"]["verification_evidence_events"] == 1.0
        assert action_data["claim_gate"]["local_node_verification_claim_allowed"] is True
        assert action_data["claim_gate"]["verification_evidence_events"] == 1
        assert action_data["claim_gate"]["restored_dataplane_claim_allowed"] is False
        assert action_data["downstream_evidence"]["source_agents"] == [
            "mesh-network-manager"
        ]
        assert action_data["downstream_evidence"]["event_ids"] == [
            verification_events[0].event_id
        ]
        assert action_data["downstream_evidence"]["events_total"] == 1
        assert "node-secret-1" not in str(action_data)

    @pytest.mark.asyncio
    async def test_healing_can_attach_bounded_post_action_probe_evidence(
        self,
        monkeypatch,
        tmp_path,
    ):
        import src.database as database_mod

        bus = EventBus(project_root=str(tmp_path))

        class ProbeProvider:
            def __init__(self):
                self.targets = []

            def probe_peer(self, target):
                self.targets.append(target)
                event = bus.publish(
                    EventType.PIPELINE_STAGE_END,
                    "real-network-adapter",
                    {
                        "operation": "dataplane_ping_probe",
                        "status": "success",
                        "redacted": True,
                        "target_redacted": True,
                    },
                )
                return {
                    "status": "ok",
                    "latency_ms": 7.5,
                    "packet_loss_percent": 0.0,
                    "jitter_ms": 0.2,
                    "evidence": {
                        "source_agents": ["real-network-adapter"],
                        "event_ids": [event.event_id],
                        "events_total": 1,
                        "redacted": True,
                    },
                    "claim_boundary": "bounded fake dataplane probe",
                    "redacted": True,
                }

        class FakeMeshNode:
            status = "offline"

        class FakeQuery:
            def filter(self, *_args, **_kwargs):
                return self

            def all(self):
                return []

        class FakeDB:
            def query(self, _model):
                return FakeQuery()

        class FakeSession:
            def __init__(self, db):
                self.db = db

            def __enter__(self):
                return self.db

            def __exit__(self, *_args):
                return False

        monkeypatch.setattr(database_mod, "MeshNode", FakeMeshNode)
        monkeypatch.setattr(database_mod, "SessionLocal", lambda: FakeSession(FakeDB()))

        probe_provider = ProbeProvider()
        mgr = MeshNetworkManager(
            event_bus=bus,
            enable_post_heal_dataplane_probe=True,
            post_heal_dataplane_probe_provider=probe_provider,
        )
        stale_route = MagicMock()
        stale_route.age = 49.0
        mock_router = MagicMock()
        mock_router.get_routes.return_value = {"dest-secret-1": [stale_route]}
        mock_router.ROUTE_TIMEOUT = 60.0
        mock_router._discover_route = AsyncMock()
        mgr._router = mock_router

        healed = await mgr.trigger_aggressive_healing(
            post_action_dataplane_probe_target="10.0.0.1"
        )
        action_event = _latest_mesh_manager_event(bus)
        action_data = action_event.data
        revalidation = action_data["post_action_dataplane_revalidation"]
        gate = revalidation["claim_gate"]

        assert healed == 1
        assert probe_provider.targets == ["10.0.0.1"]
        assert gate["decision"] == "RESTORED_DATAPLANE_CLAIM_ALLOWED"
        assert gate["post_action_probe_enabled"] is True
        assert gate["post_action_probe_target_present"] is True
        assert gate["post_action_probe_attempted"] is True
        assert gate["dataplane_confirmed"] is True
        assert gate["restored_dataplane_claim_allowed"] is True
        assert gate["traffic_delivery_claim_allowed"] is False
        assert gate["customer_traffic_claim_allowed"] is False
        assert gate["production_readiness_claim_allowed"] is False
        assert gate["blockers"] == []
        assert revalidation["post_action_dataplane_revalidated"] is True
        assert revalidation["restored_dataplane_claim_allowed"] is True
        assert action_data["downstream_evidence"]["source_agents"] == [
            "real-network-adapter"
        ]
        assert action_data["downstream_evidence"]["events_total"] == 1
        assert "10.0.0.1" not in str(action_data)
        assert "dest-secret-1" not in str(action_data)

    @pytest.mark.asyncio
    async def test_healing_default_probe_uses_recovery_dataplane_adapter(
        self,
        monkeypatch,
        tmp_path,
    ):
        import src.database as database_mod

        bus = EventBus(project_root=str(tmp_path))
        calls = []

        def fake_probe_builder(target, **kwargs):
            calls.append({"target": target, **kwargs})

            def _probe():
                event = bus.publish(
                    EventType.PIPELINE_STAGE_END,
                    "real-network-adapter",
                    {
                        "operation": "dataplane_ping_probe",
                        "status": "success",
                        "redacted": True,
                        "target_redacted": True,
                    },
                )
                return {
                    "status": "ok",
                    "dataplane_confirmed": True,
                    "latency_ms": 4.25,
                    "packet_loss_percent": 0.0,
                    "evidence": {
                        "source_agents": ["real-network-adapter"],
                        "event_ids": [event.event_id],
                        "events_total": 1,
                        "redacted": True,
                    },
                    "claim_boundary": "bounded adapter dataplane probe",
                    "raw_target_redacted": True,
                    "redacted": True,
                }

            return _probe

        class FakeMeshNode:
            status = "offline"

        class FakeQuery:
            def filter(self, *_args, **_kwargs):
                return self

            def all(self):
                return []

        class FakeDB:
            def query(self, _model):
                return FakeQuery()

        class FakeSession:
            def __init__(self, db):
                self.db = db

            def __enter__(self):
                return self.db

            def __exit__(self, *_args):
                return False

        monkeypatch.setattr(database_mod, "MeshNode", FakeMeshNode)
        monkeypatch.setattr(database_mod, "SessionLocal", lambda: FakeSession(FakeDB()))
        monkeypatch.setattr(
            "src.mesh.network_manager.build_recovery_dataplane_ping_probe",
            fake_probe_builder,
        )

        mgr = MeshNetworkManager(
            event_bus=bus,
            enable_post_heal_dataplane_probe=True,
        )
        stale_route = MagicMock()
        stale_route.age = 49.0
        mock_router = MagicMock()
        mock_router.get_routes.return_value = {"dest-secret-adapter": [stale_route]}
        mock_router.ROUTE_TIMEOUT = 60.0
        mock_router._discover_route = AsyncMock()
        mgr._router = mock_router

        healed = await mgr.trigger_aggressive_healing(
            post_action_dataplane_probe_target="10.0.0.2"
        )
        action_event = _latest_mesh_manager_event(bus)
        action_data = action_event.data
        revalidation = action_data["post_action_dataplane_revalidation"]
        gate = revalidation["claim_gate"]

        assert healed == 1
        assert calls
        assert calls[0]["target"] == "10.0.0.2"
        assert calls[0]["event_bus"] is bus
        assert gate["decision"] == "RESTORED_DATAPLANE_CLAIM_ALLOWED"
        assert gate["probe_result"]["raw_target_redacted"] is True
        assert gate["dataplane_confirmed"] is True
        assert revalidation["post_action_dataplane_revalidated"] is True
        assert revalidation["restored_dataplane_claim_allowed"] is True
        assert "10.0.0.2" not in str(action_data)
        assert "dest-secret-adapter" not in str(action_data)


class TestPreemptiveChecks:
    @pytest.mark.asyncio
    async def test_no_router_does_nothing(self):
        mgr = MeshNetworkManager()
        await mgr.trigger_preemptive_checks()  # should not raise

    @pytest.mark.asyncio
    async def test_preemptive_checks_publish_bounded_action_event(self, tmp_path):
        bus = EventBus(project_root=str(tmp_path))
        mgr = MeshNetworkManager(event_bus=bus)
        stale_route = MagicMock()
        stale_route.age = 45.0
        mock_router = MagicMock()
        mock_router.ROUTE_TIMEOUT = 60.0
        mock_router.get_routes.return_value = {"node-secret-1": [stale_route]}
        mock_router._discover_route = AsyncMock()
        mgr._router = mock_router

        await mgr.trigger_preemptive_checks()
        event = _latest_mesh_manager_event(bus)
        data = event.data

        assert data["operation"] == "trigger_preemptive_checks"
        assert data["resource"] == "mesh:network_manager:preemptive_checks"
        assert data["control_action"] is True
        assert data["success"] is True
        assert data["context"]["healing_mode"] == "preemptive"
        assert data["result"]["flags"]["router_present"] is True
        assert data["result"]["numeric"]["route_count"] == 1.0
        assert data["result"]["numeric"]["discovery_attempts"] == 1.0
        assert "node-secret-1" not in str(data)
        mock_router._discover_route.assert_awaited_once_with("node-secret-1")


class TestComputeMTTR:
    def test_empty_log(self):
        mgr = MeshNetworkManager()
        assert mgr._compute_mttr() == 0.0

    def test_with_entries(self):
        mgr = MeshNetworkManager()
        mgr._healing_log = [
            {"timestamp": "t1", "healed": 2, "duration_minutes": 1.0},
            {"timestamp": "t2", "healed": 1, "duration_minutes": 3.0},
        ]
        assert mgr._compute_mttr() == pytest.approx(2.0)

    def test_ignores_zero_healed(self):
        mgr = MeshNetworkManager()
        mgr._healing_log = [
            {"timestamp": "t1", "healed": 0, "duration_minutes": 5.0},
            {"timestamp": "t2", "healed": 1, "duration_minutes": 2.0},
        ]
        assert mgr._compute_mttr() == pytest.approx(2.0)
