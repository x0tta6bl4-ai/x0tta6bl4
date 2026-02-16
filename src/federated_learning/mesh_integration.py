"""
FL-Mesh Integration Module
==========================

Интегрирует FL Coordinator и FL Workers с mesh network.

Функции:
- Автоматическая регистрация mesh узлов в FL Coordinator
- Синхронизация heartbeat между mesh и FL
- Распределение глобальной модели через mesh
- Сбор метрик для обучения
"""

import asyncio
import logging
from dataclasses import dataclass
from typing import Any, Dict, List, Optional

from .coordinator import CoordinatorConfig, FederatedCoordinator
from .mesh_worker import FLMeshWorker

logger = logging.getLogger(__name__)


@dataclass
class MeshNodeInfo:
    """Information about a mesh node for FL integration."""

    node_id: str
    mesh_router: Any  # MeshRouter instance
    mesh_shield: Optional[Any] = None  # MeshShield instance
    fl_worker: Optional[FLMeshWorker] = None


class FLMeshIntegration:
    """
    Интеграция FL Coordinator с mesh network.

    Usage:
        integration = FLMeshIntegration(
            coordinator=fl_coordinator,
            mesh_nodes=mesh_nodes_dict
        )
        await integration.start()
        await integration.run_training_round()
    """

    def __init__(
        self,
        coordinator: FederatedCoordinator,
        mesh_nodes: Dict[str, MeshNodeInfo],
        auto_register: bool = True,
    ):
        self.coordinator = coordinator
        self.mesh_nodes: Dict[str, MeshNodeInfo] = mesh_nodes
        self.auto_register = auto_register

        self._running = False
        self._workers: Dict[str, FLMeshWorker] = {}

        logger.info(f"FLMeshIntegration initialized with {len(mesh_nodes)} mesh nodes")

    async def start(self):
        """Start FL-Mesh integration."""
        self._running = True

        # Create FL Workers for each mesh node
        for node_id, node_info in self.mesh_nodes.items():
            worker = FLMeshWorker(
                node_id=node_id,
                coordinator=self.coordinator,
                mesh_router=node_info.mesh_router,
                mesh_shield=node_info.mesh_shield,
            )

            await worker.start()
            self._workers[node_id] = worker
            node_info.fl_worker = worker

        logger.info(f"✅ FL-Mesh integration started: {len(self._workers)} workers")

    async def stop(self):
        """Stop FL-Mesh integration."""
        self._running = False

        # Stop all workers
        for worker in self._workers.values():
            await worker.stop()

        self._workers.clear()
        logger.info("FL-Mesh integration stopped")

    async def run_training_round(self) -> Optional[Dict[str, Any]]:
        """
        Run a complete training round across all mesh nodes.

        Returns:
            Dict with round results
        """
        # Start round in coordinator
        round_obj = self.coordinator.start_round()
        if not round_obj:
            logger.error("Failed to start training round")
            return None

        round_number = round_obj.round_number
        logger.info(f"🚀 Starting FL training round {round_number}")

        # Train on each worker
        updates = []
        for node_id, worker in self._workers.items():
            if node_id in round_obj.selected_nodes:
                logger.info(f"Training on {node_id}...")
                update = await worker.train_local_model(round_number)

                if update:
                    await worker.submit_update(update)
                    updates.append(update)
                    logger.info(f"✅ {node_id} submitted update")
                else:
                    logger.warning(f"⚠️ {node_id} failed to train")

        # Wait for aggregation (coordinator handles this)
        # In real implementation, this would be async
        await asyncio.sleep(1.0)

        # Get global model (if available)
        global_model = self.coordinator.get_global_model()
        if global_model:
            # Distribute to all workers
            for worker in self._workers.values():
                worker.receive_global_model(global_model)

        result = {
            "round_number": round_number,
            "participants": len(updates),
            "updates_received": len(updates),
            "global_model_available": global_model is not None,
        }

        logger.info(
            f"✅ Round {round_number} complete: "
            f"{len(updates)}/{len(round_obj.selected_nodes)} participants"
        )

        return result

    async def run_multiple_rounds(self, num_rounds: int = 5) -> List[Dict[str, Any]]:
        """Run multiple training rounds."""
        results = []

        for i in range(num_rounds):
            result = await self.run_training_round()
            if result:
                results.append(result)

            # Wait between rounds
            await asyncio.sleep(5.0)

        return results

    def get_worker_status(self) -> Dict[str, Any]:
        """Get status of all workers."""
        return {
            node_id: worker.get_status() for node_id, worker in self._workers.items()
        }

    def get_coordinator_stats(self) -> Dict[str, Any]:
        """Get coordinator statistics."""
        return {
            "total_nodes": len(self.coordinator.nodes),
            "eligible_nodes": len(self.coordinator.get_eligible_nodes()),
            "rounds_completed": self.coordinator._metrics["rounds_completed"],
            "total_updates": self.coordinator._metrics["total_updates_received"],
            "byzantine_detections": self.coordinator._metrics["byzantine_detections"],
        }


async def create_integration_from_mesh_nodes(
    coordinator: FederatedCoordinator,
    mesh_routers: Dict[str, Any],  # node_id -> MeshRouter
    mesh_shields: Optional[Dict[str, Any]] = None,  # node_id -> MeshShield
) -> FLMeshIntegration:
    """
    Create FL-Mesh integration from existing mesh routers.

    Args:
        coordinator: FL Coordinator instance
        mesh_routers: Dict of mesh routers by node_id
        mesh_shields: Optional dict of mesh shields by node_id

    Returns:
        FLMeshIntegration instance
    """
    mesh_nodes = {}

    for node_id, router in mesh_routers.items():
        shield = None
        if mesh_shields and node_id in mesh_shields:
            shield = mesh_shields[node_id]

        mesh_nodes[node_id] = MeshNodeInfo(
            node_id=node_id, mesh_router=router, mesh_shield=shield
        )

    integration = FLMeshIntegration(coordinator=coordinator, mesh_nodes=mesh_nodes)

    return integration
