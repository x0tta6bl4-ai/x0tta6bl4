"""
CompleteMeshNode - Полная интеграция Discovery + Routing + Transport.
Готовый к использованию mesh node с application API.
"""

import asyncio
import logging
from dataclasses import dataclass
from typing import Any, Callable, Dict, List, Optional

from src.network.discovery import MeshDiscovery, PeerInfo
from src.network.routing import MeshRouter, RouteEntry
from src.network.transport.udp_shaped import ShapedUDPTransport

logger = logging.getLogger(__name__)


@dataclass
class MeshConfig:
    """Конфигурация Mesh Node."""

    node_id: str
    port: int = 5000

    # Transport
    obfuscation: str = "none"
    obfuscation_key: str = "x0tta6bl4"
    traffic_profile: str = "none"

    # Discovery
    enable_discovery: bool = True
    enable_multicast: bool = True
    bootstrap_nodes: List[tuple] = None

    def __post_init__(self):
        if self.bootstrap_nodes is None:
            self.bootstrap_nodes = []


class CompleteMeshNode:
    """
    Полный Mesh Node с multi-hop routing.

    Usage:
        node = CompleteMeshNode(MeshConfig(node_id="alice", port=5001))

        @node.on_message
        async def handle(source: str, payload: bytes):
            print(f"Message from {source}: {payload}")

        await node.start()

        # Отправка сообщения (автоматический routing)
        await node.send_message("bob", b"Hello Bob!")

        # Broadcast всем
        await node.broadcast(b"Hello everyone!")
    """

    def __init__(self, config: MeshConfig):
        self.config = config
        self.node_id = config.node_id

        # Components
        self._transport: Optional[ShapedUDPTransport] = None
        self._discovery: Optional[MeshDiscovery] = None
        self._router: Optional[MeshRouter] = None

        # Peer address mapping: node_id -> (ip, port)
        self._peer_addresses: Dict[str, tuple] = {}

        # Callbacks
        self._message_handler: Optional[Callable] = None
        self._peer_handler: Optional[Callable] = None
        self._peer_lost_handler: Optional[Callable] = None

        self._running = False

    async def start(self):
        """Запустить node."""
        logger.info(f"Starting CompleteMeshNode: {self.node_id}")

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
        self._router.set_send_callback(self._router_send)
        self._router.set_receive_callback(self._router_receive)
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

        return await self._router.send(destination, payload)

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
            return self._router.get_routes()
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
            stats["routing"] = self._router.get_stats()

        if self._transport:
            stats["transport"] = self._transport.get_stats()

        return stats

    # === Internal Handlers ===

    async def _handle_transport_packet(self, data: bytes, address: tuple):
        """Обработка пакета от transport."""
        # Определяем от какого соседа пришёл пакет
        from_neighbor = None
        for peer_id, peer_addr in self._peer_addresses.items():
            if peer_addr[0] == address[0]:  # По IP
                from_neighbor = peer_id
                break

        if from_neighbor and self._router:
            await self._router.handle_packet(data, from_neighbor)

    async def _router_send(self, packet_bytes: bytes, next_hop: str) -> bool:
        """Callback для отправки пакета от router."""
        address = self._peer_addresses.get(next_hop)
        if not address:
            logger.warning(f"No address for next_hop: {next_hop}")
            return False

        return await self._transport.send_to(packet_bytes, address)

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
