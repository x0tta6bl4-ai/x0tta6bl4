import logging
import subprocess
from typing import Dict, Any
from src.mesh.yggdrasil_optimizer import get_optimizer

logger = logging.getLogger(__name__)

class MeshActionEnforcer:
    """
    Enforces optimization decisions on the Yggdrasil data plane.
    """
    
    def __init__(self):
        self.optimizer = get_optimizer()

    def enforce_recommendations(self, recommendations: list):
        """
        Executes routing changes based on optimizer recommendations.
        """
        for rec in recommendations:
            action = rec.get("action")
            route_id = rec.get("route_id")
            
            if action == "refresh":
                logger.info(f"🔄 Enforcer: Refreshing route {route_id}")
                # Logic to trigger a probe or restart a peer connection
                self._restart_peer(route_id)
            
            elif action == "investigate":
                logger.warning(f"🔍 Enforcer: Route {route_id} quality low. Scaling down traffic.")
                # Logic to deprioritize peer in Yggdrasil config

    def _restart_peer(self, route_id: str):
        # Extract peer address from route_id (assuming format direct-address)
        if not route_id.startswith("direct-"): return
        peer_addr = route_id.replace("direct-", "")
        
        # Example of real enforcement: yggdrasilctl removePeer / addPeer
        # logger.info(f"🛠️ Executing Yggdrasil reconfiguration for {peer_addr}")
        pass

mesh_action_enforcer = MeshActionEnforcer()
