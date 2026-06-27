"""
MAPE-K Tuning Benchmark Suite

Comprehensive benchmarking for self-learning thresholds,
dynamic optimization, and feedback loops.
"""

import time
import json
import logging
from pathlib import Path
from typing import Dict, Any, List
import numpy as np

logger = logging.getLogger(__name__)


class MAPEKTuningBenchmark:
    """Benchmark suite for MAPE-K tuning components"""
    
    def __init__(self, output_dir: str = "benchmarks/results"):
        self.output_dir = Path(output_dir)
        self.output_dir.mkdir(exist_ok=True)
        self.results = {}
    
    async def benchmark_self_learning(self) -> Dict[str, Any]:
        """Benchmark self-learning optimizer"""
        from src.core.mape_k_self_learning import (
            SelfLearningThresholdOptimizer
        )
        
        print("\n📊 Benchmarking Self-Learning Threshold Optimizer...")
        
        results = {
            'component': 'self_learning',
            'metrics_per_parameter': {},
            'total_time': 0
        }
        
        opt = SelfLearningThresholdOptimizer(min_data_points=50)
        
        # Benchmark: Adding metrics
        print("  - Adding metrics...")
        start = time.time()
        for param in ['cpu', 'memory', 'latency', 'packet_loss']:
            for i in range(1000):
                opt.add_metric(param, float(i % 100))
        add_time = time.time() - start
        results['metrics_per_parameter']['add_metrics'] = {
            'total_time_ms': add_time * 1000,
            'operations': 4000,
            'ops_per_sec': 4000 / add_time
        }
        
        # Benchmark: Optimization
        print("  - Optimizing thresholds...")
        start = time.time()
        recommendations = opt.optimize_thresholds()
        opt_time = time.time() - start
        results['metrics_per_parameter']['optimize'] = {
            'time_ms': opt_time * 1000,
            'parameters_optimized': len(recommendations),
            'time_per_parameter_ms': (opt_time * 1000) / max(1, len(recommendations))
        }
        
        # Benchmark: Anomaly detection
        print("  - Detecting anomalies...")
        start = time.time()
        for param in ['cpu', 'memory']:
            anomalies = opt.detect_anomalies(param)
        detect_time = time.time() - start
        results['metrics_per_parameter']['anomaly_detection'] = {
            'time_ms': detect_time * 1000,
            'parameters': 2
        }
        
        # Benchmark: Statistics calculation
        print("  - Calculating statistics...")
        start = time.time()
        for param in ['cpu', 'memory', 'latency', 'packet_loss']:
            stats = opt.get_statistics(param)
        stats_time = time.time() - start
        results['metrics_per_parameter']['statistics'] = {
            'time_ms': stats_time * 1000,
            'parameters': 4,
            'time_per_param_ms': (stats_time * 1000) / 4
        }
        
        results['total_time'] = add_time + opt_time + detect_time + stats_time
        return results
    
    async def benchmark_dynamic_optimizer(self) -> Dict[str, Any]:
        """Benchmark dynamic optimizer"""
        from src.core.mape_k_dynamic_optimizer import (
            DynamicOptimizer,
            SystemState,
            PerformanceMetrics
        )
        
        print("\n📊 Benchmarking Dynamic Optimizer...")
        
        results = {
            'component': 'dynamic_optimizer',
            'state_transitions': {},
            'total_time': 0
        }
        
        dyn_opt = DynamicOptimizer()
        
        # Benchmark: State analysis
        print("  - Analyzing system states...")
        states = [
            SystemState.HEALTHY,
            SystemState.DEGRADED,
            SystemState.CRITICAL,
            SystemState.RECOVERING,
            SystemState.OPTIMIZING
        ]
        
        metrics_samples = [
            PerformanceMetrics(50.0, 60.0, 1.0, 40, 0.9, 0.9, 0.02),
            PerformanceMetrics(70.0, 75.0, 2.0, 30, 0.8, 0.8, 0.08),
            PerformanceMetrics(85.0, 88.0, 6.0, 15, 0.6, 0.6, 0.15),
            PerformanceMetrics(60.0, 65.0, 1.5, 35, 0.85, 0.85, 0.05),
        ]
        
        start = time.time()
        for i in range(100):
            dyn_opt.record_performance(metrics_samples[i % 4])
        record_time = time.time() - start
        
        results['state_transitions']['record_performance'] = {
            'operations': 100,
            'time_ms': record_time * 1000,
            'ops_per_sec': 100 / record_time
        }
        
        # Benchmark: Optimization
        print("  - Optimizing parameters...")
        start = time.time()
        for state in states:
            params = dyn_opt.optimize(state)
        opt_time = time.time() - start
        results['state_transitions']['optimize'] = {
            'states': len(states),
            'time_ms': opt_time * 1000,
            'time_per_state_ms': (opt_time * 1000) / len(states)
        }
        
        results['total_time'] = record_time + opt_time
        return results
    
    async def benchmark_feedback_loops(self) -> Dict[str, Any]:
        """Benchmark feedback loop manager"""
        from src.core.mape_k_feedback_loops import (
            FeedbackLoopManager,
            FeedbackLoopType
        )
        from src.core.mape_k_self_learning import SelfLearningThresholdOptimizer
        from src.core.mape_k_dynamic_optimizer import DynamicOptimizer
        
        print("\n📊 Benchmarking Feedback Loop Manager...")
        
        results = {
            'component': 'feedback_loops',
            'signals': {},
            'total_time': 0
        }
        
        self_learning = SelfLearningThresholdOptimizer(min_data_points=50)
        dyn_opt = DynamicOptimizer()
        mgr = FeedbackLoopManager(self_learning, dyn_opt)
        
        # Prepare data
        for i in range(100):
            self_learning.add_metric("cpu", float(i % 80))
        self_learning.optimize_thresholds()
        
        # Benchmark: Metrics learning signals
        print("  - Signaling metrics learning...")
        start = time.time()
        for i in range(100):
            mgr.signal_metrics_learning("cpu", 80.0 + np.random.randn() * 5, 0.9)
        signal_time = time.time() - start
        results['signals']['metrics_learning'] = {
            'signals': 100,
            'time_ms': signal_time * 1000,
            'signals_per_sec': 100 / signal_time
        }
        
        # Benchmark: Performance degradation signals
        print("  - Signaling performance degradation...")
        start = time.time()
        for i in range(100):
            mgr.signal_performance_degradation(
                cpu_usage=70.0 + np.random.randn() * 5,
                memory_usage=75.0 + np.random.randn() * 5,
                latency_ms=2.0 + np.random.rand()
            )
        perf_time = time.time() - start
        results['signals']['performance_degradation'] = {
            'signals': 100,
            'time_ms': perf_time * 1000,
            'signals_per_sec': 100 / perf_time
        }
        
        # Benchmark: Decision quality signals
        print("  - Signaling decision quality...")
        start = time.time()
        for i in range(100):
            mgr.signal_decision_quality(
                decision_id=f"d_{i}",
                predicted_outcome=100.0 + np.random.randn() * 10,
                actual_outcome=100.0 + np.random.randn() * 10
            )
        quality_time = time.time() - start
        results['signals']['decision_quality'] = {
            'signals': 100,
            'time_ms': quality_time * 1000,
            'signals_per_sec': 100 / quality_time
        }
        
        # Benchmark: History retrieval
        print("  - Retrieving history...")
        start = time.time()
        signal_hist = mgr.get_signal_history(limit=1000)
        action_hist = mgr.get_action_history(limit=1000)
        hist_time = time.time() - start
        results['signals']['history_retrieval'] = {
            'signals_retrieved': len(signal_hist),
            'actions_retrieved': len(action_hist),
            'time_ms': hist_time * 1000
        }
        
        results['total_time'] = signal_time + perf_time + quality_time + hist_time
        return results
    
    async def run_all_benchmarks(self):
        """Run all benchmarks"""
        print("\n" + "="*60)
        print("MAPE-K TUNING BENCHMARK SUITE")
        print("="*60)
        
        self.results['self_learning'] = await self.benchmark_self_learning()
        self.results['dynamic_optimizer'] = await self.benchmark_dynamic_optimizer()
        self.results['feedback_loops'] = await self.benchmark_feedback_loops()
        
        # Save results
        self._save_results()
        
        # Print summary
        self._print_summary()
    
    def _save_results(self):
        """Save benchmark results to JSON"""
        output_file = self.output_dir / "mape_k_tuning_benchmarks.json"
        with open(output_file, 'w') as f:
            json.dump(self.results, f, indent=2)
        print(f"\n✅ Results saved to {output_file}")
    
    def _print_summary(self):
        """Print benchmark summary"""
        print("\n" + "="*60)
        print("SUMMARY")
        print("="*60)
        
        for component, data in self.results.items():
            print(f"\n{component.upper()}:")
            if 'total_time' in data:
                print(f"  Total time: {data['total_time']*1000:.2f}ms")
            
            if 'metrics_per_parameter' in data:
                for op, metrics in data['metrics_per_parameter'].items():
                    if 'ops_per_sec' in metrics:
                        print(f"  {op}: {metrics['ops_per_sec']:.0f} ops/sec")
                    if 'time_ms' in metrics:
                        print(f"  {op}: {metrics['time_ms']:.2f}ms")
            
            if 'state_transitions' in data:
                for op, metrics in data['state_transitions'].items():
                    if 'ops_per_sec' in metrics:
                        print(f"  {op}: {metrics['ops_per_sec']:.0f} ops/sec")
            
            if 'signals' in data:
                for signal_type, metrics in data['signals'].items():
                    if 'signals_per_sec' in metrics:
                        print(f"  {signal_type}: {metrics['signals_per_sec']:.0f} signals/sec")


async def main():
    """Run benchmark suite"""
    benchmark = MAPEKTuningBenchmark()
    await benchmark.run_all_benchmarks()


if __name__ == "__main__":
    import asyncio
    asyncio.run(main())
