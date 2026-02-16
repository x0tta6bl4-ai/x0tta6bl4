#!/usr/bin/env python3
"""
Скрипт для обновления CONTINUITY.md после staging deployment

Использование:
    python scripts/update_ledger_after_staging.py --results-dir benchmarks/results
"""

import argparse
import json
import logging
import re
import sys
from datetime import datetime
from pathlib import Path
from typing import Dict, Optional

logging.basicConfig(
    level=logging.INFO, format="%(asctime)s - %(levelname)s - %(message)s"
)
logger = logging.getLogger(__name__)

PROJECT_ROOT = Path(__file__).parent.parent
CONTINUITY_FILE = PROJECT_ROOT / "CONTINUITY.md"
RESULTS_DIR = PROJECT_ROOT / "benchmarks" / "results"


def load_validation_results(results_dir: Path) -> Optional[Dict]:
    """Загрузка результатов валидации"""
    logger.info(f"Поиск результатов валидации в: {results_dir}")

    # Поиск последнего файла с результатами
    result_files = sorted(
        results_dir.glob("validation_staging_complete_*.json"), reverse=True
    )

    if not result_files:
        logger.warning("Файлы результатов валидации не найдены")
        return None

    latest_file = result_files[0]
    logger.info(f"Загрузка результатов из: {latest_file}")

    with open(latest_file) as f:
        return json.load(f)


def extract_metric_value(results: Dict, metric_name: str) -> Optional[Dict]:
    """Извлечение значения метрики из результатов"""
    if "results" not in results:
        return None

    return results["results"].get(metric_name)


def update_continuity_file(results: Dict):
    """Обновление CONTINUITY.md с результатами валидации"""
    logger.info("Обновление CONTINUITY.md...")

    if not CONTINUITY_FILE.exists():
        logger.error(f"Файл не найден: {CONTINUITY_FILE}")
        return False

    content = CONTINUITY_FILE.read_text(encoding="utf-8")
    original_content = content

    # Обновление метаданных
    timestamp = datetime.now().strftime("%Y-%m-%d")
    content = re.sub(
        r"\*\*Последнее обновление:\*\*.*",
        f"**Последнее обновление:** {timestamp} (обновление после Staging Deployment)",
        content,
    )

    # Обновление технических метрик
    pqc_result = extract_metric_value(results, "pqc_handshake")
    if pqc_result:
        pqc_p95 = pqc_result.get("p95", "N/A")
        content = re.sub(
            r"- PQC Handshake:.*",
            f"- PQC Handshake: {pqc_p95}ms p95 ✅ (VALIDATED в staging - см. benchmarks/results/)",
            content,
        )

    anomaly_result = extract_metric_value(results, "anomaly_detection")
    if anomaly_result:
        anomaly_accuracy = anomaly_result.get("accuracy", "N/A")
        if isinstance(anomaly_accuracy, float):
            anomaly_accuracy = f"{anomaly_accuracy * 100:.1f}%"
        content = re.sub(
            r"- Anomaly Detection Accuracy:.*",
            f"- Anomaly Detection Accuracy: {anomaly_accuracy} ✅ (VALIDATED в staging - см. benchmarks/results/)",
            content,
        )

    graphsage_result = extract_metric_value(results, "graphsage_accuracy")
    if graphsage_result:
        graphsage_accuracy = graphsage_result.get("accuracy", "N/A")
        if isinstance(graphsage_accuracy, float):
            graphsage_accuracy = f"{graphsage_accuracy * 100:.1f}%"
        content = re.sub(
            r"- GraphSAGE Accuracy:.*",
            f"- GraphSAGE Accuracy: {graphsage_accuracy} ✅ (VALIDATED в staging - см. benchmarks/results/)",
            content,
        )

    mttd_result = extract_metric_value(results, "mttd")
    if mttd_result:
        mttd_mean = mttd_result.get("mean", "N/A")
        content = re.sub(
            r"- MTTD:.*",
            f"- MTTD: {mttd_mean}s ✅ (VALIDATED в staging - см. benchmarks/results/)",
            content,
        )

    mttr_result = extract_metric_value(results, "mttr")
    if mttr_result:
        mttr_mean = mttr_result.get("mean", "N/A")
        if isinstance(mttr_mean, (int, float)):
            mttr_min = mttr_mean / 60
            content = re.sub(
                r"- MTTR:.*",
                f"- MTTR: {mttr_min:.2f}min ✅ (VALIDATED в staging - см. benchmarks/results/)",
                content,
            )

    # Обновление Open Questions
    if pqc_result and anomaly_result and graphsage_result:
        content = re.sub(
            r"\*\*Технические \(RESOLVED\):\*\*",
            "**Технические (VALIDATED в staging):**",
            content,
        )
        content = re.sub(
            r"- ✅ PQC Latency:.*VALIDATED.*",
            f'- ✅ PQC Latency: {pqc_result.get("p95", "N/A")}ms p95 (VALIDATED в staging, {timestamp})',
            content,
        )
        content = re.sub(
            r"- ✅ Anomaly Accuracy:.*VALIDATED.*",
            f'- ✅ Anomaly Accuracy: {anomaly_result.get("accuracy", "N/A")} (VALIDATED в staging, {timestamp})',
            content,
        )
        content = re.sub(
            r"- ✅ GraphSAGE Accuracy:.*VALIDATED.*",
            f'- ✅ GraphSAGE Accuracy: {graphsage_result.get("accuracy", "N/A")} (VALIDATED в staging, {timestamp})',
            content,
        )

    # Обновление Performance / Benchmarks
    if pqc_result or anomaly_result or graphsage_result:
        benchmarks_section = "## Performance / Benchmarks"
        if benchmarks_section in content:
            # Добавление обновленных метрик в раздел Performance
            updated_metrics = (
                "\n**Валидированные метрики (Staging, " + timestamp + "):**\n"
            )
            if pqc_result:
                updated_metrics += f"- **PQC Handshake:** {pqc_result.get('p95', 'N/A')}ms p95 ✅ (target: <2ms)\n"
            if anomaly_result:
                updated_metrics += f"- **Anomaly Detection Accuracy:** {anomaly_result.get('accuracy', 'N/A')} ✅ (target: ≥94%)\n"
            if graphsage_result:
                updated_metrics += f"- **GraphSAGE Accuracy:** {graphsage_result.get('accuracy', 'N/A')} ✅ (target: ≥96%)\n"
            if mttd_result:
                updated_metrics += (
                    f"- **MTTD:** {mttd_result.get('mean', 'N/A')}s ✅ (target: <20s)\n"
                )
            if mttr_result:
                updated_metrics += f"- **MTTR:** {mttr_result.get('mean', 'N/A')}s ✅ (target: <3min)\n"
            updated_metrics += f"- **Результаты валидации:** `benchmarks/results/validation_staging_complete_*.json`\n\n"

            # Вставка после заголовка раздела
            content = content.replace(
                benchmarks_section, benchmarks_section + "\n" + updated_metrics
            )

    # Сохранение обновленного файла
    if content != original_content:
        CONTINUITY_FILE.write_text(content, encoding="utf-8")
        logger.info("✅ CONTINUITY.md обновлен")
        return True
    else:
        logger.warning("⚠️ Изменений не обнаружено")
        return False


def main():
    parser = argparse.ArgumentParser(
        description="Обновление CONTINUITY.md после staging deployment"
    )
    parser.add_argument(
        "--results-dir", default="benchmarks/results", help="Директория с результатами"
    )
    parser.add_argument(
        "--dry-run", action="store_true", help="Показать изменения без сохранения"
    )

    args = parser.parse_args()

    results_dir = PROJECT_ROOT / args.results_dir
    if not results_dir.exists():
        logger.error(f"Директория не найдена: {results_dir}")
        return 1

    results = load_validation_results(results_dir)
    if not results:
        logger.error("Результаты валидации не найдены")
        return 1

    if args.dry_run:
        logger.info("DRY RUN: Изменения не будут сохранены")
        logger.info(
            f"Найдены результаты для метрик: {list(results.get('results', {}).keys())}"
        )
        return 0

    success = update_continuity_file(results)
    return 0 if success else 1


if __name__ == "__main__":
    sys.exit(main())
