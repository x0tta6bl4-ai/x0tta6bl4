"""
Tests for Health Check module.
"""

import asyncio
import sys
import types
from unittest.mock import AsyncMock, Mock, patch

import pytest

from src.core.health_check import (CheckResult, HealthChecker,
                                   HealthCheckResponse, HealthStatus,
                                   check_database, check_disk, check_memory,
                                   check_redis, check_vpn_server,
                                   get_health_status, get_liveness,
                                   get_readiness)


class TestHealthStatus:
    """Tests for HealthStatus enum."""

    def test_status_values(self):
        """Test all status values exist."""
        assert HealthStatus.HEALTHY.value == "healthy"
        assert HealthStatus.DEGRADED.value == "degraded"
        assert HealthStatus.UNHEALTHY.value == "unhealthy"


class TestCheckResult:
    """Tests for CheckResult dataclass."""

    def test_to_dict(self):
        """Test serialization to dict."""
        result = CheckResult(
            name="test",
            status=HealthStatus.HEALTHY,
            latency_ms=10.5,
            message="OK",
            details={"key": "value"},
        )
        d = result.to_dict()

        assert d["name"] == "test"
        assert d["status"] == "healthy"
        assert d["latency_ms"] == 10.5
        assert d["message"] == "OK"
        assert d["details"]["key"] == "value"

    def test_to_dict_without_optional_fields(self):
        """Test serialization without optional fields."""
        result = CheckResult(
            name="test",
            status=HealthStatus.HEALTHY,
            latency_ms=5.0,
        )
        d = result.to_dict()

        assert d["name"] == "test"
        assert d["message"] is None
        assert d["details"] == {}


class TestHealthChecker:
    """Tests for HealthChecker class."""

    @pytest.mark.asyncio
    async def test_run_single_check_success(self):
        """Test running a single successful check."""
        checker = HealthChecker(version="1.0.0")

        async def passing_check():
            return True

        result = await checker.run_check("test", passing_check)

        assert result.name == "test"
        assert result.status == HealthStatus.HEALTHY
        assert result.latency_ms >= 0

    @pytest.mark.asyncio
    async def test_run_single_check_failure(self):
        """Test running a single failing check."""
        checker = HealthChecker(version="1.0.0")

        async def failing_check():
            raise Exception("Connection failed")

        result = await checker.run_check("test", failing_check)

        assert result.name == "test"
        assert result.status == HealthStatus.UNHEALTHY
        assert "Connection failed" in result.message

    @pytest.mark.asyncio
    async def test_run_check_with_result(self):
        """Test running check that returns CheckResult."""
        checker = HealthChecker(version="1.0.0")

        async def custom_check():
            return CheckResult(
                name="custom",
                status=HealthStatus.DEGRADED,
                latency_ms=0,
                message="Partially working",
            )

        result = await checker.run_check("custom", custom_check)

        assert result.status == HealthStatus.DEGRADED
        assert result.message == "Partially working"

    @pytest.mark.asyncio
    async def test_run_all_checks_healthy(self):
        """Test running all checks when all pass."""
        checker = HealthChecker(version="2.0.0")

        async def check1():
            return True

        async def check2():
            return True

        checker.add_check("check1", check1)
        checker.add_check("check2", check2)

        result = await checker.run_all_checks()

        assert result.status == HealthStatus.HEALTHY
        assert result.version == "2.0.0"
        assert len(result.checks) == 2
        assert result.uptime_seconds >= 0

    @pytest.mark.asyncio
    async def test_run_all_checks_unhealthy(self):
        """Test running all checks when one fails."""
        checker = HealthChecker(version="2.0.0")

        async def passing():
            return True

        async def failing():
            raise Exception("Failed")

        checker.add_check("passing", passing)
        checker.add_check("failing", failing)

        result = await checker.run_all_checks()

        assert result.status == HealthStatus.UNHEALTHY
        assert len(result.checks) == 2

    @pytest.mark.asyncio
    async def test_run_all_checks_with_timeout(self):
        """Test that slow checks are timed out."""
        checker = HealthChecker(version="2.0.0")

        async def slow_check():
            await asyncio.sleep(10)
            return True

        checker.add_check("slow", slow_check)

        result = await checker.run_all_checks(timeout=0.1)

        assert result.status == HealthStatus.UNHEALTHY
        assert len(result.checks) == 1
        assert "timed out" in result.checks[0].message.lower()

    @pytest.mark.asyncio
    async def test_run_all_checks_degraded_status(self):
        checker = HealthChecker(version="2.1.0")

        async def healthy_check():
            return True

        async def degraded_check():
            return CheckResult(
                name="degraded_check",
                status=HealthStatus.DEGRADED,
                latency_ms=0.0,
                message="slow",
            )

        checker.add_check("healthy", healthy_check)
        checker.add_check("degraded", degraded_check)

        result = await checker.run_all_checks()

        assert result.status == HealthStatus.DEGRADED
        assert len(result.checks) == 2

    @pytest.mark.asyncio
    async def test_run_all_checks_converts_exception_results(self, monkeypatch):
        checker = HealthChecker(version="2.1.0")
        checker.add_check("broken", lambda: True)

        async def failing_run_check(_name, _check_fn):
            raise RuntimeError("check blew up")

        monkeypatch.setattr(checker, "run_check", failing_run_check)

        result = await checker.run_all_checks()

        assert result.status == HealthStatus.UNHEALTHY
        assert result.checks[0].name == "broken"
        assert result.checks[0].message == "check blew up"


class TestDefaultChecks:
    """Tests for default health check functions."""

    @pytest.mark.asyncio
    async def test_check_memory(self):
        """Test memory check."""
        result = await check_memory()

        assert result.name == "memory"
        assert result.status in [
            HealthStatus.HEALTHY,
            HealthStatus.DEGRADED,
            HealthStatus.UNHEALTHY,
        ]
        assert "percent" in result.details or result.message

    @pytest.mark.asyncio
    async def test_check_disk(self):
        """Test disk check."""
        result = await check_disk()

        assert result.name == "disk"
        assert result.status in [
            HealthStatus.HEALTHY,
            HealthStatus.DEGRADED,
            HealthStatus.UNHEALTHY,
        ]

    @pytest.mark.asyncio
    async def test_check_database_success(self, monkeypatch):
        fake_module = types.ModuleType("src.database")
        state = {"closed": False}

        class _DB:
            def execute(self, query):
                assert query == "SELECT 1"

            def close(self):
                state["closed"] = True

        fake_module.SessionLocal = lambda: _DB()
        monkeypatch.setitem(sys.modules, "src.database", fake_module)

        result = await check_database()

        assert result.status == HealthStatus.HEALTHY
        assert result.message == "Connected"
        assert state["closed"] is True

    @pytest.mark.asyncio
    async def test_check_database_failure(self, monkeypatch):
        fake_module = types.ModuleType("src.database")

        def _failing_session():
            raise RuntimeError("db unavailable")

        fake_module.SessionLocal = _failing_session
        monkeypatch.setitem(sys.modules, "src.database", fake_module)

        result = await check_database()

        assert result.status == HealthStatus.UNHEALTHY
        assert "Connection failed" in result.message

    @pytest.mark.asyncio
    async def test_check_redis_healthy(self, monkeypatch):
        fake_cache_module = types.ModuleType("src.core.cache")

        class _Cache:
            async def set(self, *_args, **_kwargs):
                return None

            async def get(self, *_args, **_kwargs):
                return "ok"

        fake_cache_module.cache = _Cache()
        monkeypatch.setitem(sys.modules, "src.core.cache", fake_cache_module)

        result = await check_redis()

        assert result.status == HealthStatus.HEALTHY
        assert result.message == "Connected"

    @pytest.mark.asyncio
    async def test_check_redis_degraded_and_exception(self, monkeypatch):
        fake_cache_module = types.ModuleType("src.core.cache")

        class _CacheMismatch:
            async def set(self, *_args, **_kwargs):
                return None

            async def get(self, *_args, **_kwargs):
                return "mismatch"

        fake_cache_module.cache = _CacheMismatch()
        monkeypatch.setitem(sys.modules, "src.core.cache", fake_cache_module)

        degraded = await check_redis()
        assert degraded.status == HealthStatus.DEGRADED
        assert "mismatch" in degraded.message.lower()

        class _FailingCache:
            async def set(self, *_args, **_kwargs):
                raise RuntimeError("redis down")

            async def get(self, *_args, **_kwargs):  # pragma: no cover
                return None

        fake_cache_module.cache = _FailingCache()
        unhealthy = await check_redis()
        assert unhealthy.status == HealthStatus.UNHEALTHY
        assert "Connection failed" in unhealthy.message

    @pytest.mark.asyncio
    async def test_check_vpn_server_success_and_failure(self, monkeypatch):
        from src.core import health_check as mod

        monkeypatch.setenv("VPN_SERVER", "127.0.0.1")
        monkeypatch.setenv("VPN_PORT", "443")

        state = {"closed": False}

        class _Writer:
            def close(self):
                state["closed"] = True

            async def wait_closed(self):
                return None

        async def _open_connection(server, port):
            assert server == "127.0.0.1"
            assert port == 443
            return object(), _Writer()

        async def _wait_for(coro, timeout):
            assert timeout == 2.0
            return await coro

        monkeypatch.setattr(mod.asyncio, "open_connection", _open_connection)
        monkeypatch.setattr(mod.asyncio, "wait_for", _wait_for)

        healthy = await check_vpn_server()
        assert healthy.status == HealthStatus.HEALTHY
        assert state["closed"] is True

        async def _wait_for_fail(_coro, timeout):
            assert timeout == 2.0
            raise TimeoutError("vpn timeout")

        monkeypatch.setattr(mod.asyncio, "wait_for", _wait_for_fail)
        degraded = await check_vpn_server()
        assert degraded.status == HealthStatus.DEGRADED
        assert "Unreachable" in degraded.message

    @pytest.mark.asyncio
    async def test_check_memory_thresholds_and_fallback(self, monkeypatch):
        fake_psutil = types.ModuleType("psutil")

        class _Process:
            def __init__(self, percent):
                self._percent = percent

            def memory_info(self):
                return types.SimpleNamespace(rss=150 * 1024 * 1024)

            def memory_percent(self):
                return self._percent

        fake_psutil.Process = lambda: _Process(92.0)
        monkeypatch.setitem(sys.modules, "psutil", fake_psutil)
        unhealthy = await check_memory()
        assert unhealthy.status == HealthStatus.UNHEALTHY

        fake_psutil.Process = lambda: _Process(85.0)
        degraded = await check_memory()
        assert degraded.status == HealthStatus.DEGRADED

        def _raise_process():
            raise RuntimeError("psutil missing")

        fake_psutil.Process = _raise_process
        fallback = await check_memory()
        assert fallback.status == HealthStatus.HEALTHY
        assert "Check unavailable" in fallback.message

    @pytest.mark.asyncio
    async def test_check_disk_thresholds_and_fallback(self, monkeypatch):
        fake_psutil = types.ModuleType("psutil")

        def _disk(percent):
            return types.SimpleNamespace(
                total=500 * 1024 * 1024 * 1024,
                free=100 * 1024 * 1024 * 1024,
                percent=percent,
            )

        fake_psutil.disk_usage = lambda _path: _disk(96.0)
        monkeypatch.setitem(sys.modules, "psutil", fake_psutil)
        unhealthy = await check_disk()
        assert unhealthy.status == HealthStatus.UNHEALTHY

        fake_psutil.disk_usage = lambda _path: _disk(86.0)
        degraded = await check_disk()
        assert degraded.status == HealthStatus.DEGRADED

        def _disk_raise(_path):
            raise RuntimeError("disk unavailable")

        fake_psutil.disk_usage = _disk_raise
        fallback = await check_disk()
        assert fallback.status == HealthStatus.HEALTHY
        assert "Check unavailable" in fallback.message


class TestHealthWrappers:
    @pytest.mark.asyncio
    async def test_get_health_status_delegates_to_global_checker(self, monkeypatch):
        response = HealthCheckResponse(
            status=HealthStatus.HEALTHY,
            version="x",
            timestamp="2026-01-01T00:00:00Z",
            uptime_seconds=1.0,
            checks=[],
        )
        monkeypatch.setattr(
            "src.core.health_check.health_checker.run_all_checks",
            AsyncMock(return_value=response),
        )

        result = await get_health_status()
        assert result is response

    @pytest.mark.asyncio
    async def test_get_liveness_returns_status_and_timestamp(self):
        payload = await get_liveness()
        assert payload["status"] == "ok"
        assert "timestamp" in payload

    @pytest.mark.asyncio
    async def test_get_readiness_not_ready_and_ready(self, monkeypatch):
        unhealthy_db = HealthCheckResponse(
            status=HealthStatus.UNHEALTHY,
            version="x",
            timestamp="2026-01-01T00:00:00Z",
            uptime_seconds=1.0,
            checks=[
                CheckResult(
                    name="database",
                    status=HealthStatus.UNHEALTHY,
                    latency_ms=0.0,
                    message="db down",
                )
            ],
        )
        monkeypatch.setattr(
            "src.core.health_check.health_checker.run_all_checks",
            AsyncMock(return_value=unhealthy_db),
        )
        not_ready = await get_readiness()
        assert not_ready["status"] == "not_ready"
        assert "database is unhealthy" in not_ready["reason"]

        healthy = HealthCheckResponse(
            status=HealthStatus.HEALTHY,
            version="x",
            timestamp="2026-01-01T00:00:00Z",
            uptime_seconds=1.0,
            checks=[
                CheckResult(
                    name="database",
                    status=HealthStatus.HEALTHY,
                    latency_ms=0.0,
                    message="ok",
                )
            ],
        )
        monkeypatch.setattr(
            "src.core.health_check.health_checker.run_all_checks",
            AsyncMock(return_value=healthy),
        )
        ready = await get_readiness()
        assert ready["status"] == "ready"
        assert "timestamp" in ready


class TestHealthCheckResponse:
    """Tests for HealthCheckResponse dataclass."""

    def test_to_dict(self):
        """Test serialization to dict."""
        checks = [
            CheckResult(
                name="test1",
                status=HealthStatus.HEALTHY,
                latency_ms=5.0,
            ),
            CheckResult(
                name="test2",
                status=HealthStatus.DEGRADED,
                latency_ms=10.0,
            ),
        ]

        response = HealthCheckResponse(
            status=HealthStatus.DEGRADED,
            version="3.2.1",
            timestamp="2024-01-01T00:00:00Z",
            uptime_seconds=3600.5,
            checks=checks,
        )

        d = response.to_dict()

        assert d["status"] == "degraded"
        assert d["version"] == "3.2.1"
        assert d["timestamp"] == "2024-01-01T00:00:00Z"
        assert d["uptime_seconds"] == 3600.5
        assert len(d["checks"]) == 2
        assert d["checks"][0]["name"] == "test1"


class TestHealthEndpointsIntegration:
    """Integration tests for health endpoints."""

    def test_health_endpoint(self):
        """Test basic health endpoint."""
        from fastapi.testclient import TestClient

        from src.core.app import app

        client = TestClient(app)
        response = client.get("/health")

        assert response.status_code == 200
        data = response.json()
        assert data["status"] == "ok"

    def test_health_live_endpoint(self):
        """Test liveness probe endpoint."""
        from fastapi.testclient import TestClient

        from src.core.app import app

        client = TestClient(app)
        response = client.get("/health/live")

        assert response.status_code == 200
        data = response.json()
        assert data["status"] == "ok"
        assert "timestamp" in data

    def test_health_detailed_endpoint(self):
        """Test detailed health endpoint."""
        from fastapi.testclient import TestClient

        from src.core.app import app

        client = TestClient(app)
        response = client.get("/health/detailed")

        # May be 200 or 503 depending on dependencies
        assert response.status_code in [200, 503]
        data = response.json()
        assert "status" in data
        assert "version" in data
        assert "checks" in data
        assert isinstance(data["checks"], list)
