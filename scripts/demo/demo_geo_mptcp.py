"""
Demo: Geo-Fencing & MPTCP
=========================

This script demonstrates how x0tta6bl4 enforces geographic restrictions 
and leverages multi-path TCP for performance.
"""

import asyncio
import logging
import sys
import os

# Add project root to path
sys.path.append(os.getcwd())

from src.network.batman.node_manager import NodeManager
from src.network.mptcp_manager import MPTCPManager

# Configure logging
logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(name)s - %(levelname)s - %(message)s')
logger = logging.getLogger("Geo-MPTCP-Demo")

async def run_demo():
    logger.info("🚀 Starting Geo-Fencing & MPTCP Demo")
    
    # 1. Geo-Fencing Test
    # Restricted: RU (Russia)
    node_mgr = NodeManager("geo-mesh", "local-node", restricted_countries=["RU"])
    
    logger.info("🛡️ Step 1: Testing Geo-Fencing...")
    
    # Case A: Allowed IP (UA)
    res_allowed = node_mgr.register_node("node-ua", "mac1", "89.125.1.107", spiffe_id="spiffe://x0tta6bl4.mesh/node/ua")
    if res_allowed:
        logger.info("✅ Node from Ukraine ALLOWED.")
    else:
        logger.error("❌ Node from Ukraine BLOCKED (unexpected).")
        
    # Case B: Restricted IP (RU)
    res_blocked = node_mgr.register_node("node-ru", "mac2", "95.161.224.1", spiffe_id="spiffe://x0tta6bl4.mesh/node/ru")
    if not res_blocked:
        logger.info("🛑 SUCCESS: Node from Russia BLOCKED as expected.")
    else:
        logger.error("❌ Node from Russia ALLOWED (unexpected).")

    # 2. MPTCP Test
    logger.info("🔧 Step 2: Testing MPTCP Configuration...")
    status = MPTCPManager.get_status()
    logger.info(f"📊 MPTCP Status: {status}")
    
    if status['supported']:
        MPTCPManager.enable_mptcp(True)
        MPTCPManager.configure_endpoints(["eth0", "wlan0"])
        logger.info("⚡ MPTCP Path Aggregation ENABLED.")
    else:
        logger.warning("⚠️ MPTCP NOT supported on this kernel (simulating success).")
        logger.info("⚡ MPTCP Path Aggregation would be enabled on production kernels.")

    logger.info("✅ Demo Complete.")

if __name__ == "__main__":
    asyncio.run(run_demo())
