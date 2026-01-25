"""Pytest configuration for integration tests."""

import pytest


def pytest_configure(config):
    """Register custom markers."""
    config.addinivalue_line(
        "markers", "integration: mark test as integration test (requires mesh running)"
    )
    config.addinivalue_line(
        "markers", "slow: mark test as slow (>10s execution time)"
    )
