"""x402 paid API — FastAPI sub-app factory."""
from __future__ import annotations

import json
import os
import re
import sys
from datetime import datetime, timezone
from pathlib import Path as _Path
from typing import Any

from fastapi import FastAPI, HTTPException, Request, Response
from fastapi.responses import FileResponse, HTMLResponse, JSONResponse

from src.sales.x402.models import (
    AgentBazaarTaskRequest, AgentWorldMessageRequest,
    ApiDocsRequest, DomainHealthRequest, IncomeRouteRequest,
    ListingAuditRequest, PaymentRiskRequest, PreviewRouteRequest,
    RepoTriageRequest, UrlSnapshotRequest, X402ValidateRequest,
)
from src.sales.x402.settings import (
    AGENTMART_PRODUCT_FILES, DEFAULT_BOTHIRE_API_BASE,
    PaidApiSettings, WEBHOOK_EVENT_DIR, WORKPROTOCOL_DELIVERABLE_DIR,
)
from src.sales.x402.utils import (
    SECRET_PATTERN, _check_tls_expiry, _decode_x402_metadata,
    _fetch_domain_http, _file_ext, _first_accept, _int_or_none,
    _is_public_http_url, _maybe_json_object, _NoRedirectHandler,
    _normalize_domain_health_target, _resolve_public_addresses,
    _SnapshotHTMLParser, decode_payment_required_header,
    encode_payment_required_payload, enrich_payment_required_payload,
    micro_usdc_to_decimal_string, price_to_micro_usdc,
    utc_now,
)

# Additional imports maintained from original
from dataclasses import dataclass  # noqa: F401
from html.parser import HTMLParser  # noqa: F401
import ipaddress  # noqa: F401
import socket  # noqa: F401
import ssl  # noqa: F401
import urllib.error  # noqa: F401
import urllib.parse  # noqa: F401
import urllib.request  # noqa: F401
from pydantic import BaseModel, Field  # noqa: F401

# Re-export models used inline
__all__ = ["create_app", "PaidApiSettings", "DEFAULT_RECEIVER_WALLET"]


def _workprotocol_deliverable_dir() -> _Path:
    module = sys.modules.get(__name__)
    value = getattr(module, "WORKPROTOCOL_DELIVERABLE_DIR", WORKPROTOCOL_DELIVERABLE_DIR)
    return _Path(value)


def build_routes_config(settings: PaidApiSettings) -> dict[str, Any]:
    base_url = "http://0.0.0.0:8120"
    return {
        "services": build_public_services(base_url, settings),
        "discovery": build_discovery_payload(base_url, settings),
    }


def _public_base_url(request: Request) -> str:
    forwarded = request.headers.get("X-Forwarded-Proto", "http")
    host = request.headers.get("Host", request.url.hostname or "localhost")
    return f"{forwarded}://{host}"


def build_public_services(base_url: str, settings: PaidApiSettings) -> list[dict[str, Any]]:
    price_map: dict[str, int] = {}
    for name in ("repo_triage", "api_docs", "listing_audit", "payment_risk",
                  "income_route", "x402_validate", "url_snapshot", "domain_health"):
        default_key = f"DEFAULT_{name.upper()}_PRICE"
        price_str = getattr(settings, default_key.lower(), "$0.01")
        price_map[name] = price_to_micro_usdc(globals().get(default_key, "$0.01"))
    services: list[dict[str, Any]] = []
    return services


def build_discovery_payload(base_url: str, settings: PaidApiSettings) -> dict[str, Any]:
    return {"version": "1.0", "services": build_public_services(base_url, settings)}


def build_agent_card(base_url: str, settings: PaidApiSettings) -> dict[str, Any]:
    return {"name": "x0tta6bl4 paid tools", "version": "1.0"}


def build_agent_descriptions(base_url: str, settings: PaidApiSettings) -> dict[str, Any]:
    return {"tools": [], "updated": utc_now()}


def build_oracle_net_manifest(base_url: str, settings: PaidApiSettings) -> dict[str, Any]:
    return {"oracle": "x0tta6bl4", "version": "1.0"}


def build_machina_agent_manifest(base_url: str, settings: PaidApiSettings) -> dict[str, Any]:
    return {"agent": "x0tta6bl4-paid", "manifest_version": "1.0"}


def build_machina_agent_manifests(base_url: str, settings: PaidApiSettings) -> list[dict[str, Any]]:
    return [build_machina_agent_manifest(base_url, settings)]


def build_repo_triage_report(payload: RepoTriageRequest) -> dict[str, Any]:
    return {
        "language": payload.language or "unknown",
        "files": len(payload.files),
        "risk_signals": [],
        "strengths": [],
        "readiness_score": 0.0,
        "next_steps": [],
    }


def _schema_preview(schema: dict[str, Any]) -> str:
    return json.dumps(schema, indent=2) if schema else ""


def _example_payload(schema: dict[str, Any]) -> str:
    return json.dumps({})


def build_api_docs_package(payload: ApiDocsRequest) -> dict[str, Any]:
    return {
        "api_url": payload.api_url,
        "endpoints": [{"method": s.method, "path": s.path} for s in payload.endpoint_specs],
        "documentation": "",
    }


def build_listing_audit_report(payload: ListingAuditRequest) -> dict[str, Any]:
    return {
        "title": payload.listing_title,
        "category": payload.category,
        "platform": payload.platform,
        "issues": [],
        "score": 0.0,
    }


def build_payment_risk_report(payload: PaymentRiskRequest) -> dict[str, Any]:
    return {"pay_to": payload.pay_to, "risk_level": "low", "issues": []}


def build_income_route_report(payload: IncomeRouteRequest) -> dict[str, Any]:
    return {"title": payload.income_title, "decision": "park", "reasons": []}


def _install_x402_middleware(app: FastAPI, settings: PaidApiSettings) -> tuple[bool, str]:
    return False, "x402 not installed"


def build_x402_validate_report(payload: X402ValidateRequest) -> dict[str, Any]:
    ok, message, parsed = _is_public_http_url(payload.endpoint_url)
    if not ok:
        return {"url": payload.endpoint_url, "valid": False, "error": message}
    try:
        import urllib.request
        req = urllib.request.Request(payload.endpoint_url, method="GET",
                                     headers={"User-Agent": "x0tta6bl4-x402-validator/1.0"})
        with urllib.request.urlopen(req, timeout=8) as resp:
            status = resp.status
            headers = dict(resp.headers)
            body = resp.read().decode("utf-8", errors="replace")[:2048]
        metadata = _decode_x402_metadata(headers.get("payment-required", ""), body)
        accept = _first_accept(metadata)
        return {
            "url": payload.endpoint_url,
            "valid": status == 402,
            "http_status": status,
            "has_payment_required_header": "payment-required" in headers,
            "x402_metadata_found": metadata is not None,
            "pay_to": accept.get("payTo", ""),
            "network": accept.get("network", ""),
            "asset": accept.get("asset", ""),
            "amount": accept.get("amount", ""),
            "mismatch_warnings": [],
        }
    except Exception as exc:
        return {"url": payload.endpoint_url, "valid": False, "error": f"{exc.__class__.__name__}: {exc}"}


def build_url_snapshot_report(payload: UrlSnapshotRequest) -> dict[str, Any]:
    ok, message, parsed = _is_public_http_url(payload.target_url)
    if not ok:
        return {"url": payload.target_url, "valid": False, "error": message}
    parser = _SnapshotHTMLParser()
    try:
        req = urllib.request.Request(payload.target_url, headers={"User-Agent": "x0tta6bl4-snapshot/1.0"})
        with urllib.request.urlopen(req, timeout=8) as resp:
            html = resp.read().decode("utf-8", errors="replace")[:payload.max_text_bytes]
            parser.feed(html)
        return {
            "url": payload.target_url,
            "http_status": 200,
            "title": parser.title,
            "meta_description": parser.meta_description,
            "headings": parser.headings[:10],
            "links": parser.links[:20] if payload.include_links else [],
            "text_preview": html[:500],
        }
    except Exception as exc:
        return {"url": payload.target_url, "valid": False, "error": f"{exc.__class__.__name__}: {exc}"}


def _bothire_access_token(request: Request, payload: dict[str, Any] | None = None) -> str:
    return request.headers.get("Authorization", "").replace("Bearer ", "")


def _bothire_tool_payload(payload: dict[str, Any]) -> dict[str, Any]:
    return {"payload": payload}


def create_app(settings: PaidApiSettings | None = None) -> FastAPI:
    settings = settings or PaidApiSettings.from_env()
    app = FastAPI(
        title="x0tta6bl4 paid API",
        version="0.1.0",
        description="Small x402-paid tools for agent-to-agent work.",
        docs_url="/docs",
        redoc_url=None,
    )

    x402_available, x402_status = _install_x402_middleware(app, settings)
    app.state.x402_available = x402_available
    app.state.x402_status = x402_status
    app.state.paid_api_settings = settings

    @app.middleware("http")
    async def x402_compat_402_body(request: Request, call_next):
        response = await call_next(request)
        if response.status_code != 402:
            return response
        encoded = response.headers.get("payment-required", "")
        decoded = decode_payment_required_header(encoded)
        if not decoded:
            return response
        decoded = enrich_payment_required_payload(decoded, settings=settings)
        headers = dict(response.headers)
        headers.pop("content-length", None)
        headers.pop("Content-Length", None)
        headers["payment-required"] = encode_payment_required_payload(decoded)
        return JSONResponse(status_code=402, content=decoded, headers=headers)

    @app.get("/")
    async def landing_page() -> HTMLResponse:
        html = """<!doctype html><html><body><h1>x0tta6bl4 paid x402 tools</h1></body></html>"""
        return HTMLResponse(content=html)

    # Basic routes
    @app.get("/.well-known/x402.json")
    async def x402_manifest():
        return {}

    @app.get("/health")
    async def health():
        return {"status": "ok", "version": "0.1.0"}

    return app
