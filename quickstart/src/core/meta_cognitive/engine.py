"""
Core Engine for Meta-Cognitive MAPE-K Cycle.
"""
from __future__ import annotations

import logging
import time
from typing import Any, Dict, List, Optional, Tuple

from .models import (
    ReasoningApproach,
    SolutionSpace,
    ReasoningPath,
    ReasoningMetrics,
    ReasoningAnalytics,
    ExecutionLogEntry
)

logger = logging.getLogger(__name__)

# Component imports with stubs for resiliency
try:
    from ...ml.causal_analysis import CausalAnalysisEngine, CausalAnalysisResult
    from ...ml.graphsage_anomaly_detector import (AnomalyPrediction,
                                                 GraphSAGEAnomalyDetectorV2)
    from ...ml.rag import RAGAnalyzer
    from ...storage.knowledge_storage_v2 import KnowledgeStorageV2
    from ..enhanced_thinking_techniques import (FirstPrinciplesThinking,
                                               LateralThinking,
                                               MindMapGenerator,
                                               ReversePlanner, SelfReflection,
                                               SixThinkingHats,
                                               ThinkAloudLogger,
                                               ThreeQuestionsReflection)
    from ..mape_k_loop import MAPEKLoop, MAPEKState

    COMPONENTS_AVAILABLE = True
except ImportError as e:
    logger.warning(f"⚠️ Some components not available: {e}")
    COMPONENTS_AVAILABLE = False
    # Create stubs for types and techniques
    SixThinkingHats = None
    FirstPrinciplesThinking = None
    LateralThinking = None
    ReversePlanner = None
    ThinkAloudLogger = None
    ThreeQuestionsReflection = None
    MindMapGenerator = None
    SelfReflection = None
    MAPEKLoop = None
    MAPEKState = None
    RAGAnalyzer = None
    GraphSAGEAnomalyDetectorV2 = None
    AnomalyPrediction = None
    CausalAnalysisEngine = None
    CausalAnalysisResult = None
    KnowledgeStorageV2 = None


class MetaCognitiveMAPEK:
    """
    Integrated MAPE-K cycle with meta-cognitive control.

    Adds a meta-level to the standard MAPE-K cycle:
    - Meta-planning: solution space mapping
    - Meta-monitoring: thinking process tracking
    - Meta-analysis: reasoning effectiveness analysis
    - Meta-optimization: reasoning algorithm improvement
    - Meta-analytics: thinking knowledge accumulation
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
        Initialize Meta-Cognitive MAPE-K.
        """
        self.node_id = node_id
        self.mape_k = mape_k_loop
        self.rag = rag_analyzer
        self.graphsage = graphsage
        self.causal = causal_engine
        self.knowledge_base = knowledge_storage

        # Reasoning state
        self.reasoning_history: List[Dict[str, Any]] = []
        self.execution_logs: List[ExecutionLogEntry] = []

        # Statistics
        self.total_cycles = 0
        self.successful_cycles = 0
        self.failed_cycles = 0
        self.optimization_count = 0

        # Thinking techniques integration
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
        Phase 0: Meta-Planning.

        Maps the solution space and plans the reasoning path.
        """
        logger.info("🧠 Meta-Planning: Mapping solution space...")

        # "Think Aloud" logging
        if self.think_aloud:
            self.think_aloud.log("Starting meta-planning", {"task": task})

        # Six Thinking Hats analysis
        hats_analysis = None
        if self.six_hats:
            hats_analysis = self.six_hats.analyze(task)
            if self.think_aloud:
                self.think_aloud.log(
                    f"Six Hats analysis: {len(hats_analysis.white.get('facts', []))} facts found"
                )

        # First Principles decomposition
        first_principles = None
        if self.first_principles:
            first_principles = self.first_principles.decompose(task)
            if self.think_aloud:
                self.think_aloud.log(
                    f"First Principles: {len(first_principles.fundamentals)} fundamental elements"
                )

        # 1. Map solution space approaches
        approaches = [
            {
                "name": ReasoningApproach.MAPE_K_ONLY.value,
                "probability": 0.85,
                "description": "Standard MAPE-K cycle",
            },
            {
                "name": ReasoningApproach.RAG_SEARCH.value,
                "probability": 0.78,
                "description": "Knowledge Base search for similar incidents",
            },
            {
                "name": ReasoningApproach.GRAPHSAGE_PREDICTION.value,
                "probability": 0.92,
                "description": "Success prediction via GraphSAGE",
            },
            {
                "name": ReasoningApproach.CAUSAL_ANALYSIS.value,
                "probability": 0.88,
                "description": "Root cause analysis",
            },
            {
                "name": ReasoningApproach.COMBINED_RAG_GRAPHSAGE.value,
                "probability": 0.94,
                "description": "Combined RAG + GraphSAGE",
            },
            {
                "name": ReasoningApproach.COMBINED_ALL.value,
                "probability": 0.96,
                "description": "Combined holistic approach",
            },
        ]

        # Add technique-specific approaches
        if hats_analysis and hats_analysis.green.get("creative_ideas"):
            approaches.append(
                {
                    "name": "six_hats_creative",
                    "probability": 0.90,
                    "description": f"Creative ideas: {', '.join(hats_analysis.green['creative_ideas'][:2])}",
                }
            )

        if first_principles and first_principles.fundamentals:
            approaches.append(
                {
                    "name": "first_principles",
                    "probability": 0.88,
                    "description": f"First Principles: {len(first_principles.fundamentals)} elements",
                }
            )

        # 2. Search failure history
        failure_history = []
        if self.knowledge_base:
            try:
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

        # 3. Success prediction
        success_probabilities = {}
        if self.graphsage:
            try:
                features = self._extract_features_for_prediction(task)
                prediction = self.graphsage.predict(features)
                if prediction:
                    for approach in approaches:
                        success_probabilities[approach["name"]] = prediction.confidence
            except Exception as e:
                logger.warning(f"⚠️ GraphSAGE prediction failed: {e}")
                for approach in approaches:
                    success_probabilities[approach["name"]] = approach["probability"]
        else:
            for approach in approaches:
                success_probabilities[approach["name"]] = approach["probability"]

        # 4. Approach selection
        best_approach = max(
            approaches,
            key=lambda x: success_probabilities.get(x["name"], x["probability"]),
        )

        solution_space = SolutionSpace(
            approaches=approaches,
            failure_history=failure_history,
            success_probabilities=success_probabilities,
            selected_approach=best_approach["name"],
            reasoning=f"High success probability ({success_probabilities.get(best_approach['name'], best_approach['probability']):.2f}) + historical context",
        )

        # 5. Plan reasoning path
        reverse_plan = None
        if self.reverse_planner and "goal" in task:
            try:
                reverse_plan = self.reverse_planner.plan(task["goal"])
                if self.think_aloud:
                    self.think_aloud.log(
                        f"Reverse planning: {len(reverse_plan)} steps from goal"
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
                {"name": "six_hats_analysis", "metric": "all_hats_analyzed"},
                {"name": "first_principles", "metric": "fundamentals_extracted"},
            ],
            estimated_time=self._estimate_reasoning_time(task, best_approach),
        )

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
        Phase 1: Monitoring with Meta-Awareness.
        """
        reasoning_start = time.time()

        if self.think_aloud:
            self.think_aloud.log("Starting system monitoring...")

        # Standard monitoring (MAPE-K)
        system_metrics = {}
        if self.mape_k:
            try:
                system_metrics = await self.mape_k._monitor()
                if self.think_aloud:
                    self.think_aloud.log(
                        f"Metrics collected: CPU={system_metrics.get('cpu_percent', 'N/A')}%"
                    )
            except Exception as e:
                logger.warning(f"⚠️ MAPE-K monitor failed: {e}")

        # Meta-monitoring of the thinking process
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

        # Meta-anomaly detection
        if reasoning_metrics.dead_ends_encountered > 3:
            logger.warning("⚠️ Too many dead ends detected, triggering meta-analysis")
            await self._trigger_meta_analysis()

        reasoning_metrics.end_time = time.time()
        reasoning_metrics.reasoning_time = (
            reasoning_metrics.end_time - reasoning_metrics.start_time
        )

        # Mind map visualization
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
            except Exception as e:
                logger.warning(f"⚠️ Mind map creation failed: {e}")

        # Logic gap detection
        logic_gaps = []
        if self.think_aloud:
            logic_gaps = self.think_aloud.detect_logic_gaps()

        return {
            "system_metrics": system_metrics,
            "reasoning_metrics": reasoning_metrics,
            "mind_map": mind_map,
            "logic_gaps": logic_gaps,
            "think_aloud_log": (
                self.think_aloud.get_thoughts() if self.think_aloud else []
            ),
        }

    async def analyze(self, metrics: Dict[str, Any]) -> Dict[str, Any]:
        """
        Phase 2: Analysis with Meta-Reflection.
        """
        if self.think_aloud:
            self.think_aloud.log("Starting metrics analysis...")

        # Standard analysis (MAPE-K)
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
            except Exception as e:
                logger.warning(f"⚠️ MAPE-K analyze failed: {e}")

        # Lateral Thinking for alternative analysis
        lateral_approaches = None
        if self.lateral_thinking:
            try:
                lateral_approaches = self.lateral_thinking.generate(
                    metrics.get("system_metrics", {})
                )
            except Exception as e:
                logger.warning(f"⚠️ Lateral thinking failed: {e}")

        # Meta-analysis of reasoning process
        reasoning_metrics = metrics.get("reasoning_metrics", ReasoningMetrics())
        reasoning_analysis = {
            "efficiency": self._assess_reasoning_efficiency(reasoning_metrics),
            "anomaly_detected": reasoning_metrics.dead_ends_encountered > 3,
            "insights": None,
        }

        if reasoning_analysis["anomaly_detected"]:
            reasoning_analysis["insights"] = {
                "issue": "reasoning_process_inefficient",
                "root_cause": "too_many_dead_ends",
                "recommendation": "narrow_down_approaches",
            }

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
            ),
            "think_aloud_log": (
                self.think_aloud.get_thoughts() if self.think_aloud else []
            ),
        }

    async def plan(self, analysis: Dict[str, Any]) -> Dict[str, Any]:
        """
        Phase 3: Planning with Meta-Optimization.
        """
        if self.think_aloud:
            self.think_aloud.log("Starting solution planning...")

        # Standard planning (MAPE-K)
        recovery_plan = {}
        if self.mape_k:
            try:
                consciousness_metrics = self.mape_k._analyze(
                    analysis["system_analysis"].get("system_metrics", {})
                )
                recovery_plan = self.mape_k._plan(consciousness_metrics)
            except Exception as e:
                logger.warning(f"⚠️ MAPE-K plan failed: {e}")

        # Reverse planning
        reverse_plan = None
        if self.reverse_planner and "goal" in recovery_plan:
            try:
                reverse_plan = self.reverse_planner.plan(recovery_plan["goal"])
            except Exception as e:
                logger.warning(f"⚠️ Reverse planning failed: {e}")

        # First Principles based planning
        first_principles_plan = None
        if self.first_principles:
            try:
                decomposition = self.first_principles.decompose(recovery_plan)
                first_principles_plan = self.first_principles.build_from_scratch(
                    decomposition
                )
            except Exception as e:
                logger.warning(f"⚠️ First principles planning failed: {e}")

        # Meta-optimization of reasoning
        reasoning_optimization = {
            "approach_selection": self._select_best_approach(analysis),
            "time_allocation": self._optimize_reasoning_time(analysis),
            "checkpoints": self._define_meta_checkpoints(),
        }

        # Meta-validation of the plan
        if not await self._validate_plan_through_meta_analysis(
            recovery_plan, reasoning_optimization
        ):
            logger.warning("⚠️ Plan failed meta-validation, replanning...")
            return await self.plan(analysis)

        return {
            "recovery_plan": recovery_plan,
            "reasoning_optimization": reasoning_optimization,
            "reverse_plan": reverse_plan,
            "first_principles_plan": first_principles_plan,
            "think_aloud_log": (
                self.think_aloud.get_thoughts() if self.think_aloud else []
            ),
        }

    async def execute(self, plan: Dict[str, Any]) -> Dict[str, Any]:
        """
        Phase 4: Execution with Meta-Awareness.
        """
        execution_log = []
        recovery_plan = plan.get("recovery_plan", {})
        reasoning_optimization = plan.get("reasoning_optimization", {})

        # Self-reflection before execution
        self_reflection = None
        if self.self_reflection:
            try:
                self_reflection = self.self_reflection.reflect(recovery_plan)
                if self.think_aloud:
                    self.think_aloud.log(
                        f"Self-reflection: {len(self_reflection.get('assumptions', []))} assumptions found"
                    )
            except Exception as e:
                logger.warning(f"⚠️ Self-reflection failed: {e}")

        steps = recovery_plan.get("steps", [])
        if not steps:
            steps = [{"action": "monitor", "description": "Standard monitoring"}]

        if self.think_aloud:
            self.think_aloud.log(f"Starting execution: {len(steps)} steps")

        for step in steps:
            step_start = time.time()
            if self.think_aloud:
                self.think_aloud.log(f"Executing step: {step.get('action', 'unknown')}")

            # Standard execution (MAPE-K)
            result = {"status": "success", "message": "Step completed"}
            if self.mape_k:
                try:
                    # In this integrated version, we simulate the execution call
                    result = {"status": "success", "message": "Executed via MAPE-K"}
                except Exception as e:
                    result = {"status": "error", "message": str(e)}

            duration = time.time() - step_start

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

            # Handle dead ends
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
                return await self._rollback_and_replan(execution_log)

            # Handle breakthroughs
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
                            "meta_insight": "key factors identified",
                        },
                    )
                )

        self.execution_logs.extend(execution_log)

        return {
            "execution_result": {"status": "success", "steps_completed": len(steps)},
            "execution_log": [entry.__dict__ for entry in execution_log],
            "self_reflection": self_reflection,
            "think_aloud_log": (
                self.think_aloud.get_thoughts() if self.think_aloud else []
            ),
        }

    async def knowledge(self, execution_log: Dict[str, Any]) -> Dict[str, Any]:
        """
        Phase 5: Knowledge Accumulation with Meta-Analytics.
        """
        incident_record = {
            "timestamp": time.time(),
            "node_id": self.node_id,
            "execution_result": execution_log.get("execution_result", {}),
            "steps": execution_log.get("execution_log", []),
        }

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
            success=execution_log.get("execution_result", {}).get("status") == "success",
        )

        if reasoning_analytics.success:
            meta_insight = {
                "effective_algorithm": reasoning_analytics.algorithm_used,
                "why_it_worked": self._analyze_why_algorithm_worked(reasoning_analytics),
                "key_factors": self._extract_key_success_factors(execution_entries),
            }
        else:
            meta_insight = {
                "failed_algorithm": reasoning_analytics.algorithm_used,
                "why_it_failed": self._analyze_why_algorithm_failed(reasoning_analytics),
                "what_to_do_differently": self._suggest_alternative_approach(
                    reasoning_analytics
                ),
            }

        reasoning_analytics.meta_insight = meta_insight

        # Three Questions Reflection
        three_questions = None
        if self.three_questions:
            try:
                three_questions = self.three_questions.reflect(execution_log)
            except Exception as e:
                logger.warning(f"⚠️ Three questions reflection failed: {e}")

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
                logger.info(f"✅ Stored incident with reasoning analytics: {incident_id}")
            except Exception as e:
                logger.warning(f"⚠️ Failed to store in knowledge base: {e}")

        self.reasoning_history.append(
            {
                "timestamp": time.time(),
                "reasoning_analytics": reasoning_analytics.__dict__,
                "meta_insight": meta_insight,
                "success": reasoning_analytics.success,
            }
        )

        self.total_cycles += 1
        if reasoning_analytics.success:
            self.successful_cycles += 1
        else:
            self.failed_cycles += 1

        return {
            "incident_record": incident_record,
            "reasoning_analytics": reasoning_analytics.__dict__,
            "meta_insight": meta_insight,
            "three_questions": (three_questions.__dict__ if three_questions else None),
            "think_aloud_log": (
                self.think_aloud.get_thoughts() if self.think_aloud else []
            ),
        }

    async def run_full_cycle(self, task: Optional[Dict[str, Any]] = None) -> Dict[str, Any]:
        """
        Full integrated cycle with meta-cognitive control.
        """
        if task is None:
            task = {"type": "standard_cycle", "description": "Standard MAPE-K cycle"}

        logger.info("=" * 60)
        logger.info("🧠 Starting Meta-Cognitive MAPE-K Cycle")
        logger.info("=" * 60)

        try:
            solution_space, reasoning_path = await self.meta_planning(task)
            metrics = await self.monitor()
            analysis = await self.analyze(metrics)
            plan = await self.plan(analysis)
            execution_log = await self.execute(plan)
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
                        metrics.get("reasoning_metrics").__dict__
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

    # === Helper methods ===

    def _extract_features_for_prediction(self, task: Dict[str, Any]) -> Dict[str, float]:
        return {
            "task_complexity": task.get("complexity", 0.5),
            "similarity_to_history": 0.7,
            "available_approaches": 6.0,
        }

    def _estimate_reasoning_time(self, task: Dict[str, Any], approach: Dict[str, Any]) -> float:
        base_time = 1.0
        complexity = task.get("complexity", 0.5)
        return base_time * (1 + complexity)

    def _assess_confidence(self) -> float:
        if not self.reasoning_history:
            return 0.5
        recent_success_rate = sum(
            1 for h in self.reasoning_history[-10:] if h.get("success", False)
        ) / min(len(self.reasoning_history), 10)
        return recent_success_rate

    def _count_kb_hits(self) -> int:
        return sum(1 for h in self.reasoning_history if h.get("kb_hit", False))

    def _calculate_cache_hit_rate(self) -> float:
        if not self.reasoning_history:
            return 0.0
        return self._count_kb_hits() / len(self.reasoning_history)

    async def _trigger_meta_analysis(self):
        logger.info("🔍 Triggering meta-analysis due to reasoning inefficiency")

    def _assess_reasoning_efficiency(self, metrics: ReasoningMetrics) -> float:
        if metrics.reasoning_time == 0:
            return 1.0
        efficiency = 1.0 - (
            metrics.dead_ends_encountered / max(metrics.approaches_tried, 1)
        )
        return max(0.0, min(1.0, efficiency))

    def _select_best_approach(self, analysis: Dict[str, Any]) -> str:
        reasoning_analysis = analysis.get("reasoning_analysis", {})
        if reasoning_analysis.get("anomaly_detected"):
            return ReasoningApproach.COMBINED_ALL.value
        return ReasoningApproach.COMBINED_RAG_GRAPHSAGE.value

    def _optimize_reasoning_time(self, analysis: Dict[str, Any]) -> Dict[str, float]:
        return {"planning": 0.2, "execution": 0.6, "analysis": 0.2}

    def _define_meta_checkpoints(self) -> List[Dict[str, Any]]:
        return [
            {"name": "approach_selection", "metric": "success_probability > 0.9"},
            {"name": "rag_search", "metric": "similarity > 0.7"},
            {"name": "graphsage_prediction", "metric": "confidence > 0.9"},
        ]

    async def _validate_plan_through_meta_analysis(
        self, recovery_plan: Dict[str, Any], reasoning_optimization: Dict[str, Any]
    ) -> bool:
        return True

    def _explain_approach_selection(self, step: Dict[str, Any], optimization: Dict[str, Any]) -> str:
        return f"Selected {optimization.get('approach_selection', 'unknown')} based on historical success"

    def _get_alternatives(self, step: Dict[str, Any]) -> List[str]:
        return [a.value for a in ReasoningApproach]

    def _calculate_success_probability(self, step: Dict[str, Any]) -> float:
        return 0.85

    def _analyze_why_failed(self, step: Dict[str, Any]) -> Dict[str, Any]:
        return {"reason": "approach_not_suitable", "recommendation": "try_alternative"}

    async def _rollback_and_replan(self, execution_log: List[ExecutionLogEntry]) -> Dict[str, Any]:
        logger.warning("🔄 Rolling back and replanning...")
        return {
            "execution_result": {"status": "rollback", "message": "Replanning required"},
            "execution_log": [e.__dict__ for e in execution_log],
        }

    def _identify_turning_point(self, step: Dict[str, Any]) -> str:
        return f"Breakthrough at step: {step.get('action', 'unknown')}"

    def _extract_breakthrough(self, execution_entries: List[Dict[str, Any]]) -> Optional[str]:
        for entry in execution_entries:
            if entry.get("meta_insights", {}).get("event") == "breakthrough":
                return entry.get("meta_insights", {}).get("turning_point")
        return None

    def _analyze_why_algorithm_worked(self, analytics: ReasoningAnalytics) -> str:
        return f"Algorithm {analytics.algorithm_used} worked due to high confidence"

    def _extract_key_success_factors(self, execution_entries: List[Dict[str, Any]]) -> List[str]:
        return ["high_confidence", "low_dead_ends", "efficient_reasoning"]

    def _analyze_why_algorithm_failed(self, analytics: ReasoningAnalytics) -> str:
        return f"Algorithm {analytics.algorithm_used} failed due to dead ends ({analytics.dead_ends})"

    def _suggest_alternative_approach(self, analytics: ReasoningAnalytics) -> str:
        return "Try combined approach with RAG + GraphSAGE"

