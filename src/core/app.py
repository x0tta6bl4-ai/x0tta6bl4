"""Minimal FastAPI bootstrap - for P0#1 testing"""

from fastapi import FastAPI
import logging

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

app = FastAPI(
    title="x0tta6bl4",
    version="3.1.0",
    description="Minimal API for bootstrap testing"
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
    """Health check"""
    return {"status": "ok", "version": "3.1.0"}

@app.get("/status")
async def status():
    """Status endpoint"""
    return {
        "status": "healthy",
        "version": "3.1.0",
        "loop_running": True
    }

@app.get("/")
async def root():
    """Root"""
    return {"name": "x0tta6bl4", "docs": "/docs"}

logger.info("✓ Routes registered")

if __name__ == "__main__":
    import uvicorn
    logger.info("Starting server...")
    uvicorn.run(app, host="0.0.0.0", port=8000)
