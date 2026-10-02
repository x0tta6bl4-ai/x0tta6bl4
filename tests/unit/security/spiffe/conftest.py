from unittest.mock import patch

import pytest

# pytest_mock not required - using unittest.mock instead


@pytest.fixture(autouse=True)
def force_mock_spiffe_sdk_env(monkeypatch):
    """Forces the SPIFFE WorkloadAPIClient to run in mock mode during tests."""
    monkeypatch.setenv("X0TTA6BL4_FORCE_MOCK_SPIFFE", "true")


@pytest.fixture(autouse=True)
def mock_spire_agent_manager_bin():
    """Mocks the SPIRE agent manager to prevent FileNotFoundError."""
    # Only patch if the method exists
    try:
        with patch(
            "src.security.spiffe.agent.manager.SPIREAgentManager._find_spire_binary",
            return_value="/usr/local/bin/spire-agent",
            create=True,
        ):
            yield
    except AttributeError:
        # Method doesn't exist, skip patching
        yield


@pytest.fixture
def mock_spire_executable(monkeypatch):
    """Explicit executable lookup for tests which already mock subprocess calls."""
    from src.core.security import subprocess_validator
    original = subprocess_validator.shutil.which

    def which(command):
        if command in ("spire-agent", "spire-server",
                       "/usr/local/bin/spire-agent", "/usr/local/bin/spire-server"):
            return command if command.startswith("/") else f"/usr/local/bin/{command}"
        return original(command)

    monkeypatch.setattr(subprocess_validator.shutil, "which", which)
