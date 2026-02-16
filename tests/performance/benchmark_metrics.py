"""
Production Benchmarks for x0tta6bl4

Measures critical metrics:
- MTTR (Mean Time To Recovery)
- Latency (p95, p99)
- Throughput
- PQC overhead
- GraphSAGE inference time
"""

import asyncio
import csv
import json
import logging
import statistics
import time
from dataclasses import asdict, dataclass
from datetime import datetime
from pathlib import Path
from typing import Dict, List, Optional

logger = logging.getLogger(__name__)

# Try to import required components
try:
    from src.security.post_quantum_liboqs import (LIBOQS_AVAILABLE,
                                                  PQMeshSecurityLibOQS)

    PQC_AVAILABLE = LIBOQS_AVAILABLE
except ImportError:
    PQC_AVAILABLE = False
    logger.warning("⚠️ PQC not available for benchmarking")

try:
    from src.ml.graphsage_anomaly_detector import GraphSAGEAnomalyDetector

    GRAPHSAGE_AVAILABLE = True
except ImportError:
    GRAPHSAGE_AVAILABLE = False
    logger.warning("⚠️ GraphSAGE not available for benchmarking")

try:
    import httpx

    HTTPX_AVAILABLE = True
except ImportError:
    HTTPX_AVAILABLE = False
    logger.warning("⚠️ httpx not available for benchmarking")


@dataclass
class BenchmarkResult:
    """Single benchmark measurement result"""

    metric_name: str
    value: float
    unit: str
    timestamp: float
    metadata: Dict = None


@dataclass
class BenchmarkSuite:
    """Complete benchmark suite results"""

    suite_name: str
    timestamp: str
    mttr_seconds: Optional[float] = None
    latency_p50_ms: Optional[float] = None
    latency_p95_ms: Optional[float] = None
    latency_p99_ms: Optional[float] = None
    throughput_mbps: Optional[float] = None
    pqc_encrypt_latency_ms: Optional[float] = None
    pqc_decrypt_latency_ms: Optional[float] = None
    graphsage_inference_ms: Optional[float] = None
    results: List[BenchmarkResult] = None


class BenchmarkRunner:
    """Runs production benchmarks"""

    def __init__(self, output_dir: Path = Path("benchmarks/results")):
        self.output_dir = output_dir
        self.output_dir.mkdir(parents=True, exist_ok=True)
        self.results: List[BenchmarkResult] = []

    def measure_pqc_latency(self, iterations: int = 100) -> Dict[str, float]:
        """Measure PQC encryption/decryption latency"""
        if not PQC_AVAILABLE:
            logger.warning("⚠️ PQC not available, skipping PQC benchmarks")
            return {}

        logger.info(f"🔐 Measuring PQC latency ({iterations} iterations)...")

        try:
            security = PQMeshSecurityLibOQS("benchmark-node")
            encrypt_times = []
            decrypt_times = []

            # Generate test data
            test_data = b"x0tta6bl4 benchmark data" * 100  # ~2.5KB

            for _ in range(iterations):
                # Encryption
                start = time.perf_counter()
                encrypted = security.encrypt(test_data, "peer-node")
                encrypt_time = (time.perf_counter() - start) * 1000  # ms
                encrypt_times.append(encrypt_time)

                # Decryption
                start = time.perf_counter()
                decrypted = security.decrypt(encrypted, "peer-node")
                decrypt_time = (time.perf_counter() - start) * 1000  # ms
                decrypt_times.append(decrypt_time)

            encrypt_avg = statistics.mean(encrypt_times)
            encrypt_p95 = self._percentile(encrypt_times, 95)
            decrypt_avg = statistics.mean(decrypt_times)
            decrypt_p95 = self._percentile(decrypt_times, 95)

            logger.info(
                f"✅ PQC Encryption: avg={encrypt_avg:.2f}ms, p95={encrypt_p95:.2f}ms"
            )
            logger.info(
                f"✅ PQC Decryption: avg={decrypt_avg:.2f}ms, p95={decrypt_p95:.2f}ms"
            )

            return {
                "encrypt_avg_ms": encrypt_avg,
                "encrypt_p95_ms": encrypt_p95,
                "decrypt_avg_ms": decrypt_avg,
                "decrypt_p95_ms": decrypt_p95,
            }
        except Exception as e:
            logger.error(f"❌ PQC benchmark failed: {e}")
            return {}

    def measure_graphsage_inference(self, iterations: int = 50) -> Dict[str, float]:
        """Measure GraphSAGE inference latency"""
        if not GRAPHSAGE_AVAILABLE:
            logger.warning("⚠️ GraphSAGE not available, skipping inference benchmarks")
            return {}

        logger.info(f"🧠 Measuring GraphSAGE inference ({iterations} iterations)...")

        try:
            detector = GraphSAGEAnomalyDetector(use_quantization=False)
            inference_times = []

            # Simulate node features
            test_features = {
                "rssi": -50.0,
                "snr": 20.0,
                "loss_rate": 0.01,
                "link_age": 3600.0,
                "latency": 10.0,
                "throughput": 5.0,
                "cpu": 0.5,
                "memory": 0.6,
            }

            for _ in range(iterations):
                start = time.perf_counter()
                prediction = detector.predict(
                    node_id="test-node", node_features=test_features, neighbors=[]
                )
                inference_time = (time.perf_counter() - start) * 1000  # ms
                inference_times.append(inference_time)

            avg_time = statistics.mean(inference_times)
            p95_time = self._percentile(inference_times, 95)
            p99_time = self._percentile(inference_times, 99)

            logger.info(
                f"✅ GraphSAGE Inference: avg={avg_time:.2f}ms, p95={p95_time:.2f}ms, p99={p99_time:.2f}ms"
            )

            return {
                "inference_avg_ms": avg_time,
                "inference_p95_ms": p95_time,
                "inference_p99_ms": p99_time,
            }
        except Exception as e:
            logger.error(f"❌ GraphSAGE benchmark failed: {e}")
            return {}

    async def measure_api_latency(
        self, base_url: str = "http://localhost:8080", iterations: int = 100
    ) -> Dict[str, float]:
        """Measure API endpoint latency"""
        if not HTTPX_AVAILABLE:
            logger.warning("⚠️ httpx not available, skipping API latency benchmarks")
            return {}

        logger.info(f"🌐 Measuring API latency ({iterations} iterations)...")

        try:
            async with httpx.AsyncClient(timeout=10.0) as client:
                latencies = []

                for _ in range(iterations):
                    start = time.perf_counter()
                    try:
                        response = await client.get(f"{base_url}/health")
                        latency = (time.perf_counter() - start) * 1000  # ms
                        if response.status_code == 200:
                            latencies.append(latency)
                    except Exception as e:
                        logger.warning(f"Request failed: {e}")

                if not latencies:
                    logger.error("❌ No successful requests")
                    return {}

                p50 = self._percentile(latencies, 50)
                p95 = self._percentile(latencies, 95)
                p99 = self._percentile(latencies, 99)
                avg = statistics.mean(latencies)

                logger.info(
                    f"✅ API Latency: avg={avg:.2f}ms, p50={p50:.2f}ms, p95={p95:.2f}ms, p99={p99:.2f}ms"
                )

                return {
                    "api_latency_avg_ms": avg,
                    "api_latency_p50_ms": p50,
                    "api_latency_p95_ms": p95,
                    "api_latency_p99_ms": p99,
                }
        except Exception as e:
            logger.error(f"❌ API latency benchmark failed: {e}")
            return {}

    def _percentile(self, data: List[float], percentile: int) -> float:
        """Calculate percentile"""
        sorted_data = sorted(data)
        index = int(len(sorted_data) * percentile / 100)
        return sorted_data[min(index, len(sorted_data) - 1)]

    async def run_full_suite(
        self, base_url: str = "http://localhost:8080"
    ) -> BenchmarkSuite:
        """Run complete benchmark suite"""
        logger.info("🚀 Starting production benchmark suite...")

        suite = BenchmarkSuite(
            suite_name="x0tta6bl4_production_benchmarks",
            timestamp=datetime.utcnow().isoformat(),
            results=[],
        )

        # PQC benchmarks
        pqc_results = self.measure_pqc_latency()
        if pqc_results:
            suite.pqc_encrypt_latency_ms = pqc_results.get("encrypt_avg_ms")
            suite.pqc_decrypt_latency_ms = pqc_results.get("decrypt_avg_ms")

        # GraphSAGE benchmarks
        graphsage_results = self.measure_graphsage_inference()
        if graphsage_results:
            suite.graphsage_inference_ms = graphsage_results.get("inference_avg_ms")

        # API latency benchmarks
        api_results = await self.measure_api_latency(base_url)
        if api_results:
            suite.latency_p50_ms = api_results.get("api_latency_p50_ms")
            suite.latency_p95_ms = api_results.get("api_latency_p95_ms")
            suite.latency_p99_ms = api_results.get("api_latency_p99_ms")

        logger.info("✅ Benchmark suite completed")
        return suite

    def save_results(self, suite: BenchmarkSuite, format: str = "json") -> Path:
        """Save benchmark results to file"""
        timestamp = datetime.utcnow().strftime("%Y%m%d_%H%M%S")

        if format == "json":
            filename = self.output_dir / f"benchmark_{timestamp}.json"
            with open(filename, "w") as f:
                json.dump(asdict(suite), f, indent=2)
            logger.info(f"✅ Results saved to {filename}")
            return filename

        elif format == "csv":
            filename = self.output_dir / f"benchmark_{timestamp}.csv"
            with open(filename, "w", newline="") as f:
                writer = csv.writer(f)
                writer.writerow(["metric", "value", "unit", "timestamp"])
                # Write all metrics
                for key, value in asdict(suite).items():
                    if value is not None and key not in [
                        "suite_name",
                        "timestamp",
                        "results",
                    ]:
                        writer.writerow(
                            [
                                key,
                                value,
                                "ms" if "ms" in key else "seconds",
                                suite.timestamp,
                            ]
                        )
            logger.info(f"✅ Results saved to {filename}")
            return filename

        else:
            raise ValueError(f"Unknown format: {format}")


async def main():
    """Main benchmark runner"""
    import argparse

    parser = argparse.ArgumentParser(description="Run x0tta6bl4 production benchmarks")
    parser.add_argument(
        "--url", default="http://localhost:8080", help="Base URL for API benchmarks"
    )
    parser.add_argument(
        "--output-dir",
        default="benchmarks/results",
        help="Output directory for results",
    )
    parser.add_argument(
        "--format",
        choices=["json", "csv", "both"],
        default="both",
        help="Output format",
    )

    args = parser.parse_args()

    runner = BenchmarkRunner(output_dir=Path(args.output_dir))
    suite = await runner.run_full_suite(base_url=args.url)

    if args.format in ["json", "both"]:
        runner.save_results(suite, format="json")
    if args.format in ["csv", "both"]:
        runner.save_results(suite, format="csv")

    # Print summary
    print("\n" + "=" * 60)
    print("BENCHMARK SUMMARY")
    print("=" * 60)
    print(f"Timestamp: {suite.timestamp}")
    if suite.pqc_encrypt_latency_ms:
        print(f"PQC Encryption: {suite.pqc_encrypt_latency_ms:.2f}ms")
    if suite.pqc_decrypt_latency_ms:
        print(f"PQC Decryption: {suite.pqc_decrypt_latency_ms:.2f}ms")
    if suite.graphsage_inference_ms:
        print(f"GraphSAGE Inference: {suite.graphsage_inference_ms:.2f}ms")
    if suite.latency_p95_ms:
        print(f"API Latency (p95): {suite.latency_p95_ms:.2f}ms")
    if suite.latency_p99_ms:
        print(f"API Latency (p99): {suite.latency_p99_ms:.2f}ms")
    print("=" * 60)


if __name__ == "__main__":
    logging.basicConfig(level=logging.INFO)
    asyncio.run(main())
