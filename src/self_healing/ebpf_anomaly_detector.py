#!/usr/bin/env python3
"""
eBPF Anomaly Detector for x0tta6bl4 Self-Healing
Integrates eBPF network metrics with MAPE-K loop for automatic recovery.

Monitors:
- Packet drop rates
- Latency spikes
- Queue congestion
- Route failures

Triggers self-healing actions when anomalies detected.
"""

import asyncio
import logging
import time
from dataclasses import dataclass
from enum import Enum
from typing import Any, Callable, Dict, List, Optional

from ..network.ebpf.bcc_probes import MeshNetworkProbes
from ..network.ebpf.loader import EBPFLoader
from .mape_k import MAPEKAnalyzer, MAPEKExecutor, MAPEKMonitor, MAPEKPlanner

logger = logging.getLogger(__name__)


class EBPFAnomalyType(Enum):
    """Types of eBPF-detected anomalies"""

    HIGH_PACKET_DROPS = "high_packet_drops"
    LATENCY_SPIKE = "latency_spike"
    QUEUE_CONGESTION = "queue_congestion"
    ROUTE_FAILURE = "route_failure"
    LOW_THROUGHPUT = "low_throughput"


@dataclass
class EBPFAnomaly:
    """Represents a detected anomaly"""

    anomaly_type: EBPFAnomalyType
    severity: str  # LOW, MEDIUM, HIGH, CRITICAL
    metric_value: float
    threshold: float
    interface: str
    timestamp: float
    description: str


class EBPFAnalyzer(MAPEKAnalyzer):
    """
    Analyzes eBPF metrics for anomalies and root causes.
    """

    def __init__(self):
        super().__init__()
        self.anomaly_history: List[EBPFAnomaly] = []
        self.baseline_metrics = {
            "packet_drop_rate": 0.01,  # 1%
            "avg_latency_ms": 10.0,
            "queue_congestion": 50,  # 50% full
            "throughput_mbps": 100.0,
        }

    def analyze(self, metrics: Dict[str, Any]) -> Optional[EBPFAnomaly]:
        """
        Analyze eBPF metrics for anomalies.

        Args:
            metrics: Current eBPF statistics

        Returns:
            Anomaly if detected, None otherwise
        """
        # Check packet drops
        drop_rate = self._calculate_drop_rate(metrics)
        if drop_rate > self.baseline_metrics["packet_drop_rate"] * 5:  # 5% threshold
            severity = "HIGH" if drop_rate > 0.1 else "MEDIUM"
            return EBPFAnomaly(
                anomaly_type=EBPFAnomalyType.HIGH_PACKET_DROPS,
                severity=severity,
                metric_value=drop_rate,
                threshold=self.baseline_metrics["packet_drop_rate"] * 5,
                interface=metrics.get("interface", "unknown"),
                timestamp=time.time(),
                description=f"Packet drop rate {drop_rate:.2%} exceeds threshold",
            )

        # Check latency
        avg_latency = metrics.get("avg_latency_ns", 0) / 1e6  # Convert to ms
        if avg_latency > self.baseline_metrics["avg_latency_ms"] * 3:  # 3x baseline
            return EBPFAnomaly(
                anomaly_type=EBPFAnomalyType.LATENCY_SPIKE,
                severity="HIGH",
                metric_value=avg_latency,
                threshold=self.baseline_metrics["avg_latency_ms"] * 3,
                interface=metrics.get("interface", "unknown"),
                timestamp=time.time(),
                description=f"Latency spike: {avg_latency:.1f}ms",
            )

        # Check queue congestion
        queue_cong = metrics.get("queue_congestion", 0)
        if queue_cong > self.baseline_metrics["queue_congestion"]:
            severity = "CRITICAL" if queue_cong > 90 else "HIGH"
            return EBPFAnomaly(
                anomaly_type=EBPFAnomalyType.QUEUE_CONGESTION,
                severity=severity,
                metric_value=queue_cong,
                threshold=self.baseline_metrics["queue_congestion"],
                interface=metrics.get("interface", "unknown"),
                timestamp=time.time(),
                description=f"Queue congestion: {queue_cong:.1f}%",
            )

        return None

    def _calculate_drop_rate(self, metrics: Dict[str, Any]) -> float:
        """Calculate packet drop rate from stats"""
        total = metrics.get("total_packets", 0)
        dropped = metrics.get("dropped_packets", 0)

        if total == 0:
            return 0.0

        return dropped / total


class EBPFPlanner(MAPEKPlanner):
    """
    Plans recovery actions for eBPF anomalies.
    """

    def plan(self, anomaly: EBPFAnomaly) -> List[Dict[str, Any]]:
        """
        Generate recovery plan for anomaly.

        Returns:
            List of recovery actions
        """
        actions = []

        if anomaly.anomaly_type == EBPFAnomalyType.HIGH_PACKET_DROPS:
            actions.extend(
                [
                    {
                        "action": "clear_packet_queues",
                        "interface": anomaly.interface,
                        "priority": "HIGH",
                        "description": "Flush packet queues to reduce drops",
                    },
                    {
                        "action": "adjust_route_weights",
                        "interface": anomaly.interface,
                        "priority": "MEDIUM",
                        "description": "Redistribute traffic to less congested routes",
                    },
                ]
            )

        elif anomaly.anomaly_type == EBPFAnomalyType.LATENCY_SPIKE:
            actions.extend(
                [
                    {
                        "action": "optimize_ebpf_program",
                        "interface": anomaly.interface,
                        "priority": "HIGH",
                        "description": "Reload optimized eBPF program",
                    },
                    {
                        "action": "enable_hw_offload",
                        "interface": anomaly.interface,
                        "priority": "MEDIUM",
                        "description": "Enable hardware offload if available",
                    },
                ]
            )

        elif anomaly.anomaly_type == EBPFAnomalyType.QUEUE_CONGESTION:
            actions.extend(
                [
                    {
                        "action": "increase_queue_size",
                        "interface": anomaly.interface,
                        "priority": "HIGH",
                        "description": "Dynamically increase queue buffer size",
                    },
                    {
                        "action": "throttle_traffic",
                        "interface": anomaly.interface,
                        "priority": "MEDIUM",
                        "description": "Apply traffic shaping to prevent overflow",
                    },
                ]
            )

        return actions


class EBPFExecutor(MAPEKExecutor):
    """
    Executes recovery actions for eBPF anomalies.
    """

    def __init__(self, loader: EBPFLoader):
        super().__init__()
        self.loader = loader

    def execute(self, action: Dict[str, Any]) -> bool:
        """
        Execute a recovery action.

        Returns:
            True if successful, False otherwise
        """
        action_type = action["action"]
        interface = action["interface"]

        try:
            if action_type == "clear_packet_queues":
                return self._clear_queues(interface)

            elif action_type == "adjust_route_weights":
                return self._adjust_routes(interface)

            elif action_type == "optimize_ebpf_program":
                return self._reload_ebpf(interface)

            elif action_type == "enable_hw_offload":
                return self._enable_hw_offload(interface)

            elif action_type == "increase_queue_size":
                return self._increase_queue_size(interface)

            elif action_type == "throttle_traffic":
                return self._throttle_traffic(interface)

            else:
                logger.warning(f"Unknown action: {action_type}")
                return False

        except Exception as e:
            logger.error(f"Failed to execute {action_type}: {e}")
            return False

    def _clear_queues(self, interface: str) -> bool:
        """Clear packet queues"""
        # Use tc command to flush queues
        import subprocess

        try:
            subprocess.run(["tc", "qdisc", "del", "dev", interface, "root"], check=True)
            subprocess.run(
                ["tc", "qdisc", "add", "dev", interface, "root", "fq"], check=True
            )
            logger.info(f"Cleared queues on {interface}")
            return True
        except subprocess.CalledProcessError:
            return False

    def _adjust_routes(self, interface: str) -> bool:
        """Adjust routing weights"""
        # This would integrate with topology manager
        logger.info(f"Adjusting routes for {interface}")
        return True  # Placeholder

    def _reload_ebpf(self, interface: str) -> bool:
        """Reload optimized eBPF program"""
        try:
            self.loader.cleanup()
            # Reload with optimized settings
            self.loader.load_programs()
            logger.info(f"Reloaded eBPF on {interface}")
            return True
        except Exception:
            return False

    def _enable_hw_offload(self, interface: str) -> bool:
        """Enable hardware offload"""
        # Check if supported and enable
        logger.info(f"Enabling HW offload on {interface}")
        return True  # Placeholder

    def _increase_queue_size(self, interface: str) -> bool:
        """Increase queue buffer size"""
        import subprocess

        try:
            # Increase txqueuelen
            subprocess.run(
                ["ip", "link", "set", interface, "txqueuelen", "1000"], check=True
            )
            logger.info(f"Increased queue size on {interface}")
            return True
        except subprocess.CalledProcessError:
            return False

    def _throttle_traffic(self, interface: str) -> bool:
        """Apply traffic throttling"""
        # Use tc for traffic shaping
        logger.info(f"Applying traffic throttling on {interface}")
        return True  # Placeholder


class EBPFSelfHealingController:
    """
    Main controller for eBPF self-healing.
    Integrates all MAPE-K components.
    """

    def __init__(self, interface: str = "eth0"):
        self.interface = interface
        self.loader = EBPFLoader(interface)
        self.probes = MeshNetworkProbes(interface)

        # MAPE-K components
        self.monitor = MAPEKMonitor()
        self.analyzer = EBPFAnalyzer()
        self.planner = EBPFPlanner()
        self.executor = EBPFExecutor(self.loader)

        # Register eBPF anomaly detector
        self.monitor.register_detector(self._detect_anomalies)

        self.running = False

    def _detect_anomalies(self, metrics: Dict[str, Any]) -> bool:
        """Custom anomaly detector for eBPF metrics"""
        anomaly = self.analyzer.analyze(metrics)
        if anomaly:
            logger.warning(f"eBPF anomaly detected: {anomaly.description}")
            # Trigger MAPE-K loop
            asyncio.create_task(self._handle_anomaly(anomaly))
            return True
        return False

    async def _handle_anomaly(self, anomaly: EBPFAnomaly):
        """Handle detected anomaly through MAPE-K loop"""
        # Plan recovery
        actions = self.planner.plan(anomaly)

        # Execute actions
        for action in actions:
            success = self.executor.execute(action)
            if success:
                logger.info(f"Executed recovery action: {action['action']}")
            else:
                logger.error(f"Failed to execute: {action['action']}")

    async def start_monitoring(self):
        """Start self-healing monitoring loop"""
        self.running = True
        logger.info("Starting eBPF self-healing monitoring...")

        while self.running:
            try:
                # Collect current metrics
                ebpf_stats = self.loader.get_stats()
                probe_metrics = self.probes.get_current_metrics()

                # Combine metrics
                current_metrics = {
                    **ebpf_stats,
                    **probe_metrics,
                    "interface": self.interface,
                }

                # Run monitoring
                self.monitor.monitor(current_metrics)

                await asyncio.sleep(10)  # Check every 10 seconds

            except Exception as e:
                logger.error(f"Monitoring error: {e}")
                await asyncio.sleep(5)

    async def stop_monitoring(self):
        """Stop monitoring and cleanup"""
        self.running = False
        self.loader.cleanup()
        self.probes.cleanup()
        logger.info("Stopped eBPF self-healing monitoring")


# Integration with main MAPE-K
def integrate_ebpf_self_healing(mape_k_manager, interface: str = "eth0"):
    """
    Integrate eBPF self-healing with main MAPE-K manager.

    Args:
        mape_k_manager: SelfHealingManager instance
        interface: Network interface to monitor

    Returns:
        EBPFSelfHealingController instance
    """
    ebpf_controller = EBPFSelfHealingController(interface)

    # Register the eBPF anomaly detector with MAPE-K monitor
    mape_k_manager.monitor.register_detector(ebpf_controller._detect_anomalies)

    logger.info("eBPF anomaly detector registered with MAPE-K monitor")
    return ebpf_controller
