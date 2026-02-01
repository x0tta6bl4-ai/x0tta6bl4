#!/usr/bin/env python3
"""
Script to start VPN protection with all security features enabled
"""

import asyncio
import logging
import sys
from src.network.vpn_leak_protection import get_vpn_protector

# Configure logging
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

async def start_protection():
    """Start VPN protection with all security features"""
    logger.info("=== Starting VPN Protection ===")
    
    try:
        # Get VPN protector instance
        protector = await get_vpn_protector()
        
        # Enable protection
        logger.info("Enabling VPN protection...")
        await protector.enable_protection()
        
        # Check status
        status = await protector.get_status()
        logger.info(f"Protection Enabled: {status['protection_enabled']}")
        logger.info(f"Kill Switch Enabled: {status['kill_switch_enabled']}")
        logger.info(f"VPN Interface: {status['vpn_interface']}")
        
        # Run tests to verify
        logger.info("\n=== Running Leak Tests ===")
        tests = await protector.run_all_tests()
        
        all_passed = True
        for test in tests:
            if test.is_leaking:
                logger.warning(f"⚠️ {test}")
                all_passed = False
            else:
                logger.info(f"✅ {test}")
        
        if all_passed:
            logger.info("\n✅ VPN protection successfully started with all security features enabled")
        else:
            logger.warning("\n⚠️ Some tests failed - please check the VPN configuration")
        
    except Exception as e:
        logger.error(f"Error starting VPN protection: {e}")
        import traceback
        logger.error(traceback.format_exc())
        return False
        
    return True

async def main():
    """Main function to start VPN protection"""
    await start_protection()

if __name__ == "__main__":
    asyncio.run(main())
