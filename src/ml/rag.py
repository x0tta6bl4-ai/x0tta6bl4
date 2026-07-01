"""Stub: RAG Analyzer (purged in honest mode).

Original module was removed during honest-mode cleanup.
This stub allows dependent integration tests to import successfully.
"""

from __future__ import annotations

from typing import Any


class Document:
    def __init__(self, content: str, metadata: dict | None = None) -> None:
        self.content = content
        self.metadata = metadata or {}


class RAGAnalyzer:
    """Stub — was removed during honest-mode cleanup."""

    def __init__(self, config: dict | None = None) -> None:
        self.config = config or {}

    async def retrieve(self, query: str, top_k: int = 5) -> list[Document]:
        return []
