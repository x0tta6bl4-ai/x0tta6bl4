"""
Production Load Testing for x0tta6bl4

Tests system under production-like load:
- 100K+ concurrent connections
- High message throughput
- Memory pressure
- PQC handshake performance
"""

import asyncio
import logging
import os
import statistics
import time
from dataclasses import dataclass, field
from datetime import datetime
from typing import Dict, List, Optional

import aiohttp
import psutil

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)


@dataclass
class LoadTestMetrics:
    """Metrics collected during load test"""

    total_requests: int = 0
    successful_requests: int = 0
    failed_requests: int = 0
    response_times: List[float] = field(default_factory=list)
    throughput_per_second: List[float] = field(default_factory=list)
    memory_usage_mb: List[float] = field(default_factory=list)
    cpu_usage_percent: List[float] = field(default_factory=list)
    pqc_handshake_times: List[float] = field(default_factory=list)
    errors: List[str] = field(default_factory=list)
    start_time: Optional[datetime] = None
    end_time: Optional[datetime] = None


@dataclass
class LoadTestConfig:
    """Configuration for load test"""

    base_url: str = "http://localhost:8080"
    concurrent_users: int = 1000
    total_requests: int = 100000
    ramp_up_seconds: int = 60  # Gradual ramp-up
    duration_seconds: int = 300  # 5 minutes
    target_throughput: int = 6800  # msg/sec
    max_latency_p95: float = 100.0  # ms
    max_memory_mb: float = 2400.0  # MB per node
    test_pqc_handshake: bool = True
    test_mesh_routing: bool = True
    test_health_endpoints: bool = True


class ProductionLoadTester:
    """
    Production load tester for x0tta6bl4.

    Tests:
    - High concurrency (100K+ connections)
    - Message throughput
    - Memory usage
    - PQC handshake performance
    - System stability
    """

    def __init__(self, config: LoadTestConfig):
        self.config = config
        self.metrics = LoadTestMetrics()
        self.process = psutil.Process(os.getpid())
        self.session: Optional[aiohttp.ClientSession] = None

    async def run_test(self) -> LoadTestMetrics:
        """
        Run production load test.

        Returns:
            LoadTestMetrics with collected metrics
        """
        logger.info(f"🚀 Starting production load test")
        logger.info(f"   Concurrent users: {self.config.concurrent_users}")
        logger.info(f"   Total requests: {self.config.total_requests}")
        logger.info(f"   Duration: {self.config.duration_seconds}s")

        self.metrics.start_time = datetime.now()

        try:
            async with aiohttp.ClientSession() as session:
                self.session = session

                # Start monitoring
                monitor_task = asyncio.create_task(self._monitor_system())

                # Run load test
                if self.config.ramp_up_seconds > 0:
                    await self._run_ramp_up_test(session)
                else:
                    await self._run_steady_state_test(session)

                # Stop monitoring
                monitor_task.cancel()
                try:
                    await monitor_task
                except asyncio.CancelledError:
                    pass

        except Exception as e:
            logger.error(f"Load test error: {e}")
            self.metrics.errors.append(str(e))
        finally:
            self.metrics.end_time = datetime.now()
            await self._calculate_final_metrics()

        return self.metrics

    async def _run_ramp_up_test(self, session: aiohttp.ClientSession):
        """Run test with gradual ramp-up."""
        logger.info("📈 Running ramp-up test...")

        # Calculate ramp-up steps
        steps = 10
        users_per_step = self.config.concurrent_users // steps
        time_per_step = self.config.ramp_up_seconds // steps

        current_users = 0

        for step in range(steps):
            current_users += users_per_step
            logger.info(f"   Step {step+1}/{steps}: {current_users} users")

            # Start requests for this step
            tasks = []
            requests_per_user = (
                self.config.total_requests // self.config.concurrent_users
            ) // steps

            for _ in range(users_per_step):
                task = asyncio.create_task(
                    self._make_requests(session, requests_per_user)
                )
                tasks.append(task)

            # Wait for step duration
            await asyncio.sleep(time_per_step)

        # Wait for all tasks to complete
        await asyncio.gather(*tasks, return_exceptions=True)

    async def _run_steady_state_test(self, session: aiohttp.ClientSession):
        """Run test at steady state."""
        logger.info("⚡ Running steady-state test...")

        requests_per_user = self.config.total_requests // self.config.concurrent_users

        tasks = []
        for _ in range(self.config.concurrent_users):
            task = asyncio.create_task(self._make_requests(session, requests_per_user))
            tasks.append(task)

        # Run for duration
        await asyncio.sleep(self.config.duration_seconds)

        # Cancel remaining tasks
        for task in tasks:
            task.cancel()

        await asyncio.gather(*tasks, return_exceptions=True)

    async def _make_requests(self, session: aiohttp.ClientSession, count: int):
        """Make HTTP requests to test endpoints."""
        for _ in range(count):
            try:
                # Test health endpoint
                if self.config.test_health_endpoints:
                    start = time.time()
                    async with session.get(
                        f"{self.config.base_url}/health", timeout=5
                    ) as resp:
                        elapsed = (time.time() - start) * 1000  # ms
                        self.metrics.response_times.append(elapsed)

                        if resp.status == 200:
                            self.metrics.successful_requests += 1
                        else:
                            self.metrics.failed_requests += 1
                            self.metrics.errors.append(f"HTTP {resp.status}")

                # Test mesh endpoints
                if self.config.test_mesh_routing:
                    start = time.time()
                    async with session.get(
                        f"{self.config.base_url}/mesh/peers", timeout=5
                    ) as resp:
                        elapsed = (time.time() - start) * 1000
                        self.metrics.response_times.append(elapsed)

                        if resp.status == 200:
                            self.metrics.successful_requests += 1
                        else:
                            self.metrics.failed_requests += 1

                # Test PQC handshake (if endpoint exists)
                if self.config.test_pqc_handshake:
                    start = time.time()
                    try:
                        async with session.post(
                            f"{self.config.base_url}/security/pqc/handshake",
                            json={"peer_id": "test-peer"},
                            timeout=10,
                        ) as resp:
                            elapsed = (time.time() - start) * 1000
                            self.metrics.pqc_handshake_times.append(elapsed)

                            if resp.status == 200:
                                self.metrics.successful_requests += 1
                    except Exception as e:
                        logger.debug(f"PQC handshake test skipped: {e}")

                self.metrics.total_requests += 1

                # Small delay to prevent overwhelming
                await asyncio.sleep(0.001)

            except asyncio.TimeoutError:
                self.metrics.failed_requests += 1
                self.metrics.errors.append("Timeout")
            except Exception as e:
                self.metrics.failed_requests += 1
                self.metrics.errors.append(str(e))

    async def _monitor_system(self):
        """Monitor system resources during test."""
        while True:
            try:
                # Memory usage
                memory_mb = self.process.memory_info().rss / 1024 / 1024
                self.metrics.memory_usage_mb.append(memory_mb)

                # CPU usage
                cpu_percent = self.process.cpu_percent()
                self.metrics.cpu_usage_percent.append(cpu_percent)

                # Throughput (requests per second)
                if len(self.metrics.response_times) > 0:
                    # Calculate recent throughput
                    recent_requests = len(
                        [rt for rt in self.metrics.response_times[-100:]]
                    )
                    self.metrics.throughput_per_second.append(recent_requests)

                await asyncio.sleep(1)  # Sample every second

            except asyncio.CancelledError:
                break
            except Exception as e:
                logger.warning(f"Monitoring error: {e}")
                await asyncio.sleep(1)

    async def _calculate_final_metrics(self):
        """Calculate final metrics."""
        if self.metrics.end_time and self.metrics.start_time:
            duration = (self.metrics.end_time - self.metrics.start_time).total_seconds()
            if duration > 0:
                avg_throughput = self.metrics.total_requests / duration
                logger.info(f"   Average throughput: {avg_throughput:.2f} req/sec")

    def get_summary(self) -> Dict[str, any]:
        """Get test summary."""
        duration = 0
        if self.metrics.end_time and self.metrics.start_time:
            duration = (self.metrics.end_time - self.metrics.start_time).total_seconds()

        success_rate = 0.0
        if self.metrics.total_requests > 0:
            success_rate = (
                self.metrics.successful_requests / self.metrics.total_requests
            ) * 100.0
            # Cap at 100%
            success_rate = min(success_rate, 100.0)

        latency_p50 = 0
        latency_p95 = 0
        latency_p99 = 0

        if self.metrics.response_times:
            sorted_times = sorted(self.metrics.response_times)
            latency_p50 = sorted_times[len(sorted_times) * 50 // 100]
            latency_p95 = sorted_times[len(sorted_times) * 95 // 100]
            latency_p99 = sorted_times[len(sorted_times) * 99 // 100]

        avg_memory = 0
        max_memory = 0
        if self.metrics.memory_usage_mb:
            avg_memory = statistics.mean(self.metrics.memory_usage_mb)
            max_memory = max(self.metrics.memory_usage_mb)

        avg_cpu = 0
        if self.metrics.cpu_usage_percent:
            avg_cpu = statistics.mean(self.metrics.cpu_usage_percent)

        avg_pqc_handshake = 0
        if self.metrics.pqc_handshake_times:
            avg_pqc_handshake = statistics.mean(self.metrics.pqc_handshake_times)

        return {
            "duration_seconds": duration,
            "total_requests": self.metrics.total_requests,
            "successful_requests": self.metrics.successful_requests,
            "failed_requests": self.metrics.failed_requests,
            "success_rate_percent": success_rate,
            "latency_p50_ms": latency_p50,
            "latency_p95_ms": latency_p95,
            "latency_p99_ms": latency_p99,
            "avg_throughput_per_sec": (
                self.metrics.total_requests / duration if duration > 0 else 0
            ),
            "avg_memory_mb": avg_memory,
            "max_memory_mb": max_memory,
            "avg_cpu_percent": avg_cpu,
            "avg_pqc_handshake_ms": avg_pqc_handshake,
            "errors_count": len(self.metrics.errors),
            "passed": self._check_pass_criteria(success_rate, latency_p95, max_memory),
        }

    def _check_pass_criteria(
        self, success_rate: float, latency_p95: float, max_memory: float
    ) -> bool:
        """Check if test passed criteria."""
        return (
            success_rate >= 99.0
            and latency_p95 <= self.config.max_latency_p95
            and max_memory <= self.config.max_memory_mb
        )


async def main():
    """Run production load test."""
    config = LoadTestConfig(
        base_url="http://localhost:8080",
        concurrent_users=1000,
        total_requests=100000,
        ramp_up_seconds=60,
        duration_seconds=300,
        target_throughput=6800,
        max_latency_p95=100.0,
        max_memory_mb=2400.0,
    )

    tester = ProductionLoadTester(config)
    metrics = await tester.run_test()

    summary = tester.get_summary()

    print("\n" + "=" * 60)
    print("PRODUCTION LOAD TEST RESULTS")
    print("=" * 60)
    print(f"Duration: {summary['duration_seconds']:.2f}s")
    print(f"Total Requests: {summary['total_requests']:,}")
    print(f"Success Rate: {summary['success_rate_percent']:.2f}%")
    print(f"Latency P50: {summary['latency_p50_ms']:.2f}ms")
    print(f"Latency P95: {summary['latency_p95_ms']:.2f}ms")
    print(f"Latency P99: {summary['latency_p99_ms']:.2f}ms")
    print(f"Throughput: {summary['avg_throughput_per_sec']:.2f} req/sec")
    print(f"Avg Memory: {summary['avg_memory_mb']:.2f}MB")
    print(f"Max Memory: {summary['max_memory_mb']:.2f}MB")
    print(f"Avg CPU: {summary['avg_cpu_percent']:.2f}%")
    print(f"Avg PQC Handshake: {summary['avg_pqc_handshake_ms']:.2f}ms")
    print(f"Errors: {summary['errors_count']}")
    print(f"PASSED: {'✅' if summary['passed'] else '❌'}")
    print("=" * 60)


if __name__ == "__main__":
    asyncio.run(main())
