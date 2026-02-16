"""
Unit tests for ConsciousnessEngineV2 multi-objective decision scoring.
"""

import pytest

from src.core.consciousness_v2 import (ConsciousnessEngineV2, ModalityType,
                                       MultiModalInput)


class TestMultiObjectiveScoring:
    """Tests for _make_decision weighted scoring."""

    def setup_method(self):
        self.engine = ConsciousnessEngineV2()

    def _decide(self, features):
        """Helper: run _make_decision with given features."""
        unified = {"combined_features": features}
        return self.engine._make_decision(unified)

    # --- Action selection ---

    def test_high_anomaly_triggers_restart(self):
        result = self._decide({"anomaly_score": 0.9, "error_rate": 0.6})
        assert result["action"] == "restart_service"
        assert result["confidence"] > 0.5

    def test_high_traffic_triggers_scale_up(self):
        result = self._decide({"traffic_rate": 2000, "cpu_usage": 0.88})
        assert result["action"] == "scale_up"

    def test_key_age_triggers_rotate(self):
        result = self._decide({"key_age_hours": 48, "auth_failures": 15})
        assert result["action"] == "rotate_keys"

    def test_high_loss_triggers_switch_route(self):
        result = self._decide({"packet_loss": 0.5, "latency": 400, "rssi": -85})
        assert result["action"] == "switch_route"

    def test_extreme_anomaly_triggers_isolate(self):
        result = self._decide(
            {"anomaly_score": 0.95, "auth_failures": 30, "error_rate": 0.9}
        )
        assert result["action"] == "isolate_node"

    def test_normal_features_monitor(self):
        result = self._decide(
            {
                "anomaly_score": 0.1,
                "traffic_rate": 100,
                "cpu_usage": 0.3,
                "latency": 20,
            }
        )
        assert result["action"] == "monitor"

    def test_empty_features_monitor(self):
        result = self._decide({})
        assert result["action"] == "monitor"

    # --- Scoring properties ---

    def test_scores_dict_present(self):
        result = self._decide({"anomaly_score": 0.9})
        assert "scores" in result
        assert isinstance(result["scores"], dict)
        assert "restart_service" in result["scores"]

    def test_confidence_bounded(self):
        for features in [
            {"anomaly_score": 0.99, "error_rate": 0.99},
            {"traffic_rate": 10000},
            {},
        ]:
            result = self._decide(features)
            assert 0.0 <= result["confidence"] <= 1.0

    def test_higher_signal_higher_score(self):
        low = self._decide({"anomaly_score": 0.5})
        high = self._decide({"anomaly_score": 0.95})
        assert high["scores"]["restart_service"] > low["scores"]["restart_service"]

    def test_multiple_signals_amplify(self):
        single = self._decide({"anomaly_score": 0.8})
        multi = self._decide(
            {"anomaly_score": 0.8, "error_rate": 0.6, "packet_loss": 0.4}
        )
        assert multi["scores"]["restart_service"] > single["scores"]["restart_service"]

    # --- Reasoning ---

    def test_reasoning_contains_features(self):
        result = self._decide({"anomaly_score": 0.9, "error_rate": 0.7})
        assert "anomaly_score" in result["reasoning"]

    def test_monitor_reasoning(self):
        result = self._decide({"cpu_usage": 0.1})
        assert "normal" in result["reasoning"].lower()


class TestScoreActions:
    """Tests for _score_actions internals."""

    def setup_method(self):
        self.engine = ConsciousnessEngineV2()

    def test_all_actions_scored(self):
        scored = self.engine._score_actions({"anomaly_score": 0.5})
        action_names = [a for a, _ in scored]
        for action in self.engine.ACTION_SCORES:
            assert action in action_names

    def test_sorted_descending(self):
        scored = self.engine._score_actions({"anomaly_score": 0.8, "traffic_rate": 500})
        scores = [s for _, s in scored]
        assert scores == sorted(scores, reverse=True)

    def test_non_numeric_features_ignored(self):
        scored = self.engine._score_actions({"anomaly_score": "high", "cpu_usage": 0.9})
        # Should not crash, and cpu_usage should still contribute
        assert any(s > 0 for _, s in scored)

    def test_negative_threshold_rssi(self):
        """RSSI has negative threshold: worse (more negative) → higher score."""
        good_rssi = self.engine._score_actions({"rssi": -40})
        bad_rssi = self.engine._score_actions({"rssi": -90})
        good_switch = dict(good_rssi)["switch_route"]
        bad_switch = dict(bad_rssi)["switch_route"]
        assert bad_switch > good_switch


class TestEndToEndDecision:
    """Integration test: multi-modal → decision → explanation pipeline."""

    def test_structured_input_flows_to_decision(self):
        engine = ConsciousnessEngineV2()
        inputs = [
            MultiModalInput(
                modality=ModalityType.STRUCTURED,
                data={
                    "anomaly_score": 0.85,
                    "error_rate": 0.6,
                    "cpu_usage": 0.7,
                },
            )
        ]
        result = engine.process_multi_modal(inputs)
        assert "decision" in result
        assert "explanation" in result
        assert result["decision"]["action"] in (
            "restart_service",
            "isolate_node",
            "scale_up",
            "rotate_keys",
            "switch_route",
            "monitor",
        )

    def test_text_input_defaults_to_monitor(self):
        engine = ConsciousnessEngineV2()
        inputs = [MultiModalInput(modality=ModalityType.TEXT, data="hello world")]
        result = engine.process_multi_modal(inputs)
        assert result["decision"]["action"] == "monitor"
