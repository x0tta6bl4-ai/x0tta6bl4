"""
RAG Pipeline Optimization Benchmarks

Comprehensive benchmarking for HNSW vector search, semantic caching,
and batch retrieval optimization.
"""

import asyncio
import time
import json
import logging
from typing import List, Dict, Any
from datetime import datetime
from pathlib import Path

logger = logging.getLogger(__name__)


class RAGBenchmark:
    """Benchmark suite for RAG optimizations"""
    
    def __init__(self, output_dir: str = "benchmarks/results"):
        """Initialize benchmark"""
        self.output_dir = Path(output_dir)
        self.output_dir.mkdir(exist_ok=True)
        self.results = {}
    
    async def benchmark_hnsw_indexing(self, document_counts: List[int]) -> Dict[str, Any]:
        """
        Benchmark HNSW index creation and insertion.
        
        Args:
            document_counts: List of document counts to test
            
        Returns:
            Benchmark results
        """
        results = {}
        
        try:
            from src.storage.vector_index import VectorIndex
        except ImportError:
            logger.warning("VectorIndex not available")
            return {}
        
        for doc_count in document_counts:
            print(f"\n📊 Benchmarking HNSW indexing with {doc_count} documents...")
            
            start_time = time.time()
            index = VectorIndex(max_elements=doc_count + 1000)
            init_time = time.time() - start_time
            
            start_time = time.time()
            for i in range(doc_count):
                metadata = {
                    "doc_id": f"doc_{i}",
                    "content": f"Document {i} with content for vector search"
                }
                index.add(f"Document {i}", metadata)
            
            insertion_time = time.time() - start_time
            insertion_rate = doc_count / insertion_time
            
            start_time = time.time()
            search_results = index.search("test query", k=10)
            search_time = (time.time() - start_time) * 1000
            
            results[f"{doc_count}_docs"] = {
                "initialization_time_ms": init_time * 1000,
                "insertion_time_ms": insertion_time * 1000,
                "insertion_rate_docs_per_sec": insertion_rate,
                "search_time_ms": search_time,
                "docs_per_sec_at_scale": doc_count / insertion_time if insertion_time > 0 else 0
            }
            
            print(f"  ✅ Init: {init_time*1000:.2f}ms")
            print(f"  ✅ Insertion: {insertion_time*1000:.2f}ms ({insertion_rate:.0f} docs/sec)")
            print(f"  ✅ Search: {search_time:.2f}ms")
        
        self.results['hnsw_indexing'] = results
        return results
    
    async def benchmark_semantic_cache(self, query_patterns: List[Dict[str, Any]]) -> Dict[str, Any]:
        """
        Benchmark semantic cache performance.
        
        Args:
            query_patterns: List of query pattern configs
            
        Returns:
            Benchmark results
        """
        results = {}
        
        try:
            from src.rag.semantic_cache import SemanticCache
        except ImportError:
            logger.warning("SemanticCache not available")
            return {}
        
        for pattern in query_patterns:
            num_queries = pattern.get('num_queries', 100)
            similarity = pattern.get('similarity', 0.95)
            name = pattern.get('name', f'{num_queries}_queries')
            
            print(f"\n🧠 Benchmarking semantic cache ({name})...")
            
            cache = SemanticCache(
                max_cache_size=1000,
                similarity_threshold=similarity
            )
            
            base_queries = [
                "neural network anomaly detection",
                "API response time degradation",
                "memory usage patterns",
                "network latency spikes",
                "database query performance"
            ]
            
            queries = []
            for i in range(num_queries):
                base = base_queries[i % len(base_queries)]
                variation = f" with {i % 10}" if i % 2 == 0 else ""
                queries.append(base + variation)
            
            put_time = time.time()
            for i, query in enumerate(queries):
                results_list = [{"id": f"result_{j}", "score": 0.9 - j*0.1} for j in range(5)]
                scores = [0.9 - j*0.1 for j in range(5)]
                cache.put(query, results_list, scores)
            put_time = time.time() - put_time
            
            get_time = time.time()
            hits = 0
            for query in queries:
                result = cache.get(query)
                if result:
                    hits += 1
            get_time = time.time() - get_time
            
            cache_stats = cache.get_stats()
            
            results[name] = {
                'put_time_ms': put_time * 1000,
                'get_time_ms': get_time * 1000,
                'puts_per_sec': num_queries / put_time if put_time > 0 else 0,
                'gets_per_sec': num_queries / get_time if get_time > 0 else 0,
                'hits': cache_stats['hits'],
                'misses': cache_stats['misses'],
                'hit_rate': cache_stats['hit_rate'],
                'cache_size': cache_stats['cache_size']
            }
            
            print(f"  ✅ Put: {put_time*1000:.2f}ms ({num_queries/put_time:.0f} ops/sec)")
            print(f"  ✅ Get: {get_time*1000:.2f}ms ({num_queries/get_time:.0f} ops/sec)")
            print(f"  ✅ Hit rate: {cache_stats['hit_rate']:.1f}%")
        
        self.results['semantic_cache'] = results
        return results
    
    async def benchmark_batch_retrieval(self, batch_configs: List[Dict[str, Any]]) -> Dict[str, Any]:
        """
        Benchmark batch retrieval performance.
        
        Args:
            batch_configs: List of batch configuration dicts
            
        Returns:
            Benchmark results
        """
        results = {}
        
        try:
            from src.rag.batch_retrieval import BatchRetriever, BatchQuery
        except ImportError:
            logger.warning("BatchRetriever not available")
            return {}
        
        class MockPipeline:
            """Mock RAG pipeline for benchmarking"""
            async def retrieve(self, query, k=10, use_cache=False):
                await asyncio.sleep(0.01)
                return {
                    'results': [{'id': f'result_{i}'} for i in range(k)],
                    'scores': [0.9 - i*0.1 for i in range(k)]
                }
        
        pipeline = MockPipeline()
        
        for config in batch_configs:
            batch_size = config.get('batch_size', 10)
            num_workers = config.get('workers', 4)
            name = config.get('name', f'batch_{batch_size}_workers_{num_workers}')
            
            print(f"\n⚡ Benchmarking batch retrieval ({name})...")
            
            retriever = BatchRetriever(pipeline, max_workers=num_workers, batch_size=batch_size)
            
            queries = [
                BatchQuery(id=f"q_{i}", query=f"Query {i}", k=10)
                for i in range(batch_size)
            ]
            
            start_time = time.time()
            batch_results, stats = await retriever.retrieve_batch(queries, use_cache=False)
            retrieval_time = time.time() - start_time
            
            results[name] = {
                'total_queries': stats.total_queries,
                'successful_queries': stats.successful_queries,
                'failed_queries': stats.failed_queries,
                'total_time_ms': stats.total_processing_time_ms,
                'avg_latency_per_query_ms': stats.average_latency_per_query_ms,
                'throughput_qps': stats.throughput_qps,
                'parallelism_factor': stats.parallelism_factor,
                'speedup': (batch_size * 0.01) / (stats.total_processing_time_ms / 1000) if stats.total_processing_time_ms > 0 else 0
            }
            
            print(f"  ✅ Total: {stats.total_processing_time_ms:.2f}ms")
            print(f"  ✅ Avg latency: {stats.average_latency_per_query_ms:.2f}ms/query")
            print(f"  ✅ Throughput: {stats.throughput_qps:.2f} queries/sec")
            print(f"  ✅ Speedup: {results[name]['speedup']:.2f}x")
            
            retriever.shutdown()
        
        self.results['batch_retrieval'] = results
        return results
    
    async def benchmark_comparison(self, test_configs: List[Dict[str, Any]]) -> Dict[str, Any]:
        """
        Benchmark comparison: cached vs non-cached, batch vs sequential.
        
        Args:
            test_configs: Test configuration list
            
        Returns:
            Comparison results
        """
        results = {}
        
        class MockRAGPipeline:
            """Mock RAG pipeline"""
            async def retrieve(self, query, k=10, use_cache=False):
                await asyncio.sleep(0.02)
                return {
                    'results': [{'id': f'result_{i}'} for i in range(k)],
                    'scores': [0.9 - i*0.1 for i in range(k)],
                    'cache_hit': False
                }
        
        try:
            from src.rag.batch_retrieval import BatchRetriever, BatchQuery
        except ImportError:
            logger.warning("Batch retrieval not available")
            return {}
        
        pipeline = MockRAGPipeline()
        
        num_queries = 50
        queries = [
            BatchQuery(id=f"q_{i}", query=f"Query {i}", k=10)
            for i in range(num_queries)
        ]
        
        print(f"\n📈 Benchmarking comparison (sequential vs batch)...")
        
        retriever = BatchRetriever(pipeline, max_workers=4)
        
        start_time = time.time()
        batch_results, batch_stats = await retriever.retrieve_batch(queries, use_cache=False)
        batch_time = time.time() - start_time
        
        sequential_time = num_queries * 0.02
        
        results['comparison'] = {
            'num_queries': num_queries,
            'sequential_estimated_time_ms': sequential_time * 1000,
            'batch_actual_time_ms': batch_stats.total_processing_time_ms,
            'speedup': sequential_time / (batch_stats.total_processing_time_ms / 1000) if batch_stats.total_processing_time_ms > 0 else 0,
            'efficiency': (sequential_time / (batch_stats.total_processing_time_ms / 1000) / 4) * 100 if batch_stats.total_processing_time_ms > 0 else 0
        }
        
        print(f"  ✅ Sequential (estimated): {results['comparison']['sequential_estimated_time_ms']:.2f}ms")
        print(f"  ✅ Batch (actual): {results['comparison']['batch_actual_time_ms']:.2f}ms")
        print(f"  ✅ Speedup: {results['comparison']['speedup']:.2f}x")
        print(f"  ✅ Efficiency: {results['comparison']['efficiency']:.1f}%")
        
        retriever.shutdown()
        self.results['comparison'] = results
        return results
    
    def save_results(self, filename: str = "rag_benchmark_results.json") -> str:
        """Save benchmark results to file"""
        output_path = self.output_dir / filename
        
        with open(output_path, 'w') as f:
            json.dump({
                'timestamp': datetime.now().isoformat(),
                'benchmarks': self.results
            }, f, indent=2)
        
        print(f"\n✅ Results saved to {output_path}")
        return str(output_path)
    
    def print_summary(self) -> None:
        """Print benchmark summary"""
        print("\n" + "="*60)
        print("RAG OPTIMIZATION BENCHMARKS SUMMARY")
        print("="*60)
        
        for benchmark_name, benchmark_results in self.results.items():
            print(f"\n📊 {benchmark_name.upper()}")
            print("-" * 40)
            
            if isinstance(benchmark_results, dict):
                for test_name, test_result in benchmark_results.items():
                    if isinstance(test_result, dict):
                        print(f"\n  {test_name}:")
                        for key, value in test_result.items():
                            if isinstance(value, float):
                                print(f"    {key}: {value:.2f}")
                            else:
                                print(f"    {key}: {value}")


async def run_benchmarks():
    """Run all RAG benchmarks"""
    benchmark = RAGBenchmark()
    
    print("🚀 Starting RAG Optimization Benchmarks...\n")
    
    await benchmark.benchmark_hnsw_indexing([100, 500, 1000])
    
    await benchmark.benchmark_semantic_cache([
        {'num_queries': 100, 'similarity': 0.95, 'name': 'high_similarity'},
        {'num_queries': 100, 'similarity': 0.80, 'name': 'medium_similarity'},
    ])
    
    await benchmark.benchmark_batch_retrieval([
        {'batch_size': 10, 'workers': 2, 'name': 'small_batch'},
        {'batch_size': 32, 'workers': 4, 'name': 'medium_batch'},
        {'batch_size': 64, 'workers': 8, 'name': 'large_batch'},
    ])
    
    await benchmark.benchmark_comparison([{}])
    
    benchmark.print_summary()
    benchmark.save_results()


if __name__ == "__main__":
    asyncio.run(run_benchmarks())
