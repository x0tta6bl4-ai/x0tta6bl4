"""
Tests for production dependency checks
"""
import pytest
from unittest.mock import patch, MagicMock

from src.core.production_checks import (
    check_production_dependencies,
    get_dependency_status,
    ProductionDependencyError,
    PRODUCTION_MODE
)


class TestProductionChecks:
    """Test production dependency validation."""

    def test_production_checks_staging(self, monkeypatch, staging_mode):
        """Should not raise in staging mode."""
        monkeypatch.setenv("X0TTA6BL4_PRODUCTION", "false")
        # Should not raise
        check_production_dependencies()

    def test_production_checks_production_missing_deps(self, monkeypatch, production_mode):
        """Should raise error when critical deps missing in production."""
        with patch.dict('sys.modules', {
            'src.security.post_quantum_liboqs': None,
            'torch': None,
            'src.ml.graphsage_anomaly_detector': None,
            'bcc': None,
            'redis': None,
            'prometheus_client': None,
            'opentelemetry': None,
        }):
            with pytest.raises(ProductionDependencyError) as exc_info:
                check_production_dependencies()

            error_msg = str(exc_info.value)
            assert "PRODUCTION DEPENDENCY CHECK FAILED" in error_msg
            assert "liboqs-python not available" in error_msg

    def test_get_dependency_status(self):
        """Should return status for all dependencies."""
        status = get_dependency_status()

        # Should return list of tuples
        assert isinstance(status, list)
        assert len(status) > 0

        # Each item should be (name, available, message)
        for name, available, message in status:
            assert isinstance(name, str)
            assert isinstance(available, bool)
            assert isinstance(message, str)

    def test_dependency_status_includes_critical_components(self):
        """Should check all critical production dependencies."""
        status = get_dependency_status()
        component_names = [name for name, _, _ in status]

        assert "PQC (liboqs)" in component_names
        assert "PyTorch" in component_names
        assert "GraphSAGE" in component_names
        assert "eBPF (BCC)" in component_names
        assert "Redis" in component_names
        assert "Prometheus" in component_names
        assert "OpenTelemetry" in component_names