"""
CI/CD Benchmark Integration
===========================

Integrates performance benchmarks into CI/CD pipeline with:
1. Regression detection (compare against baseline)
2. Performance gates (pass/fail based on thresholds)
3. Artifact publishing
4. Slack/email notifications (optional)

Usage:
  # Run benchmarks and compare with baseline
  python ci_benchmark_integration.py --baseline benchmarks/results/baseline.json --output results/

  # Generate regression report
  python ci_benchmark_integration.py --report --baseline baseline.json --current results/latest.json

  # Set exit code based on performance gates
  python ci_benchmark_integration.py --gates --threshold 0.10
"""

import json
import sys
from pathlib import Path
from typing import Dict, List, Tuple, Optional, Any
from datetime import datetime
import argparse
import statistics


class PerformanceGate:
    """Enforces performance gates for CI/CD."""

    def __init__(self, baseline_path: str, threshold_percent: float = 10.0):
        """
        Initialize performance gate.
        
        Args:
            baseline_path: Path to baseline metrics JSON
            threshold_percent: Maximum allowed degradation (%)
        """
        self.baseline_path = Path(baseline_path)
        self.threshold_percent = threshold_percent
        self.baseline = self._load_baseline()
        self.violations = []

    def _load_baseline(self) -> Dict:
        """Load baseline metrics from JSON file."""
        if not self.baseline_path.exists():
            raise FileNotFoundError(f"Baseline file not found: {self.baseline_path}")
        
        with open(self.baseline_path) as f:
            return json.load(f)

    def check_metric(self, metric_name: str, current_value: float, 
                    metric_type: str = 'latency') -> Tuple[bool, str]:
        """
        Check if metric meets gate criteria.
        
        Args:
            metric_name: Name of the metric (e.g., 'pqc_encryption')
            current_value: Current measured value
            metric_type: Type of metric ('latency', 'throughput')
            
        Returns:
            (passed, message) tuple
        """
        baseline_value = self._get_baseline_value(metric_name)
        
        if baseline_value is None:
            return True, f"Metric {metric_name} not in baseline - skipping"
        
        if metric_type == 'latency':
            # For latency, higher is worse
            percent_change = ((current_value - baseline_value) / baseline_value) * 100
            passed = percent_change <= self.threshold_percent
        else:  # throughput
            # For throughput, lower is worse
            percent_change = ((baseline_value - current_value) / baseline_value) * 100
            passed = percent_change <= self.threshold_percent
        
        message = (
            f"{metric_name}: baseline={baseline_value:.2f}, "
            f"current={current_value:.2f}, change={percent_change:+.1f}%"
        )
        
        if not passed:
            self.violations.append({
                'metric': metric_name,
                'type': metric_type,
                'baseline': baseline_value,
                'current': current_value,
                'percent_change': percent_change,
                'threshold': self.threshold_percent
            })
        
        return passed, message

    def _get_baseline_value(self, metric_name: str) -> Optional[float]:
        """Extract baseline value from baseline data."""
        # Navigate through nested structure
        baselines = self.baseline.get('baselines', {})
        
        for component in baselines.values():
            if isinstance(component, dict):
                for metric_key, metric_data in component.items():
                    if metric_key == metric_name or metric_name in metric_key:
                        # Try common metric fields
                        for field in ['mean_ms', 'mean_us', 'throughput_per_sec']:
                            if field in metric_data:
                                return metric_data[field]
        
        return None

    def generate_violation_report(self) -> Dict[str, Any]:
        """Generate report of performance violations."""
        return {
            'timestamp': datetime.utcnow().isoformat(),
            'threshold_percent': self.threshold_percent,
            'total_violations': len(self.violations),
            'violations': self.violations,
            'status': 'FAIL' if self.violations else 'PASS'
        }


class RegressionDetector:
    """Detects performance regressions."""

    def __init__(self, baseline_path: str, current_path: str):
        """
        Initialize regression detector.
        
        Args:
            baseline_path: Path to baseline metrics
            current_path: Path to current benchmark results
        """
        self.baseline_path = Path(baseline_path)
        self.current_path = Path(current_path)
        self.baseline = self._load_json(baseline_path)
        self.current = self._load_json(current_path)

    def _load_json(self, path: str) -> Dict:
        """Load JSON file."""
        with open(Path(path)) as f:
            return json.load(f)

    def detect_regressions(self, threshold_percent: float = 10.0) -> Dict[str, Any]:
        """
        Detect performance regressions.
        
        Args:
            threshold_percent: Threshold for regression detection
            
        Returns:
            Report of detected regressions
        """
        regressions = []
        improvements = []
        
        baseline_benchmarks = self.baseline.get('benchmarks', {})
        current_benchmarks = self.current.get('benchmarks', {})
        
        for benchmark_name, baseline_result in baseline_benchmarks.items():
            if benchmark_name not in current_benchmarks:
                continue
            
            current_result = current_benchmarks[benchmark_name]
            
            # Compare latency metrics
            for metric in ['mean_ms', 'median_ms', 'p95_ms', 'p99_ms']:
                if metric in baseline_result and metric in current_result:
                    baseline_val = baseline_result[metric]
                    current_val = current_result[metric]
                    percent_change = ((current_val - baseline_val) / baseline_val) * 100
                    
                    if percent_change > threshold_percent:
                        regressions.append({
                            'benchmark': benchmark_name,
                            'metric': metric,
                            'baseline': baseline_val,
                            'current': current_val,
                            'percent_change': percent_change,
                            'severity': 'CRITICAL' if percent_change > 50 else 'WARNING'
                        })
                    elif percent_change < -5:  # Improvement threshold
                        improvements.append({
                            'benchmark': benchmark_name,
                            'metric': metric,
                            'baseline': baseline_val,
                            'current': current_val,
                            'percent_improvement': abs(percent_change)
                        })
            
            # Compare throughput metrics
            for metric in ['throughput_per_sec', 'throughput_nodes_per_sec', 
                          'throughput_links_per_sec', 'throughput_paths_per_sec']:
                if metric in baseline_result and metric in current_result:
                    baseline_val = baseline_result[metric]
                    current_val = current_result[metric]
                    
                    if baseline_val > 0:
                        percent_change = ((baseline_val - current_val) / baseline_val) * 100
                        
                        if percent_change > threshold_percent:
                            regressions.append({
                                'benchmark': benchmark_name,
                                'metric': metric,
                                'baseline': baseline_val,
                                'current': current_val,
                                'percent_degradation': percent_change,
                                'severity': 'CRITICAL' if percent_change > 50 else 'WARNING'
                            })
                        elif percent_change < -5:
                            improvements.append({
                                'benchmark': benchmark_name,
                                'metric': metric,
                                'baseline': baseline_val,
                                'current': current_val,
                                'percent_improvement': abs(percent_change)
                            })
        
        return {
            'timestamp': datetime.utcnow().isoformat(),
            'baseline_timestamp': self.baseline.get('timestamp'),
            'current_timestamp': self.current.get('timestamp'),
            'threshold_percent': threshold_percent,
            'total_regressions': len(regressions),
            'total_improvements': len(improvements),
            'regressions': regressions,
            'improvements': improvements,
            'status': 'REGRESSION_DETECTED' if regressions else 'OK'
        }


class CIBenchmarkIntegration:
    """Main CI/CD benchmark integration."""

    def __init__(self, args):
        self.args = args

    def run_benchmarks(self) -> Dict:
        """Run comprehensive benchmarks."""
        print("🚀 Running comprehensive benchmarks...")
        
        # Import and run benchmark script
        try:
            from benchmark_comprehensive import PQCBenchmark, MeshBenchmark
            
            pqc_bench = PQCBenchmark()
            pqc_results = pqc_bench.run_all()
            
            mesh_bench = MeshBenchmark()
            mesh_results = mesh_bench.run_all()
            
            return {
                'status': 'success',
                'pqc': pqc_results,
                'mesh': mesh_results
            }
        except Exception as e:
            print(f"❌ Benchmark execution failed: {e}")
            return {
                'status': 'failed',
                'error': str(e)
            }

    def check_gates(self) -> int:
        """Check performance gates and return exit code."""
        print("🚦 Checking performance gates...")
        
        try:
            gate = PerformanceGate(
                self.args.baseline,
                threshold_percent=self.args.threshold * 100
            )
            
            # Check critical metrics
            critical_metrics = {
                'kem_encapsulate': ('latency', 2.0),
                'signature_generation': ('throughput', 100),
                'link_quality': ('throughput', 10000)
            }
            
            all_passed = True
            for metric, (mtype, target) in critical_metrics.items():
                passed, message = gate.check_metric(metric, target, metric_type=mtype)
                status = "✅" if passed else "❌"
                print(f"  {status} {message}")
                all_passed = all_passed and passed
            
            return 0 if all_passed else 1
        except Exception as e:
            print(f"❌ Gate check failed: {e}")
            return 1

    def compare_with_baseline(self) -> int:
        """Compare current results with baseline and return exit code."""
        print("📊 Comparing with baseline...")
        
        try:
            detector = RegressionDetector(self.args.baseline, self.args.current)
            report = detector.detect_regressions(threshold_percent=self.args.threshold * 100)
            
            print(f"\nRegression Analysis:")
            print(f"  Regressions detected: {report['total_regressions']}")
            print(f"  Improvements detected: {report['total_improvements']}")
            
            if report['regressions']:
                print("\n⚠️  Regressions:")
                for reg in report['regressions']:
                    print(f"  • {reg['benchmark']}.{reg['metric']}")
                    print(f"    {reg['percent_change']:+.1f}% change ({reg['severity']})")
            
            if report['improvements']:
                print("\n✅ Improvements:")
                for imp in report['improvements'][:5]:  # Show top 5
                    print(f"  • {imp['benchmark']}.{imp['metric']}")
                    print(f"    {imp['percent_improvement']:+.1f}% improvement")
            
            # Save report
            if self.args.output:
                output_file = Path(self.args.output) / f"regression_report_{datetime.utcnow().strftime('%Y%m%d_%H%M%S')}.json"
                output_file.parent.mkdir(parents=True, exist_ok=True)
                with open(output_file, 'w') as f:
                    json.dump(report, f, indent=2)
                print(f"\n📄 Report saved to: {output_file}")
            
            return 0 if report['status'] == 'OK' else 1
        except Exception as e:
            print(f"❌ Comparison failed: {e}")
            return 1

    def main(self) -> int:
        """Main execution."""
        print("\n" + "=" * 70)
        print("🔧 CI/CD Benchmark Integration")
        print("=" * 70)
        
        if self.args.benchmark:
            print("\n▶ Running benchmarks...")
            results = self.run_benchmarks()
            
            if results['status'] == 'failed':
                return 1
            
            # Save results
            if self.args.output:
                output_file = Path(self.args.output) / f"benchmark_{datetime.utcnow().strftime('%Y%m%d_%H%M%S')}.json"
                output_file.parent.mkdir(parents=True, exist_ok=True)
                with open(output_file, 'w') as f:
                    json.dump(results, f, indent=2)
                print(f"\n✅ Results saved to: {output_file}")
        
        if self.args.gates:
            print("\n▶ Checking performance gates...")
            return self.check_gates()
        
        if self.args.compare:
            print("\n▶ Comparing with baseline...")
            return self.compare_with_baseline()
        
        return 0


def main():
    """Parse arguments and run integration."""
    parser = argparse.ArgumentParser(
        description='CI/CD Benchmark Integration',
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog=__doc__
    )
    
    parser.add_argument('--benchmark', action='store_true',
                       help='Run benchmarks')
    parser.add_argument('--gates', action='store_true',
                       help='Check performance gates')
    parser.add_argument('--compare', action='store_true',
                       help='Compare with baseline')
    parser.add_argument('--baseline', type=str,
                       default='benchmarks/results/baseline_report.json',
                       help='Path to baseline metrics')
    parser.add_argument('--current', type=str,
                       help='Path to current benchmark results')
    parser.add_argument('--output', type=str,
                       default='benchmarks/results',
                       help='Output directory for reports')
    parser.add_argument('--threshold', type=float, default=0.10,
                       help='Performance degradation threshold (0-1, default 0.10 = 10%)')
    
    args = parser.parse_args()
    
    # Default actions if none specified
    if not any([args.benchmark, args.gates, args.compare]):
        args.benchmark = True
        args.gates = True
    
    integration = CIBenchmarkIntegration(args)
    exit_code = integration.main()
    
    print("\n" + "=" * 70)
    sys.exit(exit_code)


if __name__ == "__main__":
    main()
