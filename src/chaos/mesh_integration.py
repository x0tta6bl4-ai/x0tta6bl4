"""
Интеграция Chaos Controller с Mesh Network
"""

import logging
from typing import Any, Dict, List, Optional

from src.chaos.controller import (ChaosController, ChaosExperiment,
                                  ExperimentType)

logger = logging.getLogger(__name__)


class MeshChaosIntegration:
    """
    Интеграция Chaos Controller с Mesh Network

    Позволяет запускать chaos experiments на реальной mesh сети
    """

    def __init__(
        self, mesh_network=None, chaos_controller: Optional[ChaosController] = None
    ):
        self.mesh_network = mesh_network
        self.chaos_controller = chaos_controller or ChaosController()

        logger.info("Mesh Chaos Integration initialized")

    async def simulate_node_failure(self, node_id: str, duration: int = 10):
        """Симулировать отказ узла в mesh сети"""
        if not self.mesh_network:
            logger.warning("Mesh network not available, using simulation")
            return

        try:
            # Получить узел
            node = self.mesh_network.get_node(node_id)
            if not node:
                logger.error(f"Node {node_id} not found")
                return

            # Сохранить состояние
            original_state = node.state

            # Установить состояние OFFLINE
            node.state = "OFFLINE"
            logger.info(f"Node {node_id} set to OFFLINE for chaos experiment")

            # Ждать duration
            import asyncio

            await asyncio.sleep(duration)

            # Восстановить состояние
            node.state = original_state
            logger.info(f"Node {node_id} restored to {original_state}")

        except Exception as e:
            logger.error(f"Error simulating node failure: {e}")

    async def simulate_network_partition(
        self, partition_groups: List[List[str]], duration: int = 15
    ):
        """Симулировать сетевой раздел"""
        if not self.mesh_network:
            logger.warning("Mesh network not available, using simulation")
            return

        try:
            # Разделить сеть на группы
            for group in partition_groups:
                for node_id in group:
                    node = self.mesh_network.get_node(node_id)
                    if node:
                        # Пометить узлы как недоступные друг для друга
                        node.partition_id = f"partition_{partition_groups.index(group)}"
                        logger.info(
                            f"Node {node_id} assigned to partition {node.partition_id}"
                        )

            # Ждать duration
            import asyncio

            await asyncio.sleep(duration)

            # Восстановить connectivity
            for group in partition_groups:
                for node_id in group:
                    node = self.mesh_network.get_node(node_id)
                    if node:
                        node.partition_id = None
                        logger.info(f"Node {node_id} partition removed")

        except Exception as e:
            logger.error(f"Error simulating network partition: {e}")

    async def simulate_high_latency(
        self, target_nodes: List[str], latency_ms: int = 500, duration: int = 20
    ):
        """Симулировать высокую задержку"""
        if not self.mesh_network:
            logger.warning("Mesh network not available, using simulation")
            return

        try:
            # Установить задержку для узлов
            for node_id in target_nodes:
                node = self.mesh_network.get_node(node_id)
                if node:
                    original_latency = getattr(node, "base_latency_ms", 10)
                    node.latency_ms = latency_ms
                    logger.info(f"Node {node_id} latency set to {latency_ms}ms")

            # Ждать duration
            import asyncio

            await asyncio.sleep(duration)

            # Восстановить нормальную задержку
            for node_id in target_nodes:
                node = self.mesh_network.get_node(node_id)
                if node:
                    node.latency_ms = getattr(node, "base_latency_ms", 10)
                    logger.info(f"Node {node_id} latency restored")

        except Exception as e:
            logger.error(f"Error simulating high latency: {e}")

    async def run_chaos_experiment_with_mesh(self, experiment: ChaosExperiment):
        """Запустить chaos experiment с реальной mesh сетью"""
        if experiment.experiment_type == ExperimentType.NODE_FAILURE:
            target_node = (
                experiment.target_nodes[0] if experiment.target_nodes else None
            )
            if target_node:
                await self.simulate_node_failure(target_node, experiment.duration)

        elif experiment.experiment_type == ExperimentType.NETWORK_PARTITION:
            partition_groups = experiment.parameters.get("partition_groups", [])
            await self.simulate_network_partition(partition_groups, experiment.duration)

        elif experiment.experiment_type == ExperimentType.HIGH_LATENCY:
            latency_ms = experiment.parameters.get("latency_ms", 500)
            await self.simulate_high_latency(
                experiment.target_nodes, latency_ms, experiment.duration
            )

        # Запустить через chaos controller для метрик
        return await self.chaos_controller.run_experiment(experiment)
