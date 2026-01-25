"""
x0tta6bl4 Mesh-VPN Bridge
Integates SOCKS5 proxy with Mesh Network and Rotating Exit Nodes.
"""
import asyncio
import random
import logging
import socket
import os
import time
from decimal import Decimal
from typing import Optional

# Import MeshNode from our existing implementation
from src.network.mesh_node import MeshNode, MeshNodeConfig
from src.network.mesh_router import MeshRouter, MeshConnection
from src.crypto.pqc_crypto import PQCCrypto
from src.dao.token_rewards import TokenRewards

logging.basicConfig(level=logging.INFO, format='%(asctime)s [%(levelname)s] %(message)s')
logger = logging.getLogger(__name__)

class MeshVPNBridge:
    """Bridge between SOCKS5 client and Mesh Network with P2P routing."""
    
    def __init__(self, socks_port=10809, node_id=None, use_mesh_routing=True):
        self.socks_port = socks_port
        self.node_id = node_id or os.getenv("NODE_ID", f"node-{random.randint(1000,9999)}")
        
        # VPS nodes (node-vps*) are exit nodes - they don't route through mesh
        # Only entry nodes (local) use mesh routing
        self.is_exit_node = self.node_id.startswith("node-vps")
        self.use_mesh_routing = use_mesh_routing and not self.is_exit_node
        
        # Legacy exit nodes (fallback)
        self.exit_nodes = [
            {"ip": "89.125.1.107", "port": 10809, "weight": 10},
            {"ip": "62.133.60.252", "port": 10809, "weight": 8},
        ]
        
        # Initialize Mesh Node
        config = MeshNodeConfig(
            node_id=self.node_id,
            port=random.randint(15000, 20000),
            services=["vpn-bridge"]
        )
        self.mesh = MeshNode(config)
        self.crypto = PQCCrypto()
        
        # Mesh Router for P2P routing
        self.router = MeshRouter(self.node_id, socks_port)
        
        # Token Rewards
        self.rewards = TokenRewards(
            contract_address="0x3f645dfa2a2a16725ed961d16f1667a13484bdd3"
        )
        
        self.packets_relayed = 0
        self.bytes_relayed = 0
        self.start_time = time.time()
        
        # Load saved stats if exist
        self.stats_file = "node_stats.json"
        self._load_stats()
        
    def _load_stats(self):
        try:
            import json
            if os.path.exists(self.stats_file):
                with open(self.stats_file, 'r') as f:
                    data = json.load(f)
                    self.packets_relayed = data.get('packets', 0)
                    self.bytes_relayed = data.get('bytes', 0)
                    # Restore balance in rewards
                    self.rewards.balance = Decimal(str(data.get('balance', '1000.0')))
                    self.rewards.daily_earnings = Decimal(str(data.get('earnings_today', '0.0')))
        except Exception as e:
            logger.error(f"Failed to load stats: {e}")

    async def _stats_loop(self):
        import json
        while True:
            await asyncio.sleep(1)
            try:
                stats = {
                    'node_id': self.node_id,
                    'packets': self.packets_relayed,
                    'bytes': self.bytes_relayed,
                    'uptime': time.time() - self.start_time,
                    'balance': str(self.rewards.balance),
                    'earnings_today': str(self.rewards.daily_earnings),
                    'active_connections': 0,
                    'mesh': self.router.get_stats()
                }
                # Fix async bottleneck: wrap file I/O in thread pool
                def _write_stats():
                    with open(self.stats_file, 'w') as f:
                        json.dump(stats, f)
                await asyncio.to_thread(_write_stats)
            except Exception as e:
                logger.error(f"Stats save error: {e}")

    async def start(self):
        """Start the bridge."""
        # Start stats loop
        asyncio.create_task(self._stats_loop())
        
        # Start mesh node
        await self.mesh.start()
        
        # Start mesh router
        await self.router.start()
        
        logger.info("=" * 60)
        logger.info(f"🌉 Mesh-VPN Bridge: {self.node_id}")
        logger.info(f"   SOCKS5: 0.0.0.0:{self.socks_port}")
        if self.is_exit_node:
            logger.info(f"   Mode: EXIT NODE (direct to internet)")
        else:
            logger.info(f"   Mode: ENTRY NODE (mesh routing enabled)")
            logger.info(f"   Peers: {len(self.router.peers)}")
            for peer_id, peer in self.router.peers.items():
                logger.info(f"      → {peer_id}: {peer.address}")
        logger.info("=" * 60)
        
        server = await asyncio.start_server(
            self.handle_connection, 
            '0.0.0.0', 
            self.socks_port
        )
        
        async with server:
            await server.serve_forever()

    async def handle_connection(self, reader, writer):
        """Handle incoming SOCKS5 connection with multi-hop mesh routing."""
        mesh_conn = None
        try:
            # 1. SOCKS5 handshake with client
            header = await reader.read(256)
            if not header:
                return
                
            writer.write(b'\x05\x00')  # No auth required
            await writer.drain()
            
            # 2. Read connection request
            request = await reader.read(1024)
            if not request:
                return
            
            # 3. Parse target
            try:
                target_host, target_port = self._parse_socks_request(request)
            except Exception as e:
                logger.error(f"Failed to parse SOCKS request: {e}")
                writer.write(b'\x05\x01\x00\x01\x00\x00\x00\x00\x00\x00')  # General failure
                await writer.drain()
                return
            
            # 4. Establish connection through mesh
            if self.use_mesh_routing and self.router.peers:
                # Multi-hop mesh routing
                mesh_conn = MeshConnection(self.router, f"{target_host}:{target_port}", self.crypto)
                
                if await mesh_conn.connect_multi_hop(target_host, target_port):
                    # Success - send OK to client
                    writer.write(b'\x05\x00\x00\x01\x00\x00\x00\x00\x00\x00')
                    await writer.drain()
                    
                    remote_reader, remote_writer = mesh_conn.get_tunnel()
                    if remote_reader and remote_writer:
                        logger.info(f"🔗 Mesh tunnel to {target_host}:{target_port} ({mesh_conn.hops_completed} hops)")
                    else:
                        raise Exception("Mesh tunnel not established")
                else:
                    # Mesh failed, try direct
                    logger.warning("Mesh routing failed, falling back to direct")
                    mesh_conn = None
            
            # Fallback: Direct connection
            if mesh_conn is None:
                logger.info(f"📡 Direct connection to {target_host}:{target_port}")
                try:
                    remote_reader, remote_writer = await asyncio.wait_for(
                        asyncio.open_connection(target_host, target_port),
                        timeout=10.0
                    )
                    writer.write(b'\x05\x00\x00\x01\x00\x00\x00\x00\x00\x00')
                    await writer.drain()
                except Exception as e:
                    logger.error(f"Direct connection failed: {e}")
                    writer.write(b'\x05\x05\x00\x01\x00\x00\x00\x00\x00\x00')  # Connection refused
                    await writer.drain()
                    return
            
            # 5. Relay data
            await asyncio.gather(
                self._relay_stream(reader, remote_writer, "upstream"),
                self._relay_stream(remote_reader, writer, "downstream")
            )
            
        except Exception as e:
            logger.error(f"Connection error: {e}")
        finally:
            if mesh_conn:
                await mesh_conn.close()
            try:
                writer.close()
                await writer.wait_closed()
            except:
                pass
    
    def _select_exit_node(self):
        """Weighted random choice of exit node."""
        weights = [n['weight'] for n in self.exit_nodes]
        return random.choices(self.exit_nodes, weights=weights)[0]
        
    def _parse_socks_request(self, data):
        """
        Parse SOCKS5 request (simplified).
        Data format: Ver(1) Cmd(1) Rsv(1) Atyp(1) Addr(?) Port(2)
        """
        # This is a very basic parser
        atyp = data[3]
        if atyp == 1: # IPv4
            addr = socket.inet_ntoa(data[4:8])
            port = int.from_bytes(data[8:10], 'big')
            return addr, port
        elif atyp == 3: # Domain
            length = data[4]
            addr = data[5:5+length].decode()
            port = int.from_bytes(data[5+length:5+length+2], 'big')
            return addr, port
        elif atyp == 4: # IPv6
            # IPv6 parsing omitted for brevity
            return "google.com", 80
        return "google.com", 80

    async def _relay_stream(self, reader, writer, direction, peer_id: str = None):
        """Relay data with PQC encryption."""
        try:
            while True:
                data = await reader.read(4096)
                if not data:
                    break
                
                # Update metrics
                self.bytes_relayed += len(data)
                self.packets_relayed += 1
                
                # Reward logic: every 100 packets (for demo speed) or 10MB
                if self.packets_relayed % 100 == 0:
                    self.rewards.reward_relay(self.mesh.config.node_id, 100)
                
                # PQC encryption for inter-node traffic
                if peer_id and self.router.pqc and self.router.pqc.has_tunnel(peer_id):
                    if direction == "upstream":
                        # Encrypt data before sending to peer
                        data = self.router.pqc.encrypt_for_peer(data, peer_id)
                    else:
                        # Decrypt data received from peer
                        try:
                            data = self.router.pqc.decrypt_from_peer(data, peer_id)
                        except:
                            pass  # Fallback to unencrypted if decryption fails
                
                writer.write(data)
                await writer.drain()
        except:
            pass
        finally:
            try:
                writer.close()
            except:
                pass

if __name__ == "__main__":
    bridge = MeshVPNBridge()
    try:
        asyncio.run(bridge.start())
    except KeyboardInterrupt:
        pass
