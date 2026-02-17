"""
MAPE-K Cycle с интеграцией всех новых компонентов
Готово для demo и sales presentations
"""

import logging
import time
from datetime import datetime
from typing import Any, Dict, Optional

from src.self_healing.mape_k import (MAPEKAnalyzer, MAPEKExecutor,
                                     MAPEKKnowledge, MAPEKMonitor,
                                     MAPEKPlanner)

# Новые компоненты
try:
    from src.ml.graphsage_observe_mode import (DetectorMode,
                                               GraphSAGEObserveMode)

    OBSERVE_MODE_AVAILABLE = True
except ImportError:
    OBSERVE_MODE_AVAILABLE = False
    logging.warning("GraphSAGE Observe Mode not available")

try:
    from src.chaos.controller import ChaosController, ExperimentType

    CHAOS_AVAILABLE = True
except ImportError:
    CHAOS_AVAILABLE = False
    logging.warning("Chaos Controller not available")

try:
    from src.network.ebpf.explainer import (EBPFEvent, EBPFEventType,
                                            EBPFExplainer)

    EBPF_EXPLAINER_AVAILABLE = True
except ImportError:
    EBPF_EXPLAINER_AVAILABLE = False
    logging.warning("eBPF Explainer not available")

logger = logging.getLogger(__name__)


class IntegratedMAPEKCycle:
    """
    Полностью интегрированный MAPE-K цикл со всеми новыми компонентами

    Готов для:
    - Demo presentations
    - Sales calls
    - Production deployment
    """

    def __init__(
        self,
        enable_observe_mode: bool = True,
        enable_chaos: bool = True,
        enable_ebpf_explainer: bool = True,
    ):
        # Базовый MAPE-K цикл
        self.knowledge = MAPEKKnowledge()
        self.monitor = MAPEKMonitor(knowledge=self.knowledge)
        self.analyzer = MAPEKAnalyzer()
        self.planner = MAPEKPlanner(knowledge=self.knowledge)
        self.executor = MAPEKExecutor()

        # self.cycle = MAPEKCycle(
        #     monitor=self.monitor,
        #     analyzer=self.analyzer,
        #     planner=self.planner,
        #     executor=self.executor,
        #     knowledge=self.knowledge
        # )

        # Интеграция GraphSAGE Observe Mode
        self.observe_detector = None
        if enable_observe_mode and OBSERVE_MODE_AVAILABLE:
            self.observe_detector = GraphSAGEObserveMode(
                mode=DetectorMode.OBSERVE, threshold=0.95, confidence_required=0.90
            )
            # Интегрировать с Monitor
            self.monitor.enable_graphsage()
            logger.info("GraphSAGE Observe Mode integrated")

        # Интеграция Chaos Controller
        self.chaos_controller = None
        if enable_chaos and CHAOS_AVAILABLE:
            self.chaos_controller = ChaosController()
            logger.info("Chaos Controller integrated")

        # Интеграция eBPF Explainer
        self.ebpf_explainer = None
        if enable_ebpf_explainer and EBPF_EXPLAINER_AVAILABLE:
            self.ebpf_explainer = EBPFExplainer()
            logger.info("eBPF Explainer integrated")

        logger.info("Integrated MAPE-K Cycle initialized with all components")

    def run_cycle(self, metrics: Dict[str, Any]) -> Dict[str, Any]:
        """
        Запустить полный MAPE-K цикл с интеграцией всех компонентов

        Returns:
            Результаты цикла с объяснениями от всех компонентов
        """
        cycle_id = f"cycle_{int(time.time() * 1000)}"
        node_id = metrics.get("node_id", "unknown")

        # 0. Tracing: Start full cycle trace with distributed tracing
        tracing = None
        try:
            from src.monitoring.tracing import get_tracing_manager

            tracing = get_tracing_manager()
        except Exception:
            pass

        # Use improved tracing with full cycle context
        cycle_trace = None
        if tracing:
            cycle_trace = tracing.trace_full_mape_k_cycle(cycle_id, node_id)
        else:
            from contextlib import nullcontext

            cycle_trace = nullcontext()

        with cycle_trace:
            # 1. Monitor: Обнаружение аномалий with tracing
            monitor_trace = None
            if tracing:
                monitor_trace = tracing.trace_mape_k_cycle(
                    "monitor", {"cycle_id": cycle_id, "node_id": node_id, **metrics}
                )
            else:
                from contextlib import nullcontext

                monitor_trace = nullcontext()

            with monitor_trace:
                anomaly_detected = self.monitor.check(metrics)

            result = {
                "timestamp": datetime.now().isoformat(),
                "cycle_id": cycle_id,
                "anomaly_detected": anomaly_detected,
                "monitor_results": {},
                "analyzer_results": {},
                "planner_results": {},
                "executor_results": {},
                "explanations": {},
            }

            if not anomaly_detected:
                return result

            # 2. Analyze: Root cause analysis with tracing
            analyze_trace = None
            if tracing:
                analyze_trace = tracing.trace_mape_k_cycle(
                    "analyze",
                    {
                        "cycle_id": cycle_id,
                        "node_id": node_id,
                        "anomaly_detected": True,
                    },
                )
            else:
                from contextlib import nullcontext

                analyze_trace = nullcontext()

            with analyze_trace:

                analysis_issue = self.analyzer.analyze(
                    metrics,
                    node_id=metrics.get("node_id", "unknown"),
                    event_id=f"{metrics.get('node_id', 'unknown')}_{int(time.time() * 1000)}",
                )
                result["analyzer_results"] = {
                    "root_cause": analysis_issue,
                    "confidence": 1.0 if analysis_issue != "Healthy" else 0.0,
                    "affected_nodes": (
                        [metrics.get("node_id")] if analysis_issue != "Healthy" else []
                    ),
                }

                # 3. GraphSAGE Observe Mode: Дополнительная валидация
                if self.observe_detector:
                    graph_data = self._prepare_graph_data(metrics)
                    event = self.observe_detector.detect(
                        graph_data, metrics.get("node_id", "unknown")
                    )

                    if event:
                        result["observe_mode"] = {
                            "anomaly_score": event.anomaly_score,
                            "confidence": event.confidence,
                            "mode": event.mode.value,
                            "action_taken": event.action_taken,
                        }

                        # Добавить объяснение
                        result["explanations"]["observe_mode"] = (
                            f"GraphSAGE detected anomaly with {event.confidence:.1%} confidence. "
                            f"Mode: {event.mode.value} (no action taken in observe mode)"
                        )

            # 4. Plan: Recovery strategy with tracing
            plan_trace = None
            if tracing:
                plan_trace = tracing.trace_mape_k_cycle(
                    "plan",
                    {"cycle_id": cycle_id, "node_id": node_id, "issue": analysis_issue},
                )
            else:
                from contextlib import nullcontext

                plan_trace = nullcontext()

            with plan_trace:
                plan_start_time = time.time()
                strategy = self.planner.plan(analysis_issue)

        # Estimate recovery time based on strategy type and historical data
        estimated_recovery_time = self._estimate_recovery_time(strategy, analysis_issue)

        result["planner_results"] = {
            "strategy": strategy,
            "actions": [strategy],
            "estimated_recovery_time": estimated_recovery_time,
        }

        # 5. Execute: Recovery actions
        try:
            from src.monitoring.tracing import get_tracing_manager

            tracing = get_tracing_manager()
            if tracing:
                tracing.trace_mape_k_cycle("execute", {"strategy": strategy})
        except Exception:
            pass

        execution_start_time = time.time()
        # Pass context for better recovery actions
        execution_context = {
            "node_id": metrics.get("node_id", "unknown"),
            "service_name": metrics.get("service_name", "x0tta6bl4"),
            "issue": analysis_issue,
        }
        execution_success = self.executor.execute(strategy, context=execution_context)
        execution_duration = time.time() - execution_start_time

        result["executor_results"] = {
            "success": execution_success,
            "actions_executed": [strategy] if execution_success else [],
            "recovery_time": execution_duration,  # Real measured recovery time
        }

        # 6. eBPF Explainer: Объяснение network events
        if self.ebpf_explainer and "network_events" in metrics:
            ebpf_explanations = []
            for event_data in metrics.get("network_events", []):
                event = EBPFEvent(
                    event_type=EBPFEventType.PACKET_DROP,  # Пример
                    timestamp=datetime.now().timestamp(),
                    node_id=metrics.get("node_id", "unknown"),
                    program_id=event_data.get("program_id", "unknown"),
                    details=event_data,
                )
                explanation = self.ebpf_explainer.explain_event(event)
                ebpf_explanations.append(explanation)

            result["explanations"]["ebpf"] = ebpf_explanations

        # 7. Knowledge: Сохранение опыта
        self.knowledge.record(
            metrics=metrics,
            issue=analysis_issue,
            action=strategy,
            success=execution_success,
            mttr=execution_duration,
            node_id=metrics.get("node_id", "default"),
        )

        return result

    def _prepare_graph_data(self, metrics: Dict[str, Any]) -> Dict[str, Any]:
        """Подготовить graph data для GraphSAGE"""
        return {
            "nodes": [{"id": metrics.get("node_id", "unknown")}],
            "edges": [],
            "cpu_percent": metrics.get("cpu_percent", 0.0),
            "memory_percent": metrics.get("memory_percent", 0.0),
            "packet_loss": metrics.get("packet_loss_percent", 0.0),
            "latency_ms": metrics.get("latency_ms", 0.0),
        }

    async def run_chaos_experiment(
        self, experiment_type: str, duration: int = 10
    ) -> Dict[str, Any]:
        """
        Запустить chaos experiment для демонстрации resilience

        Returns:
            Результаты chaos experiment
        """
        if not self.chaos_controller:
            return {"error": "Chaos Controller not available"}

        from src.chaos.controller import ChaosExperiment, ExperimentType

        # Создать experiment
        exp_type = (
            ExperimentType[experiment_type.upper()]
            if hasattr(ExperimentType, experiment_type.upper())
            else ExperimentType.NODE_FAILURE
        )
        experiment = ChaosExperiment(
            experiment_type=exp_type, duration=duration, target_nodes=[], parameters={}
        )

        # Запустить
        metrics = await self.chaos_controller.run_experiment(experiment)

        return {
            "experiment_type": experiment_type,
            "mttr": metrics.mttr,
            "recovery_success": metrics.recovery_success,
            "path_availability": metrics.path_availability,
            "service_degradation": metrics.service_degradation,
        }

    def get_system_status(self) -> Dict[str, Any]:
        """Получить полный статус системы для demo"""
        status = {
            "mape_k_cycle": {"active": True, "last_cycle": None},
            "observe_mode": {
                "enabled": self.observe_detector is not None,
                "mode": (
                    self.observe_detector.mode.value if self.observe_detector else None
                ),
                "stats": (
                    self.observe_detector.get_stats() if self.observe_detector else None
                ),
            },
            "chaos_engineering": {
                "enabled": self.chaos_controller is not None,
                "stats": (
                    self.chaos_controller.get_recovery_stats()
                    if self.chaos_controller
                    else None
                ),
            },
            "ebpf_explainer": {"enabled": self.ebpf_explainer is not None},
        }

        return status

    def _estimate_recovery_time(self, strategy: str, issue: str) -> float:
        """
        Estimate recovery time based on strategy type and historical data.

        Args:
            strategy: Recovery strategy name
            issue: Issue type/root cause

        Returns:
            Estimated recovery time in seconds
        """
        # Base recovery times by strategy type (in seconds)
        base_times = {
            "Restart service": 5.0,
            "Switch route": 2.0,
            "Clear cache": 1.0,
            "Scale up": 10.0,
            "Scale down": 3.0,
            "Failover": 3.0,
            "Quarantine node": 1.0,
            "No action needed": 0.0,
        }

        # Get base time for strategy
        base_time = base_times.get(strategy, 5.0)  # Default 5 seconds

        # Adjust based on issue severity
        severity_multipliers = {
            "High CPU": 1.0,
            "High Memory": 1.2,
            "Network Loss": 0.8,
            "Node Down": 1.5,
            "Link Failure": 1.0,
            "Congestion": 0.9,
            "Byzantine Attack": 2.0,
            "Resource Exhaustion": 1.3,
        }

        multiplier = severity_multipliers.get(issue, 1.0)

        # Try to get historical MTTR from knowledge base
        if self.knowledge:
            try:
                # Get average MTTR for this issue type from knowledge
                historical_mttr = self.knowledge.get_average_mttr(issue)
                if historical_mttr and historical_mttr > 0:
                    # Use historical data if available (weighted average: 70% historical, 30% estimated)
                    estimated = (historical_mttr * 0.7) + (base_time * multiplier * 0.3)
                    return estimated
            except Exception:
                pass  # Fall back to base calculation

        # Return estimated time
        return base_time * multiplier
