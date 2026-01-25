"""
RAG Pipeline MVP for x0tta6bl4

Retrieval-Augmented Generation pipeline for knowledge retrieval.
"""

import logging
import time
from typing import List, Dict, Any, Optional, Tuple
from dataclasses import dataclass, field
from pathlib import Path

from src.storage.vector_index import VectorIndex
from src.rag.chunker import DocumentChunker, DocumentChunk, ChunkingStrategy

logger = logging.getLogger(__name__)

# Optional imports for re-ranking
try:
    from sentence_transformers import CrossEncoder
    CROSS_ENCODER_AVAILABLE = True
except ImportError:
    CROSS_ENCODER_AVAILABLE = False
    CrossEncoder = None
    logger.warning("⚠️ CrossEncoder not available. Install with: pip install sentence-transformers")


@dataclass
class RAGResult:
    """RAG retrieval result"""
    query: str
    retrieved_chunks: List[DocumentChunk]
    scores: List[float]
    context: str
    metadata: Dict[str, Any] = field(default_factory=dict)
    retrieval_time_ms: float = 0.0
    rerank_time_ms: float = 0.0


class RAGPipeline:
    """
    RAG Pipeline MVP for knowledge retrieval.
    
    Pipeline:
    1. Document chunking
    2. Embedding generation
    3. Vector search (HNSW)
    4. Re-ranking (optional)
    5. Context augmentation
    """
    
    def __init__(
        self,
        vector_index: Optional[VectorIndex] = None,
        chunker: Optional[DocumentChunker] = None,
        enable_reranking: bool = True,
        top_k: int = 10,
        rerank_top_k: int = 5,
        similarity_threshold: float = 0.7
    ):
        """
        Initialize RAG pipeline.
        
        Args:
            vector_index: VectorIndex instance (creates new if None)
            chunker: DocumentChunker instance (creates new if None)
            enable_reranking: Enable CrossEncoder re-ranking
            top_k: Number of documents to retrieve
            rerank_top_k: Number of documents after re-ranking
            similarity_threshold: Minimum similarity score
        """
        # Initialize vector index
        if vector_index is None:
            self.vector_index = VectorIndex()
        else:
            self.vector_index = vector_index
        
        # Initialize chunker
        if chunker is None:
            self.chunker = DocumentChunker(
                strategy=ChunkingStrategy.RECURSIVE,
                chunk_size=512,
                chunk_overlap=50
            )
        else:
            self.chunker = chunker
        
        # Re-ranking
        self.enable_reranking = enable_reranking
        self.reranker = None
        if enable_reranking and CROSS_ENCODER_AVAILABLE:
            try:
                # Use a lightweight CrossEncoder model
                self.reranker = CrossEncoder('cross-encoder/ms-marco-MiniLM-L-6-v2')
                logger.info("✅ CrossEncoder re-ranker loaded")
            except Exception as e:
                logger.warning(f"⚠️ Failed to load CrossEncoder: {e}")
                self.enable_reranking = False
        
        self.top_k = top_k
        self.rerank_top_k = rerank_top_k
        self.similarity_threshold = similarity_threshold
        
        logger.info(f"✅ RAG Pipeline initialized (top_k={top_k}, rerank={enable_reranking})")
    
    def add_document(
        self,
        text: str,
        document_id: str,
        metadata: Optional[Dict[str, Any]] = None
    ) -> List[str]:
        """
        Add document to knowledge base.
        
        Args:
            text: Document text
            document_id: Document identifier
            metadata: Optional metadata
        
        Returns:
            List of chunk IDs
        
        Raises:
            ValueError: If text or document_id is empty
        """
        if not text or not text.strip():
            raise ValueError("Document text cannot be empty")
        if not document_id or not document_id.strip():
            raise ValueError("Document ID cannot be empty")
        """
        Add document to knowledge base.
        
        Args:
            text: Document text
            document_id: Document identifier
            metadata: Optional metadata
        
        Returns:
            List of chunk IDs
        """
        metadata = metadata or {}
        
        # Chunk document
        chunks = self.chunker.chunk(text, document_id, metadata)
        
        chunk_ids = []
        for chunk in chunks:
            # Add chunk to vector index
            chunk_id = self.vector_index.add(
                text=chunk.text,
                metadata={
                    **chunk.metadata,
                    'chunk_id': chunk.chunk_id,
                    'document_id': chunk.document_id,
                    'start_index': chunk.start_index,
                    'end_index': chunk.end_index
                }
            )
            chunk_ids.append(str(chunk_id))
        
        logger.info(f"📝 Added document {document_id} ({len(chunks)} chunks)")
        return chunk_ids
    
    def retrieve(
        self,
        query: str,
        top_k: Optional[int] = None,
        rerank: Optional[bool] = None
    ) -> RAGResult:
        """
        Retrieve relevant documents for query.
        
        Args:
            query: Search query
            top_k: Number of results (uses self.top_k if None)
            rerank: Enable re-ranking (uses self.enable_reranking if None)
        
        Returns:
            RAGResult with retrieved chunks and context
        
        Raises:
            ValueError: If query is empty
        """
        if not query or not query.strip():
            raise ValueError("Query cannot be empty")
        """
        Retrieve relevant documents for query.
        
        Args:
            query: Search query
            top_k: Number of results (uses self.top_k if None)
            rerank: Enable re-ranking (uses self.enable_reranking if None)
        
        Returns:
            RAGResult with retrieved chunks and context
        """
        top_k = top_k or self.top_k
        rerank = rerank if rerank is not None else self.enable_reranking
        
        start_time = time.time()
        
        # Step 1: Vector search
        search_results = self.vector_index.search(
            query=query,
            k=top_k,
            threshold=self.similarity_threshold
        )
        
        retrieval_time = (time.time() - start_time) * 1000
        
        if not search_results:
            logger.warning(f"⚠️ No results found for query: {query}")
            return RAGResult(
                query=query,
                retrieved_chunks=[],
                scores=[],
                context="",
                retrieval_time_ms=retrieval_time
            )
        
        # Extract chunks and scores
        chunks = []
        scores = []
        for doc_id, score, metadata in search_results:
            chunk = DocumentChunk(
                text=metadata.get('text', ''),
                chunk_id=metadata.get('chunk_id', str(doc_id)),
                document_id=metadata.get('document_id', 'unknown'),
                start_index=metadata.get('start_index', 0),
                end_index=metadata.get('end_index', 0),
                metadata=metadata
            )
            chunks.append(chunk)
            scores.append(score)
        
        rerank_time = 0.0
        
        # Step 2: Re-ranking (optional)
        if rerank and self.reranker and len(chunks) > 1:
            rerank_start = time.time()
            
            # Prepare query-chunk pairs
            pairs = [[query, chunk.text] for chunk in chunks]
            
            # Re-rank
            rerank_scores = self.reranker.predict(pairs)
            
            # Sort by re-rank scores
            reranked_indices = sorted(
                range(len(rerank_scores)),
                key=lambda i: rerank_scores[i],
                reverse=True
            )
            
            # Select top-k after re-ranking
            reranked_indices = reranked_indices[:self.rerank_top_k]
            
            chunks = [chunks[i] for i in reranked_indices]
            scores = [rerank_scores[i] for i in reranked_indices]
            
            rerank_time = (time.time() - rerank_start) * 1000
            logger.debug(f"🔄 Re-ranked {len(search_results)} → {len(chunks)} chunks")
        
        # Step 3: Build context
        context = self._build_context(chunks)
        
        result = RAGResult(
            query=query,
            retrieved_chunks=chunks,
            scores=scores,
            context=context,
            retrieval_time_ms=retrieval_time,
            rerank_time_ms=rerank_time,
            metadata={
                'total_chunks': len(chunks),
                'reranked': rerank and self.reranker is not None
            }
        )
        
        logger.info(f"✅ Retrieved {len(chunks)} chunks for query (retrieval: {retrieval_time:.1f}ms, rerank: {rerank_time:.1f}ms)")
        
        return result
    
    def _build_context(self, chunks: List[DocumentChunk]) -> str:
        """
        Build context string from retrieved chunks.
        
        Args:
            chunks: List of document chunks
        
        Returns:
            Context string
        """
        context_parts = []
        
        for i, chunk in enumerate(chunks):
            context_parts.append(f"[Chunk {i+1} from {chunk.document_id}]\n{chunk.text}\n")
        
        return "\n---\n".join(context_parts)
    
    def query(
        self,
        query: str,
        top_k: Optional[int] = None,
        rerank: Optional[bool] = None
    ) -> str:
        """
        Query knowledge base and return context.
        
        Convenience method that returns just the context string.
        
        Args:
            query: Search query
            top_k: Number of results
            rerank: Enable re-ranking
        
        Returns:
            Context string
        """
        result = self.retrieve(query, top_k=top_k, rerank=rerank)
        return result.context
    
    def get_stats(self) -> Dict[str, Any]:
        """Get pipeline statistics."""
        index_stats = self.vector_index.get_stats()
        
        return {
            **index_stats,
            'chunking_strategy': self.chunker.strategy.value,
            'chunk_size': self.chunker.chunk_size,
            'chunk_overlap': self.chunker.chunk_overlap,
            'top_k': self.top_k,
            'rerank_top_k': self.rerank_top_k,
            'similarity_threshold': self.similarity_threshold,
            'reranking_enabled': self.enable_reranking and self.reranker is not None
        }
    
    def save(self, path: Optional[Path] = None):
        """Save pipeline state."""
        if path:
            path.mkdir(parents=True, exist_ok=True)
            self.vector_index.save(path / "vector_index")
            logger.info(f"💾 Saved RAG pipeline to {path}")
        else:
            self.vector_index.save()
    
    def load(self, path: Optional[Path] = None):
        """Load pipeline state."""
        if path:
            self.vector_index.load(path / "vector_index")
            logger.info(f"📂 Loaded RAG pipeline from {path}")
        else:
            self.vector_index.load()

