"""
E2E Integration Tests для Mesh Routing.
Тестирует multi-hop forwarding и route discovery.
"""
import pytest
import asyncio
import sys

sys.path.insert(0, '/mnt/AC74CC2974CBF3DC')

from src.network.mesh_node_complete import CompleteMeshNode, MeshConfig
from src.network.routing import MeshRouter


class TestMeshRouter:
    """Unit tests для MeshRouter."""
    
    def test_router_creation(self):
        """Создание router."""
        router = MeshRouter("test-node")
        assert router.node_id == "test-node"
        assert router.seq_num == 0
    
    def test_add_neighbor(self):
        """Добавление соседа."""
        router = MeshRouter("node-a")
        router.add_neighbor("node-b")
        
        route = router.get_route("node-b")
        assert route is not None
        assert route.hop_count == 1
        assert route.next_hop == "node-b"
    
    def test_remove_neighbor(self):
        """Удаление соседа."""
        router = MeshRouter("node-a")
        router.add_neighbor("node-b")
        router.remove_neighbor("node-b")
        
        route = router.get_route("node-b")
        assert route is None


@pytest.mark.asyncio
async def test_two_nodes_direct_communication():
    """Тест прямой связи между двумя узлами."""
    received = []
    
    # Создаём два узла
    node_a = CompleteMeshNode(MeshConfig(node_id="alice", port=6001, enable_multicast=False))
    node_b = CompleteMeshNode(MeshConfig(node_id="bob", port=6002, enable_multicast=False))
    
    @node_b.on_message
    async def on_message(source: str, payload: bytes):
        received.append((source, payload))
    
    try:
        await node_a.start()
        await node_b.start()
        
        # Вручную добавляем связь (без multicast)
        node_a._peer_addresses["bob"] = ("127.0.0.1", node_b._transport.local_port)
        node_a._router.add_neighbor("bob")
        
        node_b._peer_addresses["alice"] = ("127.0.0.1", node_a._transport.local_port)
        node_b._router.add_neighbor("alice")
        
        # Отправляем сообщение
        success = await node_a.send_message("bob", b"Hello Bob!")
        
        # Ждём доставки
        await asyncio.sleep(0.5)
        
        assert success
        assert len(received) == 1
        assert received[0][0] == "alice"
        assert received[0][1] == b"Hello Bob!"
        
    finally:
        await node_a.stop()
        await node_b.stop()


@pytest.mark.asyncio
async def test_three_nodes_multihop():
    """Тест multi-hop: A -> B -> C."""
    received_at_c = []
    
    node_a = CompleteMeshNode(MeshConfig(node_id="alice", port=6011, enable_multicast=False))
    node_b = CompleteMeshNode(MeshConfig(node_id="bob", port=6012, enable_multicast=False))
    node_c = CompleteMeshNode(MeshConfig(node_id="charlie", port=6013, enable_multicast=False))
    
    @node_c.on_message
    async def on_message(source: str, payload: bytes):
        received_at_c.append((source, payload))
    
    try:
        await node_a.start()
        await node_b.start()
        await node_c.start()
        
        # Топология: A <-> B <-> C (A не видит C напрямую)
        # A-B connection
        node_a._peer_addresses["bob"] = ("127.0.0.1", node_b._transport.local_port)
        node_a._router.add_neighbor("bob")
        node_b._peer_addresses["alice"] = ("127.0.0.1", node_a._transport.local_port)
        node_b._router.add_neighbor("alice")
        
        # B-C connection
        node_b._peer_addresses["charlie"] = ("127.0.0.1", node_c._transport.local_port)
        node_b._router.add_neighbor("charlie")
        node_c._peer_addresses["bob"] = ("127.0.0.1", node_b._transport.local_port)
        node_c._router.add_neighbor("bob")
        
        # A отправляет C (через B)
        success = await node_a.send_message("charlie", b"Hello Charlie via Bob!")
        
        await asyncio.sleep(1.0)
        
        # Проверяем доставку
        assert len(received_at_c) == 1
        assert received_at_c[0][0] == "alice"
        assert received_at_c[0][1] == b"Hello Charlie via Bob!"
        
        # Проверяем что маршрут был обнаружен
        routes_a = node_a.get_routes()
        assert "charlie" in routes_a
        
    finally:
        await node_a.stop()
        await node_b.stop()
        await node_c.stop()


@pytest.mark.asyncio
async def test_routing_stats():
    """Тест статистики маршрутизации."""
    node = CompleteMeshNode(MeshConfig(node_id="stats-test", port=6020, enable_multicast=False))
    
    try:
        await node.start()
        
        stats = node.get_stats()
        
        assert stats["node_id"] == "stats-test"
        assert stats["running"] == True
        assert "routing" in stats
        assert stats["routing"]["packets_sent"] == 0
        
    finally:
        await node.stop()


@pytest.mark.asyncio
async def test_broadcast():
    """Тест broadcast сообщений."""
    received_at_b = []
    received_at_c = []
    
    node_a = CompleteMeshNode(MeshConfig(node_id="alice", port=6030, enable_multicast=False))
    node_b = CompleteMeshNode(MeshConfig(node_id="bob", port=6031, enable_multicast=False))
    node_c = CompleteMeshNode(MeshConfig(node_id="charlie", port=6032, enable_multicast=False))
    
    @node_b.on_message
    async def on_b(source: str, payload: bytes):
        received_at_b.append((source, payload))
    
    @node_c.on_message
    async def on_c(source: str, payload: bytes):
        received_at_c.append((source, payload))
    
    try:
        await node_a.start()
        await node_b.start()
        await node_c.start()
        
        # A connected to both B and C
        node_a._peer_addresses["bob"] = ("127.0.0.1", node_b._transport.local_port)
        node_a._router.add_neighbor("bob")
        node_a._peer_addresses["charlie"] = ("127.0.0.1", node_c._transport.local_port)
        node_a._router.add_neighbor("charlie")
        
        node_b._peer_addresses["alice"] = ("127.0.0.1", node_a._transport.local_port)
        node_b._router.add_neighbor("alice")
        node_c._peer_addresses["alice"] = ("127.0.0.1", node_a._transport.local_port)
        node_c._router.add_neighbor("alice")
        
        # Broadcast
        sent = await node_a.broadcast(b"Hello everyone!")
        
        await asyncio.sleep(0.5)
        
        assert sent == 2
        assert len(received_at_b) == 1
        assert len(received_at_c) == 1
        assert received_at_b[0][1] == b"Hello everyone!"
        assert received_at_c[0][1] == b"Hello everyone!"
        
    finally:
        await node_a.stop()
        await node_b.stop()
        await node_c.stop()


class TestRoutingPacket:
    """Тесты сериализации пакетов."""
    
    def test_packet_serialization(self):
        """Сериализация и десериализация пакета."""
        from src.network.routing import RoutingPacket, PacketType
        
        original = RoutingPacket(
            packet_type=PacketType.DATA,
            source="alice",
            destination="bob",
            seq_num=42,
            hop_count=2,
            ttl=16,
            payload=b"Hello World!"
        )
        
        data = original.to_bytes()
        restored = RoutingPacket.from_bytes(data)
        
        assert restored.packet_type == original.packet_type
        assert restored.source == original.source
        assert restored.destination == original.destination
        assert restored.seq_num == original.seq_num
        assert restored.hop_count == original.hop_count
        assert restored.ttl == original.ttl
        assert restored.payload == original.payload
    
    def test_packet_id_uniqueness(self):
        """Уникальность packet_id."""
        from src.network.routing import RoutingPacket, PacketType
        
        p1 = RoutingPacket(PacketType.DATA, "a", "b", 1, 0, 16, b"test")
        p2 = RoutingPacket(PacketType.DATA, "a", "b", 1, 0, 16, b"test")
        
        # Разные ID даже для одинаковых пакетов
        assert p1.packet_id != p2.packet_id


if __name__ == "__main__":
    pytest.main([__file__, "-v"])
