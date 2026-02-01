#!/usr/bin/env python3
"""
Test access to Claude.ai with different obfuscation methods
"""

import asyncio
import logging
import sys
from src.network.vpn_obfuscation_manager import get_vpn_obfuscator, ObfuscationMethod
from src.network.vpn_leak_protection import get_vpn_protector

# Configure logging
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

async def test_claude_access():
    """Test access to Claude.ai with different obfuscation methods"""
    logger.info("=== Testing Claude.ai Access ===")
    
    try:
        # Get VPN protector instance
        protector = await get_vpn_protector()
        
        # Check VPN connection first
        logger.info("Checking VPN connection...")
        ip_test = await protector.test_ip_leak()
        
        if ip_test.is_leaking:
            logger.error("⚠️ VPN connection not working")
            return False
            
        logger.info(f"✅ VPN IP: {', '.join(ip_test.details['normalized_ips'])}")
        
        # Test with different obfuscation methods
        obfuscator = get_vpn_obfuscator()
        methods_to_test = [
            ObfuscationMethod.SHADOWSOCKS,
            ObfuscationMethod.FAKETLS,
            ObfuscationMethod.DOMAIN_FRONTING,
            ObfuscationMethod.STEGOMESH,
            ObfuscationMethod.HYBRID
        ]
        
        logger.info("\n=== Testing Obfuscation Methods ===")
        
        for method in methods_to_test:
            logger.info(f"\n--- Testing {method.value} ---")
            try:
                obfuscator.set_obfuscation_method(method)
                
                # Test connectivity
                logger.info(f"  Current parameters: {obfuscator.get_current_parameters()}")
                
                # Test DNS resolution for claude.ai
                logger.info(f"  Resolving claude.ai...")
                claude_dns = await protector.doh_resolver.resolve_a("claude.ai")
                logger.info(f"  IP addresses: {claude_dns}")
                
                # Test with curl
                logger.info(f"  Testing connectivity to claude.ai...")
                import subprocess
                
                # Try to get response headers
                result = await asyncio.create_subprocess_shell(
                    "curl -I https://claude.ai --connect-timeout 10",
                    stdout=asyncio.subprocess.PIPE,
                    stderr=asyncio.subprocess.PIPE
                )
                stdout, stderr = await result.communicate()
                
                if result.returncode == 0:
                    logger.info(f"  ✅ Success! Status: {stdout.decode().split()[1]}")
                    logger.info(f"  Response: {stdout.decode().splitlines()[0]}")
                    return True
                else:
                    logger.warning(f"  ❌ Failed: {stderr.decode().strip()}")
                    
            except Exception as e:
                logger.error(f"  Error testing {method.value}: {e}")
                continue
        
        logger.error("\n⚠️ All obfuscation methods failed to access claude.ai")
        return False
        
    except Exception as e:
        logger.error(f"Error testing Claude access: {e}")
        import traceback
        logger.error(traceback.format_exc())
        return False

async def main():
    """Main function to test Claude.ai access"""
    success = await test_claude_access()
    
    if success:
        logger.info("\n✅ Success! Claude.ai is accessible with VPN and obfuscation")
    else:
        logger.error("\n❌ Failed to access Claude.ai")
        sys.exit(1)

if __name__ == "__main__":
    asyncio.run(main())
