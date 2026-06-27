#!/usr/bin/env python3
"""
Test script for eBPF Self-Healing integration with MAPE-K.

Demonstrates automatic recovery from network anomalies detected by eBPF.
"""

import asyncio
import logging
import time
from src.self_healing.mape_k import SelfHealingManager

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

async def simulate_network_anomaly():
    """Simulate a network anomaly that eBPF would detect"""
    logger.info("🔴 Simulating network anomaly...")

    # Create mock eBPF metrics that would trigger anomaly
    mock_ebpf_metrics = {
        'total_packets': 10000,
        'dropped_packets': 600,  # 6% drop rate - above threshold
        'passed_packets': 9400,
        'interface': 'eth0',
        'avg_latency_ns': 15000000,  # 15ms - normal
        'queue_congestion': 30  # 30% - normal
    }

    return mock_ebpf_metrics

async def test_ebpf_self_healing():
    """Test eBPF self-healing integration"""
    logger.info("🧪 Testing eBPF Self-Healing with MAPE-K")

    # Initialize MAPE-K manager
    manager = SelfHealingManager(node_id="test_node")

    # Integrate eBPF self-healing
    ebpf_controller = manager.integrate_ebpf_self_healing(interface="eth0")

    if not ebpf_controller:
        logger.error("❌ eBPF integration failed")
        return

    # Start monitoring in background
    monitoring_task = asyncio.create_task(ebpf_controller.start_monitoring())

    try:
        # Wait for initialization
        await asyncio.sleep(2)

        # Simulate network anomaly
        anomaly_metrics = await simulate_network_anomaly()

        # Manually trigger detection (in real scenario, this comes from eBPF)
        anomaly_detected = ebpf_controller._detect_anomalies(anomaly_metrics)

        if anomaly_detected:
            logger.info("✅ Anomaly detected by eBPF detector")

            # Wait for self-healing actions
            await asyncio.sleep(5)

            logger.info("✅ Self-healing completed")
        else:
            logger.warning("⚠️ Anomaly not detected")

        # Get feedback stats
        stats = manager.get_feedback_stats()
        logger.info(f"📊 Feedback stats: {stats}")

    finally:
        # Stop monitoring
        await ebpf_controller.stop_monitoring()
        monitoring_task.cancel()

        try:
            await monitoring_task
        except asyncio.CancelledError:
            pass

if __name__ == '__main__':
    asyncio.run(test_ebpf_self_healing())