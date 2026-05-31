"""FastAPI app with mTLS and real system status monitoring - P0#3-P0#4 implementation"""

import importlib
import os
import sys
import uuid
from pathlib import Path

from fastapi import FastAPI, HTTPException, Request
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse, Response

# Internal imports
from src.core.api_error_handlers import register_api_error_handlers
from src.core.cors_config import resolve_cors_allowed_origins
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
from src.version import __version__, get_health_info
from src.api.cross_plane_claim_gate import cross_plane_claim_gate_metadata
from src.coordination.events import EventBus, get_event_bus
from src.mesh.metric_evidence_policy import latest_mesh_metric_policy_evidence

# Initialize structured logging
log_level = os.getenv("LOG_LEVEL", "INFO")
logger = setup_logging(name="x0tta6bl4", log_level=log_level)
logger.info(f"✓ Structured logging initialized at level {log_level}")

# Preserve legacy module path for compatibility checks.
_LEGACY_FILE = Path(__file__).resolve().parents[2] / "libx0t" / "core" / "app.py"
if _LEGACY_FILE.exists():
    __file__ = str(_LEGACY_FILE)

# Choose lifespan based on mode
is_light_mode = os.getenv("MAAS_LIGHT_MODE", "false").lower() == "true"

if is_light_mode:
    logger.info("🚀 Starting in LIGHT MODE (Intelligence Engine disabled)")
    app = FastAPI(
        title="x0tta6bl4 MaaS",
        description="Autonomous Mesh Intelligence Gateway (Light)",
        version=f"{__version__}-light",
    )
else:
    # Production lifespan includes MAPE-K, ML engines, and background tasks
    from src.core.production_lifespan import production_lifespan

    app = FastAPI(
        title="x0tta6bl4 MaaS",
        description="Autonomous Mesh Intelligence Gateway (Production-Ready)",
        version=__version__,
        lifespan=production_lifespan,
    )

# --- Middlewares (Order matters: CORS -> RateLimit -> Tracing -> Others) ---

# 1. CORS (P1 Security)
allowed_origins = resolve_cors_allowed_origins()

app.add_middleware(
    CORSMiddleware,
    allow_origins=allowed_origins,
    allow_credentials=True,
    # Security: explicit allowlists required when allow_credentials=True.
    # Wildcard allow_methods/allow_headers + credentials enables CSRF via
    # cross-origin authenticated requests with arbitrary headers.
    allow_methods=["GET", "POST", "PUT", "PATCH", "DELETE", "OPTIONS"],
    allow_headers=["Authorization", "Content-Type", "X-API-Key", "X-Request-ID"],
)

# 2. mTLS middleware
security_flags = settings.security_profile()
testing_mode = (
    settings.is_testing()
    or os.getenv("TESTING", "false").lower() == "true"
    or bool(os.getenv("PYTEST_CURRENT_TEST"))
    or "pytest" in sys.modules
)

if security_flags["mtls_enabled"] and not testing_mode:
    app.add_middleware(
        MTLSMiddleware,
        require_mtls=True,
        enforce_tls_13=True,
        allowed_spiffe_domains=["x0tta6bl4.mesh"],
        excluded_paths=["/health", "/metrics", "/docs", "/openapi.json"],
    )
    logger.info("✓ mTLS middleware enabled (TLS 1.3 required)")

# 3. Global rate limiting
if security_flags["rate_limit_enabled"] and not testing_mode:
    rate_config = RateLimitConfig(
        requests_per_second=int(os.getenv("RATE_LIMIT_RPS", "100")),
        burst_size=int(os.getenv("RATE_LIMIT_BURST", "50")),
        block_duration=int(os.getenv("RATE_LIMIT_BLOCK_DURATION", "60")),
        path_overrides={
            # Expensive marketplace payment/state-transition flows
            "/api/v1/maas/marketplace/rent": RateLimitConfig(
                requests_per_second=0.5, burst_size=1, block_duration=120
            ),
            "/api/v1/maas/marketplace/escrow": RateLimitConfig(
                requests_per_second=0.2, burst_size=1, block_duration=180
            ),
            # Billing and webhook endpoints are high-value abuse targets
            "/api/v1/maas/billing/subscriptions/checkout": RateLimitConfig(
                requests_per_second=0.2, burst_size=2, block_duration=180
            ),
            "/api/v1/maas/billing/webhook/stripe": RateLimitConfig(
                requests_per_second=1.0, burst_size=5, block_duration=60
            ),
            "/api/v1/billing/checkout-session": RateLimitConfig(
                requests_per_second=0.5, burst_size=2, block_duration=120
            ),
            "/api/v1/billing/webhook": RateLimitConfig(
                requests_per_second=1.0, burst_size=5, block_duration=60
            ),
            # Vision endpoints are CPU-heavy and should be throttled aggressively
            "/api/v1/vision/analyze/topology": RateLimitConfig(
                requests_per_second=0.1, burst_size=1, block_duration=120
            ),
            "/api/v1/vision/debug": RateLimitConfig(
                requests_per_second=0.1, burst_size=1, block_duration=120
            ),
            "/api/v1/maas/vpn/config": RateLimitConfig(
                requests_per_second=0.2, burst_size=1, block_duration=300
            ),
        },
    )
    app.add_middleware(
        RateLimitMiddleware,
        config=rate_config,
        excluded_paths=["/health", "/metrics", "/docs", "/openapi.json"],
    )
    logger.info(f"✓ Global rate limiting enabled: {rate_config.requests_per_second} RPS")

# 4. Distributed tracing
if os.getenv("TRACING_ENABLED", "true").lower() == "true" and not testing_mode:
    app.add_middleware(
        TracingMiddleware,
        service_name="x0tta6bl4",
        excluded_paths=["/health", "/metrics", "/docs", "/openapi.json"],
    )
    logger.info("✓ Distributed tracing enabled")

# 5. Request validation
if security_flags["request_validation_enabled"] and not testing_mode:
    validation_config = ValidationConfig(
        max_content_length=int(os.getenv("MAX_CONTENT_LENGTH", str(10 * 1024 * 1024))),
        max_url_length=int(os.getenv("MAX_URL_LENGTH", "2048")),
        block_suspicious_patterns=True,
        excluded_paths=["/health", "/metrics", "/docs", "/openapi.json"],
    )
    app.add_middleware(RequestValidationMiddleware, config=validation_config)
    logger.info("✓ Request validation enabled")

# 6. Graceful shutdown
if os.getenv("GRACEFUL_SHUTDOWN_ENABLED", "true").lower() == "true":
    app.add_middleware(ShutdownMiddleware, shutdown_manager=shutdown_manager)

# 7. Metering & Audit
try:
    from src.monitoring.metrics import MetricsMiddleware
    app.add_middleware(MetricsMiddleware)
except ImportError:
    pass

try:
    from src.api.middleware.metering import MeteringMiddleware
    app.add_middleware(MeteringMiddleware)
except ImportError:
    pass

try:
    from src.api.middleware.audit import AuditMiddleware
    app.add_middleware(AuditMiddleware)
except ImportError:
    pass

# 8. Security Headers (P1 Security)
@app.middleware("http")
async def propagate_request_id(request, call_next):
    """Ensure request/correlation ID exists even when tracing middleware is disabled."""
    request_id = (
        request.headers.get("X-Request-ID")
        or request.headers.get("X-Correlation-ID")
        or str(uuid.uuid4())
    )
    RequestIdContextVar.set(request_id)
    existing_trace_id = getattr(request.state, "trace_id", None)
    request.state.trace_id = existing_trace_id or request_id

    try:
        response = await call_next(request)
    finally:
        RequestIdContextVar.clear()

    response.headers.setdefault("X-Request-ID", request_id)
    response.headers.setdefault("X-Correlation-ID", request_id)
    return response


@app.middleware("http")
async def add_security_headers(request, call_next):
    response = await call_next(request)
    set_degraded_dependencies_header(response, request)
    response.headers["Content-Security-Policy"] = (
        "default-src 'self'; script-src 'self' 'unsafe-inline'; style-src 'self' 'unsafe-inline'; "
        "img-src 'self' data:; frame-ancestors 'none'; base-uri 'self';"
    )
    response.headers["X-Content-Type-Options"] = "nosniff"
    response.headers["X-Frame-Options"] = "DENY"
    response.headers["X-XSS-Protection"] = "1; mode=block"
    response.headers["Strict-Transport-Security"] = "max-age=31536000; includeSubDomains; preload"
    response.headers["Referrer-Policy"] = "strict-origin-when-cross-origin"
    response.headers["Permissions-Policy"] = "camera=(), microphone=(), geolocation=()"
    response.headers["Server"] = "x0tta6bl4-gateway"
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

# Modular MaaS routers combined into a single entrypoint.
# This replaces the individual legacy registrations.
from src.api.maas.endpoints.combined import get_combined_router
app.include_router(get_combined_router())
logger.info("✓ Modular MaaS API routers registered")

# Other specialized routers
_include_maas_router("src.api.billing", "billing-api")
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
    from fastapi.responses import JSONResponse
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
    return {"name": "x0tta6bl4", "version": __version__, "docs": "/docs"}

# --- Static UI Routes ---
def _serve_static_asset(path: str, media_type: str) -> Response:
    try:
        content = Path(path).read_bytes()
        return Response(content=content, media_type=media_type)
    except Exception:
        raise HTTPException(status_code=404)

@app.get("/login.html", include_in_schema=False)
async def serve_login(): return _serve_static_asset("/mnt/projects/login.html", "text/html")

@app.get("/dashboard.html", include_in_schema=False)
async def serve_dashboard(): return _serve_static_asset("/mnt/projects/dashboard.html", "text/html")

if __name__ == "__main__":
    import uvicorn
    uvicorn.run(app, host=settings.api_host, port=settings.api_port)
