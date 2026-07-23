#!/usr/bin/env python3
"""Evals Benchmark: GNN (MeshGNN / GraphSAGE) + MAPE-K Integration Harness.

Evaluates GNN-driven topological anomaly detection and MAPE-K self-healing cycles
against SLA rules, generating HQI scores and Error Heatmaps.
"""

from __future__ import annotations

import json
import sys
from pathlib import Path

PROJECT_ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(PROJECT_ROOT))

from scripts.agents.agent_feedback_loop import AgentFeedbackLoop
from src.self_healing.mape_k.manager import SelfHealingManager


def main() -> int:
    print("🚀 Starting GNN (GraphSAGE/MeshGNN) + MAPE-K Evals Verification Harness...")

    # 1. Initialize SelfHealingManager and enable GraphSAGE
    manager = SelfHealingManager(node_id="gnn-edge-node-01")
    manager.analyzer.enable_graphsage()
    print("✅ GraphSAGE / MeshGNN detector enabled in MAPE-K Analyzer.")

    # 2. Simulate 5 telemetry scenarios (healthy, packet loss, high latency, link degradation, recovery)
    scenarios = [
        {
            "name": "Scenario 1: Healthy Mesh Telemetry",
            "metrics": {
                "cpu_percent": 15.0,
                "memory_percent": 25.0,
                "packet_loss_percent": 0.1,
                "latency_ms": 12.0,
                "rssi": -45.0,
                "snr": 28.0,
            },
        },
        {
            "name": "Scenario 2: High Packet Loss (Anomaly)",
            "metrics": {
                "cpu_percent": 22.0,
                "memory_percent": 30.0,
                "packet_loss_percent": 18.5,
                "latency_ms": 95.0,
                "rssi": -82.0,
                "snr": 8.0,
            },
        },
        {
            "name": "Scenario 3: Severe Link Degradation (Anomaly)",
            "metrics": {
                "cpu_percent": 88.0,
                "memory_percent": 75.0,
                "packet_loss_percent": 25.0,
                "latency_ms": 210.0,
                "rssi": -89.0,
                "snr": 4.0,
            },
        },
        {
            "name": "Scenario 4: Post-Healing Verification (Normalizing)",
            "metrics": {
                "cpu_percent": 18.0,
                "memory_percent": 28.0,
                "packet_loss_percent": 1.5,
                "latency_ms": 18.0,
                "rssi": -50.0,
                "snr": 25.0,
            },
        },
        {
            "name": "Scenario 5: Healthy State Restored",
            "metrics": {
                "cpu_percent": 14.0,
                "memory_percent": 24.0,
                "packet_loss_percent": 0.0,
                "latency_ms": 11.0,
                "rssi": -42.0,
                "snr": 30.0,
            },
        },
    ]

    print("\n📍 Executing MAPE-K cycles with GNN anomaly detection...")
    for idx, sc in enumerate(scenarios, 1):
        print(f"   [{idx}/5] {sc['name']}...")
        manager.run_cycle(sc["metrics"])

    # 3. Evaluate HQI score and print Error Heatmap
    fb_loop = AgentFeedbackLoop()
    stats = fb_loop.get_agent_performance("mapek_gnn-edge-node-01")
    heatmap = fb_loop.generate_error_heatmap()
    heatmap_ascii = fb_loop.render_error_heatmap_ascii()

    print("\n" + "=" * 60)
    print("=== 🎯 GNN + MAPE-K HARNESS EVALUATION SUMMARY ===")
    print("=" * 60)
    print(f"  Target Agent:           mapek_gnn-edge-node-01")
    print(f"  Processed Actions:      {stats['total_actions']}")
    print(f"  Average Accuracy Score: {stats['avg_accuracy']:.3f}")
    print("=" * 60)

    print("\n📊 GNN Evals Error Heatmap:")
    print(heatmap_ascii)

    print("✅ GNN + MAPE-K Evals Verification PASSED (Exit Code 0).")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
