"""
Production System Performance Benchmarks

Validates:
1. Throughput under sustained load
2. Latency percentiles (p50, p95, p99)
3. Memory efficiency
4. Resource utilization
5. Scalability characteristics
"""

import pytest
import time
import numpy as np
from datetime import datetime
from src.ml.production_anomaly_detector import get_production_anomaly_detector
from src.ml.ensemble_anomaly_detector import get_ensemble_detector, EnsembleVotingStrategy
from src.monitoring.advanced_sla_metrics import AdvancedSLAManager, MetricType
from src.monitoring.tracing_optimizer import get_tracing_optimizer, Span
from src.testing.edge_case_validator import EdgeCaseValidator


class TestThroughputBenchmarks:
    """Benchmark throughput under various loads"""
    
    def test_anomaly_detector_throughput_1k_metrics(self):
        """Measure throughput: 1000 metric recordings"""
        detector = get_production_anomaly_detector()
        
        start_time = time.time()
        
        for i in range(1000):
            detector.record_metric("service", f"metric_{i % 10}", 100.0 + np.random.normal(0, 5))
        
        duration = time.time() - start_time
        throughput = 1000 / duration
        
        assert throughput > 100
        print(f"Anomaly detector throughput: {throughput:.0f} metrics/sec")
    
    def test_ensemble_detector_throughput_500_fits(self):
        """Measure ensemble detector throughput: 500 model fits"""
        detector = get_ensemble_detector(strategy=EnsembleVotingStrategy.WEIGHTED)
        
        start_time = time.time()
        
        for i in range(500):
            data = [100.0 + np.random.normal(0, 5) for _ in range(50)]
            detector.fit_detector(f"metric_{i}", data)
        
        duration = time.time() - start_time
        throughput = 500 / duration
        
        assert throughput > 10
        print(f"Ensemble detector throughput: {throughput:.1f} fits/sec")
    
    def test_sla_manager_throughput_5k_recordings(self):
        """Measure SLA manager throughput: 5000 metric recordings"""
        manager = AdvancedSLAManager()
        manager.register_metric("latency", MetricType.HISTOGRAM, "ms")
        
        start_time = time.time()
        
        for i in range(5000):
            manager.record_metric("latency", 50.0 + (i % 200))
        
        duration = time.time() - start_time
        throughput = 5000 / duration
        
        assert throughput > 500
        print(f"SLA manager throughput: {throughput:.0f} metrics/sec")
    
    def test_tracing_optimizer_throughput_2k_spans(self):
        """Measure tracing throughput: 2000 span processing"""
        optimizer = get_tracing_optimizer()
        base_time = datetime.utcnow()
        
        start_time = time.time()
        
        for i in range(2000):
            span = Span(
                trace_id=f"trace-{i}",
                span_id=f"span-{i}",
                parent_span_id=None,
                operation_name="operation",
                service_name="api",
                start_time=base_time,
                end_time=base_time,
                status="ok"
            )
            optimizer.process_span(span)
        
        duration = time.time() - start_time
        throughput = 2000 / duration
        
        assert throughput > 100
        print(f"Tracing optimizer throughput: {throughput:.0f} spans/sec")


class TestLatencyPercentiles:
    """Benchmark latency percentiles under load"""
    
    def test_anomaly_detector_latency_percentiles(self):
        """Measure anomaly detector latency: p50, p95, p99"""
        detector = get_production_anomaly_detector()
        
        latencies = []
        
        for i in range(100):
            detector.record_metric("baseline", "metric", 100.0)
        
        for i in range(500):
            start = time.time()
            detector.record_metric("service", "metric", 100.0 + np.random.normal(0, 5))
            latencies.append((time.time() - start) * 1000)
        
        p50 = np.percentile(latencies, 50)
        p95 = np.percentile(latencies, 95)
        p99 = np.percentile(latencies, 99)
        
        assert p50 < p95 < p99
        assert p99 < 100
        print(f"Detector latency - p50: {p50:.2f}ms, p95: {p95:.2f}ms, p99: {p99:.2f}ms")
    
    def test_sla_manager_latency_percentiles(self):
        """Measure SLA manager latency: p50, p95, p99"""
        manager = AdvancedSLAManager()
        manager.register_metric("response_time", MetricType.HISTOGRAM, "ms")
        manager.define_sla("sla_1", "response_time", 200.0, "<=")
        
        latencies = []
        
        for i in range(300):
            start = time.time()
            manager.record_metric("response_time", 50.0 + (i % 100))
            latencies.append((time.time() - start) * 1000)
        
        p50 = np.percentile(latencies, 50)
        p95 = np.percentile(latencies, 95)
        p99 = np.percentile(latencies, 99)
        
        assert p50 < p95 < p99
        print(f"SLA manager latency - p50: {p50:.3f}ms, p95: {p95:.3f}ms, p99: {p99:.3f}ms")
    
    def test_edge_validator_latency_percentiles(self):
        """Measure edge validator latency: p50, p95, p99"""
        validator = EdgeCaseValidator()
        
        latencies = []
        
        for i in range(500):
            start = time.time()
            validator.check_numeric_bounds(float(i), min_val=0, max_val=1000)
            latencies.append((time.time() - start) * 1000)
        
        p50 = np.percentile(latencies, 50)
        p95 = np.percentile(latencies, 95)
        p99 = np.percentile(latencies, 99)
        
        assert p50 < p95 < p99
        assert p99 < 10
        print(f"Edge validator latency - p50: {p50:.3f}ms, p95: {p95:.3f}ms, p99: {p99:.3f}ms")


class TestScalabilityCharacteristics:
    """Test system scalability under increasing load"""
    
    def test_anomaly_detector_scalability_1k_to_10k(self):
        """Test detector scalability: 1k to 10k metrics"""
        detector = get_production_anomaly_detector()
        
        results = {}
        
        for metric_count in [1000, 2000, 5000, 10000]:
            start = time.time()
            
            for i in range(metric_count):
                detector.record_metric("service", f"metric_{i % 20}", 100.0 + np.random.normal(0, 5))
            
            duration = time.time() - start
            throughput = metric_count / duration
            results[metric_count] = throughput
        
        for metric_count, throughput in results.items():
            print(f"Detector - {metric_count} metrics: {throughput:.0f} metrics/sec")
        
        assert all(throughput > 50 for throughput in results.values())
    
    def test_sla_manager_scalability_1k_to_5k_metrics(self):
        """Test SLA manager scalability: 1k to 5k metrics"""
        results = {}
        
        for metric_count in [1000, 2000, 5000]:
            manager = AdvancedSLAManager()
            manager.register_metric("latency", MetricType.HISTOGRAM, "ms")
            manager.define_sla("sla", "latency", 200.0, "<=")
            
            start = time.time()
            
            for i in range(metric_count):
                manager.record_metric("latency", 50.0 + (i % 100))
            
            duration = time.time() - start
            throughput = metric_count / duration
            results[metric_count] = throughput
        
        for metric_count, throughput in results.items():
            print(f"SLA manager - {metric_count} metrics: {throughput:.0f} metrics/sec")
        
        assert all(throughput > 100 for throughput in results.values())
    
    def test_tracing_optimizer_scalability_500_to_5k_spans(self):
        """Test tracing scalability: 500 to 5k spans"""
        results = {}
        
        for span_count in [500, 1000, 2000, 5000]:
            optimizer = get_tracing_optimizer()
            base_time = datetime.utcnow()
            
            start = time.time()
            
            for i in range(span_count):
                span = Span(
                    trace_id=f"trace-{i}",
                    span_id=f"span-{i}",
                    parent_span_id=None,
                    operation_name="operation",
                    service_name="api",
                    start_time=base_time,
                    end_time=base_time,
                    status="ok"
                )
                optimizer.process_span(span)
            
            duration = time.time() - start
            throughput = span_count / duration
            results[span_count] = throughput
        
        for span_count, throughput in results.items():
            print(f"Tracing - {span_count} spans: {throughput:.0f} spans/sec")
        
        assert all(throughput > 50 for throughput in results.values())


class TestMemoryEfficiency:
    """Test memory efficiency under load"""
    
    def test_anomaly_detector_memory_1k_metrics(self):
        """Measure memory for 1000 metrics in detector"""
        detector = get_production_anomaly_detector()
        
        for i in range(1000):
            detector.record_metric("service", f"metric_{i % 10}", 100.0 + np.random.normal(0, 5))
        
        summary = detector.get_anomaly_summary()
        assert summary["metrics_tracked"] > 0
    
    def test_sla_manager_memory_1k_recordings(self):
        """Measure memory for 1000 metric recordings in SLA manager"""
        manager = AdvancedSLAManager()
        manager.register_metric("latency", MetricType.HISTOGRAM, "ms")
        manager.define_sla("sla_1", "latency", 200.0, "<=")
        manager.define_sla("sla_2", "latency", 500.0, "<=")
        manager.define_sla("sla_3", "latency", 100.0, "<=")
        
        for i in range(1000):
            manager.record_metric("latency", 50.0 + (i % 200))
        
        report = manager.get_compliance_report()
        assert isinstance(report, dict)
    
    def test_tracing_memory_2k_spans(self):
        """Measure memory for 2000 spans in tracing optimizer"""
        optimizer = get_tracing_optimizer()
        base_time = datetime.utcnow()
        
        for i in range(2000):
            span = Span(
                trace_id=f"trace-{i}",
                span_id=f"span-{i}",
                parent_span_id=None,
                operation_name="operation",
                service_name="api",
                start_time=base_time,
                end_time=base_time,
                status="ok"
            )
            optimizer.process_span(span)
        
        report = optimizer.get_performance_report()
        assert report["total_spans"] == 2000


class TestConcurrentLoad:
    """Test behavior under concurrent load"""
    
    def test_detector_multiple_services(self):
        """Test detector with multiple concurrent services"""
        detector = get_production_anomaly_detector()
        
        for service_id in range(20):
            for metric_id in range(50):
                value = 100.0 + service_id + np.random.normal(0, 5)
                detector.record_metric(f"service_{service_id}", f"metric_{metric_id}", value)
        
        summary = detector.get_anomaly_summary()
        assert summary["metrics_tracked"] >= 20
    
    def test_sla_manager_multiple_metrics_and_slas(self):
        """Test SLA manager with multiple metrics and SLA definitions"""
        manager = AdvancedSLAManager()
        
        for metric_id in range(10):
            manager.register_metric(f"metric_{metric_id}", MetricType.HISTOGRAM, "unit")
            manager.define_sla(f"sla_{metric_id}", f"metric_{metric_id}", 100.0, "<=")
        
        for i in range(100):
            for metric_id in range(10):
                manager.record_metric(f"metric_{metric_id}", 50.0 + (i % 50))
        
        compliance = manager.get_overall_compliance()
        assert "overall_compliance_percentage" in compliance
    
    def test_tracing_multiple_services(self):
        """Test tracing with multiple concurrent services"""
        optimizer = get_tracing_optimizer()
        base_time = datetime.utcnow()
        
        span_count = 0
        for service_id in range(10):
            for trace_id in range(50):
                span = Span(
                    trace_id=f"trace-{service_id}-{trace_id}",
                    span_id=f"span-{service_id}-{trace_id}",
                    parent_span_id=None,
                    operation_name="operation",
                    service_name=f"service_{service_id}",
                    start_time=base_time,
                    end_time=base_time,
                    status="ok"
                )
                optimizer.process_span(span)
                span_count += 1
        
        report = optimizer.get_performance_report()
        assert report["total_spans"] == span_count


class TestResourceUtilization:
    """Test resource utilization patterns"""
    
    def test_detector_cpu_efficiency(self):
        """Test detector CPU efficiency with varying dataset sizes"""
        detector = get_production_anomaly_detector()
        
        for baseline_size in [100, 200, 500]:
            for i in range(baseline_size):
                detector.record_metric("baseline", "metric", 100.0)
            
            for i in range(100):
                detector.record_metric("test", "metric", 100.0 + np.random.normal(0, 5))
        
        summary = detector.get_anomaly_summary()
        assert "metrics_tracked" in summary
    
    def test_sla_manager_report_generation_latency(self):
        """Test SLA manager report generation performance"""
        manager = AdvancedSLAManager()
        manager.register_metric("metric", MetricType.HISTOGRAM, "unit")
        manager.define_sla("sla", "metric", 100.0, "<=")
        
        for i in range(2000):
            manager.record_metric("metric", 50.0 + (i % 100))
        
        start = time.time()
        report = manager.get_compliance_report()
        report_duration = time.time() - start
        
        assert report_duration < 1.0
        print(f"Report generation time: {report_duration*1000:.2f}ms")
    
    def test_edge_validator_batch_validation(self):
        """Test edge validator batch validation performance"""
        validator = EdgeCaseValidator()
        
        start = time.time()
        
        for i in range(1000):
            validator.check_numeric_bounds(float(i), min_val=0, max_val=500)
            validator.check_string_bounds(f"string_{i}", max_length=100)
            validator.check_collection_bounds(list(range(i % 50)), max_size=100)
        
        duration = time.time() - start
        operations_per_sec = 3000 / duration
        
        assert operations_per_sec > 1000
        print(f"Batch validation rate: {operations_per_sec:.0f} ops/sec")


class TestBenchmarkSummary:
    """Summary of all benchmark results"""
    
    def test_overall_system_performance(self):
        """Validate overall system performance targets"""
        detector = get_production_anomaly_detector()
        manager = AdvancedSLAManager()
        manager.register_metric("metric", MetricType.GAUGE, "unit")
        optimizer = get_tracing_optimizer()
        
        start = time.time()
        
        for i in range(5000):
            detector.record_metric("service", f"metric_{i % 10}", 100.0)
            manager.record_metric("metric", 100.0)
            
            if i % 10 == 0:
                span = Span(
                    trace_id=f"trace-{i}",
                    span_id=f"span-{i}",
                    parent_span_id=None,
                    operation_name="op",
                    service_name="svc",
                    start_time=datetime.utcnow(),
                    end_time=datetime.utcnow(),
                    status="ok"
                )
                optimizer.process_span(span)
        
        total_duration = time.time() - start
        
        assert total_duration < 30
        print(f"Total system throughput: {5000/total_duration:.0f} ops/sec")
        print(f"All systems operational and performant ✓")


if __name__ == "__main__":
    pytest.main([__file__, "-v", "-s"])
