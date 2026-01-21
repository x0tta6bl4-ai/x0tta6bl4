#!/usr/bin/env python3
"""
Automated Benchmark Runner Script

Runs comprehensive benchmarks and generates reports.
Can be used in CI/CD pipelines.

Usage:
    python scripts/run_benchmarks.py [--quick] [--full] [--output-dir DIR]
"""

import asyncio
import sys
import logging
from pathlib import Path

# Add src to path
sys.path.insert(0, str(Path(__file__).parent.parent / "src"))
sys.path.insert(0, str(Path(__file__).parent.parent / "tests" / "performance"))

from comprehensive_benchmark_suite import ComprehensiveBenchmarkRunner

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s - %(levelname)s - %(message)s"
)
logger = logging.getLogger(__name__)


async def main():
    """Main benchmark runner"""
    import argparse
    
    parser = argparse.ArgumentParser(description="Run x0tta6bl4 Benchmarks")
    parser.add_argument(
        "--quick",
        action="store_true",
        help="Quick benchmark run (fewer iterations)"
    )
    parser.add_argument(
        "--full",
        action="store_true",
        help="Full benchmark run (more iterations)"
    )
    parser.add_argument(
        "--output-dir",
        default="benchmarks/results",
        help="Output directory for results"
    )
    parser.add_argument(
        "--format",
        choices=["json", "html", "markdown"],
        default="json",
        help="Output format"
    )
    
    args = parser.parse_args()
    
    # Set iterations based on mode
    if args.quick:
        mttd_iterations = 5
        mttr_iterations = 5
        pqc_iterations = 100
        accuracy_samples = 100
        auto_resolution_incidents = 20
        root_cause_cases = 20
    elif args.full:
        mttd_iterations = 50
        mttr_iterations = 50
        pqc_iterations = 10000
        accuracy_samples = 10000
        auto_resolution_incidents = 500
        root_cause_cases = 500
    else:
        # Default
        mttd_iterations = 10
        mttr_iterations = 10
        pqc_iterations = 1000
        accuracy_samples = 1000
        auto_resolution_incidents = 100
        root_cause_cases = 100
    
    logger.info("🚀 Starting benchmark run...")
    logger.info(f"Mode: {'quick' if args.quick else 'full' if args.full else 'default'}")
    
    runner = ComprehensiveBenchmarkRunner(output_dir=Path(args.output_dir))
    
    try:
        suite = await runner.run_all_benchmarks(
            mttd_iterations=mttd_iterations,
            mttr_iterations=mttr_iterations,
            pqc_iterations=pqc_iterations,
            accuracy_samples=accuracy_samples,
            auto_resolution_incidents=auto_resolution_incidents,
            root_cause_cases=root_cause_cases
        )
        
        # Save results
        result_file = runner.save_results(suite, format=args.format)
        
        # Check if all passed
        all_passed = all(
            metric.get("passed", False)
            for metric in suite.summary.values()
            if isinstance(metric, dict)
        )
        
        if all_passed:
            logger.info("✅ All benchmarks passed!")
            sys.exit(0)
        else:
            logger.warning("⚠️ Some benchmarks failed")
            sys.exit(1)
    
    except Exception as e:
        logger.error(f"❌ Benchmark run failed: {e}")
        sys.exit(1)


if __name__ == "__main__":
    asyncio.run(main())

