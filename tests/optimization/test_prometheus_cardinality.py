import pytest
from datetime import datetime, timedelta
from src.optimization.prometheus_cardinality_optimizer import (
    CardinalityMetric,
    CardinalityAlert,
    CardinalityLimiter,
    LabelAggregator,
    SamplingStrategy,
    CardinalityTracker,
    PrometheusCardinalityOptimizer,
    get_cardinality_optimizer,
)


class TestCardinalityMetric:
    def test_create_metric(self):
        metric = CardinalityMetric("test_metric")
        assert metric.metric_name == "test_metric"
        assert metric.current_cardinality == 0
        assert metric.recorded_samples == 0
    
    def test_record_sample(self):
        metric = CardinalityMetric("test_metric")
        metric.record_sample("label1=value1")
        assert metric.current_cardinality == 1
        assert metric.recorded_samples == 1
    
    def test_duplicate_samples(self):
        metric = CardinalityMetric("test_metric")
        metric.record_sample("label1=value1")
        metric.record_sample("label1=value1")
        assert metric.current_cardinality == 1
        assert metric.recorded_samples == 2
    
    def test_peak_cardinality_tracking(self):
        metric = CardinalityMetric("test_metric")
        for i in range(5):
            metric.record_sample(f"label1=value{i}")
        assert metric.peak_cardinality == 5
    
    def test_cardinality_growth_rate(self):
        metric = CardinalityMetric("test_metric")
        metric.record_sample("label1=value1")
        rate = metric.get_cardinality_growth_rate()
        assert rate >= 0


class TestCardinalityLimiter:
    def test_default_limit(self):
        limiter = CardinalityLimiter(5000)
        assert limiter.get_limit_for_metric("any_metric") == 5000
    
    def test_set_metric_limit(self):
        limiter = CardinalityLimiter()
        limiter.set_metric_limit("high_cardinality_metric", 1000)
        assert limiter.get_limit_for_metric("high_cardinality_metric") == 1000
    
    def test_set_label_limit(self):
        limiter = CardinalityLimiter()
        limiter.set_label_limit("metric1", "node_id", 100)
        assert limiter.get_label_limit("metric1", "node_id") == 100
    
    def test_is_within_limits_cardinality(self):
        limiter = CardinalityLimiter(default_limit=1000)
        assert limiter.is_within_limits("metric1", 500)
        assert not limiter.is_within_limits("metric1", 1001)
    
    def test_is_within_limits_with_label(self):
        limiter = CardinalityLimiter()
        limiter.set_label_limit("metric1", "node_id", 100)
        assert limiter.is_within_limits("metric1", 500, "node_id", 50)
        assert not limiter.is_within_limits("metric1", 500, "node_id", 101)


class TestLabelAggregator:
    def test_no_aggregation(self):
        agg = LabelAggregator()
        result = agg.aggregate_label("metric", "label", "value")
        assert result == "value"
    
    def test_explicit_aggregation(self):
        agg = LabelAggregator()
        agg.add_aggregation_rule("metric", "node_id", "node_001", "region_us")
        agg.add_aggregation_rule("metric", "node_id", "node_002", "region_us")
        assert agg.aggregate_label("metric", "node_id", "node_001") == "region_us"
        assert agg.aggregate_label("metric", "node_id", "node_002") == "region_us"
    
    def test_regex_aggregation(self):
        agg = LabelAggregator()
        agg.add_regex_rule("metric", "pod_name", r"pod_\d+_.*", "pod_generic")
        assert agg.aggregate_label("metric", "pod_name", "pod_123_app") == "pod_generic"
        assert agg.aggregate_label("metric", "pod_name", "pod_456_worker") == "pod_generic"
    
    def test_multiple_rules(self):
        agg = LabelAggregator()
        agg.add_regex_rule("metric", "path", r"^/api/v\d+/", "/api")
        result = agg.aggregate_label("metric", "path", "/api/v1/users")
        assert result.startswith("/api")


class TestSamplingStrategy:
    def test_full_sampling(self):
        sampler = SamplingStrategy()
        for _ in range(10):
            assert sampler.should_sample("metric1")
    
    def test_50_percent_sampling(self):
        sampler = SamplingStrategy()
        sampler.set_sampling_rate("metric1", 0.5)
        samples = sum(1 for _ in range(100) if sampler.should_sample("metric1"))
        assert 40 <= samples <= 60
    
    def test_sampling_rate_validation(self):
        sampler = SamplingStrategy()
        with pytest.raises(ValueError):
            sampler.set_sampling_rate("metric", 0.0)
        with pytest.raises(ValueError):
            sampler.set_sampling_rate("metric", 1.5)
    
    def test_different_metrics_independent(self):
        sampler = SamplingStrategy()
        sampler.set_sampling_rate("metric1", 0.5)
        m1_samples = sum(1 for _ in range(100) if sampler.should_sample("metric1"))
        m2_samples = sum(1 for _ in range(100) if sampler.should_sample("metric2"))
        assert m2_samples == 100


class TestCardinalityTracker:
    def test_record_simple_metric(self):
        tracker = CardinalityTracker()
        accepted = tracker.record_metric("test_metric", {"label1": "value1"})
        assert accepted
        assert tracker.get_metric_cardinality("test_metric") == 1
    
    def test_cardinality_growth(self):
        tracker = CardinalityTracker()
        for i in range(5):
            tracker.record_metric("test_metric", {"label1": f"value{i}"})
        assert tracker.get_metric_cardinality("test_metric") == 5
    
    def test_cardinality_limit_enforcement(self):
        tracker = CardinalityTracker()
        tracker.limiter.set_metric_limit("limited_metric", 3)
        
        for i in range(3):
            accepted = tracker.record_metric("limited_metric", {"label1": f"value{i}"})
            assert accepted
        
        accepted = tracker.record_metric("limited_metric", {"label1": "value3"})
        assert not accepted
    
    def test_label_aggregation_reduces_cardinality(self):
        tracker = CardinalityTracker()
        tracker.aggregator.add_aggregation_rule("metric", "node_id", "node_1", "region_a")
        tracker.aggregator.add_aggregation_rule("metric", "node_id", "node_2", "region_a")
        
        tracker.record_metric("metric", {"node_id": "node_1"})
        tracker.record_metric("metric", {"node_id": "node_2"})
        
        assert tracker.get_metric_cardinality("metric") == 1
    
    def test_max_metrics_limit(self):
        tracker = CardinalityTracker(max_metrics=2)
        
        assert tracker.record_metric("metric1", {"label": "value"})
        assert tracker.record_metric("metric2", {"label": "value"})
        assert not tracker.record_metric("metric3", {"label": "value"})
    
    def test_cardinality_report(self):
        tracker = CardinalityTracker()
        tracker.record_metric("metric1", {"label1": "value1"})
        tracker.record_metric("metric1", {"label1": "value2"})
        tracker.record_metric("metric2", {"label2": "value1"})
        
        report = tracker.get_cardinality_report()
        assert report["total_unique_metrics"] == 2
        assert report["total_cardinality"] == 3
        assert len(report["top_10_high_cardinality"]) == 2
    
    def test_sampling_reduces_cardinality(self):
        tracker = CardinalityTracker()
        tracker.sampler.set_sampling_rate("metric1", 0.1)
        
        for i in range(100):
            tracker.record_metric("metric1", {"label": "same"})
        
        cardinality = tracker.get_metric_cardinality("metric1")
        assert cardinality == 1


class TestPrometheusCardinalityOptimizer:
    def test_record_and_get_status(self):
        optimizer = PrometheusCardinalityOptimizer()
        optimizer.record_metric_sample("metric1", {"label": "value1"})
        
        status = optimizer.get_status()
        assert not status["aggressive_mode"]
        assert status["cardinality_report"]["total_unique_metrics"] == 1
    
    def test_configure_metric_limit(self):
        optimizer = PrometheusCardinalityOptimizer()
        optimizer.configure_metric_limit("metric1", 500)
        
        assert optimizer.tracker.limiter.get_limit_for_metric("metric1") == 500
    
    def test_configure_label_limit(self):
        optimizer = PrometheusCardinalityOptimizer()
        optimizer.configure_label_limit("metric1", "node_id", 50)
        
        assert optimizer.tracker.limiter.get_label_limit("metric1", "node_id") == 50
    
    def test_add_label_aggregation(self):
        optimizer = PrometheusCardinalityOptimizer()
        optimizer.add_label_aggregation("metric1", "node_id", "node_001", "us_west")
        
        agg = optimizer.tracker.aggregator
        assert agg.aggregate_label("metric1", "node_id", "node_001") == "us_west"
    
    def test_add_regex_aggregation(self):
        optimizer = PrometheusCardinalityOptimizer()
        optimizer.add_label_regex_aggregation("metric1", "path", r"^/api/.*", "/api")
        
        agg = optimizer.tracker.aggregator
        assert agg.aggregate_label("metric1", "path", "/api/users") == "/api"
    
    def test_aggressive_mode_activation(self):
        optimizer = PrometheusCardinalityOptimizer()
        optimizer.tracker.limiter.set_metric_limit("metric1", 2)
        
        optimizer.record_metric_sample("metric1", {"label": "value1"})
        optimizer.record_metric_sample("metric1", {"label": "value2"})
        optimizer.record_metric_sample("metric1", {"label": "value3"})
        
        assert optimizer.aggressive_mode
    
    def test_get_cardinality_report(self):
        optimizer = PrometheusCardinalityOptimizer()
        optimizer.record_metric_sample("metric1", {"label1": "value1"})
        optimizer.record_metric_sample("metric1", {"label1": "value2"})
        optimizer.record_metric_sample("metric2", {"label2": "value1"})
        
        report = optimizer.get_cardinality_report()
        assert report["total_unique_metrics"] == 2
        assert report["total_cardinality"] == 3


class TestCardinalityAlert:
    def test_create_alert(self):
        alert = CardinalityAlert(
            timestamp=datetime.utcnow(),
            metric_name="metric1",
            alert_type="high",
            current_cardinality=5000,
            threshold=1000,
            message="Test alert"
        )
        assert alert.metric_name == "metric1"
        assert alert.current_cardinality == 5000


class TestIntegration:
    def test_complete_cardinality_control_workflow(self):
        tracker = CardinalityTracker()
        
        tracker.limiter.set_metric_limit("requests", 5000)
        tracker.limiter.set_label_limit("requests", "endpoint", 100)
        
        tracker.aggregator.add_regex_rule(
            "requests", "endpoint", r"^/api/v\d+/", "/api"
        )
        
        for i in range(100):
            tracker.record_metric(
                "requests",
                {
                    "endpoint": f"/api/v1/endpoint_{i}",
                    "method": "GET",
                    "status": "200"
                }
            )
        
        report = tracker.get_cardinality_report()
        assert report["total_unique_metrics"] == 1
        assert 0 < report["total_cardinality"] <= 100
    
    def test_alert_generation_and_cleanup(self):
        tracker = CardinalityTracker()
        tracker.limiter.set_metric_limit("metric", 5)
        
        for i in range(10):
            tracker.record_metric("metric", {"label": f"value{i}"})
        
        initial_alerts = len(tracker.alerts)
        assert initial_alerts > 0
        
        tracker.cleanup_old_alerts(older_than_minutes=0)
        assert len(tracker.alerts) == 0
    
    def test_multiple_metrics_with_different_cardinalities(self):
        optimizer = PrometheusCardinalityOptimizer()
        
        for i in range(10):
            optimizer.record_metric_sample(f"metric_{i}", {"label": "value"})
        
        for i in range(5):
            for j in range(20):
                optimizer.record_metric_sample("high_cardinality", {"label": f"value_{j}"})
        
        report = optimizer.get_cardinality_report()
        assert report["total_unique_metrics"] == 11
        assert "high_cardinality" in [m["metric"] for m in report["top_10_high_cardinality"]]


if __name__ == "__main__":
    pytest.main([__file__, "-v"])
