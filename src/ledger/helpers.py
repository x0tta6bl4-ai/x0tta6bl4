"""
Helper функции для работы с Continuity Ledger

Утилиты для парсинга, валидации и работы с ledger
"""

import logging
import re
from datetime import datetime
from pathlib import Path
from typing import Any, Dict, List, Optional, Tuple

logger = logging.getLogger(__name__)

PROJECT_ROOT = Path(__file__).parent.parent.parent
CONTINUITY_FILE = PROJECT_ROOT / "CONTINUITY.md"


def parse_sections(content: str) -> List[Dict[str, str]]:
    """
    Парсинг CONTINUITY.md на разделы.

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
        sections.append({"title": current_title, "content": "\n".join(current_section)})

    return sections


def find_metrics(content: str) -> List[Dict[str, Any]]:
    """
    Поиск метрик в ledger.

    Args:
        content: Содержимое файла

    Returns:
        Список найденных метрик
    """
    metrics = []

    # Паттерны для метрик
    patterns = [
        # "Metric: value unit"
        (r"([A-Za-z\s]+):\s*([<>]?[\d.]+)\s*(ms|s|%|MB|GB|KB)", "metric_value"),
        # "value unit (status)"
        (r"([<>]?[\d.]+)\s*(ms|s|%|MB|GB|KB)\s*(p\d+|✅|❌|⚠️)", "value_status"),
        # "Metric: value (VALIDATED)"
        (
            r"([A-Za-z\s]+):\s*([<>]?[\d.]+)\s*(ms|s|%|MB|GB|KB)\s*\(([^)]+)\)",
            "metric_validated",
        ),
    ]

    for pattern, pattern_type in patterns:
        matches = re.finditer(pattern, content, re.IGNORECASE)
        for match in matches:
            metrics.append(
                {
                    "type": pattern_type,
                    "match": match.group(0),
                    "position": match.start(),
                    "line": content[: match.start()].count("\n") + 1,
                }
            )

    return metrics


def find_unconfirmed(content: str) -> List[Dict[str, Any]]:
    """
    Поиск UNCONFIRMED меток в ledger.

    Args:
        content: Содержимое файла

    Returns:
        Список найденных UNCONFIRMED меток
    """
    unconfirmed = []

    # Паттерн для UNCONFIRMED
    pattern = r"UNCONFIRMED"
    matches = re.finditer(pattern, content, re.IGNORECASE)

    for match in matches:
        # Получаем контекст (50 символов до и после)
        start = max(0, match.start() - 50)
        end = min(len(content), match.end() + 50)
        context = content[start:end]

        # Пытаемся найти раздел
        section_start = content.rfind("## ", 0, match.start())
        section_name = "Unknown"
        if section_start != -1:
            section_line = content[section_start : match.start()].split("\n")[0]
            section_name = section_line.replace("## ", "").strip()

        unconfirmed.append(
            {
                "position": match.start(),
                "line": content[: match.start()].count("\n") + 1,
                "section": section_name,
                "context": context,
            }
        )

    return unconfirmed


def find_todos(content: str) -> List[Dict[str, Any]]:
    """
    Поиск TODO/FIXME/XXX в ledger.

    Args:
        content: Содержимое файла

    Returns:
        Список найденных TODO/FIXME/XXX
    """
    todos = []

    # Паттерн для TODO/FIXME/XXX
    pattern = r"(TODO|FIXME|XXX):?\s*(.+?)(?:\n|$)"
    matches = re.finditer(pattern, content, re.IGNORECASE | re.MULTILINE)

    for match in matches:
        todo_type = match.group(1).upper()
        todo_text = match.group(2).strip()

        # Пытаемся найти раздел
        section_start = content.rfind("## ", 0, match.start())
        section_name = "Unknown"
        if section_start != -1:
            section_line = content[section_start : match.start()].split("\n")[0]
            section_name = section_line.replace("## ", "").strip()

        todos.append(
            {
                "type": todo_type,
                "text": todo_text,
                "position": match.start(),
                "line": content[: match.start()].count("\n") + 1,
                "section": section_name,
            }
        )

    return todos


def find_dates(content: str) -> List[Dict[str, Any]]:
    """
    Поиск дат в ledger.

    Args:
        content: Содержимое файла

    Returns:
        Список найденных дат
    """
    dates = []

    # Паттерн для дат (YYYY-MM-DD, DD.MM.YYYY, и т.д.)
    patterns = [
        (r"\d{4}-\d{2}-\d{2}", "ISO"),
        (r"\d{2}\.\d{2}\.\d{4}", "DD.MM.YYYY"),
        (r"\d{2}/\d{2}/\d{4}", "MM/DD/YYYY"),
        (
            r"(Jan|Feb|Mar|Apr|May|Jun|Jul|Aug|Sep|Oct|Nov|Dec)\s+\d{1,2},?\s+\d{4}",
            "Month DD, YYYY",
        ),
    ]

    for pattern, format_type in patterns:
        matches = re.finditer(pattern, content, re.IGNORECASE)
        for match in matches:
            dates.append(
                {
                    "date": match.group(0),
                    "format": format_type,
                    "position": match.start(),
                    "line": content[: match.start()].count("\n") + 1,
                }
            )

    return dates


def validate_ledger_structure(content: str) -> Dict[str, Any]:
    """
    Валидация структуры ledger.

    Проверяет наличие обязательных разделов и их структуру.

    Args:
        content: Содержимое файла

    Returns:
        Dict с результатами валидации
    """
    required_sections = ["Goal", "State", "Done", "Next"]

    sections = parse_sections(content)
    section_titles = [s["title"] for s in sections]

    missing_sections = []
    for req_section in required_sections:
        if not any(req_section.lower() in title.lower() for title in section_titles):
            missing_sections.append(req_section)

    # Проверка на наличие хотя бы одного раздела
    has_structure = len(sections) > 0

    # Проверка на наличие контента
    has_content = len(content.strip()) > 0

    return {
        "valid": len(missing_sections) == 0 and has_structure and has_content,
        "has_structure": has_structure,
        "has_content": has_content,
        "total_sections": len(sections),
        "missing_sections": missing_sections,
        "section_titles": section_titles,
    }


def get_ledger_summary(content: str) -> Dict[str, Any]:
    """
    Получение summary информации о ledger.

    Args:
        content: Содержимое файла

    Returns:
        Dict с summary информацией
    """
    sections = parse_sections(content)
    metrics = find_metrics(content)
    unconfirmed = find_unconfirmed(content)
    todos = find_todos(content)
    dates = find_dates(content)
    validation = validate_ledger_structure(content)

    return {
        "total_lines": len(content.splitlines()),
        "total_chars": len(content),
        "total_words": len(content.split()),
        "total_sections": len(sections),
        "total_metrics": len(metrics),
        "total_unconfirmed": len(unconfirmed),
        "total_todos": len(todos),
        "total_dates": len(dates),
        "validation": validation,
        "last_update": None,  # Будет заполнено из файла
    }


def extract_key_metrics(content: str) -> Dict[str, Any]:
    """
    Извлечение ключевых метрик из ledger.

    Args:
        content: Содержимое файла

    Returns:
        Dict с ключевыми метриками
    """
    key_metrics = {}

    # Поиск метрик в разделе State
    state_section = None
    for section in parse_sections(content):
        if "State" in section["title"] or "Технические метрики" in section["content"]:
            state_section = section["content"]
            break

    if state_section:
        # Извлечение конкретных метрик
        patterns = {
            "error_rate": r"Error Rate:\s*([<>]?[\d.]+%?)",
            "response_time": r"Response Time:\s*([<>]?[\d.]+)\s*(ms|s)",
            "uptime": r"Uptime:\s*([<>]?[\d.]+%?)",
            "test_coverage": r"Test Coverage:\s*([<>]?[\d.]+%?)",
            "pqc_handshake": r"PQC Handshake:\s*([<>]?[\d.]+)\s*(ms|s)",
            "anomaly_detection": r"Anomaly Detection Accuracy:\s*([<>]?[\d.]+%?)",
            "graphsage_accuracy": r"GraphSAGE Accuracy:\s*([<>]?[\d.]+%?)",
            "mttd": r"MTTD:\s*([<>]?[\d.]+)\s*(ms|s)",
            "mttr": r"MTTR:\s*([<>]?[\d.]+)\s*(ms|s|min)",
        }

        for metric_name, pattern in patterns.items():
            match = re.search(pattern, state_section, re.IGNORECASE)
            if match:
                key_metrics[metric_name] = {
                    "value": match.group(1),
                    "unit": match.group(2) if len(match.groups()) > 1 else None,
                    "raw": match.group(0),
                }

    return key_metrics
