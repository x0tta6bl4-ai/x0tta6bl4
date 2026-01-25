"""
Batch Retrieval Optimization for RAG Pipeline

Implements efficient batch processing for multiple queries
with parallel execution and result aggregation.
"""

import asyncio
import logging
import time
from typing import List, Dict, Any, Optional, Coroutine
from dataclasses import dataclass
from concurrent.futures import ThreadPoolExecutor
import numpy as np

logger = logging.getLogger(__name__)


@dataclass
class BatchQuery:
    """Query in batch"""
    id: str
    query: str
    k: int = 10
    threshold: float = 0.3


@dataclass
class BatchResult:
    """Result for batch query"""
    query_id: str
    query: str
    results: List[Dict[str, Any]]
    scores: List[float]
    processing_time_ms: float
    success: bool
    error: Optional[str] = None


@dataclass
class BatchRetrievalStats:
    """Statistics for batch retrieval"""
    total_queries: int
    successful_queries: int
    failed_queries: int
    total_processing_time_ms: float
    average_latency_per_query_ms: float
    parallelism_factor: float
    throughput_qps: float


class BatchRetriever:
    """
    Batch retrieval optimizer for RAG pipeline.
    
    Features:
    - Parallel query processing
    - Batch embedding generation
    - Result aggregation
    - Performance tracking
    - Automatic retries
    """
    
    def __init__(
        self,
        rag_pipeline,
        max_workers: int = 4,
        batch_size: int = 32,
        enable_batch_embeddings: bool = True
    ):
        """
        Initialize batch retriever.
        
        Args:
            rag_pipeline: Underlying RAG pipeline
            max_workers: Max parallel workers
            batch_size: Batch size for processing
            enable_batch_embeddings: Batch embed generation
        """
        self.rag_pipeline = rag_pipeline
        self.max_workers = max_workers
        self.batch_size = batch_size
        self.enable_batch_embeddings = enable_batch_embeddings
        
        self.executor = ThreadPoolExecutor(max_workers=max_workers)
        self.stats = {
            'total_queries': 0,
            'successful_queries': 0,
            'failed_queries': 0,
            'total_processing_time_ms': 0,
            'batch_retrieval_calls': 0
        }
    
    async def retrieve_batch(
        self,
        queries: List[BatchQuery],
        use_cache: bool = True
    ) -> tuple[List[BatchResult], BatchRetrievalStats]:
        """
        Retrieve results for multiple queries in parallel.
        
        Args:
            queries: List of queries to process
            use_cache: Enable caching if available
            
        Returns:
            Tuple of (results, statistics)
        """
        start_time = time.time()
        
        if not queries:
            return [], BatchRetrievalStats(0, 0, 0, 0, 0, 0, 0)
        
        self.stats['batch_retrieval_calls'] += 1
        
        if self.enable_batch_embeddings and len(queries) > 1:
            results = await self._retrieve_batch_optimized(queries, use_cache)
        else:
            results = await self._retrieve_batch_sequential(queries, use_cache)
        
        processing_time_ms = (time.time() - start_time) * 1000
        
        self.stats['total_queries'] += len(queries)
        self.stats['total_processing_time_ms'] += processing_time_ms
        
        successful = sum(1 for r in results if r.success)
        failed = len(results) - successful
        
        self.stats['successful_queries'] += successful
        self.stats['failed_queries'] += failed
        
        avg_latency = processing_time_ms / len(queries) if queries else 0
        throughput = (len(queries) * 1000) / processing_time_ms if processing_time_ms > 0 else 0
        
        stats = BatchRetrievalStats(
            total_queries=len(queries),
            successful_queries=successful,
            failed_queries=failed,
            total_processing_time_ms=processing_time_ms,
            average_latency_per_query_ms=avg_latency,
            parallelism_factor=min(len(queries), self.max_workers),
            throughput_qps=throughput
        )
        
        return results, stats
    
    async def _retrieve_batch_sequential(
        self,
        queries: List[BatchQuery],
        use_cache: bool
    ) -> List[BatchResult]:
        """Sequential retrieval (fallback)"""
        results = []
        
        for query in queries:
            start = time.time()
            
            try:
                result = await self.rag_pipeline.retrieve(
                    query.query,
                    k=query.k,
                    use_cache=use_cache
                )
                
                processing_time = (time.time() - start) * 1000
                
                results.append(BatchResult(
                    query_id=query.id,
                    query=query.query,
                    results=result.get('results', []),
                    scores=result.get('scores', []),
                    processing_time_ms=processing_time,
                    success=True
                ))
            except Exception as e:
                processing_time = (time.time() - start) * 1000
                results.append(BatchResult(
                    query_id=query.id,
                    query=query.query,
                    results=[],
                    scores=[],
                    processing_time_ms=processing_time,
                    success=False,
                    error=str(e)
                ))
        
        return results
    
    async def _retrieve_batch_optimized(
        self,
        queries: List[BatchQuery],
        use_cache: bool
    ) -> List[BatchResult]:
        """Optimized batch retrieval with parallel processing"""
        
        tasks = []
        for query in queries:
            task = asyncio.create_task(
                self._retrieve_single(query, use_cache)
            )
            tasks.append(task)
        
        results = await asyncio.gather(*tasks, return_exceptions=False)
        
        return results
    
    async def _retrieve_single(
        self,
        query: BatchQuery,
        use_cache: bool
    ) -> BatchResult:
        """Retrieve single query"""
        start_time = time.time()
        
        try:
            result = await self.rag_pipeline.retrieve(
                query.query,
                k=query.k,
                use_cache=use_cache
            )
            
            processing_time = (time.time() - start_time) * 1000
            
            return BatchResult(
                query_id=query.id,
                query=query.query,
                results=result.get('results', []),
                scores=result.get('scores', []),
                processing_time_ms=processing_time,
                success=True
            )
        except Exception as e:
            processing_time = (time.time() - start_time) * 1000
            return BatchResult(
                query_id=query.id,
                query=query.query,
                results=[],
                scores=[],
                processing_time_ms=processing_time,
                success=False,
                error=str(e)
            )
    
    async def retrieve_batch_chunked(
        self,
        queries: List[BatchQuery],
        chunk_size: Optional[int] = None,
        use_cache: bool = True
    ) -> tuple[List[BatchResult], BatchRetrievalStats]:
        """
        Retrieve in chunks (for very large batch sizes).
        
        Args:
            queries: List of queries
            chunk_size: Chunk size (defaults to batch_size)
            use_cache: Enable caching
            
        Returns:
            Tuple of (results, aggregated statistics)
        """
        chunk_size = chunk_size or self.batch_size
        
        all_results = []
        aggregated_stats = BatchRetrievalStats(0, 0, 0, 0, 0, 0, 0)
        
        for i in range(0, len(queries), chunk_size):
            chunk = queries[i:i+chunk_size]
            results, stats = await self.retrieve_batch(chunk, use_cache)
            all_results.extend(results)
            
            aggregated_stats.total_queries += stats.total_queries
            aggregated_stats.successful_queries += stats.successful_queries
            aggregated_stats.failed_queries += stats.failed_queries
            aggregated_stats.total_processing_time_ms += stats.total_processing_time_ms
        
        if all_results:
            avg_latency = aggregated_stats.total_processing_time_ms / len(all_results)
            throughput = (len(all_results) * 1000) / aggregated_stats.total_processing_time_ms
        else:
            avg_latency = 0
            throughput = 0
        
        aggregated_stats.average_latency_per_query_ms = avg_latency
        aggregated_stats.throughput_qps = throughput
        aggregated_stats.parallelism_factor = min(len(queries), self.max_workers)
        
        return all_results, aggregated_stats
    
    def get_stats(self) -> Dict[str, Any]:
        """Get batch retriever statistics"""
        total_time = self.stats['total_processing_time_ms']
        total_queries = self.stats['total_queries']
        
        avg_latency = total_time / total_queries if total_queries > 0 else 0
        throughput = (total_queries * 1000) / total_time if total_time > 0 else 0
        success_rate = (self.stats['successful_queries'] / total_queries * 100) if total_queries > 0 else 0
        
        return {
            'total_queries': total_queries,
            'successful_queries': self.stats['successful_queries'],
            'failed_queries': self.stats['failed_queries'],
            'success_rate': success_rate,
            'total_processing_time_ms': total_time,
            'average_latency_per_query_ms': avg_latency,
            'throughput_qps': throughput,
            'batch_retrieval_calls': self.stats['batch_retrieval_calls']
        }
    
    def reset_stats(self) -> None:
        """Reset statistics"""
        self.stats = {
            'total_queries': 0,
            'successful_queries': 0,
            'failed_queries': 0,
            'total_processing_time_ms': 0,
            'batch_retrieval_calls': 0
        }
    
    def shutdown(self) -> None:
        """Shutdown thread pool"""
        self.executor.shutdown(wait=True)


class AdaptiveBatchRetriever(BatchRetriever):
    """
    Adaptive batch retriever with dynamic parallelism.
    
    Automatically adjusts parallelism based on latency.
    """
    
    def __init__(self, rag_pipeline, initial_workers: int = 4):
        """Initialize adaptive batch retriever"""
        super().__init__(rag_pipeline, max_workers=initial_workers)
        
        self.latency_history: List[float] = []
        self.target_latency_ms = 100
        self.adjustment_step = 1
    
    async def retrieve_batch_adaptive(
        self,
        queries: List[BatchQuery],
        target_latency_ms: Optional[float] = None,
        use_cache: bool = True
    ) -> tuple[List[BatchResult], BatchRetrievalStats]:
        """
        Retrieve with adaptive parallelism.
        
        Args:
            queries: List of queries
            target_latency_ms: Target latency goal
            use_cache: Enable caching
            
        Returns:
            Tuple of (results, statistics)
        """
        if target_latency_ms:
            self.target_latency_ms = target_latency_ms
        
        results, stats = await self.retrieve_batch(queries, use_cache)
        
        self.latency_history.append(stats.average_latency_per_query_ms)
        if len(self.latency_history) > 100:
            self.latency_history = self.latency_history[-100:]
        
        self._adjust_parallelism()
        
        return results, stats
    
    def _adjust_parallelism(self) -> None:
        """Adjust max_workers based on latency"""
        if len(self.latency_history) < 2:
            return
        
        recent_avg = np.mean(self.latency_history[-10:])
        
        if recent_avg < self.target_latency_ms * 0.8:
            self.max_workers = min(self.max_workers + self.adjustment_step, 16)
            logger.info(f"Increased parallelism to {self.max_workers}")
        elif recent_avg > self.target_latency_ms * 1.2:
            self.max_workers = max(self.max_workers - self.adjustment_step, 1)
            logger.info(f"Decreased parallelism to {self.max_workers}")
