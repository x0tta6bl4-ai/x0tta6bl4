#!/usr/bin/env python3
"""
Статистика по Continuity Ledger

Показывает метрики и информацию о ledger
"""

import re
import sys
from datetime import datetime
from pathlib import Path

PROJECT_ROOT = Path(__file__).parent.parent
CONTINUITY_FILE = PROJECT_ROOT / "CONTINUITY.md"


def analyze_ledger():
    """Анализ CONTINUITY.md и вывод статистики"""
    if not CONTINUITY_FILE.exists():
        print(f"❌ Файл не найден: {CONTINUITY_FILE}")
        sys.exit(1)

    content = CONTINUITY_FILE.read_text(encoding="utf-8")

    # Базовые метрики
    total_lines = len(content.splitlines())
    total_chars = len(content)
    total_words = len(content.split())

    # Разделы
    sections = re.findall(r"^##\s+(.+)$", content, re.MULTILINE)

    # Подразделы
    subsections = re.findall(r"^###\s+(.+)$", content, re.MULTILINE)

    # Ссылки
    links = re.findall(r"\[([^\]]+)\]\(([^\)]+)\)", content)

    # Код блоки
    code_blocks = re.findall(r"```[\s\S]*?```", content)

    # UNCONFIRMED метки
    unconfirmed = content.count("UNCONFIRMED")

    # TODO/FIXME
    todos = len(re.findall(r"(TODO|FIXME|XXX)", content, re.IGNORECASE))

    # Метрики
    metrics = re.findall(r"(\d+\.?\d*)\s*(ms|s|%|MB|GB)", content, re.IGNORECASE)

    # Даты
    dates = re.findall(r"\d{4}-\d{2}-\d{2}", content)

    print("=" * 60)
    print("📊 СТАТИСТИКА CONTINUITY LEDGER")
    print("=" * 60)
    print(f"\n📄 Файл: {CONTINUITY_FILE}")
    print(
        f"📅 Последнее обновление: {datetime.fromtimestamp(CONTINUITY_FILE.stat().st_mtime).strftime('%Y-%m-%d %H:%M:%S')}"
    )

    print(f"\n📏 Размер:")
    print(f"  - Строк: {total_lines:,}")
    print(f"  - Символов: {total_chars:,}")
    print(f"  - Слов: {total_words:,}")
    print(f"  - Размер файла: {CONTINUITY_FILE.stat().st_size / 1024:.2f} KB")

    print(f"\n📚 Структура:")
    print(f"  - Разделов (##): {len(sections)}")
    print(f"  - Подразделов (###): {len(subsections)}")
    print(f"  - Ссылок: {len(links)}")
    print(f"  - Код блоков: {len(code_blocks)}")

    print(f"\n⚠️  Статус:")
    print(f"  - UNCONFIRMED меток: {unconfirmed}")
    print(f"  - TODO/FIXME: {todos}")

    print(f"\n📈 Метрики:")
    print(f"  - Найдено метрик: {len(metrics)}")
    if metrics:
        print(f"  - Примеры: {', '.join([f'{m[0]}{m[1]}' for m in metrics[:5]])}")

    print(f"\n📅 Даты:")
    print(f"  - Упоминаний дат: {len(dates)}")
    if dates:
        unique_dates = sorted(set(dates))
        print(f"  - Уникальных дат: {len(unique_dates)}")
        print(f"  - Первая: {unique_dates[0]}")
        print(f"  - Последняя: {unique_dates[-1]}")

    # Топ разделов по размеру
    print(f"\n📋 Топ-10 разделов по размеру:")
    section_sizes = []
    current_section = None
    current_size = 0

    for line in content.splitlines():
        if line.startswith("## "):
            if current_section:
                section_sizes.append((current_section, current_size))
            current_section = line.replace("## ", "").strip()
            current_size = len(line)
        else:
            current_size += len(line) + 1  # +1 for newline

    if current_section:
        section_sizes.append((current_section, current_size))

    section_sizes.sort(key=lambda x: x[1], reverse=True)
    for i, (section, size) in enumerate(section_sizes[:10], 1):
        print(f"  {i}. {section[:50]}: {size:,} символов")

    print("\n" + "=" * 60)


if __name__ == "__main__":
    analyze_ledger()
