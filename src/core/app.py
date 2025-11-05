from __future__ import annotations

from fastapi import FastAPI
from .health import get_health

app = FastAPI(title="x0tta6bl4", version="1.0.0", docs_url="/docs")


@app.get("/health", summary="Liveness / readiness probe")
async def health():  # pragma: no cover - trivial wrapper
    return get_health()


def create_app() -> FastAPI:
    """Factory for ASGI servers / testing frameworks.

    Allows future injection of:
      - dependency overrides
      - middleware (tracing, metrics, auth)
      - startup/shutdown hooks
    """
    return app


if __name__ == "__main__":  # pragma: no cover
    import uvicorn

    uvicorn.run("src.core.app:app", host="0.0.0.0", port=8000, reload=False)
