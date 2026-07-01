"""RAG Analyzer — Retrieval-Augmented Generation for mesh context retrieval."""

from __future__ import annotations

import time
from dataclasses import dataclass, field
from typing import Any


class Document:
    """A document with content and metadata for RAG retrieval."""

    def __init__(self, id: str, content: str, metadata: dict | None = None) -> None:
        self.id = id
        self.content = content
        self.metadata = metadata or {}


@dataclass
class RetrievalResult:
    """Result of a retrieval operation.

    Behaves as a list-of-Documents via __iter__/__len__/__getitem__
    and as an object with .documents attribute.
    """
    documents: list[Document] = field(default_factory=list)
    query: str = ""
    total_results: int = 0

    def __len__(self) -> int:
        return len(self.documents)

    def __getitem__(self, idx: int) -> Document:
        return self.documents[idx]

    def __iter__(self):
        return iter(self.documents)

    def __class_getitem__(cls, item):
        return list[item]  # noqa


class RAGAnalyzer:
    """In-memory RAG analyzer with simple keyword matching.

    Supports use_langchain and use_hnsw kwargs for test compat (ignored).
    """

    def __init__(
        self,
        config: dict | None = None,
        use_langchain: bool = False,
        use_hnsw: bool = False,
    ) -> None:
        self.config = config or {}
        self.use_langchain = use_langchain
        self.use_hnsw = use_hnsw
        self._documents: dict[str, Document] = {}
        self._last_query = ""

    async def index_knowledge(self, documents: list[Document]) -> int:
        """Index a list of documents. Returns the number indexed."""
        for doc in documents:
            self._documents[doc.id] = doc
        return len(documents)

    async def retrieve_context(
        self,
        query: str,
        k: int = 5,
        threshold: float = 0.0,
    ) -> RetrievalResult:
        """Retrieve top-k documents matching the query."""
        self._last_query = query
        query_lower = query.lower()
        scored: list[tuple[float, Document]] = []
        for doc in self._documents.values():
            score = self._compute_relevance(query_lower, doc.content.lower())
            if score > threshold:
                scored.append((score, doc))
        scored.sort(key=lambda x: x[0], reverse=True)
        matched = [doc for _, doc in scored[:k]]
        return RetrievalResult(documents=matched, query=query, total_results=len(matched))

    def get_stats(self) -> dict[str, Any]:
        return {"documents_indexed": len(self._documents)}

    async def retrieve(self, query: str, top_k: int = 5) -> list[Document]:
        """Alias returning plain list."""
        result = await self.retrieve_context(query, top_k)
        return result.documents

    def get_thinking_status(self) -> dict[str, Any]:
        return {
            "thinking": {
                "profile": {"role": "documentation"},
                "state": "active",
                "documents_indexed": len(self._documents),
            }
        }

    def _compute_relevance(self, query: str, content: str) -> float:
        query_words = set(query.split())
        content_words = set(content.split())
        if not query_words:
            return 0.0
        overlap = len(query_words & content_words)
        return overlap / len(query_words)
