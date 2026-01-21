"""
Distributed Load Generator for x0tta6bl4
========================================

Simulates 1000+ node mesh network for performance validation.

Components:
1. DistributedLoadGenerator - Master orchestrator
2. VirtualMeshNode - Individual node simulator
3. PerformanceAnalyzer - Results analysis
4. TrafficPattern - Load profile definitions
5. FailureInjector - Controlled failure simulation

Usage:
  # Run load test with 1000 nodes
  gen = DistributedLoadGenerator(node_count=1000, duration_seconds=3600)
  result = gen.run_steady_state_test()
  report = result.generate_report()
"""

import json
import time
import statistics
import asyncio
from dataclasses import dataclass, asdict, field
from typing import Dict, List, Tuple, Optional, Any
from datetime import datetime, timedelta
from pathlib import Path
import random
import logging

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)


@dataclass
class BeaconMessage:
    """Mesh beacon message"""
    node_id: str
    timestamp: float
    slot_number: int
    signature: bytes = b"signature"
    spiffe_id: str = ""
    
    def to_dict(self) -> Dict:
        return asdict(self)


@dataclass
class NodeMetrics:
    """Metrics collected by a single node"""
    node_id: str
    beacon_latencies: List[float] = field(default_factory=list)
    pqc_operation_times: List[float] = field(default_factory=list)
    spiffe_rotation_times: List[float] = field(default_factory=list)
    cpu_usage: float = 0.0
    memory_usage_mb: float = 0.0
    beacons_processed: int = 0
    beacons_failed: int = 0
    signatures_verified: int = 0
    signatures_failed: int = 0
    identity_rotations: int = 0
    last_update: float = field(default_factory=time.time)


@dataclass
class LoadTestResult:
    """Complete test results"""
    test_name: str
    node_count: int
    duration_seconds: int
    start_time: str
    end_time: str
    
    # Aggregate metrics
    total_beacons: int = 0
    total_pqc_ops: int = 0
    total_identity_ops: int = 0
    
    # Latency metrics (milliseconds)
    beacon_latencies: List[float] = field(default_factory=list)
    pqc_latencies: List[float] = field(default_factory=list)
    spiffe_latencies: List[float] = field(default_factory=list)
    
    # Node metrics
    node_metrics: Dict[str, NodeMetrics] = field(default_factory=dict)
    
    # Resource utilization
    peak_cpu: float = 0.0
    peak_memory_mb: float = 0.0
    avg_cpu: float = 0.0
    avg_memory_mb: float = 0.0
    
    # Failure recovery
    failures_injected: List[str] = field(default_factory=list)
    recovery_times: List[float] = field(default_factory=list)
    
    def calculate_percentiles(self, values: List[float]) -> Dict[str, float]:
        """Calculate latency percentiles"""
        if not values:
            return {"p50": 0, "p95": 0, "p99": 0}
        
        sorted_vals = sorted(values)
        n = len(sorted_vals)
        return {
            "p50": sorted_vals[int(n * 0.50)],
            "p95": sorted_vals[int(n * 0.95)],
            "p99": sorted_vals[int(n * 0.99)],
            "min": min(sorted_vals),
            "max": max(sorted_vals),
            "mean": statistics.mean(sorted_vals),
            "stdev": statistics.stdev(sorted_vals) if len(sorted_vals) > 1 else 0,
        }
    
    def generate_report(self) -> Dict[str, Any]:
        """Generate complete test report"""
        beacon_stats = self.calculate_percentiles(self.beacon_latencies)
        pqc_stats = self.calculate_percentiles(self.pqc_latencies)
        spiffe_stats = self.calculate_percentiles(self.spiffe_latencies)
        
        return {
            "metadata": {
                "test_name": self.test_name,
                "node_count": self.node_count,
                "duration_seconds": self.duration_seconds,
                "start_time": self.start_time,
                "end_time": self.end_time,
                "timestamp": datetime.utcnow().isoformat(),
            },
            "summary": {
                "total_beacons_processed": self.total_beacons,
                "total_pqc_operations": self.total_pqc_ops,
                "total_identity_operations": self.total_identity_ops,
                "beacon_throughput": self.total_beacons / self.duration_seconds if self.duration_seconds > 0 else 0,
                "pqc_throughput": self.total_pqc_ops / self.duration_seconds if self.duration_seconds > 0 else 0,
            },
            "beacon_latency_ms": beacon_stats,
            "pqc_latency_ms": pqc_stats,
            "spiffe_latency_ms": spiffe_stats,
            "resource_utilization": {
                "peak_cpu_percent": self.peak_cpu,
                "peak_memory_mb": self.peak_memory_mb,
                "avg_cpu_percent": self.avg_cpu,
                "avg_memory_mb": self.avg_memory_mb,
            },
            "failure_recovery": {
                "failures_injected": self.failures_injected,
                "recovery_times_seconds": self.recovery_times,
                "avg_recovery_time": statistics.mean(self.recovery_times) if self.recovery_times else 0,
            },
            "scaling_analysis": {
                "latency_per_thousand_nodes": (beacon_stats["p99"] / self.node_count) * 1000,
                "efficiency_percent": (100 / (1 + (beacon_stats["p99"] - beacon_stats["p50"]))) if beacon_stats["p50"] > 0 else 0,
            }
        }


class TrafficPattern:
    """Load traffic pattern definition"""
    
    def __init__(self, name: str, beacon_rate: float = 1.0, 
                 pqc_ops_rate: float = 100, identity_rotation_interval: int = 600):
        self.name = name
        self.beacon_rate = beacon_rate  # beacons per second per node
        self.pqc_ops_rate = pqc_ops_rate  # operations per second (cluster)
        self.identity_rotation_interval = identity_rotation_interval  # seconds
    
    @staticmethod
    def steady_state() -> 'TrafficPattern':
        """Normal production load"""
        return TrafficPattern("steady_state", beacon_rate=1.0, pqc_ops_rate=100)
    
    @staticmethod
    def burst() -> 'TrafficPattern':
        """Burst traffic (10x normal)"""
        return TrafficPattern("burst", beacon_rate=10.0, pqc_ops_rate=1000)
    
    @staticmethod
    def high_churn() -> 'TrafficPattern':
        """High identity churn"""
        return TrafficPattern("high_churn", beacon_rate=1.0, 
                            pqc_ops_rate=100, identity_rotation_interval=60)


class FailurePattern:
    """Failure injection pattern"""
    
    def __init__(self, failure_type: str, start_time: float, 
                 duration: float = 10.0, intensity: float = 0.05):
        self.failure_type = failure_type  # "node_crash", "network_partition", "byzantine", "identity_loss"
        self.start_time = start_time
        self.duration = duration
        self.intensity = intensity  # % of nodes affected
    
    @staticmethod
    def node_crash(start_time: float) -> 'FailurePattern':
        """5% of nodes crash at start_time"""
        return FailurePattern("node_crash", start_time, duration=30.0, intensity=0.05)
    
    @staticmethod
    def network_partition(start_time: float) -> 'FailurePattern':
        """50-50 network partition"""
        return FailurePattern("network_partition", start_time, duration=60.0, intensity=0.5)
    
    @staticmethod
    def byzantine_nodes(start_time: float) -> 'FailurePattern':
        """5% of nodes send invalid data"""
        return FailurePattern("byzantine", start_time, duration=120.0, intensity=0.05)


class VirtualMeshNode:
    """Simulates a single mesh node"""
    
    def __init__(self, node_id: str, node_index: int = 0):
        self.node_id = node_id
        self.node_index = node_index
        self.metrics = NodeMetrics(node_id=node_id)
        self.last_beacon_time = time.time()
        self.last_identity_rotation = time.time()
        self.is_failed = False
        self.is_byzantine = False
        self.spiffe_id = f"spiffe://x0tta6bl4.mesh/node/{node_id}"
    
    def process_beacon(self, beacon: BeaconMessage) -> Tuple[bool, float]:
        """
        Process incoming beacon
        Returns: (success: bool, latency_ms: float)
        """
        if self.is_failed:
            return False, 0.0
        
        processing_start = time.time()
        
        # Simulate beacon processing
        # 1. Parse beacon (0.01ms)
        # 2. Verify signature (0.1-0.5ms depending on scale)
        # 3. Update topology (0.05ms)
        # 4. Check identity (0.05ms)
        
        latency = random.uniform(0.1, 0.5) + (self.node_index / 10000.0)  # Scale dependent
        time.sleep(latency / 1000.0)  # Simulate processing
        
        processing_end = time.time()
        actual_latency_ms = (processing_end - processing_start) * 1000
        
        success = random.random() > 0.0001  # 99.99% success
        if success:
            self.metrics.beacons_processed += 1
            self.metrics.signatures_verified += 1
        else:
            self.metrics.beacons_failed += 1
            self.metrics.signatures_failed += 1
        
        self.metrics.beacon_latencies.append(actual_latency_ms)
        return success, actual_latency_ms
    
    def generate_beacon(self) -> Optional[BeaconMessage]:
        """Generate outgoing beacon"""
        if self.is_failed:
            return None
        
        beacon = BeaconMessage(
            node_id=self.node_id,
            timestamp=time.time(),
            slot_number=int(time.time()),
            spiffe_id=self.spiffe_id,
        )
        
        # If byzantine, send invalid signature
        if self.is_byzantine:
            beacon.signature = b"invalid_signature_" + str(random.random()).encode()
        
        return beacon
    
    def simulate_pqc_operation(self) -> float:
        """Simulate PQC operation (signature, verification, KEM)"""
        if self.is_failed:
            return 0.0
        
        operation_start = time.time()
        
        # Simulate PQC operation latency
        # KEM operations: 0.45-2ms
        # DSA operations: 0.8-1.5ms
        operation_type = random.choice(["kem", "dsa"])
        
        if operation_type == "kem":
            latency = random.uniform(0.45, 2.0)
        else:
            latency = random.uniform(0.8, 1.5)
        
        time.sleep(latency / 1000.0)
        
        operation_end = time.time()
        actual_latency_ms = (operation_end - operation_start) * 1000
        
        self.metrics.pqc_operation_times.append(actual_latency_ms)
        return actual_latency_ms
    
    def rotate_identity(self) -> float:
        """Simulate SPIFFE identity rotation"""
        if self.is_failed:
            return 0.0
        
        rotation_start = time.time()
        
        # Simulate SVID rotation (typically 100-500ms)
        latency = random.uniform(0.1, 0.5)
        time.sleep(latency / 1000.0)
        
        rotation_end = time.time()
        actual_latency_ms = (rotation_end - rotation_start) * 1000
        
        self.metrics.spiffe_rotation_times.append(actual_latency_ms)
        self.metrics.identity_rotations += 1
        self.last_identity_rotation = time.time()
        
        return actual_latency_ms
    
    def check_should_rotate(self, interval: int) -> bool:
        """Check if identity rotation is needed"""
        return (time.time() - self.last_identity_rotation) > interval
    
    def inject_failure(self, failure_pattern: FailurePattern):
        """Inject failure into this node"""
        if failure_pattern.failure_type == "node_crash":
            self.is_failed = True
        elif failure_pattern.failure_type == "byzantine":
            self.is_byzantine = True
    
    def recover(self):
        """Recover from failure"""
        self.is_failed = False
        self.is_byzantine = False


class PerformanceAnalyzer:
    """Analyzes load test results"""
    
    @staticmethod
    def analyze_beacon_latency(result: LoadTestResult) -> Dict[str, Any]:
        """Analyze beacon processing latency"""
        latencies = result.beacon_latencies
        if not latencies:
            return {}
        
        sorted_lats = sorted(latencies)
        n = len(sorted_lats)
        mean_val = statistics.mean(sorted_lats)
        stdev_val = statistics.stdev(sorted_lats) if n > 1 else 0
        
        # Count outliers
        if n > 1 and stdev_val > 0:
            threshold = mean_val + 3 * stdev_val
            outlier_count = sum(1 for x in sorted_lats if x > threshold)
        else:
            outlier_count = 0
        
        return {
            "count": n,
            "p50_ms": sorted_lats[int(n * 0.50)],
            "p95_ms": sorted_lats[int(n * 0.95)],
            "p99_ms": sorted_lats[int(n * 0.99)],
            "max_ms": max(sorted_lats),
            "min_ms": min(sorted_lats),
            "mean_ms": mean_val,
            "stdev_ms": stdev_val,
            "outliers": outlier_count,
        }
    
    @staticmethod
    def identify_bottleneck(result: LoadTestResult) -> str:
        """Identify scaling bottleneck"""
        beacon_stats = PerformanceAnalyzer.analyze_beacon_latency(result)
        
        if not beacon_stats:
            return "No metrics collected"
        
        latency_degradation = (beacon_stats["p99_ms"] - beacon_stats["p50_ms"]) / beacon_stats["p50_ms"]
        
        if latency_degradation > 0.5:
            return "High variance suggests contention - likely PQC operations are bottleneck"
        elif beacon_stats["p99_ms"] > 100:
            return "High latency at 1000+ nodes - network or synchronization overhead"
        elif beacon_stats["mean_ms"] > 50:
            return "Elevated mean latency - per-node processing cost increasing"
        else:
            return "Scaling is acceptable - no major bottleneck identified"
    
    @staticmethod
    def predict_scaling(results_by_count: Dict[int, LoadTestResult]) -> Dict[str, Any]:
        """Predict scaling characteristics"""
        if len(results_by_count) < 2:
            return {"error": "Need at least 2 data points"}
        
        # Linear regression for latency vs node count
        node_counts = sorted(results_by_count.keys())
        latencies = []
        
        for count in node_counts:
            result = results_by_count[count]
            beacon_stats = PerformanceAnalyzer.analyze_beacon_latency(result)
            latencies.append(beacon_stats.get("p99_ms", 0))
        
        # Simple linear fit
        if len(node_counts) >= 2:
            x_mean = statistics.mean(node_counts)
            y_mean = statistics.mean(latencies)
            
            numerator = sum((node_counts[i] - x_mean) * (latencies[i] - y_mean) 
                          for i in range(len(node_counts)))
            denominator = sum((node_counts[i] - x_mean) ** 2 for i in range(len(node_counts)))
            
            slope = numerator / denominator if denominator != 0 else 0
            intercept = y_mean - slope * x_mean
            
            # Predict for 2000 nodes
            predicted_2000 = slope * 2000 + intercept
            
            return {
                "slope": slope,
                "intercept": intercept,
                "r_squared": PerformanceAnalyzer._calculate_r_squared(node_counts, latencies, slope, intercept),
                "predicted_latency_at_2000_nodes": predicted_2000,
                "scaling_type": "linear" if slope > 0.001 else "sublinear",
                "feasible_for_1000": latencies[-1] < 100,
                "feasible_for_2000": predicted_2000 < 300,
            }
        
        return {}
    
    @staticmethod
    def _calculate_r_squared(x_vals: List[float], y_vals: List[float], 
                            slope: float, intercept: float) -> float:
        """Calculate R² for linear fit"""
        y_mean = statistics.mean(y_vals)
        ss_res = sum((y_vals[i] - (slope * x_vals[i] + intercept)) ** 2 
                     for i in range(len(x_vals)))
        ss_tot = sum((y_vals[i] - y_mean) ** 2 for i in range(len(y_vals)))
        return 1 - (ss_res / ss_tot) if ss_tot != 0 else 0


class DistributedLoadGenerator:
    """Master load test orchestrator"""
    
    def __init__(self, node_count: int, duration_seconds: int = 3600):
        self.node_count = node_count
        self.duration_seconds = duration_seconds
        self.nodes: List[VirtualMeshNode] = []
        self.start_time = None
        self.end_time = None
        self.result: Optional[LoadTestResult] = None
    
    def spawn_mesh_nodes(self) -> List[VirtualMeshNode]:
        """Create virtual mesh nodes"""
        logger.info(f"Spawning {self.node_count} virtual mesh nodes")
        self.nodes = []
        
        for i in range(self.node_count):
            node = VirtualMeshNode(f"node-{i}", node_index=i)
            self.nodes.append(node)
        
        logger.info(f"✅ Spawned {len(self.nodes)} nodes")
        return self.nodes
    
    def run_steady_state_test(self, pattern: Optional[TrafficPattern] = None) -> LoadTestResult:
        """Run steady-state load test"""
        if pattern is None:
            pattern = TrafficPattern.steady_state()
        
        logger.info(f"Starting load test: {self.node_count} nodes, {pattern.name}")
        self.spawn_mesh_nodes()
        
        self.result = LoadTestResult(
            test_name=f"steady_state_{pattern.name}",
            node_count=self.node_count,
            duration_seconds=self.duration_seconds,
            start_time=datetime.utcnow().isoformat(),
            end_time="",
        )
        
        self.start_time = time.time()
        elapsed = 0
        iteration = 0
        
        while elapsed < self.duration_seconds:
            iteration += 1
            
            # Beacon generation and processing
            beacon_count = int(self.node_count * pattern.beacon_rate)
            for i in range(beacon_count):
                node_idx = random.randint(0, self.node_count - 1)
                node = self.nodes[node_idx]
                
                beacon = node.generate_beacon()
                if beacon:
                    # Process at other nodes
                    for j in range(min(10, self.node_count)):  # Process at 10 random nodes
                        target_node = self.nodes[random.randint(0, self.node_count - 1)]
                        success, latency = target_node.process_beacon(beacon)
                        if success:
                            self.result.total_beacons += 1
                            self.result.beacon_latencies.append(latency)
            
            # PQC operations
            pqc_ops = int(pattern.pqc_ops_rate / 10)  # Iterate 10x per check
            for _ in range(pqc_ops):
                node = self.nodes[random.randint(0, self.node_count - 1)]
                latency = node.simulate_pqc_operation()
                if latency > 0:
                    self.result.total_pqc_ops += 1
                    self.result.pqc_latencies.append(latency)
            
            # Identity rotations
            for node in self.nodes:
                if node.check_should_rotate(pattern.identity_rotation_interval):
                    latency = node.rotate_identity()
                    if latency > 0:
                        self.result.total_identity_ops += 1
                        self.result.spiffe_latencies.append(latency)
            
            # Log progress every 60 iterations
            if iteration % 60 == 0:
                elapsed = time.time() - self.start_time
                logger.info(f"Progress: {elapsed:.1f}s / {self.duration_seconds}s "
                           f"({int(elapsed/self.duration_seconds*100)}%)")
            
            # Small sleep to avoid busy loop
            time.sleep(0.01)
            elapsed = time.time() - self.start_time
        
        self.end_time = time.time()
        self.result.end_time = datetime.utcnow().isoformat()
        
        # Aggregate node metrics
        for node in self.nodes:
            self.result.node_metrics[node.node_id] = node.metrics
        
        logger.info(f"✅ Test complete: {self.result.total_beacons} beacons, "
                   f"{self.result.total_pqc_ops} PQC ops")
        
        return self.result
    
    def run_failure_injection_test(self, failure_patterns: List[FailurePattern],
                                   pattern: Optional[TrafficPattern] = None) -> LoadTestResult:
        """Run test with failure injection"""
        if pattern is None:
            pattern = TrafficPattern.steady_state()
        
        logger.info(f"Starting failure injection test with {len(failure_patterns)} patterns")
        self.spawn_mesh_nodes()
        
        self.result = LoadTestResult(
            test_name=f"failure_injection",
            node_count=self.node_count,
            duration_seconds=self.duration_seconds,
            start_time=datetime.utcnow().isoformat(),
            end_time="",
        )
        
        self.start_time = time.time()
        active_failures: Dict[str, float] = {}  # failure_id -> end_time
        
        for failure_pattern in failure_patterns:
            active_failures[failure_pattern.failure_type] = failure_pattern.start_time + failure_pattern.duration
        
        elapsed = 0
        iteration = 0
        
        while elapsed < self.duration_seconds:
            iteration += 1
            elapsed = time.time() - self.start_time
            
            # Check and inject failures
            for failure_pattern in failure_patterns:
                if failure_pattern.start_time <= elapsed < failure_pattern.start_time + failure_pattern.duration:
                    # Inject failure
                    affected_count = int(self.node_count * failure_pattern.intensity)
                    for i in range(affected_count):
                        if i < len(self.nodes):
                            self.nodes[i].inject_failure(failure_pattern)
                            if i == 0:  # Log once
                                logger.info(f"Injected {failure_pattern.failure_type} at {elapsed:.1f}s")
                else:
                    # Recover from failure
                    if failure_pattern.start_time + failure_pattern.duration <= elapsed:
                        affected_count = int(self.node_count * failure_pattern.intensity)
                        for i in range(affected_count):
                            if i < len(self.nodes):
                                if self.nodes[i].is_failed or self.nodes[i].is_byzantine:
                                    self.nodes[i].recover()
                                    recovery_time = elapsed - failure_pattern.start_time
                                    self.result.recovery_times.append(recovery_time)
                                    if i == 0:  # Log once
                                        logger.info(f"Recovered from {failure_pattern.failure_type} "
                                                   f"in {recovery_time:.1f}s")
            
            # Normal operations during failure
            beacon_count = int(self.node_count * pattern.beacon_rate)
            for i in range(beacon_count):
                node_idx = random.randint(0, self.node_count - 1)
                node = self.nodes[node_idx]
                
                beacon = node.generate_beacon()
                if beacon:
                    for j in range(min(10, self.node_count)):
                        target_node = self.nodes[random.randint(0, self.node_count - 1)]
                        success, latency = target_node.process_beacon(beacon)
                        if success:
                            self.result.total_beacons += 1
                            self.result.beacon_latencies.append(latency)
            
            # PQC operations
            pqc_ops = int(pattern.pqc_ops_rate / 10)
            for _ in range(pqc_ops):
                node = self.nodes[random.randint(0, self.node_count - 1)]
                latency = node.simulate_pqc_operation()
                if latency > 0:
                    self.result.total_pqc_ops += 1
                    self.result.pqc_latencies.append(latency)
            
            # Small sleep
            time.sleep(0.01)
        
        self.end_time = time.time()
        self.result.end_time = datetime.utcnow().isoformat()
        self.result.failures_injected = [p.failure_type for p in failure_patterns]
        
        # Aggregate node metrics
        for node in self.nodes:
            self.result.node_metrics[node.node_id] = node.metrics
        
        logger.info(f"✅ Failure injection test complete")
        
        return self.result


def main():
    """Example usage"""
    import sys
    
    # Test configurations
    test_configs = [
        (100, 60),    # 100 nodes, 60 seconds
        (500, 120),   # 500 nodes, 120 seconds
        (1000, 180),  # 1000 nodes, 180 seconds
    ]
    
    all_results = {}
    
    for node_count, duration in test_configs:
        logger.info(f"\n{'='*60}")
        logger.info(f"Running test: {node_count} nodes for {duration}s")
        logger.info(f"{'='*60}")
        
        gen = DistributedLoadGenerator(node_count, duration)
        result = gen.run_steady_state_test()
        all_results[node_count] = result
        
        # Print results
        report = result.generate_report()
        logger.info(f"\nResults for {node_count} nodes:")
        logger.info(f"  Beacons: {report['summary']['total_beacons_processed']}")
        logger.info(f"  Beacon p99: {report['beacon_latency_ms']['p99']:.2f}ms")
        logger.info(f"  PQC ops: {report['summary']['total_pqc_operations']}")
        logger.info(f"  PQC p99: {report['pqc_latency_ms']['p99']:.2f}ms")
    
    # Scaling analysis
    logger.info(f"\n{'='*60}")
    logger.info("Scaling Analysis")
    logger.info(f"{'='*60}")
    
    scaling_analysis = PerformanceAnalyzer.predict_scaling(all_results)
    logger.info(f"Scaling slope: {scaling_analysis.get('slope', 0):.6f}ms per node")
    logger.info(f"Feasible for 1000 nodes: {scaling_analysis.get('feasible_for_1000', False)}")
    logger.info(f"Feasible for 2000 nodes: {scaling_analysis.get('feasible_for_2000', False)}")
    
    # Save results
    results_file = Path("benchmarks/results/load_test_results.json")
    results_file.parent.mkdir(parents=True, exist_ok=True)
    
    with open(results_file, 'w') as f:
        output = {
            k: v.generate_report() for k, v in all_results.items()
        }
        json.dump(output, f, indent=2)
    
    logger.info(f"\n✅ Results saved to {results_file}")


if __name__ == "__main__":
    main()
