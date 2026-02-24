"""
Tests for core health module.
"""

import os
import sys
from io import StringIO
from unittest.mock import MagicMock, patch

import pytest

from src.core.health import check_cli, get_health


class TestHealth:
    """Tests for health check functionality"""

    def test_get_health_returns_dict(self):
        """Test that get_health returns a dictionary"""
        health = get_health()

        assert isinstance(health, dict)
        assert "status" in health
        assert "version" in health
        assert health["status"] == "ok"

    def test_get_health_version_from_env(self):
        """Test that version can be overridden by patching the module-level constant."""
        with patch("src.core.health._VERSION", "2.0.0"):
            from src.core.health import get_health

            health = get_health()
            assert health["version"] == "2.0.0"

    def test_get_health_default_version(self):
        """Test that the default version matches the canonical version."""
        from src.version import __version__
        from src.core.health import get_health

        health = get_health()
        assert health["version"] == __version__

    def test_check_cli_success(self):
        """Test CLI health check with ok status"""
        with (
            patch("sys.stdout", new=StringIO()) as mock_stdout,
            patch("sys.exit") as mock_exit,
        ):
            check_cli()

            output = mock_stdout.getvalue()
            assert "status" in output
            assert "version" in output
            mock_exit.assert_called_once_with(0)

    def test_check_cli_failure(self):
        """Test CLI health check with failure status"""
        with (
            patch("src.core.health.get_health", return_value={"status": "error"}),
            patch("sys.stdout", new=StringIO()) as mock_stdout,
            patch("sys.exit") as mock_exit,
        ):
            check_cli()

            mock_exit.assert_called_once_with(1)

    def test_check_cli_output_format(self):
        """Test that CLI output is valid JSON"""
        import json

        with patch("sys.stdout", new=StringIO()) as mock_stdout, patch("sys.exit"):
            check_cli()

            output = mock_stdout.getvalue()
            # Should be valid JSON
            data = json.loads(output)
            assert isinstance(data, dict)
            assert "status" in data
            assert "version" in data
