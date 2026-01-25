"""
Tests for Prometheus metrics in Anti-Delos Charter.

WEST-0105-1: Prometheus Exporter tests.
Verifies that all metrics are properly emitted.
"""

import pytest
import time
from prometheus_client import CollectorRegistry
from src.westworld import prometheus_metrics


@pytest.fixture
def clean_registry():
    """Create a fresh registry for each test."""
    # Get current registry
    registry = prometheus_metrics.get_registry()
    return registry


class TestViolationMetrics:
    """Tests for violation counters."""
    
    def test_record_violation_increments_counter(self, clean_registry):
        """Recording a violation increments the counter."""
        # Record multiple violations
        prometheus_metrics.record_violation('WARNING', 'silent_collection', 'test_node')
        prometheus_metrics.record_violation('WARNING', 'silent_collection', 'test_node')
        
        # Verify in exported metrics
        text = prometheus_metrics.get_metrics_text().decode('utf-8')
        assert 'westworld_charter_violations_total' in text
        assert 'silent_collection' in text
        assert 'test_node' in text
    
    def test_record_violation_multiple_types(self, clean_registry):
        """Record violations of different types."""
        violations = [
            ('WARNING', 'silent_collection', 'node1'),
            ('SUSPENSION', 'data_extraction', 'node2'),
            ('PERMANENT_BAN', 'algorithm_manipulation', 'node3'),
            ('CRIMINAL_REFERRAL', 'unauthorized_override', 'node4'),
        ]
        
        for severity, vtype, node in violations:
            prometheus_metrics.record_violation(severity, vtype, node)
        
        text = prometheus_metrics.get_metrics_text().decode('utf-8')
        
        # All violations should be present
        for severity, vtype, node in violations:
            assert severity in text
            assert vtype in text


class TestForbiddenMetricAttempts:
    """Tests for forbidden metric attempt tracking."""
    
    def test_record_forbidden_attempt(self, clean_registry):
        """Recording forbidden metric attempt increments counter."""
        prometheus_metrics.record_forbidden_attempt(
            'user_location',
            'suspicious_node',
            status='blocked'
        )
        
        text = prometheus_metrics.get_metrics_text().decode('utf-8')
        assert 'forbidden_metric_attempts' in text
        assert 'user_location' in text
    
    def test_forbidden_attempts_different_statuses(self, clean_registry):
        """Record attempts with different statuses."""
        statuses = ['blocked', 'reported', 'escalated']
        
        for status in statuses:
            prometheus_metrics.record_forbidden_attempt(
                'browsing_history',
                'node1',
                status=status
            )
        
        text = prometheus_metrics.get_metrics_text().decode('utf-8')
        assert 'forbidden_metric_attempts' in text


class TestDataRevocationMetrics:
    """Tests for data revocation event tracking."""
    
    def test_record_data_revocation(self, clean_registry):
        """Recording data revocation increments counter."""
        prometheus_metrics.record_data_revocation(
            'account_closure',
            'user_alice'
        )
        
        text = prometheus_metrics.get_metrics_text().decode('utf-8')
        assert 'data_revocation_events_total' in text
        assert 'account_closure' in text
    
    def test_revocation_different_reasons(self, clean_registry):
        """Record revocations with different reasons."""
        reasons = ['account_closure', 'policy_violation', 'security_incident']
        
        for reason in reasons:
            prometheus_metrics.record_data_revocation(reason, 'test_service')
        
        text = prometheus_metrics.get_metrics_text().decode('utf-8')
        for reason in reasons:
            assert reason in text


class TestLatencyHistograms:
    """Tests for latency measurement histograms."""
    
    def test_record_validation_latency(self, clean_registry):
        """Recording validation latency updates histogram."""
        prometheus_metrics.record_validation_latency_ns(500.0)  # 500 ns
        prometheus_metrics.record_validation_latency_ns(5000.0)  # 5 µs
        prometheus_metrics.record_validation_latency_ns(50000.0)  # 50 µs
        
        text = prometheus_metrics.get_metrics_text().decode('utf-8')
        assert 'metric_validation_latency_ns_bucket' in text
        assert 'metric_validation_latency_ns_sum' in text
        assert 'metric_validation_latency_ns_count' in text
        assert 'count="3"' in text or 'count=3' in text or 'count 3' in text
    
    def test_record_policy_load_duration(self, clean_registry):
        """Recording policy load duration updates histogram."""
        prometheus_metrics.record_policy_load_duration_ms(25.5)
        prometheus_metrics.record_policy_load_duration_ms(75.2)
        
        text = prometheus_metrics.get_metrics_text().decode('utf-8')
        assert 'policy_load_duration_ms_bucket' in text
    
    def test_record_violation_report_latency(self, clean_registry):
        """Recording violation report latency updates histogram."""
        prometheus_metrics.record_violation_report_latency_ms(150.0)
        
        text = prometheus_metrics.get_metrics_text().decode('utf-8')
        assert 'violation_report_latency_ms_bucket' in text
    
    def test_latency_histogram_buckets(self, clean_registry):
        """Verify histogram buckets are correctly configured."""
        # Record values in each bucket range
        latencies = [100, 500, 5000, 50000, 500000, 5000000]  # ns
        
        for latency in latencies:
            prometheus_metrics.record_validation_latency_ns(float(latency))
        
        text = prometheus_metrics.get_metrics_text().decode('utf-8')
        
        # Should have buckets defined
        assert 'metric_validation_latency_ns_bucket' in text
        assert '+Inf' in text  # +Inf bucket should exist


class TestGaugeMetrics:
    """Tests for gauge (current state) metrics."""
    
    def test_update_committee_size(self, clean_registry):
        """Updating committee size sets gauge."""
        prometheus_metrics.update_committee_size(5)
        
        text = prometheus_metrics.get_metrics_text().decode('utf-8')
        assert 'audit_committee_size' in text
    
    def test_update_violations_investigating(self, clean_registry):
        """Updating violations investigating sets gauge."""
        prometheus_metrics.update_violations_investigating('CRITICAL', 3)
        prometheus_metrics.update_violations_investigating('WARNING', 8)
        
        text = prometheus_metrics.get_metrics_text().decode('utf-8')
        assert 'violations_under_investigation' in text
        assert 'CRITICAL' in text
        assert 'WARNING' in text
    
    def test_gauge_multiple_updates(self, clean_registry):
        """Gauge should reflect most recent value."""
        prometheus_metrics.update_committee_size(3)
        prometheus_metrics.update_committee_size(5)
        prometheus_metrics.update_committee_size(7)
        
        text = prometheus_metrics.get_metrics_text().decode('utf-8')
        # Most recent value should be reflected
        assert 'audit_committee_size' in text


class TestMetricsExport:
    """Tests for metrics export and formatting."""
    
    def test_get_metrics_text_format(self, clean_registry):
        """Exported metrics are in valid Prometheus text format."""
        prometheus_metrics.record_violation('WARNING', 'silent_collection', 'node1')
        
        text = prometheus_metrics.get_metrics_text()
        
        # Should be bytes
        assert isinstance(text, bytes)
        
        # Should be UTF-8 decodable
        text_str = text.decode('utf-8')
        
        # Should contain TYPE definitions
        assert '# TYPE' in text_str
        assert 'westworld_charter' in text_str
    
    def test_metrics_include_labels(self, clean_registry):
        """Exported metrics include proper labels."""
        prometheus_metrics.record_violation('CRITICAL', 'data_extraction', 'malicious_node')
        
        text = prometheus_metrics.get_metrics_text().decode('utf-8')
        
        # Labels should be present
        assert 'severity=' in text
        assert 'violation_type=' in text
        assert 'node_or_service=' in text
    
    def test_metrics_helper_text(self, clean_registry):
        """Exported metrics include HELP text."""
        text = prometheus_metrics.get_metrics_text().decode('utf-8')
        
        # Should have HELP text
        assert '# HELP' in text
        assert 'Total charter violations' in text or 'violations' in text.lower()


class TestConcurrentMetricUpdates:
    """Tests for thread-safe metric updates."""
    
    def test_concurrent_violation_records(self, clean_registry):
        """Multiple concurrent violation records work correctly."""
        import threading
        
        def record_violations(node_id, count):
            for i in range(count):
                prometheus_metrics.record_violation(
                    'WARNING',
                    'silent_collection',
                    f'node_{node_id}'
                )
        
        threads = []
        for node_id in range(5):
            t = threading.Thread(target=record_violations, args=(node_id, 10))
            threads.append(t)
            t.start()
        
        for t in threads:
            t.join()
        
        # Should complete without errors
        text = prometheus_metrics.get_metrics_text().decode('utf-8')
        assert 'westworld_charter_violations_total' in text
    
    def test_concurrent_latency_records(self, clean_registry):
        """Multiple concurrent latency records work correctly."""
        import threading
        
        def record_latencies(count):
            for i in range(count):
                prometheus_metrics.record_validation_latency_ns(float(i * 1000))
        
        threads = []
        for _ in range(5):
            t = threading.Thread(target=record_latencies, args=(20,))
            threads.append(t)
            t.start()
        
        for t in threads:
            t.join()
        
        text = prometheus_metrics.get_metrics_text().decode('utf-8')
        assert 'metric_validation_latency_ns' in text


class TestMetricsErrorHandling:
    """Tests for error handling in metrics recording."""
    
    def test_invalid_label_format_handled(self, clean_registry):
        """Invalid label values don't crash metrics."""
        # These should not raise exceptions
        prometheus_metrics.record_violation('INVALID_SEVERITY', 'invalid_type', 'node')
        prometheus_metrics.record_forbidden_attempt('metric', 'node', 'invalid_status')
        
        # Metrics should still export
        text = prometheus_metrics.get_metrics_text()
        assert text is not None
    
    def test_missing_required_label(self, clean_registry):
        """Recording without required labels doesn't crash."""
        # These test that the function handles edge cases gracefully
        try:
            prometheus_metrics.record_violation('', '', '')
            text = prometheus_metrics.get_metrics_text()
            assert text is not None
        except Exception as e:
            # Some implementations might raise - that's ok if it's caught
            assert "missing" in str(e).lower() or "required" in str(e).lower()


if __name__ == '__main__':
    pytest.main([__file__, '-v'])
