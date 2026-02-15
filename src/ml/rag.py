"""
RAG (Retrieval-Augmented Generation) Module

Provides context-aware analysis by retrieving relevant historical patterns
and generating augmented insights for better decision making.
"""

import asyncio
import json
import os
import time
from collections import defaultdict
from dataclasses import dataclass
from datetime import datetime
from pathlib import Path
from typing import Any, Dict, List, Optional, Tuple

import numpy as np

# Monitoring metrics
try:
    from src.monitoring import record_rag_retrieval

    MONITORING_AVAILABLE = True
except ImportError:
    MONITORING_AVAILABLE = False

    def record_rag_retrieval(*args, **kwargs):
        pass


try:
    import chromadb
    from langchain.embeddings import HuggingFaceEmbeddings
    from langchain.text_splitter import RecursiveCharacterTextSplitter

    LANGCHAIN_AVAILABLE = True
except ImportError:
    LANGCHAIN_AVAILABLE = False

try:
    import hnswlib

    HNSWLIB_AVAILABLE = True
except ImportError:
    HNSWLIB_AVAILABLE = False


@dataclass
class Document:
    """Document for RAG retrieval"""

    id: str
    content: str
    metadata: Dict[str, Any]
    embedding: Optional[np.ndarray] = None
    timestamp: datetime = None


@dataclass
class RetrievalResult(list):
    """Result from RAG retrieval (list-compatible for legacy callers)."""

    documents: List[Document]
    similarities: List[float]
    query: str
    timestamp: datetime

    def __post_init__(self):
        super().clear()
        super().extend(self.documents)


def serialize_document(doc: Document) -> Dict[str, Any]:
    """Serialize Document to JSON-safe dict."""
    return {
        "id": doc.id,
        "content": doc.content,
        "metadata": doc.metadata,
        "embedding": doc.embedding.tolist() if doc.embedding is not None else None,
        "timestamp": doc.timestamp.isoformat() if doc.timestamp else None,
    }


def deserialize_document(data: Dict[str, Any]) -> Document:
    """Deserialize Document from JSON-safe dict."""
    embedding = (
        np.array(data["embedding"]) if data.get("embedding") is not None else None
    )
    timestamp = (
        datetime.fromisoformat(data["timestamp"]) if data.get("timestamp") else None
    )
    return Document(
        id=data["id"],
        content=data["content"],
        metadata=data.get("metadata", {}),
        embedding=embedding,
        timestamp=timestamp,
    )


class HNSWVectorStore:
    """HNSW-based vector store for efficient similarity search"""

    def __init__(
        self,
        embedding_dim: int = 384,
        max_elements: int = 10000,
        ef_construction: int = 200,
        ef: int = 50,
        persist_dir: Optional[str] = None,
    ):
        """
        Initialize HNSW vector store

        Args:
            embedding_dim: Dimension of embeddings
            max_elements: Maximum number of elements in the index
            ef_construction: Size of dynamic list (construction parameter)
            ef: Size of dynamic list (search parameter)
            persist_dir: Directory to persist index to disk
        """
        self.embedding_dim = embedding_dim
        self.max_elements = max_elements
        self.ef_construction = ef_construction
        self.ef = ef
        self.persist_dir = persist_dir
        self.documents: Dict[str, Document] = {}
        self.id_to_label: Dict[str, int] = {}
        self.label_to_id: Dict[int, str] = {}
        self.next_label = 0

        if HNSWLIB_AVAILABLE:
            self.index = hnswlib.Index(space="cosine", dim=embedding_dim)
            self.index.init_index(
                max_elements=max_elements, ef_construction=ef_construction, M=16
            )
            self.index.set_ef(ef)
        else:
            self.index = None

    def add_document(self, doc: Document) -> None:
        """Add document to store"""
        if doc.embedding is None:
            doc.embedding = np.random.randn(self.embedding_dim)

        self.documents[doc.id] = doc

        if self.index is not None:
            label = self.next_label
            self.id_to_label[doc.id] = label
            self.label_to_id[label] = doc.id
            self.next_label += 1

            # Normalize embedding for cosine distance
            embedding = doc.embedding / (np.linalg.norm(doc.embedding) + 1e-8)
            self.index.add_items(embedding.reshape(1, -1), np.array([label]))

    def add_documents_batch(self, docs: List[Document]) -> None:
        """Batch add documents for efficiency"""
        embeddings = []
        labels = []

        for doc in docs:
            if doc.embedding is None:
                doc.embedding = np.random.randn(self.embedding_dim)

            self.documents[doc.id] = doc

            if self.index is not None:
                label = self.next_label
                self.id_to_label[doc.id] = label
                self.label_to_id[label] = doc.id
                self.next_label += 1

                # Normalize embedding
                embedding = doc.embedding / (np.linalg.norm(doc.embedding) + 1e-8)
                embeddings.append(embedding)
                labels.append(label)

        if self.index is not None and embeddings:
            self.index.add_items(np.array(embeddings), np.array(labels))

    def retrieve(
        self, query_embedding: np.ndarray, k: int = 5
    ) -> List[Tuple[str, float]]:
        """Retrieve similar documents using HNSW"""
        if not self.documents:
            return []

        if self.index is not None:
            # Normalize query embedding
            query_norm = query_embedding / (np.linalg.norm(query_embedding) + 1e-8)

            # Search in HNSW index
            labels, distances = self.index.knn_query(
                query_norm.reshape(1, -1), k=min(k, len(self.documents))
            )

            # Convert distances to similarities (cosine distance to similarity)
            results = []
            for label, distance in zip(labels[0], distances[0]):
                if label >= 0:  # Valid label
                    doc_id = self.label_to_id[label]
                    similarity = 1 - distance  # Convert distance to similarity
                    results.append((doc_id, float(similarity)))

            return results
        else:
            # Fallback to brute-force if HNSW not available
            similarities = []
            for doc_id, doc in self.documents.items():
                norm_q = np.linalg.norm(query_embedding)
                norm_d = np.linalg.norm(doc.embedding)

                if norm_q > 0 and norm_d > 0:
                    sim = np.dot(query_embedding, doc.embedding) / (norm_q * norm_d)
                else:
                    sim = 0.0

                similarities.append((doc_id, float(sim)))

            similarities.sort(key=lambda x: x[1], reverse=True)
            return similarities[:k]

    def save(self, path: str) -> None:
        """Save index to disk"""
        os.makedirs(path, exist_ok=True)

        if self.index is not None:
            self.index.save_index(os.path.join(path, "hnsw.index"))

        # Save metadata as JSON (no pickle)
        metadata = {
            "documents": {
                doc_id: serialize_document(doc)
                for doc_id, doc in self.documents.items()
            },
            "id_to_label": self.id_to_label,
            "label_to_id": {
                str(label): doc_id for label, doc_id in self.label_to_id.items()
            },
            "next_label": self.next_label,
            "embedding_dim": self.embedding_dim,
            "max_elements": self.max_elements,
        }

        with open(os.path.join(path, "metadata.json"), "w", encoding="utf-8") as f:
            json.dump(metadata, f, ensure_ascii=True)

    def load(self, path: str) -> None:
        """Load index from disk"""
        if self.index is not None:
            self.index.load_index(os.path.join(path, "hnsw.index"))

        # Load metadata
        with open(os.path.join(path, "metadata.json"), "r", encoding="utf-8") as f:
            metadata = json.load(f)

        self.documents = {
            doc_id: deserialize_document(doc_data)
            for doc_id, doc_data in metadata["documents"].items()
        }
        self.id_to_label = {
            k: int(v) if isinstance(v, str) and v.isdigit() else v
            for k, v in metadata["id_to_label"].items()
        }
        self.label_to_id = {
            int(label): doc_id for label, doc_id in metadata["label_to_id"].items()
        }
        self.next_label = metadata["next_label"]


class VectorStore:
    """Simple in-memory vector store (can replace with ChromaDB)"""

    def __init__(self, embedding_dim: int = 384):
        self.documents: Dict[str, Document] = {}
        self.embeddings: Dict[str, np.ndarray] = {}
        self.embedding_dim = embedding_dim

    def add_document(self, doc: Document) -> None:
        """Add document to store"""
        if doc.embedding is None:
            doc.embedding = np.random.randn(self.embedding_dim)

        self.documents[doc.id] = doc
        self.embeddings[doc.id] = doc.embedding

    def retrieve(
        self, query_embedding: np.ndarray, k: int = 5
    ) -> List[Tuple[str, float]]:
        """Retrieve similar documents"""
        if not self.embeddings:
            return []

        # Cosine similarity
        similarities = []
        for doc_id, doc_embedding in self.embeddings.items():
            norm_q = np.linalg.norm(query_embedding)
            norm_d = np.linalg.norm(doc_embedding)

            if norm_q > 0 and norm_d > 0:
                sim = np.dot(query_embedding, doc_embedding) / (norm_q * norm_d)
            else:
                sim = 0.0

            similarities.append((doc_id, float(sim)))

        # Sort by similarity
        similarities.sort(key=lambda x: x[1], reverse=True)
        return similarities[:k]


class RAGAnalyzer:
    """Retrieval-Augmented Generation for MAPE-K"""

    def __init__(
        self,
        embedding_dim: int = 384,
        use_langchain: bool = True,
        use_hnsw: bool = True,
        persist_dir: Optional[str] = None,
    ):
        """
        Initialize RAG analyzer

        Args:
            embedding_dim: Dimension of embeddings
            use_langchain: Use LangChain if available
            use_hnsw: Use HNSW vector store if available
            persist_dir: Directory to persist HNSW index
        """
        self.embedding_dim = embedding_dim
        self.use_langchain = use_langchain and LANGCHAIN_AVAILABLE
        self.use_hnsw = use_hnsw and HNSWLIB_AVAILABLE
        self.persist_dir = persist_dir

        # Use HNSW if available, otherwise fall back to simple VectorStore
        if self.use_hnsw:
            self.vector_store = HNSWVectorStore(
                embedding_dim=embedding_dim, persist_dir=persist_dir
            )
        else:
            self.vector_store = VectorStore(embedding_dim)

        self.query_history: List[Dict] = []
        self.index_stats = {
            "documents_indexed": 0,
            "last_batch_size": 0,
            "retrieval_times": [],
        }

        if self.use_langchain:
            try:
                self.embeddings = HuggingFaceEmbeddings(model_name="all-MiniLM-L6-v2")
            except Exception as e:
                print(f"Warning: LangChain embeddings not available: {e}")
                self.use_langchain = False

        self.text_splitter = (
            RecursiveCharacterTextSplitter(chunk_size=500, chunk_overlap=50)
            if self.use_langchain
            else None
        )

    async def index_knowledge(self, knowledge_entries: List[Dict[str, Any]]) -> int:
        """
        Index knowledge entries for retrieval

        Args:
            knowledge_entries: List of knowledge entries from Knowledge module

        Returns:
            Number of documents indexed
        """
        documents = []

        for i, entry in enumerate(knowledge_entries):
            if isinstance(entry, Document):
                doc = Document(
                    id=entry.id or f"knowledge_{i}_{int(time.time())}",
                    content=entry.content,
                    metadata=entry.metadata or {},
                    embedding=entry.embedding,
                    timestamp=entry.timestamp or datetime.now(),
                )
                content = doc.content
            else:
                content = str(entry.get("insight", ""))
                # Create document
                doc = Document(
                    id=f"knowledge_{i}_{entry.get('timestamp', 'unknown')}",
                    content=content,
                    metadata=entry,
                    timestamp=datetime.now(),
                )

            # Generate embedding
            if doc.embedding is None and self.use_langchain:
                try:
                    embedding = self.embeddings.embed_query(content)
                    doc.embedding = np.array(embedding)
                except Exception:
                    doc.embedding = np.random.randn(self.embedding_dim)
            elif doc.embedding is None:
                doc.embedding = np.random.randn(self.embedding_dim)

            documents.append(doc)

        # Batch add for efficiency
        if self.use_hnsw and hasattr(self.vector_store, "add_documents_batch"):
            self.vector_store.add_documents_batch(documents)
        else:
            for doc in documents:
                self.vector_store.add_document(doc)

        indexed = len(documents)
        self.index_stats["documents_indexed"] += indexed
        self.index_stats["last_batch_size"] = indexed

        return indexed

    async def retrieve_context(
        self, query: str, k: int = 5, threshold: float = 0.3
    ) -> RetrievalResult:
        """
        Retrieve relevant context for a query

        Args:
            query: Query string
            k: Number of documents to retrieve
            threshold: Minimum similarity threshold

        Returns:
            RetrievalResult with documents and similarities
        """
        start_time = time.time()

        # Generate query embedding
        if self.use_langchain:
            try:
                query_emb = self.embeddings.embed_query(query)
                query_embedding = np.array(query_emb)
            except Exception:
                query_embedding = np.random.randn(self.embedding_dim)
        else:
            query_embedding = np.random.randn(self.embedding_dim)

        # Retrieve similar documents
        results = self.vector_store.retrieve(query_embedding, k)

        # Filter by threshold
        documents = []
        similarities = []

        for doc_id, similarity in results:
            if similarity >= threshold:
                doc = self.vector_store.documents[doc_id]
                documents.append(doc)
                similarities.append(similarity)

        retrieval_time_ms = (time.time() - start_time) * 1000
        record_rag_retrieval(retrieval_time_ms, len(documents))

        # Track retrieval time
        self.index_stats["retrieval_times"].append(retrieval_time_ms)
        # Keep only last 100 measurements
        if len(self.index_stats["retrieval_times"]) > 100:
            self.index_stats["retrieval_times"] = self.index_stats["retrieval_times"][
                -100:
            ]

        # Store query
        self.query_history.append(
            {
                "query": query,
                "timestamp": datetime.now(),
                "results_count": len(documents),
                "latency_ms": retrieval_time_ms,
            }
        )

        return RetrievalResult(
            documents=documents,
            similarities=similarities,
            query=query,
            timestamp=datetime.now(),
        )

    async def augment_analysis(
        self, current_analysis: Dict[str, Any], query: str
    ) -> Dict[str, Any]:
        """
        Augment current analysis with retrieved context

        Args:
            current_analysis: Original analysis from Analyzer
            query: Query for context retrieval

        Returns:
            Augmented analysis with historical context
        """
        # Retrieve context
        context = await self.retrieve_context(query, k=3)

        # Augment analysis
        augmented = {
            **current_analysis,
            "rag": {
                "context_documents": len(context.documents),
                "average_similarity": (
                    float(np.mean(context.similarities))
                    if context.similarities
                    else 0.0
                ),
                "context_insights": [
                    {
                        "content": doc.content[:200],
                        "similarity": float(sim),
                        "timestamp": doc.metadata.get("timestamp", "unknown"),
                    }
                    for doc, sim in zip(context.documents, context.similarities)
                ],
                "augmentation_timestamp": context.timestamp.isoformat(),
            },
        }

        return augmented

    def get_stats(self) -> Dict[str, Any]:
        """Get RAG statistics"""
        avg_retrieval_time = (
            float(np.mean(self.index_stats["retrieval_times"]))
            if self.index_stats["retrieval_times"]
            else 0.0
        )

        return {
            "documents_indexed": len(self.vector_store.documents),
            "queries_processed": len(self.query_history),
            "embedding_dim": self.embedding_dim,
            "langchain_enabled": self.use_langchain,
            "hnsw_enabled": self.use_hnsw,
            "vector_store_type": "HNSW" if self.use_hnsw else "Simple",
            "last_batch_size": self.index_stats["last_batch_size"],
            "avg_retrieval_time_ms": avg_retrieval_time,
            "total_retrieval_queries": len(self.index_stats["retrieval_times"]),
        }

    def save_index(self, path: Optional[str] = None) -> None:
        """Save HNSW index to disk"""
        if path is None:
            path = self.persist_dir

        if path is None:
            raise ValueError("No persist directory specified")

        if self.use_hnsw and hasattr(self.vector_store, "save"):
            self.vector_store.save(path)

    def load_index(self, path: Optional[str] = None) -> None:
        """Load HNSW index from disk"""
        if path is None:
            path = self.persist_dir

        if path is None:
            raise ValueError("No persist directory specified")

        if self.use_hnsw and hasattr(self.vector_store, "load"):
            self.vector_store.load(path)


# Example usage
async def example_rag_workflow():
    """Example of RAG workflow"""
    rag = RAGAnalyzer()

    # Index knowledge
    knowledge = [
        {
            "insight": "Network latency spike detected at 14:30",
            "timestamp": "2026-01-10",
        },
        {"insight": "API response time degradation", "timestamp": "2026-01-10"},
        {"insight": "Memory usage anomaly", "timestamp": "2026-01-11"},
    ]

    indexed = await rag.index_knowledge(knowledge)
    print(f"Indexed {indexed} documents")

    # Retrieve context
    query = "response time performance"
    result = await rag.retrieve_context(query, k=2)
    print(f"Retrieved {len(result.documents)} documents for query: {query}")

    return rag


if __name__ == "__main__":
    # Example
    rag = RAGAnalyzer()
    print(f"RAG Analyzer initialized. LangChain: {rag.use_langchain}")
