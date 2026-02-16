"""Unit tests for MeshShield quarantine engine."""

import unittest
from datetime import datetime, timedelta

from src.security.mesh_shield import (MeshShield, QuarantineReason,
                                      ThreatIndicator, ThreatLevel)


class TestMeshShield(unittest.TestCase):
    """Test MeshShield functionality."""

    def setUp(self):
        self.shield = MeshShield()

    def test_report_low_anomaly_no_quarantine(self):
        """Low anomaly score should not trigger quarantine."""
        result = self.shield.report_indicator(
            ThreatIndicator(node_id="node-1", indicator_type="anomaly_score", value=0.3)
        )
        self.assertIsNone(result)
        self.assertFalse(self.shield.is_quarantined("node-1"))

    def test_report_high_anomaly_triggers_quarantine(self):
        """High anomaly score should trigger quarantine."""
        result = self.shield.report_indicator(
            ThreatIndicator(
                node_id="node-1", indicator_type="anomaly_score", value=0.95
            )
        )
        self.assertEqual(result, ThreatLevel.CRITICAL)
        self.assertTrue(self.shield.is_quarantined("node-1"))

    def test_manual_quarantine(self):
        """Manual quarantine should work."""
        record = self.shield.quarantine_node(
            "node-2", QuarantineReason.MANUAL, ThreatLevel.HIGH
        )
        self.assertTrue(self.shield.is_quarantined("node-2"))
        self.assertEqual(record.reason, QuarantineReason.MANUAL)

    def test_release_node(self):
        """Released node should no longer be quarantined."""
        self.shield.quarantine_node("node-3", QuarantineReason.MANUAL)
        self.assertTrue(self.shield.is_quarantined("node-3"))

        released = self.shield.release_node("node-3", "investigation_complete")
        self.assertTrue(released)
        self.assertFalse(self.shield.is_quarantined("node-3"))

    def test_release_nonexistent_node(self):
        """Releasing non-quarantined node should return False."""
        released = self.shield.release_node("node-999")
        self.assertFalse(released)

    def test_replay_attack_detection(self):
        """Multiple replay attacks should trigger critical quarantine."""
        for _ in range(3):
            self.shield.report_indicator(
                ThreatIndicator(
                    node_id="node-4", indicator_type="replay_attack", value=1.0
                )
            )
        self.assertTrue(self.shield.is_quarantined("node-4"))

    def test_metrics_tracking(self):
        """Metrics should be tracked correctly."""
        self.shield.quarantine_node("node-5", QuarantineReason.MANUAL)
        self.shield.release_node("node-5", "false_positive")

        metrics = self.shield.get_metrics()
        self.assertEqual(metrics["quarantines_total"], 1)
        self.assertEqual(metrics["releases_total"], 1)
        self.assertGreater(metrics["false_positive_rate"], 0)

    def test_list_quarantined(self):
        """Should list all quarantined nodes."""
        self.shield.quarantine_node("node-a", QuarantineReason.MANUAL)
        self.shield.quarantine_node("node-b", QuarantineReason.MANUAL)

        quarantined = self.shield.list_quarantined()
        self.assertEqual(len(quarantined), 2)


class TestThreatAnalysis(unittest.TestCase):
    """Test threat level analysis."""

    def setUp(self):
        self.shield = MeshShield()

    def test_no_indicators_returns_none(self):
        """No indicators should return NONE threat level."""
        level = self.shield._analyze_threat("unknown-node")
        self.assertEqual(level, ThreatLevel.NONE)

    def test_cert_failures_trigger_high(self):
        """Certificate failures should trigger HIGH threat."""
        for _ in range(2):
            self.shield.report_indicator(
                ThreatIndicator(
                    node_id="node-cert", indicator_type="cert_failure", value=1.0
                )
            )
        self.assertTrue(self.shield.is_quarantined("node-cert"))


if __name__ == "__main__":
    unittest.main()
