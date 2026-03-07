"""
Demo: Smart Protocol Switching (Anti-Censorship)
==============================================

This script demonstrates how x0tta6bl4 automatically switches to 
Stego-Mesh mimicry when DPI/Censorship is detected by AI.
"""

import asyncio
import logging
import sys
import os
from unittest.mock import MagicMock, patch

# Add project root to path
sys.path.append(os.getcwd())

from src.self_healing.mape_k_integrated import IntegratedMAPEKCycle
from src.network.batman.node_manager import NodeManager

# Configure logging
logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(name)s - %(levelname)s - %(message)s')
logger = logging.getLogger("Smart-Routing-Demo")

async def run_demo():
    logger.info("🚀 Starting Smart Protocol Switching Demo")
    
    # 1. Setup Mock NodeManager with Protocol Support
    node_mgr = NodeManager("demo-mesh", "local-01")
    
    # 2. Setup Integrated MAPE-K
    cycle = IntegratedMAPEKCycle(enable_observe_mode=False)
    # Inject our node_mgr as the routing backend
    cycle.executor.recovery_executor._routing_backend = node_mgr
    
    # 3. Simulate "Censorship Interference" detection (via logs)
    CENSORSHIP_LOGS = """
    2026-02-26 10:00:01 [Warning] Connection reset by peer (DPI-Signature matched)
    2026-02-26 10:00:05 [Error] TLS Handshake timed out - possibly blocked by firewall
    """
    
    metrics = {
        "node_id": "local-01",
        "cpu_percent": 10,
        "memory_percent": 20,
        "packet_loss_percent": 50.0, # High loss due to DPI
        "logs": CENSORSHIP_LOGS
    }
    
    logger.info("🔍 Step 1: Monitor detecting instability...")
    logger.info("🤖 Step 2: AI Analyzing logs for censorship...")
    
    # Mock AI response to return Censorship Interference
    with patch("src.self_healing.mape_k.MAPEKAnalyzer.analyze_with_llm", 
               return_value="AI-Analysis (Censorship Interference): DPI reset detected. Suggesting Stego mimicry."):
        
        logger.info(f"📡 Current Protocol: {node_mgr.active_protocol}")
        
        result = await cycle.run_cycle(metrics)
        
        logger.info(f"📋 Cycle Result Keys: {result.keys()}")
        if 'planner_results' in result and 'strategy' in result['planner_results']:
            logger.info(f"🎯 Planned Action: {result['planner_results']['strategy']}")
        else:
            logger.error(f"❌ Planner results incomplete: {result.get('planner_results')}")
            return
        
        if result['executor_results'].get('success'):
            logger.info(f"✅ Recovery successful!")
            logger.info(f"📡 NEW Protocol: {node_mgr.active_protocol} (mimic: {node_mgr.stego_mimic})")
            
            if node_mgr.active_protocol == "stego":
                logger.info("🎉 SUCCESS: System automatically escaped censorship!")
            else:
                logger.error("❌ FAILED: Protocol did not switch.")

if __name__ == "__main__":
    asyncio.run(run_demo())
