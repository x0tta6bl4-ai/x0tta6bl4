"""
Ledger Graph Builder and Feature Extractor.
"""
from __future__ import annotations

import logging
import re
from datetime import datetime
from pathlib import Path
from typing import Any, Dict, List, Optional
from .models import DriftResult

try:
    import numpy as np
    NUMPY_AVAILABLE = True
except ImportError:
    NUMPY_AVAILABLE = False

logger = logging.getLogger(__name__)

PROJECT_ROOT = Path(__file__).parent.parent.parent.parent
CONTINUITY_FILE = PROJECT_ROOT / "CONTINUITY.md"

class LedgerGraphBuilder:
    """Класс для построения графа леджера и анализа структуры документации."""

    def __init__(self, continuity_file: Path = CONTINUITY_FILE):
        self.continuity_file = continuity_file

    def build_ledger_graph(self) -> Dict[str, Any]:
        """
        Построение граф представления ledger.
        Разделы = узлы, зависимости = рёбра.
        """
        if not self.continuity_file.exists():
            logger.error(f"❌ Файл не найден: {self.continuity_file}")
            return {"nodes": [], "edges": [], "sections": []}

        content = self.continuity_file.read_text(encoding="utf-8")

        # Парсинг разделов
        sections = []
        current_section = None

        for line in content.split("\n"):
            if line.startswith("## "):
                if current_section:
                    sections.append(current_section)
                current_section = {
                    "title": line.replace("## ", "").strip(),
                    "content": line,
                    "dependencies": [],
                }
            elif current_section:
                current_section["content"] += "\n" + line

                # Обнаружение зависимостей
                if "State" in line and "Done" in line:
                    current_section["dependencies"].append("Done")
                if "Now" in line and "Next" in line:
                    current_section["dependencies"].extend(["Now", "Next"])

        if current_section:
            sections.append(current_section)

        # Построение графа
        nodes = []
        edges = []

        for i, section in enumerate(sections):
            nodes.append(
                {
                    "id": i,
                    "title": section["title"],
                    "content_length": len(section["content"]),
                }
            )

            # Добавление рёбер для зависимостей
            for dep in section["dependencies"]:
                dep_idx = next(
                    (j for j, s in enumerate(sections) if s["title"] == dep), None
                )
                if dep_idx is not None:
                    edges.append({"source": dep_idx, "target": i, "type": "depends_on"})

        logger.info(f"📊 Построен граф: {len(nodes)} узлов, {len(edges)} рёбер")
        return {"nodes": nodes, "edges": edges, "sections": sections}


class LedgerFeatureExtractor:
    """Класс для извлечения признаков узлов графа и статистического анализа аномалий."""

    def __init__(self, continuity_file: Path = CONTINUITY_FILE):
        self.continuity_file = continuity_file

    def extract_node_features(
        self,
        node: Dict[str, Any],
        graph: Dict[str, Any],
        all_drifts: List[DriftResult],
    ) -> Dict[str, float]:
        """Извлечение признаков для конкретного узла."""
        title = str(node.get("title", ""))
        node_id = node.get("id")
        in_degree = len([e for e in graph["edges"] if e["target"] == node_id])
        out_degree = len([e for e in graph["edges"] if e["source"] == node_id])
        section_content = self._section_content(title, graph)
        drift_count = len([d for d in all_drifts if d.section == title])

        return {
            "content_length": float(node.get("content_length", 0)) / 1000.0,
            "title_length": float(len(title)) / 100.0,
            "in_degree": float(in_degree) / 10.0,
            "out_degree": float(out_degree) / 10.0,
            "last_update_age": self._section_last_update_age(section_content),
            "drift_count": float(drift_count) / 10.0,
            "complexity": self._section_complexity_score(
                section_content,
                in_degree,
                out_degree,
            ),
            "importance": self._section_importance_score(
                title,
                in_degree,
                out_degree,
                drift_count,
            ),
        }

    @staticmethod
    def _section_content(title: str, graph: Dict[str, Any]) -> str:
        for section in graph.get("sections", []):
            if section.get("title") == title:
                return str(section.get("content", ""))
        return ""

    def _section_last_update_age(self, section_content: str) -> float:
        dates = []
        for match in re.findall(r"\b20\d{2}-\d{2}-\d{2}(?:[T ][0-9:.+-]+Z?)?", section_content):
            parsed = self._parse_datetime(match)
            if parsed is not None:
                dates.append(parsed)

        if dates:
            reference = max(dates)
        elif self.continuity_file.exists():
            reference = datetime.utcfromtimestamp(self.continuity_file.stat().st_mtime)
        else:
            return 1.0

        age_days = max(0.0, (datetime.utcnow() - reference).total_seconds() / 86400.0)
        return min(1.0, age_days / 365.0)

    @staticmethod
    def _parse_datetime(raw_value: str) -> Optional[datetime]:
        try:
            parsed = datetime.fromisoformat(raw_value.replace("Z", "+00:00"))
            if parsed.tzinfo is not None:
                parsed = parsed.astimezone().replace(tzinfo=None)
            return parsed
        except ValueError:
            return None

    @staticmethod
    def _section_complexity_score(
        section_content: str,
        in_degree: int,
        out_degree: int,
    ) -> float:
        content_length = len(section_content)
        line_count = section_content.count("\n") + (1 if section_content else 0)
        heading_count = section_content.count("### ")
        score = (
            content_length / 5000.0
            + line_count / 200.0
            + heading_count / 20.0
            + (in_degree + out_degree) / 20.0
        )
        return min(1.0, score)

    @staticmethod
    def _section_importance_score(
        title: str,
        in_degree: int,
        out_degree: int,
        drift_count: int,
    ) -> float:
        important_keywords = (
            "state",
            "now",
            "next",
            "done",
            "metric",
            "security",
            "production",
            "evidence",
        )
        keyword_bonus = 0.2 if any(k in title.lower() for k in important_keywords) else 0.0
        score = (
            0.05
            + keyword_bonus
            + min(0.45, (in_degree + out_degree) / 10.0)
            + min(0.30, drift_count / 3.0)
        )
        return min(1.0, score)
