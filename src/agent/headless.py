"""
x0tta6bl4 Headless Agent.
Designed for IoT, Robotics, and Servers.
Runs as a daemon/service.

Usage:
    export MAAS_API_KEY="your_key"
    python -m src.agent.headless start
"""

import asyncio
import logging
import os
import sys
import json
from pathlib import Path
import httpx

# Add project root to path
sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), '../../')))

from src.security.pqc_identity import PQCNodeIdentity
from src.network.discovery.protocol import MeshDiscovery
from src.network.routing.stigmergy import StigmergyRouter

# Setup logging
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - [AGENT] - %(levelname)s - %(message)s'
)
logger = logging.getLogger(__name__)

# Config
DATA_DIR = Path(os.getenv("X0T_DATA_DIR", "./agent_data"))
MAAS_URL = os.getenv("MAAS_URL", "http://localhost:8000/api/v1/maas")
API_KEY = os.getenv("MAAS_API_KEY")

class HeadlessAgent:
    def __init__(self):
        self.node_id = None
        self.identity = None
        self.discovery = None
        self.router = None
        
        DATA_DIR.mkdir(parents=True, exist_ok=True)

    async def initialize(self):
        """Initialize identity and config."""
        logger.info("Initializing Headless Agent...")
        
        # 1. Load or Create Identity
        id_path = DATA_DIR / "identity.json"
        if id_path.exists():
            # In a real impl, we'd load keys securely
            # For MVP, we regenerate based on saved ID or just new
            # Let's assume we store the Node ID and keys are managed by PQCNodeIdentity internal storage
            try:
                with open(id_path, "r") as f:
                    data = json.load(f)
                    self.node_id = data["node_id"]
                    logger.info(f"Loaded identity: {self.node_id}")
            except Exception:
                pass
        
        if not self.node_id:
            import uuid
            self.node_id = f"node-{uuid.uuid4().hex[:8]}"
            with open(id_path, "w") as f:
                json.dump({"node_id": self.node_id}, f)
            logger.info(f"Generated new identity: {self.node_id}")

        self.identity = PQCNodeIdentity(self.node_id)
        
        # 2. Register with MaaS (if API Key provided)
        if API_KEY:
            await self._register_with_maas()
        else:
            logger.warning("No MAAS_API_KEY provided. Running in offline/autonomous mode.")

        # 3. Setup Networking
        self.router = StigmergyRouter(self.node_id)
        
        # Discovery with Stigmergy hooks
        self.discovery = MeshDiscovery(
            node_id=self.node_id,
            service_port=7777,
            identity_manager=self.identity
        )
        
        # Hook discovery into router
        @self.discovery.on_peer_discovered
        async def on_peer(peer):
            # Initial "trust" score for new peer?
            # Or just wait for traffic.
            # We can ping them to start the pheromone trail.
            logger.info(f"New peer found: {peer.node_id}. Sending probe.")
            self.router.reinforce(peer.node_id, peer.node_id, success=True) # Boost initial contact

    async def _register_with_maas(self):
        """Register/Heartbeat with Control Plane."""
        try:
            # Here we would send our PubKey and IP
            async with httpx.AsyncClient() as client:
                # 1. Heartbeat
                resp = await client.get(
                    f"{MAAS_URL}/me", 
                    headers={"X-API-Key": API_KEY}
                )
                if resp.status_code == 200:
                    logger.info("✅ Connected to MaaS Control Plane")
                
                # 2. Fetch Policies (ACL)
                # Note: currentMeshId is hardcoded or fetched during onboarding
                mesh_id = os.getenv("MAAS_MESH_ID", "mesh-auto-001")
                config_resp = await client.get(
                    f"{MAAS_URL}/{mesh_id}/node-config/{self.node_id}",
                    headers={"X-API-Key": API_KEY}
                )
                if config_resp.status_code == 200:
                    config = config_resp.json()
                    self.router.update_policies(config["policies"], config["peer_tags"])
                    
        except Exception as e:
            logger.error(f"MaaS connection error: {e}")

    async def start(self):
        """Main loop."""
        await self.initialize()
        
        await self.router.start()
        await self.discovery.start()
        
        logger.info(f"🚀 Agent {self.node_id} RUNNING. (Ctrl+C to stop)")
        
        try:
            while True:
                # Agent Main Loop
                # 1. Report telemetry to MaaS
                # 2. Check for commands (Ghost in the Shell / Config updates)
                # 3. Optimize routes
                
                # Debug: Print Routing Table
                snapshot = self.router.get_routing_table_snapshot()
                if snapshot:
                    logger.debug(f"Routing Table: {snapshot}")
                
                await asyncio.sleep(5)
        except asyncio.CancelledError:
            logger.info("Stopping agent...")
        finally:
            await self.stop()

    async def stop(self):
        if self.discovery:
            await self.discovery.stop()
        if self.router:
            await self.router.stop()

if __name__ == "__main__":
    agent = HeadlessAgent()
    try:
        asyncio.run(agent.start())
    except KeyboardInterrupt:
        pass
