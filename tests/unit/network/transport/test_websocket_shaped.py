"""
Тесты для WebSocket транспорта с Traffic Shaping.
"""

import sys

import pytest

sys.path.insert(0, "/mnt/AC74CC2974CBF3DC")

# Тесты без реального WebSocket соединения (mock-based)
from src.network.transport.websocket_shaped import (ConnectionState,
                                                    ShapedMessage,
                                                    ShapedWebSocketClient,
                                                    ShapedWebSocketServer)


class TestShapedWebSocketClient:
    """Тесты клиента."""

    def test_initialization_default(self):
        """Проверка инициализации с параметрами по умолчанию."""
        try:
            client = ShapedWebSocketClient(uri="ws://localhost:8765")
            assert client.state == ConnectionState.DISCONNECTED
            assert client._transport is None
            assert client._shaper is None
            assert client.auto_reconnect is True
        except ImportError:
            pytest.skip("websockets not installed")

    def test_initialization_with_obfuscation(self):
        """Инициализация с обфускацией."""
        try:
            client = ShapedWebSocketClient(
                uri="ws://localhost:8765", obfuscation="xor", obfuscation_key="test-key"
            )
            assert client._transport is not None
        except ImportError:
            pytest.skip("websockets not installed")

    def test_initialization_with_shaping(self):
        """Инициализация с шейпингом."""
        try:
            client = ShapedWebSocketClient(
                uri="ws://localhost:8765", traffic_profile="video_streaming"
            )
            assert client._shaper is not None
            assert client._shaper.profile.value == "video_streaming"
        except ImportError:
            pytest.skip("websockets not installed")

    def test_initialization_full(self):
        """Полная инициализация."""
        try:
            client = ShapedWebSocketClient(
                uri="ws://localhost:8765",
                obfuscation="faketls",
                obfuscation_key="google.com",
                traffic_profile="gaming",
            )
            assert client._transport is not None
            assert client._shaper is not None
        except ImportError:
            pytest.skip("websockets not installed")

    def test_prepare_message_no_processing(self):
        """Подготовка сообщения без обработки."""
        try:
            client = ShapedWebSocketClient(uri="ws://localhost:8765")
            data = b"test message"
            msg = client._prepare_message(data)

            assert isinstance(msg, ShapedMessage)
            assert msg.data == data
            assert msg.original_size == len(data)
            assert msg.delay_ms == 0.0
        except ImportError:
            pytest.skip("websockets not installed")

    def test_prepare_message_with_shaping(self):
        """Подготовка сообщения с шейпингом."""
        try:
            client = ShapedWebSocketClient(
                uri="ws://localhost:8765", traffic_profile="voice_call"
            )
            data = b"x" * 50
            msg = client._prepare_message(data)

            # voice_call паддит до 200 + 2 prefix = 202
            assert msg.shaped_size >= 202
            assert msg.profile == "voice_call"
        except ImportError:
            pytest.skip("websockets not installed")

    def test_prepare_unpack_roundtrip(self):
        """Roundtrip: prepare -> unpack."""
        try:
            client = ShapedWebSocketClient(
                uri="ws://localhost:8765",
                obfuscation="xor",
                obfuscation_key="roundtrip-key",
                traffic_profile="gaming",
            )

            original = b"roundtrip test data"
            msg = client._prepare_message(original)
            recovered = client._unpack_message(msg.data)

            assert recovered == original
        except ImportError:
            pytest.skip("websockets not installed")

    def test_stats_initial(self):
        """Начальная статистика."""
        try:
            client = ShapedWebSocketClient(uri="ws://localhost:8765")
            stats = client.get_stats()

            assert stats["state"] == "disconnected"
            assert stats["messages_sent"] == 0
            assert stats["bytes_sent"] == 0
        except ImportError:
            pytest.skip("websockets not installed")


class TestShapedWebSocketServer:
    """Тесты сервера."""

    def test_initialization(self):
        """Проверка инициализации сервера."""
        try:
            server = ShapedWebSocketServer(
                host="127.0.0.1",
                port=9999,
                obfuscation="xor",
                traffic_profile="video_streaming",
            )
            assert server.host == "127.0.0.1"
            assert server.port == 9999
            assert server._obfuscation == "xor"
            assert server._traffic_profile == "video_streaming"
        except ImportError:
            pytest.skip("websockets not installed")

    def test_stats_initial(self):
        """Начальная статистика сервера."""
        try:
            server = ShapedWebSocketServer()
            stats = server.get_stats()

            assert stats["clients_connected"] == 0
            assert stats["total_messages"] == 0
        except ImportError:
            pytest.skip("websockets not installed")

    def test_message_handler_registration(self):
        """Регистрация обработчика сообщений."""
        try:
            server = ShapedWebSocketServer()

            @server.on_message
            async def handler(client_id, data):
                return b"response"

            assert server._message_handler is not None
        except ImportError:
            pytest.skip("websockets not installed")


class TestConnectionState:
    """Тесты состояний соединения."""

    def test_states_exist(self):
        """Все состояния определены."""
        assert ConnectionState.DISCONNECTED.value == "disconnected"
        assert ConnectionState.CONNECTING.value == "connecting"
        assert ConnectionState.CONNECTED.value == "connected"
        assert ConnectionState.RECONNECTING.value == "reconnecting"
        assert ConnectionState.CLOSED.value == "closed"


class TestShapedMessage:
    """Тесты структуры сообщения."""

    def test_message_creation(self):
        """Создание сообщения."""
        msg = ShapedMessage(
            data=b"test",
            delay_ms=10.5,
            original_size=4,
            shaped_size=100,
            profile="gaming",
        )

        assert msg.data == b"test"
        assert msg.delay_ms == 10.5
        assert msg.original_size == 4
        assert msg.shaped_size == 100
        assert msg.profile == "gaming"
