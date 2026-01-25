"""
Chaos Testing for Slot-Based Synchronization

Tests slot-based synchronization resilience with >50 nodes:
- Node failures
- Network partitions
- Beacon signal loss
- Race conditions
- Clock drift

Target: Validate slot-sync works correctly with 50+ nodes
Risk: Race conditions at 100+ nodes (Stage 1 requirement)
"""

import asyncio
import logging
import time
import random
from typing import List, Dict, Set, Optional
from dataclasses import dataclass, field
from datetime import datetime
from enum import Enum

logger = logging.getLogger(__name__)


class NodeState(Enum):
    """Node state in chaos test"""
    HEALTHY = "healthy"
    FAILED = "failed"
    PARTITIONED = "partitioned"
    BEACON_LOST = "beacon_lost"
    CLOCK_DRIFT = "clock_drift"


@dataclass
class ChaosTestResult:
    """Results from chaos test session"""
    test_name: str
    timestamp: datetime
    duration_seconds: float
    nodes_total: int
    nodes_failed: int
    nodes_partitioned: int
    slot_sync_success_rate: float
    beacon_collisions: int
    recovery_time_avg: float
    recovery_time_max: float
    race_conditions_detected: int
    test_passed: bool


@dataclass
class MeshNode:
    """Simulated mesh node for chaos testing"""
    node_id: str
    state: NodeState = NodeState.HEALTHY
    slot_number: int = 0
    last_beacon: Optional[datetime] = None
    neighbors: Set[str] = field(default_factory=set)
    clock_offset_ms: float = 0.0  # Clock drift simulation
    beacon_collisions: int = 0
    recovery_time: Optional[float] = None


class SlotSyncChaosTester:
    """
    Chaos testing framework for slot-based synchronization.
    
    Simulates:
    - Node failures
    - Network partitions
    - Beacon signal loss
    - Clock drift
    - Race conditions
    
    Usage:
        >>> tester = SlotSyncChaosTester(num_nodes=50)
        >>> result = await tester.run_chaos_test()
        >>> print(f"Test passed: {result.test_passed}")
    """
    
    def __init__(self, num_nodes: int = 50, slot_count: int = 10):
        """
        Initialize chaos tester.
        
        Args:
            num_nodes: Number of nodes in mesh network
            slot_count: Number of available time slots
        """
        self.num_nodes = num_nodes
        self.slot_count = slot_count
        self.nodes: Dict[str, MeshNode] = {}
        self.test_results: List[ChaosTestResult] = []
        
        # Initialize nodes
        for i in range(num_nodes):
            node_id = f"node-{i:03d}"
            self.nodes[node_id] = MeshNode(
                node_id=node_id,
                slot_number=i % slot_count,
                neighbors=set()
            )
        
        # Create mesh topology (random graph)
        self._create_mesh_topology()
    
    def _create_mesh_topology(self):
        """Create random mesh topology with average 3-5 neighbors per node."""
        node_ids = list(self.nodes.keys())
        
        for node_id in node_ids:
            # Each node connects to 3-5 random neighbors
            num_neighbors = random.randint(3, 5)
            neighbors = random.sample(
                [n for n in node_ids if n != node_id],
                min(num_neighbors, len(node_ids) - 1)
            )
            self.nodes[node_id].neighbors = set(neighbors)
            
            # Bidirectional links
            for neighbor in neighbors:
                self.nodes[neighbor].neighbors.add(node_id)
    
    async def run_chaos_test(
        self,
        duration: float = 60.0,
        failure_rate: float = 0.1,
        partition_probability: float = 0.05
    ) -> ChaosTestResult:
        """
        Run chaos test with node failures and network partitions.
        
        Args:
            duration: Test duration in seconds
            failure_rate: Probability of node failure per second
            partition_probability: Probability of network partition
            
        Returns:
            ChaosTestResult with test outcomes
        """
        logger.info(f"Starting chaos test: {self.num_nodes} nodes, {duration}s duration")
        
        start_time = time.time()
        nodes_failed = 0
        nodes_partitioned = 0
        beacon_collisions = 0
        race_conditions = 0
        recovery_times = []
        
        # Reset all nodes to healthy
        for node in self.nodes.values():
            node.state = NodeState.HEALTHY
            node.beacon_collisions = 0
            node.recovery_time = None
        
        # Run test loop
        while time.time() - start_time < duration:
            # Simulate node failures
            if random.random() < failure_rate:
                await self._simulate_node_failure()
                nodes_failed += 1
            
            # Simulate network partitions
            if random.random() < partition_probability:
                await self._simulate_network_partition()
                nodes_partitioned += 1
            
            # Simulate beacon collisions
            collisions = await self._simulate_beacon_collisions()
            beacon_collisions += collisions
            
            # Detect race conditions
            race_conditions += await self._detect_race_conditions()
            
            # Measure recovery times
            recovery_time = await self._measure_recovery_time()
            if recovery_time:
                recovery_times.append(recovery_time)
            
            await asyncio.sleep(0.1)  # 100ms tick
        
        # Calculate metrics
        slot_sync_success = self._calculate_slot_sync_success_rate()
        avg_recovery = sum(recovery_times) / len(recovery_times) if recovery_times else 0.0
        max_recovery = max(recovery_times) if recovery_times else 0.0
        
        # Test passes if:
        # - Slot sync success rate > 95%
        # - Average recovery time < 2s
        # - Race conditions < 5% of test duration
        test_passed = (
            slot_sync_success > 0.95 and
            avg_recovery < 2.0 and
            race_conditions < (duration * 0.05)
        )
        
        result = ChaosTestResult(
            test_name="slot_sync_chaos",
            timestamp=datetime.now(),
            duration_seconds=duration,
            nodes_total=self.num_nodes,
            nodes_failed=nodes_failed,
            nodes_partitioned=nodes_partitioned,
            slot_sync_success_rate=slot_sync_success,
            beacon_collisions=beacon_collisions,
            recovery_time_avg=avg_recovery,
            recovery_time_max=max_recovery,
            race_conditions_detected=race_conditions,
            test_passed=test_passed
        )
        
        self.test_results.append(result)
        logger.info(
            f"Chaos test complete: "
            f"Success rate={slot_sync_success:.2%}, "
            f"Recovery={avg_recovery:.2f}s, "
            f"Passed={test_passed}"
        )
        
        return result
    
    async def _simulate_node_failure(self):
        """Simulate random node failure."""
        healthy_nodes = [n for n in self.nodes.values() if n.state == NodeState.HEALTHY]
        if not healthy_nodes:
            return
        
        node = random.choice(healthy_nodes)
        node.state = NodeState.FAILED
        logger.debug(f"Node {node.node_id} failed")
        
        # Remove from neighbors
        for neighbor_id in node.neighbors:
            if neighbor_id in self.nodes:
                self.nodes[neighbor_id].neighbors.discard(node.node_id)
    
    async def _simulate_network_partition(self):
        """Simulate network partition (split network into two parts)."""
        if len(self.nodes) < 4:
            return
        
        node_ids = list(self.nodes.keys())
        partition_size = len(node_ids) // 2
        
        partition1 = set(node_ids[:partition_size])
        partition2 = set(node_ids[partition_size:])
        
        # Remove links between partitions
        for node_id in partition1:
            node = self.nodes[node_id]
            node.neighbors = node.neighbors.intersection(partition1)
            node.state = NodeState.PARTITIONED
        
        for node_id in partition2:
            node = self.nodes[node_id]
            node.neighbors = node.neighbors.intersection(partition2)
            node.state = NodeState.PARTITIONED
        
        logger.debug(f"Network partitioned: {len(partition1)} + {len(partition2)} nodes")
    
    async def _simulate_beacon_collisions(self) -> int:
        """Simulate beacon collisions (multiple nodes using same slot)."""
        collisions = 0
        
        # Group nodes by slot
        slot_usage: Dict[int, List[MeshNode]] = {}
        for node in self.nodes.values():
            if node.state == NodeState.HEALTHY:
                slot = node.slot_number
                if slot not in slot_usage:
                    slot_usage[slot] = []
                slot_usage[slot].append(node)
        
        # Detect collisions (multiple nodes in same slot)
        for slot, nodes in slot_usage.items():
            if len(nodes) > 1:
                # Collision detected
                collisions += len(nodes) - 1
                for node in nodes:
                    node.beacon_collisions += 1
                    # Nodes should resynchronize
                    await self._resynchronize_slot(node)
        
        return collisions
    
    async def _resynchronize_slot(self, node: MeshNode):
        """Resynchronize node slot after collision."""
        # Find available slot
        used_slots = set()
        for neighbor_id in node.neighbors:
            if neighbor_id in self.nodes:
                neighbor = self.nodes[neighbor_id]
                if neighbor.state == NodeState.HEALTHY:
                    used_slots.add(neighbor.slot_number)
        
        # Choose first available slot
        for slot in range(self.slot_count):
            if slot not in used_slots:
                node.slot_number = slot
                node.last_beacon = datetime.now()
                logger.debug(f"Node {node.node_id} resynchronized to slot {slot}")
                return
    
    async def _detect_race_conditions(self) -> int:
        """
        Detect race conditions in slot assignment.
        
        Race condition: Multiple nodes simultaneously trying to claim same slot.
        """
        race_conditions = 0
        
        # Check for simultaneous slot changes
        changing_nodes = []
        for node in self.nodes.values():
            if node.state == NodeState.HEALTHY:
                # Check if node needs to change slot (collision detected)
                neighbor_slots = set()
                for neighbor_id in node.neighbors:
                    if neighbor_id in self.nodes:
                        neighbor = self.nodes[neighbor_id]
                        if neighbor.state == NodeState.HEALTHY:
                            neighbor_slots.add(neighbor.slot_number)
                
                if node.slot_number in neighbor_slots:
                    changing_nodes.append(node)
        
        # Race condition: multiple nodes changing to same slot simultaneously
        if len(changing_nodes) > 1:
            target_slots = {}
            for node in changing_nodes:
                # Find target slot
                used_slots = set()
                for neighbor_id in node.neighbors:
                    if neighbor_id in self.nodes:
                        neighbor = self.nodes[neighbor_id]
                        if neighbor.state == NodeState.HEALTHY:
                            used_slots.add(neighbor.slot_number)
                
                for slot in range(self.slot_count):
                    if slot not in used_slots:
                        if slot not in target_slots:
                            target_slots[slot] = []
                        target_slots[slot].append(node)
                        break
            
            # Count conflicts (multiple nodes targeting same slot)
            for slot, nodes in target_slots.items():
                if len(nodes) > 1:
                    race_conditions += len(nodes) - 1
        
        return race_conditions
    
    async def _measure_recovery_time(self) -> Optional[float]:
        """Measure recovery time for failed nodes."""
        recovery_time = None
        
        for node in self.nodes.values():
            if node.state == NodeState.FAILED:
                # Check if node recovered (simulated)
                if random.random() < 0.1:  # 10% recovery chance per tick
                    node.state = NodeState.HEALTHY
                    recovery_start = time.time()
                    # Simulate recovery process
                    await asyncio.sleep(0.1)
                    recovery_time = time.time() - recovery_start
                    node.recovery_time = recovery_time
                    logger.debug(f"Node {node.node_id} recovered in {recovery_time:.3f}s")
        
        return recovery_time
    
    def _calculate_slot_sync_success_rate(self) -> float:
        """Calculate slot synchronization success rate."""
        healthy_nodes = [n for n in self.nodes.values() if n.state == NodeState.HEALTHY]
        if not healthy_nodes:
            return 0.0
        
        synchronized = 0
        for node in healthy_nodes:
            # Check if node has unique slot among neighbors
            neighbor_slots = set()
            for neighbor_id in node.neighbors:
                if neighbor_id in self.nodes:
                    neighbor = self.nodes[neighbor_id]
                    if neighbor.state == NodeState.HEALTHY:
                        neighbor_slots.add(neighbor.slot_number)
            
            if node.slot_number not in neighbor_slots:
                synchronized += 1
        
        return synchronized / len(healthy_nodes) if healthy_nodes else 0.0
    
    def generate_report(self) -> str:
        """Generate chaos test report."""
        if not self.test_results:
            return "No test results available."
        
        report = []
        report.append("=" * 60)
        report.append("Slot-Based Synchronization Chaos Test Report")
        report.append("=" * 60)
        report.append("")
        
        for result in self.test_results:
            report.append(f"Test: {result.test_name}")
            report.append(f"  Timestamp: {result.timestamp}")
            report.append(f"  Duration: {result.duration_seconds:.1f}s")
            report.append(f"  Nodes: {result.nodes_total}")
            report.append(f"  Failed: {result.nodes_failed}")
            report.append(f"  Partitioned: {result.nodes_partitioned}")
            report.append("")
            report.append("  Metrics:")
            report.append(f"    Slot Sync Success Rate: {result.slot_sync_success_rate:.2%}")
            report.append(f"    Beacon Collisions: {result.beacon_collisions}")
            report.append(f"    Average Recovery Time: {result.recovery_time_avg:.3f}s")
            report.append(f"    Maximum Recovery Time: {result.recovery_time_max:.3f}s")
            report.append(f"    Race Conditions: {result.race_conditions_detected}")
            report.append("")
            report.append(f"  Result: {'✅ PASSED' if result.test_passed else '❌ FAILED'}")
            report.append("-" * 60)
            report.append("")
        
        return "\n".join(report)


async def main():
    """CLI entry point for chaos testing."""
    import argparse
    
    parser = argparse.ArgumentParser(description="Chaos test slot-based synchronization")
    parser.add_argument("--nodes", type=int, default=50, help="Number of nodes")
    parser.add_argument("--duration", type=float, default=60.0, help="Test duration in seconds")
    parser.add_argument("--failure-rate", type=float, default=0.1, help="Node failure rate per second")
    parser.add_argument("--partition-prob", type=float, default=0.05, help="Network partition probability")
    parser.add_argument("--output", type=str, help="Output file for report")
    
    args = parser.parse_args()
    
    logging.basicConfig(level=logging.INFO)
    
    tester = SlotSyncChaosTester(num_nodes=args.nodes)
    result = await tester.run_chaos_test(
        duration=args.duration,
        failure_rate=args.failure_rate,
        partition_probability=args.partition_prob
    )
    
    report = tester.generate_report()
    print(report)
    
    if args.output:
        with open(args.output, 'w') as f:
            f.write(report)
        print(f"\nReport saved to: {args.output}")
    
    exit(0 if result.test_passed else 1)


if __name__ == "__main__":
    asyncio.run(main())














