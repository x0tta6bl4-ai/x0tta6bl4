"""
MeshRouter - AODV-like Routing Protocol для x0tta6bl4.
Multi-hop forwarding с reactive route discovery.
"""
import asyncio
import time
import logging
from typing import Optional, Dict, List, Callable, Set, Tuple
from dataclasses import dataclass, field
from enum import Enum
import hashlib
import json

logger = logging.getLogger(__name__)


class PacketType(Enum):
    """Типы пакетов маршрутизации."""
    DATA = 0x01        # Данные приложения
    RREQ = 0x02        # Route Request
    RREP = 0x03        # Route Reply
    RERR = 0x04        # Route Error
    HELLO = 0x05       # Hello/keepalive


@dataclass
class RouteEntry:
    """Запись в routing table."""
    destination: str
    next_hop: str
    hop_count: int
    seq_num: int
    timestamp: float = field(default_factory=time.time)
    valid: bool = True
    
    @property
    def age(self) -> float:
        return time.time() - self.timestamp


@dataclass
class RoutingPacket:
    """Пакет маршрутизации."""
    packet_type: PacketType
    source: str
    destination: str
    seq_num: int
    hop_count: int
    ttl: int
    payload: bytes
    packet_id: str = ""
    
    def __post_init__(self):
        if not self.packet_id:
            self.packet_id = hashlib.md5(
                f"{self.source}{self.destination}{self.seq_num}{time.time()}".encode()
            ).hexdigest()[:16]
    
    def to_bytes(self) -> bytes:
        header = {
            "type": self.packet_type.value,
            "src": self.source,
            "dst": self.destination,
            "seq": self.seq_num,
            "hops": self.hop_count,
            "ttl": self.ttl,
            "id": self.packet_id
        }
        header_bytes = json.dumps(header).encode()
        return len(header_bytes).to_bytes(2, 'big') + header_bytes + self.payload
    
    @classmethod
    def from_bytes(cls, data: bytes) -> 'RoutingPacket':
        header_len = int.from_bytes(data[:2], 'big')
        header = json.loads(data[2:2+header_len].decode())
        payload = data[2+header_len:]
        
        return cls(
            packet_type=PacketType(header["type"]),
            source=header["src"],
            destination=header["dst"],
            seq_num=header["seq"],
            hop_count=header["hops"],
            ttl=header["ttl"],
            payload=payload,
            packet_id=header["id"]
        )


class MeshRouter:
    """
    AODV-like Mesh Router.
    
    Features:
    - Reactive route discovery (RREQ/RREP)
    - Multi-hop forwarding
    - Route maintenance
    - Loop prevention via TTL and sequence numbers
    """
    
    DEFAULT_TTL = 16
    ROUTE_TIMEOUT = 60.0  # секунды
    RREQ_TIMEOUT = 5.0    # таймаут ожидания RREP
    
    def __init__(self, node_id: str):
        self.node_id = node_id
        self.seq_num = 0
        
        # Routing table: destination -> RouteEntry
        self._routes: Dict[str, RouteEntry] = {}
        
        # Pending route requests
        self._pending_rreq: Dict[str, asyncio.Future] = {}
        
        # Seen packet IDs (for deduplication)
        self._seen_packets: Set[str] = set()
        self._seen_cleanup_task: Optional[asyncio.Task] = None
        
        # Callbacks
        self._send_callback: Optional[Callable] = None  # (packet_bytes, next_hop) -> bool
        self._receive_callback: Optional[Callable] = None  # (source, payload) -> None
        
        # Statistics
        self._stats = {
            "packets_sent": 0,
            "packets_received": 0,
            "packets_forwarded": 0,
            "packets_dropped": 0,
            "rreq_sent": 0,
            "rreq_received": 0,
            "rrep_sent": 0,
            "rrep_received": 0,
            "routes_discovered": 0
        }
    
    def start(self):
        """Запустить router."""
        self._seen_cleanup_task = asyncio.create_task(self._cleanup_seen_packets())
        logger.info(f"MeshRouter started for {self.node_id}")
    
    async def stop(self):
        """Остановить router."""
        if self._seen_cleanup_task:
            self._seen_cleanup_task.cancel()
            try:
                await self._seen_cleanup_task
            except asyncio.CancelledError:
                pass
        logger.info(f"MeshRouter stopped for {self.node_id}")
    
    def set_send_callback(self, callback: Callable):
        """Установить callback для отправки пакетов."""
        self._send_callback = callback
    
    def set_receive_callback(self, callback: Callable):
        """Установить callback для полученных данных."""
        self._receive_callback = callback
    
    def add_neighbor(self, neighbor_id: str):
        """Добавить прямого соседа (1 hop)."""
        self._routes[neighbor_id] = RouteEntry(
            destination=neighbor_id,
            next_hop=neighbor_id,
            hop_count=1,
            seq_num=0
        )
        logger.debug(f"Added neighbor route: {neighbor_id}")
    
    def remove_neighbor(self, neighbor_id: str):
        """Удалить соседа и связанные маршруты."""
        # Удаляем прямой маршрут
        if neighbor_id in self._routes:
            del self._routes[neighbor_id]
        
        # Инвалидируем маршруты через этого соседа
        for dest, route in self._routes.items():
            if route.next_hop == neighbor_id:
                route.valid = False
        
        logger.debug(f"Removed neighbor: {neighbor_id}")
    
    def get_route(self, destination: str) -> Optional[RouteEntry]:
        """Получить маршрут к destination."""
        route = self._routes.get(destination)
        if route and route.valid and route.age < self.ROUTE_TIMEOUT:
            return route
        return None
    
    def get_routes(self) -> Dict[str, RouteEntry]:
        """Получить все активные маршруты."""
        return {
            dest: route for dest, route in self._routes.items()
            if route.valid and route.age < self.ROUTE_TIMEOUT
        }
    
    async def send(self, destination: str, payload: bytes) -> bool:
        """
        Отправить данные к destination.
        Автоматически выполняет route discovery если нужно.
        """
        # Проверяем локальную доставку
        if destination == self.node_id:
            if self._receive_callback:
                await self._receive_callback(self.node_id, payload)
            return True
        
        # Ищем маршрут
        route = self.get_route(destination)
        
        if not route:
            # Route discovery
            logger.info(f"No route to {destination}, starting discovery...")
            route = await self._discover_route(destination)
            
            if not route:
                logger.warning(f"Route discovery failed for {destination}")
                self._stats["packets_dropped"] += 1
                return False
        
        # Создаём DATA пакет
        self.seq_num += 1
        packet = RoutingPacket(
            packet_type=PacketType.DATA,
            source=self.node_id,
            destination=destination,
            seq_num=self.seq_num,
            hop_count=0,
            ttl=self.DEFAULT_TTL,
            payload=payload
        )
        
        return await self._send_packet(packet, route.next_hop)
    
    async def handle_packet(self, data: bytes, from_neighbor: str):
        """Обработать входящий пакет."""
        try:
            packet = RoutingPacket.from_bytes(data)
        except Exception as e:
            logger.error(f"Failed to parse packet: {e}")
            return
        
        # Дедупликация
        if packet.packet_id in self._seen_packets:
            return
        self._seen_packets.add(packet.packet_id)
        
        self._stats["packets_received"] += 1
        
        # Обновляем обратный маршрут к source
        self._update_route(packet.source, from_neighbor, packet.hop_count + 1, packet.seq_num)
        
        # Обрабатываем по типу
        if packet.packet_type == PacketType.DATA:
            await self._handle_data(packet, from_neighbor)
        elif packet.packet_type == PacketType.RREQ:
            await self._handle_rreq(packet, from_neighbor)
        elif packet.packet_type == PacketType.RREP:
            await self._handle_rrep(packet, from_neighbor)
        elif packet.packet_type == PacketType.RERR:
            await self._handle_rerr(packet, from_neighbor)
    
    async def _handle_data(self, packet: RoutingPacket, from_neighbor: str):
        """Обработать DATA пакет."""
        if packet.destination == self.node_id:
            # Для нас - доставляем приложению
            logger.debug(f"Received data from {packet.source}")
            if self._receive_callback:
                await self._receive_callback(packet.source, packet.payload)
        else:
            # Forwarding
            await self._forward_packet(packet)
    
    async def _handle_rreq(self, packet: RoutingPacket, from_neighbor: str):
        """Обработать Route Request."""
        self._stats["rreq_received"] += 1
        target = packet.payload.decode()
        
        logger.debug(f"RREQ from {packet.source} for {target}")
        
        if target == self.node_id:
            # Мы - цель, отправляем RREP
            await self._send_rrep(packet.source, from_neighbor)
        else:
            # Проверяем есть ли у нас маршрут к цели
            route = self.get_route(target)
            if route:
                # Отвечаем за цель (proxy reply)
                await self._send_rrep(packet.source, from_neighbor, target, route.hop_count)
            else:
                # Пересылаем RREQ
                await self._forward_packet(packet)
    
    async def _handle_rrep(self, packet: RoutingPacket, from_neighbor: str):
        """Обработать Route Reply."""
        self._stats["rrep_received"] += 1
        
        # Парсим payload: target:hop_count
        parts = packet.payload.decode().split(":")
        target = parts[0]
        hop_count = int(parts[1]) if len(parts) > 1 else packet.hop_count
        
        logger.debug(f"RREP: route to {target} via {from_neighbor}, hops={hop_count}")
        
        # Обновляем маршрут к цели
        self._update_route(target, from_neighbor, hop_count, packet.seq_num)
        
        if packet.destination == self.node_id:
            # RREP для нас - завершаем route discovery
            if target in self._pending_rreq:
                future = self._pending_rreq.pop(target)
                if not future.done():
                    future.set_result(self.get_route(target))
        else:
            # Пересылаем RREP к источнику
            await self._forward_packet(packet)
    
    async def _handle_rerr(self, packet: RoutingPacket, from_neighbor: str):
        """Обработать Route Error."""
        broken_dest = packet.payload.decode()
        
        # Инвалидируем маршрут
        if broken_dest in self._routes:
            self._routes[broken_dest].valid = False
        
        # Пересылаем RERR
        await self._forward_packet(packet)
    
    async def _forward_packet(self, packet: RoutingPacket):
        """Переслать пакет к следующему hop."""
        # Проверяем TTL
        if packet.ttl <= 1:
            logger.debug(f"Packet dropped: TTL expired")
            self._stats["packets_dropped"] += 1
            return
        
        # Ищем маршрут
        route = self.get_route(packet.destination)
        
        if not route:
            # Для RREQ - broadcast
            if packet.packet_type == PacketType.RREQ:
                await self._broadcast_packet(packet)
            else:
                logger.warning(f"No route to forward packet to {packet.destination}")
                self._stats["packets_dropped"] += 1
            return
        
        # Декрементируем TTL и увеличиваем hop_count
        packet.ttl -= 1
        packet.hop_count += 1
        
        await self._send_packet(packet, route.next_hop)
        self._stats["packets_forwarded"] += 1
    
    async def _broadcast_packet(self, packet: RoutingPacket):
        """Broadcast пакет всем соседям."""
        packet.ttl -= 1
        packet.hop_count += 1
        
        for dest, route in self._routes.items():
            if route.hop_count == 1:  # Только прямые соседи
                await self._send_packet(packet, dest)
    
    async def _send_packet(self, packet: RoutingPacket, next_hop: str) -> bool:
        """Отправить пакет через transport."""
        if not self._send_callback:
            logger.error("No send callback configured")
            return False
        
        try:
            result = await self._send_callback(packet.to_bytes(), next_hop)
            if result:
                self._stats["packets_sent"] += 1
            return result
        except Exception as e:
            logger.error(f"Failed to send packet: {e}")
            return False
    
    async def _discover_route(self, destination: str) -> Optional[RouteEntry]:
        """Выполнить route discovery."""
        # Создаём future для ожидания RREP
        future = asyncio.get_event_loop().create_future()
        self._pending_rreq[destination] = future
        
        # Отправляем RREQ
        self.seq_num += 1
        rreq = RoutingPacket(
            packet_type=PacketType.RREQ,
            source=self.node_id,
            destination=destination,
            seq_num=self.seq_num,
            hop_count=0,
            ttl=self.DEFAULT_TTL,
            payload=destination.encode()
        )
        
        await self._broadcast_packet(rreq)
        self._stats["rreq_sent"] += 1
        
        # Ждём RREP
        try:
            route = await asyncio.wait_for(future, timeout=self.RREQ_TIMEOUT)
            self._stats["routes_discovered"] += 1
            return route
        except asyncio.TimeoutError:
            logger.warning(f"Route discovery timeout for {destination}")
            self._pending_rreq.pop(destination, None)
            return None
    
    async def _send_rrep(self, requester: str, next_hop: str, target: str = None, hop_count: int = 0):
        """Отправить Route Reply."""
        target = target or self.node_id
        
        self.seq_num += 1
        rrep = RoutingPacket(
            packet_type=PacketType.RREP,
            source=self.node_id,
            destination=requester,
            seq_num=self.seq_num,
            hop_count=0,
            ttl=self.DEFAULT_TTL,
            payload=f"{target}:{hop_count}".encode()
        )
        
        await self._send_packet(rrep, next_hop)
        self._stats["rrep_sent"] += 1
    
    def _update_route(self, destination: str, next_hop: str, hop_count: int, seq_num: int):
        """Обновить или добавить маршрут."""
        existing = self._routes.get(destination)
        
        # Обновляем если: нет маршрута, новый seq_num больше, или меньше hops
        if not existing or seq_num > existing.seq_num or \
           (seq_num == existing.seq_num and hop_count < existing.hop_count):
            self._routes[destination] = RouteEntry(
                destination=destination,
                next_hop=next_hop,
                hop_count=hop_count,
                seq_num=seq_num
            )
            logger.debug(f"Route updated: {destination} via {next_hop} (hops={hop_count})")
    
    async def _cleanup_seen_packets(self):
        """Периодическая очистка seen packets."""
        while True:
            await asyncio.sleep(30)
            # Ограничиваем размер
            if len(self._seen_packets) > 10000:
                self._seen_packets = set(list(self._seen_packets)[-5000:])
    
    def get_stats(self) -> dict:
        """Получить статистику."""
        return {
            "node_id": self.node_id,
            "routes_count": len(self.get_routes()),
            **self._stats
        }
