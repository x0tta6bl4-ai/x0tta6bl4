"""FastAPI app with mTLS and real system status monitoring - P0#3-P0#4 implementation"""

from fastapi import FastAPI
from fastapi.responses import JSONResponse
import logging
import os
from src.core.status_collector import get_current_status
from src.core.mtls_middleware import MTLSMiddleware
from src.core.rate_limit_middleware import RateLimitMiddleware, RateLimitConfig
from src.core.tracing_middleware import TracingMiddleware

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

app = FastAPI(
    title="x0tta6bl4",
    version="3.1.0",
    description="Self-healing mesh network node with MAPE-K autonomic loop"
)

# Import and register API routers
try:
    from src.api.vpn import router as vpn_router
    app.include_router(vpn_router)
    logger.info("✓ VPN router registered")
except ImportError as e:
    logger.warning(f"Could not import VPN router: {e}")

try:
    from src.api.users import router as users_router
    app.include_router(users_router)
    logger.info("✓ Users router registered")
except ImportError as e:
    logger.warning(f"Could not import users router: {e}")

try:
    from src.api.billing import router as billing_router
    app.include_router(billing_router)
    logger.info("✓ Billing router registered")
except ImportError as e:
    logger.warning(f"Could not import billing router: {e}")

# Add mTLS middleware (only in production)
# In development, set MTLS_ENABLED=false or leave unset for TestClient compatibility
mtls_enabled = os.getenv("MTLS_ENABLED", "false").lower() == "true"
if mtls_enabled:
    app.add_middleware(
        MTLSMiddleware,
        require_mtls=True,
        enforce_tls_13=True,
        allowed_spiffe_domains=["x0tta6bl4.mesh"],
        excluded_paths=["/health", "/metrics", "/docs", "/openapi.json"]
    )
    logger.info("✓ mTLS middleware enabled (TLS 1.3 required)")
else:
    logger.info("⚠️  mTLS middleware disabled (dev mode)")

# Add global rate limiting (DDoS protection)
rate_limit_enabled = os.getenv("RATE_LIMIT_ENABLED", "true").lower() == "true"
if rate_limit_enabled:
    rate_config = RateLimitConfig(
        requests_per_second=int(os.getenv("RATE_LIMIT_RPS", "100")),
        burst_size=int(os.getenv("RATE_LIMIT_BURST", "50")),
        block_duration=int(os.getenv("RATE_LIMIT_BLOCK_DURATION", "60"))
    )
    app.add_middleware(
        RateLimitMiddleware,
        config=rate_config,
        excluded_paths=["/health", "/metrics", "/docs", "/openapi.json"]
    )
    logger.info(f"✓ Global rate limiting enabled: {rate_config.requests_per_second} RPS")
else:
    logger.info("⚠️  Global rate limiting disabled")

# Add distributed tracing
tracing_enabled = os.getenv("TRACING_ENABLED", "true").lower() == "true"
if tracing_enabled:
    app.add_middleware(
        TracingMiddleware,
        service_name="x0tta6bl4",
        excluded_paths=["/health", "/metrics", "/docs", "/openapi.json"]
    )
    logger.info("✓ Distributed tracing enabled")
else:
    logger.info("⚠️  Distributed tracing disabled")

# Security headers via decorator
@app.middleware("http")
async def add_security_headers(request, call_next):
    response = await call_next(request)
    response.headers["Content-Security-Policy"] = "default-src 'self'"
    response.headers["X-Content-Type-Options"] = "nosniff"
    response.headers["X-Frame-Options"] = "SAMEORIGIN"
    response.headers["X-XSS-Protection"] = "1; mode=block"
    response.headers["Strict-Transport-Security"] = "max-age=31536000; includeSubDomains"
    return response

logger.info("✓ App created")

@app.get("/health")
async def health():
    """Simple health check endpoint - returns 200 if alive"""
    return {"status": "ok", "version": "3.1.0"}


@app.get("/health/live")
async def health_live():
    """Kubernetes liveness probe - is the app running?"""
    from src.core.health_check import get_liveness
    return await get_liveness()


@app.get("/health/ready")
async def health_ready():
    """Kubernetes readiness probe - is the app ready to serve traffic?"""
    from src.core.health_check import get_readiness
    result = await get_readiness()
    if result["status"] == "not_ready":
        from fastapi.responses import JSONResponse
        return JSONResponse(status_code=503, content=result)
    return result


@app.get("/health/detailed")
async def health_detailed():
    """Detailed health check with all dependency statuses."""
    from src.core.health_check import get_health_status, HealthStatus
    from fastapi.responses import JSONResponse
    result = await get_health_status()
    status_code = 200 if result.status != HealthStatus.UNHEALTHY else 503
    return JSONResponse(status_code=status_code, content=result.to_dict())

@app.get("/status")
async def status():
    """
    Comprehensive status endpoint with real system metrics
    
    Returns:
    - System metrics (CPU, memory, disk, network)
    - Mesh network status (connected peers)
    - MAPE-K loop state
    - Overall system health
    """
    try:
        status_data = get_current_status()
        return JSONResponse(content=status_data)
    except Exception as e:
        logger.error(f"Error getting status: {e}")
        # Fallback to minimal status if error
        return JSONResponse(
            status_code=200,
            content={
                "status": "healthy",
                "version": "3.1.0",
                "error": str(e)
            }
        )

@app.get("/")
async def root():
    """API root with documentation links"""
    return {
        "name": "x0tta6bl4",
        "version": "3.1.0",
        "docs": "/docs",
        "endpoints": {
            "health": "/health",
            "status": "/status",
            "mesh/status": "/mesh/status",
            "mesh/peers": "/mesh/peers",
            "mesh/routes": "/mesh/routes"
        }
    }


# Mesh network endpoints
@app.get("/mesh/status")
async def mesh_status():
    """Get Yggdrasil mesh network status"""
    try:
        from src.network.yggdrasil_client import get_yggdrasil_status
        return get_yggdrasil_status()
    except Exception as e:
        logger.error(f"Error getting mesh status: {e}")
        return JSONResponse(status_code=500, content={"error": str(e)})


@app.get("/mesh/peers")
async def mesh_peers():
    """Get Yggdrasil mesh network peers"""
    try:
        from src.network.yggdrasil_client import get_yggdrasil_peers
        return get_yggdrasil_peers()
    except Exception as e:
        logger.error(f"Error getting mesh peers: {e}")
        return JSONResponse(status_code=500, content={"error": str(e)})


@app.get("/mesh/routes")
async def mesh_routes():
    """Get Yggdrasil mesh network routes"""
    try:
        from src.network.yggdrasil_client import get_yggdrasil_routes
        return get_yggdrasil_routes()
    except Exception as e:
        logger.error(f"Error getting mesh routes: {e}")
        return JSONResponse(status_code=500, content={"error": str(e)})

logger.info("✓ Routes registered")

if __name__ == "__main__":
    import uvicorn
    from src.core.settings import settings
    logger.info(f"Starting server on {settings.api_host}:{settings.api_port}...")
    uvicorn.run(app, host=settings.api_host, port=settings.api_port)
