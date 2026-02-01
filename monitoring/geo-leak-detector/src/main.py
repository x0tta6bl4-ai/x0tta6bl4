"""
Main entry point for Geo-Leak Detector
FastAPI application with integrated detection engine
"""
import asyncio
import signal
import sys
from contextlib import asynccontextmanager

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from fastapi.middleware.gzip import GZipMiddleware
import structlog

from config.settings import settings
from src.models.database import init_db
from src.core.leak_detector import LeakDetectionEngine, LeakEvent
from src.services.alert_manager import AlertManager
from src.services.killswitch import KillSwitchManager
from src.services.prometheus_metrics import metrics
from src.api import routes


# Configure structured logging
structlog.configure(
    processors=[
        structlog.stdlib.filter_by_level,
        structlog.stdlib.add_logger_name,
        structlog.stdlib.add_log_level,
        structlog.stdlib.PositionalArgumentsFormatter(),
        structlog.processors.TimeStamper(fmt="iso"),
        structlog.processors.StackInfoRenderer(),
        structlog.processors.format_exc_info,
        structlog.processors.UnicodeDecoder(),
        structlog.processors.JSONRenderer()
    ],
    context_class=dict,
    logger_factory=structlog.stdlib.LoggerFactory(),
    wrapper_class=structlog.stdlib.BoundLogger,
    cache_logger_on_first_use=True,
)

logger = structlog.get_logger()

# Global service instances
detection_engine: LeakDetectionEngine = None
alert_manager: AlertManager = None
killswitch_manager: KillSwitchManager = None


async def on_leak_detected(leak: LeakEvent):
    """Callback when a leak is detected"""
    logger.critical(
        "Leak detected",
        leak_type=leak.leak_type.value,
        severity=leak.severity.value,
        detected_value=leak.detected_value
    )
    
    # Record metrics
    if metrics:
        metrics.record_leak(
            leak_type=leak.leak_type.value,
            severity=leak.severity.value,
            country=leak.detected_country
        )
    
    # Store in database
    from src.models.database import async_session_maker, LeakEvent as DBLeakEvent, RemediationStatus
    
    async with async_session_maker() as session:
        db_leak = DBLeakEvent(
            leak_type=leak.leak_type,
            severity=leak.severity,
            message=leak.message,
            detected_value=leak.detected_value,
            expected_value=leak.expected_value,
            source_ip=leak.source_ip,
            detected_country=leak.detected_country,
            detected_city=leak.detected_city,
            detected_isp=leak.detected_isp,
            user_agent=leak.user_agent,
            check_source=leak.check_source,
            raw_data=leak.raw_data
        )
        session.add(db_leak)
        await session.commit()
        
        # Update leak with DB ID for reference
        if leak.raw_data is None:
            leak.raw_data = {}
        leak.raw_data["id"] = str(db_leak.id)
    
    # Send alerts
    if alert_manager:
        await alert_manager.send_alert(leak)
    
    # Trigger kill-switch for critical leaks
    if leak.severity.value == "critical" and killswitch_manager:
        logger.critical("Triggering kill-switch for critical leak")
        await killswitch_manager.trigger(leak)
        
        # Update metrics
        if metrics:
            metrics.record_killswitch(leak.leak_type.value)
    
    # Broadcast to WebSocket clients
    await routes.broadcast_leak_event(leak)
    
    # Update unresolved count metric
    if metrics:
        async with async_session_maker() as session:
            from sqlalchemy import func
            from src.models.database import LeakEvent as DBLeakEvent
            result = await session.execute(
                select(func.count()).where(DBLeakEvent.resolved == False)
            )
            metrics.update_unresolved_leaks(result.scalar())


async def on_check_complete(result):
    """Callback when a check completes"""
    if metrics:
        metrics.record_check_duration(
            check_type=result.check_type,
            duration_seconds=result.response_time_ms / 1000
        )
        
        if result.status == "error":
            metrics.record_check_error(
                check_type=result.check_type,
                error_type=result.error_message or "unknown"
            )
        
        # Update detection status
        metrics.update_detection_status(
            detector_type=result.check_type,
            ok=result.status != "error"
        )
        
        metrics.update_last_check()


async def start_detection_engine():
    """Start the leak detection engine"""
    global detection_engine
    
    detection_engine = LeakDetectionEngine(
        check_interval=settings.detection.check_interval
    )
    
    # Register callbacks
    detection_engine.on_leak_detected.append(on_leak_detected)
    detection_engine.on_check_complete.append(on_check_complete)
    
    # Start monitoring in background
    asyncio.create_task(detection_engine.start_monitoring())
    
    if metrics:
        metrics.update_detector_status(True)
    
    logger.info("Detection engine started")


async def stop_detection_engine():
    """Stop the leak detection engine"""
    global detection_engine
    
    if detection_engine:
        detection_engine.stop_monitoring()
        
        if metrics:
            metrics.update_detector_status(False)
        
        logger.info("Detection engine stopped")


@asynccontextmanager
async def lifespan(app: FastAPI):
    """Application lifespan manager"""
    logger.info("=" * 60)
    logger.info(f"Starting {settings.app_name} v{settings.version}")
    logger.info("=" * 60)
    
    # Initialize database
    logger.info("Initializing database...")
    await init_db()
    logger.info("Database initialized")
    
    # Initialize services
    global alert_manager, killswitch_manager
    
    # Alert manager
    alert_manager = AlertManager()
    await alert_manager.start()
    logger.info("Alert manager started")
    
    # Kill-switch manager
    killswitch_manager = KillSwitchManager()
    logger.info("Kill-switch manager initialized")
    
    # Start detection engine
    await start_detection_engine()
    
    # Update routes with global instances
    routes.detection_engine = detection_engine
    routes.alert_manager = alert_manager
    routes.killswitch_manager = killswitch_manager
    
    logger.info("Application startup complete")
    
    yield
    
    # Shutdown
    logger.info("Shutting down...")
    
    await stop_detection_engine()
    await alert_manager.stop()
    
    logger.info("Application shutdown complete")


# Create FastAPI application
app = FastAPI(
    title=settings.app_name,
    version=settings.version,
    description="Real-time geolocation leak detection and monitoring system",
    lifespan=lifespan
)

# Add middleware
app.add_middleware(GZipMiddleware, minimum_size=1000)
app.add_middleware(
    CORSMiddleware,
    allow_origins=settings.api.cors_origins,
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# Include routes
app.include_router(routes.router, prefix="/api/v1")


@app.get("/")
async def root():
    """Root endpoint"""
    return {
        "name": settings.app_name,
        "version": settings.version,
        "environment": settings.environment,
        "status": "running",
        "docs": "/docs"
    }


# Signal handlers for graceful shutdown
def signal_handler(sig, frame):
    """Handle shutdown signals"""
    logger.info(f"Received signal {sig}, initiating shutdown...")
    sys.exit(0)


signal.signal(signal.SIGINT, signal_handler)
signal.signal(signal.SIGTERM, signal_handler)


if __name__ == "__main__":
    import uvicorn
    
    uvicorn.run(
        "src.main:app",
        host=settings.api.host,
        port=settings.api.port,
        reload=settings.api.debug,
        log_level="info"
    )
