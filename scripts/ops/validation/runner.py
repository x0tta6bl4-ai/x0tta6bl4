"""Validation Runner for x0tta6bl4 Validation Framework.

Main entry point for running validation suites.
Orchestrates failure injection, metrics collection, and evaluation.

Usage:
    python -m scripts.ops.validation.runner --samples 30
    python -m scripts.ops.validation.runner --suite V1 --failure F1
    python -m scripts.ops.validation.runner --dry-run
"""

import argparse
import json
import subprocess
import time
from datetime import datetime
from pathlib import Path

from .failure_taxonomy import get_failure, list_failures
from .failure_injector import FailureInjector
from .metrics_collector import MetricsCollector
from .evaluation_gate import EvaluationGate, Verdict


def get_git_commit() -> str:
    """Get current git commit SHA."""
    try:
        result = subprocess.run(
            ["git", "rev-parse", "--short", "HEAD"],
            capture_output=True,
            text=True,
            timeout=5,
        )
        return result.stdout.strip()
    except Exception:
        return "unknown"


def get_system_info() -> dict:
    """Collect system information for metadata."""
    info = {}

    try:
        result = subprocess.run(["uname", "-r"], capture_output=True, text=True, timeout=5)
        info["kernel"] = result.stdout.strip()
    except Exception:
        info["kernel"] = "unknown"

    try:
        result = subprocess.run(["nproc"], capture_output=True, text=True, timeout=5)
        info["cpu_cores"] = int(result.stdout.strip())
    except Exception:
        info["cpu_cores"] = 0

    try:
        with open("/proc/meminfo") as f:
            for line in f:
                if "MemTotal" in line:
                    info["ram_kb"] = int(line.split()[1])
                    break
    except Exception:
        info["ram_kb"] = 0

    try:
        result = subprocess.run(
            ["cat", "/proc/sys/net/ipv4/tcp_congestion_control"],
            capture_output=True,
            text=True,
            timeout=5,
        )
        info["tcp_cc"] = result.stdout.strip()
    except Exception:
        info["tcp_cc"] = "unknown"

    return info


def run_suite_v1(
    injector: FailureInjector,
    collector: MetricsCollector,
    target_ip: str,
    samples: int,
    dry_run: bool = False,
) -> None:
    """Suite V1: Node Failure Recovery (F1, F3)."""
    print(f"\n{'='*60}")
    print(f"Suite V1: Node Failure Recovery (F1, F3)")
    print(f"Target: {target_ip}, Samples: {samples}")
    print(f"{'='*60}")

    for i in range(samples):
        print(f"\n--- Sample {i+1}/{samples} ---")

        # Measure baseline
        print("Measuring baseline latency...")
        collector.measure_latency(
            target=f"baseline_{i}",
            url=f"https://httpbin.org/get",
            proxy=None,
        )

        # Inject failure
        print("Injecting F3 (Network Partition)...")
        result = injector.inject(
            failure_id="F3",
            target=target_ip,
            duration_sec=5.0,
        )

        if result.success:
            # Measure recovery
            print("Measuring recovery time...")
            recovery = collector.measure_recovery_time(
                failure_id="F3",
                target=f"https://{target_ip}",
                check_interval_ms=200,
                max_wait_sec=15,
            )
            print(f"  Recovery: {recovery.recovery_time_ms:.0f}ms, survived: {recovery.session_survived}")

            # Cleanup
            injector.cleanup("F3", target_ip)

        time.sleep(1)


def run_suite_v2(
    collector: MetricsCollector,
    samples: int,
) -> None:
    """Suite V2: Synthetic Packet Loss Resilience (F4)."""
    print(f"\n{'='*60}")
    print(f"Suite V2: Synthetic Loss Resilience (F4)")
    print(f"Samples: {samples}")
    print(f"{'='*60}")

    targets = [
        ("direct", None),
        ("vpn_socks", "socks5://127.0.0.1:10818"),
    ]

    for target_name, proxy in targets:
        print(f"\n--- Target: {target_name} ---")
        for i in range(samples):
            collector.measure_latency(
                target=target_name,
                url="https://httpbin.org/get",
                proxy=proxy,
            )
            time.sleep(0.5)


def run_latency_baseline(
    collector: MetricsCollector,
    samples: int,
) -> None:
    """Measure baseline latency without failures."""
    print(f"\n{'='*60}")
    print(f"Latency Baseline Measurement")
    print(f"Samples: {samples}")
    print(f"{'='*60}")

    targets = [
        ("direct_google", "https://www.google.com", None),
        ("direct_telegram", "https://api.telegram.org", None),
        ("vpn_telegram", "https://api.telegram.org", "socks5://127.0.0.1:10818"),
    ]

    for target_name, url, proxy in targets:
        print(f"\n--- {target_name} ---")
        for i in range(samples):
            collector.measure_latency(
                target=target_name,
                url=url,
                proxy=proxy,
            )
            if (i + 1) % 10 == 0:
                stats = collector.compute_latency_stats(target_name)
                if stats:
                    print(f"  [{i+1}/{samples}] median={stats.median_ms:.0f}ms, stdev={stats.stdev_ms:.0f}ms")
            time.sleep(0.3)


def main():
    parser = argparse.ArgumentParser(description="x0tta6bl4 Validation Framework Runner")
    parser.add_argument("--samples", type=int, default=30, help="Number of samples per test (minimum 30)")
    parser.add_argument("--suite", type=str, help="Specific suite to run (V1-V7)")
    parser.add_argument("--failure", type=str, help="Specific failure to inject (F1-F10)")
    parser.add_argument("--target", type=str, default="89.125.1.107", help="Target IP for failure injection")
    parser.add_argument("--dry-run", action="store_true", help="Dry run mode (no actual injection)")
    parser.add_argument("--output-dir", type=str, default="results", help="Output directory for results")
    args = parser.parse_args()

    if args.samples < 30:
        print(f"WARNING: N={args.samples} is below minimum (30). p95/p99 will not be computed.")

    # Setup output directory
    timestamp = datetime.now().strftime("%Y-%m-%d_%H-%M-%S")
    commit = get_git_commit()
    output_dir = Path(args.output_dir) / f"{timestamp}_sha-{commit}"
    output_dir.mkdir(parents=True, exist_ok=True)

    # Collect system metadata
    system_info = get_system_info()
    metadata = {
        "git_commit": commit,
        "timestamp": datetime.now().isoformat(),
        "samples": args.samples,
        "target": args.target,
        "dry_run": args.dry_run,
        "system": system_info,
    }

    with open(output_dir / "metadata.json", "w") as f:
        json.dump(metadata, f, indent=2)

    print(f"Validation Framework v1.0")
    print(f"Output: {output_dir}")
    print(f"Commit: {commit}")
    print(f"System: {system_info}")

    # Initialize components
    injector = FailureInjector(dry_run=args.dry_run)
    collector = MetricsCollector()
    gate = EvaluationGate()

    # Run suites
    if args.suite:
        suite_name = args.suite.upper()
        if suite_name == "V1":
            run_suite_v1(injector, collector, args.target, args.samples, args.dry_run)
        elif suite_name == "V2":
            run_suite_v2(collector, args.samples)
        else:
            print(f"Suite {suite_name} not yet implemented")
            return
    elif args.failure:
        failure = get_failure(args.failure.upper())
        print(f"Injecting failure: {failure.name} ({failure.id})")
        result = injector.inject(failure.id, args.target)
        print(f"Result: {result}")
        if not args.dry_run:
            input("Press Enter to cleanup...")
            injector.cleanup(failure.id, args.target)
    else:
        # Run full baseline
        run_latency_baseline(collector, args.samples)

    # Export results
    collector.export_json(output_dir / "raw.json")
    collector.export_prometheus(output_dir / "metrics.prom")

    # Evaluate
    recovery_results = collector.recovery_metrics
    if recovery_results:
        gate.evaluate_recovery(recovery_results)
        gate.evaluate_session_survival(recovery_results)

    stats = {}
    for target in set(s.target for s in collector.samples):
        s = collector.compute_latency_stats(target)
        if s:
            stats[target] = s

    if stats:
        gate.evaluate_latency(stats, "direct_google", "vpn_telegram")

    gate.export_json(output_dir / "summary.json")

    # Print summary
    print(f"\n{'='*60}")
    print(f"VALIDATION COMPLETE")
    print(f"{'='*60}")
    print(f"Overall verdict: {gate.get_overall_verdict().value}")
    print(f"Results saved to: {output_dir}")

    for result in gate.results:
        print(f"  [{result.verdict.value}] {result.rule.name}: {result.details}")


if __name__ == "__main__":
    main()
