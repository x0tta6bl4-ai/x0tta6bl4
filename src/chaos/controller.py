"""
Chaos Engineering Controller
Управляет chaos experiments и собирает метрики recovery
"""

import asyncio
import logging
import time
from typing import Dict, List, Any, Optional
from datetime import datetime
from dataclasses import dataclass, field
from enum import Enum

from src.monitoring.metrics import (
    record_self_healing_event,
    record_mttr,
    record_mape_k_cycle,
)

logger = logging.getLogger(__name__)


class ExperimentType(Enum):
    """Типы chaos experiments"""
    NODE_FAILURE = "node_failure"
    NETWORK_PARTITION = "network_partition"
    HIGH_LATENCY = "high_latency"
    PACKET_LOSS = "packet_loss"
    COMBINED = "combined"


@dataclass
class ChaosExperiment:
    """Chaos experiment конфигурация"""
    experiment_type: ExperimentType
    duration: int  # секунды
    target_nodes: List[str] = field(default_factory=list)
    parameters: Dict[str, Any] = field(default_factory=dict)
    start_time: Optional[datetime] = None
    end_time: Optional[datetime] = None
    status: str = "pending"  # pending, running, completed, failed


@dataclass
class RecoveryMetrics:
    """Метрики recovery после chaos"""
    experiment_type: ExperimentType
    mttr: float  # секунды
    recovery_success: bool
    path_availability: float  # процент доступных путей
    service_degradation: float  # процент деградации
    nodes_affected: int
    recovery_actions: List[str] = field(default_factory=list)


class ChaosController:
    """
    Управляет chaos experiments и собирает метрики
    
    Интегрируется с MAPE-K циклом для автоматического recovery
    """
    
    def __init__(self):
        self.experiments: List[ChaosExperiment] = []
        self.recovery_metrics: List[RecoveryMetrics] = []
        self.is_running = False
        
        logger.info("Chaos Controller initialized")
    
    async def run_experiment(self, experiment: ChaosExperiment) -> RecoveryMetrics:
        """
        Запустить chaos experiment
        
        Returns:
            RecoveryMetrics после завершения experiment
        """
        experiment.start_time = datetime.now()
        experiment.status = "running"
        self.experiments.append(experiment)
        
        logger.info(f"Starting chaos experiment: {experiment.experiment_type.value}")
        
        # Запустить experiment в зависимости от типа
        if experiment.experiment_type == ExperimentType.NODE_FAILURE:
            await self._run_node_failure(experiment)
        elif experiment.experiment_type == ExperimentType.NETWORK_PARTITION:
            await self._run_network_partition(experiment)
        elif experiment.experiment_type == ExperimentType.HIGH_LATENCY:
            await self._run_high_latency(experiment)
        elif experiment.experiment_type == ExperimentType.PACKET_LOSS:
            await self._run_packet_loss(experiment)
        elif experiment.experiment_type == ExperimentType.COMBINED:
            await self._run_combined(experiment)
        
        # Ждать завершения experiment
        await asyncio.sleep(experiment.duration)
        
        # Остановить experiment
        await self._stop_experiment(experiment)
        
        # Собрать метрики recovery
        metrics = await self._collect_recovery_metrics(experiment)
        
        experiment.end_time = datetime.now()
        experiment.status = "completed"
        
        # Обновить Prometheus metrics
        record_mttr(experiment.experiment_type.value, metrics.mttr)
        record_self_healing_event(
            experiment.experiment_type.value,
            f"chaos_{experiment.experiment_type.value}"
        )
        
        self.recovery_metrics.append(metrics)
        
        logger.info(
            f"Chaos experiment completed: {experiment.experiment_type.value}, "
            f"MTTR: {metrics.mttr:.2f}s, Success: {metrics.recovery_success}"
        )
        
        return metrics
    
    async def _run_node_failure(self, experiment: ChaosExperiment):
        """Симулировать отказ узла"""
        target_node = experiment.target_nodes[0] if experiment.target_nodes else None
        
        if target_node:
            logger.info(f"Simulating node failure: {target_node}")
            # TODO: Интеграция с mesh network для реального failure
            # mesh_network.simulate_node_failure(target_node)
        else:
            logger.warning("No target node specified for node failure experiment")
    
    async def _run_network_partition(self, experiment: ChaosExperiment):
        """Симулировать сетевой раздел"""
        logger.info("Simulating network partition")
        # TODO: Интеграция с mesh network для реального partition
        # mesh_network.simulate_partition(experiment.parameters)
    
    async def _run_high_latency(self, experiment: ChaosExperiment):
        """Симулировать высокую задержку"""
        latency_ms = experiment.parameters.get('latency_ms', 500)
        logger.info(f"Simulating high latency: {latency_ms}ms")
        # TODO: Интеграция с network для реального latency injection
    
    async def _run_packet_loss(self, experiment: ChaosExperiment):
        """Симулировать потерю пакетов"""
        loss_percent = experiment.parameters.get('loss_percent', 10)
        logger.info(f"Simulating packet loss: {loss_percent}%")
        # TODO: Интеграция с network для реального packet loss
    
    async def _run_combined(self, experiment: ChaosExperiment):
        """Симулировать комбинированный failure"""
        logger.info("Simulating combined failures")
        # TODO: Комбинация нескольких типов failures
    
    async def _stop_experiment(self, experiment: ChaosExperiment):
        """Остановить experiment"""
        logger.info(f"Stopping chaos experiment: {experiment.experiment_type.value}")
        # TODO: Восстановить нормальное состояние
    
    async def _collect_recovery_metrics(self, experiment: ChaosExperiment) -> RecoveryMetrics:
        """Собрать метрики recovery"""
        start_time = experiment.start_time
        end_time = datetime.now()
        
        # Вычислить MTTR
        recovery_time = (end_time - start_time).total_seconds()
        
        # TODO: Получить реальные метрики от mesh network
        # path_availability = mesh_network.get_path_availability()
        # service_degradation = mesh_network.get_service_degradation()
        
        # Временные значения для демо
        path_availability = 0.95  # 95% путей доступны
        service_degradation = 0.10  # 10% деградация
        recovery_success = recovery_time < 10.0  # Success если recovery < 10s
        
        metrics = RecoveryMetrics(
            experiment_type=experiment.experiment_type,
            mttr=recovery_time,
            recovery_success=recovery_success,
            path_availability=path_availability,
            service_degradation=service_degradation,
            nodes_affected=len(experiment.target_nodes),
            recovery_actions=["route_switch", "node_restart"]  # Пример
        )
        
        return metrics
    
    def get_experiment_history(self) -> List[Dict[str, Any]]:
        """Получить историю experiments"""
        return [
            {
                'type': exp.experiment_type.value,
                'status': exp.status,
                'start_time': exp.start_time.isoformat() if exp.start_time else None,
                'end_time': exp.end_time.isoformat() if exp.end_time else None,
                'duration': exp.duration,
            }
            for exp in self.experiments
        ]
    
    def get_recovery_stats(self) -> Dict[str, Any]:
        """Получить статистику recovery"""
        if not self.recovery_metrics:
            return {
                'total_experiments': 0,
                'success_rate': 0.0,
                'avg_mttr': 0.0,
            }
        
        successful = sum(1 for m in self.recovery_metrics if m.recovery_success)
        avg_mttr = sum(m.mttr for m in self.recovery_metrics) / len(self.recovery_metrics)
        
        return {
            'total_experiments': len(self.recovery_metrics),
            'success_rate': successful / len(self.recovery_metrics),
            'avg_mttr': avg_mttr,
            'min_mttr': min(m.mttr for m in self.recovery_metrics),
            'max_mttr': max(m.mttr for m in self.recovery_metrics),
        }
    
    def generate_report(self) -> str:
        """Сгенерировать отчет о chaos experiments"""
        stats = self.get_recovery_stats()
        
        report = f"""
Chaos Engineering Report
========================

Total Experiments: {stats['total_experiments']}
Success Rate: {stats['success_rate']:.2%}
Average MTTR: {stats['avg_mttr']:.2f}s
Min MTTR: {stats['min_mttr']:.2f}s
Max MTTR: {stats['max_mttr']:.2f}s

Recent Experiments:
"""
        for exp in self.experiments[-5:]:
            report += f"  - {exp.experiment_type.value}: {exp.status}\n"
        
        return report

