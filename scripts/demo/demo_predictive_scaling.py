"""
Demo: Predictive Scaling via GraphSAGE Load Forecasting
======================================================

This script demonstrates how x0tta6bl4 uses GraphSAGE load forecasting 
to proactively scale resources BEFORE a peak is reached.
"""

import asyncio
import logging
import sys
import os

# Add project root to path
sys.path.append(os.getcwd())

from src.self_healing.mape_k_integrated import IntegratedMAPEKCycle
from src.ml.graphsage_anomaly_detector_v3_enhanced import create_graphsage_v3_for_mapek

# Configure logging
logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(name)s - %(levelname)s - %(message)s')
logger = logging.getLogger("Predictive-Scaling-Demo")

async def run_demo():
    logger.info("🚀 Starting Predictive Scaling Demo")
    
    # 1. Setup Integrated MAPE-K with GraphSAGE v3
    cycle = IntegratedMAPEKCycle(enable_observe_mode=False)
    detector = create_graphsage_v3_for_mapek()
    cycle.monitor.enable_graphsage(detector=detector)
    
    node_id = "proactive-node-01"
    
    # 2. Simulate rising load (Trend)
    # Samples: 0.1, 0.2, 0.3, 0.4, 0.5, 0.6
    loads = [10, 20, 30, 40, 50, 60] # Rising CPU %
    
    logger.info("📈 Step 1: Simulating rising load trend...")
    
    for i, cpu in enumerate(loads):
        metrics = {
            "node_id": node_id,
            "cpu_percent": cpu,
            "memory_percent": 40,
            "packet_loss_percent": 0.1,
            "latency_ms": 15
        }
        
        logger.info(f"📊 Observation {i+1}: CPU={cpu}%")
        result = cycle.run_cycle(metrics)
        
        if result.get("scaling_recommended"):
            logger.info("🔮 SUCCESS: Proactive scaling triggered!")
            logger.info(f"🎯 Strategy: {result['planner_results']['strategy']}")
            logger.info(f"⏰ Estimated Recovery: {result['planner_results']['estimated_recovery_time']}s")
            break
        
        await asyncio.sleep(0.1)

    logger.info("✅ Demo complete.")

if __name__ == "__main__":
    asyncio.run(run_demo())
