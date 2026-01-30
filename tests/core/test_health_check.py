"""
Tests for Health Check module.
"""
import pytest
import asyncio
from unittest.mock import Mock, patch, AsyncMock

from src.core.health_check import (
    HealthChecker,
    HealthStatus,
    CheckResult,
    HealthCheckResponse,
    check_memory,
    check_disk,
)


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
            details={"key": "value"}
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


class TestDefaultChecks:
    """Tests for default health check functions."""

    @pytest.mark.asyncio
    async def test_check_memory(self):
        """Test memory check."""
        result = await check_memory()

        assert result.name == "memory"
        assert result.status in [HealthStatus.HEALTHY, HealthStatus.DEGRADED, HealthStatus.UNHEALTHY]
        assert "percent" in result.details or result.message

    @pytest.mark.asyncio
    async def test_check_disk(self):
        """Test disk check."""
        result = await check_disk()

        assert result.name == "disk"
        assert result.status in [HealthStatus.HEALTHY, HealthStatus.DEGRADED, HealthStatus.UNHEALTHY]


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
            version="3.0.0",
            timestamp="2024-01-01T00:00:00Z",
            uptime_seconds=3600.5,
            checks=checks,
        )

        d = response.to_dict()

        assert d["status"] == "degraded"
        assert d["version"] == "3.0.0"
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
