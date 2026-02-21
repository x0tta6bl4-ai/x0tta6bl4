import pytest
from unittest.mock import MagicMock, AsyncMock, patch
import sys
from src.mesh.network_manager import MeshNetworkManager

class TestMeshNetworkManager:
    @pytest.fixture
    def manager(self):
        return MeshNetworkManager(node_id="test-node")

    def test_init(self, manager):
        assert manager.node_id == "test-node"
        assert manager._router is None

    def test_get_router_lazy_init(self, manager):
        # Mock the module import
        with patch.dict(sys.modules, {"src.network.routing.mesh_router": MagicMock()}):
            with patch("src.network.routing.mesh_router.MeshRouter") as MockRouter:
                router = manager._get_router()
                assert router is not None
                assert manager._router is not None
                MockRouter.assert_called_once_with("test-node")

    @pytest.mark.asyncio
    async def test_get_statistics(self, manager):
        # Mock router and yggdrasil
        mock_router = AsyncMock()
        mock_router.get_mape_k_metrics.return_value = {
            "packet_drop_rate": 0.05,
            "total_routes_known": 10,
            "avg_route_hop_count": 3
        }
        manager._router = mock_router
        
        with patch("src.network.yggdrasil_client.get_yggdrasil_peers") as mock_ygg:
            mock_ygg.return_value = {"count": 12}
            
            stats = await manager.get_statistics()
            
            assert stats["packet_loss_percent"] == 5.0
            assert stats["active_peers"] == 12 # max(10, 12)
            assert stats["avg_latency_ms"] == 45.0 # 3 * 15.0

    @pytest.mark.asyncio
    async def test_set_route_preference(self, manager):
        assert await manager.set_route_preference("low_latency") is True
        assert manager._route_preference == "low_latency"
        
        assert await manager.set_route_preference("invalid") is False
        assert manager._route_preference == "low_latency" # Unchanged

    @pytest.mark.asyncio
    async def test_trigger_aggressive_healing(self, manager):
        mock_router = MagicMock()
        mock_route = MagicMock()
        mock_route.age = 1000
        mock_router.ROUTE_TIMEOUT = 100
        mock_router.get_routes.return_value = {"dest1": [mock_route]}
        mock_router._discover_route = AsyncMock()
        
        manager._router = mock_router
        
        healed = await manager.trigger_aggressive_healing()
        
        assert healed == 1
        mock_router._discover_route.assert_called_once_with("dest1")
        assert len(manager._healing_log) == 1

    @pytest.mark.asyncio
    async def test_trigger_preemptive_checks(self, manager):
        mock_router = MagicMock()
        mock_route = MagicMock()
        mock_route.age = 60 # > 100 * 0.5
        mock_router.ROUTE_TIMEOUT = 100
        mock_router.get_routes.return_value = {"dest1": [mock_route]}
        mock_router._discover_route = AsyncMock()
        
        manager._router = mock_router
        
        await manager.trigger_preemptive_checks()
        
        mock_router._discover_route.assert_called_once_with("dest1")

    def test_compute_mttr(self, manager):
        assert manager._compute_mttr() == 0.0
        
        manager._healing_log = [
            {"healed": 1, "duration_minutes": 2.0},
            {"healed": 0, "duration_minutes": 1.0}, # Should be ignored
            {"healed": 2, "duration_minutes": 4.0}
        ]
        
        # (2.0 + 4.0) / 2 = 3.0
        assert manager._compute_mttr() == 3.0
