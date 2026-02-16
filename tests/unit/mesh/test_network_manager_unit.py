"""Unit tests for MeshNetworkManager."""

from unittest.mock import AsyncMock, MagicMock, patch

import pytest

from src.mesh.network_manager import MeshNetworkManager


class TestMeshNetworkManagerInit:
    def test_default_init(self):
        mgr = MeshNetworkManager()
        assert mgr.node_id == "local"
        assert mgr._router is None
        assert mgr._route_preference == "balanced"

    def test_custom_node_id(self):
        mgr = MeshNetworkManager(node_id="node-a")
        assert mgr.node_id == "node-a"


class TestGetStatistics:
    @pytest.mark.asyncio
    async def test_returns_expected_keys(self):
        mgr = MeshNetworkManager(node_id="test")
        stats = await mgr.get_statistics()
        assert "active_peers" in stats
        assert "avg_latency_ms" in stats
        assert "packet_loss_percent" in stats
        assert "mttr_minutes" in stats

    @pytest.mark.asyncio
    async def test_with_mocked_router(self):
        mgr = MeshNetworkManager(node_id="test")
        mock_router = MagicMock()
        mock_router.get_mape_k_metrics = AsyncMock(
            return_value={
                "packet_drop_rate": 0.05,
                "total_routes_known": 3,
                "avg_route_hop_count": 2.0,
            }
        )
        mgr._router = mock_router

        stats = await mgr.get_statistics()
        assert stats["packet_loss_percent"] == pytest.approx(5.0)
        assert stats["active_peers"] >= 3
        assert stats["avg_latency_ms"] == pytest.approx(30.0)

    @pytest.mark.asyncio
    async def test_router_failure_graceful(self):
        mgr = MeshNetworkManager(node_id="test")
        mock_router = MagicMock()
        mock_router.get_mape_k_metrics = AsyncMock(side_effect=RuntimeError("down"))
        mgr._router = mock_router

        stats = await mgr.get_statistics()
        # Router metrics default to 0, but Yggdrasil may still contribute peers
        assert stats["packet_loss_percent"] == 0.0
        assert isinstance(stats["active_peers"], (int, float))


class TestSetRoutePreference:
    @pytest.mark.asyncio
    async def test_valid_preferences(self):
        mgr = MeshNetworkManager()
        for pref in ("low_latency", "reliability", "balanced"):
            assert await mgr.set_route_preference(pref) is True
            assert mgr._route_preference == pref

    @pytest.mark.asyncio
    async def test_invalid_preference(self):
        mgr = MeshNetworkManager()
        assert await mgr.set_route_preference("invalid") is False
        assert mgr._route_preference == "balanced"


class TestAggressiveHealing:
    @pytest.mark.asyncio
    async def test_no_router_returns_zero(self):
        mgr = MeshNetworkManager()
        # _get_router will fail to import, returns None
        healed = await mgr.trigger_aggressive_healing()
        assert healed == 0

    @pytest.mark.asyncio
    async def test_healing_logs_entry(self):
        mgr = MeshNetworkManager()
        mock_router = MagicMock()
        mock_router.get_routes.return_value = {}
        mock_router.ROUTE_TIMEOUT = 60.0
        mgr._router = mock_router

        await mgr.trigger_aggressive_healing()
        assert len(mgr._healing_log) == 1
        assert "healed" in mgr._healing_log[0]


class TestPreemptiveChecks:
    @pytest.mark.asyncio
    async def test_no_router_does_nothing(self):
        mgr = MeshNetworkManager()
        await mgr.trigger_preemptive_checks()  # should not raise


class TestComputeMTTR:
    def test_empty_log(self):
        mgr = MeshNetworkManager()
        assert mgr._compute_mttr() == 0.0

    def test_with_entries(self):
        mgr = MeshNetworkManager()
        mgr._healing_log = [
            {"timestamp": "t1", "healed": 2, "duration_minutes": 1.0},
            {"timestamp": "t2", "healed": 1, "duration_minutes": 3.0},
        ]
        assert mgr._compute_mttr() == pytest.approx(2.0)

    def test_ignores_zero_healed(self):
        mgr = MeshNetworkManager()
        mgr._healing_log = [
            {"timestamp": "t1", "healed": 0, "duration_minutes": 5.0},
            {"timestamp": "t2", "healed": 1, "duration_minutes": 2.0},
        ]
        assert mgr._compute_mttr() == pytest.approx(2.0)
