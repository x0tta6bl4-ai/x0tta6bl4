#!/usr/bin/env python3
"""
Production monitoring observation script

Records local HTTP health/metrics observations during rollout monitoring.
It does not prove production readiness or production SLOs.
"""

import asyncio
import hashlib
import json
import sys
import time
from datetime import datetime
from pathlib import Path
from typing import Any, Dict, List

import httpx

project_root = Path(__file__).parent.parent
sys.path.insert(0, str(project_root))

try:
    from src.monitoring.production_monitoring import get_production_monitor
except (ImportError, ValueError):
    print("⚠️ Production monitoring module not available")
    get_production_monitor = None


PRODUCTION_MONITOR_CLAIM_BOUNDARY = (
    "This script records local HTTP health/metrics observations for a configured "
    "base URL. It does not prove live customer traffic, traffic shifting, "
    "external DPI bypass, settlement finality, production SLOs, or production "
    "readiness without separate rollout/evidence artifacts."
)
PRODUCTION_MONITOR_OBSERVATION_SCOPE = "local_http_monitoring_observation"


def _bounded_output_metadata(text: str) -> Dict[str, Any]:
    """Return bounded metadata for response bodies without retaining raw output."""
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
        "observation_scope": PRODUCTION_MONITOR_OBSERVATION_SCOPE,
        "production_readiness_claim_allowed": False,
        "production_slo_claim_allowed": False,
        "live_customer_traffic_proven": False,
        "traffic_shift_claim_allowed": False,
        "external_dpi_bypass_confirmed": False,
        "settlement_finality_confirmed": False,
        "claim_boundary": PRODUCTION_MONITOR_CLAIM_BOUNDARY,
    }


class ProductionMonitor:
    """Real-time local HTTP monitor with explicit production-claim boundaries."""

    def __init__(self, base_url: str = "http://localhost:8080"):
        self.base_url = base_url
        self.alerts: List[Dict[str, Any]] = []
        self.metrics_history: List[Dict[str, Any]] = []

    async def check_health(self) -> Dict[str, Any]:
        """Check health endpoint."""
        started_at = time.perf_counter()
        try:
            async with httpx.AsyncClient() as client:
                response = await client.get(f"{self.base_url}/health", timeout=5)
                return {
                    "healthy": response.status_code == 200,
                    "status_code": response.status_code,
                    "duration_ms": _elapsed_ms(started_at),
                    "bounded_output_metadata": _bounded_output_metadata(response.text),
                    "raw_output_retained": False,
                    "timestamp": datetime.now().isoformat(),
                    "observation_scope": PRODUCTION_MONITOR_OBSERVATION_SCOPE,
                }
        except Exception as e:
            return {
                "healthy": False,
                "error_type": type(e).__name__,
                "duration_ms": _elapsed_ms(started_at),
                "raw_error_redacted": True,
                "raw_output_retained": False,
                "timestamp": datetime.now().isoformat(),
                "observation_scope": PRODUCTION_MONITOR_OBSERVATION_SCOPE,
            }

    async def check_metrics(self) -> Dict[str, Any]:
        """Check Prometheus metrics."""
        started_at = time.perf_counter()
        try:
            async with httpx.AsyncClient() as client:
                response = await client.get(f"{self.base_url}/metrics", timeout=5)
                if response.status_code == 200:
                    # Parse key metrics (simplified)
                    metrics_text = response.text

                    # Extract error rate (simplified parsing)
                    error_rate = 0.0
                    for line in metrics_text.split("\n"):
                        if "production_error_rate" in line and not line.startswith("#"):
                            try:
                                error_rate = float(line.split()[-1])
                            except:
                                pass

                    return {
                        "available": True,
                        "error_rate": error_rate,
                        "status_code": response.status_code,
                        "duration_ms": _elapsed_ms(started_at),
                        "bounded_output_metadata": _bounded_output_metadata(
                            metrics_text
                        ),
                        "raw_output_retained": False,
                        "timestamp": datetime.now().isoformat(),
                        "observation_scope": PRODUCTION_MONITOR_OBSERVATION_SCOPE,
                    }
                return {
                    "available": False,
                    "status_code": response.status_code,
                    "duration_ms": _elapsed_ms(started_at),
                    "bounded_output_metadata": _bounded_output_metadata(response.text),
                    "raw_output_retained": False,
                    "timestamp": datetime.now().isoformat(),
                    "observation_scope": PRODUCTION_MONITOR_OBSERVATION_SCOPE,
                }
        except Exception as e:
            return {
                "available": False,
                "error_type": type(e).__name__,
                "duration_ms": _elapsed_ms(started_at),
                "raw_error_redacted": True,
                "raw_output_retained": False,
                "timestamp": datetime.now().isoformat(),
                "observation_scope": PRODUCTION_MONITOR_OBSERVATION_SCOPE,
            }

    def check_alerts(self, metrics: Dict[str, Any]) -> List[Dict[str, Any]]:
        """Check for alert conditions."""
        alerts = []

        # Error rate alert
        if metrics.get("error_rate", 0) > 0.05:  # 5%
            alerts.append(
                {
                    "severity": "critical",
                    "message": f"High error rate: {metrics.get('error_rate', 0)*100:.2f}%",
                    "timestamp": datetime.now().isoformat(),
                }
            )
        elif metrics.get("error_rate", 0) > 0.01:  # 1%
            alerts.append(
                {
                    "severity": "warning",
                    "message": f"Elevated error rate: {metrics.get('error_rate', 0)*100:.2f}%",
                    "timestamp": datetime.now().isoformat(),
                }
            )

        return alerts

    async def monitor(self, duration_minutes: int = 60, interval_seconds: int = 10):
        """
        Observe local HTTP health/metrics for a configured base URL.

        Args:
            duration_minutes: How long to monitor
            interval_seconds: Check interval
        """
        print(f"\n{'='*60}")
        print(f"📊 PRODUCTION MONITORING OBSERVATION")
        print(f"{'='*60}\n")
        print(f"Monitoring for {duration_minutes} minutes")
        print(f"Check interval: {interval_seconds} seconds")
        print(f"Claim boundary: {PRODUCTION_MONITOR_CLAIM_BOUNDARY}")
        print()

        start_time = datetime.now()
        end_time = start_time.timestamp() + (duration_minutes * 60)

        check_count = 0

        while datetime.now().timestamp() < end_time:
            check_count += 1
            elapsed = (datetime.now() - start_time).total_seconds()

            # Check health
            health = await self.check_health()
            metrics = await self.check_metrics()

            # Check alerts
            alerts = self.check_alerts(metrics)
            self.alerts.extend(alerts)

            # Display status
            health_status = "✅" if health.get("healthy") else "❌"
            error_rate = metrics.get("error_rate", 0) * 100

            print(
                f"[{int(elapsed)}s] {health_status} Health | Error Rate: {error_rate:.2f}%",
                end="",
            )

            if alerts:
                print(f" | 🚨 {len(alerts)} alerts", end="")
                for alert in alerts:
                    print(
                        f"\n   [{alert['severity'].upper()}] {alert['message']}", end=""
                    )

            print()

            # Store metrics
            self.metrics_history.append(
                {
                    "timestamp": datetime.now().isoformat(),
                    "health": health,
                    "metrics": metrics,
                    "alerts": alerts,
                }
            )

            await asyncio.sleep(interval_seconds)

        # Summary
        print()
        print(f"{'='*60}")
        print(f"📊 MONITORING SUMMARY")
        print(f"{'='*60}")
        print(f"Duration: {duration_minutes} minutes")
        print(f"Checks: {check_count}")
        print(f"Alerts: {len(self.alerts)}")
        print(
            f"Critical Alerts: {sum(1 for a in self.alerts if a['severity'] == 'critical')}"
        )
        print(f"Warnings: {sum(1 for a in self.alerts if a['severity'] == 'warning')}")
        print("This is not production-readiness or production-SLO proof.")
        print(f"{'='*60}\n")

        return {
            "duration_minutes": duration_minutes,
            "checks": check_count,
            "alerts": self.alerts,
            "metrics_history": self.metrics_history,
            **_claim_boundary_fields(),
        }


async def main():
    """Main monitoring function."""
    import argparse

    parser = argparse.ArgumentParser(
        description="Observe local HTTP health/metrics during rollout monitoring"
    )
    parser.add_argument(
        "--duration", type=int, default=60, help="Monitoring duration in minutes"
    )
    parser.add_argument(
        "--interval", type=int, default=10, help="Check interval in seconds"
    )
    parser.add_argument(
        "--url", type=str, default="http://localhost:8080", help="Base URL"
    )

    args = parser.parse_args()
    if args.duration < 0:
        parser.error("--duration must be >= 0")
    if args.interval <= 0:
        parser.error("--interval must be > 0")

    monitor = ProductionMonitor(base_url=args.url)
    result = await monitor.monitor(
        duration_minutes=args.duration, interval_seconds=args.interval
    )

    # Save results
    results_file = project_root / "monitoring_results.json"
    with open(results_file, "w") as f:
        json.dump(result, f, indent=2)

    print(f"✅ Monitoring results saved to: {results_file}")


if __name__ == "__main__":
    asyncio.run(main())
