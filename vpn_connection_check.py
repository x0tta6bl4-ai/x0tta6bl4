#!/usr/bin/env python3
"""
Script to check VPN connection status and verify IP match
"""

import asyncio
import logging
from src.network.vpn_leak_protection import get_vpn_protector, LeakType

# Configure logging
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

async def check_vpn_connection():
    """Check VPN connection status and IP match"""
    logger.info("=== Checking VPN Connection Status ===")
    
    try:
        # Get VPN protector instance
        protector = await get_vpn_protector()
        
        # Run IP leak test specifically
        logger.info("Running IP leak test...")
        ip_test = await protector.test_ip_leak()
        logger.info(f"IP Leak Test Result: {'✅ No leak' if not ip_test.is_leaking else '⚠️ LEAK DETECTED'}")
        
        if not ip_test.is_leaking:
            logger.info("✅ VPN connection is active and working correctly")
        else:
            logger.warning("⚠️ VPN connection is not active or IP is not matching")
        
        # Get and log detected IPs
        if "detected_ips" in ip_test.details:
            detected_ips = ip_test.details["detected_ips"]
            logger.info(f"Detected IPs: {', '.join(detected_ips)}")
        
        # Check consistency
        if "consistent_ip" in ip_test.details:
            logger.info(f"IP consistency: {'✅ Consistent' if ip_test.details['consistent_ip'] else '⚠️ Inconsistent'}")
        
    except Exception as e:
        logger.error(f"Error checking VPN connection: {e}")
        import traceback
        logger.error(traceback.format_exc())
        return False
        
    return True

async def check_dns_resolution():
    """Check DNS resolution through VPN"""
    logger.info("\n=== Checking DNS Resolution ===")
    
    try:
        protector = await get_vpn_protector()
        dns_test = await protector.test_dns_leak()
        
        logger.info(f"DNS Leak Test Result: {'✅ No leak' if not dns_test.is_leaking else '⚠️ LEAK DETECTED'}")
        
        if not dns_test.is_leaking:
            for result in dns_test.details["results"]:
                logger.info(f"Resolved {result['domain']} to: {', '.join(result['resolved_ips'])}")
        
    except Exception as e:
        logger.error(f"Error checking DNS resolution: {e}")
        import traceback
        logger.error(traceback.format_exc())
        return False
        
    return True

async def main():
    """Main function to check VPN connection and DNS resolution"""
    await check_vpn_connection()
    await check_dns_resolution()

if __name__ == "__main__":
    asyncio.run(main())
