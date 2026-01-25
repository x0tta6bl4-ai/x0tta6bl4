"""
WebSocket транспорт с интегрированным Traffic Shaping.
Обеспечивает передачу данных через WebSocket с обфускацией и шейпингом трафика.
"""
import asyncio
import json
import logging
import time
from typing import Optional, Callable, Dict, Any
from dataclasses import dataclass
from enum import Enum

try:
    import websockets
    from websockets.client import WebSocketClientProtocol
    from websockets.server import WebSocketServerProtocol
    WEBSOCKETS_AVAILABLE = True
except ImportError:
    WEBSOCKETS_AVAILABLE = False
    # Заглушки для type hints когда websockets недоступен
    WebSocketClientProtocol = None
    WebSocketServerProtocol = None

from src.network.obfuscation import (
    TransportManager, 
    ObfuscationTransport,
    TrafficShaper,
    TrafficProfile,
    TrafficAnalyzer
)

logger = logging.getLogger(__name__)


class ConnectionState(Enum):
    """Состояние соединения."""
    DISCONNECTED = "disconnected"
    CONNECTING = "connecting"
    CONNECTED = "connected"
    RECONNECTING = "reconnecting"
    CLOSED = "closed"


@dataclass
class ShapedMessage:
    """Сообщение после шейпинга."""
    data: bytes
    delay_ms: float
    original_size: int
    shaped_size: int
    profile: str


class ShapedWebSocketClient:
    """
    WebSocket клиент с Traffic Shaping и Obfuscation.
    
    Использование:
        client = ShapedWebSocketClient(
            uri="ws://localhost:8765",
            obfuscation="faketls",
            traffic_profile="video_streaming"
        )
        await client.connect()
        await client.send(b"Hello mesh!")
        data = await client.receive()
        await client.close()
    """
    
    def __init__(
        self,
        uri: str,
        obfuscation: str = "none",
        obfuscation_key: str = "x0tta6bl4",
        traffic_profile: str = "none",
        auto_reconnect: bool = True,
        reconnect_delay: float = 1.0,
        max_reconnect_attempts: int = 5
    ):
        if not WEBSOCKETS_AVAILABLE:
            raise ImportError("websockets library not installed. Run: pip install websockets")
        
        self.uri = uri
        self.auto_reconnect = auto_reconnect
        self.reconnect_delay = reconnect_delay
        self.max_reconnect_attempts = max_reconnect_attempts
        
        # Состояние
        self.state = ConnectionState.DISCONNECTED
        self._ws: Optional[WebSocketClientProtocol] = None
        self._reconnect_attempts = 0
        
        # Obfuscation
        self._transport: Optional[ObfuscationTransport] = None
        if obfuscation != "none":
            self._transport = self._create_transport(obfuscation, obfuscation_key)
        
        # Traffic Shaping
        self._shaper: Optional[TrafficShaper] = None
        if traffic_profile != "none":
            try:
                profile = TrafficProfile(traffic_profile)
                self._shaper = TrafficShaper(profile)
            except ValueError:
                logger.warning(f"Неизвестный профиль: {traffic_profile}")
        
        # Метрики
        self._analyzer = TrafficAnalyzer()
        self._messages_sent = 0
        self._messages_received = 0
        self._bytes_sent = 0
        self._bytes_received = 0
    
    def _create_transport(self, name: str, key: str) -> Optional[ObfuscationTransport]:
        """Создать транспорт обфускации."""
        try:
            if name == "xor":
                return TransportManager.create("xor", key=key)
            elif name == "faketls":
                return TransportManager.create("faketls", sni=key or "google.com")
            elif name == "shadowsocks":
                return TransportManager.create("shadowsocks", password=key)
            else:
                logger.warning(f"Неизвестный транспорт: {name}")
                return None
        except Exception as e:
            logger.error(f"Ошибка создания транспорта {name}: {e}")
            return None
    
    async def connect(self) -> bool:
        """Установить соединение."""
        self.state = ConnectionState.CONNECTING
        
        try:
            self._ws = await websockets.connect(self.uri)
            self.state = ConnectionState.CONNECTED
            self._reconnect_attempts = 0
            logger.info(f"Подключено к {self.uri}")
            return True
        except Exception as e:
            logger.error(f"Ошибка подключения: {e}")
            self.state = ConnectionState.DISCONNECTED
            return False
    
    async def _reconnect(self) -> bool:
        """Переподключение с exponential backoff."""
        if not self.auto_reconnect:
            return False
        
        while self._reconnect_attempts < self.max_reconnect_attempts:
            self.state = ConnectionState.RECONNECTING
            self._reconnect_attempts += 1
            
            delay = self.reconnect_delay * (2 ** (self._reconnect_attempts - 1))
            logger.info(f"Переподключение через {delay:.1f}с (попытка {self._reconnect_attempts})")
            
            await asyncio.sleep(delay)
            
            if await self.connect():
                return True
        
        logger.error(f"Не удалось переподключиться после {self.max_reconnect_attempts} попыток")
        self.state = ConnectionState.CLOSED
        return False
    
    def _prepare_message(self, data: bytes) -> ShapedMessage:
        """Подготовить сообщение: obfuscate + shape."""
        original_size = len(data)
        processed = data
        
        # 1. Обфускация
        if self._transport:
            processed = self._transport.obfuscate(processed)
        
        # 2. Шейпинг
        delay_ms = 0.0
        profile = "none"
        
        if self._shaper:
            processed = self._shaper.shape_packet(processed)
            delay_ms = self._shaper.get_send_delay() * 1000
            profile = self._shaper.profile.value
        
        return ShapedMessage(
            data=processed,
            delay_ms=delay_ms,
            original_size=original_size,
            shaped_size=len(processed),
            profile=profile
        )
    
    def _unpack_message(self, data: bytes) -> bytes:
        """Распаковать сообщение: unshape + deobfuscate."""
        processed = data
        
        # 1. Unshape
        if self._shaper:
            processed = self._shaper.unshape_packet(processed)
        
        # 2. Deobfuscate
        if self._transport:
            processed = self._transport.deobfuscate(processed)
        
        return processed
    
    async def send(self, data: bytes) -> bool:
        """Отправить данные с шейпингом."""
        if self.state != ConnectionState.CONNECTED or not self._ws:
            if not await self._reconnect():
                return False
        
        try:
            msg = self._prepare_message(data)
            
            # Применяем задержку для имитации профиля
            if msg.delay_ms > 0:
                await asyncio.sleep(msg.delay_ms / 1000)
            
            await self._ws.send(msg.data)
            
            # Метрики
            self._messages_sent += 1
            self._bytes_sent += msg.shaped_size
            self._analyzer.record_packet(msg.shaped_size)
            
            logger.debug(f"Отправлено: {msg.original_size}B -> {msg.shaped_size}B, delay={msg.delay_ms:.1f}ms")
            return True
            
        except websockets.ConnectionClosed:
            logger.warning("Соединение закрыто, переподключение...")
            self.state = ConnectionState.DISCONNECTED
            return await self._reconnect() and await self.send(data)
        except Exception as e:
            logger.error(f"Ошибка отправки: {e}")
            return False
    
    async def receive(self, timeout: Optional[float] = None) -> Optional[bytes]:
        """Получить данные."""
        if self.state != ConnectionState.CONNECTED or not self._ws:
            return None
        
        try:
            if timeout:
                raw = await asyncio.wait_for(self._ws.recv(), timeout=timeout)
            else:
                raw = await self._ws.recv()
            
            if isinstance(raw, str):
                raw = raw.encode()
            
            data = self._unpack_message(raw)
            
            # Метрики
            self._messages_received += 1
            self._bytes_received += len(raw)
            
            return data
            
        except asyncio.TimeoutError:
            return None
        except websockets.ConnectionClosed:
            self.state = ConnectionState.DISCONNECTED
            return None
        except Exception as e:
            logger.error(f"Ошибка получения: {e}")
            return None
    
    async def close(self):
        """Закрыть соединение."""
        if self._ws:
            await self._ws.close()
            self._ws = None
        self.state = ConnectionState.CLOSED
        logger.info("Соединение закрыто")
    
    def get_stats(self) -> Dict[str, Any]:
        """Получить статистику."""
        traffic_stats = self._analyzer.get_statistics()
        return {
            "state": self.state.value,
            "messages_sent": self._messages_sent,
            "messages_received": self._messages_received,
            "bytes_sent": self._bytes_sent,
            "bytes_received": self._bytes_received,
            "traffic_analysis": traffic_stats,
            "obfuscation": self._transport.__class__.__name__ if self._transport else "none",
            "traffic_profile": self._shaper.profile.value if self._shaper else "none"
        }


class ShapedWebSocketServer:
    """
    WebSocket сервер с Traffic Shaping и Obfuscation.
    """
    
    def __init__(
        self,
        host: str = "0.0.0.0",
        port: int = 8765,
        obfuscation: str = "none",
        obfuscation_key: str = "x0tta6bl4",
        traffic_profile: str = "none"
    ):
        if not WEBSOCKETS_AVAILABLE:
            raise ImportError("websockets library not installed")
        
        self.host = host
        self.port = port
        self._server = None
        self._clients: Dict[str, WebSocketServerProtocol] = {}
        self._message_handler: Optional[Callable] = None
        
        # Obfuscation & Shaping config
        self._obfuscation = obfuscation
        self._obfuscation_key = obfuscation_key
        self._traffic_profile = traffic_profile
        
        # Stats
        self._total_messages = 0
        self._total_bytes = 0
    
    def _create_shaper(self) -> Optional[TrafficShaper]:
        """Создать шейпер для клиента."""
        if self._traffic_profile == "none":
            return None
        try:
            return TrafficShaper(TrafficProfile(self._traffic_profile))
        except ValueError:
            return None
    
    def _create_transport(self) -> Optional[ObfuscationTransport]:
        """Создать транспорт для клиента."""
        if self._obfuscation == "none":
            return None
        try:
            if self._obfuscation == "xor":
                return TransportManager.create("xor", key=self._obfuscation_key)
            elif self._obfuscation == "faketls":
                return TransportManager.create("faketls", sni=self._obfuscation_key)
            elif self._obfuscation == "shadowsocks":
                return TransportManager.create("shadowsocks", password=self._obfuscation_key)
        except Exception:
            pass
        return None
    
    async def _handle_client(self, websocket: WebSocketServerProtocol, path: str):
        """Обработчик клиентского подключения."""
        client_id = f"{websocket.remote_address[0]}:{websocket.remote_address[1]}"
        self._clients[client_id] = websocket
        
        transport = self._create_transport()
        shaper = self._create_shaper()
        
        logger.info(f"Клиент подключён: {client_id}")
        
        try:
            async for message in websocket:
                if isinstance(message, str):
                    message = message.encode()
                
                # Unpack
                data = message
                if shaper:
                    data = shaper.unshape_packet(data)
                if transport:
                    data = transport.deobfuscate(data)
                
                self._total_messages += 1
                self._total_bytes += len(message)
                
                # Обработка
                if self._message_handler:
                    response = await self._message_handler(client_id, data)
                    if response:
                        # Pack response
                        resp_data = response
                        if transport:
                            resp_data = transport.obfuscate(resp_data)
                        if shaper:
                            resp_data = shaper.shape_packet(resp_data)
                            delay = shaper.get_send_delay()
                            if delay > 0:
                                await asyncio.sleep(delay)
                        
                        await websocket.send(resp_data)
                        
        except websockets.ConnectionClosed:
            pass
        finally:
            del self._clients[client_id]
            logger.info(f"Клиент отключён: {client_id}")
    
    def on_message(self, handler: Callable):
        """Зарегистрировать обработчик сообщений."""
        self._message_handler = handler
        return handler
    
    async def start(self):
        """Запустить сервер."""
        self._server = await websockets.serve(
            self._handle_client,
            self.host,
            self.port
        )
        logger.info(f"WebSocket сервер запущен на ws://{self.host}:{self.port}")
        logger.info(f"  Obfuscation: {self._obfuscation}")
        logger.info(f"  Traffic Profile: {self._traffic_profile}")
    
    async def stop(self):
        """Остановить сервер."""
        if self._server:
            self._server.close()
            await self._server.wait_closed()
            logger.info("Сервер остановлен")
    
    def get_stats(self) -> Dict[str, Any]:
        """Статистика сервера."""
        return {
            "clients_connected": len(self._clients),
            "total_messages": self._total_messages,
            "total_bytes": self._total_bytes,
            "obfuscation": self._obfuscation,
            "traffic_profile": self._traffic_profile
        }


# Пример использования
async def example_echo_server():
    """Пример: эхо-сервер с шейпингом."""
    server = ShapedWebSocketServer(
        port=8765,
        obfuscation="xor",
        obfuscation_key="demo-key",
        traffic_profile="gaming"
    )
    
    @server.on_message
    async def handle(client_id: str, data: bytes) -> Optional[bytes]:
        logger.info(f"[{client_id}] Получено: {data[:50]}...")
        return b"ECHO: " + data
    
    await server.start()
    
    # Держим сервер запущенным
    try:
        await asyncio.Future()  # run forever
    except asyncio.CancelledError:
        await server.stop()


async def example_client():
    """Пример: клиент с шейпингом."""
    client = ShapedWebSocketClient(
        uri="ws://localhost:8765",
        obfuscation="xor",
        obfuscation_key="demo-key",
        traffic_profile="gaming"
    )
    
    if await client.connect():
        for i in range(5):
            await client.send(f"Сообщение #{i+1}".encode())
            response = await client.receive(timeout=5.0)
            if response:
                print(f"Ответ: {response.decode()}")
        
        print(f"Статистика: {client.get_stats()}")
        await client.close()


if __name__ == "__main__":
    import sys
    
    if len(sys.argv) > 1 and sys.argv[1] == "server":
        asyncio.run(example_echo_server())
    else:
        asyncio.run(example_client())
