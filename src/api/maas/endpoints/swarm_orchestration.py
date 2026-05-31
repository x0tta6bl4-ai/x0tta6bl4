"""
API Endpoints for Swarm Orchestration
======================================
"""

import asyncio
import logging
from typing import Any, Dict

from fastapi import APIRouter, HTTPException, Request
from pydantic import BaseModel

from src.api.cross_plane_claim_gate import readiness_cross_plane_claim_gate_metadata
from src.core.reliability_policy import mark_degraded_dependency

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/api/v1/swarm", tags=["Swarm Orchestration"])

try:
    from src.swarm.orchestrator import SwarmOrchestrator

    # We initialize a global orchestrator for the API
    _orchestrator = SwarmOrchestrator()
    SWARM_AVAILABLE = True
except ImportError:
    SWARM_AVAILABLE = False
    logger.warning("Swarm components not available")


def _get_orchestrator() -> Any:
    return globals().get("_orchestrator")


def _swarm_components_available() -> bool:
    return SWARM_AVAILABLE and _get_orchestrator() is not None


def _orchestrator_surface_available() -> bool:
    orchestrator = _get_orchestrator()
    if orchestrator is None:
        return False
    return all(
        callable(getattr(orchestrator, attr, None))
        for attr in ("get_status", "execute_task")
    )


def _orchestrator_runtime_state_available() -> bool:
    orchestrator = _get_orchestrator()
    if orchestrator is None:
        return False
    return all(
        hasattr(orchestrator, attr)
        for attr in ("status", "agents", "tasks", "metrics")
    )


def _task_scheduler_available() -> bool:
    return callable(asyncio.create_task)


def _orchestrator_agents_ready() -> bool:
    orchestrator = _get_orchestrator()
    agents = getattr(orchestrator, "agents", None)
    return isinstance(agents, dict) and bool(agents)


def _orchestrator_counts() -> Dict[str, Any]:
    orchestrator = _get_orchestrator()
    agents = getattr(orchestrator, "agents", None)
    tasks = getattr(orchestrator, "tasks", None)
    return {
        "active_agents": len(agents) if isinstance(agents, dict) else None,
        "tracked_tasks": len(tasks) if isinstance(tasks, dict) else None,
    }


def _swarm_orchestration_readiness_status() -> Dict[str, Any]:
    swarm_components_ready = _swarm_components_available()
    orchestrator_surface_ready = _orchestrator_surface_available()
    orchestrator_state_ready = _orchestrator_runtime_state_available()
    task_scheduler_ready = _task_scheduler_available()
    agents_ready = _orchestrator_agents_ready()
    swarm_orchestration_ready = (
        swarm_components_ready
        and orchestrator_surface_ready
        and orchestrator_state_ready
        and task_scheduler_ready
        and agents_ready
    )

    degraded_dependencies = []
    if not swarm_components_ready:
        degraded_dependencies.append("swarm_components")
    if not orchestrator_surface_ready:
        degraded_dependencies.append("orchestrator")
    if not orchestrator_state_ready:
        degraded_dependencies.append("orchestrator_runtime_state")
    if not task_scheduler_ready:
        degraded_dependencies.append("task_scheduler")
    if not agents_ready:
        degraded_dependencies.append("agents")

    return {
        "status": "ready" if not degraded_dependencies else "degraded",
        "route_registered": True,
        "registration_mode": "full_mode_only",
        "route_present_in_light_mode": False,
        "lifecycle_binding": "route_import_only",
        "startup_hook_completed": None,
        "swarm_orchestration_ready": swarm_orchestration_ready,
        "swarm_components_ready": swarm_components_ready,
        "orchestrator_surface_ready": orchestrator_surface_ready,
        "orchestrator_state_ready": orchestrator_state_ready,
        "task_scheduler_ready": task_scheduler_ready,
        "agents_ready": agents_ready,
        **_orchestrator_counts(),
        "route_precedence": {
            "shadowed_by_legacy": [],
            "fixed_prefix": "/api/v1/swarm",
            "boundary": (
                "Swarm orchestration routes use the fixed /api/v1/swarm prefix, "
                "so they are outside legacy MaaS catch-all matching. They are "
                "still full-mode-only because src.core.app only registers this "
                "router when light mode is disabled."
            ),
        },
        "degraded_dependencies": degraded_dependencies,
        "backing_state": {
            "swarm_components": (
                "The module imports SwarmOrchestrator and creates a global "
                "_orchestrator at import time."
            ),
            "orchestrator": (
                "Status and task routes require get_status and execute_task on "
                "the global orchestrator."
            ),
            "orchestrator_runtime_state": (
                "Operational state is held in orchestrator status, agents, tasks, "
                "and metrics attributes."
            ),
            "task_scheduler": (
                "Task submission schedules execute_task through asyncio.create_task "
                "inside the request loop."
            ),
            "agents": (
                "Accepted tasks still need at least one live agent; otherwise the "
                "background execute_task path can fail after the API has accepted "
                "the request."
            ),
        },
        "cross_plane_claim_gate": readiness_cross_plane_claim_gate_metadata(
            surface="swarm_orchestration_readiness"
        ),
        "claim_boundary": (
            "Swarm orchestration readiness proves that the legacy orchestrator "
            "surface and in-memory state are present. It does not start agents, "
            "run a task, or prove that a background task accepted by /task will "
            "finish successfully."
        ),
    }


class TaskRequest(BaseModel):
    task_type: str
    payload: Dict[str, Any]
    priority: int = 1


@router.get("/readiness")
async def swarm_orchestration_readiness(request: Request):
    payload = _swarm_orchestration_readiness_status()
    for dependency in payload["degraded_dependencies"]:
        mark_degraded_dependency(request, dependency)
    return payload


@router.get("/status")
async def get_swarm_status():
    """Get the current status of the agent swarm."""
    if not SWARM_AVAILABLE:
        raise HTTPException(status_code=503, detail="Swarm not available")

    return _orchestrator.get_status()

@router.post("/task")
async def submit_swarm_task(task: TaskRequest):
    """Submit a new task to the swarm."""
    if not SWARM_AVAILABLE:
        raise HTTPException(status_code=503, detail="Swarm not available")

    try:
        task_id = f"api_task_{task.task_type}"

        # Schedule it in background
        asyncio.create_task(_orchestrator.execute_task(
            task_id=task_id,
            agent_type="base", # Simplified
            payload=task.payload
        ))

        return {"status": "accepted", "task_id": task_id}
    except Exception as e:
        logger.error(f"Failed to submit task: {e}")
        raise HTTPException(status_code=500, detail=str(e))
