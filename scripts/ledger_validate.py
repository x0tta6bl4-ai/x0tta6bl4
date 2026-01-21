#!/usr/bin/env python3
"""
Валидация Continuity Ledger

Проверка структуры, метрик, UNCONFIRMED меток и других аспектов ledger
"""

import sys
from pathlib import Path

PROJECT_ROOT = Path(__file__).parent.parent
sys.path.insert(0, str(PROJECT_ROOT))

# Прямой импорт helpers без использования __init__.py
from src.ledger.helpers import (
    validate_ledger_structure,
    find_unconfirmed,
    find_todos,
    find_metrics,
    get_ledger_summary,
    extract_key_metrics
)

CONTINUITY_FILE = PROJECT_ROOT / "CONTINUITY.md"


def validate_ledger():
    """Валидация ledger"""
    if not CONTINUITY_FILE.exists():
        print(f"❌ Файл не найден: {CONTINUITY_FILE}")
        sys.exit(1)
    
    content = CONTINUITY_FILE.read_text(encoding="utf-8")
    
    print("=" * 60)
    print("🔍 ВАЛИДАЦИЯ CONTINUITY LEDGER")
    print("=" * 60)
    
    # Валидация структуры
    print("\n📋 Структура:")
    validation = validate_ledger_structure(content)
    
    if validation["valid"]:
        print("  ✅ Структура валидна")
    else:
        print("  ❌ Структура невалидна")
        if validation["missing_sections"]:
            print(f"  ⚠️  Отсутствующие разделы: {', '.join(validation['missing_sections'])}")
    
    print(f"  📊 Всего разделов: {validation['total_sections']}")
    
    # Summary
    print("\n📊 Summary:")
    summary = get_ledger_summary(content)
    print(f"  - Строк: {summary['total_lines']:,}")
    print(f"  - Символов: {summary['total_chars']:,}")
    print(f"  - Слов: {summary['total_words']:,}")
    print(f"  - Разделов: {summary['total_sections']}")
    print(f"  - Метрик: {summary['total_metrics']}")
    print(f"  - UNCONFIRMED: {summary['total_unconfirmed']}")
    print(f"  - TODO/FIXME: {summary['total_todos']}")
    print(f"  - Дат: {summary['total_dates']}")
    
    # UNCONFIRMED метки
    print("\n⚠️  UNCONFIRMED метки:")
    unconfirmed = find_unconfirmed(content)
    if unconfirmed:
        print(f"  Найдено: {len(unconfirmed)}")
        print("  Топ-5:")
        for i, uc in enumerate(unconfirmed[:5], 1):
            print(f"    {i}. Раздел: {uc['section']}, строка: {uc['line']}")
            print(f"       Контекст: {uc['context'][:80]}...")
    else:
        print("  ✅ UNCONFIRMED меток не найдено")
    
    # TODO/FIXME
    print("\n📝 TODO/FIXME:")
    todos = find_todos(content)
    if todos:
        print(f"  Найдено: {len(todos)}")
        print("  Топ-5:")
        for i, todo in enumerate(todos[:5], 1):
            print(f"    {i}. [{todo['type']}] {todo['text'][:60]}")
            print(f"       Раздел: {todo['section']}, строка: {todo['line']}")
    else:
        print("  ✅ TODO/FIXME не найдено")
    
    # Ключевые метрики
    print("\n📈 Ключевые метрики:")
    key_metrics = extract_key_metrics(content)
    if key_metrics:
        for metric_name, metric_data in key_metrics.items():
            value = metric_data["value"]
            unit = metric_data["unit"] or ""
            print(f"  - {metric_name}: {value}{unit}")
    else:
        print("  ⚠️  Ключевые метрики не найдены")
    
    # Общая оценка
    print("\n" + "=" * 60)
    print("📊 ОБЩАЯ ОЦЕНКА:")
    
    issues = []
    if not validation["valid"]:
        issues.append("Структура невалидна")
    if len(unconfirmed) > 10:
        issues.append(f"Много UNCONFIRMED меток ({len(unconfirmed)})")
    if len(todos) > 5:
        issues.append(f"Много TODO/FIXME ({len(todos)})")
    
    if issues:
        print("  ⚠️  Обнаружены проблемы:")
        for issue in issues:
            print(f"    - {issue}")
        print("\n  Рекомендации:")
        if not validation["valid"]:
            print("    - Добавьте отсутствующие разделы")
        if len(unconfirmed) > 10:
            print("    - Валидируйте UNCONFIRMED метки")
        if len(todos) > 5:
            print("    - Решите TODO/FIXME задачи")
    else:
        print("  ✅ Ledger в хорошем состоянии")
    
    print("=" * 60)
    
    # Exit code
    sys.exit(0 if not issues else 1)


if __name__ == "__main__":
    validate_ledger()

