"""FastAPI app with mTLS and real system status monitoring - P0#3-P0#4 implementation"""

import importlib
import os
import sys
import uuid
from pathlib import Path

from fastapi import FastAPI, HTTPException
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
        version=__version__,
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

_include_maas_router("src.api.maas_legacy", "legacy")
_include_maas_router("src.api.maas_compat", "compat")
_include_maas_router("src.api.maas_auth", "auth")
_include_maas_router("src.api.maas_playbooks", "playbooks")
_include_maas_router("src.api.maas_supply_chain", "supply-chain")
_include_maas_router("src.api.maas_marketplace", "marketplace")
_include_maas_router("src.api.maas_governance", "governance")
_include_maas_router("src.api.maas_analytics", "analytics")
_include_maas_router("src.api.maas_billing", "billing")
_include_maas_router("src.api.billing", "billing-api")
_include_maas_router("src.api.maas_agent_mesh", "agent-mesh")

if not is_light_mode:
    _include_maas_router("src.api.maas_nodes", "nodes")
    _include_maas_router("src.api.maas_policies", "policies")
    _include_maas_router("src.api.maas_telemetry", "telemetry")
    _include_maas_router("src.api.vpn", "vpn")
    _include_maas_router("src.api.users", "users")
    _include_maas_router("src.api.swarm", "swarm")
    _include_maas_router("src.api.ledger_endpoints", "ledger")
    _include_maas_router("src.api.swarm_endpoints", "swarm-orchestration")
    _include_maas_router("src.api.vision_endpoints", "vision-analytics")

_include_maas_router("src.api.maas_dashboard", "dashboard")
_include_maas_router("src.edge.api", "edge-computing")
_include_maas_router("src.event_sourcing.api", "event-sourcing")

# --- Basic Endpoints ---

@app.get("/health")
async def health():
    return {
        "status": "ok",
        **get_health_info(),
        "shutdown": shutdown_manager.get_status(),
    }


@app.get("/health/live")
async def health_live():
    """Kubernetes liveness probe - is the app running?"""
    from datetime import datetime
    return {"status": "ok", "timestamp": datetime.utcnow().isoformat() + "Z"}


@app.get("/health/ready")
async def health_ready():
    """Kubernetes readiness probe - is the app ready to serve traffic?"""
    from datetime import datetime
    return {"status": "ready", "timestamp": datetime.utcnow().isoformat() + "Z"}


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
    return JSONResponse(content=payload, status_code=status_code)


@app.get("/metrics")
async def metrics():
    """Expose Prometheus-compatible metrics for scraping."""
    from src.monitoring.metrics import get_metrics

    metrics_payload = get_metrics()
    return Response(
        content=metrics_payload.body,
        media_type=metrics_payload.media_type,
    )


# --- Mesh / Yggdrasil Status Endpoints ---
@app.get("/mesh/status")
async def mesh_status():
    from src.network import yggdrasil_client as yc
    return yc.get_yggdrasil_status()


@app.get("/mesh/peers")
async def mesh_peers():
    from src.network import yggdrasil_client as yc
    return yc.get_yggdrasil_peers()


@app.get("/mesh/routes")
async def mesh_routes():
    from src.network import yggdrasil_client as yc
    return yc.get_yggdrasil_routes()

from src.core.cache import cached

@app.get("/status")
@cached(ttl=5, key_prefix="api_status")
async def status_endpoint():
    return JSONResponse(content=get_current_status())

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
