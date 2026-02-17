"""
Tests for refactored Telemetry Module components.
"""
import pytest
from unittest.mock import MagicMock, patch

from src.network.ebpf.telemetry import (
    MetricType,
    MapType,
    EventSeverity,
    TelemetryConfig,
    MetricDefinition,
    TelemetryEvent,
    CollectionStats,
    SecurityManager,
    MapReader,
    PerfBufferReader,
    PrometheusExporter,
    EBPFTelemetryCollector,
    create_collector,
)


class TestTelemetryModels:
    """Tests for telemetry data models."""
    
    def test_telemetry_config_defaults(self):
        """Test TelemetryConfig default values."""
        config = TelemetryConfig()
        
        assert config.collection_interval == 1.0
        assert config.batch_size == 100
        assert config.max_queue_size == 10000
        assert config.prometheus_port == 9090
        assert config.enable_validation is True
    
    def test_metric_definition(self):
        """Test MetricDefinition creation."""
        definition = MetricDefinition(
            name="test_metric",
            type=MetricType.COUNTER,
            description="Test metric",
            labels=["label1", "label2"]
        )
        
        assert definition.name == "test_metric"
        assert definition.type == MetricType.COUNTER
        assert len(definition.labels) == 2
    
    def test_telemetry_event(self):
        """Test TelemetryEvent creation."""
        event = TelemetryEvent(
            event_type="test_event",
            timestamp_ns=1234567890,
            cpu_id=0,
            pid=1234,
            data={"key": "value"},
            severity=EventSeverity.INFO
        )
        
        assert event.event_type == "test_event"
        assert event.cpu_id == 0
        assert event.severity == EventSeverity.INFO
    
    def test_collection_stats(self):
        """Test CollectionStats."""
        stats = CollectionStats()
        
        assert stats.total_collections == 0
        assert stats.successful_collections == 0
        
        # Test to_dict
        stats_dict = stats.to_dict()
        assert "total_collections" in stats_dict
        assert "collection_times" in stats_dict


class TestSecurityManager:
    """Tests for SecurityManager component."""
    
    def test_validate_metric_name_valid(self):
        """Test valid metric name validation."""
        config = TelemetryConfig()
        security = SecurityManager(config)
        
        is_valid, error = security.validate_metric_name("valid_metric_name")
        assert is_valid is True
        assert error is None
    
    def test_validate_metric_name_empty(self):
        """Test empty metric name validation."""
        config = TelemetryConfig()
        security = SecurityManager(config)
        
        is_valid, error = security.validate_metric_name("")
        assert is_valid is False
        assert "empty" in error.lower()
    
    def test_validate_metric_name_too_long(self):
        """Test too long metric name validation."""
        config = TelemetryConfig()
        security = SecurityManager(config)
        
        long_name = "a" * 201
        is_valid, error = security.validate_metric_name(long_name)
        assert is_valid is False
        assert "long" in error.lower()
    
    def test_validate_metric_value_valid(self):
        """Test valid metric value validation."""
        config = TelemetryConfig()
        security = SecurityManager(config)
        
        is_valid, error = security.validate_metric_value(42.0)
        assert is_valid is True
        assert error is None
        
        is_valid, error = security.validate_metric_value(100)
        assert is_valid is True
    
    def test_validate_metric_value_nan(self):
        """Test NaN metric value validation."""
        config = TelemetryConfig()
        security = SecurityManager(config)
        
        is_valid, error = security.validate_metric_value(float('nan'))
        assert is_valid is False
        assert "nan" in error.lower()
    
    def test_sanitize_string(self):
        """Test string sanitization."""
        config = TelemetryConfig()
        security = SecurityManager(config)
        
        # Test null byte removal
        result = security.sanitize_string("test\x00string")
        assert "\x00" not in result
        
        # Test length limit
        long_string = "a" * 2000
        result = security.sanitize_string(long_string)
        assert len(result) == 1000
    
    def test_sanitize_path(self):
        """Test path sanitization."""
        config = TelemetryConfig(sanitize_paths=True)
        security = SecurityManager(config)
        
        # Test path traversal prevention
        result = security.sanitize_path("../../../etc/passwd")
        assert ".." not in result
        assert "passwd" in result
    
    def test_validate_event(self):
        """Test event validation."""
        config = TelemetryConfig()
        security = SecurityManager(config)
        
        event = TelemetryEvent(
            event_type="test",
            timestamp_ns=1234567890,
            cpu_id=0,
            pid=1,
            severity=EventSeverity.INFO
        )
        
        is_valid, error = security.validate_event(event)
        assert is_valid is True


class TestMapReader:
    """Tests for MapReader component."""
    
    def test_init(self):
        """Test MapReader initialization."""
        config = TelemetryConfig()
        security = SecurityManager(config)
        reader = MapReader(config, security)
        
        assert reader.config == config
        assert reader.cache_ttl == 0.5
    
    def test_clear_cache(self):
        """Test cache clearing."""
        config = TelemetryConfig()
        security = SecurityManager(config)
        reader = MapReader(config, security)
        
        reader.cache["test"] = (0.0, {"data": "value"})
        reader.clear_cache()
        
        assert len(reader.cache) == 0


class TestPerfBufferReader:
    """Tests for PerfBufferReader component."""
    
    def test_init(self):
        """Test PerfBufferReader initialization."""
        config = TelemetryConfig()
        security = SecurityManager(config)
        reader = PerfBufferReader(config, security)
        
        assert reader.running is False
        assert "events_received" in reader.stats
    
    def test_register_handler(self):
        """Test handler registration."""
        config = TelemetryConfig()
        security = SecurityManager(config)
        reader = PerfBufferReader(config, security)
        
        def handler(event):
            pass
        
        reader.register_handler("test_event", handler)
        
        assert "test_event" in reader.event_handlers
        assert len(reader.event_handlers["test_event"]) == 1
    
    def test_get_stats(self):
        """Test stats retrieval."""
        config = TelemetryConfig()
        security = SecurityManager(config)
        reader = PerfBufferReader(config, security)
        
        stats = reader.get_stats()
        
        assert "events_received" in stats
        assert "events_processed" in stats
        assert "events_dropped" in stats


class TestPrometheusExporter:
    """Tests for PrometheusExporter component."""
    
    def test_init(self):
        """Test PrometheusExporter initialization."""
        config = TelemetryConfig()
        security = SecurityManager(config)
        exporter = PrometheusExporter(config, security)
        
        assert exporter.config == config
        assert len(exporter.metrics) == 0
    
    def test_register_metric(self):
        """Test metric registration."""
        config = TelemetryConfig()
        security = SecurityManager(config)
        exporter = PrometheusExporter(config, security)
        
        definition = MetricDefinition(
            name="test_counter",
            type=MetricType.COUNTER,
            description="Test counter"
        )
        
        exporter.register_metric(definition)
        
        # Should be registered if Prometheus is available
        # If not available, metrics dict will be empty
        assert "test_counter" in exporter.metric_definitions
    
    def test_get_metrics_text_without_prometheus(self):
        """Test metrics text generation without Prometheus."""
        config = TelemetryConfig()
        security = SecurityManager(config)
        exporter = PrometheusExporter(config, security)
        
        text = exporter.get_metrics_text()
        
        # Should return something even without Prometheus
        assert isinstance(text, str)


class TestEBPFTelemetryCollector:
    """Tests for EBPFTelemetryCollector main class."""
    
    def test_init(self):
        """Test collector initialization."""
        collector = EBPFTelemetryCollector()
        
        assert collector.config is not None
        assert collector.security is not None
        assert collector.map_reader is not None
        assert collector.perf_reader is not None
        assert collector.prometheus is not None
    
    def test_init_with_config(self):
        """Test collector initialization with custom config."""
        config = TelemetryConfig(
            prometheus_port=9091,
            collection_interval=5.0
        )
        collector = EBPFTelemetryCollector(config)
        
        assert collector.config.prometheus_port == 9091
        assert collector.config.collection_interval == 5.0
    
    def test_register_program(self):
        """Test program registration."""
        collector = EBPFTelemetryCollector()
        
        collector.register_program(
            bpf_program=MagicMock(),
            program_name="test_program",
            map_names=["map1", "map2"]
        )
        
        assert "test_program" in collector.programs
        assert len(collector.program_maps["test_program"]) == 2
    
    def test_register_map(self):
        """Test map registration."""
        collector = EBPFTelemetryCollector()
        collector.programs["test_program"] = MagicMock()
        collector.program_maps["test_program"] = []
        
        collector.register_map("test_program", "new_map")
        
        assert "new_map" in collector.program_maps["test_program"]
    
    def test_get_stats(self):
        """Test stats retrieval."""
        collector = EBPFTelemetryCollector()
        
        stats = collector.get_stats()
        
        assert "collection" in stats
        assert "security" in stats
        assert "perf_reader" in stats
        assert "programs" in stats
    
    def test_context_manager(self):
        """Test context manager usage."""
        with EBPFTelemetryCollector() as collector:
            assert collector is not None
            # Collector should be started


class TestConvenienceFunctions:
    """Tests for convenience functions."""
    
    def test_create_collector(self):
        """Test create_collector function."""
        collector = create_collector(
            prometheus_port=9092,
            collection_interval=2.0
        )
        
        assert collector.config.prometheus_port == 9092
        assert collector.config.collection_interval == 2.0
    
    def test_quick_start(self):
        """Test quick_start function."""
        mock_program = MagicMock()
        
        collector = quick_start(
            bpf_program=mock_program,
            program_name="test",
            prometheus_port=9093
        )
        
        assert "test" in collector.programs
        assert collector.config.prometheus_port == 9093


class TestBackwardCompatibility:
    """Test backward compatibility with old imports."""
    
    def test_import_from_old_path(self):
        """Test that old import path still works."""
        # This should work because we re-export in __init__.py
        from src.network.ebpf.telemetry import EBPFTelemetryCollector as Collector
        from src.network.ebpf.telemetry import TelemetryConfig as Config
        
        assert Collector is EBPFTelemetryCollector
        assert Config is TelemetryConfig


if __name__ == "__main__":
    pytest.main([__file__, "-v"])