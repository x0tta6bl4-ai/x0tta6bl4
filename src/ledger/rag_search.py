"""
Ledger RAG Search Integration

Использование существующего RAG pipeline для semantic search в CONTINUITY.md
"""

import asyncio
import hashlib
import json
import logging
from dataclasses import dataclass
from pathlib import Path
from typing import Any, Dict, List, Optional

from src.rag.pipeline import RAGPipeline
from src.storage.vector_index import VectorIndex

logger = logging.getLogger(__name__)

PROJECT_ROOT = Path(__file__).parent.parent.parent
CONTINUITY_FILE = PROJECT_ROOT / "CONTINUITY.md"
VERIFICATION_ROOT = PROJECT_ROOT / "docs" / "verification"
VERIFICATION_SUFFIXES = {".md", ".json", ".jsonl"}
EVENT_TRACE_SOURCE = "EventBus"
EVENT_TRACE_SOURCE_CLASS = "event_trace"
EVENT_TRACE_RELATIVE_PATH = ".agent_coordination/events.log"


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
        verification_root: Path = VERIFICATION_ROOT,
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
        self.verification_root = verification_root
        self.top_k = top_k

        # Инициализация RAG pipeline с существующими компонентами
        self.rag = RAGPipeline(
            vector_index=vector_index, top_k=top_k, enable_reranking=enable_reranking
        )

        self._indexed = False
        self._verification_indexed = False
        self._verification_indexed_files = 0
        self._verification_indexed_chunks = 0
        self._event_trace_indexed = False
        self._event_trace_indexed_events = 0
        self._event_trace_indexed_chunks = 0
        self._event_trace_indexed_event_ids: set[str] = set()
        logger.info(f"✅ LedgerRAGSearch инициализирован (file: {continuity_file})")

    def is_indexed(self) -> bool:
        """Проверка, проиндексирован ли ledger"""
        return self._indexed

    def is_verification_indexed(self) -> bool:
        """Проверка, проиндексированы ли verification artifacts."""
        return self._verification_indexed

    def is_event_trace_indexed(self) -> bool:
        """Проверка, проиндексированы ли EventBus trace artifacts."""
        return self._event_trace_indexed

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
            logger.info("✅ CONTINUITY.md успешно проиндексирован")
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

    def _iter_verification_files(self) -> List[Path]:
        """Return text-like verification artifacts that can be indexed by RAG."""
        if not self.verification_root.exists():
            return []
        return sorted(
            path
            for path in self.verification_root.rglob("*")
            if path.is_file() and path.suffix.lower() in VERIFICATION_SUFFIXES
        )

    def _relative_evidence_path(self, path: Path) -> str:
        try:
            return path.relative_to(PROJECT_ROOT).as_posix()
        except ValueError:
            relative = path.relative_to(self.verification_root).as_posix()
            return f"docs/verification/{relative}"

    def verification_evidence_status(self) -> Dict[str, Any]:
        """Summarize verification artifacts available for runtime indexing."""
        files = self._iter_verification_files()
        by_suffix: Dict[str, int] = {}
        for path in files:
            suffix = path.suffix.lower()
            by_suffix[suffix] = by_suffix.get(suffix, 0) + 1

        latest_aliases = [
            self._relative_evidence_path(path)
            for path in files
            if "_LATEST" in path.name
        ]

        return {
            "verification_root": str(self.verification_root),
            "root_exists": self.verification_root.exists(),
            "indexable_files": len(files),
            "by_suffix": by_suffix,
            "latest_aliases": latest_aliases,
            "latest_alias_count": len(latest_aliases),
            "indexed": self._verification_indexed,
            "indexed_files": self._verification_indexed_files,
            "indexed_chunks": self._verification_indexed_chunks,
            "source": "docs/verification",
        }

    def event_trace_status(self) -> Dict[str, Any]:
        """Summarize EventBus trace artifacts indexed into runtime search."""
        return {
            "source": EVENT_TRACE_SOURCE,
            "source_class": EVENT_TRACE_SOURCE_CLASS,
            "relative_path": EVENT_TRACE_RELATIVE_PATH,
            "indexed": self._event_trace_indexed,
            "indexed_events": self._event_trace_indexed_events,
            "indexed_chunks": self._event_trace_indexed_chunks,
            "redacted": True,
        }

    def _verification_document_id(self, path: Path) -> str:
        relative = self._relative_evidence_path(path)
        digest = hashlib.sha1(relative.encode("utf-8")).hexdigest()[:12]
        safe_name = (
            relative.replace("/", "_")
            .replace(".", "_")
            .replace("-", "_")
            .replace(" ", "_")
        )
        return f"verification_{safe_name}_{digest}"

    def _verification_metadata(self, path: Path) -> Dict[str, Any]:
        relative = self._relative_evidence_path(path)
        return {
            "title": path.stem,
            "section": path.stem,
            "source": "docs/verification",
            "source_class": "verification_evidence",
            "relative_path": relative,
            "file_suffix": path.suffix.lower(),
            "latest_alias": "_LATEST" in path.name,
            "parent_run": (
                path.parent.name if path.parent != self.verification_root else None
            ),
        }

    async def index_verification_evidence(
        self, force: bool = False, max_files: Optional[int] = None
    ) -> bool:
        """
        Индексирование docs/verification artifacts в тот же RAG pipeline.

        This is intentionally explicit: normal ledger search keeps indexing
        CONTINUITY.md only unless callers request verification evidence too.
        """
        if self._verification_indexed and not force:
            logger.info("✅ Verification evidence уже проиндексирован")
            return True

        files = self._iter_verification_files()
        if max_files is not None:
            files = files[:max_files]

        if not files:
            logger.warning("⚠️ Verification evidence files not found")
            self._verification_indexed = False
            self._verification_indexed_files = 0
            self._verification_indexed_chunks = 0
            return False

        total_chunks = 0
        indexed_files = 0

        for path in files:
            try:
                content = path.read_text(encoding="utf-8", errors="replace")
            except OSError as exc:
                logger.warning(
                    "Skipping unreadable verification artifact %s: %s", path, exc
                )
                continue

            if not content.strip():
                continue

            chunk_ids = self.rag.add_document(
                text=content,
                document_id=self._verification_document_id(path),
                metadata=self._verification_metadata(path),
            )
            indexed_files += 1
            total_chunks += len(chunk_ids)

        self._verification_indexed = indexed_files > 0
        self._verification_indexed_files = indexed_files
        self._verification_indexed_chunks = total_chunks

        logger.info(
            "✅ Verification evidence indexed: files=%s chunks=%s",
            indexed_files,
            total_chunks,
        )
        return self._verification_indexed

    def _event_trace_document_id(self, event: Dict[str, Any]) -> str:
        event_id = str(event.get("event_id") or "unknown")
        digest = hashlib.sha1(event_id.encode("utf-8")).hexdigest()[:12]
        safe_id = (
            event_id.replace("/", "_")
            .replace(".", "_")
            .replace("-", "_")
            .replace(" ", "_")
        )
        return f"event_trace_{safe_id}_{digest}"

    def _event_trace_service_metadata(
        self,
        event: Dict[str, Any],
        trace_filter: Dict[str, Any],
    ) -> Dict[str, Optional[str]]:
        source_agent = event.get("source_agent")
        matched_service: Dict[str, Any] = {}
        for service in trace_filter.get("services") or []:
            if not isinstance(service, dict):
                continue
            service_source_agent = service.get("source_agent") or service.get(
                "service_name"
            )
            if service_source_agent == source_agent:
                matched_service = service
                break

        return {
            "service_name": trace_filter.get("service_name")
            or matched_service.get("service_name")
            or source_agent,
            "layer": trace_filter.get("layer") or matched_service.get("layer"),
            "entrypoint": matched_service.get("entrypoint"),
        }

    def _event_trace_metadata(
        self,
        event: Dict[str, Any],
        trace_filter: Dict[str, Any],
    ) -> Dict[str, Any]:
        service_metadata = self._event_trace_service_metadata(event, trace_filter)
        event_type = event.get("event_type")
        source_agent = event.get("source_agent")
        return {
            "title": f"EventBus {event_type} from {source_agent}",
            "section": f"{source_agent}:{event_type}",
            "source": EVENT_TRACE_SOURCE,
            "source_class": EVENT_TRACE_SOURCE_CLASS,
            "relative_path": EVENT_TRACE_RELATIVE_PATH,
            "event_id": event.get("event_id"),
            "event_type": event_type,
            "source_agent": source_agent,
            "service_name": service_metadata["service_name"],
            "layer": service_metadata["layer"],
            "entrypoint": service_metadata["entrypoint"],
            "redacted": event.get("redacted") is True,
        }

    def _event_trace_text(
        self,
        event: Dict[str, Any],
        trace_filter: Dict[str, Any],
    ) -> str:
        metadata = self._event_trace_metadata(event, trace_filter)
        payload = {
            "event_id": metadata["event_id"],
            "event_type": metadata["event_type"],
            "source_agent": metadata["source_agent"],
            "service_name": metadata["service_name"],
            "layer": metadata["layer"],
            "timestamp": event.get("timestamp"),
            "target_agents": event.get("target_agents"),
            "data": event.get("data"),
            "redacted": event.get("redacted") is True,
        }
        return json.dumps(payload, sort_keys=True, ensure_ascii=False, default=str)

    async def index_event_traces(
        self,
        trace_payload: Dict[str, Any],
        force: bool = False,
    ) -> bool:
        """Index redacted EventBus traces as runtime evidence for RAG search."""
        if trace_payload.get("redacted") is not True:
            logger.warning("Skipping EventBus traces without redacted=true")
            return False

        events = trace_payload.get("events") or []
        if not isinstance(events, list):
            logger.warning("Skipping malformed EventBus trace payload")
            return False

        trace_filter = trace_payload.get("filter") or {}
        indexed_events = 0
        indexed_chunks = 0

        for event in events:
            if not isinstance(event, dict):
                continue
            if event.get("redacted") is not True:
                logger.warning(
                    "Skipping EventBus trace without event-level redacted=true"
                )
                continue

            event_id = str(event.get("event_id") or "")
            if event_id and event_id in self._event_trace_indexed_event_ids and not force:
                continue

            document_id = self._event_trace_document_id(event)
            chunk_ids = self.rag.add_document(
                text=self._event_trace_text(event, trace_filter),
                document_id=document_id,
                metadata=self._event_trace_metadata(event, trace_filter),
            )
            if event_id:
                self._event_trace_indexed_event_ids.add(event_id)
            indexed_events += 1
            indexed_chunks += len(chunk_ids)

        self._event_trace_indexed = (
            self._event_trace_indexed or indexed_events > 0
        )
        self._event_trace_indexed_events = len(self._event_trace_indexed_event_ids)
        self._event_trace_indexed_chunks += indexed_chunks

        logger.info(
            "✅ EventBus traces indexed: events=%s chunks=%s",
            indexed_events,
            indexed_chunks,
        )
        return True

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
