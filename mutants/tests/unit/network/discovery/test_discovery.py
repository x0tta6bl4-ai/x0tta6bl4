"""
Тесты для Mesh Discovery.
"""
import pytest
import asyncio
import sys
import time

sys.path.insert(0, '/mnt/AC74CC2974CBF3DC')

from src.network.discovery.protocol import (
    MeshDiscovery,
    MulticastDiscovery,
    BootstrapDiscovery,
    KademliaNode,
    PeerInfo,
    DiscoveryMessage,
    MessageType
)


class TestPeerInfo:
    """Тесты PeerInfo."""
    
    def test_creation(self):
        """Создание PeerInfo."""
        peer = PeerInfo(
            node_id="node-123",
            addresses=[("192.168.1.100", 5000)],
            services=["mesh", "relay"]
        )
        
        assert peer.node_id == "node-123"
        assert len(peer.addresses) == 1
        assert "mesh" in peer.services
    
    def test_to_dict(self):
        """Сериализация в dict."""
        peer = PeerInfo(
            node_id="node-abc",
            addresses=[("10.0.0.1", 8000), ("10.0.0.2", 8000)],
            services=["mesh"]
        )
        
        d = peer.to_dict()
        
        assert d["node_id"] == "node-abc"
        assert len(d["addresses"]) == 2
    
    def test_from_dict(self):
        """Десериализация из dict."""
        data = {
            "node_id": "node-xyz",
            "addresses": [["127.0.0.1", 5000]],
            "services": ["exit"],
            "version": "2.0.0"
        }
        
        peer = PeerInfo.from_dict(data)
        
        assert peer.node_id == "node-xyz"
        assert peer.version == "2.0.0"
        assert ("127.0.0.1", 5000) in peer.addresses
    
    def test_roundtrip(self):
        """Полный цикл сериализации."""
        original = PeerInfo(
            node_id="test-node",
            addresses=[("1.2.3.4", 9999)],
            services=["mesh", "relay", "exit"],
            version="1.5.0"
        )
        
        restored = PeerInfo.from_dict(original.to_dict())
        
        assert restored.node_id == original.node_id
        assert restored.services == original.services


class TestDiscoveryMessage:
    """Тесты DiscoveryMessage."""
    
    def test_creation(self):
        """Создание сообщения."""
        msg = DiscoveryMessage(
            msg_type=MessageType.ANNOUNCE,
            sender_id="node-1",
            payload={"test": "data"}
        )
        
        assert msg.msg_type == MessageType.ANNOUNCE
        assert msg.sender_id == "node-1"
    
    def test_serialization(self):
        """Сериализация в bytes."""
        msg = DiscoveryMessage(
            msg_type=MessageType.QUERY,
            sender_id="sender",
            payload={"key": "value"}
        )
        
        data = msg.to_bytes()
        
        assert isinstance(data, bytes)
        assert b"sender" in data
    
    def test_deserialization(self):
        """Десериализация из bytes."""
        original = DiscoveryMessage(
            msg_type=MessageType.RESPONSE,
            sender_id="responder",
            payload={"peers": []},
            timestamp=1234567890
        )
        
        data = original.to_bytes()
        restored = DiscoveryMessage.from_bytes(data)
        
        assert restored.msg_type == original.msg_type
        assert restored.sender_id == original.sender_id
        assert restored.payload == original.payload
    
    def test_all_message_types(self):
        """Все типы сообщений."""
        for msg_type in MessageType:
            msg = DiscoveryMessage(
                msg_type=msg_type,
                sender_id="test",
                payload={}
            )
            
            data = msg.to_bytes()
            restored = DiscoveryMessage.from_bytes(data)
            
            assert restored.msg_type == msg_type


class TestKademliaNode:
    """Тесты Kademlia DHT."""
    
    def test_creation(self):
        """Создание узла."""
        node = KademliaNode(node_id="kademlia-node", port=5000)
        
        assert node.node_id == "kademlia-node"
        assert len(node.node_id_bytes) == 32  # SHA256
    
    def test_xor_distance(self):
        """XOR distance вычисление."""
        node = KademliaNode(node_id="node-a", port=5000)
        
        id1 = node._id_to_bytes("peer-1")
        id2 = node._id_to_bytes("peer-2")
        
        dist = node._xor_distance(id1, id2)
        
        assert dist > 0
        assert node._xor_distance(id1, id1) == 0
    
    def test_add_peer(self):
        """Добавление пира."""
        node = KademliaNode(node_id="main", port=5000)
        
        peer = PeerInfo(
            node_id="peer-1",
            addresses=[("10.0.0.1", 5000)]
        )
        
        node.add_peer(peer)
        
        # Проверяем что пир добавлен
        closest = node.find_closest("peer-1")
        assert any(p.node_id == "peer-1" for p in closest)
    
    def test_find_closest(self):
        """Поиск ближайших."""
        node = KademliaNode(node_id="center", port=5000)
        
        # Добавляем много пиров
        for i in range(30):
            peer = PeerInfo(
                node_id=f"peer-{i}",
                addresses=[(f"10.0.0.{i}", 5000)]
            )
            node.add_peer(peer)
        
        # Ищем ближайших к target
        closest = node.find_closest("target-node", count=5)
        
        assert len(closest) <= 5
        # Проверяем сортировку по distance
        for i in range(len(closest) - 1):
            assert closest[i].distance <= closest[i+1].distance
    
    def test_store_get(self):
        """DHT storage."""
        node = KademliaNode(node_id="storage", port=5000)
        
        node.store("key1", b"value1")
        node.store("key2", b"value2")
        
        assert node.get("key1") == b"value1"
        assert node.get("key2") == b"value2"
        assert node.get("unknown") is None


class TestMulticastDiscovery:
    """Тесты Multicast Discovery."""
    
    def test_initialization(self):
        """Инициализация."""
        discovery = MulticastDiscovery(
            node_id="test-node",
            service_port=5000,
            services=["mesh"]
        )
        
        assert discovery.node_id == "test-node"
        assert discovery.service_port == 5000
        assert "mesh" in discovery.services
    
    def test_get_local_ip(self):
        """Получение локального IP."""
        discovery = MulticastDiscovery(
            node_id="test",
            service_port=5000
        )
        
        ip = discovery._get_local_ip()
        
        # Должен быть валидный IP
        parts = ip.split(".")
        assert len(parts) == 4
    
    def test_peers_initially_empty(self):
        """Изначально нет пиров."""
        discovery = MulticastDiscovery(
            node_id="alone",
            service_port=5000
        )
        
        assert len(discovery.get_peers()) == 0
        assert discovery.get_peer("unknown") is None


class TestMeshDiscovery:
    """Тесты MeshDiscovery."""
    
    def test_initialization_minimal(self):
        """Минимальная инициализация."""
        discovery = MeshDiscovery(
            node_id="mesh-node",
            service_port=5000
        )
        
        assert discovery.node_id == "mesh-node"
        assert discovery._multicast is not None
        assert discovery._dht is not None
    
    def test_initialization_no_multicast(self):
        """Без multicast."""
        discovery = MeshDiscovery(
            node_id="no-mcast",
            service_port=5000,
            enable_multicast=False
        )
        
        assert discovery._multicast is None
    
    def test_initialization_with_bootstrap(self):
        """С bootstrap nodes."""
        discovery = MeshDiscovery(
            node_id="boot-node",
            service_port=5000,
            bootstrap_nodes=[
                ("bootstrap1.example.com", 7777),
                ("bootstrap2.example.com", 7777)
            ]
        )
        
        assert discovery._bootstrap is not None
        assert len(discovery._bootstrap.bootstrap_nodes) == 2
    
    def test_find_peers_for_service(self):
        """Поиск пиров по сервису."""
        discovery = MeshDiscovery(
            node_id="finder",
            service_port=5000,
            enable_multicast=False
        )
        
        # Добавляем пиров вручную
        discovery._peers["relay-1"] = PeerInfo(
            node_id="relay-1",
            addresses=[("10.0.0.1", 5000)],
            services=["mesh", "relay"]
        )
        discovery._peers["exit-1"] = PeerInfo(
            node_id="exit-1",
            addresses=[("10.0.0.2", 5000)],
            services=["mesh", "exit"]
        )
        discovery._peers["mesh-only"] = PeerInfo(
            node_id="mesh-only",
            addresses=[("10.0.0.3", 5000)],
            services=["mesh"]
        )
        
        relays = discovery.find_peers_for_service("relay")
        exits = discovery.find_peers_for_service("exit")
        mesh = discovery.find_peers_for_service("mesh")
        
        assert len(relays) == 1
        assert len(exits) == 1
        assert len(mesh) == 3
    
    def test_stats(self):
        """Статистика."""
        discovery = MeshDiscovery(
            node_id="stats-node",
            service_port=5000,
            enable_multicast=False
        )
        
        stats = discovery.get_stats()
        
        assert stats["node_id"] == "stats-node"
        assert stats["peers_count"] == 0
        assert "peers" in stats


@pytest.mark.asyncio
async def test_multicast_start_stop():
    """Тест запуска и остановки multicast."""
    discovery = MulticastDiscovery(
        node_id="lifecycle-test",
        service_port=5000
    )
    
    await discovery.start()
    
    assert discovery._running is True
    assert discovery._socket is not None
    
    await discovery.stop()
    
    assert discovery._running is False


@pytest.mark.asyncio
async def test_mesh_discovery_start_stop():
    """Тест запуска и остановки MeshDiscovery."""
    discovery = MeshDiscovery(
        node_id="mesh-lifecycle",
        service_port=5000,
        enable_multicast=False  # Без multicast для простоты
    )
    
    await discovery.start()
    await discovery.stop()
    
    # Не должно быть ошибок


@pytest.mark.asyncio
async def test_peer_discovery_callback():
    """Тест callback при обнаружении пира."""
    discovered_peers = []
    
    discovery = MeshDiscovery(
        node_id="callback-test",
        service_port=5000,
        enable_multicast=False
    )
    
    @discovery.on_peer_discovered
    async def on_found(peer):
        discovered_peers.append(peer)
    
    # Симулируем обнаружение
    test_peer = PeerInfo(
        node_id="new-peer",
        addresses=[("1.2.3.4", 5000)]
    )
    
    await discovery._handle_discovered(test_peer)
    
    assert len(discovered_peers) == 1
    assert discovered_peers[0].node_id == "new-peer"


class TestMessageType:
    """Тесты типов сообщений."""
    
    def test_all_types_unique(self):
        """Все типы уникальны."""
        values = [t.value for t in MessageType]
        assert len(values) == len(set(values))
    
    def test_announce_value(self):
        """ANNOUNCE = 0x01."""
        assert MessageType.ANNOUNCE.value == 0x01
