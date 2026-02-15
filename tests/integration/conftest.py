"""Pytest configuration for integration tests."""

import sys
from unittest.mock import MagicMock

# Mock optional dependencies before any src imports
_hvac_mock = MagicMock()
_hvac_mock.exceptions = MagicMock()
_hvac_mock.api = MagicMock()
_hvac_mock.api.auth_methods = MagicMock()
_hvac_mock.api.auth_methods.Kubernetes = MagicMock()

# NOTE: torch is NOT mocked because it's installed and mocking causes __spec__ errors

_mocked_modules = {
    "hvac": _hvac_mock,
    "hvac.exceptions": _hvac_mock.exceptions,
    "hvac.api": _hvac_mock.api,
    "hvac.api.auth_methods": _hvac_mock.api.auth_methods,
}

for mod_name, mock_obj in _mocked_modules.items():
    if mod_name not in sys.modules:
        sys.modules[mod_name] = mock_obj

import pytest


def pytest_configure(config):
    """Register custom markers."""
    config.addinivalue_line(
        "markers", "integration: mark test as integration test (requires mesh running)"
    )
    config.addinivalue_line("markers", "slow: mark test as slow (>10s execution time)")
