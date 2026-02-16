import logging
from typing import Optional

from libx0t.crypto.pqc import PQC
from libx0t.network.tunnel import Tunnel

logger = logging.getLogger("x0t")

class Node:
    """
    Represents a local node in the x0t mesh network.
    """
    def __init__(self, node_id: Optional[str] = None):
        import uuid
        self.node_id = node_id or str(uuid.uuid4())
        self.pqc = PQC()
        logger.info(f"Initialized x0t Node: {self.node_id}")
        logger.info(f"PQC Algorithm: {self.pqc.algorithm}")

    def connect(self, peer_address: str, secure: bool = True) -> Tunnel:
        """
        Establish a connection to a peer.
        
        Args:
            peer_address: Address of the peer (IP:Port or NodeID)
            secure: Whether to enforce PQC encryption
            
        Returns:
            Tunnel object for data transfer
        """
        logger.info(f"Connecting to {peer_address} (Secure={secure})...")
        tunnel = Tunnel(peer_address, self.pqc if secure else None)
        tunnel.handshake()
        return tunnel
