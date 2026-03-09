"""
Crisis Connectivity Kit — x0tta6bl4
====================================

Orchestration of mesh-core with pluggable transports for 
humanitarian missions and underserved areas.

Features:
- Auto-detection of censorship level
- Dynamic transport switching (OBFS4, Meek, Snowflake)
- Offline-first mesh synchronization
"""

import logging
import asyncio
from typing import Dict, Any, List, Optional
from src.anti_censorship.transports import create_transport, TransportType
from src.anti_censorship.censorship_detector import CensorshipDetector

logger = logging.getLogger(__name__)

class CrisisKitOrchestrator:
    def __init__(self, node_id: str, mesh_id: str):
        self.node_id = node_id
        self.mesh_id = mesh_id
        self.detector = CensorshipDetector()
        self.active_transport = None
        self._running = False

    async def detect_and_adapt(self):
        """Monitor environment and switch transports if blocked."""
        while self._running:
            try:
                status = await self.detector.check_connectivity()
                logger.info(f"[CrisisKit] Connectivity Status: {status}")

                if status["blocked"]:
                    recommendation = status["recommended_transport"]
                    await self._switch_transport(recommendation)
                else:
                    if self.active_transport:
                        logger.info("[CrisisKit] Direct connectivity restored. Scaling down transports.")
                        await self._close_current_transport()

            except Exception as e:
                logger.error(f"[CrisisKit] Adaptation error: {e}")
            
            await asyncio.sleep(60) # Re-check every minute

    async def _switch_transport(self, transport_type: str):
        """Switch to a more resilient transport."""
        if self.active_transport and self.active_transport.config.transport_type.value == transport_type:
            return # Already on optimal transport

        logger.warning(f"[CrisisKit] Switching to resilient transport: {transport_type}")
        await self._close_current_transport()

        try:
            self.active_transport = create_transport(
                transport_type=transport_type,
                front_domain="cdn.cloudflare.net" if transport_type == "meek" else ""
            )
            # Logic to bridge mesh traffic through this transport would go here
            logger.info(f"✅ Transport {transport_type} activated for Node {self.node_id}")
        except Exception as e:
            logger.error(f"❌ Failed to activate {transport_type}: {e}")

    async def _close_current_transport(self):
        if self.active_transport:
            await self.active_transport.close()
            self.active_transport = None

    async def start(self):
        self._running = True
        asyncio.create_task(self.detect_and_adapt())
        logger.info(f"🚀 Crisis Connectivity Kit initialized for Node {self.node_id}")

    async def stop(self):
        self._running = False
        await self._close_current_transport()
