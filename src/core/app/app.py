"""
x0tta6bl4 gateway application entrypoint.
"""

import importlib
import os
import random
import secrets
import time
from collections.abc import Sequence
from datetime import UTC, datetime
from pathlib import Path
from typing import Any

from fastapi import FastAPI, Query, Request, Response
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import HTMLResponse, JSONResponse
from pydantic import BaseModel, Field

from src.coordination.events import Event, EventBus, get_event_bus
from src.core.app.api_error_handlers import register_api_error_handlers
from src.core.app.graceful_shutdown import shutdown_manager
from src.core.health.status_collector import get_current_status
from src.core.logging.logging_config import RequestIdContextVar, setup_logging
from src.core.resilience.reliability_policy import set_degraded_dependencies_header
from src.mesh.metric_evidence_policy import latest_mesh_metric_policy_evidence
from src.version import __version__, get_health_info

# Initialize structured logging
log_level = os.getenv("LOG_LEVEL", "INFO")
logger = setup_logging(name="x0tta6bl4", log_level=log_level)
logger.info(f"✓ Structured logging initialized at level {log_level}")

_LIGHT_MODE = os.getenv("MAAS_LIGHT_MODE", "false").lower() == "true"
_APP_VERSION = f"{__version__}-light" if _LIGHT_MODE else __version__
STARTED_AT = time.time()

from src.core.app.production_lifespan import production_lifespan

app = FastAPI(
    title="x0tta6bl4",
    version=_APP_VERSION,
    description="Autonomous Mesh-as-a-Service Gateway",
    docs_url="/docs",
    redoc_url="/redoc",
    openapi_url="/openapi.json",
    lifespan=production_lifespan,
)

_DEFAULT_APP_CORS_ORIGINS = (
    "http://127.0.0.1:5173",
    "http://localhost:5173",
    "http://127.0.0.1:8081",
    "http://localhost:8081",
    "https://localhost",
    "capacitor://localhost",
    "ionic://localhost",
    "tauri://localhost",
    "https://tauri.localhost",
)


def _app_cors_origins() -> list[str]:
    raw = os.getenv("X0TTA6BL4_APP_CORS_ORIGINS", "")
    configured = [item.strip() for item in raw.split(",") if item.strip()]
    return configured or list(_DEFAULT_APP_CORS_ORIGINS)


app.add_middleware(
    CORSMiddleware,
    allow_origins=_app_cors_origins(),
    allow_credentials=True,
    allow_methods=["GET", "POST", "PUT", "DELETE", "OPTIONS"],
    allow_headers=["Authorization", "Content-Type", "X-Request-ID"],
)

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

def _include_maas_router(module_path: str, label: str) -> None:
    try:
        module = importlib.import_module(module_path)
        router = getattr(module, "router", None)
        if router:
            app.include_router(router)
            logger.info(f"✓ MaaS router registered: {label}")
    except Exception as exc:
        logger.warning(f"Could not import MaaS router {label}: {exc}")

# Fixed-prefix MaaS routers must be registered before the legacy catch-all
# routes such as /api/v1/maas/{mesh_id}/status.
# src.api.maas_billing is DEPRECATED — routes shadowed by src.api.billing
# Kept commented to avoid duplicate OpenAPI operation IDs.
# _include_maas_router("src.api.maas_billing", "billing")
_include_maas_router("src.api.billing", "billing-api")
_include_maas_router("src.api.maas_legacy", "legacy")
_include_maas_router("src.api.maas_compat", "compat")
_include_maas_router("src.api.maas_auth", "auth")
_include_maas_router("src.api.maas_playbooks", "playbooks")
_include_maas_router("src.api.maas_supply_chain", "supply-chain")
_include_maas_router("src.api.maas_marketplace", "marketplace")
_include_maas_router("src.api.maas_governance", "governance")
_include_maas_router("src.api.maas_analytics", "analytics")
_include_maas_router("src.api.maas_agent_mesh", "agent-mesh")
_include_maas_router("src.api.service_identity_status", "service-identity-status")

if not _LIGHT_MODE:
    _include_maas_router("src.api.maas_nodes", "nodes")
    _include_maas_router("src.api.maas_policies", "policies")
    _include_maas_router("src.api.maas_telemetry", "telemetry")
    _include_maas_router("src.api.vpn", "vpn")
    _include_maas_router("src.api.users", "users")
    _include_maas_router("src.api.swarm", "swarm")
    _include_maas_router("src.api.ledger_endpoints", "ledger")
    _include_maas_router("src.api.swarm_endpoints", "swarm-orchestration")
    _include_maas_router("src.api.vision_endpoints", "vision-analytics")

# legacy/v1 routers (not yet fully modularized or needed for specialized v1 paths)
_include_maas_router("src.api.billing", "billing-v1")
_include_maas_router("src.api.maas_dashboard", "dashboard")
_include_maas_router("src.edge.api", "edge-computing")
_include_maas_router("src.event_sourcing.api", "event-sourcing")

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


def _fast_fail_closed_cross_plane_claim_gate(
    claims: Sequence[str],
    *,
    surface: str,
    blocker: str,
    claim_boundary: str,
) -> dict[str, Any]:
    requested_claim_ids = list(dict.fromkeys(str(claim) for claim in claims if str(claim)))
    return {
        "schema": "x0tta6bl4.cross_plane_proof_gate.v1",
        "decision": "CROSS_PLANE_CLAIMS_BLOCKED_FAST_LOCAL_OBSERVATION",
        "allowed": False,
        "available": False,
        "surface": surface,
        "requested_claim_ids": requested_claim_ids,
        "allowed_claim_ids": [],
        "blocked_claim_ids": requested_claim_ids,
        "blockers": [blocker],
        "claim_blockers": {
            claim_id: [blocker]
            for claim_id in requested_claim_ids
        },
        "plane_claims": {},
        "allowed_plane_ids": [],
        "blocked_plane_ids": [],
        "plane_blockers": {},
        "proof_dependency_graph": {},
        "next_actions": [],
        "next_actions_by_plane": {},
        "claim_boundary": claim_boundary,
    }


def _health_api_response(payload: dict, *, surface: str):
    return {
        **payload,
        "health_api_claim_gate": _health_api_claim_gate(surface),
        "cross_plane_claim_gate": _fast_fail_closed_cross_plane_claim_gate(
            _HEALTH_API_CROSS_PLANE_CLAIMS,
            surface=surface,
            blocker="health_liveness_endpoint_does_not_run_full_cross_plane_proof_gate",
            claim_boundary=(
                "Health endpoints are fast local liveness/readiness observations. "
                "They intentionally do not run the full cross-plane proof gate on "
                "each request and must not be used to promote production, dataplane, "
                "DPI, traffic, trust-finality, or settlement claims."
            ),
        ),
    }


_METRICS_API_CLAIM_BOUNDARY = (
    "Prometheus metrics expose local scrape observations only. A successful "
    "scrape does not prove production readiness, production SLOs, dataplane "
    "delivery, customer traffic, external DPI bypass, or settlement finality."
)
_METRICS_API_CLAIM_HEADERS = {
    "X-x0tta6bl4-Claim-Gate-Schema": "x0tta6bl4.metrics_api_claim_boundary_headers.v1",
    "X-x0tta6bl4-Claim-Boundary": _METRICS_API_CLAIM_BOUNDARY,
    "X-x0tta6bl4-Local-Metrics-Observation-Claim-Allowed": "true",
    "X-x0tta6bl4-Production-Readiness-Claim-Allowed": "false",
    "X-x0tta6bl4-Production-SLO-Claim-Allowed": "false",
    "X-x0tta6bl4-Dataplane-Delivery-Claim-Allowed": "false",
    "X-x0tta6bl4-Traffic-Delivery-Claim-Allowed": "false",
    "X-x0tta6bl4-Customer-Traffic-Claim-Allowed": "false",
    "X-x0tta6bl4-External-DPI-Bypass-Claim-Allowed": "false",
    "X-x0tta6bl4-Settlement-Finality-Claim-Allowed": "false",
}


def _metrics_api_claim_boundary_headers():
    return dict(_METRICS_API_CLAIM_HEADERS)


_FULL_CORE_DESKTOP_STATE_DIR = Path(
    os.getenv("X0TTA6BL4_DESKTOP_STATE_DIR", "/opt/x0tta6bl4-mesh/state")
)
_FULL_CORE_RUNTIME_STATE_PATH = _FULL_CORE_DESKTOP_STATE_DIR / "runtime-state.json"
_FULL_CORE_CLIENT_PROFILE_HINT_PATH = _FULL_CORE_DESKTOP_STATE_DIR / "client-profile-hint.json"
_FULL_CORE_LISTENER_SIGNAL_PATH = _FULL_CORE_DESKTOP_STATE_DIR / "listener-loss-signal.json"
_FULL_CORE_LIVE_SNAPSHOT_CLAIMS = (
    "production_readiness",
    "dataplane_delivery",
    "traffic_delivery",
    "customer_traffic",
    "settlement_finality",
    "dpi_bypass",
)
_FULL_CORE_LIVE_SNAPSHOT_CLAIM_BOUNDARY = (
    "Full Core live snapshot exposes local process, router, EventBus, and desktop "
    "runtime-state observations only. It is a fast UI status surface, not a "
    "production-readiness, customer-traffic, dataplane-delivery, external-DPI, "
    "trust-finality, or settlement proof."
)
_LIVE_SNAPSHOT_SENSITIVE_KEY_PARTS = (
    "api_key",
    "authorization",
    "bearer",
    "credential",
    "email",
    "hostname",
    "install_command",
    "key",
    "link",
    "node_id",
    "password",
    "private",
    "secret",
    "spiffe",
    "svid",
    "token",
    "url",
    "vless",
    "wallet",
)
_LIVE_SNAPSHOT_SURFACE_KEYWORDS = (
    ("mesh", ("mesh", "node", "peer", "route", "listener", "vpn", "runtime")),
    ("marketplace", ("market", "listing", "rental", "escrow")),
    ("billing", ("billing", "invoice", "payment", "subscription")),
    ("wallet", ("wallet", "ledger", "reward", "settlement")),
    ("dao", ("dao", "governance", "proposal", "vote")),
    ("ops", ("readiness", "proof", "gate", "deploy", "health", "mape", "graphsage")),
)


def _live_snapshot_read_json(path: Path) -> dict[str, Any]:
    try:
        value = json.loads(path.read_text(encoding="utf-8"))
    except Exception:
        return {}
    return value if isinstance(value, dict) else {}


def _live_snapshot_is_sensitive_key(key: Any) -> bool:
    normalized = str(key).lower()
    return any(part in normalized for part in _LIVE_SNAPSHOT_SENSITIVE_KEY_PARTS)


def _live_snapshot_safe_scalar(value: Any) -> Any:
    if isinstance(value, bool) or value is None:
        return value
    if isinstance(value, (int, float)):
        return value
    if isinstance(value, str):
        return value[:160]
    return None


def _live_snapshot_data_summary(data: Any) -> dict[str, Any]:
    if not isinstance(data, dict):
        return {"data_type": type(data).__name__, "payloads_redacted": True}

    fields: dict[str, Any] = {}
    redacted: list[str] = []
    for key, value in sorted(data.items(), key=lambda pair: str(pair[0]))[:80]:
        key_text = str(key)
        if _live_snapshot_is_sensitive_key(key_text):
            redacted.append(key_text)
            continue
        if isinstance(value, (str, int, float, bool)) or value is None:
            fields[key_text] = _live_snapshot_safe_scalar(value)
        elif isinstance(value, list):
            fields[key_text] = {"item_count": len(value)}
        elif isinstance(value, dict):
            fields[key_text] = {"keys": sorted(str(item) for item in value.keys())[:12]}

    fields["data_keys"] = sorted(str(key) for key in data.keys())[:80]
    fields["redacted_sensitive_keys"] = redacted
    fields["payloads_redacted"] = True
    return fields


def _live_snapshot_event_surface(event: Event) -> str:
    data = event.data if isinstance(event.data, dict) else {}
    haystack = " ".join(
        [
            event.event_type.value,
            event.source_agent,
            str(data.get("surface", "")),
            str(data.get("operation", "")),
            str(data.get("action", "")),
            str(data.get("stage", "")),
            str(data.get("transition", "")),
        ]
    ).lower()
    for surface, keywords in _LIVE_SNAPSHOT_SURFACE_KEYWORDS:
        if any(keyword in haystack for keyword in keywords):
            return surface
    return "system"


def _live_snapshot_event_summary(event: Event) -> dict[str, Any]:
    return {
        "event_id": event.event_id,
        "event_type": event.event_type.value,
        "surface": _live_snapshot_event_surface(event),
        "source_agent": event.source_agent,
        "timestamp": event.timestamp.isoformat(),
        "priority": event.priority,
        "requires_ack": event.requires_ack,
        "acked_by_count": len(event.acked_by),
        "targeted": event.target_agents is not None,
        "data": _live_snapshot_data_summary(event.data),
    }


def _live_snapshot_event_bus_or_none() -> EventBus | None:
    try:
        return get_event_bus(".")
    except Exception:
        return None


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
    node_features = [
        _get_simulated_features(f"node-{seed}-{i}") for i in range(num_nodes)
    ]
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
    return _health_api_response(
        {"status": "ok", "timestamp": datetime.now(UTC).isoformat()},
        surface="health_api.live",
    )


@app.get("/health/ready")
async def health_ready():
    return _health_api_response(
        {"status": "ready", "timestamp": datetime.now(UTC).isoformat()},
        surface="health_api.ready",
    )


@app.get("/metrics")
async def metrics():
    from src.monitoring.metrics import get_metrics

    metrics_payload = get_metrics()
    return Response(
        content=metrics_payload.body,
        media_type=metrics_payload.media_type,
        headers=_metrics_api_claim_boundary_headers(),
    )


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
_MESH_API_EVENT_LOG_MAX_BYTES_ENV = "X0TTA6BL4_MESH_API_EVENT_LOG_MAX_BYTES"
_MESH_API_EVENT_LOG_MAX_BYTES_DEFAULT = 16 * 1024 * 1024
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
    app_state = getattr(getattr(request, "app", None), "state", None)
    injected_bus = getattr(app_state, "event_bus", None)
    if injected_bus is not None:
        return injected_bus
    project_root = getattr(state, "event_project_root", ".")
    event_log_path = Path(project_root) / EventBus.EVENT_LOG
    try:
        max_bytes = int(
            os.getenv(
                _MESH_API_EVENT_LOG_MAX_BYTES_ENV,
                str(_MESH_API_EVENT_LOG_MAX_BYTES_DEFAULT),
            )
        )
    except ValueError:
        max_bytes = _MESH_API_EVENT_LOG_MAX_BYTES_DEFAULT
    try:
        if max_bytes > 0 and event_log_path.stat().st_size > max_bytes:
            logger.warning(
                "Skipping mesh API EventBus evidence from oversized log: %s",
                event_log_path,
            )
            return None
    except FileNotFoundError:
        pass
    except OSError as exc:
        logger.error("Failed to stat mesh API EventBus log %s: %s", event_log_path, exc)
        return None
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
        "cross_plane_claim_gate": _fast_fail_closed_cross_plane_claim_gate(
            _STATUS_API_CROSS_PLANE_CLAIMS,
            surface="status_api",
            blocker="status_endpoint_does_not_run_full_cross_plane_proof_gate",
            claim_boundary=(
                "Status endpoint responses expose local process, system, resilience, "
                "mesh-health, and loop-state observations. They intentionally do not "
                "run the full cross-plane proof gate on each request and must not be "
                "used to promote production, dataplane, DPI, traffic, trust-finality, "
                "or settlement claims."
            ),
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
            "cross_plane_claim_gate": _fast_fail_closed_cross_plane_claim_gate(
                _MESH_API_CROSS_PLANE_CLAIMS,
                surface=f"mesh_api.{operation}",
                blocker="mesh_endpoint_does_not_run_full_cross_plane_proof_gate",
                claim_boundary=(
                    "Mesh endpoints expose local Yggdrasil observed-state and local "
                    "control policy evidence. They intentionally do not run the full "
                    "cross-plane proof gate on each request and must not be used to "
                    "promote production, dataplane, DPI, traffic, or customer-traffic "
                    "claims."
                ),
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


@app.get("/status")
async def status_endpoint():
    return JSONResponse(content=_status_api_response(get_current_status()))


@app.get("/api/v1/platform/live-snapshot")
async def platform_live_snapshot(
    limit: int = Query(default=25, ge=1, le=100),
) -> dict[str, Any]:
    runtime = _live_snapshot_read_json(_FULL_CORE_RUNTIME_STATE_PATH)
    hint = _live_snapshot_read_json(_FULL_CORE_CLIENT_PROFILE_HINT_PATH)
    signal = _live_snapshot_read_json(_FULL_CORE_LISTENER_SIGNAL_PATH)
    event_bus = _live_snapshot_event_bus_or_none()
    events = event_bus.get_event_history(limit=limit) if event_bus else []

    event_type_counts: dict[str, int] = {}
    source_agent_counts: dict[str, int] = {}
    surface_counts: dict[str, int] = {}
    recent_by_surface: dict[str, list[dict[str, Any]]] = {}
    recent_events: list[dict[str, Any]] = []
    for event in events:
        surface = _live_snapshot_event_surface(event)
        summary = _live_snapshot_event_summary(event)
        event_type_counts[event.event_type.value] = event_type_counts.get(event.event_type.value, 0) + 1
        source_agent_counts[event.source_agent] = source_agent_counts.get(event.source_agent, 0) + 1
        surface_counts[surface] = surface_counts.get(surface, 0) + 1
        recent_by_surface.setdefault(surface, []).append(summary)
        recent_events.append(summary)

    local_state = {
        "runtime_state_present": _FULL_CORE_RUNTIME_STATE_PATH.is_file(),
        "client_profile_hint_present": _FULL_CORE_CLIENT_PROFILE_HINT_PATH.is_file(),
        "listener_signal_present": _FULL_CORE_LISTENER_SIGNAL_PATH.is_file(),
        "runtime_mode": runtime.get("mode") or hint.get("runtime_mode"),
        "recommended_action": runtime.get("recommended_action") or hint.get("recommended_action"),
        "recommended_profile": hint.get("recommended_profile"),
        "listener_signal_status": signal.get("status"),
    }
    return {
        "schema": "x0tta6bl4.platform.live_snapshot.v1",
        "status": "observed" if event_bus or any(local_state.values()) else "missing",
        "mode": "full-core-api",
        "generated_at": datetime.now(UTC).isoformat(),
        "uptime_seconds": round(time.time() - STARTED_AT, 3),
        "local_state": local_state,
        "routers": {
            "mode": "full-core-api",
            "full_core_required_for_mutations": False,
            "loaded": "full-router-set",
        },
        "event_bus": {
            "available": event_bus is not None,
            "event_log": str(event_bus.event_log_path) if event_bus else None,
            "events_returned": len(events),
            "event_type_counts": event_type_counts,
            "source_agent_counts": source_agent_counts,
            "surface_counts": surface_counts,
            "recent_by_surface": {
                surface: items[-8:]
                for surface, items in sorted(recent_by_surface.items())
            },
            "recent_events": recent_events,
            "payloads_redacted": True,
        },
        "claim_boundary": _FULL_CORE_LIVE_SNAPSHOT_CLAIM_BOUNDARY,
        "cross_plane_claim_gate": _fast_fail_closed_cross_plane_claim_gate(
            _FULL_CORE_LIVE_SNAPSHOT_CLAIMS,
            surface="full_core_api.platform_live_snapshot",
            blocker="live_snapshot_endpoint_does_not_run_full_cross_plane_proof_gate",
            claim_boundary=_FULL_CORE_LIVE_SNAPSHOT_CLAIM_BOUNDARY,
        ),
    }


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
    uvicorn.run(app, host=os.getenv("X0TTA6BL4_API_HOST", "127.0.0.1"), port=8000)
