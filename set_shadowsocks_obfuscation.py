#!/usr/bin/env python3
"""
Script to set ShadowSocks as the active obfuscation method
"""

import asyncio
import logging
from src.network.vpn_obfuscation_manager import get_vpn_obfuscator, ObfuscationMethod

# Configure logging
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

async def set_shadowsocks():
    """Set ShadowSocks as the active obfuscation method"""
    logger.info("=== Setting ShadowSocks Obfuscation ===")
    
    try:
        obfuscator = get_vpn_obfuscator()
        obfuscator.set_obfuscation_method(ObfuscationMethod.SHADOWSOCKS)
        
        params = obfuscator.get_current_parameters()
        logger.info(f"✅ ShadowSocks obfuscation active")
        logger.info(f"  Method: {params['method']}")
        logger.info(f"  SNI: {params['sni']}")
        logger.info(f"  TLS Fingerprint: {params['fingerprint']}")
        logger.info(f"  SpiderX Path: {params['spiderx']}")
        
        return True
        
    except Exception as e:
        logger.error(f"Error setting ShadowSocks obfuscation: {e}")
        import traceback
        logger.error(traceback.format_exc())
        return False

async def main():
    """Main function to set ShadowSocks obfuscation"""
    await set_shadowsocks()

if __name__ == "__main__":
    asyncio.run(main())
