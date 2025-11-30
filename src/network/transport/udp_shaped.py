"""
UDP транспорт с Traffic Shaping для low-latency приложений.
Оптимизирован для gaming и VoIP трафика.

Особенности:
- Минимальная латентность (no TCP overhead)
- Интеграция с Traffic Shaping профилями
- NAT traversal через UDP hole punching
- Reliable delivery опционально (для критичных пакетов)
"""
import asyncio
import socket
import struct
import time
import logging
import hashlib
from typing import Optional, Callable, Dict, Tuple, Any, List
from dataclasses import dataclass, field
from enum import Enum
from collections import defaultdict

from src.network.obfuscation import (
    TransportManager,
    ObfuscationTransport,
    TrafficShaper,
    TrafficProfile,
    TrafficAnalyzer
)

logger = logging.getLogger(__name__)


class PacketType(Enum):
    """Типы UDP пакетов."""
    DATA = 0x01           # Обычные данные
    ACK = 0x02            # Подтверждение (для reliable mode)
    PING = 0x03           # Проверка соединения
    PONG = 0x04           # Ответ на ping
    HOLE_PUNCH = 0x05     # NAT traversal
    HANDSHAKE = 0x06      # Начало сессии
    CLOSE = 0x07          # Закрытие сессии


@dataclass
class UDPPacket:
    """Структура UDP пакета с метаданными."""
    packet_type: PacketType
    sequence: int
    timestamp_ms: int
    payload: bytes
    
    # Для reliable delivery
    requires_ack: bool = False
    retries: int = 0
    
    def to_bytes(self) -> bytes:
        """Сериализация пакета."""
        # Header: type(1) + seq(4) + timestamp(8) + flags(1) + payload_len(2)
        flags = 0x01 if self.requires_ack else 0x00
        header = struct.pack(
            "!BIQBH",
            self.packet_type.value,
            self.sequence,
            self.timestamp_ms,
            flags,
            len(self.payload)
        )
        return header + self.payload
    
    @classmethod
    def from_bytes(cls, data: bytes) -> 'UDPPacket':
        """Десериализация пакета."""
        if len(data) < 16:
            raise ValueError("Пакет слишком короткий")
        
        ptype, seq, ts, flags, plen = struct.unpack("!BIQBH", data[:16])
        payload = data[16:16+plen]
        
        return cls(
            packet_type=PacketType(ptype),
            sequence=seq,
            timestamp_ms=ts,
            payload=payload,
            requires_ack=(flags & 0x01) != 0
        )


@dataclass
class PeerInfo:
    """Информация о пире."""
    address: Tuple[str, int]
    last_seen: float = 0
    rtt_ms: float = 0
    packets_sent: int = 0
    packets_received: int = 0
    packets_lost: int = 0
    
    @property
    def packet_loss_percent(self) -> float:
        total = self.packets_sent
        if total == 0:
            return 0
        return (self.packets_lost / total) * 100


class ShapedUDPTransport:
    """
    UDP транспорт с Traffic Shaping для low-latency.
    
    Использование:
        transport = ShapedUDPTransport(
            local_port=5000,
            traffic_profile="gaming",
            obfuscation="xor"
        )
        await transport.start()
        await transport.send_to(b"game data", ("192.168.1.100", 5000))
        data, addr = await transport.receive()
        await transport.stop()
    """
    
    # Константы
    MAX_PACKET_SIZE = 1400  # Безопасный размер для UDP
    PING_INTERVAL = 5.0     # Секунды между ping
    PEER_TIMEOUT = 30.0     # Таймаут пира
    ACK_TIMEOUT = 0.1       # Таймаут ожидания ACK
    MAX_RETRIES = 3         # Максимум повторов для reliable
    
    def __init__(
        self,
        local_port: int = 0,
        local_host: str = "0.0.0.0",
        traffic_profile: str = "gaming",
        obfuscation: str = "none",
        obfuscation_key: str = "x0tta6bl4",
        reliable_mode: bool = False
    ):
        self.local_host = local_host
        self.local_port = local_port
        self.reliable_mode = reliable_mode
        
        # Сокет
        self._socket: Optional[socket.socket] = None
        self._running = False
        self._receive_task: Optional[asyncio.Task] = None
        self._maintenance_task: Optional[asyncio.Task] = None
        
        # Sequence numbers
        self._sequence = 0
        self._pending_acks: Dict[int, UDPPacket] = {}
        
        # Пиры
        self._peers: Dict[Tuple[str, int], PeerInfo] = {}
        
        # Callbacks
        self._on_receive: Optional[Callable] = None
        self._on_peer_timeout: Optional[Callable] = None
        
        # Traffic Shaping
        self._shaper: Optional[TrafficShaper] = None
        if traffic_profile != "none":
            try:
                profile = TrafficProfile(traffic_profile)
                self._shaper = TrafficShaper(profile)
                logger.info(f"UDP Traffic Shaping: {traffic_profile}")
            except ValueError:
                logger.warning(f"Неизвестный профиль: {traffic_profile}")
        
        # Obfuscation
        self._transport: Optional[ObfuscationTransport] = None
        if obfuscation != "none":
            self._transport = self._create_transport(obfuscation, obfuscation_key)
        
        # Метрики
        self._analyzer = TrafficAnalyzer()
        self._total_sent = 0
        self._total_received = 0
        self._start_time = 0
    
    def _create_transport(self, name: str, key: str) -> Optional[ObfuscationTransport]:
        """Создать обфускатор."""
        try:
            if name == "xor":
                return TransportManager.create("xor", key=key)
            elif name == "shadowsocks":
                return TransportManager.create("shadowsocks", password=key)
            # FakeTLS не подходит для UDP
        except Exception as e:
            logger.error(f"Ошибка создания транспорта: {e}")
        return None
    
    def _next_sequence(self) -> int:
        """Получить следующий sequence number."""
        self._sequence = (self._sequence + 1) % (2**32)
        return self._sequence
    
    def _current_timestamp_ms(self) -> int:
        """Текущий timestamp в миллисекундах."""
        return int(time.time() * 1000)
    
    async def start(self):
        """Запустить транспорт."""
        self._socket = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
        self._socket.setsockopt(socket.SOL_SOCKET, socket.SO_REUSEADDR, 1)
        self._socket.setblocking(False)
        self._socket.bind((self.local_host, self.local_port))
        
        # Получаем реальный порт если был 0
        self.local_port = self._socket.getsockname()[1]
        
        self._running = True
        self._start_time = time.time()
        
        # Запускаем фоновые задачи
        loop = asyncio.get_event_loop()
        self._receive_task = loop.create_task(self._receive_loop())
        self._maintenance_task = loop.create_task(self._maintenance_loop())
        
        logger.info(f"UDP транспорт запущен на {self.local_host}:{self.local_port}")
    
    async def stop(self):
        """Остановить транспорт."""
        self._running = False
        
        if self._receive_task:
            self._receive_task.cancel()
            try:
                await self._receive_task
            except asyncio.CancelledError:
                pass
        
        if self._maintenance_task:
            self._maintenance_task.cancel()
            try:
                await self._maintenance_task
            except asyncio.CancelledError:
                pass
        
        if self._socket:
            self._socket.close()
            self._socket = None
        
        logger.info("UDP транспорт остановлен")
    
    def _prepare_packet(self, data: bytes, requires_ack: bool = False) -> bytes:
        """Подготовить пакет: создать заголовок + obfuscate + shape."""
        packet = UDPPacket(
            packet_type=PacketType.DATA,
            sequence=self._next_sequence(),
            timestamp_ms=self._current_timestamp_ms(),
            payload=data,
            requires_ack=requires_ack or self.reliable_mode
        )
        
        raw = packet.to_bytes()
        
        # Обфускация
        if self._transport:
            raw = self._transport.obfuscate(raw)
        
        # Шейпинг (только паддинг, без задержки для UDP)
        if self._shaper:
            raw = self._shaper.shape_packet(raw)
        
        return raw
    
    def _unpack_packet(self, data: bytes) -> UDPPacket:
        """Распаковать пакет."""
        raw = data
        
        # Unshape
        if self._shaper:
            raw = self._shaper.unshape_packet(raw)
        
        # Deobfuscate
        if self._transport:
            raw = self._transport.deobfuscate(raw)
        
        return UDPPacket.from_bytes(raw)
    
    async def send_to(
        self, 
        data: bytes, 
        address: Tuple[str, int],
        reliable: bool = False
    ) -> bool:
        """Отправить данные на адрес."""
        if not self._socket or not self._running:
            return False
        
        try:
            packet_data = self._prepare_packet(data, requires_ack=reliable)
            
            # Применяем задержку шейпинга для имитации профиля
            if self._shaper:
                delay = self._shaper.get_send_delay()
                if delay > 0:
                    await asyncio.sleep(delay)
            
            loop = asyncio.get_event_loop()
            await loop.run_in_executor(
                None,
                lambda: self._socket.sendto(packet_data, address)
            )
            
            # Обновляем статистику пира
            if address not in self._peers:
                self._peers[address] = PeerInfo(address=address)
            self._peers[address].packets_sent += 1
            self._peers[address].last_seen = time.time()
            
            # Метрики
            self._total_sent += 1
            self._analyzer.record_packet(len(packet_data))
            
            return True
            
        except Exception as e:
            logger.error(f"Ошибка отправки на {address}: {e}")
            return False
    
    async def send_ping(self, address: Tuple[str, int]):
        """Отправить ping для измерения RTT."""
        packet = UDPPacket(
            packet_type=PacketType.PING,
            sequence=self._next_sequence(),
            timestamp_ms=self._current_timestamp_ms(),
            payload=b""
        )
        
        raw = packet.to_bytes()
        if self._transport:
            raw = self._transport.obfuscate(raw)
        
        try:
            loop = asyncio.get_event_loop()
            await loop.run_in_executor(
                None,
                lambda: self._socket.sendto(raw, address)
            )
        except Exception as e:
            logger.error(f"Ошибка отправки ping: {e}")
    
    async def _send_pong(self, address: Tuple[str, int], ping_timestamp: int):
        """Отправить pong в ответ на ping."""
        packet = UDPPacket(
            packet_type=PacketType.PONG,
            sequence=self._next_sequence(),
            timestamp_ms=ping_timestamp,  # Эхо оригинального timestamp
            payload=b""
        )
        
        raw = packet.to_bytes()
        if self._transport:
            raw = self._transport.obfuscate(raw)
        
        try:
            loop = asyncio.get_event_loop()
            await loop.run_in_executor(
                None,
                lambda: self._socket.sendto(raw, address)
            )
        except Exception:
            pass
    
    async def _send_ack(self, address: Tuple[str, int], sequence: int):
        """Отправить ACK."""
        packet = UDPPacket(
            packet_type=PacketType.ACK,
            sequence=sequence,
            timestamp_ms=self._current_timestamp_ms(),
            payload=b""
        )
        
        raw = packet.to_bytes()
        if self._transport:
            raw = self._transport.obfuscate(raw)
        
        try:
            loop = asyncio.get_event_loop()
            await loop.run_in_executor(
                None,
                lambda: self._socket.sendto(raw, address)
            )
        except Exception:
            pass
    
    async def _receive_loop(self):
        """Фоновый цикл приёма пакетов."""
        loop = asyncio.get_event_loop()
        
        while self._running:
            try:
                # Non-blocking receive
                data, address = await loop.run_in_executor(
                    None,
                    lambda: self._socket.recvfrom(65535)
                )
                
                packet = self._unpack_packet(data)
                
                # Обновляем информацию о пире
                if address not in self._peers:
                    self._peers[address] = PeerInfo(address=address)
                peer = self._peers[address]
                peer.last_seen = time.time()
                peer.packets_received += 1
                
                self._total_received += 1
                
                # Обработка по типу пакета
                if packet.packet_type == PacketType.DATA:
                    if packet.requires_ack:
                        await self._send_ack(address, packet.sequence)
                    
                    if self._on_receive:
                        await self._on_receive(packet.payload, address)
                
                elif packet.packet_type == PacketType.PING:
                    await self._send_pong(address, packet.timestamp_ms)
                
                elif packet.packet_type == PacketType.PONG:
                    # Вычисляем RTT
                    rtt = self._current_timestamp_ms() - packet.timestamp_ms
                    peer.rtt_ms = rtt
                
                elif packet.packet_type == PacketType.ACK:
                    # Удаляем из pending
                    if packet.sequence in self._pending_acks:
                        del self._pending_acks[packet.sequence]
                
            except BlockingIOError:
                await asyncio.sleep(0.001)  # 1ms
            except Exception as e:
                if self._running:
                    logger.debug(f"Ошибка приёма: {e}")
                await asyncio.sleep(0.01)
    
    async def _maintenance_loop(self):
        """Фоновые задачи: ping, retry, cleanup."""
        while self._running:
            try:
                now = time.time()
                
                # Ping всех пиров
                for address, peer in list(self._peers.items()):
                    # Проверка таймаута
                    if now - peer.last_seen > self.PEER_TIMEOUT:
                        if self._on_peer_timeout:
                            await self._on_peer_timeout(address)
                        del self._peers[address]
                        continue
                    
                    # Отправляем ping
                    if now - peer.last_seen > self.PING_INTERVAL:
                        await self.send_ping(address)
                
                # Retry для reliable пакетов
                for seq, packet in list(self._pending_acks.items()):
                    packet.retries += 1
                    if packet.retries > self.MAX_RETRIES:
                        del self._pending_acks[seq]
                        # Увеличиваем счётчик потерь
                    # TODO: реальный retry
                
            except Exception as e:
                logger.error(f"Maintenance error: {e}")
            
            await asyncio.sleep(1.0)
    
    def on_receive(self, handler: Callable):
        """Зарегистрировать обработчик входящих данных."""
        self._on_receive = handler
        return handler
    
    def on_peer_timeout(self, handler: Callable):
        """Зарегистрировать обработчик таймаута пира."""
        self._on_peer_timeout = handler
        return handler
    
    def get_peer_info(self, address: Tuple[str, int]) -> Optional[PeerInfo]:
        """Получить информацию о пире."""
        return self._peers.get(address)
    
    def get_all_peers(self) -> Dict[Tuple[str, int], PeerInfo]:
        """Получить всех пиров."""
        return self._peers.copy()
    
    def get_stats(self) -> Dict[str, Any]:
        """Статистика транспорта."""
        uptime = time.time() - self._start_time if self._start_time else 0
        traffic_stats = self._analyzer.get_statistics()
        
        return {
            "local_address": f"{self.local_host}:{self.local_port}",
            "uptime_seconds": uptime,
            "peers_count": len(self._peers),
            "total_sent": self._total_sent,
            "total_received": self._total_received,
            "packets_per_second": self._total_sent / uptime if uptime > 0 else 0,
            "traffic_profile": self._shaper.profile.value if self._shaper else "none",
            "obfuscation": self._transport.__class__.__name__ if self._transport else "none",
            "traffic_analysis": traffic_stats
        }


class UDPHolePuncher:
    """
    NAT Traversal через UDP hole punching.
    Позволяет устанавливать P2P соединения через NAT.
    """
    
    def __init__(self, stun_server: Tuple[str, int] = ("stun.l.google.com", 19302)):
        self.stun_server = stun_server
        self._local_socket: Optional[socket.socket] = None
        self._public_address: Optional[Tuple[str, int]] = None
    
    async def discover_public_address(self, local_port: int = 0) -> Optional[Tuple[str, int]]:
        """
        Узнать публичный IP:port через STUN-подобный запрос.
        Упрощённая реализация без полного STUN протокола.
        """
        try:
            sock = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
            sock.setsockopt(socket.SOL_SOCKET, socket.SO_REUSEADDR, 1)
            sock.setblocking(False)
            sock.bind(("0.0.0.0", local_port))
            
            self._local_socket = sock
            local_port = sock.getsockname()[1]
            
            # Простой STUN Binding Request (упрощённый)
            # В реальности нужен полный STUN клиент
            transaction_id = hashlib.md5(str(time.time()).encode()).digest()[:12]
            stun_request = struct.pack("!HHI", 0x0001, 0, 0x2112A442) + transaction_id
            
            loop = asyncio.get_event_loop()
            await loop.run_in_executor(
                None,
                lambda: sock.sendto(stun_request, self.stun_server)
            )
            
            # Ждём ответ
            try:
                data, _ = await asyncio.wait_for(
                    loop.run_in_executor(None, lambda: sock.recvfrom(1024)),
                    timeout=3.0
                )
                
                # Парсим упрощённо (полный парсинг сложнее)
                # XOR-MAPPED-ADDRESS обычно на offset 20+ в ответе
                # Для demo возвращаем локальный адрес
                logger.info(f"STUN response received ({len(data)} bytes)")
                
            except asyncio.TimeoutError:
                logger.warning("STUN timeout, using local address")
            
            # Fallback: возвращаем локальный адрес
            local_ip = socket.gethostbyname(socket.gethostname())
            self._public_address = (local_ip, local_port)
            return self._public_address
            
        except Exception as e:
            logger.error(f"STUN discovery error: {e}")
            return None
    
    async def punch_hole(
        self,
        transport: ShapedUDPTransport,
        peer_address: Tuple[str, int],
        attempts: int = 10
    ) -> bool:
        """
        Выполнить hole punching к пиру.
        Оба пира должны одновременно слать пакеты друг другу.
        """
        packet = UDPPacket(
            packet_type=PacketType.HOLE_PUNCH,
            sequence=0,
            timestamp_ms=int(time.time() * 1000),
            payload=b"PUNCH"
        )
        
        raw = packet.to_bytes()
        
        for i in range(attempts):
            try:
                await asyncio.get_event_loop().run_in_executor(
                    None,
                    lambda: transport._socket.sendto(raw, peer_address)
                )
                logger.debug(f"Hole punch attempt {i+1} to {peer_address}")
                await asyncio.sleep(0.1)
            except Exception as e:
                logger.error(f"Hole punch error: {e}")
        
        # Проверяем успех через ping
        await transport.send_ping(peer_address)
        await asyncio.sleep(0.5)
        
        peer = transport.get_peer_info(peer_address)
        return peer is not None and peer.rtt_ms > 0


# Пример использования
async def example_gaming_transport():
    """Пример: gaming транспорт."""
    
    transport = ShapedUDPTransport(
        local_port=5000,
        traffic_profile="gaming",
        obfuscation="xor",
        obfuscation_key="game-key-123"
    )
    
    @transport.on_receive
    async def handle_data(data: bytes, address: Tuple[str, int]):
        print(f"[{address}] Получено: {data[:50]}")
    
    @transport.on_peer_timeout
    async def handle_timeout(address: Tuple[str, int]):
        print(f"[{address}] Пир отключился")
    
    await transport.start()
    
    print(f"Gaming UDP транспорт запущен на порту {transport.local_port}")
    print(f"Профиль: gaming (10-33ms интервал, 50-300 байт)")
    print(f"Обфускация: XOR")
    
    # Симуляция отправки игровых пакетов
    target = ("127.0.0.1", 5001)
    
    for i in range(10):
        game_state = f"player_pos:{i*10},{i*5}|health:100|ammo:30".encode()
        await transport.send_to(game_state, target)
        await asyncio.sleep(0.033)  # ~30 FPS
    
    print(f"\nСтатистика: {transport.get_stats()}")
    
    await transport.stop()


if __name__ == "__main__":
    asyncio.run(example_gaming_transport())
