"""
Swarm API Endpoints - Kimi K2.5 Integration
=============================================

REST API for managing agent swarms with PARL parallel execution.

Endpoints:
- POST /swarm/create - Create new swarm
- GET /swarm/{swarm_id}/status - Get swarm status
- POST /swarm/{swarm_id}/tasks - Submit task
- GET /swarm/{swarm_id}/tasks/{task_id} - Get task status
- GET /swarm/{swarm_id}/agents - List agents
- POST /swarm/{swarm_id}/scale - Scale swarm
- DELETE /swarm/{swarm_id} - Terminate swarm
- GET /swarm - List all swarms
- POST /swarm/{swarm_id}/vision/analyze - Visual analysis
"""

from fastapi import APIRouter, HTTPException, Depends, Request, Header, status, UploadFile, File
from pydantic import BaseModel, Field
from typing import Dict, Any, Optional, List
import logging
import os
import hmac
import asyncio
from datetime import datetime

from slowapi import Limiter
from slowapi.util import get_remote_address

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/api/v3/swarm", tags=["swarm"])
limiter = Limiter(key_func=get_remote_address)

# Global swarm registry
_swarms: Dict[str, Any] = {}
_swarm_lock = asyncio.Lock()


async def verify_admin_token(x_admin_token: Optional[str] = Header(None)):
    """Verify admin token for protected endpoints."""
    admin_token = os.getenv("ADMIN_TOKEN")
    if not admin_token:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Admin token not configured"
        )
    if not x_admin_token or not hmac.compare_digest(x_admin_token, admin_token):
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Admin access required"
        )


# Request/Response Models

class SwarmConstraints(BaseModel):
    max_parallel_steps: int = Field(default=1500, ge=1, le=1500)
    target_latency_ms: float = Field(default=100.0, ge=1)
    resource_limits: Optional[Dict[str, Any]] = None


class SwarmCreateRequest(BaseModel):
    name: str = Field(..., min_length=1, max_length=100)
    task_type: Optional[str] = None
    num_agents: int = Field(default=10, ge=1, le=100)
    capabilities: List[str] = Field(default_factory=lambda: ["task_execution"])
    constraints: Optional[SwarmConstraints] = None
    integration_targets: List[str] = Field(default_factory=list)
    auto_terminate: bool = True
    ttl_seconds: Optional[int] = Field(default=3600, ge=60, le=86400)


class SwarmResponse(BaseModel):
    swarm_id: str
    name: str
    status: str
    created_at: str
    num_agents: int
    endpoints: Dict[str, str]


class TaskSubmitRequest(BaseModel):
    task_type: str
    priority: int = Field(default=5, ge=1, le=10)
    payload: Dict[str, Any] = Field(default_factory=dict)
    parallelization: Optional[Dict[str, Any]] = None
    timeout_seconds: float = Field(default=30.0, ge=1, le=300)
    callback_url: Optional[str] = None


class TaskResponse(BaseModel):
    task_id: str
    swarm_id: str
    status: str
    created_at: str
    progress: Dict[str, Any]


class ScaleRequest(BaseModel):
    action: str = Field(..., pattern="^(scale_up|scale_down)$")
    num_agents: int = Field(..., ge=1, le=100)
    capabilities: List[str] = Field(default_factory=list)
    reason: Optional[str] = None


class TerminateRequest(BaseModel):
    graceful: bool = True
    timeout_seconds: int = Field(default=60, ge=1, le=300)
    force: bool = False


# Endpoints

@router.post("/create", response_model=SwarmResponse)
@limiter.limit("10/minute")
async def create_swarm(
    request: Request,
    body: SwarmCreateRequest,
    _: None = Depends(verify_admin_token)
):
    """
    Create a new agent swarm.

    Creates a swarm with specified number of agents and capabilities.
    Uses PARL for parallel task execution with up to 4.5x speedup.
    """
    try:
        from src.swarm import SwarmOrchestrator, SwarmConfig

        config = SwarmConfig(
            name=body.name,
            max_agents=body.num_agents,
            min_agents=min(body.num_agents, 3),
            max_parallel_steps=body.constraints.max_parallel_steps if body.constraints else 1500,
            target_latency_ms=body.constraints.target_latency_ms if body.constraints else 100.0,
            enable_parl=True,
            enable_vision=True,
            ttl_seconds=body.ttl_seconds
        )

        swarm = SwarmOrchestrator(config)
        await swarm.initialize()

        async with _swarm_lock:
            _swarms[swarm.swarm_id] = swarm

        logger.info(f"Swarm created: {swarm.swarm_id} with {len(swarm.agents)} agents")

        return SwarmResponse(
            swarm_id=swarm.swarm_id,
            name=body.name,
            status=swarm.status.value,
            created_at=datetime.fromtimestamp(swarm.created_at).isoformat(),
            num_agents=len(swarm.agents),
            endpoints={
                "status": f"/api/v3/swarm/{swarm.swarm_id}/status",
                "tasks": f"/api/v3/swarm/{swarm.swarm_id}/tasks",
                "agents": f"/api/v3/swarm/{swarm.swarm_id}/agents"
            }
        )

    except Exception as e:
        logger.error(f"Failed to create swarm: {e}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Failed to create swarm: {str(e)}"
        )


@router.get("/{swarm_id}/status")
@limiter.limit("100/minute")
async def get_swarm_status(request: Request, swarm_id: str):
    """Get current status of a swarm."""
    swarm = _swarms.get(swarm_id)
    if not swarm:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Swarm not found: {swarm_id}"
        )

    return swarm.get_status()


@router.post("/{swarm_id}/tasks", response_model=TaskResponse)
@limiter.limit("1000/minute")
async def submit_task(
    request: Request,
    swarm_id: str,
    body: TaskSubmitRequest,
    _: None = Depends(verify_admin_token)
):
    """Submit a task for execution by the swarm."""
    swarm = _swarms.get(swarm_id)
    if not swarm:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Swarm not found: {swarm_id}"
        )

    try:
        from src.swarm import Task

        task = Task(
            task_type=body.task_type,
            payload=body.payload,
            priority=body.priority,
            timeout_seconds=body.timeout_seconds
        )

        task_id = await swarm.submit_task(task)

        return TaskResponse(
            task_id=task_id,
            swarm_id=swarm_id,
            status="queued",
            created_at=datetime.fromtimestamp(task.created_at).isoformat(),
            progress={
                "total": 1,
                "completed": 0,
                "failed": 0,
                "percent": 0
            }
        )

    except Exception as e:
        logger.error(f"Failed to submit task: {e}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Failed to submit task: {str(e)}"
        )


@router.post("/{swarm_id}/tasks/batch")
@limiter.limit("100/minute")
async def submit_tasks_batch(
    request: Request,
    swarm_id: str,
    tasks: List[TaskSubmitRequest],
    _: None = Depends(verify_admin_token)
):
    """Submit multiple tasks for parallel execution."""
    swarm = _swarms.get(swarm_id)
    if not swarm:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Swarm not found: {swarm_id}"
        )

    try:
        from src.swarm import Task

        task_objects = [
            Task(
                task_type=t.task_type,
                payload=t.payload,
                priority=t.priority,
                timeout_seconds=t.timeout_seconds
            )
            for t in tasks
        ]

        task_ids = await swarm.submit_tasks_batch(task_objects)

        return {
            "swarm_id": swarm_id,
            "tasks_submitted": len(task_ids),
            "task_ids": task_ids,
            "status": "queued"
        }

    except Exception as e:
        logger.error(f"Failed to submit batch tasks: {e}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Failed to submit batch tasks: {str(e)}"
        )


@router.get("/{swarm_id}/tasks/{task_id}")
@limiter.limit("100/minute")
async def get_task_status(request: Request, swarm_id: str, task_id: str):
    """Get status of a specific task."""
    swarm = _swarms.get(swarm_id)
    if not swarm:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Swarm not found: {swarm_id}"
        )

    task_status = await swarm.get_task_status(task_id)
    if not task_status:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Task not found: {task_id}"
        )

    return task_status


@router.get("/{swarm_id}/agents")
@limiter.limit("100/minute")
async def list_agents(
    request: Request,
    swarm_id: str,
    status_filter: Optional[str] = None,
    limit: int = 100,
    offset: int = 0
):
    """List all agents in a swarm."""
    swarm = _swarms.get(swarm_id)
    if not swarm:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Swarm not found: {swarm_id}"
        )

    agents = []
    for agent_id, agent in swarm.agents.items():
        agent_status = agent.get_status()
        if status_filter and agent_status["state"] != status_filter:
            continue
        agents.append(agent_status)

    # Apply pagination
    total = len(agents)
    agents = agents[offset:offset + limit]

    return {
        "swarm_id": swarm_id,
        "total_agents": total,
        "returned": len(agents),
        "agents": agents
    }


@router.get("/{swarm_id}/agents/{agent_id}")
@limiter.limit("100/minute")
async def get_agent_status(request: Request, swarm_id: str, agent_id: str):
    """Get detailed status of a specific agent."""
    swarm = _swarms.get(swarm_id)
    if not swarm:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Swarm not found: {swarm_id}"
        )

    agent = swarm.agents.get(agent_id)
    if not agent:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Agent not found: {agent_id}"
        )

    return agent.get_status()


@router.post("/{swarm_id}/agents/{agent_id}/control")
@limiter.limit("50/minute")
async def control_agent(
    request: Request,
    swarm_id: str,
    agent_id: str,
    action: str,
    _: None = Depends(verify_admin_token)
):
    """Control agent state (pause, resume, restart, terminate)."""
    swarm = _swarms.get(swarm_id)
    if not swarm:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Swarm not found: {swarm_id}"
        )

    agent = swarm.agents.get(agent_id)
    if not agent:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Agent not found: {agent_id}"
        )

    if action == "pause":
        await agent.pause()
    elif action == "resume":
        await agent.resume()
    elif action == "terminate":
        await agent.terminate()
        del swarm.agents[agent_id]
    else:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=f"Invalid action: {action}"
        )

    return {
        "agent_id": agent_id,
        "action": action,
        "status": agent.state.value if action != "terminate" else "terminated"
    }


@router.post("/{swarm_id}/scale")
@limiter.limit("5/minute")
async def scale_swarm(
    request: Request,
    swarm_id: str,
    body: ScaleRequest,
    _: None = Depends(verify_admin_token)
):
    """Scale the swarm up or down."""
    swarm = _swarms.get(swarm_id)
    if not swarm:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Swarm not found: {swarm_id}"
        )

    previous_count = len(swarm.agents)

    if body.action == "scale_up":
        target = previous_count + body.num_agents
    else:
        target = max(1, previous_count - body.num_agents)

    await swarm.scale(target)

    return {
        "swarm_id": swarm_id,
        "action": body.action,
        "previous_count": previous_count,
        "new_count": len(swarm.agents),
        "scaling_status": "completed"
    }


@router.get("/{swarm_id}/metrics")
@limiter.limit("100/minute")
async def get_swarm_metrics(request: Request, swarm_id: str):
    """Get detailed performance metrics for a swarm."""
    swarm = _swarms.get(swarm_id)
    if not swarm:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Swarm not found: {swarm_id}"
        )

    metrics = await swarm.get_metrics()

    # Add PARL metrics if available
    if swarm.parl_controller:
        parl_metrics = swarm.parl_controller.get_metrics()
        metrics["parl"] = parl_metrics

    return {
        "swarm_id": swarm_id,
        "metrics": metrics
    }


@router.delete("/{swarm_id}")
@limiter.limit("10/minute")
async def terminate_swarm(
    request: Request,
    swarm_id: str,
    body: Optional[TerminateRequest] = None,
    _: None = Depends(verify_admin_token)
):
    """Terminate a swarm and release resources."""
    swarm = _swarms.get(swarm_id)
    if not swarm:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Swarm not found: {swarm_id}"
        )

    graceful = body.graceful if body else True

    await swarm.terminate(graceful=graceful)

    async with _swarm_lock:
        del _swarms[swarm_id]

    logger.info(f"Swarm terminated: {swarm_id}")

    return {
        "swarm_id": swarm_id,
        "status": "terminated",
        "graceful": graceful
    }


@router.get("")
@limiter.limit("100/minute")
async def list_swarms(
    request: Request,
    status_filter: Optional[str] = None,
    limit: int = 100,
    offset: int = 0
):
    """List all active swarms."""
    swarms_list = []

    for swarm_id, swarm in _swarms.items():
        swarm_status = swarm.get_status()
        if status_filter and swarm_status["status"] != status_filter:
            continue
        swarms_list.append({
            "swarm_id": swarm_id,
            "name": swarm.config.name,
            "status": swarm_status["status"],
            "num_agents": len(swarm.agents),
            "created_at": datetime.fromtimestamp(swarm.created_at).isoformat()
        })

    total = len(swarms_list)
    swarms_list = swarms_list[offset:offset + limit]

    return {
        "total": total,
        "swarms": swarms_list
    }


@router.post("/{swarm_id}/vision/analyze")
@limiter.limit("50/minute")
async def analyze_visual(
    request: Request,
    swarm_id: str,
    analysis_type: str = "mesh_topology",
    image: UploadFile = File(...),
    _: None = Depends(verify_admin_token)
):
    """
    Analyze an image using the swarm's vision module.

    Supports:
    - mesh_topology: Analyze mesh network topology
    - routing_visualization: Analyze route visualizations
    - anomaly_detection: Detect visual anomalies
    """
    swarm = _swarms.get(swarm_id)
    if not swarm:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Swarm not found: {swarm_id}"
        )

    if not swarm.config.enable_vision:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Vision module not enabled for this swarm"
        )

    try:
        # Read image content
        image_content = await image.read()

        # Import vision engine
        from src.swarm.vision_coding import get_vision_engine

        engine = get_vision_engine()

        # Perform analysis based on type
        if analysis_type == "mesh_topology":
            results = await engine.analyze_mesh_topology(image_content)
        elif analysis_type == "anomaly_detection":
            results = await engine.detect_anomalies(image_content)
        elif analysis_type == "routing_visualization":
            # For routing, we need start/end positions - use defaults or from context
            results = await engine.analyze_maze(
                image_content,
                start_pos=(0, 0),
                end_pos=(100, 100)
            )
        else:
            # Default to mesh topology analysis
            results = await engine.analyze_mesh_topology(image_content)

        return {
            "analysis_id": f"analysis_{swarm_id[:8]}",
            "swarm_id": swarm_id,
            "status": "completed",
            "analysis_type": analysis_type,
            "image_size": len(image_content),
            "results": results
        }

    except Exception as e:
        logger.error(f"Vision analysis failed: {e}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Vision analysis failed: {str(e)}"
        )


# Health check for swarm subsystem
@router.get("/health")
async def swarm_health():
    """Health check for swarm subsystem."""
    return {
        "status": "healthy",
        "active_swarms": len(_swarms),
        "total_agents": sum(len(s.agents) for s in _swarms.values())
    }
