"""
Helper functions for meta-cognitive MAPE-K loop.

This module contains utility functions for feature extraction,
time estimation, confidence assessment, and probability calculations.
"""
from __future__ import annotations

import logging
from typing import Any, Dict, List, Optional

from .models import ReasoningAnalytics, ReasoningApproach, ReasoningMetrics

logger = logging.getLogger(__name__)


def extract_features_for_prediction(task: Dict[str, Any]) -> Dict[str, float]:
    """
    Извлечение признаков для предсказания GraphSAGE.

    Args:
        task: Описание задачи

    Returns:
        Словарь с признаками
    """
    return {
        "task_complexity": 0.5,
        "similarity_to_history": 0.7,
        "available_approaches": 6.0,
    }


def estimate_reasoning_time(task: Dict[str, Any], approach: Dict[str, Any]) -> float:
    """
    Оценка времени рассуждения.

    Args:
        task: Описание задачи
        approach: Выбранный подход

    Returns:
        Оценка времени в секундах
    """
    base_time = 1.0  # секунды
    complexity = task.get("complexity", 0.5)
    return base_time * (1 + complexity)


def assess_confidence(reasoning_history: List[Dict[str, Any]]) -> float:
    """
    Оценка уровня уверенности на основе истории.

    Args:
        reasoning_history: История рассуждений

    Returns:
        Уровень уверенности (0.0 - 1.0)
    """
    if not reasoning_history:
        return 0.5

    recent_success_rate = sum(1 for h in reasoning_history[-10:] if h.get("success", False)) / min(
        len(reasoning_history), 10
    )

    return recent_success_rate


def count_kb_hits(reasoning_history: List[Dict[str, Any]]) -> int:
    """
    Подсчет попаданий в Knowledge Base.

    Args:
        reasoning_history: История рассуждений

    Returns:
        Количество попаданий
    """
    return sum(1 for h in reasoning_history if h.get("kb_hit", False))


def calculate_cache_hit_rate(reasoning_history: List[Dict[str, Any]]) -> float:
    """
    Расчет hit rate кэша.

    Args:
        reasoning_history: История рассуждений

    Returns:
        Hit rate (0.0 - 1.0)
    """
    if not reasoning_history:
        return 0.0
    return count_kb_hits(reasoning_history) / len(reasoning_history)


def assess_reasoning_efficiency(metrics: ReasoningMetrics) -> float:
    """
    Оценка эффективности рассуждений.

    Args:
        metrics: Метрики рассуждений

    Returns:
        Эффективность (0.0 - 1.0)
    """
    if metrics.reasoning_time == 0:
        return 1.0

    efficiency = 1.0 - (metrics.dead_ends_encountered / max(metrics.approaches_tried, 1))
    return max(0.0, min(1.0, efficiency))


def select_best_approach(analysis: Dict[str, Any]) -> str:
    """
    Выбор лучшего подхода на основе анализа.

    Args:
        analysis: Результаты анализа

    Returns:
        Название подхода
    """
    reasoning_analysis = analysis.get("reasoning_analysis", {})
    if reasoning_analysis.get("anomaly_detected"):
        return ReasoningApproach.COMBINED_ALL.value
    return ReasoningApproach.COMBINED_RAG_GRAPHSAGE.value


def optimize_reasoning_time(analysis: Dict[str, Any]) -> Dict[str, float]:
    """
    Оптимизация распределения времени.

    Args:
        analysis: Результаты анализа

    Returns:
        Распределение времени по фазам
    """
    return {"planning": 0.2, "execution": 0.6, "analysis": 0.2}


def define_meta_checkpoints() -> List[Dict[str, Any]]:
    """
    Определение мета-контрольных точек.

    Returns:
        Список контрольных точек
    """
    return [
        {"name": "approach_selection", "metric": "success_probability > 0.9"},
        {"name": "rag_search", "metric": "similarity > 0.7"},
        {"name": "graphsage_prediction", "metric": "confidence > 0.9"},
    ]


def explain_approach_selection(step: Dict[str, Any], optimization: Dict[str, Any]) -> str:
    """
    Объяснение выбора подхода.

    Args:
        step: Шаг выполнения
        optimization: Параметры оптимизации

    Returns:
        Объяснение выбора
    """
    return f"Selected {optimization.get('approach_selection', 'unknown')} based on historical success rate"


def get_alternatives() -> List[str]:
    """
    Получение альтернативных подходов.

    Returns:
        Список альтернативных подходов
    """
    return [a.value for a in ReasoningApproach]


def calculate_success_probability(step: Dict[str, Any]) -> float:
    """
    Расчет вероятности успеха.

    Args:
        step: Шаг выполнения

    Returns:
        Вероятность успеха (0.0 - 1.0)
    """
    return 0.85


def analyze_why_failed(step: Dict[str, Any]) -> Dict[str, Any]:
    """
    Анализ причин неудачи.

    Args:
        step: Шаг выполнения

    Returns:
        Анализ причин
    """
    return {"reason": "approach_not_suitable", "recommendation": "try_alternative"}


def identify_turning_point(step: Dict[str, Any]) -> str:
    """
    Идентификация поворотного момента.

    Args:
        step: Шаг выполнения

    Returns:
        Описание поворотного момента
    """
    return f"Breakthrough at step: {step.get('action', 'unknown')}"


def extract_breakthrough(execution_entries: List[Dict[str, Any]]) -> Optional[str]:
    """
    Извлечение момента прорыва.

    Args:
        execution_entries: Записи выполнения

    Returns:
        Описание прорыва или None
    """
    for entry in execution_entries:
        if entry.get("meta_insights", {}).get("event") == "breakthrough":
            return entry.get("meta_insights", {}).get("turning_point")
    return None


def analyze_why_algorithm_worked(analytics: ReasoningAnalytics) -> str:
    """
    Анализ почему алгоритм сработал.

    Args:
        analytics: Аналитика рассуждений

    Returns:
    Анализ успеха
    """
    return f"Algorithm {analytics.algorithm_used} worked due to high confidence and low dead ends"


def extract_key_success_factors(execution_entries: List[Dict[str, Any]]) -> List[str]:
    """
    Извлечение ключевых факторов успеха.

    Args:
        execution_entries: Записи выполнения

    Returns:
        Список факторов успеха
    """
    return ["high_confidence", "low_dead_ends", "efficient_reasoning"]


def analyze_why_algorithm_failed(analytics: ReasoningAnalytics) -> str:
    """
    Анализ почему алгоритм провалился.

    Args:
        analytics: Аналитика рассуждений

    Returns:
        Анализ неудачи
    """
    return f"Algorithm {analytics.algorithm_used} failed due to too many dead ends ({analytics.dead_ends})"


def suggest_alternative_approach(analytics: ReasoningAnalytics) -> str:
    """
    Предложение альтернативного подхода.

    Args:
        analytics: Аналитика рассуждений

    Returns:
        Рекомендация альтернативы
    """
    return "Try combined approach with RAG + GraphSAGE for better results"


__all__ = [
    "extract_features_for_prediction",
    "estimate_reasoning_time",
    "assess_confidence",
    "count_kb_hits",
    "calculate_cache_hit_rate",
    "assess_reasoning_efficiency",
    "select_best_approach",
    "optimize_reasoning_time",
    "define_meta_checkpoints",
    "explain_approach_selection",
    "get_alternatives",
    "calculate_success_probability",
    "analyze_why_failed",
    "identify_turning_point",
    "extract_breakthrough",
    "analyze_why_algorithm_worked",
    "extract_key_success_factors",
    "analyze_why_algorithm_failed",
    "suggest_alternative_approach",
]

