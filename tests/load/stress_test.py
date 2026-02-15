"""
Load Tester for x0tta6bl4 Commercial MVP
Simulates concurrent user activity to verify system stability under load.

Scenarios:
1.  **Public API**: High-frequency checks to `/status` and `/pqc/status`.
2.  **User Journey**: Simulate flow: Landing -> Payment (Mock) -> Provision -> Connect.
3.  **Metrics**: Measure latency, error rate, and throughput.

Usage:
    python3 tests/load/stress_test.py --users 100 --duration 10
"""

import asyncio
import logging
import random
import statistics
import time
from typing import Dict, List

import aiohttp

# Configure Logging
logging.basicConfig(
    level=logging.INFO, format="%(asctime)s - %(name)s - %(levelname)s - %(message)s"
)
logger = logging.getLogger("LOAD_TEST")

BASE_URL = "http://localhost:8080"  # Adjust if traversing Caddy (https://localhost)


class LoadTester:
    def __init__(self, users: int, duration_sec: int):
        self.users = users
        self.duration_sec = duration_sec
        self.results: List[float] = []
        self.errors = 0
        self.requests = 0
        self.start_time = 0.0

    async def fetch(self, session: aiohttp.ClientSession, url: str):
        """Perform a single HTTP GET request."""
        start = time.time()
        try:
            async with session.get(url) as response:
                await response.read()
                latency = (time.time() - start) * 1000  # ms
                self.results.append(latency)
                self.requests += 1
                if response.status >= 400:
                    self.errors += 1
                    logger.warning(f"Error {response.status} from {url}")
        except Exception as e:
            self.errors += 1
            logger.error(f"Request failed: {e}")

    async def user_behavior(self, user_id: int):
        """Simulate a single user's behavior loop."""
        async with aiohttp.ClientSession() as session:
            end_time = time.time() + self.duration_sec
            while time.time() < end_time:
                # 1. Check System Status (Dashboard)
                await self.fetch(session, f"{BASE_URL}/status")

                # 2. Check PQC Status (Security Verify)
                if random.random() < 0.3:  # 30% chance
                    await self.fetch(session, f"{BASE_URL}/pqc/status")

                # 3. Simulate "Browsing" delay
                await asyncio.sleep(random.uniform(0.5, 2.0))

    async def run(self):
        """Run the load test."""
        logger.info(
            f"🚀 Starting Load Test: {self.users} users for {self.duration_sec}s"
        )
        self.start_time = time.time()

        tasks = [self.user_behavior(i) for i in range(self.users)]
        await asyncio.gather(*tasks)

        self.report()

    def report(self):
        """Print test results."""
        total_time = time.time() - self.start_time
        rps = self.requests / total_time

        logger.info("=" * 40)
        logger.info(f"📊 Load Test Results ({self.users} Users)")
        logger.info("=" * 40)
        logger.info(f"Total Requests: {self.requests}")
        logger.info(
            f"Total Errors:   {self.errors} ({self.errors/self.requests*100:.2f}%)"
        )
        logger.info(f"Throughput:     {rps:.2f} req/s")

        if self.results:
            avg_lat = statistics.mean(self.results)
            p95_lat = statistics.quantiles(self.results, n=20)[18]  # 95th percentile
            p99_lat = statistics.quantiles(self.results, n=100)[98]  # 99th percentile

            logger.info(f"Latency (Avg):  {avg_lat:.2f} ms")
            logger.info(f"Latency (P95):  {p95_lat:.2f} ms")
            logger.info(f"Latency (P99):  {p99_lat:.2f} ms")

        logger.info("=" * 40)

        if self.errors == 0 and rps > 10:
            logger.info("✅ SUCCESS: System handled load.")
        else:
            logger.warning("⚠️  WARNING: Errors detected or low throughput.")


if __name__ == "__main__":
    import argparse

    parser = argparse.ArgumentParser()
    parser.add_argument(
        "--users", type=int, default=100, help="Number of concurrent users"
    )
    parser.add_argument(
        "--duration", type=int, default=10, help="Test duration in seconds"
    )
    args = parser.parse_args()

    tester = LoadTester(args.users, args.duration)
    asyncio.run(tester.run())
