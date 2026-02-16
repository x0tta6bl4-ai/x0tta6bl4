"""
Unit tests for Recovery Actions.

Tests production-ready recovery actions.
"""

import asyncio
from unittest.mock import AsyncMock, Mock, patch

import pytest

try:
    from src.self_healing.recovery_actions import RecoveryActionExecutor

    RECOVERY_ACTIONS_AVAILABLE = True
except ImportError:
    RECOVERY_ACTIONS_AVAILABLE = False
    RecoveryActionExecutor = None  # type: ignore


@pytest.mark.skipif(
    not RECOVERY_ACTIONS_AVAILABLE, reason="Recovery actions not available"
)
class TestRecoveryActionExecutor:
    """Unit tests for RecoveryActionExecutor"""

    @pytest.fixture
    def executor(self):
        """Create Recovery Action Executor"""
        return RecoveryActionExecutor(node_id="test-node")

    def test_executor_initialization(self, executor):
        """Test executor initialization"""
        assert executor.node_id == "test-node"

    @pytest.mark.asyncio
    async def test_restart_service(self, executor):
        """Test service restart"""
        with patch("asyncio.create_subprocess_shell") as mock_subprocess:
            mock_process = AsyncMock()
            mock_process.communicate = AsyncMock(return_value=(b"restarted", b""))
            mock_process.returncode = 0
            mock_subprocess.return_value = mock_process

            result = await executor.restart_service("test-service", "default")

            assert result is True

    @pytest.mark.asyncio
    async def test_switch_route(self, executor):
        """Test route switching"""
        result = await executor.switch_route("old-route", "new-route")

        assert result is True

    @pytest.mark.asyncio
    async def test_clear_cache(self, executor):
        """Test cache clearing"""
        result = await executor.clear_cache("test-service", "all")

        assert result is True

    @pytest.mark.asyncio
    async def test_scale_up(self, executor):
        """Test scaling up"""
        with patch("asyncio.create_subprocess_shell") as mock_subprocess:
            mock_process = AsyncMock()
            mock_process.communicate = AsyncMock(return_value=(b"scaled", b""))
            mock_process.returncode = 0
            mock_subprocess.return_value = mock_process

            result = await executor.scale_up(
                "test-deployment", replicas=5, namespace="default"
            )

            assert result is True

    @pytest.mark.asyncio
    async def test_failover(self, executor):
        """Test failover"""
        result = await executor.failover(
            "test-service", "primary-region", "fallback-region"
        )

        assert result is True

    @pytest.mark.asyncio
    async def test_quarantine_node(self, executor):
        """Test node quarantine"""
        result = await executor.quarantine_node("problematic-node")

        assert result is True

    @pytest.mark.asyncio
    async def test_execute_action_dynamic(self, executor):
        """Test dynamic action execution"""
        with patch("asyncio.create_subprocess_shell"):
            result = await executor.execute_action(
                "Restart service", service_name="test-service", namespace="default"
            )

            assert result is True

    @pytest.mark.asyncio
    async def test_execute_action_unknown(self, executor):
        """Test unknown action execution"""
        result = await executor.execute_action("Unknown action")

        assert result is False
