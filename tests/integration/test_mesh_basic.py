"""Minimal integration tests for x0tta6bl4 multi-node API endpoints.

These tests verify basic multi-node REST API functionality without
dependencies on Yggdrasil, Prometheus, or sudo/network namespaces.

Run with minimal compose stack:
    docker compose -f docker-compose.minimal.yml up -d
    pytest tests/integration/test_mesh_basic.py -v
"""

import subprocess
import time
from typing import Dict

import pytest
import requests

# Test configuration
NODES = {
    "node-a": "http://localhost:8000",
    "node-b": "http://localhost:8001",
    "node-c": "http://localhost:8002",
}
COMPOSE_FILE = "/mnt/AC74CC2974CBF3DC/docker-compose.minimal.yml"


@pytest.fixture(scope="module")
def mesh_running():
    """Verify minimal mesh is running before tests."""
    for node_id, url in NODES.items():
        try:
            response = requests.get(f"{url}/health", timeout=5)
            assert (
                response.status_code == 200
            ), f"{node_id} not healthy: {response.status_code}"
        except requests.RequestException as e:
            pytest.skip(f"Mesh not running: {node_id} unreachable ({e})")
    yield
    # Cleanup: ensure all nodes are running after tests
    subprocess.run(
        [
            "docker",
            "compose",
            "-f",
            COMPOSE_FILE,
            "start",
            "node-a",
            "node-b",
            "node-c",
        ],
        check=False,
    )


@pytest.mark.integration
def test_all_nodes_healthy(mesh_running):
    """Test: All 3 nodes respond to /health with 200 OK."""
    for node_id, url in NODES.items():
        response = requests.get(f"{url}/health", timeout=5)
        assert (
            response.status_code == 200
        ), f"{node_id} not returning 200: {response.status_code}"
        data = response.json()
        assert data["status"] == "ok", f"{node_id} status not ok: {data}"
        assert "version" in data, f"{node_id} missing version in /health"


@pytest.mark.integration
def test_api_endpoints_available(mesh_running):
    """Test: All REST API endpoints respond correctly on each node."""
    endpoints = ["/health"]

    for node_id, base_url in NODES.items():
        for endpoint in endpoints:
            response = requests.get(f"{base_url}{endpoint}", timeout=5)
            assert (
                response.status_code == 200
            ), f"{node_id} endpoint {endpoint} failed: {response.status_code}"

            # Verify response is valid JSON
            try:
                data = response.json()
                assert isinstance(
                    data, dict
                ), f"{node_id} {endpoint} not returning JSON object"
            except ValueError:
                pytest.fail(f"{node_id} {endpoint} returned invalid JSON")


@pytest.mark.integration
def test_node_restart_recovery(mesh_running):
    """Test: Node can be stopped and restarted without errors."""
    # Stop node-b
    print("\n[TEST] Stopping node-b...")
    result = subprocess.run(
        ["docker", "compose", "-f", COMPOSE_FILE, "stop", "node-b"],
        capture_output=True,
        text=True,
    )
    assert result.returncode == 0, f"Failed to stop node-b: {result.stderr}"
    time.sleep(3)

    # Verify node-b is unreachable
    try:
        requests.get(f"{NODES['node-b']}/health", timeout=2)
        pytest.fail("node-b should be unreachable after stop")
    except requests.RequestException:
        pass  # Expected

    # Verify other nodes still healthy
    for node_id in ["node-a", "node-c"]:
        response = requests.get(f"{NODES[node_id]}/health", timeout=5)
        assert response.status_code == 200, f"{node_id} unhealthy after node-b stopped"

    # Restart node-b
    print("[TEST] Restarting node-b...")
    result = subprocess.run(
        ["docker", "compose", "-f", COMPOSE_FILE, "start", "node-b"],
        capture_output=True,
        text=True,
    )
    assert result.returncode == 0, f"Failed to start node-b: {result.stderr}"
    time.sleep(5)  # Allow node to initialize

    # Verify node-b is healthy again
    response = requests.get(f"{NODES['node-b']}/health", timeout=10)
    assert response.status_code == 200, "node-b not healthy after restart"
    data = response.json()
    assert data["status"] == "ok", f"node-b status not ok after restart: {data}"


@pytest.mark.integration
def test_concurrent_requests(mesh_running):
    """Test: All nodes can handle multiple concurrent requests."""
    import concurrent.futures

    def fetch_health(url: str) -> int:
        response = requests.get(f"{url}/health", timeout=5)
        return response.status_code

    with concurrent.futures.ThreadPoolExecutor(max_workers=10) as executor:
        # Send 10 requests to each node concurrently (30 total)
        futures = []
        for _ in range(10):
            for url in NODES.values():
                futures.append(executor.submit(fetch_health, url))

        # Verify all requests succeeded
        for future in concurrent.futures.as_completed(futures):
            status = future.result()
            assert status == 200, f"Concurrent request failed: {status}"


if __name__ == "__main__":
    pytest.main([__file__, "-v", "--tb=short"])
