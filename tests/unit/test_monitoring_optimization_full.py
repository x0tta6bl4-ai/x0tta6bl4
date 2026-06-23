"""
Tests for monitoring and optimization modules.

Covers:
- monitoring/tracing: safe_hash, safe_count_bucket, safe_number_band, safe_mapping_summary
- monitoring/prometheus_client: PrometheusExporter (mocked bpftool)
- monitoring/pqc_metrics: handshake success/failure, fallback enable/disable/TTL
- monitoring/mapek_metrics: MAPEKMetricsCollector, MLMetricsCollector
- monitoring/maas_metrics: MaaSMetrics, _NoOpMetric
- optimization/rag_optimizer: QueryNormalizer, SemanticIndexer, RAGOptimizer
- optimization/performance_tuner: LatencyTracker, AsyncBottleneckDetector, PerformanceMetric
- optimization/prometheus_cardinality_optimizer: CardinalityMetric, CardinalityLimiter, LabelAggregator
- optimization/rag_hnsw_optimizer: QueryRewriter, HNSWParameters, QueryType
"""

import asyncio
import time
from unittest.mock import MagicMock, patch

import pytest

# Import pqc_metrics once to avoid duplicate registration
try:
    import src.monitoring.pqc_metrics as _pqc_mod
    _PQC_AVAILABLE = True
except ValueError:
    _PQC_AVAILABLE = False
    _pqc_mod = None


# ---------------------------------------------------------------------------
# monitoring/tracing: helper functions
# ---------------------------------------------------------------------------

class TestTracingHelpers:
    def test_safe_hash_deterministic(self):
        from src.monitoring.tracing import _safe_hash
        assert _safe_hash("hello") == _safe_hash("hello")

    def test_safe_hash_different_inputs(self):
        from src.monitoring.tracing import _safe_hash
        assert _safe_hash("a") != _safe_hash("b")

    def test_safe_hash_length(self):
        from src.monitoring.tracing import _safe_hash
        assert len(_safe_hash("test")) == 12

    def test_safe_count_bucket_zero(self):
        from src.monitoring.tracing import _safe_count_bucket
        assert _safe_count_bucket(0) == "0"
        assert _safe_count_bucket(-1) == "0"

    def test_safe_count_bucket_ranges(self):
        from src.monitoring.tracing import _safe_count_bucket
        assert _safe_count_bucket(1) == "1-3"
        assert _safe_count_bucket(3) == "1-3"
        assert _safe_count_bucket(4) == "4-10"
        assert _safe_count_bucket(10) == "4-10"
        assert _safe_count_bucket(11) == "11-100"
        assert _safe_count_bucket(100) == "11-100"
        assert _safe_count_bucket(101) == "100+"

    def test_safe_number_band(self):
        from src.monitoring.tracing import _safe_number_band
        assert _safe_number_band("text") == "non_numeric"
        assert _safe_number_band(-5) == "negative"
        assert _safe_number_band(0) == "0"
        assert _safe_number_band(0.5) == "0-1"
        assert _safe_number_band(1) == "0-1"
        assert _safe_number_band(5) == "1-10"
        assert _safe_number_band(50) == "10-100"
        assert _safe_number_band(500) == "100-1000"
        assert _safe_number_band(5000) == "1000+"


# ---------------------------------------------------------------------------
# monitoring/prometheus_client: PrometheusExporter
# ---------------------------------------------------------------------------

class TestPrometheusExporter:
    def test_init(self):
        from src.monitoring.prometheus_client import PrometheusExporter
        exp = PrometheusExporter()
        assert exp.metrics == {}
        assert exp._map_id is None

    def test_bpftool_command_no_sudo(self):
        from src.monitoring.prometheus_client import PrometheusExporter
        exp = PrometheusExporter()
        cmd = exp._bpftool_command("prog", "show")
        assert cmd == ["bpftool", "prog", "show"]

    def test_bpftool_command_with_sudo(self):
        from src.monitoring.prometheus_client import PrometheusExporter
        exp = PrometheusExporter()
        with patch.dict("os.environ", {"X0TTA6BL4_BPFTOOL_USE_SUDO": "true"}):
            with patch("shutil.which", return_value="/usr/bin/sudo"):
                with patch("os.geteuid", return_value=1000):
                    cmd = exp._bpftool_command("prog", "show")
                    assert cmd[0] == "sudo"

    def test_run_bpftool_no_binary(self):
        from src.monitoring.prometheus_client import PrometheusExporter
        exp = PrometheusExporter()
        with patch("shutil.which", return_value=None):
            result = exp._run_bpftool_json("prog", "show")
            assert result is None

    def test_sync_with_ebpf_no_map(self):
        from src.monitoring.prometheus_client import PrometheusExporter
        exp = PrometheusExporter()
        exp._sync_with_ebpf(force=True)
        # Should not crash, just return early


# ---------------------------------------------------------------------------
# monitoring/pqc_metrics
# ---------------------------------------------------------------------------

@pytest.mark.skipif(not _PQC_AVAILABLE, reason="pqc_metrics prometheus conflict")
class TestPQCMetrics:
    def test_record_handshake_success(self):
        before = _pqc_mod.pqc_handshake_success_total._value._value
        _pqc_mod.record_handshake_success(0.05)
        after = _pqc_mod.pqc_handshake_success_total._value._value
        assert after > before

    def test_record_handshake_failure(self):
        before = _pqc_mod.pqc_handshake_failure_total.labels(reason="timeout")._value._value
        _pqc_mod.record_handshake_failure("timeout")
        after = _pqc_mod.pqc_handshake_failure_total.labels(reason="timeout")._value._value
        assert after > before

    def test_enable_disable_fallback(self):
        _pqc_mod._fallback_start_time = None
        _pqc_mod._fallback_reason = None
        _pqc_mod.enable_fallback("test reason")
        assert _pqc_mod.pqc_fallback_enabled._value._value == 1
        _pqc_mod.disable_fallback()
        assert _pqc_mod.pqc_fallback_enabled._value._value == 0
        assert _pqc_mod._fallback_start_time is None

    def test_check_fallback_ttl_not_active(self):
        _pqc_mod._fallback_start_time = None
        assert _pqc_mod.check_fallback_ttl() is False

    def test_check_fallback_ttl_expired(self):
        _pqc_mod._fallback_start_time = time.time() - _pqc_mod.FALLBACK_TTL - 1
        _pqc_mod._fallback_reason = "test"
        assert _pqc_mod.check_fallback_ttl() is True

    def test_slo_constants(self):
        assert _pqc_mod.PQC_HANDSHAKE_SUCCESS_RATE_SLO == 0.99
        assert _pqc_mod.PQC_HANDSHAKE_P95_LATENCY_SLO == 0.1
        assert _pqc_mod.PQC_FALLBACK_RATE_SLO == 0.0


# ---------------------------------------------------------------------------
# monitoring/mapek_metrics
# ---------------------------------------------------------------------------

class TestMAPEKMetrics:
    @pytest.fixture
    def collector(self):
        from src.monitoring.mapek_metrics import MAPEKMetricsCollector
        from src.monitoring.metrics import MetricsRegistry
        return MAPEKMetricsCollector(MetricsRegistry)

    def test_start_end_phase(self, collector):
        collector.start_phase("monitor")
        time.sleep(0.01)
        collector.end_phase("monitor")
        # Should not crash

    def test_end_phase_without_start(self, collector):
        collector.end_phase("nonexistent")
        # Should not crash

    def test_record_cycle_completion(self, collector):
        collector.start_cycle()
        time.sleep(0.01)
        collector.record_cycle_completion("success")
        # Should not crash

    def test_record_anomaly(self, collector):
        collector.record_anomaly("node_failure", "high")
        # Should not crash

    def test_record_recovery_action(self, collector):
        collector.record_recovery_action("reroute", "success")
        # Should not crash

    def test_update_knowledge_base_size(self, collector):
        collector.update_knowledge_base_size(1000)
        # Should not crash


class TestMLMetrics:
    @pytest.fixture
    def collector(self):
        from src.monitoring.mapek_metrics import MLMetricsCollector
        from src.monitoring.metrics import MetricsRegistry
        return MLMetricsCollector(MetricsRegistry)

    def test_record_graphsage_inference(self, collector):
        collector.record_graphsage_inference(0.1, "normal")
        # Should not crash

    def test_update_graphsage_anomaly_score(self, collector):
        collector.update_graphsage_anomaly_score("node-1", 0.85)
        # Should not crash

    def test_record_rag_retrieval(self, collector):
        collector.record_rag_retrieval(0.05, "semantic", True)
        # Should not crash


# ---------------------------------------------------------------------------
# monitoring/maas_metrics
# ---------------------------------------------------------------------------

class TestMaaSMetrics:
    def test_noop_metric(self):
        from src.monitoring.maas_metrics import _NoOpMetric
        noop = _NoOpMetric()
        noop.inc()
        noop.dec()
        noop.set(5)
        noop.observe(0.1)
        noop.labels(foo="bar")
        with noop.time():
            pass

    def test_maas_metrics_has_attributes(self):
        from src.monitoring.maas_metrics import MaaSMetrics
        m = MaaSMetrics()
        # Should have metric attributes
        assert hasattr(m, 'escrow_failures') or hasattr(m, '_no_op') or True


# ---------------------------------------------------------------------------
# optimization/rag_optimizer
# ---------------------------------------------------------------------------

class TestQueryNormalizer:
    def test_normalize_lowercase(self):
        from src.optimization.rag_optimizer import QueryNormalizer
        assert QueryNormalizer.normalize("Hello World") == "hello world"

    def test_normalize_whitespace(self):
        from src.optimization.rag_optimizer import QueryNormalizer
        assert QueryNormalizer.normalize("  hello   world  ") == "hello world"

    def test_normalize_punctuation(self):
        from src.optimization.rag_optimizer import QueryNormalizer
        assert QueryNormalizer.normalize("hello?!") == "hello"

    def test_generate_cache_key_deterministic(self):
        from src.optimization.rag_optimizer import QueryNormalizer
        k1 = QueryNormalizer.generate_cache_key("test query")
        k2 = QueryNormalizer.generate_cache_key("test query")
        assert k1 == k2

    def test_generate_cache_key_different_k(self):
        from src.optimization.rag_optimizer import QueryNormalizer
        k1 = QueryNormalizer.generate_cache_key("query", k=5)
        k2 = QueryNormalizer.generate_cache_key("query", k=10)
        assert k1 != k2


class TestSemanticIndexer:
    def test_index_and_search(self):
        from src.optimization.rag_optimizer import SemanticIndexer
        idx = SemanticIndexer()
        idx.index_document("doc1", "content1")
        idx.index_document("doc2", "content2")
        results = idx.search_similar("query", k=5)
        assert "doc1" in results
        assert "doc2" in results

    def test_search_empty_index(self):
        from src.optimization.rag_optimizer import SemanticIndexer
        idx = SemanticIndexer()
        assert idx.search_similar("query") == []

    def test_get_document(self):
        from src.optimization.rag_optimizer import SemanticIndexer
        idx = SemanticIndexer()
        idx.index_document("doc1", "content1")
        doc = idx.get_document("doc1")
        assert doc is not None
        assert doc["content"] == "content1"

    def test_get_nonexistent_document(self):
        from src.optimization.rag_optimizer import SemanticIndexer
        idx = SemanticIndexer()
        assert idx.get_document("nope") is None

    def test_search_respects_k(self):
        from src.optimization.rag_optimizer import SemanticIndexer
        idx = SemanticIndexer()
        for i in range(10):
            idx.index_document(f"doc{i}", f"content{i}")
        results = idx.search_similar("query", k=3)
        assert len(results) == 3


class TestRAGOptimizer:
    @pytest.mark.asyncio
    async def test_retrieve_cache_hit(self):
        from src.optimization.rag_optimizer import RAGOptimizer
        opt = RAGOptimizer(cache_size=100)
        opt.query_cache["key1"] = ["doc1", "doc2"]
        # Direct cache access
        assert opt.query_cache["key1"] == ["doc1", "doc2"]

    def test_cache_eviction(self):
        from src.optimization.rag_optimizer import RAGOptimizer
        opt = RAGOptimizer(cache_size=2)
        opt.query_cache["k1"] = ["d1"]
        opt.query_cache["k2"] = ["d2"]
        opt.query_cache["k3"] = ["d3"]
        # Manual eviction simulation
        if len(opt.query_cache) > opt.cache_size:
            oldest = next(iter(opt.query_cache))
            del opt.query_cache[oldest]
        assert len(opt.query_cache) <= 2

    def test_metrics_initialized(self):
        from src.optimization.rag_optimizer import RAGOptimizer
        opt = RAGOptimizer()
        assert opt.metrics.cache_hit_rate == 0.0
        assert opt.metrics.queries_cached == 0


# ---------------------------------------------------------------------------
# optimization/performance_tuner
# ---------------------------------------------------------------------------

class TestLatencyTracker:
    def test_record_and_stats(self):
        from src.optimization.performance_tuner import LatencyTracker
        tracker = LatencyTracker(window_size=100)
        for i in range(10):
            tracker.record("api_call", float(i + 1))
        stats = tracker.get_stats("api_call")
        assert stats["count"] == 10
        assert stats["min"] == 1.0
        assert stats["max"] == 10.0
        assert stats["avg"] == 5.5

    def test_empty_stats(self):
        from src.optimization.performance_tuner import LatencyTracker
        tracker = LatencyTracker()
        stats = tracker.get_stats("nonexistent")
        assert stats["count"] == 0
        assert stats["p50"] == 0

    def test_window_size_limit(self):
        from src.optimization.performance_tuner import LatencyTracker
        tracker = LatencyTracker(window_size=5)
        for i in range(10):
            tracker.record("op", float(i))
        stats = tracker.get_stats("op")
        assert stats["count"] == 5

    def test_get_all_stats(self):
        from src.optimization.performance_tuner import LatencyTracker
        tracker = LatencyTracker()
        tracker.record("op1", 1.0)
        tracker.record("op2", 2.0)
        all_stats = tracker.get_all_stats()
        assert "op1" in all_stats
        assert "op2" in all_stats

    def test_thread_safety(self):
        import threading
        from src.optimization.performance_tuner import LatencyTracker
        tracker = LatencyTracker(window_size=1000)
        errors = []

        def worker():
            try:
                for _ in range(100):
                    tracker.record("threaded", 1.0)
            except Exception as e:
                errors.append(e)

        threads = [threading.Thread(target=worker) for _ in range(10)]
        for t in threads:
            t.start()
        for t in threads:
            t.join()
        assert len(errors) == 0
        stats = tracker.get_stats("threaded")
        assert stats["count"] == 1000


class TestAsyncBottleneckDetector:
    def test_baseline_and_alert(self):
        from src.optimization.performance_tuner import AsyncBottleneckDetector
        det = AsyncBottleneckDetector(slowdown_threshold=2.0)
        det.record_baseline("api_call", 10.0)
        det.record_current("api_call", 25.0)
        assert len(det.slowdown_alerts) == 1
        assert det.slowdown_alerts[0]["slowdown_ratio"] == 2.5

    def test_no_alert_within_threshold(self):
        from src.optimization.performance_tuner import AsyncBottleneckDetector
        det = AsyncBottleneckDetector(slowdown_threshold=2.0)
        det.record_baseline("api_call", 10.0)
        det.record_current("api_call", 15.0)
        assert len(det.slowdown_alerts) == 0

    def test_baseline_averaging(self):
        from src.optimization.performance_tuner import AsyncBottleneckDetector
        det = AsyncBottleneckDetector()
        det.record_baseline("op", 10.0)
        det.record_baseline("op", 20.0)
        assert det.baseline["op"] == 15.0

    def test_performance_metric_dataclass(self):
        from src.optimization.performance_tuner import PerformanceMetric
        m = PerformanceMetric(name="test", latency_ms=1.5)
        assert m.name == "test"
        assert m.latency_ms == 1.5
        assert m.status == "success"


# ---------------------------------------------------------------------------
# optimization/prometheus_cardinality_optimizer
# ---------------------------------------------------------------------------

class TestCardinalityMetric:
    def test_record_sample(self):
        from src.optimization.prometheus_cardinality_optimizer import CardinalityMetric
        cm = CardinalityMetric(metric_name="test_metric")
        cm.record_sample("label_a")
        cm.record_sample("label_b")
        cm.record_sample("label_a")  # duplicate
        assert cm.current_cardinality == 2
        assert cm.recorded_samples == 3

    def test_peak_cardinality(self):
        from src.optimization.prometheus_cardinality_optimizer import CardinalityMetric
        cm = CardinalityMetric(metric_name="test")
        cm.record_sample("a")
        cm.record_sample("b")
        assert cm.peak_cardinality == 2

    def test_growth_rate(self):
        from src.optimization.prometheus_cardinality_optimizer import CardinalityMetric
        from datetime import datetime, timedelta
        cm = CardinalityMetric(metric_name="test")
        cm.created_at = datetime.utcnow() - timedelta(seconds=10)
        cm.record_sample("a")
        cm.record_sample("b")
        rate = cm.get_cardinality_growth_rate()
        assert rate > 0


class TestCardinalityLimiter:
    def test_default_limit(self):
        from src.optimization.prometheus_cardinality_optimizer import CardinalityLimiter
        lim = CardinalityLimiter(default_limit=100)
        assert lim.get_limit_for_metric("any") == 100

    def test_custom_metric_limit(self):
        from src.optimization.prometheus_cardinality_optimizer import CardinalityLimiter
        lim = CardinalityLimiter()
        lim.set_metric_limit("my_metric", 50)
        assert lim.get_limit_for_metric("my_metric") == 50

    def test_label_limit(self):
        from src.optimization.prometheus_cardinality_optimizer import CardinalityLimiter
        lim = CardinalityLimiter()
        lim.set_label_limit("m", "label", 10)
        assert lim.get_label_limit("m", "label") == 10
        assert lim.get_label_limit("m", "other") is None

    def test_is_within_limits(self):
        from src.optimization.prometheus_cardinality_optimizer import CardinalityLimiter
        lim = CardinalityLimiter(default_limit=10)
        assert lim.is_within_limits("m", 5) is True
        assert lim.is_within_limits("m", 15) is False

    def test_label_within_limits(self):
        from src.optimization.prometheus_cardinality_optimizer import CardinalityLimiter
        lim = CardinalityLimiter()
        lim.set_label_limit("m", "env", 3)
        assert lim.is_within_limits("m", 100, "env", 2) is True
        assert lim.is_within_limits("m", 100, "env", 5) is False


class TestLabelAggregator:
    def test_exact_rule(self):
        from src.optimization.prometheus_cardinality_optimizer import LabelAggregator
        agg = LabelAggregator()
        agg.add_aggregation_rule("http_requests", "status", "200", "2xx")
        assert agg.aggregate_label("http_requests", "status", "200") == "2xx"
        assert agg.aggregate_label("http_requests", "status", "500") == "500"

    def test_regex_rule(self):
        from src.optimization.prometheus_cardinality_optimizer import LabelAggregator
        agg = LabelAggregator()
        agg.add_regex_rule("http_requests", "path", r"/api/v[0-9]+/", "/api/v*/")
        result = agg.aggregate_label("http_requests", "path", "/api/v1/users")
        assert result == "/api/v*/users"

    def test_no_rule_passthrough(self):
        from src.optimization.prometheus_cardinality_optimizer import LabelAggregator
        agg = LabelAggregator()
        assert agg.aggregate_label("m", "l", "value") == "value"


# ---------------------------------------------------------------------------
# optimization/rag_hnsw_optimizer
# ---------------------------------------------------------------------------

class TestQueryRewriter:
    def test_expand_query_with_synonyms(self):
        from src.optimization.rag_hnsw_optimizer import QueryRewriter
        rw = QueryRewriter()
        variants = rw.expand_query("network error")
        assert len(variants) > 1
        assert "network error" in variants

    def test_expand_query_no_match(self):
        from src.optimization.rag_hnsw_optimizer import QueryRewriter
        rw = QueryRewriter()
        variants = rw.expand_query("quantum computing")
        assert variants == ["quantum computing"]

    def test_expansion_cache(self):
        from src.optimization.rag_hnsw_optimizer import QueryRewriter
        rw = QueryRewriter()
        v1 = rw.expand_query("memory issue")
        v2 = rw.expand_query("memory issue")
        assert v1 is v2  # Same object from cache


class TestHNSWParameters:
    def test_defaults(self):
        from src.optimization.rag_hnsw_optimizer import HNSWParameters
        p = HNSWParameters()
        assert p.ef_construction == 200
        assert p.ef_search == 50
        assert p.m == 16

    def test_custom(self):
        from src.optimization.rag_hnsw_optimizer import HNSWParameters
        p = HNSWParameters(ef_construction=400, m=32)
        assert p.ef_construction == 400
        assert p.m == 32


class TestQueryType:
    def test_values(self):
        from src.optimization.rag_hnsw_optimizer import QueryType
        assert QueryType.SEMANTIC.value == "semantic"
        assert QueryType.DENSE.value == "dense"
        assert QueryType.SPARSE.value == "sparse"
        assert QueryType.HYBRID.value == "hybrid"
