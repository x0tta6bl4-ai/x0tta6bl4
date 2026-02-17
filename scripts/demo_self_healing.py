import asyncio
import logging
import time
import os
import signal
from src.monitoring.metrics import record_self_healing_event, record_mttr

logging.basicConfig(level=logging.INFO, format="%(asctime)s [%(levelname)s] %(message)s")
logger = logging.getLogger("SelfHealingDemo")

async def run_demo():
    logger.info("🚀 Starting Self-Healing Demonstration")
    
    node_id = "ingress-01"
    target_node = "mesh-01"
    
    # 1. Simulate active session
    logger.info(f"📡 Node {node_id} is communicating with {target_node} via {target_node}")
    
    # 2. Simulate failure
    logger.info(f"💥 Simulating CRITICAL FAILURE of node {target_node}...")
    start_failure = time.time()
    record_self_healing_event("node_failure", target_node)
    
    # 3. Wait for mesh rerouting (simulated delay based on MAPE-K cycle)
    # In a real system, the MAPE-K loop would detect this and plan a new route
    recovery_delay = 2.45  # Simulated recovery time
    await asyncio.sleep(recovery_delay)
    
    # 4. Success rerouting
    end_recovery = time.time()
    mttr = end_recovery - start_failure
    
    logger.info(f"✅ Route RECOVERED! Traffic redirected through alternate path in {mttr:.2f}s")
    record_mttr("mesh_reroute", mttr)
    record_self_healing_event("route_recovered", node_id)
    
    logger.info("📊 Metrics updated in Prometheus registry.")

if __name__ == "__main__":
    asyncio.run(run_demo())
