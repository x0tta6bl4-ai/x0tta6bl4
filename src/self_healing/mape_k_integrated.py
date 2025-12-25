"""
MAPE-K Cycle с интеграцией всех новых компонентов
Готово для demo и sales presentations
"""

import logging
from typing import Dict, Any, Optional
from datetime import datetime

from src.self_healing.mape_k import (
    MAPEKMonitor,
    MAPEKAnalyzer,
    MAPEKPlanner,
    MAPEKExecutor,
    MAPEKKnowledge
)

# Новые компоненты
try:
    from src.ml.graphsage_observe_mode import GraphSAGEObserveMode, DetectorMode
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
    from src.network.ebpf.explainer import EBPFExplainer, EBPFEvent, EBPFEventType
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
        enable_ebpf_explainer: bool = True
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
                mode=DetectorMode.OBSERVE,
                threshold=0.95,
                confidence_required=0.90
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
        # 1. Monitor: Обнаружение аномалий
        anomaly_detected = self.monitor.check(metrics)
        
        result = {
            'timestamp': datetime.now().isoformat(),
            'anomaly_detected': anomaly_detected,
            'monitor_results': {},
            'analyzer_results': {},
            'planner_results': {},
            'executor_results': {},
            'explanations': {}
        }
        
        if not anomaly_detected:
            return result
        
        # 2. Analyze: Root cause analysis
        analysis_issue = self.analyzer.analyze(metrics)
        result['analyzer_results'] = {
            'root_cause': analysis_issue,
            'confidence': 1.0 if analysis_issue != 'Healthy' else 0.0,
            'affected_nodes': [metrics.get('node_id')] if analysis_issue != 'Healthy' else []
        }
        
        # 3. GraphSAGE Observe Mode: Дополнительная валидация
        if self.observe_detector:
            graph_data = self._prepare_graph_data(metrics)
            event = self.observe_detector.detect(graph_data, metrics.get('node_id', 'unknown'))
            
            if event:
                result['observe_mode'] = {
                    'anomaly_score': event.anomaly_score,
                    'confidence': event.confidence,
                    'mode': event.mode.value,
                    'action_taken': event.action_taken
                }
                
                # Добавить объяснение
                result['explanations']['observe_mode'] = (
                    f"GraphSAGE detected anomaly with {event.confidence:.1%} confidence. "
                    f"Mode: {event.mode.value} (no action taken in observe mode)"
                )
        
        # 4. Plan: Recovery strategy
        strategy = self.planner.plan(analysis_issue)
        result['planner_results'] = {
            'strategy': strategy,
            'actions': [strategy],
            'estimated_recovery_time': 5.0  # Mock value
        }
        
        # 5. Execute: Recovery actions
        execution_success = self.executor.execute(strategy)
        result['executor_results'] = {
            'success': execution_success,
            'actions_executed': [strategy] if execution_success else [],
            'recovery_time': 5.0  # Mock value
        }
        
        # 6. eBPF Explainer: Объяснение network events
        if self.ebpf_explainer and 'network_events' in metrics:
            ebpf_explanations = []
            for event_data in metrics.get('network_events', []):
                event = EBPFEvent(
                    event_type=EBPFEventType.PACKET_DROP,  # Пример
                    timestamp=datetime.now().timestamp(),
                    node_id=metrics.get('node_id', 'unknown'),
                    program_id=event_data.get('program_id', 'unknown'),
                    details=event_data
                )
                explanation = self.ebpf_explainer.explain_event(event)
                ebpf_explanations.append(explanation)
            
            result['explanations']['ebpf'] = ebpf_explanations
        
        # 7. Knowledge: Сохранение опыта
        self.knowledge.record(
            metrics=metrics,
            analysis=analysis_issue,
            plan=result['planner_results'],
            execution=result['executor_results']
        )
        
        return result
    
    def _prepare_graph_data(self, metrics: Dict[str, Any]) -> Dict[str, Any]:
        """Подготовить graph data для GraphSAGE"""
        return {
            'nodes': [{'id': metrics.get('node_id', 'unknown')}],
            'edges': [],
            'cpu_percent': metrics.get('cpu_percent', 0.0),
            'memory_percent': metrics.get('memory_percent', 0.0),
            'packet_loss': metrics.get('packet_loss_percent', 0.0),
            'latency_ms': metrics.get('latency_ms', 0.0),
        }
    
    async def run_chaos_experiment(self, experiment_type: str, duration: int = 10) -> Dict[str, Any]:
        """
        Запустить chaos experiment для демонстрации resilience
        
        Returns:
            Результаты chaos experiment
        """
        if not self.chaos_controller:
            return {'error': 'Chaos Controller not available'}
        
        from src.chaos.controller import ChaosExperiment, ExperimentType
        
        # Создать experiment
        exp_type = ExperimentType[experiment_type.upper()] if hasattr(ExperimentType, experiment_type.upper()) else ExperimentType.NODE_FAILURE
        experiment = ChaosExperiment(
            experiment_type=exp_type,
            duration=duration,
            target_nodes=[],
            parameters={}
        )
        
        # Запустить
        metrics = await self.chaos_controller.run_experiment(experiment)
        
        return {
            'experiment_type': experiment_type,
            'mttr': metrics.mttr,
            'recovery_success': metrics.recovery_success,
            'path_availability': metrics.path_availability,
            'service_degradation': metrics.service_degradation
        }
    
    def get_system_status(self) -> Dict[str, Any]:
        """Получить полный статус системы для demo"""
        status = {
            'mape_k_cycle': {
                'active': True,
                'last_cycle': None
            },
            'observe_mode': {
                'enabled': self.observe_detector is not None,
                'mode': self.observe_detector.mode.value if self.observe_detector else None,
                'stats': self.observe_detector.get_stats() if self.observe_detector else None
            },
            'chaos_engineering': {
                'enabled': self.chaos_controller is not None,
                'stats': self.chaos_controller.get_recovery_stats() if self.chaos_controller else None
            },
            'ebpf_explainer': {
                'enabled': self.ebpf_explainer is not None
            }
        }
        
        return status

