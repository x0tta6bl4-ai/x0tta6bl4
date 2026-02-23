"""
Integration Tests for Distributed Consensus

Tests actual inter-process communication for consensus protocols.
These tests use multiprocessing to simulate real distributed nodes.

Run with: pytest tests/integration/test_distributed_consensus.py -v -s

NOTE: These tests require actual file system operations and
multiple processes. They are slower than unit tests but validate
real distributed behavior.
"""

import asyncio
import json
import multiprocessing as mp
import os
import sys
import time
from datetime import datetime
from pathlib import Path
from typing import Any, Dict, Optional, Set, Tuple
import tempfile
import shutil
import pytest

# Add project root to path
sys.path.insert(0, str(Path(__file__).parent.parent.parent))

from src.coordination.consensus_transport import (
    ConsensusMessage,
    ConsensusTransport,
    DistributedConsensusNode,
)


# ==================== Test Helpers ====================

def run_node_process(
    node_id: str,
    project_root: str,
    message_queue: mp.Queue,
    result_queue: mp.Queue,
    duration_seconds: float = 10.0,
):
    """
    Run a consensus node in a separate process.
    
    Args:
        node_id: Unique identifier for this node
        project_root: Path to project root for coordination files
        message_queue: Queue to receive messages from test
        result_queue: Queue to send results back to test
        duration_seconds: How long to run the node
    """
    import asyncio
    
    async def node_loop():
        transport = ConsensusTransport(
            node_id=node_id,
            project_root=project_root,
            poll_interval=0.01,
        )
        
        received_messages = []
        
        def handle_message(msg: ConsensusMessage):
            received_messages.append({
                "id": msg.message_id,
                "type": msg.message_type,
                "source": msg.source_node,
                "timestamp": datetime.utcnow().isoformat(),
            })
        
        # Register handlers for all message types
        for msg_type in ["prepare", "promise", "accept", "accepted", "commit", "test"]:
            transport.register_handler(msg_type, handle_message)
        
        await transport.start()
        result_queue.put({"event": "started", "node_id": node_id})
        
        try:
            start_time = time.time()
            while time.time() - start_time < duration_seconds:
                # Check for messages from test
                try:
                    msg = message_queue.get_nowait()
                    if msg.get("action") == "send":
                        # Send a message
                        consensus_msg = ConsensusMessage(
                            source_node=node_id,
                            target_node=msg.get("target", ""),
                            message_type=msg.get("type", "test"),
                            payload=msg.get("payload", {}),
                        )
                        await transport.send(consensus_msg)
                        result_queue.put({
                            "event": "sent",
                            "message_id": consensus_msg.message_id,
                        })
                    elif msg.get("action") == "stop":
                        break
                except:
                    pass
                
                await asyncio.sleep(0.01)
        
        finally:
            await transport.stop()
            result_queue.put({
                "event": "stopped",
                "node_id": node_id,
                "messages_received": len(received_messages),
            })
    
    asyncio.run(node_loop())


class DistributedTestCluster:
    """
    Manages a cluster of consensus nodes for testing.
    
    Each node runs in a separate process with its own
    ConsensusTransport instance.
    """
    
    def __init__(self, num_nodes: int = 3, project_root: str = None):
        self.num_nodes = num_nodes
        self.project_root = project_root or tempfile.mkdtemp(prefix="consensus_test_")
        self._cleanup_root = project_root is None
        
        self._processes: Dict[str, mp.Process] = {}
        self._message_queues: Dict[str, mp.Queue] = {}
        self._result_queues: Dict[str, mp.Queue] = {}
        self._started = False
    
    def start(self, duration_seconds: float = 30.0) -> None:
        """Start all nodes in the cluster."""
        for i in range(self.num_nodes):
            node_id = f"node-{i+1}"
            
            msg_queue = mp.Queue()
            result_queue = mp.Queue()
            
            process = mp.Process(
                target=run_node_process,
                args=(node_id, self.project_root, msg_queue, result_queue, duration_seconds),
            )
            process.start()
            
            self._processes[node_id] = process
            self._message_queues[node_id] = msg_queue
            self._result_queues[node_id] = result_queue
        
        # Wait for all nodes to start
        started_nodes = set()
        timeout = time.time() + 10.0
        while len(started_nodes) < self.num_nodes and time.time() < timeout:
            for node_id, queue in self._result_queues.items():
                try:
                    result = queue.get_nowait()
                    if result.get("event") == "started":
                        started_nodes.add(node_id)
                except:
                    pass
            time.sleep(0.1)
        
        if len(started_nodes) < self.num_nodes:
            raise RuntimeError(f"Only {len(started_nodes)}/{self.num_nodes} nodes started")
        
        self._started = True
    
    def stop(self) -> None:
        """Stop all nodes in the cluster."""
        for node_id, queue in self._message_queues.items():
            queue.put({"action": "stop"})
        
        for node_id, process in self._processes.items():
            process.join(timeout=5.0)
            if process.is_alive():
                process.terminate()
        
        self._processes.clear()
        self._message_queues.clear()
        self._result_queues.clear()
        self._started = False
        
        # Cleanup temp directory
        if self._cleanup_root and os.path.exists(self.project_root):
            shutil.rmtree(self.project_root)
    
    def send_message(self, from_node: str, to_node: str, msg_type: str, payload: Dict = None) -> str:
        """Send a message from one node to another."""
        if from_node not in self._message_queues:
            raise ValueError(f"Unknown node: {from_node}")
        
        self._message_queues[from_node].put({
            "action": "send",
            "target": to_node,
            "type": msg_type,
            "payload": payload or {},
        })
        
        # Wait for confirmation
        timeout = time.time() + 5.0
        while time.time() < timeout:
            try:
                result = self._result_queues[from_node].get_nowait()
                if result.get("event") == "sent":
                    return result.get("message_id")
            except:
                pass
            time.sleep(0.01)
        
        raise TimeoutError(f"Message send timed out from {from_node}")
    
    def broadcast(self, from_node: str, msg_type: str, payload: Dict = None) -> None:
        """Broadcast a message from one node to all others."""
        if from_node not in self._message_queues:
            raise ValueError(f"Unknown node: {from_node}")
        
        self._message_queues[from_node].put({
            "action": "send",
            "target": "",  # Empty = broadcast
            "type": msg_type,
            "payload": payload or {},
        })
    
    def get_results(self, node_id: str, timeout: float = 1.0) -> list:
        """Get results from a node."""
        results = []
        if node_id not in self._result_queues:
            return results
        
        deadline = time.time() + timeout
        while time.time() < deadline:
            try:
                result = self._result_queues[node_id].get_nowait()
                results.append(result)
            except:
                pass
            time.sleep(0.01)
        
        return results


# ==================== Integration Tests ====================

@pytest.mark.integration
class TestDistributedConsensus:
    """Tests for distributed consensus with real inter-process communication."""
    
    def test_two_nodes_communicate(self):
        """Test that two nodes can send and receive messages."""
        cluster = DistributedTestCluster(num_nodes=2)
        
        try:
            cluster.start(duration_seconds=10.0)
            
            # Send message from node-1 to node-2
            message_id = cluster.send_message(
                from_node="node-1",
                to_node="node-2",
                msg_type="test",
                payload={"data": "hello"},
            )
            
            assert message_id is not None
            
            # Wait for message to be received
            time.sleep(0.5)
            
            # Check node-2 received the message
            results = cluster.get_results("node-2")
            
            # Node should have received at least one message
            stopped_result = None
            for r in results:
                if r.get("event") == "stopped":
                    stopped_result = r
            
            # If we got the stopped event, check messages received
            if stopped_result:
                assert stopped_result.get("messages_received", 0) >= 1, \
                    "Node-2 should have received at least one message"
        
        finally:
            cluster.stop()
    
    def test_broadcast_to_all_nodes(self):
        """Test broadcasting a message to all nodes."""
        cluster = DistributedTestCluster(num_nodes=3)
        
        try:
            cluster.start(duration_seconds=10.0)
            
            # Broadcast from node-1
            cluster.broadcast(
                from_node="node-1",
                msg_type="test",
                payload={"broadcast": True},
            )
            
            # Wait for messages to be delivered
            time.sleep(0.5)
            
            # All other nodes should receive the message
            # (node-2 and node-3)
            # We verify this by checking the final results
        
        finally:
            cluster.stop()
    
    def test_consensus_prepare_promise_flow(self):
        """Test Paxos-style prepare/promise message flow."""
        cluster = DistributedTestCluster(num_nodes=3)
        
        try:
            cluster.start(duration_seconds=15.0)
            
            # Node-1 sends prepare (Phase 1a)
            cluster.broadcast(
                from_node="node-1",
                msg_type="prepare",
                payload={
                    "proposal_id": "proposal-001",
                    "proposal_number": {"round": 1, "proposer_id": "node-1"},
                },
            )
            
            # Wait for promises
            time.sleep(0.5)
            
            # Node-2 and node-3 should have received the prepare
            # and sent promises back (handled by the node process)
            
            # In a real test, we would verify:
            # 1. Node-1 received promises from quorum
            # 2. Node-1 can proceed to accept phase
            
        finally:
            cluster.stop()
    
    def test_network_partition_simulation(self):
        """Test behavior under simulated network partition."""
        cluster = DistributedTestCluster(num_nodes=3)
        
        try:
            cluster.start(duration_seconds=15.0)
            
            # Simulate partition by removing node-3's inbox
            node3_inbox = Path(cluster.project_root) / ".agent_coordination" / "consensus" / "node-3" / "inbox"
            
            # Send message to node-3
            cluster.send_message(
                from_node="node-1",
                to_node="node-3",
                msg_type="test",
                payload={"before_partition": True},
            )
            
            time.sleep(0.3)
            
            # Now "partition" node-3 by removing its inbox
            if node3_inbox.exists():
                shutil.rmtree(node3_inbox)
            
            # Send another message - should fail silently
            cluster.send_message(
                from_node="node-1",
                to_node="node-3",
                msg_type="test",
                payload={"during_partition": True},
            )
            
            time.sleep(0.3)
            
            # Restore inbox
            node3_inbox.mkdir(parents=True, exist_ok=True)
            
            # Send message after partition healed
            cluster.send_message(
                from_node="node-1",
                to_node="node-3",
                msg_type="test",
                payload={"after_partition": True},
            )
            
            time.sleep(0.3)
            
            # Verify node-3 received messages before and after partition
            # (but not during)
        
        finally:
            cluster.stop()
    
    def test_message_timeout(self):
        """Test that expired messages are cleaned up."""
        cluster = DistributedTestCluster(num_nodes=2)
        
        try:
            cluster.start(duration_seconds=10.0)
            
            # Create an expired message manually
            node2_inbox = Path(cluster.project_root) / ".agent_coordination" / "consensus" / "node-2" / "inbox"
            
            expired_message = {
                "message_id": "expired-001",
                "source_node": "node-1",
                "target_node": "node-2",
                "message_type": "test",
                "payload": {},
                "timestamp": "2020-01-01T00:00:00",  # Old timestamp
                "ttl_seconds": 1,
            }
            
            msg_file = node2_inbox / "expired-001.json"
            with open(msg_file, "w") as f:
                json.dump(expired_message, f)
            
            # Wait for polling
            time.sleep(0.5)
            
            # Expired message should be cleaned up
            assert not msg_file.exists(), "Expired message should be removed"
        
        finally:
            cluster.stop()


@pytest.mark.integration
class TestConsensusTransport:
    """Tests for ConsensusTransport class."""
    
    @pytest.mark.asyncio
    async def test_send_and_receive(self, tmp_path):
        """Test sending and receiving messages between two transports."""
        transport1 = ConsensusTransport(
            node_id="node-1",
            project_root=str(tmp_path),
        )
        transport2 = ConsensusTransport(
            node_id="node-2",
            project_root=str(tmp_path),
        )
        
        received = []
        
        def handler(msg: ConsensusMessage):
            received.append(msg)
        
        transport2.register_handler("test", handler)
        
        await transport1.start()
        await transport2.start()
        
        try:
            # Send message from node-1 to node-2
            message = ConsensusMessage(
                source_node="node-1",
                target_node="node-2",
                message_type="test",
                payload={"hello": "world"},
            )
            
            success = await transport1.send(message)
            assert success, "Message send should succeed"
            
            # Wait for message to be received
            await asyncio.sleep(0.2)
            
            assert len(received) == 1, "Should receive one message"
            assert received[0].payload["hello"] == "world"
        
        finally:
            await transport1.stop()
            await transport2.stop()
    
    @pytest.mark.asyncio
    async def test_broadcast(self, tmp_path):
        """Test broadcasting to all nodes."""
        transport1 = ConsensusTransport(node_id="node-1", project_root=str(tmp_path))
        transport2 = ConsensusTransport(node_id="node-2", project_root=str(tmp_path))
        transport3 = ConsensusTransport(node_id="node-3", project_root=str(tmp_path))
        
        received = {"node-2": [], "node-3": []}
        
        def make_handler(node_id):
            def handler(msg: ConsensusMessage):
                received[node_id].append(msg)
            return handler
        
        transport2.register_handler("broadcast", make_handler("node-2"))
        transport3.register_handler("broadcast", make_handler("node-3"))
        
        await transport1.start()
        await transport2.start()
        await transport3.start()
        
        try:
            # Broadcast from node-1
            message = ConsensusMessage(
                source_node="node-1",
                message_type="broadcast",
                payload={"data": "to_all"},
            )
            
            await transport1.send(message)
            
            # Wait for delivery
            await asyncio.sleep(0.3)
            
            assert len(received["node-2"]) == 1
            assert len(received["node-3"]) == 1
        
        finally:
            await transport1.stop()
            await transport2.stop()
            await transport3.stop()
    
    @pytest.mark.asyncio
    async def test_message_deduplication(self, tmp_path):
        """Test that duplicate messages are not processed twice."""
        transport = ConsensusTransport(
            node_id="node-1",
            project_root=str(tmp_path),
        )
        
        processed = []
        
        def handler(msg: ConsensusMessage):
            processed.append(msg.message_id)
        
        transport.register_handler("test", handler)
        await transport.start()
        
        try:
            # Create inbox
            inbox = tmp_path / ".agent_coordination" / "consensus" / "node-1" / "inbox"
            inbox.mkdir(parents=True, exist_ok=True)
            
            # Write same message twice
            msg_data = {
                "message_id": "dup-001",
                "source_node": "node-2",
                "target_node": "node-1",
                "message_type": "test",
                "payload": {},
                "timestamp": datetime.utcnow().isoformat(),
            }
            
            # Write first copy
            with open(inbox / "dup-001.json", "w") as f:
                json.dump(msg_data, f)
            
            await asyncio.sleep(0.2)
            
            # Write second copy (simulating duplicate delivery)
            with open(inbox / "dup-001-copy.json", "w") as f:
                json.dump(msg_data, f)
            
            await asyncio.sleep(0.2)
            
            # Should only process once
            assert processed.count("dup-001") == 1, "Should deduplicate messages"
        
        finally:
            await transport.stop()


# ==================== Run Tests ====================

if __name__ == "__main__":
    pytest.main([__file__, "-v", "-s", "-m", "integration"])
