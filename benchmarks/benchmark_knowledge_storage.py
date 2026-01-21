"""
Knowledge Storage Performance Benchmarks
=========================================

Benchmarks for Knowledge Storage operations:
- Store incidents
- Search performance (<50ms target)
- Vector index operations
"""
import time
import statistics
import asyncio
import tempfile
from pathlib import Path
from typing import Dict, List

try:
    from src.storage.knowledge_storage_v2 import KnowledgeStorageV2
    from src.storage.vector_index import VectorIndex
    STORAGE_AVAILABLE = True
except ImportError:
    STORAGE_AVAILABLE = False
    print("⚠️ Storage modules not available.")


async def benchmark_store_incidents(storage, num_incidents: int = 100) -> Dict:
    """
    Benchmark storing incidents.
    
    Args:
        storage: KnowledgeStorageV2 instance
        num_incidents: Number of incidents to store
        
    Returns:
        Performance statistics
    """
    if not STORAGE_AVAILABLE:
        return {'error': 'Storage not available'}
    
    times = []
    
    for i in range(num_incidents):
        incident = {
            'id': f'benchmark-incident-{i}',
            'timestamp': time.time() + i,
            'anomaly_type': 'MEMORY_PRESSURE',
            'metrics': {'memory_percent': 90.0 + (i % 10)},
            'root_cause': f'Memory issue {i}',
            'recovery_plan': f'Action {i}',
            'execution_result': {'success': True, 'duration': 2.0 + (i % 5)}
        }
        
        start = time.perf_counter()
        try:
            await storage.store_incident(incident, "node-1")
            elapsed = (time.perf_counter() - start) * 1000
            times.append(elapsed)
        except Exception as e:
            print(f"⚠️ Store failed: {e}")
            continue
    
    if not times:
        return {'error': 'No successful stores'}
    
    return {
        'iterations': len(times),
        'avg_ms': statistics.mean(times),
        'min_ms': min(times),
        'max_ms': max(times),
        'median_ms': statistics.median(times),
        'p95_ms': sorted(times)[int(len(times) * 0.95)]
    }


async def benchmark_search(storage, num_searches: int = 50) -> Dict:
    """
    Benchmark search performance.
    
    Args:
        storage: KnowledgeStorageV2 instance
        num_searches: Number of searches
        
    Returns:
        Performance statistics
    """
    if not STORAGE_AVAILABLE:
        return {'error': 'Storage not available'}
    
    times = []
    queries = [
        "memory pressure recovery",
        "CPU usage high",
        "network latency issue",
        "successful recovery pattern",
        "failed recovery attempt"
    ]
    
    for i in range(num_searches):
        query = queries[i % len(queries)]
        
        start = time.perf_counter()
        try:
            results = await storage.search_incidents(query, k=10, threshold=0.7)
            elapsed = (time.perf_counter() - start) * 1000
            times.append(elapsed)
        except Exception as e:
            print(f"⚠️ Search failed: {e}")
            continue
    
    if not times:
        return {'error': 'No successful searches'}
    
    return {
        'iterations': len(times),
        'avg_ms': statistics.mean(times),
        'min_ms': min(times),
        'max_ms': max(times),
        'median_ms': statistics.median(times),
        'p95_ms': sorted(times)[int(len(times) * 0.95)],
        'target_met': statistics.mean(times) < 50.0  # Target: <50ms
    }


async def benchmark_vector_index(index, num_docs: int = 100) -> Dict:
    """
    Benchmark vector index operations.
    
    Args:
        index: VectorIndex instance
        num_docs: Number of documents to add
        
    Returns:
        Performance statistics
    """
    if not STORAGE_AVAILABLE:
        return {'error': 'Storage not available'}
    
    add_times = []
    search_times = []
    
    # Add documents
    for i in range(num_docs):
        text = f"Memory pressure detected on node {i}. Recovery action taken."
        metadata = {
            'incident_id': f'incident-{i}',
            'anomaly_type': 'MEMORY_PRESSURE',
            'timestamp': time.time() + i
        }
        
        start = time.perf_counter()
        try:
            doc_id = index.add(text, metadata)
            elapsed = (time.perf_counter() - start) * 1000
            add_times.append(elapsed)
        except Exception as e:
            print(f"⚠️ Add failed: {e}")
            continue
    
    # Search
    for i in range(10):
        query = "memory pressure recovery"
        start = time.perf_counter()
        try:
            results = index.search(query, k=10, threshold=0.7)
            elapsed = (time.perf_counter() - start) * 1000
            search_times.append(elapsed)
        except Exception as e:
            print(f"⚠️ Search failed: {e}")
            continue
    
    return {
        'add': {
            'iterations': len(add_times),
            'avg_ms': statistics.mean(add_times) if add_times else 0,
            'total_ms': sum(add_times)
        },
        'search': {
            'iterations': len(search_times),
            'avg_ms': statistics.mean(search_times) if search_times else 0,
            'target_met': statistics.mean(search_times) < 50.0 if search_times else False
        }
    }


async def run_all_benchmarks():
    """Run all Knowledge Storage benchmarks."""
    if not STORAGE_AVAILABLE:
        print("❌ Storage modules not available. Skipping benchmarks.")
        return
    
    print("🚀 Running Knowledge Storage Benchmarks...\n")
    
    # Create temporary storage
    temp_dir = tempfile.mkdtemp()
    storage_path = Path(temp_dir)
    
    try:
        # Create storage
        storage = KnowledgeStorageV2(
            storage_path=storage_path,
            use_real_ipfs=False  # Use mock
        )
        
        # Benchmark 1: Store incidents
        print("📊 Benchmark 1: Store Incidents")
        print("-" * 50)
        store_stats = await benchmark_store_incidents(storage, num_incidents=100)
        if 'error' not in store_stats:
            print(f"  Iterations: {store_stats['iterations']}")
            print(f"  Average: {store_stats['avg_ms']:.3f} ms")
            print(f"  Min: {store_stats['min_ms']:.3f} ms")
            print(f"  Max: {store_stats['max_ms']:.3f} ms")
            print(f"  P95: {store_stats['p95_ms']:.3f} ms")
        else:
            print(f"  ❌ {store_stats['error']}")
        print()
        
        # Benchmark 2: Search
        print("📊 Benchmark 2: Search Performance")
        print("-" * 50)
        search_stats = await benchmark_search(storage, num_searches=50)
        if 'error' not in search_stats:
            print(f"  Iterations: {search_stats['iterations']}")
            print(f"  Average: {search_stats['avg_ms']:.3f} ms")
            print(f"  Min: {search_stats['min_ms']:.3f} ms")
            print(f"  Max: {search_stats['max_ms']:.3f} ms")
            print(f"  P95: {search_stats['p95_ms']:.3f} ms")
            print(f"  Target (<50ms): {'✅' if search_stats['target_met'] else '❌'}")
        else:
            print(f"  ❌ {search_stats['error']}")
        print()
        
        # Benchmark 3: Vector Index
        print("📊 Benchmark 3: Vector Index Operations")
        print("-" * 50)
        index = VectorIndex(index_path=storage_path / "vector_index")
        vector_stats = await benchmark_vector_index(index, num_docs=100)
        if 'error' not in vector_stats:
            print(f"  Add operations: {vector_stats['add']['iterations']}")
            print(f"  Avg add time: {vector_stats['add']['avg_ms']:.3f} ms")
            print(f"  Search operations: {vector_stats['search']['iterations']}")
            print(f"  Avg search time: {vector_stats['search']['avg_ms']:.3f} ms")
            print(f"  Target (<50ms): {'✅' if vector_stats['search']['target_met'] else '❌'}")
        else:
            print(f"  ❌ {vector_stats['error']}")
        print()
        
        # Overall stats
        print("📊 Overall Storage Stats")
        print("-" * 50)
        stats = storage.get_stats()
        print(f"  Total incidents: {stats.get('total_incidents', 0)}")
        print(f"  IPFS available: {stats.get('ipfs_available', False)}")
        print()
        
    finally:
        # Cleanup
        import shutil
        shutil.rmtree(temp_dir)


if __name__ == "__main__":
    asyncio.run(run_all_benchmarks())

