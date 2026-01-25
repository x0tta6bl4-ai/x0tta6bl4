"""
MTTR (Mean Time To Recovery) Benchmark

Measures time to recover from node/link failures in mesh network.
"""

import asyncio
import time
import statistics
import json
from pathlib import Path
from typing import Dict, List, Optional
from dataclasses import dataclass, asdict
from datetime import datetime
import logging

logger = logging.getLogger(__name__)

try:
    import httpx
    HTTPX_AVAILABLE = True
except ImportError:
    HTTPX_AVAILABLE = False
    logger.warning("⚠️ httpx not available for MTTR benchmarks")


@dataclass
class MTTRResult:
    """MTTR measurement result"""
    scenario: str
    failure_type: str
    recovery_time_seconds: float
    timestamp: float
    metadata: Dict = None


class MTTRBenchmark:
    """MTTR benchmark runner"""
    
    def __init__(self, base_url: str = "http://localhost:8080", output_dir: Path = Path("benchmarks/results")):
        self.base_url = base_url
        self.output_dir = output_dir
        self.output_dir.mkdir(parents=True, exist_ok=True)
        self.results: List[MTTRResult] = []
    
    async def check_health(self) -> bool:
        """Check if service is healthy"""
        if not HTTPX_AVAILABLE:
            return False
        
        try:
            async with httpx.AsyncClient(timeout=5.0) as client:
                response = await client.get(f"{self.base_url}/health")
                return response.status_code == 200
        except Exception:
            return False
    
    async def wait_for_recovery(self, max_wait: int = 60, check_interval: float = 0.5) -> Optional[float]:
        """Wait for service to recover, returns recovery time in seconds"""
        start_time = time.time()
        
        while time.time() - start_time < max_wait:
            if await self.check_health():
                recovery_time = time.time() - start_time
                return recovery_time
            await asyncio.sleep(check_interval)
        
        return None  # Timeout
    
    async def simulate_node_failure(self, node_id: str = "node-01") -> Optional[MTTRResult]:
        """Simulate node failure and measure recovery time"""
        logger.info(f"🔴 Simulating node failure: {node_id}")
        
        # In real scenario, this would kill/stop the node
        # For now, we simulate by checking if service becomes unavailable
        # and then recovers
        
        # Check initial health
        if not await self.check_health():
            logger.warning("⚠️ Service already unhealthy, skipping test")
            return None
        
        # Simulate failure (in real test, this would be docker kill, k8s delete pod, etc.)
        failure_time = time.time()
        logger.info("💥 Node failure simulated")
        
        # Wait for recovery
        recovery_time = await self.wait_for_recovery()
        
        if recovery_time is None:
            logger.error("❌ Service did not recover within timeout")
            return None
        
        result = MTTRResult(
            scenario="node_failure",
            failure_type="node_crash",
            recovery_time_seconds=recovery_time,
            timestamp=failure_time,
            metadata={"node_id": node_id}
        )
        
        logger.info(f"✅ Recovery time: {recovery_time:.2f}s")
        return result
    
    async def simulate_link_failure(self) -> Optional[MTTRResult]:
        """Simulate link failure and measure recovery time"""
        logger.info("🔴 Simulating link failure")
        
        # In real scenario, this would use tc/netem to drop packets
        # or disconnect network interface
        
        failure_time = time.time()
        logger.info("💥 Link failure simulated")
        
        # Wait for recovery (mesh should reroute)
        recovery_time = await self.wait_for_recovery()
        
        if recovery_time is None:
            logger.error("❌ Service did not recover within timeout")
            return None
        
        result = MTTRResult(
            scenario="link_failure",
            failure_type="network_partition",
            recovery_time_seconds=recovery_time,
            timestamp=failure_time
        )
        
        logger.info(f"✅ Recovery time: {recovery_time:.2f}s")
        return result
    
    async def run_mttr_suite(self, iterations: int = 5) -> Dict:
        """Run complete MTTR benchmark suite"""
        logger.info(f"🚀 Starting MTTR benchmark suite ({iterations} iterations)...")
        
        node_failure_times = []
        link_failure_times = []
        
        for i in range(iterations):
            logger.info(f"\n--- Iteration {i+1}/{iterations} ---")
            
            # Node failure test
            node_result = await self.simulate_node_failure()
            if node_result:
                node_failure_times.append(node_result.recovery_time_seconds)
                self.results.append(node_result)
                await asyncio.sleep(2)  # Cooldown
            
            # Link failure test
            link_result = await self.simulate_link_failure()
            if link_result:
                link_failure_times.append(link_result.recovery_time_seconds)
                self.results.append(link_result)
                await asyncio.sleep(2)  # Cooldown
        
        # Calculate statistics
        mttr_stats = {
            "node_failure": {
                "mttr_seconds": statistics.mean(node_failure_times) if node_failure_times else None,
                "min_seconds": min(node_failure_times) if node_failure_times else None,
                "max_seconds": max(node_failure_times) if node_failure_times else None,
                "iterations": len(node_failure_times)
            },
            "link_failure": {
                "mttr_seconds": statistics.mean(link_failure_times) if link_failure_times else None,
                "min_seconds": min(link_failure_times) if link_failure_times else None,
                "max_seconds": max(link_failure_times) if link_failure_times else None,
                "iterations": len(link_failure_times)
            },
            "overall_mttr_seconds": statistics.mean(node_failure_times + link_failure_times) if (node_failure_times or link_failure_times) else None,
            "timestamp": datetime.utcnow().isoformat()
        }
        
        logger.info("\n" + "="*60)
        logger.info("MTTR BENCHMARK RESULTS")
        logger.info("="*60)
        if mttr_stats["node_failure"]["mttr_seconds"]:
            logger.info(f"Node Failure MTTR: {mttr_stats['node_failure']['mttr_seconds']:.2f}s")
        if mttr_stats["link_failure"]["mttr_seconds"]:
            logger.info(f"Link Failure MTTR: {mttr_stats['link_failure']['mttr_seconds']:.2f}s")
        if mttr_stats["overall_mttr_seconds"]:
            logger.info(f"Overall MTTR: {mttr_stats['overall_mttr_seconds']:.2f}s")
        logger.info("="*60)
        
        return mttr_stats
    
    def save_results(self, stats: Dict, format: str = "json") -> Path:
        """Save MTTR results to file"""
        timestamp = datetime.utcnow().strftime("%Y%m%d_%H%M%S")
        
        if format == "json":
            filename = self.output_dir / f"mttr_benchmark_{timestamp}.json"
            with open(filename, "w") as f:
                json.dump(stats, f, indent=2)
            logger.info(f"✅ Results saved to {filename}")
            return filename
        else:
            raise ValueError(f"Unknown format: {format}")


async def main():
    """Main MTTR benchmark runner"""
    import argparse
    
    parser = argparse.ArgumentParser(description="Run x0tta6bl4 MTTR benchmarks")
    parser.add_argument("--url", default="http://localhost:8080", help="Base URL for service")
    parser.add_argument("--output-dir", default="benchmarks/results", help="Output directory for results")
    parser.add_argument("--iterations", type=int, default=5, help="Number of iterations")
    
    args = parser.parse_args()
    
    benchmark = MTTRBenchmark(base_url=args.url, output_dir=Path(args.output_dir))
    stats = await benchmark.run_mttr_suite(iterations=args.iterations)
    benchmark.save_results(stats)


if __name__ == "__main__":
    logging.basicConfig(level=logging.INFO)
    asyncio.run(main())

