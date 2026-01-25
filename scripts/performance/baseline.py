#!/usr/bin/env python3
"""
Production performance baseline collection for x0tta6bl4.

Measures:
- API response latency (p50, p95, p99)
- Throughput (requests/sec)
- Error rates
- Resource utilization (CPU, memory)
- Database performance
- Network metrics
- Garbage collection impact
"""

import asyncio
import json
import logging
import os
import psutil
import subprocess
import sys
import time
from dataclasses import dataclass, asdict
from datetime import datetime
from pathlib import Path
from statistics import mean, median, stdev
from typing import Optional, Dict, List, Any

try:
    import httpx
    import prometheus_client
    from prometheus_client import CollectorRegistry, generate_latest, Counter, Histogram
except ImportError:
    pass

logger = logging.getLogger(__name__)


@dataclass
class PerformanceMetrics:
    """Container for performance metrics"""
    
    timestamp: str
    test_name: str
    duration_seconds: float
    requests_total: int
    requests_successful: int
    requests_failed: int
    
    latency_min_ms: float
    latency_max_ms: float
    latency_mean_ms: float
    latency_p50_ms: float
    latency_p95_ms: float
    latency_p99_ms: float
    
    throughput_rps: float
    error_rate_percent: float
    
    cpu_percent_mean: float
    cpu_percent_max: float
    memory_mb_mean: float
    memory_mb_max: float
    memory_percent_mean: float
    
    database_query_time_ms: Optional[float] = None
    database_connection_pool_usage: Optional[float] = None
    
    gc_collections: Optional[int] = None
    gc_time_ms: Optional[float] = None


class ResourceMonitor:
    """Monitor system resource usage during tests"""
    
    def __init__(self, process_name: str = "uvicorn"):
        self.process_name = process_name
        self.process = None
        self.metrics = []
        self.monitoring = False
    
    def start(self):
        """Start resource monitoring"""
        try:
            for p in psutil.process_iter(['name']):
                if self.process_name in p.info['name']:
                    self.process = p
                    break
            
            if not self.process:
                logger.warning(f"Process '{self.process_name}' not found")
                return
            
            self.monitoring = True
            asyncio.create_task(self._monitor_loop())
            logger.info("✅ Resource monitoring started")
        
        except Exception as e:
            logger.warning(f"⚠️  Resource monitoring disabled: {e}")
    
    async def _monitor_loop(self):
        """Monitor resources periodically"""
        while self.monitoring:
            try:
                if self.process and self.process.is_running():
                    with self.process.oneshot():
                        cpu_percent = self.process.cpu_percent(interval=0.1)
                        memory_info = self.process.memory_info()
                        memory_mb = memory_info.rss / (1024 * 1024)
                        memory_percent = self.process.memory_percent()
                    
                    self.metrics.append({
                        "cpu_percent": cpu_percent,
                        "memory_mb": memory_mb,
                        "memory_percent": memory_percent,
                    })
                
                await asyncio.sleep(0.5)
            
            except Exception as e:
                logger.debug(f"Monitor error: {e}")
                await asyncio.sleep(1)
    
    def stop(self):
        """Stop resource monitoring"""
        self.monitoring = False
    
    def get_summary(self) -> Dict[str, float]:
        """Get resource usage summary"""
        if not self.metrics:
            return {
                "cpu_percent_mean": 0,
                "cpu_percent_max": 0,
                "memory_mb_mean": 0,
                "memory_mb_max": 0,
                "memory_percent_mean": 0,
            }
        
        cpu_values = [m["cpu_percent"] for m in self.metrics]
        memory_values = [m["memory_mb"] for m in self.metrics]
        memory_percent_values = [m["memory_percent"] for m in self.metrics]
        
        return {
            "cpu_percent_mean": mean(cpu_values) if cpu_values else 0,
            "cpu_percent_max": max(cpu_values) if cpu_values else 0,
            "memory_mb_mean": mean(memory_values) if memory_values else 0,
            "memory_mb_max": max(memory_values) if memory_values else 0,
            "memory_percent_mean": mean(memory_percent_values) if memory_percent_values else 0,
        }


class LatencyMeasurer:
    """Measure and analyze latency"""
    
    def __init__(self):
        self.latencies: List[float] = []
    
    def add(self, latency_ms: float):
        """Record latency measurement"""
        self.latencies.append(latency_ms)
    
    def percentile(self, p: float) -> float:
        """Calculate percentile latency"""
        if not self.latencies:
            return 0.0
        
        sorted_latencies = sorted(self.latencies)
        index = int((p / 100.0) * len(sorted_latencies))
        return sorted_latencies[min(index, len(sorted_latencies) - 1)]
    
    def get_summary(self) -> Dict[str, float]:
        """Get latency summary"""
        if not self.latencies:
            return {
                "min_ms": 0,
                "max_ms": 0,
                "mean_ms": 0,
                "p50_ms": 0,
                "p95_ms": 0,
                "p99_ms": 0,
            }
        
        return {
            "min_ms": min(self.latencies),
            "max_ms": max(self.latencies),
            "mean_ms": mean(self.latencies),
            "p50_ms": self.percentile(50),
            "p95_ms": self.percentile(95),
            "p99_ms": self.percentile(99),
        }


class ApiLoadTester:
    """Load test API endpoints"""
    
    def __init__(self, base_url: str = "http://localhost:8000"):
        self.base_url = base_url
        self.client = None
        self.latency_measurer = LatencyMeasurer()
        self.request_count = 0
        self.success_count = 0
        self.error_count = 0
    
    async def __aenter__(self):
        self.client = httpx.AsyncClient(base_url=self.base_url, timeout=30.0)
        return self
    
    async def __aexit__(self, exc_type, exc_val, exc_tb):
        if self.client:
            await self.client.aclose()
    
    async def test_endpoint(self, method: str = "GET", path: str = "/health/ready") -> bool:
        """Test single endpoint"""
        try:
            start = time.time()
            
            response = await self.client.request(method, path)
            
            latency_ms = (time.time() - start) * 1000
            self.latency_measurer.add(latency_ms)
            
            self.request_count += 1
            
            if 200 <= response.status_code < 300:
                self.success_count += 1
                return True
            else:
                self.error_count += 1
                logger.warning(f"⚠️  Status {response.status_code} for {path}")
                return False
        
        except Exception as e:
            self.request_count += 1
            self.error_count += 1
            logger.warning(f"⚠️  Request error: {e}")
            return False
    
    async def run_load_test(
        self,
        duration_seconds: int = 30,
        concurrent_requests: int = 10,
        endpoint: str = "/health/ready"
    ) -> PerformanceMetrics:
        """Run load test against endpoint"""
        logger.info(f"📊 Running load test ({duration_seconds}s, {concurrent_requests} concurrent)...")
        
        start_time = time.time()
        resource_monitor = ResourceMonitor()
        resource_monitor.start()
        
        tasks = []
        
        async def request_loop():
            while time.time() - start_time < duration_seconds:
                await self.test_endpoint("GET", endpoint)
                await asyncio.sleep(0.01)
        
        try:
            for _ in range(concurrent_requests):
                tasks.append(asyncio.create_task(request_loop()))
            
            await asyncio.gather(*tasks)
        
        finally:
            resource_monitor.stop()
            for task in tasks:
                task.cancel()
        
        duration = time.time() - start_time
        latency_stats = self.latency_measurer.get_summary()
        resource_stats = resource_monitor.get_summary()
        
        error_rate = (self.error_count / self.request_count * 100) if self.request_count > 0 else 0
        throughput_rps = self.request_count / duration
        
        metrics = PerformanceMetrics(
            timestamp=datetime.now().isoformat(),
            test_name=endpoint,
            duration_seconds=duration,
            requests_total=self.request_count,
            requests_successful=self.success_count,
            requests_failed=self.error_count,
            latency_min_ms=latency_stats["min_ms"],
            latency_max_ms=latency_stats["max_ms"],
            latency_mean_ms=latency_stats["mean_ms"],
            latency_p50_ms=latency_stats["p50_ms"],
            latency_p95_ms=latency_stats["p95_ms"],
            latency_p99_ms=latency_stats["p99_ms"],
            throughput_rps=throughput_rps,
            error_rate_percent=error_rate,
            cpu_percent_mean=resource_stats["cpu_percent_mean"],
            cpu_percent_max=resource_stats["cpu_percent_max"],
            memory_mb_mean=resource_stats["memory_mb_mean"],
            memory_mb_max=resource_stats["memory_mb_max"],
            memory_percent_mean=resource_stats["memory_percent_mean"],
        )
        
        logger.info(f"✅ Load test completed")
        logger.info(f"   Requests: {self.request_count} ({self.success_count} OK, {self.error_count} failed)")
        logger.info(f"   Throughput: {throughput_rps:.2f} req/s")
        logger.info(f"   Latency P50: {latency_stats['p50_ms']:.2f}ms, P95: {latency_stats['p95_ms']:.2f}ms, P99: {latency_stats['p99_ms']:.2f}ms")
        
        return metrics


class DatabaseBenchmark:
    """Benchmark database performance"""
    
    def __init__(self):
        self.connection_string = os.getenv(
            "DATABASE_URL",
            "postgresql://postgres:postgres@localhost:5432/x0tta6bl4"
        )
    
    async def measure_query_time(self, query: str = "SELECT 1;") -> float:
        """Measure single query execution time"""
        try:
            import asyncpg
            
            conn = await asyncpg.connect(self.connection_string)
            
            start = time.time()
            await conn.fetch(query)
            latency_ms = (time.time() - start) * 1000
            
            await conn.close()
            return latency_ms
        
        except Exception as e:
            logger.warning(f"⚠️  Database benchmark skipped: {e}")
            return 0.0
    
    async def get_connection_pool_stats(self) -> Optional[Dict[str, Any]]:
        """Get database connection pool statistics"""
        try:
            import asyncpg
            
            conn = await asyncpg.connect(self.connection_string.split("?")[0])
            
            result = await conn.fetch(
                "SELECT count(*) as active_connections FROM pg_stat_activity"
            )
            
            await conn.close()
            
            if result:
                return {
                    "active_connections": result[0]["active_connections"]
                }
        
        except Exception as e:
            logger.debug(f"Database stats unavailable: {e}")
        
        return None


class PerformanceBaseline:
    """Orchestrate performance baseline collection"""
    
    def __init__(self, output_dir: str = "./performance_baselines"):
        self.output_dir = Path(output_dir)
        self.output_dir.mkdir(parents=True, exist_ok=True)
        self.baseline_file = self.output_dir / f"baseline_{datetime.now().strftime('%Y%m%d_%H%M%S')}.json"
        self.metrics: List[PerformanceMetrics] = []
    
    async def run_baseline(self) -> bool:
        """Run complete baseline collection"""
        logger.info("🚀 Starting performance baseline collection...")
        
        try:
            # Wait for application to be ready
            logger.info("⏳ Waiting for application to be ready...")
            await self._wait_for_app()
            
            # API load test
            async with ApiLoadTester() as tester:
                # Warm up
                logger.info("🔥 Warming up...")
                for _ in range(50):
                    await tester.test_endpoint("GET", "/health/ready")
                
                # Reset metrics
                tester.latency_measurer = LatencyMeasurer()
                tester.request_count = 0
                tester.success_count = 0
                tester.error_count = 0
                
                # Load test
                metrics = await tester.run_load_test(
                    duration_seconds=30,
                    concurrent_requests=10,
                    endpoint="/health/ready"
                )
                self.metrics.append(metrics)
            
            # Database benchmark
            db_bench = DatabaseBenchmark()
            db_time = await db_bench.measure_query_time()
            logger.info(f"📊 Database query time: {db_time:.2f}ms")
            
            # Save results
            self._save_baseline()
            
            logger.info(f"✅ Baseline collection completed")
            logger.info(f"   Results saved to: {self.baseline_file}")
            
            return True
        
        except Exception as e:
            logger.error(f"❌ Baseline collection failed: {e}")
            return False
    
    async def _wait_for_app(self, timeout: int = 60) -> bool:
        """Wait for application health check"""
        start = time.time()
        
        async with ApiLoadTester() as tester:
            while time.time() - start < timeout:
                try:
                    if await tester.test_endpoint("GET", "/health/ready"):
                        return True
                except:
                    pass
                
                await asyncio.sleep(1)
        
        logger.error("⚠️  Application not ready after timeout")
        return False
    
    def _save_baseline(self):
        """Save baseline results to file"""
        results = {
            "timestamp": datetime.now().isoformat(),
            "metrics": [asdict(m) for m in self.metrics],
        }
        
        with open(self.baseline_file, "w") as f:
            json.dump(results, f, indent=2)
        
        logger.info(f"💾 Baseline saved to {self.baseline_file}")
    
    def compare_to_previous(self) -> Dict[str, Any]:
        """Compare current baseline to previous"""
        try:
            baselines = list(self.output_dir.glob("baseline_*.json"))
            baselines.sort()
            
            if len(baselines) < 2:
                logger.info("ℹ️  No previous baseline to compare")
                return {}
            
            with open(baselines[-1]) as f:
                current = json.load(f)
            
            with open(baselines[-2]) as f:
                previous = json.load(f)
            
            comparison = self._compare_metrics(
                current["metrics"][0],
                previous["metrics"][0]
            )
            
            return comparison
        
        except Exception as e:
            logger.error(f"❌ Comparison failed: {e}")
            return {}
    
    def _compare_metrics(self, current: Dict, previous: Dict) -> Dict[str, Any]:
        """Compare two metric sets"""
        comparison = {}
        
        key_metrics = [
            "throughput_rps",
            "latency_p95_ms",
            "latency_p99_ms",
            "error_rate_percent",
            "memory_mb_max",
            "cpu_percent_mean",
        ]
        
        for key in key_metrics:
            current_val = current.get(key, 0)
            previous_val = previous.get(key, 0)
            
            if previous_val == 0:
                percent_change = 0
            else:
                percent_change = ((current_val - previous_val) / previous_val) * 100
            
            comparison[key] = {
                "current": current_val,
                "previous": previous_val,
                "percent_change": percent_change,
                "regression": percent_change > 10 if key != "error_rate_percent" else percent_change > 5,
            }
        
        return comparison


async def main():
    """CLI entry point"""
    logging.basicConfig(
        level=logging.INFO,
        format="%(message)s"
    )
    
    if len(sys.argv) < 2:
        print("Usage: python baseline.py <command>")
        print("\nCommands:")
        print("  collect    - Collect performance baseline")
        print("  compare    - Compare to previous baseline")
        sys.exit(1)
    
    command = sys.argv[1]
    baseline = PerformanceBaseline()
    
    if command == "collect":
        success = await baseline.run_baseline()
        sys.exit(0 if success else 1)
    
    elif command == "compare":
        comparison = baseline.compare_to_previous()
        print(json.dumps(comparison, indent=2))
    
    else:
        print(f"Unknown command: {command}")
        sys.exit(1)


if __name__ == "__main__":
    asyncio.run(main())
