"""
x0tta6bl4 gateway application entrypoint.
"""

import importlib
import logging
import os
import random
import secrets
import time
from pathlib import Path
from typing import Any, Dict, List, Optional

from fastapi import APIRouter, Depends, FastAPI, HTTPException, Request, Response, status
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import HTMLResponse, JSONResponse
from pydantic import BaseModel, Field
from sqlalchemy.orm import Session

from src.database import get_db
from src.api.cross_plane_claim_gate import cross_plane_claim_gate_metadata
from src.core.api_error_handlers import register_api_error_handlers
from src.core.graceful_shutdown import (ShutdownMiddleware, shutdown_manager)
from src.core.mtls_middleware import MTLSMiddleware
from src.core.rate_limit_middleware import RateLimitConfig, RateLimitMiddleware
from src.core.request_validation import (RequestValidationMiddleware,
                                          ValidationConfig)
from src.core.reliability_policy import set_degraded_dependencies_header
from src.core.logging_config import RequestIdContextVar, setup_logging
from src.core.settings import settings
from src.core.status_collector import get_current_status
from src.core.tracing_middleware import TracingMiddleware
from src.coordination.events import EventBus, get_event_bus
from src.mesh.metric_evidence_policy import latest_mesh_metric_policy_evidence
from src.version import __version__, get_health_info

# Initialize structured logging
log_level = os.getenv("LOG_LEVEL", "INFO")
logger = setup_logging(name="x0tta6bl4", log_level=log_level)
logger.info(f"✓ Structured logging initialized at level {log_level}")

is_light_mode = os.getenv("MAAS_LIGHT_MODE", "false").lower() == "true"

app = FastAPI(
    title="x0tta6bl4",
    version=f"{__version__}-light" if is_light_mode else __version__,
    description="Autonomous Mesh-as-a-Service Gateway",
    docs_url="/docs",
    redoc_url="/redoc",
    openapi_url="/openapi.json",
)

# --- Middlewares ---

@app.middleware("http")
async def propagate_request_id(request: Request, call_next):
    request_id = request.headers.get("X-Request-ID", secrets.token_hex(8))
    RequestIdContextVar.set(request_id)
    response = await call_next(request)
    response.headers["X-Request-ID"] = request_id
    return response

@app.middleware("http")
async def add_security_headers(request: Request, call_next):
    response = await call_next(request)
    set_degraded_dependencies_header(response, request)
    response.headers["X-Content-Type-Options"] = "nosniff"
    response.headers["X-Frame-Options"] = "SAMEORIGIN"
    response.headers["X-XSS-Protection"] = "1; mode=block"
    response.headers["Strict-Transport-Security"] = "max-age=31536000; includeSubDomains"
    response.headers["Content-Security-Policy"] = "default-src 'self'"
    return response

register_api_error_handlers(app)

# --- Routes Registration ---

def _include_maas_router(module_path: str, label: str) -> None:
    try:
        module = importlib.import_module(module_path)
        router = getattr(module, "router", None)
        if router:
            app.include_router(router)
            logger.info(f"✓ MaaS router registered: {label}")
    except Exception as exc:
        logger.warning(f"Could not import MaaS router {label}: {exc}")


def _include_filtered_maas_router(
    module_path: str,
    label: str,
    *,
    include_paths: set[str],
) -> None:
    try:
        module = importlib.import_module(module_path)
        source_router = getattr(module, "router", None)
        if not source_router:
            return
        filtered_router = APIRouter()
        for route in source_router.routes:
            if getattr(route, "path", "") in include_paths:
                filtered_router.routes.append(route)
        if filtered_router.routes:
            app.include_router(filtered_router)
            logger.info(f"✓ MaaS router registered: {label}")
    except Exception as exc:
        logger.warning(f"Could not import MaaS router {label}: {exc}")


# Legacy auth owns /api/v1/maas/auth/* and returns access_token.
_include_maas_router("src.api.maas_auth", "auth-legacy")

# Modular MaaS routers combined into a single entrypoint.
from src.api.maas.endpoints.combined import get_combined_router
app.include_router(
    get_combined_router(
        include_auth_namespace=False,
        include_mesh_namespace=False,
        mesh_root_excluded_paths={
            "/list",
            "/{mesh_id}/status",
            "/{mesh_id}/metrics",
            "/{mesh_id}/scale",
            "/{mesh_id}",
        },
        billing_excluded_paths={"/pay"},
        include_compat=False,
    )
)
logger.info("✓ Modular MaaS API routers registered")

_include_filtered_maas_router(
    "src.api.maas_compat",
    "compat",
    include_paths={
        "/api/v1/maas/compat/readiness",
        "/api/v3/maas/auth/register",
        "/api/v1/maas/mesh/deploy",
        "/api/v1/maas/list",
        "/api/v1/maas/{mesh_id}/status",
        "/api/v1/maas/{mesh_id}/metrics",
        "/api/v1/maas/{mesh_id}/scale",
        "/api/v1/maas/{mesh_id}",
        "/api/v1/maas/{mesh_id}/audit-logs",
        "/api/v1/maas/{mesh_id}/mapek/events",
        "/api/v1/maas/billing/pay",
    },
)

# Other specialized routers
_include_maas_router("src.api.maas_dashboard", "dashboard")
_include_maas_router("src.edge.api", "edge-computing")
_include_maas_router("src.event_sourcing.api", "event-sourcing")

# --- Basic Endpoints ---
_HEALTH_API_CROSS_PLANE_CLAIMS = (
    "production_readiness",
    "dataplane_delivery",
    "traffic_delivery",
    "customer_traffic",
    "settlement_finality",
    "dpi_bypass",
)
_HEALTH_API_CLAIM_BOUNDARY = (
    "Health API responses expose local process liveness, readiness probe, "
    "shutdown, and component-check observations only. HTTP 200, ok, ready, or "
    "healthy does not prove production readiness, customer traffic, dataplane "
    "delivery, external DPI bypass, settlement finality, or production SLOs."
)


def _health_api_claim_gate(surface: str):
    return {
        "schema": "x0tta6bl4.health_api_claim_gate.v1",
        "surface": surface,
        "local_liveness_observation_claim_allowed": True,
        "local_readiness_probe_observation_claim_allowed": True,
        "local_component_health_observation_claim_allowed": True,
        "production_readiness_claim_allowed": False,
        "production_slo_claim_allowed": False,
        "dataplane_delivery_claim_allowed": False,
        "traffic_delivery_claim_allowed": False,
        "customer_traffic_claim_allowed": False,
        "external_dpi_bypass_claim_allowed": False,
        "settlement_finality_claim_allowed": False,
        "claim_boundary": _HEALTH_API_CLAIM_BOUNDARY,
    }


def _health_api_response(payload: dict, *, surface: str):
    return {
        **payload,
        "health_api_claim_gate": _health_api_claim_gate(surface),
        "cross_plane_claim_gate": cross_plane_claim_gate_metadata(
            _HEALTH_API_CROSS_PLANE_CLAIMS,
            surface=surface,
        ),
    }


_METRICS_API_CLAIM_BOUNDARY = (
    "Prometheus metrics expose local scrape observations only. A successful "
    "scrape does not prove production readiness, production SLOs, dataplane "
    "delivery, customer traffic, external DPI bypass, or settlement finality."
)
_METRICS_API_CLAIM_HEADERS = {
    "X-X0TTA6BL4-Claim-Gate-Schema": "x0tta6bl4.metrics_api_claim_boundary_headers.v1",
    "X-X0TTA6BL4-Claim-Boundary": _METRICS_API_CLAIM_BOUNDARY,
    "X-X0TTA6BL4-Local-Metrics-Observation-Claim-Allowed": "true",
    "X-X0TTA6BL4-Production-Readiness-Claim-Allowed": "false",
    "X-X0TTA6BL4-Production-SLO-Claim-Allowed": "false",
    "X-X0TTA6BL4-Dataplane-Delivery-Claim-Allowed": "false",
    "X-X0TTA6BL4-Traffic-Delivery-Claim-Allowed": "false",
    "X-X0TTA6BL4-Customer-Traffic-Claim-Allowed": "false",
    "X-X0TTA6BL4-External-DPI-Bypass-Claim-Allowed": "false",
    "X-X0TTA6BL4-Settlement-Finality-Claim-Allowed": "false",
}


def _metrics_api_claim_boundary_headers():
    return dict(_METRICS_API_CLAIM_HEADERS)


_peers: dict[str, dict[str, Any]] = {}
_beacons: list[dict[str, Any]] = []
PQC_LIBOQS_AVAILABLE = False
_pqc_sig = None
_pqc_sig_public_key = None


class BeaconRequest(BaseModel):
    node_id: str = Field(..., min_length=1)
    timestamp: float
    neighbors: list[str] = Field(default_factory=list)


def _get_simulated_features(node_id: str) -> dict[str, float]:
    rng = random.Random(node_id)
    return {
        "rssi": rng.uniform(-80, -30),
        "snr": rng.uniform(5, 25),
        "loss_rate": rng.uniform(0, 0.25),
        "link_age": rng.uniform(0, 86400),
        "latency": rng.uniform(1, 100),
        "throughput": rng.uniform(0, 100),
        "cpu": rng.uniform(0, 1),
        "memory": rng.uniform(0, 1),
    }


def _generate_training_data(
    *,
    num_nodes: int = 10,
    num_edges: int = 20,
    seed: int | None = None,
) -> tuple[list[dict[str, float]], list[tuple[int, int]]]:
    rng = random.Random(seed)
    node_features = [_get_simulated_features(f"node-{seed}-{i}") for i in range(num_nodes)]
    possible_edges = [
        (src, dst)
        for src in range(num_nodes)
        for dst in range(num_nodes)
        if src != dst
    ]
    rng.shuffle(possible_edges)
    return node_features, possible_edges[: max(0, min(num_edges, len(possible_edges)))]


def pqc_verify(data: bytes, signature: bytes, public_key: bytes) -> bool:
    if not PQC_LIBOQS_AVAILABLE or _pqc_sig is None:
        logger.warning("PQC verification unavailable; failing closed")
        return False
    if _pqc_sig_public_key is not None and public_key != _pqc_sig_public_key:
        logger.warning("PQC verification public key mismatch")
        return False
    try:
        verified = bool(_pqc_sig.verify(data, signature, public_key))
        logger.info("PQC verification completed: verified=%s", verified)
        return verified
    except Exception as exc:
        logger.warning("PQC verification failed: %s", type(exc).__name__)
        return False


async def receive_beacon(request: BeaconRequest) -> dict[str, Any]:
    _peers[request.node_id] = {
        "last_seen": time.time(),
        "neighbors": list(request.neighbors or []),
    }
    _beacons.append(
        {
            "node_id": request.node_id,
            "timestamp": request.timestamp,
            "neighbors": list(request.neighbors or []),
        }
    )
    return {"accepted": True, "peers_count": len(_peers)}


async def get_mesh_status() -> dict[str, Any]:
    try:
        return get_current_status()
    except Exception:
        return {
            "status": "ok",
            "peers": list(_peers.keys()),
            "routes": [],
        }


async def get_mesh_peers() -> list[Any]:
    try:
        from src.network.yggdrasil_client import get_yggdrasil_peers

        result = get_yggdrasil_peers()
        if isinstance(result, dict):
            return result.get("peers", [])
        return result
    except Exception:
        return list(_peers.keys())


def get_mesh_routes() -> list[Any]:
    try:
        from src.network.yggdrasil_client import get_yggdrasil_routes

        result = get_yggdrasil_routes()
        if isinstance(result, dict):
            return result.get("routes", [])
        return result
    except Exception:
        return []


@app.get("/health")
async def health():
    return _health_api_response(
        {
            "status": "ok",
            **get_health_info(),
            "shutdown": shutdown_manager.get_status(),
        },
        surface="health_api.health",
    )


@app.get("/health/live")
async def health_live():
    """Kubernetes liveness probe - is the app running?"""
    from datetime import datetime
    return _health_api_response(
        {"status": "ok", "timestamp": datetime.utcnow().isoformat() + "Z"},
        surface="health_api.live",
    )


@app.get("/health/ready")
async def health_ready():
    """Kubernetes readiness probe - is the app ready to serve traffic?"""
    from datetime import datetime
    return _health_api_response(
        {"status": "ready", "timestamp": datetime.utcnow().isoformat() + "Z"},
        surface="health_api.ready",
    )


@app.get("/health/detailed")
async def health_detailed():
    """Detailed health status including all component checks."""
    from src.core.health_check import get_health_status
    result = await get_health_status()
    checks = [
        {"name": c.name, "status": c.status.value, "message": c.message}
        for c in result.checks
    ]
    payload = {
        "status": result.status.value,
        "version": result.version,
        "checks": checks,
    }
    status_code = 503 if result.status.value == "unhealthy" else 200
    return JSONResponse(
        content=_health_api_response(payload, surface="health_api.detailed"),
        status_code=status_code,
    )


@app.get("/metrics")
async def metrics():
    """Expose Prometheus-compatible metrics for scraping."""
    from src.monitoring.metrics import get_metrics

    metrics_payload = get_metrics()
    return Response(
        content=metrics_payload.body,
        media_type=metrics_payload.media_type,
        headers=_metrics_api_claim_boundary_headers(),
    )


# --- Mesh / Yggdrasil Status Endpoints ---
_MESH_API_CROSS_PLANE_CLAIMS = (
    "dataplane_delivery",
    "traffic_delivery",
    "customer_traffic",
    "dpi_bypass",
    "production_readiness",
)
_MESH_API_CLAIM_BOUNDARY = (
    "Mesh API responses expose local Yggdrasil observed-state and local control "
    "policy evidence only. They do not prove dataplane delivery, customer "
    "traffic, external DPI bypass, production SLOs, or production readiness."
)
_STATUS_API_CROSS_PLANE_CLAIMS = (
    "production_readiness",
    "dataplane_delivery",
    "traffic_delivery",
    "customer_traffic",
    "settlement_finality",
    "dpi_bypass",
)
_STATUS_API_CLAIM_BOUNDARY = (
    "Status API responses expose local process, system, resilience, mesh-health, "
    "and loop-state observations only. A healthy local status does not prove "
    "production readiness, live customer traffic, external DPI bypass, "
    "settlement finality, or production SLOs."
)


def _mesh_event_bus_from_request(request: Request) -> EventBus | None:
    state = getattr(request, "state", None)
    injected_bus = getattr(state, "event_bus", None)
    if injected_bus is not None:
        return injected_bus
    project_root = getattr(state, "event_project_root", ".")
    try:
        return get_event_bus(project_root)
    except Exception as exc:
        logger.error("Failed to initialize mesh API EventBus: %s", exc)
        return None


def _mesh_api_claim_gate(operation: str):
    return {
        "schema": "x0tta6bl4.mesh_api_claim_gate.v1",
        "surface": f"mesh_api.{operation}",
        "local_yggdrasil_observed_state_claim_allowed": True,
        "control_policy_observation_claim_allowed": True,
        "dataplane_delivery_claim_allowed": False,
        "traffic_delivery_claim_allowed": False,
        "customer_traffic_claim_allowed": False,
        "external_dpi_bypass_claim_allowed": False,
        "production_slo_claim_allowed": False,
        "production_readiness_claim_allowed": False,
        "claim_boundary": _MESH_API_CLAIM_BOUNDARY,
    }


def _status_api_claim_gate():
    return {
        "schema": "x0tta6bl4.status_api_claim_gate.v1",
        "surface": "status_api",
        "local_system_health_observation_claim_allowed": True,
        "local_mesh_health_observation_claim_allowed": True,
        "local_loop_state_observation_claim_allowed": True,
        "production_readiness_claim_allowed": False,
        "production_slo_claim_allowed": False,
        "dataplane_delivery_claim_allowed": False,
        "traffic_delivery_claim_allowed": False,
        "customer_traffic_claim_allowed": False,
        "external_dpi_bypass_claim_allowed": False,
        "settlement_finality_claim_allowed": False,
        "claim_boundary": _STATUS_API_CLAIM_BOUNDARY,
    }


def _status_api_response(status_data: dict):
    return {
        **status_data,
        "status_api_claim_gate": _status_api_claim_gate(),
        "cross_plane_claim_gate": cross_plane_claim_gate_metadata(
            _STATUS_API_CROSS_PLANE_CLAIMS,
            surface="status_api",
        ),
    }


def _call_yggdrasil_with_api_evidence(func, request: Request, *, operation: str):
    event_bus = _mesh_event_bus_from_request(request)
    kwargs = {
        "event_bus": event_bus,
        "include_evidence": True,
    }
    try:
        result = func(**kwargs)
    except TypeError as exc:
        message = str(exc)
        if "unexpected keyword" not in message and "positional argument" not in message:
            raise
        result = func()
    if isinstance(result, dict):
        return {
            **result,
            "control_policy_evidence": latest_mesh_metric_policy_evidence(event_bus),
            "mesh_api_claim_gate": _mesh_api_claim_gate(operation),
            "cross_plane_claim_gate": cross_plane_claim_gate_metadata(
                _MESH_API_CROSS_PLANE_CLAIMS,
                surface=f"mesh_api.{operation}",
            ),
        }
    return result


@app.get("/mesh/status")
async def mesh_status(request: Request):
    from src.network import yggdrasil_client as yc
    return _call_yggdrasil_with_api_evidence(
        yc.get_yggdrasil_status,
        request,
        operation="status",
    )


@app.get("/mesh/peers")
async def mesh_peers(request: Request):
    from src.network import yggdrasil_client as yc
    return _call_yggdrasil_with_api_evidence(
        yc.get_yggdrasil_peers,
        request,
        operation="peers",
    )


@app.get("/mesh/routes")
async def mesh_routes(request: Request):
    from src.network import yggdrasil_client as yc
    return _call_yggdrasil_with_api_evidence(
        yc.get_yggdrasil_routes,
        request,
        operation="routes",
    )


from src.core.cache import cached


@app.get("/status")
@cached(ttl=5, key_prefix="api_status")
async def status_endpoint():
    return JSONResponse(content=_status_api_response(get_current_status()))


@app.get("/")
async def root():
    return {
        "name": "x0tta6bl4",
        "version": __version__,
        "docs": "/docs",
        "endpoints": {
            "health": "/health",
            "status": "/status",
            "mesh/status": "/mesh/status",
            "mesh/peers": "/mesh/peers",
            "mesh/routes": "/mesh/routes",
        },
    }


@app.get("/index.html", response_class=HTMLResponse)
async def index_html():
    return "<!doctype html><title>x0tta6bl4</title><h1>x0tta6bl4</h1>"

if __name__ == "__main__":
    import uvicorn
    uvicorn.run(app, host="0.0.0.0", port=8000)
