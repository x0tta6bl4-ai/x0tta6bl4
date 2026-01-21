"""
Базовые тесты для Ledger RAG Search (без зависимостей)

Проверяет базовую функциональность без полных ML зависимостей
"""

import pytest
import sys
from pathlib import Path

PROJECT_ROOT = Path(__file__).parent.parent.parent
sys.path.insert(0, str(PROJECT_ROOT))

from src.ledger.helpers import (
    parse_sections,
    find_metrics,
    find_unconfirmed,
    validate_ledger_structure,
    extract_key_metrics
)


class TestLedgerHelpers:
    """Тесты для helper функций"""
    
    def test_parse_sections(self):
        """Тест парсинга разделов"""
        content = """## Goal
Цель проекта

## State
Состояние проекта

## Done
Завершенные задачи
"""
        sections = parse_sections(content)
        assert len(sections) == 3
        assert sections[0]["title"] == "Goal"
        assert sections[1]["title"] == "State"
        assert sections[2]["title"] == "Done"
    
    def test_find_metrics(self):
        """Тест поиска метрик"""
        content = """
Error Rate: <1%
Response Time: <500ms
Uptime: >99.9%
Test Coverage: >90%
"""
        metrics = find_metrics(content)
        assert len(metrics) > 0
        assert any("Error Rate" in m["match"] or "1%" in m["match"] for m in metrics)
    
    def test_find_unconfirmed(self):
        """Тест поиска UNCONFIRMED меток"""
        content = """
## State
- Метрика 1: 100ms (UNCONFIRMED)
- Метрика 2: 200ms
"""
        unconfirmed = find_unconfirmed(content)
        assert len(unconfirmed) == 1
        assert unconfirmed[0]["section"] in ["State", "Unknown"]
    
    def test_validate_ledger_structure(self):
        """Тест валидации структуры"""
        content = """
## Goal
Цель проекта

## State
Состояние проекта

## Done
Завершенные задачи

## Next
Следующие шаги
"""
        validation = validate_ledger_structure(content)
        assert validation["valid"] is True
        assert validation["total_sections"] == 4
        assert len(validation["missing_sections"]) == 0
    
    def test_extract_key_metrics(self):
        """Тест извлечения ключевых метрик"""
        content = """
## State

**Технические метрики:**
- Error Rate: <1%
- Response Time: <500ms
- Uptime: >99.9%
- Test Coverage: >90%
- PQC Handshake: 0.81ms
- Anomaly Detection Accuracy: 96%
"""
        key_metrics = extract_key_metrics(content)
        assert len(key_metrics) > 0
        assert "error_rate" in key_metrics or "response_time" in key_metrics


class TestLedgerFile:
    """Тесты для работы с файлом CONTINUITY.md"""
    
    def test_continuity_file_exists(self):
        """Проверка существования файла"""
        continuity_file = PROJECT_ROOT / "CONTINUITY.md"
        assert continuity_file.exists(), "CONTINUITY.md должен существовать"
    
    def test_continuity_file_readable(self):
        """Проверка читаемости файла"""
        continuity_file = PROJECT_ROOT / "CONTINUITY.md"
        content = continuity_file.read_text(encoding="utf-8")
        assert len(content) > 0, "CONTINUITY.md не должен быть пустым"
    
    def test_continuity_file_structure(self):
        """Проверка структуры файла"""
        continuity_file = PROJECT_ROOT / "CONTINUITY.md"
        content = continuity_file.read_text(encoding="utf-8")
        
        validation = validate_ledger_structure(content)
        assert validation["has_structure"], "CONTINUITY.md должен иметь структуру"
        assert validation["has_content"], "CONTINUITY.md должен иметь содержимое"
        assert validation["total_sections"] > 0, "CONTINUITY.md должен иметь разделы"
    
    def test_continuity_file_has_required_sections(self):
        """Проверка наличия обязательных разделов"""
        continuity_file = PROJECT_ROOT / "CONTINUITY.md"
        content = continuity_file.read_text(encoding="utf-8")
        
        validation = validate_ledger_structure(content)
        # Проверяем, что есть хотя бы основные разделы
        section_titles = [s.lower() for s in validation["section_titles"]]
        
        # Проверяем наличие ключевых разделов (хотя бы одного из каждой группы)
        has_goal = any("goal" in title for title in section_titles)
        has_state = any("state" in title for title in section_titles)
        has_done = any("done" in title for title in section_titles)
        has_next = any("next" in title for title in section_titles)
        
        assert has_goal or has_state, "Должен быть раздел Goal или State"
        assert has_done or has_next, "Должен быть раздел Done или Next"

