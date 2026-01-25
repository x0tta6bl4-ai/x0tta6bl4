"""
Demo API для sales presentations
Показывает все интегрированные компоненты в действии
"""

from fastapi import FastAPI, HTTPException
from fastapi.responses import JSONResponse
from typing import Dict, Any, Optional
import logging

from src.self_healing.mape_k_integrated import IntegratedMAPEKCycle

logger = logging.getLogger(__name__)

app = FastAPI(
    title="x0tta6bl4 Demo API",
    description="Self-Healing Mesh Network - Integrated Demo",
    version="1.0.0"
)

# Инициализация интегрированного цикла
integrated_cycle = IntegratedMAPEKCycle(
    enable_observe_mode=True,
    enable_chaos=True,
    enable_ebpf_explainer=True
)


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
            "ebpf_explainer": "enabled"
        }
    }


@app.get("/api/status")
async def get_status():
    """Получить статус всех компонентов"""
    return integrated_cycle.get_system_status()


@app.post("/api/demo/anomaly")
async def demo_anomaly_detection(metrics: Dict[str, Any]):
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
async def demo_chaos_experiment(experiment: Dict[str, Any]):
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
async def get_observe_mode_stats():
    """Получить статистику GraphSAGE Observe Mode"""
    if not integrated_cycle.observe_detector:
        raise HTTPException(status_code=404, detail="Observe Mode not enabled")
    
    return integrated_cycle.observe_detector.get_stats()


@app.get("/api/demo/chaos/stats")
async def get_chaos_stats():
    """Получить статистику Chaos Engineering"""
    if not integrated_cycle.chaos_controller:
        raise HTTPException(status_code=404, detail="Chaos Controller not enabled")
    
    return integrated_cycle.chaos_controller.get_recovery_stats()


@app.get("/api/demo/explain/{event_type}")
async def explain_ebpf_event(event_type: str):
    """
    Объяснить eBPF событие
    
    Примеры: packet_drop, high_cpu_usage, connection_established
    """
    if not integrated_cycle.ebpf_explainer:
        raise HTTPException(status_code=404, detail="eBPF Explainer not enabled")
    
    try:
        from src.network.ebpf.explainer import EBPFEventType, EBPFEvent
        
        # Создать пример события
        event = EBPFEvent(
            event_type=EBPFEventType[event_type.upper()] if hasattr(EBPFEventType, event_type.upper()) else EBPFEventType.PACKET_DROP,
            timestamp=0.0,
            node_id="demo-node",
            program_id="demo-program",
            details={"demo": True}
        )
        
        explanation = integrated_cycle.ebpf_explainer.explain_event(event)
        
        return {
            "event_type": event_type,
            "explanation": explanation,
            "human_readable": event.human_readable
        }
    except Exception as e:
        logger.error(f"Error explaining event: {e}")
        raise HTTPException(status_code=500, detail=str(e))


if __name__ == "__main__":
    import uvicorn
    uvicorn.run(app, host="0.0.0.0", port=8081)

