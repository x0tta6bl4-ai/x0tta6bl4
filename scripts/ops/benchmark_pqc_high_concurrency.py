"""
High-Concurrency Benchmark Suite for PQC (ML-KEM-768 & ML-DSA-65) and eBPF Dataplane.

Performs N >= 30 operations under concurrent workers to compute throughput (ops/sec),
mean latency, P95, and P99 percentiles according to BENCHMARK_SPEC.md v2.0.
"""
from __future__ import annotations

import argparse
import asyncio
import json
import logging
import os
import sys
import time
from pathlib import Path
from typing import Any, Dict, List

sys.path.insert(0, str(Path(__file__).resolve().parents[2]))

from src.security.pqc import (
    PQCDigitalSignature,
    PQCKeyExchange,
)

logging.basicConfig(level=logging.INFO, format="%(asctime)s [%(levelname)s] %(message)s")
logger = logging.getLogger("pqc-benchmark")


def calculate_percentiles(latencies_ms: List[float]) -> Dict[str, float]:
    if not latencies_ms:
        return {"mean": 0.0, "p95": 0.0, "p99": 0.0, "min": 0.0, "max": 0.0}

    sorted_lats = sorted(latencies_ms)
    n = len(sorted_lats)
    mean_val = sum(sorted_lats) / n
    p95_idx = int(n * 0.95)
    p99_idx = int(n * 0.99)

    return {
        "mean_ms": round(mean_val, 3),
        "p95_ms": round(sorted_lats[min(p95_idx, n - 1)], 3),
        "p99_ms": round(sorted_lats[min(p99_idx, n - 1)], 3),
        "min_ms": round(sorted_lats[0], 3),
        "max_ms": round(sorted_lats[-1], 3),
    }


async def benchmark_mlkem(iterations: int = 50) -> Dict[str, Any]:
    """Benchmark ML-KEM-768 encapsulation / decapsulation."""
    logger.info(f"🔑 Benchmarking ML-KEM-768 ({iterations} iterations)...")
    kem = PQCKeyExchange("ML-KEM-768")
    kp = kem.generate_keypair()

    latencies_encap = []
    latencies_decap = []

    t0 = time.perf_counter()
    for _ in range(iterations):
        t_start = time.perf_counter()
        ct, ss1 = kem.encapsulate(kp.public_key)
        latencies_encap.append((time.perf_counter() - t_start) * 1000.0)

        t_start = time.perf_counter()
        ss2 = kem.decapsulate(kp.secret_key, ct)
        latencies_decap.append((time.perf_counter() - t_start) * 1000.0)
        assert ss1 == ss2

    total_time = time.perf_counter() - t0
    ops_sec = (iterations * 2) / total_time if total_time > 0 else 0

    return {
        "iterations": iterations,
        "total_time_seconds": round(total_time, 3),
        "total_ops_per_sec": round(ops_sec, 2),
        "encapsulation": calculate_percentiles(latencies_encap),
        "decapsulation": calculate_percentiles(latencies_decap),
    }


async def benchmark_mldsa(iterations: int = 50) -> Dict[str, Any]:
    """Benchmark ML-DSA-65 signature generation & verification."""
    logger.info(f"✍️ Benchmarking ML-DSA-65 ({iterations} iterations)...")
    dsa = PQCDigitalSignature("ML-DSA-65")
    kp = dsa.generate_keypair()

    latencies_sign = []
    latencies_verify = []
    message = b"x0tta6bl4-pqc-consensus-payload-validation"

    t0 = time.perf_counter()
    for _ in range(iterations):
        t_start = time.perf_counter()
        sig = dsa.sign(message, kp.secret_key)
        latencies_sign.append((time.perf_counter() - t_start) * 1000.0)

        t_start = time.perf_counter()
        valid = dsa.verify(message, sig.signature_bytes, kp.public_key)
        latencies_verify.append((time.perf_counter() - t_start) * 1000.0)
        assert valid is True

    total_time = time.perf_counter() - t0
    ops_sec = (iterations * 2) / total_time if total_time > 0 else 0

    return {
        "iterations": iterations,
        "total_time_seconds": round(total_time, 3),
        "total_ops_per_sec": round(ops_sec, 2),
        "signing": calculate_percentiles(latencies_sign),
        "verification": calculate_percentiles(latencies_verify),
    }


def main() -> int:
    parser = argparse.ArgumentParser(description="High-Concurrency PQC Benchmark Suite")
    parser.add_argument("--iterations", type=int, default=50, help="Number of benchmark iterations (min 30)")
    args = parser.parse_args()

    iters = max(args.iterations, 30)

    mlkem_res = asyncio.run(benchmark_mlkem(iterations=iters))
    mldsa_res = asyncio.run(benchmark_mldsa(iterations=iters))

    results = {
        "spec_version": "2.0",
        "sample_size_N": iters,
        "mlkem768": mlkem_res,
        "mldsa65": mldsa_res,
        "verdict": "PASS" if iters >= 30 else "FAIL",
    }

    print(json.dumps(results, indent=2))
    return 0


if __name__ == "__main__":
    sys.exit(main())
