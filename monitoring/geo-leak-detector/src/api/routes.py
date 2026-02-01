"""
FastAPI Routes for Geo-Leak Detector Dashboard API
"""
from datetime import datetime, timedelta
from typing import List, Optional, Dict, Any
from uuid import UUID

from fastapi import APIRouter, Depends, HTTPException, Query, WebSocket, WebSocketDisconnect
from fastapi.responses import PlainTextResponse
from sqlalchemy import func, select, desc
from sqlalchemy.ext.asyncio import AsyncSession

from config.settings import settings
from src.models.database import (
    get_db, LeakEvent, DetectionStatus, MAPEKIntegrationLog,
    LeakType, LeakSeverity, RemediationStatus
)
from src.core.leak_detector import LeakDetectionEngine
from src.services.alert_manager import AlertManager
from src.services.killswitch import KillSwitchManager
from src.services.prometheus_metrics import metrics


router = APIRouter()

# Global instances (initialized in main.py)
detection_engine: Optional[LeakDetectionEngine] = None
alert_manager: Optional[AlertManager] = None
killswitch_manager: Optional[KillSwitchManager] = None


# ========== WebSocket Connections ==========
class ConnectionManager:
    """Manage WebSocket connections for real-time updates"""
    
    def __init__(self):
        self.active_connections: List[WebSocket] = []
    
    async def connect(self, websocket: WebSocket):
        await websocket.accept()
        self.active_connections.append(websocket)
    
    def disconnect(self, websocket: WebSocket):
        self.active_connections.remove(websocket)
    
    async def broadcast(self, message: Dict[str, Any]):
        for connection in self.active_connections:
            try:
                await connection.send_json(message)
            except Exception:
                pass


ws_manager = ConnectionManager()


# ========== API Routes ==========

@router.get("/health")
async def health_check():
    """Health check endpoint"""
    return {
        "status": "healthy",
        "timestamp": datetime.utcnow().isoformat(),
        "version": settings.version,
        "environment": settings.environment
    }


@router.get("/status")
async def get_status():
    """Get system status"""
    status = {
        "detector": detection_engine.get_status() if detection_engine else None,
        "killswitch": killswitch_manager.get_status() if killswitch_manager else None,
        "timestamp": datetime.utcnow().isoformat()
    }
    return status


# ========== Leak Events Routes ==========

@router.get("/leaks", response_model=List[Dict[str, Any]])
async def get_leaks(
    db: AsyncSession = Depends(get_db),
    leak_type: Optional[LeakType] = None,
    severity: Optional[LeakSeverity] = None,
    resolved: Optional[bool] = None,
    limit: int = Query(100, ge=1, le=1000),
    offset: int = Query(0, ge=0)
):
    """Get leak events with optional filtering"""
    query = select(LeakEvent).order_by(desc(LeakEvent.timestamp))
    
    if leak_type:
        query = query.where(LeakEvent.leak_type == leak_type)
    if severity:
        query = query.where(LeakEvent.severity == severity)
    if resolved is not None:
        query = query.where(LeakEvent.resolved == resolved)
    
    query = query.offset(offset).limit(limit)
    
    result = await db.execute(query)
    leaks = result.scalars().all()
    
    return [leak.to_dict() for leak in leaks]


@router.get("/leaks/{leak_id}")
async def get_leak(leak_id: UUID, db: AsyncSession = Depends(get_db)):
    """Get a specific leak event"""
    result = await db.execute(
        select(LeakEvent).where(LeakEvent.id == leak_id)
    )
    leak = result.scalar_one_or_none()
    
    if not leak:
        raise HTTPException(status_code=404, detail="Leak not found")
    
    return leak.to_dict()


@router.post("/leaks/{leak_id}/resolve")
async def resolve_leak(
    leak_id: UUID,
    db: AsyncSession = Depends(get_db),
    resolved_by: str = "manual"
):
    """Mark a leak as resolved"""
    result = await db.execute(
        select(LeakEvent).where(LeakEvent.id == leak_id)
    )
    leak = result.scalar_one_or_none()
    
    if not leak:
        raise HTTPException(status_code=404, detail="Leak not found")
    
    leak.resolved = True
    leak.resolved_at = datetime.utcnow()
    leak.resolved_by = resolved_by
    
    await db.commit()
    
    # Update metrics
    if metrics:
        # Recalculate unresolved count
        unresolved_result = await db.execute(
            select(func.count()).where(LeakEvent.resolved == False)
        )
        metrics.update_unresolved_leaks(unresolved_result.scalar())
    
    return {"status": "resolved", "leak_id": str(leak_id)}


@router.get("/leaks/stats/summary")
async def get_leak_stats(db: AsyncSession = Depends(get_db)):
    """Get leak statistics summary"""
    # Total leaks
    total_result = await db.execute(select(func.count()).select_from(LeakEvent))
    total = total_result.scalar()
    
    # By type
    type_result = await db.execute(
        select(LeakEvent.leak_type, func.count())
        .group_by(LeakEvent.leak_type)
    )
    by_type = {t.value: c for t, c in type_result.all()}
    
    # By severity
    severity_result = await db.execute(
        select(LeakEvent.severity, func.count())
        .group_by(LeakEvent.severity)
    )
    by_severity = {s.value: c for s, c in severity_result.all()}
    
    # Unresolved
    unresolved_result = await db.execute(
        select(func.count()).where(LeakEvent.resolved == False)
    )
    unresolved = unresolved_result.scalar()
    
    # Recent (last 24h)
    recent_result = await db.execute(
        select(func.count()).where(
            LeakEvent.timestamp >= datetime.utcnow() - timedelta(hours=24)
        )
    )
    recent = recent_result.scalar()
    
    return {
        "total": total,
        "unresolved": unresolved,
        "recent_24h": recent,
        "by_type": by_type,
        "by_severity": by_severity
    }


# ========== Detection Control Routes ==========

@router.post("/detection/start")
async def start_detection():
    """Start leak detection monitoring"""
    if not detection_engine:
        raise HTTPException(status_code=503, detail="Detection engine not initialized")
    
    if detection_engine.running:
        return {"status": "already_running"}
    
    # Start in background
    import asyncio
    asyncio.create_task(detection_engine.start_monitoring())
    
    if metrics:
        metrics.update_detector_status(True)
    
    return {"status": "started"}


@router.post("/detection/stop")
async def stop_detection():
    """Stop leak detection monitoring"""
    if not detection_engine:
        raise HTTPException(status_code=503, detail="Detection engine not initialized")
    
    detection_engine.stop_monitoring()
    
    if metrics:
        metrics.update_detector_status(False)
    
    return {"status": "stopped"}


@router.post("/detection/check")
async def run_manual_check():
    """Run a manual leak check"""
    if not detection_engine:
        raise HTTPException(status_code=503, detail="Detection engine not initialized")
    
    results = await detection_engine.run_full_check()
    
    return {
        "status": "completed",
        "checks": len(results),
        "leaks_found": sum(len(r.leaks) for r in results),
        "results": [
            {
                "check_type": r.check_type,
                "status": r.status,
                "leaks": len(r.leaks)
            }
            for r in results
        ]
    }


# ========== Kill-Switch Routes ==========

@router.post("/killswitch/trigger")
async def trigger_killswitch(leak_id: UUID, db: AsyncSession = Depends(get_db)):
    """Manually trigger kill-switch for a leak"""
    if not killswitch_manager:
        raise HTTPException(status_code=503, detail="Kill-switch not initialized")
    
    # Get leak details
    result = await db.execute(
        select(LeakEvent).where(LeakEvent.id == leak_id)
    )
    leak = result.scalar_one_or_none()
    
    if not leak:
        raise HTTPException(status_code=404, detail="Leak not found")
    
    # Import LeakEvent from core for killswitch
    from src.core.leak_detector import LeakEvent as CoreLeakEvent, LeakType, LeakSeverity
    
    core_leak = CoreLeakEvent(
        timestamp=leak.timestamp,
        leak_type=LeakType(leak.leak_type.value),
        severity=LeakSeverity(leak.severity.value),
        message=leak.message,
        detected_value=leak.detected_value,
        expected_value=leak.expected_value,
        source_ip=leak.source_ip
    )
    
    results = await killswitch_manager.trigger(core_leak)
    
    # Update leak record
    leak.remediation_action = "Manual kill-switch triggered"
    leak.remediation_status = RemediationStatus.IN_PROGRESS
    leak.remediation_timestamp = datetime.utcnow()
    await db.commit()
    
    return {
        "status": "triggered",
        "actions": [
            {
                "action": r.action.value,
                "success": r.success,
                "message": r.message
            }
            for r in results
        ]
    }


@router.post("/killswitch/restore")
async def restore_network():
    """Restore network after kill-switch activation"""
    if not killswitch_manager:
        raise HTTPException(status_code=503, detail="Kill-switch not initialized")
    
    results = await killswitch_manager.restore_network()
    
    return {
        "status": "restoration_attempted",
        "actions": [
            {
                "action": r.action.value,
                "success": r.success,
                "message": r.message
            }
            for r in results
        ]
    }


# ========== WebSocket Routes ==========

@router.websocket("/ws")
async def websocket_endpoint(websocket: WebSocket):
    """WebSocket endpoint for real-time updates"""
    await ws_manager.connect(websocket)
    
    try:
        # Send initial status
        await websocket.send_json({
            "type": "connected",
            "timestamp": datetime.utcnow().isoformat(),
            "message": "Connected to Geo-Leak Detector real-time feed"
        })
        
        # Keep connection alive and handle client messages
        while True:
            try:
                data = await websocket.receive_text()
                # Handle ping/pong or other client messages
                if data == "ping":
                    await websocket.send_json({"type": "pong"})
            except WebSocketDisconnect:
                break
            
    except WebSocketDisconnect:
        pass
    finally:
        ws_manager.disconnect(websocket)


@router.websocket("/ws/leaks")
async def websocket_leaks(websocket: WebSocket):
    """WebSocket endpoint for leak updates only"""
    await ws_manager.connect(websocket)
    
    try:
        while True:
            await asyncio.sleep(1)  # Keep connection alive
    except WebSocketDisconnect:
        ws_manager.disconnect(websocket)


# ========== Prometheus Metrics Route ==========

@router.get("/metrics")
async def get_metrics():
    """Prometheus metrics endpoint"""
    if metrics:
        return PlainTextResponse(
            content=metrics.get_metrics(),
            media_type="text/plain"
        )
    return PlainTextResponse(content="# No metrics available")


# ========== MAPE-K Integration Routes ==========

@router.get("/mapek/events")
async def get_mapek_events(
    db: AsyncSession = Depends(get_db),
    limit: int = Query(100, ge=1, le=1000)
):
    """Get MAPE-K integration events"""
    result = await db.execute(
        select(MAPEKIntegrationLog)
        .order_by(desc(MAPEKIntegrationLog.timestamp))
        .limit(limit)
    )
    events = result.scalars().all()
    
    return [
        {
            "id": str(e.id),
            "timestamp": e.timestamp.isoformat(),
            "event_type": e.event_type,
            "consciousness_state": e.consciousness_state,
            "phi_ratio": e.phi_ratio,
            "data": e.data
        }
        for e in events
    ]


@router.post("/mapek/report")
async def report_mapek_event(
    event: Dict[str, Any],
    db: AsyncSession = Depends(get_db)
):
    """Report a MAPE-K event from external system"""
    mapek_log = MAPEKIntegrationLog(
        event_type=event.get("event_type", "unknown"),
        consciousness_state=event.get("consciousness_state"),
        phi_ratio=event.get("phi_ratio"),
        data=event.get("data")
    )
    
    db.add(mapek_log)
    await db.commit()
    
    # Update metrics
    if metrics:
        metrics.record_mapek_event(event.get("event_type", "unknown"))
        if event.get("phi_ratio"):
            metrics.update_mapek_phi(event["phi_ratio"])
    
    return {"status": "recorded", "id": str(mapek_log.id)}


# ========== Configuration Routes ==========

@router.get("/config")
async def get_config():
    """Get current configuration (safe values only)"""
    return {
        "check_interval": settings.detection.check_interval,
        "auto_remediate": settings.detection.auto_remediate,
        "expected_exit_ips": list(settings.detection.expected_exit_ips),
        "expected_dns_servers": list(settings.detection.expected_dns_servers),
        "telegram_enabled": settings.telegram.enabled,
        "prometheus_enabled": settings.prometheus.enabled,
        "mapek_enabled": settings.mapek.enabled,
    }


# Helper function to broadcast leak events
async def broadcast_leak_event(leak_event):
    """Broadcast leak event to all WebSocket clients"""
    await ws_manager.broadcast({
        "type": "leak_detected",
        "timestamp": datetime.utcnow().isoformat(),
        "data": leak_event.to_dict()
    })
