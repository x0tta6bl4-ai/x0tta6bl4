"""
SPIRE Integration Examples for x0tta6bl4.

This module demonstrates how to use SPIRE for:
1. Workload API (X.509 SVID fetching)
2. Auto-renewal of certificates
3. mTLS between mesh nodes
4. Zero-trust authentication
"""
import asyncio
import logging
from typing import Optional, Tuple
from dataclasses import dataclass

# Configure logging
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)


@dataclass
class SVID:
    """SPIFFE X.509 SVID container."""
    spiffe_id: str
    cert_chain: bytes
    private_key: bytes
    expiry_timestamp: float
    renew_hint: float  # Timestamp when renewal should start


class SpiffeWorkloadAPIClient:
    """
    Client for SPIFFE Workload API.
    
    This is a simplified example. In production, use the official
    python-spiffe library or the SPIFFE SDK.
    """
    
    DEFAULT_SOCKET_PATH = "/run/spire/sockets/agent.sock"
    
    def __init__(self, socket_path: str = DEFAULT_SOCKET_PATH):
        self.socket_path = socket_path
        self._current_svid: Optional[SVID] = None
        self._renewal_task: Optional[asyncio.Task] = None
        self._running = False
    
    async def start(self):
        """Start the workload API client."""
        self._running = True
        
        # Fetch initial SVID
        self._current_svid = await self._fetch_svid()
        logger.info(f"Obtained SVID: {self._current_svid.spiffe_id}")
        
        # Start auto-renewal
        self._renewal_task = asyncio.create_task(self._auto_renew_loop())
    
    async def stop(self):
        """Stop the workload API client."""
        self._running = False
        
        if self._renewal_task:
            self._renewal_task.cancel()
            try:
                await self._renewal_task
            except asyncio.CancelledError:
                pass
    
    async def _fetch_svid(self) -> SVID:
        """
        Fetch X.509 SVID from Workload API.
        
        In production, this would use gRPC to communicate with the SPIRE Agent.
        """
        # Simulated SVID fetch
        # Real implementation would use:
        # from spiffe import WorkloadApiClient
        # client = WorkloadApiClient(self.socket_path)
        # svid = client.fetch_x509_svid()
        
        import time
        return SVID(
            spiffe_id="spiffe://x0tta6bl4.mesh/workload/x0tta6bl4-node",
            cert_chain=b"SIMULATED_CERT_CHAIN",
            private_key=b"SIMULATED_PRIVATE_KEY",
            expiry_timestamp=time.time() + 3600,  # 1 hour
            renew_hint=time.time() + 3000  # Renew at 50 minutes
        )
    
    async def _auto_renew_loop(self):
        """Auto-renew SVID before expiry."""
        while self._running:
            if self._current_svid:
                import time
                time_until_renew = self._current_svid.renew_hint - time.time()
                
                if time_until_renew <= 0:
                    logger.info("Renewing SVID...")
                    self._current_svid = await self._fetch_svid()
                    logger.info(f"Renewed SVID: {self._current_svid.spiffe_id}")
                else:
                    await asyncio.sleep(min(time_until_renew, 60))
            else:
                await asyncio.sleep(5)
    
    def get_svid(self) -> Optional[SVID]:
        """Get current SVID."""
        return self._current_svid
    
    def get_spiffe_id(self) -> Optional[str]:
        """Get current SPIFFE ID."""
        if self._current_svid:
            return self._current_svid.spiffe_id
        return None


class MTLSChannel:
    """
    mTLS channel using SPIFFE SVIDs.
    
    Demonstrates how to establish mutual TLS between mesh nodes
    using SPIRE-issued certificates.
    """
    
    def __init__(self, spiffe_client: SpiffeWorkloadAPIClient):
        self.spiffe_client = spiffe_client
    
    async def connect(
        self,
        peer_address: str,
        peer_spiffe_id: str
    ) -> Tuple[asyncio.StreamReader, asyncio.StreamWriter]:
        """
        Establish mTLS connection to peer.
        
        Args:
            peer_address: Network address of peer (host:port)
            peer_spiffe_id: Expected SPIFFE ID of peer
        
        Returns:
            Tuple of (reader, writer) for the connection
        """
        svid = self.spiffe_client.get_svid()
        if not svid:
            raise RuntimeError("No SVID available")
        
        # In production, this would:
        # 1. Create SSL context with SVID cert and key
        # 2. Enable client certificate verification
        # 3. Verify peer's SPIFFE ID in SAN
        
        logger.info(f"Establishing mTLS to {peer_address} (peer: {peer_spiffe_id})")
        
        # Simulated connection
        reader, writer = await asyncio.open_connection(
            peer_address.split(":")[0],
            int(peer_address.split(":")[1])
        )
        
        return reader, writer
    
    async def create_server(
        self,
        bind_address: str = "0.0.0.0:8443"
    ) -> asyncio.Server:
        """
        Create mTLS server that verifies client SPIFFE IDs.
        
        Args:
            bind_address: Address to bind server to
        
        Returns:
            asyncio.Server instance
        """
        svid = self.spiffe_client.get_svid()
        if not svid:
            raise RuntimeError("No SVID available")
        
        # In production, this would:
        # 1. Create SSL context with SVID cert and key
        # 2. Require client certificates
        # 3. Verify client SPIFFE IDs against allowlist
        
        logger.info(f"Starting mTLS server on {bind_address}")
        
        server = await asyncio.start_server(
            self._handle_client,
            bind_address.split(":")[0],
            int(bind_address.split(":")[1])
        )
        
        return server
    
    async def _handle_client(
        self,
        reader: asyncio.StreamReader,
        writer: asyncio.StreamWriter
    ):
        """Handle incoming mTLS client connection."""
        # In production, verify client SPIFFE ID
        peer_spiffe_id = "spiffe://x0tta6bl4.mesh/workload/client"  # Extracted from cert
        
        logger.info(f"Client connected: {peer_spiffe_id}")
        
        try:
            while True:
                data = await reader.read(4096)
                if not data:
                    break
                # Process data...
                writer.write(data)  # Echo back
                await writer.drain()
        except asyncio.CancelledError:
            pass
        finally:
            writer.close()
            await writer.wait_closed()


class ZeroTrustAuthenticator:
    """
    Zero-trust authentication using SPIFFE.
    
    Demonstrates how to implement zero-trust authentication
    for mesh node communication.
    """
    
    def __init__(self, spiffe_client: SpiffeWorkloadAPIClient):
        self.spiffe_client = spiffe_client
        self._trust_domain = "x0tta6bl4.mesh"
    
    async def authenticate_peer(
        self,
        peer_spiffe_id: str,
        required_role: Optional[str] = None
    ) -> bool:
        """
        Authenticate a peer based on SPIFFE ID.
        
        Args:
            peer_spiffe_id: SPIFFE ID of the peer
            required_role: Optional role requirement
        
        Returns:
            True if peer is authenticated, False otherwise
        """
        # 1. Verify trust domain
        if not peer_spiffe_id.startswith(f"spiffe://{self._trust_domain}/"):
            logger.warning(f"Peer from untrusted domain: {peer_spiffe_id}")
            return False
        
        # 2. Verify our own identity
        our_id = self.spiffe_client.get_spiffe_id()
        if not our_id:
            logger.error("No SVID available for authentication")
            return False
        
        # 3. Check role if required
        if required_role:
            peer_role = self._extract_role(peer_spiffe_id)
            if peer_role != required_role:
                logger.warning(f"Peer role mismatch: {peer_role} != {required_role}")
                return False
        
        logger.info(f"Peer authenticated: {peer_spiffe_id}")
        return True
    
    def _extract_role(self, spiffe_id: str) -> Optional[str]:
        """Extract role from SPIFFE ID path."""
        # Example: spiffe://x0tta6bl4.mesh/workload/x0tta6bl4-node
        # Role could be encoded in the path
        parts = spiffe_id.split("/")
        if len(parts) >= 5:
            return parts[4].split("-")[0]  # "node" from "x0tta6bl4-node"
        return None
    
    async def create_auth_token(self) -> str:
        """
        Create authentication token using SVID.
        
        Returns:
            JWT-SVID token for authentication
        """
        svid = self.spiffe_client.get_svid()
        if not svid:
            raise RuntimeError("No SVID available")
        
        # In production, this would use JWT-SVID from Workload API
        import time
        import json
        import base64
        
        header = {"alg": "RS256", "typ": "JWT"}
        payload = {
            "sub": svid.spiffe_id,
            "iat": int(time.time()),
            "exp": int(svid.expiry_timestamp),
            "aud": ["x0tta6bl4-mesh"]
        }
        
        # Simulated JWT (not cryptographically valid)
        token = base64.urlsafe_b64encode(
            json.dumps(header).encode()
        ).decode() + "." + \
        base64.urlsafe_b64encode(
            json.dumps(payload).encode()
        ).decode() + "." + \
        "signature"
        
        return token


# Example usage
async def example_mesh_node():
    """Example of a mesh node using SPIRE."""
    
    # 1. Initialize SPIFFE client
    spiffe_client = SpiffeWorkloadAPIClient()
    await spiffe_client.start()
    
    # 2. Create mTLS channel
    mtls = MTLSChannel(spiffe_client)
    
    # 3. Create zero-trust authenticator
    authenticator = ZeroTrustAuthenticator(spiffe_client)
    
    try:
        # 4. Start mTLS server
        server = await mtls.create_server("0.0.0.0:8443")
        logger.info("mTLS server started")
        
        # 5. Connect to peer
        peer_reader, peer_writer = await mtls.connect(
            "peer.example.com:8443",
            "spiffe://x0tta6bl4.mesh/workload/peer-node"
        )
        
        # 6. Authenticate peer
        is_authenticated = await authenticator.authenticate_peer(
            "spiffe://x0tta6bl4.mesh/workload/peer-node",
            required_role="node"
        )
        
        if is_authenticated:
            logger.info("Peer authenticated, starting communication...")
            # Send/receive data...
        
        # 7. Create auth token for API calls
        token = await authenticator.create_auth_token()
        logger.info(f"Created auth token: {token[:50]}...")
        
        # Keep running
        await asyncio.sleep(3600)
        
    finally:
        await spiffe_client.stop()


async def example_health_check():
    """Example health check with SPIRE."""
    from tests.test_spire_integration import SpireHealthChecker
    
    checker = SpireHealthChecker()
    
    # Check SPIRE server
    server_healthy = await checker.check_spire_server("localhost:8081")
    logger.info(f"SPIRE Server healthy: {server_healthy}")
    
    # Check SPIRE agent
    agent_healthy = await checker.check_spire_agent("/run/spire/sockets/agent.sock")
    logger.info(f"SPIRE Agent healthy: {agent_healthy}")
    
    # Check SVID renewal
    renewal_ok = await checker.check_svid_renewal()
    logger.info(f"SVID renewal OK: {renewal_ok}")


if __name__ == "__main__":
    print("SPIRE Integration Examples")
    print("=" * 50)
    print("\n1. Mesh Node Example:")
    print("   asyncio.run(example_mesh_node())")
    print("\n2. Health Check Example:")
    print("   asyncio.run(example_health_check())")
    print("\n3. SPIFFE Workload API Client:")
    print("   client = SpiffeWorkloadAPIClient()")
    print("   await client.start()")
    print("   svid = client.get_svid()")
    print("\n4. mTLS Channel:")
    print("   mtls = MTLSChannel(spiffe_client)")
    print("   reader, writer = await mtls.connect('peer:8443', 'spiffe://...')")
    print("\n5. Zero-Trust Authentication:")
    print("   auth = ZeroTrustAuthenticator(spiffe_client)")
    print("   is_valid = await auth.authenticate_peer('spiffe://...')")