"""
PARL Integration for Mesh Network

Provides parallelized route optimization and anomaly detection
using the PARL (Parallel Agent Reinforcement Learning) Engine.
"""

import asyncio
import logging
import time
from collections.abc import Mapping, Sequence
from dataclasses import asdict, fields, is_dataclass
from typing import Any

from src.network.routing.types import RouteEntry
from src.swarm.parl.controller import PARLController

logger = logging.getLogger(__name__)


class PARLMeshOptimizer:
    """
    Optimizes mesh network routes and detects anomalies using PARL Engine.
    """

    def __init__(self, parl_controller: PARLController | None = None):
        self.parl_controller = parl_controller or PARLController()
        logger.info("✅ PARL Mesh Optimizer initialized")

    async def optimize_routes_parallel(
        self, current_routes: dict[str, list[RouteEntry]]
    ) -> dict[str, list[RouteEntry]]:
        """
        Parallelize route evaluation using PARL workers.
        """
        if not current_routes:
            return {}

        logger.info(f"🚀 Starting parallel route optimization for {len(current_routes)} destinations")
        start_time = asyncio.get_event_loop().time()

        tasks: list[dict[str, Any]] = []
        task_destinations: dict[str, str] = {}
        # Create a task for each destination's route list
        for dest, routes in current_routes.items():
            task_id = f"opt_route_{dest}_{int(time.time()*1000)}"
            tasks.append({
                "task_id": task_id,
                "task_type": "route_optimization",
                "payload": {
                    "destination": dest,
                    "routes": [self._route_to_dict(route) for route in routes],
                },
                "priority": 1,
            })
            task_destinations[task_id] = dest

        # Execute parallel tasks
        results = await self.parl_controller.execute_parallel(tasks)

        # Process results
        optimized_routes: dict[str, list[RouteEntry]] = {}
        for result in results:
            if not self._get_value(result, "success", False):
                continue

            worker_result = self._get_value(result, "result")
            if not isinstance(worker_result, Mapping):
                continue

            task_id = self._get_value(result, "task_id")
            dest = worker_result.get("destination") or task_destinations.get(task_id)
            if not isinstance(dest, str) or dest not in current_routes:
                continue

            optimized = self._routes_from_worker_result(dest, worker_result, current_routes[dest])
            if optimized:
                optimized_routes[dest] = optimized

        for dest, routes in current_routes.items():
            optimized_routes.setdefault(dest, self._rank_routes(routes))

        elapsed = asyncio.get_event_loop().time() - start_time
        logger.info(f"✨ Parallel route optimization completed in {elapsed:.3f}s")
        return optimized_routes

    async def detect_anomalies_parallel(self, node_metrics: dict[str, dict[str, Any]]) -> list[str]:
        """
        Parallelize anomaly detection across multiple nodes.
        """
        if not node_metrics:
            return []

        logger.info(f"🔍 Starting parallel anomaly detection for {len(node_metrics)} nodes")
        start_time = asyncio.get_event_loop().time()

        tasks: list[dict[str, Any]] = []
        task_nodes: dict[str, str] = {}
        for node_id, metrics in node_metrics.items():
            task_id = f"anomaly_{node_id}"
            tasks.append({
                "task_id": task_id,
                "task_type": "anomaly_detection",
                "payload": {"node_id": node_id, "metrics": metrics},
                "priority": 2,
            })
            task_nodes[task_id] = node_id

        results = await self.parl_controller.execute_parallel(tasks)

        anomalous_nodes = []
        for result in results:
            worker_result = self._get_value(result, "result")
            if (
                self._get_value(result, "success", False)
                and isinstance(worker_result, Mapping)
                and worker_result.get("is_anomaly")
            ):
                task_id = self._get_value(result, "task_id")
                node_id = worker_result.get("node_id") or task_nodes.get(task_id)
                if node_id:
                    anomalous_nodes.append(node_id)

        elapsed = asyncio.get_event_loop().time() - start_time
        logger.info(f"✨ Parallel anomaly detection completed in {elapsed:.3f}s. Found {len(anomalous_nodes)} anomalies.")
        return anomalous_nodes

    @staticmethod
    def _get_value(container: Any, key: str, default: Any = None) -> Any:
        if isinstance(container, Mapping):
            return container.get(key, default)
        return getattr(container, key, default)

    @staticmethod
    def _route_to_dict(route: RouteEntry) -> dict[str, Any]:
        if is_dataclass(route):
            return asdict(route)
        return dict(getattr(route, "__dict__", {}))

    @staticmethod
    def _rank_routes(routes: Sequence[RouteEntry]) -> list[RouteEntry]:
        return sorted(
            routes,
            key=lambda route: (
                not route.valid,
                route.hop_count,
                -route.seq_num,
                -route.timestamp,
                route.next_hop,
            ),
        )

    def _routes_from_worker_result(
        self,
        destination: str,
        worker_result: Mapping[str, Any],
        current_routes: Sequence[RouteEntry],
    ) -> list[RouteEntry]:
        ranked_routes = self._rank_routes(current_routes)

        ordered_route_dicts = worker_result.get("routes") or worker_result.get("optimized_routes")
        if isinstance(ordered_route_dicts, list):
            return self._merge_worker_routes(destination, ordered_route_dicts, ranked_routes)

        best_route = worker_result.get("best_route")
        if isinstance(best_route, Mapping):
            return self._merge_worker_routes(destination, [best_route], ranked_routes)

        if isinstance(best_route, list):
            matching_route = self._match_path_route(destination, best_route, ranked_routes)
            if matching_route:
                return self._prepend_route(matching_route, ranked_routes)

        return ranked_routes

    def _merge_worker_routes(
        self,
        destination: str,
        worker_routes: Sequence[Any],
        ranked_routes: Sequence[RouteEntry],
    ) -> list[RouteEntry]:
        selected: list[RouteEntry] = []
        selected_keys: set[tuple[Any, ...]] = set()

        for raw_route in worker_routes:
            if not isinstance(raw_route, Mapping):
                continue
            route = self._match_route(destination, raw_route, ranked_routes)
            if route is None:
                route = self._route_from_dict(destination, raw_route)
            if route is None:
                continue

            route_key = self._route_identity(route)
            if route_key not in selected_keys:
                selected.append(route)
                selected_keys.add(route_key)

        for route in ranked_routes:
            route_key = self._route_identity(route)
            if route_key not in selected_keys:
                selected.append(route)
                selected_keys.add(route_key)

        return selected

    @staticmethod
    def _route_identity(route: RouteEntry) -> tuple[Any, ...]:
        return (route.destination, route.next_hop, route.hop_count, route.seq_num)

    def _match_route(
        self,
        destination: str,
        raw_route: Mapping[str, Any],
        ranked_routes: Sequence[RouteEntry],
    ) -> RouteEntry | None:
        candidates = [
            route
            for route in ranked_routes
            if route.destination == raw_route.get("destination", destination)
            and route.next_hop == raw_route.get("next_hop")
        ]
        if not candidates:
            return None

        for route in candidates:
            if (
                route.hop_count == raw_route.get("hop_count", route.hop_count)
                and route.seq_num == raw_route.get("seq_num", route.seq_num)
            ):
                return route

        return candidates[0]

    @staticmethod
    def _match_path_route(
        destination: str,
        path: Sequence[Any],
        ranked_routes: Sequence[RouteEntry],
    ) -> RouteEntry | None:
        route_path = [str(node) for node in path]
        for route in ranked_routes:
            if route.destination == destination and route.path == route_path:
                return route
        return None

    @staticmethod
    def _prepend_route(route: RouteEntry, ranked_routes: Sequence[RouteEntry]) -> list[RouteEntry]:
        route_key = PARLMeshOptimizer._route_identity(route)
        return [route] + [
            candidate
            for candidate in ranked_routes
            if PARLMeshOptimizer._route_identity(candidate) != route_key
        ]

    @staticmethod
    def _route_from_dict(destination: str, raw_route: Mapping[str, Any]) -> RouteEntry | None:
        try:
            field_names = {field.name for field in fields(RouteEntry)}
            route_data = {
                key: value
                for key, value in raw_route.items()
                if key in field_names
            }
            route_data.setdefault("destination", destination)
            return RouteEntry(**route_data)
        except (TypeError, ValueError):
            logger.warning("Ignoring invalid PARL route result for %s: %r", destination, raw_route)
            return None
