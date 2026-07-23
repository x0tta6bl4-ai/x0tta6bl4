"""
Comprehensive Performance Benchmarks for x0tta6bl4
==================================================

Benchmarks for:
1. Post-Quantum Cryptography (PQC) operations
2. Mesh Network operations
3. Self-healing (MAPE-K) integration

Establishes baseline metrics for production monitoring and regression detection.
"""

import sys
import json
import time
import statistics
import asyncio
from datetime import datetime, timezone
from typing import Dict, List, Tuple, Any
from pathlib import Path

PROJECT_ROOT = Path(__file__).resolve().parent.parent
if str(PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(PROJECT_ROOT))

try:
    from src.security.post_quantum_liboqs import PQMeshSecurityLibOQS
    PQC_AVAILABLE = True
except ImportError:
    try:
        import os
        from src.network.firstparty_vpn.mlkem import mlkem_keygen, mlkem_encapsulate, mlkem_decapsulate
        from src.network.firstparty_vpn.mldsa import mldsa_derive_reference_keypair, mldsa_reference_sign, mldsa_reference_verify

        class FirstPartyPQCWrapper:
            def __init__(self, node_id: str = "benchmark-pqc"):
                self._os = os
                self._mlkem_keygen = mlkem_keygen
                self._mlkem_encapsulate = mlkem_encapsulate
                self._mlkem_decapsulate = mlkem_decapsulate
                self._mldsa_derive = mldsa_derive_reference_keypair
                self._mldsa_sign = mldsa_reference_sign
                self._mldsa_verify = mldsa_reference_verify

            def generate_kem_keypair(self):
                return self._mlkem_keygen("ML-KEM-768")

            def kem_encapsulate(self, kp):
                return self._mlkem_encapsulate("ML-KEM-768", getattr(kp, 'encapsulation_key', kp))

            def generate_dsa_keypair(self):
                seed = self._os.urandom(32)
                return self._mldsa_derive(seed, "ML-DSA-65")

            def sign(self, message: bytes):
                seed = self._os.urandom(32)
                kp = self._mldsa_derive(seed, "ML-DSA-65")
                return self._mldsa_sign("ML-DSA-65", kp.signing_key, message)

            def verify(self, message: bytes, signature: bytes):
                seed = self._os.urandom(32)
                kp = self._mldsa_derive(seed, "ML-DSA-65")
                return self._mldsa_verify("ML-DSA-65", kp.verification_key, message, signature)

        PQMeshSecurityLibOQS = FirstPartyPQCWrapper
        PQC_AVAILABLE = True
    except ImportError:
        PQC_AVAILABLE = False

try:
    from src.network.batman.topology import MeshTopology, MeshNode, MeshLink, LinkQuality, NodeState
    MESH_AVAILABLE = True
except ImportError:
    MESH_AVAILABLE = False

try:
    from src.self_healing.mape_k import MAPEK
    MAPEK_AVAILABLE = True
except ImportError:
    MAPEK_AVAILABLE = False


class PQCBenchmark:
    """Comprehensive PQC performance benchmarks."""

    def __init__(self):
        self.results: Dict[str, Any] = {}
        if PQC_AVAILABLE:
            self.pqc = PQMeshSecurityLibOQS(node_id="benchmark-pqc")
        else:
            self.pqc = None

    def benchmark_kem_keygen(self, iterations: int = 100) -> Dict[str, float]:
        """Benchmark KEM keypair generation (ML-KEM-768)."""
        if not PQC_AVAILABLE or self.pqc is None:
            return {'error': 'PQC not available', 'status': 'skipped'}

        times = []
        for _ in range(iterations):
            start = time.perf_counter()
            pk = self.pqc.generate_kem_keypair()
            elapsed = (time.perf_counter() - start) * 1000
            if pk is not None:
                times.append(elapsed)

        if not times:
            return {'error': 'No successful key generations', 'status': 'failed'}

        return {
            'status': 'passed',
            'iterations': len(times),
            'mean_ms': statistics.mean(times),
            'median_ms': statistics.median(times),
            'min_ms': min(times),
            'max_ms': max(times),
            'p95_ms': sorted(times)[int(len(times) * 0.95)] if len(times) > 20 else max(times),
            'p99_ms': sorted(times)[int(len(times) * 0.99)] if len(times) > 100 else max(times),
            'target_ms': 10.0,
            'target_met': statistics.mean(times) < 10.0
        }

    def benchmark_kem_encapsulate(self, iterations: int = 100) -> Dict[str, float]:
        """Benchmark KEM encapsulation (encryption)."""
        if not PQC_AVAILABLE or self.pqc is None:
            return {'error': 'PQC not available', 'status': 'skipped'}

        pk = self.pqc.generate_kem_keypair()
        if pk is None:
            return {'error': 'Failed to generate keypair', 'status': 'failed'}

        times = []
        for _ in range(iterations):
            start = time.perf_counter()
            result = self.pqc.kem_encapsulate(pk)
            elapsed = (time.perf_counter() - start) * 1000
            if result is not None:
                times.append(elapsed)

        if not times:
            return {'error': 'No successful encapsulations', 'status': 'failed'}

        return {
            'status': 'passed',
            'iterations': len(times),
            'mean_ms': statistics.mean(times),
            'median_ms': statistics.median(times),
            'min_ms': min(times),
            'max_ms': max(times),
            'p95_ms': sorted(times)[int(len(times) * 0.95)] if len(times) > 20 else max(times),
            'target_ms': 2.0,
            'target_met': statistics.mean(times) < 2.0
        }

    def benchmark_dsa_keygen(self, iterations: int = 50) -> Dict[str, float]:
        """Benchmark ML-DSA-65 keypair generation (signatures)."""
        if not PQC_AVAILABLE or self.pqc is None:
            return {'error': 'PQC not available', 'status': 'skipped'}

        times = []
        for i in range(iterations):
            start = time.perf_counter()
            if hasattr(self.pqc, 'generate_dsa_keypair'):
                pk = self.pqc.generate_dsa_keypair()
            else:
                pk = PQMeshSecurityLibOQS(node_id=f"benchmark-dsa-{i}")
            elapsed = (time.perf_counter() - start) * 1000
            if pk is not None:
                times.append(elapsed)

        if not times:
            return {'error': 'No successful DSA key generations', 'status': 'failed'}

        return {
            'status': 'passed',
            'iterations': len(times),
            'mean_ms': statistics.mean(times),
            'median_ms': statistics.median(times),
            'min_ms': min(times),
            'max_ms': max(times),
            'p95_ms': sorted(times)[int(len(times) * 0.95)] if len(times) > 20 else max(times),
            'target_ms': 5.0,
            'target_met': statistics.mean(times) < 5.0
        }

    def benchmark_signature_generation(self, message_size: int = 256, iterations: int = 100) -> Dict[str, float]:
        """Benchmark ML-DSA-65 signature generation."""
        if not PQC_AVAILABLE or self.pqc is None:
            return {'error': 'PQC not available', 'status': 'skipped'}

        message = b'x' * message_size
        times = []

        for _ in range(iterations):
            start = time.perf_counter()
            sig = self.pqc.sign(message)
            elapsed = (time.perf_counter() - start) * 1000
            if sig is not None:
                times.append(elapsed)

        if not times:
            return {'error': 'No successful signatures', 'status': 'failed'}

        throughput = 1000 / statistics.mean(times) if statistics.mean(times) > 0 else 0

        return {
            'status': 'passed',
            'iterations': len(times),
            'message_size': message_size,
            'mean_ms': statistics.mean(times),
            'median_ms': statistics.median(times),
            'min_ms': min(times),
            'max_ms': max(times),
            'throughput_per_sec': throughput,
            'target_per_sec': 100,
            'target_met': throughput >= 100
        }

    def benchmark_signature_verification(self, message_size: int = 256, iterations: int = 100) -> Dict[str, float]:
        """Benchmark ML-DSA-65 signature verification."""
        if not PQC_AVAILABLE or self.pqc is None:
            return {'error': 'PQC not available', 'status': 'skipped'}

        message = b'x' * message_size
        signature = self.pqc.sign(message)
        if signature is None:
            return {'error': 'Failed to create test signature', 'status': 'failed'}

        times = []
        for _ in range(iterations):
            start = time.perf_counter()
            verified = self.pqc.verify(message, signature)
            elapsed = (time.perf_counter() - start) * 1000
            if verified:
                times.append(elapsed)

        if not times:
            return {'error': 'No successful verifications', 'status': 'failed'}

        throughput = 1000 / statistics.mean(times) if statistics.mean(times) > 0 else 0

        return {
            'status': 'passed',
            'iterations': len(times),
            'message_size': message_size,
            'mean_ms': statistics.mean(times),
            'median_ms': statistics.median(times),
            'min_ms': min(times),
            'max_ms': max(times),
            'throughput_per_sec': throughput,
            'target_per_sec': 150,
            'target_met': throughput >= 150
        }

    def benchmark_batch_operations(self, batch_size: int = 10) -> Dict[str, Any]:
        """Benchmark batch PQC operations."""
        if not PQC_AVAILABLE or self.pqc is None:
            return {'error': 'PQC not available', 'status': 'skipped'}

        messages = [f"message-{i}".encode() for i in range(batch_size)]

        start = time.perf_counter()
        signatures = [self.pqc.sign(msg) for msg in messages]
        sig_time = (time.perf_counter() - start) * 1000

        start = time.perf_counter()
        verifications = [self.pqc.verify(msg, sig) for msg, sig in zip(messages, signatures)]
        verify_time = (time.perf_counter() - start) * 1000

        return {
            'status': 'passed',
            'batch_size': batch_size,
            'batch_sign_time_ms': sig_time,
            'batch_verify_time_ms': verify_time,
            'avg_sign_per_msg_ms': sig_time / batch_size,
            'avg_verify_per_msg_ms': verify_time / batch_size,
            'total_time_ms': sig_time + verify_time
        }

    def run_all(self) -> Dict[str, Any]:
        """Run all PQC benchmarks."""
        print("\n🔐 PQC Performance Benchmarks")
        print("=" * 60)

        results = {
            'timestamp': datetime.now(timezone.utc).isoformat(),
            'component': 'pqc',
            'availability': 'available' if PQC_AVAILABLE else 'unavailable',
            'benchmarks': {}
        }

        benchmarks = [
            ('kem_keygen', self.benchmark_kem_keygen, {}),
            ('kem_encapsulate', self.benchmark_kem_encapsulate, {}),
            ('dsa_keygen', self.benchmark_dsa_keygen, {}),
            ('signature_generation', self.benchmark_signature_generation, {'message_size': 256}),
            ('signature_verification', self.benchmark_signature_verification, {'message_size': 256}),
            ('batch_operations', self.benchmark_batch_operations, {'batch_size': 10})
        ]

        for name, func, kwargs in benchmarks:
            print(f"\n📊 {name}")
            print("-" * 40)
            try:
                result = func(**kwargs)
                results['benchmarks'][name] = result
                if result.get('status') == 'passed':
                    mean_val = result.get('mean_ms', result.get('total_time_ms'))
                    if isinstance(mean_val, (int, float)):
                        print(f"  ✅ Mean/Total: {mean_val:.2f}ms")
                    if 'target_met' in result:
                        print(f"  Target: {'✅ MET' if result.get('target_met') else '❌ MISSED'}")
                else:
                    print(f"  ⚠️ Status: {result.get('status', 'unknown')}")
            except Exception as e:
                print(f"  ❌ Error: {e}")
                results['benchmarks'][name] = {'error': str(e), 'status': 'error'}

        return results


class MeshBenchmark:
    """Comprehensive mesh network performance benchmarks."""

    def __init__(self):
        self.results: Dict[str, Any] = {}
        if MESH_AVAILABLE:
            self.topology = MeshTopology(mesh_id="bench-mesh", local_node_id="bench-local")
        else:
            self.topology = None

    def benchmark_node_addition(self, num_nodes: int = 100) -> Dict[str, float]:
        """Benchmark adding nodes to topology."""
        if not MESH_AVAILABLE or self.topology is None:
            return {'error': 'Mesh not available', 'status': 'skipped'}

        times = []
        for i in range(num_nodes):
            node = MeshNode(
                node_id=f"node-{i}",
                mac_address=f"00:11:22:33:44:{i:02x}",
                ip_address=f"192.168.1.{i}",
                state=NodeState.ONLINE
            )

            start = time.perf_counter()
            self.topology.add_node(node)
            elapsed = (time.perf_counter() - start) * 1000
            times.append(elapsed)

        return {
            'status': 'passed',
            'nodes_added': num_nodes,
            'mean_ms': statistics.mean(times),
            'median_ms': statistics.median(times),
            'min_ms': min(times),
            'max_ms': max(times),
            'total_ms': sum(times),
            'throughput_nodes_per_sec': num_nodes / (sum(times) / 1000) if sum(times) > 0 else 0
        }

    def benchmark_link_quality_calculation(self, num_links: int = 100) -> Dict[str, float]:
        """Benchmark link quality score calculation."""
        if not MESH_AVAILABLE or self.topology is None:
            return {'error': 'Mesh not available', 'status': 'skipped'}

        links = [
            MeshLink(
                source=f"node-{i}",
                destination=f"node-{i+1}",
                quality=LinkQuality.GOOD,
                throughput_mbps=100.0,
                latency_ms=5.0 + (i % 5),
                packet_loss_percent=1.0 + (i % 3)
            )
            for i in range(num_links)
        ]

        times = []
        for link in links:
            start = time.perf_counter()
            score = link.quality_score()
            elapsed = (time.perf_counter() - start) * 1000
            times.append(elapsed)

        return {
            'status': 'passed',
            'links_calculated': num_links,
            'mean_us': statistics.mean(times) * 1000,
            'total_ms': sum(times),
            'throughput_links_per_sec': num_links / (sum(times) / 1000) if sum(times) > 0 else 0
        }

    def benchmark_shortest_path(self, nodes: int = 50, density: float = 0.3) -> Dict[str, float]:
        """Benchmark Dijkstra shortest path calculation."""
        if not MESH_AVAILABLE or self.topology is None:
            return {'error': 'Mesh not available', 'status': 'skipped'}

        for i in range(nodes):
            node = MeshNode(
                node_id=f"path-node-{i}",
                mac_address=f"00:22:33:44:55:{i:02x}",
                ip_address=f"10.0.0.{i}",
                state=NodeState.ONLINE
            )
            self.topology.add_node(node)

        import random
        random.seed(42)
        for i in range(nodes):
            for j in range(i + 1, nodes):
                if random.random() < density:
                    link = MeshLink(
                        source=f"path-node-{i}",
                        destination=f"path-node-{j}",
                        quality=LinkQuality.GOOD,
                        throughput_mbps=100.0,
                        latency_ms=random.uniform(1.0, 10.0)
                    )
                    self.topology.add_link(link)

        times = []
        source = "path-node-0"
        for dest_idx in range(1, min(10, nodes)):
            dest = f"path-node-{dest_idx}"
            start = time.perf_counter()
            path = self.topology.compute_shortest_path(source, dest)
            elapsed = (time.perf_counter() - start) * 1000
            if path:
                times.append(elapsed)

        if not times:
            return {'error': 'No valid paths found', 'status': 'failed'}

        return {
            'status': 'passed',
            'graph_nodes': nodes,
            'graph_density': density,
            'paths_calculated': len(times),
            'mean_ms': statistics.mean(times),
            'median_ms': statistics.median(times),
            'max_ms': max(times),
            'throughput_paths_per_sec': len(times) / (sum(times) / 1000) if sum(times) > 0 else 0
        }

    def run_all(self) -> Dict[str, Any]:
        """Run all mesh benchmarks."""
        print("\n🕸️  Mesh Network Performance Benchmarks")
        print("=" * 60)

        results = {
            'timestamp': datetime.now(timezone.utc).isoformat(),
            'component': 'mesh',
            'availability': 'available' if MESH_AVAILABLE else 'unavailable',
            'benchmarks': {}
        }

        benchmarks = [
            ('node_addition', self.benchmark_node_addition, {'num_nodes': 100}),
            ('link_quality_calculation', self.benchmark_link_quality_calculation, {'num_links': 100}),
            ('shortest_path', self.benchmark_shortest_path, {'nodes': 50, 'density': 0.3})
        ]

        for name, func, kwargs in benchmarks:
            print(f"\n📊 {name}")
            print("-" * 40)
            try:
                result = func(**kwargs)
                results['benchmarks'][name] = result
                if result.get('status') == 'passed':
                    print(f"  ✅ Mean: {result.get('mean_ms', result.get('mean_us', 'N/A')):.3f}ms")
                    print(f"  Throughput: {result.get('throughput_nodes_per_sec', result.get('throughput_links_per_sec', result.get('throughput_paths_per_sec', 'N/A'))):.2f} ops/sec")
                else:
                    print(f"  ⚠️ Status: {result.get('status', 'unknown')}")
            except Exception as e:
                print(f"  ❌ Error: {e}")
                results['benchmarks'][name] = {'error': str(e), 'status': 'error'}

        return results


def generate_baseline_report(pqc_results: Dict, mesh_results: Dict, output_file: str = None) -> Dict[str, Any]:
    """Generate comprehensive baseline performance report."""
    report = {
        'timestamp': datetime.now(timezone.utc).isoformat(),
        'version': '1.0',
        'baseline_type': 'comprehensive_performance',
        'results': {
            'pqc': pqc_results,
            'mesh': mesh_results
        },
        'summary': {}
    }

    pqc_tests_passed = sum(1 for b in pqc_results.get('benchmarks', {}).values() 
                          if b.get('status') == 'passed')
    mesh_tests_passed = sum(1 for b in mesh_results.get('benchmarks', {}).values() 
                           if b.get('status') == 'passed')

    report['summary'] = {
        'pqc': {
            'total_benchmarks': len(pqc_results.get('benchmarks', {})),
            'passed': pqc_tests_passed,
            'availability': pqc_results.get('availability')
        },
        'mesh': {
            'total_benchmarks': len(mesh_results.get('benchmarks', {})),
            'passed': mesh_tests_passed,
            'availability': mesh_results.get('availability')
        }
    }

    if output_file:
        out_path = Path(output_file)
        out_path.parent.mkdir(parents=True, exist_ok=True)
        with open(out_path, 'w') as f:
            json.dump(report, f, indent=2)
        print(f"\n✅ Baseline report saved to: {output_file}")

        # Also write canonical release benchmark file: results/pqc_benchmark_v3.5.0.json
        rel_path = out_path.parent / "pqc_benchmark_v3.5.0.json"
        with open(rel_path, 'w') as f:
            json.dump(report, f, indent=2)
        print(f"✅ Release benchmark artifact saved to: {rel_path}")

    return report


def main():
    """Run all benchmarks and generate baseline report."""
    print("\n" + "=" * 60)
    print("x0tta6bl4 Comprehensive Performance Benchmark Suite")
    print("=" * 60)

    pqc_bench = PQCBenchmark()
    pqc_results = pqc_bench.run_all()

    mesh_bench = MeshBenchmark()
    mesh_results = mesh_bench.run_all()

    output_dir = Path(__file__).parent / 'results'
    timestamp = datetime.now(timezone.utc).strftime('%Y%m%d_%H%M%S')
    output_file = output_dir / f'baseline_comprehensive_{timestamp}.json'

    report = generate_baseline_report(pqc_results, mesh_results, str(output_file))

    print("\n" + "=" * 60)
    print("📋 Benchmark Summary")
    print("=" * 60)
    print(f"\nPQC Benchmarks:")
    print(f"  ✅ Passed: {report['summary']['pqc']['passed']}/{report['summary']['pqc']['total_benchmarks']}")
    print(f"  Status: {report['summary']['pqc']['availability']}")

    print(f"\nMesh Benchmarks:")
    print(f"  ✅ Passed: {report['summary']['mesh']['passed']}/{report['summary']['mesh']['total_benchmarks']}")
    print(f"  Status: {report['summary']['mesh']['availability']}")

    print(f"\n📊 Baseline report: {output_file}")


if __name__ == "__main__":
    main()
