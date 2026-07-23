"""
Tests for core modules that are importable without VPN dependency chain.

Covers:
- Circuit Breaker (resilience)
- Event Bus (coordination)
- Env Settings (config)
- Version contract
- Graceful Shutdown
- Reliability Policy
"""

import asyncio
import os
import threading
import time
from datetime import datetime, timedelta
from unittest.mock import MagicMock, patch

import pytest


# ---------------------------------------------------------------------------
# Circuit Breaker
# ---------------------------------------------------------------------------

class TestCircuitBreaker:
    def test_initial_state_is_closed(self):
        from src.resilience.advanced_patterns import CircuitBreaker, CircuitState
        cb = CircuitBreaker()
        assert cb.state == CircuitState.CLOSED
        assert cb.get_state() == "closed"

    def test_call_success_keeps_closed(self):
        from src.resilience.advanced_patterns import CircuitBreaker
        cb = CircuitBreaker()
        result = cb.call(lambda: 42)
        assert result == 42
        assert cb.get_state() == "closed"

    def test_call_failure_increments_count(self):
        from src.resilience.advanced_patterns import CircuitBreaker
        cb = CircuitBreaker()
        with pytest.raises(ValueError):
            cb.call(lambda: (_ for _ in ()).throw(ValueError("boom")))
        assert cb.failure_count == 1
        assert cb.get_state() == "closed"

    def test_opens_after_threshold(self):
        from src.resilience.advanced_patterns import CircuitBreaker
        cb = CircuitBreaker(failure_threshold=3)
        for _ in range(3):
            with pytest.raises(ValueError):
                cb.call(lambda: (_ for _ in ()).throw(ValueError("boom")))
        assert cb.get_state() == "open"

    def test_open_raises_on_call(self):
        from src.resilience.advanced_patterns import CircuitBreaker
        cb = CircuitBreaker(failure_threshold=1)
        with pytest.raises(ValueError):
            cb.call(lambda: (_ for _ in ()).throw(ValueError("boom")))
        with pytest.raises(Exception, match="Circuit breaker is OPEN"):
            cb.call(lambda: 42)

    def test_half_open_after_recovery_timeout(self):
        from src.resilience.advanced_patterns import CircuitBreaker, CircuitState
        cb = CircuitBreaker(failure_threshold=1, recovery_timeout=0, success_threshold=1)
        with pytest.raises(ValueError):
            cb.call(lambda: (_ for _ in ()).throw(ValueError("boom")))
        # recovery_timeout=0 means immediate recovery attempt
        cb.call(lambda: "recovered")
        assert cb.state == CircuitState.CLOSED

    def test_success_resets_failure_count(self):
        from src.resilience.advanced_patterns import CircuitBreaker
        cb = CircuitBreaker(failure_threshold=5)
        with pytest.raises(ValueError):
            cb.call(lambda: (_ for _ in ()).throw(ValueError("boom")))
        assert cb.failure_count == 1
        cb.call(lambda: "ok")
        assert cb.failure_count == 0

    def test_thread_safety(self):
        from src.resilience.advanced_patterns import CircuitBreaker
        cb = CircuitBreaker(failure_threshold=100)
        errors = []

        def worker():
            try:
                cb.call(lambda: 1)
            except Exception as e:
                errors.append(e)

        threads = [threading.Thread(target=worker) for _ in range(50)]
        for t in threads:
            t.start()
        for t in threads:
            t.join()
        assert len(errors) == 0
        assert cb.get_state() == "closed"


# ---------------------------------------------------------------------------
# Event Bus
# ---------------------------------------------------------------------------

class TestEventBus:
    def _make_bus(self, tmp_path):
        """Create EventBus backed by a temp directory (avoids loading 1.2GB events.log)."""
        from src.coordination.events import EventBus
        return EventBus(project_root=str(tmp_path))

    def test_create_event(self):
        from src.coordination.events import Event, EventType
        event = Event(
            event_type=EventType.AGENT_REGISTERED,
            source_agent="agent-1",
            data={"role": "worker"},
        )
        assert event.event_type == EventType.AGENT_REGISTERED
        assert event.source_agent == "agent-1"
        assert event.data == {"role": "worker"}
        assert event.event_id  # UUID generated

    def test_event_to_dict(self):
        from src.coordination.events import Event, EventType
        event = Event(
            event_type=EventType.TASK_CREATED,
            source_agent="agent-1",
            data={"task_id": "T1"},
        )
        d = event.to_dict()
        assert d["event_type"] == "task.created"
        assert d["source_agent"] == "agent-1"
        assert "event_id" in d
        assert "timestamp" in d

    def test_event_bus_subscribe_and_publish(self, tmp_path):
        from src.coordination.events import EventType
        bus = self._make_bus(tmp_path)
        received = []

        def handler(event):
            received.append(event)

        bus.subscribe(EventType.TASK_CREATED, handler)
        bus.publish(EventType.TASK_CREATED, "agent-1", {"task_id": "T1"})
        assert len(received) == 1
        assert received[0].event_type == EventType.TASK_CREATED

    def test_event_bus_multiple_subscribers(self, tmp_path):
        from src.coordination.events import EventType
        bus = self._make_bus(tmp_path)
        received_a = []
        received_b = []

        bus.subscribe(EventType.AGENT_HEARTBEAT, lambda e: received_a.append(e))
        bus.subscribe(EventType.AGENT_HEARTBEAT, lambda e: received_b.append(e))

        bus.publish(EventType.AGENT_HEARTBEAT, "agent-1", {})
        assert len(received_a) == 1
        assert len(received_b) == 1

    def test_event_bus_unsubscribe(self, tmp_path):
        from src.coordination.events import EventType
        bus = self._make_bus(tmp_path)
        received = []

        def handler(event):
            received.append(event)

        bus.subscribe(EventType.SYSTEM_ALERT, handler)
        bus.unsubscribe(EventType.SYSTEM_ALERT, handler)

        bus.publish(EventType.SYSTEM_ALERT, "system", {})
        assert len(received) == 0

    def test_event_type_all_values_exist(self):
        from src.coordination.events import EventType
        assert EventType.AGENT_REGISTERED.value == "agent.registered"
        assert EventType.TASK_CREATED.value == "task.created"
        assert EventType.LOCK_ACQUIRED.value == "lock.acquired"
        assert EventType.MARKETPLACE_ESCROW_HELD.value == "marketplace.escrow.held"
        assert EventType.SYSTEM_SHUTDOWN.value == "system.shutdown"


# ---------------------------------------------------------------------------
# Env Settings
# ---------------------------------------------------------------------------

class TestEnvSettings:
    def test_default_settings(self):
        from src.config.env_settings import AppSettings
        with patch.dict(os.environ, {}, clear=False):
            s = AppSettings()
            assert s.environment in ("development", "production")
            assert s.api_port > 0
            assert s.vpn.server  # has default
            assert s.database.url  # has default

    def test_vpn_settings_defaults(self):
        from src.config.env_settings import VPNSettings
        v = VPNSettings()
        assert v.server == "89.125.1.107"
        assert v.port == 443
        assert v.socks_port == 10808

    def test_vpn_settings_from_env(self):
        from src.config.env_settings import VPNSettings
        with patch.dict(os.environ, {"VPN_SERVER": "1.2.3.4", "VPN_PORT": "8443"}):
            v = VPNSettings()
            assert v.server == "1.2.3.4"
            assert v.port == 8443

    def test_database_settings_defaults(self):
        from src.config.env_settings import DatabaseSettings
        d = DatabaseSettings()
        assert "sqlite" in d.url or "postgresql" in d.url
        assert d.pool_size == 20

    def test_feature_flags_defaults(self):
        from src.config.env_settings import FeatureFlags
        f = FeatureFlags()
        assert isinstance(f.byzantine, bool)
        assert isinstance(f.dao, bool)
        assert isinstance(f.pqc_beacons, bool)

    def test_feature_flags_from_env(self):
        from src.config.env_settings import FeatureFlags
        with patch.dict(os.environ, {"X0TTA6BL4_FEATURE_DAO": "true", "X0TTA6BL4_FEATURE_EBPF": "1"}):
            f = FeatureFlags()
            assert f.dao is True
            assert f.ebpf is True

    def test_app_settings_properties(self):
        from src.config.env_settings import AppSettings
        with patch.dict(os.environ, {"ENVIRONMENT": "production"}):
            s = AppSettings()
            assert s.is_production is True
            assert s.is_development is False

    def test_settings_singleton(self):
        from src.config.env_settings import get_settings
        s1 = get_settings()
        s2 = get_settings()
        assert s1 is s2

    def test_security_settings(self):
        from src.config.env_settings import SecuritySettings
        with patch.dict(os.environ, {"JWT_SECRET_KEY": "test-secret", "PQC_FAIL_CLOSED": "false"}):
            sec = SecuritySettings()
            assert sec.jwt_secret == "test-secret"
            assert sec.pqc_fail_closed is False


# ---------------------------------------------------------------------------
# Version Contract
# ---------------------------------------------------------------------------

class TestVersion:
    def test_version_format(self):
        from src.version import __version__
        parts = __version__.split(".")
        assert len(parts) == 3
        assert all(p.isdigit() for p in parts)

    def test_parse_version(self):
        from src.version import parse_version
        assert parse_version("3.4.0") == (3, 4, 0)
        assert parse_version("1.0.0") == (1, 0, 0)
        assert parse_version("2.10.5") == (2, 10, 5)

    def test_get_version_info(self):
        from src.version import get_version_info
        info = get_version_info()
        assert info.version == "3.5.0"
        assert info.major == 3
        assert info.minor == 5
        assert info.patch == 0

    def test_version_info_to_dict(self):
        from src.version import get_version_info
        d = get_version_info().to_dict()
        assert "version" in d
        assert "api_version" in d
        assert "docker_tag" in d
        assert "user_agent" in d

    def test_docker_tag_stable(self):
        from src.version import get_version_info
        info = get_version_info()
        if info.channel == "stable":
            assert info.docker_tag == info.version

    def test_user_agent_format(self):
        from src.version import get_version_info
        info = get_version_info()
        assert info.user_agent.startswith("x0tta6bl4/")

    def test_is_compatible(self):
        from src.version import is_compatible
        assert is_compatible("3.0.0") is True
        assert is_compatible("3.4.0") is True
        assert is_compatible("3.5.0") is True
        assert is_compatible("3.6.0") is False
        assert is_compatible("4.0.0") is False

    def test_check_min_version_raises(self):
        from src.version import check_min_version
        with pytest.raises(RuntimeError):
            check_min_version("99.0.0")

    def test_get_health_info(self):
        from src.version import get_health_info
        info = get_health_info()
        assert "version" in info
        assert "timestamp" in info


# ---------------------------------------------------------------------------
# Graceful Shutdown
# ---------------------------------------------------------------------------

class TestGracefulShutdown:
    def test_shutdown_state_defaults(self):
        from src.core.graceful_shutdown import ShutdownState
        state = ShutdownState()
        assert state.is_shutting_down is False
        assert state.active_requests == 0
        assert state.cleanup_handlers == []

    def test_shutdown_manager_creation(self):
        from src.core.graceful_shutdown import GracefulShutdownManager
        mgr = GracefulShutdownManager(shutdown_timeout=5.0)
        assert mgr.shutdown_timeout == 5.0

    def test_register_cleanup(self):
        from src.core.graceful_shutdown import GracefulShutdownManager
        mgr = GracefulShutdownManager()

        def my_handler():
            pass

        mgr.register_cleanup(my_handler, name="test_cleanup")
        assert my_handler in mgr.state.cleanup_handlers

    def test_track_request_start_end(self):
        from src.core.graceful_shutdown import GracefulShutdownManager
        mgr = GracefulShutdownManager()
        mgr.track_request_start()
        mgr.track_request_start()
        assert mgr.active_requests == 2
        mgr.track_request_end()
        assert mgr.active_requests == 1
        mgr.track_request_end()
        assert mgr.active_requests == 0

    def test_is_shutting_down_property(self):
        from src.core.graceful_shutdown import GracefulShutdownManager
        mgr = GracefulShutdownManager()
        assert mgr.is_shutting_down is False


# ---------------------------------------------------------------------------
# Reliability Policy
# ---------------------------------------------------------------------------

class TestReliabilityPolicy:
    def test_default_policy(self):
        from src.core.resilience.reliability_policy import ReliabilityPolicy
        p = ReliabilityPolicy()
        assert p.timeout_seconds == 8.0
        assert p.max_retries == 2
        assert p.failure_threshold == 3

    def test_policy_for_dependency(self):
        from src.core.resilience.reliability_policy import policy_for_dependency
        with patch.dict(os.environ, {
            "RELIABILITY_STRIPE_TIMEOUT_SECONDS": "5.0",
            "RELIABILITY_STRIPE_MAX_RETRIES": "3",
        }):
            p = policy_for_dependency("stripe")
            assert p.timeout_seconds == 5.0
            assert p.max_retries == 3

    def test_policy_for_dependency_defaults(self):
        from src.core.resilience.reliability_policy import policy_for_dependency
        p = policy_for_dependency("nonexistent_dep")
        assert p.timeout_seconds == 8.0


# ---------------------------------------------------------------------------
# Logging Config
# ---------------------------------------------------------------------------

class TestLoggingConfig:
    def test_setup_logging(self):
        from src.core.logging_config import setup_logging
        logger = setup_logging(name="test_logger", log_level="INFO")
        assert logger is not None
        logger.info("test message")

    def test_request_id_context_var(self):
        from src.core.logging_config import RequestIdContextVar
        RequestIdContextVar.set("test-123")
        assert RequestIdContextVar.get() == "test-123"


# ---------------------------------------------------------------------------
# Status Collector
# ---------------------------------------------------------------------------

class TestStatusCollector:
    def test_system_metrics_collector(self):
        from src.core.status_collector import SystemMetricsCollector
        collector = SystemMetricsCollector()
        cpu = collector.get_cpu_metrics()
        assert "percent" in cpu
        assert "cores" in cpu

    def test_memory_metrics(self):
        from src.core.status_collector import SystemMetricsCollector
        collector = SystemMetricsCollector()
        mem = collector.get_memory_metrics()
        assert "total_mb" in mem
        assert mem["total_mb"] > 0

    def test_disk_metrics(self):
        from src.core.status_collector import SystemMetricsCollector
        collector = SystemMetricsCollector()
        disk = collector.get_disk_metrics()
        assert "total_gb" in disk
        assert disk["total_gb"] > 0
