"""Minimal FastAPI bootstrap - for P0#1 testing"""

import logging

from fastapi import FastAPI

from src.version import __version__

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

app = FastAPI(
    title="x0tta6bl4", version=__version__, description="Minimal API for bootstrap testing"
)

logger.info("✓ App created")


@app.get("/health")
async def health():
    """Health check"""
    return {"status": "ok", "version": __version__}


@app.get("/status")
async def status():
    """Status endpoint"""
    return {"status": "healthy", "version": __version__, "loop_running": True}


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
