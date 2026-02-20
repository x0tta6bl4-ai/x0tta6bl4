"""FastAPI app with mTLS and real system status monitoring - P0#3-P0#4 implementation"""

import importlib
import logging
import os
from pathlib import Path

from fastapi import FastAPI
from fastapi.responses import JSONResponse

from src.core.graceful_shutdown import (ShutdownMiddleware, create_lifespan,
                                        shutdown_manager)
from src.core.mtls_middleware import MTLSMiddleware
from src.core.production_lifespan import production_lifespan
from src.core.rate_limit_middleware import RateLimitConfig, RateLimitMiddleware
from src.core.request_validation import (RequestValidationMiddleware,
                                         ValidationConfig)
from src.core.settings import settings
from src.core.status_collector import get_current_status
from src.core.tracing_middleware import TracingMiddleware

# Preserve legacy module path for compatibility checks.
_LEGACY_FILE = Path(__file__).resolve().parents[2] / "libx0t" / "core" / "app.py"
if _LEGACY_FILE.exists():
    __file__ = str(_LEGACY_FILE)

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

app = FastAPI(
    title="x0tta6bl4",
    version="3.2.1",
    description="Self-healing mesh network node with MAPE-K autonomic loop and Kimi K2.5 Agent Swarm",
    lifespan=production_lifespan,
)

# --- Request models ---
from typing import List as TypingList
from typing import Optional

from pydantic import BaseModel

try:
    from src.core.app_minimal import BeaconRequest
except ImportError:

    class BeaconRequest(BaseModel):  # type: ignore[no-redef]
        node_id: str
        timestamp: float
        neighbors: Optional[TypingList[str]] = []


class VoteRequest(BaseModel):
    proposal_id: str
    voter_id: str
    tokens: int
    vote: bool


class HandshakeRequest(BaseModel):
    node_id: str
    algorithm: str


import time

# In-memory beacon / peer tracking (lightweight, no external state)
_peers: dict = {}
_beacons: list = []


async def receive_beacon(req: BeaconRequest):
    """Accept a mesh beacon and register the sending peer."""
    beacon = {
        "node_id": req.node_id,
        "timestamp": req.timestamp,
        "neighbors": req.neighbors,
        "received_at": time.time(),
    }
    _beacons.append(beacon)
    _peers[req.node_id] = {"last_seen": time.time(), "neighbors": req.neighbors}
    return {"accepted": True, "peers_count": len(_peers)}


async def get_mesh_status():
    """Return real mesh status from StatusCollector."""
    try:
        return get_current_status()
    except Exception as exc:
        logger.warning(f"get_mesh_status fallback: {exc}")
        return {"status": "ok", "peers": list(_peers.keys()), "routes": []}


async def get_mesh_peers():
    """Return mesh peers from Yggdrasil or local tracking."""
    try:
        from src.network.yggdrasil_client import get_yggdrasil_peers

        data = get_yggdrasil_peers()
        return data.get("peers", [])
    except Exception:
        return list(_peers.keys())


def get_mesh_routes(*args, **kwargs):
    """Return mesh routes from Yggdrasil or empty list."""
    try:
        from src.network.yggdrasil_client import get_yggdrasil_routes

        return get_yggdrasil_routes()
    except Exception:
        return []


# --- Prometheus metrics (real MetricsRegistry) ---
try:
    from src.monitoring.metrics import MetricsRegistry

    metrics = MetricsRegistry
except ImportError:

    class _StubMetrics:
        def __getattr__(self, name):
            return lambda *a, **kw: None

    metrics = _StubMetrics()  # type: ignore[assignment]

# Import and register API routers
try:
    from src.api.vpn import router as vpn_router

    app.include_router(vpn_router)
    logger.info("✓ VPN router registered")
except Exception as e:
    logger.warning(f"Could not import VPN router: {e}")

from src.api.billing import router as billing_router
from src.api.ledger_endpoints import router as ledger_router
from src.api.swarm import router as swarm_router
# Critical API routers must load successfully. Fail-fast if missing.
from src.api.users import router as users_router

app.include_router(users_router)
logger.info("✓ Users router registered")
app.include_router(billing_router)
logger.info("✓ Billing router registered")
app.include_router(swarm_router)
logger.info("✓ Swarm router registered (Kimi K2.5 integration)")
app.include_router(ledger_router)
logger.info("✓ Ledger router registered")

# v3.4 MaaS API
def _include_maas_router(module_path: str, label: str) -> None:
    """Register a MaaS router without blocking the whole MaaS API on one import error."""
    try:
        module = importlib.import_module(module_path)
        router = getattr(module, "router", None)
        if router is None:
            logger.warning("Could not register MaaS router %s: missing `router`", label)
            return
        app.include_router(router)
        logger.info("✓ MaaS router registered: %s", label)
    except Exception as exc:
        logger.warning("Could not import MaaS router %s (%s): %s", label, module_path, exc)


# maas_legacy provides the full MaaS API surface (register/login/deploy/status/nodes/etc.)
# maas_core is disabled to avoid route conflicts with legacy (both expose /deploy, /list, /{id})
_include_maas_router("src.api.maas_legacy", "legacy")
_include_maas_router("src.api.maas_auth", "auth")
_include_maas_router("src.api.maas_playbooks", "playbooks")
_include_maas_router("src.api.maas_supply_chain", "supply-chain")
_include_maas_router("src.api.maas_marketplace", "marketplace")
_include_maas_router("src.api.maas_governance", "governance")
_include_maas_router("src.api.maas_analytics", "analytics")
_include_maas_router("src.api.maas_billing", "billing")
_include_maas_router("src.api.maas_nodes", "nodes")
_include_maas_router("src.api.maas_policies", "policies")
_include_maas_router("src.api.maas_telemetry", "telemetry")
_include_maas_router("src.api.maas_dashboard", "dashboard")

# Add mTLS middleware (security profile + env override)
security_flags = settings.security_profile()
testing_mode = (
    settings.is_testing()
    or os.getenv("TESTING", "false").lower() == "true"
    or bool(os.getenv("PYTEST_CURRENT_TEST"))
)
mtls_enabled = security_flags["mtls_enabled"] and not testing_mode
if mtls_enabled:
    app.add_middleware(
        MTLSMiddleware,
        require_mtls=True,
        enforce_tls_13=True,
        allowed_spiffe_domains=["x0tta6bl4.mesh"],
        excluded_paths=["/health", "/metrics", "/docs", "/openapi.json"],
    )
    logger.info("✓ mTLS middleware enabled (TLS 1.3 required)")
else:
    logger.info("⚠️  mTLS middleware disabled (dev mode)")

# Add global rate limiting (DDoS protection)
if security_flags["rate_limit_enabled"] and not testing_mode:
    rate_config = RateLimitConfig(
        requests_per_second=int(os.getenv("RATE_LIMIT_RPS", "100")),
        burst_size=int(os.getenv("RATE_LIMIT_BURST", "50")),
        block_duration=int(os.getenv("RATE_LIMIT_BLOCK_DURATION", "60")),
    )
    app.add_middleware(
        RateLimitMiddleware,
        config=rate_config,
        excluded_paths=["/health", "/metrics", "/docs", "/openapi.json"],
    )
    logger.info(
        f"✓ Global rate limiting enabled: {rate_config.requests_per_second} RPS"
    )
    # logger.info("⚠️  Global rate limiting TEMPORARILY DISABLED for Load Test")
else:
    logger.info(
        "⚠️  Global rate limiting disabled (TESTING mode or RATE_LIMIT_ENABLED is false)"
    )

# Add distributed tracing
tracing_enabled = (
    os.getenv("TRACING_ENABLED", "true").lower() == "true" and not testing_mode
)
if tracing_enabled:
    app.add_middleware(
        TracingMiddleware,
        service_name="x0tta6bl4",
        excluded_paths=["/health", "/metrics", "/docs", "/openapi.json"],
    )
    logger.info("✓ Distributed tracing enabled")
else:
    logger.info("⚠️  Distributed tracing disabled")

# Add request validation middleware
validation_enabled = security_flags["request_validation_enabled"] and not testing_mode
if validation_enabled:
    validation_config = ValidationConfig(
        max_content_length=int(os.getenv("MAX_CONTENT_LENGTH", str(10 * 1024 * 1024))),
        max_url_length=int(os.getenv("MAX_URL_LENGTH", "2048")),
        block_suspicious_patterns=True,
        excluded_paths=["/health", "/metrics", "/docs", "/openapi.json"],
    )
    app.add_middleware(RequestValidationMiddleware, config=validation_config)
    logger.info("✓ Request validation enabled (injection protection active)")
else:
    logger.info("⚠️  Request validation disabled")

# Add graceful shutdown middleware
shutdown_enabled = os.getenv("GRACEFUL_SHUTDOWN_ENABLED", "true").lower() == "true"
if shutdown_enabled:
    app.add_middleware(ShutdownMiddleware, shutdown_manager=shutdown_manager)
    logger.info("✓ Graceful shutdown middleware enabled")
else:
    logger.info("⚠️  Graceful shutdown middleware disabled")

# Add Metering Middleware for MaaS
try:
    from src.api.middleware.metering import MeteringMiddleware
    app.add_middleware(MeteringMiddleware)
    logger.info("✓ Metering middleware enabled")
except ImportError:
    logger.warning("⚠️ Metering middleware not available")

# Add Audit Middleware for MaaS
try:
    from src.api.middleware.audit import AuditMiddleware
    app.add_middleware(AuditMiddleware)
    logger.info("✓ Audit middleware enabled")
except ImportError:
    logger.warning("⚠️ Audit middleware not available")


# Security headers via decorator
@app.middleware("http")
async def add_security_headers(request, call_next):
    response = await call_next(request)
    response.headers["Content-Security-Policy"] = "default-src 'self'"
    response.headers["X-Content-Type-Options"] = "nosniff"
    response.headers["X-Frame-Options"] = "SAMEORIGIN"
    response.headers["X-XSS-Protection"] = "1; mode=block"
    response.headers["Strict-Transport-Security"] = (
        "max-age=31536000; includeSubDomains"
    )
    return response


# --- PQC Integration (liboqs-python, API >=0.14) ---
try:
    from oqs import Signature

    PQC_LIBOQS_AVAILABLE = True
    logger.info("✅ liboqs available - PQC signatures enabled")
except ImportError:
    PQC_LIBOQS_AVAILABLE = False
    logger.warning("⚠️ liboqs not available - PQC signatures disabled")

_pqc_sig_public_key = None
_pqc_sig = None
if PQC_LIBOQS_AVAILABLE:
    try:
        try:
            _pqc_sig = Signature("ML-DSA-65")
            _pqc_sig_public_key = _pqc_sig.generate_keypair()
            logger.info("✅ PQC signature keypair generated (ML-DSA-65, NIST FIPS 204)")
        except Exception:
            _pqc_sig = Signature("Dilithium3")
            _pqc_sig_public_key = _pqc_sig.generate_keypair()
            logger.info("✅ PQC signature keypair generated (Dilithium3, legacy)")
    except Exception as e:
        logger.error(f"Failed to generate PQC keys: {e}")
        PQC_LIBOQS_AVAILABLE = False


def pqc_sign(data: bytes) -> bytes:
    if not PQC_LIBOQS_AVAILABLE or _pqc_sig is None:
        return b""
    try:
        return _pqc_sig.sign(data)
    except Exception as e:
        logger.error(f"Failed to sign data with PQC: {e}")
        return b""


def pqc_verify(data: bytes, signature: bytes, public_key: bytes) -> bool:
    if not PQC_LIBOQS_AVAILABLE:
        # Security-first default: deny verification when PQC is unavailable.
        # Dev-only override can be enabled explicitly for local bring-up.
        allow_insecure = (
            os.getenv("X0TTA6BL4_ALLOW_INSECURE_PQC_VERIFY", "false").lower() == "true"
        )
        if allow_insecure:
            logger.warning(
                "PQC not available, insecure verify override enabled: returning True"
            )
            return True
        logger.error("PQC not available, verification denied (fail-closed)")
        return False
    if not signature or not public_key:
        logger.error("PQC verify failed: empty signature or public key")
        return False
    try:
        logger.info(
            "[PQC_VERIFY] verification started data_len=%d signature_len=%d key_len=%d",
            len(data),
            len(signature),
            len(public_key),
        )
        if _pqc_sig is not None and _pqc_sig_public_key == public_key:
            result = _pqc_sig.verify(data, signature, public_key)
            logger.info("[PQC_VERIFY] verification completed result=%s", result)
            return result
        try:
            verifier = Signature("ML-DSA-65")
        except Exception:
            verifier = Signature("Dilithium3")
        verifier.set_public_key(public_key)
        result = verifier.verify(data, signature)
        logger.info("[PQC_VERIFY] verification completed result=%s", result)
        return result
    except Exception as e:
        logger.error("Failed to verify PQC signature: %s", e)
        return False


@app.get("/pqc/status")
async def pqc_status():
    """Show PQC (liboqs) status and public key (hex)."""
    return {
        "liboqs_available": PQC_LIBOQS_AVAILABLE,
        "public_key": _pqc_sig_public_key.hex() if _pqc_sig_public_key else None,
        "algorithm": "ML-DSA-65" if PQC_LIBOQS_AVAILABLE else None,
    }


logger.info("✓ App created")


# --- Prometheus /metrics endpoint ---
@app.get("/metrics")
async def prometheus_metrics():
    """Expose Prometheus metrics for scraping."""
    from fastapi.responses import Response

    try:
        import prometheus_client

        from src.monitoring.metrics import _metrics_registry

        data = prometheus_client.generate_latest(_metrics_registry)
        return Response(content=data, media_type=prometheus_client.CONTENT_TYPE_LATEST)
    except Exception:
        # Fallback: default registry
        import prometheus_client

        data = prometheus_client.generate_latest()
        return Response(content=data, media_type=prometheus_client.CONTENT_TYPE_LATEST)


@app.get("/health")
async def health():
    """Simple health check endpoint - returns 200 if alive"""
    return {"status": "ok", "version": "3.2.0"}


@app.get("/health/live")
async def health_live():
    """Kubernetes liveness probe - is the app running?"""
    from src.core.health_check import get_liveness

    return await get_liveness()


@app.get("/health/ready")
async def health_ready():
    """Kubernetes readiness probe - is the app ready to serve traffic?"""
    from src.core.health_check import get_readiness

    result = await get_readiness()
    if result["status"] == "not_ready":
        from fastapi.responses import JSONResponse

        return JSONResponse(status_code=503, content=result)
    return result


@app.get("/health/detailed")
async def health_detailed():
    """Detailed health check with all dependency statuses."""
    from fastapi.responses import JSONResponse

    from src.core.health_check import HealthStatus, get_health_status

    result = await get_health_status()
    status_code = 200 if result.status != HealthStatus.UNHEALTHY else 503
    return JSONResponse(status_code=status_code, content=result.to_dict())


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
            content={"status": "healthy", "version": "3.2.0", "error": str(e)},
        )


@app.get("/")
async def root():
    """API root with documentation links"""
    return {
        "name": "x0tta6bl4",
        "version": "3.2.0",
        "docs": "/docs",
        "endpoints": {
            "health": "/health",
            "status": "/status",
            "mesh/status": "/mesh/status",
            "mesh/peers": "/mesh/peers",
            "mesh/routes": "/mesh/routes",
            "swarm": "/api/v3/swarm",
            "swarm/health": "/api/v3/swarm/health",
        },
        "features": {
            "kimi_k2.5_swarm": True,
            "parl_parallel_execution": True,
            "max_agents": 100,
            "max_parallel_steps": 1500,
        },
    }


import math
import random


# Mesh network endpoints
# --- Simulated feature generator for tests ---
def _get_simulated_features(node_id: str) -> dict:
    """
    Generate reproducible simulated node features for testing.
    Output dict includes: rssi, snr, loss_rate, link_age, latency, throughput, cpu, memory.
    Value ranges:
        rssi: -80..-30, snr: 5..25, loss_rate: >=0, link_age: 0..86400, latency: 1..100, throughput: 0..100, cpu: 0..1, memory: 0..1
    Reproducible for same node_id.
    """
    rnd = random.Random()
    rnd.seed(str(node_id))
    rssi = rnd.uniform(-80, -30)
    snr = rnd.uniform(5, 25)
    loss_rate = abs(rnd.gauss(0.01, 0.02))  # >=0
    link_age = rnd.uniform(0, 86400)  # seconds (0..24h)
    latency = rnd.uniform(1, 100)
    throughput = rnd.uniform(0, 100)
    cpu = rnd.uniform(0, 1)
    memory = rnd.uniform(0, 1)
    return {
        "rssi": rssi,
        "snr": snr,
        "loss_rate": loss_rate,
        "link_age": link_age,
        "latency": latency,
        "throughput": throughput,
        "cpu": cpu,
        "memory": memory,
    }


# --- Simulated training data generator for tests ---
def _generate_training_data(num_nodes=10, num_edges=15, seed=42):
    """
    Generate simulated training data for anomaly detection models.
    Returns (node_features, edge_index):
        node_features: list of dicts (one per node, see _get_simulated_features)
        edge_index: list of (src, dst) tuples (undirected, no self-loops, no duplicates)
    """
    import random

    rnd = random.Random(seed)
    node_ids = [f"node-{i}" for i in range(num_nodes)]
    node_features = [_get_simulated_features(nid) for nid in node_ids]
    # Generate random edges (undirected, no self-loops, no duplicates)
    possible_edges = [(i, j) for i in range(num_nodes) for j in range(i + 1, num_nodes)]
    rnd.shuffle(possible_edges)
    edge_index = possible_edges[: min(num_edges, len(possible_edges))]
    return node_features, edge_index


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


def predict_anomaly(metrics: dict = None, node_id: str = None, **kwargs):
    """Predict anomalies using ML anomaly detector."""
    try:
        from src.ml.anomaly import AnomalyDetector

        detector = AnomalyDetector()
        return detector.predict(metrics or {}, node_id=node_id)
    except (ImportError, Exception) as e:
        logger.debug(f"Anomaly prediction unavailable: {e}")
        return None


def cast_vote(proposal_id: str = None, voter_id: str = None, vote: bool = True, **kwargs):
    """Cast a DAO governance vote."""
    try:
        from src.dao.governance import GovernanceEngine

        engine = GovernanceEngine()
        return engine.cast_vote(proposal_id, voter_id, vote)
    except (ImportError, Exception) as e:
        logger.debug(f"Governance voting unavailable: {e}")
        return None


def handshake(peer_id: str = None, public_key: bytes = None, **kwargs):
    """Perform PQC key exchange handshake with peer."""
    try:
        from src.security.post_quantum import LibOQSBackend

        backend = LibOQSBackend()
        if public_key:
            return backend.kem_encapsulate(public_key)
        return backend.generate_kem_keypair()
    except (ImportError, Exception) as e:
        logger.debug(f"PQC handshake unavailable: {e}")
        return None


def train_model_background(node_data=None, edge_data=None):
    """Train anomaly detection model in background."""
    try:
        from src.ml.anomaly import AnomalyDetector

        detector = AnomalyDetector()
        if node_data and edge_data:
            detector.train(node_data, edge_data)
            return {"status": "trained", "nodes": len(node_data), "edges": len(edge_data)}
        return {"status": "no_data"}
    except Exception as e:
        logger.error(f"Background training error: {e}")
        return {"status": "error", "message": str(e)}


if __name__ == "__main__":
    import uvicorn

    from src.core.settings import settings

    logger.info(f"Starting server on {settings.api_host}:{settings.api_port}...")
    uvicorn.run(app, host=settings.api_host, port=settings.api_port)
