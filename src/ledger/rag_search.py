"""
Ledger RAG Search Integration

Использование существующего RAG pipeline для semantic search в CONTINUITY.md
"""

import asyncio
import logging
from dataclasses import dataclass
from pathlib import Path
from typing import Any, Dict, List, Optional

from src.rag.chunker import ChunkingStrategy, DocumentChunker
from src.rag.pipeline import RAGPipeline, RAGResult
from src.storage.vector_index import VectorIndex

logger = logging.getLogger(__name__)

PROJECT_ROOT = Path(__file__).parent.parent.parent
CONTINUITY_FILE = PROJECT_ROOT / "CONTINUITY.md"


@dataclass
class LedgerSearchResult:
    """Результат поиска в ledger"""

    query: str
    results: List[Dict[str, Any]]
    total_results: int
    search_time_ms: float
    metadata: Dict[str, Any] = None


class LedgerRAGSearch:
    """
    Semantic search в Continuity Ledger через существующий RAG pipeline.

    Использует:
    - RAGPipeline для semantic search
    - VectorIndex (HNSW) для быстрого поиска
    - DocumentChunker для разбиения на chunks
    """

    def __init__(
        self,
        continuity_file: Path = CONTINUITY_FILE,
        vector_index: Optional[VectorIndex] = None,
        top_k: int = 10,
        enable_reranking: bool = True,
    ):
        """
        Инициализация Ledger RAG Search.

        Args:
            continuity_file: Путь к CONTINUITY.md
            vector_index: VectorIndex instance (создается новый если None)
            top_k: Количество результатов для возврата
            enable_reranking: Включить re-ranking через CrossEncoder
        """
        self.continuity_file = continuity_file
        self.top_k = top_k

        # Инициализация RAG pipeline с существующими компонентами
        self.rag = RAGPipeline(
            vector_index=vector_index, top_k=top_k, enable_reranking=enable_reranking
        )

        self._indexed = False
        logger.info(f"✅ LedgerRAGSearch инициализирован (file: {continuity_file})")

    def is_indexed(self) -> bool:
        """Проверка, проиндексирован ли ledger"""
        return self._indexed

    async def index_ledger(self, force: bool = False) -> bool:
        """
        Индексирование CONTINUITY.md в RAG pipeline.

        Args:
            force: Принудительная переиндексация даже если уже проиндексировано

        Returns:
            True если успешно
        """
        if self._indexed and not force:
            logger.info("✅ Ledger уже проиндексирован")
            return True

        if not self.continuity_file.exists():
            logger.error(f"❌ Файл не найден: {self.continuity_file}")
            return False

        logger.info(f"📖 Индексирование {self.continuity_file}...")

        try:
            content = self.continuity_file.read_text(encoding="utf-8")

            # Разбиение на разделы (по заголовкам ##)
            sections = self._parse_sections(content)

            logger.info(f"📚 Найдено разделов: {len(sections)}")

            # Индексирование каждого раздела
            total_chunks = 0
            for i, section in enumerate(sections, 1):
                logger.info(
                    f"  [{i}/{len(sections)}] Индексирование: {section['title']}"
                )

                # Добавляем раздел в RAG
                chunk_ids = self.rag.add_document(
                    text=section["content"],
                    document_id=f"continuity_{section['title'].lower().replace(' ', '_').replace('/', '_')}",
                    metadata={
                        "title": section["title"],
                        "section": section["title"],
                        "source": "CONTINUITY.md",
                        "section_index": i,
                    },
                )

                total_chunks += len(chunk_ids)
                logger.info(f"     ✅ Индексировано chunks: {len(chunk_ids)}")

            self._indexed = True
            logger.info(f"✅ CONTINUITY.md успешно проиндексирован")
            logger.info(f"📊 Всего разделов: {len(sections)}, chunks: {total_chunks}")

            return True

        except Exception as e:
            logger.error(f"❌ Ошибка при индексировании: {e}", exc_info=True)
            return False

    def _parse_sections(self, content: str) -> List[Dict[str, str]]:
        """
        Разбор CONTINUITY.md на разделы.

        Args:
            content: Содержимое файла

        Returns:
            Список разделов с title и content
        """
        sections = []
        current_section = []
        current_title = None

        for line in content.split("\n"):
            if line.startswith("## "):
                # Сохраняем предыдущий раздел
                if current_title and current_section:
                    sections.append(
                        {"title": current_title, "content": "\n".join(current_section)}
                    )
                # Начинаем новый раздел
                current_title = line.replace("## ", "").strip()
                current_section = [line]
            else:
                current_section.append(line)

        # Сохраняем последний раздел
        if current_title and current_section:
            sections.append(
                {"title": current_title, "content": "\n".join(current_section)}
            )

        return sections

    async def query(
        self, question: str, top_k: Optional[int] = None
    ) -> LedgerSearchResult:
        """
        Semantic search в ledger через RAG.

        Args:
            question: Вопрос на естественном языке
            top_k: Количество результатов (используется self.top_k если None)

        Returns:
            LedgerSearchResult с результатами поиска
        """
        import time

        start_time = time.time()

        # Убеждаемся, что ledger проиндексирован
        if not self._indexed:
            logger.warning("⚠️ Ledger не проиндексирован. Индексирую...")
            await self.index_ledger()

        # Выполнение запроса через RAG
        try:
            # Используем метод retrieve (синхронный) через asyncio
            rag_result = await asyncio.to_thread(
                self.rag.retrieve, question, top_k=top_k or self.top_k
            )

            # Преобразование результатов в формат LedgerSearchResult
            results = []
            for i, chunk in enumerate(rag_result.retrieved_chunks):
                # Получаем score из списка scores
                score = rag_result.scores[i] if i < len(rag_result.scores) else 0.0

                results.append(
                    {
                        "text": chunk.text,
                        "score": score,
                        "metadata": (
                            chunk.metadata if hasattr(chunk, "metadata") else {}
                        ),
                        "section": (
                            chunk.metadata.get("title", "Unknown")
                            if hasattr(chunk, "metadata") and chunk.metadata
                            else "Unknown"
                        ),
                    }
                )

            search_time_ms = (time.time() - start_time) * 1000

            return LedgerSearchResult(
                query=question,
                results=results,
                total_results=len(results),
                search_time_ms=search_time_ms,
                metadata={
                    "retrieval_time_ms": rag_result.retrieval_time_ms,
                    "rerank_time_ms": rag_result.rerank_time_ms,
                },
            )

        except Exception as e:
            logger.error(f"❌ Ошибка при поиске: {e}", exc_info=True)
            search_time_ms = (time.time() - start_time) * 1000
            return LedgerSearchResult(
                query=question,
                results=[],
                total_results=0,
                search_time_ms=search_time_ms,
                metadata={"error": str(e)},
            )

    async def search(self, query: str, top_k: Optional[int] = None) -> Dict[str, Any]:
        """
        Удобный метод для поиска (возвращает dict вместо dataclass).

        Args:
            query: Вопрос на естественном языке
            top_k: Количество результатов

        Returns:
            Dict с результатами поиска
        """
        result = await self.query(query, top_k)
        return {
            "query": result.query,
            "results": result.results,
            "total_results": result.total_results,
            "search_time_ms": result.search_time_ms,
            "metadata": result.metadata,
        }


# Singleton instance для использования в API
_ledger_rag_instance: Optional[LedgerRAGSearch] = None


def get_ledger_rag() -> LedgerRAGSearch:
    """Получить singleton instance LedgerRAGSearch"""
    global _ledger_rag_instance
    if _ledger_rag_instance is None:
        _ledger_rag_instance = LedgerRAGSearch()
    return _ledger_rag_instance
