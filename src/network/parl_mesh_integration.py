"""
PARL Integration for Mesh Network

Provides parallelized route optimization and anomaly detection
using the PARL (Parallel Agent Reinforcement Learning) Engine.
"""

import asyncio
import logging
import time
from typing import Any, Dict, List, Optional

from src.swarm.parl.controller import PARLController, TaskContext
from src.network.routing.mesh_router import RouteEntry

logger = logging.getLogger(__name__)


class PARLMeshOptimizer:
    """
    Optimizes mesh network routes and detects anomalies using PARL Engine.
    """

    def __init__(self, parl_controller: Optional[PARLController] = None):
        self.parl_controller = parl_controller or PARLController()
        logger.info("✅ PARL Mesh Optimizer initialized")

    async def optimize_routes_parallel(
        self, current_routes: Dict[str, List[RouteEntry]]
    ) -> Dict[str, List[RouteEntry]]:
        """
        Parallelize route evaluation using PARL workers.
        """
        if not current_routes:
            return {}

        logger.info(f"🚀 Starting parallel route optimization for {len(current_routes)} destinations")
        start_time = asyncio.get_event_loop().time()

        tasks = []
        # Create a task for each destination's route list
        for dest, routes in current_routes.items():
            task_context = TaskContext(
                task_id=f"opt_route_{dest}_{int(time.time()*1000)}",
                task_type="route_optimization",
                payload={"destination": dest, "routes": [r.__dict__ for r in routes]},
                priority=1
            )
            tasks.append(task_context)

        # Execute parallel tasks
        results = await self.parl_controller.execute_parallel(tasks)

        # Process results
        optimized_routes: Dict[str, List[RouteEntry]] = {}
        for result in results:
            if result.success and result.result:
                dest = result.result.get("destination")
                best_route_dict = result.result.get("best_route")
                if dest and best_route_dict:
                    # In a real scenario, we'd reconstruct the RouteEntry perfectly
                    # For now, we return the original routes, but sorted optimally
                    # (assuming the PARL worker did the sorting/filtering)
                    optimized_routes[dest] = current_routes[dest] # Placeholder

        elapsed = asyncio.get_event_loop().time() - start_time
        logger.info(f"✨ Parallel route optimization completed in {elapsed:.3f}s")
        return optimized_routes

    async def detect_anomalies_parallel(self, node_metrics: Dict[str, Dict[str, Any]]) -> List[str]:
        """
        Parallelize anomaly detection across multiple nodes.
        """
        if not node_metrics:
            return []

        logger.info(f"🔍 Starting parallel anomaly detection for {len(node_metrics)} nodes")
        start_time = asyncio.get_event_loop().time()

        tasks = []
        for node_id, metrics in node_metrics.items():
            task_context = TaskContext(
                task_id=f"anomaly_{node_id}",
                task_type="anomaly_detection",
                payload={"node_id": node_id, "metrics": metrics},
                priority=2
            )
            tasks.append(task_context)

        results = await self.parl_controller.execute_parallel(tasks)

        anomalous_nodes = []
        for result in results:
            if result.success and result.result and result.result.get("is_anomaly"):
                anomalous_nodes.append(result.result.get("node_id"))

        elapsed = asyncio.get_event_loop().time() - start_time
        logger.info(f"✨ Parallel anomaly detection completed in {elapsed:.3f}s. Found {len(anomalous_nodes)} anomalies.")
        return anomalous_nodes
