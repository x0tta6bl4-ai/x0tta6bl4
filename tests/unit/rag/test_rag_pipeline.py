"""
Unit tests for RAG Pipeline MVP
"""

import os

# Prevent heavy model downloads during unit tests
os.environ.setdefault("RAG_DISABLE_EMBEDDING_MODEL", "true")
os.environ.setdefault("RAG_DISABLE_RERANKER", "true")

from pathlib import Path
from unittest.mock import MagicMock, Mock, patch

import pytest

try:
    from src.rag.chunker import (ChunkingStrategy, DocumentChunk,
                                 DocumentChunker)
    from src.rag.pipeline import RAGPipeline, RAGResult
    from src.storage.vector_index import VectorIndex

    RAG_AVAILABLE = True
except ImportError:
    RAG_AVAILABLE = False
    RAGPipeline = None
    RAGResult = None
    DocumentChunker = None


@pytest.mark.skipif(not RAG_AVAILABLE, reason="RAG Pipeline not available")
class TestRAGPipeline:
    """Tests for RAG Pipeline"""

    def test_pipeline_initialization(self):
        """Test RAG pipeline initialization"""
        pipeline = RAGPipeline(top_k=10, rerank_top_k=5, similarity_threshold=0.7)

        assert pipeline.top_k == 10
        assert pipeline.rerank_top_k == 5
        assert pipeline.similarity_threshold == 0.7
        assert pipeline.vector_index is not None
        assert pipeline.chunker is not None

    def test_add_document(self):
        """Test adding document to pipeline"""
        pipeline = RAGPipeline()

        text = "This is a test document about network routing and mesh topology."
        chunk_ids = pipeline.add_document(
            text=text,
            document_id="doc_001",
            metadata={"type": "technical", "topic": "networking"},
        )

        assert len(chunk_ids) > 0
        assert all(isinstance(cid, str) for cid in chunk_ids)

    def test_retrieve_without_documents(self):
        """Test retrieval when no documents are indexed"""
        pipeline = RAGPipeline()

        result = pipeline.retrieve("test query")

        assert isinstance(result, RAGResult)
        assert result.query == "test query"
        assert len(result.retrieved_chunks) == 0
        assert result.context == ""

    def test_retrieve_with_documents(self):
        """Test retrieval with indexed documents"""
        pipeline = RAGPipeline()

        # Add document
        pipeline.add_document(
            text="Network routing is important for mesh networks.",
            document_id="doc_001",
        )

        # Retrieve
        result = pipeline.retrieve("mesh network routing")

        assert isinstance(result, RAGResult)
        assert result.query == "mesh network routing"
        assert result.retrieval_time_ms >= 0

    def test_query_convenience_method(self):
        """Test query convenience method - mock heavy retrieval to avoid model downloads/hangs"""
        pipeline = RAGPipeline()

        # Avoid calling the real add_document (may trigger embedding/model loads)
        from unittest.mock import patch

        with (
            patch.object(RAGPipeline, "add_document", return_value=["doc_001_chunk_0"]),
            patch.object(
                RAGPipeline,
                "retrieve",
                return_value=RAGResult(
                    query="test query",
                    retrieved_chunks=[],
                    scores=[],
                    context="mocked context",
                    retrieval_time_ms=0.0,
                ),
            ),
        ):
            # Call add_document (mocked) and then query (retrieve mocked)
            chunk_ids = pipeline.add_document(
                text="Test document content", document_id="doc_001"
            )
            assert chunk_ids == ["doc_001_chunk_0"]
            context = pipeline.query("test query")

        assert isinstance(context, str)
        assert context == "mocked context"

    def test_get_stats(self):
        """Test getting pipeline statistics"""
        pipeline = RAGPipeline()

        stats = pipeline.get_stats()

        assert isinstance(stats, dict)
        assert "chunking_strategy" in stats
        assert "top_k" in stats
        assert "similarity_threshold" in stats

    def test_save_and_load(self, tmp_path):
        """Test saving and loading pipeline"""
        pipeline = RAGPipeline()

        # Add some documents (text must exceed min_chunk_size=100 to produce at least one chunk)
        pipeline.add_document(
            "This is a sufficiently long test document about mesh networking, "
            "post-quantum cryptography, and self-healing infrastructure that "
            "exceeds the minimum chunk size threshold for the recursive chunker.",
            "doc_001",
        )

        # Save
        save_path = tmp_path / "rag_pipeline"
        pipeline.save(save_path)

        # Create new pipeline and load
        new_pipeline = RAGPipeline()
        new_pipeline.load(save_path)

        # Verify loaded
        stats = new_pipeline.get_stats()
        assert stats["total_documents"] > 0


@pytest.mark.skipif(not RAG_AVAILABLE, reason="RAG Pipeline not available")
class TestDocumentChunker:
    """Tests for Document Chunker"""

    def test_chunker_initialization(self):
        """Test chunker initialization"""
        chunker = DocumentChunker(
            strategy=ChunkingStrategy.RECURSIVE, chunk_size=512, chunk_overlap=50
        )

        assert chunker.strategy == ChunkingStrategy.RECURSIVE
        assert chunker.chunk_size == 512
        assert chunker.chunk_overlap == 50

    def test_fixed_size_chunking(self):
        """Test fixed size chunking"""
        chunker = DocumentChunker(
            strategy=ChunkingStrategy.FIXED_SIZE, chunk_size=100, chunk_overlap=10
        )

        text = "A" * 250  # 250 characters
        chunks = chunker.chunk(text, "doc_001")

        assert len(chunks) > 1
        assert all(len(chunk.text) <= 100 for chunk in chunks)

    def test_sentence_chunking(self):
        """Test sentence chunking"""
        chunker = DocumentChunker(strategy=ChunkingStrategy.SENTENCE, chunk_size=100)

        text = "First sentence. Second sentence. Third sentence."
        chunks = chunker.chunk(text, "doc_001")

        assert len(chunks) > 0
        assert all(isinstance(chunk, DocumentChunk) for chunk in chunks)

    def test_paragraph_chunking(self):
        """Test paragraph chunking"""
        chunker = DocumentChunker(strategy=ChunkingStrategy.PARAGRAPH, chunk_size=200)

        text = "First paragraph.\n\nSecond paragraph.\n\nThird paragraph."
        chunks = chunker.chunk(text, "doc_001")

        assert len(chunks) > 0

    def test_recursive_chunking(self):
        """Test recursive chunking"""
        chunker = DocumentChunker(strategy=ChunkingStrategy.RECURSIVE, chunk_size=100)

        text = "Test document with multiple sentences. Each sentence adds content."
        chunks = chunker.chunk(text, "doc_001")

        assert len(chunks) > 0
        assert all(chunk.document_id == "doc_001" for chunk in chunks)
