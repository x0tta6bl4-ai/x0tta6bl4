"""FastAPI app with mTLS and real system status monitoring - P0#3-P0#4 implementation"""

from fastapi import FastAPI
from fastapi.responses import JSONResponse
import logging
import os
from src.core.status_collector import get_current_status
from src.core.mtls_middleware import MTLSMiddleware

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

app = FastAPI(
    title="x0tta6bl4",
    version="3.1.0",
    description="Self-healing mesh network node with MAPE-K autonomic loop"
)

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
    """Health check endpoint - returns 200 if alive"""
    return {"status": "ok", "version": "3.1.0"}

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
