#!/usr/bin/env python3
"""
Script to stop VPN protection and restore original network configuration
"""

import asyncio
import logging
from src.network.vpn_leak_protection import get_vpn_protector

# Configure logging
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

async def stop_protection():
    """Stop VPN protection and restore original network configuration"""
    logger.info("=== Stopping VPN Protection ===")
    
    try:
        # Get VPN protector instance
        protector = await get_vpn_protector()
        
        # Disable protection
        logger.info("Disabling VPN protection...")
        await protector.disable_protection()
        
        # Check status
        status = await protector.get_status()
        logger.info(f"Protection Enabled: {status['protection_enabled']}")
        logger.info(f"Kill Switch Enabled: {status['kill_switch_enabled']}")
        
        logger.info("\n✅ VPN protection successfully stopped")
        logger.info("✅ Original network configuration restored")
        
    except Exception as e:
        logger.error(f"Error stopping VPN protection: {e}")
        import traceback
        logger.error(traceback.format_exc())
        return False
        
    return True

async def main():
    """Main function to stop VPN protection"""
    await stop_protection()

if __name__ == "__main__":
    asyncio.run(main())
