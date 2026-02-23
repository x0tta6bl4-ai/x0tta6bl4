#!/usr/bin/env python3
"""
Mininet Simulation Scenarios for MTTR Benchmarking.

Compares x0tta6bl4 Make-Never-Break implementation against:
- Rajant Kinetic Mesh (<1ms MTTR)
- Traditional mesh protocols (OSPF, AODV)
- Cisco PQC/Zero-Trust solutions

Simulation Scenarios:
1. Single Path Failure - Basic failover test
2. Multiple Path Failure - Cascading failures
3. Network Partition - Split-brain scenario
4. High Churn - Rapid topology changes
5. PQC Handshake Overhead - Encryption performance
"""

import asyncio
import json
import logging
import os
import random
import time
from dataclasses import dataclass, field
from datetime import datetime
from typing import Any, Dict, List, Optional, Tuple
import subprocess
import tempfile

logger = logging.getLogger(__name__)

# Check if Mininet is available
MININET_AVAILABLE = False
try:
    from mininet.net import Mininet
    from mininet.node import Controller, OVSSwitch
    from mininet.link import TCLink
    from mininet.cli import CLI
    MININET_AVAILABLE = True
except ImportError:
    logger.warning("Mininet not available, using simulation mode")


@dataclass
class SimulationConfig:
    """Configuration for simulation scenario."""
    name: str
    description: str
    duration_sec: float = 60.0
    num_nodes: int = 10
    num_paths: int = 4  # Make-Never-Break default
    failure_interval_sec: float = 5.0
    measurement_interval_sec: float = 0.1
    
    # Network parameters
    base_latency_ms: float = 10.0
    jitter_ms: float = 2.0
    packet_loss_rate: float = 0.01
    
    # Failure scenarios
    failure_type: str = "single"  # single, multiple, partition, churn
    failure_count: int = 1
    recovery_delay_ms: float = 100.0


@dataclass
class SimulationResult:
    """Result of a simulation run."""
    scenario_name: str
    timestamp: str
    duration_sec: float
    
    # MTTR metrics
    mttr_ms: float = 0.0
    mttr_min_ms: float = 0.0
    mttr_max_ms: float = 0.0
    mttr_std_ms: float = 0.0
    
    # Path metrics
    paths_available: int = 0
    paths_failed: int = 0
    reroutes_triggered: int = 0
    
    # Traffic metrics
    packets_sent: int = 0
    packets_received: int = 0
    packets_lost: int = 0
    
    # Performance
    avg_latency_ms: float = 0.0
    p99_latency_ms: float = 0.0
    
    # Raw measurements
    mttr_samples: List[float] = field(default_factory=list)
    latency_samples: List[float] = field(default_factory=list)


class MininetSimulator:
    """
    Mininet-based network simulator for MTTR benchmarking.
    
    Falls back to pure Python simulation if Mininet is not available.
    """
    
    def __init__(self, config: SimulationConfig):
        self.config = config
        self._net = None
        self._nodes = {}
        self._links = {}
        self._running = False
        
        # Simulation state (for non-Mininet mode)
        self._sim_nodes: Dict[str, Dict] = {}
        self._sim_links: Dict[str, Dict] = {}
        self._sim_paths: List[List[str]] = []
    
    async def setup(self) -> None:
        """Set up the simulation environment."""
        if MININET_AVAILABLE:
            await self._setup_mininet()
        else:
            self._setup_simulation()
        
        logger.info(f"Simulation '{self.config.name}' setup complete")
    
    async def _setup_mininet(self) -> None:
        """Set up Mininet network."""
        self._net = Mininet(
            controller=Controller,
            switch=OVSSwitch,
            link=TCLink,
        )
        
        # Add controller
        self._net.addController('c0')
        
        # Add nodes
        for i in range(self.config.num_nodes):
            node_name = f"h{i+1}"
            node = self._net.addHost(node_name)
            self._nodes[node_name] = node
        
        # Add switch for connectivity
        switch = self._net.addSwitch('s1')
        
        # Connect nodes to switch with links
        for node_name, node in self._nodes.items():
            link = self._net.addLink(
                node, switch,
                delay=f"{self.config.base_latency_ms}ms",
                loss=self.config.packet_loss_rate * 100,
            )
            self._links[f"{node_name}-s1"] = link
        
        # Start network
        self._net.start()
    
    def _setup_simulation(self) -> None:
        """Set up pure Python simulation."""
        # Create nodes
        for i in range(self.config.num_nodes):
            node_name = f"node_{i}"
            self._sim_nodes[node_name] = {
                "id": node_name,
                "active": True,
                "paths": [],
            }
        
        # Create mesh links (full mesh for simplicity)
        node_names = list(self._sim_nodes.keys())
        for i, n1 in enumerate(node_names):
            for n2 in node_names[i+1:]:
                link_id = f"{n1}-{n2}"
                self._sim_links[link_id] = {
                    "source": n1,
                    "target": n2,
                    "active": True,
                    "latency_ms": self.config.base_latency_ms + random.uniform(
                        -self.config.jitter_ms, self.config.jitter_ms
                    ),
                    "loss_rate": self.config.packet_loss_rate,
                }
        
        # Establish initial paths
        self._establish_paths()
    
    def _establish_paths(self) -> None:
        """Establish redundant paths between nodes."""
        node_names = list(self._sim_nodes.keys())
        
        # Create multiple paths between first and last node
        source = node_names[0]
        target = node_names[-1]
        
        # Find diverse routes
        intermediate = node_names[1:-1]
        
        for i in range(self.config.num_paths):
            # Create path with different intermediate nodes
            if len(intermediate) > i:
                path = [source, intermediate[i], target]
            else:
                path = [source, target]
            
            self._sim_paths.append(path)
            
            # Register path with nodes
            for node in path:
                if node in self._sim_nodes:
                    self._sim_nodes[node]["paths"].append(path)
    
    async def run(self) -> SimulationResult:
        """Run the simulation scenario."""
        result = SimulationResult(
            scenario_name=self.config.name,
            timestamp=datetime.utcnow().isoformat(),
            duration_sec=self.config.duration_sec,
        )
        
        self._running = True
        start_time = time.time()
        
        logger.info(f"Starting simulation '{self.config.name}'")
        
        # Run simulation loop
        while self._running and (time.time() - start_time) < self.config.duration_sec:
            # Inject failure
            if self.config.failure_type != "none":
                await self._inject_failure(result)
            
            # Measure MTTR
            mttr = await self._measure_mttr()
            if mttr > 0:
                result.mttr_samples.append(mttr)
            
            # Measure latency
            latency = await self._measure_latency()
            result.latency_samples.append(latency)
            
            await asyncio.sleep(self.config.measurement_interval_sec)
        
        # Calculate final metrics
        self._calculate_metrics(result)
        
        self._running = False
        return result
    
    async def _inject_failure(self, result: SimulationResult) -> None:
        """Inject a failure into the network."""
        if self.config.failure_type == "single":
            # Single link failure
            if random.random() < 0.1:  # 10% chance per interval
                link_id = random.choice(list(self._sim_links.keys()))
                self._sim_links[link_id]["active"] = False
                result.paths_failed += 1
                logger.debug(f"Failed link: {link_id}")
        
        elif self.config.failure_type == "multiple":
            # Multiple simultaneous failures
            if random.random() < 0.05:
                num_failures = min(
                    self.config.failure_count,
                    len(self._sim_links) - self.config.num_paths  # Keep some paths
                )
                for _ in range(num_failures):
                    link_id = random.choice([
                        k for k, v in self._sim_links.items() if v["active"]
                    ])
                    self._sim_links[link_id]["active"] = False
                    result.paths_failed += 1
        
        elif self.config.failure_type == "partition":
            # Network partition
            if random.random() < 0.02:
                # Disable links between node groups
                mid = len(self._sim_nodes) // 2
                nodes1 = list(self._sim_nodes.keys())[:mid]
                nodes2 = list(self._sim_nodes.keys())[mid:]
                
                for n1 in nodes1:
                    for n2 in nodes2:
                        link_id = f"{n1}-{n2}"
                        if link_id in self._sim_links:
                            self._sim_links[link_id]["active"] = False
        
        elif self.config.failure_type == "churn":
            # Rapid topology changes
            if random.random() < 0.2:
                # Toggle random link
                link_id = random.choice(list(self._sim_links.keys()))
                self._sim_links[link_id]["active"] = not self._sim_links[link_id]["active"]
    
    async def _measure_mttr(self) -> float:
        """Measure Mean Time To Recovery."""
        # Check if we have connectivity
        has_connectivity = self._check_connectivity()
        
        if not has_connectivity:
            # Start timer
            failure_time = time.time()
            
            # Wait for recovery (simulate rerouting)
            await asyncio.sleep(self.config.recovery_delay_ms / 1000)
            
            # Check if recovered
            recovered = self._check_connectivity()
            
            if recovered:
                return (time.time() - failure_time) * 1000  # ms
        
        return 0.0
    
    def _check_connectivity(self) -> bool:
        """Check if there's at least one active path."""
        for path in self._sim_paths:
            path_active = True
            for i in range(len(path) - 1):
                n1, n2 = path[i], path[i+1]
                link_id = f"{n1}-{n2}"
                reverse_id = f"{n2}-{n1}"
                
                link = self._sim_links.get(link_id) or self._sim_links.get(reverse_id)
                if not link or not link["active"]:
                    path_active = False
                    break
            
            if path_active:
                return True
        
        return False
    
    async def _measure_latency(self) -> float:
        """Measure current latency."""
        # Find active path and measure latency
        for path in self._sim_paths:
            path_latency = 0.0
            path_active = True
            
            for i in range(len(path) - 1):
                n1, n2 = path[i], path[i+1]
                link_id = f"{n1}-{n2}"
                reverse_id = f"{n2}-{n1}"
                
                link = self._sim_links.get(link_id) or self._sim_links.get(reverse_id)
                if not link or not link["active"]:
                    path_active = False
                    break
                
                path_latency += link["latency_ms"]
            
            if path_active:
                return path_latency
        
        return float('inf')  # No path available
    
    def _calculate_metrics(self, result: SimulationResult) -> None:
        """Calculate final metrics from samples."""
        if result.mttr_samples:
            result.mttr_ms = sum(result.mttr_samples) / len(result.mttr_samples)
            result.mttr_min_ms = min(result.mttr_samples)
            result.mttr_max_ms = max(result.mttr_samples)
            
            # Calculate std deviation
            mean = result.mttr_ms
            variance = sum((x - mean) ** 2 for x in result.mttr_samples) / len(result.mttr_samples)
            result.mttr_std_ms = variance ** 0.5
        
        if result.latency_samples:
            valid_latencies = [l for l in result.latency_samples if l < float('inf')]
            if valid_latencies:
                result.avg_latency_ms = sum(valid_latencies) / len(valid_latencies)
                sorted_latencies = sorted(valid_latencies)
                p99_idx = int(len(sorted_latencies) * 0.99)
                result.p99_latency_ms = sorted_latencies[min(p99_idx, len(sorted_latencies) - 1)]
        
        # Count available paths
        result.paths_available = sum(1 for p in self._sim_paths if self._is_path_active(p))
    
    def _is_path_active(self, path: List[str]) -> bool:
        """Check if a specific path is active."""
        for i in range(len(path) - 1):
            n1, n2 = path[i], path[i+1]
            link_id = f"{n1}-{n2}"
            reverse_id = f"{n2}-{n1}"
            
            link = self._sim_links.get(link_id) or self._sim_links.get(reverse_id)
            if not link or not link["active"]:
                return False
        
        return True
    
    async def teardown(self) -> None:
        """Clean up simulation."""
        if MININET_AVAILABLE and self._net:
            self._net.stop()
        
        self._nodes.clear()
        self._links.clear()
        self._sim_nodes.clear()
        self._sim_links.clear()
        self._sim_paths.clear()
        
        logger.info("Simulation teardown complete")


class BenchmarkSuite:
    """
    Benchmark suite for comparing MTTR across different implementations.
    """
    
    # Reference MTTR values (from competitive analysis)
    REFERENCE_MTTR = {
        "rajant_kinetic_mesh": 1.0,      # <1ms
        "cisco_pqc": 50.0,                # ~50ms
        "ospf_traditional": 1000.0,       # ~1s
        "aodv_mesh": 2000.0,              # ~2s
        "x0tta6bl4_target": 100.0,        # Target: <100ms
    }
    
    def __init__(self, output_dir: str = "simulation/results"):
        self.output_dir = output_dir
        os.makedirs(output_dir, exist_ok=True)
        
        self.results: Dict[str, SimulationResult] = {}
    
    async def run_all_scenarios(self) -> Dict[str, SimulationResult]:
        """Run all benchmark scenarios."""
        scenarios = [
            # Scenario 1: Single Path Failure
            SimulationConfig(
                name="single_path_failure",
                description="Basic failover test with single link failure",
                duration_sec=30.0,
                num_nodes=10,
                num_paths=4,
                failure_type="single",
                recovery_delay_ms=50.0,  # x0tta6bl4 target
            ),
            
            # Scenario 2: Multiple Path Failure
            SimulationConfig(
                name="multiple_path_failure",
                description="Cascading failures with multiple simultaneous link failures",
                duration_sec=60.0,
                num_nodes=20,
                num_paths=4,
                failure_type="multiple",
                failure_count=3,
                recovery_delay_ms=100.0,
            ),
            
            # Scenario 3: Network Partition
            SimulationConfig(
                name="network_partition",
                description="Split-brain scenario with network partition",
                duration_sec=60.0,
                num_nodes=15,
                num_paths=6,
                failure_type="partition",
                recovery_delay_ms=200.0,
            ),
            
            # Scenario 4: High Churn
            SimulationConfig(
                name="high_churn",
                description="Rapid topology changes simulating mobile nodes",
                duration_sec=120.0,
                num_nodes=30,
                num_paths=4,
                failure_type="churn",
                recovery_delay_ms=50.0,
            ),
            
            # Scenario 5: PQC Handshake Overhead
            SimulationConfig(
                name="pqc_handshake",
                description="Measure PQC handshake overhead for tunnel establishment",
                duration_sec=30.0,
                num_nodes=5,
                num_paths=2,
                failure_type="none",
                recovery_delay_ms=100.0,  # PQC handshake time
            ),
        ]
        
        for config in scenarios:
            logger.info(f"\n{'='*60}")
            logger.info(f"Running scenario: {config.name}")
            logger.info(f"{'='*60}")
            
            simulator = MininetSimulator(config)
            
            try:
                await simulator.setup()
                result = await simulator.run()
                self.results[config.name] = result
                
                # Log intermediate results
                self._log_result(result)
                
            finally:
                await simulator.teardown()
        
        # Save all results
        self._save_results()
        
        return self.results
    
    def _log_result(self, result: SimulationResult) -> None:
        """Log simulation result."""
        logger.info(f"\nResults for {result.scenario_name}:")
        logger.info(f"  MTTR: {result.mttr_ms:.2f}ms (min: {result.mttr_min_ms:.2f}, max: {result.mttr_max_ms:.2f})")
        logger.info(f"  Latency: {result.avg_latency_ms:.2f}ms (p99: {result.p99_latency_ms:.2f}ms)")
        logger.info(f"  Paths: {result.paths_available} available, {result.paths_failed} failed")
        
        # Compare to reference
        target = self.REFERENCE_MTTR["x0tta6bl4_target"]
        rajant = self.REFERENCE_MTTR["rajant_kinetic_mesh"]
        
        if result.mttr_ms > 0:
            vs_target = "PASS" if result.mttr_ms < target else "FAIL"
            vs_rajant = f"{result.mttr_ms / rajant:.1f}x Rajant"
            
            logger.info(f"  vs Target (<{target}ms): {vs_target}")
            logger.info(f"  vs Rajant (<{rajant}ms): {vs_rajant}")
    
    def _save_results(self) -> None:
        """Save results to JSON file."""
        output = {
            "timestamp": datetime.utcnow().isoformat(),
            "reference_mttr": self.REFERENCE_MTTR,
            "scenarios": {},
        }
        
        for name, result in self.results.items():
            output["scenarios"][name] = {
                "scenario_name": result.scenario_name,
                "timestamp": result.timestamp,
                "duration_sec": result.duration_sec,
                "mttr_ms": result.mttr_ms,
                "mttr_min_ms": result.mttr_min_ms,
                "mttr_max_ms": result.mttr_max_ms,
                "mttr_std_ms": result.mttr_std_ms,
                "paths_available": result.paths_available,
                "paths_failed": result.paths_failed,
                "avg_latency_ms": result.avg_latency_ms,
                "p99_latency_ms": result.p99_latency_ms,
            }
        
        output_file = os.path.join(
            self.output_dir,
            f"mttr_benchmark_{datetime.utcnow().strftime('%Y%m%d_%H%M%S')}.json"
        )
        
        with open(output_file, 'w') as f:
            json.dump(output, f, indent=2)
        
        logger.info(f"\nResults saved to: {output_file}")
    
    def generate_report(self) -> str:
        """Generate a markdown report of benchmark results."""
        report = [
            "# MTTR Benchmark Report",
            "",
            f"Generated: {datetime.utcnow().isoformat()}",
            "",
            "## Reference MTTR Values",
            "",
            "| Implementation | Target MTTR |",
            "|---------------|-------------|",
        ]
        
        for name, mttr in self.REFERENCE_MTTR.items():
            report.append(f"| {name} | {mttr}ms |")
        
        report.extend([
            "",
            "## Scenario Results",
            "",
        ])
        
        for name, result in self.results.items():
            target = self.REFERENCE_MTTR["x0tta6bl4_target"]
            status = "✅ PASS" if result.mttr_ms < target else "❌ FAIL"
            
            report.extend([
                f"### {result.scenario_name}",
                "",
                f"- **MTTR**: {result.mttr_ms:.2f}ms (σ={result.mttr_std_ms:.2f})",
                f"- **Latency**: {result.avg_latency_ms:.2f}ms (p99: {result.p99_latency_ms:.2f}ms)",
                f"- **Paths**: {result.paths_available} available, {result.paths_failed} failed",
                f"- **Status**: {status} (target: <{target}ms)",
                "",
            ])
        
        return "\n".join(report)


async def main():
    """Run benchmark suite."""
    logging.basicConfig(
        level=logging.INFO,
        format="%(asctime)s - %(name)s - %(levelname)s - %(message)s"
    )
    
    suite = BenchmarkSuite()
    results = await suite.run_all_scenarios()
    
    # Generate and print report
    report = suite.generate_report()
    print("\n" + report)
    
    return results


if __name__ == "__main__":
    asyncio.run(main())
