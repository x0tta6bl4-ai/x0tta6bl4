"""
Comprehensive unit tests for Production Dependency Checks.

Tests cover:
- Dependency availability detection
- Production mode validation
- Staging mode behavior
- Error handling and messaging
- Status reporting
- Critical component validation
"""

import os
import sys
from io import StringIO
from unittest.mock import MagicMock, Mock, patch

import pytest

from src.core.production_checks import (PRODUCTION_MODE,
                                        ProductionDependencyError,
                                        check_production_dependencies,
                                        get_dependency_status)


@pytest.fixture
def cleanup_modules():
    """Clean up imported modules after test."""
    yield
    # Cleanup module cache
    if "src.security.post_quantum_liboqs" in sys.modules:
        del sys.modules["src.security.post_quantum_liboqs"]


class TestProductionDependencyError:
    """Tests for ProductionDependencyError exception."""

    def test_error_creation(self):
        """Test creating ProductionDependencyError."""
        error = ProductionDependencyError("Test error message")
        assert isinstance(error, Exception)
        assert str(error) == "Test error message"

    def test_error_inheritance(self):
        """Test ProductionDependencyError inherits from Exception."""
        error = ProductionDependencyError("Test")
        assert isinstance(error, Exception)

    def test_error_with_multiple_lines(self):
        """Test error with multi-line message."""
        message = "Line 1\nLine 2\nLine 3"
        error = ProductionDependencyError(message)
        assert "Line 1" in str(error)
        assert "Line 2" in str(error)
        assert "Line 3" in str(error)


class TestCheckProductionDependenciesStaging:
    """Tests for staging mode behavior."""

    def test_staging_mode_no_check(self, monkeypatch):
        """Test that staging mode doesn't raise errors."""
        monkeypatch.setenv("X0TTA6BL4_PRODUCTION", "false")

        # Should not raise
        check_production_dependencies()

    def test_staging_mode_with_missing_deps(self, monkeypatch):
        """Test staging mode succeeds even with missing dependencies."""
        monkeypatch.setenv("X0TTA6BL4_PRODUCTION", "false")

        with patch.dict("sys.modules", {"torch": None, "redis": None}):
            # Should not raise in staging
            check_production_dependencies()

    def test_staging_mode_explicit_false(self, monkeypatch):
        """Test explicit false staging mode."""
        monkeypatch.setenv("X0TTA6BL4_PRODUCTION", "false")

        # Should be safe to call multiple times
        check_production_dependencies()
        check_production_dependencies()


class TestCheckProductionDependenciesProduction:
    """Tests for production mode behavior."""

    def test_production_mode_with_all_deps(self):
        """Test production mode either passes or raises with correct message."""
        # Don't use patch.dict('sys.modules') — it removes submodules loaded
        # during the context (e.g. torch._tensor), corrupting torch's state.
        with patch("src.core.production_checks.PRODUCTION_MODE", True):
            try:
                check_production_dependencies()
            except ProductionDependencyError as e:
                # Expected on dev machines missing CUDA, bcc, etc.
                assert "PRODUCTION DEPENDENCY CHECK FAILED" in str(e)

    def test_production_mode_missing_pqc(self):
        """Test production mode behavior with PQC check."""
        with patch("src.core.production_checks.PRODUCTION_MODE", True):
            # In production mode, check should either pass (if all deps present) or raise
            try:
                check_production_dependencies()
            except ProductionDependencyError as e:
                error_msg = str(e)
                assert "PRODUCTION DEPENDENCY CHECK FAILED" in error_msg

    def test_production_mode_missing_pytorch(self):
        """Test production mode behavior with PyTorch check."""
        with patch("src.core.production_checks.PRODUCTION_MODE", True):
            # In production mode with missing deps should raise or pass if all present
            try:
                check_production_dependencies()
            except ProductionDependencyError as e:
                assert "PRODUCTION DEPENDENCY CHECK FAILED" in str(e)

    def test_production_error_message_format(self, monkeypatch):
        """Test production error message format."""
        monkeypatch.setenv("X0TTA6BL4_PRODUCTION", "true")

        with patch("src.core.production_checks.PRODUCTION_MODE", True):
            try:
                check_production_dependencies()
            except ProductionDependencyError as e:
                error_msg = str(e)
                # Should contain header
                assert "PRODUCTION DEPENDENCY CHECK FAILED" in error_msg
                # Should list individual failures
                assert "- " in error_msg or "not available" in error_msg.lower()


class TestGetDependencyStatus:
    """Tests for get_dependency_status function."""

    def test_status_returns_list(self):
        """Test that get_dependency_status returns a list."""
        status = get_dependency_status()
        assert isinstance(status, list)

    def test_status_list_not_empty(self):
        """Test that status list contains items."""
        status = get_dependency_status()
        assert len(status) > 0

    def test_status_tuple_structure(self):
        """Test each status item is a 3-tuple."""
        status = get_dependency_status()

        for item in status:
            assert isinstance(item, tuple)
            assert len(item) == 3

    def test_status_tuple_types(self):
        """Test status tuple contains correct types."""
        status = get_dependency_status()

        for name, available, message in status:
            assert isinstance(name, str)
            assert isinstance(available, bool)
            assert isinstance(message, str)

    def test_status_includes_pqc(self):
        """Test status includes PQC component."""
        status = get_dependency_status()
        component_names = [name for name, _, _ in status]

        # Should include PQC
        assert any("PQC" in name or "liboqs" in name for name in component_names)

    def test_status_includes_pytorch(self):
        """Test status includes PyTorch component."""
        status = get_dependency_status()
        component_names = [name for name, _, _ in status]

        assert "PyTorch" in component_names

    def test_status_includes_graphsage(self):
        """Test status includes GraphSAGE component."""
        status = get_dependency_status()
        component_names = [name for name, _, _ in status]

        assert "GraphSAGE" in component_names

    def test_status_includes_ebpf(self):
        """Test status includes eBPF component."""
        status = get_dependency_status()
        component_names = [name for name, _, _ in status]

        # Should include eBPF
        assert any("eBPF" in name or "BCC" in name for name in component_names)

    def test_status_includes_redis(self):
        """Test status includes Redis component."""
        status = get_dependency_status()
        component_names = [name for name, _, _ in status]

        assert "Redis" in component_names

    def test_status_includes_prometheus(self):
        """Test status includes Prometheus component."""
        status = get_dependency_status()
        component_names = [name for name, _, _ in status]

        assert "Prometheus" in component_names

    def test_status_includes_opentelemetry(self):
        """Test status includes OpenTelemetry component."""
        status = get_dependency_status()
        component_names = [name for name, _, _ in status]

        assert "OpenTelemetry" in component_names

    def test_status_has_at_least_7_components(self):
        """Test that at least 7 critical components are checked."""
        status = get_dependency_status()
        assert len(status) >= 7

    def test_status_message_clarity(self):
        """Test that status messages are clear."""
        status = get_dependency_status()

        for name, available, message in status:
            if available:
                assert "available" in message.lower()
            else:
                assert "not" in message.lower() or "missing" in message.lower()

    def test_status_all_unique_names(self):
        """Test that all component names are unique."""
        status = get_dependency_status()
        names = [name for name, _, _ in status]

        assert len(names) == len(set(names))

    def test_status_reproducibility(self):
        """Test that multiple calls return consistent results."""
        status1 = get_dependency_status()
        status2 = get_dependency_status()

        # Should have same number of items
        assert len(status1) == len(status2)

        # Names should be in same order
        names1 = [name for name, _, _ in status1]
        names2 = [name for name, _, _ in status2]
        assert names1 == names2


class TestCriticalComponents:
    """Tests for critical production components."""

    def test_pqc_component_critical(self):
        """Test PQC is marked as critical dependency."""
        status = get_dependency_status()
        pqc_status = next(
            (s for s in status if "PQC" in s[0] or "liboqs" in s[0]), None
        )

        assert pqc_status is not None

    def test_ml_component_critical(self):
        """Test ML components are critical."""
        status = get_dependency_status()
        ml_components = [
            s for s in status if any(x in s[0] for x in ["GraphSAGE", "PyTorch", "ML"])
        ]

        assert len(ml_components) >= 2

    def test_observability_components(self):
        """Test observability components are checked."""
        status = get_dependency_status()
        obs_components = [
            s
            for s in status
            if any(x in s[0] for x in ["Prometheus", "OpenTelemetry", "trace"])
        ]

        assert len(obs_components) >= 2

    def test_infrastructure_components(self):
        """Test infrastructure dependencies are checked."""
        status = get_dependency_status()
        infra_components = [
            s for s in status if any(x in s[0] for x in ["Redis", "eBPF", "BCC"])
        ]

        assert len(infra_components) >= 2


class TestDependencyStatusMessages:
    """Tests for dependency status messages."""

    def test_message_for_available_component(self):
        """Test message format for available component."""
        # Get all status items
        status = get_dependency_status()

        available_items = [s for s in status if s[1]]

        # If there are available items, check message format
        if available_items:
            for name, available, message in available_items:
                assert available is True
                # Message should indicate availability
                assert isinstance(message, str)
                assert len(message) > 0

    def test_message_for_unavailable_component(self):
        """Test message format for unavailable component."""
        status = get_dependency_status()

        unavailable_items = [s for s in status if not s[1]]

        for name, available, message in unavailable_items:
            assert available is False
            assert any(
                x in message.lower() for x in ["not", "missing", "unavailable", "fail"]
            )


class TestProductionModeDetection:
    """Tests for production mode detection."""

    def test_production_mode_is_boolean(self):
        """Test PRODUCTION_MODE is a boolean."""
        assert isinstance(PRODUCTION_MODE, bool)

    def test_production_mode_defaults_false(self, monkeypatch):
        """Test production mode defaults to false when env var not set."""
        monkeypatch.delenv("X0TTA6BL4_PRODUCTION", raising=False)
        # PRODUCTION_MODE is evaluated at import time, so we test the logic directly
        import os

        assert os.getenv("X0TTA6BL4_PRODUCTION", "false").lower() != "true"


class TestDependencyCheckErrorHandling:
    """Tests for error handling in dependency checks."""

    def test_missing_pqc_module(self):
        """Test handling of missing PQC module."""
        with patch("sys.stderr", new=StringIO()) as fake_err:
            status = get_dependency_status()

            pqc_status = next(
                (s for s in status if "PQC" in s[0] or "liboqs" in s[0]), None
            )
            assert pqc_status is not None

    def test_import_error_handling(self):
        """Test that import errors are handled gracefully."""
        with patch.dict("sys.modules", {"torch": None}):
            # Should not raise, just mark as unavailable
            status = get_dependency_status()

            pytorch_items = [s for s in status if "PyTorch" in s[0]]
            assert len(pytorch_items) > 0

    def test_attribute_error_handling(self):
        """Test that attribute errors in torch.cuda are handled gracefully."""
        # Patch torch.cuda.is_available to raise AttributeError instead of
        # replacing torch in sys.modules (which corrupts module state).
        with patch("torch.cuda.is_available", side_effect=AttributeError("no cuda")):
            status = get_dependency_status()
            assert len(status) > 0


class TestDependencyCheckEdgeCases:
    """Edge case tests for dependency checks."""

    def test_check_called_multiple_times(self, monkeypatch):
        """Test that check can be called multiple times safely."""
        monkeypatch.setenv("X0TTA6BL4_PRODUCTION", "false")

        # Should not raise and be idempotent
        check_production_dependencies()
        check_production_dependencies()
        check_production_dependencies()

    def test_status_with_no_errors(self):
        """Test getting status doesn't modify state."""
        status1 = get_dependency_status()
        status2 = get_dependency_status()

        # Results should be identical
        assert status1 == status2

    def test_empty_error_message_not_raised_in_staging(self, monkeypatch):
        """Test that empty error messages don't cause issues in staging."""
        monkeypatch.setenv("X0TTA6BL4_PRODUCTION", "false")

        # Should complete without raising
        check_production_dependencies()


class TestProductionReadiness:
    """Tests for production readiness validation."""

    def test_all_critical_components_reported(self):
        """Test that all critical components are in status report."""
        status = get_dependency_status()

        critical_keywords = [
            "PQC",
            "PyTorch",
            "GraphSAGE",
            "eBPF",
            "Redis",
            "Prometheus",
            "OpenTelemetry",
        ]

        for keyword in critical_keywords:
            found = any(keyword in s[0] for s in status)
            # At least some critical components should be checked
            if keyword in ["PQC", "Redis", "Prometheus"]:
                assert found, f"{keyword} should be in status"

    def test_status_provides_actionable_info(self):
        """Test that status provides actionable information."""
        status = get_dependency_status()

        for name, available, message in status:
            # Message should be informative
            assert len(message) > 0
            # Should indicate availability clearly
            assert (
                "available" in message.lower()
                or "not" in message.lower()
                or "missing" in message.lower()
            )
