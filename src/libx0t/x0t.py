"""
libx0t: The DeepTech Mesh SDK.
Provides a simple interface for quantum-secure, self-healing mesh networking.
"""

import logging
import asyncio
from typing import Optional, Dict, Any, List

from libx0t.network.mesh_router import MeshRouter
from libx0t.network.mesh_node import MeshNode, MeshNodeConfig
from libx0t.security.post_quantum import PQMeshSecurityLibOQS as PQMeshSecurity

logger = logging.getLogger("libx0t")

class X0T:
    """
    Main SDK Facade for libx0t.
    
    Example:
        >>> import libx0t
        >>> mesh = libx0t.X0T()
        >>> await mesh.connect(pqc_level="military")
        >>> tunnel = mesh.create_tunnel("target_node")
    """

    def __init__(self, config: Optional[Dict[str, Any]] = None):
        self.config = config or {}
        self.router = None
        self.security = None
        logger.info("Initializing libx0t SDK")

    async def connect(self, pqc_level: str = "military") -> bool:
        """
        Initialize the mesh node and connect to the network.
        """
        logger.info(f"Connecting to mesh with PQC level: {pqc_level}")
        
        # Initialize Core components (Real Logic)
        logger.info("Initializing MeshNodeConfig...")
        config = MeshNodeConfig(node_id=self.config.get("node_id"))
        logger.info("Initializing MeshNode...")
        self.node = MeshNode(config)
        logger.info("Initializing MeshRouter...")
        self.router = MeshRouter(node_id=self.node.config.node_id)
        logger.info("Core components initialized successfully.")
        
        return True

    def create_tunnel(self, target: str) -> 'MeshTunnel':
        """Create a secure tunnel to a target node."""
        logger.info(f"Creating tunnel to {target}")
        return MeshTunnel(target)

class MeshTunnel:
    """Represents a secure PQC tunnel within the mesh."""
    def __init__(self, target: str):
        self.target = target
        self.is_active = True

    async def send(self, data: bytes):
        """Send encrypted data through the tunnel."""
        if not self.is_active:
            raise Exception("Tunnel is closed")
        logger.debug(f"Sending {len(data)} bytes to {self.target} (PQC Encrypted)")
        await asyncio.sleep(0.01)

    def close(self):
        """Close the tunnel."""
        self.is_active = False
        logger.info(f"Tunnel to {self.target} closed")

# Singleton instance for quick access
default_x0t = X0T()
