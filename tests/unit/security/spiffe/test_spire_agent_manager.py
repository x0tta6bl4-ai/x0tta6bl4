import os
import shutil
import subprocess
from pathlib import Path
from unittest.mock import patch, MagicMock, ANY

import pytest

from src.security.spiffe.agent.manager import SPIREAgentManager, WorkloadEntry, AttestationStrategy

MOCK_AGENT_BIN = "/usr/bin/spire-agent"
MOCK_SERVER_BIN = "/usr/bin/spire-server"


@pytest.fixture
def mock_spire_env():
    """Fixture to mock the presence of SPIRE binaries and subprocess calls."""
    with patch('shutil.which') as mock_which, \
         patch('subprocess.Popen') as mock_popen, \
         patch('subprocess.run') as mock_run, \
         patch('os.getpgid') as mock_getpgid, \
         patch('os.killpg') as mock_killpg:

        def which_side_effect(binary_name):
            if binary_name == 'spire-agent':
                return MOCK_AGENT_BIN
            if binary_name == 'spire-server':
                return MOCK_SERVER_BIN
            return None
        
        mock_which.side_effect = which_side_effect
        
        # Mock Popen process
        mock_process = MagicMock()
        mock_process.pid = 1234
        mock_process.poll.return_value = None  # Indicates process is running
        mock_popen.return_value = mock_process
        
        # Mock getpgid to avoid ProcessLookupError
        mock_getpgid.return_value = 1234
        
        # Mock Run result
        mock_run_result = MagicMock()
        mock_run_result.returncode = 0
        mock_run_result.stdout = "Entry created"
        mock_run.return_value = mock_run_result

        yield {
            "which": mock_which,
            "popen": mock_popen,
            "run": mock_run,
            "getpgid": mock_getpgid,
            "killpg": mock_killpg,
            "process": mock_process,
        }

def test_init_fails_if_binary_not_found():
    """Test that SPIREAgentManager fails to initialize if binaries are missing."""
    with patch('shutil.which', return_value=None):
        with pytest.raises(FileNotFoundError, match="spire-agent not found"):
            SPIREAgentManager()

def test_start_agent_success(mock_spire_env, tmp_path):
    """Test the successful start of the SPIRE agent."""
    socket_path = tmp_path / "agent.sock"
    
    # Simulate the socket appearing after the process starts
    def touch_socket(*args, **kwargs):
        socket_path.parent.mkdir(parents=True, exist_ok=True)
        socket_path.touch()
        return mock_spire_env["process"]

    mock_spire_env["popen"].side_effect = touch_socket

    mgr = SPIREAgentManager(socket_path=socket_path)
    assert mgr.start() is True
    
    mock_spire_env["popen"].assert_called_once_with(
        [MOCK_AGENT_BIN, "run", "-config", ANY],
        stdout=subprocess.PIPE,
        stderr=subprocess.PIPE,
        env=ANY,
        preexec_fn=os.setsid,
    )

def test_start_agent_timeout(mock_spire_env, tmp_path):
    """Test that starting the agent fails if the socket does not appear."""
    socket_path = tmp_path / "agent.sock"
    
    # Ensure socket never gets created
    if socket_path.exists():
        socket_path.unlink()

    mgr = SPIREAgentManager(socket_path=socket_path)
    
    # Mock time.sleep to speed up the test
    with patch('time.sleep'):
      assert mgr.start() is False
    
    mock_spire_env["popen"].assert_called_once()
    # Assert that stop is called, which in turn calls killpg
    mock_spire_env["killpg"].assert_called()

def test_stop_agent(mock_spire_env, tmp_path):
    """Test stopping a running agent."""
    mgr = SPIREAgentManager(socket_path=tmp_path / "agent.sock")
    mgr.agent_process = mock_spire_env["process"] # Pretend it's running

    assert mgr.stop() is True
    mock_spire_env["killpg"].assert_called()


def test_register_workload_success(mock_spire_env, tmp_path):
    """Test successful workload registration."""
    mgr = SPIREAgentManager(socket_path=tmp_path / "agent.sock")
    entry = WorkloadEntry(
        spiffe_id='spiffe://x0tta6bl4.mesh/workload/api',
        parent_id='spiffe://x0tta6bl4.mesh/node/n1',
        selectors={'unix:uid': '1000'},
        ttl=60
    )
    
    assert mgr.register_workload(entry) is True
    
    expected_cmd = [
        MOCK_SERVER_BIN, "entry", "create",
        "-spiffeID", "spiffe://x0tta6bl4.mesh/workload/api",
        "-parentID", "spiffe://x0tta6bl4.mesh/node/n1",
        "-ttl", "60",
        "-selector", "unix:uid:1000",
    ]
    mock_spire_env["run"].assert_called_once_with(
        expected_cmd,
        capture_output=True,
        check=True,
        text=True,
        timeout=30,
    )

def test_register_workload_fails(mock_spire_env, tmp_path):
    """Test that workload registration returns False on command failure."""
    mock_spire_env["run"].side_effect = subprocess.CalledProcessError(1, "cmd", stderr="entry already exists")
    
    mgr = SPIREAgentManager(socket_path=tmp_path / "agent.sock")
    entry = WorkloadEntry(
        spiffe_id='spiffe://x0tta6bl4.mesh/workload/api',
        parent_id='spiffe://x0tta6bl4.mesh/node/n1',
        selectors={'unix:uid': '1000'}
    )
    
    assert mgr.register_workload(entry) is False

def test_attest_node_sets_token_if_not_running(mock_spire_env, tmp_path):
    """Test that attest_node just sets the token if the agent isn't running."""
    mgr = SPIREAgentManager(socket_path=tmp_path / "agent.sock")
    mgr.agent_process = None # Ensure agent is not running

    token = "test_token_123"
    result = mgr.attest_node(AttestationStrategy.JOIN_TOKEN, token=token)

    assert result is True
    assert mgr._join_token == token
    # Assert that start/stop were NOT called
    mock_spire_env["popen"].assert_not_called()
    mock_spire_env["killpg"].assert_not_called()

def test_attest_node_restarts_running_agent(mock_spire_env, tmp_path):
    """Test that attest_node restarts a running agent to apply the new token."""
    mgr = SPIREAgentManager(socket_path=tmp_path / "agent.sock")
    mgr.agent_process = mock_spire_env["process"] # Pretend agent is running

    # Make start() successful
    socket_path = tmp_path / "agent.sock"
    def touch_socket(*args, **kwargs):
        socket_path.parent.mkdir(parents=True, exist_ok=True)
        socket_path.touch()
        return mock_spire_env["process"]
    mock_spire_env["popen"].side_effect = touch_socket
    
    token = "test_token_456"
    result = mgr.attest_node(AttestationStrategy.JOIN_TOKEN, token=token)

    assert result is True
    assert mgr._join_token == token
    # Assert that stop and start were called
    mock_spire_env["killpg"].assert_called()
    mock_spire_env["popen"].assert_called_once()

def test_start_uses_attest_token(mock_spire_env, tmp_path):
    """Test that start() uses the token set by attest_node."""
    mgr = SPIREAgentManager(socket_path=tmp_path / "agent.sock")
    token = "my_special_token"
    
    # 1. Attest first (while agent is not running)
    mgr.attest_node(AttestationStrategy.JOIN_TOKEN, token=token)

    # 2. Then start the agent
    mgr.start()

    # 3. Check the environment passed to Popen
    mock_spire_env["popen"].assert_called_once()
    call_args = mock_spire_env["popen"].call_args
    assert 'env' in call_args.kwargs
    subprocess_env = call_args.kwargs['env']
    assert subprocess_env.get("SPIRE_JOIN_TOKEN") == token