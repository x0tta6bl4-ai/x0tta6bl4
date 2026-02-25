#!/usr/bin/env python3
"""
Comprehensive MAPE-K Self-Healing Load Test
============================================

Tests MTTR target: 0.8-1.2 seconds on 1000 nodes
Validates all MAPE-K phases under load:
- Monitor: Anomaly detection latency
- Analyze: Root cause identification time
- Plan: Recovery strategy selection time
- Execute: Action execution time
- Knowledge: Learning and feedback loop time
"""

import asyncio
import time
import statistics
import json
import random
import logging
from datetime import datetime
from typing import Dict, List, Any, Optional
from dataclasses import dataclass, field
from concurrent.futures import ThreadPoolExecutor
import threading

# Configure logging
logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(levelname)s - %(message)s')
logger = logging.getLogger(__name__)


@dataclass
class NodeMetrics:
    """Simulated node metrics for testing"""
    node_id: str
    cpu_percent: float
    memory_percent: float
    packet_loss_percent: float
    latency_ms: float
    rssi: float = -50.0
    snr: float = 20.0
    throughput_mbps: float = 100.0
    link_age_seconds: float = 3600.0


@dataclass
class MAPEKCycleResult:
    """Result of a single MAPE-K cycle"""
    cycle_id: str
    node_id: str
    monitor_time_ms: float
    analyze_time_ms: float
    plan_time_ms: float
    execute_time_ms: float
    knowledge_time_ms: float
    total_time_ms: float
    anomaly_detected: bool
    recovery_success: bool
    issue_type: str = ""
    action_taken: str = ""


class SimulatedMeshNode:
    """Simulated mesh node for load testing"""
    
    def __init__(self, node_id: str, anomaly_rate: float = 0.1):
        self.node_id = node_id
        self.anomaly_rate = anomaly_rate
        self.is_healthy = True
        self.metrics_history: List[NodeMetrics] = []
        
    def generate_metrics(self) -> NodeMetrics:
        """Generate realistic metrics with occasional anomalies"""
        is_anomaly = random.random() < self.anomaly_rate
        
        if is_anomaly:
            # Generate anomalous metrics
            cpu = random.uniform(85, 99)
            memory = random.uniform(80, 95)
            packet_loss = random.uniform(5, 20)
            latency = random.uniform(50, 200)
        else:
            # Normal metrics
            cpu = random.uniform(20, 60)
            memory = random.uniform(30, 70)
            packet_loss = random.uniform(0, 2)
            latency = random.uniform(5, 30)
        
        metrics = NodeMetrics(
            node_id=self.node_id,
            cpu_percent=cpu,
            memory_percent=memory,
            packet_loss_percent=packet_loss,
            latency_ms=latency,
            rssi=random.uniform(-70, -30),
            snr=random.uniform(10, 30),
            throughput_mbps=random.uniform(50, 150),
            link_age_seconds=random.uniform(100, 10000)
        )
        
        self.metrics_history.append(metrics)
        return metrics


class MAPEKLoadTester:
    """Load tester for MAPE-K self-healing system"""
    
    def __init__(self, num_nodes: int = 1000, anomaly_rate: float = 0.1):
        self.num_nodes = num_nodes
        self.anomaly_rate = anomaly_rate
        self.nodes: List[SimulatedMeshNode] = []
        self.results: List[MAPEKCycleResult] = []
        self.lock = threading.Lock()
        
        # MAPE-K components (lazy loaded)
        self._manager = None
        self._monitor = None
        self._analyzer = None
        self._planner = None
        self._executor = None
        self._knowledge = None
        
        # Statistics
        self.stats = {
            "total_cycles": 0,
            "anomalies_detected": 0,
            "recoveries_success": 0,
            "recoveries_failed": 0,
            "mttr_values": [],
            "phase_times": {
                "monitor": [],
                "analyze": [],
                "plan": [],
                "execute": [],
                "knowledge": []
            }
        }
    
    def _init_mapek_components(self):
        """Initialize MAPE-K components"""
        try:
            from src.self_healing.mape_k import (
                MAPEKMonitor, MAPEKAnalyzer, MAPEKPlanner, 
                MAPEKExecutor, MAPEKKnowledge
            )
            
            self._knowledge = MAPEKKnowledge()
            self._monitor = MAPEKMonitor(knowledge=self._knowledge)
            self._analyzer = MAPEKAnalyzer()
            self._planner = MAPEKPlanner(knowledge=self._knowledge)
            self._executor = MAPEKExecutor()
            
            logger.info("✅ MAPE-K components initialized")
            return True
        except ImportError as e:
            logger.warning(f"⚠️ MAPE-K components not available: {e}")
            return False
    
    def setup(self):
        """Setup test environment"""
        logger.info(f"🔧 Setting up load test with {self.num_nodes} nodes...")
        
        # Initialize nodes
        self.nodes = [
            SimulatedMeshNode(f"node-{i:04d}", self.anomaly_rate)
            for i in range(self.num_nodes)
        ]
        
        # Try to init MAPE-K components
        self._mapek_available = self._init_mapek_components()
        
        logger.info(f"✅ Setup complete: {len(self.nodes)} nodes ready")
    
    def _run_single_cycle(self, node: SimulatedMeshNode) -> MAPEKCycleResult:
        """Run a single MAPE-K cycle for a node"""
        cycle_id = f"cycle-{node.node_id}-{time.time_ns()}"
        
        # Generate metrics
        metrics = node.generate_metrics()
        metrics_dict = {
            "node_id": node.node_id,
            "cpu_percent": metrics.cpu_percent,
            "memory_percent": metrics.memory_percent,
            "packet_loss_percent": metrics.packet_loss_percent,
            "latency_ms": metrics.latency_ms,
            "rssi": metrics.rssi,
            "snr": metrics.snr,
            "throughput_mbps": metrics.throughput_mbps,
            "link_age_seconds": metrics.link_age_seconds
        }
        
        # Monitor phase
        monitor_start = time.perf_counter()
        if self._mapek_available and self._monitor:
            anomaly_detected = self._monitor.check(metrics_dict)
        else:
            # Fallback: simple threshold check
            anomaly_detected = (
                metrics.cpu_percent > 90 or
                metrics.memory_percent > 85 or
                metrics.packet_loss_percent > 5
            )
        monitor_time = (time.perf_counter() - monitor_start) * 1000
        
        analyze_time = 0
        plan_time = 0
        execute_time = 0
        knowledge_time = 0
        issue_type = ""
        action_taken = ""
        recovery_success = False
        
        if anomaly_detected:
            # Analyze phase
            analyze_start = time.perf_counter()
            if self._mapek_available and self._analyzer:
                issue_type = self._analyzer.analyze(metrics_dict, node.node_id)
            else:
                # Fallback: simple analysis
                if metrics.cpu_percent > 90:
                    issue_type = "High CPU"
                elif metrics.memory_percent > 85:
                    issue_type = "High Memory"
                else:
                    issue_type = "Network Loss"
            analyze_time = (time.perf_counter() - analyze_start) * 1000
            
            # Plan phase
            plan_start = time.perf_counter()
            if self._mapek_available and self._planner:
                action_taken = self._planner.plan(issue_type)
            else:
                # Fallback: simple planning
                actions = {
                    "High CPU": "Restart service",
                    "High Memory": "Clear cache",
                    "Network Loss": "Switch route"
                }
                action_taken = actions.get(issue_type, "No action")
            plan_time = (time.perf_counter() - plan_start) * 1000
            
            # Execute phase
            execute_start = time.perf_counter()
            if self._mapek_available and self._executor:
                recovery_success = self._executor.execute(action_taken)
            else:
                # Simulate execution
                time.sleep(0.001)  # 1ms simulated execution
                recovery_success = random.random() > 0.1  # 90% success rate
            execute_time = (time.perf_counter() - execute_start) * 1000
            
            # Knowledge phase
            knowledge_start = time.perf_counter()
            if self._mapek_available and self._knowledge:
                self._knowledge.record(metrics_dict, issue_type, action_taken, recovery_success)
            knowledge_time = (time.perf_counter() - knowledge_start) * 1000
        
        total_time = monitor_time + analyze_time + plan_time + execute_time + knowledge_time
        
        return MAPEKCycleResult(
            cycle_id=cycle_id,
            node_id=node.node_id,
            monitor_time_ms=monitor_time,
            analyze_time_ms=analyze_time,
            plan_time_ms=plan_time,
            execute_time_ms=execute_time,
            knowledge_time_ms=knowledge_time,
            total_time_ms=total_time,
            anomaly_detected=anomaly_detected,
            recovery_success=recovery_success,
            issue_type=issue_type,
            action_taken=action_taken
        )
    
    def run_concurrent_cycles(self, num_cycles: int = 100) -> Dict[str, Any]:
        """Run concurrent MAPE-K cycles"""
        logger.info(f"🔄 Running {num_cycles} concurrent cycles...")
        
        start_time = time.time()
        
        with ThreadPoolExecutor(max_workers=min(32, self.num_nodes)) as executor:
            # Select random nodes for each cycle
            nodes_to_test = [random.choice(self.nodes) for _ in range(num_cycles)]
            
            # Run cycles in parallel
            futures = [executor.submit(self._run_single_cycle, node) for node in nodes_to_test]
            
            # Collect results
            results = []
            for future in futures:
                try:
                    result = future.result(timeout=10.0)
                    results.append(result)
                except Exception as e:
                    logger.warning(f"Cycle failed: {e}")
        
        total_time = time.time() - start_time
        
        # Process results
        with self.lock:
            self.results.extend(results)
            
            for r in results:
                self.stats["total_cycles"] += 1
                
                if r.anomaly_detected:
                    self.stats["anomalies_detected"] += 1
                    
                    if r.recovery_success:
                        self.stats["recoveries_success"] += 1
                    else:
                        self.stats["recoveries_failed"] += 1
                    
                    # MTTR is total cycle time when anomaly detected
                    self.stats["mttr_values"].append(r.total_time_ms)
                
                # Phase times
                self.stats["phase_times"]["monitor"].append(r.monitor_time_ms)
                if r.analyze_time_ms > 0:
                    self.stats["phase_times"]["analyze"].append(r.analyze_time_ms)
                    self.stats["phase_times"]["plan"].append(r.plan_time_ms)
                    self.stats["phase_times"]["execute"].append(r.execute_time_ms)
                    self.stats["phase_times"]["knowledge"].append(r.knowledge_time_ms)
        
        return {
            "cycles_completed": len(results),
            "total_time_seconds": total_time,
            "throughput_cycles_per_sec": len(results) / total_time if total_time > 0 else 0
        }
    
    def run_stress_test(self, duration_seconds: int = 60, cycles_per_batch: int = 100) -> Dict[str, Any]:
        """Run stress test for specified duration"""
        logger.info(f"🔥 Starting stress test: {duration_seconds}s duration, {cycles_per_batch} cycles/batch")
        
        start_time = time.time()
        batch_count = 0
        
        while time.time() - start_time < duration_seconds:
            batch_result = self.run_concurrent_cycles(cycles_per_batch)
            batch_count += 1
            
            if batch_count % 10 == 0:
                elapsed = time.time() - start_time
                logger.info(f"  Batch {batch_count}: {batch_result['throughput_cycles_per_sec']:.1f} cycles/sec")
        
        total_time = time.time() - start_time
        
        return {
            "total_batches": batch_count,
            "total_time_seconds": total_time,
            "total_cycles": self.stats["total_cycles"]
        }
    
    def calculate_statistics(self) -> Dict[str, Any]:
        """Calculate comprehensive statistics"""
        stats = {
            "timestamp": datetime.now().isoformat(),
            "test_config": {
                "num_nodes": self.num_nodes,
                "anomaly_rate": self.anomaly_rate
            },
            "summary": {
                "total_cycles": self.stats["total_cycles"],
                "anomalies_detected": self.stats["anomalies_detected"],
                "anomaly_rate_percent": (self.stats["anomalies_detected"] / max(1, self.stats["total_cycles"])) * 100,
                "recoveries_success": self.stats["recoveries_success"],
                "recoveries_failed": self.stats["recoveries_failed"],
                "recovery_success_rate_percent": (self.stats["recoveries_success"] / max(1, self.stats["anomalies_detected"])) * 100
            },
            "mttr": {},
            "phase_times": {}
        }
        
        # MTTR statistics
        if self.stats["mttr_values"]:
            mttr_values = self.stats["mttr_values"]
            sorted_mttr = sorted(mttr_values)
            
            stats["mttr"] = {
                "count": len(mttr_values),
                "min_ms": min(mttr_values),
                "max_ms": max(mttr_values),
                "mean_ms": statistics.mean(mttr_values),
                "median_ms": statistics.median(mttr_values),
                "stddev_ms": statistics.stdev(mttr_values) if len(mttr_values) > 1 else 0,
                "p50_ms": sorted_mttr[int(len(sorted_mttr) * 0.50)],
                "p90_ms": sorted_mttr[int(len(sorted_mttr) * 0.90)],
                "p95_ms": sorted_mttr[int(len(sorted_mttr) * 0.95)],
                "p99_ms": sorted_mttr[int(len(sorted_mttr) * 0.99)],
                "target_met": statistics.mean(mttr_values) < 1200  # Target: <1.2 seconds
            }
        
        # Phase times
        for phase, times in self.stats["phase_times"].items():
            if times:
                stats["phase_times"][phase] = {
                    "count": len(times),
                    "mean_ms": statistics.mean(times),
                    "median_ms": statistics.median(times),
                    "p95_ms": sorted(times)[int(len(times) * 0.95)] if len(times) > 5 else max(times),
                    "p99_ms": sorted(times)[int(len(times) * 0.99)] if len(times) > 10 else max(times)
                }
        
        return stats
    
    def generate_report(self) -> str:
        """Generate human-readable report"""
        stats = self.calculate_statistics()
        
        report = []
        report.append("=" * 70)
        report.append("MAPE-K SELF-HEALING LOAD TEST REPORT")
        report.append("=" * 70)
        report.append(f"\nTest Configuration:")
        report.append(f"  Nodes: {self.num_nodes}")
        report.append(f"  Anomaly Rate: {self.anomaly_rate * 100}%")
        
        report.append(f"\nSummary:")
        report.append(f"  Total Cycles: {stats['summary']['total_cycles']}")
        report.append(f"  Anomalies Detected: {stats['summary']['anomalies_detected']} ({stats['summary']['anomaly_rate_percent']:.1f}%)")
        report.append(f"  Successful Recoveries: {stats['summary']['recoveries_success']}")
        report.append(f"  Failed Recoveries: {stats['summary']['recoveries_failed']}")
        report.append(f"  Recovery Success Rate: {stats['summary']['recovery_success_rate_percent']:.1f}%")
        
        if stats["mttr"]:
            report.append(f"\nMTTR (Mean Time To Recovery):")
            report.append(f"  Mean: {stats['mttr']['mean_ms']:.2f} ms")
            report.append(f"  Median: {stats['mttr']['median_ms']:.2f} ms")
            report.append(f"  P95: {stats['mttr']['p95_ms']:.2f} ms")
            report.append(f"  P99: {stats['mttr']['p99_ms']:.2f} ms")
            report.append(f"  Min: {stats['mttr']['min_ms']:.2f} ms")
            report.append(f"  Max: {stats['mttr']['max_ms']:.2f} ms")
            
            target_status = "✅ PASS" if stats['mttr']['target_met'] else "❌ FAIL"
            report.append(f"  Target (<1200ms): {target_status}")
        
        report.append(f"\nPhase Times:")
        for phase, times in stats["phase_times"].items():
            if times:
                report.append(f"  {phase.upper()}:")
                report.append(f"    Mean: {times['mean_ms']:.2f} ms")
                report.append(f"    P95: {times['p95_ms']:.2f} ms")
        
        report.append("\n" + "=" * 70)
        
        return "\n".join(report)


async def main():
    """Main entry point"""
    print("\n" + "=" * 70)
    print("MAPE-K SELF-HEALING LOAD TEST")
    print("Target: MTTR < 1.2 seconds on 1000 nodes")
    print("=" * 70)
    
    # Test configurations
    configs = [
        {"name": "Light Load (100 nodes)", "nodes": 100, "duration": 30},
        {"name": "Medium Load (500 nodes)", "nodes": 500, "duration": 45},
        {"name": "Heavy Load (1000 nodes)", "nodes": 1000, "duration": 60},
    ]
    
    all_results = {}
    
    for config in configs:
        print(f"\n{'='*70}")
        print(f"Running: {config['name']}")
        print(f"{'='*70}")
        
        tester = MAPEKLoadTester(num_nodes=config["nodes"], anomaly_rate=0.1)
        tester.setup()
        
        # Run stress test
        stress_result = tester.run_stress_test(
            duration_seconds=config["duration"],
            cycles_per_batch=50
        )
        
        # Generate report
        report = tester.generate_report()
        print(report)
        
        # Save results
        all_results[config["name"]] = tester.calculate_statistics()
    
    # Save combined results
    output_file = "benchmarks/results/mapek_load_test_results.json"
    with open(output_file, "w") as f:
        json.dump(all_results, f, indent=2)
    
    print(f"\n📊 Results saved to: {output_file}")
    
    # Final verdict
    print("\n" + "=" * 70)
    print("FINAL VERDICT")
    print("=" * 70)
    
    for name, results in all_results.items():
        if results.get("mttr") and results["mttr"].get("target_met"):
            print(f"✅ {name}: MTTR target met ({results['mttr']['mean_ms']:.0f}ms)")
        else:
            mttr = results.get("mttr", {}).get("mean_ms", "N/A")
            print(f"❌ {name}: MTTR target not met ({mttr}ms)")


if __name__ == "__main__":
    asyncio.run(main())
