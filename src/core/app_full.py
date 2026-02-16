"""Minimal FastAPI bootstrap - for P0#1 testing"""

import logging

from fastapi import FastAPI

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

app = FastAPI(
    title="x0tta6bl4", version="3.1.0", description="Minimal API for bootstrap testing"
)

logger.info("✓ App created")


@app.get("/health")
async def health():
    """Health check"""
    return {"status": "ok", "version": "3.1.0"}


@app.get("/status")
async def status():
    """Status endpoint"""
    return {"status": "healthy", "version": "3.1.0", "loop_running": True}


@app.get("/")
async def root():
    """Root"""
    return {"name": "x0tta6bl4", "docs": "/docs"}


logger.info("✓ Routes registered")

if __name__ == "__main__":
    import uvicorn

    from src.core.settings import settings

    logger.info(f"Starting server on {settings.api_host}:{settings.api_port}...")
    uvicorn.run(app, host=settings.api_host, port=settings.api_port)
