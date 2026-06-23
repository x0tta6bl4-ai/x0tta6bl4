"""
Mesh healing logic for MeshNetworkManager.
Handles aggressive healing, preemptive checks, and MTTR tracking.
"""

import asyncio
import logging
import os
import time
from datetime import datetime
from typing import Any, Callable, Dict, List, Optional

from src.coordination.events import EventBus, EventType
from src.mesh.node_verifier import NodeVerificationResult, NodeVerifier, VerificationMode
from src.services.service_event_identity import service_event_identity

logger = logging.getLogger(__name__)

_SERVICE_AGENT = "mesh-healer"
_POST_HEAL_PROBE_ENV_VAR = "X0TTA6BL4_MESH_HEAL_POST_ACTION_PROBE"
_POST_HEAL_PROBE_TARGET_ENV_VAR = "X0TTA6BL4_MESH_HEAL_POST_ACTION_PROBE_TARGET"


class NodeVerificationError(Exception):
    """Raised when node verification fails critically."""
    pass


def _sha256_text(text: str) -> str:
    import hashlib
    return hashlib.sha256(text.encode()).hexdigest()[:16]


class MeshHealer:
    """Handles mesh healing operations and MTTR tracking."""

    def __init__(
        self,
        node_id: str,
        verifier: NodeVerifier,
        enable_database_node_healing: bool = True,
        event_bus: Optional[EventBus] = None,
        event_project_root: str = ".",
        enable_post_heal_dataplane_probe: Optional[bool] = None,
    ):
        self.node_id = node_id
        self.verifier = verifier
        self.enable_database_node_healing = enable_database_node_healing
        self.event_bus = event_bus
        self.event_project_root = event_project_root
        self._healing_log: List[Dict[str, Any]] = []
        self._post_heal_probe_enabled_flag = enable_post_heal_dataplane_probe

    def _post_heal_probe_enabled(self) -> bool:
        if self._post_heal_probe_enabled_flag is None:
            return os.environ.get(_POST_HEAL_PROBE_ENV_VAR, "").lower() in ("1", "true", "yes")
        return bool(self._post_heal_probe_enabled_flag)

    async def trigger_aggressive_healing(
        self,
        auto_restore_nodes: bool = False,
        node_recovery_callback: Optional[Callable[[str], bool]] = None,
        verification_mode: VerificationMode = VerificationMode.FULL,
        require_verification: bool = True,
        post_action_dataplane_probe_target: Optional[str] = None,
    ) -> int:
        """
        Force route rediscovery and optionally restore offline nodes in DB.

        Returns:
            Number of components healed (routes + nodes).
        """
        healed = 0
        start_time = time.time()
        started = time.monotonic()
        error_types: List[str] = []
        verification_results: List[NodeVerificationResult] = []

        router = self._get_router()
        if router is not None:
            try:
                active_routes = router.get_routes()
                for dest in list(active_routes.keys()):
                    routes = active_routes[dest]
                    stale = [r for r in routes if r.age > router.ROUTE_TIMEOUT * 0.8]
                    for route in stale:
                        try:
                            await router._discover_route(dest)
                            healed += 1
                        except Exception:
                            error_types.append("RouteDiscoveryFailure")
            except Exception as e:
                error_types.append(type(e).__name__)
                logger.error(f"Aggressive routing healing failed: {e}")

        if self.enable_database_node_healing:
            try:
                from src.database import SessionLocal, MeshNode
                with SessionLocal() as db:
                    offline_nodes = db.query(MeshNode).filter(MeshNode.status == "offline").all()
                    if offline_nodes and auto_restore_nodes:
                        for node in offline_nodes:
                            try:
                                is_recovered = False
                                if node_recovery_callback is not None:
                                    is_recovered = await node_recovery_callback(node.id)
                                else:
                                    result = await self.verifier.verify_node_state(
                                        target_node_id=node.id,
                                        mode=verification_mode,
                                    )
                                    verification_results.append(result)
                                    is_recovered = result.verified

                                if is_recovered:
                                    node.status = "healthy"
                                    node.last_seen = datetime.utcnow()
                                    healed += 1
                                elif not require_verification:
                                    node.status = "healthy"
                                    node.last_seen = datetime.utcnow()
                                    healed += 1
                            except Exception as e:
                                error_types.append(type(e).__name__)
                                logger.warning(f"Node {node.id} recovery failed: {e}")
                        db.commit()
            except Exception as e:
                error_types.append(type(e).__name__)
                logger.error(f"Database node healing failed: {e}")

        elapsed = (time.time() - start_time) / 60.0
        self._healing_log.append({
            "timestamp": datetime.utcnow().isoformat(),
            "healed": healed,
            "duration_minutes": elapsed,
            "verification_mode": verification_mode.value,
        })

        return healed

    async def trigger_preemptive_checks(self):
        """Proactively check route freshness for all known destinations."""
        started = time.monotonic()
        route_count = 0
        discovery_attempts = 0
        discovery_successes = 0
        discovery_failures = 0

        router = self._get_router()
        if router is None:
            return

        try:
            active_routes = router.get_routes()
            route_count = len(active_routes)
            for dest in list(active_routes.keys()):
                routes = active_routes[dest]
                if routes and routes[0].age > router.ROUTE_TIMEOUT * 0.5:
                    discovery_attempts += 1
                    try:
                        await router._discover_route(dest)
                        discovery_successes += 1
                    except Exception:
                        discovery_failures += 1
        except Exception as e:
            logger.debug(f"Preemptive check error: {e}")

    def _compute_mttr(self) -> float:
        """Compute mean time to repair from healing log (minutes)."""
        if not self._healing_log:
            return 0.0
        recent = self._healing_log[-10:]
        durations = [entry["duration_minutes"] for entry in recent if entry["healed"] > 0]
        if not durations:
            return 0.0
        return sum(durations) / len(durations)

    def _get_router(self):
        """Lazy-init MeshRouter."""
        try:
            from src.network.routing.mesh_router import MeshRouter
            return MeshRouter(self.node_id)
        except Exception as e:
            logger.warning(f"MeshRouter unavailable: {e}")
            return None
