from __future__ import annotations

from fastapi import FastAPI
from .health import get_health

app = FastAPI(title="x0tta6bl4", version="1.0.0", docs_url="/docs")


@app.get("/health", summary="Liveness / readiness probe")
async def health():  # pragma: no cover - trivial wrapper
    return get_health()


@app.get("/mesh/status", summary="Get Yggdrasil mesh node status")
async def mesh_status():
    """Get current mesh network node status."""
    try:
        from src.network.yggdrasil_client import get_yggdrasil_status
        return get_yggdrasil_status()
    except ImportError:
        return {"status": "error", "error": "Yggdrasil client not available"}


@app.get("/mesh/peers", summary="Get list of mesh network peers")
async def mesh_peers():
    """Get list of connected mesh peers."""
    try:
        from src.network.yggdrasil_client import get_yggdrasil_peers
        return get_yggdrasil_peers()
    except ImportError:
        return {"status": "error", "error": "Yggdrasil client not available", "peers": [], "count": 0}


@app.get("/mesh/routes", summary="Get mesh routing table information")
async def mesh_routes():
    """Get routing table information."""
    try:
        from src.network.yggdrasil_client import get_yggdrasil_routes
        return get_yggdrasil_routes()
    except ImportError:
        return {"status": "error", "error": "Yggdrasil client not available", "routing_table_size": 0}


@app.get("/metrics", summary="Prometheus metrics endpoint")
async def metrics():
    """Expose Prometheus metrics for monitoring."""
    try:
        from src.monitoring.metrics import get_metrics
        return get_metrics()
    except ImportError:
        from fastapi import Response
        return Response(
            content="# Prometheus metrics not available\n",
            media_type="text/plain",
        )


def create_app() -> FastAPI:
    """Factory for ASGI servers / testing frameworks.

    Allows future injection of:
      - dependency overrides
      - middleware (tracing, metrics, auth)
      - startup/shutdown hooks
    """
    # Add metrics middleware
    try:
        from src.monitoring.metrics import MetricsMiddleware
        app.add_middleware(MetricsMiddleware)
    except ImportError:
        pass  # Metrics middleware optional

    return app


if __name__ == "__main__":  # pragma: no cover
    import uvicorn

    uvicorn.run("src.core.app:app", host="0.0.0.0", port=8000, reload=False)


def main():
    """CLI entry point for x0tta6bl4-server command."""
    import uvicorn
    import os
    
    # Get host/port from environment (set by docker-entrypoint.sh)
    host = os.environ.get("HOST", "0.0.0.0")
    port = int(os.environ.get("PORT", "8000"))
    
    uvicorn.run("src.core.app:app", host=host, port=port, reload=False)
