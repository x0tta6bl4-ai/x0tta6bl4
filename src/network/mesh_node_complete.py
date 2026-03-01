"""
CompleteMeshNode - Полная интеграция Discovery + Routing + Transport.
Готовый к использованию mesh node с application API.
"""

import asyncio
import logging
import os
from dataclasses import dataclass
from typing import Any, Callable, Dict, List, Optional

from src.network.discovery import MeshDiscovery, PeerInfo
from src.network.routing import MeshRouter, RouteEntry
from src.network.routing.packet_handler import RoutingPacket
from src.network.transport.udp_shaped import ShapedUDPTransport
from src.network.transport.ghost_proto import GhostTransport
from src.security.pqc import PQCKeyExchange
from src.network.integrity import verify_integrity

logger = logging.getLogger(__name__)


@dataclass
class MeshConfig:
    """Конфигурация Mesh Node."""

    node_id: str
    port: int = 5000
    agent_version: str = "v3.4.0-alpha"
    strict_integrity: bool = False

    # Transport & Obfuscation
    transport_type: str = "udp_shaped"  # "udp_shaped" or "ghost"
    obfuscation: str = "none"
    obfuscation_key: str = "x0tta6bl4"
    traffic_profile: str = "none"
    
    # Security (PQC)
    enable_pqc: bool = False
    pqc_master_key: Optional[bytes] = None  # 32 bytes for Ghost/ChaCha20

    # Discovery
    enable_discovery: bool = True
    enable_multicast: bool = True
    bootstrap_nodes: List[tuple] = None

    def __post_init__(self):
        if self.bootstrap_nodes is None:
            self.bootstrap_nodes = []


class CompleteMeshNode:
    """
    Полный Mesh Node с multi-hop routing и PQC Handshake.
    """

    def __init__(self, config: MeshConfig):
        self.config = config
        self.node_id = config.node_id

        # Components
        self._transport: Optional[ShapedUDPTransport] = None
        self._discovery: Optional[MeshDiscovery] = None
        self._router: Optional[MeshRouter] = None
        self._ghost: Optional[GhostTransport] = None
        self._kem: Optional[PQCKeyExchange] = None

        # Peer and Key mapping
        self._peer_addresses: Dict[str, tuple] = {}
        self._session_keys: Dict[str, bytes] = {} # peer_id -> key
        self._ghost_transports: Dict[str, GhostTransport] = {} # peer_id -> transport
        self._pending_handshakes: Dict[str, bytes] = {} # peer_id -> our_secret_key
        self._handshake_in_progress: set[str] = set()
        self._pending_packets: Dict[str, List[bytes]] = {}
        self._max_pending_packets_per_peer = 128

        # Initialize components
        if config.transport_type == "ghost":
            self._kem = PQCKeyExchange()
            logger.info(f"🛡️ PQC KEM initialized for node {self.node_id}")

        # Callbacks
        self._message_handler: Optional[Callable] = None
        self._peer_handler: Optional[Callable] = None
        self._peer_lost_handler: Optional[Callable] = None

        self._running = False

    async def start(self):
        """Запустить node."""
        logger.info(f"Starting CompleteMeshNode: {self.node_id}")

        # 0. Supply Chain Integrity Check
        if os.getenv("X0T_SKIP_INTEGRITY") != "1":
            verified = await verify_integrity(self.node_id, self.config.agent_version)
            if not verified:
                msg = f"🚨 FATAL: Integrity check failed for node {self.node_id}"
                logger.error(msg)
                if self.config.strict_integrity:
                    raise RuntimeError(msg)
                else:
                    logger.warning("Continuing in non-strict mode despite integrity failure.")

        # 1. Transport
        self._transport = ShapedUDPTransport(
            local_port=self.config.port,
            traffic_profile=self.config.traffic_profile,
            obfuscation=self.config.obfuscation,
            obfuscation_key=self.config.obfuscation_key,
        )

        @self._transport.on_receive
        async def on_transport_receive(data: bytes, address: tuple):
            await self._handle_transport_packet(data, address)

        await self._transport.start()

        # 2. Router
        self._router = MeshRouter(self.node_id)
        # The router is synchronous; wrap async callbacks so it can call them.
        self._router.set_send_callback(self._make_sync_send_cb())
        self._router.set_receive_callback(self._make_sync_receive_cb())
        self._router.start()

        # 3. Discovery
        if self.config.enable_discovery:
            self._discovery = MeshDiscovery(
                node_id=self.node_id,
                service_port=self.config.port,
                services=["mesh"],
                bootstrap_nodes=self.config.bootstrap_nodes,
                enable_multicast=self.config.enable_multicast,
            )

            @self._discovery.on_peer_discovered
            async def on_peer(peer: PeerInfo):
                await self._handle_peer_discovered(peer)

            @self._discovery.on_peer_lost
            async def on_lost(peer: PeerInfo):
                await self._handle_peer_lost(peer)

            await self._discovery.start()

        self._running = True

        logger.info(
            f"CompleteMeshNode started: {self.node_id} on port {self._transport.local_port}"
        )

    async def stop(self):
        """Остановить node."""
        self._running = False

        if self._router:
            self._router.stop()  # sync method

        if self._discovery:
            await self._discovery.stop()

        if self._transport:
            await self._transport.stop()

        logger.info(f"CompleteMeshNode stopped: {self.node_id}")

    # === Application API ===

    async def send_message(self, destination: str, payload: bytes) -> bool:
        """
        Отправить сообщение к destination node.
        Автоматически выполняет route discovery и multi-hop forwarding.
        """
        if not self._router:
            return False

        # For direct neighbors, seed a direct route and send a DATA packet.
        if destination in self._peer_addresses and not self._router.has_route(destination):
            from src.network.routing.route_table import RouteEntry
            self._router.route_table.add_route(RouteEntry(
                destination=destination,
                next_hop=destination,
                hop_count=1,
                seq_num=0,
            ))

        from src.network.routing.packet_handler import PacketType, RoutingPacket

        async def _send_data_packet(nh: str) -> bool:
            data_pkt = RoutingPacket(
                packet_type=PacketType.DATA,
                source=self.node_id,
                destination=destination,
                seq_num=self._router.packet_handler.next_seq_num(),
                hop_count=0,
                payload=payload,
            )
            return await self._router_send(data_pkt.to_bytes(), nh)

        success, next_hop = self._router.send_data(destination, payload)
        if success and next_hop:
            return await _send_data_packet(next_hop)

        # Route discovery was initiated; wait briefly and retry.
        await asyncio.sleep(0.4)
        success, next_hop = self._router.send_data(destination, payload)
        if success and next_hop:
            return await _send_data_packet(next_hop)
        return False

    async def broadcast(self, payload: bytes) -> int:
        """Отправить сообщение всем известным peers."""
        sent = 0
        for peer_id in self._peer_addresses.keys():
            if await self.send_message(peer_id, payload):
                sent += 1
        return sent

    def on_message(self, handler: Callable):
        """
        Декоратор для обработки входящих сообщений.

        @node.on_message
        async def handle(source: str, payload: bytes):
            print(f"From {source}: {payload}")
        """
        self._message_handler = handler
        return handler

    def on_peer_discovered(self, handler: Callable):
        """Callback при обнаружении нового peer."""
        self._peer_handler = handler
        return handler

    def on_peer_lost(self, handler: Callable):
        """Callback при потере peer."""
        self._peer_lost_handler = handler
        return handler

    # === Getters ===

    def get_peers(self) -> List[str]:
        """Список известных peer IDs."""
        return list(self._peer_addresses.keys())

    def get_routes(self) -> Dict[str, RouteEntry]:
        """Таблица маршрутизации."""
        if self._router:
            return dict(self._router.route_table._routes)
        return {}

    def get_stats(self) -> dict:
        """Полная статистика."""
        stats = {
            "node_id": self.node_id,
            "port": self._transport.local_port if self._transport else self.config.port,
            "running": self._running,
            "peers_count": len(self._peer_addresses),
            "peers": list(self._peer_addresses.keys()),
        }

        if self._router:
            stats["routing"] = self._router.get_all_stats()

        if self._transport:
            stats["transport"] = self._transport.get_stats()

        return stats

    # === Sync wrappers for router callbacks ===

    def _make_sync_send_cb(self):
        """Sync send callback for the (sync) router; schedules async UDP delivery."""
        def _cb(packet, next_hop: str) -> None:
            packet_bytes = packet.to_bytes() if hasattr(packet, "to_bytes") else bytes(packet)
            address = self._peer_addresses.get(next_hop)
            if not address or not self._transport:
                return
            try:
                loop = asyncio.get_event_loop()
                loop.create_task(self._transport.send_to(packet_bytes, address))
            except Exception:
                pass
        return _cb

    def _make_sync_receive_cb(self):
        """Sync receive callback for the router; schedules async app delivery."""
        def _cb(source: str, payload: bytes) -> None:
            if not self._message_handler:
                return
            try:
                loop = asyncio.get_event_loop()
                loop.create_task(self._message_handler(source, payload))
            except Exception:
                pass
        return _cb

    # === Internal Handlers ===

    async def _handle_transport_packet(self, data: bytes, address: tuple):
        """Обработка пакета от transport (с поддержкой Ghost и PQC)."""
        from src.network.routing.packet_handler import PacketType, RoutingPacket
        
        # 1. Identify neighbor
        from_neighbor = None
        for peer_id, peer_addr in self._peer_addresses.items():
            if peer_addr[0] == address[0]:
                from_neighbor = peer_id
                break

        # 2. Ghost Decapsulation if enabled for this peer
        if from_neighbor and from_neighbor in self._ghost_transports:
            decrypted = self._ghost_transports[from_neighbor].unwrap_packet(data)
            if not decrypted:
                logger.debug(f"Failed to unwrap Ghost packet from {from_neighbor}")
                return
            data = decrypted

        try:
            packet = RoutingPacket.from_bytes(data)
            
            # PQC Handshake Logic
            if packet.packet_type == PacketType.HANDSHAKE_INIT:
                await self._handle_handshake_init(packet, address)
                return
            elif packet.packet_type == PacketType.HANDSHAKE_RESPONSE:
                await self._handle_handshake_response(packet)
                return
                
            # Normal Routing
            if packet.packet_type == PacketType.DATA:
                if packet.destination == self.node_id:
                    await self._router_receive(packet.source, packet.payload)
                else:
                    next_hop = self._router.get_next_hop(packet.destination)
                    if next_hop:
                        await self._router_send(packet.to_bytes(), next_hop)
            else:
                response = self._router.handle_packet(packet, from_neighbor or packet.source)
                if response:
                    await self._router_send(response.to_bytes(), from_neighbor or packet.source)
        except Exception as exc:
            logger.debug(f"Packet parse error from {address}: {exc}")

    async def _initiate_pqc_handshake(self, peer_id: str):
        """Alice: Phase 1 - Send our PQC Public Key."""
        if not self._kem:
            self._handshake_in_progress.discard(peer_id)
            return

        logger.info(f"🤝 Initiating PQC Handshake with {peer_id}")
        try:
            keypair = self._kem.generate_keypair()
            self._pending_handshakes[peer_id] = keypair.secret_key

            from src.network.routing.packet_handler import PacketType, RoutingPacket
            pkt = RoutingPacket(
                packet_type=PacketType.HANDSHAKE_INIT,
                source=self.node_id,
                destination=peer_id,
                seq_num=0,
                payload=keypair.public_key
            )
            sent = await self._router_send_raw(pkt.to_bytes(), peer_id)
            if not sent:
                self._pending_handshakes.pop(peer_id, None)
                self._handshake_in_progress.discard(peer_id)
                logger.warning("Failed to send PQC handshake init to %s", peer_id)
        except Exception as exc:
            self._pending_handshakes.pop(peer_id, None)
            self._handshake_in_progress.discard(peer_id)
            logger.warning("PQC handshake init failed for %s: %s", peer_id, exc)

    async def _handle_handshake_init(self, packet: RoutingPacket, address: tuple):
        """Bob: Phase 2 - Encapsulate shared secret."""
        if not self._kem: return
        
        peer_id = packet.source
        peer_public_key = packet.payload
        logger.info(f"🤝 Received PQC Handshake Init from {peer_id}")
        
        ciphertext, shared_secret = self._kem.encapsulate(peer_public_key)
        
        # Bob now has the session key
        self._session_keys[peer_id] = shared_secret[:32]
        self._ghost_transports[peer_id] = GhostTransport(self._session_keys[peer_id])
        self._handshake_in_progress.discard(peer_id)
        
        from src.network.routing.packet_handler import PacketType, RoutingPacket
        response_pkt = RoutingPacket(
            packet_type=PacketType.HANDSHAKE_RESPONSE,
            source=self.node_id,
            destination=peer_id,
            seq_num=0,
            payload=ciphertext
        )
        await self._router_send_raw(response_pkt.to_bytes(), peer_id)
        logger.info(f"✅ Bob: Session key established with {peer_id}")
        await self._flush_pending_packets(peer_id)

    async def _handle_handshake_response(self, packet: RoutingPacket):
        """Alice: Phase 3 - Decapsulate and establish transport."""
        peer_id = packet.source
        ciphertext = packet.payload
        
        secret_key = self._pending_handshakes.pop(peer_id, None)
        if not secret_key:
            logger.warning(f"Unexpected Handshake Response from {peer_id}")
            return
            
        shared_secret = self._kem.decapsulate(secret_key, ciphertext)
        self._session_keys[peer_id] = shared_secret[:32]
        self._ghost_transports[peer_id] = GhostTransport(self._session_keys[peer_id])
        self._handshake_in_progress.discard(peer_id)
        logger.info(f"✅ Alice: Session key established with {peer_id}")
        await self._flush_pending_packets(peer_id)

    async def _router_send_raw(self, data: bytes, next_hop: str) -> bool:
        """Helper to send raw data without Ghost wrapping (used for handshake)."""
        address = self._peer_addresses.get(next_hop)
        if not address or not self._transport:
            return False
        return await self._transport.send_to(data, address)

    async def _router_send(self, packet_bytes: bytes, next_hop: str) -> bool:
        """Callback для отправки пакета от router (с поддержкой Peer-specific Ghost)."""
        address = self._peer_addresses.get(next_hop)
        if not address or not self._transport:
            logger.warning(f"No address for next_hop: {next_hop}")
            return False

        # Apply Ghost wrapping if session key established
        if next_hop in self._ghost_transports:
            packet_bytes = self._ghost_transports[next_hop].wrap_packet(packet_bytes)
        elif self.config.transport_type == "ghost":
            self._queue_pending_packet(next_hop, packet_bytes)
            if next_hop not in self._handshake_in_progress:
                self._handshake_in_progress.add(next_hop)
                asyncio.create_task(self._initiate_pqc_handshake(next_hop))
                logger.debug("Queued packet and started PQC handshake for %s", next_hop)
            else:
                logger.debug("Queued packet while waiting PQC handshake for %s", next_hop)
            return True

        return await self._transport.send_to(packet_bytes, address)

    def _queue_pending_packet(self, peer_id: str, packet_bytes: bytes) -> None:
        queue = self._pending_packets.setdefault(peer_id, [])
        if len(queue) >= self._max_pending_packets_per_peer:
            queue.pop(0)
            logger.warning("Pending packet queue overflow for %s, dropping oldest packet", peer_id)
        queue.append(packet_bytes)

    async def _flush_pending_packets(self, peer_id: str) -> None:
        queued = self._pending_packets.get(peer_id, [])
        if not queued:
            return

        transport = self._ghost_transports.get(peer_id)
        address = self._peer_addresses.get(peer_id)
        if not transport or not address or not self._transport:
            return

        self._pending_packets.pop(peer_id, None)
        for raw_packet in queued:
            wrapped = transport.wrap_packet(raw_packet)
            await self._transport.send_to(wrapped, address)

        logger.info("Flushed %d queued packet(s) to %s", len(queued), peer_id)

    async def _router_receive(self, source: str, payload: bytes):
        """Callback для доставки данных от router."""
        if self._message_handler:
            await self._message_handler(source, payload)

    async def _handle_peer_discovered(self, peer: PeerInfo):
        """Обработка обнаруженного peer."""
        if peer.addresses:
            self._peer_addresses[peer.node_id] = peer.addresses[0]

            # Добавляем как соседа в router
            if self._router:
                self._router.add_neighbor(peer.node_id)

            logger.info(f"Peer discovered: {peer.node_id} @ {peer.addresses[0]}")

            if self._peer_handler:
                await self._peer_handler(peer.node_id)

    async def _handle_peer_lost(self, peer: PeerInfo):
        """Обработка потерянного peer."""
        if peer.node_id in self._peer_addresses:
            del self._peer_addresses[peer.node_id]
        self._session_keys.pop(peer.node_id, None)
        self._ghost_transports.pop(peer.node_id, None)
        self._pending_handshakes.pop(peer.node_id, None)
        self._pending_packets.pop(peer.node_id, None)
        self._handshake_in_progress.discard(peer.node_id)

        if self._router:
            self._router.remove_neighbor(peer.node_id)

        logger.info(f"Peer lost: {peer.node_id}")

        if self._peer_lost_handler:
            await self._peer_lost_handler(peer.node_id)


# === Convenience Functions ===


async def create_mesh_node(
    node_id: str,
    port: int = 5000,
    traffic_profile: str = "none",
    obfuscation: str = "none",
) -> CompleteMeshNode:
    """
    Быстрое создание и запуск mesh node.

    Usage:
        node = await create_mesh_node("alice", 5001)
        await node.send_message("bob", b"Hello!")
    """
    config = MeshConfig(
        node_id=node_id,
        port=port,
        traffic_profile=traffic_profile,
        obfuscation=obfuscation,
    )

    node = CompleteMeshNode(config)
    await node.start()
    return node
