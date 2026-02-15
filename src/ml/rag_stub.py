"""
Lightweight RAG stub for staging environment
Full implementation requires torch, transformers, and other heavy ML dependencies
"""

from dataclasses import dataclass
from typing import Any, Dict, List, Optional


@dataclass
class Document:
    """Lightweight document representation"""

    id: str
    content: str
    metadata: Optional[Dict[str, Any]] = None


class VectorStore:
    """Lightweight vector store stub"""

    def __init__(self):
        self.documents: Dict[str, Document] = {}

    def add_documents(self, docs: List[Document]) -> None:
        """Add documents to store"""
        for doc in docs:
            self.documents[doc.id] = doc

    def search(self, query: str, k: int = 5) -> List[Document]:
        """Simple string matching search"""
        results = []
        query_lower = query.lower()
        for doc in self.documents.values():
            if query_lower in doc.content.lower():
                results.append(doc)
        return results[:k]


class RAGAnalyzer:
    """Lightweight RAG analyzer stub"""

    def __init__(self, vector_store: Optional[VectorStore] = None):
        self.vector_store = vector_store or VectorStore()

    async def analyze(self, query: str) -> Dict[str, Any]:
        """Analyze with RAG"""
        docs = self.vector_store.search(query)
        return {
            "query": query,
            "documents_found": len(docs),
            "relevant_docs": [d.id for d in docs],
        }
