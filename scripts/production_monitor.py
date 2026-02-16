#!/usr/bin/env python3
"""
Production Monitoring Script

Monitors production deployment in real-time during rollout.
"""

import asyncio
import json
import sys
from datetime import datetime
from pathlib import Path
from typing import Any, Dict, List

import httpx

project_root = Path(__file__).parent.parent
sys.path.insert(0, str(project_root))

try:
    from src.monitoring.production_monitoring import get_production_monitor
except ImportError:
    print("⚠️ Production monitoring module not available")
    get_production_monitor = None


class ProductionMonitor:
    """Real-time production monitor."""

    def __init__(self, base_url: str = "http://localhost:8080"):
        self.base_url = base_url
        self.alerts: List[Dict[str, Any]] = []
        self.metrics_history: List[Dict[str, Any]] = []

    async def check_health(self) -> Dict[str, Any]:
        """Check health endpoint."""
        try:
            async with httpx.AsyncClient() as client:
                response = await client.get(f"{self.base_url}/health", timeout=5)
                return {
                    "healthy": response.status_code == 200,
                    "status_code": response.status_code,
                    "timestamp": datetime.now().isoformat(),
                }
        except Exception as e:
            return {
                "healthy": False,
                "error": str(e),
                "timestamp": datetime.now().isoformat(),
            }

    async def check_metrics(self) -> Dict[str, Any]:
        """Check Prometheus metrics."""
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
                        "timestamp": datetime.now().isoformat(),
                    }
        except Exception as e:
            return {
                "available": False,
                "error": str(e),
                "timestamp": datetime.now().isoformat(),
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
        Monitor production deployment.

        Args:
            duration_minutes: How long to monitor
            interval_seconds: Check interval
        """
        print(f"\n{'='*60}")
        print(f"📊 PRODUCTION MONITORING")
        print(f"{'='*60}\n")
        print(f"Monitoring for {duration_minutes} minutes")
        print(f"Check interval: {interval_seconds} seconds")
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
        print(f"{'='*60}\n")

        return {
            "duration_minutes": duration_minutes,
            "checks": check_count,
            "alerts": self.alerts,
            "metrics_history": self.metrics_history,
        }


async def main():
    """Main monitoring function."""
    import argparse

    parser = argparse.ArgumentParser(description="Monitor production deployment")
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
