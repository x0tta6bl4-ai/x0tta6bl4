import os
import pytest
from unittest.mock import patch, MagicMock

# pytest_mock not required - using unittest.mock instead

@pytest.fixture(autouse=True)
def force_mock_spiffe_sdk_env():
    """Forces the SPIFFE WorkloadAPIClient to run in mock mode during tests."""
    os.environ["X0TTA6BL4_FORCE_MOCK_SPIFFE"] = "true"
    yield
    if "X0TTA6BL4_FORCE_MOCK_SPIFFE" in os.environ:
        del os.environ["X0TTA6BL4_FORCE_MOCK_SPIFFE"]

@pytest.fixture(autouse=True)
def mock_spire_agent_manager_bin():
    """Mocks the SPIRE agent manager to prevent FileNotFoundError."""
    # Only patch if the method exists
    try:
        with patch('src.security.spiffe.agent.manager.SPIREAgentManager._find_spire_binary', return_value="/usr/local/bin/spire-agent", create=True):
            yield
    except AttributeError:
        # Method doesn't exist, skip patching
        yield