"""
Unit tests for SelfHealingManager
"""

from unittest.mock import Mock, patch


from src.coordination.events import EventBus, EventType
from src.self_healing.mape_k import SelfHealingManager
from src.services.service_event_trace import service_event_trace_history


def _latest_self_healing_event(bus: EventBus, *, operation: str):
    events = bus.get_event_history(
        EventType.PIPELINE_STAGE_END,
        source_agent="self-healing-mapek",
        limit=20,
    )
    events = [event for event in events if event.data.get("operation") == operation]
    assert events
    return events[-1]


class TestSelfHealingManager:
    """Test SelfHealingManager functionality"""

    def test_self_healing_manager_initialization(self):
        """Test SelfHealingManager can be initialized"""
        manager = SelfHealingManager()
        assert manager is not None
        assert manager.node_id == "default"
        assert manager.monitor is not None
        assert manager.analyzer is not None
        assert manager.planner is not None
        assert manager.executor is not None
        assert manager.knowledge is not None

    def test_self_healing_manager_custom_node_id(self):
        """Test SelfHealingManager with custom node ID"""
        manager = SelfHealingManager(node_id="test_node")
        assert manager.node_id == "test_node"

    def test_run_cycle_no_anomalies(self):
        """Test run_cycle with no anomalies detected"""
        manager = SelfHealingManager()

        # Mock monitor to return no anomalies
        with patch.object(manager.monitor, "check", return_value=False):
            # Should not trigger analysis/planning/execution
            manager.run_cycle({"cpu_percent": 10, "memory_percent": 20})

            # Knowledge should still be empty (no incidents recorded)
            assert len(manager.knowledge.incidents) == 0

    def test_run_cycle_publishes_redacted_monitor_event(self, tmp_path):
        """Monitor evidence records bounded metrics without raw node/log values."""
        bus = EventBus(project_root=str(tmp_path))
        manager = SelfHealingManager(node_id="node-secret", event_bus=bus)

        metrics = {
            "cpu_percent": 10,
            "memory_percent": 20,
            "node_id": "raw-node-id",
            "logs": "raw log with 10.0.0.1 and private detail",
            "service_id": "svc-secret",
        }
        manager.run_cycle(metrics)

        event = _latest_self_healing_event(bus, operation="monitor")
        data = event.data
        event_text = str(data)

        assert data["resource"] == "self_healing:mapek:monitor"
        assert data["service_name"] == "self-healing-mapek"
        assert data["layer"] == "self_healing_mapek_control_spine"
        assert data["read_only"] is True
        assert data["observed_state"] is True
        assert data["control_action"] is False
        assert data["metrics"]["numeric"]["cpu_percent"] == 10.0
        assert data["metrics"]["values_redacted"] is True
        assert data["node_id_redacted"] is True
        assert "node-secret" not in event_text
        assert "raw-node-id" not in event_text
        assert "10.0.0.1" not in event_text
        assert "svc-secret" not in event_text

    def test_run_cycle_with_anomalies(self):
        """Test run_cycle with anomalies detected"""
        manager = SelfHealingManager()

        # Mock components
        with (
            patch.object(manager.monitor, "check", return_value=True),
            patch.object(manager.analyzer, "analyze", return_value="High CPU"),
            patch.object(manager.planner, "plan", return_value="Restart service"),
            patch.object(manager.executor, "execute", return_value=True),
        ):

            metrics = {"cpu_percent": 95, "memory_percent": 20}
            manager.run_cycle(metrics)

            # Should have recorded the incident
            assert len(manager.knowledge.incidents) == 1
            incident = manager.knowledge.incidents[0]
            assert incident["issue"] == "High CPU"
            assert incident["action"] == "Restart service"
            assert incident["success"]

    def test_run_cycle_publishes_safe_actuator_execute_event(self, tmp_path):
        """Execute evidence is redacted and still calls the existing executor API."""
        bus = EventBus(project_root=str(tmp_path))
        manager = SelfHealingManager(node_id="node-secret", event_bus=bus)
        raw_action = "AI-Analysis ```restart raw-node-id via 10.0.0.1```"

        with (
            patch.object(manager.monitor, "check", return_value=True),
            patch.object(
                manager.analyzer, "analyze", return_value="Root cause raw-node-id"
            ),
            patch.object(manager.planner, "plan", return_value=raw_action),
            patch.object(manager.executor, "execute", return_value=True) as execute,
        ):
            manager.run_cycle({"cpu_percent": 95, "node_id": "raw-node-id"})

        execute.assert_called_once_with(raw_action)
        event = _latest_self_healing_event(bus, operation="execute")
        data = event.data
        event_text = str(data)

        assert data["resource"] == "self_healing:mapek:execute"
        assert data["safe_actuator"] is True
        assert data["control_action"] is True
        assert data["success"] is True
        assert data["simulated"] is False
        assert data["action"]["redacted"] is True
        assert data["issue"]["redacted"] is True
        assert "raw-node-id" not in event_text
        assert "10.0.0.1" not in event_text
        assert "Root cause" not in event_text

    def test_run_cycle_links_recovery_executor_event_ids_without_payload(
        self, tmp_path
    ):
        """Execute evidence links lower recovery events without copying raw payload."""
        bus = EventBus(project_root=str(tmp_path))
        manager = SelfHealingManager(node_id="node-secret", event_bus=bus)

        def publish_recovery_event(_action):
            bus.publish(
                EventType.PIPELINE_STAGE_END,
                "recovery-action-executor",
                {
                    "raw_node": "raw-node-id",
                    "raw_target": "10.0.0.1",
                    "raw_action": "restart private service",
                },
            )
            return True

        with (
            patch.object(manager.monitor, "check", return_value=True),
            patch.object(manager.analyzer, "analyze", return_value="High CPU"),
            patch.object(manager.planner, "plan", return_value="Restart service"),
            patch.object(
                manager.executor, "execute", side_effect=publish_recovery_event
            ),
        ):
            manager.run_cycle({"cpu_percent": 95, "node_id": "raw-node-id"})

        recovery_events = bus.get_event_history(
            EventType.PIPELINE_STAGE_END,
            source_agent="recovery-action-executor",
            limit=10,
        )
        event = _latest_self_healing_event(bus, operation="execute")
        data = event.data
        event_text = str(data)

        assert len(recovery_events) == 1
        assert data["downstream_evidence"]["source_agents"] == [
            "recovery-action-executor"
        ]
        assert data["downstream_evidence"]["event_ids"] == [recovery_events[0].event_id]
        assert data["downstream_evidence"]["events_total"] == 1
        assert data["downstream_evidence"]["payloads_redacted"] is True
        assert "raw-node-id" not in event_text
        assert "10.0.0.1" not in event_text
        assert "restart private service" not in event_text

    def test_self_healing_mapek_trace_is_registered(self, tmp_path):
        bus = EventBus(project_root=str(tmp_path))
        manager = SelfHealingManager(event_bus=bus)

        manager.run_cycle({"cpu_percent": 10, "memory_percent": 20})
        trace = service_event_trace_history(
            bus,
            service_name="self-healing-mapek",
            event_type=EventType.PIPELINE_STAGE_END,
            limit=10,
        )

        assert trace["events_total"] == 1
        assert trace["filter"]["services"][0]["layer"] == (
            "self_healing_mapek_control_spine"
        )
        assert trace["events"][0]["source_agent"] == "self-healing-mapek"

    def test_feedback_loop_tracking(self):
        """Test that feedback loop statistics are tracked"""
        manager = SelfHealingManager()

        initial_updates = manager.feedback_updates

        # Run a cycle
        with (
            patch.object(manager.monitor, "check", return_value=True),
            patch.object(manager.analyzer, "analyze", return_value="High CPU"),
            patch.object(manager.planner, "plan", return_value="Restart service"),
            patch.object(manager.executor, "execute", return_value=True),
        ):

            manager.run_cycle({"cpu_percent": 95})

        # Feedback should be updated
        assert manager.feedback_updates > initial_updates

    def test_get_feedback_stats(self):
        """Test get_feedback_stats returns proper structure"""
        manager = SelfHealingManager()
        stats = manager.get_feedback_stats()

        required_keys = [
            "feedback_updates",
            "threshold_adjustments",
            "strategy_improvements",
            "knowledge_base_size",
            "successful_patterns",
            "failed_patterns",
        ]

        for key in required_keys:
            assert key in stats
            assert isinstance(stats[key], int)

    def test_threshold_manager_integration(self):
        """Test integration with threshold manager"""
        mock_threshold_manager = Mock()
        mock_threshold_manager.get_threshold.return_value = 80.0

        manager = SelfHealingManager(threshold_manager=mock_threshold_manager)

        # Threshold manager should be passed to monitor
        assert manager.threshold_manager is mock_threshold_manager
        assert manager.monitor.threshold_manager is mock_threshold_manager
