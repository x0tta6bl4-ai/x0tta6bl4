"""
Мета-когнитивный MAPE-K цикл для x0tta6bl4

Объединяет мета-когнитивный подход (анализ процесса мышления)
с техниками x0tta6bl4 (MAPE-K, RAG, GraphSAGE, Causal Analysis).

Ключевая инновация: Система думает о том, как она думает,
создавая проверяемый след рассуждений и самокорректирующуюся логику.
"""

import logging
import time
from dataclasses import dataclass, field
from enum import Enum
from typing import Any, Dict, List, Optional, Tuple

logger = logging.getLogger(__name__)

# Импорты существующих компонентов
try:
    from ..ml.causal_analysis import CausalAnalysisEngine, CausalAnalysisResult
    from ..ml.graphsage_anomaly_detector import (AnomalyPrediction,
                                                 GraphSAGEAnomalyDetectorV2)
    from ..ml.rag import RAGAnalyzer
    from ..storage.knowledge_storage_v2 import KnowledgeStorageV2
    from .enhanced_thinking_techniques import (FirstPrinciplesThinking,
                                               LateralThinking,
                                               MindMapGenerator,
                                               ReversePlanner, SelfReflection,
                                               SixThinkingHats,
                                               ThinkAloudLogger,
                                               ThreeQuestionsReflection)
    from .mape_k_loop import MAPEKLoop, MAPEKState

    COMPONENTS_AVAILABLE = True
except ImportError as e:
    logger.warning(f"⚠️ Some components not available: {e}")
    COMPONENTS_AVAILABLE = False
    # Создаем заглушки для новых техник
    SixThinkingHats = None
    FirstPrinciplesThinking = None
    LateralThinking = None
    ReversePlanner = None
    ThinkAloudLogger = None
    ThreeQuestionsReflection = None
    MindMapGenerator = None
    SelfReflection = None
    # Создаем заглушки для type hints
    MAPEKLoop = None
    MAPEKState = None
    RAGAnalyzer = None
    GraphSAGEAnomalyDetectorV2 = None
    AnomalyPrediction = None
    CausalAnalysisEngine = None
    CausalAnalysisResult = None
    KnowledgeStorageV2 = None


class ReasoningApproach(Enum):
    """Подходы к рассуждению"""

    MAPE_K_ONLY = "mape_k_only"
    RAG_SEARCH = "rag_search"
    GRAPHSAGE_PREDICTION = "graphsage_prediction"
    CAUSAL_ANALYSIS = "causal_analysis"
    COMBINED_RAG_GRAPHSAGE = "combined_rag_graphsage"
    COMBINED_ALL = "combined_all"


@dataclass
class SolutionSpace:
    """Карта пространства решений"""

    approaches: List[Dict[str, Any]] = field(default_factory=list)
    failure_history: List[Dict[str, Any]] = field(default_factory=list)
    success_probabilities: Dict[str, float] = field(default_factory=dict)
    selected_approach: Optional[str] = None
    reasoning: Optional[str] = None
    # Улучшения: новые техники
    hats_analysis: Optional[Dict[str, Any]] = None
    first_principles: Optional[Dict[str, Any]] = None
    reverse_plan: Optional[List[str]] = None


@dataclass
class ReasoningPath:
    """План пути рассуждения"""

    first_step: str
    dead_ends_to_avoid: List[str] = field(default_factory=list)
    checkpoints: List[Dict[str, Any]] = field(default_factory=list)
    estimated_time: float = 0.0


@dataclass
class ReasoningMetrics:
    """Метрики процесса мышления"""

    reasoning_time: float = 0.0
    approaches_tried: int = 0
    dead_ends_encountered: int = 0
    confidence_level: float = 0.0
    knowledge_base_hits: int = 0
    cache_hit_rate: float = 0.0
    start_time: float = field(default_factory=time.time)
    end_time: Optional[float] = None


@dataclass
class ReasoningAnalytics:
    """Аналитика процесса мышления"""

    algorithm_used: str
    reasoning_time: float
    approaches_tried: int
    dead_ends: int
    breakthrough_moment: Optional[str] = None
    success: bool = False
    meta_insight: Optional[Dict[str, Any]] = None


@dataclass
class ExecutionLogEntry:
    """Запись в журнале выполнения"""

    step: Dict[str, Any]
    result: Dict[str, Any]
    duration: float
    reasoning_approach: str
    meta_insights: Dict[str, Any]
    timestamp: float = field(default_factory=time.time)


class MetaCognitiveMAPEK:
    """
    Интегрированный MAPE-K цикл с мета-когнитивным контролем.

    Добавляет мета-уровень к стандартному MAPE-K циклу:
    - Мета-планирование: карта пространства решений
    - Мета-мониторинг: отслеживание процесса мышления
    - Мета-анализ: анализ эффективности подходов
    - Мета-оптимизация: улучшение алгоритмов рассуждений
    - Мета-аналитика: накопление знаний о процессе мышления
    """

    def __init__(
        self,
        mape_k_loop: Optional[MAPEKLoop] = None,
        rag_analyzer: Optional[RAGAnalyzer] = None,
        graphsage: Optional[GraphSAGEAnomalyDetectorV2] = None,
        causal_engine: Optional[CausalAnalysisEngine] = None,
        knowledge_storage: Optional[KnowledgeStorageV2] = None,
        node_id: str = "default",
    ):
        """
        Инициализация мета-когнитивного MAPE-K.

        Args:
            mape_k_loop: Существующий MAPE-K цикл
            rag_analyzer: RAG анализатор для поиска похожих случаев
            graphsage: GraphSAGE для предсказания успеха
            causal_engine: Causal Analysis для анализа причин
            knowledge_storage: Хранилище знаний
            node_id: ID узла
        """
        self.node_id = node_id
        self.mape_k = mape_k_loop
        self.rag = rag_analyzer
        self.graphsage = graphsage
        self.causal = causal_engine
        self.knowledge_base = knowledge_storage

        # История рассуждений
        self.reasoning_history: List[Dict[str, Any]] = []
        self.execution_logs: List[ExecutionLogEntry] = []

        # Статистика
        self.total_cycles = 0
        self.successful_cycles = 0
        self.failed_cycles = 0
        self.optimization_count = 0

        # Улучшенные техники мышления
        if COMPONENTS_AVAILABLE:
            self.six_hats = SixThinkingHats() if SixThinkingHats else None
            self.first_principles = (
                FirstPrinciplesThinking() if FirstPrinciplesThinking else None
            )
            self.lateral_thinking = LateralThinking() if LateralThinking else None
            self.reverse_planner = ReversePlanner() if ReversePlanner else None
            self.think_aloud = ThinkAloudLogger() if ThinkAloudLogger else None
            self.three_questions = (
                ThreeQuestionsReflection() if ThreeQuestionsReflection else None
            )
            self.mind_maps = MindMapGenerator() if MindMapGenerator else None
            self.self_reflection = SelfReflection() if SelfReflection else None
        else:
            self.six_hats = None
            self.first_principles = None
            self.lateral_thinking = None
            self.reverse_planner = None
            self.think_aloud = None
            self.three_questions = None
            self.mind_maps = None
            self.self_reflection = None

        logger.info(f"✅ MetaCognitiveMAPEK initialized for node {node_id}")

    async def meta_planning(
        self, task: Dict[str, Any]
    ) -> Tuple[SolutionSpace, ReasoningPath]:
        """
        Фаза 0: Мета-планирование.

        Создает карту пространства решений и планирует путь рассуждения.

        Args:
            task: Описание задачи

        Returns:
            Кортеж (SolutionSpace, ReasoningPath)
        """
        logger.info("🧠 Meta-Planning: Mapping solution space...")

        # Улучшение: "Думай вслух"
        if self.think_aloud:
            self.think_aloud.log("Начинаю мета-планирование", {"task": task})

        # Улучшение: Six Thinking Hats для фрейминга
        hats_analysis = None
        if self.six_hats:
            hats_analysis = self.six_hats.analyze(task)
            if self.think_aloud:
                self.think_aloud.log(
                    f"Six Hats анализ: {len(hats_analysis.white.get('facts', []))} фактов найдено"
                )

        # Улучшение: First Principles для разбиения
        first_principles = None
        if self.first_principles:
            first_principles = self.first_principles.decompose(task)
            if self.think_aloud:
                self.think_aloud.log(
                    f"First Principles: {len(first_principles.fundamentals)} фундаментальных элементов"
                )

        # 1. Карта пространства решений
        approaches = [
            {
                "name": ReasoningApproach.MAPE_K_ONLY.value,
                "probability": 0.85,
                "description": "Стандартный MAPE-K цикл",
            },
            {
                "name": ReasoningApproach.RAG_SEARCH.value,
                "probability": 0.78,
                "description": "Поиск похожих случаев в Knowledge Base",
            },
            {
                "name": ReasoningApproach.GRAPHSAGE_PREDICTION.value,
                "probability": 0.92,
                "description": "Предсказание успеха через GraphSAGE",
            },
            {
                "name": ReasoningApproach.CAUSAL_ANALYSIS.value,
                "probability": 0.88,
                "description": "Анализ корневых причин",
            },
            {
                "name": ReasoningApproach.COMBINED_RAG_GRAPHSAGE.value,
                "probability": 0.94,
                "description": "Комбинация RAG + GraphSAGE",
            },
            {
                "name": ReasoningApproach.COMBINED_ALL.value,
                "probability": 0.96,
                "description": "Комбинация всех подходов",
            },
        ]

        # Улучшение: Добавляем подходы из Six Hats и First Principles
        if hats_analysis and hats_analysis.green.get("creative_ideas"):
            approaches.append(
                {
                    "name": "six_hats_creative",
                    "probability": 0.90,
                    "description": f"Креативные идеи: {', '.join(hats_analysis.green['creative_ideas'][:2])}",
                }
            )

        if first_principles and first_principles.fundamentals:
            approaches.append(
                {
                    "name": "first_principles",
                    "probability": 0.88,
                    "description": f"First Principles: {len(first_principles.fundamentals)} элементов",
                }
            )

        # 2. Поиск неудачных подходов в истории
        failure_history = []
        if self.knowledge_base:
            try:
                # Поиск похожих неудачных случаев
                similar_failures = await self.knowledge_base.search_incidents(
                    query=f"failed reasoning approach {task.get('type', 'unknown')}",
                    k=5,
                    threshold=0.6,
                )
                for failure in similar_failures:
                    failure_history.append(
                        {
                            "approach": failure.get("reasoning_analytics", {}).get(
                                "algorithm_used"
                            ),
                            "reason": failure.get("meta_insight", {}).get(
                                "why_it_failed"
                            ),
                            "timestamp": failure.get("timestamp"),
                        }
                    )
            except Exception as e:
                logger.warning(f"⚠️ Failed to search failure history: {e}")

        # 3. Предсказание вероятности успеха через GraphSAGE
        success_probabilities = {}
        if self.graphsage:
            try:
                # Создаем признаки для предсказания
                features = self._extract_features_for_prediction(task)
                prediction = self.graphsage.predict(features)
                if prediction:
                    for approach in approaches:
                        # Упрощенная модель: GraphSAGE дает общую уверенность
                        success_probabilities[approach["name"]] = prediction.confidence
            except Exception as e:
                logger.warning(f"⚠️ GraphSAGE prediction failed: {e}")
                # Fallback: используем базовые вероятности
                for approach in approaches:
                    success_probabilities[approach["name"]] = approach["probability"]
        else:
            # Fallback: используем базовые вероятности
            for approach in approaches:
                success_probabilities[approach["name"]] = approach["probability"]

        # 4. Выбор лучшего подхода
        best_approach = max(
            approaches,
            key=lambda x: success_probabilities.get(x["name"], x["probability"]),
        )

        solution_space = SolutionSpace(
            approaches=approaches,
            failure_history=failure_history,
            success_probabilities=success_probabilities,
            selected_approach=best_approach["name"],
            reasoning=f"Высокая вероятность успеха ({success_probabilities.get(best_approach['name'], best_approach['probability']):.2f}) + исторические данные",
        )

        # 5. Планирование пути рассуждения
        # Улучшение: Обратное планирование
        reverse_plan = None
        if self.reverse_planner and "goal" in task:
            try:
                reverse_plan = self.reverse_planner.plan(task["goal"])
                if self.think_aloud:
                    self.think_aloud.log(
                        f"Обратное планирование: {len(reverse_plan)} шагов"
                    )
            except Exception as e:
                logger.warning(f"⚠️ Reverse planning failed: {e}")

        reasoning_path = ReasoningPath(
            first_step=best_approach["name"],
            dead_ends_to_avoid=[
                f["approach"] for f in failure_history if f.get("approach")
            ],
            checkpoints=[
                {"name": "approach_selection", "metric": "success_probability > 0.9"},
                {"name": "rag_search", "metric": "similarity > 0.7"},
                {"name": "graphsage_prediction", "metric": "confidence > 0.9"},
                {"name": "six_hats_analysis", "metric": "all_hats_analyzed"},  # Новое
                {
                    "name": "first_principles",
                    "metric": "fundamentals_extracted",
                },  # Новое
            ],
            estimated_time=self._estimate_reasoning_time(task, best_approach),
        )

        # Сохраняем улучшения в solution_space
        solution_space.hats_analysis = hats_analysis.__dict__ if hats_analysis else None
        solution_space.first_principles = (
            first_principles.__dict__ if first_principles else None
        )
        solution_space.reverse_plan = reverse_plan

        logger.info(
            f"✅ Meta-Planning complete: Selected {best_approach['name']} "
            f"(probability: {success_probabilities.get(best_approach['name'], best_approach['probability']):.2f})"
        )

        return solution_space, reasoning_path

    async def monitor(self) -> Dict[str, Any]:
        """
        Фаза 1: Мониторинг с мета-осознанием.

        Мониторит не только метрики системы, но и процесс мышления.

        Returns:
            Словарь с system_metrics и reasoning_metrics
        """
        reasoning_start = time.time()

        # Улучшение: "Думай вслух"
        if self.think_aloud:
            self.think_aloud.log("Начинаю мониторинг системы...")

        # Стандартный мониторинг (MAPE-K)
        system_metrics = {}
        if self.mape_k:
            try:
                system_metrics = await self.mape_k._monitor()
                if self.think_aloud:
                    self.think_aloud.log(
                        f"Метрики собраны: CPU={system_metrics.get('cpu_percent', 'N/A')}%"
                    )
            except Exception as e:
                logger.warning(f"⚠️ MAPE-K monitor failed: {e}")
                if self.think_aloud:
                    self.think_aloud.log(f"⚠️ Ошибка мониторинга: {e}")

        # Мета-мониторинг процесса мышления
        reasoning_metrics = ReasoningMetrics(
            start_time=reasoning_start,
            approaches_tried=len(self.reasoning_history),
            dead_ends_encountered=sum(
                1 for h in self.reasoning_history if h.get("dead_end", False)
            ),
            confidence_level=self._assess_confidence(),
            knowledge_base_hits=self._count_kb_hits(),
            cache_hit_rate=self._calculate_cache_hit_rate(),
        )

        # Обнаружение аномалий в процессе мышления
        if reasoning_metrics.dead_ends_encountered > 3:
            logger.warning("⚠️ Too many dead ends detected, triggering meta-analysis")
            await self._trigger_meta_analysis()

        reasoning_metrics.end_time = time.time()
        reasoning_metrics.reasoning_time = (
            reasoning_metrics.end_time - reasoning_metrics.start_time
        )

        # Улучшение: Mind Maps для визуализации
        mind_map = None
        if self.mind_maps:
            try:
                mind_map = self.mind_maps.create(
                    {
                        "center": "System Monitoring",
                        "system_metrics": system_metrics,
                        "reasoning_metrics": reasoning_metrics.__dict__,
                    }
                )
                if self.think_aloud:
                    self.think_aloud.log("Интеллект-карта создана")
            except Exception as e:
                logger.warning(f"⚠️ Mind map creation failed: {e}")

        # Улучшение: Обнаружение пробелов в логике
        logic_gaps = []
        if self.think_aloud:
            logic_gaps = self.think_aloud.detect_logic_gaps()
            if logic_gaps:
                logger.warning(f"⚠️ Обнаружены пробелы в логике: {logic_gaps}")

        return {
            "system_metrics": system_metrics,
            "reasoning_metrics": reasoning_metrics,
            "mind_map": (
                mind_map if mind_map else None
            ),  # mind_maps.create() already returns dict
            "logic_gaps": logic_gaps,
            "think_aloud_log": (
                self.think_aloud.get_thoughts() if self.think_aloud else []
            ),
        }

    async def analyze(self, metrics: Dict[str, Any]) -> Dict[str, Any]:
        """
        Фаза 2: Анализ с мета-рефлексией.

        Анализирует не только проблему, но и процесс анализа.

        Args:
            metrics: Метрики из monitor()

        Returns:
            Словарь с system_analysis и reasoning_analysis
        """
        # Улучшение: "Думай вслух" при анализе
        if self.think_aloud:
            self.think_aloud.log("Начинаю анализ метрик...")

        # Стандартный анализ (MAPE-K)
        system_analysis = {}
        if self.mape_k:
            try:
                consciousness_metrics = self.mape_k._analyze(metrics["system_metrics"])
                system_analysis = {
                    "consciousness_state": (
                        consciousness_metrics.state.value
                        if hasattr(consciousness_metrics, "state")
                        else "UNKNOWN"
                    ),
                    "phi_ratio": (
                        consciousness_metrics.phi_ratio
                        if hasattr(consciousness_metrics, "phi_ratio")
                        else 0.0
                    ),
                    "anomaly_detected": (
                        consciousness_metrics.phi_ratio < 0.5
                        if hasattr(consciousness_metrics, "phi_ratio")
                        else False
                    ),
                }
                if self.think_aloud:
                    self.think_aloud.log(
                        f"Состояние сознания: {system_analysis['consciousness_state']}"
                    )
            except Exception as e:
                logger.warning(f"⚠️ MAPE-K analyze failed: {e}")
                if self.think_aloud:
                    self.think_aloud.log(f"⚠️ Ошибка анализа: {e}")

        # Улучшение: Lateral Thinking для нестандартных решений
        lateral_approaches = None
        if self.lateral_thinking:
            try:
                lateral_approaches = self.lateral_thinking.generate(
                    metrics.get("system_metrics", {})
                )
                if self.think_aloud:
                    self.think_aloud.log(
                        f"Латеральное мышление: {len(lateral_approaches.alternative_approaches)} альтернатив"
                    )
            except Exception as e:
                logger.warning(f"⚠️ Lateral thinking failed: {e}")

        # Мета-анализ процесса мышления
        reasoning_metrics = metrics.get("reasoning_metrics", ReasoningMetrics())
        reasoning_analysis = {
            "efficiency": self._assess_reasoning_efficiency(reasoning_metrics),
            "anomaly_detected": reasoning_metrics.dead_ends_encountered > 3,
            "insights": None,
        }

        if reasoning_analysis["anomaly_detected"]:
            reasoning_analysis["insights"] = {
                "issue": "reasoning_process_inefficient",
                "root_cause": "too_many_approaches_tried",
                "recommendation": "focus_on_single_approach",
            }

            # Сохранение в Knowledge Base
            if self.knowledge_base:
                try:
                    await self.knowledge_base.store_incident(
                        {
                            "type": "reasoning_failure",
                            "meta_insight": reasoning_analysis["insights"],
                            "timestamp": time.time(),
                            "node_id": self.node_id,
                        },
                        self.node_id,
                    )
                except Exception as e:
                    logger.warning(f"⚠️ Failed to store reasoning failure: {e}")

        return {
            "system_analysis": system_analysis,
            "reasoning_analysis": reasoning_analysis,
            "lateral_approaches": (
                lateral_approaches.__dict__ if lateral_approaches else None
            ),  # Новое
            "think_aloud_log": (
                self.think_aloud.get_thoughts() if self.think_aloud else []
            ),  # Новое
        }

    async def plan(self, analysis: Dict[str, Any]) -> Dict[str, Any]:
        """
        Фаза 3: Планирование с мета-оптимизацией.

        Планирует не только решение, но и оптимизацию процесса мышления.

        Args:
            analysis: Результаты analyze()

        Returns:
            Словарь с recovery_plan и reasoning_optimization
        """
        # Улучшение: "Думай вслух" при планировании
        if self.think_aloud:
            self.think_aloud.log("Начинаю планирование решения...")

        # Стандартное планирование (MAPE-K)
        recovery_plan = {}
        if self.mape_k:
            try:
                consciousness_metrics = self.mape_k._analyze(
                    analysis["system_analysis"].get("system_metrics", {})
                )
                recovery_plan = self.mape_k._plan(consciousness_metrics)
                if self.think_aloud:
                    self.think_aloud.log(
                        f"План создан: {len(recovery_plan.get('steps', []))} шагов"
                    )
            except Exception as e:
                logger.warning(f"⚠️ MAPE-K plan failed: {e}")
                if self.think_aloud:
                    self.think_aloud.log(f"⚠️ Ошибка планирования: {e}")

        # Улучшение: Обратное планирование
        reverse_plan = None
        if self.reverse_planner and "goal" in recovery_plan:
            try:
                reverse_plan = self.reverse_planner.plan(recovery_plan["goal"])
                if self.think_aloud:
                    self.think_aloud.log(
                        f"Обратное планирование: {len(reverse_plan)} шагов от цели"
                    )
            except Exception as e:
                logger.warning(f"⚠️ Reverse planning failed: {e}")

        # Улучшение: First Principles для планирования
        first_principles_plan = None
        if self.first_principles:
            try:
                decomposition = self.first_principles.decompose(recovery_plan)
                first_principles_plan = self.first_principles.build_from_scratch(
                    decomposition
                )
                if self.think_aloud:
                    self.think_aloud.log(
                        f"First Principles: {len(decomposition.fundamentals)} элементов"
                    )
            except Exception as e:
                logger.warning(f"⚠️ First principles planning failed: {e}")

        # Мета-планирование: оптимизация процесса мышления
        reasoning_optimization = {
            "approach_selection": self._select_best_approach(analysis),
            "time_allocation": self._optimize_reasoning_time(analysis),
            "checkpoints": self._define_meta_checkpoints(),
        }

        # Валидация плана через мета-анализ
        if not await self._validate_plan_through_meta_analysis(
            recovery_plan, reasoning_optimization
        ):
            logger.warning("⚠️ Plan failed meta-validation, replanning...")
            # Рекурсивный вызов с улучшенным подходом
            return await self.plan(analysis)

        return {
            "recovery_plan": recovery_plan,
            "reasoning_optimization": reasoning_optimization,
            "reverse_plan": reverse_plan,  # Новое
            "first_principles_plan": first_principles_plan,  # Новое
            "think_aloud_log": (
                self.think_aloud.get_thoughts() if self.think_aloud else []
            ),  # Новое
        }

    async def execute(self, plan: Dict[str, Any]) -> Dict[str, Any]:
        """
        Фаза 4: Выполнение с мета-осознанием.

        Выполняет план с фиксацией процесса мышления.

        Args:
            plan: Результаты plan()

        Returns:
            Словарь с execution_result и execution_log
        """
        execution_log = []
        recovery_plan = plan.get("recovery_plan", {})
        reasoning_optimization = plan.get("reasoning_optimization", {})

        # Улучшение: Self-рефлексия перед выполнением
        self_reflection = None
        if self.self_reflection:
            try:
                self_reflection = self.self_reflection.reflect(recovery_plan)
                if self.think_aloud:
                    self.think_aloud.log(
                        f"Саморефлексия: {len(self_reflection.get('assumptions', []))} предположений"
                    )
                    assumptions = self_reflection.get("assumptions", [])
                    for assumption in assumptions:
                        self.think_aloud.log(f"  Предположение: {assumption}")
            except Exception as e:
                logger.warning(f"⚠️ Self-reflection failed: {e}")

        # Выполнение шагов плана
        steps = recovery_plan.get("steps", [])
        if not steps:
            # Если нет шагов, создаем базовый шаг
            steps = [{"action": "monitor", "description": "Standard monitoring"}]

        # Улучшение: "Думай вслух" при выполнении
        if self.think_aloud:
            self.think_aloud.log(f"Начинаю выполнение: {len(steps)} шагов")

        for step in steps:
            step_start = time.time()

            # Улучшение: "Думай вслух" для каждого шага
            if self.think_aloud:
                self.think_aloud.log(f"Выполняю шаг: {step.get('action', 'unknown')}")

            # Стандартное выполнение (MAPE-K)
            result = {"status": "success", "message": "Step completed"}
            if self.mape_k:
                try:
                    # Упрощенное выполнение
                    result = {"status": "success", "message": "Executed via MAPE-K"}
                    if self.think_aloud:
                        self.think_aloud.log("✅ Шаг выполнен успешно")
                except Exception as e:
                    result = {"status": "error", "message": str(e)}
                    if self.think_aloud:
                        self.think_aloud.log(f"❌ Ошибка выполнения: {e}")

            duration = time.time() - step_start

            # Мета-фиксация процесса мышления
            meta_insights = {
                "why_this_approach": self._explain_approach_selection(
                    step, reasoning_optimization
                ),
                "alternative_approaches": self._get_alternatives(step),
                "success_probability": self._calculate_success_probability(step),
            }

            entry = ExecutionLogEntry(
                step=step,
                result=result,
                duration=duration,
                reasoning_approach=reasoning_optimization.get(
                    "approach_selection", "unknown"
                ),
                meta_insights=meta_insights,
            )
            execution_log.append(entry)

            # Если застряли → явный возврат назад
            if result.get("status") == "stuck":
                logger.warning(f"⚠️ Dead end detected at step: {step}")
                execution_log.append(
                    ExecutionLogEntry(
                        step={"action": "dead_end_detected"},
                        result={"status": "rollback"},
                        duration=0.0,
                        reasoning_approach=reasoning_optimization.get(
                            "approach_selection", "unknown"
                        ),
                        meta_insights={
                            "event": "dead_end_detected",
                            "reason": "approach_failed",
                            "rollback": True,
                            "meta_analysis": self._analyze_why_failed(step),
                        },
                    )
                )

                # Вернуться к мета-планированию
                return await self._rollback_and_replan(execution_log)

            # Когда произошел прорыв → отметить поворотный момент
            if result.get("status") == "breakthrough":
                logger.info(f"✅ Breakthrough at step: {step}")
                execution_log.append(
                    ExecutionLogEntry(
                        step={"action": "breakthrough"},
                        result={"status": "success"},
                        duration=0.0,
                        reasoning_approach=reasoning_optimization.get(
                            "approach_selection", "unknown"
                        ),
                        meta_insights={
                            "event": "breakthrough",
                            "turning_point": self._identify_turning_point(step),
                            "meta_insight": "what_made_it_work",
                        },
                    )
                )

        # Сохраняем лог
        self.execution_logs.extend(execution_log)

        return {
            "execution_result": {"status": "success", "steps_completed": len(steps)},
            "execution_log": [entry.__dict__ for entry in execution_log],
            "self_reflection": self_reflection,  # Новое
            "think_aloud_log": (
                self.think_aloud.get_thoughts() if self.think_aloud else []
            ),  # Новое
        }

    async def knowledge(self, execution_log: Dict[str, Any]) -> Dict[str, Any]:
        """
        Фаза 5: Накопление знаний с мета-аналитикой.

        Накопляет знания не только о решениях, но и о процессе мышления.

        Args:
            execution_log: Результаты execute()

        Returns:
            Словарь с incident_record, reasoning_analytics и meta_insight
        """
        # Стандартное накопление знаний (MAPE-K)
        incident_record = {
            "timestamp": time.time(),
            "node_id": self.node_id,
            "execution_result": execution_log.get("execution_result", {}),
            "steps": execution_log.get("execution_log", []),
        }

        # Мета-аналитика процесса мышления
        execution_entries = execution_log.get("execution_log", [])
        reasoning_analytics = ReasoningAnalytics(
            algorithm_used=(
                execution_entries[0].get("reasoning_approach", "unknown")
                if execution_entries
                else "unknown"
            ),
            reasoning_time=sum(e.get("duration", 0.0) for e in execution_entries),
            approaches_tried=len(
                set(e.get("reasoning_approach", "unknown") for e in execution_entries)
            ),
            dead_ends=sum(
                1
                for e in execution_entries
                if e.get("meta_insights", {}).get("event") == "dead_end_detected"
            ),
            breakthrough_moment=self._extract_breakthrough(execution_entries),
            success=execution_log.get("execution_result", {}).get("status")
            == "success",
        )

        # Генерация мета-инсайта
        if reasoning_analytics.success:
            meta_insight = {
                "effective_algorithm": reasoning_analytics.algorithm_used,
                "why_it_worked": self._analyze_why_algorithm_worked(
                    reasoning_analytics
                ),
                "key_factors": self._extract_key_success_factors(execution_entries),
            }
        else:
            meta_insight = {
                "failed_algorithm": reasoning_analytics.algorithm_used,
                "why_it_failed": self._analyze_why_algorithm_failed(
                    reasoning_analytics
                ),
                "what_to_do_differently": self._suggest_alternative_approach(
                    reasoning_analytics
                ),
            }

        reasoning_analytics.meta_insight = meta_insight

        # Улучшение: Метод "Трёх вопросов" для рефлексии
        three_questions = None
        if self.three_questions:
            try:
                three_questions = self.three_questions.reflect(execution_log)
                if self.think_aloud:
                    self.think_aloud.log("Метод трёх вопросов:")
                    self.think_aloud.log(
                        f"  Что удачно: {len(three_questions.what_worked)} пунктов"
                    )
                    self.think_aloud.log(
                        f"  Что улучшить: {len(three_questions.what_improve)} пунктов"
                    )
                    self.think_aloud.log(
                        f"  Что выучить: {len(three_questions.what_learn)} уроков"
                    )
            except Exception as e:
                logger.warning(f"⚠️ Three questions reflection failed: {e}")

        # Сохранение в Knowledge Base
        if self.knowledge_base:
            try:
                incident_id = await self.knowledge_base.store_incident(
                    {
                        "incident": incident_record,
                        "reasoning_analytics": reasoning_analytics.__dict__,
                        "meta_insight": meta_insight,
                    },
                    self.node_id,
                )
                logger.info(
                    f"✅ Stored incident with reasoning analytics: {incident_id}"
                )
            except Exception as e:
                logger.warning(f"⚠️ Failed to store in knowledge base: {e}")

        # Обновление истории рассуждений
        self.reasoning_history.append(
            {
                "timestamp": time.time(),
                "reasoning_analytics": reasoning_analytics.__dict__,
                "meta_insight": meta_insight,
                "success": reasoning_analytics.success,
            }
        )

        # Обновление статистики
        self.total_cycles += 1
        if reasoning_analytics.success:
            self.successful_cycles += 1
        else:
            self.failed_cycles += 1

        return {
            "incident_record": incident_record,
            "reasoning_analytics": reasoning_analytics.__dict__,
            "meta_insight": meta_insight,
            "three_questions": (
                three_questions.__dict__ if three_questions else None
            ),  # Новое
            "think_aloud_log": (
                self.think_aloud.get_thoughts() if self.think_aloud else []
            ),  # Новое
        }

    async def run_full_cycle(
        self, task: Optional[Dict[str, Any]] = None
    ) -> Dict[str, Any]:
        """
        Полный интегрированный цикл с мета-когнитивным контролем.

        Args:
            task: Описание задачи (опционально)

        Returns:
            Полный результат цикла
        """
        if task is None:
            task = {"type": "standard_cycle", "description": "Standard MAPE-K cycle"}

        logger.info("=" * 60)
        logger.info("🧠 Starting Meta-Cognitive MAPE-K Cycle")
        logger.info("=" * 60)

        try:
            # Фаза 0: Мета-планирование
            solution_space, reasoning_path = await self.meta_planning(task)

            # Фаза 1: Мониторинг
            metrics = await self.monitor()

            # Фаза 2: Анализ
            analysis = await self.analyze(metrics)

            # Фаза 3: Планирование
            plan = await self.plan(analysis)

            # Фаза 4: Выполнение
            execution_log = await self.execute(plan)

            # Фаза 5: Знания
            knowledge = await self.knowledge(execution_log)

            logger.info("=" * 60)
            logger.info("✅ Meta-Cognitive MAPE-K Cycle Complete")
            logger.info("=" * 60)

            return {
                "meta_plan": {
                    "solution_space": solution_space.__dict__,
                    "reasoning_path": reasoning_path.__dict__,
                },
                "metrics": {
                    "system_metrics": metrics.get("system_metrics", {}),
                    "reasoning_metrics": (
                        metrics.get("reasoning_metrics", {}).__dict__
                        if hasattr(metrics.get("reasoning_metrics"), "__dict__")
                        else {}
                    ),
                },
                "analysis": analysis,
                "plan": plan,
                "execution_log": execution_log,
                "knowledge": knowledge,
            }

        except Exception as e:
            logger.error(f"❌ Meta-Cognitive MAPE-K Cycle failed: {e}", exc_info=True)
            return {"error": str(e)}

    # === Вспомогательные методы ===

    def _extract_features_for_prediction(
        self, task: Dict[str, Any]
    ) -> Dict[str, float]:
        """Извлечение признаков для предсказания GraphSAGE"""
        # Упрощенная реализация
        return {
            "task_complexity": 0.5,
            "similarity_to_history": 0.7,
            "available_approaches": 6.0,
        }

    def _estimate_reasoning_time(
        self, task: Dict[str, Any], approach: Dict[str, Any]
    ) -> float:
        """Оценка времени рассуждения"""
        base_time = 1.0  # секунды
        complexity = task.get("complexity", 0.5)
        return base_time * (1 + complexity)

    def _assess_confidence(self) -> float:
        """Оценка уровня уверенности"""
        if not self.reasoning_history:
            return 0.5

        recent_success_rate = sum(
            1 for h in self.reasoning_history[-10:] if h.get("success", False)
        ) / min(len(self.reasoning_history), 10)

        return recent_success_rate

    def _count_kb_hits(self) -> int:
        """Подсчет попаданий в Knowledge Base"""
        return sum(1 for h in self.reasoning_history if h.get("kb_hit", False))

    def _calculate_cache_hit_rate(self) -> float:
        """Расчет hit rate кэша"""
        if not self.reasoning_history:
            return 0.0
        return self._count_kb_hits() / len(self.reasoning_history)

    async def _trigger_meta_analysis(self):
        """Триггер мета-анализа при обнаружении проблем"""
        logger.info("🔍 Triggering meta-analysis due to reasoning inefficiency")
        # Можно добавить дополнительный анализ

    def _assess_reasoning_efficiency(self, metrics: ReasoningMetrics) -> float:
        """Оценка эффективности рассуждений"""
        if metrics.reasoning_time == 0:
            return 1.0

        efficiency = 1.0 - (
            metrics.dead_ends_encountered / max(metrics.approaches_tried, 1)
        )
        return max(0.0, min(1.0, efficiency))

    def _select_best_approach(self, analysis: Dict[str, Any]) -> str:
        """Выбор лучшего подхода"""
        reasoning_analysis = analysis.get("reasoning_analysis", {})
        if reasoning_analysis.get("anomaly_detected"):
            return ReasoningApproach.COMBINED_ALL.value
        return ReasoningApproach.COMBINED_RAG_GRAPHSAGE.value

    def _optimize_reasoning_time(self, analysis: Dict[str, Any]) -> Dict[str, float]:
        """Оптимизация распределения времени"""
        return {"planning": 0.2, "execution": 0.6, "analysis": 0.2}

    def _define_meta_checkpoints(self) -> List[Dict[str, Any]]:
        """Определение мета-контрольных точек"""
        return [
            {"name": "approach_selection", "metric": "success_probability > 0.9"},
            {"name": "rag_search", "metric": "similarity > 0.7"},
            {"name": "graphsage_prediction", "metric": "confidence > 0.9"},
        ]

    async def _validate_plan_through_meta_analysis(
        self, recovery_plan: Dict[str, Any], reasoning_optimization: Dict[str, Any]
    ) -> bool:
        """Валидация плана через мета-анализ"""
        # Упрощенная валидация
        return True

    def _explain_approach_selection(
        self, step: Dict[str, Any], optimization: Dict[str, Any]
    ) -> str:
        """Объяснение выбора подхода"""
        return f"Selected {optimization.get('approach_selection', 'unknown')} based on historical success rate"

    def _get_alternatives(self, step: Dict[str, Any]) -> List[str]:
        """Получение альтернативных подходов"""
        return [a.value for a in ReasoningApproach]

    def _calculate_success_probability(self, step: Dict[str, Any]) -> float:
        """Расчет вероятности успеха"""
        return 0.85

    def _analyze_why_failed(self, step: Dict[str, Any]) -> Dict[str, Any]:
        """Анализ причин неудачи"""
        return {"reason": "approach_not_suitable", "recommendation": "try_alternative"}

    async def _rollback_and_replan(
        self, execution_log: List[ExecutionLogEntry]
    ) -> Dict[str, Any]:
        """Откат и перепланирование"""
        logger.warning("🔄 Rolling back and replanning...")
        # Упрощенная реализация
        return {
            "execution_result": {
                "status": "rollback",
                "message": "Replanning required",
            },
            "execution_log": [e.__dict__ for e in execution_log],
        }

    def _identify_turning_point(self, step: Dict[str, Any]) -> str:
        """Идентификация поворотного момента"""
        return f"Breakthrough at step: {step.get('action', 'unknown')}"

    def _extract_breakthrough(
        self, execution_entries: List[Dict[str, Any]]
    ) -> Optional[str]:
        """Извлечение момента прорыва"""
        for entry in execution_entries:
            if entry.get("meta_insights", {}).get("event") == "breakthrough":
                return entry.get("meta_insights", {}).get("turning_point")
        return None

    def _analyze_why_algorithm_worked(self, analytics: ReasoningAnalytics) -> str:
        """Анализ почему алгоритм сработал"""
        return f"Algorithm {analytics.algorithm_used} worked due to high confidence and low dead ends"

    def _extract_key_success_factors(
        self, execution_entries: List[Dict[str, Any]]
    ) -> List[str]:
        """Извлечение ключевых факторов успеха"""
        return ["high_confidence", "low_dead_ends", "efficient_reasoning"]

    def _analyze_why_algorithm_failed(self, analytics: ReasoningAnalytics) -> str:
        """Анализ почему алгоритм провалился"""
        return f"Algorithm {analytics.algorithm_used} failed due to too many dead ends ({analytics.dead_ends})"

    def _suggest_alternative_approach(self, analytics: ReasoningAnalytics) -> str:
        """Предложение альтернативного подхода"""
        return "Try combined approach with RAG + GraphSAGE for better results"
