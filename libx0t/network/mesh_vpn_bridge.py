"""
x0tta6bl4 Mesh-VPN Bridge
Integates SOCKS5 proxy with Mesh Network and Rotating Exit Nodes.

Features:
- Batman-adv layer 2 mesh networking integration
- PQC encryption for inter-node traffic
- Multi-hop routing through mesh
- Health monitoring and MAPE-K integration
"""

import asyncio
import logging
import os
import random
import socket
import time
from decimal import Decimal
from typing import Optional, Dict, Any

from src.crypto.pqc_crypto import PQCCrypto
from src.dao.token_rewards import TokenRewards
# Import MeshNode from our existing implementation
from .mesh_node import MeshNode, MeshNodeConfig
from .mesh_router import MeshConnection, MeshRouter

# Batman-adv integration
try:
    from .batman import (
        BatmanHealthMonitor,
        BatmanMetricsCollector,
        BatmanMAPEKLoop,
        create_batman_mapek_loop,
    )
    BATMAN_AVAILABLE = True
except ImportError:
    BATMAN_AVAILABLE = False
    BatmanHealthMonitor = None
    BatmanMetricsCollector = None
    BatmanMAPEKLoop = None

logging.basicConfig(
    level=logging.INFO, format="%(asctime)s [%(levelname)s] %(message)s"
)
logger = logging.getLogger(__name__)


class MeshVPNBridge:
    """Bridge between SOCKS5 client and Mesh Network with P2P routing."""

    # Domains that should bypass mesh routing for compatibility
    BYPASS_DOMAINS = [
        "googleapis.com",
        "cloud.google.com",
        "appspot.com",
        "googleusercontent.com",
        "gstatic.com",
        "spotify.com",
        "scdn.co",
        "spotifycdn.com",
    ]

    def __init__(self, socks_port=10809, node_id=None, use_mesh_routing=True):
        self.socks_port = socks_port
        self.node_id = node_id or os.getenv(
            "NODE_ID", f"node-{random.randint(1000,9999)}"
        )

        # VPS nodes (node-vps*) are exit nodes - they don't route through mesh
        # Only entry nodes (local) use mesh routing
        self.is_exit_node = self.node_id.startswith("node-vps")
        self.use_mesh_routing = use_mesh_routing and not self.is_exit_node

        # Legacy exit nodes (fallback) - configured via environment
        exit_nodes_env = os.getenv("EXIT_NODES", "")
        if exit_nodes_env:
            # Format: "ip:port:weight,ip:port:weight"
            self.exit_nodes = []
            for node_str in exit_nodes_env.split(","):
                parts = node_str.strip().split(":")
                if len(parts) >= 2:
                    self.exit_nodes.append(
                        {
                            "ip": parts[0],
                            "port": int(parts[1]),
                            "weight": int(parts[2]) if len(parts) > 2 else 10,
                        }
                    )
        else:
            # Development defaults (empty for production safety)
            self.exit_nodes = []

        # Initialize Mesh Node
        config = MeshNodeConfig(
            node_id=self.node_id,
            port=random.randint(15000, 20000),
            services=["vpn-bridge"],
        )
        self.mesh = MeshNode(config)
        self.crypto = PQCCrypto()

        # Mesh Router for P2P routing
        self.router = MeshRouter(self.node_id, socks_port)

        # Token Rewards
        contract_address = os.getenv("TOKEN_CONTRACT_ADDRESS", "")
        if not contract_address and os.getenv("ENVIRONMENT") != "production":
            # Development placeholder only
            contract_address = os.getenv("TOKEN_CONTRACT_ADDRESS", "")
        self.rewards = TokenRewards(contract_address=contract_address)

        self.packets_relayed = 0
        self.bytes_relayed = 0
        self.start_time = time.time()

        # Batman-adv integration
        self.batman_interface = os.getenv("BATMAN_INTERFACE", "bat0")
        self.batman_enabled = os.getenv("BATMAN_ENABLED", "false").lower() == "true"
        self.batman_health_monitor: Optional[BatmanHealthMonitor] = None
        self.batman_metrics_collector: Optional[BatmanMetricsCollector] = None
        self.batman_mapek_loop: Optional[BatmanMAPEKLoop] = None
        
        if BATMAN_AVAILABLE and self.batman_enabled:
            self._init_batman_components()

        # Load saved stats if exist
        self.stats_file = "node_stats.json"
        self._load_stats()
    
    def _init_batman_components(self) -> None:
        """Initialize Batman-adv components for mesh networking."""
        try:
            # Initialize health monitor
            self.batman_health_monitor = BatmanHealthMonitor(
                node_id=self.node_id,
                interface=self.batman_interface,
                enable_prometheus=True,
                alert_callback=self._on_batman_health_alert,
            )
            logger.info(f"Batman health monitor initialized on {self.batman_interface}")
            
            # Initialize metrics collector
            self.batman_metrics_collector = BatmanMetricsCollector(
                node_id=self.node_id,
                interface=self.batman_interface,
            )
            logger.info("Batman metrics collector initialized")
            
            # Initialize MAPE-K loop for autonomous healing
            self.batman_mapek_loop = create_batman_mapek_loop(
                node_id=self.node_id,
                interface=self.batman_interface,
                auto_heal=True,
            )
            logger.info("Batman MAPE-K loop initialized with auto-heal enabled")
            
        except Exception as e:
            logger.error(f"Failed to initialize Batman components: {e}")
            self.batman_enabled = False
    
    def _on_batman_health_alert(self, health_report) -> None:
        """Callback for Batman health alerts."""
        logger.warning(
            f"Batman health alert: {health_report.overall_status.value} "
            f"(score: {health_report.overall_score:.2f})"
        )
        
        # Log recommendations
        for recommendation in health_report.recommendations:
            logger.info(f"Recommendation: {recommendation}")

    def _load_stats(self):
        try:
            import json

            if os.path.exists(self.stats_file):
                with open(self.stats_file, "r") as f:
                    data = json.load(f)
                    self.packets_relayed = data.get("packets", 0)
                    self.bytes_relayed = data.get("bytes", 0)
                    # Restore balance in rewards
                    self.rewards.balance = Decimal(str(data.get("balance", "1000.0")))
                    self.rewards.daily_earnings = Decimal(
                        str(data.get("earnings_today", "0.0"))
                    )
        except Exception as e:
            logger.error(f"Failed to load stats: {e}")

    async def _stats_loop(self):
        import json

        while True:
            await asyncio.sleep(1)
            try:
                stats = {
                    "node_id": self.node_id,
                    "packets": self.packets_relayed,
                    "bytes": self.bytes_relayed,
                    "uptime": time.time() - self.start_time,
                    "balance": str(self.rewards.balance),
                    "earnings_today": str(self.rewards.daily_earnings),
                    "active_connections": 0,
                    "mesh": self.router.get_stats(),
                    "batman": self._get_batman_stats(),
                }

                # Fix async bottleneck: wrap file I/O in thread pool
                def _write_stats():
                    with open(self.stats_file, "w") as f:
                        json.dump(stats, f)

                await asyncio.to_thread(_write_stats)
            except Exception as e:
                logger.error(f"Stats save error: {e}")
    
    def _get_batman_stats(self) -> Dict[str, Any]:
        """Get Batman-adv statistics."""
        if not self.batman_enabled or not self.batman_metrics_collector:
            return {"enabled": False}
        
        snapshot = self.batman_metrics_collector.get_last_snapshot()
        if snapshot:
            return {
                "enabled": True,
                "interface": self.batman_interface,
                "originators_count": snapshot.originators_count,
                "avg_link_quality": snapshot.avg_link_quality,
                "gateways_count": snapshot.gateways_count,
                "latency_ms": snapshot.latency_ms,
                "packet_loss_percent": snapshot.packet_loss_percent,
            }
        
        return {"enabled": True, "interface": self.batman_interface}
    
    async def _batman_health_loop(self) -> None:
        """Background task for Batman health monitoring."""
        if not self.batman_enabled or not self.batman_health_monitor:
            return
        
        while True:
            try:
                # Run health checks
                report = await self.batman_health_monitor.run_health_checks()
                
                # Collect metrics
                if self.batman_metrics_collector:
                    await self.batman_metrics_collector.collect()
                
                # Log health status periodically
                logger.debug(
                    f"Batman health: {report.overall_status.value} "
                    f"(score: {report.overall_score:.2f})"
                )
                
                await asyncio.sleep(30)  # Check every 30 seconds
                
            except asyncio.CancelledError:
                break
            except Exception as e:
                logger.error(f"Batman health loop error: {e}")
                await asyncio.sleep(30)
    
    async def _batman_mapek_loop(self) -> None:
        """Background task for Batman MAPE-K autonomous healing."""
        if not self.batman_enabled or not self.batman_mapek_loop:
            return
        
        try:
            await self.batman_mapek_loop.start()
        except asyncio.CancelledError:
            pass
        except Exception as e:
            logger.error(f"Batman MAPE-K loop error: {e}")

    async def start(self):
        """Start the bridge."""
        # Start stats loop
        asyncio.create_task(self._stats_loop())

        # Start mesh node
        await self.mesh.start()

        # Start mesh router
        await self.router.start()
        
        # Start Batman-adv components if enabled
        if self.batman_enabled:
            logger.info("Starting Batman-adv components...")
            
            # Start health monitoring loop
            asyncio.create_task(self._batman_health_loop())
            
            # Start MAPE-K autonomous healing loop
            asyncio.create_task(self._batman_mapek_loop())
            
            logger.info("Batman-adv components started")

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
        if self.batman_enabled:
            logger.info(f"   Batman-adv: ENABLED ({self.batman_interface})")
        logger.info("=" * 60)

        server = await asyncio.start_server(
            self.handle_connection, "0.0.0.0", self.socks_port  # nosec B104
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

            writer.write(b"\x05\x00")  # No auth required
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
                writer.write(
                    b"\x05\x01\x00\x01\x00\x00\x00\x00\x00\x00"
                )  # General failure
                await writer.drain()
                return

            # Check if target should bypass mesh routing
            should_bypass_mesh = any(
                target_host.endswith(d) or target_host == d for d in self.BYPASS_DOMAINS
            )
            if should_bypass_mesh:
                logger.info(
                    f"🔄 Bypassing mesh for {target_host} (Google Cloud/Spotify domain)"
                )

            # 4. Establish connection through mesh
            if self.use_mesh_routing and self.router.peers and not should_bypass_mesh:
                # Multi-hop mesh routing
                mesh_conn = MeshConnection(
                    self.router, f"{target_host}:{target_port}", self.crypto
                )

                if await mesh_conn.connect_multi_hop(target_host, target_port):
                    # Success - send OK to client
                    writer.write(b"\x05\x00\x00\x01\x00\x00\x00\x00\x00\x00")
                    await writer.drain()

                    remote_reader, remote_writer = mesh_conn.get_tunnel()
                    if remote_reader and remote_writer:
                        logger.info(
                            f"🔗 Mesh tunnel to {target_host}:{target_port} ({mesh_conn.hops_completed} hops)"
                        )
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
                        asyncio.open_connection(target_host, target_port), timeout=10.0
                    )
                    writer.write(b"\x05\x00\x00\x01\x00\x00\x00\x00\x00\x00")
                    await writer.drain()
                except Exception as e:
                    logger.error(f"Direct connection failed: {e}")
                    writer.write(
                        b"\x05\x05\x00\x01\x00\x00\x00\x00\x00\x00"
                    )  # Connection refused
                    await writer.drain()
                    return

            # 5. Relay data
            await asyncio.gather(
                self._relay_stream(reader, remote_writer, "upstream"),
                self._relay_stream(remote_reader, writer, "downstream"),
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
        weights = [n["weight"] for n in self.exit_nodes]
        return random.choices(self.exit_nodes, weights=weights)[0]

    def _parse_socks_request(self, data):
        """
        Parse SOCKS5 request (simplified).
        Data format: Ver(1) Cmd(1) Rsv(1) Atyp(1) Addr(?) Port(2)
        """
        # This is a very basic parser
        atyp = data[3]
        if atyp == 1:  # IPv4
            addr = socket.inet_ntoa(data[4:8])
            port = int.from_bytes(data[8:10], "big")
            return addr, port
        elif atyp == 3:  # Domain
            length = data[4]
            addr = data[5 : 5 + length].decode()
            port = int.from_bytes(data[5 + length : 5 + length + 2], "big")
            return addr, port
        elif atyp == 4:  # IPv6
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
    
    def get_batman_status(self) -> Dict[str, Any]:
        """
        Get Batman-adv status for this node.
        
        Returns:
            Dict with Batman health, metrics, and MAPE-K status
        """
        if not self.batman_enabled:
            return {"enabled": False}
        
        status = {
            "enabled": True,
            "interface": self.batman_interface,
            "node_id": self.node_id,
        }
        
        # Get health status
        if self.batman_health_monitor:
            last_report = self.batman_health_monitor.get_last_report()
            if last_report:
                status["health"] = {
                    "overall_status": last_report.overall_status.value,
                    "overall_score": last_report.overall_score,
                    "recommendations": last_report.recommendations,
                }
                status["health_trend"] = self.batman_health_monitor.get_health_trend()
        
        # Get metrics
        if self.batman_metrics_collector:
            snapshot = self.batman_metrics_collector.get_last_snapshot()
            if snapshot:
                status["metrics"] = snapshot.to_dict()
        
        # Get MAPE-K status
        if self.batman_mapek_loop:
            status["mapek"] = self.batman_mapek_loop.get_status()
        
        return status
    
    async def trigger_batman_healing(self, action: str) -> Dict[str, Any]:
        """
        Manually trigger a Batman healing action.
        
        Args:
            action: Healing action to perform
        
        Returns:
            Dict with action result
        """
        if not self.batman_enabled:
            return {"success": False, "error": "Batman not enabled"}
        
        if not self.batman_mapek_loop:
            return {"success": False, "error": "MAPE-K loop not initialized"}
        
        from .batman.mape_k_integration import BatmanRecoveryAction, BatmanMAPEKExecutor
        
        try:
            recovery_action = BatmanRecoveryAction(action)
        except ValueError:
            valid_actions = [a.value for a in BatmanRecoveryAction]
            return {
                "success": False,
                "error": f"Invalid action. Valid actions: {valid_actions}",
            }
        
        executor = BatmanMAPEKExecutor(interface=self.batman_interface)
        
        try:
            result = await executor._execute_action(recovery_action, None)
            return {
                "success": result.get("status") == "success",
                "action": action,
                "result": result,
            }
        except Exception as e:
            return {
                "success": False,
                "action": action,
                "error": str(e),
            }


if __name__ == "__main__":
    bridge = MeshVPNBridge()
    try:
        asyncio.run(bridge.start())
    except KeyboardInterrupt:
        pass
