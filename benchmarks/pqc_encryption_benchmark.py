#!/usr/bin/env python3
"""
PQC Encryption Performance Benchmark
=====================================

Comprehensive benchmark for Post-Quantum Cryptography operations:
- Kyber KEM key generation
- Encapsulation/Decapsulation performance
- AES-GCM encryption throughput
- Hybrid handshake simulation
- Batch processing scalability
"""

import asyncio
import time
import statistics
import json
import os
from datetime import datetime
from typing import Dict, List, Any, Tuple, Optional
from dataclasses import dataclass
from concurrent.futures import ThreadPoolExecutor
import logging

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)


@dataclass
class CryptoBenchmarkResult:
    """Result of a crypto operation benchmark"""
    operation: str
    iterations: int
    total_time_ms: float
    avg_time_ms: float
    min_time_ms: float
    max_time_ms: float
    p50_ms: float
    p95_ms: float
    p99_ms: float
    ops_per_sec: float
    target_met: bool
    target_ms: float


class PQCEncryptionBenchmark:
    """Benchmark suite for PQC encryption operations"""
    
    def __init__(self):
        self.pqc_available = False
        self.pqc_crypto = None
        self.results: Dict[str, Any] = {}
        
        # Try to import PQC modules
        self._init_pqc()
    
    def _init_pqc(self):
        """Initialize PQC modules"""
        try:
            from src.crypto.pqc_crypto import PQCCrypto
            self.pqc_crypto = PQCCrypto
            self.pqc_available = True
            logger.info("✅ PQC module available")
        except ImportError as e:
            logger.warning(f"⚠️ PQC module not available: {e}")
            self.pqc_available = False
    
    def _measure_operation(self, operation_func, iterations: int = 100) -> CryptoBenchmarkResult:
        """Measure a crypto operation multiple times"""
        times = []
        
        for _ in range(iterations):
            start = time.perf_counter()
            try:
                operation_func()
                elapsed = (time.perf_counter() - start) * 1000
                times.append(elapsed)
            except Exception as e:
                logger.warning(f"Operation failed: {e}")
        
        if not times:
            return None
        
        sorted_times = sorted(times)
        avg_time = statistics.mean(times)
        
        return CryptoBenchmarkResult(
            operation=operation_func.__name__ if hasattr(operation_func, '__name__') else 'unknown',
            iterations=len(times),
            total_time_ms=sum(times),
            avg_time_ms=avg_time,
            min_time_ms=min(times),
            max_time_ms=max(times),
            p50_ms=sorted_times[int(len(sorted_times) * 0.50)],
            p95_ms=sorted_times[int(len(sorted_times) * 0.95)],
            p99_ms=sorted_times[int(len(sorted_times) * 0.99)],
            ops_per_sec=1000 / avg_time if avg_time > 0 else 0,
            target_met=True,  # Will be set by caller
            target_ms=0
        )
    
    def benchmark_aes_gcm_encryption(self, data_size_bytes: int = 1024, iterations: int = 1000) -> CryptoBenchmarkResult:
        """Benchmark AES-GCM encryption"""
        logger.info(f"  Benchmarking AES-GCM encryption ({data_size_bytes} bytes)...")
        
        if self.pqc_available:
            crypto = self.pqc_crypto(use_real_pqc=False)  # Use mock for pure AES benchmark
            data = os.urandom(data_size_bytes)
            
            def encrypt_op():
                crypto.encrypt(data)
            
            result = self._measure_operation(encrypt_op, iterations)
            if result:
                result.operation = f"aes_gcm_encrypt_{data_size_bytes}b"
                result.target_met = result.avg_time_ms < 1.0  # Target: <1ms for 1KB
                result.target_ms = 1.0
            return result
        else:
            # Simulate AES-GCM performance
            return self._simulate_aes_gcm(data_size_bytes, iterations)
    
    def _simulate_aes_gcm(self, data_size_bytes: int, iterations: int) -> CryptoBenchmarkResult:
        """Simulate AES-GCM performance based on typical hardware"""
        # AES-GCM typically achieves 1-10 GB/s on modern hardware
        # Simulate ~2 GB/s throughput
        base_time_per_kb = 0.5  # 0.5ms per KB (conservative)
        time_per_op = base_time_per_kb * (data_size_bytes / 1024)
        
        times = [time_per_op * (0.8 + 0.4 * (hash(str(i)) % 100) / 100) for i in range(iterations)]
        sorted_times = sorted(times)
        avg_time = statistics.mean(times)
        
        return CryptoBenchmarkResult(
            operation=f"aes_gcm_encrypt_{data_size_bytes}b_simulated",
            iterations=iterations,
            total_time_ms=sum(times),
            avg_time_ms=avg_time,
            min_time_ms=min(times),
            max_time_ms=max(times),
            p50_ms=sorted_times[int(len(sorted_times) * 0.50)],
            p95_ms=sorted_times[int(len(sorted_times) * 0.95)],
            p99_ms=sorted_times[int(len(sorted_times) * 0.99)],
            ops_per_sec=1000 / avg_time if avg_time > 0 else 0,
            target_met=avg_time < 1.0,
            target_ms=1.0
        )
    
    def benchmark_kyber_keygen(self, iterations: int = 100) -> CryptoBenchmarkResult:
        """Benchmark Kyber key generation"""
        logger.info(f"  Benchmarking Kyber key generation...")
        
        if self.pqc_available:
            def keygen_op():
                crypto = self.pqc_crypto(use_real_pqc=True)
                return crypto.get_public_key()
            
            result = self._measure_operation(keygen_op, iterations)
            if result:
                result.operation = "kyber_keygen"
                result.target_met = result.avg_time_ms < 10.0  # Target: <10ms
                result.target_ms = 10.0
            return result
        else:
            return self._simulate_kyber_keygen(iterations)
    
    def _simulate_kyber_keygen(self, iterations: int) -> CryptoBenchmarkResult:
        """Simulate Kyber key generation performance"""
        # Kyber-768 keygen: ~0.5-2ms on modern hardware
        times = [1.0 + 0.5 * (hash(str(i)) % 100) / 100 for i in range(iterations)]
        sorted_times = sorted(times)
        avg_time = statistics.mean(times)
        
        return CryptoBenchmarkResult(
            operation="kyber_keygen_simulated",
            iterations=iterations,
            total_time_ms=sum(times),
            avg_time_ms=avg_time,
            min_time_ms=min(times),
            max_time_ms=max(times),
            p50_ms=sorted_times[int(len(sorted_times) * 0.50)],
            p95_ms=sorted_times[int(len(sorted_times) * 0.95)],
            p99_ms=sorted_times[int(len(sorted_times) * 0.99)],
            ops_per_sec=1000 / avg_time if avg_time > 0 else 0,
            target_met=avg_time < 10.0,
            target_ms=10.0
        )
    
    def benchmark_kyber_encaps(self, iterations: int = 100) -> CryptoBenchmarkResult:
        """Benchmark Kyber encapsulation"""
        logger.info(f"  Benchmarking Kyber encapsulation...")
        
        if self.pqc_available:
            crypto = self.pqc_crypto(use_real_pqc=True)
            public_key = crypto.get_public_key()
            
            if public_key:
                def encaps_op():
                    return crypto.encapsulate_for_peer(public_key)
                
                result = self._measure_operation(encaps_op, iterations)
                if result:
                    result.operation = "kyber_encaps"
                    result.target_met = result.avg_time_ms < 5.0  # Target: <5ms
                    result.target_ms = 5.0
                return result
        
        return self._simulate_kyber_encaps(iterations)
    
    def _simulate_kyber_encaps(self, iterations: int) -> CryptoBenchmarkResult:
        """Simulate Kyber encapsulation performance"""
        # Kyber-768 encaps: ~0.3-1ms on modern hardware
        times = [0.5 + 0.3 * (hash(str(i)) % 100) / 100 for i in range(iterations)]
        sorted_times = sorted(times)
        avg_time = statistics.mean(times)
        
        return CryptoBenchmarkResult(
            operation="kyber_encaps_simulated",
            iterations=iterations,
            total_time_ms=sum(times),
            avg_time_ms=avg_time,
            min_time_ms=min(times),
            max_time_ms=max(times),
            p50_ms=sorted_times[int(len(sorted_times) * 0.50)],
            p95_ms=sorted_times[int(len(sorted_times) * 0.95)],
            p99_ms=sorted_times[int(len(sorted_times) * 0.99)],
            ops_per_sec=1000 / avg_time if avg_time > 0 else 0,
            target_met=avg_time < 5.0,
            target_ms=5.0
        )
    
    def benchmark_full_handshake(self, iterations: int = 100) -> CryptoBenchmarkResult:
        """Benchmark full PQC handshake (keygen + encaps + encrypt)"""
        logger.info(f"  Benchmarking full PQC handshake...")
        
        if self.pqc_available:
            def handshake_op():
                # Create new crypto instance (simulates new session)
                crypto = self.pqc_crypto(use_real_pqc=True)
                # Get public key
                pk = crypto.get_public_key()
                # Encrypt test data
                data = b"test_data_32_bytes_for_handshake!!"
                return crypto.encrypt(data)
            
            result = self._measure_operation(handshake_op, iterations)
            if result:
                result.operation = "full_handshake"
                result.target_met = result.avg_time_ms < 50.0  # Target: <50ms
                result.target_ms = 50.0
            return result
        
        return self._simulate_full_handshake(iterations)
    
    def _simulate_full_handshake(self, iterations: int) -> CryptoBenchmarkResult:
        """Simulate full handshake performance"""
        # Full handshake: keygen + encaps + AES ~2-5ms
        times = [3.0 + 1.5 * (hash(str(i)) % 100) / 100 for i in range(iterations)]
        sorted_times = sorted(times)
        avg_time = statistics.mean(times)
        
        return CryptoBenchmarkResult(
            operation="full_handshake_simulated",
            iterations=iterations,
            total_time_ms=sum(times),
            avg_time_ms=avg_time,
            min_time_ms=min(times),
            max_time_ms=max(times),
            p50_ms=sorted_times[int(len(sorted_times) * 0.50)],
            p95_ms=sorted_times[int(len(sorted_times) * 0.95)],
            p99_ms=sorted_times[int(len(sorted_times) * 0.99)],
            ops_per_sec=1000 / avg_time if avg_time > 0 else 0,
            target_met=avg_time < 50.0,
            target_ms=50.0
        )
    
    def benchmark_batch_encryption(self, batch_sizes: List[int] = [10, 50, 100, 500]) -> Dict[str, Any]:
        """Benchmark batch encryption operations"""
        logger.info(f"  Benchmarking batch encryption...")
        
        results = {}
        
        for batch_size in batch_sizes:
            if self.pqc_available:
                crypto = self.pqc_crypto(use_real_pqc=False)
                data_batch = [os.urandom(1024) for _ in range(batch_size)]
                
                start = time.perf_counter()
                for data in data_batch:
                    crypto.encrypt(data)
                elapsed = (time.perf_counter() - start) * 1000
                
                results[f"batch_{batch_size}"] = {
                    "batch_size": batch_size,
                    "total_time_ms": elapsed,
                    "avg_per_item_ms": elapsed / batch_size,
                    "throughput_items_per_sec": batch_size / (elapsed / 1000)
                }
            else:
                # Simulate
                time_per_item = 0.5  # 0.5ms per KB
                total_time = time_per_item * batch_size
                results[f"batch_{batch_size}"] = {
                    "batch_size": batch_size,
                    "total_time_ms": total_time,
                    "avg_per_item_ms": time_per_item,
                    "throughput_items_per_sec": 1000 / time_per_item,
                    "simulated": True
                }
        
        return results
    
    def run_all_benchmarks(self) -> Dict[str, Any]:
        """Run all PQC benchmarks"""
        logger.info("\n" + "=" * 70)
        logger.info("PQC ENCRYPTION PERFORMANCE BENCHMARK")
        logger.info("=" * 70)
        
        results = {
            "timestamp": datetime.now().isoformat(),
            "pqc_available": self.pqc_available,
            "benchmarks": {}
        }
        
        # AES-GCM benchmarks
        logger.info("\n📊 AES-GCM Encryption Benchmarks")
        for size in [64, 256, 1024, 4096, 16384]:
            result = self.benchmark_aes_gcm_encryption(data_size_bytes=size, iterations=500)
            if result:
                results["benchmarks"][result.operation] = self._result_to_dict(result)
        
        # Kyber benchmarks
        logger.info("\n📊 Kyber KEM Benchmarks")
        for bench_name, bench_func, iterations in [
            ("keygen", self.benchmark_kyber_keygen, 100),
            ("encaps", self.benchmark_kyber_encaps, 100),
            ("handshake", self.benchmark_full_handshake, 100),
        ]:
            result = bench_func(iterations)
            if result:
                results["benchmarks"][result.operation] = self._result_to_dict(result)
        
        # Batch benchmarks
        logger.info("\n📊 Batch Processing Benchmarks")
        results["batch"] = self.benchmark_batch_encryption()
        
        return results
    
    def _result_to_dict(self, result: CryptoBenchmarkResult) -> Dict:
        """Convert result to dictionary"""
        return {
            "operation": result.operation,
            "iterations": result.iterations,
            "total_time_ms": result.total_time_ms,
            "avg_time_ms": result.avg_time_ms,
            "min_time_ms": result.min_time_ms,
            "max_time_ms": result.max_time_ms,
            "p50_ms": result.p50_ms,
            "p95_ms": result.p95_ms,
            "p99_ms": result.p99_ms,
            "ops_per_sec": result.ops_per_sec,
            "target_met": result.target_met,
            "target_ms": result.target_ms
        }
    
    def generate_report(self) -> str:
        """Generate human-readable report"""
        results = self.run_all_benchmarks()
        
        report = []
        report.append("=" * 70)
        report.append("PQC ENCRYPTION PERFORMANCE REPORT")
        report.append("=" * 70)
        report.append(f"\nPQC Module Available: {'✅ Yes' if results['pqc_available'] else '⚠️ No (simulated)'}")
        
        report.append("\n" + "-" * 70)
        report.append("OPERATION PERFORMANCE")
        report.append("-" * 70)
        
        for name, data in results["benchmarks"].items():
            status = "✅ PASS" if data["target_met"] else "❌ FAIL"
            report.append(f"\n{name}:")
            report.append(f"  Avg: {data['avg_time_ms']:.3f} ms")
            report.append(f"  P95: {data['p95_ms']:.3f} ms")
            report.append(f"  P99: {data['p99_ms']:.3f} ms")
            report.append(f"  Throughput: {data['ops_per_sec']:.0f} ops/sec")
            report.append(f"  Target (<{data['target_ms']}ms): {status}")
        
        report.append("\n" + "-" * 70)
        report.append("BATCH PROCESSING")
        report.append("-" * 70)
        
        for name, data in results["batch"].items():
            report.append(f"\n{name}:")
            report.append(f"  Total time: {data['total_time_ms']:.2f} ms")
            report.append(f"  Avg per item: {data['avg_per_item_ms']:.3f} ms")
            report.append(f"  Throughput: {data['throughput_items_per_sec']:.0f} items/sec")
        
        report.append("\n" + "=" * 70)
        
        return "\n".join(report)


def main():
    """Main entry point"""
    benchmark = PQCEncryptionBenchmark()
    report = benchmark.generate_report()
    print(report)
    
    # Save results
    results = benchmark.run_all_benchmarks()
    output_file = "benchmarks/results/pqc_benchmark_results.json"
    os.makedirs("benchmarks/results", exist_ok=True)
    with open(output_file, "w") as f:
        json.dump(results, f, indent=2)
    
    print(f"\n📊 Results saved to: {output_file}")


if __name__ == "__main__":
    main()
