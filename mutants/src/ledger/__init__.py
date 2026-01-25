"""
Ledger Integration Module

Интеграция Continuity Ledger с существующими технологиями проекта:
- RAG Pipeline для semantic search (Phase 1 - реализовано)
- GraphSAGE для drift detection (Phase 2 - будет реализовано)
- AI Agents для автообновления (Phase 3 - будет реализовано)
"""

from .rag_search import LedgerRAGSearch, get_ledger_rag

try:
    from .drift_detector import LedgerDriftDetector
except ImportError:
    LedgerDriftDetector = None

__all__ = [
    "LedgerRAGSearch",
    "get_ledger_rag"
]

if LedgerDriftDetector:
    __all__.append("LedgerDriftDetector")

