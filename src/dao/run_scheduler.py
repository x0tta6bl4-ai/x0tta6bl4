#!/usr/bin/env python3
"""
X0T Epoch Reward Scheduler Service.
Runs constantly, checking for epoch completion every minute.
"""
import asyncio
import logging
import os
import sys
from typing import Dict

# Add project root to path
sys.path.append(os.path.abspath(os.path.join(os.path.dirname(__file__), "../../")))

from src.dao.token import MeshToken
from src.dao.token_bridge import TokenBridge, BridgeConfig, EpochRewardScheduler
from src.network.batman.node_manager import NodeManager

# Setup logging
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s',
    handlers=[
        logging.FileHandler("scheduler.log"),
        logging.StreamHandler()
    ]
)
logger = logging.getLogger("EpochScheduler")

def get_mock_uptimes() -> Dict[str, float]:
    """
    Get uptime data from NodeManager or monitoring system.
    For now, returns mock data based on active nodes.
    """
    # TODO: Connect to actual Prometheus or NodeManager state
    return {
        "node-1": 0.99,
        "node-2": 0.95,
        "node-3": 0.80
    }

async def main():
    logger.info("Starting X0T Epoch Scheduler...")
    
    # Load config from env
    private_key = os.getenv("PRIVATE_KEY")
    rpc_url = os.getenv("RPC_URL", "https://sepolia.base.org")
    contract_addr = os.getenv("CONTRACT_ADDRESS")
    
    if not private_key or not contract_addr:
        logger.error("PRIVATE_KEY or CONTRACT_ADDRESS not set")
        return

    # Initialize components
    token = MeshToken()
    config = BridgeConfig(
        rpc_url=rpc_url,
        contract_address=contract_addr,
        private_key=private_key
    )
    bridge = TokenBridge(token, config)
    
    # Start bridge listener
    asyncio.create_task(bridge.start())
    
    # Start scheduler
    scheduler = EpochRewardScheduler(
        bridge=bridge,
        uptime_provider=get_mock_uptimes
    )
    
    await scheduler.start()

if __name__ == "__main__":
    try:
        asyncio.run(main())
    except KeyboardInterrupt:
        logger.info("Scheduler stopped by user")
    except Exception as e:
        logger.critical(f"Scheduler crashed: {e}")
