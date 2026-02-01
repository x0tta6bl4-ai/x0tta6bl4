#!/usr/bin/env python3
"""
Script to get a comprehensive overview of the VPN system status
"""

import asyncio
import logging
import sys
from src.network.vpn_leak_protection import get_vpn_protector
from src.network.vpn_obfuscation_manager import get_vpn_obfuscator
from src.network.dns_over_https import get_doh_resolver

# Configure logging
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

async def check_system_status():
    """Check the complete system status including VPN, DNS, and obfuscation"""
    logger.info("=== VPN System Status Check ===")
    
    try:
        # Get all system components
        protector = await get_vpn_protector()
        obfuscator = get_vpn_obfuscator()
        resolver = await get_doh_resolver()
        
        # System information
        logger.info("\n--- System Information ---")
        logger.info(f"Python Version: {sys.version}")
        logger.info(f"Platform: {sys.platform}")
        
        # VPN Connection Status
        logger.info("\n--- VPN Connection Status ---")
        ip_test = await protector.test_ip_leak()
        logger.info(f"IP Leak Test: {'✅ No leak' if not ip_test.is_leaking else '⚠️ LEAK DETECTED'}")
        
        if not ip_test.is_leaking:
            logger.info("✅ VPN connection is active and working correctly")
            
            # Display detected IPs
            if "normalized_ips" in ip_test.details:
                logger.info(f"Detected IPs: {', '.join(ip_test.details['normalized_ips'])}")
            
            # Display IP consistency
            if "consistent_ip" in ip_test.details:
                logger.info(f"IP Consistency: {'✅ Consistent' if ip_test.details['consistent_ip'] else '⚠️ Inconsistent'}")
        else:
            logger.warning("⚠️ VPN connection is not active or IP is not matching")
        
        # DNS Resolution Status
        logger.info("\n--- DNS Resolution Status ---")
        dns_test = await protector.test_dns_leak()
        logger.info(f"DNS Leak Test: {'✅ No leak' if not dns_test.is_leaking else '⚠️ LEAK DETECTED'}")
        
        if not dns_test.is_leaking:
            for result in dns_test.details["results"]:
                logger.info(f"Resolved {result['domain']} to: {', '.join(result['resolved_ips'])}")
        
        # Obfuscation Status
        logger.info("\n--- Obfuscation Status ---")
        current_params = obfuscator.get_current_parameters()
        logger.info(f"Current Obfuscation Method: {current_params['method']}")
        logger.info(f"Rotation Strategy: {current_params['rotation_strategy']}")
        logger.info(f"Rotation Interval: {current_params['rotation_interval']} seconds")
        logger.info(f"Current SNI: {current_params['sni']}")
        logger.info(f"Current TLS Fingerprint: {current_params['fingerprint']}")
        logger.info(f"Current SpiderX Path: {current_params['spiderx']}")
        
        # DNS Resolver Status
        logger.info("\n--- DNS Resolver Status ---")
        resolver_stats = resolver.get_stats()
        logger.info(f"Number of DNS Servers: {resolver_stats['server_count']}")
        logger.info(f"Current Server: {resolver_stats['current_server']['name']}")
        logger.info(f"Server URL: {resolver_stats['current_server']['url']}")
        
        # Protection Status
        logger.info("\n--- Protection Status ---")
        status = await protector.get_status()
        logger.info(f"Protection Enabled: {status['protection_enabled']}")
        logger.info(f"Kill Switch Enabled: {status['kill_switch_enabled']}")
        logger.info(f"VPN Interface: {status['vpn_interface']}")
        
        logger.info("\n=== System Status Check Completed ===")
        
    except Exception as e:
        logger.error(f"Error checking system status: {e}")
        import traceback
        logger.error(traceback.format_exc())
        return False
        
    return True

async def main():
    """Main function to check system status"""
    await check_system_status()

if __name__ == "__main__":
    asyncio.run(main())
