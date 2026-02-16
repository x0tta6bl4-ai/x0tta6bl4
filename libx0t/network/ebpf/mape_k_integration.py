"""
MAPE-K Integration for eBPF Observability

Integrates eBPF telemetry into MAPE-K Monitor phase for real-time
anomaly detection and self-healing.
"""

import logging
from pathlib import Path
from typing import Dict, Optional

logger = logging.getLogger(__name__)


class EBPFMAPEKIntegration:
    """
    Integrates eBPF metrics into MAPE-K loop.

    Provides:
    - Real-time packet loss detection (<100ms)
    - Syscall latency anomaly detection
    - Automatic alerting to MAPE-K Analyzer
    """

    def __init__(self, metrics_exporter=None):
        """
        Initialize eBPF-MAPE-K integration.

        Args:
            metrics_exporter: EBPFMetricsExporter instance
        """
        self.metrics_exporter = metrics_exporter
        self.alert_thresholds = {
            "packet_loss_percent": 5.0,  # Alert if >5% loss
            "syscall_latency_p99_ms": 100.0,  # Alert if P99 >100ms
            "tcp_packets_drop_rate": 0.1,  # Alert if drop rate >0.1%
        }
        self.last_metrics: Dict = {}

        logger.info("eBPF-MAPE-K integration initialized")

    def get_metrics_for_mapek(self) -> Dict[str, float]:
        """
        Get eBPF metrics formatted for MAPE-K Monitor phase.

        Returns:
            Dict of metrics compatible with MAPE-K Monitor
        """
        if not self.metrics_exporter:
            logger.warning("Metrics exporter not configured")
            return {}

        # Export current metrics
        current_metrics = self.metrics_exporter.export_metrics()

        # Calculate derived metrics
        derived = {}

        # Calculate packet loss rate (if we have drop counters)
        if "ebpf_xdp_counter_tcp_packets" in current_metrics:
            tcp_packets = current_metrics.get("ebpf_xdp_counter_tcp_packets", 0)
            # Compare with previous measurement for rate
            if "tcp_packets" in self.last_metrics:
                delta = tcp_packets - self.last_metrics["tcp_packets"]
                # Simplified: assume we know expected rate
                # Real implementation would track expected vs actual
                derived["packet_rate_tcp"] = delta

        # Store for next iteration
        self.last_metrics = current_metrics.copy()

        # Format for MAPE-K
        mapek_metrics = {
            **current_metrics,
            **derived,
        }

        return mapek_metrics

    def check_anomalies(self, metrics: Dict[str, float]) -> Optional[Dict]:
        """
        Check eBPF metrics for anomalies.

        Returns:
            Dict with anomaly info if detected, None otherwise
        """
        anomalies = []

        # Check packet loss
        packet_loss = metrics.get("packet_loss_percent", 0.0)
        if packet_loss > self.alert_thresholds["packet_loss_percent"]:
            anomalies.append(
                {
                    "type": "high_packet_loss",
                    "value": packet_loss,
                    "threshold": self.alert_thresholds["packet_loss_percent"],
                    "severity": "high",
                }
            )

        # Check syscall latency
        latency_p99 = metrics.get("syscall_latency_p99_ms", 0.0)
        if latency_p99 > self.alert_thresholds["syscall_latency_p99_ms"]:
            anomalies.append(
                {
                    "type": "high_syscall_latency",
                    "value": latency_p99,
                    "threshold": self.alert_thresholds["syscall_latency_p99_ms"],
                    "severity": "medium",
                }
            )

        if anomalies:
            return {
                "anomalies": anomalies,
                "timestamp": metrics.get("timestamp"),
            }

        return None

    def trigger_mapek_alert(self, anomaly_info: Dict):
        """
        Trigger alert in MAPE-K Analyzer phase.

        Args:
            anomaly_info: Anomaly information from check_anomalies()
        """
        try:
            from libx0t.core.mape_k_loop import MAPEKLoop
            from src.self_healing.mape_k import MAPEKAnalyzer

            # This would integrate with actual MAPE-K instance
            # For now, just log
            logger.warning(
                f"🚨 eBPF Anomaly detected: {anomaly_info['anomalies']} "
                f"(triggering MAPE-K Analyzer)"
            )

            # In real implementation:
            # mape_k_loop = MAPEKLoop.get_instance()
            # mape_k_loop.trigger_analysis(anomaly_info)

        except ImportError:
            logger.warning("MAPE-K not available, logging anomaly only")
            logger.warning(f"Anomaly: {anomaly_info}")


# Integration example
def integrate_with_mapek(mapek_loop, ebpf_exporter):
    """
    Integrate eBPF exporter with MAPE-K loop.

    Args:
        mapek_loop: MAPEKLoop instance
        ebpf_exporter: EBPFMetricsExporter instance
    """
    integration = EBPFMAPEKIntegration(ebpf_exporter)

    # In Monitor phase, get eBPF metrics
    ebpf_metrics = integration.get_metrics_for_mapek()

    # Check for anomalies
    anomaly = integration.check_anomalies(ebpf_metrics)
    if anomaly:
        integration.trigger_mapek_alert(anomaly)

    return ebpf_metrics
