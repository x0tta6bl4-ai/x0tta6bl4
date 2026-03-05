"""
Digital Twins для Chaos Testing
================================

Цифровые двойники mesh-сети для тестирования без воздействия на production.
Позволяет запускать chaos-тесты и проверять self-healing в безопасной среде.
"""

import asyncio
import logging
import random
from dataclasses import dataclass, field
from datetime import datetime
from enum import Enum
from typing import Dict, List

logger = logging.getLogger(__name__)


class ChaosScenario(Enum):
    """Типы chaos-сценариев"""

    NODE_DOWN = "node_down"
    LINK_FAILURE = "link_failure"
    DDOS = "ddos"
    BYZANTINE = "byzantine"
    RESOURCE_EXHAUSTION = "resource_exhaustion"
    NETWORK_PARTITION = "network_partition"


@dataclass
class DigitalTwinNode:
    """Цифровой двойник узла mesh-сети"""

    node_id: str
    cpu_usage: float
    memory_usage: float
    latency: float
    packet_loss: float
    neighbors: List[str] = field(default_factory=list)
    is_byzantine: bool = False
    is_down: bool = False
    failed_links: List[str] = field(default_factory=list)
    metrics_history: List[Dict] = field(default_factory=list)


@dataclass
class ChaosTestResult:
    """Результат chaos-теста"""

    scenario: ChaosScenario
    intensity: float
    initial_impact: Dict
    recovery_time: float
    success: bool
    timestamp: datetime
    affected_nodes: List[str]


class DigitalTwinsSimulator:
    """
    Симулятор цифровых двойников для chaos-тестирования.

    Создаёт виртуальную копию mesh-сети и позволяет запускать
    различные сценарии сбоев для проверки self-healing.
    """

    def __init__(self, node_count: int = 100):
        """
        Инициализация симулятора.

        Args:
            node_count: Количество узлов в симуляции
        """
        self.node_count = node_count
        self.nodes: Dict[str, DigitalTwinNode] = {}
        self.metrics_history: List[Dict] = []
        self.chaos_results: List[ChaosTestResult] = []

        self._create_twin_network(node_count)

        logger.info(f"Digital Twins Simulator initialized with {node_count} nodes")

    def _create_twin_network(self, node_count: int):
        """Создание сети цифровых двойников"""
        node_ids = [f"dt-node-{i:03d}" for i in range(node_count)]

        for i, node_id in enumerate(node_ids):
            # Создаём случайных соседей (2-5 соседей на узел)
            num_neighbors = random.randint(2, 5)
            potential_neighbors = [n for n in node_ids if n != node_id]
            neighbors = random.sample(
                potential_neighbors, min(num_neighbors, len(potential_neighbors))
            )

            self.nodes[node_id] = DigitalTwinNode(
                node_id=node_id,
                cpu_usage=random.uniform(10, 40),
                memory_usage=random.uniform(20, 60),
                latency=random.uniform(5, 50),
                packet_loss=random.uniform(0.1, 2.0),
                neighbors=neighbors,
                is_byzantine=random.random() < 0.05,  # 5% византийских узлов
            )

    async def run_chaos_test(
        self, scenario: ChaosScenario, intensity: float = 0.3, duration: float = 60.0
    ) -> ChaosTestResult:
        """
        Запуск chaos-теста.

        Args:
            scenario: Тип chaos-сценария
            intensity: Интенсивность (0.0 - 1.0)
            duration: Длительность теста в секундах

        Returns:
            Результат chaos-теста
        """
        logger.info(
            f"🚨 ЗАПУСК CHAOS-ТЕСТА: {scenario.value} с интенсивностью {intensity}"
        )

        # Сохраняем начальное состояние
        initial_state = self._collect_metrics()
        initial_impact = self._calculate_impact(initial_state)

        # Запускаем сценарий
        affected_nodes = await self._apply_chaos_scenario(scenario, intensity)

        # Ждём некоторое время для развития сбоя
        await asyncio.sleep(2.0)

        # Запускаем self-healing (симуляция)
        recovery_start = datetime.now()
        recovery_time = await self._simulate_self_healing(scenario, affected_nodes)
        recovery_end = datetime.now()

        actual_recovery_time = (recovery_end - recovery_start).total_seconds()

        # Собираем финальные метрики
        final_state = self._collect_metrics()
        final_impact = self._calculate_impact(final_state)

        # Определяем успех (MTTR < 3 секунд и восстановление > 90%)
        success = (
            actual_recovery_time < 3.0 and final_impact.get("network_health", 0) > 0.9
        )

        result = ChaosTestResult(
            scenario=scenario,
            intensity=intensity,
            initial_impact=initial_impact,
            recovery_time=actual_recovery_time,
            success=success,
            timestamp=datetime.now(),
            affected_nodes=affected_nodes,
        )

        self.chaos_results.append(result)

        logger.info(
            f"✅ Chaos test completed: recovery_time={actual_recovery_time:.2f}s, "
            f"success={success}"
        )

        return result

    async def _apply_chaos_scenario(
        self, scenario: ChaosScenario, intensity: float
    ) -> List[str]:
        """Применение chaos-сценария"""
        affected_nodes = []

        if scenario == ChaosScenario.NODE_DOWN:
            # Отключаем процент узлов
            num_nodes_to_down = int(self.node_count * intensity)
            nodes_to_down = random.sample(list(self.nodes.keys()), num_nodes_to_down)
            for node_id in nodes_to_down:
                self.nodes[node_id].is_down = True
                affected_nodes.append(node_id)

        elif scenario == ChaosScenario.LINK_FAILURE:
            # Ломаем процент связей
            total_links = sum(len(n.neighbors) for n in self.nodes.values()) // 2
            num_links_to_fail = int(total_links * intensity)

            for _ in range(num_links_to_fail):
                node_id = random.choice(list(self.nodes.keys()))
                if self.nodes[node_id].neighbors:
                    neighbor = random.choice(self.nodes[node_id].neighbors)
                    if neighbor not in self.nodes[node_id].failed_links:
                        self.nodes[node_id].failed_links.append(neighbor)
                        affected_nodes.append(node_id)

        elif scenario == ChaosScenario.DDOS:
            # Имитация DDoS: резкое увеличение нагрузки
            num_targets = int(self.node_count * intensity)
            targets = random.sample(list(self.nodes.keys()), num_targets)

            for node_id in targets:
                self.nodes[node_id].cpu_usage = min(
                    100.0, self.nodes[node_id].cpu_usage * 3
                )
                self.nodes[node_id].packet_loss = min(
                    50.0, self.nodes[node_id].packet_loss * 10
                )
                affected_nodes.append(node_id)

        elif scenario == ChaosScenario.BYZANTINE:
            # Включаем византийские узлы
            num_byzantine = int(self.node_count * intensity)
            byzantine_nodes = random.sample(list(self.nodes.keys()), num_byzantine)

            for node_id in byzantine_nodes:
                self.nodes[node_id].is_byzantine = True
                affected_nodes.append(node_id)

        elif scenario == ChaosScenario.RESOURCE_EXHAUSTION:
            # Исчерпание ресурсов
            num_nodes = int(self.node_count * intensity)
            exhausted_nodes = random.sample(list(self.nodes.keys()), num_nodes)

            for node_id in exhausted_nodes:
                self.nodes[node_id].cpu_usage = 95.0
                self.nodes[node_id].memory_usage = 95.0
                affected_nodes.append(node_id)

        return affected_nodes

    async def _simulate_self_healing(
        self, scenario: ChaosScenario, affected_nodes: List[str]
    ) -> float:
        """
        Симуляция самовосстановления.

        В реальности здесь будет интеграция с MAPE-K и GraphSAGE.
        Пока симулируем восстановление.
        """
        # Симуляция времени восстановления в зависимости от сценария
        base_recovery_times = {
            ChaosScenario.NODE_DOWN: 2.0,
            ChaosScenario.LINK_FAILURE: 1.5,
            ChaosScenario.DDOS: 2.5,
            ChaosScenario.BYZANTINE: 3.0,
            ChaosScenario.RESOURCE_EXHAUSTION: 2.0,
            ChaosScenario.NETWORK_PARTITION: 3.0,
        }

        base_time = base_recovery_times.get(scenario, 2.0)

        # Добавляем случайность
        recovery_time = base_time + random.uniform(-0.5, 0.5)
        recovery_time = max(0.5, recovery_time)  # Минимум 0.5 секунды

        # Симулируем процесс восстановления
        await asyncio.sleep(recovery_time)

        # Восстанавливаем узлы (в реальности это делает MAPE-K)
        if scenario == ChaosScenario.NODE_DOWN:
            for node_id in affected_nodes:
                if node_id in self.nodes:
                    self.nodes[node_id].is_down = False
        elif scenario == ChaosScenario.LINK_FAILURE:
            for node_id in affected_nodes:
                if node_id in self.nodes:
                    self.nodes[node_id].failed_links = []
        elif scenario == ChaosScenario.DDOS:
            for node_id in affected_nodes:
                if node_id in self.nodes:
                    self.nodes[node_id].cpu_usage = random.uniform(10, 40)
                    self.nodes[node_id].packet_loss = random.uniform(0.1, 2.0)

        return recovery_time

    def _collect_metrics(self) -> Dict:
        """Сбор метрик сети"""
        total_nodes = len(self.nodes)
        healthy_nodes = sum(1 for n in self.nodes.values() if not n.is_down)
        byzantine_nodes = sum(1 for n in self.nodes.values() if n.is_byzantine)

        avg_cpu = (
            sum(n.cpu_usage for n in self.nodes.values()) / total_nodes
            if total_nodes > 0
            else 0
        )
        avg_memory = (
            sum(n.memory_usage for n in self.nodes.values()) / total_nodes
            if total_nodes > 0
            else 0
        )
        avg_latency = (
            sum(n.latency for n in self.nodes.values()) / total_nodes
            if total_nodes > 0
            else 0
        )
        avg_loss = (
            sum(n.packet_loss for n in self.nodes.values()) / total_nodes
            if total_nodes > 0
            else 0
        )

        return {
            "total_nodes": total_nodes,
            "healthy_nodes": healthy_nodes,
            "byzantine_nodes": byzantine_nodes,
            "avg_cpu": avg_cpu,
            "avg_memory": avg_memory,
            "avg_latency": avg_latency,
            "avg_packet_loss": avg_loss,
            "network_health": healthy_nodes / total_nodes if total_nodes > 0 else 0,
        }

    def _calculate_impact(self, metrics: Dict) -> Dict:
        """Расчёт влияния сбоя"""
        return {
            "network_health": metrics.get("network_health", 0),
            "node_availability": metrics.get("healthy_nodes", 0)
            / metrics.get("total_nodes", 1),
            "performance_degradation": (
                metrics.get("avg_cpu", 0) / 100.0
                + metrics.get("avg_packet_loss", 0) / 100.0
            )
            / 2,
        }

    def get_chaos_statistics(self) -> Dict:
        """Получение статистики по chaos-тестам"""
        if not self.chaos_results:
            return {}

        total_tests = len(self.chaos_results)
        successful_tests = sum(1 for r in self.chaos_results if r.success)
        avg_recovery_time = (
            sum(r.recovery_time for r in self.chaos_results) / total_tests
        )

        return {
            "total_tests": total_tests,
            "successful_tests": successful_tests,
            "success_rate": successful_tests / total_tests if total_tests > 0 else 0,
            "avg_recovery_time": avg_recovery_time,
            "scenarios_tested": [r.scenario.value for r in self.chaos_results],
        }
