"""
API Endpoints for Swarm Orchestration
======================================
"""

import logging
from typing import Any, Dict, List, Optional
from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel

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

class TaskRequest(BaseModel):
    task_type: str
    payload: Dict[str, Any]
    priority: int = 1

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
        # We need an async wrapper to start the execution
        import asyncio
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
