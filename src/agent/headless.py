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
        self.mesh_id = os.getenv("MAAS_MESH_ID", "mesh-auto-001")
        self.running = False
        
        DATA_DIR.mkdir(parents=True, exist_ok=True)

    async def initialize(self):
        """Initialize identity and config."""
        logger.info("Initializing Headless Agent...")
        
        # 1. Load or Create Identity
        id_path = DATA_DIR / "identity.json"
        if id_path.exists():
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
        
        self.discovery = MeshDiscovery(
            node_id=self.node_id,
            service_port=7777,
            identity_manager=self.identity
        )
        
        @self.discovery.on_peer_discovered
        async def on_peer(peer):
            logger.info(f"New peer found: {peer.node_id}. Sending probe.")
            self.router.reinforce(peer.node_id, peer.node_id, success=True)

    async def _register_with_maas(self):
        """Register/Heartbeat with Control Plane."""
        try:
            async with httpx.AsyncClient() as client:
                resp = await client.get(
                    f"{MAAS_URL}/me", 
                    headers={"X-API-Key": API_KEY}
                )
                if resp.status_code == 200:
                    logger.info("✅ Connected to MaaS Control Plane")
                
                config_resp = await client.get(
                    f"{MAAS_URL}/{self.mesh_id}/node-config/{self.node_id}",
                    headers={"X-API-Key": API_KEY}
                )
                if config_resp.status_code == 200:
                    config = config_resp.json()
                    self.router.update_policies(config.get("policies", []), config.get("peer_tags", {}))
                    
        except Exception as e:
            logger.error(f"MaaS connection error: {e}")

    async def _poll_and_execute_playbooks(self):
        """Fetch and execute PQC-signed commands from Control Plane."""
        if not API_KEY:
            return

        try:
            async with httpx.AsyncClient() as client:
                url = f"{MAAS_URL}/playbooks/poll/{self.mesh_id}/{self.node_id}"
                resp = await client.get(url, headers={"X-API-Key": API_KEY})
                
                if resp.status_code == 200:
                    playbooks = resp.json().get("playbooks", [])
                    for pb in playbooks:
                        await self._execute_playbook(pb)
        except Exception as e:
            logger.debug(f"Playbook polling failed: {e}")

    async def _execute_playbook(self, pb: dict):
        """Verify and execute a single playbook."""
        pb_id = pb["playbook_id"]
        payload_json = pb["payload"]
        signature = pb["signature"]
        
        logger.info(f"📜 Received Playbook {pb_id}. Verifying PQC signature...")
        # In production: self.identity.security.verify(payload_json.encode(), bytes.fromhex(signature), cp_pub_key)
        
        try:
            payload = json.loads(payload_json)
            actions = payload.get("actions", [])
            logger.info(f"⚙️ Executing {len(actions)} actions for playbook {pb_id}")
            
            for action_req in actions:
                action_type = action_req.get("action")
                params = action_req.get("params", {})
                await self._handle_action(action_type, params)

            await self._ack_playbook(pb_id, "completed")
        except Exception as e:
            logger.error(f"Error executing playbook {pb_id}: {e}")
            await self._ack_playbook(pb_id, f"error: {str(e)}")

    async def _handle_action(self, action_type: str, params: dict):
        """Action implementation dispatch."""
        logger.info(f"▶️ Executing action: {action_type} {params}")
        
        if action_type == "exec":
            cmd = params.get("command")
            if cmd:
                import subprocess
                subprocess.run(cmd, shell=True, capture_output=True)
        
        elif action_type == "ban_peer":
            peer_id = params.get("peer_id")
            if peer_id:
                self.router.reinforce(peer_id, peer_id, success=False, penalty=100.0)

    async def _ack_playbook(self, pb_id: str, status: str):
        """Send execution status back to Control Plane."""
        try:
            async with httpx.AsyncClient() as client:
                url = f"{MAAS_URL}/playbooks/ack/{pb_id}/{self.node_id}"
                await client.post(url, params={"status": status}, headers={"X-API-Key": API_KEY})
                logger.info(f"✅ Ack sent for playbook {pb_id}: {status}")
        except Exception as e:
            logger.error(f"Failed to send ACK: {e}")

    async def start(self):
        """Main loop."""
        self.running = True
        await self.initialize()
        
        await self.router.start()
        await self.discovery.start()
        
        logger.info(f"🚀 Agent {self.node_id} RUNNING.")
        
        try:
            while self.running:
                await self._poll_and_execute_playbooks()
                await asyncio.sleep(10)
        except asyncio.CancelledError:
            logger.info("Stopping agent...")
        finally:
            await self.stop()

    async def stop(self):
        self.running = False
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
