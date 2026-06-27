#!/usr/bin/env python3
"""
Example: PQC Performance Optimization
======================================

Demonstrates PQC performance features:
- Key caching
- Batch processing
- Performance metrics
- Hybrid mode
"""
import time

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


def main():
    """Example usage of PQC Performance Optimizer."""
    if not PQC_AVAILABLE:
        print("❌ PQC modules not available")
        return
    
    print("🚀 PQC Performance Optimization Example\n")
    
    try:
        # Create optimizer with caching
        print("📦 Creating PQC Performance Optimizer...")
        optimizer = PQCPerformanceOptimizer(
            kem_algorithm="ML-KEM-768",
            sig_algorithm="ML-DSA-65",
            enable_cache=True
        )
        print("  ✅ Optimizer created")
        print()
        
        # Benchmark handshakes
        print("⚡ Benchmarking handshakes...")
        peer_public_key = b'benchmark_peer_public_key_32_bytes'
        
        # First handshake (cache miss)
        print("  First handshake (cache miss):")
        start = time.perf_counter()
        shared_secret1, metrics1 = optimizer.optimized_handshake("peer-1", peer_public_key)
        elapsed1 = (time.perf_counter() - start) * 1000
        print(f"    Time: {elapsed1:.3f} ms")
        print(f"    Metrics: {metrics1.handshake_time_ms:.3f} ms")
        print()
        
        # Second handshake (cache hit)
        print("  Second handshake (cache hit):")
        start = time.perf_counter()
        shared_secret2, metrics2 = optimizer.optimized_handshake("peer-1", peer_public_key)
        elapsed2 = (time.perf_counter() - start) * 1000
        print(f"    Time: {elapsed2:.3f} ms")
        print(f"    Metrics: {metrics2.handshake_time_ms:.3f} ms")
        if elapsed1 > 0:
            speedup = elapsed1 / elapsed2
            print(f"    Speedup: {speedup:.2f}x")
        print()
        
        # Batch handshakes
        print("📦 Batch handshakes:")
        peers = [
            (f"peer-{i}", b'peer_public_key_32_bytes_here')
            for i in range(5)
        ]
        
        start = time.perf_counter()
        results = optimizer.batch_handshakes(peers)
        total_time = (time.perf_counter() - start) * 1000
        
        print(f"  Processed {len(peers)} peers in {total_time:.3f} ms")
        print(f"  Average: {total_time / len(peers):.3f} ms per peer")
        print()
        
        # Performance statistics
        print("📊 Performance Statistics:")
        stats = optimizer.get_performance_stats()
        print(f"  Total handshakes: {stats['total_handshakes']}")
        print(f"  Average: {stats['avg_handshake_time_ms']:.3f} ms")
        print(f"  Min: {stats['min_handshake_time_ms']:.3f} ms")
        print(f"  Max: {stats['max_handshake_time_ms']:.3f} ms")
        print(f"  P50: {stats['p50_handshake_time_ms']:.3f} ms")
        print(f"  P95: {stats['p95_handshake_time_ms']:.3f} ms")
        print(f"  P99: {stats['p99_handshake_time_ms']:.3f} ms")
        print()
        
        # Optimized Mesh Security
        print("🔐 Optimized PQ Mesh Security:")
        mesh_security = OptimizedPQMeshSecurity(
            node_id="node-1",
            enable_cache=True
        )
        
        # Get public keys
        public_keys = mesh_security.get_public_keys()
        print(f"  Node ID: {public_keys['node_id']}")
        print(f"  KEM Algorithm: {public_keys['kem_algorithm']}")
        print(f"  SIG Algorithm: {public_keys['sig_algorithm']}")
        print()
        
        # Performance stats
        mesh_stats = mesh_security.get_performance_stats()
        print("  Performance Stats:")
        print(f"    eBPF available: {mesh_stats.get('ebpf_available', False)}")
        print(f"    Cache enabled: {mesh_stats.get('cache_enabled', False)}")
        print(f"    Cache size: {mesh_stats.get('cache_size', 0)}")
        print()
        
        print("✅ Example completed successfully!")
        
    except Exception as e:
        print(f"❌ Error: {e}")
        import traceback
        traceback.print_exc()


if __name__ == "__main__":
    main()

