#!/usr/bin/env python3
"""
Metrics Collector

Collects and stores metrics for analysis and comparison.
"""

import asyncio
import json
import sys
from datetime import datetime
from pathlib import Path
from typing import Any, Dict, List

import httpx

project_root = Path(__file__).parent.parent


class MetricsCollector:
    """Metrics collector for production monitoring."""

    def __init__(self, base_url: str = "http://localhost:8080"):
        self.base_url = base_url
        self.metrics = []

    async def collect_metrics(self) -> Dict[str, Any]:
        """Collect current metrics."""
        metrics = {
            "timestamp": datetime.now().isoformat(),
            "health": {},
            "performance": {},
            "resources": {},
        }

        try:
            async with httpx.AsyncClient() as client:
                # Health
                health_response = await client.get(f"{self.base_url}/health", timeout=5)
                if health_response.status_code == 200:
                    metrics["health"] = health_response.json()

                # Metrics (Prometheus format)
                metrics_response = await client.get(
                    f"{self.base_url}/metrics", timeout=5
                )
                if metrics_response.status_code == 200:
                    # Parse Prometheus metrics
                    metrics_text = metrics_response.text

                    # Extract key metrics (simplified parsing)
                    for line in metrics_text.split("\n"):
                        if line.startswith("#") or not line.strip():
                            continue

                        # Parse Prometheus metric line
                        parts = line.split()
                        if len(parts) >= 2:
                            metric_name = parts[0]
                            metric_value = parts[-1]

                            try:
                                value = float(metric_value)

                                if "error_rate" in metric_name:
                                    metrics["performance"]["error_rate"] = value
                                elif "latency" in metric_name and "p95" in metric_name:
                                    metrics["performance"]["latency_p95"] = value
                                elif "throughput" in metric_name:
                                    metrics["performance"]["throughput"] = value
                                elif "memory" in metric_name:
                                    metrics["resources"]["memory_mb"] = (
                                        value / 1024 / 1024
                                    )
                                elif "cpu" in metric_name:
                                    metrics["resources"]["cpu_percent"] = value
                            except ValueError:
                                pass

        except Exception as e:
            metrics["error"] = str(e)

        return metrics

    async def collect_continuous(
        self, duration_minutes: int = 60, interval_seconds: int = 10
    ):
        """
        Collect metrics continuously.

        Args:
            duration_minutes: How long to collect
            interval_seconds: Collection interval
        """
        print(f"\n{'='*60}")
        print(f"📊 METRICS COLLECTION")
        print(f"{'='*60}\n")
        print(f"Duration: {duration_minutes} minutes")
        print(f"Interval: {interval_seconds} seconds")
        print()

        start_time = datetime.now()
        end_time = start_time.timestamp() + (duration_minutes * 60)

        collection_count = 0

        while datetime.now().timestamp() < end_time:
            metrics = await self.collect_metrics()
            self.metrics.append(metrics)
            collection_count += 1

            elapsed = (datetime.now() - start_time).total_seconds()
            print(f"[{int(elapsed)}s] Collected metrics #{collection_count}", end="\r")

            await asyncio.sleep(interval_seconds)

        print(f"\n\n✅ Collected {collection_count} metric snapshots")

        # Save metrics
        metrics_file = (
            project_root / f"metrics_{datetime.now().strftime('%Y%m%d_%H%M%S')}.json"
        )
        with open(metrics_file, "w") as f:
            json.dump(self.metrics, f, indent=2)

        print(f"✅ Metrics saved to: {metrics_file}")

        return metrics_file


async def main():
    """Main function."""
    import argparse

    parser = argparse.ArgumentParser(description="Collect production metrics")
    parser.add_argument(
        "--url", type=str, default="http://localhost:8080", help="Base URL"
    )
    parser.add_argument(
        "--duration", type=int, default=60, help="Collection duration in minutes"
    )
    parser.add_argument(
        "--interval", type=int, default=10, help="Collection interval in seconds"
    )

    args = parser.parse_args()

    collector = MetricsCollector(base_url=args.url)
    await collector.collect_continuous(
        duration_minutes=args.duration, interval_seconds=args.interval
    )


if __name__ == "__main__":
    asyncio.run(main())
