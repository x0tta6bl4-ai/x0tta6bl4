"""FastAPI app with real system status monitoring - P0#3 implementation"""

from fastapi import FastAPI
from fastapi.responses import JSONResponse
import logging
from src.core.status_collector import get_current_status

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

app = FastAPI(
    title="x0tta6bl4",
    version="3.1.0",
    description="Self-healing mesh network node with MAPE-K autonomic loop"
)

# Security headers via decorator
@app.middleware("http")
async def add_security_headers(request, call_next):
    response = await call_next(request)
    response.headers["Content-Security-Policy"] = "default-src 'self'"
    response.headers["X-Content-Type-Options"] = "nosniff"
    response.headers["X-Frame-Options"] = "SAMEORIGIN"
    response.headers["X-XSS-Protection"] = "1; mode=block"
    response.headers["Strict-Transport-Security"] = "max-age=31536000"
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
            "status": "/status"
        }
    }

logger.info("✓ Routes registered")

if __name__ == "__main__":
    import uvicorn
    logger.info("Starting server...")
    uvicorn.run(app, host="0.0.0.0", port=8000)
