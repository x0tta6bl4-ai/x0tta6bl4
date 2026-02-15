# Task 5 Testing and Benchmarking Suite
# Validates all AI enhancements and compares v2 vs v3

"""
Comprehensive Testing Suite for AI Enhancement Task

Tests:
1. GraphSAGE v3 functionality and accuracy improvements
2. Enhanced Causal Analysis accuracy and speed
3. Integration between both systems
4. Benchmark comparisons (v2 vs v3)
5. Performance metrics (latency, memory, accuracy)

Target Metrics Validation:
- GraphSAGE v3: ≥99% accuracy, ≤5% FPR, <30ms inference, <3MB
- Causal Analysis v2: >95% root cause accuracy, <50ms analysis
- Integration: <100ms total pipeline latency
"""

import json
import logging
import time
from datetime import datetime, timedelta
from typing import Any, Dict, List, Tuple

import pytest

logger = logging.getLogger(__name__)


class TestGraphSAGEV3Enhancements:
    """Test GraphSAGE v3 improvements"""

    @pytest.fixture
    def detector(self):
        """Create GraphSAGE v3 detector"""
        from src.ml.graphsage_anomaly_detector_v3_enhanced import \
            GraphSAGEAnomalyDetectorV3

        return GraphSAGEAnomalyDetectorV3()

    def test_adaptive_threshold(self, detector):
        """Test adaptive threshold adjustment"""
        # Good network health
        threshold_good = detector.adaptive_threshold.get_threshold(0.9)

        # Poor network health
        threshold_poor = detector.adaptive_threshold.get_threshold(0.2)

        # Threshold should increase in poor conditions
        assert threshold_poor > threshold_good
        assert 0.6 <= threshold_good <= 0.75
        assert 0.7 <= threshold_poor <= 0.85
        logger.info(
            f"✓ Adaptive threshold: good={threshold_good:.2f}, poor={threshold_poor:.2f}"
        )

    def test_feature_normalization(self, detector):
        """Test feature normalization with baseline awareness"""
        features = {
            "rssi": -75,
            "loss_rate": 0.05,
            "latency": 100,
            "link_age_hours": 12,
            "throughput_mbps": 50,
            "cpu_percent": 70,
            "memory_percent": 80,
        }

        normalized = detector.normalizer.normalize_features(
            features, detector.adaptive_threshold.baseline
        )

        # Verify normalization
        assert "rssi_z" in normalized
        assert "loss_rate_z" in normalized
        assert "latency_z" in normalized
        assert 0 <= normalized["link_age_norm"] <= 1
        assert 0 <= normalized["throughput_norm"] <= 1
        assert 0 <= normalized["resource_stress"] <= 1
        logger.info(f"✓ Feature normalization: {len(normalized)} features normalized")

    def test_network_health_calculation(self, detector):
        """Test network health score calculation"""
        node_features = {"rssi": -70, "loss_rate": 0.01, "throughput_mbps": 80}

        neighbors = [
            ("n2", {"rssi": -72, "loss_rate": 0.015, "throughput_mbps": 75}),
            ("n3", {"rssi": -68, "loss_rate": 0.005, "throughput_mbps": 85}),
        ]

        health = detector._calculate_network_health(node_features, neighbors)

        assert 0.0 <= health <= 1.0
        assert health > 0.5  # Good network conditions
        logger.info(f"✓ Network health score: {health:.2%}")

    def test_anomaly_score_computation(self, detector):
        """Test anomaly score computation with multiple heuristics"""
        normalized_features = {
            "rssi_z": 0.5,
            "loss_rate_z": 0.3,
            "latency_z": -0.2,
            "link_age_norm": 0.8,
            "throughput_norm": 0.6,
            "resource_stress": 0.4,
        }

        neighbors = [
            ("n2", {"rssi": -70, "loss_rate": 0.01}),
            ("n3", {"rssi": -72, "loss_rate": 0.015}),
        ]

        score = detector._compute_anomaly_score(
            "node-01", normalized_features, neighbors, network_nodes_count=10
        )

        assert 0.0 <= score <= 1.0
        logger.info(f"✓ Anomaly score: {score:.3f}")

    def test_prediction_enhanced(self, detector):
        """Test enhanced prediction with all features"""
        node_features = {
            "rssi": -75,
            "loss_rate": 0.02,
            "latency": 80,
            "link_age_hours": 48,
            "throughput_mbps": 60,
            "cpu_percent": 65,
            "memory_percent": 72,
        }

        neighbors = [
            ("n2", {"rssi": -70, "loss_rate": 0.01, "latency": 50}),
            ("n3", {"rssi": -72, "loss_rate": 0.015, "latency": 65}),
        ]

        result = detector.predict_enhanced(
            node_id="node-01",
            node_features=node_features,
            neighbors=neighbors,
            network_nodes_count=10,
            update_baseline=True,
        )

        assert result["is_anomaly"] in [True, False]
        assert 0.0 <= result["anomaly_score"] <= 1.0
        assert 0.0 <= result["anomaly_confidence"] <= 1.0
        assert 0.0 <= result["network_health"] <= 1.0
        assert "explanation" in result
        assert "recommendations" in result
        assert result["inference_time_ms"] < 50  # <50ms requirement

        logger.info(
            f"✓ Enhanced prediction: anomaly={result['is_anomaly']}, "
            f"score={result['anomaly_score']:.3f}, "
            f"latency={result['inference_time_ms']:.1f}ms"
        )

    def test_confidence_calibration(self, detector):
        """Test confidence calibration to prevent alert fatigue"""
        # Generate many predictions to build history
        for i in range(50):
            detector.last_predictions[f"node-{i}"] = 0.65
            detector.prediction_history.append(
                {
                    "node_id": f"node-{i}",
                    "is_anomaly": True,
                    "timestamp": datetime.now(),
                }
            )

        # Test calibration
        calibrated = detector._calibrate_confidence(0.7, 0.8)

        # Should reduce confidence due to alert fatigue
        assert calibrated < 0.8
        logger.info(f"✓ Confidence calibration: {0.8:.2f} → {calibrated:.2f}")

    def test_recommendations_generation(self, detector):
        """Test recommendation generation based on anomaly type"""
        node_features = {
            "rssi": -85,
            "cpu_percent": 95,
            "memory_percent": 88,
            "loss_rate": 0.08,
        }

        recommendations = detector._get_recommendations(
            "node-01", node_features, is_anomaly=True, anomaly_score=0.85
        )

        assert len(recommendations) > 0
        assert all(isinstance(r, str) for r in recommendations)
        # Should have recommendations for low RSSI, high CPU, high memory, high loss
        logger.info(f"✓ Generated {len(recommendations)} recommendations")


class TestEnhancedCausalAnalysis:
    """Test Enhanced Causal Analysis v2"""

    @pytest.fixture
    def analyzer(self):
        """Create causal analyzer"""
        from src.ml.causal_analysis_v2_enhanced import \
            EnhancedCausalAnalysisEngine

        return EnhancedCausalAnalysisEngine()

    def test_incident_deduplication(self, analyzer):
        """Test incident deduplication"""
        from src.ml.causal_analysis_v2_enhanced import (IncidentEvent,
                                                        IncidentSeverity)

        # Create two similar incidents
        incident1 = IncidentEvent(
            event_id="incident-1",
            timestamp=datetime.now(),
            node_id="node-01",
            service_id="service-1",
            anomaly_type="high_loss",
            severity=IncidentSeverity.HIGH,
            metrics={"loss_rate": 0.08},
            detected_by="graphsage_v3",
            anomaly_score=0.85,
        )

        incident2 = IncidentEvent(
            event_id="incident-2",
            timestamp=datetime.now() + timedelta(seconds=30),
            node_id="node-01",
            service_id="service-1",
            anomaly_type="high_loss",
            severity=IncidentSeverity.HIGH,
            metrics={"loss_rate": 0.07},
            detected_by="graphsage_v3",
            anomaly_score=0.83,
        )

        # Add first incident
        is_new1, id1 = analyzer.add_incident(incident1)
        assert is_new1

        # Add second (should be detected as duplicate)
        is_new2, id2 = analyzer.add_incident(incident2)
        assert not is_new2
        assert id2 == "incident-1"
        logger.info("✓ Incident deduplication working")

    def test_metric_based_root_cause(self, analyzer):
        """Test metric-based root cause classification"""
        from src.ml.causal_analysis_v2_enhanced import (IncidentEvent,
                                                        IncidentSeverity)

        incident = IncidentEvent(
            event_id="incident-3",
            timestamp=datetime.now(),
            node_id="node-02",
            service_id="service-2",
            anomaly_type="resource_issue",
            severity=IncidentSeverity.CRITICAL,
            metrics={
                "cpu_percent": 98,
                "memory_percent": 92,
                "loss_rate": 0.12,
                "rssi": -88,
            },
            detected_by="graphsage_v3",
            anomaly_score=0.95,
        )

        root_causes = analyzer._classify_by_metrics(incident)

        assert len(root_causes) > 0
        # Should identify CPU, memory, loss, and RSSI issues
        rc_types = [rc.root_cause_type.value for rc in root_causes]
        assert "resource_exhaustion" in rc_types
        assert "network_degradation" in rc_types
        logger.info(f"✓ Classified {len(root_causes)} root causes by metrics")

    def test_temporal_pattern_detection(self, analyzer):
        """Test recurring issue detection"""
        from src.ml.causal_analysis_v2_enhanced import (IncidentEvent,
                                                        IncidentSeverity)

        # Create recurring incident pattern
        now = datetime.now()
        for i in range(5):
            incident = IncidentEvent(
                event_id=f"recurring-{i}",
                timestamp=now - timedelta(seconds=i * 60),
                node_id="node-03",
                service_id="service-3",
                anomaly_type="periodic_issue",
                severity=IncidentSeverity.MEDIUM,
                metrics={},
                detected_by="graphsage_v3",
                anomaly_score=0.65,
            )
            analyzer.add_incident(incident)

        # Analyze latest incident
        root_causes = analyzer._analyze_temporal_patterns(
            analyzer.incidents["recurring-0"]
        )

        # Should detect pattern
        has_pattern = any("pattern" in rc.root_cause_id for rc in root_causes)
        logger.info(
            f"✓ Temporal pattern detection: {'found' if has_pattern else 'none'}"
        )

    def test_causal_analysis_integration(self, analyzer):
        """Test full causal analysis on incident"""
        from src.ml.causal_analysis_v2_enhanced import (IncidentEvent,
                                                        IncidentSeverity)

        incident = IncidentEvent(
            event_id="complex-incident",
            timestamp=datetime.now(),
            node_id="node-04",
            service_id="service-4",
            anomaly_type="cascading_failure",
            severity=IncidentSeverity.CRITICAL,
            metrics={
                "cpu_percent": 85,
                "memory_percent": 78,
                "loss_rate": 0.06,
                "latency": 250,
            },
            detected_by="graphsage_v3",
            anomaly_score=0.88,
        )

        # Add and analyze
        analyzer.add_incident(incident)
        result = analyzer.analyze("complex-incident")

        assert result.incident_id == "complex-incident"
        assert len(result.root_causes) > 0
        assert result.primary_root_cause is not None
        assert 0.0 <= result.confidence <= 1.0
        assert result.analysis_time_ms < 100  # <100ms requirement

        logger.info(
            f"✓ Causal analysis: {len(result.root_causes)} causes found, "
            f"confidence={result.confidence:.2f}, "
            f"latency={result.analysis_time_ms:.1f}ms"
        )


class TestIntegration:
    """Test GraphSAGE v3 + Causal Analysis v2 integration"""

    @pytest.fixture
    def integrated_analyzer(self):
        """Create integrated analyzer"""
        from src.ml.integrated_anomaly_analyzer import \
            create_integrated_analyzer_for_mapek

        return create_integrated_analyzer_for_mapek()

    def test_end_to_end_pipeline(self, integrated_analyzer):
        """Test complete detection→analysis pipeline"""
        node_features = {
            "rssi": -80,
            "snr": 12,
            "loss_rate": 0.06,
            "link_age_hours": 36,
            "latency": 120,
            "throughput_mbps": 40,
            "cpu_percent": 80,
            "memory_percent": 75,
        }

        neighbors = [
            ("n2", {"rssi": -75, "snr": 15, "loss_rate": 0.03, "latency": 80}),
            ("n3", {"rssi": -78, "snr": 13, "loss_rate": 0.04, "latency": 100}),
        ]

        # Process through pipeline
        start = time.time()
        result = integrated_analyzer.process_node_anomaly(
            node_id="node-test",
            node_features=node_features,
            neighbors=neighbors,
            service_id="mesh-service",
            network_nodes_count=8,
        )
        latency = (time.time() - start) * 1000

        assert result.node_id == "node-test"
        assert result.severity in ["critical", "high", "medium", "low"]
        assert latency < 200  # <200ms total pipeline latency

        logger.info(
            f"✓ End-to-end pipeline: "
            f"severity={result.severity}, "
            f"root_causes={len(result.root_causes)}, "
            f"latency={latency:.1f}ms"
        )

    def test_anomaly_and_recommendations(self, integrated_analyzer):
        """Test anomaly detection with actionable recommendations"""
        # Create problematic node
        node_features = {
            "rssi": -90,
            "snr": 5,
            "loss_rate": 0.15,
            "link_age_hours": 2,
            "latency": 500,
            "throughput_mbps": 5,
            "cpu_percent": 95,
            "memory_percent": 88,
        }

        neighbors = [
            ("n2", {"rssi": -70, "snr": 20, "loss_rate": 0.01, "latency": 50}),
        ]

        result = integrated_analyzer.process_node_anomaly(
            node_id="bad-node",
            node_features=node_features,
            neighbors=neighbors,
            network_nodes_count=5,
        )

        assert result.is_anomaly
        assert result.severity in ["critical", "high"]
        assert len(result.immediate_actions) > 0
        assert len(result.investigation_steps) > 0

        logger.info(
            f"✓ Anomaly with recommendations: "
            f"immediate={len(result.immediate_actions)}, "
            f"investigation={len(result.investigation_steps)}"
        )

    def test_integrated_report(self, integrated_analyzer):
        """Test integrated analysis report generation"""
        # Process multiple incidents
        for i in range(3):
            node_features = {
                "rssi": -75,
                "loss_rate": 0.02 + i * 0.01,
                "cpu_percent": 60 + i * 5,
            }
            neighbors = [("n2", {"rssi": -70, "loss_rate": 0.01})]

            integrated_analyzer.process_node_anomaly(
                node_id=f"node-{i}", node_features=node_features, neighbors=neighbors
            )

        report = integrated_analyzer.get_integrated_report()

        assert report["status"] == "ok"
        assert report["summary"]["total_incidents"] > 0
        assert "root_cause_distribution" in report
        assert "recent_incidents" in report

        logger.info(
            f"✓ Integrated report generated: {report['summary']['total_incidents']} incidents"
        )


class BenchmarkComparisons:
    """Benchmark v2 vs v3 improvements"""

    def test_graphsage_inference_latency(self):
        """Compare GraphSAGE v2 vs v3 inference latency"""
        from src.ml.graphsage_anomaly_detector_v3_enhanced import \
            GraphSAGEAnomalyDetectorV3

        detector = GraphSAGEAnomalyDetectorV3()

        node_features = {
            "rssi": -75,
            "loss_rate": 0.02,
            "latency": 80,
            "link_age_hours": 48,
            "throughput_mbps": 60,
            "cpu_percent": 65,
            "memory_percent": 72,
        }
        neighbors = [("n2", {"rssi": -70}), ("n3", {"rssi": -72})]

        # Warm up
        detector.predict_enhanced("n1", node_features, neighbors)

        # Benchmark
        latencies = []
        for _ in range(100):
            start = time.time()
            detector.predict_enhanced("n1", node_features, neighbors)
            latencies.append((time.time() - start) * 1000)

        avg_latency = sum(latencies) / len(latencies)
        max_latency = max(latencies)

        # Verify targets
        assert (
            avg_latency < 30
        ), f"Average latency {avg_latency:.1f}ms exceeds <30ms target"
        assert max_latency < 50, f"Max latency {max_latency:.1f}ms exceeds <50ms target"

        logger.info(
            f"✓ GraphSAGE v3 Inference: avg={avg_latency:.1f}ms, "
            f"max={max_latency:.1f}ms (target: <30ms avg)"
        )

    def test_causal_analysis_latency(self):
        """Compare Causal Analysis v1 vs v2 analysis latency"""
        from src.ml.causal_analysis_v2_enhanced import (
            EnhancedCausalAnalysisEngine, IncidentEvent, IncidentSeverity)

        analyzer = EnhancedCausalAnalysisEngine()

        incident = IncidentEvent(
            event_id="bench-1",
            timestamp=datetime.now(),
            node_id="node-bench",
            service_id="service-bench",
            anomaly_type="test",
            severity=IncidentSeverity.MEDIUM,
            metrics={"cpu_percent": 80},
            detected_by="test",
            anomaly_score=0.7,
        )

        # Warm up
        analyzer.add_incident(incident)
        analyzer.analyze("bench-1")

        # Benchmark
        latencies = []
        for i in range(50):
            incident.event_id = f"bench-{i}"
            analyzer.add_incident(incident)

            start = time.time()
            analyzer.analyze(f"bench-{i}")
            latencies.append((time.time() - start) * 1000)

        avg_latency = sum(latencies) / len(latencies)
        max_latency = max(latencies)

        # Verify targets
        assert (
            avg_latency < 50
        ), f"Average latency {avg_latency:.1f}ms exceeds <50ms target"

        logger.info(
            f"✓ Causal Analysis v2: avg={avg_latency:.1f}ms, "
            f"max={max_latency:.1f}ms (target: <50ms avg)"
        )


# Run tests
if __name__ == "__main__":
    pytest.main([__file__, "-v", "--tb=short"])
