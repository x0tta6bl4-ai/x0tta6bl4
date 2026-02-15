"""
Tests for Mesh Router module.
"""

import asyncio
import time
from unittest.mock import AsyncMock, MagicMock, Mock, patch

import pytest


class TestMeshPeer:
    """Tests for MeshPeer dataclass."""

    def test_peer_initialization(self):
        """Test MeshPeer initialization."""
        from src.network.mesh_router import MeshPeer

        peer = MeshPeer(
            node_id="test-node-1",
            host="192.168.1.100",
            port=10809,
            latency=50.0,
            is_exit=True,
        )

        assert peer.node_id == "test-node-1"
        assert peer.host == "192.168.1.100"
        assert peer.port == 10809
        assert peer.latency == 50.0
        assert peer.is_exit is True
        assert peer.capacity == 100

    def test_peer_address_property(self):
        """Test address property returns host:port."""
        from src.network.mesh_router import MeshPeer

        peer = MeshPeer(node_id="test-node", host="10.0.0.1", port=8080)

        assert peer.address == "10.0.0.1:8080"

    def test_peer_is_alive_fresh(self):
        """Test is_alive returns True for recently seen peer."""
        from src.network.mesh_router import MeshPeer

        peer = MeshPeer(
            node_id="test-node", host="10.0.0.1", port=8080, last_seen=time.time()
        )

        assert peer.is_alive(timeout=60.0) is True

    def test_peer_is_alive_stale(self):
        """Test is_alive returns False for stale peer."""
        from src.network.mesh_router import MeshPeer

        peer = MeshPeer(
            node_id="test-node",
            host="10.0.0.1",
            port=8080,
            last_seen=time.time() - 120,  # 2 minutes ago
        )

        assert peer.is_alive(timeout=60.0) is False

    def test_peer_is_alive_never_seen(self):
        """Test is_alive for peer never seen."""
        from src.network.mesh_router import MeshPeer

        peer = MeshPeer(node_id="test-node", host="10.0.0.1", port=8080, last_seen=0.0)

        assert peer.is_alive(timeout=60.0) is False

    def test_peer_default_values(self):
        """Test default values for MeshPeer."""
        from src.network.mesh_router import MeshPeer

        peer = MeshPeer(node_id="test-node", host="10.0.0.1", port=8080)

        assert peer.latency == 0.0
        assert peer.last_seen == 0.0
        assert peer.is_exit is True
        assert peer.capacity == 100


class TestMeshRouter:
    """Tests for MeshRouter class."""

    def test_router_initialization(self):
        """Test MeshRouter initialization."""
        from src.network.mesh_router import MeshRouter

        with patch.dict("os.environ", {"BOOTSTRAP_NODES": ""}):
            router = MeshRouter(node_id="my-node", local_port=10809)

        assert router.node_id == "my-node"
        assert router.local_port == 10809
        assert router._running is False

    def test_router_with_bootstrap_nodes(self):
        """Test MeshRouter loads bootstrap nodes from environment."""
        from src.network.mesh_router import MeshRouter

        bootstrap = "192.168.1.1:10809:node-1,192.168.1.2:10810:node-2"
        with patch.dict("os.environ", {"BOOTSTRAP_NODES": bootstrap}):
            router = MeshRouter(node_id="my-node")

        assert len(router.peers) == 2
        assert "node-1" in router.peers
        assert "node-2" in router.peers
        assert router.peers["node-1"].host == "192.168.1.1"
        assert router.peers["node-1"].port == 10809
        assert router.peers["node-2"].port == 10810

    def test_router_does_not_add_self(self):
        """Test router doesn't add itself as a peer."""
        from src.network.mesh_router import MeshRouter

        bootstrap = "192.168.1.1:10809:my-node"  # Same as router node_id
        with patch.dict("os.environ", {"BOOTSTRAP_NODES": bootstrap}):
            router = MeshRouter(node_id="my-node")

        assert "my-node" not in router.peers

    def test_get_route_no_peers(self):
        """Test get_route with no alive peers."""
        from src.network.mesh_router import MeshRouter

        with patch.dict("os.environ", {"BOOTSTRAP_NODES": ""}):
            router = MeshRouter(node_id="my-node")

        route = router.get_route("example.com:443")
        assert route == []

    def test_get_route_with_alive_peers(self):
        """Test get_route with alive peers."""
        from src.network.mesh_router import MeshPeer, MeshRouter

        with patch.dict("os.environ", {"BOOTSTRAP_NODES": ""}):
            router = MeshRouter(node_id="my-node")

        # Add some alive peers
        router.peers["node-1"] = MeshPeer(
            node_id="node-1",
            host="192.168.1.1",
            port=10809,
            latency=50.0,
            last_seen=time.time(),
            is_exit=True,
        )
        router.peers["node-2"] = MeshPeer(
            node_id="node-2",
            host="192.168.1.2",
            port=10809,
            latency=30.0,
            last_seen=time.time(),
            is_exit=True,
        )

        route = router.get_route("example.com:443", hops=1)

        # Should have at least one exit node
        assert len(route) >= 1
        assert all(isinstance(p, MeshPeer) for p in route)

    def test_get_route_destination_is_peer(self):
        """Test get_route returns empty when destination is a peer."""
        from src.network.mesh_router import MeshPeer, MeshRouter

        with patch.dict("os.environ", {"BOOTSTRAP_NODES": ""}):
            router = MeshRouter(node_id="my-node")

        # Add peer with specific host
        router.peers["node-1"] = MeshPeer(
            node_id="node-1",
            host="192.168.1.1",
            port=10809,
            latency=50.0,
            last_seen=time.time(),
            is_exit=True,
        )

        # Try to route to the peer's host
        route = router.get_route("192.168.1.1:443")
        assert route == []

    def test_get_route_sorts_by_latency(self):
        """Test get_route prefers lower latency peers."""
        from src.network.mesh_router import MeshPeer, MeshRouter

        with patch.dict("os.environ", {"BOOTSTRAP_NODES": ""}):
            router = MeshRouter(node_id="my-node")

        # Add peers with different latencies
        router.peers["slow-node"] = MeshPeer(
            node_id="slow-node",
            host="192.168.1.1",
            port=10809,
            latency=200.0,
            last_seen=time.time(),
            is_exit=True,
        )
        router.peers["fast-node"] = MeshPeer(
            node_id="fast-node",
            host="192.168.1.2",
            port=10809,
            latency=20.0,
            last_seen=time.time(),
            is_exit=True,
        )

        route = router.get_route("example.com:443", hops=1)

        # Fast node should be the exit (last in route)
        assert route[-1].node_id == "fast-node"

    def test_get_route_filters_dead_peers(self):
        """Test get_route excludes stale peers."""
        from src.network.mesh_router import MeshPeer, MeshRouter

        with patch.dict("os.environ", {"BOOTSTRAP_NODES": ""}):
            router = MeshRouter(node_id="my-node")

        # Add alive and dead peers
        router.peers["alive-node"] = MeshPeer(
            node_id="alive-node",
            host="192.168.1.1",
            port=10809,
            latency=50.0,
            last_seen=time.time(),
            is_exit=True,
        )
        router.peers["dead-node"] = MeshPeer(
            node_id="dead-node",
            host="192.168.1.2",
            port=10809,
            latency=30.0,
            last_seen=time.time() - 120,  # Dead
            is_exit=True,
        )

        route = router.get_route("example.com:443", hops=1)

        # Dead node should not be in route
        for peer in route:
            assert peer.node_id != "dead-node"

    def test_get_route_respects_hop_count(self):
        """Test get_route respects maximum hops."""
        from src.network.mesh_router import MeshPeer, MeshRouter

        with patch.dict("os.environ", {"BOOTSTRAP_NODES": ""}):
            router = MeshRouter(node_id="my-node")

        # Add many peers
        for i in range(5):
            router.peers[f"node-{i}"] = MeshPeer(
                node_id=f"node-{i}",
                host=f"192.168.1.{i+1}",
                port=10809,
                latency=50.0 + i * 10,
                last_seen=time.time(),
                is_exit=True,
            )

        route = router.get_route("example.com:443", hops=2)

        # Route should not exceed requested hops
        assert len(route) <= 2

    @pytest.mark.asyncio
    async def test_router_start_stop(self):
        """Test router start and stop."""
        from src.network.mesh_router import MeshRouter

        with patch.dict("os.environ", {"BOOTSTRAP_NODES": ""}):
            router = MeshRouter(node_id="my-node")

        # Mock health check and discovery loops to exit quickly
        with patch.object(router, "_health_check_loop", new_callable=AsyncMock):
            with patch.object(router, "_peer_discovery_loop", new_callable=AsyncMock):
                await router.start()
                assert router._running is True

                await router.stop()
                assert router._running is False


class TestBootstrapNodeParsing:
    """Tests for bootstrap node parsing."""

    def test_parse_simple_bootstrap(self):
        """Test parsing simple bootstrap node format."""
        from src.network.mesh_router import MeshRouter

        bootstrap = "10.0.0.1:8080:node-a"
        with patch.dict("os.environ", {"BOOTSTRAP_NODES": bootstrap}):
            router = MeshRouter(node_id="my-node")

        assert "node-a" in router.peers
        assert router.peers["node-a"].host == "10.0.0.1"
        assert router.peers["node-a"].port == 8080

    def test_parse_multiple_bootstrap(self):
        """Test parsing multiple bootstrap nodes."""
        from src.network.mesh_router import MeshRouter

        bootstrap = "10.0.0.1:8080:node-a,10.0.0.2:8081:node-b,10.0.0.3:8082:node-c"
        with patch.dict("os.environ", {"BOOTSTRAP_NODES": bootstrap}):
            router = MeshRouter(node_id="my-node")

        assert len(router.peers) == 3
        assert "node-a" in router.peers
        assert "node-b" in router.peers
        assert "node-c" in router.peers

    def test_parse_bootstrap_with_whitespace(self):
        """Test parsing bootstrap with extra whitespace."""
        from src.network.mesh_router import MeshRouter

        bootstrap = "  10.0.0.1:8080:node-a  ,  10.0.0.2:8081:node-b  "
        with patch.dict("os.environ", {"BOOTSTRAP_NODES": bootstrap}):
            router = MeshRouter(node_id="my-node")

        assert len(router.peers) == 2

    def test_parse_bootstrap_auto_node_id(self):
        """Test auto-generated node ID when not provided."""
        from src.network.mesh_router import MeshRouter

        # Only host:port, no node_id
        bootstrap = "10.0.0.1:8080"
        with patch.dict("os.environ", {"BOOTSTRAP_NODES": bootstrap}):
            router = MeshRouter(node_id="my-node")

        # Should have auto-generated node ID
        assert len(router.peers) == 1
        peer = list(router.peers.values())[0]
        assert peer.host == "10.0.0.1"
        assert peer.port == 8080

    def test_empty_bootstrap_in_production(self):
        """Test empty bootstrap nodes in production."""
        from src.network.mesh_router import MeshRouter

        with patch.dict(
            "os.environ", {"BOOTSTRAP_NODES": "", "ENVIRONMENT": "production"}
        ):
            router = MeshRouter(node_id="my-node")

        assert len(router.peers) == 0


class TestRouteCaching:
    """Tests for route caching functionality."""

    def test_routes_cache_initialized(self):
        """Test routes cache is initialized."""
        from src.network.mesh_router import MeshRouter

        with patch.dict("os.environ", {"BOOTSTRAP_NODES": ""}):
            router = MeshRouter(node_id="my-node")

        assert router.routes_cache == {}


class TestPeerDiscovery:
    """Tests for peer discovery functionality."""

    @pytest.mark.asyncio
    async def test_get_peers_from_dead_peer(self):
        """Test _get_peers_from returns empty for dead peer."""
        from src.network.mesh_router import MeshPeer, MeshRouter

        with patch.dict("os.environ", {"BOOTSTRAP_NODES": ""}):
            router = MeshRouter(node_id="my-node")

        dead_peer = MeshPeer(
            node_id="dead-node",
            host="192.168.1.1",
            port=10809,
            last_seen=0.0,  # Never seen
        )

        result = await router._get_peers_from(dead_peer)
        assert result == []

    @pytest.mark.asyncio
    async def test_ping_peer_unreachable(self):
        """Test _ping_peer returns -1 for unreachable peer."""
        from src.network.mesh_router import MeshPeer, MeshRouter

        with patch.dict("os.environ", {"BOOTSTRAP_NODES": ""}):
            router = MeshRouter(node_id="my-node")

        peer = MeshPeer(
            node_id="unreachable",
            host="192.0.2.1",  # TEST-NET-1, should be unreachable
            port=99999,
        )

        latency = await router._ping_peer(peer)
        assert latency == -1
