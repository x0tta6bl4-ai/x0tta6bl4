import os
import pytest
import pytest_mock # Explicitly import pytest_mock

@pytest.fixture(autouse=True)
def force_mock_spiffe_sdk_env():
    """Forces the SPIFFE WorkloadAPIClient to run in mock mode during tests."""
    os.environ["X0TTA6BL4_FORCE_MOCK_SPIFFE"] = "true"
    yield
    del os.environ["X0TTA6BL4_FORCE_MOCK_SPIFFE"]

@pytest.fixture(autouse=True)
def mock_spire_agent_manager_bin(mocker):
    """Mocks the _find_spire_binary method to prevent FileNotFoundError."""
    mocker.patch('src.security.spiffe.agent.manager.SPIREAgentManager._find_spire_binary', return_value="/usr/local/bin/spire-agent")
    mocker.patch('src.security.spiffe.agent.manager.SPIREAgentManager._run_subprocess_with_timeout', return_value=(0, "mocked agent output", ""))