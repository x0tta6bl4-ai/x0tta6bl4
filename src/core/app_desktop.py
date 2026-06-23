"""Desktop/mobile control-plane API for the x0tta6bl4 native app.

This entrypoint is intentionally narrower than ``src.core.app``. It exposes the
read-only and low-risk surfaces the native control panels need, while avoiding
heavy production routers that make the installed desktop shell feel broken.
"""

from __future__ import annotations

import json
import time
from datetime import datetime, timezone
from importlib import import_module
from pathlib import Path
from typing import Any

from fastapi import APIRouter, FastAPI, HTTPException, Query, Response
from fastapi.middleware.cors import CORSMiddleware
from pydantic import BaseModel, Field

from src.coordination.events import Event, EventBus, get_event_bus
from src.sales.pilot_package import build_pilot_package
from src.sales.product_ideas import build_product_idea_portfolio, get_product_idea
from src.sales.wallet_payment_intake import build_wallet_payment_intake
from src.version import __version__


STARTED_AT = time.time()
RUNTIME_STATE_PATH = Path("/opt/x0tta6bl4-mesh/state/runtime-state.json")
CLIENT_PROFILE_HINT_PATH = Path("/opt/x0tta6bl4-mesh/state/client-profile-hint.json")
LISTENER_SIGNAL_PATH = Path("/opt/x0tta6bl4-mesh/state/listener-loss-signal.json")
ACTION_CONFIRMATION_PHRASE = "CONFIRM LOCAL ACTION"

DEFAULT_APP_CORS_ORIGINS = (
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

LOCAL_OBSERVATION_CLAIM_BOUNDARY = (
    "Desktop control-plane responses expose local process, router, and observed "
    "state only. They do not prove production readiness, customer traffic, "
    "external DPI bypass, settlement finality, production SLOs, or live service "
    "delivery."
)
SENSITIVE_EVENT_KEY_PARTS = (
    "api_key",
    "authorization",
    "bearer",
    "config",
    "credential",
    "email",
    "install_command",
    "key",
    "link",
    "password",
    "private",
    "secret",
    "token",
    "url",
    "vless",
    "wallet",
)
SAFE_EVENT_SUMMARY_KEYS = (
    "action",
    "decision",
    "http_status_code",
    "operation",
    "reason",
    "stage",
    "status",
    "surface",
    "transition",
)
SURFACE_KEYWORDS: tuple[tuple[str, tuple[str, ...]], ...] = (
    ("marketplace", ("marketplace", "escrow", "listing", "rental", "rent_node")),
    ("billing", ("billing", "invoice", "payment", "checkout", "subscription", "stripe")),
    ("wallet", ("wallet", "ledger", "reward", "settlement", "token", "bridge")),
    ("dao", ("dao", "governance", "proposal", "vote", "quorum")),
    ("ops", ("identity", "spire", "spiffe", "vpn", "provision", "node", "heal", "service")),
    ("mesh", ("mesh", "runtime", "mape", "heartbeat", "routing", "transport")),
)

app = FastAPI(
    title="x0tta6bl4 desktop control-plane",
    version=f"{__version__}-desktop",
    description="Fast local API surface for the installed x0tta6bl4 native app.",
    docs_url="/docs",
    redoc_url="/redoc",
    openapi_url="/openapi.json",
)

app.add_middleware(
    CORSMiddleware,
    allow_origins=list(DEFAULT_APP_CORS_ORIGINS),
    allow_credentials=True,
    allow_methods=["GET", "POST", "PUT", "DELETE", "OPTIONS"],
    allow_headers=["Authorization", "Content-Type", "X-Request-ID"],
)

_imported_routers: list[dict[str, str]] = []
_router_errors: list[dict[str, str]] = []


class DesktopActionRequest(BaseModel):
    action_id: str
    confirmation: str | None = None
    dry_run: bool = True
    parameters: dict[str, Any] = Field(default_factory=dict)


ACTION_CATALOG: dict[str, dict[str, Any]] = {
    "mesh.refresh_runtime": {
        "label": "Refresh local mesh runtime",
        "surface": "mesh",
        "description": "Refresh the local runtime, metrics, and mesh status panels.",
        "read_paths": ["/mesh/status", "/mesh/peers", "/metrics", "/status"],
        "requires_confirmation": False,
        "requires_full_core_api": False,
        "claim_ids": ("dataplane_delivery", "traffic_delivery", "customer_traffic"),
    },
    "marketplace.refresh_snapshot": {
        "label": "Refresh marketplace snapshot",
        "surface": "marketplace",
        "description": "Refresh marketplace status and listing/search views.",
        "read_paths": [
            "/api/v1/maas/marketplace/status",
            "/api/v1/maas/marketplace/search",
        ],
        "requires_confirmation": False,
        "requires_full_core_api": False,
        "claim_ids": ("production_readiness", "settlement_finality"),
    },
    "marketplace.create_listing": {
        "label": "Create marketplace listing",
        "surface": "marketplace",
        "description": "Create a node listing through the authenticated full Core API.",
        "read_paths": ["/api/v1/maas/marketplace/status"],
        "requires_confirmation": True,
        "requires_full_core_api": True,
        "mutates_runtime": True,
        "mutates_chain": False,
        "claim_ids": ("production_readiness", "settlement_finality"),
    },
    "marketplace.rent_listing": {
        "label": "Rent marketplace listing",
        "surface": "marketplace",
        "description": "Start a marketplace rental and escrow hold through the full Core API.",
        "read_paths": ["/api/v1/maas/marketplace/search"],
        "requires_confirmation": True,
        "requires_full_core_api": True,
        "mutates_runtime": True,
        "mutates_chain": True,
        "claim_ids": ("settlement_finality", "customer_traffic"),
    },
    "marketplace.release_escrow": {
        "label": "Release marketplace escrow",
        "surface": "marketplace",
        "description": "Release held marketplace escrow through the full Core API.",
        "read_paths": ["/api/v1/maas/marketplace/search"],
        "requires_confirmation": True,
        "requires_full_core_api": True,
        "mutates_runtime": True,
        "mutates_chain": True,
        "claim_ids": ("settlement_finality",),
    },
    "marketplace.refund_escrow": {
        "label": "Refund marketplace escrow",
        "surface": "marketplace",
        "description": "Refund held marketplace escrow through the full Core API.",
        "read_paths": ["/api/v1/maas/marketplace/search"],
        "requires_confirmation": True,
        "requires_full_core_api": True,
        "mutates_runtime": True,
        "mutates_chain": True,
        "claim_ids": ("settlement_finality",),
    },
    "billing.prepare_invoice": {
        "label": "Prepare billing invoice handoff",
        "surface": "billing",
        "description": (
            "Prepare a local invoice/subscription handoff. No payment, subscription, "
            "or external provider mutation is performed by the desktop control-plane."
        ),
        "read_paths": [
            "/api/v1/maas/billing/usage",
            "/api/v1/maas/billing/billing/plans",
        ],
        "requires_confirmation": True,
        "requires_full_core_api": True,
        "claim_ids": ("settlement_finality", "production_readiness"),
    },
    "wallet.open_ledger_status": {
        "label": "Open wallet ledger status",
        "surface": "wallet",
        "description": (
            "Open the local ledger/reward status surface. Signed wallet operations "
            "require a dedicated signer service."
        ),
        "read_paths": ["/api/v1/ledger/status"],
        "requires_confirmation": False,
        "requires_full_core_api": True,
        "claim_ids": ("settlement_finality", "trust_finality"),
    },
    "wallet.search_ledger": {
        "label": "Search continuity ledger",
        "surface": "wallet",
        "description": "Search the continuity ledger through the full Core API.",
        "read_paths": ["/api/v1/ledger/search"],
        "requires_confirmation": False,
        "requires_full_core_api": True,
        "claim_ids": ("settlement_finality", "trust_finality", "production_readiness"),
    },
    "ledger.index": {
        "label": "Index continuity ledger",
        "surface": "wallet",
        "description": "Run ledger indexing through the authenticated full Core API.",
        "read_paths": ["/api/v1/ledger/status"],
        "requires_confirmation": True,
        "requires_full_core_api": True,
        "mutates_runtime": True,
        "mutates_chain": False,
        "claim_ids": ("production_readiness",),
    },
    "ledger.index_evidence": {
        "label": "Index verification evidence",
        "surface": "wallet",
        "description": "Index verification evidence through the authenticated full Core API.",
        "read_paths": ["/api/v1/ledger/evidence/status"],
        "requires_confirmation": True,
        "requires_full_core_api": True,
        "mutates_runtime": True,
        "mutates_chain": False,
        "claim_ids": ("production_readiness",),
    },
    "ledger.index_event_traces": {
        "label": "Index event traces",
        "surface": "wallet",
        "description": "Index EventBus traces through the authenticated full Core API.",
        "read_paths": ["/api/v1/ledger/event-traces/status"],
        "requires_confirmation": True,
        "requires_full_core_api": True,
        "mutates_runtime": True,
        "mutates_chain": False,
        "claim_ids": ("production_readiness",),
    },
    "agent_health.run": {
        "label": "Run MAPE-K health bot",
        "surface": "dao",
        "description": "Run the MaaS agent health bot through the authenticated full Core API.",
        "read_paths": ["/api/v1/maas/agents/health/status"],
        "requires_confirmation": True,
        "requires_full_core_api": True,
        "mutates_runtime": True,
        "mutates_chain": False,
        "claim_ids": ("production_readiness",),
    },
    "identity.refresh_status": {
        "label": "Refresh service identity status",
        "surface": "ops",
        "description": "Read redacted Service Identity/SPIFFE surface status.",
        "read_paths": [
            "/api/v1/service-identity/status",
            "/api/v1/service-identity/event-trace-filter",
        ],
        "requires_confirmation": False,
        "requires_full_core_api": True,
        "claim_ids": ("trust_finality", "production_readiness"),
    },
    "identity.read_event_traces": {
        "label": "Read service identity event traces",
        "surface": "ops",
        "description": "Read redacted service identity EventBus traces through the full Core API.",
        "read_paths": ["/api/v1/service-identity/event-traces"],
        "requires_confirmation": False,
        "requires_full_core_api": True,
        "claim_ids": ("trust_finality", "production_readiness"),
    },
    "vpn.refresh_status": {
        "label": "Refresh VPN status",
        "surface": "ops",
        "description": "Read VPN readiness and runtime status through the full Core API.",
        "read_paths": ["/api/v1/vpn/readiness", "/api/v1/vpn/status"],
        "requires_confirmation": False,
        "requires_full_core_api": True,
        "claim_ids": ("traffic_delivery", "customer_traffic", "dpi_bypass"),
    },
    "vpn.list_users": {
        "label": "List VPN users",
        "surface": "ops",
        "description": "Read VPN users through authenticated full Core API admin access.",
        "read_paths": ["/api/v1/vpn/users"],
        "requires_confirmation": True,
        "requires_full_core_api": True,
        "claim_ids": ("customer_traffic", "production_readiness"),
    },
    "provisioning.refresh_readiness": {
        "label": "Refresh provisioning readiness",
        "surface": "ops",
        "description": "Read MaaS provisioning setup readiness.",
        "read_paths": ["/api/v1/maas/provisioning/readiness"],
        "requires_confirmation": False,
        "requires_full_core_api": True,
        "claim_ids": ("production_readiness",),
    },
    "provisioning.generate_setup": {
        "label": "Generate node setup",
        "surface": "ops",
        "description": "Generate a node setup package through the authenticated full Core API.",
        "read_paths": ["/api/v1/maas/provisioning/readiness"],
        "requires_confirmation": True,
        "requires_full_core_api": True,
        "mutates_runtime": True,
        "mutates_chain": False,
        "claim_ids": ("production_readiness", "dataplane_delivery"),
    },
    "node.list_pending": {
        "label": "List pending nodes",
        "surface": "ops",
        "description": "Read pending nodes for a mesh through the full Core API.",
        "read_paths": ["/api/v1/maas/nodes/{mesh_id}/nodes/pending"],
        "requires_confirmation": False,
        "requires_full_core_api": True,
        "claim_ids": ("dataplane_delivery", "production_readiness"),
    },
    "node.list_all": {
        "label": "List all nodes",
        "surface": "ops",
        "description": "Read all nodes for a mesh through the full Core API.",
        "read_paths": ["/api/v1/maas/nodes/{mesh_id}/nodes/all"],
        "requires_confirmation": False,
        "requires_full_core_api": True,
        "claim_ids": ("dataplane_delivery", "production_readiness"),
    },
    "node.readiness": {
        "label": "Read node readiness",
        "surface": "ops",
        "description": "Read node readiness for a specific mesh/node pair.",
        "read_paths": ["/api/v1/maas/nodes/{mesh_id}/nodes/{node_id}/readiness"],
        "requires_confirmation": False,
        "requires_full_core_api": True,
        "claim_ids": ("dataplane_delivery", "production_readiness"),
    },
    "node.telemetry": {
        "label": "Read node telemetry",
        "surface": "ops",
        "description": "Read node telemetry for a specific mesh/node pair.",
        "read_paths": ["/api/v1/maas/nodes/{mesh_id}/nodes/{node_id}/telemetry"],
        "requires_confirmation": False,
        "requires_full_core_api": True,
        "claim_ids": ("dataplane_delivery", "customer_traffic"),
    },
    "node.approve": {
        "label": "Approve node",
        "surface": "ops",
        "description": "Approve a pending node through the authenticated full Core API.",
        "read_paths": ["/api/v1/maas/nodes/{mesh_id}/nodes/pending"],
        "requires_confirmation": True,
        "requires_full_core_api": True,
        "mutates_runtime": True,
        "mutates_chain": False,
        "claim_ids": ("dataplane_delivery", "production_readiness"),
    },
    "node.revoke": {
        "label": "Revoke node",
        "surface": "ops",
        "description": "Revoke a node through the authenticated full Core API.",
        "read_paths": ["/api/v1/maas/nodes/{mesh_id}/nodes/all"],
        "requires_confirmation": True,
        "requires_full_core_api": True,
        "mutates_runtime": True,
        "mutates_chain": False,
        "claim_ids": ("dataplane_delivery", "production_readiness"),
    },
    "node.heal": {
        "label": "Trigger node healing",
        "surface": "ops",
        "description": "Trigger node healing through the authenticated full Core API.",
        "read_paths": ["/api/v1/maas/nodes/{mesh_id}/nodes/{node_id}/readiness"],
        "requires_confirmation": True,
        "requires_full_core_api": True,
        "mutates_runtime": True,
        "mutates_chain": False,
        "claim_ids": ("production_readiness", "dataplane_delivery"),
    },
    "dao.prepare_proposal": {
        "label": "Prepare DAO proposal handoff",
        "surface": "dao",
        "description": (
            "Prepare a proposal handoff for the full governance API. The desktop "
            "control-plane does not sign or submit governance transactions."
        ),
        "read_paths": [
            "/api/v1/maas/governance/readiness",
            "/api/v1/maas/governance/proposals",
        ],
        "requires_confirmation": True,
        "requires_full_core_api": True,
        "claim_ids": ("trust_finality", "production_readiness"),
    },
    "dao.prepare_vote": {
        "label": "Prepare DAO vote handoff",
        "surface": "dao",
        "description": (
            "Prepare a vote handoff for the full governance API. The desktop "
            "control-plane never handles private keys."
        ),
        "read_paths": [
            "/api/v1/maas/governance/readiness",
            "/api/v1/maas/governance/proposals",
        ],
        "requires_confirmation": True,
        "requires_full_core_api": True,
        "claim_ids": ("trust_finality", "production_readiness"),
    },
    "readiness.open_gate": {
        "label": "Open readiness gate handoff",
        "surface": "readiness",
        "description": "Prepare the user to run the local readiness gate from the native shell.",
        "read_paths": ["/health/ready", "/status"],
        "requires_confirmation": False,
        "requires_full_core_api": False,
        "claim_ids": ("production_readiness",),
    },
    "vpn.refresh_readiness": {
        "label": "Refresh VPN/readiness view",
        "surface": "vpn",
        "description": "Refresh local VPN readiness and observed mesh transport signals.",
        "read_paths": ["/api/v1/vpn/readiness", "/mesh/status", "/metrics"],
        "requires_confirmation": False,
        "requires_full_core_api": False,
        "claim_ids": ("traffic_delivery", "customer_traffic", "dpi_bypass"),
    },
    "product.refresh_ideas": {
        "label": "Refresh product idea portfolio",
        "surface": "readiness",
        "description": "Read the ten productized x0tta6bl4 ideas and their proof boundaries.",
        "read_paths": ["/api/v1/product/ideas"],
        "requires_confirmation": False,
        "requires_full_core_api": False,
        "claim_ids": ("production_readiness", "customer_traffic", "settlement_finality"),
    },
    "product.open_pilot_package": {
        "label": "Open first paid pilot package",
        "surface": "readiness",
        "description": "Read the first sellable self-hosted secure mesh pilot package.",
        "read_paths": ["/api/v1/product/pilot-package"],
        "requires_confirmation": False,
        "requires_full_core_api": False,
        "claim_ids": ("production_readiness", "customer_traffic", "settlement_finality"),
    },
    "product.open_payment_intake": {
        "label": "Open wallet payment intake",
        "surface": "readiness",
        "description": "Read the wallet, pricing ladder, buyer steps, and payment proof boundary.",
        "read_paths": ["/api/v1/product/payment-intake"],
        "requires_confirmation": False,
        "requires_full_core_api": False,
        "claim_ids": ("settlement_finality", "customer_traffic"),
    },
}


def _claim_gate(surface: str, requested_claims: tuple[str, ...] = ()) -> dict[str, Any]:
    blocker = "desktop_control_plane_local_observation_only"
    return {
        "schema": "x0tta6bl4.cross_plane_proof_gate.v1",
        "decision": "CROSS_PLANE_CLAIMS_BLOCKED_FAST_LOCAL_OBSERVATION",
        "allowed": False,
        "available": False,
        "surface": surface,
        "requested_claim_ids": list(requested_claims),
        "allowed_claim_ids": [],
        "blocked_claim_ids": list(requested_claims),
        "blockers": [blocker],
        "claim_blockers": {claim: [blocker] for claim in requested_claims},
        "plane_claims": {},
        "allowed_plane_ids": [],
        "blocked_plane_ids": [],
        "plane_blockers": {},
        "proof_dependency_graph": {},
        "next_actions": [],
        "next_actions_by_plane": {},
        "production_readiness_claim_allowed": False,
        "production_slo_claim_allowed": False,
        "dataplane_delivery_claim_allowed": False,
        "traffic_delivery_claim_allowed": False,
        "customer_traffic_claim_allowed": False,
        "external_dpi_bypass_claim_allowed": False,
        "settlement_finality_claim_allowed": False,
        "claim_boundary": LOCAL_OBSERVATION_CLAIM_BOUNDARY,
    }


def _read_json(path: Path) -> dict[str, Any] | None:
    try:
        value = json.loads(path.read_text())
    except Exception:
        return None
    return value if isinstance(value, dict) else None


def _is_sensitive_event_key(key: Any) -> bool:
    normalized = str(key).lower()
    return any(part in normalized for part in SENSITIVE_EVENT_KEY_PARTS)


def _safe_scalar(value: Any) -> Any:
    if isinstance(value, bool) or value is None:
        return value
    if isinstance(value, (int, float)):
        return value
    if isinstance(value, str):
        return value[:160]
    return None


def _safe_dict_summary(value: Any) -> dict[str, Any] | None:
    if not isinstance(value, dict):
        return None
    summary: dict[str, Any] = {}
    for key, item in sorted(value.items(), key=lambda pair: str(pair[0]))[:20]:
        if _is_sensitive_event_key(key):
            continue
        if isinstance(item, (str, int, float, bool)) or item is None:
            summary[str(key)] = _safe_scalar(item)
        elif isinstance(item, list):
            summary[str(key)] = {"item_count": len(item)}
        elif isinstance(item, dict):
            summary[str(key)] = {"keys": sorted(str(nested) for nested in item.keys())[:12]}
    return summary


def _event_data_summary(data: Any) -> dict[str, Any]:
    if not isinstance(data, dict):
        return {
            "data_type": type(data).__name__,
            "payloads_redacted": True,
        }

    fields: dict[str, Any] = {}
    redacted_sensitive_keys: list[str] = []
    for key in sorted(str(item) for item in data.keys())[:80]:
        value = data.get(key)
        if _is_sensitive_event_key(key):
            redacted_sensitive_keys.append(key)
            continue
        if key in SAFE_EVENT_SUMMARY_KEYS:
            fields[key] = _safe_scalar(value)
    for nested_key in ("result_summary", "output_summary", "db_evidence", "bridge_evidence"):
        if nested_key in data and not _is_sensitive_event_key(nested_key):
            nested_summary = _safe_dict_summary(data.get(nested_key))
            if nested_summary:
                fields[nested_key] = nested_summary

    fields["data_keys"] = sorted(str(key) for key in data.keys())[:80]
    fields["redacted_sensitive_keys"] = redacted_sensitive_keys
    fields["payloads_redacted"] = True
    return fields


def _event_surface(event: Event) -> str:
    data = event.data if isinstance(event.data, dict) else {}
    haystack_parts = [
        event.event_type.value,
        event.source_agent,
        str(data.get("surface", "")),
        str(data.get("operation", "")),
        str(data.get("action", "")),
        str(data.get("stage", "")),
        str(data.get("transition", "")),
    ]
    haystack = " ".join(haystack_parts).lower()
    for surface, keywords in SURFACE_KEYWORDS:
        if any(keyword in haystack for keyword in keywords):
            return surface
    return "system"


def _event_summary(event: Event) -> dict[str, Any]:
    return {
        "event_id": event.event_id,
        "event_type": event.event_type.value,
        "surface": _event_surface(event),
        "source_agent": event.source_agent,
        "timestamp": event.timestamp.isoformat(),
        "priority": event.priority,
        "requires_ack": event.requires_ack,
        "acked_by_count": len(event.acked_by),
        "targeted": event.target_agents is not None,
        "data": _event_data_summary(event.data),
    }


def _event_bus_or_none() -> EventBus | None:
    try:
        return get_event_bus(".")
    except Exception:
        return None


def _public_action_catalog() -> list[dict[str, Any]]:
    return [
        {
            "action_id": action_id,
            "label": spec["label"],
            "surface": spec["surface"],
            "description": spec["description"],
            "read_paths": spec["read_paths"],
            "requires_confirmation": spec["requires_confirmation"],
            "requires_full_core_api": spec["requires_full_core_api"],
            "mutates_runtime": spec.get("mutates_runtime", False),
            "mutates_chain": spec.get("mutates_chain", False),
            "confirmation_phrase": (
                ACTION_CONFIRMATION_PHRASE
                if spec["requires_confirmation"]
                else None
            ),
        }
        for action_id, spec in sorted(ACTION_CATALOG.items())
    ]


def _execute_desktop_action(request: DesktopActionRequest) -> dict[str, Any]:
    action_id = request.action_id.strip()
    spec = ACTION_CATALOG.get(action_id)
    if spec is None:
        raise HTTPException(status_code=404, detail=f"Unknown desktop action: {action_id}")

    if spec["requires_confirmation"] and request.confirmation != ACTION_CONFIRMATION_PHRASE:
        raise HTTPException(
            status_code=403,
            detail=(
                "This local action requires confirmation. Send confirmation="
                f"{ACTION_CONFIRMATION_PHRASE!r} from the app runtime."
            ),
        )

    now = datetime.now(timezone.utc).isoformat()
    claim_ids = tuple(spec.get("claim_ids", ()))
    runtime = _read_json(RUNTIME_STATE_PATH) or {}
    result_status = "dry_run_ready" if request.dry_run else "accepted_local_handoff"
    executed = False
    if action_id in {
        "mesh.refresh_runtime",
        "marketplace.refresh_snapshot",
        "vpn.refresh_readiness",
        "wallet.open_ledger_status",
        "readiness.open_gate",
    }:
        result_status = "local_snapshot_ready" if not request.dry_run else result_status
        executed = not request.dry_run

    return {
        "schema": "x0tta6bl4.desktop_control_action_result.v1",
        "status": result_status,
        "action_id": action_id,
        "label": spec["label"],
        "surface": spec["surface"],
        "dry_run": request.dry_run,
        "executed": executed,
        "mutation_performed": False,
        "mutates_runtime": spec.get("mutates_runtime", False),
        "mutates_chain": spec.get("mutates_chain", False),
        "requires_full_core_api": spec["requires_full_core_api"],
        "read_paths": spec["read_paths"],
        "parameters_received": sorted(request.parameters.keys()),
        "runtime_state_present": RUNTIME_STATE_PATH.is_file(),
        "runtime_mode": runtime.get("mode"),
        "message": (
            "Local desktop action accepted. Mutating production work is delegated "
            "to the full Core API or a signer/runtime service."
        ),
        "claim_boundary": LOCAL_OBSERVATION_CLAIM_BOUNDARY,
        "cross_plane_claim_gate": _claim_gate(
            f"desktop_control_plane.action.{action_id}",
            claim_ids,
        ),
        "timestamp": now,
    }


def _include_router(module_path: str, prefix: str, label: str) -> None:
    try:
        module = import_module(module_path)
        router = getattr(module, "router", None)
        if not isinstance(router, APIRouter):
            raise TypeError(f"{module_path}.router is not an APIRouter")
        app.include_router(router, prefix=prefix)
        _imported_routers.append({"label": label, "module": module_path, "prefix": prefix})
    except Exception as exc:  # pragma: no cover - exercised by runtime smoke tests
        _router_errors.append(
            {
                "label": label,
                "module": module_path,
                "prefix": prefix,
                "error": f"{type(exc).__name__}: {exc}",
            }
        )


@app.get("/health/live")
async def health_live() -> dict[str, Any]:
    return {
        "status": "ok",
        "version": __version__,
        "mode": "desktop-control-plane",
        "timestamp": datetime.now(timezone.utc).isoformat(),
        "uptime_seconds": round(time.time() - STARTED_AT, 3),
        "cross_plane_claim_gate": _claim_gate(
            "desktop_control_plane.health_live",
            ("production_readiness",),
        ),
    }


@app.get("/health")
async def health() -> dict[str, Any]:
    return {
        "status": "ok",
        "version": __version__,
        "mode": "desktop-control-plane",
        "routers_loaded": len(_imported_routers),
        "router_errors": _router_errors,
        "timestamp": datetime.now(timezone.utc).isoformat(),
        "cross_plane_claim_gate": _claim_gate(
            "desktop_control_plane.health",
            ("production_readiness",),
        ),
    }


@app.get("/health/ready")
async def health_ready() -> dict[str, Any]:
    return {
        "status": "ready" if not _router_errors else "degraded",
        "ready": not _router_errors,
        "router_errors": _router_errors,
        "cross_plane_claim_gate": _claim_gate(
            "desktop_control_plane.health_ready",
            ("production_readiness",),
        ),
    }


@app.get("/status")
async def status() -> dict[str, Any]:
    return {
        "status": "healthy" if not _router_errors else "degraded",
        "version": __version__,
        "mode": "desktop-control-plane",
        "uptime_seconds": round(time.time() - STARTED_AT, 3),
        "routers": _imported_routers,
        "router_errors": _router_errors,
        "local_state": {
            "runtime_state_present": RUNTIME_STATE_PATH.is_file(),
            "client_profile_hint_present": CLIENT_PROFILE_HINT_PATH.is_file(),
            "listener_signal_present": LISTENER_SIGNAL_PATH.is_file(),
        },
        "cross_plane_claim_gate": _claim_gate(
            "desktop_control_plane.status",
            (
                "production_readiness",
                "dataplane_delivery",
                "traffic_delivery",
                "customer_traffic",
                "settlement_finality",
                "dpi_bypass",
            ),
        ),
    }


@app.get("/api/v1/platform/live-snapshot")
async def platform_live_snapshot(
    limit: int = Query(default=25, ge=1, le=100),
) -> dict[str, Any]:
    runtime = _read_json(RUNTIME_STATE_PATH) or {}
    hint = _read_json(CLIENT_PROFILE_HINT_PATH) or {}
    signal = _read_json(LISTENER_SIGNAL_PATH) or {}
    event_bus = _event_bus_or_none()
    events: list[Event] = event_bus.get_event_history(limit=limit) if event_bus else []
    event_type_counts: dict[str, int] = {}
    source_agent_counts: dict[str, int] = {}
    surface_counts: dict[str, int] = {}
    recent_by_surface: dict[str, list[dict[str, Any]]] = {}
    for event in events:
        surface = _event_surface(event)
        summary = _event_summary(event)
        event_type_counts[event.event_type.value] = event_type_counts.get(event.event_type.value, 0) + 1
        source_agent_counts[event.source_agent] = source_agent_counts.get(event.source_agent, 0) + 1
        surface_counts[surface] = surface_counts.get(surface, 0) + 1
        recent_by_surface.setdefault(surface, []).append(summary)

    local_state = {
        "runtime_state_present": RUNTIME_STATE_PATH.is_file(),
        "client_profile_hint_present": CLIENT_PROFILE_HINT_PATH.is_file(),
        "listener_signal_present": LISTENER_SIGNAL_PATH.is_file(),
        "runtime_mode": runtime.get("mode") or hint.get("runtime_mode"),
        "recommended_action": runtime.get("recommended_action") or hint.get("recommended_action"),
        "recommended_profile": hint.get("recommended_profile"),
        "listener_signal_status": signal.get("status"),
    }
    return {
        "schema": "x0tta6bl4.platform.live_snapshot.v1",
        "status": "observed" if event_bus or any(local_state.values()) else "missing",
        "mode": "desktop-control-plane",
        "generated_at": datetime.now(timezone.utc).isoformat(),
        "uptime_seconds": round(time.time() - STARTED_AT, 3),
        "local_state": local_state,
        "routers": {
            "loaded": len(_imported_routers),
            "errors": len(_router_errors),
            "error_labels": [item["label"] for item in _router_errors],
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
            "recent_events": [_event_summary(event) for event in events],
            "payloads_redacted": True,
        },
        "claim_boundary": LOCAL_OBSERVATION_CLAIM_BOUNDARY,
        "cross_plane_claim_gate": _claim_gate(
            "desktop_control_plane.platform_live_snapshot",
            (
                "production_readiness",
                "dataplane_delivery",
                "traffic_delivery",
                "customer_traffic",
                "settlement_finality",
                "dpi_bypass",
            ),
        ),
    }


@app.get("/metrics")
async def metrics() -> Response:
    body = "\n".join(
        [
            "# HELP x0tta6bl4_desktop_control_plane_up Desktop control-plane process liveness.",
            "# TYPE x0tta6bl4_desktop_control_plane_up gauge",
            "x0tta6bl4_desktop_control_plane_up 1",
            "# HELP x0tta6bl4_desktop_control_plane_router_errors Router import errors.",
            "# TYPE x0tta6bl4_desktop_control_plane_router_errors gauge",
            f"x0tta6bl4_desktop_control_plane_router_errors {len(_router_errors)}",
            "",
        ]
    )
    return Response(content=body, media_type="text/plain; version=0.0.4")


@app.get("/mesh/status")
async def mesh_status() -> dict[str, Any]:
    runtime = _read_json(RUNTIME_STATE_PATH) or {}
    hint = _read_json(CLIENT_PROFILE_HINT_PATH) or {}
    signal = _read_json(LISTENER_SIGNAL_PATH) or {}
    return {
        "status": "observed" if (runtime or hint or signal) else "missing",
        "mode": runtime.get("mode") or hint.get("runtime_mode"),
        "recommended_action": runtime.get("recommended_action") or hint.get("recommended_action"),
        "recommended_profile": hint.get("recommended_profile"),
        "listener_signal_status": signal.get("status"),
        "state_paths": {
            "runtime_state": str(RUNTIME_STATE_PATH),
            "client_profile_hint": str(CLIENT_PROFILE_HINT_PATH),
            "listener_signal": str(LISTENER_SIGNAL_PATH),
        },
        "cross_plane_claim_gate": _claim_gate(
            "desktop_control_plane.mesh_status",
            ("dataplane_delivery", "traffic_delivery", "customer_traffic"),
        ),
    }


@app.get("/mesh/peers")
async def mesh_peers() -> dict[str, Any]:
    runtime = _read_json(RUNTIME_STATE_PATH) or {}
    peers = runtime.get("peers")
    if not isinstance(peers, list):
        peers = []
    return {
        "status": "observed",
        "count": len(peers),
        "peers": peers,
        "cross_plane_claim_gate": _claim_gate(
            "desktop_control_plane.mesh_peers",
            ("dataplane_delivery", "customer_traffic"),
        ),
    }


@app.get("/api/v1/ledger/status")
async def ledger_status() -> dict[str, Any]:
    return {
        "status": "source_available",
        "mode": "desktop-read-only",
        "source_module": "src.api.maas.endpoints.ledger",
        "source_import_deferred": True,
        "reason": (
            "The full ledger router is intentionally not imported by the desktop "
            "control-plane because it dominates local startup time. Wallet actions "
            "must use the full Core API or a dedicated signed wallet service."
        ),
        "cross_plane_claim_gate": _claim_gate(
            "desktop_control_plane.ledger_status",
            ("settlement_finality", "production_readiness"),
        ),
    }


@app.get("/api/v1/actions")
async def action_catalog() -> dict[str, Any]:
    return {
        "schema": "x0tta6bl4.desktop_control_action_catalog.v1",
        "status": "available",
        "confirmation_phrase": ACTION_CONFIRMATION_PHRASE,
        "actions": _public_action_catalog(),
        "claim_boundary": LOCAL_OBSERVATION_CLAIM_BOUNDARY,
        "cross_plane_claim_gate": _claim_gate(
            "desktop_control_plane.action_catalog",
            ("production_readiness",),
        ),
    }


@app.post("/api/v1/actions/execute")
async def execute_action(request: DesktopActionRequest) -> dict[str, Any]:
    return _execute_desktop_action(request)


@app.get("/api/v1/product/ideas")
async def product_ideas() -> dict[str, Any]:
    return build_product_idea_portfolio(Path("."))


@app.get("/api/v1/product/ideas/{idea_id}")
async def product_idea(idea_id: str) -> dict[str, Any]:
    idea = get_product_idea(idea_id, Path("."))
    if idea is None:
        raise HTTPException(status_code=404, detail=f"Unknown product idea: {idea_id}")
    return idea


@app.get("/api/v1/product/pilot-package")
async def product_pilot_package() -> dict[str, Any]:
    return build_pilot_package(Path("."))


@app.get("/api/v1/product/payment-intake")
async def product_payment_intake() -> dict[str, Any]:
    return build_wallet_payment_intake(Path("."))


@app.get("/api/v1/maas/marketplace/status")
async def marketplace_status() -> dict[str, Any]:
    return {
        "status": "desktop_read_only",
        "mode": "native-control-plane",
        "listings_endpoint": "/api/v1/maas/marketplace/search",
        "mutating_routes_available_in_full_core_api": True,
        "cross_plane_claim_gate": _claim_gate(
            "desktop_control_plane.marketplace_status",
            ("production_readiness", "settlement_finality", "customer_traffic"),
        ),
    }


@app.get("/api/v1/maas/marketplace/search")
async def marketplace_search() -> list[dict[str, Any]]:
    return []


@app.get("/api/v1/maas/billing/billing/plans")
async def billing_plans() -> list[dict[str, Any]]:
    return [
        {
            "name": "free",
            "limits": {"meshes": 1, "nodes_per_mesh": 3, "bandwidth_gb": 10},
        },
        {
            "name": "pro",
            "limits": {"meshes": 10, "nodes_per_mesh": 50, "bandwidth_gb": 1000},
        },
        {
            "name": "enterprise",
            "limits": {
                "meshes": "custom",
                "nodes_per_mesh": "custom",
                "bandwidth_gb": "custom",
            },
        },
    ]


@app.get("/api/v1/maas/billing/usage")
async def billing_usage() -> dict[str, Any]:
    return {
        "status": "desktop_read_only",
        "owner_id": "local-desktop",
        "mesh_count": 0,
        "meshes": [],
        "total_node_hours": 0,
        "generated_at": datetime.now(timezone.utc).isoformat(),
        "cross_plane_claim_gate": _claim_gate(
            "desktop_control_plane.billing_usage",
            ("settlement_finality", "production_readiness"),
        ),
    }


@app.get("/api/v1/maas/governance/readiness")
async def governance_readiness() -> dict[str, Any]:
    return {
        "status": "desktop_read_only",
        "ready": False,
        "proposal_read_endpoint": "/api/v1/maas/governance/proposals",
        "execution_requires_full_core_api": True,
        "cross_plane_claim_gate": _claim_gate(
            "desktop_control_plane.governance_readiness",
            ("production_readiness", "trust_finality"),
        ),
    }


@app.get("/api/v1/maas/governance/proposals")
async def governance_proposals() -> dict[str, Any]:
    return {"proposals": []}


@app.get("/api/v1/maas/agents/health/status")
async def agent_health_status() -> dict[str, Any]:
    return {
        "status": "desktop_read_only",
        "agent_mesh_ready": False,
        "full_agent_runtime_required": True,
        "cross_plane_claim_gate": _claim_gate(
            "desktop_control_plane.agent_health_status",
            ("production_readiness",),
        ),
    }


@app.get("/api/v1/service-identity/status")
async def service_identity_status() -> dict[str, Any]:
    return {
        "status": "desktop_read_only",
        "spiffe_domain": "spiffe://x0tta6bl4.mesh",
        "live_spire_svid_confirmed": False,
        "full_spire_runtime_required": True,
        "cross_plane_claim_gate": _claim_gate(
            "desktop_control_plane.service_identity_status",
            ("production_readiness", "trust_finality"),
        ),
    }


@app.get("/api/v1/vpn/readiness")
async def vpn_readiness() -> dict[str, Any]:
    return {
        "status": "desktop_read_only",
        "ready": False,
        "runtime_state_present": RUNTIME_STATE_PATH.is_file(),
        "cross_plane_claim_gate": _claim_gate(
            "desktop_control_plane.vpn_readiness",
            ("traffic_delivery", "customer_traffic", "dpi_bypass"),
        ),
    }


_include_router(
    "src.api.maas.endpoints.marketplace",
    "/api/v1/maas/marketplace",
    "marketplace",
)
_include_router("src.api.maas.endpoints.billing", "/api/v1/maas/billing", "billing")
_include_router(
    "src.api.maas.endpoints.governance",
    "/api/v1/maas/governance",
    "governance",
)
_include_router("src.api.maas.endpoints.agent_mesh", "/api/v1/maas/agents", "agent_mesh")
_include_router(
    "src.api.maas.endpoints.provisioning",
    "/api/v1/maas/provisioning",
    "provisioning",
)
_include_router(
    "src.api.maas.endpoints.service_identity_status",
    "/api/v1/service-identity",
    "service_identity",
)
_include_router("src.api.maas.endpoints.vpn", "/api/v1/vpn", "vpn")
