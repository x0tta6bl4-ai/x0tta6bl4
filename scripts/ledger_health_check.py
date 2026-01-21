#!/usr/bin/env python3
"""
Health Check для Continuity Ledger

Проверка здоровья ledger и его готовности к использованию
"""

import sys
from pathlib import Path
from datetime import datetime, timedelta

PROJECT_ROOT = Path(__file__).parent.parent
CONTINUITY_FILE = PROJECT_ROOT / "CONTINUITY.md"


def health_check():
    """Health check для ledger"""
    print("=" * 60)
    print("🏥 HEALTH CHECK - CONTINUITY LEDGER")
    print("=" * 60)
    
    checks = []
    
    # Проверка существования файла
    if not CONTINUITY_FILE.exists():
        print("\n❌ Файл не найден")
        checks.append(("Файл существует", False))
        sys.exit(1)
    else:
        checks.append(("Файл существует", True))
    
    # Проверка размера файла
    file_size = CONTINUITY_FILE.stat().st_size
    if file_size < 1000:
        checks.append(("Размер файла (>1KB)", False))
        print(f"\n⚠️  Файл слишком маленький: {file_size} bytes")
    else:
        checks.append(("Размер файла (>1KB)", True))
    
    # Проверка последнего обновления
    last_modified = datetime.fromtimestamp(CONTINUITY_FILE.stat().st_mtime)
    days_since_update = (datetime.now() - last_modified).days
    
    if days_since_update > 30:
        checks.append(("Актуальность (<30 дней)", False))
        print(f"\n⚠️  Файл не обновлялся {days_since_update} дней")
    else:
        checks.append(("Актуальность (<30 дней)", True))
    
    # Проверка содержимого
    content = CONTINUITY_FILE.read_text(encoding="utf-8")
    
    required_keywords = ["Goal", "State", "Done", "Next"]
    missing_keywords = []
    for keyword in required_keywords:
        if keyword not in content:
            missing_keywords.append(keyword)
    
    if missing_keywords:
        checks.append(("Обязательные разделы", False))
        print(f"\n⚠️  Отсутствуют разделы: {', '.join(missing_keywords)}")
    else:
        checks.append(("Обязательные разделы", True))
    
    # Проверка индексирования (если доступно)
    try:
        sys.path.insert(0, str(PROJECT_ROOT))
        from src.ledger.rag_search import LedgerRAGSearch
        
        ledger_rag = LedgerRAGSearch()
        if ledger_rag.is_indexed():
            checks.append(("RAG индексирование", True))
        else:
            checks.append(("RAG индексирование", False))
            print("\n⚠️  Ledger не проиндексирован в RAG")
    except Exception as e:
        checks.append(("RAG индексирование", None))
        print(f"\n⚠️  Не удалось проверить RAG индексирование: {e}")
    
    # Итоговый отчет
    print("\n" + "=" * 60)
    print("📊 РЕЗУЛЬТАТЫ ПРОВЕРКИ:")
    print("=" * 60)
    
    passed = sum(1 for _, status in checks if status is True)
    failed = sum(1 for _, status in checks if status is False)
    unknown = sum(1 for _, status in checks if status is None)
    
    for check_name, status in checks:
        if status is True:
            print(f"  ✅ {check_name}")
        elif status is False:
            print(f"  ❌ {check_name}")
        else:
            print(f"  ⚠️  {check_name} (неизвестно)")
    
    print("\n" + "=" * 60)
    print(f"📈 Итого: {passed} ✅, {failed} ❌, {unknown} ⚠️")
    
    if failed == 0:
        print("✅ Ledger в хорошем состоянии")
        sys.exit(0)
    else:
        print("⚠️  Обнаружены проблемы")
        sys.exit(1)


if __name__ == "__main__":
    health_check()

