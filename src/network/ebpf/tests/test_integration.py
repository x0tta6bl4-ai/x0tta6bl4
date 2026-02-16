"""
Integration tests for eBPF telemetry module.

Tests cover:
- Full workflow testing
- Component interaction
- End-to-end scenarios
- Error recovery
- Performance under load
"""

import time
from unittest.mock import MagicMock, Mock, patch

import pytest
from telemetry_module import (EBPFTelemetryCollector, EventSeverity,
                              MetricDefinition, MetricType, TelemetryConfig,
                              TelemetryEvent)


class TestIntegrationFullWorkflow:
    """Test full workflow of telemetry collection."""

    @pytest.fixture
    def collector(self, telemetry_config):
        return EBPFTelemetryCollector(telemetry_config)

    def test_full_workflow(self, collector, mock_bpf_program):
        """Test complete workflow from registration to export."""
        # Register program
        collector.register_program(mock_bpf_program, "test_program", ["map1", "map2"])

        # Collect metrics
        metrics = collector.collect_all_metrics()

        # Verify metrics
        assert isinstance(metrics, dict)
        assert "test_program" in metrics

        # Export to Prometheus
        collector.export_to_prometheus(metrics)

        # Verify export
        assert len(collector.prometheus.metrics) > 0

    def test_workflow_with_multiple_programs(self, collector):
        """Test workflow with multiple eBPF programs."""
        # Create multiple mock programs
        program1 = MagicMock()
        program2 = MagicMock()
        program3 = MagicMock()

        # Register all programs
        collector.register_program(program1, "program1", ["map1"])
        collector.register_program(program2, "program2", ["map2"])
        collector.register_program(program3, "program3", ["map3"])

        # Collect metrics
        metrics = collector.collect_all_metrics()

        # Verify all programs are represented
        assert "program1" in metrics
        assert "program2" in metrics
        assert "program3" in metrics

    def test_workflow_with_custom_metrics(self, collector):
        """Test workflow with custom metrics."""
        # Register custom metric
        collector.prometheus.register_metric(
            MetricDefinition(
                name="custom_metric", type=MetricType.GAUGE, description="Custom metric"
            )
        )

        # Set custom metric value
        collector.prometheus.set_metric("custom_metric", 42.0)

        # Collect and export
        metrics = collector.collect_all_metrics()
        collector.export_to_prometheus(metrics)

        # Verify custom metric is exported
        assert "custom_metric" in collector.prometheus.metrics


class TestIntegrationComponentInteraction:
    """Test interaction between components."""

    @pytest.fixture
    def collector(self, telemetry_config):
        return EBPFTelemetryCollector(telemetry_config)

    def test_map_reader_to_prometheus(self, collector, mock_bpf_program):
        """Test data flow from MapReader to PrometheusExporter."""
        # Register program
        collector.register_program(mock_bpf_program, "test_program", ["test_map"])

        # Collect metrics
        metrics = collector.collect_all_metrics()

        # Export to Prometheus
        collector.export_to_prometheus(metrics)

        # Verify data flow
        assert len(collector.prometheus.metrics) > 0

    def test_perf_buffer_to_prometheus(self, collector):
        """Test data flow from PerfBufferReader to PrometheusExporter."""

        # Register event handler that updates Prometheus
        def event_handler(event):
            collector.prometheus.increment_metric("events_total")

        collector.perf_reader.register_handler("test_event", event_handler)

        # Simulate event
        event = TelemetryEvent(
            event_type="test_event", timestamp_ns=1000000000, cpu_id=0, pid=1234
        )
        collector.perf_reader.event_queue.append(event)
        collector.perf_reader._process_events()

        # Verify metric was updated
        assert "events_total" in collector.prometheus.metrics

    def test_security_to_map_reader(self, collector, mock_bpf_program):
        """Test security validation in map reading."""
        # Register program
        collector.register_program(mock_bpf_program, "test_program", ["test_map"])

        # Collect metrics (security validation happens here)
        metrics = collector.collect_all_metrics()

        # Verify metrics are valid
        assert isinstance(metrics, dict)


class TestIntegrationErrorRecovery:
    """Test error recovery scenarios."""

    @pytest.fixture
    def collector(self, telemetry_config):
        return EBPFTelemetryCollector(telemetry_config)

    def test_bcc_unavailable_fallback(self, collector):
        """Test fallback when BCC is unavailable."""
        with patch("telemetry_module.BCC_AVAILABLE", False):
            with patch.object(collector.map_reader, "bpftool_available", True):
                # Register program
                mock_bpf = MagicMock()
                collector.register_program(mock_bpf, "test_program", ["test_map"])

                # Should not raise exception
                metrics = collector.collect_all_metrics()

                assert isinstance(metrics, dict)

    def test_map_read_failure_recovery(self, collector, mock_bpf_program):
        """Test recovery from map read failure."""
        # Mock map read to fail
        mock_bpf_program.__getitem__ = Mock(side_effect=Exception("Map read error"))

        # Register program
        collector.register_program(mock_bpf_program, "test_program", ["test_map"])

        # Collect metrics (should handle error gracefully)
        metrics = collector.collect_all_metrics()

        # Should return empty dict for failed program
        assert isinstance(metrics, dict)

    def test_prometheus_export_failure_recovery(self, collector):
        """Test recovery from Prometheus export failure."""
        # Mock Prometheus to fail
        collector.prometheus.set_metric = Mock(side_effect=Exception("Export error"))

        # Export metrics (should handle error gracefully)
        metrics = {"test_metric": 42.0}
        result = collector.export_to_prometheus(metrics)

        # Should handle gracefully
        assert isinstance(result, dict)


class TestIntegrationPerformance:
    """Test performance under load."""

    @pytest.fixture
    def collector(self, telemetry_config):
        config = TelemetryConfig(
            collection_interval=0.01,  # Very fast for testing
            batch_size=100,
            max_queue_size=1000,
            max_workers=4,
        )
        return EBPFTelemetryCollector(config)

    def test_high_throughput_collection(self, collector, mock_bpf_program):
        """Test collection under high throughput."""
        # Register program
        collector.register_program(mock_bpf_program, "test_program", ["test_map"])

        # Collect multiple times
        start_time = time.time()
        for _ in range(100):
            metrics = collector.collect_all_metrics()
            assert isinstance(metrics, dict)
        end_time = time.time()

        # Should complete in reasonable time
        duration = end_time - start_time
        assert duration < 10.0  # 100 collections in < 10 seconds

    def test_parallel_map_reading(self, collector, mock_bpf_program_with_maps):
        """Test parallel map reading performance."""
        # Register program with multiple maps
        collector.register_program(
            mock_bpf_program_with_maps,
            "test_program",
            ["map1", "map2", "map3", "map4", "map5"],
        )

        # Collect metrics (should read maps in parallel)
        start_time = time.time()
        metrics = collector.collect_all_metrics()
        end_time = time.time()

        # Should complete quickly
        duration = end_time - start_time
        assert duration < 1.0  # 5 maps in < 1 second

    def test_event_processing_performance(self, collector):
        """Test event processing performance."""
        # Register event handler
        handler = Mock()
        collector.perf_reader.register_handler("test_event", handler)

        # Add many events
        for i in range(1000):
            event = TelemetryEvent(
                event_type="test_event",
                timestamp_ns=1000000000 + i,
                cpu_id=i % 4,
                pid=1234 + i,
            )
            collector.perf_reader.event_queue.append(event)

        # Process events
        start_time = time.time()
        collector.perf_reader._process_events()
        end_time = time.time()

        # Should process quickly
        duration = end_time - start_time
        assert duration < 1.0  # 1000 events in < 1 second
        assert handler.call_count == 1000


class TestIntegrationLifecycle:
    """Test collector lifecycle."""

    @pytest.fixture
    def collector(self, telemetry_config):
        return EBPFTelemetryCollector(telemetry_config)

    def test_start_stop_lifecycle(self, collector, mock_bpf_program):
        """Test start and stop lifecycle."""
        # Register program
        collector.register_program(mock_bpf_program, "test_program", ["test_map"])

        # Start collector
        collector.start()

        # Verify started
        assert collector.stop_event.is_set() == False

        # Stop collector
        collector.stop()

        # Verify stopped
        assert collector.stop_event.is_set() == True

    def test_context_manager(self, telemetry_config, mock_bpf_program):
        """Test using collector as context manager."""
        with EBPFTelemetryCollector(telemetry_config) as collector:
            # Register program
            collector.register_program(mock_bpf_program, "test_program", ["test_map"])

            # Collect metrics
            metrics = collector.collect_all_metrics()

            assert isinstance(metrics, dict)

        # Collector should be stopped after context exit
        assert collector.stop_event.is_set() == True


class TestIntegrationStatistics:
    """Test statistics collection."""

    @pytest.fixture
    def collector(self, telemetry_config):
        return EBPFTelemetryCollector(telemetry_config)

    def test_collection_stats(self, collector, mock_bpf_program):
        """Test collection statistics."""
        # Register program
        collector.register_program(mock_bpf_program, "test_program", ["test_map"])

        # Collect metrics multiple times
        for _ in range(10):
            collector.collect_all_metrics()

        # Get stats
        stats = collector.get_stats()

        # Verify stats
        assert "collection" in stats
        assert stats["collection"]["total_collections"] == 10
        assert stats["collection"]["successful_collections"] >= 0

    def test_security_stats(self, collector):
        """Test security statistics."""
        # Get stats
        stats = collector.get_stats()

        # Verify security stats
        assert "security" in stats
        assert "validation_errors" in stats["security"]
        assert "sanitized_count" in stats["security"]

    def test_perf_reader_stats(self, collector):
        """Test perf reader statistics."""
        # Get stats
        stats = collector.get_stats()

        # Verify perf reader stats
        assert "perf_reader" in stats
        assert "events_received" in stats["perf_reader"]
        assert "events_processed" in stats["perf_reader"]


class TestIntegrationEdgeCases:
    """Test integration edge cases."""

    @pytest.fixture
    def collector(self, telemetry_config):
        return EBPFTelemetryCollector(telemetry_config)

    def test_empty_program_list(self, collector):
        """Test with no programs registered."""
        # Collect metrics with no programs
        metrics = collector.collect_all_metrics()

        # Should return empty dict
        assert isinstance(metrics, dict)
        assert len(metrics) == 0

    def test_program_with_no_maps(self, collector, mock_bpf_program):
        """Test program with no maps specified."""
        # Register program without maps
        collector.register_program(mock_bpf_program, "test_program", [])

        # Collect metrics
        metrics = collector.collect_all_metrics()

        # Should handle gracefully
        assert isinstance(metrics, dict)

    def test_duplicate_program_registration(self, collector, mock_bpf_program):
        """Test registering same program twice."""
        # Register program
        collector.register_program(mock_bpf_program, "test_program", ["map1"])

        # Register same program again
        collector.register_program(mock_bpf_program, "test_program", ["map2"])

        # Should handle gracefully
        assert "test_program" in collector.programs

    def test_large_metric_dataset(self, collector, mock_bpf_program):
        """Test with large metric dataset."""
        # Mock program with many maps
        mock_bpf_program.__getitem__ = Mock(return_value=MagicMock())

        # Register program with many maps
        map_names = [f"map{i}" for i in range(100)]
        collector.register_program(mock_bpf_program, "test_program", map_names)

        # Collect metrics
        metrics = collector.collect_all_metrics()

        # Should handle large dataset
        assert isinstance(metrics, dict)


class TestIntegrationRealWorldScenarios:
    """Test real-world scenarios."""

    @pytest.fixture
    def collector(self, telemetry_config):
        return EBPFTelemetryCollector(telemetry_config)

    def test_performance_monitoring_scenario(
        self, collector, mock_bpf_program_with_maps
    ):
        """Test performance monitoring scenario."""
        # Register performance monitor
        collector.register_program(
            mock_bpf_program_with_maps,
            "performance_monitor",
            ["process_map", "system_metrics_map"],
        )

        # Collect metrics
        metrics = collector.collect_all_metrics()

        # Verify performance metrics
        assert "performance_monitor" in metrics
        perf_metrics = metrics["performance_monitor"]
        assert isinstance(perf_metrics, dict)

    def test_network_monitoring_scenario(self, collector, mock_bpf_program_with_maps):
        """Test network monitoring scenario."""
        # Register network monitor
        collector.register_program(
            mock_bpf_program_with_maps,
            "network_monitor",
            ["connection_map", "system_network_map"],
        )

        # Collect metrics
        metrics = collector.collect_all_metrics()

        # Verify network metrics
        assert "network_monitor" in metrics
        net_metrics = metrics["network_monitor"]
        assert isinstance(net_metrics, dict)

    def test_security_monitoring_scenario(self, collector, mock_bpf_program_with_maps):
        """Test security monitoring scenario."""
        # Register security monitor
        collector.register_program(
            mock_bpf_program_with_maps,
            "security_monitor",
            ["connections", "system_security_map"],
        )

        # Collect metrics
        metrics = collector.collect_all_metrics()

        # Verify security metrics
        assert "security_monitor" in metrics
        sec_metrics = metrics["security_monitor"]
        assert isinstance(sec_metrics, dict)

    def test_combined_monitoring_scenario(self, collector):
        """Test combined monitoring scenario."""
        # Create mock programs
        perf_program = MagicMock()
        net_program = MagicMock()
        sec_program = MagicMock()

        # Register all programs
        collector.register_program(perf_program, "performance_monitor", ["perf_map"])
        collector.register_program(net_program, "network_monitor", ["net_map"])
        collector.register_program(sec_program, "security_monitor", ["sec_map"])

        # Collect metrics
        metrics = collector.collect_all_metrics()

        # Verify all programs
        assert "performance_monitor" in metrics
        assert "network_monitor" in metrics
        assert "security_monitor" in metrics

        # Export all metrics
        collector.export_to_prometheus(metrics)

        # Verify export
        assert len(collector.prometheus.metrics) > 0
