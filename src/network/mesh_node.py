"""
Полноценный Mesh Node с интегрированными компонентами.
Объединяет: Discovery, Transport, Obfuscation, Traffic Shaping, DAO.
"""
import asyncio
import logging
import uuid
from typing import Optional, Dict, List, Callable, Any
from dataclasses import dataclass

from src.network.discovery import MeshDiscovery, PeerInfo
from src.network.transport.udp_shaped import ShapedUDPTransport
from src.network.obfuscation import TransportManager, TrafficShaper, TrafficProfile
from src.network.batman.node_manager import NodeManager

logger = logging.getLogger(__name__)


@dataclass
class MeshNodeConfig:
    """Конфигурация Mesh Node."""
    node_id: str = None
    port: int = 5000
    
    # Discovery
    enable_discovery: bool = True
    enable_multicast: bool = True
    bootstrap_nodes: List[tuple] = None
    
    # Transport
    obfuscation: str = "none"  # none, xor, shadowsocks
    obfuscation_key: str = "x0tta6bl4"
    traffic_profile: str = "none"  # none, gaming, voice_call, video_streaming
    
    # Services
    services: List[str] = None
    
    def __post_init__(self):
        if self.node_id is None:
            self.node_id = f"node-{uuid.uuid4().hex[:8]}"
        if self.services is None:
            self.services = ["mesh"]
        if self.bootstrap_nodes is None:
            self.bootstrap_nodes = []


class MeshNode:
    """
    Полноценный Mesh Node.
    
    Использование:
        node = MeshNode(MeshNodeConfig(
            port=5000,
            traffic_profile="gaming",
            obfuscation="xor"
        ))
        
        @node.on_message
        async def handle(data, peer):
            print(f"Received from {peer}")
        
        await node.start()
        await node.send_to_peer("peer-id", b"hello")
        await node.broadcast(b"hello all")
        await node.stop()
    """
    
    def __init__(self, config: MeshNodeConfig = None):
        self.config = config or MeshNodeConfig()
        
        self._discovery: Optional[MeshDiscovery] = None
        self._transport: Optional[ShapedUDPTransport] = None
        self._node_manager: Optional[NodeManager] = None
        
        self._running = False
        self._message_handler: Optional[Callable] = None
        self._peer_handler: Optional[Callable] = None
        self._peer_lost_handler: Optional[Callable] = None
        
        # Статистика
        self._messages_sent = 0
        self._messages_received = 0
        self._bytes_sent = 0
        self._bytes_received = 0
    
    async def start(self):
        """Запустить узел."""
        logger.info(f"Запуск Mesh Node: {self.config.node_id}")
        
        # 1. Инициализируем transport
        self._transport = ShapedUDPTransport(
            local_port=self.config.port,
            traffic_profile=self.config.traffic_profile,
            obfuscation=self.config.obfuscation,
            obfuscation_key=self.config.obfuscation_key
        )
        
        @self._transport.on_receive
        async def on_transport_receive(data: bytes, address: tuple):
            await self._handle_message(data, address)
        
        await self._transport.start()
        
        # 2. Инициализируем discovery
        if self.config.enable_discovery:
            self._discovery = MeshDiscovery(
                node_id=self.config.node_id,
                service_port=self.config.port,
                services=self.config.services,
                bootstrap_nodes=self.config.bootstrap_nodes,
                enable_multicast=self.config.enable_multicast
            )
            
            @self._discovery.on_peer_discovered
            async def on_peer_found(peer: PeerInfo):
                logger.info(f"Пир обнаружен: {peer.node_id}")
                if self._peer_handler:
                    await self._peer_handler(peer)
            
            @self._discovery.on_peer_lost
            async def on_peer_lost(peer: PeerInfo):
                logger.info(f"Пир потерян: {peer.node_id}")
                if self._peer_lost_handler:
                    await self._peer_lost_handler(peer)
            
            await self._discovery.start()
        
        # 3. Инициализируем NodeManager
        obfuscation_transport = None
        if self.config.obfuscation != "none":
            if self.config.obfuscation == "shadowsocks":
                obfuscation_transport = TransportManager.create(
                    self.config.obfuscation,
                    password=self.config.obfuscation_key
                )
            else:
                obfuscation_transport = TransportManager.create(
                    self.config.obfuscation,
                    key=self.config.obfuscation_key
                )
        
        self._node_manager = NodeManager(
            mesh_id="x0tta6bl4-mesh",
            local_node_id=self.config.node_id,
            obfuscation_transport=obfuscation_transport,
            traffic_profile=self.config.traffic_profile
        )
        
        self._running = True
        
        logger.info(f"Mesh Node запущен на порту {self._transport.local_port}")
        logger.info(f"  Obfuscation: {self.config.obfuscation}")
        logger.info(f"  Traffic Profile: {self.config.traffic_profile}")
        logger.info(f"  Discovery: {'enabled' if self.config.enable_discovery else 'disabled'}")
    
    async def stop(self):
        """Остановить узел."""
        self._running = False
        
        if self._discovery:
            await self._discovery.stop()
        
        if self._transport:
            await self._transport.stop()
        
        logger.info("Mesh Node остановлен")
    
    async def _handle_message(self, data: bytes, address: tuple):
        """Обработка входящего сообщения."""
        self._messages_received += 1
        self._bytes_received += len(data)
        
        # Находим пир по адресу
        peer = None
        if self._discovery:
            for p in self._discovery.get_peers():
                if address in p.addresses:
                    peer = p
                    break
        
        if self._message_handler:
            await self._message_handler(data, peer, address)
    
    def on_message(self, handler: Callable):
        """Callback при получении сообщения."""
        self._message_handler = handler
        return handler
    
    def on_peer_discovered(self, handler: Callable):
        """Callback при обнаружении пира."""
        self._peer_handler = handler
        return handler
    
    def on_peer_lost(self, handler: Callable):
        """Callback при потере пира."""
        self._peer_lost_handler = handler
        return handler
    
    async def send_to_peer(self, peer_id: str, data: bytes) -> bool:
        """Отправить данные конкретному пиру."""
        if not self._discovery:
            logger.error("Discovery не включён")
            return False
        
        peer = self._discovery.get_peer(peer_id)
        if not peer or not peer.addresses:
            logger.warning(f"Пир не найден: {peer_id}")
            return False
        
        address = peer.addresses[0]
        result = await self._transport.send_to(data, address)
        
        if result:
            self._messages_sent += 1
            self._bytes_sent += len(data)
        
        return result
    
    async def send_to_address(self, address: tuple, data: bytes) -> bool:
        """Отправить данные на адрес."""
        result = await self._transport.send_to(data, address)
        
        if result:
            self._messages_sent += 1
            self._bytes_sent += len(data)
        
        return result
    
    async def broadcast(self, data: bytes) -> int:
        """Отправить всем известным пирам."""
        if not self._discovery:
            return 0
        
        sent = 0
        for peer in self._discovery.get_peers():
            if peer.addresses:
                if await self.send_to_address(peer.addresses[0], data):
                    sent += 1
        
        return sent
    
    def get_peers(self) -> List[PeerInfo]:
        """Получить список пиров."""
        if self._discovery:
            return self._discovery.get_peers()
        return []
    
    def get_stats(self) -> Dict[str, Any]:
        """Получить статистику."""
        return {
            "node_id": self.config.node_id,
            "port": self._transport.local_port if self._transport else self.config.port,
            "running": self._running,
            "peers_count": len(self.get_peers()),
            "messages_sent": self._messages_sent,
            "messages_received": self._messages_received,
            "bytes_sent": self._bytes_sent,
            "bytes_received": self._bytes_received,
            "obfuscation": self.config.obfuscation,
            "traffic_profile": self.config.traffic_profile,
            "discovery": self._discovery.get_stats() if self._discovery else None,
            "transport": self._transport.get_stats() if self._transport else None
        }
    
    # DAO методы (proxy к NodeManager)
    def propose(self, title: str, action: dict) -> Optional[str]:
        """Создать DAO proposal."""
        if self._node_manager:
            return self._node_manager.propose_network_update(title, action)
        return None
    
    def vote(self, proposal_id: str, vote: str) -> bool:
        """Голосовать за proposal."""
        if self._node_manager:
            return self._node_manager.vote_on_proposal(proposal_id, vote)
        return False


# Пример использования
async def example_node():
    """Пример mesh node."""
    config = MeshNodeConfig(
        port=5000,
        traffic_profile="gaming",
        obfuscation="xor",
        services=["mesh", "relay"]
    )
    
    node = MeshNode(config)
    
    @node.on_message
    async def handle(data: bytes, peer: PeerInfo, address: tuple):
        print(f"📨 Сообщение от {peer.node_id if peer else address}: {data[:50]}")
    
    @node.on_peer_discovered
    async def on_peer(peer: PeerInfo):
        print(f"🟢 Новый пир: {peer.node_id}")
        # Отправляем приветствие
        await node.send_to_peer(peer.node_id, b"Hello from " + config.node_id.encode())
    
    await node.start()
    
    print(f"\n📡 Mesh Node запущен: {config.node_id}")
    print(f"   Порт: {node._transport.local_port}")
    print("\nОжидание пиров... (Ctrl+C для выхода)\n")
    
    try:
        while True:
            await asyncio.sleep(10)
            stats = node.get_stats()
            print(f"📊 Пиров: {stats['peers_count']}, "
                  f"Отправлено: {stats['messages_sent']}, "
                  f"Получено: {stats['messages_received']}")
    except asyncio.CancelledError:
        pass
    finally:
        await node.stop()


if __name__ == "__main__":
    asyncio.run(example_node())
