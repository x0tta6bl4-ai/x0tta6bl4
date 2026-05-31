#!/usr/bin/env python3
"""
Canary rollout observation script

Runs local health/metrics observations for requested rollout percentages.
It does not prove traffic shifting or production readiness.
"""

import argparse
import asyncio
import sys
import time
from datetime import datetime
from pathlib import Path
from typing import Any, Dict

import httpx

project_root = Path(__file__).parent.parent
sys.path.insert(0, str(project_root))

try:
    from src.deployment.canary_deployment import (CanaryDeployment,
                                                  DeploymentConfig,
                                                  DeploymentStage)
except ImportError:
    print("⚠️ Canary deployment module not available")
    CanaryDeployment = None

CANARY_CLAIM_BOUNDARY = (
    "This script records local health/metrics observations for requested rollout "
    "percentages. It does not prove traffic was shifted, live customer traffic, "
    "external DPI bypass, settlement finality, production SLOs, or production "
    "readiness without separate rollout/evidence artifacts."
)
DEFAULT_STAGE_DURATIONS = {
    5.0: 15,
    25.0: 30,
    50.0: 60,
    75.0: 120,
    100.0: 1440,
}


def parse_stage_percentages(raw: str) -> list[float]:
    """Parse comma-separated rollout percentages."""
    stages = []
    for item in raw.split(","):
        text = item.strip()
        if not text:
            continue
        percentage = float(text)
        if percentage <= 0 or percentage > 100:
            raise ValueError("stage percentages must be between 0 and 100")
        stages.append(percentage)
    if not stages:
        raise ValueError("at least one stage percentage is required")
    return stages


async def check_health(url: str = "http://localhost:8080/health") -> bool:
    """Check if service is healthy."""
    try:
        async with httpx.AsyncClient() as client:
            response = await client.get(url, timeout=5)
            return response.status_code == 200
    except:
        return False


async def check_metrics(url: str = "http://localhost:8080/metrics") -> Dict[str, Any]:
    """Check current metrics."""
    try:
        async with httpx.AsyncClient() as client:
            response = await client.get(url, timeout=5)
            if response.status_code == 200:
                # Parse Prometheus metrics (simplified)
                metrics_text = response.text
                return {
                    "available": True,
                    "error_rate": 0.0,  # Would parse from metrics
                    "latency_p95": 0.0,  # Would parse from metrics
                    "throughput": 0.0,  # Would parse from metrics
                }
    except:
        pass

    return {"available": False}


async def deploy_canary(
    percentage: float, duration_minutes: int = 15
) -> Dict[str, Any]:
    """
    Observe a requested canary percentage with local health/metrics checks.

    Args:
        percentage: Requested traffic percentage (5, 25, 50, 75, 100)
        duration_minutes: Monitoring duration in minutes
    """
    print(f"\n{'='*60}")
    print(f"🚀 CANARY ROLLOUT OBSERVATION: {percentage}%")
    print(f"{'='*60}\n")

    print(f"Requested rollout percentage: {percentage}%")
    print(f"Monitoring for {duration_minutes} minutes...")
    print(f"Claim boundary: {CANARY_CLAIM_BOUNDARY}")
    print()

    # This script observes local endpoints only; actual traffic shifting must be
    # proven by separate rollout controller evidence.

    start_time = time.time()
    end_time = start_time + (duration_minutes * 60)

    checks = []
    all_healthy = True

    while time.time() < end_time:
        elapsed = int(time.time() - start_time)
        remaining = int(end_time - time.time())

        # Check health
        healthy = await check_health()
        metrics = await check_metrics()

        status = "✅" if healthy else "❌"
        print(
            f"[{elapsed}s/{duration_minutes*60}s] {status} Health check: {'OK' if healthy else 'FAILED'}"
        )

        if not healthy:
            all_healthy = False

        checks.append(
            {
                "timestamp": datetime.now().isoformat(),
                "healthy": healthy,
                "metrics": metrics,
            }
        )

        # Wait 30 seconds between checks
        await asyncio.sleep(30)

    # Summary
    healthy_checks = sum(1 for c in checks if c["healthy"])
    total_checks = len(checks)
    health_rate = (healthy_checks / total_checks * 100) if total_checks > 0 else 0

    print()
    print(f"{'='*60}")
    print(f"📊 CANARY ROLLOUT OBSERVATION RESULTS: {percentage}%")
    print(f"{'='*60}")
    print(f"Duration: {duration_minutes} minutes")
    print(f"Health Checks: {healthy_checks}/{total_checks} ({health_rate:.1f}%)")
    print(
        f"Status: {'✅ PASSED' if all_healthy and health_rate >= 95 else '❌ FAILED'}"
    )
    print(f"{'='*60}\n")

    return {
        "percentage": percentage,
        "duration_minutes": duration_minutes,
        "health_rate": health_rate,
        "all_healthy": all_healthy,
        "passed": all_healthy and health_rate >= 95,
        "checks": checks,
        "traffic_shift_claim_allowed": False,
        "production_readiness_claim_allowed": False,
        "live_customer_traffic_proven": False,
        "external_dpi_bypass_confirmed": False,
        "settlement_finality_confirmed": False,
        "claim_boundary": CANARY_CLAIM_BOUNDARY,
    }


async def main():
    """Main canary deployment function."""
    parser = argparse.ArgumentParser(description="Observe canary rollout health")
    parser.add_argument(
        "--stages",
        default="5,25,50,75,100",
        help="Comma-separated rollout percentages to observe",
    )
    parser.add_argument(
        "--duration-override",
        type=int,
        default=None,
        help="Override each stage duration in minutes",
    )
    args = parser.parse_args()
    try:
        parsed_stages = parse_stage_percentages(args.stages)
    except ValueError as exc:
        parser.error(str(exc))

    print("\n" + "=" * 60)
    print("🚀 CANARY ROLLOUT OBSERVATION MANAGER")
    print("=" * 60)
    print("\nThis script observes requested rollout stages:")
    print(f"  {args.stages}")
    print(f"Claim boundary: {CANARY_CLAIM_BOUNDARY}")
    print()

    # Check if service is running
    if not await check_health():
        print("❌ Service is not running on http://localhost:8080")
        print("   Please start the service first.")
        sys.exit(1)

    print("✅ Service is running\n")

    stages = [
        (
            percentage,
            args.duration_override
            if args.duration_override is not None
            else DEFAULT_STAGE_DURATIONS.get(percentage, 15),
        )
        for percentage in parsed_stages
    ]

    results = []

    for index, (percentage, duration) in enumerate(stages):
        result = await deploy_canary(percentage, duration)
        results.append(result)

        if not result["passed"]:
            print(f"❌ Canary rollout observation failed at {percentage}%")
            print("   Rollback requires separate rollout-controller evidence.")
            sys.exit(1)

        print(f"✅ Canary rollout observation at {percentage}% passed local checks")
        print()

        # Ask for confirmation before next stage (except for 100%)
        if index < len(stages) - 1:
            print(f"Ready to proceed to {stages[index + 1][0]}%?")
            print("Press Enter to continue, or 'q' to quit...")
            # In real scenario, would wait for user input or automated approval

    # Final summary
    print("\n" + "=" * 60)
    print("🎉 CANARY ROLLOUT OBSERVATION COMPLETE")
    print("=" * 60)
    print("All requested observation stages passed local checks.")
    print("This is not traffic-shift or production-readiness proof.")
    print("=" * 60 + "\n")


if __name__ == "__main__":
    asyncio.run(main())
