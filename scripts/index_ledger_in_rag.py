#!/usr/bin/env python3
"""
Скрипт для индексирования CONTINUITY.md в RAG pipeline

Использование:
    python scripts/index_ledger_in_rag.py
"""

import sys
import asyncio
from pathlib import Path

PROJECT_ROOT = Path(__file__).parent.parent
sys.path.insert(0, str(PROJECT_ROOT))

from src.ledger.rag_search import LedgerRAGSearch
import logging

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)


async def index_ledger():
    """Индексирование CONTINUITY.md в RAG pipeline"""
    logger.info("🚀 Индексирование CONTINUITY.md в RAG pipeline...")
    
    # Инициализация LedgerRAGSearch
    ledger_rag = LedgerRAGSearch()
    
    # Индексирование
    success = await ledger_rag.index_ledger()
    
    if success:
        logger.info("✅ CONTINUITY.md успешно проиндексирован")
        return True
    else:
        logger.error("❌ Не удалось проиндексировать CONTINUITY.md")
        return False


if __name__ == "__main__":
    success = asyncio.run(index_ledger())
    sys.exit(0 if success else 1)

