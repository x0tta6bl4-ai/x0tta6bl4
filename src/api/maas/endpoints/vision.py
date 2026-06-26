"""
API Endpoints for Vision Coding Module
=======================================
"""
from __future__ import annotations

import logging
from typing import Any, Dict, List

from fastapi import APIRouter, File, HTTPException, Request, UploadFile
from pydantic import BaseModel

from src.api.cross_plane_claim_gate import readiness_cross_plane_claim_gate_metadata
from src.core.resilience.reliability_policy import mark_degraded_dependency

logger = logging.getLogger(__name__)

router = APIRouter( tags=["Vision Analytics"])

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


def _vision_component(name: str) -> Any:
    return globals().get(name)


def _vision_components_available() -> bool:
    return (
        VISION_AVAILABLE
        and _vision_component("_processor") is not None
        and _vision_component("_topology_analyzer") is not None
        and _vision_component("_correction_engine") is not None
    )


def _processor_surface_available() -> bool:
    processor = _vision_component("_processor")
    return all(
        callable(getattr(processor, attr, None))
        for attr in ("process_image", "extract_text")
    )


def _topology_surface_available() -> bool:
    analyzer = _vision_component("_topology_analyzer")
    return all(
        callable(getattr(analyzer, attr, None))
        for attr in ("analyze_bytes", "analyze", "clear_cache")
    )


def _correction_surface_available() -> bool:
    correction_engine = _vision_component("_correction_engine")
    return all(
        callable(getattr(correction_engine, attr, None))
        for attr in ("debug_bytes", "debug_visually")
    )


def _upload_surface_available() -> bool:
    return callable(File) and UploadFile is not None


def _vision_readiness_status() -> Dict[str, Any]:
    vision_components_ready = _vision_components_available()
    processor_surface_ready = _processor_surface_available()
    topology_surface_ready = _topology_surface_available()
    correction_surface_ready = _correction_surface_available()
    upload_surface_ready = _upload_surface_available()
    local_image_backend_ready = vision_components_ready

    checks = {
        "vision_components": vision_components_ready,
        "processor_surface": processor_surface_ready,
        "topology_surface": topology_surface_ready,
        "correction_surface": correction_surface_ready,
        "upload_surface": upload_surface_ready,
        "local_image_backend": local_image_backend_ready,
    }
    degraded_dependencies = [
        dependency for dependency, ready in checks.items() if not ready
    ]
    vision_runtime_ready = not degraded_dependencies

    return {
        "status": "ready" if vision_runtime_ready else "degraded",
        "route_registered": True,
        "registration_mode": "full_mode_only",
        "route_present_in_light_mode": False,
        "lifecycle_binding": "route_import_only",
        "startup_hook_completed": None,
        "vision_runtime_ready": vision_runtime_ready,
        "vision_components_ready": vision_components_ready,
        "processor_surface_ready": processor_surface_ready,
        "topology_surface_ready": topology_surface_ready,
        "correction_surface_ready": correction_surface_ready,
        "upload_surface_ready": upload_surface_ready,
        "local_image_backend_ready": local_image_backend_ready,
        "external_provider_required": bool(
            getattr(_vision_component("_processor"), "require_external_provider", False)
        ),
        "external_provider_configured": bool(
            getattr(_vision_component("_processor"), "api_key", None)
        ),
        "route_precedence": {
            "fixed_prefix": "/api/v1/vision",
            "legacy_maas_catch_all_shadowing": "not_applicable",
            "rate_limited_paths": [
                "/api/v1/vision/analyze/topology",
                "/api/v1/vision/debug",
            ],
        },
        "degraded_dependencies": degraded_dependencies,
        "backing_state": {
            "processor": type(_vision_component("_processor")).__name__
            if _vision_component("_processor") is not None
            else None,
            "topology_analyzer": type(_vision_component("_topology_analyzer")).__name__
            if _vision_component("_topology_analyzer") is not None
            else None,
            "correction_engine": type(_vision_component("_correction_engine")).__name__
            if _vision_component("_correction_engine") is not None
            else None,
        },
        "cross_plane_claim_gate": readiness_cross_plane_claim_gate_metadata(
            surface="vision_readiness"
        ),
        "claim_boundary": (
            "Readiness verifies the import-time vision component surfaces used by "
            "the upload routes. It does not process an image, prove OCR is installed, "
            "or prove an external vision provider is configured."
        ),
    }


@router.get("/readiness")
async def vision_readiness(request: Request):
    payload = _vision_readiness_status()
    for dependency in payload["degraded_dependencies"]:
        mark_degraded_dependency(request, dependency)
    return payload


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
        content = await file.read()
        # Pass bytes directly to the processor/analyzer
        result = await _topology_analyzer.analyze_bytes(content)
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
        content = await file.read()
        result = await _correction_engine.debug_bytes(content)
        return result
    except Exception as e:
        logger.error(f"Visual debugging failed: {e}")
        raise HTTPException(status_code=500, detail=str(e))

