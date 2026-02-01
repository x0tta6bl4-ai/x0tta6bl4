"""
Comprehensive test suite for Proxy Metrics Collector.

Tests:
- Real-time aggregation pipelines
- Time-series storage with retention
- Performance analytics calculations
- Threshold-based alerting
"""
import pytest
import asyncio
import time
from unittest.mock import Mock, AsyncMock

from src.network.proxy_metrics_collector import (
    ProxyMetricsCollector,
    MetricSeries,
    MetricType,
    create_default_collector
)


class TestMetricSeries:
    """Test metric series functionality."""
    
    def test_add_value(self):
        """Test adding values to series."""
        series = MetricSeries(
            name="test_metric",
            metric_type=MetricType.COUNTER,
            description="Test metric"
        )
        
        series.add(100.0, {"label": "value"})
        
        assert len(series.values) == 1
        assert series.values[0].value == 100.0
        assert series.values[0].labels["label"] == "value"
    
    def test_retention_cleanup(self):
        """Test that old values are cleaned up."""
        series = MetricSeries(
            name="test_metric",
            metric_type=MetricType.COUNTER,
            description="Test metric",
            retention_seconds=1  # 1 second retention for testing
        )
        
        # Add old value
        series.add(100.0)
        series.values[0].timestamp = time.time() - 2  # 2 seconds ago
        
        # Add new value (should trigger cleanup)
        series.add(200.0)
        
        # Old value should be removed
        assert len(series.values) == 1
        assert series.values[0].value == 200.0
    
    def test_get_latest(self):
        """Test getting latest value."""
        series = MetricSeries(
            name="test_metric",
            metric_type=MetricType.GAUGE,
            description="Test metric"
        )
        
        assert series.get_latest() is None
        
        series.add(100.0)
        series.add(200.0)
        
        assert series.get_latest() == 200.0
    
    def test_get_average(self):
        """Test average calculation."""
        series = MetricSeries(
            name="test_metric",
            metric_type=MetricType.GAUGE,
            description="Test metric"
        )
        
        for i in range(10):
            series.add(float(i * 10))
        
        avg = series.get_average(window_seconds=300)
        assert avg == 45.0  # Average of 0, 10, 20, ..., 90
    
    def test_get_percentile(self):
        """Test percentile calculation."""
        series = MetricSeries(
            name="test_metric",
            metric_type=MetricType.HISTOGRAM,
            description="Test metric"
        )
        
        for i in range(100):
            series.add(float(i))
        
        p50 = series.get_percentile(50)
        p95 = series.get_percentile(95)
        p99 = series.get_percentile(99)
        
        assert p50 == 50
        assert p95 == 95
        assert p99 == 99
    
    def test_get_rate(self):
        """Test rate calculation for counters."""
        series = MetricSeries(
            name="test_counter",
            metric_type=MetricType.COUNTER,
            description="Test counter"
        )

        # Simulate counter increasing over time
        now = time.time()
        # Add first value (older)
        series.add(0.0)
        series.values[0].timestamp = now - 30  # 30 seconds ago (within 60s window)

        # Add second value (recent)
        series.add(30.0)
        series.values[1].timestamp = now

        # Rate should be (30 - 0) / 60 = 0.5 per second
        rate = series.get_rate(window_seconds=60)
        assert rate == 0.5  # 0.5 units per second over 60s window


class TestProxyMetricsCollector:
    """Test metrics collector functionality."""

    @pytest.fixture
    def collector(self):
        # Use create_default_collector to have all metrics pre-registered
        return create_default_collector()
    
    @pytest.mark.asyncio
    async def test_register_metric(self, collector):
        """Test metric registration."""
        collector.register_metric(
            "custom_metric",
            MetricType.GAUGE,
            "Custom test metric"
        )
        
        assert "custom_metric" in collector.metrics
        assert collector.metrics["custom_metric"].metric_type == MetricType.GAUGE
    
    @pytest.mark.asyncio
    async def test_record_metric(self, collector):
        """Test recording metric values."""
        collector.register_metric("test", MetricType.COUNTER, "Test")
        
        await collector.record("test", 100.0, {"proxy": "p1"})
        
        metric = collector.get_metric("test")
        assert metric.get_latest() == 100.0
    
    @pytest.mark.asyncio
    async def test_record_unknown_metric(self, collector):
        """Test recording to unknown metric logs warning."""
        # Should not raise, just log warning
        await collector.record("unknown", 100.0)
    
    @pytest.mark.asyncio
    async def test_record_proxy_request(self, collector):
        """Test recording proxy request."""
        await collector.record_proxy_request(
            proxy_id="proxy-1",
            success=True,
            latency_ms=100.0
        )
        
        # Should have recorded to multiple metrics
        total = collector.get_metric("proxy_requests_total")
        success = collector.get_metric("proxy_requests_success")
        latency = collector.get_metric("proxy_latency_ms")
        
        assert total.get_latest() == 1.0
        assert success.get_latest() == 1.0
        assert latency.get_latest() == 100.0
    
    @pytest.mark.asyncio
    async def test_record_proxy_request_failure(self, collector):
        """Test recording failed proxy request."""
        await collector.record_proxy_request(
            proxy_id="proxy-1",
            success=False,
            latency_ms=0.0
        )
        
        failed = collector.get_metric("proxy_requests_failed")
        assert failed.get_latest() == 1.0
    
    @pytest.mark.asyncio
    async def test_get_proxy_metrics(self, collector):
        """Test getting aggregated metrics for a proxy."""
        # Record some data
        for i in range(10):
            await collector.record_proxy_request(
                proxy_id="proxy-1",
                success=True,
                latency_ms=100.0 + i * 10
            )
        
        metrics = collector.get_proxy_metrics("proxy-1", window_seconds=300)
        
        assert metrics["proxy_id"] == "proxy-1"
        assert "metrics" in metrics
        assert "proxy_requests_total" in metrics["metrics"]
    
    @pytest.mark.asyncio
    async def test_get_global_metrics(self, collector):
        """Test getting global aggregated metrics."""
        # Record data for multiple proxies
        for i in range(10):
            await collector.record_proxy_request(
                proxy_id=f"proxy-{i % 3}",
                success=True,
                latency_ms=100.0
            )
        
        global_metrics = collector.get_global_metrics(window_seconds=300)
        
        assert "metrics" in global_metrics
        assert "proxy_requests_total" in global_metrics["metrics"]
        assert global_metrics["metrics"]["proxy_requests_total"]["count"] == 10
    
    @pytest.mark.asyncio
    async def test_alert_handler(self, collector):
        """Test alert handler registration and triggering."""
        handler = AsyncMock()
        collector.add_alert_handler(handler)

        # Record high failure rate to trigger alert
        for _ in range(20):
            await collector.record_proxy_request(
                proxy_id="proxy-1",
                success=False,
                latency_ms=3000.0  # High latency to trigger alert
            )

        # Manually trigger alert check (bypassing the 60s interval)
        await collector._check_alerts()

        # Handler should have been called for high latency alert
        assert handler.called
    
    def test_export_prometheus_format(self, collector):
        """Test Prometheus format export."""
        collector.register_metric("test_metric", MetricType.COUNTER, "Test")
        
        # Can't use async in non-async test, directly manipulate
        series = collector.metrics["test_metric"]
        series.add(100.0, {"proxy_id": "p1"})
        
        output = collector.export_prometheus_format()
        
        assert "# HELP test_metric Test" in output
        assert "# TYPE test_metric counter" in output
        assert 'proxy_id="p1"' in output
    
    def test_export_json(self, collector):
        """Test JSON export."""
        collector.register_metric("test_metric", MetricType.GAUGE, "Test")
        series = collector.metrics["test_metric"]
        series.add(100.0)
        
        data = collector.export_json()
        
        assert "timestamp" in data
        assert "metrics" in data
        assert "test_metric" in data["metrics"]


class TestDefaultCollector:
    """Test default collector factory."""
    
    def test_default_metrics_registered(self):
        """Test that default metrics are pre-registered."""
        collector = create_default_collector()
        
        expected_metrics = [
            "proxy_requests_total",
            "proxy_requests_success",
            "proxy_requests_failed",
            "proxy_latency_ms",
            "proxy_health_check"
        ]
        
        for metric in expected_metrics:
            assert metric in collector.metrics


class TestPerformance:
    """Performance and load tests."""
    
    @pytest.mark.asyncio
    async def test_high_throughput_recording(self):
        """Test high throughput metric recording."""
        collector = ProxyMetricsCollector()
        collector.register_metric("load_test", MetricType.COUNTER, "Load test")
        
        start = time.time()
        
        # Record 10000 metrics
        tasks = [
            collector.record("load_test", float(i))
            for i in range(10000)
        ]
        await asyncio.gather(*tasks)
        
        elapsed = time.time() - start
        
        metric = collector.get_metric("load_test")
        assert len(metric.values) == 10000
        assert elapsed < 5.0  # Should complete in under 5 seconds
    
    @pytest.mark.asyncio
    async def test_concurrent_access(self):
        """Test concurrent access to metrics."""
        collector = ProxyMetricsCollector()
        collector.register_metric("concurrent", MetricType.COUNTER, "Concurrent")
        
        async def writer(proxy_id: str, count: int):
            for i in range(count):
                await collector.record(
                    "concurrent",
                    float(i),
                    {"proxy_id": proxy_id}
                )
        
        # Run multiple concurrent writers
        await asyncio.gather(
            writer("proxy-1", 100),
            writer("proxy-2", 100),
            writer("proxy-3", 100)
        )
        
        metric = collector.get_metric("concurrent")
        assert len(metric.values) == 300


if __name__ == "__main__":
    pytest.main([__file__, "-v"])
