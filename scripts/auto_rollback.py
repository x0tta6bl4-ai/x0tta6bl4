#!/usr/bin/env python3
"""
Rollback recommendation monitor

Monitors local health/metrics observations and recommends rollback when
thresholds are exceeded. The current implementation records recommendations
only; it does not include a live rollback command adapter.
"""

import asyncio
import hashlib
import os
import time
from datetime import datetime
from pathlib import Path
from typing import Any, Dict

import httpx

project_root = Path(__file__).parent.parent
AUTO_ROLLBACK_CLAIM_BOUNDARY = (
    "This script records local health/metrics observations and rollback "
    "recommendations. Local error-rate, latency, or health observations do not "
    "prove live customer impact, production SLO breach, traffic shifting, "
    "external DPI bypass, settlement finality, or production readiness. Live "
    "rollback requires separate authorization and rollout evidence."
)


def _env_flag(name: str) -> bool:
    return os.getenv(name, "").lower() == "yes"


def _bounded_output_metadata(text: str) -> Dict[str, Any]:
    encoded = text.encode("utf-8", errors="replace")
    return {
        "bytes": len(encoded),
        "sha256": hashlib.sha256(encoded).hexdigest(),
        "raw_output_retained": False,
    }


def _elapsed_ms(started_at: float) -> int:
    return int((time.perf_counter() - started_at) * 1000)


def _claim_boundary_fields() -> Dict[str, Any]:
    return {
        "rollback_recommendation_only": True,
        "live_rollback_executed": False,
        "production_readiness_claim_allowed": False,
        "production_slo_claim_allowed": False,
        "live_customer_traffic_proven": False,
        "traffic_shift_claim_allowed": False,
        "external_dpi_bypass_confirmed": False,
        "settlement_finality_confirmed": False,
        "claim_boundary": AUTO_ROLLBACK_CLAIM_BOUNDARY,
    }


class AutoRollback:
    """Rollback recommendation manager with explicit live-action boundaries."""

    def __init__(
        self,
        base_url: str = "http://localhost:8080",
        allow_live_rollback: bool | None = None,
    ):
        self.base_url = base_url
        self.allow_live_rollback = (
            _env_flag("X0TTA6BL4_ALLOW_LIVE_ROLLBACK")
            if allow_live_rollback is None
            else allow_live_rollback
        )
        self.rollback_triggered = False
        self.metrics_history = []

    async def check_metrics(self) -> Dict[str, Any]:
        """Check current metrics."""
        started_at = time.perf_counter()
        try:
            async with httpx.AsyncClient() as client:
                # Check health
                health_response = await client.get(f"{self.base_url}/health", timeout=5)
                healthy = health_response.status_code == 200

                # Check metrics
                metrics_response = await client.get(
                    f"{self.base_url}/metrics", timeout=5
                )
                metrics_text = (
                    metrics_response.text if metrics_response.status_code == 200 else ""
                )

                # Parse metrics (simplified)
                error_rate = 0.0
                latency_p95 = 0.0

                for line in metrics_text.split("\n"):
                    if "production_error_rate" in line and not line.startswith("#"):
                        try:
                            error_rate = float(line.split()[-1])
                        except:
                            pass
                    # Would parse latency similarly

                return {
                    "healthy": healthy,
                    "health_status_code": health_response.status_code,
                    "metrics_status_code": metrics_response.status_code,
                    "error_rate": error_rate,
                    "latency_p95": latency_p95,
                    "duration_ms": _elapsed_ms(started_at),
                    "health_output_metadata": _bounded_output_metadata(
                        health_response.text
                    ),
                    "metrics_output_metadata": _bounded_output_metadata(metrics_text),
                    "raw_output_retained": False,
                    "timestamp": datetime.now().isoformat(),
                    **_claim_boundary_fields(),
                }
        except Exception as e:
            return {
                "healthy": False,
                "error_type": type(e).__name__,
                "duration_ms": _elapsed_ms(started_at),
                "raw_error_redacted": True,
                "raw_output_retained": False,
                "timestamp": datetime.now().isoformat(),
                **_claim_boundary_fields(),
            }

    def should_rollback(self, metrics: Dict[str, Any]) -> tuple[bool, str]:
        """
        Determine if rollback should be triggered.

        Returns:
            (should_rollback, reason)
        """
        # Check health
        if not metrics.get("healthy", False):
            return True, "Service unhealthy"

        # Check error rate
        error_rate = metrics.get("error_rate", 0)
        if error_rate > 0.10:  # 10%
            return True, f"Error rate too high: {error_rate*100:.2f}%"

        # Check latency
        latency_p95 = metrics.get("latency_p95", 0)
        if latency_p95 > 500:  # 500ms
            return True, f"Latency too high: {latency_p95:.2f}ms"

        return False, ""

    async def execute_rollback(self):
        """Record rollback recommendation; never claim placeholder work as live action."""
        print("\n" + "=" * 60)
        print("🔄 ROLLBACK RECOMMENDATION")
        print("=" * 60 + "\n")
        print(f"Claim boundary: {AUTO_ROLLBACK_CLAIM_BOUNDARY}")
        print()

        if not self.allow_live_rollback:
            print("LIVE ROLLBACK: BLOCKED")
            print(
                "Set X0TTA6BL4_ALLOW_LIVE_ROLLBACK=yes only after reviewing "
                "current rollout evidence."
            )
            print("No live rollback command was executed.")
            return {
                "rollback_recommended": True,
                "rollback_executed": False,
                "live_rollback_authorized": False,
                **_claim_boundary_fields(),
            }

        print("LIVE ROLLBACK: AUTHORIZED")
        print("ROLLBACK COMMAND ADAPTER: NOT CONFIGURED")
        print("No live rollback command was executed by this script.")
        return {
            "rollback_recommended": True,
            "rollback_executed": False,
            "live_rollback_authorized": True,
            "rollback_command_adapter_configured": False,
            **_claim_boundary_fields(),
        }

    async def monitor(self, check_interval: int = 10):
        """
        Monitor local observations and recommend rollback if needed.

        Args:
            check_interval: Seconds between checks
        """
        print("\n" + "=" * 60)
        print("🛡️ ROLLBACK RECOMMENDATION MONITOR ACTIVE")
        print("=" * 60 + "\n")
        print(f"Monitoring {self.base_url}")
        print(f"Check interval: {check_interval} seconds")
        print(f"Claim boundary: {AUTO_ROLLBACK_CLAIM_BOUNDARY}")
        print("Rollback triggers:")
        print("  • Error rate > 10%")
        print("  • Latency P95 > 500ms")
        print("  • Service unhealthy")
        print()

        consecutive_failures = 0
        failure_threshold = 3  # 3 consecutive failures trigger rollback

        while not self.rollback_triggered:
            metrics = await self.check_metrics()
            self.metrics_history.append(metrics)

            should_rollback, reason = self.should_rollback(metrics)

            if should_rollback:
                consecutive_failures += 1
                print(f"⚠️  Rollback condition detected: {reason}")
                print(
                    f"   Consecutive failures: {consecutive_failures}/{failure_threshold}"
                )

                if consecutive_failures >= failure_threshold:
                    print(f"\n🚨 ROLLBACK RECOMMENDED: {reason}")
                    self.rollback_triggered = True
                    await self.execute_rollback()
                    break
            else:
                consecutive_failures = 0
                print(
                    f"✅ Metrics OK | Error Rate: {metrics.get('error_rate', 0)*100:.2f}% | Healthy: {metrics.get('healthy', False)}"
                )

            await asyncio.sleep(check_interval)

        if not self.rollback_triggered:
            print("\n✅ Monitoring complete - no rollback recommendation")


async def main():
    """Main function."""
    import argparse

    parser = argparse.ArgumentParser(description="Automatic rollback monitor")
    parser.add_argument(
        "--url", type=str, default="http://localhost:8080", help="Base URL"
    )
    parser.add_argument(
        "--interval", type=int, default=10, help="Check interval in seconds"
    )
    parser.add_argument(
        "--allow-live-rollback",
        action="store_true",
        help=(
            "Mark live rollback as locally authorized; this script still has no "
            "live rollback command adapter"
        ),
    )

    args = parser.parse_args()
    if args.interval <= 0:
        parser.error("--interval must be > 0")

    rollback = AutoRollback(
        base_url=args.url,
        allow_live_rollback=args.allow_live_rollback
        or _env_flag("X0TTA6BL4_ALLOW_LIVE_ROLLBACK"),
    )
    await rollback.monitor(check_interval=args.interval)


if __name__ == "__main__":
    asyncio.run(main())
