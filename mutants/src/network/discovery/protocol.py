"""
Mesh Discovery Protocol для x0tta6bl4.
Автоматическое обнаружение узлов в локальной сети и через DHT.

Методы обнаружения:
1. Multicast UDP (LAN) - быстрое обнаружение в локальной сети
2. Bootstrap nodes - начальные узлы для подключения
3. DHT (Kademlia-like) - распределённая таблица для глобального discovery
"""
import asyncio
import socket
import struct
import json
import time
import hashlib
import logging
from typing import Optional, Dict, List, Tuple, Callable, Set
from dataclasses import dataclass, field
from enum import Enum
from collections import defaultdict

logger = logging.getLogger(__name__)


# Константы
MULTICAST_GROUP = "239.255.77.77"  # x0tta6bl4 multicast group
MULTICAST_PORT = 7777
ANNOUNCE_INTERVAL = 10.0  # секунды
PEER_TIMEOUT = 60.0       # секунды без announce = offline
DHT_K = 20                # Kademlia K-bucket size


class MessageType(Enum):
    """Типы сообщений discovery."""
    ANNOUNCE = 0x01       # Объявление о себе
    QUERY = 0x02          # Запрос пиров
    RESPONSE = 0x03       # Ответ с пирами
    PING = 0x04           # Проверка живости
    PONG = 0x05           # Ответ на ping
    JOIN = 0x06           # Запрос на присоединение
    LEAVE = 0x07          # Уход из сети


@dataclass
class PeerInfo:
    """Информация о пире."""
    node_id: str
    addresses: List[Tuple[str, int]]  # [(ip, port), ...]
    services: List[str] = field(default_factory=list)  # ["mesh", "relay", "exit"]
    version: str = "1.0.0"
    last_seen: float = 0
    rtt_ms: float = 0
    
    # DHT данные
    distance: int = 0  # XOR distance для Kademlia
    
    def to_dict(self) -> dict:
        return {
            "node_id": self.node_id,
            "addresses": self.addresses,
            "services": self.services,
            "version": self.version
        }
    
    @classmethod
    def from_dict(cls, data: dict) -> 'PeerInfo':
        return cls(
            node_id=data["node_id"],
            addresses=[tuple(a) for a in data["addresses"]],
            services=data.get("services", []),
            version=data.get("version", "1.0.0")
        )


@dataclass 
class DiscoveryMessage:
    """Сообщение discovery протокола."""
    msg_type: MessageType
    sender_id: str
    payload: dict
    timestamp: int = 0
    
    def to_bytes(self) -> bytes:
        """Сериализация в bytes."""
        data = {
            "type": self.msg_type.value,
            "sender": self.sender_id,
            "payload": self.payload,
            "ts": self.timestamp or int(time.time() * 1000)
        }
        return json.dumps(data).encode('utf-8')
    
    @classmethod
    def from_bytes(cls, data: bytes) -> 'DiscoveryMessage':
        """Десериализация из bytes."""
        obj = json.loads(data.decode('utf-8'))
        return cls(
            msg_type=MessageType(obj["type"]),
            sender_id=obj["sender"],
            payload=obj["payload"],
            timestamp=obj["ts"]
        )


class MulticastDiscovery:
    """
    LAN Discovery через UDP Multicast.
    Быстрое обнаружение узлов в локальной сети.
    """
    
    def __init__(
        self,
        node_id: str,
        service_port: int,
        services: List[str] = None,
        multicast_group: str = MULTICAST_GROUP,
        multicast_port: int = MULTICAST_PORT
    ):
        self.node_id = node_id
        self.service_port = service_port
        self.services = services or ["mesh"]
        self.multicast_group = multicast_group
        self.multicast_port = multicast_port
        
        self._socket: Optional[socket.socket] = None
        self._running = False
        self._peers: Dict[str, PeerInfo] = {}
        self._on_peer_discovered: Optional[Callable] = None
        self._on_peer_lost: Optional[Callable] = None
        
        self._announce_task: Optional[asyncio.Task] = None
        self._listen_task: Optional[asyncio.Task] = None
        self._cleanup_task: Optional[asyncio.Task] = None
    
    async def start(self):
        """Запустить discovery."""
        # Создаём multicast socket
        self._socket = socket.socket(socket.AF_INET, socket.SOCK_DGRAM, socket.IPPROTO_UDP)
        self._socket.setsockopt(socket.SOL_SOCKET, socket.SO_REUSEADDR, 1)
        
        # Разрешаем multicast loopback для тестирования
        self._socket.setsockopt(socket.IPPROTO_IP, socket.IP_MULTICAST_LOOP, 1)
        
        # TTL для multicast
        self._socket.setsockopt(socket.IPPROTO_IP, socket.IP_MULTICAST_TTL, 32)
        
        # Bind
        self._socket.bind(('', self.multicast_port))
        
        # Присоединяемся к multicast группе
        mreq = struct.pack("4sl", socket.inet_aton(self.multicast_group), socket.INADDR_ANY)
        self._socket.setsockopt(socket.IPPROTO_IP, socket.IP_ADD_MEMBERSHIP, mreq)
        
        self._socket.setblocking(False)
        self._running = True
        
        # Запускаем задачи
        loop = asyncio.get_event_loop()
        self._announce_task = loop.create_task(self._announce_loop())
        self._listen_task = loop.create_task(self._listen_loop())
        self._cleanup_task = loop.create_task(self._cleanup_loop())
        
        logger.info(f"Multicast Discovery запущен: {self.multicast_group}:{self.multicast_port}")
        
        # Сразу announce
        await self._send_announce()
    
    async def stop(self):
        """Остановить discovery."""
        self._running = False
        
        # Отправляем LEAVE
        await self._send_leave()
        
        for task in [self._announce_task, self._listen_task, self._cleanup_task]:
            if task:
                task.cancel()
                try:
                    await task
                except asyncio.CancelledError:
                    pass
        
        if self._socket:
            self._socket.close()
        
        logger.info("Multicast Discovery остановлен")
    
    async def _send_announce(self):
        """Отправить announce."""
        # Получаем локальные адреса
        local_ip = self._get_local_ip()
        
        msg = DiscoveryMessage(
            msg_type=MessageType.ANNOUNCE,
            sender_id=self.node_id,
            payload={
                "peer": PeerInfo(
                    node_id=self.node_id,
                    addresses=[(local_ip, self.service_port)],
                    services=self.services
                ).to_dict()
            }
        )
        
        try:
            data = msg.to_bytes()
            await asyncio.get_event_loop().run_in_executor(
                None,
                lambda: self._socket.sendto(data, (self.multicast_group, self.multicast_port))
            )
        except Exception as e:
            logger.error(f"Ошибка отправки announce: {e}")
    
    async def _send_leave(self):
        """Отправить leave."""
        msg = DiscoveryMessage(
            msg_type=MessageType.LEAVE,
            sender_id=self.node_id,
            payload={}
        )
        
        try:
            data = msg.to_bytes()
            self._socket.sendto(data, (self.multicast_group, self.multicast_port))
        except Exception:
            pass
    
    async def _announce_loop(self):
        """Периодическая отправка announce."""
        while self._running:
            await self._send_announce()
            await asyncio.sleep(ANNOUNCE_INTERVAL)
    
    async def _listen_loop(self):
        """Приём сообщений."""
        loop = asyncio.get_event_loop()
        
        while self._running:
            try:
                data, addr = await loop.run_in_executor(
                    None,
                    lambda: self._socket.recvfrom(4096)
                )
                
                await self._handle_message(data, addr)
                
            except BlockingIOError:
                await asyncio.sleep(0.01)
            except Exception as e:
                if self._running:
                    logger.debug(f"Listen error: {e}")
                await asyncio.sleep(0.1)
    
    async def _handle_message(self, data: bytes, addr: Tuple[str, int]):
        """Обработка входящего сообщения."""
        try:
            msg = DiscoveryMessage.from_bytes(data)
            
            # Игнорируем свои сообщения
            if msg.sender_id == self.node_id:
                return
            
            if msg.msg_type == MessageType.ANNOUNCE:
                await self._handle_announce(msg, addr)
            elif msg.msg_type == MessageType.LEAVE:
                await self._handle_leave(msg)
            elif msg.msg_type == MessageType.QUERY:
                await self._handle_query(msg, addr)
            elif msg.msg_type == MessageType.PING:
                await self._handle_ping(msg, addr)
                
        except Exception as e:
            logger.debug(f"Ошибка обработки сообщения: {e}")
    
    async def _handle_announce(self, msg: DiscoveryMessage, addr: Tuple[str, int]):
        """Обработка announce."""
        peer_data = msg.payload.get("peer", {})
        peer = PeerInfo.from_dict(peer_data)
        peer.last_seen = time.time()
        
        # Добавляем адрес отправителя если его нет
        sender_addr = (addr[0], peer.addresses[0][1] if peer.addresses else self.service_port)
        if sender_addr not in peer.addresses:
            peer.addresses.append(sender_addr)
        
        is_new = peer.node_id not in self._peers
        self._peers[peer.node_id] = peer
        
        if is_new:
            logger.info(f"Обнаружен новый пир: {peer.node_id} @ {peer.addresses}")
            if self._on_peer_discovered:
                await self._on_peer_discovered(peer)
    
    async def _handle_leave(self, msg: DiscoveryMessage):
        """Обработка leave."""
        if msg.sender_id in self._peers:
            peer = self._peers.pop(msg.sender_id)
            logger.info(f"Пир ушёл: {msg.sender_id}")
            if self._on_peer_lost:
                await self._on_peer_lost(peer)
    
    async def _handle_query(self, msg: DiscoveryMessage, addr: Tuple[str, int]):
        """Обработка query - отправляем список пиров."""
        peers_list = [p.to_dict() for p in self._peers.values()]
        
        response = DiscoveryMessage(
            msg_type=MessageType.RESPONSE,
            sender_id=self.node_id,
            payload={"peers": peers_list}
        )
        
        try:
            self._socket.sendto(response.to_bytes(), addr)
        except Exception:
            pass
    
    async def _handle_ping(self, msg: DiscoveryMessage, addr: Tuple[str, int]):
        """Обработка ping."""
        pong = DiscoveryMessage(
            msg_type=MessageType.PONG,
            sender_id=self.node_id,
            payload={"ping_ts": msg.timestamp}
        )
        
        try:
            self._socket.sendto(pong.to_bytes(), addr)
        except Exception:
            pass
    
    async def _cleanup_loop(self):
        """Удаление устаревших пиров."""
        while self._running:
            now = time.time()
            expired = []
            
            for node_id, peer in self._peers.items():
                if now - peer.last_seen > PEER_TIMEOUT:
                    expired.append(node_id)
            
            for node_id in expired:
                peer = self._peers.pop(node_id)
                logger.info(f"Пир таймаут: {node_id}")
                if self._on_peer_lost:
                    await self._on_peer_lost(peer)
            
            await asyncio.sleep(10)
    
    def _get_local_ip(self) -> str:
        """Получить локальный IP."""
        try:
            s = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
            s.connect(("8.8.8.8", 80))
            ip = s.getsockname()[0]
            s.close()
            return ip
        except Exception:
            return "127.0.0.1"
    
    def on_peer_discovered(self, handler: Callable):
        """Callback при обнаружении пира."""
        self._on_peer_discovered = handler
        return handler
    
    def on_peer_lost(self, handler: Callable):
        """Callback при потере пира."""
        self._on_peer_lost = handler
        return handler
    
    def get_peers(self) -> List[PeerInfo]:
        """Получить список пиров."""
        return list(self._peers.values())
    
    def get_peer(self, node_id: str) -> Optional[PeerInfo]:
        """Получить пир по ID."""
        return self._peers.get(node_id)


class BootstrapDiscovery:
    """
    Discovery через bootstrap nodes.
    Для начального подключения к сети.
    """
    
    def __init__(
        self,
        node_id: str,
        service_port: int,
        bootstrap_nodes: List[Tuple[str, int]] = None
    ):
        self.node_id = node_id
        self.service_port = service_port
        self.bootstrap_nodes = bootstrap_nodes or []
        self._peers: Dict[str, PeerInfo] = {}
    
    async def bootstrap(self) -> List[PeerInfo]:
        """Подключиться к bootstrap nodes и получить пиров."""
        discovered = []
        
        for host, port in self.bootstrap_nodes:
            try:
                peers = await self._query_bootstrap(host, port)
                discovered.extend(peers)
            except Exception as e:
                logger.warning(f"Bootstrap {host}:{port} недоступен: {e}")
        
        # Дедупликация
        seen = set()
        unique = []
        for peer in discovered:
            if peer.node_id not in seen:
                seen.add(peer.node_id)
                unique.append(peer)
                self._peers[peer.node_id] = peer
        
        logger.info(f"Bootstrap: обнаружено {len(unique)} пиров")
        return unique
    
    async def _query_bootstrap(self, host: str, port: int) -> List[PeerInfo]:
        """Запросить пиров у bootstrap node."""
        sock = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
        sock.settimeout(5.0)
        
        try:
            msg = DiscoveryMessage(
                msg_type=MessageType.QUERY,
                sender_id=self.node_id,
                payload={}
            )
            
            sock.sendto(msg.to_bytes(), (host, port))
            
            data, _ = sock.recvfrom(65535)
            response = DiscoveryMessage.from_bytes(data)
            
            if response.msg_type == MessageType.RESPONSE:
                return [PeerInfo.from_dict(p) for p in response.payload.get("peers", [])]
            
        finally:
            sock.close()
        
        return []


class KademliaNode:
    """
    Упрощённая реализация Kademlia DHT для глобального discovery.
    """
    
    def __init__(self, node_id: str, port: int):
        self.node_id = node_id
        self.node_id_bytes = self._id_to_bytes(node_id)
        self.port = port
        
        # K-buckets: distance -> list of peers
        self._buckets: Dict[int, List[PeerInfo]] = defaultdict(list)
        self._data: Dict[str, bytes] = {}  # DHT storage
    
    def _id_to_bytes(self, node_id: str) -> bytes:
        """Конвертировать ID в bytes для XOR."""
        return hashlib.sha256(node_id.encode()).digest()
    
    def _xor_distance(self, id1: bytes, id2: bytes) -> int:
        """Вычислить XOR distance."""
        return int.from_bytes(
            bytes(a ^ b for a, b in zip(id1, id2)),
            'big'
        )
    
    def _bucket_index(self, distance: int) -> int:
        """Индекс bucket по distance."""
        if distance == 0:
            return 0
        return distance.bit_length() - 1
    
    def add_peer(self, peer: PeerInfo):
        """Добавить пир в routing table."""
        peer_id_bytes = self._id_to_bytes(peer.node_id)
        distance = self._xor_distance(self.node_id_bytes, peer_id_bytes)
        peer.distance = distance
        
        bucket_idx = self._bucket_index(distance)
        bucket = self._buckets[bucket_idx]
        
        # Проверяем, есть ли уже
        for i, existing in enumerate(bucket):
            if existing.node_id == peer.node_id:
                bucket[i] = peer  # Обновляем
                return
        
        # Добавляем если есть место
        if len(bucket) < DHT_K:
            bucket.append(peer)
        else:
            # Bucket полный - проверяем живость первого (LRU)
            # Упрощённо: заменяем если новый ближе
            if distance < bucket[-1].distance:
                bucket[-1] = peer
                bucket.sort(key=lambda p: p.distance)
    
    def find_closest(self, target_id: str, count: int = DHT_K) -> List[PeerInfo]:
        """Найти K ближайших пиров к target."""
        target_bytes = self._id_to_bytes(target_id)
        
        all_peers = []
        for bucket in self._buckets.values():
            all_peers.extend(bucket)
        
        # Сортируем по distance до target
        for peer in all_peers:
            peer_bytes = self._id_to_bytes(peer.node_id)
            peer.distance = self._xor_distance(target_bytes, peer_bytes)
        
        all_peers.sort(key=lambda p: p.distance)
        return all_peers[:count]
    
    def store(self, key: str, value: bytes):
        """Сохранить данные в DHT."""
        self._data[key] = value
    
    def get(self, key: str) -> Optional[bytes]:
        """Получить данные из DHT."""
        return self._data.get(key)


class MeshDiscovery:
    """
    Объединённый Mesh Discovery.
    Комбинирует все методы обнаружения.
    """
    
    def __init__(
        self,
        node_id: str,
        service_port: int,
        services: List[str] = None,
        bootstrap_nodes: List[Tuple[str, int]] = None,
        enable_multicast: bool = True,
        enable_dht: bool = True
    ):
        self.node_id = node_id
        self.service_port = service_port
        
        # Методы discovery
        self._multicast: Optional[MulticastDiscovery] = None
        self._bootstrap: Optional[BootstrapDiscovery] = None
        self._dht: Optional[KademliaNode] = None
        
        if enable_multicast:
            self._multicast = MulticastDiscovery(
                node_id=node_id,
                service_port=service_port,
                services=services
            )
        
        if bootstrap_nodes:
            self._bootstrap = BootstrapDiscovery(
                node_id=node_id,
                service_port=service_port,
                bootstrap_nodes=bootstrap_nodes
            )
        
        if enable_dht:
            self._dht = KademliaNode(node_id=node_id, port=service_port)
        
        # Общий пул пиров
        self._peers: Dict[str, PeerInfo] = {}
        self._on_peer_discovered: Optional[Callable] = None
        self._on_peer_lost: Optional[Callable] = None
    
    async def start(self):
        """Запустить discovery."""
        # Multicast
        if self._multicast:
            self._multicast._on_peer_discovered = self._handle_discovered
            self._multicast._on_peer_lost = self._handle_lost
            await self._multicast.start()
        
        # Bootstrap
        if self._bootstrap:
            peers = await self._bootstrap.bootstrap()
            for peer in peers:
                await self._handle_discovered(peer)
        
        logger.info(f"MeshDiscovery запущен для {self.node_id}")
    
    async def stop(self):
        """Остановить discovery."""
        if self._multicast:
            await self._multicast.stop()
        
        logger.info("MeshDiscovery остановлен")
    
    async def _handle_discovered(self, peer: PeerInfo):
        """Обработка обнаруженного пира."""
        is_new = peer.node_id not in self._peers
        self._peers[peer.node_id] = peer
        
        # Добавляем в DHT
        if self._dht:
            self._dht.add_peer(peer)
        
        if is_new and self._on_peer_discovered:
            await self._on_peer_discovered(peer)
    
    async def _handle_lost(self, peer: PeerInfo):
        """Обработка потерянного пира."""
        if peer.node_id in self._peers:
            del self._peers[peer.node_id]
        
        if self._on_peer_lost:
            await self._on_peer_lost(peer)
    
    def on_peer_discovered(self, handler: Callable):
        """Callback при обнаружении пира."""
        self._on_peer_discovered = handler
        return handler
    
    def on_peer_lost(self, handler: Callable):
        """Callback при потере пира."""
        self._on_peer_lost = handler
        return handler
    
    def get_peers(self) -> List[PeerInfo]:
        """Получить всех известных пиров."""
        return list(self._peers.values())
    
    def get_peer(self, node_id: str) -> Optional[PeerInfo]:
        """Получить пир по ID."""
        return self._peers.get(node_id)
    
    def find_peers_for_service(self, service: str) -> List[PeerInfo]:
        """Найти пиров с определённым сервисом."""
        return [p for p in self._peers.values() if service in p.services]
    
    def get_stats(self) -> dict:
        """Статистика discovery."""
        return {
            "node_id": self.node_id,
            "peers_count": len(self._peers),
            "multicast_enabled": self._multicast is not None,
            "dht_enabled": self._dht is not None,
            "peers": [p.to_dict() for p in self._peers.values()]
        }


# CLI пример
async def example_discovery():
    """Пример использования discovery."""
    import uuid
    
    node_id = f"node-{uuid.uuid4().hex[:8]}"
    
    discovery = MeshDiscovery(
        node_id=node_id,
        service_port=5000,
        services=["mesh", "relay"]
    )
    
    @discovery.on_peer_discovered
    async def on_found(peer: PeerInfo):
        print(f"🟢 Найден: {peer.node_id} @ {peer.addresses}")
    
    @discovery.on_peer_lost
    async def on_lost(peer: PeerInfo):
        print(f"🔴 Потерян: {peer.node_id}")
    
    await discovery.start()
    
    print(f"Discovery запущен для {node_id}")
    print("Ожидание пиров... (Ctrl+C для выхода)")
    
    try:
        while True:
            await asyncio.sleep(5)
            print(f"Известно пиров: {len(discovery.get_peers())}")
    except KeyboardInterrupt:
        pass
    finally:
        await discovery.stop()


if __name__ == "__main__":
    asyncio.run(example_discovery())
