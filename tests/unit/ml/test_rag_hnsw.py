"""
Unit tests for RAG with HNSW vector index
"""

import asyncio
import tempfile
from datetime import datetime
from pathlib import Path

import numpy as np
import pytest

try:
    from src.ml.rag import (HNSWLIB_AVAILABLE, Document, HNSWVectorStore,
                            RAGAnalyzer, VectorStore)

    RAG_AVAILABLE = True
except ImportError:
    RAG_AVAILABLE = False
    HNSWLIB_AVAILABLE = False


@pytest.mark.skipif(not RAG_AVAILABLE, reason="RAG module not available")
class TestHNSWVectorStore:
    """Tests for HNSW Vector Store"""

    @pytest.mark.skipif(not HNSWLIB_AVAILABLE, reason="HNSWLIB not available")
    def test_hnsw_initialization(self):
        """Test HNSW vector store initialization"""
        store = HNSWVectorStore(embedding_dim=384, max_elements=1000)

        assert store.embedding_dim == 384
        assert store.max_elements == 1000
        assert len(store.documents) == 0
        assert store.next_label == 0

    @pytest.mark.skipif(not HNSWLIB_AVAILABLE, reason="HNSWLIB not available")
    def test_hnsw_add_single_document(self):
        """Test adding a single document to HNSW"""
        store = HNSWVectorStore(embedding_dim=384)

        doc = Document(
            id="doc_001",
            content="Test document content",
            metadata={"source": "test"},
            embedding=np.random.randn(384),
        )

        store.add_document(doc)

        assert len(store.documents) == 1
        assert "doc_001" in store.documents
        assert store.next_label == 1

    @pytest.mark.skipif(not HNSWLIB_AVAILABLE, reason="HNSWLIB not available")
    def test_hnsw_batch_add_documents(self):
        """Test batch adding documents to HNSW"""
        store = HNSWVectorStore(embedding_dim=384)

        docs = [
            Document(
                id=f"doc_{i:03d}",
                content=f"Document content {i}",
                metadata={"index": i},
                embedding=np.random.randn(384),
            )
            for i in range(10)
        ]

        store.add_documents_batch(docs)

        assert len(store.documents) == 10
        assert store.next_label == 10

    def test_hnsw_retrieve_similar_documents(self):
        """Test retrieving similar documents"""
        store = HNSWVectorStore(embedding_dim=384)

        # Create a base embedding
        base_embedding = np.random.randn(384)
        base_embedding /= np.linalg.norm(base_embedding)

        # Add similar documents
        for i in range(5):
            doc = Document(
                id=f"doc_{i:03d}",
                content=f"Document {i}",
                metadata={},
                embedding=base_embedding + np.random.randn(384) * 0.01,
            )
            store.add_document(doc)

        # Retrieve
        results = store.retrieve(base_embedding, k=3)

        assert len(results) == 3
        assert all(isinstance(doc_id, str) for doc_id, _ in results)
        assert all(isinstance(sim, float) for _, sim in results)

    def test_hnsw_retrieve_empty_store(self):
        """Test retrieving from empty store"""
        store = HNSWVectorStore(embedding_dim=384)

        query_embedding = np.random.randn(384)
        results = store.retrieve(query_embedding, k=5)

        assert len(results) == 0

    @pytest.mark.skipif(not HNSWLIB_AVAILABLE, reason="HNSWLIB not available")
    def test_hnsw_save_and_load(self):
        """Test saving and loading HNSW index"""
        with tempfile.TemporaryDirectory() as tmpdir:
            # Create and populate store
            store = HNSWVectorStore(embedding_dim=384, max_elements=1000)

            docs = [
                Document(
                    id=f"doc_{i:03d}",
                    content=f"Content {i}",
                    metadata={},
                    embedding=np.random.randn(384),
                )
                for i in range(5)
            ]

            store.add_documents_batch(docs)

            # Save
            store.save(tmpdir)

            # Load into new store
            new_store = HNSWVectorStore(embedding_dim=384, max_elements=1000)
            new_store.load(tmpdir)

            assert len(new_store.documents) == 5
            assert new_store.next_label == 5


@pytest.mark.skipif(not RAG_AVAILABLE, reason="RAG module not available")
class TestRAGAnalyzerHNSW:
    """Tests for RAG Analyzer with HNSW"""

    @pytest.mark.asyncio
    @pytest.mark.skipif(not HNSWLIB_AVAILABLE, reason="HNSWLIB not available")
    async def test_rag_initialization_with_hnsw(self):
        """Test RAG analyzer initialization with HNSW"""
        rag = RAGAnalyzer(use_hnsw=True, use_langchain=False)

        assert rag.use_hnsw == True
        assert isinstance(rag.vector_store, HNSWVectorStore)
        assert rag.embedding_dim == 384

    @pytest.mark.asyncio
    async def test_rag_initialization_fallback(self):
        """Test RAG analyzer fallback to simple store"""
        rag = RAGAnalyzer(use_hnsw=False, use_langchain=False)

        assert rag.use_hnsw == False
        assert isinstance(rag.vector_store, VectorStore)

    @pytest.mark.asyncio
    async def test_rag_index_knowledge(self):
        """Test indexing knowledge entries"""
        rag = RAGAnalyzer(use_hnsw=True, use_langchain=False)

        knowledge = [
            {"insight": "Network latency spike detected", "timestamp": "2026-01-10"},
            {"insight": "API response time degradation", "timestamp": "2026-01-10"},
            {"insight": "Memory usage anomaly", "timestamp": "2026-01-11"},
        ]

        indexed = await rag.index_knowledge(knowledge)

        assert indexed == 3
        assert len(rag.vector_store.documents) == 3
        assert rag.index_stats["documents_indexed"] == 3
        assert rag.index_stats["last_batch_size"] == 3

    @pytest.mark.asyncio
    async def test_rag_retrieve_context(self):
        """Test retrieving context"""
        rag = RAGAnalyzer(use_hnsw=True, use_langchain=False)

        # Index some knowledge
        knowledge = [
            {"insight": "Network latency spike at 14:30", "timestamp": "2026-01-10"},
            {"insight": "CPU usage increased", "timestamp": "2026-01-10"},
            {"insight": "Memory pressure alert", "timestamp": "2026-01-11"},
        ]

        await rag.index_knowledge(knowledge)

        # Retrieve context
        result = await rag.retrieve_context("network performance", k=2, threshold=0.0)

        assert result.query == "network performance"
        assert result.timestamp is not None
        assert len(rag.index_stats["retrieval_times"]) > 0

    @pytest.mark.asyncio
    async def test_rag_retrieval_latency_tracking(self):
        """Test retrieval latency tracking"""
        rag = RAGAnalyzer(use_hnsw=True, use_langchain=False)

        knowledge = [
            {"insight": f"Insight {i}", "timestamp": "2026-01-10"} for i in range(10)
        ]

        await rag.index_knowledge(knowledge)

        # Retrieve multiple times
        for _ in range(5):
            await rag.retrieve_context("test query")

        assert len(rag.index_stats["retrieval_times"]) == 5
        assert all(t > 0 for t in rag.index_stats["retrieval_times"])

    def test_rag_get_stats(self):
        """Test RAG statistics"""
        rag = RAGAnalyzer(use_hnsw=False, use_langchain=False)

        stats = rag.get_stats()

        assert "documents_indexed" in stats
        assert "queries_processed" in stats
        assert "embedding_dim" in stats
        assert "hnsw_enabled" in stats
        assert "vector_store_type" in stats

    @pytest.mark.skipif(not HNSWLIB_AVAILABLE, reason="HNSWLIB not available")
    def test_rag_get_stats_with_hnsw(self):
        """Test RAG statistics with HNSW"""
        rag = RAGAnalyzer(use_hnsw=True, use_langchain=False)

        stats = rag.get_stats()

        assert stats["hnsw_enabled"] == True
        assert stats["vector_store_type"] == "HNSW"

    @pytest.mark.asyncio
    async def test_rag_augment_analysis(self):
        """Test augmenting analysis with RAG context"""
        rag = RAGAnalyzer(use_hnsw=True, use_langchain=False)

        # Index knowledge
        knowledge = [
            {"insight": "High CPU usage detected", "timestamp": "2026-01-10"},
            {"insight": "Memory pressure increasing", "timestamp": "2026-01-10"},
        ]

        await rag.index_knowledge(knowledge)

        # Augment analysis
        current_analysis = {"anomaly": "high_cpu", "severity": "medium"}
        augmented = await rag.augment_analysis(
            current_analysis, "CPU performance issue"
        )

        assert "rag" in augmented
        assert "context_documents" in augmented["rag"]
        assert isinstance(augmented["rag"]["context_documents"], int)

    @pytest.mark.skipif(not HNSWLIB_AVAILABLE, reason="HNSWLIB not available")
    def test_rag_index_persistence(self):
        """Test saving and loading RAG index"""
        with tempfile.TemporaryDirectory() as tmpdir:
            # Create and populate RAG analyzer
            rag = RAGAnalyzer(use_hnsw=True, use_langchain=False, persist_dir=tmpdir)

            # Manually add some documents to the vector store
            doc = Document(
                id="doc_001",
                content="Test document",
                metadata={},
                embedding=np.random.randn(384),
            )
            rag.vector_store.add_document(doc)

            # Save
            rag.save_index(tmpdir)

            # Create new analyzer and load
            rag2 = RAGAnalyzer(use_hnsw=True, use_langchain=False, persist_dir=tmpdir)
            rag2.load_index(tmpdir)

            assert len(rag2.vector_store.documents) == 1
            assert "doc_001" in rag2.vector_store.documents

    @pytest.mark.asyncio
    async def test_rag_batch_indexing_efficiency(self):
        """Test batch indexing is recorded properly"""
        rag = RAGAnalyzer(use_hnsw=False, use_langchain=False)

        # Index in batches with unique IDs
        for batch_idx in range(3):
            knowledge = [
                {
                    "insight": f"Batch {batch_idx} insight {i}",
                    "timestamp": f"2026-01-{10+batch_idx:02d}",
                }
                for i in range(5)
            ]
            await rag.index_knowledge(knowledge)

        # Check stats
        assert rag.index_stats["documents_indexed"] == 15
        assert rag.index_stats["last_batch_size"] == 5
        assert len(rag.vector_store.documents) == 15


if __name__ == "__main__":
    pytest.main([__file__, "-v"])
