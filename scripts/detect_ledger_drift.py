#!/usr/bin/env python3
"""
Скрипт для обнаружения расхождений в ledger

Использование:
    python scripts/detect_ledger_drift.py
"""

import sys
import asyncio
import json
from pathlib import Path

PROJECT_ROOT = Path(__file__).parent.parent
sys.path.insert(0, str(PROJECT_ROOT / "src"))

from ledger.drift_detector import LedgerDriftDetector
import logging

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)


async def detect_drift():
    """Обнаружение расхождений в ledger"""
    logger.info("🚀 Запуск drift detection...")
    
    detector = LedgerDriftDetector()
    
    # Обнаружение расхождений
    result = await detector.detect_drift()
    
    # Вывод результатов
    print("\n" + "=" * 60)
    print("РЕЗУЛЬТАТЫ DRIFT DETECTION")
    print("=" * 60)
    print(f"Время: {result['timestamp']}")
    print(f"Всего расхождений: {result['total_drifts']}")
    print(f"  - Code drifts: {result['code_drifts']}")
    print(f"  - Metrics drifts: {result['metrics_drifts']}")
    print(f"  - Doc drifts: {result['doc_drifts']}")
    print(f"Граф: {result['graph']['nodes_count']} узлов, {result['graph']['edges_count']} рёбер")
    print(f"Статус: {result['status']}")
    print("=" * 60)
    
    if result['drifts']:
        print("\nОбнаруженные расхождения:")
        for i, drift in enumerate(result['drifts'], 1):
            print(f"\n[{i}] {drift['type']} ({drift['severity']})")
            print(f"    Раздел: {drift['section']}")
            print(f"    Описание: {drift['description']}")
            if drift.get('recommendations'):
                print(f"    Рекомендации:")
                for rec in drift['recommendations']:
                    print(f"      - {rec}")
    else:
        print("\n✅ Расхождений не обнаружено")
    
    # Сохранение результатов
    results_file = PROJECT_ROOT / "benchmarks" / "results" / f"drift_detection_{result['timestamp'].replace(':', '-').split('.')[0]}.json"
    results_file.parent.mkdir(parents=True, exist_ok=True)
    
    with open(results_file, "w", encoding="utf-8") as f:
        json.dump(result, f, indent=2, ensure_ascii=False)
    
    print(f"\n💾 Результаты сохранены в: {results_file}")
    
    return result


if __name__ == "__main__":
    result = asyncio.run(detect_drift())
    sys.exit(0 if result['total_drifts'] == 0 else 1)

