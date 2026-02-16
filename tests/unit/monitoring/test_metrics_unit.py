"""
Comprehensive unit tests for src/monitoring/metrics.py

Tests cover:
- MetricsRegistry class attributes (all metric types)
- get_metrics_registry() singleton behavior
- get_metrics() Prometheus exposition
- MetricsResponse wrapper
- Helper functions: record_self_healing_event, record_mttr, record_mape_k_cycle,
  update_mesh_peer_count, record_mesh_latency, set_node_health, set_node_uptime
- _get_singleton_metrics() internal function
- _initialize_module_level_metrics() references
- Legacy metric aliases
- MetricsMiddleware ASGI middleware
"""

import asyncio
import time
from unittest.mock import AsyncMock, MagicMock, patch

import pytest


class TestMetricsRegistry:
    """Tests for the MetricsRegistry class and its metric attributes."""

    def test_registry_is_class(self):
        from src.monitoring.metrics import MetricsRegistry
        assert isinstance(MetricsRegistry, type)

    def test_request_count_is_counter(self):
        from src.monitoring.metrics import MetricsRegistry
        from prometheus_client import Counter
        assert isinstance(MetricsRegistry.request_count, Counter)

    def test_request_duration_is_histogram(self):
        from src.monitoring.metrics import MetricsRegistry
        from prometheus_client import Histogram
        assert isinstance(MetricsRegistry.request_duration, Histogram)

    def test_db_connections_active_is_gauge(self):
        from src.monitoring.metrics import MetricsRegistry
        from prometheus_client import Gauge
        assert isinstance(MetricsRegistry.db_connections_active, Gauge)

    def test_mapek_cycle_duration_is_histogram(self):
        from src.monitoring.metrics import MetricsRegistry
        from prometheus_client import Histogram
        assert isinstance(MetricsRegistry.mapek_cycle_duration, Histogram)

    def test_mapek_cycles_total_is_counter(self):
        from src.monitoring.metrics import MetricsRegistry
        from prometheus_client import Counter
        assert isinstance(MetricsRegistry.mapek_cycles_total, Counter)

    def test_mapek_anomalies_detected_is_counter(self):
        from src.monitoring.metrics import MetricsRegistry
        from prometheus_client import Counter
        assert isinstance(MetricsRegistry.mapek_anomalies_detected, Counter)

    def test_mapek_recovery_actions_is_counter(self):
        from src.monitoring.metrics import MetricsRegistry
        from prometheus_client import Counter
        assert isinstance(MetricsRegistry.mapek_recovery_actions, Counter)

    def test_mapek_knowledge_base_size_is_gauge(self):
        from src.monitoring.metrics import MetricsRegistry
        from prometheus_client import Gauge
        assert isinstance(MetricsRegistry.mapek_knowledge_base_size, Gauge)

    def test_mapek_metrics_cache_size_is_gauge(self):
        from src.monitoring.metrics import MetricsRegistry
        from prometheus_client import Gauge
        assert isinstance(MetricsRegistry.mapek_metrics_cache_size, Gauge)

    def test_graphsage_inference_duration_is_histogram(self):
        from src.monitoring.metrics import MetricsRegistry
        from prometheus_client import Histogram
        assert isinstance(MetricsRegistry.graphsage_inference_duration, Histogram)

    def test_graphsage_predictions_total_is_counter(self):
        from src.monitoring.metrics import MetricsRegistry
        from prometheus_client import Counter
        assert isinstance(MetricsRegistry.graphsage_predictions_total, Counter)

    def test_graphsage_anomaly_score_is_gauge(self):
        from src.monitoring.metrics import MetricsRegistry
        from prometheus_client import Gauge
        assert isinstance(MetricsRegistry.graphsage_anomaly_score, Gauge)

    def test_graphsage_model_accuracy_is_gauge(self):
        from src.monitoring.metrics import MetricsRegistry
        from prometheus_client import Gauge
        assert isinstance(MetricsRegistry.graphsage_model_accuracy, Gauge)

    def test_graphsage_training_duration_is_histogram(self):
        from src.monitoring.metrics import MetricsRegistry
        from prometheus_client import Histogram
        assert isinstance(MetricsRegistry.graphsage_training_duration, Histogram)

    def test_graphsage_training_loss_is_gauge(self):
        from src.monitoring.metrics import MetricsRegistry
        from prometheus_client import Gauge
        assert isinstance(MetricsRegistry.graphsage_training_loss, Gauge)

    def test_rag_retrieval_duration_is_histogram(self):
        from src.monitoring.metrics import MetricsRegistry
        from prometheus_client import Histogram
        assert isinstance(MetricsRegistry.rag_retrieval_duration, Histogram)

    def test_rag_retrieval_results_is_counter(self):
        from src.monitoring.metrics import MetricsRegistry
        from prometheus_client import Counter
        assert isinstance(MetricsRegistry.rag_retrieval_results, Counter)

    def test_rag_vector_similarity_is_gauge(self):
        from src.monitoring.metrics import MetricsRegistry
        from prometheus_client import Gauge
        assert isinstance(MetricsRegistry.rag_vector_similarity, Gauge)

    def test_rag_index_size_is_gauge(self):
        from src.monitoring.metrics import MetricsRegistry
        from prometheus_client import Gauge
        assert isinstance(MetricsRegistry.rag_index_size, Gauge)

    def test_rag_generation_duration_is_histogram(self):
        from src.monitoring.metrics import MetricsRegistry
        from prometheus_client import Histogram
        assert isinstance(MetricsRegistry.rag_generation_duration, Histogram)

    def test_ledger_entries_total_is_counter(self):
        from src.monitoring.metrics import MetricsRegistry
        from prometheus_client import Counter
        assert isinstance(MetricsRegistry.ledger_entries_total, Counter)

    def test_ledger_chain_length_is_gauge(self):
        from src.monitoring.metrics import MetricsRegistry
        from prometheus_client import Gauge
        assert isinstance(MetricsRegistry.ledger_chain_length, Gauge)

    def test_ledger_sync_duration_is_histogram(self):
        from src.monitoring.metrics import MetricsRegistry
        from prometheus_client import Histogram
        assert isinstance(MetricsRegistry.ledger_sync_duration, Histogram)

    def test_ledger_consistency_failures_is_counter(self):
        from src.monitoring.metrics import MetricsRegistry
        from prometheus_client import Counter
        assert isinstance(MetricsRegistry.ledger_consistency_failures, Counter)

    def test_crdt_sync_operations_is_counter(self):
        from src.monitoring.metrics import MetricsRegistry
        from prometheus_client import Counter
        assert isinstance(MetricsRegistry.crdt_sync_operations, Counter)

    def test_crdt_sync_duration_is_histogram(self):
        from src.monitoring.metrics import MetricsRegistry
        from prometheus_client import Histogram
        assert isinstance(MetricsRegistry.crdt_sync_duration, Histogram)

    def test_crdt_state_size_is_gauge(self):
        from src.monitoring.metrics import MetricsRegistry
        from prometheus_client import Gauge
        assert isinstance(MetricsRegistry.crdt_state_size, Gauge)

    def test_raft_leader_changes_is_counter(self):
        from src.monitoring.metrics import MetricsRegistry
        from prometheus_client import Counter
        assert isinstance(MetricsRegistry.raft_leader_changes, Counter)

    def test_raft_log_replication_duration_is_histogram(self):
        from src.monitoring.metrics import MetricsRegistry
        from prometheus_client import Histogram
        assert isinstance(MetricsRegistry.raft_log_replication_duration, Histogram)

    def test_raft_followers_count_is_gauge(self):
        from src.monitoring.metrics import MetricsRegistry
        from prometheus_client import Gauge
        assert isinstance(MetricsRegistry.raft_followers_count, Gauge)

    def test_raft_term_gauge_is_gauge(self):
        from src.monitoring.metrics import MetricsRegistry
        from prometheus_client import Gauge
        assert isinstance(MetricsRegistry.raft_term_gauge, Gauge)

    def test_mesh_nodes_active_is_gauge(self):
        from src.monitoring.metrics import MetricsRegistry
        from prometheus_client import Gauge
        assert isinstance(MetricsRegistry.mesh_nodes_active, Gauge)

    def test_mesh_connections_total_is_counter(self):
        from src.monitoring.metrics import MetricsRegistry
        from prometheus_client import Counter
        assert isinstance(MetricsRegistry.mesh_connections_total, Counter)

    def test_mesh_packet_loss_ratio_is_gauge(self):
        from src.monitoring.metrics import MetricsRegistry
        from prometheus_client import Gauge
        assert isinstance(MetricsRegistry.mesh_packet_loss_ratio, Gauge)

    def test_mesh_hop_count_is_histogram(self):
        from src.monitoring.metrics import MetricsRegistry
        from prometheus_client import Histogram
        assert isinstance(MetricsRegistry.mesh_hop_count, Histogram)

    def test_mesh_bandwidth_bytes_is_counter(self):
        from src.monitoring.metrics import MetricsRegistry
        from prometheus_client import Counter
        assert isinstance(MetricsRegistry.mesh_bandwidth_bytes, Counter)

    def test_mesh_latency_is_histogram(self):
        from src.monitoring.metrics import MetricsRegistry
        from prometheus_client import Histogram
        assert isinstance(MetricsRegistry.mesh_latency, Histogram)

    def test_mesh_peers_count_is_gauge(self):
        from src.monitoring.metrics import MetricsRegistry
        from prometheus_client import Gauge
        assert isinstance(MetricsRegistry.mesh_peers_count, Gauge)

    def test_node_health_status_is_gauge(self):
        from src.monitoring.metrics import MetricsRegistry
        from prometheus_client import Gauge
        assert isinstance(MetricsRegistry.node_health_status, Gauge)

    def test_node_uptime_seconds_is_gauge(self):
        from src.monitoring.metrics import MetricsRegistry
        from prometheus_client import Gauge
        assert isinstance(MetricsRegistry.node_uptime_seconds, Gauge)

    def test_self_healing_mttr_seconds_is_histogram(self):
        from src.monitoring.metrics import MetricsRegistry
        from prometheus_client import Histogram
        assert isinstance(MetricsRegistry.self_healing_mttr_seconds, Histogram)

    def test_mtls_certificate_rotations_total_is_counter(self):
        from src.monitoring.metrics import MetricsRegistry
        from prometheus_client import Counter
        assert isinstance(MetricsRegistry.mtls_certificate_rotations_total, Counter)

    def test_mtls_certificate_expiry_seconds_is_gauge(self):
        from src.monitoring.metrics import MetricsRegistry
        from prometheus_client import Gauge
        assert isinstance(MetricsRegistry.mtls_certificate_expiry_seconds, Gauge)

    def test_mtls_certificate_age_seconds_is_gauge(self):
        from src.monitoring.metrics import MetricsRegistry
        from prometheus_client import Gauge
        assert isinstance(MetricsRegistry.mtls_certificate_age_seconds, Gauge)

    def test_mtls_validation_failures_is_counter(self):
        from src.monitoring.metrics import MetricsRegistry
        from prometheus_client import Counter
        assert isinstance(MetricsRegistry.mtls_validation_failures, Counter)

    def test_spiffe_svid_issuance_is_counter(self):
        from src.monitoring.metrics import MetricsRegistry
        from prometheus_client import Counter
        assert isinstance(MetricsRegistry.spiffe_svid_issuance, Counter)

    def test_spiffe_svid_renewal_is_counter(self):
        from src.monitoring.metrics import MetricsRegistry
        from prometheus_client import Counter
        assert isinstance(MetricsRegistry.spiffe_svid_renewal, Counter)

    def test_spire_server_latency_is_histogram(self):
        from src.monitoring.metrics import MetricsRegistry
        from prometheus_client import Histogram
        assert isinstance(MetricsRegistry.spire_server_latency, Histogram)

    def test_fl_round_duration_is_histogram(self):
        from src.monitoring.metrics import MetricsRegistry
        from prometheus_client import Histogram
        assert isinstance(MetricsRegistry.fl_round_duration, Histogram)

    def test_fl_global_model_loss_is_gauge(self):
        from src.monitoring.metrics import MetricsRegistry
        from prometheus_client import Gauge
        assert isinstance(MetricsRegistry.fl_global_model_loss, Gauge)

    def test_fl_local_updates_is_counter(self):
        from src.monitoring.metrics import MetricsRegistry
        from prometheus_client import Counter
        assert isinstance(MetricsRegistry.fl_local_updates, Counter)

    def test_fl_communication_bytes_is_counter(self):
        from src.monitoring.metrics import MetricsRegistry
        from prometheus_client import Counter
        assert isinstance(MetricsRegistry.fl_communication_bytes, Counter)

    def test_fl_participant_count_is_gauge(self):
        from src.monitoring.metrics import MetricsRegistry
        from prometheus_client import Gauge
        assert isinstance(MetricsRegistry.fl_participant_count, Gauge)

    def test_dao_proposals_total_is_counter(self):
        from src.monitoring.metrics import MetricsRegistry
        from prometheus_client import Counter
        assert isinstance(MetricsRegistry.dao_proposals_total, Counter)

    def test_dao_voting_power_is_gauge(self):
        from src.monitoring.metrics import MetricsRegistry
        from prometheus_client import Gauge
        assert isinstance(MetricsRegistry.dao_voting_power, Gauge)

    def test_dao_treasury_balance_is_gauge(self):
        from src.monitoring.metrics import MetricsRegistry
        from prometheus_client import Gauge
        assert isinstance(MetricsRegistry.dao_treasury_balance, Gauge)

    def test_dao_vote_participation_is_gauge(self):
        from src.monitoring.metrics import MetricsRegistry
        from prometheus_client import Gauge
        assert isinstance(MetricsRegistry.dao_vote_participation, Gauge)

    def test_contract_calls_total_is_counter(self):
        from src.monitoring.metrics import MetricsRegistry
        from prometheus_client import Counter
        assert isinstance(MetricsRegistry.contract_calls_total, Counter)

    def test_contract_execution_duration_is_histogram(self):
        from src.monitoring.metrics import MetricsRegistry
        from prometheus_client import Histogram
        assert isinstance(MetricsRegistry.contract_execution_duration, Histogram)

    def test_contract_gas_used_is_histogram(self):
        from src.monitoring.metrics import MetricsRegistry
        from prometheus_client import Histogram
        assert isinstance(MetricsRegistry.contract_gas_used, Histogram)

    def test_storage_operations_is_counter(self):
        from src.monitoring.metrics import MetricsRegistry
        from prometheus_client import Counter
        assert isinstance(MetricsRegistry.storage_operations, Counter)

    def test_storage_operation_duration_is_histogram(self):
        from src.monitoring.metrics import MetricsRegistry
        from prometheus_client import Histogram
        assert isinstance(MetricsRegistry.storage_operation_duration, Histogram)

    def test_storage_size_bytes_is_gauge(self):
        from src.monitoring.metrics import MetricsRegistry
        from prometheus_client import Gauge
        assert isinstance(MetricsRegistry.storage_size_bytes, Gauge)

    def test_memory_usage_bytes_is_gauge(self):
        from src.monitoring.metrics import MetricsRegistry
        from prometheus_client import Gauge
        assert isinstance(MetricsRegistry.memory_usage_bytes, Gauge)

    def test_cpu_usage_percent_is_gauge(self):
        from src.monitoring.metrics import MetricsRegistry
        from prometheus_client import Gauge
        assert isinstance(MetricsRegistry.cpu_usage_percent, Gauge)

    def test_goroutines_count_is_gauge(self):
        from src.monitoring.metrics import MetricsRegistry
        from prometheus_client import Gauge
        assert isinstance(MetricsRegistry.goroutines_count, Gauge)

    def test_gc_pause_duration_is_histogram(self):
        from src.monitoring.metrics import MetricsRegistry
        from prometheus_client import Histogram
        assert isinstance(MetricsRegistry.gc_pause_duration, Histogram)

    def test_threat_alerts_total_is_counter(self):
        from src.monitoring.metrics import MetricsRegistry
        from prometheus_client import Counter
        assert isinstance(MetricsRegistry.threat_alerts_total, Counter)

    def test_suspect_nodes_count_is_gauge(self):
        from src.monitoring.metrics import MetricsRegistry
        from prometheus_client import Gauge
        assert isinstance(MetricsRegistry.suspect_nodes_count, Gauge)

    def test_byzantine_detections_is_counter(self):
        from src.monitoring.metrics import MetricsRegistry
        from prometheus_client import Counter
        assert isinstance(MetricsRegistry.byzantine_detections, Counter)

    def test_operation_throughput_is_counter(self):
        from src.monitoring.metrics import MetricsRegistry
        from prometheus_client import Counter
        assert isinstance(MetricsRegistry.operation_throughput, Counter)

    def test_p99_latency_seconds_is_gauge(self):
        from src.monitoring.metrics import MetricsRegistry
        from prometheus_client import Gauge
        assert isinstance(MetricsRegistry.p99_latency_seconds, Gauge)

    def test_error_rate_is_gauge(self):
        from src.monitoring.metrics import MetricsRegistry
        from prometheus_client import Gauge
        assert isinstance(MetricsRegistry.error_rate, Gauge)

    def test_self_healing_events_is_counter(self):
        from src.monitoring.metrics import MetricsRegistry
        from prometheus_client import Counter
        assert isinstance(MetricsRegistry.self_healing_events, Counter)

    def test_instantiation(self):
        from src.monitoring.metrics import MetricsRegistry
        instance = MetricsRegistry()
        assert instance is not None


class TestLegacyMetricAliases:
    """Tests for the backward-compatible legacy metric aliases."""

    def test_legacy_aliases_exist(self):
        from src.monitoring.metrics import MetricsRegistry
        for i in range(1, 31):
            attr_name = f"legacy_metric_alias_{i}"
            assert hasattr(MetricsRegistry, attr_name), f"Missing {attr_name}"

    def test_legacy_aliases_point_to_request_count(self):
        from src.monitoring.metrics import MetricsRegistry
        for i in range(1, 31):
            attr_name = f"legacy_metric_alias_{i}"
            assert getattr(MetricsRegistry, attr_name) is MetricsRegistry.request_count

    def test_legacy_alias_31_does_not_exist(self):
        from src.monitoring.metrics import MetricsRegistry
        assert not hasattr(MetricsRegistry, "legacy_metric_alias_31")

    def test_legacy_alias_0_does_not_exist(self):
        from src.monitoring.metrics import MetricsRegistry
        assert not hasattr(MetricsRegistry, "legacy_metric_alias_0")


class TestGetMetricsRegistry:
    """Tests for the get_metrics_registry() singleton function."""

    def test_returns_metrics_registry_instance(self):
        from src.monitoring.metrics import MetricsRegistry, get_metrics_registry
        result = get_metrics_registry()
        assert isinstance(result, MetricsRegistry)

    def test_returns_singleton(self):
        from src.monitoring.metrics import get_metrics_registry
        r1 = get_metrics_registry()
        r2 = get_metrics_registry()
        assert r1 is r2

    def test_creates_instance_when_none(self):
        import src.monitoring.metrics as mod
        old = mod._metrics_registry_instance
        try:
            mod._metrics_registry_instance = None
            result = mod.get_metrics_registry()
            assert isinstance(result, mod.MetricsRegistry)
        finally:
            mod._metrics_registry_instance = old


class TestGetSingletonMetrics:
    """Tests for _get_singleton_metrics() internal function."""

    def test_returns_metrics_registry(self):
        from src.monitoring.metrics import MetricsRegistry, _get_singleton_metrics
        result = _get_singleton_metrics()
        assert isinstance(result, MetricsRegistry)

    def test_returns_same_as_get_metrics_registry(self):
        from src.monitoring.metrics import _get_singleton_metrics, get_metrics_registry
        assert _get_singleton_metrics() is get_metrics_registry()


class TestMetricsResponse:
    """Tests for the MetricsResponse wrapper class."""

    def test_body_stored(self):
        from src.monitoring.metrics import MetricsResponse
        body = b"some_metric 42\n"
        resp = MetricsResponse(body)
        assert resp.body == body

    def test_media_type(self):
        from src.monitoring.metrics import MetricsResponse
        resp = MetricsResponse(b"")
        assert resp.media_type == "text/plain; version=0.0.4; charset=utf-8"

    def test_empty_body(self):
        from src.monitoring.metrics import MetricsResponse
        resp = MetricsResponse(b"")
        assert resp.body == b""

    def test_large_body(self):
        from src.monitoring.metrics import MetricsResponse
        body = b"x" * 100000
        resp = MetricsResponse(body)
        assert len(resp.body) == 100000


class TestGetMetrics:
    """Tests for the get_metrics() function."""

    def test_returns_metrics_response(self):
        from src.monitoring.metrics import MetricsResponse, get_metrics
        result = get_metrics()
        assert isinstance(result, MetricsResponse)

    def test_body_is_bytes(self):
        from src.monitoring.metrics import get_metrics
        result = get_metrics()
        assert isinstance(result.body, bytes)

    def test_body_contains_metric_names(self):
        from src.monitoring.metrics import get_metrics
        result = get_metrics()
        body_str = result.body.decode("utf-8")
        # The registry should contain at least some of our defined metrics
        assert "x0tta6bl4" in body_str

    def test_media_type_is_prometheus_format(self):
        from src.monitoring.metrics import get_metrics
        result = get_metrics()
        assert "text/plain" in result.media_type
        assert "0.0.4" in result.media_type

    def test_uses_custom_registry(self):
        from src.monitoring.metrics import _metrics_registry, get_metrics
        with patch("src.monitoring.metrics.prometheus_client.generate_latest") as mock_gen:
            mock_gen.return_value = b"mocked"
            result = get_metrics()
            mock_gen.assert_called_once_with(_metrics_registry)
            assert result.body == b"mocked"


class TestRecordSelfHealingEvent:
    """Tests for the record_self_healing_event() helper."""

    def test_increments_counter(self):
        from src.monitoring.metrics import record_self_healing_event
        # Should not raise
        record_self_healing_event("restart", "node-1")

    def test_different_event_types(self):
        from src.monitoring.metrics import record_self_healing_event
        record_self_healing_event("isolate", "node-2")
        record_self_healing_event("scale", "node-3")
        record_self_healing_event("restart", "node-4")

    def test_uses_singleton_registry(self):
        from src.monitoring.metrics import record_self_healing_event
        with patch("src.monitoring.metrics.get_metrics_registry") as mock_get:
            mock_registry = MagicMock()
            mock_get.return_value = mock_registry
            record_self_healing_event("restart", "node-x")
            mock_registry.self_healing_events.labels.assert_called_once_with(
                event_type="restart", node_id="node-x"
            )
            mock_registry.self_healing_events.labels().inc.assert_called_once()


class TestRecordMttr:
    """Tests for the record_mttr() helper."""

    def test_records_duration(self):
        from src.monitoring.metrics import record_mttr
        record_mttr("restart", 5.5)

    def test_uses_singleton_registry(self):
        from src.monitoring.metrics import record_mttr
        with patch("src.monitoring.metrics.get_metrics_registry") as mock_get:
            mock_registry = MagicMock()
            mock_get.return_value = mock_registry
            record_mttr("scale", 2.3)
            mock_registry.self_healing_mttr_seconds.labels.assert_called_once_with(
                recovery_type="scale"
            )
            mock_registry.self_healing_mttr_seconds.labels().observe.assert_called_once_with(2.3)

    def test_handles_missing_attribute(self):
        from src.monitoring.metrics import record_mttr
        with patch("src.monitoring.metrics.get_metrics_registry") as mock_get:
            mock_registry = MagicMock(spec=[])
            mock_get.return_value = mock_registry
            # Should not raise, due to hasattr check
            record_mttr("restart", 1.0)

    def test_zero_duration(self):
        from src.monitoring.metrics import record_mttr
        record_mttr("restart", 0.0)

    def test_large_duration(self):
        from src.monitoring.metrics import record_mttr
        record_mttr("restart", 999999.99)


class TestRecordMapeKCycle:
    """Tests for the record_mape_k_cycle() helper."""

    def test_records_monitor_phase(self):
        from src.monitoring.metrics import record_mape_k_cycle
        record_mape_k_cycle("monitor", 0.1)

    def test_records_analyze_phase(self):
        from src.monitoring.metrics import record_mape_k_cycle
        record_mape_k_cycle("analyze", 0.05)

    def test_records_plan_phase(self):
        from src.monitoring.metrics import record_mape_k_cycle
        record_mape_k_cycle("plan", 0.02)

    def test_records_execute_phase(self):
        from src.monitoring.metrics import record_mape_k_cycle
        record_mape_k_cycle("execute", 0.5)

    def test_uses_singleton_registry(self):
        from src.monitoring.metrics import record_mape_k_cycle
        with patch("src.monitoring.metrics.get_metrics_registry") as mock_get:
            mock_registry = MagicMock()
            mock_get.return_value = mock_registry
            record_mape_k_cycle("monitor", 0.3)
            mock_registry.mapek_cycle_duration.labels.assert_called_once_with(phase="monitor")
            mock_registry.mapek_cycle_duration.labels().observe.assert_called_once_with(0.3)

    def test_handles_missing_attribute(self):
        from src.monitoring.metrics import record_mape_k_cycle
        with patch("src.monitoring.metrics.get_metrics_registry") as mock_get:
            mock_registry = MagicMock(spec=[])
            mock_get.return_value = mock_registry
            # Should not raise
            record_mape_k_cycle("monitor", 0.1)


class TestUpdateMeshPeerCount:
    """Tests for the update_mesh_peer_count() helper."""

    def test_updates_count(self):
        from src.monitoring.metrics import update_mesh_peer_count
        update_mesh_peer_count("node-1", 5)

    def test_uses_singleton_registry(self):
        from src.monitoring.metrics import update_mesh_peer_count
        with patch("src.monitoring.metrics.get_metrics_registry") as mock_get:
            mock_registry = MagicMock()
            mock_get.return_value = mock_registry
            update_mesh_peer_count("node-1", 10)
            mock_registry.mesh_peers_count.labels.assert_called_once_with(node_id="node-1")
            mock_registry.mesh_peers_count.labels().set.assert_called_once_with(10)

    def test_zero_count(self):
        from src.monitoring.metrics import update_mesh_peer_count
        update_mesh_peer_count("node-1", 0)

    def test_handles_missing_attribute(self):
        from src.monitoring.metrics import update_mesh_peer_count
        with patch("src.monitoring.metrics.get_metrics_registry") as mock_get:
            mock_registry = MagicMock(spec=[])
            mock_get.return_value = mock_registry
            update_mesh_peer_count("node-1", 5)


class TestRecordMeshLatency:
    """Tests for the record_mesh_latency() helper."""

    def test_records_latency(self):
        from src.monitoring.metrics import record_mesh_latency
        record_mesh_latency("node-1", "node-2", 0.05)

    def test_uses_singleton_registry(self):
        from src.monitoring.metrics import record_mesh_latency
        with patch("src.monitoring.metrics.get_metrics_registry") as mock_get:
            mock_registry = MagicMock()
            mock_get.return_value = mock_registry
            record_mesh_latency("a", "b", 0.1)
            mock_registry.mesh_latency.labels.assert_called_once_with(node_id="a", peer_id="b")
            mock_registry.mesh_latency.labels().observe.assert_called_once_with(0.1)

    def test_handles_missing_attribute(self):
        from src.monitoring.metrics import record_mesh_latency
        with patch("src.monitoring.metrics.get_metrics_registry") as mock_get:
            mock_registry = MagicMock(spec=[])
            mock_get.return_value = mock_registry
            record_mesh_latency("a", "b", 0.1)


class TestSetNodeHealth:
    """Tests for the set_node_health() helper."""

    def test_healthy_sets_1(self):
        from src.monitoring.metrics import set_node_health
        with patch("src.monitoring.metrics.get_metrics_registry") as mock_get:
            mock_registry = MagicMock()
            mock_get.return_value = mock_registry
            set_node_health("node-1", True)
            mock_registry.node_health_status.labels.assert_called_once_with(node_id="node-1")
            mock_registry.node_health_status.labels().set.assert_called_once_with(1)

    def test_unhealthy_sets_0(self):
        from src.monitoring.metrics import set_node_health
        with patch("src.monitoring.metrics.get_metrics_registry") as mock_get:
            mock_registry = MagicMock()
            mock_get.return_value = mock_registry
            set_node_health("node-2", False)
            mock_registry.node_health_status.labels().set.assert_called_once_with(0)

    def test_handles_missing_attribute(self):
        from src.monitoring.metrics import set_node_health
        with patch("src.monitoring.metrics.get_metrics_registry") as mock_get:
            mock_registry = MagicMock(spec=[])
            mock_get.return_value = mock_registry
            set_node_health("node-1", True)


class TestSetNodeUptime:
    """Tests for the set_node_uptime() helper."""

    def test_sets_uptime(self):
        from src.monitoring.metrics import set_node_uptime
        with patch("src.monitoring.metrics.get_metrics_registry") as mock_get:
            mock_registry = MagicMock()
            mock_get.return_value = mock_registry
            set_node_uptime("node-1", 3600.0)
            mock_registry.node_uptime_seconds.labels.assert_called_once_with(node_id="node-1")
            mock_registry.node_uptime_seconds.labels().set.assert_called_once_with(3600.0)

    def test_zero_uptime(self):
        from src.monitoring.metrics import set_node_uptime
        with patch("src.monitoring.metrics.get_metrics_registry") as mock_get:
            mock_registry = MagicMock()
            mock_get.return_value = mock_registry
            set_node_uptime("node-1", 0.0)
            mock_registry.node_uptime_seconds.labels().set.assert_called_once_with(0.0)

    def test_handles_missing_attribute(self):
        from src.monitoring.metrics import set_node_uptime
        with patch("src.monitoring.metrics.get_metrics_registry") as mock_get:
            mock_registry = MagicMock(spec=[])
            mock_get.return_value = mock_registry
            set_node_uptime("node-1", 100.0)


class TestModuleLevelMetrics:
    """Tests for module-level metric references initialized by _initialize_module_level_metrics."""

    def test_http_requests_total_initialized(self):
        import src.monitoring.metrics as mod
        assert mod.http_requests_total is not None

    def test_http_request_duration_seconds_initialized(self):
        import src.monitoring.metrics as mod
        assert mod.http_request_duration_seconds is not None

    def test_mesh_peers_count_module_level(self):
        import src.monitoring.metrics as mod
        assert mod.mesh_peers_count is not None

    def test_mesh_latency_seconds_module_level(self):
        import src.monitoring.metrics as mod
        assert mod.mesh_latency_seconds is not None

    def test_mape_k_cycle_duration_seconds_module_level(self):
        import src.monitoring.metrics as mod
        assert mod.mape_k_cycle_duration_seconds is not None

    def test_self_healing_events_total_module_level(self):
        import src.monitoring.metrics as mod
        assert mod.self_healing_events_total is not None

    def test_self_healing_mttr_seconds_module_level(self):
        import src.monitoring.metrics as mod
        assert mod.self_healing_mttr_seconds is not None

    def test_node_health_status_module_level(self):
        import src.monitoring.metrics as mod
        assert mod.node_health_status is not None

    def test_node_uptime_seconds_module_level(self):
        import src.monitoring.metrics as mod
        assert mod.node_uptime_seconds is not None

    def test_http_requests_total_is_request_count(self):
        import src.monitoring.metrics as mod
        registry = mod.get_metrics_registry()
        assert mod.http_requests_total is registry.request_count

    def test_http_request_duration_is_request_duration(self):
        import src.monitoring.metrics as mod
        registry = mod.get_metrics_registry()
        assert mod.http_request_duration_seconds is registry.request_duration

    def test_reinitialize_module_level_metrics(self):
        import src.monitoring.metrics as mod
        mod._initialize_module_level_metrics()
        assert mod.http_requests_total is not None
        assert mod.mesh_peers_count is not None


class TestCustomRegistry:
    """Tests for the custom Prometheus CollectorRegistry."""

    def test_custom_registry_exists(self):
        from src.monitoring.metrics import _metrics_registry
        import prometheus_client
        assert isinstance(_metrics_registry, prometheus_client.CollectorRegistry)

    def test_custom_registry_is_not_default(self):
        from src.monitoring.metrics import _metrics_registry
        import prometheus_client
        assert _metrics_registry is not prometheus_client.REGISTRY


class TestMetricsMiddleware:
    """Tests for the MetricsMiddleware ASGI middleware."""

    def test_init_stores_app(self):
        from src.monitoring.metrics import MetricsMiddleware
        mock_app = MagicMock()
        mw = MetricsMiddleware(mock_app)
        assert mw.app is mock_app

    @pytest.mark.asyncio
    async def test_non_http_passthrough(self):
        """Non-HTTP scopes should pass through without recording metrics."""
        from src.monitoring.metrics import MetricsMiddleware
        mock_app = AsyncMock()
        mw = MetricsMiddleware(mock_app)

        scope = {"type": "websocket"}
        receive = AsyncMock()
        send = AsyncMock()

        await mw(scope, receive, send)
        mock_app.assert_called_once_with(scope, receive, send)

    @pytest.mark.asyncio
    async def test_metrics_path_passthrough(self):
        """Requests to /metrics should pass through without recording."""
        from src.monitoring.metrics import MetricsMiddleware
        mock_app = AsyncMock()
        mw = MetricsMiddleware(mock_app)

        scope = {"type": "http", "method": "GET", "path": "/metrics"}
        receive = AsyncMock()
        send = AsyncMock()

        await mw(scope, receive, send)
        mock_app.assert_called_once_with(scope, receive, send)

    @pytest.mark.asyncio
    async def test_records_metrics_on_success(self):
        """Successful HTTP requests should record count and duration."""
        from src.monitoring.metrics import MetricsMiddleware

        async def fake_app(scope, receive, send):
            await send({"type": "http.response.start", "status": 200})
            await send({"type": "http.response.body", "body": b"ok"})

        mw = MetricsMiddleware(fake_app)
        scope = {"type": "http", "method": "GET", "path": "/api/health"}
        receive = AsyncMock()
        send = AsyncMock()

        with patch("src.monitoring.metrics._get_singleton_metrics") as mock_get:
            mock_registry = MagicMock()
            mock_get.return_value = mock_registry
            await mw(scope, receive, send)
            mock_registry.request_count.labels.assert_called_with(
                method="GET", endpoint="/api/health", status=200
            )
            mock_registry.request_count.labels().inc.assert_called()
            mock_registry.request_duration.labels.assert_called_with(
                method="GET", endpoint="/api/health"
            )
            mock_registry.request_duration.labels().observe.assert_called()

    @pytest.mark.asyncio
    async def test_records_metrics_on_exception(self):
        """Exceptions should still record metrics before re-raising."""
        from src.monitoring.metrics import MetricsMiddleware

        async def failing_app(scope, receive, send):
            raise ValueError("test error")

        mw = MetricsMiddleware(failing_app)
        scope = {"type": "http", "method": "POST", "path": "/api/data"}
        receive = AsyncMock()
        send = AsyncMock()

        with patch("src.monitoring.metrics._get_singleton_metrics") as mock_get:
            mock_registry = MagicMock()
            mock_get.return_value = mock_registry
            with pytest.raises(ValueError, match="test error"):
                await mw(scope, receive, send)
            # Metrics should still be recorded
            mock_registry.request_count.labels.assert_called_with(
                method="POST", endpoint="/api/data", status=500
            )
            mock_registry.request_count.labels().inc.assert_called()

    @pytest.mark.asyncio
    async def test_default_status_500_on_exception(self):
        """Default status should be 500 when no response start is sent."""
        from src.monitoring.metrics import MetricsMiddleware

        async def failing_app(scope, receive, send):
            raise RuntimeError("crash")

        mw = MetricsMiddleware(failing_app)
        scope = {"type": "http", "method": "GET", "path": "/crash"}
        receive = AsyncMock()
        send = AsyncMock()

        with patch("src.monitoring.metrics._get_singleton_metrics") as mock_get:
            mock_registry = MagicMock()
            mock_get.return_value = mock_registry
            with pytest.raises(RuntimeError):
                await mw(scope, receive, send)
            mock_registry.request_count.labels.assert_called_with(
                method="GET", endpoint="/crash", status=500
            )

    @pytest.mark.asyncio
    async def test_captures_status_from_response_start(self):
        """Status should be captured from http.response.start message."""
        from src.monitoring.metrics import MetricsMiddleware

        async def app_with_404(scope, receive, send):
            await send({"type": "http.response.start", "status": 404})
            await send({"type": "http.response.body", "body": b"not found"})

        mw = MetricsMiddleware(app_with_404)
        scope = {"type": "http", "method": "GET", "path": "/missing"}
        receive = AsyncMock()
        send = AsyncMock()

        with patch("src.monitoring.metrics._get_singleton_metrics") as mock_get:
            mock_registry = MagicMock()
            mock_get.return_value = mock_registry
            await mw(scope, receive, send)
            mock_registry.request_count.labels.assert_called_with(
                method="GET", endpoint="/missing", status=404
            )

    @pytest.mark.asyncio
    async def test_missing_method_uses_unknown(self):
        """Missing method in scope should default to 'unknown'."""
        from src.monitoring.metrics import MetricsMiddleware

        async def ok_app(scope, receive, send):
            await send({"type": "http.response.start", "status": 200})

        mw = MetricsMiddleware(ok_app)
        scope = {"type": "http", "path": "/test"}  # no 'method' key
        receive = AsyncMock()
        send = AsyncMock()

        with patch("src.monitoring.metrics._get_singleton_metrics") as mock_get:
            mock_registry = MagicMock()
            mock_get.return_value = mock_registry
            await mw(scope, receive, send)
            mock_registry.request_count.labels.assert_called_with(
                method="unknown", endpoint="/test", status=200
            )

    @pytest.mark.asyncio
    async def test_missing_path_uses_unknown(self):
        """Missing path in scope should default to 'unknown'."""
        from src.monitoring.metrics import MetricsMiddleware

        async def ok_app(scope, receive, send):
            await send({"type": "http.response.start", "status": 200})

        mw = MetricsMiddleware(ok_app)
        scope = {"type": "http", "method": "GET"}  # no 'path' key
        receive = AsyncMock()
        send = AsyncMock()

        with patch("src.monitoring.metrics._get_singleton_metrics") as mock_get:
            mock_registry = MagicMock()
            mock_get.return_value = mock_registry
            await mw(scope, receive, send)
            mock_registry.request_count.labels.assert_called_with(
                method="GET", endpoint="unknown", status=200
            )

    @pytest.mark.asyncio
    async def test_duration_is_positive(self):
        """Recorded duration should be a positive float."""
        from src.monitoring.metrics import MetricsMiddleware

        async def slow_app(scope, receive, send):
            await send({"type": "http.response.start", "status": 200})

        mw = MetricsMiddleware(slow_app)
        scope = {"type": "http", "method": "GET", "path": "/slow"}
        receive = AsyncMock()
        send = AsyncMock()

        with patch("src.monitoring.metrics._get_singleton_metrics") as mock_get:
            mock_registry = MagicMock()
            mock_get.return_value = mock_registry
            await mw(scope, receive, send)
            # Check observe was called with a positive number
            call_args = mock_registry.request_duration.labels().observe.call_args
            duration = call_args[0][0]
            assert duration >= 0

    @pytest.mark.asyncio
    async def test_send_wrapper_passes_non_response_start_messages(self):
        """Non http.response.start messages should pass through send."""
        from src.monitoring.metrics import MetricsMiddleware

        sent_messages = []

        async def capture_send(message):
            sent_messages.append(message)

        async def app_multi_messages(scope, receive, send):
            await send({"type": "http.response.start", "status": 200})
            await send({"type": "http.response.body", "body": b"hello"})

        mw = MetricsMiddleware(app_multi_messages)
        scope = {"type": "http", "method": "GET", "path": "/multi"}
        receive = AsyncMock()

        with patch("src.monitoring.metrics._get_singleton_metrics") as mock_get:
            mock_get.return_value = MagicMock()
            await mw(scope, receive, capture_send)

        assert len(sent_messages) == 2
        assert sent_messages[0]["type"] == "http.response.start"
        assert sent_messages[1]["type"] == "http.response.body"

    @pytest.mark.asyncio
    async def test_response_start_missing_status_defaults_500(self):
        """If http.response.start lacks status key, default should be 500."""
        from src.monitoring.metrics import MetricsMiddleware

        async def no_status_app(scope, receive, send):
            await send({"type": "http.response.start"})  # no status key

        mw = MetricsMiddleware(no_status_app)
        scope = {"type": "http", "method": "GET", "path": "/no-status"}
        receive = AsyncMock()
        send = AsyncMock()

        with patch("src.monitoring.metrics._get_singleton_metrics") as mock_get:
            mock_registry = MagicMock()
            mock_get.return_value = mock_registry
            await mw(scope, receive, send)
            mock_registry.request_count.labels.assert_called_with(
                method="GET", endpoint="/no-status", status=500
            )


class TestMetricLabels:
    """Tests to verify metric label configurations."""

    def test_request_count_labels(self):
        from src.monitoring.metrics import MetricsRegistry
        # Verify we can use the expected labels
        labeled = MetricsRegistry.request_count.labels(method="GET", endpoint="/test", status="200")
        assert labeled is not None

    def test_mapek_cycle_duration_labels(self):
        from src.monitoring.metrics import MetricsRegistry
        labeled = MetricsRegistry.mapek_cycle_duration.labels(phase="monitor")
        assert labeled is not None

    def test_mapek_anomalies_detected_labels(self):
        from src.monitoring.metrics import MetricsRegistry
        labeled = MetricsRegistry.mapek_anomalies_detected.labels(
            anomaly_type="cpu_usage", severity="high"
        )
        assert labeled is not None

    def test_mapek_recovery_actions_labels(self):
        from src.monitoring.metrics import MetricsRegistry
        labeled = MetricsRegistry.mapek_recovery_actions.labels(
            action_type="restart", status="success"
        )
        assert labeled is not None

    def test_mesh_latency_labels(self):
        from src.monitoring.metrics import MetricsRegistry
        labeled = MetricsRegistry.mesh_latency.labels(node_id="n1", peer_id="n2")
        assert labeled is not None

    def test_threat_alerts_labels(self):
        from src.monitoring.metrics import MetricsRegistry
        labeled = MetricsRegistry.threat_alerts_total.labels(
            threat_type="dos", severity="critical"
        )
        assert labeled is not None

    def test_contract_calls_labels(self):
        from src.monitoring.metrics import MetricsRegistry
        labeled = MetricsRegistry.contract_calls_total.labels(
            contract="token", function="transfer", status="success"
        )
        assert labeled is not None

    def test_storage_operations_labels(self):
        from src.monitoring.metrics import MetricsRegistry
        labeled = MetricsRegistry.storage_operations.labels(operation="get", status="success")
        assert labeled is not None

    def test_self_healing_events_labels(self):
        from src.monitoring.metrics import MetricsRegistry
        labeled = MetricsRegistry.self_healing_events.labels(
            event_type="restart", node_id="node-1"
        )
        assert labeled is not None

    def test_fl_local_updates_labels(self):
        from src.monitoring.metrics import MetricsRegistry
        labeled = MetricsRegistry.fl_local_updates.labels(node_id="node-1")
        assert labeled is not None

    def test_mtls_validation_failures_labels(self):
        from src.monitoring.metrics import MetricsRegistry
        labeled = MetricsRegistry.mtls_validation_failures.labels(failure_type="expiry")
        assert labeled is not None
