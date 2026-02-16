#!/usr/bin/env python3
"""
Health Check Dashboard

Real-time health status dashboard for production monitoring.
"""

import asyncio
import json
import sys
from datetime import datetime
from pathlib import Path
from typing import Any, Dict

import httpx

project_root = Path(__file__).parent.parent


class HealthDashboard:
    """Health check dashboard."""

    def __init__(self, base_url: str = "http://localhost:8080"):
        self.base_url = base_url
        self.status_history = []

    async def get_health_status(self) -> Dict[str, Any]:
        """Get comprehensive health status."""
        status = {
            "timestamp": datetime.now().isoformat(),
            "overall": "unknown",
            "checks": {},
        }

        # Health endpoint
        try:
            async with httpx.AsyncClient() as client:
                response = await client.get(f"{self.base_url}/health", timeout=5)
                status["checks"]["health_endpoint"] = {
                    "status": "healthy" if response.status_code == 200 else "unhealthy",
                    "status_code": response.status_code,
                }
        except Exception as e:
            status["checks"]["health_endpoint"] = {"status": "error", "error": str(e)}

        # Metrics endpoint
        try:
            async with httpx.AsyncClient() as client:
                response = await client.get(f"{self.base_url}/metrics", timeout=5)
                status["checks"]["metrics_endpoint"] = {
                    "status": (
                        "available" if response.status_code == 200 else "unavailable"
                    ),
                    "status_code": response.status_code,
                }
        except Exception as e:
            status["checks"]["metrics_endpoint"] = {"status": "error", "error": str(e)}

        # Mesh endpoints
        try:
            async with httpx.AsyncClient() as client:
                response = await client.get(f"{self.base_url}/mesh/peers", timeout=5)
                status["checks"]["mesh_peers"] = {
                    "status": (
                        "available" if response.status_code == 200 else "unavailable"
                    ),
                    "status_code": response.status_code,
                }
        except Exception as e:
            status["checks"]["mesh_peers"] = {"status": "error", "error": str(e)}

        # Determine overall status
        all_healthy = all(
            check.get("status") in ["healthy", "available"]
            for check in status["checks"].values()
        )

        status["overall"] = "healthy" if all_healthy else "unhealthy"

        return status

    def display_dashboard(self, status: Dict[str, Any]):
        """Display health dashboard."""
        # Clear screen (simplified)
        print("\n" * 2)
        print("=" * 60)
        print("🏥 HEALTH CHECK DASHBOARD")
        print("=" * 60)
        print(f"Time: {status['timestamp']}")
        print(f"Overall Status: {status['overall'].upper()}")
        print()
        print("Checks:")
        for check_name, check_status in status["checks"].items():
            status_icon = (
                "✅" if check_status.get("status") in ["healthy", "available"] else "❌"
            )
            print(
                f"  {status_icon} {check_name}: {check_status.get('status', 'unknown')}"
            )
        print("=" * 60)

    async def run_dashboard(self, interval: int = 5):
        """Run dashboard in loop."""
        print("Starting health check dashboard...")
        print(f"URL: {self.base_url}")
        print(f"Update interval: {interval} seconds")
        print("Press Ctrl+C to stop\n")

        try:
            while True:
                status = await self.get_health_status()
                self.status_history.append(status)
                self.display_dashboard(status)
                await asyncio.sleep(interval)
        except KeyboardInterrupt:
            print("\n\nDashboard stopped.")


async def main():
    """Main function."""
    import argparse

    parser = argparse.ArgumentParser(description="Health check dashboard")
    parser.add_argument(
        "--url", type=str, default="http://localhost:8080", help="Base URL"
    )
    parser.add_argument(
        "--interval", type=int, default=5, help="Update interval in seconds"
    )

    args = parser.parse_args()

    dashboard = HealthDashboard(base_url=args.url)
    await dashboard.run_dashboard(interval=args.interval)


if __name__ == "__main__":
    asyncio.run(main())
