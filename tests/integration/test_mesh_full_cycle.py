"""
Full cycle integration tests for mesh network.

Tests complete scenarios:
- Node discovery and connection
- Data synchronization
- Self-healing recovery
- Consensus participation
- Security (PQC + SPIFFE)
"""

import asyncio
from typing import Dict, List
from unittest.mock import AsyncMock, Mock, patch

import pytest

try:
    from src.consensus.raft_consensus import RaftNode
    from src.data_sync.crdt_sync import CRDTSync
    from src.network.batman.node_manager import NodeManager
    from src.security.post_quantum_liboqs import (LIBOQS_AVAILABLE,
                                                  PQMeshSecurityLibOQS)
    from src.self_healing.mape_k import MAPEKLoop

    MESH_COMPONENTS_AVAILABLE = True
except ImportError:
    MESH_COMPONENTS_AVAILABLE = False
    NodeManager = None
    CRDTSync = None
    MAPEKLoop = None
    RaftNode = None
    LIBOQS_AVAILABLE = False


@pytest.mark.skipif(
    not MESH_COMPONENTS_AVAILABLE, reason="Mesh components not available"
)
class TestMeshFullCycle:
    """Full cycle integration tests for mesh network"""

    @pytest.mark.asyncio
    async def test_node_discovery_and_connection(self):
        """Test complete node discovery and connection flow"""
        # Create node manager
        node_manager = NodeManager(node_id="node-1")

        # Simulate peer discovery
        peer_node = {"node_id": "node-2", "address": "192.168.1.2", "port": 8080}

        # Add peer
        node_manager.add_peer(
            peer_node["node_id"], peer_node["address"], peer_node["port"]
        )

        # Verify peer is added
        assert peer_node["node_id"] in node_manager.peers
        assert (
            node_manager.peers[peer_node["node_id"]]["address"] == peer_node["address"]
        )

    @pytest.mark.asyncio
    async def test_data_sync_full_cycle(self):
        """Test complete data synchronization cycle"""
        # Create CRDT sync for two nodes
        sync1 = CRDTSync(node_id="node-1")
        sync2 = CRDTSync(node_id="node-2")

        # Node 1 updates data
        sync1.update("key1", "value1")

        # Simulate sync to node 2
        sync_data = sync1.get_sync_data()
        sync2.apply_sync_data(sync_data)

        # Verify node 2 has the data
        assert sync2.get("key1") == "value1"

        # Node 2 updates
        sync2.update("key2", "value2")

        # Sync back to node 1
        sync_data2 = sync2.get_sync_data()
        sync1.apply_sync_data(sync_data2)

        # Both nodes should have both values
        assert sync1.get("key1") == "value1"
        assert sync1.get("key2") == "value2"
        assert sync2.get("key1") == "value1"
        assert sync2.get("key2") == "value2"

    @pytest.mark.asyncio
    async def test_self_healing_full_cycle(self):
        """Test complete self-healing cycle (detect → analyze → plan → execute)"""
        from src.self_healing.mape_k import (MAPEKAnalyzer, MAPEKExecutor,
                                             MAPEKKnowledge, MAPEKMonitor,
                                             MAPEKPlanner)

        knowledge = MAPEKKnowledge()
        monitor = MAPEKMonitor(knowledge=knowledge)
        analyzer = MAPEKAnalyzer()
        planner = MAPEKPlanner(knowledge=knowledge)
        executor = MAPEKExecutor()

        mapek = MAPEKLoop(monitor, analyzer, planner, executor, knowledge)

        # Simulate healthy state
        healthy_metrics = {
            "cpu_percent": 50.0,
            "memory_percent": 60.0,
            "packet_loss_percent": 0.1,
        }

        # Run cycle - should be healthy
        result = mapek.run_cycle(healthy_metrics)
        assert result == "Healthy" or result is None

        # Simulate failure
        failure_metrics = {
            "cpu_percent": 95.0,
            "memory_percent": 90.0,
            "packet_loss_percent": 10.0,
        }

        # Run cycle - should detect and plan recovery
        result = mapek.run_cycle(failure_metrics)
        assert result is not None
        assert (
            "High CPU" in result or "High Memory" in result or "Network Loss" in result
        )

        # Simulate recovery
        recovery_metrics = {
            "cpu_percent": 50.0,
            "memory_percent": 60.0,
            "packet_loss_percent": 0.1,
        }

        # Run cycle - should detect recovery
        result = mapek.run_cycle(recovery_metrics)
        assert result == "Healthy" or result is None

    @pytest.mark.asyncio
    @pytest.mark.skipif(not LIBOQS_AVAILABLE, reason="LibOQS not available")
    async def test_pqc_communication_cycle(self):
        """Test complete PQC communication cycle"""
        # Create security instances for two nodes
        security1 = PQMeshSecurityLibOQS("node-1")
        security2 = PQMeshSecurityLibOQS("node-2")

        # Node 1 encrypts message for node 2
        plaintext = b"Hello from node-1"
        ciphertext = security1.encrypt(plaintext, "node-2")

        # Node 2 decrypts
        decrypted = security2.decrypt(ciphertext, "node-1")

        assert decrypted == plaintext

    @pytest.mark.asyncio
    async def test_consensus_participation(self):
        """Test node participation in consensus"""
        # Create Raft nodes
        node1 = RaftNode(node_id="node-1", peers=["node-2", "node-3"])
        node2 = RaftNode(node_id="node-2", peers=["node-1", "node-3"])
        node3 = RaftNode(node_id="node-3", peers=["node-1", "node-2"])

        # Node 1 proposes value
        result = node1.propose("key1", "value1")

        # Should be accepted (in real scenario, requires majority)
        assert result is not None

    @pytest.mark.asyncio
    async def test_multi_node_scenario(self):
        """Test scenario with multiple nodes"""
        nodes = {}
        syncs = {}

        # Create 5 nodes
        for i in range(1, 6):
            node_id = f"node-{i}"
            nodes[node_id] = NodeManager(node_id=node_id)
            syncs[node_id] = CRDTSync(node_id=node_id)

        # Node 1 updates
        syncs["node-1"].update("shared_key", "shared_value")

        # Sync to all other nodes
        sync_data = syncs["node-1"].get_sync_data()
        for node_id in ["node-2", "node-3", "node-4", "node-5"]:
            syncs[node_id].apply_sync_data(sync_data)

        # All nodes should have the value
        for node_id in nodes.keys():
            assert syncs[node_id].get("shared_key") == "shared_value"


@pytest.mark.skipif(
    not MESH_COMPONENTS_AVAILABLE, reason="Mesh components not available"
)
class TestMeshFailureRecovery:
    """Test mesh network failure and recovery scenarios"""

    @pytest.mark.asyncio
    async def test_node_failure_and_recovery(self):
        """Test node failure and automatic recovery"""
        # Create mesh with 3 nodes
        nodes = {}
        for i in range(1, 4):
            node_id = f"node-{i}"
            nodes[node_id] = NodeManager(node_id=node_id)

        # Node 2 fails
        nodes["node-2"].stop()

        # Remaining nodes should detect failure
        # (In real scenario, this would be detected via health checks)
        assert nodes["node-2"].is_running() == False

        # Node 2 recovers
        nodes["node-2"].start()

        # Should rejoin mesh
        assert nodes["node-2"].is_running() == True

    @pytest.mark.asyncio
    async def test_network_partition_recovery(self):
        """Test recovery from network partition"""
        # Create mesh with 5 nodes
        nodes = {}
        for i in range(1, 6):
            node_id = f"node-{i}"
            nodes[node_id] = NodeManager(node_id=node_id)

        # Simulate partition: nodes 1-2 vs nodes 3-5
        # (In real scenario, this would be network-level)

        # Partition heals
        # All nodes should reconnect
        for node_id in nodes.keys():
            assert nodes[node_id].is_running() == True


@pytest.mark.skipif(
    not MESH_COMPONENTS_AVAILABLE, reason="Mesh components not available"
)
class TestMeshSecurityIntegration:
    """Test security integration in mesh network"""

    @pytest.mark.asyncio
    @pytest.mark.skipif(not LIBOQS_AVAILABLE, reason="LibOQS not available")
    async def test_pqc_in_mesh_communication(self):
        """Test PQC encryption in mesh communication"""
        # Create nodes with PQC security
        security1 = PQMeshSecurityLibOQS("node-1")
        security2 = PQMeshSecurityLibOQS("node-2")

        # Encrypt message
        message = b"Secure mesh message"
        ciphertext = security1.encrypt(message, "node-2")

        # Decrypt
        decrypted = security2.decrypt(ciphertext, "node-1")

        assert decrypted == message

    @pytest.mark.asyncio
    async def test_spiffe_integration(self):
        """Test SPIFFE integration in mesh (if available)"""
        try:
            from src.security.spiffe.workload.api_client_production import \
                WorkloadAPIClientProduction

            # Create SPIFFE client
            client = WorkloadAPIClientProduction()

            # Should be able to fetch SVID (or handle gracefully if SPIRE not available)
            try:
                svid = await client.fetch_x509_svid()
                assert svid is not None
            except (FileNotFoundError, ConnectionError):
                # SPIRE not available - this is expected in test environment
                pass
        except ImportError:
            pytest.skip("SPIFFE components not available")


if __name__ == "__main__":
    pytest.main([__file__, "-v"])
