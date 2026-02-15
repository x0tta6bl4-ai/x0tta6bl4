import logging
import os
import shutil
import signal
import subprocess
import tempfile
import time
from datetime import datetime, timedelta
from pathlib import Path
from unittest.mock import MagicMock, mock_open, patch

import pytest

from src.security.spiffe.agent.manager import (AttestationStrategy,
                                               SPIREAgentManager,
                                               WorkloadEntry)


@pytest.fixture(autouse=True)
def setup_env_vars():
    """Set up and tear down environment variables for each test."""
    original_env = os.environ.copy()
    yield
    os.environ.clear()
    os.environ.update(original_env)


@pytest.fixture
def mock_path_factory(mocker):
    """Mocks pathlib.Path constructor and returns a factory for mock Path objects."""
    mock_paths = {}

    def _path_factory(path_str):
        if path_str not in mock_paths:
            instance = MagicMock(spec=Path)
            instance.exists.return_value = True
            instance.mkdir.return_value = None
            instance.unlink.return_value = None
            instance.write_text.return_value = None
            instance.__str__.return_value = str(path_str)
            mock_paths[path_str] = instance
        return mock_paths[path_str]

    mocker.patch("pathlib.Path", side_effect=_path_factory)
    return _path_factory


@pytest.fixture
def mock_subprocess(mocker):
    """Mocks subprocess.Popen, subprocess.run, os.killpg, and os.getpgid."""
    mock_popen = MagicMock(spec=subprocess.Popen)
    mock_popen.pid = 12345
    mock_popen.poll.return_value = None

    mock_run_result = MagicMock(spec=subprocess.CompletedProcess)
    mock_run_result.returncode = 0
    mock_run_result.stdout = "Success"
    mock_run_result.stderr = ""

    mock_subprocess_popen = mocker.patch(
        "src.security.spiffe.agent.manager.subprocess.Popen", return_value=mock_popen
    )
    mock_subprocess_run = mocker.patch(
        "src.security.spiffe.agent.manager.subprocess.run", return_value=mock_run_result
    )
    mock_shutil_which = mocker.patch(
        "src.security.spiffe.agent.manager.shutil.which",
        return_value="/usr/bin/spire-agent",
    )
    mock_os_killpg = mocker.patch("src.security.spiffe.agent.manager.os.killpg")
    mock_os_getpgid = mocker.patch(
        "src.security.spiffe.agent.manager.os.getpgid", return_value=12345
    )

    return {
        "popen": mock_subprocess_popen,
        "run": mock_subprocess_run,
        "which": mock_shutil_which,
        "killpg": mock_os_killpg,
        "getpgid": mock_os_getpgid,
        "popen_instance": mock_popen,
        "run_result_instance": mock_run_result,
    }


@pytest.fixture
def manager(mocker, mock_subprocess, mock_path_factory):
    """Fixture for SPIREAgentManager."""
    mocker.patch(
        "src.security.spiffe.agent.manager.shutil.which",
        side_effect=lambda x: f"/usr/bin/{x}",
    )

    config_path_str = "/tmp/agent.conf"
    socket_path_str = "/tmp/agent.sock"

    mock_config_path = mock_path_factory(config_path_str)
    mock_socket_path = mock_path_factory(socket_path_str)

    mock_config_path.exists.return_value = True
    mock_socket_path.exists.side_effect = [False, True]

    manager_instance = SPIREAgentManager(
        config_path=mock_config_path, socket_path=mock_socket_path
    )

    mocker.patch(
        "tempfile.mkstemp",
        return_value=(None, str(mock_path_factory("/tmp/generated.conf"))),
    )
    mocker.patch("os.fdopen", MagicMock())

    return manager_instance


# --- SPIREAgentManager.__init__ Tests ---


def test_init_success(manager):
    """Test successful initialization."""
    assert str(manager.config_path) == "/tmp/agent.conf"
    assert str(manager.socket_path) == "/tmp/agent.sock"
    assert manager._spire_agent_bin == "/usr/bin/spire-agent"
    assert manager._spire_server_bin == "/usr/bin/spire-server"


def test_init_binaries_not_found(mocker):
    """Test initialization when spire binaries are not found."""
    mocker.patch("src.security.spiffe.agent.manager.shutil.which", return_value=None)
    with pytest.raises(FileNotFoundError, match="spire-agent not found"):
        SPIREAgentManager()


def test_init_binaries_from_env(mocker):
    """Test initialization with binary paths from environment variables."""
    mocker.patch("src.security.spiffe.agent.manager.shutil.which", return_value=None)
    mocker.patch("os.path.isfile", return_value=True)

    os.environ["SPIRE_SPIRE_AGENT_BIN_PATH"] = "/opt/agent/bin/spire-agent"
    os.environ["SPIRE_SPIRE_SERVER_BIN_PATH"] = "/opt/server/bin/spire-server"
    manager = SPIREAgentManager()
    assert manager._spire_agent_bin == "/opt/agent/bin/spire-agent"
    assert manager._spire_server_bin == "/opt/server/bin/spire-server"


# --- SPIREAgentManager.start() Tests ---


@pytest.mark.asyncio
async def test_start_success(manager, mock_subprocess, mocker):
    """Test successful agent start."""
    manager.socket_path.exists.side_effect = [False, True]

    mocker.patch("time.sleep", return_value=None)

    result = manager.start()
    mock_subprocess["popen"].assert_called_once()
    assert manager.agent_process == mock_subprocess["popen_instance"]
    manager.socket_path.exists.assert_called()
    assert result is True


@pytest.mark.asyncio
async def test_start_already_running(manager, mock_subprocess):
    """Test starting agent when it's already running."""
    manager.agent_process = mock_subprocess["popen_instance"]
    result = manager.start()
    mock_subprocess["popen"].assert_not_called()
    assert result is True


@pytest.mark.asyncio
async def test_start_socket_timeout(manager, mock_subprocess, mocker):
    """Test agent start fails due to socket timeout."""
    manager.socket_path.exists.side_effect = [
        False
    ] * 20  # Force exists() to always return False
    mocker.patch("time.sleep", return_value=None)

    mock_manager_stop = mocker.patch.object(manager, "stop")

    result = manager.start()
    mock_subprocess["popen"].assert_called_once()
    mock_manager_stop.assert_called_once()
    assert result is False


@pytest.mark.asyncio
async def test_start_exception(manager, mock_subprocess, caplog):
    """Test agent start fails due to an exception."""
    mock_subprocess["popen"].side_effect = Exception(
        "Test exception"
    )  # Fixed: Apply side_effect to the patched class
    with caplog.at_level(logging.ERROR):
        result = manager.start()
        assert "Failed to start SPIRE Agent" in caplog.text
        assert result is False


# --- SPIREAgentManager.stop() Tests ---


def test_stop_success(manager, mock_subprocess, mocker):
    """Test successful agent stop."""
    manager.agent_process = mock_subprocess["popen_instance"]
    mock_subprocess["popen_instance"].poll.side_effect = [None, 0]
    mocker.patch("time.sleep", return_value=None)

    result = manager.stop()
    mock_subprocess["killpg"].assert_called_once_with(12345, signal.SIGTERM)
    assert manager.agent_process is None
    assert manager._generated_config_path is None
    assert result is True


def test_stop_no_running_agent(manager):
    """Test stopping when no agent is running."""
    manager.agent_process = None
    result = manager.stop()
    assert result is True


def test_stop_sigkill(manager, mock_subprocess, mocker):
    """Test agent stop sends SIGKILL if graceful stop fails."""
    manager.agent_process = mock_subprocess["popen_instance"]
    mock_subprocess["popen_instance"].poll.return_value = None
    mock_subprocess["popen_instance"].wait.return_value = 0
    mocker.patch("time.sleep", return_value=None)

    result = manager.stop()
    mock_subprocess["killpg"].assert_called_with(12345, signal.SIGKILL)
    assert result is True


# --- SPIREAgentManager.attest_node() Tests ---


def test_attest_node_join_token_success(manager, mock_subprocess, mocker):
    """Test attest_node with JOIN_TOKEN strategy."""
    mocker.patch.object(manager, "start", return_value=True)
    mocker.patch.object(manager, "stop", return_value=True)

    result = manager.attest_node(
        AttestationStrategy.JOIN_TOKEN, token="test-join-token"
    )
    assert manager._join_token == "test-join-token"
    assert manager.agent_process is None
    assert result is True


def test_attest_node_join_token_restart_agent(manager, mock_subprocess, mocker):
    """Test attest_node with JOIN_TOKEN restarts agent if running."""
    manager.agent_process = mock_subprocess["popen_instance"]
    mocker.patch.object(manager, "start", return_value=True)
    mocker.patch.object(manager, "stop", return_value=True)

    result = manager.attest_node(
        AttestationStrategy.JOIN_TOKEN, token="test-join-token"
    )
    manager.stop.assert_called_once()
    manager.start.assert_called_once()
    assert result is True


def test_attest_node_join_token_missing_token(manager):
    """Test attest_node with JOIN_TOKEN and missing token."""
    with pytest.raises(
        ValueError, match="join_token strategy requires 'token' parameter"
    ):
        manager.attest_node(AttestationStrategy.JOIN_TOKEN)


def test_attest_node_unimplemented_strategy(manager, caplog):
    """Test attest_node with an unimplemented strategy."""
    with caplog.at_level(logging.WARNING):
        result = manager.attest_node(AttestationStrategy.AWS_IID)
        assert "Attestation strategy aws_iid is not fully implemented" in caplog.text
        assert result is False


# --- SPIREAgentManager.register_workload() Tests ---


def test_register_workload_success(manager, mock_subprocess):
    """Test successful workload registration."""
    entry = WorkloadEntry(
        "spiffe://test.mesh/workload/app",
        "spiffe://test.mesh/node/agent",
        {"unix:uid": "1000"},
    )
    result = manager.register_workload(entry)
    mock_subprocess["run"].assert_called_once_with(
        [
            "/usr/bin/spire-server",
            "entry",
            "create",
            "-spiffeID",
            "spiffe://test.mesh/workload/app",
            "-parentID",
            "spiffe://test.mesh/node/agent",
            "-ttl",
            "3600",
            "-selector",
            "unix:uid:1000",
        ],
        capture_output=True,
        check=True,
        text=True,
        timeout=30,
    )
    assert result is True


def test_register_workload_spire_server_not_found(manager, mock_subprocess):
    """Test workload registration when spire-server binary is not found."""
    mock_subprocess["run"].side_effect = FileNotFoundError
    entry = WorkloadEntry(
        "spiffe://test.mesh/workload/app", "spiffe://test.mesh/node/agent", {}
    )
    result = manager.register_workload(entry)
    assert result is False


def test_register_workload_called_process_error(manager, mock_subprocess, caplog):
    """Test workload registration fails due to subprocess.CalledProcessError."""
    mock_subprocess["run"].side_effect = subprocess.CalledProcessError(
        1, "cmd", stderr="Error output"
    )  # Fixed: Apply side_effect to the patched function
    with caplog.at_level(logging.ERROR):
        result = manager.register_workload(
            WorkloadEntry(
                "spiffe://test.mesh/workload/app", "spiffe://test.mesh/node/agent", {}
            )
        )
        assert "Failed to register workload" in caplog.text
        assert result is False


# --- SPIREAgentManager.list_workloads() Tests ---


def test_list_workloads_success(manager, mock_subprocess):
    """Test successful listing of workloads."""
    mock_subprocess[
        "run_result_instance"
    ].stdout = """
Entry ID: entry-id-1
SPIFFE ID: spiffe://test.mesh/workload/app1
Parent ID: spiffe://test.mesh/node/agent1
TTL: 3600s
Selector: unix:uid:1000
"""
    workloads = manager.list_workloads()
    assert len(workloads) == 1
    assert workloads[0].spiffe_id == "spiffe://test.mesh/workload/app1"
    assert workloads[0].selectors == {"unix:uid": "1000"}


def test_list_workloads_spire_server_not_found(manager, mock_subprocess):
    """Test listing workloads when spire-server binary is not found."""
    manager._spire_server_bin = None
    mock_subprocess["run"].side_effect = FileNotFoundError
    result = manager.list_workloads()
    assert result == []


def test_list_workloads_timeout(manager, mock_subprocess):
    """Test listing workloads times out."""
    mock_subprocess["run"].side_effect = subprocess.TimeoutExpired("cmd", 30)
    result = manager.list_workloads()
    assert result == []


# --- SPIREAgentManager.health_check() Tests ---


def test_health_check_healthy(manager, mock_subprocess):  # Removed mocker for this test
    """Test health check when agent is healthy."""
    manager.agent_process = mock_subprocess["popen_instance"]
    manager.socket_path.exists.return_value = True
    result = manager.health_check()
    mock_subprocess["run"].assert_called_once_with(
        [
            "/usr/bin/spire-agent",
            "healthcheck",
            "-socketPath",
            str(manager.socket_path),
        ],
        capture_output=True,
        timeout=5,
    )
    assert result is True


def test_health_check_no_process(manager):
    """Test health check when agent process is not running."""
    manager.agent_process = None
    result = manager.health_check()
    assert result is False


def test_health_check_no_socket(manager, mock_subprocess):
    """Test health check when agent socket does not exist."""
    manager.agent_process = mock_subprocess["popen_instance"]
    manager.socket_path.exists.return_value = False
    result = manager.health_check()
    assert result is False


def test_health_check_command_fails(
    manager, mock_subprocess, caplog
):  # Removed mocker for this test
    """Test health check when healthcheck command fails."""
    manager.agent_process = mock_subprocess["popen_instance"]
    manager.socket_path.exists.return_value = True
    mock_subprocess["run"].side_effect = subprocess.CalledProcessError(
        1, "cmd", stderr="Healthcheck failed"
    )  # Apply side_effect to the patched function
    with caplog.at_level(logging.ERROR):
        result = manager.health_check()
        mock_subprocess["run"].assert_called_once_with(
            [
                "/usr/bin/spire-agent",
                "healthcheck",
                "-socketPath",
                str(manager.socket_path),
            ],
            capture_output=True,
            timeout=5,
        )
        assert "SPIRE Agent healthcheck command failed" in caplog.text
        assert result is True


# --- SPIREAgentManager._cleanup() Tests ---


def test_cleanup_removes_generated_config(manager, mocker):
    """Test _cleanup removes generated config file."""
    mock_config_path = MagicMock(spec=Path)
    mock_config_path.exists.return_value = True
    mock_config_path.unlink.return_value = None
    manager._generated_config_path = mock_config_path

    manager._cleanup()
    mock_config_path.unlink.assert_called_once()
    assert manager._generated_config_path is None
    assert manager.agent_process is None


def test_cleanup_no_generated_config(manager):
    """Test _cleanup with no generated config."""
    manager._generated_config_path = None
    manager._cleanup()
    # No exception, nothing happens
