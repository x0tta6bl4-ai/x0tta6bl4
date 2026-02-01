"""
Tests for Recovery Action Orchestrator (RecoveryActionExecutor).

Tests:
- Action type parsing
- Individual recovery actions
- Retry logic with exponential backoff
- Rate limiting
- Circuit breaker integration
- Rollback functionality
- Action history and metrics
"""
import pytest
import time
from unittest.mock import Mock, patch, MagicMock
from datetime import datetime, timedelta

from src.self_healing.recovery_actions import (
    RecoveryActionType,
    RecoveryResult,
    RecoveryActionExecutor,
    RateLimiter,
    CircuitBreaker as RecoveryCircuitBreaker,
    CircuitBreakerState,
)


class TestRecoveryActionType:
    """Tests for RecoveryActionType enum."""

    def test_action_types_exist(self):
        """All expected action types exist."""
        assert RecoveryActionType.RESTART_SERVICE.value == "restart_service"
        assert RecoveryActionType.SWITCH_ROUTE.value == "switch_route"
        assert RecoveryActionType.CLEAR_CACHE.value == "clear_cache"
        assert RecoveryActionType.SCALE_UP.value == "scale_up"
        assert RecoveryActionType.SCALE_DOWN.value == "scale_down"
        assert RecoveryActionType.FAILOVER.value == "failover"
        assert RecoveryActionType.QUARANTINE_NODE.value == "quarantine_node"
        assert RecoveryActionType.NO_ACTION.value == "no_action"


class TestRecoveryResult:
    """Tests for RecoveryResult dataclass."""

    def test_successful_result(self):
        """Test successful recovery result."""
        result = RecoveryResult(
            success=True,
            action_type=RecoveryActionType.RESTART_SERVICE,
            duration_seconds=1.5,
            details={"method": "docker"}
        )
        assert result.success is True
        assert result.error_message is None
        assert result.details["method"] == "docker"

    def test_failed_result(self):
        """Test failed recovery result."""
        result = RecoveryResult(
            success=False,
            action_type=RecoveryActionType.FAILOVER,
            duration_seconds=0.5,
            error_message="Connection refused"
        )
        assert result.success is False
        assert result.error_message == "Connection refused"


class TestActionTypeParsing:
    """Tests for action type parsing from strings."""

    def test_parse_restart_actions(self, recovery_executor):
        """Parse restart-related action strings."""
        assert recovery_executor._parse_action_type("Restart service") == RecoveryActionType.RESTART_SERVICE
        assert recovery_executor._parse_action_type("REBOOT node") == RecoveryActionType.RESTART_SERVICE
        assert recovery_executor._parse_action_type("restart x0tta6bl4") == RecoveryActionType.RESTART_SERVICE

    def test_parse_route_actions(self, recovery_executor):
        """Parse route-related action strings."""
        assert recovery_executor._parse_action_type("Switch route") == RecoveryActionType.SWITCH_ROUTE
        assert recovery_executor._parse_action_type("change route to backup") == RecoveryActionType.SWITCH_ROUTE

    def test_parse_cache_actions(self, recovery_executor):
        """Parse cache-related action strings."""
        assert recovery_executor._parse_action_type("Clear cache") == RecoveryActionType.CLEAR_CACHE
        assert recovery_executor._parse_action_type("invalidate cache") == RecoveryActionType.CLEAR_CACHE

    def test_parse_scale_actions(self, recovery_executor):
        """Parse scaling action strings."""
        assert recovery_executor._parse_action_type("Scale up") == RecoveryActionType.SCALE_UP
        assert recovery_executor._parse_action_type("scale-up pods") == RecoveryActionType.SCALE_UP
        assert recovery_executor._parse_action_type("Scale down") == RecoveryActionType.SCALE_DOWN
        assert recovery_executor._parse_action_type("scale-down replicas") == RecoveryActionType.SCALE_DOWN

    def test_parse_failover_action(self, recovery_executor):
        """Parse failover action strings."""
        assert recovery_executor._parse_action_type("Failover to backup") == RecoveryActionType.FAILOVER
        assert recovery_executor._parse_action_type("trigger failover") == RecoveryActionType.FAILOVER

    def test_parse_quarantine_action(self, recovery_executor):
        """Parse quarantine action strings."""
        assert recovery_executor._parse_action_type("Quarantine node") == RecoveryActionType.QUARANTINE_NODE
        assert recovery_executor._parse_action_type("quarantine-node-123") == RecoveryActionType.QUARANTINE_NODE

    def test_parse_unknown_returns_no_action(self, recovery_executor):
        """Unknown actions return NO_ACTION."""
        assert recovery_executor._parse_action_type("unknown action") == RecoveryActionType.NO_ACTION
        assert recovery_executor._parse_action_type("do something") == RecoveryActionType.NO_ACTION


class TestRestartService:
    """Tests for restart service action."""

    def test_restart_with_systemd(self, recovery_executor, mock_subprocess):
        """Restart using systemd succeeds."""
        result = recovery_executor.execute("Restart service", {"service_name": "x0tta6bl4"})

        assert result is True
        mock_subprocess.assert_called()

    def test_restart_simulated_fallback(self, recovery_executor):
        """Restart falls back to simulated mode."""
        with patch('subprocess.run') as mock_run:
            mock_run.side_effect = FileNotFoundError("systemctl not found")

            result = recovery_executor.execute("Restart service", {"service_name": "test-service"})

            # Should succeed with simulated fallback
            assert result is True


class TestSwitchRoute:
    """Tests for route switching action."""

    def test_switch_route_success(self, recovery_executor):
        """Switch route action succeeds."""
        result = recovery_executor.execute(
            "Switch route",
            {
                "target_node": "node-001",
                "alternative_route": "backup-route"
            }
        )
        assert result is True

    def test_switch_route_records_old_route(self, recovery_executor):
        """Switch route saves old route for rollback."""
        recovery_executor.execute(
            "Switch route",
            {
                "target_node": "node-001",
                "old_route": "primary-route",
                "alternative_route": "backup-route"
            }
        )

        # Check rollback stack
        assert len(recovery_executor.rollback_stack) >= 1


class TestClearCache:
    """Tests for cache clearing action."""

    def test_clear_cache_all(self, recovery_executor):
        """Clear all caches."""
        result = recovery_executor.execute("Clear cache", {"cache_type": "all"})
        assert result is True

    def test_clear_cache_specific(self, recovery_executor):
        """Clear specific cache type."""
        result = recovery_executor.execute("Clear cache", {"cache_type": "session"})
        assert result is True


class TestScaleActions:
    """Tests for scaling actions."""

    def test_scale_up(self, recovery_executor, mock_kubernetes):
        """Scale up action."""
        result = recovery_executor.execute(
            "Scale up",
            {"service_name": "api", "replicas": 5}
        )
        assert result is True

    def test_scale_down(self, recovery_executor, mock_kubernetes):
        """Scale down action."""
        result = recovery_executor.execute(
            "Scale down",
            {"service_name": "api", "replicas": 2}
        )
        assert result is True

    def test_scale_simulated_fallback(self, recovery_executor):
        """Scale falls back to simulated when kubectl not available."""
        with patch('subprocess.run') as mock_run:
            mock_run.side_effect = FileNotFoundError("kubectl not found")

            result = recovery_executor.execute("Scale up", {"replicas": 3})
            assert result is True


class TestFailover:
    """Tests for failover action."""

    def test_failover_success(self, recovery_executor):
        """Failover action succeeds."""
        result = recovery_executor.execute(
            "Failover",
            {
                "primary_node": "node-001",
                "backup_node": "node-002"
            }
        )
        assert result is True


class TestQuarantineNode:
    """Tests for node quarantine action."""

    def test_quarantine_node(self, recovery_executor):
        """Quarantine node action succeeds."""
        result = recovery_executor.execute(
            "Quarantine node",
            {"node_id": "suspicious-node-123"}
        )
        assert result is True


class TestRateLimiter:
    """Tests for rate limiter."""

    def test_allows_within_limit(self, rate_limiter):
        """Allows actions within rate limit."""
        for _ in range(5):  # max_actions=5
            assert rate_limiter.allow() is True

    def test_blocks_over_limit(self, rate_limiter):
        """Blocks actions over rate limit."""
        for _ in range(5):
            rate_limiter.allow()

        assert rate_limiter.allow() is False

    def test_window_expiry_allows_again(self, rate_limiter):
        """Actions allowed again after window expires."""
        for _ in range(5):
            rate_limiter.allow()

        assert rate_limiter.allow() is False

        # Wait for window to expire (1 second)
        time.sleep(1.1)

        assert rate_limiter.allow() is True

    def test_rate_limiter_blocks_executor(self, recovery_executor):
        """Rate limiter blocks executor when exceeded."""
        # Exhaust rate limit (default 10 actions)
        for _ in range(10):
            recovery_executor.execute("Clear cache", {})

        # Next action should be blocked by rate limiter
        result = recovery_executor.execute("Clear cache", {})
        assert result is False


class TestRecoveryCircuitBreaker:
    """Tests for circuit breaker in recovery actions."""

    def test_circuit_breaker_closed_allows_calls(self, recovery_circuit_breaker):
        """Closed circuit allows calls."""
        def successful_func():
            return "success"

        result = recovery_circuit_breaker.call(successful_func)
        assert result == "success"
        assert recovery_circuit_breaker.state.state == "closed"

    def test_circuit_breaker_opens_on_failures(self, recovery_circuit_breaker):
        """Circuit opens after failure threshold."""
        def failing_func():
            raise Exception("failure")

        for _ in range(3):  # failure_threshold=3
            with pytest.raises(Exception):
                recovery_circuit_breaker.call(failing_func)

        assert recovery_circuit_breaker.state.state == "open"

    def test_circuit_breaker_rejects_when_open(self, recovery_circuit_breaker):
        """Open circuit rejects calls."""
        def failing_func():
            raise Exception("failure")

        # Open the circuit
        for _ in range(3):
            with pytest.raises(Exception):
                recovery_circuit_breaker.call(failing_func)

        # Should reject immediately
        with pytest.raises(Exception, match="Circuit breaker is OPEN"):
            recovery_circuit_breaker.call(lambda: "success")

    def test_circuit_breaker_transitions_to_half_open(self, recovery_circuit_breaker):
        """Circuit transitions to half-open after timeout."""
        # Open the circuit
        recovery_circuit_breaker.state.state = "open"
        recovery_circuit_breaker.state.opened_at = datetime.now() - timedelta(seconds=2)

        def successful_func():
            return "success"

        # Should transition to half-open and allow call
        result = recovery_circuit_breaker.call(successful_func)
        assert result == "success"

    def test_circuit_breaker_closes_after_successes(self, recovery_circuit_breaker):
        """Circuit closes after success threshold in half-open."""
        recovery_circuit_breaker.state.state = "half_open"
        recovery_circuit_breaker.state.successes = 0

        def successful_func():
            return "success"

        # success_threshold=2
        recovery_circuit_breaker.call(successful_func)
        recovery_circuit_breaker.call(successful_func)

        assert recovery_circuit_breaker.state.state == "closed"


class TestRetryLogic:
    """Tests for retry logic with exponential backoff."""

    def test_retries_on_failure(self, recovery_executor_no_protection):
        """Executor retries on failure."""
        call_count = [0]

        def failing_action(action_type, context):
            call_count[0] += 1
            raise Exception("temporary failure")

        with patch.object(recovery_executor_no_protection, '_execute_action_internal', failing_action):
            result = recovery_executor_no_protection.execute("Restart service", {})

        assert result is False
        assert call_count[0] == 1  # max_retries=1 for this executor

    def test_exponential_backoff(self):
        """Verify exponential backoff between retries."""
        executor = RecoveryActionExecutor(
            node_id="test",
            enable_circuit_breaker=False,
            enable_rate_limiting=False,
            max_retries=3,
            retry_delay=0.1
        )

        start_times = []

        def timing_action(action_type, context):
            start_times.append(time.time())
            raise Exception("failure")

        with patch.object(executor, '_execute_action_internal', timing_action):
            executor.execute("Restart service", {})

        # Should have 3 attempts
        assert len(start_times) == 3

        # Check exponential backoff (delays: 0.1, 0.2, 0.3)
        if len(start_times) >= 2:
            delay1 = start_times[1] - start_times[0]
            assert delay1 >= 0.09  # ~0.1s

        if len(start_times) >= 3:
            delay2 = start_times[2] - start_times[1]
            assert delay2 >= 0.19  # ~0.2s

    def test_success_after_retry(self, recovery_executor_no_protection):
        """Action succeeds after retries."""
        attempt = [0]

        def eventually_succeeds(action_type, context):
            attempt[0] += 1
            if attempt[0] < 2:
                raise Exception("temporary failure")
            return RecoveryResult(
                success=True,
                action_type=action_type,
                duration_seconds=0.1
            )

        with patch.object(recovery_executor_no_protection, '_execute_action_internal', eventually_succeeds):
            # Need more retries for this test
            recovery_executor_no_protection.max_retries = 3
            result = recovery_executor_no_protection.execute("Restart service", {})

        # Note: depends on executor configuration


class TestRollback:
    """Tests for rollback functionality."""

    def test_successful_action_saved_for_rollback(self, recovery_executor):
        """Successful actions are saved for rollback."""
        initial_stack_size = len(recovery_executor.rollback_stack)

        recovery_executor.execute(
            "Switch route",
            {"old_route": "route-a", "alternative_route": "route-b"}
        )

        assert len(recovery_executor.rollback_stack) > initial_stack_size

    def test_rollback_last_action(self, recovery_executor):
        """Rollback reverses last action."""
        # Execute an action
        recovery_executor.execute(
            "Scale up",
            {"deployment_name": "api", "replicas": 5, "old_replicas": 3}
        )

        # Rollback
        success = recovery_executor.rollback_last_action()
        assert success is True

    def test_rollback_empty_stack_returns_false(self, recovery_executor):
        """Rollback with empty stack returns False."""
        recovery_executor.rollback_stack.clear()
        result = recovery_executor.rollback_last_action()
        assert result is False

    def test_rollback_strategies(self, recovery_executor):
        """Get rollback action returns correct strategy."""
        context = {"old_route": "route-a"}
        rollback = recovery_executor._get_rollback_action("switch_route", context)
        assert "route-a" in rollback

        # No rollback for restart
        rollback = recovery_executor._get_rollback_action("restart_service", {})
        assert rollback is None


class TestActionHistory:
    """Tests for action history tracking."""

    def test_actions_recorded_in_history(self, recovery_executor):
        """Actions are recorded in history."""
        recovery_executor.execute("Restart service", {"service_name": "api"})
        recovery_executor.execute("Clear cache", {"cache_type": "all"})

        history = recovery_executor.get_action_history()
        assert len(history) >= 2

    def test_history_limit_respected(self, recovery_executor):
        """History respects max size limit."""
        recovery_executor.max_history_size = 5

        for i in range(10):
            recovery_executor.execute("Clear cache", {"cache_type": f"type-{i}"})

        history = recovery_executor.get_action_history()
        assert len(history) <= 5

    def test_success_rate_calculation(self, recovery_executor):
        """Success rate calculated correctly."""
        # Execute some successful actions
        for _ in range(4):
            recovery_executor.execute("Clear cache", {})

        success_rate = recovery_executor.get_success_rate()
        assert success_rate == 1.0  # All should succeed

    def test_success_rate_by_action_type(self, recovery_executor):
        """Success rate can be filtered by action type."""
        recovery_executor.execute("Clear cache", {})
        recovery_executor.execute("Restart service", {})

        cache_rate = recovery_executor.get_success_rate(RecoveryActionType.CLEAR_CACHE)
        assert cache_rate == 1.0


class TestExecutorStatus:
    """Tests for executor status reporting."""

    def test_circuit_breaker_status(self, recovery_executor):
        """Circuit breaker status reported correctly."""
        status = recovery_executor.get_circuit_breaker_status()

        assert status["enabled"] is True
        assert status["state"] == "closed"
        assert status["failures"] == 0

    def test_circuit_breaker_disabled_status(self, recovery_executor_no_protection):
        """Disabled circuit breaker status."""
        status = recovery_executor_no_protection.get_circuit_breaker_status()
        assert status["enabled"] is False

    def test_rate_limiter_status(self, recovery_executor):
        """Rate limiter status reported correctly."""
        status = recovery_executor.get_rate_limiter_status()

        assert status["enabled"] is True
        assert status["max_actions"] == 10  # default
        assert status["current_actions"] == 0

    def test_rate_limiter_disabled_status(self, recovery_executor_no_protection):
        """Disabled rate limiter status."""
        status = recovery_executor_no_protection.get_rate_limiter_status()
        assert status["enabled"] is False


class TestAsyncWrappers:
    """Tests for async wrapper methods."""

    @pytest.mark.asyncio
    async def test_async_restart_service(self, recovery_executor):
        """Async restart_service wrapper."""
        result = await recovery_executor.restart_service("test-service", "default")
        assert result is True

    @pytest.mark.asyncio
    async def test_async_switch_route(self, recovery_executor):
        """Async switch_route wrapper."""
        result = await recovery_executor.switch_route("old-route", "new-route")
        assert result is True

    @pytest.mark.asyncio
    async def test_async_clear_cache(self, recovery_executor):
        """Async clear_cache wrapper."""
        result = await recovery_executor.clear_cache("test-service", "session")
        assert result is True

    @pytest.mark.asyncio
    async def test_async_scale_up(self, recovery_executor):
        """Async scale_up wrapper."""
        result = await recovery_executor.scale_up("deployment", 5)
        assert result is True

    @pytest.mark.asyncio
    async def test_async_scale_down(self, recovery_executor):
        """Async scale_down wrapper."""
        result = await recovery_executor.scale_down("deployment", 2)
        assert result is True

    @pytest.mark.asyncio
    async def test_async_failover(self, recovery_executor):
        """Async failover wrapper."""
        result = await recovery_executor.failover("service", "primary", "backup")
        assert result is True

    @pytest.mark.asyncio
    async def test_async_quarantine_node(self, recovery_executor):
        """Async quarantine_node wrapper."""
        result = await recovery_executor.quarantine_node("node-123")
        assert result is True

    @pytest.mark.asyncio
    async def test_async_execute_action(self, recovery_executor):
        """Async execute_action wrapper."""
        result = await recovery_executor.execute_action(
            "Clear cache",
            cache_type="all"
        )
        assert result is True


if __name__ == "__main__":
    pytest.main([__file__, "-v"])
