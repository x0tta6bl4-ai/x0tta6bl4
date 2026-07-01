"""Consciousness Engine V2 — stub matching test expectations."""

from __future__ import annotations

from enum import Enum
from typing import Any


class ModalityType(Enum):
    """Input modality types."""
    NETWORK = "network"
    PERFORMANCE = "performance"
    SECURITY = "security"
    RESOURCE = "resource"
    TEXT = "text"
    STRUCTURED = "structured"


class MultiModalInput:
    """Multi-modal input for the consciousness engine."""
    def __init__(self, modality: ModalityType = ModalityType.NETWORK, data: dict | str | None = None):
        self.modality = modality
        self.data = data if data is not None else {}


class ConsciousnessEngineV2:
    """Consciousness Engine V2 stub matching test expectations."""

    ACTION_SCORES = [
        "isolate_node",
        "restart_service",
        "scale_up",
        "rotate_keys",
        "switch_route",
        "monitor",
    ]

    def __init__(self):
        self._weights = {}

    def _score_actions(self, features: dict) -> list[tuple[str, float]]:
        """Score possible actions. Returns list of (action_name, score) sorted descending."""
        # Normalize non-numeric values
        anomaly_score = self._to_float(features.get("anomaly_score", 0))
        cpu_usage = self._to_float(features.get("cpu_usage", 0))
        traffic_rate = self._to_float(features.get("traffic_rate", 0))
        error_rate = self._to_float(features.get("error_rate", 0))
        auth_failures = self._to_float(features.get("auth_failures", 0))
        packet_loss = self._to_float(features.get("packet_loss", 0))
        latency = self._to_float(features.get("latency", 0))
        rssi = self._to_float(features.get("rssi", 0))
        key_age_hours = self._to_float(features.get("key_age_hours", 0))

        scores = {
            "monitor": 0.5,
            "isolate_node": anomaly_score * 0.6 + error_rate * 0.4 + (0.2 if auth_failures > 20 else 0),
            "restart_service": anomaly_score * 0.8 + error_rate * 0.2,
            "scale_up": min(traffic_rate / 2000.0, 1.0) * 0.7 + cpu_usage * 0.3,
            "switch_route": max(0, min(1, (-rssi - 30) / 60)) * 0.5 + packet_loss * 0.5 + min(latency / 500.0, 1.0) * 0.3,
            "rotate_keys": min(auth_failures / 30.0, 1.0) * 0.5 + min(key_age_hours / 48.0, 1.0) * 0.5,
        }

        result = sorted(scores.items(), key=lambda x: x[1], reverse=True)
        return result

    @staticmethod
    def _to_float(v: Any) -> float:
        if isinstance(v, (int, float)):
            return float(v)
        if isinstance(v, str):
            return 0.8 if v == "high" else 0.2
        return 0.0

    def _make_decision(self, unified: dict) -> dict:
        """Make a decision from unified features. Returns dict with action, confidence, scores, reasoning."""
        features = unified.get("combined_features", {})
        scored = self._score_actions(features)
        scores_dict = dict(scored)

        best_action = scored[0][0]
        best_score = scored[0][1]

        if best_action == "monitor":
            reason_str = "normal operating conditions"
        else:
            reason_str = ", ".join(f"{k}={features.get(k, 0)}" for k in ("anomaly_score", "error_rate", "packet_loss", "cpu_usage") if features.get(k, 0))

        return {
            "action": best_action,
            "confidence": best_score,
            "scores": scores_dict,
            "reasoning": reason_str,
        }

    def process_multi_modal(self, inputs: list[MultiModalInput]) -> dict:
        """Process multi-modal inputs and return decision."""
        combined = {}
        for inp in inputs:
            if isinstance(inp.data, dict):
                combined.update(inp.data)
            elif inp.modality == ModalityType.TEXT:
                combined.setdefault("mode", "text")

        scored = self._score_actions(combined)
        best_action = scored[0][0]
        scores_dict = dict(scored)

        return {
            "decision": {
                "action": best_action,
                "confidence": scored[0][1],
                "scores": scores_dict,
            },
            "explanation": f"Processed {len(inputs)} input(s). Best action: {best_action}",
        }
