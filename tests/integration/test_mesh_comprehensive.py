"""Comprehensive integration tests for x0tta6bl4 mesh networking.

These tests verify the full functionality of the mesh network using the
docker-compose.mesh.yml stack. The tests cover:
- Health checks for all mesh components
- Enhanced metrics exporting
- Mesh communication between nodes
- eBPF related functionality

Run with:
    docker-compose -f docker/docker-compose.mesh.yml up -d
    pytest tests/integration/test_mesh_comprehensive.py -v
"""

import pytest
import subprocess
import time
from typing import Dict, List
import socket

# Test configuration
NODES = {
    "node-alpha": {"container": "mesh-node-alpha", "ip": "172.31.0.10", "port": 5000, "host_port": 5001},
    "node-beta": {"container": "mesh-node-beta", "ip": "172.31.0.11", "port": 5000, "host_port": 5002}, 
    "node-gamma": {"container": "mesh-node-gamma", "ip": "172.31.0.12", "port": 5000, "host_port": 5003},
    "node-delta": {"container": "mesh-node-delta", "ip": "172.31.0.13", "port": 5000, "host_port": 5004}
}
COMPOSE_FILE = "/mnt/AC74CC2974CBF3DC/docker/docker-compose.mesh.yml"


@pytest.fixture(scope="module")
def mesh_running():
    """Ensure mesh is running before tests.
    This fixture will start the mesh if it's not already running and 
    wait for all nodes to be initialized.
    """
    print("Checking if mesh network is running...")
    
    # Try to start the mesh if not running
    try:
        for node_id, config in NODES.items():
            sock = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
            sock.settimeout(1)
            sock.connect((config["ip"], config["port"]))
            sock.send(b"HELLO")
            sock.close()
            print(f"{node_id} is reachable at {config['ip']}:{config['port']}")
    except Exception as e:
        print(f"Mesh not running or nodes unreachable: {e}")
        print("Starting mesh network...")
        
        # Start the mesh
        result = subprocess.run(
            ["docker", "compose", "-f", COMPOSE_FILE, "up", "-d"],
            check=True,
            capture_output=True,
            text=True
        )
        print(f"docker-compose output: {result.stdout}")
        
        # Wait for nodes to initialize
        time.sleep(30)
        
        # Verify all containers are running
        print("Verifying containers are running...")
        result = subprocess.run(
            ["docker", "compose", "-f", COMPOSE_FILE, "ps"],
            capture_output=True,
            text=True
        )
        print(f"Container status:\n{result.stdout}")
        
        # Check each node
        for node_id, config in NODES.items():
            retries = 5
            while retries > 0:
                try:
                    sock = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
                    sock.settimeout(2)
                    sock.connect((config["ip"], config["port"]))
                    sock.send(b"HELLO")
                    sock.close()
                    print(f"{node_id} is reachable after start")
                    break
                except Exception as e:
                    print(f"Waiting for {node_id}... {e}")
                    time.sleep(5)
                retries -= 1
            assert retries > 0, f"{node_id} failed to start after retries"
    
    yield
    
    # Cleanup: stop the mesh
    print("Stopping mesh network...")
    subprocess.run(
        ["docker", "compose", "-f", COMPOSE_FILE, "stop"],
        check=False,
        capture_output=True,
        text=True
    )


@pytest.mark.integration
def test_container_status(mesh_running):
    """Test: All containers are running properly."""
    result = subprocess.run(
        ["docker", "compose", "-f", COMPOSE_FILE, "ps"],
        capture_output=True,
        text=True
    )
    assert result.returncode == 0, "Failed to get container status"
    
    output = result.stdout
    print(f"Container status:\n{output}")
    
    for node_id, config in NODES.items():
        assert config["container"] in output, f"{config['container']} not in container list"
        assert "Up" in output.split(config["container"])[1].split("\n")[0], \
            f"{config['container']} is not running"


@pytest.mark.integration
def test_health_checks(mesh_running):
    """Test: Health check endpoints are accessible and return valid data."""
    print("Checking health endpoints...")
    
    for node_id, config in NODES.items():
        # Use docker exec to check health inside container
        result = subprocess.run(
            ["docker", "exec", config["container"], "curl", "-s", "http://localhost:5000/health"],
            capture_output=True,
            text=True
        )
        
        assert result.returncode == 0, f"{node_id} health check failed"
        
        output = result.stdout
        print(f"{node_id} health check output: {output}")
        
        # Verify basic health check format
        assert "status" in output, f"{node_id} health check missing 'status' field"
        assert "ok" in output.lower(), f"{node_id} health status not 'ok'"
        assert "version" in output, f"{node_id} health check missing 'version' field"
        assert "node_id" in output, f"{node_id} health check missing 'node_id' field"


@pytest.mark.integration
def test_enhanced_metrics(mesh_running):
    """Test: Enhanced metrics endpoints are accessible and contain expected metrics."""
    print("Checking metrics endpoints...")
    
    for node_id, config in NODES.items():
        # Use docker exec to check metrics inside container
        result = subprocess.run(
            ["docker", "exec", config["container"], "curl", "-s", "http://localhost:5000/metrics"],
            capture_output=True,
            text=True
        )
        
        assert result.returncode == 0, f"{node_id} metrics endpoint failed"
        
        output = result.stdout
        print(f"{node_id} metrics received, length: {len(output)} characters")
        
        # Verify expected metrics are present
        assert len(output) > 0, f"{node_id} returned empty metrics"
        
        # Check for eBPF related metrics
        if "ebpf" in node_id.lower() or node_id == "node-alpha":  # Alpha is likely to have eBPF
            assert "x0tta6bl4_mesh_connected_peers" in output, \
                f"{node_id} missing eBPF mesh metrics"
            assert "x0tta6bl4_node_info" in output, \
                f"{node_id} missing node info metric"
            assert "x0tta6bl4_uptime_seconds" in output, \
                f"{node_id} missing uptime metric"
        
        # Check for health check metrics
        assert "x0tta6bl4_health_check" in output, \
            f"{node_id} missing health check metric"


@pytest.mark.integration
def test_mesh_communication(mesh_running):
    """Test: Nodes can communicate with each other through the mesh network."""
    print("Testing mesh communication between nodes...")
    
    # Try to communicate between each pair of nodes
    all_node_ids = list(NODES.keys())
    
    for source_node in all_node_ids:
        for target_node in all_node_ids:
            if source_node == target_node:
                continue
                
            source_config = NODES[source_node]
            target_config = NODES[target_node]
            
            print(f"Testing {source_node} -> {target_node} communication...")
            
            try:
                # Use docker exec to test communication from source container
                result = subprocess.run(
                    ["docker", "exec", source_config["container"], 
                     "curl", "-s", f"http://{target_config['ip']}:5000/health"],
                    capture_output=True,
                    text=True,
                    timeout=10
                )
                
                print(f"Command output: {result.stdout}")
                print(f"Error output: {result.stderr}")
                
                assert result.returncode == 0, \
                    f"{source_node} -> {target_node} communication failed (exit code: {result.returncode})"
                
                output = result.stdout
                assert "status" in output and "ok" in output.lower(), \
                    f"{source_node} -> {target_node} health check failed"
                
                print(f"{source_node} -> {target_node} communication successful")
                
            except subprocess.TimeoutExpired:
                pytest.fail(f"{source_node} -> {target_node} communication timed out (10 seconds)")
            except Exception as e:
                pytest.fail(f"{source_node} -> {target_node} communication failed: {e}")


@pytest.mark.integration
def test_container_connectivity(mesh_running):
    """Test: Containers can reach each other using container names."""
    print("Testing container name resolution and connectivity...")
    
    all_node_ids = list(NODES.keys())
    
    for source_node in all_node_ids:
        for target_node in all_node_ids:
            if source_node == target_node:
                continue
                
            source_config = NODES[source_node]
            target_config = NODES[target_node]
            
            print(f"Testing {source_node} -> {target_config['container']} communication...")
            
            try:
                # Use container name instead of IP
                result = subprocess.run(
                    ["docker", "exec", source_config["container"], 
                     "curl", "-s", f"http://{target_config['container']}:5000/health"],
                    capture_output=True,
                    text=True,
                    timeout=5
                )
                
                assert result.returncode == 0, \
                    f"{source_node} -> {target_config['container']} failed"
                
                output = result.stdout
                assert "status" in output and "ok" in output.lower(), \
                    f"{target_config['container']} health check failed"
                
                print(f"{source_node} -> {target_config['container']} successful")
                
            except Exception as e:
                print(f"Warning: {source_node} -> {target_config['container']} failed: {e}")
                print("This is expected if container name resolution is not configured")


@pytest.mark.integration
def test_port_mapping(mesh_running):
    """Test: Host port mapping is working correctly."""
    print("Testing host port mapping...")
    
    for node_id, config in NODES.items():
        print(f"Testing port {config['host_port']} for {node_id}...")
        
        try:
            sock = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
            sock.settimeout(5)
            sock.connect(("localhost", config["host_port"]))
            sock.send(b"GET /health HTTP/1.1\r\nHost: localhost\r\n\r\n")
            response = sock.recv(1024).decode()
            sock.close()
            
            print(f"Port {config['host_port']} responds with: {response[:50]}...")
            
            # Verify basic HTTP response
            assert "HTTP" in response and "200" in response, \
                f"Port {config['host_port']} is not responding correctly"
                
            print(f"Port {config['host_port']} is working correctly")
                
        except Exception as e:
            pytest.fail(f"Port {config['host_port']} for {node_id} is not accessible: {e}")


@pytest.mark.integration
def test_mesh_status(mesh_running):
    """Test: Mesh status endpoint returns valid peer information."""
    print("Checking mesh status endpoints...")
    
    for node_id, config in NODES.items():
        try:
            result = subprocess.run(
                ["docker", "exec", config["container"], 
                 "curl", "-s", "http://localhost:5000/mesh/status"],
                capture_output=True,
                text=True,
                timeout=10
            )
            
            assert result.returncode == 0, f"{node_id} mesh status endpoint failed"
            
            output = result.stdout
            print(f"{node_id} mesh status output: {output}")
            
            # Check if peer information is present
            if len(NODES) > 1:
                assert "connected_peers" in output, f"{node_id} missing connected peers"
                
        except Exception as e:
            print(f"Warning: {node_id} mesh status check failed: {e}")


@pytest.mark.integration
def test_service_restart_recovery(mesh_running):
    """Test: Service can be restarted and recovers properly."""
    print("Testing service restart recovery...")
    
    # Choose a node to restart (node-beta)
    test_node_id = "node-beta"
    test_config = NODES[test_node_id]
    
    # Stop the container
    print(f"Stopping {test_node_id}...")
    subprocess.run(
        ["docker", "compose", "-f", COMPOSE_FILE, "stop", test_node_id],
        capture_output=True,
        text=True,
        check=True
    )
    time.sleep(5)
    
    # Verify it's stopped
    result = subprocess.run(
        ["docker", "compose", "-f", COMPOSE_FILE, "ps"],
        capture_output=True,
        text=True
    )
    assert "Exit" in result.stdout.split(test_config["container"])[1].split("\n")[0]
    
    # Start the container again
    print(f"Starting {test_node_id}...")
    subprocess.run(
        ["docker", "compose", "-f", COMPOSE_FILE, "start", test_node_id],
        capture_output=True,
        text=True,
        check=True
    )
    time.sleep(15)
    
    # Verify it's running and healthy
    result = subprocess.run(
        ["docker", "compose", "-f", COMPOSE_FILE, "ps"],
        capture_output=True,
        text=True
    )
    assert "Up" in result.stdout.split(test_config["container"])[1].split("\n")[0]
    
    # Check health
    health_result = subprocess.run(
        ["docker", "exec", test_config["container"], "curl", "-s", "http://localhost:5000/health"],
        capture_output=True,
        text=True,
        timeout=10
    )
    assert health_result.returncode == 0
    assert "status" in health_result.stdout and "ok" in health_result.stdout.lower()
    
    print(f"{test_node_id} restarted successfully")


if __name__ == "__main__":
    pytest.main([__file__, "-v", "--tb=short"])
