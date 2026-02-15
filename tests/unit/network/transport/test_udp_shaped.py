"""
Тесты для UDP транспорта с Traffic Shaping.
"""

import asyncio
import struct
import sys

import pytest

sys.path.insert(0, "/mnt/AC74CC2974CBF3DC")

from src.network.transport.udp_shaped import (PacketType, PeerInfo,
                                              ShapedUDPTransport,
                                              UDPHolePuncher, UDPPacket)


class TestUDPPacket:
    """Тесты структуры пакета."""

    def test_packet_creation(self):
        """Создание пакета."""
        packet = UDPPacket(
            packet_type=PacketType.DATA,
            sequence=42,
            timestamp_ms=1234567890,
            payload=b"test data",
        )

        assert packet.packet_type == PacketType.DATA
        assert packet.sequence == 42
        assert packet.payload == b"test data"
        assert packet.requires_ack is False

    def test_packet_serialization(self):
        """Сериализация/десериализация пакета."""
        original = UDPPacket(
            packet_type=PacketType.DATA,
            sequence=100,
            timestamp_ms=9876543210,
            payload=b"hello mesh network",
            requires_ack=True,
        )

        serialized = original.to_bytes()
        restored = UDPPacket.from_bytes(serialized)

        assert restored.packet_type == original.packet_type
        assert restored.sequence == original.sequence
        assert restored.timestamp_ms == original.timestamp_ms
        assert restored.payload == original.payload
        assert restored.requires_ack == original.requires_ack

    def test_packet_types(self):
        """Проверка всех типов пакетов."""
        types = [
            PacketType.DATA,
            PacketType.ACK,
            PacketType.PING,
            PacketType.PONG,
            PacketType.HOLE_PUNCH,
            PacketType.HANDSHAKE,
            PacketType.CLOSE,
        ]

        for ptype in types:
            packet = UDPPacket(
                packet_type=ptype, sequence=1, timestamp_ms=1000, payload=b""
            )
            serialized = packet.to_bytes()
            restored = UDPPacket.from_bytes(serialized)
            assert restored.packet_type == ptype

    def test_large_payload(self):
        """Тест с большим payload."""
        large_payload = bytes(range(256)) * 5  # 1280 bytes

        packet = UDPPacket(
            packet_type=PacketType.DATA,
            sequence=999,
            timestamp_ms=5555555,
            payload=large_payload,
        )

        serialized = packet.to_bytes()
        restored = UDPPacket.from_bytes(serialized)

        assert restored.payload == large_payload

    def test_empty_payload(self):
        """Тест с пустым payload."""
        packet = UDPPacket(
            packet_type=PacketType.PING, sequence=0, timestamp_ms=0, payload=b""
        )

        serialized = packet.to_bytes()
        restored = UDPPacket.from_bytes(serialized)

        assert restored.payload == b""


class TestPeerInfo:
    """Тесты информации о пире."""

    def test_peer_creation(self):
        """Создание информации о пире."""
        peer = PeerInfo(address=("192.168.1.100", 5000))

        assert peer.address == ("192.168.1.100", 5000)
        assert peer.packets_sent == 0
        assert peer.rtt_ms == 0

    def test_packet_loss_calculation(self):
        """Расчёт потерь пакетов."""
        peer = PeerInfo(address=("10.0.0.1", 8000))
        peer.packets_sent = 100
        peer.packets_lost = 5

        assert peer.packet_loss_percent == 5.0

    def test_packet_loss_zero_division(self):
        """Нет деления на ноль при 0 пакетов."""
        peer = PeerInfo(address=("10.0.0.1", 8000))
        assert peer.packet_loss_percent == 0


class TestShapedUDPTransport:
    """Тесты UDP транспорта."""

    def test_initialization_default(self):
        """Инициализация с параметрами по умолчанию."""
        transport = ShapedUDPTransport()

        assert transport.local_port == 0
        assert transport.reliable_mode is False
        assert transport._shaper is not None  # gaming по умолчанию

    def test_initialization_with_shaping(self):
        """Инициализация с профилем шейпинга."""
        transport = ShapedUDPTransport(local_port=5000, traffic_profile="voice_call")

        assert transport._shaper is not None
        assert transport._shaper.profile.value == "voice_call"

    def test_initialization_with_obfuscation(self):
        """Инициализация с обфускацией."""
        transport = ShapedUDPTransport(obfuscation="xor", obfuscation_key="test-key")

        assert transport._transport is not None

    def test_initialization_no_shaping(self):
        """Инициализация без шейпинга."""
        transport = ShapedUDPTransport(traffic_profile="none")
        assert transport._shaper is None

    def test_prepare_packet_basic(self):
        """Подготовка пакета без обработки."""
        transport = ShapedUDPTransport(traffic_profile="none", obfuscation="none")

        data = b"test game data"
        packet_bytes = transport._prepare_packet(data)

        # Должен содержать заголовок + данные
        assert len(packet_bytes) > len(data)

        # Распаковка должна работать
        packet = transport._unpack_packet(packet_bytes)
        assert packet.payload == data

    def test_prepare_unpack_roundtrip_with_shaping(self):
        """Roundtrip с шейпингом."""
        transport = ShapedUDPTransport(traffic_profile="gaming", obfuscation="none")

        original = b"player position update"
        packet_bytes = transport._prepare_packet(original)
        restored = transport._unpack_packet(packet_bytes)

        assert restored.payload == original

    def test_prepare_unpack_roundtrip_with_obfuscation(self):
        """Roundtrip с обфускацией."""
        transport = ShapedUDPTransport(
            traffic_profile="none", obfuscation="xor", obfuscation_key="game-secret"
        )

        original = b"encrypted game state"
        packet_bytes = transport._prepare_packet(original)
        restored = transport._unpack_packet(packet_bytes)

        assert restored.payload == original

    def test_prepare_unpack_roundtrip_full(self):
        """Roundtrip с полной обработкой."""
        transport = ShapedUDPTransport(
            traffic_profile="voice_call", obfuscation="xor", obfuscation_key="voip-key"
        )

        original = b"voice frame data" * 10
        packet_bytes = transport._prepare_packet(original)
        restored = transport._unpack_packet(packet_bytes)

        assert restored.payload == original

    def test_sequence_numbers(self):
        """Проверка sequence numbers."""
        transport = ShapedUDPTransport(traffic_profile="none")

        seq1 = transport._next_sequence()
        seq2 = transport._next_sequence()
        seq3 = transport._next_sequence()

        assert seq2 == seq1 + 1
        assert seq3 == seq2 + 1

    def test_stats_initial(self):
        """Начальная статистика."""
        transport = ShapedUDPTransport()
        stats = transport.get_stats()

        assert stats["total_sent"] == 0
        assert stats["total_received"] == 0
        assert stats["peers_count"] == 0


@pytest.mark.asyncio
async def test_udp_transport_start_stop():
    """Тест запуска и остановки транспорта."""
    transport = ShapedUDPTransport(
        local_port=0, traffic_profile="gaming"  # Авто-выбор порта
    )

    try:
        await transport.start()
    except (PermissionError, OSError) as exc:
        pytest.skip(f"UDP socket unavailable in test environment: {exc}")

    assert transport._running is True
    assert transport._socket is not None
    assert transport.local_port > 0

    await transport.stop()

    assert transport._running is False
    assert transport._socket is None


@pytest.mark.asyncio
async def test_udp_loopback_communication():
    """Тест loopback коммуникации."""
    received_data = []

    transport = ShapedUDPTransport(
        local_port=0,
        traffic_profile="gaming",
        obfuscation="xor",
        obfuscation_key="loopback-test",
    )

    @transport.on_receive
    async def handler(data: bytes, address):
        received_data.append(data)

    try:
        await transport.start()
    except (PermissionError, OSError) as exc:
        pytest.skip(f"UDP socket unavailable in test environment: {exc}")
    local_addr = ("127.0.0.1", transport.local_port)

    # Отправляем сами себе
    await transport.send_to(b"hello loopback", local_addr)

    # Ждём получения
    await asyncio.sleep(0.1)

    await transport.stop()

    assert len(received_data) == 1
    assert received_data[0] == b"hello loopback"


class TestPacketType:
    """Тесты типов пакетов."""

    def test_all_types_have_unique_values(self):
        """Все типы имеют уникальные значения."""
        values = [pt.value for pt in PacketType]
        assert len(values) == len(set(values))

    def test_data_type_value(self):
        """DATA имеет значение 0x01."""
        assert PacketType.DATA.value == 0x01


class TestUDPHolePuncher:
    """Тесты NAT traversal."""

    def test_initialization(self):
        """Инициализация hole puncher."""
        puncher = UDPHolePuncher()
        assert puncher.stun_server == ("stun.l.google.com", 19302)

    def test_custom_stun_server(self):
        """Кастомный STUN сервер."""
        puncher = UDPHolePuncher(stun_server=("stun.example.com", 3478))
        assert puncher.stun_server == ("stun.example.com", 3478)
