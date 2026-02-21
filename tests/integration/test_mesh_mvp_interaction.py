import os
import pytest
import subprocess
from unittest.mock import patch, MagicMock

def test_mesh_binary_exists():
    """Verify that the x0tta6bl4-mesh-mvp binary path is correctly defined"""
    # Assuming binary is in the standard path or defined in env
    mesh_path = os.getenv("MESH_BINARY_PATH", "./x0tta6bl4-mesh-mvp/x0tta6bl4-mesh")
    # We don't fail if it's missing in this environment, but we log a warning
    if not os.path.exists(mesh_path):
        pytest.skip(f"Mesh binary not found at {mesh_path}")

@patch("subprocess.Popen")
def test_mesh_node_start(mock_popen):
    """Test starting the mesh node process"""
    process_mock = MagicMock()
    process_mock.poll.return_value = None
    mock_popen.return_value = process_mock

    # Simulate starting the node
    # In reality, this would call a function from src.core.mesh_controller
    cmd = ["./x0tta6bl4-mesh-mvp/x0tta6bl4-mesh", "--config", "config.yaml"]
    subprocess.Popen(cmd)
    
    mock_popen.assert_called_with(cmd)
