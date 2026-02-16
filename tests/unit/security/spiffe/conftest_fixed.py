"""
Fixed conftest for SPIFFE tests - removes pytest_mock dependency.
"""

import pytest

# Remove pytest_mock dependency - use unittest.mock instead
# This is a minimal conftest that doesn't require pytest_mock
