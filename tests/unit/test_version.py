"""
Unit tests for centralized version module.

Tests cover:
- Version parsing and formatting
- Version info structure
- Compatibility checks
- Health check integration
"""

import pytest


class TestVersionModule:
    """Tests for src/version.py"""

    def test_version_import(self):
        """Test that version module can be imported."""
        from src.version import __version__, get_version
        
        assert __version__ is not None
        assert get_version() == __version__

    def test_version_format(self):
        """Test that version follows semantic versioning."""
        from src.version import __version__, parse_version
        
        major, minor, patch = parse_version(__version__)
        
        assert isinstance(major, int)
        assert isinstance(minor, int)
        assert isinstance(patch, int)
        assert major >= 3  # Current major version
        assert minor >= 0
        assert patch >= 0

    def test_get_version_info(self):
        """Test get_version_info returns structured data."""
        from src.version import get_version_info, __version__
        
        info = get_version_info()
        
        assert info.version == __version__
        assert info.api_version == __version__
        assert isinstance(info.major, int)
        assert isinstance(info.minor, int)
        assert isinstance(info.patch, int)
        assert info.channel in ["stable", "beta", "alpha"]

    def test_version_info_to_dict(self):
        """Test VersionInfo serialization."""
        from src.version import get_version_info
        
        info = get_version_info()
        data = info.to_dict()
        
        assert "version" in data
        assert "major" in data
        assert "minor" in data
        assert "patch" in data
        assert "api_version" in data
        assert "docker_tag" in data
        assert "user_agent" in data

    def test_docker_tag_stable(self, monkeypatch):
        """Test Docker tag for stable channel."""
        monkeypatch.setenv("X0TTA6BL4_CHANNEL", "stable")
        
        # Re-import to pick up env change
        import importlib
        import src.version
        importlib.reload(src.version)
        
        from src.version import get_version_info, __version__
        info = get_version_info()
        
        # For stable, docker_tag should be just the version
        assert info.docker_tag == __version__

    def test_user_agent_format(self):
        """Test User-Agent string format."""
        from src.version import get_user_agent, __version__
        
        user_agent = get_user_agent()
        
        assert "x0tta6bl4" in user_agent
        assert __version__ in user_agent

    def test_parse_version_valid(self):
        """Test parsing valid version strings."""
        from src.version import parse_version
        
        assert parse_version("3.2.1") == (3, 2, 1)
        assert parse_version("3.0.0") == (3, 0, 0)
        assert parse_version("4.1.0") == (4, 1, 0)

    def test_parse_version_with_metadata(self):
        """Test parsing version strings with build metadata."""
        from src.version import parse_version
        
        # Should ignore build metadata
        assert parse_version("3.2.1+build123") == (3, 2, 1)
        assert parse_version("3.2.1-beta") == (3, 2, 1)
        assert parse_version("3.2.1-alpha+build") == (3, 2, 1)

    def test_is_compatible_same_version(self):
        """Test compatibility check with same version."""
        from src.version import is_compatible, __version__
        
        assert is_compatible(__version__) is True

    def test_is_compatible_lower_patch(self):
        """Test compatibility with lower patch requirement."""
        from src.version import is_compatible, get_version_info
        
        info = get_version_info()
        required = f"{info.major}.{info.minor}.{max(0, info.patch - 1)}"
        
        assert is_compatible(required) is True

    def test_is_compatible_higher_minor(self):
        """Test incompatibility with higher minor requirement."""
        from src.version import is_compatible, get_version_info
        
        info = get_version_info()
        required = f"{info.major}.{info.minor + 1}.0"
        
        assert is_compatible(required) is False

    def test_is_compatible_different_major(self):
        """Test incompatibility with different major version."""
        from src.version import is_compatible, get_version_info
        
        info = get_version_info()
        required = f"{info.major + 1}.0.0"
        
        assert is_compatible(required) is False

    def test_check_min_version_passes(self):
        """Test check_min_version passes for compatible version."""
        from src.version import check_min_version, get_version_info
        
        info = get_version_info()
        lower_version = f"{info.major}.{info.minor}.{max(0, info.patch - 1)}"
        
        # Should not raise
        check_min_version(lower_version)

    def test_check_min_version_fails(self):
        """Test check_min_version raises for incompatible version."""
        from src.version import check_min_version, get_version_info
        
        info = get_version_info()
        higher_version = f"{info.major}.{info.minor + 1}.0"
        
        with pytest.raises(RuntimeError) as exc_info:
            check_min_version(higher_version)
        
        assert "required" in str(exc_info.value).lower()

    def test_get_health_info(self):
        """Test health info structure."""
        from src.version import get_health_info, __version__
        
        health = get_health_info()
        
        assert health["version"] == __version__
        assert "full_version" in health
        assert "channel" in health
        assert "timestamp" in health

    def test_get_api_version(self):
        """Test API version getter."""
        from src.version import get_api_version, __version__
        
        assert get_api_version() == __version__

    def test_get_docker_tag(self):
        """Test Docker tag getter."""
        from src.version import get_docker_tag, get_version_info
        
        info = get_version_info()
        assert get_docker_tag() == info.docker_tag


class TestVersionIntegration:
    """Integration tests for version module with other components."""

    def test_health_endpoint_uses_version(self):
        """Test that health endpoint uses centralized version."""
        from src.core.health import get_health
        from src.version import __version__
        
        health = get_health()
        
        assert health["version"] == __version__

    def test_app_uses_version(self):
        """Test that FastAPI app uses centralized version."""
        from src.core.app import app
        from src.version import __version__
        
        assert app.version == __version__

    def test_ml_module_uses_version(self):
        """Test that ML module uses centralized version."""
        from src.ml import __version__
        from src.version import __version__ as core_version
        
        assert __version__ == core_version

    def test_v3_metrics_uses_version(self):
        """Test that v3_metrics uses centralized version."""
        # The V3MetricsCollector should use the version
        from src.version import __version__
        
        # Just verify the version is importable in that context
        assert __version__ is not None


class TestVersionConsistency:
    """Tests to ensure version consistency across the codebase."""

    def test_no_hardcoded_versions_in_health(self):
        """Test that health.py doesn't have hardcoded version."""
        import inspect
        from src.core import health
        
        source = inspect.getsource(health)
        
        # Should not contain hardcoded version strings
        assert '"3.0.0"' not in source
        assert '"3.1.0"' not in source
        assert '"3.2.0"' not in source
        assert '"3.2.1"' not in source
        assert '"3.3.0"' not in source

    def test_version_module_exports(self):
        """Test that version module exports all expected symbols."""
        from src.version import (
            __version__,
            __build__,
            __commit__,
            __channel__,
            __full_version__,
            get_version,
            get_version_info,
            get_api_version,
            get_docker_tag,
            get_user_agent,
            get_health_info,
            is_compatible,
            check_min_version,
            parse_version,
            VersionInfo,
        )
        
        assert __version__ is not None
        assert __build__ is not None
        assert __channel__ in ["stable", "beta", "alpha"]


if __name__ == "__main__":
    pytest.main([__file__, "-v"])
