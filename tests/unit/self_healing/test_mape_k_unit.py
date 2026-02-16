"""
Comprehensive unit tests for MAPE-K Self-Healing Core.

Tests cover: MAPEKMonitor, MAPEKAnalyzer, MAPEKPlanner,
MAPEKExecutor, MAPEKKnowledge, SelfHealingManager.
"""

import time
from unittest.mock import MagicMock, patch, PropertyMock

import pytest

from src.self_healing.mape_k import (
    MAPEKAnalyzer,
    MAPEKExecutor,
    MAPEKKnowledge,
    MAPEKMonitor,
    MAPEKPlanner,
    SelfHealingManager,
)


# ─── MAPEKMonitor ───────────────────────────────────────────────


class TestMAPEKMonitor:
    """Tests for MAPEKMonitor class."""

    def test_init_defaults(self):
        monitor = MAPEKMonitor()
        assert monitor.anomaly_detectors == []
        assert monitor.knowledge is None
        assert monitor.threshold_manager is None
        assert monitor.graphsage_detector is None
        assert monitor.use_graphsage is False
        assert monitor.default_thresholds["cpu_percent"] == 90.0
        assert monitor.default_thresholds["memory_percent"] == 85.0
        assert monitor.default_thresholds["packet_loss_percent"] == 5.0

    def test_init_with_knowledge(self):
        knowledge = MagicMock()
        monitor = MAPEKMonitor(knowledge=knowledge)
        assert monitor.knowledge is knowledge

    def test_init_with_threshold_manager(self):
        tm = MagicMock()
        monitor = MAPEKMonitor(threshold_manager=tm)
        assert monitor.threshold_manager is tm

    def test_register_detector(self):
        monitor = MAPEKMonitor()
        fn = lambda m: True
        monitor.register_detector(fn)
        assert fn in monitor.anomaly_detectors

    def test_register_multiple_detectors(self):
        monitor = MAPEKMonitor()
        fn1 = lambda m: False
        fn2 = lambda m: True
        monitor.register_detector(fn1)
        monitor.register_detector(fn2)
        assert len(monitor.anomaly_detectors) == 2

    # ── check() with default thresholds ──

    def test_check_default_cpu_anomaly(self):
        monitor = MAPEKMonitor()
        assert monitor.check({"cpu_percent": 95}) is True

    def test_check_default_cpu_normal(self):
        monitor = MAPEKMonitor()
        assert monitor.check({"cpu_percent": 80}) is False

    def test_check_default_cpu_boundary(self):
        monitor = MAPEKMonitor()
        # Exactly at threshold should NOT trigger (> not >=)
        assert monitor.check({"cpu_percent": 90}) is False

    def test_check_default_memory_anomaly(self):
        monitor = MAPEKMonitor()
        assert monitor.check({"memory_percent": 90}) is True

    def test_check_default_memory_normal(self):
        monitor = MAPEKMonitor()
        assert monitor.check({"memory_percent": 80}) is False

    def test_check_default_memory_boundary(self):
        monitor = MAPEKMonitor()
        assert monitor.check({"memory_percent": 85}) is False

    def test_check_default_packet_loss_anomaly(self):
        monitor = MAPEKMonitor()
        assert monitor.check({"packet_loss_percent": 10}) is True

    def test_check_default_packet_loss_normal(self):
        monitor = MAPEKMonitor()
        assert monitor.check({"packet_loss_percent": 3}) is False

    def test_check_default_packet_loss_boundary(self):
        monitor = MAPEKMonitor()
        assert monitor.check({"packet_loss_percent": 5}) is False

    def test_check_default_all_normal(self):
        monitor = MAPEKMonitor()
        metrics = {"cpu_percent": 50, "memory_percent": 50, "packet_loss_percent": 1}
        assert monitor.check(metrics) is False

    def test_check_empty_metrics(self):
        monitor = MAPEKMonitor()
        assert monitor.check({}) is False

    def test_check_missing_metric_keys(self):
        monitor = MAPEKMonitor()
        assert monitor.check({"unrelated": 100}) is False

    # ── check() with knowledge thresholds ──

    def test_check_with_knowledge_cpu_anomaly(self):
        knowledge = MagicMock()
        knowledge.get_adjusted_threshold.side_effect = lambda name, default: {
            "cpu_percent": 80.0,
            "memory_percent": 85.0,
            "packet_loss_percent": 5.0,
        }[name]
        monitor = MAPEKMonitor(knowledge=knowledge)
        assert monitor.check({"cpu_percent": 85}) is True

    def test_check_with_knowledge_no_anomaly(self):
        knowledge = MagicMock()
        knowledge.get_adjusted_threshold.return_value = 95.0
        monitor = MAPEKMonitor(knowledge=knowledge)
        assert monitor.check({"cpu_percent": 91}) is False

    # ── check() with threshold_manager ──

    def test_check_with_threshold_manager_cpu(self):
        tm = MagicMock()
        tm.get_threshold.side_effect = lambda name, default: {
            "cpu_threshold": 70.0,
            "memory_threshold": 85.0,
            "network_loss_threshold": 5.0,
        }[name]
        monitor = MAPEKMonitor(threshold_manager=tm)
        # 75 > 70 threshold from DAO
        assert monitor.check({"cpu_percent": 75}) is True

    def test_check_with_threshold_manager_memory(self):
        tm = MagicMock()
        tm.get_threshold.side_effect = lambda name, default: {
            "cpu_threshold": 90.0,
            "memory_threshold": 60.0,
            "network_loss_threshold": 5.0,
        }[name]
        monitor = MAPEKMonitor(threshold_manager=tm)
        assert monitor.check({"memory_percent": 65}) is True

    def test_check_with_threshold_manager_packet_loss(self):
        tm = MagicMock()
        tm.get_threshold.side_effect = lambda name, default: {
            "cpu_threshold": 90.0,
            "memory_threshold": 85.0,
            "network_loss_threshold": 2.0,
        }[name]
        monitor = MAPEKMonitor(threshold_manager=tm)
        assert monitor.check({"packet_loss_percent": 3}) is True

    def test_check_threshold_manager_priority_over_knowledge(self):
        """threshold_manager takes priority over knowledge."""
        knowledge = MagicMock()
        knowledge.get_adjusted_threshold.return_value = 95.0
        tm = MagicMock()
        tm.get_threshold.side_effect = lambda name, default: {
            "cpu_threshold": 70.0,
            "memory_threshold": 85.0,
            "network_loss_threshold": 5.0,
        }[name]
        monitor = MAPEKMonitor(knowledge=knowledge, threshold_manager=tm)
        # Should use tm threshold (70), not knowledge (95)
        assert monitor.check({"cpu_percent": 75}) is True
        # Knowledge should not be called
        knowledge.get_adjusted_threshold.assert_not_called()

    # ── check() with custom detectors ──

    def test_check_custom_detector_triggers(self):
        monitor = MAPEKMonitor()
        monitor.register_detector(lambda m: m.get("custom", 0) > 50)
        assert monitor.check({"custom": 60}) is True

    def test_check_custom_detector_does_not_trigger(self):
        monitor = MAPEKMonitor()
        monitor.register_detector(lambda m: m.get("custom", 0) > 50)
        assert monitor.check({"custom": 30}) is False

    def test_check_any_detector_triggers(self):
        monitor = MAPEKMonitor()
        monitor.register_detector(lambda m: False)
        monitor.register_detector(lambda m: True)
        assert monitor.check({}) is True

    def test_check_no_detector_triggers(self):
        monitor = MAPEKMonitor()
        monitor.register_detector(lambda m: False)
        monitor.register_detector(lambda m: False)
        assert monitor.check({}) is False

    # ── enable_graphsage ──

    @patch("src.self_healing.mape_k.MAPEKMonitor.enable_graphsage")
    def test_enable_graphsage_with_detector(self):
        monitor = MAPEKMonitor()
        mock_detector = MagicMock()
        # Call the real method manually
        MAPEKMonitor.enable_graphsage(monitor, detector=mock_detector)
        # The mock replaced enable_graphsage, so we test directly
        # Instead, test without patching the import
        pass

    def test_enable_graphsage_with_provided_detector(self):
        monitor = MAPEKMonitor()
        mock_detector = MagicMock()
        with patch(
            "src.self_healing.mape_k.GraphSAGEAnomalyDetector", create=True
        ), patch(
            "src.self_healing.mape_k.create_graphsage_detector_for_mapek", create=True
        ):
            # Patch the import inside enable_graphsage
            with patch.dict(
                "sys.modules",
                {
                    "src.ml.graphsage_anomaly_detector": MagicMock(
                        GraphSAGEAnomalyDetector=MagicMock,
                        create_graphsage_detector_for_mapek=MagicMock(),
                    )
                },
            ):
                monitor.enable_graphsage(detector=mock_detector)
        assert monitor.graphsage_detector is mock_detector
        assert monitor.use_graphsage is True

    def test_enable_graphsage_creates_default(self):
        monitor = MAPEKMonitor()
        mock_factory = MagicMock(return_value=MagicMock())
        mock_module = MagicMock(
            GraphSAGEAnomalyDetector=MagicMock,
            create_graphsage_detector_for_mapek=mock_factory,
        )
        with patch.dict("sys.modules", {"src.ml.graphsage_anomaly_detector": mock_module}):
            monitor.enable_graphsage(detector=None)
        assert monitor.graphsage_detector is mock_factory.return_value
        assert monitor.use_graphsage is True

    # ── check() with GraphSAGE ──

    def test_check_graphsage_predict_with_causal_anomaly(self):
        monitor = MAPEKMonitor()
        mock_prediction = MagicMock()
        mock_prediction.is_anomaly = True
        mock_prediction.anomaly_score = 0.95
        mock_prediction.inference_time_ms = 1.5

        mock_root_cause = MagicMock()
        mock_root_cause.root_cause_type = "network_failure"
        mock_root_cause.confidence = 0.85

        mock_causal = MagicMock()
        mock_causal.root_causes = [mock_root_cause]

        mock_detector = MagicMock()
        mock_detector.predict_with_causal.return_value = (mock_prediction, mock_causal)

        monitor.graphsage_detector = mock_detector
        monitor.use_graphsage = True

        metrics = {"cpu_percent": 50, "memory_percent": 50}
        assert monitor.check(metrics) is True

    def test_check_graphsage_predict_with_causal_no_anomaly(self):
        monitor = MAPEKMonitor()
        mock_prediction = MagicMock()
        mock_prediction.is_anomaly = False

        mock_detector = MagicMock()
        mock_detector.predict_with_causal.return_value = (mock_prediction, None)

        monitor.graphsage_detector = mock_detector
        monitor.use_graphsage = True

        metrics = {"cpu_percent": 50, "memory_percent": 50}
        assert monitor.check(metrics) is False

    def test_check_graphsage_predict_with_causal_no_root_causes(self):
        monitor = MAPEKMonitor()
        mock_prediction = MagicMock()
        mock_prediction.is_anomaly = True
        mock_prediction.anomaly_score = 0.8
        mock_prediction.inference_time_ms = 2.0

        mock_causal = MagicMock()
        mock_causal.root_causes = []

        mock_detector = MagicMock()
        mock_detector.predict_with_causal.return_value = (mock_prediction, mock_causal)

        monitor.graphsage_detector = mock_detector
        monitor.use_graphsage = True

        assert monitor.check({"cpu_percent": 50}) is True

    def test_check_graphsage_predict_with_causal_null_result(self):
        monitor = MAPEKMonitor()
        mock_prediction = MagicMock()
        mock_prediction.is_anomaly = True
        mock_prediction.anomaly_score = 0.8
        mock_prediction.inference_time_ms = 2.0

        mock_detector = MagicMock()
        mock_detector.predict_with_causal.return_value = (mock_prediction, None)

        monitor.graphsage_detector = mock_detector
        monitor.use_graphsage = True

        assert monitor.check({"cpu_percent": 50}) is True

    def test_check_graphsage_fallback_predict(self):
        """If predict_with_causal not available, falls back to predict."""
        monitor = MAPEKMonitor()
        mock_prediction = MagicMock()
        mock_prediction.is_anomaly = True
        mock_prediction.anomaly_score = 0.9
        mock_prediction.inference_time_ms = 1.0

        mock_detector = MagicMock(spec=[])  # empty spec, no predict_with_causal
        mock_detector.predict = MagicMock(return_value=mock_prediction)

        monitor.graphsage_detector = mock_detector
        monitor.use_graphsage = True

        assert monitor.check({"cpu_percent": 50}) is True

    def test_check_graphsage_fallback_predict_no_anomaly(self):
        monitor = MAPEKMonitor()
        mock_prediction = MagicMock()
        mock_prediction.is_anomaly = False

        mock_detector = MagicMock(spec=[])
        mock_detector.predict = MagicMock(return_value=mock_prediction)

        monitor.graphsage_detector = mock_detector
        monitor.use_graphsage = True

        assert monitor.check({"cpu_percent": 50}) is False

    def test_check_graphsage_exception_falls_through(self):
        """GraphSAGE exception should not prevent custom detectors from running."""
        monitor = MAPEKMonitor()
        mock_detector = MagicMock()
        mock_detector.predict_with_causal.side_effect = RuntimeError("boom")

        monitor.graphsage_detector = mock_detector
        monitor.use_graphsage = True

        monitor.register_detector(lambda m: True)
        assert monitor.check({"cpu_percent": 50}) is True

    def test_check_graphsage_disabled(self):
        """GraphSAGE not used when use_graphsage is False."""
        monitor = MAPEKMonitor()
        mock_detector = MagicMock()
        monitor.graphsage_detector = mock_detector
        monitor.use_graphsage = False

        assert monitor.check({"cpu_percent": 50}) is False
        mock_detector.predict_with_causal.assert_not_called()

    def test_check_graphsage_node_features_extraction(self):
        """Verify correct features are extracted from metrics."""
        monitor = MAPEKMonitor()
        mock_prediction = MagicMock()
        mock_prediction.is_anomaly = False

        mock_detector = MagicMock()
        mock_detector.predict_with_causal.return_value = (mock_prediction, None)

        monitor.graphsage_detector = mock_detector
        monitor.use_graphsage = True

        metrics = {
            "rssi": -70.0,
            "snr": 15.0,
            "packet_loss_percent": 2.0,
            "link_age_seconds": 7200.0,
            "latency_ms": 20.0,
            "throughput_mbps": 50.0,
            "cpu_percent": 60.0,
            "memory_percent": 40.0,
            "node_id": "test-node",
        }
        monitor.check(metrics)

        call_args = mock_detector.predict_with_causal.call_args
        assert call_args.kwargs["node_id"] == "test-node"
        features = call_args.kwargs["node_features"]
        assert features["rssi"] == -70.0
        assert features["loss_rate"] == 0.02
        assert features["cpu"] == 0.6
        assert features["memory"] == 0.4


# ─── MAPEKAnalyzer ──────────────────────────────────────────────


class TestMAPEKAnalyzer:
    """Tests for MAPEKAnalyzer class."""

    def test_init_defaults(self):
        analyzer = MAPEKAnalyzer()
        assert analyzer.causal_analyzer is None
        assert analyzer.use_causal_analysis is False
        assert analyzer.graphsage_detector is None
        assert analyzer.use_graphsage is False

    # ── Basic threshold analysis ──

    def test_analyze_high_cpu(self):
        analyzer = MAPEKAnalyzer()
        assert analyzer.analyze({"cpu_percent": 95}) == "High CPU"

    def test_analyze_high_memory(self):
        analyzer = MAPEKAnalyzer()
        assert analyzer.analyze({"memory_percent": 90}) == "High Memory"

    def test_analyze_network_loss(self):
        analyzer = MAPEKAnalyzer()
        assert analyzer.analyze({"packet_loss_percent": 10}) == "Network Loss"

    def test_analyze_healthy(self):
        analyzer = MAPEKAnalyzer()
        assert analyzer.analyze({"cpu_percent": 50, "memory_percent": 50}) == "Healthy"

    def test_analyze_empty_metrics(self):
        analyzer = MAPEKAnalyzer()
        assert analyzer.analyze({}) == "Healthy"

    def test_analyze_cpu_priority_over_memory(self):
        """CPU check comes first."""
        analyzer = MAPEKAnalyzer()
        result = analyzer.analyze({"cpu_percent": 95, "memory_percent": 90})
        assert result == "High CPU"

    def test_analyze_memory_priority_over_network(self):
        analyzer = MAPEKAnalyzer()
        result = analyzer.analyze(
            {"cpu_percent": 50, "memory_percent": 90, "packet_loss_percent": 10}
        )
        assert result == "High Memory"

    def test_analyze_cpu_boundary(self):
        analyzer = MAPEKAnalyzer()
        assert analyzer.analyze({"cpu_percent": 90}) == "Healthy"

    def test_analyze_memory_boundary(self):
        analyzer = MAPEKAnalyzer()
        assert analyzer.analyze({"memory_percent": 85}) == "Healthy"

    def test_analyze_packet_loss_boundary(self):
        analyzer = MAPEKAnalyzer()
        assert analyzer.analyze({"packet_loss_percent": 5}) == "Healthy"

    # ── enable_causal_analysis ──

    def test_enable_causal_analysis_with_provided_analyzer(self):
        analyzer = MAPEKAnalyzer()
        mock_causal = MagicMock()
        mock_module = MagicMock(
            CausalAnalysisEngine=MagicMock,
            IncidentEvent=MagicMock,
            IncidentSeverity=MagicMock,
            create_causal_analyzer_for_mapek=MagicMock(),
        )
        with patch.dict("sys.modules", {"src.ml.causal_analysis": mock_module}):
            analyzer.enable_causal_analysis(analyzer=mock_causal)
        assert analyzer.causal_analyzer is mock_causal
        assert analyzer.use_causal_analysis is True

    def test_enable_causal_analysis_creates_default(self):
        analyzer = MAPEKAnalyzer()
        mock_factory = MagicMock(return_value=MagicMock())
        mock_module = MagicMock(
            CausalAnalysisEngine=MagicMock,
            IncidentEvent=MagicMock,
            IncidentSeverity=MagicMock,
            create_causal_analyzer_for_mapek=mock_factory,
        )
        with patch.dict("sys.modules", {"src.ml.causal_analysis": mock_module}):
            analyzer.enable_causal_analysis(analyzer=None)
        assert analyzer.causal_analyzer is mock_factory.return_value

    # ── enable_graphsage ──

    def test_enable_graphsage_with_detector(self):
        analyzer = MAPEKAnalyzer()
        mock_detector = MagicMock()
        mock_module = MagicMock(
            GraphSAGEAnomalyDetector=MagicMock,
            create_graphsage_detector_for_mapek=MagicMock(),
        )
        with patch.dict("sys.modules", {"src.ml.graphsage_anomaly_detector": mock_module}):
            analyzer.enable_graphsage(detector=mock_detector)
        assert analyzer.graphsage_detector is mock_detector
        assert analyzer.use_graphsage is True

    def test_enable_graphsage_creates_default(self):
        analyzer = MAPEKAnalyzer()
        mock_factory = MagicMock(return_value=MagicMock())
        mock_module = MagicMock(
            GraphSAGEAnomalyDetector=MagicMock,
            create_graphsage_detector_for_mapek=mock_factory,
        )
        with patch.dict("sys.modules", {"src.ml.graphsage_anomaly_detector": mock_module}):
            analyzer.enable_graphsage(detector=None)
        assert analyzer.graphsage_detector is mock_factory.return_value

    # ── analyze with GraphSAGE ──

    def test_analyze_graphsage_with_causal_anomaly_and_root_causes(self):
        analyzer = MAPEKAnalyzer()
        mock_root = MagicMock()
        mock_root.root_cause_type = "cpu_overload"
        mock_root.confidence = 0.9
        mock_root.explanation = "CPU overloaded"

        mock_prediction = MagicMock()
        mock_prediction.is_anomaly = True
        mock_prediction.anomaly_score = 0.95

        mock_causal = MagicMock()
        mock_causal.root_causes = [mock_root]

        mock_detector = MagicMock()
        mock_detector.predict_with_causal.return_value = (mock_prediction, mock_causal)

        analyzer.graphsage_detector = mock_detector
        analyzer.use_graphsage = True

        result = analyzer.analyze({"cpu_percent": 50}, node_id="n1")
        assert "cpu_overload" in result
        assert "GraphSAGE+Causal" in result
        assert "90.0%" in result

    def test_analyze_graphsage_with_causal_anomaly_type_in_name(self):
        analyzer = MAPEKAnalyzer()
        mock_root = MagicMock()
        mock_root.root_cause_type = "anomaly_network"
        mock_root.confidence = 0.8
        mock_root.explanation = "test"

        mock_prediction = MagicMock()
        mock_prediction.is_anomaly = True

        mock_causal = MagicMock()
        mock_causal.root_causes = [mock_root]

        mock_detector = MagicMock()
        mock_detector.predict_with_causal.return_value = (mock_prediction, mock_causal)

        analyzer.graphsage_detector = mock_detector
        analyzer.use_graphsage = True

        result = analyzer.analyze({"cpu_percent": 50})
        assert "Anomaly:" in result

    def test_analyze_graphsage_with_causal_anomaly_no_root_causes(self):
        analyzer = MAPEKAnalyzer()
        mock_prediction = MagicMock()
        mock_prediction.is_anomaly = True
        mock_prediction.anomaly_score = 0.75

        mock_causal = MagicMock()
        mock_causal.root_causes = []

        mock_detector = MagicMock()
        mock_detector.predict_with_causal.return_value = (mock_prediction, mock_causal)

        analyzer.graphsage_detector = mock_detector
        analyzer.use_graphsage = True

        result = analyzer.analyze({"cpu_percent": 50})
        assert "Anomaly detected" in result
        assert "0.75" in result

    def test_analyze_graphsage_with_causal_no_anomaly(self):
        """If GraphSAGE says no anomaly, fall through to threshold-based."""
        analyzer = MAPEKAnalyzer()
        mock_prediction = MagicMock()
        mock_prediction.is_anomaly = False

        mock_detector = MagicMock()
        mock_detector.predict_with_causal.return_value = (mock_prediction, None)

        analyzer.graphsage_detector = mock_detector
        analyzer.use_graphsage = True

        result = analyzer.analyze({"cpu_percent": 95})
        assert result == "High CPU"

    def test_analyze_graphsage_fallback_predict_anomaly(self):
        """Uses basic predict when predict_with_causal not available."""
        analyzer = MAPEKAnalyzer()
        mock_prediction = MagicMock()
        mock_prediction.is_anomaly = True
        mock_prediction.anomaly_score = 0.88

        mock_detector = MagicMock(spec=[])
        mock_detector.predict = MagicMock(return_value=mock_prediction)

        analyzer.graphsage_detector = mock_detector
        analyzer.use_graphsage = True

        result = analyzer.analyze({"cpu_percent": 50})
        assert "Anomaly detected" in result
        assert "0.88" in result

    def test_analyze_graphsage_fallback_predict_no_anomaly(self):
        analyzer = MAPEKAnalyzer()
        mock_prediction = MagicMock()
        mock_prediction.is_anomaly = False

        mock_detector = MagicMock(spec=[])
        mock_detector.predict = MagicMock(return_value=mock_prediction)

        analyzer.graphsage_detector = mock_detector
        analyzer.use_graphsage = True

        result = analyzer.analyze({"cpu_percent": 95})
        assert result == "High CPU"

    def test_analyze_graphsage_exception_falls_back(self):
        analyzer = MAPEKAnalyzer()
        mock_detector = MagicMock()
        mock_detector.predict_with_causal.side_effect = RuntimeError("fail")

        analyzer.graphsage_detector = mock_detector
        analyzer.use_graphsage = True

        result = analyzer.analyze({"cpu_percent": 95})
        assert result == "High CPU"

    # ── analyze with causal analysis ──

    def test_analyze_causal_analysis_high_cpu_with_root_cause(self):
        analyzer = MAPEKAnalyzer()
        mock_root = MagicMock()
        mock_root.root_cause_type = "resource_exhaustion"
        mock_root.confidence = 0.85
        mock_root.explanation = "Resource exhaustion detected"

        mock_result = MagicMock()
        mock_result.root_causes = [mock_root]

        mock_causal = MagicMock()
        mock_causal.add_incident = MagicMock()
        mock_causal.analyze.return_value = mock_result

        analyzer.causal_analyzer = mock_causal
        analyzer.use_causal_analysis = True

        mock_incident_cls = MagicMock()
        mock_severity = MagicMock()
        mock_severity.HIGH = "HIGH"
        mock_severity.MEDIUM = "MEDIUM"

        mock_ca_module = MagicMock(
            IncidentEvent=mock_incident_cls,
            IncidentSeverity=mock_severity,
        )
        with patch.dict("sys.modules", {"src.ml.causal_analysis": mock_ca_module}):
            result = analyzer.analyze(
                {"cpu_percent": 95}, node_id="n1", event_id="evt1"
            )

        assert "High CPU" in result
        assert "Root cause" in result
        assert "resource_exhaustion" in result

    def test_analyze_causal_analysis_no_root_causes(self):
        analyzer = MAPEKAnalyzer()
        mock_result = MagicMock()
        mock_result.root_causes = []

        mock_causal = MagicMock()
        mock_causal.analyze.return_value = mock_result

        analyzer.causal_analyzer = mock_causal
        analyzer.use_causal_analysis = True

        mock_ca_module = MagicMock()
        with patch.dict("sys.modules", {"src.ml.causal_analysis": mock_ca_module}):
            result = analyzer.analyze(
                {"cpu_percent": 95}, node_id="n1", event_id="evt1"
            )
        assert result == "High CPU"

    def test_analyze_causal_analysis_no_event_id(self):
        """Causal analysis requires event_id."""
        analyzer = MAPEKAnalyzer()
        analyzer.causal_analyzer = MagicMock()
        analyzer.use_causal_analysis = True

        result = analyzer.analyze({"cpu_percent": 95})
        assert result == "High CPU"
        analyzer.causal_analyzer.add_incident.assert_not_called()

    def test_analyze_causal_analysis_exception(self):
        analyzer = MAPEKAnalyzer()
        mock_causal = MagicMock()
        mock_causal.add_incident.side_effect = RuntimeError("causal fail")

        analyzer.causal_analyzer = mock_causal
        analyzer.use_causal_analysis = True

        mock_ca_module = MagicMock()
        with patch.dict("sys.modules", {"src.ml.causal_analysis": mock_ca_module}):
            result = analyzer.analyze(
                {"cpu_percent": 95}, node_id="n1", event_id="evt1"
            )
        # Should still return basic issue
        assert result == "High CPU"

    def test_analyze_causal_severity_high_for_cpu_over_95(self):
        """Verify HIGH severity used when cpu > 95."""
        analyzer = MAPEKAnalyzer()
        mock_result = MagicMock()
        mock_result.root_causes = []

        mock_causal = MagicMock()
        mock_causal.analyze.return_value = mock_result

        analyzer.causal_analyzer = mock_causal
        analyzer.use_causal_analysis = True

        mock_incident_cls = MagicMock()
        mock_severity = MagicMock()

        mock_ca_module = MagicMock(
            IncidentEvent=mock_incident_cls,
            IncidentSeverity=mock_severity,
        )
        with patch.dict("sys.modules", {"src.ml.causal_analysis": mock_ca_module}):
            analyzer.analyze({"cpu_percent": 96}, node_id="n1", event_id="evt1")

        # Check that IncidentEvent was called with HIGH severity
        call_kwargs = mock_incident_cls.call_args
        assert call_kwargs.kwargs["severity"] == mock_severity.HIGH

    def test_analyze_causal_severity_medium_for_cpu_under_95(self):
        analyzer = MAPEKAnalyzer()
        mock_result = MagicMock()
        mock_result.root_causes = []

        mock_causal = MagicMock()
        mock_causal.analyze.return_value = mock_result

        analyzer.causal_analyzer = mock_causal
        analyzer.use_causal_analysis = True

        mock_incident_cls = MagicMock()
        mock_severity = MagicMock()

        mock_ca_module = MagicMock(
            IncidentEvent=mock_incident_cls,
            IncidentSeverity=mock_severity,
        )
        with patch.dict("sys.modules", {"src.ml.causal_analysis": mock_ca_module}):
            analyzer.analyze({"cpu_percent": 91}, node_id="n1", event_id="evt1")

        call_kwargs = mock_incident_cls.call_args
        assert call_kwargs.kwargs["severity"] == mock_severity.MEDIUM


# ─── MAPEKPlanner ────────────────────────────────────────────────


class TestMAPEKPlanner:
    """Tests for MAPEKPlanner class."""

    def test_init_defaults(self):
        planner = MAPEKPlanner()
        assert planner.knowledge is None
        assert "High CPU" in planner.default_strategies
        assert "High Memory" in planner.default_strategies
        assert "Network Loss" in planner.default_strategies

    def test_plan_high_cpu(self):
        planner = MAPEKPlanner()
        assert planner.plan("High CPU") == "Restart service"

    def test_plan_high_memory(self):
        planner = MAPEKPlanner()
        assert planner.plan("High Memory") == "Clear cache"

    def test_plan_network_loss(self):
        planner = MAPEKPlanner()
        assert planner.plan("Network Loss") == "Switch route"

    def test_plan_unknown_issue(self):
        planner = MAPEKPlanner()
        assert planner.plan("Unknown Issue") == "No action needed"

    def test_plan_healthy(self):
        planner = MAPEKPlanner()
        assert planner.plan("Healthy") == "No action needed"

    def test_plan_with_knowledge_recommendation(self):
        knowledge = MagicMock()
        knowledge.get_recommended_action.return_value = "Scale horizontally"
        planner = MAPEKPlanner(knowledge=knowledge)
        assert planner.plan("High CPU") == "Scale horizontally"

    def test_plan_with_knowledge_no_recommendation(self):
        knowledge = MagicMock()
        knowledge.get_recommended_action.return_value = None
        planner = MAPEKPlanner(knowledge=knowledge)
        assert planner.plan("High CPU") == "Restart service"

    def test_plan_knowledge_returns_empty_string(self):
        """Empty string is falsy, should fall back to default."""
        knowledge = MagicMock()
        knowledge.get_recommended_action.return_value = ""
        planner = MAPEKPlanner(knowledge=knowledge)
        assert planner.plan("High CPU") == "Restart service"


# ─── MAPEKExecutor ───────────────────────────────────────────────


class TestMAPEKExecutor:
    """Tests for MAPEKExecutor class."""

    def test_init_with_recovery_executor(self):
        mock_executor = MagicMock()
        mock_module = MagicMock()
        mock_module.RecoveryActionExecutor.return_value = mock_executor
        with patch.dict(
            "sys.modules", {"src.self_healing.recovery_actions": mock_module}
        ):
            executor = MAPEKExecutor()
        assert executor.use_recovery_executor is True

    def test_init_without_recovery_executor(self):
        with patch.dict("sys.modules", {"src.self_healing.recovery_actions": None}):
            executor = MAPEKExecutor()
        assert executor.use_recovery_executor is False
        assert executor.recovery_executor is None

    def test_execute_with_recovery_executor(self):
        executor = MAPEKExecutor.__new__(MAPEKExecutor)
        mock_re = MagicMock()
        mock_re.execute.return_value = True
        executor.recovery_executor = mock_re
        executor.use_recovery_executor = True

        result = executor.execute("Restart service", context={"node": "n1"})
        assert result is True
        mock_re.execute.assert_called_once_with("Restart service", {"node": "n1"})

    def test_execute_with_recovery_executor_failure(self):
        executor = MAPEKExecutor.__new__(MAPEKExecutor)
        mock_re = MagicMock()
        mock_re.execute.return_value = False
        executor.recovery_executor = mock_re
        executor.use_recovery_executor = True

        result = executor.execute("Restart service")
        assert result is False

    def test_execute_placeholder_fallback(self):
        executor = MAPEKExecutor.__new__(MAPEKExecutor)
        executor.recovery_executor = None
        executor.use_recovery_executor = False

        with patch("src.self_healing.mape_k.time") as mock_time:
            result = executor.execute("Restart service")
        assert result is True
        mock_time.sleep.assert_called_once_with(0.1)

    def test_execute_with_context_none(self):
        executor = MAPEKExecutor.__new__(MAPEKExecutor)
        mock_re = MagicMock()
        mock_re.execute.return_value = True
        executor.recovery_executor = mock_re
        executor.use_recovery_executor = True

        result = executor.execute("action")
        assert result is True
        mock_re.execute.assert_called_once_with("action", None)


# ─── MAPEKKnowledge ──────────────────────────────────────────────


class TestMAPEKKnowledge:
    """Tests for MAPEKKnowledge class."""

    def test_init_defaults(self):
        k = MAPEKKnowledge()
        assert k.incidents == []
        assert k.successful_patterns == {}
        assert k.failed_patterns == {}
        assert k.threshold_adjustments == {}
        assert k.knowledge_storage is None

    def test_init_with_storage(self):
        storage = MagicMock()
        k = MAPEKKnowledge(knowledge_storage=storage)
        assert k.knowledge_storage is storage

    # ── record ──

    def test_record_success(self):
        k = MAPEKKnowledge()
        k.record({"cpu": 95}, "High CPU", "Restart service", success=True, mttr=1.5)
        assert len(k.incidents) == 1
        assert k.incidents[0]["issue"] == "High CPU"
        assert k.incidents[0]["success"] is True
        assert "High CPU" in k.successful_patterns
        assert len(k.successful_patterns["High CPU"]) == 1

    def test_record_failure(self):
        k = MAPEKKnowledge()
        k.record({"cpu": 95}, "High CPU", "Restart service", success=False, mttr=10.0)
        assert len(k.incidents) == 1
        assert "High CPU" in k.failed_patterns
        assert len(k.failed_patterns["High CPU"]) == 1
        assert "High CPU" not in k.successful_patterns

    def test_record_multiple(self):
        k = MAPEKKnowledge()
        k.record({"cpu": 95}, "High CPU", "Restart", success=True)
        k.record({"cpu": 96}, "High CPU", "Scale", success=True)
        k.record({"cpu": 97}, "High CPU", "Restart", success=False)
        assert len(k.incidents) == 3
        assert len(k.successful_patterns["High CPU"]) == 2
        assert len(k.failed_patterns["High CPU"]) == 1

    def test_record_default_success(self):
        k = MAPEKKnowledge()
        k.record({"cpu": 95}, "High CPU", "Restart")
        assert k.incidents[0]["success"] is True

    def test_record_with_adapter_storage(self):
        storage = MagicMock()
        storage.record_incident_sync = MagicMock()
        k = MAPEKKnowledge(knowledge_storage=storage)
        k.record({"cpu": 95}, "High CPU", "Restart", success=True, mttr=1.0)
        storage.record_incident_sync.assert_called_once()

    def test_record_with_storage_exception(self):
        storage = MagicMock()
        storage.record_incident_sync = MagicMock(side_effect=RuntimeError("fail"))
        k = MAPEKKnowledge(knowledge_storage=storage)
        # Should not raise
        k.record({"cpu": 95}, "High CPU", "Restart", success=True)
        assert len(k.incidents) == 1

    # ── get_history ──

    def test_get_history_empty(self):
        k = MAPEKKnowledge()
        assert k.get_history() == []

    def test_get_history(self):
        k = MAPEKKnowledge()
        k.record({"cpu": 95}, "High CPU", "Restart")
        k.record({"mem": 90}, "High Memory", "Clear cache")
        history = k.get_history()
        assert len(history) == 2

    # ── get_successful_patterns ──

    def test_get_successful_patterns_with_data(self):
        k = MAPEKKnowledge()
        k.record({"cpu": 95}, "High CPU", "Restart", success=True)
        patterns = k.get_successful_patterns("High CPU")
        assert len(patterns) == 1

    def test_get_successful_patterns_empty(self):
        k = MAPEKKnowledge()
        patterns = k.get_successful_patterns("High CPU")
        assert patterns == []

    def test_get_successful_patterns_with_adapter_search(self):
        storage = MagicMock()
        storage.search_patterns_sync = MagicMock(
            return_value=[{"issue": "High CPU", "action": "Restart"}]
        )
        k = MAPEKKnowledge(knowledge_storage=storage)
        patterns = k.get_successful_patterns("High CPU")
        assert len(patterns) == 1
        storage.search_patterns_sync.assert_called_once()

    def test_get_successful_patterns_storage_exception(self):
        storage = MagicMock()
        storage.search_patterns_sync = MagicMock(side_effect=RuntimeError("fail"))
        k = MAPEKKnowledge(knowledge_storage=storage)
        k.record({"cpu": 95}, "High CPU", "Restart", success=True)
        patterns = k.get_successful_patterns("High CPU")
        # Falls back to local patterns
        assert len(patterns) == 1

    def test_get_successful_patterns_storage_returns_empty(self):
        storage = MagicMock()
        storage.search_patterns_sync = MagicMock(return_value=[])
        k = MAPEKKnowledge(knowledge_storage=storage)
        k.record({"cpu": 95}, "High CPU", "Restart", success=True)
        patterns = k.get_successful_patterns("High CPU")
        # Empty from storage, falls to local
        assert len(patterns) == 1

    # ── get_average_mttr ──

    def test_get_average_mttr_with_data(self):
        k = MAPEKKnowledge()
        k.record({"cpu": 95}, "High CPU", "Restart", success=True, mttr=2.0)
        k.record({"cpu": 96}, "High CPU", "Restart", success=True, mttr=4.0)
        avg = k.get_average_mttr("High CPU")
        assert avg == 3.0

    def test_get_average_mttr_no_data(self):
        k = MAPEKKnowledge()
        assert k.get_average_mttr("High CPU") is None

    def test_get_average_mttr_no_mttr_values(self):
        k = MAPEKKnowledge()
        k.record({"cpu": 95}, "High CPU", "Restart", success=True, mttr=None)
        assert k.get_average_mttr("High CPU") is None

    def test_get_average_mttr_zero_mttr(self):
        k = MAPEKKnowledge()
        k.record({"cpu": 95}, "High CPU", "Restart", success=True, mttr=0)
        assert k.get_average_mttr("High CPU") is None

    def test_get_average_mttr_mixed_mttr(self):
        k = MAPEKKnowledge()
        k.record({"cpu": 95}, "High CPU", "Restart", success=True, mttr=2.0)
        k.record({"cpu": 96}, "High CPU", "Restart", success=True, mttr=None)
        avg = k.get_average_mttr("High CPU")
        assert avg == 2.0

    def test_get_average_mttr_from_storage(self):
        """Falls back to storage when no local data."""
        storage = MagicMock()
        storage.search_patterns_sync = MagicMock(
            return_value=[{"mttr": 3.0}, {"mttr": 5.0}]
        )
        k = MAPEKKnowledge(knowledge_storage=storage)
        avg = k.get_average_mttr("High CPU")
        assert avg == 4.0

    def test_get_average_mttr_storage_no_mttr(self):
        storage = MagicMock()
        storage.search_patterns_sync = MagicMock(
            return_value=[{"action": "restart"}]  # no mttr key
        )
        k = MAPEKKnowledge(knowledge_storage=storage)
        avg = k.get_average_mttr("High CPU")
        assert avg is None

    # ── get_recommended_action ──

    def test_get_recommended_action_no_patterns(self):
        k = MAPEKKnowledge()
        assert k.get_recommended_action("High CPU") is None

    def test_get_recommended_action_single_action(self):
        k = MAPEKKnowledge()
        k.record({"cpu": 95}, "High CPU", "Restart", success=True, mttr=2.0)
        assert k.get_recommended_action("High CPU") == "Restart"

    def test_get_recommended_action_best_mttr(self):
        k = MAPEKKnowledge()
        # "Scale" has lower avg MTTR
        k.record({"cpu": 95}, "High CPU", "Restart", success=True, mttr=5.0)
        k.record({"cpu": 95}, "High CPU", "Scale", success=True, mttr=1.0)
        assert k.get_recommended_action("High CPU") == "Scale"

    def test_get_recommended_action_multiple_same_action(self):
        k = MAPEKKnowledge()
        k.record({"cpu": 95}, "High CPU", "Restart", success=True, mttr=2.0)
        k.record({"cpu": 96}, "High CPU", "Restart", success=True, mttr=4.0)
        k.record({"cpu": 97}, "High CPU", "Scale", success=True, mttr=2.5)
        # Restart avg MTTR = 3.0, Scale avg MTTR = 2.5
        assert k.get_recommended_action("High CPU") == "Scale"

    def test_get_recommended_action_default_mttr(self):
        """When mttr is None, defaults to 10.0."""
        k = MAPEKKnowledge()
        k.record({"cpu": 95}, "High CPU", "Restart", success=True, mttr=None)
        k.record({"cpu": 95}, "High CPU", "Scale", success=True, mttr=2.0)
        assert k.get_recommended_action("High CPU") == "Scale"

    # ── get_adjusted_threshold ──

    def test_get_adjusted_threshold_no_adjustments(self):
        k = MAPEKKnowledge()
        assert k.get_adjusted_threshold("cpu_percent", 90.0) == 90.0

    def test_get_adjusted_threshold_with_adjustment(self):
        k = MAPEKKnowledge()
        k.threshold_adjustments["cpu_percent"] = 85.0
        assert k.get_adjusted_threshold("cpu_percent", 90.0) == 85.0

    # ── _update_thresholds ──

    def test_update_thresholds_initial_success(self):
        k = MAPEKKnowledge()
        k._update_thresholds({"cpu_percent": 95.0}, "High CPU", success=True)
        # Initial: 95 * 1.1 = 104.5, then * 0.98 = 102.41
        assert "cpu_percent" in k.threshold_adjustments
        assert k.threshold_adjustments["cpu_percent"] == pytest.approx(
            95.0 * 1.1 * 0.98, rel=1e-3
        )

    def test_update_thresholds_initial_failure(self):
        k = MAPEKKnowledge()
        k._update_thresholds({"cpu_percent": 95.0}, "High CPU", success=False)
        # Initial: 95 * 1.1, then * 1.05
        assert k.threshold_adjustments["cpu_percent"] == pytest.approx(
            95.0 * 1.1 * 1.05, rel=1e-3
        )

    def test_update_thresholds_non_numeric_ignored(self):
        k = MAPEKKnowledge()
        k._update_thresholds({"node_id": "test-node"}, "issue", success=True)
        assert "node_id" not in k.threshold_adjustments

    def test_update_thresholds_successive(self):
        k = MAPEKKnowledge()
        k._update_thresholds({"cpu_percent": 90.0}, "High CPU", success=True)
        first = k.threshold_adjustments["cpu_percent"]
        k._update_thresholds({"cpu_percent": 90.0}, "High CPU", success=True)
        # Already set, so just *= 0.98
        assert k.threshold_adjustments["cpu_percent"] == pytest.approx(
            first * 0.98, rel=1e-3
        )


# ─── SelfHealingManager ─────────────────────────────────────────


class TestSelfHealingManager:
    """Tests for SelfHealingManager class."""

    @patch("src.self_healing.mape_k.MAPEKExecutor")
    def test_init_defaults(self, mock_executor_cls):
        manager = SelfHealingManager()
        assert manager.node_id == "default"
        assert isinstance(manager.knowledge, MAPEKKnowledge)
        assert isinstance(manager.monitor, MAPEKMonitor)
        assert isinstance(manager.analyzer, MAPEKAnalyzer)
        assert isinstance(manager.planner, MAPEKPlanner)
        assert manager.threshold_manager is None
        assert manager.feedback_updates == 0
        assert manager.threshold_adjustments == 0
        assert manager.strategy_improvements == 0

    @patch("src.self_healing.mape_k.MAPEKExecutor")
    def test_init_with_node_id(self, mock_executor_cls):
        manager = SelfHealingManager(node_id="node-42")
        assert manager.node_id == "node-42"

    @patch("src.self_healing.mape_k.MAPEKExecutor")
    def test_init_with_threshold_manager(self, mock_executor_cls):
        tm = MagicMock()
        tm.check_and_apply_dao_proposals.return_value = 3
        manager = SelfHealingManager(threshold_manager=tm)
        assert manager.threshold_manager is tm
        assert manager.monitor.threshold_manager is tm
        tm.check_and_apply_dao_proposals.assert_called_once()

    @patch("src.self_healing.mape_k.MAPEKExecutor")
    def test_init_threshold_manager_apply_exception(self, mock_executor_cls):
        tm = MagicMock()
        tm.check_and_apply_dao_proposals.side_effect = RuntimeError("fail")
        # Should not raise
        manager = SelfHealingManager(threshold_manager=tm)
        assert manager.threshold_manager is tm

    @patch("src.self_healing.mape_k.MAPEKExecutor")
    def test_init_with_knowledge_storage(self, mock_executor_cls):
        storage = MagicMock()
        mock_adapter = MagicMock()
        with patch(
            "src.self_healing.mape_k.MAPEKKnowledgeStorageAdapter",
            create=True,
        ) as mock_adapter_cls, patch.dict(
            "sys.modules",
            {
                "src.storage.mapek_integration": MagicMock(
                    MAPEKKnowledgeStorageAdapter=mock_adapter_cls
                )
            },
        ):
            mock_adapter_cls.return_value = mock_adapter
            manager = SelfHealingManager(knowledge_storage=storage)
        assert manager.knowledge.knowledge_storage is mock_adapter

    # ── run_cycle ──

    @patch("src.self_healing.mape_k.MAPEKExecutor")
    def test_run_cycle_no_anomaly(self, mock_executor_cls):
        manager = SelfHealingManager()
        metrics = {"cpu_percent": 50, "memory_percent": 50, "packet_loss_percent": 1}
        manager.run_cycle(metrics)
        assert len(manager.knowledge.incidents) == 0

    @patch("src.self_healing.mape_k.MAPEKExecutor")
    def test_run_cycle_high_cpu(self, mock_executor_cls):
        mock_exec_instance = MagicMock()
        mock_exec_instance.execute.return_value = True
        mock_executor_cls.return_value = mock_exec_instance

        manager = SelfHealingManager()
        metrics = {"cpu_percent": 95}
        manager.run_cycle(metrics)

        mock_exec_instance.execute.assert_called_once()

    @patch("src.self_healing.mape_k.MAPEKExecutor")
    def test_run_cycle_high_memory(self, mock_executor_cls):
        mock_exec_instance = MagicMock()
        mock_exec_instance.execute.return_value = True
        mock_executor_cls.return_value = mock_exec_instance

        manager = SelfHealingManager()
        metrics = {"memory_percent": 90}
        manager.run_cycle(metrics)

        call_args = mock_exec_instance.execute.call_args
        assert call_args[0][0] == "Clear cache"

    @patch("src.self_healing.mape_k.MAPEKExecutor")
    def test_run_cycle_network_loss(self, mock_executor_cls):
        mock_exec_instance = MagicMock()
        mock_exec_instance.execute.return_value = True
        mock_executor_cls.return_value = mock_exec_instance

        manager = SelfHealingManager()
        metrics = {"packet_loss_percent": 10}
        manager.run_cycle(metrics)

        call_args = mock_exec_instance.execute.call_args
        assert call_args[0][0] == "Switch route"

    @patch("src.self_healing.mape_k.MAPEKExecutor")
    def test_run_cycle_custom_detector(self, mock_executor_cls):
        mock_exec_instance = MagicMock()
        mock_exec_instance.execute.return_value = True
        mock_executor_cls.return_value = mock_exec_instance

        manager = SelfHealingManager()
        manager.monitor.register_detector(lambda m: m.get("custom", 0) > 50)
        metrics = {"custom": 60}
        manager.run_cycle(metrics)
        # Analyze sees healthy metrics but monitor detects via custom detector
        mock_exec_instance.execute.assert_called_once()

    @patch("src.self_healing.mape_k.MAPEKExecutor")
    def test_run_cycle_cleanup_recovery_tracking(self, mock_executor_cls):
        mock_exec_instance = MagicMock()
        mock_exec_instance.execute.return_value = True
        mock_executor_cls.return_value = mock_exec_instance

        manager = SelfHealingManager()
        metrics = {"cpu_percent": 95}
        manager.run_cycle(metrics)

        # Recovery tracking should be cleaned up
        assert len(manager.recovery_start_times) == 0
        assert len(manager.recovery_events) == 0

    @patch("src.self_healing.mape_k.MAPEKExecutor")
    def test_run_cycle_metrics_import_error(self, mock_executor_cls):
        """run_cycle should work even if monitoring.metrics is unavailable."""
        mock_exec_instance = MagicMock()
        mock_exec_instance.execute.return_value = True
        mock_executor_cls.return_value = mock_exec_instance

        with patch.dict("sys.modules", {"src.monitoring.metrics": None}):
            manager = SelfHealingManager()
            metrics = {"cpu_percent": 95}
            # Should not raise
            manager.run_cycle(metrics)

    # ── _apply_feedback_loop ──

    @patch("src.self_healing.mape_k.MAPEKExecutor")
    def test_apply_feedback_successful_fast_recovery(self, mock_executor_cls):
        manager = SelfHealingManager()
        manager._apply_feedback_loop("High CPU", "Restart", success=True, mttr=1.0)
        assert manager.feedback_updates == 1
        assert manager.threshold_adjustments == 1
        assert manager.strategy_improvements == 1

    @patch("src.self_healing.mape_k.MAPEKExecutor")
    def test_apply_feedback_failed_recovery(self, mock_executor_cls):
        manager = SelfHealingManager()
        manager._apply_feedback_loop("High CPU", "Restart", success=False, mttr=5.0)
        assert manager.feedback_updates == 1
        assert manager.threshold_adjustments == 1
        assert manager.strategy_improvements == 0

    @patch("src.self_healing.mape_k.MAPEKExecutor")
    def test_apply_feedback_slow_recovery(self, mock_executor_cls):
        manager = SelfHealingManager()
        manager._apply_feedback_loop("High CPU", "Restart", success=True, mttr=8.0)
        assert manager.feedback_updates == 1
        assert manager.threshold_adjustments == 1
        assert manager.strategy_improvements == 1

    @patch("src.self_healing.mape_k.MAPEKExecutor")
    def test_apply_feedback_normal_recovery(self, mock_executor_cls):
        """MTTR between 3 and 7, success=True: no threshold adj, but strategy improved."""
        manager = SelfHealingManager()
        manager._apply_feedback_loop("High CPU", "Restart", success=True, mttr=5.0)
        assert manager.feedback_updates == 1
        assert manager.threshold_adjustments == 0
        assert manager.strategy_improvements == 1

    @patch("src.self_healing.mape_k.MAPEKExecutor")
    def test_apply_feedback_periodic_summary(self, mock_executor_cls):
        """Every 10th update logs a summary."""
        manager = SelfHealingManager()
        for i in range(10):
            manager._apply_feedback_loop("High CPU", "Restart", success=True, mttr=1.0)
        assert manager.feedback_updates == 10

    # ── get_feedback_stats ──

    @patch("src.self_healing.mape_k.MAPEKExecutor")
    def test_get_feedback_stats_initial(self, mock_executor_cls):
        manager = SelfHealingManager()
        stats = manager.get_feedback_stats()
        assert stats["feedback_updates"] == 0
        assert stats["threshold_adjustments"] == 0
        assert stats["strategy_improvements"] == 0
        assert stats["knowledge_base_size"] == 0
        assert stats["successful_patterns"] == 0
        assert stats["failed_patterns"] == 0

    @patch("src.self_healing.mape_k.MAPEKExecutor")
    def test_get_feedback_stats_after_records(self, mock_executor_cls):
        manager = SelfHealingManager()
        manager.knowledge.record({"cpu": 95}, "High CPU", "Restart", success=True)
        manager.knowledge.record({"cpu": 96}, "High CPU", "Restart", success=False)
        stats = manager.get_feedback_stats()
        assert stats["knowledge_base_size"] == 2
        assert stats["successful_patterns"] == 1
        assert stats["failed_patterns"] == 1

    # ── integrate_ebpf_self_healing ──

    @patch("src.self_healing.mape_k.MAPEKExecutor")
    def test_integrate_ebpf_self_healing_success(self, mock_executor_cls):
        manager = SelfHealingManager()
        mock_controller = MagicMock()
        mock_integrate = MagicMock(return_value=mock_controller)

        with patch.dict(
            "sys.modules",
            {
                "src.self_healing.ebpf_anomaly_detector": MagicMock(
                    integrate_ebpf_self_healing=mock_integrate
                )
            },
        ):
            result = manager.integrate_ebpf_self_healing("wlan0")

        assert result is mock_controller

    @patch("src.self_healing.mape_k.MAPEKExecutor")
    def test_integrate_ebpf_self_healing_import_error(self, mock_executor_cls):
        manager = SelfHealingManager()
        with patch.dict(
            "sys.modules", {"src.self_healing.ebpf_anomaly_detector": None}
        ):
            result = manager.integrate_ebpf_self_healing()
        assert result is None

    @patch("src.self_healing.mape_k.MAPEKExecutor")
    def test_integrate_ebpf_default_interface(self, mock_executor_cls):
        manager = SelfHealingManager()
        mock_integrate = MagicMock(return_value=MagicMock())

        with patch.dict(
            "sys.modules",
            {
                "src.self_healing.ebpf_anomaly_detector": MagicMock(
                    integrate_ebpf_self_healing=mock_integrate
                )
            },
        ):
            manager.integrate_ebpf_self_healing()

        mock_integrate.assert_called_once_with(manager, "eth0")


# ─── Integration-style tests (multiple components) ───────────────


class TestMAPEKIntegration:
    """Integration-style tests combining multiple MAPE-K components."""

    @patch("src.self_healing.mape_k.MAPEKExecutor")
    def test_full_cycle_knowledge_feedback(self, mock_executor_cls):
        mock_exec = MagicMock()
        mock_exec.execute.return_value = True
        mock_executor_cls.return_value = mock_exec

        manager = SelfHealingManager()
        # Run cycle with high CPU
        manager.run_cycle({"cpu_percent": 95})
        # Knowledge should have recorded the incident
        history = manager.knowledge.get_history()
        assert len(history) >= 1

    @patch("src.self_healing.mape_k.MAPEKExecutor")
    def test_planner_uses_knowledge_from_previous_cycle(self, mock_executor_cls):
        mock_exec = MagicMock()
        mock_exec.execute.return_value = True
        mock_executor_cls.return_value = mock_exec

        manager = SelfHealingManager()
        # First record a successful pattern with good MTTR
        manager.knowledge.record(
            {"cpu": 95}, "High CPU", "Scale horizontally", success=True, mttr=0.5
        )
        # Now the planner should recommend "Scale horizontally"
        action = manager.planner.plan("High CPU")
        assert action == "Scale horizontally"

    def test_monitor_with_knowledge_threshold_adjustment(self):
        knowledge = MAPEKKnowledge()
        knowledge.threshold_adjustments["cpu_percent"] = 80.0
        monitor = MAPEKMonitor(knowledge=knowledge)
        # 85 > 80 adjusted threshold should trigger
        assert monitor.check({"cpu_percent": 85}) is True
        # 75 < 80 should not trigger
        assert monitor.check({"cpu_percent": 75}) is False

    @patch("src.self_healing.mape_k.MAPEKExecutor")
    def test_multiple_cycles_accumulate_knowledge(self, mock_executor_cls):
        mock_exec = MagicMock()
        mock_exec.execute.return_value = True
        mock_executor_cls.return_value = mock_exec

        manager = SelfHealingManager()
        for _ in range(5):
            manager.run_cycle({"cpu_percent": 95})

        stats = manager.get_feedback_stats()
        assert stats["knowledge_base_size"] >= 1
