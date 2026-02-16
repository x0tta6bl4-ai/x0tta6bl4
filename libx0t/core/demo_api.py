"""
Demo API для sales presentations
Показывает все интегрированные компоненты в действии
"""

import logging
from typing import Annotated, Any, Dict, Optional

from fastapi import Depends, FastAPI, HTTPException
from fastapi.responses import JSONResponse

logger = logging.getLogger(__name__)

app = FastAPI(
    title="x0tta6bl4 Demo API",
    description="Self-Healing Mesh Network - Integrated Demo",
    version="1.0.0",
)

# Global variable to hold the IntegratedMAPEKCycle instance
# It will be initialized via a dependency
_integrated_cycle_instance: Optional["IntegratedMAPEKCycle"] = None


def get_integrated_cycle_dependency() -> "IntegratedMAPEKCycle":
    """Dependency that provides a singleton IntegratedMAPEKCycle instance."""
    global _integrated_cycle_instance
    if _integrated_cycle_instance is None:
        # Import IntegratedMAPEKCycle here to delay module-level side effects
        from src.self_healing.mape_k_integrated import IntegratedMAPEKCycle

        _integrated_cycle_instance = IntegratedMAPEKCycle(
            enable_observe_mode=True, enable_chaos=True, enable_ebpf_explainer=True
        )
    return _integrated_cycle_instance


@app.get("/")
async def root():
    """Root endpoint"""
    return {
        "name": "x0tta6bl4",
        "version": "1.0.0",
        "status": "operational",
        "components": {
            "mape_k": "integrated",
            "graphsage_observe": "enabled",
            "chaos_engineering": "enabled",
            "ebpf_explainer": "enabled",
        },
    }


@app.get("/api/status")
async def get_status(
    integrated_cycle: Annotated[
        "IntegratedMAPEKCycle", Depends(get_integrated_cycle_dependency)
    ],
):
    """Получить статус всех компонентов"""
    return integrated_cycle.get_system_status()


@app.post("/api/demo/anomaly")
async def demo_anomaly_detection(
    metrics: Dict[str, Any],
    integrated_cycle: Annotated[
        "IntegratedMAPEKCycle", Depends(get_integrated_cycle_dependency)
    ],
):
    """
    Демонстрация обнаружения и восстановления аномалии

    Пример metrics:
    {
        "node_id": "node-001",
        "cpu_percent": 95.0,
        "memory_percent": 87.0,
        "packet_loss_percent": 7.0,
        "latency_ms": 150.0
    }
    """
    try:
        result = integrated_cycle.run_cycle(metrics)
        return JSONResponse(content=result)
    except Exception as e:
        logger.error(f"Error in demo anomaly detection: {e}")
        raise HTTPException(status_code=500, detail=str(e))


@app.post("/api/demo/chaos")
async def demo_chaos_experiment(
    experiment: Dict[str, Any],
    integrated_cycle: Annotated[
        "IntegratedMAPEKCycle", Depends(get_integrated_cycle_dependency)
    ],
):
    """
    Демонстрация chaos engineering

    Пример experiment:
    {
        "type": "node_failure",
        "duration": 10
    }
    """
    try:
        exp_type = experiment.get("type", "node_failure")
        duration = experiment.get("duration", 10)

        result = integrated_cycle.run_chaos_experiment(exp_type, duration)
        return JSONResponse(content=result)
    except Exception as e:
        logger.error(f"Error in chaos experiment: {e}")
        raise HTTPException(status_code=500, detail=str(e))


@app.get("/api/demo/observe-mode/stats")
async def get_observe_mode_stats(
    integrated_cycle: Annotated[
        "IntegratedMAPEKCycle", Depends(get_integrated_cycle_dependency)
    ],
):
    """Получить статистику GraphSAGE Observe Mode"""
    if not integrated_cycle.observe_detector:
        raise HTTPException(status_code=404, detail="Observe Mode not enabled")

    return integrated_cycle.observe_detector.get_stats()


@app.get("/api/demo/chaos/stats")
async def get_chaos_stats(
    integrated_cycle: Annotated[
        "IntegratedMAPEKCycle", Depends(get_integrated_cycle_dependency)
    ],
):
    """Получить статистику Chaos Engineering"""
    if not integrated_cycle.chaos_controller:
        raise HTTPException(status_code=404, detail="Chaos Controller not enabled")

    return integrated_cycle.chaos_controller.get_recovery_stats()


@app.get("/api/demo/explain/{event_type}")
async def explain_ebpf_event(
    event_type: str,
    integrated_cycle: Annotated[
        "IntegratedMAPEKCycle", Depends(get_integrated_cycle_dependency)
    ],
):
    """
    Объяснить eBPF событие

    Примеры: packet_drop, high_cpu_usage, connection_established
    """
    if not integrated_cycle.ebpf_explainer:
        raise HTTPException(status_code=404, detail="eBPF Explainer not enabled")

    try:
        # Import EBPFEvent and EBPFEventType here to delay module-level side effects
        from src.network.ebpf.explainer import EBPFEvent, EBPFEventType

        # Создать пример события
        event = EBPFEvent(
            event_type=(
                EBPFEventType[event_type.upper()]
                if hasattr(EBPFEventType, event_type.upper())
                else EBPFEventType.PACKET_DROP
            ),
            timestamp=0.0,
            node_id="demo-node",
            program_id="demo-program",
            details={"demo": True},
        )

        explanation = integrated_cycle.ebpf_explainer.explain_event(event)

        return {
            "event_type": event_type,
            "explanation": explanation,
            "human_readable": event.human_readable,
        }
    except Exception as e:
        logger.error(f"Error explaining event: {e}")
        raise HTTPException(status_code=500, detail=str(e))


if __name__ == "__main__":
    import uvicorn

    uvicorn.run(app, host="0.0.0.0", port=8081)  # nosec B104
