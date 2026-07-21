"""
Drift Checkers for code, metrics, and documentation consistency.
"""
from __future__ import annotations

import ast
import logging
import re
from datetime import datetime
from pathlib import Path
from typing import Any, Dict, List, Optional
from .models import DriftResult

try:
    from src.ledger.helpers import find_metrics
except ImportError:
    def find_metrics(*args, **kwargs):  # type: ignore[no-redef]
        return []

logger = logging.getLogger(__name__)

PROJECT_ROOT = Path(__file__).parent.parent.parent.parent
CONTINUITY_FILE = PROJECT_ROOT / "CONTINUITY.md"

class CodeDriftChecker:
    """Обнаружение расхождений между кодом и документацией."""

    def __init__(self, continuity_file: Path = CONTINUITY_FILE, project_root: Path = PROJECT_ROOT):
        self.continuity_file = continuity_file
        self.project_root = project_root

    def detect(self) -> List[DriftResult]:
        """🔍 Обнаружение code drift..."""
        drifts = []

        try:
            # 1. Парсинг кода (AST analysis) - анализ основных компонентов
            src_path = self.project_root / "src"
            if not src_path.exists():
                logger.warning(f"⚠️ src/ directory not found at {src_path}")
                return drifts

            # Собираем информацию о коде
            code_info = {"files": [], "functions": [], "classes": [], "imports": []}

            for py_file in src_path.rglob("*.py"):
                try:
                    with open(py_file, "r", encoding="utf-8") as f:
                        tree = ast.parse(f.read(), filename=str(py_file))

                    for node in ast.walk(tree):
                        if isinstance(node, ast.FunctionDef):
                            code_info["functions"].append(node.name)
                        elif isinstance(node, ast.ClassDef):
                            code_info["classes"].append(node.name)
                        elif isinstance(node, (ast.Import, ast.ImportFrom)):
                            if isinstance(node, ast.ImportFrom) and node.module:
                                code_info["imports"].append(node.module)

                    code_info["files"].append(str(py_file.relative_to(self.project_root)))
                except (SyntaxError, UnicodeDecodeError) as e:
                    logger.debug(f"⚠️ Cannot parse {py_file}: {e}")
                    continue

            # 2. Парсинг документации из CONTINUITY.md
            if not self.continuity_file.exists():
                return drifts

            content = self.continuity_file.read_text(encoding="utf-8")

            # Поиск упоминаний компонентов в документации
            doc_components = {
                "files_mentioned": [],
                "functions_mentioned": [],
                "classes_mentioned": [],
            }

            # Простой поиск упоминаний
            for func_name in code_info["functions"][:20]:  # Limit для производительности
                if func_name in content:
                    doc_components["functions_mentioned"].append(func_name)

            for class_name in code_info["classes"][:20]:
                if class_name in content:
                    doc_components["classes_mentioned"].append(class_name)

            # 3. Сравнение и обнаружение расхождений
            # Проверяем, что основные компоненты упомянуты в документации
            critical_functions = [
                "detect_drift",
                "build_ledger_graph",
                "get_drift_detector",
            ]
            for func in critical_functions:
                if (
                    func in code_info["functions"]
                    and func not in doc_components["functions_mentioned"]
                ):
                    drifts.append(
                        DriftResult(
                            drift_type="code_drift",
                            severity="medium",
                            description=f"Function '{func}' exists in code but not documented",
                            section="Working set",
                            detected_at=datetime.utcnow().isoformat() + "Z",
                            recommendations=[
                                f"Add documentation for {func} in CONTINUITY.md",
                                "Update Working set section with function details",
                            ],
                            metadata={
                                "function": func,
                                "file_count": len(code_info["files"]),
                            },
                        )
                    )

            if drifts:
                logger.info(f"✅ Обнаружено {len(drifts)} code drifts")
            else:
                logger.info("✅ Code drift не обнаружен")

        except Exception as e:
            logger.error(f"❌ Error in code drift detection: {e}", exc_info=True)

        return drifts


class MetricsDriftChecker:
    """Обнаружение расхождений в числовых метриках."""

    def __init__(self, continuity_file: Path = CONTINUITY_FILE):
        self.continuity_file = continuity_file

    def detect(self) -> List[DriftResult]:
        """🔍 Обнаружение metrics drift..."""
        drifts = []

        if not self.continuity_file.exists():
            return drifts

        try:
            content = self.continuity_file.read_text(encoding="utf-8")

            # Парсинг метрик из ledger
            find_metrics(content)

            # Поиск метрик с числовыми значениями для сравнения
            metric_patterns = {
                "test_coverage": r"Test Coverage[:\s]+(\d+(?:\.\d+)?)%",
                "production_readiness": r"Production Readiness[:\s]+(\d+(?:\.\d+)?)%",
                "error_rate": r"Error Rate[:\s]+[<>=]?\s*(\d+(?:\.\d+)?)%",
                "response_time": r"Response Time[:\s]+[<>=]?\s*(\d+(?:\.\d+)?)\s*ms",
                "mttd": r"MTTD[:\s]+[<>=]?\s*(\d+(?:\.\d+)?)\s*s",
                "mttr": r"MTTR[:\s]+[<>=]?\s*(\d+(?:\.\d+)?)\s*min",
            }

            for metric_name, pattern in metric_patterns.items():
                matches = re.finditer(pattern, content, re.IGNORECASE)
                for match in matches:
                    documented_value = float(match.group(1))

                    # Базовая проверка: ожидаемые диапазоны
                    expected_ranges = {
                        "test_coverage": (75.0, 100.0),
                        "production_readiness": (60.0, 100.0),
                        "error_rate": (0.0, 5.0),
                        "response_time": (0.0, 500.0),
                        "mttd": (0.0, 30.0),
                        "mttr": (0.0, 10.0),
                    }

                    if metric_name in expected_ranges:
                        min_val, max_val = expected_ranges[metric_name]
                        if not (min_val <= documented_value <= max_val):
                            drifts.append(
                                DriftResult(
                                    drift_type="metrics_drift",
                                    severity="high",
                                    description=f"Metric '{metric_name}' value {documented_value} outside expected range [{min_val}, {max_val}]",
                                    section="Performance / Benchmarks",
                                    detected_at=datetime.utcnow().isoformat() + "Z",
                                    recommendations=[
                                        f"Verify actual {metric_name} value",
                                        "Update CONTINUITY.md if value is correct",
                                        "Check monitoring system for real-time values",
                                    ],
                                    metadata={
                                        "metric": metric_name,
                                        "documented_value": documented_value,
                                        "expected_range": [min_val, max_val],
                                    },
                                )
                            )

            if drifts:
                logger.info(f"✅ Обнаружено {len(drifts)} metrics drifts")
            else:
                logger.info("✅ Metrics drift не обнаружен")

        except Exception as e:
            logger.error(f"❌ Error in metrics drift detection: {e}", exc_info=True)

        return drifts


class DocDriftChecker:
    """Обнаружение устаревшей документации и логических нестыковок."""

    def __init__(self, continuity_file: Path = CONTINUITY_FILE):
        self.continuity_file = continuity_file

    def detect(self) -> List[DriftResult]:
        """🔍 Обнаружение doc drift..."""
        drifts = []

        try:
            if not self.continuity_file.exists():
                return drifts

            content = self.continuity_file.read_text(encoding="utf-8")

            # 1. Сравнение дат обновления
            last_update_pattern = r"Последнее обновление[:\s]+(\d{4}-\d{2}-\d{2}[^\n]*)"
            last_update_match = re.search(last_update_pattern, content, re.IGNORECASE)

            if last_update_match:
                last_update_str = last_update_match.group(1)
                date_pattern = r"(\d{4}-\d{2}-\d{2})"
                date_match = re.search(date_pattern, last_update_str)
                if date_match:
                    try:
                        last_update = datetime.strptime(date_match.group(1), "%Y-%m-%d")
                        days_since_update = (datetime.utcnow() - last_update).days

                        # Предупреждение, если документация не обновлялась более 7 дней
                        if days_since_update > 7:
                            drifts.append(
                                DriftResult(
                                    drift_type="doc_drift",
                                    severity="medium",
                                    description=f"Documentation not updated for {days_since_update} days",
                                    section="Примечания по обновлению",
                                    detected_at=datetime.utcnow().isoformat() + "Z",
                                    recommendations=[
                                        "Update CONTINUITY.md with latest changes",
                                        "Review and update all sections",
                                        "Verify all metrics and statuses are current",
                                    ],
                                    metadata={
                                        "days_since_update": days_since_update,
                                        "last_update": last_update_str,
                                    },
                                )
                            )
                    except ValueError:
                        logger.debug("Could not parse date from last update")

            # 2. Проверка ссылок на устаревшие компоненты
            deprecated_patterns = [
                (r"SimplifiedNTRU", "SimplifiedNTRU is deprecated, use liboqs"),
                (r"mock.*mode", "Mock modes should be replaced with real implementations"),
            ]

            for pattern, description in deprecated_patterns:
                matches = re.finditer(pattern, content, re.IGNORECASE)
                for match in matches:
                    context_start = max(0, match.start() - 100)
                    context_end = min(len(content), match.end() + 100)
                    context = content[context_start:context_end]

                    if (
                        "Known issues" not in context
                        and "deprecated" not in context.lower()
                    ):
                        drifts.append(
                            DriftResult(
                                drift_type="doc_drift",
                                severity="low",
                                description=f"Possible reference to deprecated component: {description}",
                                section="Unknown",
                                detected_at=datetime.utcnow().isoformat() + "Z",
                                recommendations=[
                                    "Review and update documentation",
                                    "Remove or mark as deprecated if applicable",
                                ],
                                metadata={"pattern": pattern, "match": match.group(0)},
                            )
                        )

            # 3. Обнаружение несоответствий в версиях
            version_pattern = r"версия[:\s]+(\d+\.\d+\.\d+)"
            version_matches = list(re.finditer(version_pattern, content, re.IGNORECASE))
            if len(version_matches) > 1:
                versions = [m.group(1) for m in version_matches]
                unique_versions = set(versions)
                if len(unique_versions) > 1:
                    drifts.append(
                        DriftResult(
                            drift_type="doc_drift",
                            severity="medium",
                            description=f"Multiple version numbers found: {', '.join(unique_versions)}",
                            section="Multiple sections",
                            detected_at=datetime.utcnow().isoformat() + "Z",
                            recommendations=[
                                "Standardize version number across all sections",
                                "Update all version references to match current version",
                            ],
                            metadata={"versions": list(unique_versions)},
                        )
                    )

            if drifts:
                logger.info(f"✅ Обнаружено {len(drifts)} doc drifts")
            else:
                logger.info("✅ Doc drift не обнаружен")

        except Exception as e:
            logger.error(f"❌ Error in doc drift detection: {e}", exc_info=True)

        return drifts
