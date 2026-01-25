"""
PQC Performance Benchmarks
===========================

Benchmarks for Post-Quantum Cryptography operations:
- Handshake performance (<0.5ms target)
- Key generation
- Batch processing
- Cache hit rates
"""
import time
import statistics
from typing import List, Dict
import asyncio

try:
    from src.security.pqc_performance import (
        PQCPerformanceOptimizer,
        OptimizedPQMeshSecurity
    )
    from src.security.pqc_hybrid import HybridPQEncryption
    PQC_AVAILABLE = True
except ImportError:
    PQC_AVAILABLE = False
    print("⚠️ PQC modules not available. Install dependencies.")


def benchmark_handshake(optimizer, iterations: int = 100) -> Dict:
    """
    Benchmark handshake performance.
    
    Args:
        optimizer: PQCPerformanceOptimizer instance
        iterations: Number of iterations
        
    Returns:
        Performance statistics
    """
    if not PQC_AVAILABLE:
        return {'error': 'PQC not available'}
    
    times = []
    
    # Mock peer
    peer_id = "benchmark-peer"
    peer_public_key = b'benchmark_public_key_32_bytes_here'
    
    for i in range(iterations):
        start = time.perf_counter()
        try:
            shared_secret, metrics = optimizer.optimized_handshake(peer_id, peer_public_key)
            elapsed = (time.perf_counter() - start) * 1000  # Convert to ms
            times.append(elapsed)
        except Exception as e:
            print(f"⚠️ Handshake failed: {e}")
            continue
    
    if not times:
        return {'error': 'No successful handshakes'}
    
    return {
        'iterations': len(times),
        'avg_ms': statistics.mean(times),
        'min_ms': min(times),
        'max_ms': max(times),
        'median_ms': statistics.median(times),
        'p95_ms': sorted(times)[int(len(times) * 0.95)],
        'p99_ms': sorted(times)[int(len(times) * 0.99)],
        'target_met': statistics.mean(times) < 0.5  # Target: <0.5ms
    }


def benchmark_batch_handshakes(optimizer, batch_size: int = 10) -> Dict:
    """
    Benchmark batch handshakes.
    
    Args:
        optimizer: PQCPerformanceOptimizer instance
        batch_size: Number of peers in batch
        
    Returns:
        Performance statistics
    """
    if not PQC_AVAILABLE:
        return {'error': 'PQC not available'}
    
    # Create batch of peers
    peers = [
        (f"peer-{i}", b'peer_public_key_32_bytes_here')
        for i in range(batch_size)
    ]
    
    start = time.perf_counter()
    try:
        results = optimizer.batch_handshakes(peers)
        total_time = (time.perf_counter() - start) * 1000
        avg_time = total_time / batch_size if batch_size > 0 else 0
        
        return {
            'batch_size': batch_size,
            'total_time_ms': total_time,
            'avg_per_peer_ms': avg_time,
            'throughput_peers_per_sec': (batch_size / total_time * 1000) if total_time > 0 else 0
        }
    except Exception as e:
        return {'error': str(e)}


def benchmark_cache_performance(optimizer, iterations: int = 100) -> Dict:
    """
    Benchmark cache performance.
    
    Args:
        optimizer: PQCPerformanceOptimizer instance
        iterations: Number of iterations
        
    Returns:
        Cache statistics
    """
    if not PQC_AVAILABLE:
        return {'error': 'PQC not available'}
    
    if not optimizer.cache:
        return {'error': 'Cache not enabled'}
    
    peer_id = "cache-test-peer"
    peer_public_key = b'cache_test_public_key_32_bytes'
    
    # First handshake (cache miss)
    start = time.perf_counter()
    optimizer.optimized_handshake(peer_id, peer_public_key)
    first_time = (time.perf_counter() - start) * 1000
    
    # Subsequent handshakes (cache hits)
    cache_times = []
    for i in range(iterations - 1):
        start = time.perf_counter()
        optimizer.optimized_handshake(peer_id, peer_public_key)
        elapsed = (time.perf_counter() - start) * 1000
        cache_times.append(elapsed)
    
    if not cache_times:
        return {'error': 'No cache hits'}
    
    return {
        'first_handshake_ms': first_time,
        'avg_cache_hit_ms': statistics.mean(cache_times),
        'cache_speedup': first_time / statistics.mean(cache_times) if cache_times else 0,
        'iterations': iterations
    }


def run_all_benchmarks():
    """Run all PQC benchmarks."""
    if not PQC_AVAILABLE:
        print("❌ PQC modules not available. Skipping benchmarks.")
        return
    
    print("🚀 Running PQC Performance Benchmarks...\n")
    
    # Create optimizer
    try:
        optimizer = PQCPerformanceOptimizer(enable_cache=True)
    except Exception as e:
        print(f"❌ Failed to create optimizer: {e}")
        return
    
    # Benchmark 1: Handshake performance
    print("📊 Benchmark 1: Handshake Performance")
    print("-" * 50)
    handshake_stats = benchmark_handshake(optimizer, iterations=100)
    if 'error' not in handshake_stats:
        print(f"  Iterations: {handshake_stats['iterations']}")
        print(f"  Average: {handshake_stats['avg_ms']:.3f} ms")
        print(f"  Min: {handshake_stats['min_ms']:.3f} ms")
        print(f"  Max: {handshake_stats['max_ms']:.3f} ms")
        print(f"  P95: {handshake_stats['p95_ms']:.3f} ms")
        print(f"  Target (<0.5ms): {'✅' if handshake_stats['target_met'] else '❌'}")
    else:
        print(f"  ❌ {handshake_stats['error']}")
    print()
    
    # Benchmark 2: Batch processing
    print("📊 Benchmark 2: Batch Handshakes")
    print("-" * 50)
    batch_stats = benchmark_batch_handshakes(optimizer, batch_size=10)
    if 'error' not in batch_stats:
        print(f"  Batch size: {batch_stats['batch_size']}")
        print(f"  Total time: {batch_stats['total_time_ms']:.3f} ms")
        print(f"  Avg per peer: {batch_stats['avg_per_peer_ms']:.3f} ms")
        print(f"  Throughput: {batch_stats['throughput_peers_per_sec']:.1f} peers/sec")
    else:
        print(f"  ❌ {batch_stats['error']}")
    print()
    
    # Benchmark 3: Cache performance
    print("📊 Benchmark 3: Cache Performance")
    print("-" * 50)
    cache_stats = benchmark_cache_performance(optimizer, iterations=100)
    if 'error' not in cache_stats:
        print(f"  First handshake: {cache_stats['first_handshake_ms']:.3f} ms")
        print(f"  Avg cache hit: {cache_stats['avg_cache_hit_ms']:.3f} ms")
        print(f"  Speedup: {cache_stats['cache_speedup']:.2f}x")
    else:
        print(f"  ⚠️ {cache_stats['error']}")
    print()
    
    # Overall stats
    print("📊 Overall Performance Stats")
    print("-" * 50)
    overall_stats = optimizer.get_performance_stats()
    print(f"  Total handshakes: {overall_stats['total_handshakes']}")
    print(f"  Avg handshake: {overall_stats['avg_handshake_time_ms']:.3f} ms")
    print(f"  P50: {overall_stats['p50_handshake_time_ms']:.3f} ms")
    print(f"  P95: {overall_stats['p95_handshake_time_ms']:.3f} ms")
    print(f"  P99: {overall_stats['p99_handshake_time_ms']:.3f} ms")
    print()


if __name__ == "__main__":
    run_all_benchmarks()

