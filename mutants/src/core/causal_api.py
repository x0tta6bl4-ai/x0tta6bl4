"""
Causal Analysis API Endpoint

FastAPI endpoint for serving causal analysis visualization data.
"""

from fastapi import APIRouter, HTTPException
from typing import Dict, Any, Optional
import logging

from src.ml.causal_analysis import CausalAnalysisEngine
from src.ml.causal_visualization import CausalAnalysisVisualizer

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/api/causal-analysis", tags=["causal-analysis"])

# Global instances (would be dependency injection in production)
_causal_engine: Optional[CausalAnalysisEngine] = None
_visualizer: Optional[CausalAnalysisVisualizer] = None
from inspect import signature as _mutmut_signature
from typing import Annotated
from typing import Callable
from typing import ClassVar


MutantDict = Annotated[dict[str, Callable], "Mutant"]


def _mutmut_trampoline(orig, mutants, call_args, call_kwargs, self_arg = None):
    """Forward call to original or mutated function, depending on the environment"""
    import os
    mutant_under_test = os.environ['MUTANT_UNDER_TEST']
    if mutant_under_test == 'fail':
        from mutmut.__main__ import MutmutProgrammaticFailException
        raise MutmutProgrammaticFailException('Failed programmatically')      
    elif mutant_under_test == 'stats':
        from mutmut.__main__ import record_trampoline_hit
        record_trampoline_hit(orig.__module__ + '.' + orig.__name__)
        result = orig(*call_args, **call_kwargs)
        return result
    prefix = orig.__module__ + '.' + orig.__name__ + '__mutmut_'
    if not mutant_under_test.startswith(prefix):
        result = orig(*call_args, **call_kwargs)
        return result
    mutant_name = mutant_under_test.rpartition('.')[-1]
    if self_arg is not None:
        # call to a class method where self is not bound
        result = mutants[mutant_name](self_arg, *call_args, **call_kwargs)
    else:
        result = mutants[mutant_name](*call_args, **call_kwargs)
    return result


def x_init_causal_analysis__mutmut_orig():
    """Initialize causal analysis components."""
    global _causal_engine, _visualizer
    
    if _causal_engine is None:
        _causal_engine = CausalAnalysisEngine()
        _visualizer = CausalAnalysisVisualizer(_causal_engine)
        logger.info("Causal Analysis API initialized")


def x_init_causal_analysis__mutmut_1():
    """Initialize causal analysis components."""
    global _causal_engine, _visualizer
    
    if _causal_engine is not None:
        _causal_engine = CausalAnalysisEngine()
        _visualizer = CausalAnalysisVisualizer(_causal_engine)
        logger.info("Causal Analysis API initialized")


def x_init_causal_analysis__mutmut_2():
    """Initialize causal analysis components."""
    global _causal_engine, _visualizer
    
    if _causal_engine is None:
        _causal_engine = None
        _visualizer = CausalAnalysisVisualizer(_causal_engine)
        logger.info("Causal Analysis API initialized")


def x_init_causal_analysis__mutmut_3():
    """Initialize causal analysis components."""
    global _causal_engine, _visualizer
    
    if _causal_engine is None:
        _causal_engine = CausalAnalysisEngine()
        _visualizer = None
        logger.info("Causal Analysis API initialized")


def x_init_causal_analysis__mutmut_4():
    """Initialize causal analysis components."""
    global _causal_engine, _visualizer
    
    if _causal_engine is None:
        _causal_engine = CausalAnalysisEngine()
        _visualizer = CausalAnalysisVisualizer(None)
        logger.info("Causal Analysis API initialized")


def x_init_causal_analysis__mutmut_5():
    """Initialize causal analysis components."""
    global _causal_engine, _visualizer
    
    if _causal_engine is None:
        _causal_engine = CausalAnalysisEngine()
        _visualizer = CausalAnalysisVisualizer(_causal_engine)
        logger.info(None)


def x_init_causal_analysis__mutmut_6():
    """Initialize causal analysis components."""
    global _causal_engine, _visualizer
    
    if _causal_engine is None:
        _causal_engine = CausalAnalysisEngine()
        _visualizer = CausalAnalysisVisualizer(_causal_engine)
        logger.info("XXCausal Analysis API initializedXX")


def x_init_causal_analysis__mutmut_7():
    """Initialize causal analysis components."""
    global _causal_engine, _visualizer
    
    if _causal_engine is None:
        _causal_engine = CausalAnalysisEngine()
        _visualizer = CausalAnalysisVisualizer(_causal_engine)
        logger.info("causal analysis api initialized")


def x_init_causal_analysis__mutmut_8():
    """Initialize causal analysis components."""
    global _causal_engine, _visualizer
    
    if _causal_engine is None:
        _causal_engine = CausalAnalysisEngine()
        _visualizer = CausalAnalysisVisualizer(_causal_engine)
        logger.info("CAUSAL ANALYSIS API INITIALIZED")

x_init_causal_analysis__mutmut_mutants : ClassVar[MutantDict] = {
'x_init_causal_analysis__mutmut_1': x_init_causal_analysis__mutmut_1, 
    'x_init_causal_analysis__mutmut_2': x_init_causal_analysis__mutmut_2, 
    'x_init_causal_analysis__mutmut_3': x_init_causal_analysis__mutmut_3, 
    'x_init_causal_analysis__mutmut_4': x_init_causal_analysis__mutmut_4, 
    'x_init_causal_analysis__mutmut_5': x_init_causal_analysis__mutmut_5, 
    'x_init_causal_analysis__mutmut_6': x_init_causal_analysis__mutmut_6, 
    'x_init_causal_analysis__mutmut_7': x_init_causal_analysis__mutmut_7, 
    'x_init_causal_analysis__mutmut_8': x_init_causal_analysis__mutmut_8
}

def init_causal_analysis(*args, **kwargs):
    result = _mutmut_trampoline(x_init_causal_analysis__mutmut_orig, x_init_causal_analysis__mutmut_mutants, args, kwargs)
    return result 

init_causal_analysis.__signature__ = _mutmut_signature(x_init_causal_analysis__mutmut_orig)
x_init_causal_analysis__mutmut_orig.__name__ = 'x_init_causal_analysis'


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
        raise HTTPException(status_code=500, detail=str(e))


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
        return {
            "incident_id": incident_id,
            "dashboard_data": asdict(dashboard_data)
        }
    except Exception as e:
        logger.error(f"Error creating demo incident: {e}", exc_info=True)
        raise HTTPException(status_code=500, detail=str(e))


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
        incidents.append({
            "event_id": event_id,
            "timestamp": incident.timestamp.isoformat(),
            "node_id": incident.node_id,
            "service_id": incident.service_id,
            "anomaly_type": incident.anomaly_type,
            "severity": incident.severity.value
        })
    
    return {
        "incidents": incidents,
        "total": len(incidents)
    }

