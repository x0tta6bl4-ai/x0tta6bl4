"""
Monitor phase for MAPE-K Self-Healing.
"""

import hashlib
import logging
from typing import Any, Callable, Dict, List, Optional

logger = logging.getLogger(__name__)

from src.core.agent_thinking import AgentThinkingCoach
from src.core.mape_k.interfaces import MonitorInterface


def _hash_value(value: Any) -> Optional[str]:
    if value is None:
        return None
    text = str(value)
    if not text:
        return None
    return hashlib.sha256(text.encode("utf-8", errors="replace")).hexdigest()


class MAPEKMonitor(MonitorInterface):
    """
    Monitor phase with feedback loop support.

    Uses adaptive thresholds from Knowledge base to improve
    detection accuracy and reduce false positives.

    Supports GraphSAGE v2 anomaly detector for advanced detection.
    Now supports DAO-managed thresholds via ThresholdManager.
    """

    def __init__(self, knowledge: Optional[Any] = None, threshold_manager=None):
        self.anomaly_detectors: List[Callable[[Dict], bool]] = []
        self.knowledge = knowledge
        self.threshold_manager = threshold_manager
        self.thinking_coach = AgentThinkingCoach(
            agent_id="self-healing-mapek-monitor",
            role="monitoring",
            capabilities=("mape_k", "causal_analysis", "security"),
        )
        self.last_thinking_context: Dict[str, Any] = {}

        # Default thresholds (can be overridden by DAO)
        self.default_thresholds = {
            "cpu_percent": 90.0,
            "memory_percent": 85.0,
            "packet_loss_percent": 5.0,
        }

        # GraphSAGE v2 detector (optional, loaded on demand)
        self.graphsage_detector = None
        self.use_graphsage = False

    def _prepare_thinking_context(
        self,
        *,
        metrics: Dict[str, Any],
        thresholds: Optional[Dict[str, float]] = None,
        result: Optional[Dict[str, Any]] = None,
        error_type: Optional[str] = None,
    ) -> Dict[str, Any]:
        """Prepare redacted thinking context for monitor decisions."""
        numeric_metrics = {
            str(key): round(float(value), 4)
            for key, value in metrics.items()
            if isinstance(value, (int, float)) and not isinstance(value, bool)
        }
        context: Dict[str, Any] = {
            "type": "mapek_monitor_check",
            "goal": "detect anomalies from bounded metrics and adaptive thresholds",
            "node_id_hash": _hash_value(metrics.get("node_id")),
            "node_id_redacted": "node_id" in metrics,
            "metric_keys": sorted(str(key) for key in metrics),
            "numeric_metrics": numeric_metrics,
            "thresholds": thresholds or {},
            "detector_count": len(self.anomaly_detectors),
            "graphsage_enabled": bool(self.use_graphsage),
            "threshold_source": (
                "dao"
                if self.threshold_manager
                else "knowledge" if self.knowledge else "default"
            ),
            "result": dict(result or {}),
            "error_type": error_type,
            "constraints": {
                "redact_node_ids": True,
                "only_use_bounded_metric_summary": True,
                "separate_local_anomaly_detection_from_recovery_claims": True,
            },
            "safety_boundary": (
                "Do not expose raw node identifiers or claim recovery, dataplane "
                "restoration, production readiness, or root cause finality from the "
                "monitor phase alone."
            ),
        }
        self.last_thinking_context = self.thinking_coach.prepare_task(context)
        return self.last_thinking_context

    def get_thinking_status(self) -> Dict[str, Any]:
        """Expose thinking profile and latest redacted monitor context."""
        return {
            "thinking": self.thinking_coach.status(),
            "last_thinking_context": self.last_thinking_context,
        }

    def register_detector(self, fn: Callable[[Dict], bool]):
        """Register custom anomaly detector."""
        self.anomaly_detectors.append(fn)

    def enable_graphsage(self, detector=None):
        """
        Enable GraphSAGE v2 anomaly detector.
        """
        from src.ml.graphsage_anomaly_detector import (
            create_graphsage_detector_for_mapek,
        )

        if detector is None:
            self.graphsage_detector = create_graphsage_detector_for_mapek()
        else:
            self.graphsage_detector = detector

        self.use_graphsage = True
        logger.info("GraphSAGE v2 detector enabled for Monitor phase")

    def check(self, metrics: Dict) -> Dict[str, Any]:
        """
        Check for anomalies and perform load forecasting.
        """
        node_id = metrics.get("node_id", "unknown")

        # Get thresholds (priority: DAO > Knowledge > Default)
        if self.threshold_manager:
            cpu_threshold = self.threshold_manager.get_threshold("cpu_threshold", 90.0)
            memory_threshold = self.threshold_manager.get_threshold(
                "memory_threshold", 85.0
            )
            packet_loss_threshold = self.threshold_manager.get_threshold(
                "network_loss_threshold", 5.0
            )
        elif self.knowledge:
            cpu_threshold = self.knowledge.get_adjusted_threshold(
                "cpu_percent", self.default_thresholds["cpu_percent"]
            )
            memory_threshold = self.knowledge.get_adjusted_threshold(
                "memory_percent", self.default_thresholds["memory_percent"]
            )
            packet_loss_threshold = self.knowledge.get_adjusted_threshold(
                "packet_loss_percent", self.default_thresholds["packet_loss_percent"]
            )
        else:
            cpu_threshold = self.default_thresholds["cpu_percent"]
            memory_threshold = self.default_thresholds["memory_percent"]
            packet_loss_threshold = self.default_thresholds["packet_loss_percent"]
        thresholds = {
            "cpu_percent": float(cpu_threshold),
            "memory_percent": float(memory_threshold),
            "packet_loss_percent": float(packet_loss_threshold),
        }

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

        result = {
            "anomaly_detected": anomaly_detected,
            "scaling_recommended": scaling_recommended,
            "issue": (
                issue
                if anomaly_detected
                else ("Predicted Peak" if scaling_recommended else "Healthy")
            ),
        }
        self._prepare_thinking_context(
            metrics=metrics,
            thresholds=thresholds,
            result=result,
        )
        return result
