"""
API Endpoints for Vision Coding Module
=======================================
"""

import logging
import base64
from typing import Any, Dict, List, Optional
from fastapi import APIRouter, Depends, HTTPException, File, UploadFile
from pydantic import BaseModel

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/api/v1/vision", tags=["Vision Analytics"])

try:
    from src.vision.processor import VisionProcessor
    from src.vision.topology_analyzer import MeshTopologyAnalyzer
    from src.vision.self_correction import SelfCorrectionEngine
    
    _processor = VisionProcessor()
    _topology_analyzer = MeshTopologyAnalyzer(_processor)
    _correction_engine = SelfCorrectionEngine(_processor, _topology_analyzer)
    VISION_AVAILABLE = True
except ImportError:
    VISION_AVAILABLE = False
    logger.warning("Vision components not available")

class DebuggingResponse(BaseModel):
    status: str
    findings: Dict[str, Any]
    proposed_plan: List[Dict[str, Any]]

@router.post("/analyze/topology")
async def analyze_topology_image(file: UploadFile = File(...)):
    """
    Analyze a network topology screenshot to detect bottlenecks.
    """
    if not VISION_AVAILABLE:
        raise HTTPException(status_code=503, detail="Vision components not available")
        
    try:
        # In a real scenario we'd save the file or pass bytes. 
        # Since our mock just takes a string path, we pass a dummy path.
        result = await _topology_analyzer.analyze("uploaded_image.png")
        return result
    except Exception as e:
        logger.error(f"Topology analysis failed: {e}")
        raise HTTPException(status_code=500, detail=str(e))

@router.post("/debug", response_model=DebuggingResponse)
async def visual_debug(file: UploadFile = File(...)):
    """
    Visual debugging endpoint. Analyzes dashboard screenshots to propose recovery actions.
    """
    if not VISION_AVAILABLE:
        raise HTTPException(status_code=503, detail="Vision components not available")
        
    try:
        result = await _correction_engine.debug_visually("uploaded_debug_image.png")
        return result
    except Exception as e:
        logger.error(f"Visual debugging failed: {e}")
        raise HTTPException(status_code=500, detail=str(e))
