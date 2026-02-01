#!/usr/bin/env python3
"""
Test script for VPN anonymity and leak protection improvements
"""

import asyncio
import logging
from src.network.dns_over_https import test_doh_resolver
from src.network.vpn_leak_protection import test_protection
from src.network.vpn_obfuscation_manager import test_obfuscation

# Configure logging
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

async def run_all_tests():
    """Run all VPN anonymity and leak protection tests"""
    logger.info("=== Running VPN Anonymity and Leak Protection Tests ===")
    
    try:
        logger.info("\n1. Testing DNS-over-HTTPS Resolver")
        await test_doh_resolver()
        
        logger.info("\n2. Testing VPN Leak Protection")
        await test_protection()
        
        logger.info("\n3. Testing VPN Obfuscation Manager")
        test_obfuscation()
        
        logger.info("\n✅ All tests completed successfully!")
        
    except Exception as e:
        logger.error(f"\n❌ Test failed: {e}")
        import traceback
        logger.error(traceback.format_exc())
        return False
        
    return True

if __name__ == "__main__":
    success = asyncio.run(run_all_tests())
    exit(0 if success else 1)
