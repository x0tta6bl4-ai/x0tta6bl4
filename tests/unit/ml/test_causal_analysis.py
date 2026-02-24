"""
Unit tests for CausalAnalysisEngine — x0tta6bl4
Covers temporal correlation, dependency tracking, metric similarity, and root cause scoring.
"""

import unittest
from datetime import datetime, timedelta
from src.ml.causal_analysis import (
    CausalAnalysisEngine, IncidentEvent, IncidentSeverity, 
    CausalAnalysisResult, RootCause
)

class TestCausalAnalysis(unittest.TestCase):
    def setUp(self):
        self.engine = CausalAnalysisEngine(correlation_window_seconds=600)
        self.now = datetime.now()

    def _make_event(self, event_id, offset_sec=0, node_id="n1", service_id=None, metrics=None):
        return IncidentEvent(
            event_id=event_id,
            timestamp=self.now + timedelta(seconds=offset_sec),
            node_id=node_id,
            service_id=service_id,
            anomaly_type="high_cpu",
            severity=IncidentSeverity.MEDIUM,
            metrics=metrics or {"cpu_percent": 95.0},
            detected_by="graphsage",
            anomaly_score=0.8
        )

    def test_add_incident_and_correlation(self):
        # Event 1: Root cause (earlier)
        e1 = self._make_event("root", offset_sec=-100, metrics={"cpu_percent": 99.0})
        # Event 2: Symptom (later)
        e2 = self._make_event("symptom", offset_sec=0, metrics={"cpu_percent": 90.0})
        
        self.engine.add_incident(e1)
        self.engine.add_incident(e2)
        
        # Check if edge exists in causal graph
        self.assertTrue(self.engine.causal_graph.has_edge("root", "symptom"))
        edge_data = self.engine.causal_graph.get_edge_data("root", "symptom")
        self.assertEqual(edge_data["relationship_type"], "causes")

    def test_service_dependency_correlation(self):
        self.engine.service_dependencies = {"api": ["db"]} # api depends on db
        
        e_db = self._make_event("db_fail", offset_sec=-50, service_id="db")
        e_api = self._make_event("api_fail", offset_sec=0, service_id="api")
        
        self.engine.add_incident(e_db)
        self.engine.add_incident(e_api)
        
        self.assertTrue(self.engine.causal_graph.has_edge("db_fail", "api_fail"))
        edge = self.engine.causal_graph.get_edge_data("db_fail", "api_fail")
        # Confidence should be high due to dependency
        self.assertGreater(edge["confidence"], 0.6)

    def test_metric_correlation_logic(self):
        # Similar metrics
        m1 = {"cpu_percent": 90.0, "memory_percent": 20.0}
        m2 = {"cpu_percent": 95.0, "memory_percent": 25.0}
        corr = self.engine._check_metric_correlation(m1, m2)
        self.assertGreater(corr, 0.8)
        
        # Different metrics
        m3 = {"cpu_percent": 10.0, "memory_percent": 90.0}
        corr_low = self.engine._check_metric_correlation(m1, m3)
        self.assertLess(corr_low, 0.5)

    def test_analyze_root_cause_identification(self):
        # Chain: A -> B -> C
        e_a = self._make_event("A", offset_sec=-200, metrics={"cpu_percent": 99.0})
        e_b = self._make_event("B", offset_sec=-100)
        e_c = self._make_event("C", offset_sec=0)

        self.engine.add_incident(e_a)
        self.engine.add_incident(e_b)
        self.engine.add_incident(e_c)

        result = self.engine.analyze("C")

        self.assertEqual(result.incident_id, "C")
        self.assertGreater(len(result.root_causes), 0)
        # The algorithm identifies the highest-confidence direct predecessor as
        # root cause; B is the direct cause of C (1 hop, higher confidence).
        self.assertEqual(result.root_causes[0].event_id, "B")
        self.assertIn("B", result.event_chain)

    def test_classify_root_cause_types(self):
        # Test CPU
        e_cpu = self._make_event("cpu", metrics={"cpu_percent": 95.0})
        self.assertEqual(self.engine._classify_root_cause(e_cpu), "High CPU Usage")
        
        # Test Memory
        e_mem = self._make_event("mem", metrics={"memory_percent": 90.0})
        self.assertEqual(self.engine._classify_root_cause(e_mem), "Memory Leak / High Memory Usage")
        
        # Test Network
        e_net = self._make_event("net", metrics={"packet_loss_percent": 10.0})
        self.assertEqual(self.engine._classify_root_cause(e_net), "Network Packet Loss")

    def test_analyze_with_no_path(self):
        e1 = self._make_event("unrelated", offset_sec=-1000) # Outside window
        e2 = self._make_event("target", offset_sec=0)
        
        self.engine.add_incident(e1)
        self.engine.add_incident(e2)
        
        result = self.engine.analyze("target")
        # Should only have itself as root cause if no edges
        self.assertEqual(len(result.root_causes), 1)
        self.assertEqual(result.root_causes[0].event_id, "target")

if __name__ == "__main__":
    unittest.main()
