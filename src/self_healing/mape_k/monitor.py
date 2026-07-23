"""MAPE-K Monitor component."""

from __future__ import annotations

import logging
import time
from datetime import datetime
from typing import Any, Callable, Dict, List, Optional

from src.core.thinking.agent_thinking import AgentThinkingCoach

logger = logging.getLogger(__name__)


class MAPEKMonitor:
    """
    Monitor phase with feedback loop support.

    Uses adaptive thresholds from Knowledge base to improve
    detection accuracy and reduce false positives.

    Supports GraphSAGE v2 anomaly detector for advanced detection.
    Now supports DAO-managed thresholds via ThresholdManager.
    """

    def __init__(
        self, knowledge: Optional["MAPEKKnowledge"] = None, threshold_manager=None
    ):
        self.anomaly_detectors: List[Callable[[Dict], bool]] = []
        self.thinking_coach = AgentThinkingCoach(agent_id="mapek_monitor", role="monitoring")
        self.last_thinking_context: Dict[str, Any] = {}
        
        # Resolve via DI if not passed explicitly
        try:
            from src.core.di import get_container
            di = get_container()
            if not knowledge and di.has("knowledge"):
                knowledge = di.resolve("knowledge")
            if not threshold_manager and di.has("threshold_manager"):
                threshold_manager = di.resolve("threshold_manager")
        except ImportError:
            pass
            
        self.knowledge = knowledge
        self.threshold_manager = threshold_manager

        # Default thresholds (can be overridden by DAO)
        self.default_thresholds = {
            "cpu_percent": 90.0,
            "memory_percent": 85.0,
            "packet_loss_percent": 5.0,
        }

        # GraphSAGE v2 detector (optional, loaded on demand)
        self.graphsage_detector = None
        self.use_graphsage = False

    def register_detector(self, fn: Callable[[Dict], bool]):
        """Register custom anomaly detector."""
        self.anomaly_detectors.append(fn)

    def enable_graphsage(self, detector=None):
        """
        Enable GraphSAGE v2 anomaly detector.

        Args:
            detector: Optional GraphSAGE detector instance (created if None)
        """
        from src.ml.graphsage_anomaly_detector import (
            create_graphsage_detector_for_mapek)

        if detector is None:
            self.graphsage_detector = create_graphsage_detector_for_mapek()
        else:
            self.graphsage_detector = detector

        self.use_graphsage = True
        logger.info("GraphSAGE v2 detector enabled for Monitor phase")

    def check(self, metrics: Dict) -> Dict[str, Any]:
        """
        Check for anomalies and perform load forecasting.

        Returns:
            Dict with 'anomaly_detected' (bool) and 'scaling_recommended' (bool)
        """
        node_id = metrics.get("node_id", "unknown")
        redacted_metrics = dict(metrics)
        if "node_id" in redacted_metrics:
            redacted_metrics["node_id"] = "[REDACTED]"
        self.last_thinking_context = self.thinking_coach.prepare_task(
            {
                "task_type": "mapek_monitor_check",
                "goal": "Detect metric anomaly for self-healing cycle",
                "constraints": {"redact_node_ids": True},
                "metrics": redacted_metrics,
            }
        )

        # Get thresholds (priority: DAO > Knowledge > Default)
        if self.threshold_manager:
            cpu_threshold = self.threshold_manager.get_threshold("cpu_threshold", 90.0)
            memory_threshold = self.threshold_manager.get_threshold("memory_threshold", 85.0)
            packet_loss_threshold = self.threshold_manager.get_threshold("network_loss_threshold", 5.0)
        elif self.knowledge:
            cpu_threshold = self.knowledge.get_adjusted_threshold("cpu_percent", self.default_thresholds["cpu_percent"])
            memory_threshold = self.knowledge.get_adjusted_threshold("memory_percent", self.default_thresholds["memory_percent"])
            packet_loss_threshold = self.knowledge.get_adjusted_threshold("packet_loss_percent", self.default_thresholds["packet_loss_percent"])
        else:
            cpu_threshold = self.default_thresholds["cpu_percent"]
            memory_threshold = self.default_thresholds["memory_percent"]
            packet_loss_threshold = self.default_thresholds["packet_loss_percent"]

        # 1. Simple Threshold Check
        anomaly_detected = False
        issue = "Healthy"
        if metrics.get("cpu_percent", 0) > cpu_threshold:
            anomaly_detected = True
            issue = "High CPU"
        if metrics.get("memory_percent", 0) > memory_threshold:
            anomaly_detected = True
            issue = "High Memory"
        if metrics.get("packet_loss_percent", 0) > packet_loss_threshold:
            anomaly_detected = True
            issue = "High Packet Loss"

        # 2. Custom registered detectors
        for detector in self.anomaly_detectors:
            try:
                if detector(metrics):
                    anomaly_detected = True
                    if issue == "Healthy":
                        issue = "Custom Anomaly"
            except Exception as e:
                logger.warning(f"Custom detector error: {e}")

        # 3. GraphSAGE Enhanced Check
        scaling_recommended = False
        if self.use_graphsage and self.graphsage_detector:
            try:
                node_features = {
                    "rssi": metrics.get("rssi", -80.0),
                    "snr": metrics.get("snr", 10.0),
                    "loss_rate": metrics.get("packet_loss_percent", 0.0) / 100.0,
                    "link_age_seconds": metrics.get("link_age_seconds", 0.0),
                    "latency_ms": metrics.get("latency_ms", 0.0),
                    "throughput_mbps": metrics.get("throughput_mbps", 0.0),
                    "cpu": metrics.get("cpu_percent", 0.0) / 100.0,
                    "memory": metrics.get("memory_percent", 0.0) / 100.0,
                }
                if hasattr(self.graphsage_detector, "predict_with_causal"):
                    prediction, _causal = self.graphsage_detector.predict_with_causal(
                        node_id=node_id, node_features=node_features, neighbors=[]
                    )
                    if prediction.is_anomaly:
                        anomaly_detected = True
                        if issue == "Healthy":
                            issue = "GraphSAGE Anomaly"
                elif hasattr(self.graphsage_detector, "predict"):
                    prediction = self.graphsage_detector.predict(
                        node_id=node_id, node_features=node_features, neighbors=[]
                    )
                    if prediction.is_anomaly:
                        anomaly_detected = True
                        if issue == "Healthy":
                            issue = "GraphSAGE Anomaly"
            except Exception as e:
                logger.warning(f"GraphSAGE check failed: {e}")

        return {
            "anomaly_detected": anomaly_detected,
            "scaling_recommended": scaling_recommended,
            "issue": issue if anomaly_detected else ("Predicted Peak" if scaling_recommended else "Healthy")
        }

    def get_thinking_status(self) -> Dict[str, Any]:
        """Return thinking status for inspection."""
        return {
            "thinking": self.thinking_coach.prepare_task({"task_type": "status"}),
            "last_thinking_context": self.last_thinking_context,
        }


