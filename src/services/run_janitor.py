#!/usr/bin/env python3
"""
Entrypoint for Marketplace Janitor Service.
Designed to run as a standalone process or container.
"""
import asyncio
import logging
import os
import sys

# Ensure src is in python path
sys.path.append(os.getcwd())

from src.services.marketplace_janitor import marketplace_janitor_loop

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s - %(name)s - %(levelname)s - %(message)s"
)
logger = logging.getLogger("maas-janitor")

def main():
    logger.info("🚀 Starting Marketplace Janitor Service...")
    try:
        asyncio.run(marketplace_janitor_loop())
    except KeyboardInterrupt:
        logger.info("🛑 Janitor service stopping...")
    except Exception as e:
        logger.critical(f"🔥 Fatal error: {e}", exc_info=True)
        sys.exit(1)

if __name__ == "__main__":
    main()
