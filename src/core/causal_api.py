"""
Causal Analysis API Endpoint

FastAPI endpoint for serving causal analysis visualization data.
"""

import logging
from typing import Any, Dict, Optional

from fastapi import APIRouter, HTTPException

from src.ml.causal_analysis import CausalAnalysisEngine
from src.ml.causal_visualization import CausalAnalysisVisualizer

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/api/causal-analysis", tags=["causal-analysis"])

# Global instances (would be dependency injection in production)
_causal_engine: Optional[CausalAnalysisEngine] = None
_visualizer: Optional[CausalAnalysisVisualizer] = None


def init_causal_analysis():
    """Initialize causal analysis components."""
    global _causal_engine, _visualizer

    if _causal_engine is None:
        _causal_engine = CausalAnalysisEngine()
        _visualizer = CausalAnalysisVisualizer(_causal_engine)
        logger.info("Causal Analysis API initialized")


@router.get("/incidents/{incident_id}")
async def get_causal_analysis(incident_id: str) -> Dict[str, Any]:
    """
    Get causal analysis dashboard data for an incident.

    Returns:
        Dashboard data JSON
    """
    init_causal_analysis()

    if incident_id not in _causal_engine.incidents:
        raise HTTPException(status_code=404, detail=f"Incident {incident_id} not found")

    try:
        dashboard_data = _visualizer.generate_dashboard_data(incident_id)

        # Convert to dict (dataclass to dict)
        from dataclasses import asdict

        return asdict(dashboard_data)
    except Exception as e:
        logger.error(f"Error generating dashboard data: {e}", exc_info=True)
        raise HTTPException(status_code=500, detail="Internal server error")


@router.post("/demo")
async def create_demo_incident() -> Dict[str, Any]:
    """
    Create a demo incident for visualization.

    Returns:
        Incident ID and dashboard data
    """
    init_causal_analysis()

    try:
        incident_id = _visualizer.generate_demo_incident()
        dashboard_data = _visualizer.generate_dashboard_data(incident_id)

        from dataclasses import asdict

        return {"incident_id": incident_id, "dashboard_data": asdict(dashboard_data)}
    except Exception as e:
        logger.error(f"Error creating demo incident: {e}", exc_info=True)
        raise HTTPException(status_code=500, detail="Internal server error")


@router.get("/incidents")
async def list_incidents() -> Dict[str, Any]:
    """
    List all incidents available for analysis.

    Returns:
        List of incident IDs and metadata
    """
    init_causal_analysis()

    incidents = []
    for event_id, incident in _causal_engine.incidents.items():
        incidents.append(
            {
                "event_id": event_id,
                "timestamp": incident.timestamp.isoformat(),
                "node_id": incident.node_id,
                "service_id": incident.service_id,
                "anomaly_type": incident.anomaly_type,
                "severity": incident.severity.value,
            }
        )

    return {"incidents": incidents, "total": len(incidents)}
