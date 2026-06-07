"""Small x402-paid API surface for x0tta6bl4 agent monetization."""

from __future__ import annotations

import base64
import binascii
from html.parser import HTMLParser
import ipaddress
import os
import re
import socket
import ssl
import sys
import urllib.error
import urllib.parse
import urllib.request
from dataclasses import dataclass
from datetime import datetime, timezone
import json
from pathlib import Path
from pathlib import PurePosixPath
from typing import Any

from fastapi import FastAPI, HTTPException, Request, Response
from fastapi.responses import FileResponse, HTMLResponse, JSONResponse, PlainTextResponse
from pydantic import BaseModel, Field


DEFAULT_RECEIVER_WALLET = "0x6017613e80d7893EB2aD5c0585b3f1f88CD6e099"
DEFAULT_FACILITATOR_URL = "https://facilitator.openx402.ai"
DEFAULT_NETWORK = "eip155:8453"  # Base mainnet
USDC_ASSET_ADDRESS = "0x833589fCD6eDb6E08f4c7C32D4f71b54bdA02913"
DEFAULT_REPO_TRIAGE_PRICE = "$0.02"
DEFAULT_API_DOCS_PRICE = "$0.03"
DEFAULT_LISTING_AUDIT_PRICE = "$0.02"
DEFAULT_PAYMENT_RISK_PRICE = "$0.02"
DEFAULT_INCOME_ROUTE_PRICE = "$0.02"
DEFAULT_X402_VALIDATE_PRICE = "$0.01"
DEFAULT_URL_SNAPSHOT_PRICE = "$0.01"
DEFAULT_DOMAIN_HEALTH_PRICE = "$0.001"
DEFAULT_BOTHIRE_API_BASE = "https://www.bothire.io"
WEBHOOK_EVENT_DIR = Path(".tmp/non-bounty/webhooks")
WORKPROTOCOL_DELIVERABLE_DIR = Path(".tmp/non-bounty/workprotocol_deliverables")
AGENTMART_PRODUCT_FILES = {
    "x402_micro_api_seller_pack.md": Path("docs/commercial/agentmart_products/x402_micro_api_seller_pack.md"),
    "public_url_snapshot_buyer_kit.md": Path("docs/commercial/agentmart_products/public_url_snapshot_buyer_kit.md"),
    "domain_health_lite_workflow.md": Path("docs/commercial/agentmart_products/domain_health_lite_workflow.md"),
}


def _workprotocol_deliverable_dir() -> Path:
    module = sys.modules.get(__name__)
    value = getattr(module, "WORKPROTOCOL_DELIVERABLE_DIR", WORKPROTOCOL_DELIVERABLE_DIR)
    return Path(value)


SECRET_PATTERN = re.compile(
    r"(api[_-]?key|private[_-]?key|secret|token|password|bearer\s+[a-z0-9._-]+)",
    re.IGNORECASE,
)


@dataclass(frozen=True)
class PaidApiSettings:
    pay_to: str = DEFAULT_RECEIVER_WALLET
    network: str = DEFAULT_NETWORK
    facilitator_url: str = DEFAULT_FACILITATOR_URL
    repo_triage_price: str = DEFAULT_REPO_TRIAGE_PRICE
    api_docs_price: str = DEFAULT_API_DOCS_PRICE
    listing_audit_price: str = DEFAULT_LISTING_AUDIT_PRICE
    payment_risk_price: str = DEFAULT_PAYMENT_RISK_PRICE
    income_route_price: str = DEFAULT_INCOME_ROUTE_PRICE
    x402_validate_price: str = DEFAULT_X402_VALIDATE_PRICE
    url_snapshot_price: str = DEFAULT_URL_SNAPSHOT_PRICE
    domain_health_price: str = DEFAULT_DOMAIN_HEALTH_PRICE
    x402_enabled: bool = True
    allow_unpaid_dev: bool = False
    bothire_verify_access: bool = True
    bothire_api_base: str = DEFAULT_BOTHIRE_API_BASE

    @classmethod
    def from_env(cls) -> "PaidApiSettings":
        return cls(
            pay_to=os.getenv("X0T_X402_PAY_TO", DEFAULT_RECEIVER_WALLET),
            network=os.getenv("X0T_X402_NETWORK", DEFAULT_NETWORK),
            facilitator_url=os.getenv("X0T_X402_FACILITATOR_URL", DEFAULT_FACILITATOR_URL),
            repo_triage_price=os.getenv("X0T_X402_REPO_TRIAGE_PRICE", DEFAULT_REPO_TRIAGE_PRICE),
            api_docs_price=os.getenv("X0T_X402_API_DOCS_PRICE", DEFAULT_API_DOCS_PRICE),
            listing_audit_price=os.getenv("X0T_X402_LISTING_AUDIT_PRICE", DEFAULT_LISTING_AUDIT_PRICE),
            payment_risk_price=os.getenv("X0T_X402_PAYMENT_RISK_PRICE", DEFAULT_PAYMENT_RISK_PRICE),
            income_route_price=os.getenv("X0T_X402_INCOME_ROUTE_PRICE", DEFAULT_INCOME_ROUTE_PRICE),
            x402_validate_price=os.getenv("X0T_X402_VALIDATE_PRICE", DEFAULT_X402_VALIDATE_PRICE),
            url_snapshot_price=os.getenv("X0T_X402_URL_SNAPSHOT_PRICE", DEFAULT_URL_SNAPSHOT_PRICE),
            domain_health_price=os.getenv("X0T_X402_DOMAIN_HEALTH_PRICE", DEFAULT_DOMAIN_HEALTH_PRICE),
            x402_enabled=os.getenv("X0T_X402_ENABLED", "true").lower()
            not in {"0", "false", "no"},
            allow_unpaid_dev=os.getenv("X0T_X402_ALLOW_UNPAID_DEV", "false").lower()
            in {"1", "true", "yes"},
            bothire_verify_access=os.getenv("X0T_BOTHIRE_VERIFY_ACCESS", "true").lower()
            not in {"0", "false", "no"},
            bothire_api_base=os.getenv("X0T_BOTHIRE_API_BASE", DEFAULT_BOTHIRE_API_BASE),
        )


def utc_now() -> str:
    return datetime.now(timezone.utc).replace(microsecond=0).isoformat().replace("+00:00", "Z")


def price_to_micro_usdc(price: str | float | int) -> int:
    if isinstance(price, str):
        price_value = float(price.strip().replace("$", ""))
    else:
        price_value = float(price)
    return int(round(price_value * 1_000_000))


def micro_usdc_to_decimal_string(amount: int) -> str:
    value = amount / 1_000_000
    return f"{value:.6f}".rstrip("0").rstrip(".")


def encode_payment_required_payload(payload: dict[str, Any]) -> str:
    raw = json.dumps(payload, separators=(",", ":"), ensure_ascii=False).encode("utf-8")
    return base64.b64encode(raw).decode("ascii")


def enrich_payment_required_payload(
    payload: dict[str, Any],
    *,
    settings: PaidApiSettings,
) -> dict[str, Any]:
    enriched = json.loads(json.dumps(payload))
    resource = enriched.get("resource") if isinstance(enriched.get("resource"), dict) else {}
    resource_url = str(resource.get("url") or resource.get("resource") or "")
    description = str(resource.get("description") or "")
    mime_type = str(resource.get("mimeType") or "application/json")
    accepts = enriched.get("accepts")
    if isinstance(accepts, list):
        for item in accepts:
            if not isinstance(item, dict):
                continue
            amount = str(item.get("amount") or item.get("maxAmountRequired") or "0")
            item.setdefault("maxAmountRequired", amount)
            item.setdefault("description", description)
            item.setdefault("mimeType", mime_type)
            item.setdefault("resource", resource_url)
            item.setdefault("facilitator", settings.facilitator_url)
    enriched.setdefault("facilitator", settings.facilitator_url)
    return enriched


class FileSnippet(BaseModel):
    path: str = Field(..., min_length=1, max_length=240)
    text: str = Field(..., max_length=20_000)


class RepoTriageRequest(BaseModel):
    repo_url: str | None = Field(default=None, max_length=500)
    files: list[FileSnippet] = Field(default_factory=list, max_length=80)
    focus: list[str] = Field(default_factory=list, max_length=12)


class ApiEndpointSpec(BaseModel):
    method: str = Field(..., min_length=3, max_length=8)
    path: str = Field(..., min_length=1, max_length=240)
    summary: str = Field(default="", max_length=500)
    auth: str = Field(default="", max_length=160)
    request_schema: dict[str, Any] = Field(default_factory=dict)
    response_schema: dict[str, Any] = Field(default_factory=dict)
    errors: list[str] = Field(default_factory=list, max_length=20)


class ApiDocsRequest(BaseModel):
    service_name: str = Field(..., min_length=1, max_length=120)
    base_url: str | None = Field(default=None, max_length=500)
    auth_guide: str = Field(default="", max_length=2000)
    endpoints: list[ApiEndpointSpec] = Field(default_factory=list, min_length=1, max_length=80)
    languages: list[str] = Field(default_factory=lambda: ["curl", "python", "javascript"], max_length=6)


class ListingAuditRequest(BaseModel):
    listing_url: str | None = Field(default=None, max_length=500)
    profile_text: str = Field(..., min_length=1, max_length=12_000)
    target_buyer: str = Field(default="", max_length=500)
    price_usdc: float | None = Field(default=None, ge=0, le=10_000)


class PaymentRiskRequest(BaseModel):
    resource_url: str | None = Field(default=None, max_length=500)
    pay_to: str | None = Field(default=None, max_length=80)
    amount: int | None = Field(default=None, ge=0, le=10_000_000_000)
    network: str | None = Field(default=None, max_length=80)
    asset: str | None = Field(default=None, max_length=120)
    service_name: str = Field(default="", max_length=160)
    description: str = Field(default="", max_length=2_000)
    tags: list[str] = Field(default_factory=list, max_length=30)


class IncomeRouteRequest(BaseModel):
    opportunity_title: str = Field(..., min_length=1, max_length=240)
    description: str = Field(..., min_length=1, max_length=4_000)
    source_url: str | None = Field(default=None, max_length=500)
    payout_usdc: float | None = Field(default=None, ge=0, le=100_000)
    required_upfront_usdc: float = Field(default=0, ge=0, le=100_000)
    estimated_token_cost: int = Field(default=0, ge=0, le=5_000_000)
    estimated_minutes: int = Field(default=0, ge=0, le=100_000)
    payout_type: str = Field(default="", max_length=80)
    buyer_type: str = Field(default="", max_length=160)
    payment_rail: str = Field(default="", max_length=160)
    deliverable_type: str = Field(default="", max_length=160)
    tags: list[str] = Field(default_factory=list, max_length=30)


class X402ValidateRequest(BaseModel):
    url: str = Field(..., min_length=8, max_length=500)
    method: str = Field(default="GET", pattern="^(GET|HEAD|get|head)$")
    expected_pay_to: str | None = Field(default=None, max_length=80)
    expected_network: str = Field(default=DEFAULT_NETWORK, max_length=80)
    max_amount_micro_usdc: int | None = Field(default=None, ge=0, le=10_000_000_000)


class UrlSnapshotRequest(BaseModel):
    url: str = Field(..., min_length=8, max_length=500)
    max_links: int = Field(default=12, ge=0, le=50)
    max_text_chars: int = Field(default=1200, ge=0, le=5000)


class DomainHealthRequest(BaseModel):
    target: str = Field(..., min_length=3, max_length=500)
    fetch_http: bool = True
    check_tls: bool = True


class AgentWorldMessageRequest(BaseModel):
    message: str = Field(..., min_length=1, max_length=4_000)
    from_agent: str = Field(default="", max_length=160)
    from_wallet: str | None = Field(default=None, max_length=80)
    context: str = Field(default="", max_length=4_000)


class PreviewRouteRequest(BaseModel):
    message: str = Field(..., min_length=1, max_length=3_000)
    public_url: str | None = Field(default=None, max_length=500)
    snippet: str = Field(default="", max_length=4_000)


class AgentBazaarTaskRequest(BaseModel):
    task: str = Field(default="", max_length=8_000)
    message: str = Field(default="", max_length=8_000)
    files: list[dict[str, Any]] = Field(default_factory=list, max_length=20)
    buyer: str | None = Field(default=None, max_length=160)
    jobId: str | int | None = None
    payload: dict[str, Any] = Field(default_factory=dict)


def build_routes_config(settings: PaidApiSettings) -> dict[str, Any]:
    repo_triage = {
        "accepts": {
            "scheme": "exact",
            "payTo": settings.pay_to,
            "price": settings.repo_triage_price,
            "network": settings.network,
        },
        "resource": "/paid/repo-triage",
        "description": (
            "x0tta6bl4 repo triage: accepts file snippets and returns a compact "
            "engineering risk report."
        ),
        "mimeType": "application/json",
        "serviceName": "x0t repo triage",
        "tags": ["python", "repo", "triage", "tests", "docs"],
    }
    api_docs = {
        "accepts": {
            "scheme": "exact",
            "payTo": settings.pay_to,
            "price": settings.api_docs_price,
            "network": settings.network,
        },
        "resource": "/paid/api-docs",
        "description": (
            "x0tta6bl4 API docs generator: accepts endpoint specs and returns "
            "clean Markdown docs with examples."
        ),
        "mimeType": "application/json",
        "serviceName": "x0t api docs",
        "tags": ["api", "docs", "openapi", "python", "javascript"],
    }
    listing_audit = {
        "accepts": {
            "scheme": "exact",
            "payTo": settings.pay_to,
            "price": settings.listing_audit_price,
            "network": settings.network,
        },
        "resource": "/paid/listing-audit",
        "description": (
            "x0tta6bl4 listing audit: accepts marketplace/profile text and returns "
            "a conversion scorecard for agent-service listings."
        ),
        "mimeType": "application/json",
        "serviceName": "x0t listing audit",
        "tags": ["agent", "marketplace", "listing", "copy", "conversion"],
    }
    payment_risk = {
        "accepts": {
            "scheme": "exact",
            "payTo": settings.pay_to,
            "price": settings.payment_risk_price,
            "network": settings.network,
        },
        "resource": "/paid/payment-risk",
        "description": (
            "x0tta6bl4 payment risk: accepts public x402/payment metadata and returns "
            "a compact spend-risk report for autonomous wallet decisions."
        ),
        "mimeType": "application/json",
        "serviceName": "x0t payment risk",
        "tags": ["x402", "wallet", "payment", "risk", "base"],
    }
    income_route = {
        "accepts": {
            "scheme": "exact",
            "payTo": settings.pay_to,
            "price": settings.income_route_price,
            "network": settings.network,
        },
        "resource": "/paid/income-route",
        "description": (
            "x0tta6bl4 income route: scores a non-bounty earning opportunity by "
            "token cost, upfront cost, automation fit, payment certainty, and refusal triggers."
        ),
        "mimeType": "application/json",
        "serviceName": "x0t income route",
        "tags": ["agent-income", "x402", "roi", "marketplace", "automation"],
    }
    x402_validate = {
        "accepts": {
            "scheme": "exact",
            "payTo": settings.pay_to,
            "price": settings.x402_validate_price,
            "network": settings.network,
        },
        "resource": "/paid/x402-validate",
        "description": (
            "x0tta6bl4 x402 validator: fetches a public endpoint and returns HTTP 402, "
            "Payment-Required, payTo, network, asset, and amount checks."
        ),
        "mimeType": "application/json",
        "serviceName": "x0t x402 validator",
        "tags": ["x402", "validator", "payment", "endpoint", "base"],
    }
    url_snapshot = {
        "accepts": {
            "scheme": "exact",
            "payTo": settings.pay_to,
            "price": settings.url_snapshot_price,
            "network": settings.network,
        },
        "resource": "/paid/url-snapshot",
        "description": (
            "x0tta6bl4 URL snapshot: fetches a public page and returns status, title, "
            "meta description, headings, links, and text preview."
        ),
        "mimeType": "application/json",
        "serviceName": "x0t url snapshot",
        "tags": ["url", "snapshot", "web", "metadata", "agent"],
    }
    domain_health = {
        "accepts": {
            "scheme": "exact",
            "payTo": settings.pay_to,
            "price": settings.domain_health_price,
            "network": settings.network,
        },
        "resource": "/paid/domain-health",
        "description": (
            "x0tta6bl4 Domain Health Lite: checks a public domain or URL for DNS/IP, "
            "HTTP status, redirect, and TLS expiry signals."
        ),
        "mimeType": "application/json",
        "serviceName": "x0t domain health lite",
        "tags": ["domain", "dns", "http", "tls", "health"],
    }
    routes = {
        "GET /paid/repo-triage": repo_triage,
        "POST /paid/repo-triage": {
            **repo_triage,
        },
        "GET /paid/api-docs": api_docs,
        "POST /paid/api-docs": {
            **api_docs,
        },
        "GET /paid/listing-audit": listing_audit,
        "POST /paid/listing-audit": {
            **listing_audit,
        },
        "GET /paid/payment-risk": payment_risk,
        "POST /paid/payment-risk": {
            **payment_risk,
        },
        "GET /paid/income-route": income_route,
        "POST /paid/income-route": {
            **income_route,
        },
        "GET /paid/x402-validate": x402_validate,
        "POST /paid/x402-validate": {
            **x402_validate,
        },
        "GET /paid/url-snapshot": url_snapshot,
        "POST /paid/url-snapshot": {
            **url_snapshot,
        },
        "GET /paid/domain-health": domain_health,
        "POST /paid/domain-health": {
            **domain_health,
        },
    }
    for route in routes.values():
        accepts = route.get("accepts")
        if not isinstance(accepts, dict):
            continue
        amount = str(price_to_micro_usdc(accepts.get("price", 0)))
        accepts.update(
            {
                "asset": USDC_ASSET_ADDRESS,
                "amount": amount,
                "maxAmountRequired": amount,
                "description": route.get("description", ""),
                "mimeType": route.get("mimeType", "application/json"),
                "resource": route.get("resource", ""),
                "facilitator": settings.facilitator_url,
                "maxTimeoutSeconds": 300,
            }
        )
    return routes


def _public_base_url(request: Request) -> str:
    forwarded_proto = request.headers.get("x-forwarded-proto")
    forwarded_host = request.headers.get("x-forwarded-host")
    if forwarded_host:
        scheme = forwarded_proto or "https"
        return f"{scheme}://{forwarded_host}".rstrip("/")
    return str(request.base_url).rstrip("/")


def build_public_services(base_url: str, settings: PaidApiSettings) -> list[dict[str, Any]]:
    services = [
        {
            "id": "x0tta6bl4-repo-triage",
            "name": "x0tta6bl4 Repo Triage",
            "description": (
                "Paid x402 API for compact repository triage from submitted file snippets. "
                "Returns JSON risk signals, strengths, readiness score, and next engineering steps."
            ),
            "url": f"{base_url}/paid/repo-triage",
            "category": "developer-tool",
            "price_usd": float(settings.repo_triage_price.strip("$")),
            "network": "base",
            "x402_network": settings.network,
            "asset_address": USDC_ASSET_ADDRESS,
            "asset_contract": USDC_ASSET_ADDRESS,
            "payment_address": settings.pay_to,
            "tags": ["x402", "python", "repo-triage", "testing", "docs"],
            "capability_tags": ["code-review", "validation", "documentation"],
            "input_format": "json",
            "output_format": "json",
            "pricing_model": "flat",
            "agent_callable": True,
            "auth_required": False,
            "facilitator": settings.facilitator_url,
        },
        {
            "id": "x0tta6bl4-api-docs",
            "name": "x0tta6bl4 API Docs Generator",
            "description": (
                "Paid x402 API that turns REST endpoint specs into clean Markdown documentation "
                "with cURL, Python, and JavaScript examples."
            ),
            "url": f"{base_url}/paid/api-docs",
            "category": "developer-tool",
            "price_usd": float(settings.api_docs_price.strip("$")),
            "network": "base",
            "x402_network": settings.network,
            "asset_address": USDC_ASSET_ADDRESS,
            "asset_contract": USDC_ASSET_ADDRESS,
            "payment_address": settings.pay_to,
            "tags": ["x402", "api-docs", "openapi", "python", "javascript"],
            "capability_tags": ["documentation", "code-generation", "developer-tools"],
            "input_format": "json",
            "output_format": "json",
            "pricing_model": "flat",
            "agent_callable": True,
            "auth_required": False,
            "facilitator": settings.facilitator_url,
        },
        {
            "id": "x0tta6bl4-listing-audit",
            "name": "x0tta6bl4 Agent Listing Audit",
            "description": (
                "Paid x402 API that scores an agent marketplace listing and returns "
                "clear fixes for price, input scope, delivery mode, trust, and conversion."
            ),
            "url": f"{base_url}/paid/listing-audit",
            "category": "business-tool",
            "price_usd": float(settings.listing_audit_price.strip("$")),
            "network": "base",
            "x402_network": settings.network,
            "asset_address": USDC_ASSET_ADDRESS,
            "asset_contract": USDC_ASSET_ADDRESS,
            "payment_address": settings.pay_to,
            "tags": ["x402", "agent-marketplace", "listing-audit", "copywriting", "conversion"],
            "capability_tags": ["marketplace-optimization", "copy-review", "sales"],
            "input_format": "json",
            "output_format": "json",
            "pricing_model": "flat",
            "agent_callable": True,
            "auth_required": False,
            "facilitator": settings.facilitator_url,
        },
        {
            "id": "x0tta6bl4-payment-risk",
            "name": "x0tta6bl4 Payment Risk Report",
            "description": (
                "Paid x402 API that checks public payment metadata and returns a compact "
                "risk report for autonomous wallet approval decisions."
            ),
            "url": f"{base_url}/paid/payment-risk",
            "category": "security",
            "price_usd": float(settings.payment_risk_price.strip("$")),
            "network": "base",
            "x402_network": settings.network,
            "asset_address": USDC_ASSET_ADDRESS,
            "asset_contract": USDC_ASSET_ADDRESS,
            "payment_address": settings.pay_to,
            "tags": ["x402", "payment-risk", "wallet", "base", "security"],
            "capability_tags": ["risk-scoring", "payment-verification", "wallet-safety"],
            "input_format": "json",
            "output_format": "json",
            "pricing_model": "flat",
            "agent_callable": True,
            "auth_required": False,
            "facilitator": settings.facilitator_url,
        },
        {
            "id": "x0tta6bl4-income-route",
            "name": "x0tta6bl4 Income Route",
            "description": (
                "Paid x402 API that scores a non-bounty earning opportunity and returns "
                "a simple take, park, or reject decision by token cost, upfront cost, "
                "automation fit, payment certainty, and safety boundaries."
            ),
            "url": f"{base_url}/paid/income-route",
            "category": "business-tool",
            "price_usd": float(settings.income_route_price.strip("$")),
            "network": "base",
            "x402_network": settings.network,
            "asset_address": USDC_ASSET_ADDRESS,
            "asset_contract": USDC_ASSET_ADDRESS,
            "payment_address": settings.pay_to,
            "tags": ["x402", "agent-income", "roi", "paid-tasks", "automation"],
            "capability_tags": ["opportunity-scoring", "marketplace-routing", "cost-control"],
            "input_format": "json",
            "output_format": "json",
            "pricing_model": "flat",
            "agent_callable": True,
            "auth_required": False,
            "facilitator": settings.facilitator_url,
        },
        {
            "id": "x0tta6bl4-x402-validator",
            "name": "x0tta6bl4 x402 Endpoint Validator",
            "description": (
                "Paid x402 API that checks a public endpoint live and returns HTTP 402, "
                "Payment-Required, payTo, network, asset, amount, and mismatch warnings."
            ),
            "url": f"{base_url}/paid/x402-validate",
            "category": "security",
            "price_usd": float(settings.x402_validate_price.strip("$")),
            "network": "base",
            "x402_network": settings.network,
            "asset_address": USDC_ASSET_ADDRESS,
            "asset_contract": USDC_ASSET_ADDRESS,
            "payment_address": settings.pay_to,
            "tags": ["x402", "validator", "payment-risk", "endpoint", "base-usdc"],
            "capability_tags": ["x402-validation", "payment-verification", "wallet-safety"],
            "input_format": "json",
            "output_format": "json",
            "pricing_model": "flat",
            "agent_callable": True,
            "auth_required": False,
            "facilitator": settings.facilitator_url,
        },
        {
            "id": "x0tta6bl4-url-snapshot",
            "name": "x0tta6bl4 Public URL Snapshot",
            "description": (
                "Paid x402 API that fetches a public URL and returns HTTP status, title, "
                "meta description, headings, links, and text preview for agents."
            ),
            "url": f"{base_url}/paid/url-snapshot",
            "category": "data-tool",
            "price_usd": float(settings.url_snapshot_price.strip("$")),
            "network": "base",
            "x402_network": settings.network,
            "asset_address": USDC_ASSET_ADDRESS,
            "asset_contract": USDC_ASSET_ADDRESS,
            "payment_address": settings.pay_to,
            "tags": ["x402", "url-snapshot", "web-metadata", "agent-data", "base-usdc"],
            "capability_tags": ["web-snapshot", "metadata-extraction", "agent-research"],
            "input_format": "json",
            "output_format": "json",
            "pricing_model": "flat",
            "agent_callable": True,
            "auth_required": False,
            "facilitator": settings.facilitator_url,
        },
        {
            "id": "x0tta6bl4-domain-health",
            "name": "x0tta6bl4 Domain Health Lite",
            "description": (
                "Paid x402 micro-API that checks a public domain or URL for DNS/IP, "
                "HTTP status, redirect, TLS expiry, and private-network refusal signals."
            ),
            "url": f"{base_url}/paid/domain-health",
            "category": "security",
            "price_usd": float(settings.domain_health_price.strip("$")),
            "network": "base",
            "x402_network": settings.network,
            "asset_address": USDC_ASSET_ADDRESS,
            "asset_contract": USDC_ASSET_ADDRESS,
            "payment_address": settings.pay_to,
            "tags": ["x402", "domain-health", "dns", "http", "tls", "base-usdc"],
            "capability_tags": ["domain-health", "dns-check", "tls-check", "agent-research"],
            "input_format": "json",
            "output_format": "json",
            "pricing_model": "flat",
            "agent_callable": True,
            "auth_required": False,
            "facilitator": settings.facilitator_url,
        },
    ]
    for service in services:
        price_micro_usdc = price_to_micro_usdc(service["price_usd"])
        resource_path = urllib.parse.urlparse(service["url"]).path
        accepts = [
            {
                "scheme": "exact",
                "network": settings.network,
                "asset": USDC_ASSET_ADDRESS,
                "amount": str(price_micro_usdc),
                "maxAmountRequired": str(price_micro_usdc),
                "payTo": settings.pay_to,
                "facilitator": settings.facilitator_url,
                "description": service["description"],
                "mimeType": "application/json",
                "resource": resource_path,
                "maxTimeoutSeconds": 300,
                "extra": {"name": "USD Coin", "version": "2"},
            }
        ]
        service.update(
            {
                "chain": "Base",
                "chain_id": 8453,
                "network_aliases": ["base", "base-mainnet", settings.network],
                "asset_symbol": "USDC",
                "asset_decimals": 6,
                "price_micro_usdc": price_micro_usdc,
                "price_atomic": price_micro_usdc,
                "price_usdc": micro_usdc_to_decimal_string(price_micro_usdc),
                "priceUsd": f"${float(service['price_usd']):.3f}".rstrip("0").rstrip("."),
                "pay_to": settings.pay_to,
                "endpoint": service["url"],
                "method": "POST",
                "resource": resource_path,
                "mimeType": "application/json",
                "accepts": accepts,
            }
        )
    return services


def build_discovery_payload(base_url: str, settings: PaidApiSettings) -> dict[str, Any]:
    services = build_public_services(base_url, settings)
    for service in services:
        service["endpoints"] = [
            {
                "url": service["url"],
                "method": "POST",
                "description": service["description"],
                "pricing": {
                    "amount": str(service["price_usd"]),
                    "currency": "USDC",
                    "network": settings.network,
                    "scheme": "exact",
                },
            }
        ]
    resources = [
        {
            "name": service["name"],
            "description": service["description"],
            "url": service["url"],
            "path": urllib.parse.urlparse(service["url"]).path,
            "method": "POST",
            "type": "http",
            "mimeType": "application/json",
            "input_format": service["input_format"],
            "output_format": service["output_format"],
            "tags": service["tags"],
            "capabilities": service["capability_tags"],
            "pricing": {
                "price": str(service["price_usd"]),
                "currency": "USDC",
                "network": "base",
            },
            "x402": {
                "scheme": "exact",
                "network": settings.network,
                "asset": USDC_ASSET_ADDRESS,
                "amount": str(price_to_micro_usdc(service["price_usd"])),
                "maxAmountRequired": str(price_to_micro_usdc(service["price_usd"])),
                "payTo": settings.pay_to,
                "facilitator": settings.facilitator_url,
                "description": service["description"],
                "mimeType": "application/json",
                "resource": urllib.parse.urlparse(service["url"]).path,
                "maxTimeoutSeconds": 300,
            },
        }
        for service in services
    ]
    timestamp = utc_now()
    return {
        "name": "x0tta6bl4 paid x402 tools",
        "description": (
            "Public-input x402 paid tools for repository triage, API docs, "
            "agent listing audits, payment-risk checks, income-route scoring, "
            "x402 validation, URL snapshots, and domain health checks."
        ),
        "network": "base",
        "chain": "Base",
        "chain_id": 8453,
        "network_aliases": ["base", "base-mainnet", settings.network],
        "currency": "USDC",
        "asset_symbol": "USDC",
        "asset_address": USDC_ASSET_ADDRESS,
        "pay_to": settings.pay_to,
        "facilitator": {
            "default": settings.facilitator_url,
            "url": settings.facilitator_url,
            "type": "hosted",
        },
        "facilitator_url": settings.facilitator_url,
        "generated_at": timestamp,
        "updated_at": timestamp,
        "last_updated": timestamp,
        "dateModified": timestamp,
        "version": "1.0",
        "documentation": f"{base_url}/docs",
        "instructions": (
            "Choose a resource, send a POST JSON request to its URL, and pay the "
            "advertised x402 exact USDC amount on Base. Public inputs only; do not "
            "send secrets, private account data, CAPTCHA tasks, spam tasks, or "
            "harmful automation requests."
        ),
        "resources": resources,
        "capabilities": sorted({tag for service in services for tag in service["capability_tags"]}),
        "category": "developer-tools",
        "pricing": {
            "price": str(min(service["price_usd"] for service in services)),
            "currency": "USDC",
        },
        "discovery_provider": "x0tta6bl4 paid API",
        "discovery_url": f"{base_url}/.well-known/x402-discovery",
        "x402_json_url": f"{base_url}/.well-known/x402.json",
        "total_services": len(services),
        "services": services,
        "x402Version": 2,
        "items": [
            {
                "resource": service["url"],
                "type": "http",
                "x402Version": 2,
                "metadata": {
                    "name": service["name"],
                    "description": service["description"],
                    "tags": service["tags"],
                    "capability_tags": service["capability_tags"],
                    "input_format": service["input_format"],
                    "output_format": service["output_format"],
                },
                "accepts": [
                    {
                        "scheme": "exact",
                        "network": settings.network,
                        "asset": USDC_ASSET_ADDRESS,
                        "amount": str(price_to_micro_usdc(service["price_usd"])),
                        "maxAmountRequired": str(price_to_micro_usdc(service["price_usd"])),
                        "payTo": settings.pay_to,
                        "facilitator": settings.facilitator_url,
                        "description": service["description"],
                        "mimeType": "application/json",
                        "resource": urllib.parse.urlparse(service["url"]).path,
                        "maxTimeoutSeconds": 300,
                        "extra": {"name": "USD Coin", "version": "2"},
                    }
                ],
            }
            for service in services
        ],
    }


def build_agent_card(base_url: str, settings: PaidApiSettings) -> dict[str, Any]:
    services = build_public_services(base_url, settings)
    return {
        "schema": "x0tta6bl4.agent_card.v1",
        "name": "x0tta6bl4-paid-tools",
        "description": (
            "Autonomous paid tools for API docs generation, repository triage, "
            "agent listing audits, payment risk checks, income-route scoring, live x402 validation, "
            "and public URL snapshots. "
            "Public inputs only; no secrets, CAPTCHA, spam, KYC bypass, private "
            "accounts, or harmful automation."
        ),
        "provider": {
            "organization": "x0tta6bl4",
            "url": base_url,
        },
        "wallet": settings.pay_to,
        "network": settings.network,
        "protocols": ["x402", "http-json"],
        "security": ["x402"],
        "securitySchemes": {
            "x402": {
                "type": "x402",
                "description": "USDC payment via x402 exact payment on Base.",
                "network": settings.network,
                "asset": "0x833589fCD6eDb6E08f4c7C32D4f71b54bdA02913",
                "payTo": settings.pay_to,
            }
        },
        "skills": [
            {
                "id": item["id"],
                "name": item["name"],
                "description": item["description"],
                "endpoint": item["url"],
                "method": "POST",
                "price_usd": item["price_usd"],
                "pricing_model": item["pricing_model"],
                "input_format": item["input_format"],
                "output_format": item["output_format"],
                "tags": item["tags"],
            }
            for item in services
        ],
        "endpoints": {
            "x402_discovery": f"{base_url}/.well-known/x402-discovery",
            "x402_json": f"{base_url}/.well-known/x402.json",
            "mcp_server_json": f"{base_url}/.well-known/mcp/server.json",
            "agent_descriptions": f"{base_url}/.well-known/agent-descriptions",
            "agent_pulse": f"{base_url}/.well-known/agent-pulse",
            "oracle_net": f"{base_url}/.well-known/oracle-net.json",
            "jwks": f"{base_url}/.well-known/jwks.json",
            "mcp_manifest": f"{base_url}/mcp-manifest",
            "llms_txt": f"{base_url}/llms.txt",
            "agentbazaar_task": f"{base_url}/agentbazaar/task",
            "clustly_webhook": f"{base_url}/clustly/webhook",
            "agoragentic_webhook": f"{base_url}/agoragentic/webhook",
            "agentpact_webhook": f"{base_url}/agentpact/webhook",
            "agentworld_message": f"{base_url}/agentworld/message",
            "payanagent_webhook": f"{base_url}/payanagent/webhook",
            "free_preview": f"{base_url}/preview/route",
        },
        "claim_boundary": (
            "This card advertises available services. It does not prove buyer traffic, "
            "payment settlement, on-chain payout, or received funds."
        ),
    }


def build_agent_descriptions(base_url: str, settings: PaidApiSettings) -> dict[str, Any]:
    services = build_public_services(base_url, settings)
    return {
        "@context": [
            "https://schema.org",
            {
                "x402": "https://www.x402.org/",
                "payTo": "x402:payTo",
                "network": "x402:network",
                "facilitator": "x402:facilitator",
            },
        ],
        "@type": "Service",
        "@id": f"{base_url}/.well-known/agent-descriptions#x0tta6bl4-paid-tools",
        "name": "x0tta6bl4 paid x402 tools",
        "description": (
            "Public-input paid developer tools for autonomous agents: API docs, "
            "repo triage, marketplace listing audits, payment risk checks, "
            "x402 endpoint validation, URL snapshots, and domain health."
        ),
        "provider": {
            "@type": "Organization",
            "name": "x0tta6bl4",
            "url": base_url,
        },
        "serviceType": "x402 paid API",
        "areaServed": "Internet",
        "url": base_url,
        "documentation": f"{base_url}/docs",
        "network": settings.network,
        "payTo": settings.pay_to,
        "facilitator": settings.facilitator_url,
        "offers": [
            {
                "@type": "Offer",
                "name": service["name"],
                "description": service["description"],
                "price": str(service["price_usd"]),
                "priceCurrency": "USDC",
                "url": service["url"],
                "category": service["category"],
                "acceptedPaymentMethod": "x402 exact USDC on Base",
            }
            for service in services
        ],
        "sameAs": [
            f"{base_url}/.well-known/x402.json",
            f"{base_url}/.well-known/agent.json",
            f"{base_url}/.well-known/openapi.json",
            f"{base_url}/.well-known/mcp/server.json",
            f"{base_url}/llms.txt",
        ],
        "claim_boundary": (
            "This JSON-LD advertises service discovery metadata only. It does not "
            "prove buyer traffic, payment settlement, on-chain payout, or received funds."
        ),
    }


def build_oracle_net_manifest(base_url: str, settings: PaidApiSettings) -> dict[str, Any]:
    host = urllib.parse.urlparse(base_url).netloc or base_url.removeprefix("https://")
    return {
        "schema": "x0tta6bl4.oracle_net_manifest.v1",
        "name": "x0tta6bl4 paid x402 tools",
        "description": "Machine-readable discovery manifest for paid x402 developer tools.",
        "did": f"did:web:{host}",
        "origin": base_url,
        "agent_card": f"{base_url}/.well-known/agent.json",
        "agent_descriptions": f"{base_url}/.well-known/agent-descriptions",
        "mcp_server": f"{base_url}/.well-known/mcp/server.json",
        "x402_discovery": f"{base_url}/.well-known/x402-discovery",
        "jwks": f"{base_url}/.well-known/jwks.json",
        "network": settings.network,
        "asset": USDC_ASSET_ADDRESS,
        "payTo": settings.pay_to,
        "facilitator": settings.facilitator_url,
        "services": build_public_services(base_url, settings),
        "claim_boundary": (
            "This manifest is for discovery and routing. It does not claim oracle "
            "attestation, escrow, buyer traffic, settlement, or received funds."
        ),
    }


def build_machina_agent_manifest(
    base_url: str,
    settings: PaidApiSettings,
    service_id: str = "x0tta6bl4-domain-health",
) -> dict[str, Any]:
    services = build_public_services(base_url, settings)
    service = next((item for item in services if item["id"] == service_id), None)
    if service is None:
        raise KeyError(f"unknown Machina service id: {service_id}")
    capabilities = sorted(set(service["capability_tags"] + service["tags"]))
    resource = str(service["resource"])
    return {
        "name": service["name"],
        "description": service["description"],
        "endpoint": service["url"],
        "capabilities": capabilities[:12],
        "tags": service["tags"],
        "pricing": {
            "model": "per-call",
            "amount": float(service["price_usd"]),
            "currency": "USDC",
            "network": settings.network,
        },
        "payment": {
            "scheme": "exact",
            "network": settings.network,
            "receive_address": settings.pay_to,
            "payTo": settings.pay_to,
            "asset": USDC_ASSET_ADDRESS,
            "facilitator": settings.facilitator_url,
        },
        "routes": {
            f"POST {resource}": {
                "description": service["description"],
                "params": {
                    "input": "Send a public JSON payload matching this tool. Do not send secrets.",
                },
                "returns": "JSON result for the paid tool.",
            }
        },
        "version": "2.0.0",
    }


def build_machina_agent_manifests(base_url: str, settings: PaidApiSettings) -> list[dict[str, Any]]:
    return [
        build_machina_agent_manifest(base_url, settings, service["id"])
        for service in build_public_services(base_url, settings)
    ]


def _file_ext(path: str) -> str:
    suffix = PurePosixPath(path).suffix.lower().lstrip(".")
    return suffix or "no_ext"


def build_repo_triage_report(payload: RepoTriageRequest) -> dict[str, Any]:
    file_count = len(payload.files)
    extensions: dict[str, int] = {}
    paths = [item.path for item in payload.files]
    joined_text = "\n".join(item.text[:4000] for item in payload.files)
    lower_paths = [path.lower() for path in paths]

    for item in payload.files:
        ext = _file_ext(item.path)
        extensions[ext] = extensions.get(ext, 0) + 1

    has_tests = any("/test" in path or path.startswith("test") or "_test." in path for path in lower_paths)
    has_python_project = any(path.endswith(("pyproject.toml", "requirements.txt")) for path in lower_paths)
    has_node_project = any(path.endswith(("package.json", "pnpm-lock.yaml", "yarn.lock")) for path in lower_paths)
    has_docker = any("dockerfile" in path or "docker-compose" in path for path in lower_paths)
    has_ci = any(".github/workflows/" in path or ".gitlab-ci" in path for path in lower_paths)
    possible_secret = bool(SECRET_PATTERN.search(joined_text))

    risks: list[str] = []
    if file_count == 0:
        risks.append("No files were supplied; report is only a request-shape check.")
    if not has_tests:
        risks.append("No obvious tests supplied.")
    if not has_ci:
        risks.append("No CI workflow supplied.")
    if possible_secret:
        risks.append("Possible secret-like text detected in submitted snippets; rotate real secrets.")
    if has_docker and not has_ci:
        risks.append("Docker/deploy files appear without matching CI evidence.")

    strengths: list[str] = []
    if has_python_project:
        strengths.append("Python project metadata detected.")
    if has_node_project:
        strengths.append("Node project metadata detected.")
    if has_tests:
        strengths.append("Test files detected.")
    if has_ci:
        strengths.append("CI workflow detected.")
    if has_docker:
        strengths.append("Container/deploy files detected.")

    suggested_next_steps = [
        "Add a minimal smoke test command if tests are missing.",
        "Add CI that runs formatting and focused tests on pull requests.",
        "Keep secrets out of snippets and logs; use local environment variables.",
    ]
    if payload.focus:
        suggested_next_steps.insert(0, f"Prioritize requested focus: {', '.join(payload.focus[:5])}.")

    readiness_score = 100
    readiness_score -= 20 if not has_tests else 0
    readiness_score -= 15 if not has_ci else 0
    readiness_score -= 25 if possible_secret else 0
    readiness_score -= 15 if file_count == 0 else 0
    readiness_score = max(0, readiness_score)

    return {
        "schema": "x0tta6bl4.paid_repo_triage_report.v1",
        "repo_url": payload.repo_url,
        "files_seen": file_count,
        "extensions": dict(sorted(extensions.items())),
        "signals": {
            "has_tests": has_tests,
            "has_python_project": has_python_project,
            "has_node_project": has_node_project,
            "has_docker": has_docker,
            "has_ci": has_ci,
            "possible_secret": possible_secret,
        },
        "readiness_score": readiness_score,
        "strengths": strengths,
        "risks": risks,
        "suggested_next_steps": suggested_next_steps,
        "claim_boundary": (
            "This is a static triage of submitted snippets. It does not prove the full "
            "repository state, build success, security, production readiness, or payout."
        ),
    }


def _schema_preview(schema: dict[str, Any]) -> str:
    if not schema:
        return "{}"
    try:
        import json

        return json.dumps(schema, indent=2, sort_keys=True)[:1600]
    except TypeError:
        return "{}"


def _example_payload(schema: dict[str, Any]) -> str:
    properties = schema.get("properties") if isinstance(schema, dict) else None
    if not isinstance(properties, dict):
        return "{}"
    example: dict[str, Any] = {}
    for key, value in list(properties.items())[:8]:
        if not isinstance(value, dict):
            example[key] = "value"
            continue
        typ = value.get("type")
        if typ == "integer":
            example[key] = 1
        elif typ == "number":
            example[key] = 1.0
        elif typ == "boolean":
            example[key] = True
        elif typ == "array":
            example[key] = []
        elif typ == "object":
            example[key] = {}
        else:
            example[key] = value.get("example", "value")
    return _schema_preview(example)


def build_api_docs_package(payload: ApiDocsRequest) -> dict[str, Any]:
    base_url = (payload.base_url or "https://api.example.com").rstrip("/")
    lines: list[str] = [
        f"# {payload.service_name} API",
        "",
        "## Overview",
        "",
        f"Base URL: `{base_url}`",
        "",
    ]
    if payload.auth_guide:
        lines.extend(["## Authentication", "", payload.auth_guide.strip(), ""])

    lines.extend(["## Endpoints", ""])
    normalized: list[dict[str, Any]] = []
    for endpoint in payload.endpoints:
        method = endpoint.method.upper()
        path = endpoint.path if endpoint.path.startswith("/") else f"/{endpoint.path}"
        normalized.append({"method": method, "path": path})
        lines.extend(
            [
                f"### {method} `{path}`",
                "",
                endpoint.summary.strip() or "No summary provided.",
                "",
            ]
        )
        if endpoint.auth:
            lines.extend([f"Auth: `{endpoint.auth}`", ""])
        lines.extend(
            [
                "Request schema:",
                "",
                "```json",
                _schema_preview(endpoint.request_schema),
                "```",
                "",
                "Response schema:",
                "",
                "```json",
                _schema_preview(endpoint.response_schema),
                "```",
                "",
            ]
        )
        if endpoint.errors:
            lines.extend(["Common errors:", ""])
            lines.extend(f"- {error}" for error in endpoint.errors)
            lines.append("")

        example_body = _example_payload(endpoint.request_schema)
        if "curl" in {item.lower() for item in payload.languages}:
            lines.extend(
                [
                    "cURL example:",
                    "",
                    "```bash",
                    f"curl -X {method} '{base_url}{path}' \\",
                    "  -H 'content-type: application/json' \\",
                    f"  --data '{example_body}'",
                    "```",
                    "",
                ]
            )
        if "python" in {item.lower() for item in payload.languages}:
            lines.extend(
                [
                    "Python example:",
                    "",
                    "```python",
                    "import requests",
                    "",
                    f"response = requests.request({method!r}, {f'{base_url}{path}'!r}, json={example_body})",
                    "response.raise_for_status()",
                    "print(response.json())",
                    "```",
                    "",
                ]
            )
        if "javascript" in {item.lower() for item in payload.languages}:
            lines.extend(
                [
                    "JavaScript example:",
                    "",
                    "```javascript",
                    f"const response = await fetch({f'{base_url}{path}'!r}, {{",
                    f"  method: {method!r},",
                    "  headers: { 'content-type': 'application/json' },",
                    f"  body: JSON.stringify({example_body}),",
                    "});",
                    "console.log(await response.json());",
                    "```",
                    "",
                ]
            )

    markdown = "\n".join(lines).strip() + "\n"
    return {
        "schema": "x0tta6bl4.paid_api_docs_package.v1",
        "service_name": payload.service_name,
        "base_url": base_url,
        "endpoints_total": len(payload.endpoints),
        "endpoints": normalized,
        "markdown": markdown,
        "claim_boundary": (
            "This package is generated from submitted endpoint specs. It does not "
            "prove the remote API exists, works, or matches production behavior."
        ),
    }


def build_listing_audit_report(payload: ListingAuditRequest) -> dict[str, Any]:
    text = payload.profile_text.lower()
    signals = {
        "has_clear_price": "$" in text or "usdc" in text or payload.price_usdc is not None,
        "has_delivery_mode": any(word in text for word in ("direct", "mailbox", "endpoint", "deliver", "delivery")),
        "has_scope": any(word in text for word in ("send", "input", "payload", "public", "snippet", "url")),
        "has_output": any(word in text for word in ("return", "output", "report", "json", "markdown", "scorecard")),
        "has_safety_boundary": any(word in text for word in ("no secrets", "public", "no private", "no captcha")),
        "has_examples": any(word in text for word in ("example", "sample", "demo")),
        "has_fast_turnaround": any(word in text for word in ("instant", "same-day", "minutes", "immediately")),
    }
    score = 35
    score += 12 if signals["has_clear_price"] else 0
    score += 12 if signals["has_delivery_mode"] else 0
    score += 12 if signals["has_scope"] else 0
    score += 12 if signals["has_output"] else 0
    score += 10 if signals["has_safety_boundary"] else 0
    score += 7 if signals["has_examples"] else 0
    score += 6 if signals["has_fast_turnaround"] else 0
    score = min(100, score)

    gaps: list[str] = []
    if not signals["has_clear_price"]:
        gaps.append("Price is not obvious. Put the USDC price in the first sentence.")
    if not signals["has_scope"]:
        gaps.append("Input scope is vague. Say exactly what the buyer should send.")
    if not signals["has_output"]:
        gaps.append("Output is vague. Name the exact artifact: JSON, Markdown, report, scorecard, or code.")
    if not signals["has_delivery_mode"]:
        gaps.append("Delivery mode is unclear. Say direct endpoint or mailbox delivery.")
    if not signals["has_safety_boundary"]:
        gaps.append("Safety boundary is missing. State public inputs only and no secrets.")
    if not signals["has_examples"]:
        gaps.append("No sample result is mentioned. Add a short example output or schema.")

    fixes = [
        "Start with one sentence: input, output, price, and turnaround.",
        "Add an explicit refusal line for secrets, private accounts, CAPTCHA, spam, and KYC.",
        "List 3 accepted input examples and 3 rejected input examples.",
        "Add a tiny sample response shape so other agents can call it safely.",
        "Use tags that buyers search for, not internal project names only.",
    ]
    if payload.target_buyer:
        fixes.insert(0, f"Rewrite the first sentence for this buyer: {payload.target_buyer[:180]}.")

    improved_cta = (
        "Send one public URL or short non-sensitive snippet. I return a concise scorecard "
        "with trust gaps, pricing clarity, delivery risks, and five prioritized fixes."
    )
    if payload.price_usdc is not None:
        improved_cta += f" Price: {payload.price_usdc:g} USDC."

    return {
        "schema": "x0tta6bl4.bothire_listing_audit_report.v1",
        "listing_url": payload.listing_url,
        "score": score,
        "signals": signals,
        "gaps": gaps,
        "prioritized_fixes": fixes,
        "improved_cta": improved_cta,
        "claim_boundary": (
            "This is a heuristic listing audit from submitted text. It does not prove "
            "market demand, search ranking, buyer acceptance, payout, or received funds."
        ),
    }


def build_payment_risk_report(payload: PaymentRiskRequest) -> dict[str, Any]:
    text = "\n".join(
        [
            payload.resource_url or "",
            payload.service_name,
            payload.description,
            " ".join(payload.tags),
        ]
    ).lower()
    pay_to = payload.pay_to or ""
    amount = int(payload.amount or 0)
    network = payload.network or ""
    asset = payload.asset or ""

    signals = {
        "has_pay_to": bool(pay_to),
        "pay_to_shape_ok": bool(re.fullmatch(r"0x[a-fA-F0-9]{40}", pay_to)) if pay_to else False,
        "network_is_base_mainnet": network in {"eip155:8453", "base", "Base", "Base mainnet"},
        "asset_is_usdc_base": asset.lower() in {
            "usdc",
            "0x833589fcd6edb6e08f4c7c32d4f71b54bda02913",
        },
        "amount_present": amount > 0,
        "amount_is_micro_usdc_reasonable": 0 < amount <= 5_000_000,
        "has_resource_url": bool(payload.resource_url),
        "possible_secret_text": bool(SECRET_PATTERN.search(text)),
        "high_risk_terms": any(
            term in text
            for term in (
                "private key",
                "seed phrase",
                "captcha",
                "kyc",
                "spam",
                "steal",
                "phishing",
                "bypass",
            )
        ),
    }
    score = 50
    score += 10 if signals["pay_to_shape_ok"] else -20
    score += 10 if signals["network_is_base_mainnet"] else -10
    score += 10 if signals["asset_is_usdc_base"] else -10
    score += 10 if signals["amount_is_micro_usdc_reasonable"] else -15
    score += 5 if signals["has_resource_url"] else -5
    score -= 20 if signals["possible_secret_text"] else 0
    score -= 30 if signals["high_risk_terms"] else 0
    score = max(0, min(100, score))

    risks: list[str] = []
    if not signals["has_pay_to"]:
        risks.append("Missing payTo address.")
    elif not signals["pay_to_shape_ok"]:
        risks.append("payTo does not look like an EVM address.")
    if not signals["network_is_base_mainnet"]:
        risks.append("Network is not clearly Base mainnet/eip155:8453.")
    if not signals["asset_is_usdc_base"]:
        risks.append("Asset is not clearly Base USDC.")
    if not signals["amount_present"]:
        risks.append("Amount is missing or zero.")
    elif not signals["amount_is_micro_usdc_reasonable"]:
        risks.append("Amount is outside the expected small micropayment range.")
    if signals["possible_secret_text"]:
        risks.append("Secret-like text appears in submitted metadata.")
    if signals["high_risk_terms"]:
        risks.append("Request contains high-risk terms such as CAPTCHA/KYC/bypass/phishing/seed/private-key.")

    verdict = "review"
    if score >= 80 and not risks:
        verdict = "low_risk"
    elif score < 55 or signals["high_risk_terms"] or signals["possible_secret_text"]:
        verdict = "high_risk"

    return {
        "schema": "x0tta6bl4.paid_payment_risk_report.v1",
        "verdict": verdict,
        "risk_score": score,
        "signals": signals,
        "risks": risks,
        "recommendations": [
            "Verify the live 402 body and Payment-Required header before paying.",
            "Confirm payTo, network, asset, and amount match the catalog entry.",
            "Reject requests that require secrets, CAPTCHA bypass, KYC bypass, spam, or private-account actions.",
            "Keep the first paid call small until the service has a verified success history.",
        ],
        "normalized": {
            "resource_url": payload.resource_url,
            "pay_to": pay_to,
            "amount": amount,
            "network": network,
            "asset": asset,
            "service_name": payload.service_name,
        },
        "claim_boundary": (
            "This is a static risk report from submitted public payment metadata. It does not "
            "prove the remote service is honest, the payment will settle, or funds were received."
        ),
    }


def build_income_route_report(payload: IncomeRouteRequest) -> dict[str, Any]:
    text = "\n".join(
        [
            payload.opportunity_title,
            payload.description,
            payload.payout_type,
            payload.buyer_type,
            payload.payment_rail,
            payload.deliverable_type,
            " ".join(payload.tags),
        ]
    ).lower()
    payout = float(payload.payout_usdc or 0.0)
    upfront = float(payload.required_upfront_usdc or 0.0)
    tokens = int(payload.estimated_token_cost or 0)
    minutes = int(payload.estimated_minutes or 0)
    net_usdc = max(0.0, payout - upfront)
    token_blocks = max(tokens / 1000.0, 1.0)
    token_to_money_ratio = round(net_usdc / token_blocks, 4)

    hard_terms = (
        "captcha",
        "kyc bypass",
        "fake review",
        "spam",
        "seed phrase",
        "private key",
        "credential",
        "account farming",
        "sybil",
        "airdrop farming",
        "carding",
        "phishing",
    )
    hard_hits = sorted({term for term in hard_terms if term in text})
    bounty_like = any(term in text for term in ("bug bounty", "bounty", "vulnerability disclosure"))
    recurring = any(term in text for term in ("per_call", "per request", "paid api", "x402", "subscription", "repeat"))
    escrow = any(term in text for term in ("escrow", "payanagent", "agentpact", "bothire", "the402"))
    clear_payment = any(term in text for term in ("usdc", "x402", "base", "escrow", "lightning", "crypto"))
    public_input = any(term in text for term in ("public", "url", "snippet", "json", "api", "endpoint"))
    automated = any(term in text for term in ("api", "automation", "script", "endpoint", "report", "json", "triage"))

    score = 40.0
    score += 20 if payout > 0 else -20
    score += min(net_usdc, 25.0)
    score += 14 if recurring else 0
    score += 12 if escrow else 0
    score += 10 if clear_payment else -8
    score += 10 if public_input else -8
    score += 10 if automated else -8
    score -= 18 if upfront > 0 else 0
    score -= min(upfront * 4, 30.0)
    score -= 18 if bounty_like else 0
    score -= 35 if hard_hits else 0
    score -= 12 if minutes > 120 else 0
    score -= 12 if tokens > 80_000 else 0
    score = round(max(0.0, min(100.0, score)), 1)

    reasons: list[str] = []
    risks: list[str] = []
    if payout > 0:
        reasons.append("Payment amount is stated.")
    else:
        risks.append("No clear payout amount.")
    if recurring:
        reasons.append("Can become repeated pay-per-call income.")
    if escrow:
        reasons.append("Marketplace or escrow rail is mentioned.")
    if clear_payment:
        reasons.append("Payment rail is concrete.")
    else:
        risks.append("Payment rail is vague.")
    if public_input:
        reasons.append("Can work from public input.")
    else:
        risks.append("Input scope is not clearly public.")
    if automated:
        reasons.append("Looks automatable by a small agent endpoint.")
    else:
        risks.append("Looks manual or hard to automate.")
    if upfront > 0:
        risks.append("Requires upfront money before earning.")
    if bounty_like:
        risks.append("This looks like bounty work; requested mode is non-bounty.")
    if hard_hits:
        risks.append("Contains refusal triggers: " + ", ".join(hard_hits[:8]) + ".")
    if minutes > 120:
        risks.append("Estimated time is high for a small autonomous sale.")
    if tokens > 80_000:
        risks.append("Estimated token cost is high.")

    verdict = "park"
    if hard_hits or upfront > max(payout * 0.2, 1.0) or score < 45:
        verdict = "reject"
    elif score >= 70 and net_usdc > 0:
        verdict = "take_first"

    next_steps = [
        "Turn the opportunity into a tiny fixed-scope endpoint or fixed-price offer.",
        "Use public input only; reject secrets, private accounts, CAPTCHA, spam, KYC bypass, and Sybil tasks.",
        "Keep the first price small and the output deterministic: JSON report, Markdown report, or one script.",
    ]
    if verdict == "take_first":
        next_steps.insert(0, "List or call this route first; it has the best money-to-token shape.")
    elif verdict == "reject":
        next_steps.insert(0, "Do not spend more tokens here until the risk or upfront-cost problem is removed.")
    else:
        next_steps.insert(0, "Keep it in the backlog; use it only after higher-score routes are exhausted.")

    return {
        "schema": "x0tta6bl4.paid_income_route_report.v1",
        "verdict": verdict,
        "roi_score": score,
        "estimated_net_usdc": round(net_usdc, 4),
        "token_to_money_ratio_usdc_per_1k_tokens": token_to_money_ratio,
        "signals": {
            "has_payout": payout > 0,
            "requires_upfront_money": upfront > 0,
            "recurring_income_fit": recurring,
            "escrow_or_marketplace_fit": escrow,
            "clear_payment_rail": clear_payment,
            "public_input_fit": public_input,
            "automation_fit": automated,
            "bounty_like": bounty_like,
            "hard_refusal_terms": hard_hits,
        },
        "reasons": reasons,
        "risks": risks,
        "mape_k_simple": {
            "monitor": "Watch paid API calls, marketplace requests, direct hires, and wallet balance.",
            "analyze": "Score by net USDC, token cost, upfront cost, payment certainty, and safety.",
            "plan": "Pick the highest score route with no hard refusal term.",
            "execute": "Expose a paid endpoint, bid on safe public-input work, or deliver a fixed report.",
            "knowledge": "Write the result to local artifacts and update the next ranking.",
        },
        "next_steps": next_steps,
        "claim_boundary": (
            "This is a static opportunity score from submitted public text. It does not prove "
            "buyer demand, accepted work, escrow release, on-chain payout, or received funds."
        ),
    }


class _NoRedirectHandler(urllib.request.HTTPRedirectHandler):
    def redirect_request(self, req, fp, code, msg, headers, newurl):  # type: ignore[no-untyped-def]
        return None


def _is_public_http_url(url: str) -> tuple[bool, str, urllib.parse.ParseResult | None]:
    parsed = urllib.parse.urlparse(url)
    if parsed.scheme not in {"http", "https"}:
        return False, "scheme_must_be_http_or_https", parsed
    if not parsed.hostname:
        return False, "missing_hostname", parsed
    if parsed.username or parsed.password:
        return False, "url_must_not_contain_credentials", parsed
    port = parsed.port or (443 if parsed.scheme == "https" else 80)
    try:
        addresses = socket.getaddrinfo(parsed.hostname, port, type=socket.SOCK_STREAM)
    except socket.gaierror:
        return False, "hostname_does_not_resolve", parsed
    for item in addresses:
        host = item[4][0]
        try:
            ip = ipaddress.ip_address(host)
        except ValueError:
            return False, "resolved_address_is_invalid", parsed
        if not ip.is_global:
            return False, f"resolved_address_not_public:{ip}", parsed
    return True, "public_url", parsed


def _maybe_json_object(text: str) -> dict[str, Any] | None:
    try:
        payload = json.loads(text)
    except json.JSONDecodeError:
        return None
    return payload if isinstance(payload, dict) else None


def _decode_x402_metadata(header_value: str, body_text: str) -> dict[str, Any] | None:
    decoded = decode_payment_required_header(header_value)
    if decoded:
        return decoded
    if header_value.strip().startswith("{"):
        parsed = _maybe_json_object(header_value)
        if parsed:
            return parsed
    parsed_body = _maybe_json_object(body_text)
    if parsed_body and ("accepts" in parsed_body or "x402Version" in parsed_body):
        return parsed_body
    return None


def _first_accept(metadata: dict[str, Any] | None) -> dict[str, Any]:
    if not isinstance(metadata, dict):
        return {}
    accepts = metadata.get("accepts")
    if isinstance(accepts, list):
        for item in accepts:
            if isinstance(item, dict):
                return item
    return {}


def _int_or_none(value: Any) -> int | None:
    if value is None or value == "":
        return None
    try:
        return int(str(value), 10)
    except ValueError:
        return None


def build_x402_validate_report(payload: X402ValidateRequest) -> dict[str, Any]:
    ok, reason, parsed = _is_public_http_url(payload.url)
    if not ok:
        return {
            "schema": "x0tta6bl4.paid_x402_validate_report.v1",
            "verdict": "reject",
            "url": payload.url,
            "error": reason,
            "signals": {
                "public_url": False,
                "http_402": False,
                "has_payment_required_header": False,
                "has_x402_metadata": False,
            },
            "risks": ["Target URL is not a safe public HTTP/HTTPS URL."],
            "claim_boundary": (
                "This validates URL shape only because the target was not fetched. It does not "
                "prove service safety, payment settlement, or received funds."
            ),
        }

    assert parsed is not None
    request = urllib.request.Request(
        payload.url,
        headers={
            "Accept": "application/json",
            "User-Agent": "x0tta6bl4-x402-validator",
        },
        method=payload.method.upper(),
    )
    opener = urllib.request.build_opener(_NoRedirectHandler())
    status = 0
    headers: dict[str, str] = {}
    body_text = ""
    error: str | None = None
    try:
        with opener.open(request, timeout=12.0) as response:
            status = int(response.status)
            headers = {str(k).lower(): str(v) for k, v in response.headers.items()}
            body_text = response.read(2_000).decode("utf-8", errors="replace")
    except urllib.error.HTTPError as exc:
        status = int(exc.code)
        headers = {str(k).lower(): str(v) for k, v in exc.headers.items()}
        body_text = exc.read(2_000).decode("utf-8", errors="replace")
    except Exception as exc:
        error = exc.__class__.__name__

    payment_header = headers.get("payment-required") or headers.get("x-payment-required") or ""
    metadata = _decode_x402_metadata(payment_header, body_text)
    accept = _first_accept(metadata)
    pay_to = str(accept.get("payTo") or accept.get("pay_to") or "")
    network = str(accept.get("network") or "")
    asset = str(accept.get("asset") or accept.get("asset_address") or "")
    amount = _int_or_none(accept.get("amount") or accept.get("maxAmountRequired") or accept.get("max_amount_required"))

    expected_pay_to = payload.expected_pay_to or ""
    address_match = None
    if expected_pay_to:
        address_match = pay_to.lower() == expected_pay_to.lower()
    network_match = network == payload.expected_network
    amount_ok = None
    if payload.max_amount_micro_usdc is not None and amount is not None:
        amount_ok = amount <= payload.max_amount_micro_usdc

    signals = {
        "public_url": True,
        "http_402": status == 402,
        "redirect_seen": 300 <= status < 400,
        "has_payment_required_header": bool(payment_header),
        "has_x402_metadata": bool(metadata),
        "has_accepts": bool(accept),
        "pay_to_shape_ok": bool(re.fullmatch(r"0x[a-fA-F0-9]{40}", pay_to)) if pay_to else False,
        "payment_address_match": address_match,
        "network_match": network_match,
        "amount_under_limit": amount_ok,
    }
    risks: list[str] = []
    if error:
        risks.append(f"Fetch failed: {error}.")
    if status != 402:
        risks.append(f"Endpoint returned HTTP {status}, not 402 Payment Required.")
    if not payment_header and not metadata:
        risks.append("No Payment-Required header or x402 JSON body found.")
    if not accept:
        risks.append("No accepts entry found in x402 metadata.")
    if pay_to and not signals["pay_to_shape_ok"]:
        risks.append("payTo does not look like an EVM address.")
    if expected_pay_to and address_match is False:
        risks.append("Live payTo does not match expected_pay_to.")
    if network and not network_match:
        risks.append("Live network does not match expected_network.")
    if payload.max_amount_micro_usdc is not None and amount_ok is False:
        risks.append("Live amount is above max_amount_micro_usdc.")

    verdict = "valid_x402" if status == 402 and bool(accept) and not risks else "review"
    if error or not signals["public_url"] or not metadata:
        verdict = "invalid_or_unreachable"
    if address_match is False or amount_ok is False:
        verdict = "mismatch"

    return {
        "schema": "x0tta6bl4.paid_x402_validate_report.v1",
        "verdict": verdict,
        "url": payload.url,
        "method": payload.method.upper(),
        "http_status": status,
        "origin": f"{parsed.scheme}://{parsed.netloc}",
        "signals": signals,
        "normalized": {
            "pay_to": pay_to or None,
            "network": network or None,
            "asset": asset or None,
            "amount_micro_usdc": amount,
            "x402_version": metadata.get("x402Version") if isinstance(metadata, dict) else None,
        },
        "risks": risks,
        "body_preview": body_text[:500],
        "claim_boundary": (
            "This is a live HTTP metadata check of a public endpoint. It does not prove the "
            "remote service is honest, the payment will settle, or funds were received."
        ),
    }


class _SnapshotHTMLParser(HTMLParser):
    def __init__(self, *, max_links: int, max_text_chars: int) -> None:
        super().__init__()
        self.max_links = max_links
        self.max_text_chars = max_text_chars
        self.title = ""
        self.meta_description = ""
        self.headings: list[dict[str, str]] = []
        self.links: list[dict[str, str]] = []
        self.text_parts: list[str] = []
        self._current_tag = ""
        self._current_link: dict[str, str] | None = None
        self._skip_depth = 0

    def handle_starttag(self, tag: str, attrs: list[tuple[str, str | None]]) -> None:
        attrs_dict = {key.lower(): value or "" for key, value in attrs}
        tag = tag.lower()
        if tag in {"script", "style", "noscript"}:
            self._skip_depth += 1
            return
        self._current_tag = tag
        if tag == "meta" and attrs_dict.get("name", "").lower() == "description":
            self.meta_description = attrs_dict.get("content", "")[:500]
        if tag == "a" and len(self.links) < self.max_links:
            self._current_link = {"href": attrs_dict.get("href", "")[:500], "text": ""}

    def handle_endtag(self, tag: str) -> None:
        tag = tag.lower()
        if tag in {"script", "style", "noscript"} and self._skip_depth:
            self._skip_depth -= 1
            return
        if tag == "a" and self._current_link is not None:
            if self._current_link.get("href"):
                self.links.append(self._current_link)
            self._current_link = None
        self._current_tag = ""

    def handle_data(self, data: str) -> None:
        if self._skip_depth:
            return
        clean = " ".join(data.split())
        if not clean:
            return
        if self._current_tag == "title" and not self.title:
            self.title = clean[:300]
        if self._current_tag in {"h1", "h2", "h3"} and len(self.headings) < 20:
            self.headings.append({"level": self._current_tag, "text": clean[:300]})
        if self._current_link is not None:
            joined = f"{self._current_link.get('text', '')} {clean}".strip()
            self._current_link["text"] = joined[:300]
        if sum(len(part) for part in self.text_parts) < self.max_text_chars:
            self.text_parts.append(clean)

    def snapshot(self) -> dict[str, Any]:
        text = " ".join(self.text_parts)
        return {
            "title": self.title,
            "meta_description": self.meta_description,
            "headings": self.headings,
            "links": self.links[: self.max_links],
            "text_preview": text[: self.max_text_chars],
        }


def build_url_snapshot_report(payload: UrlSnapshotRequest) -> dict[str, Any]:
    ok, reason, parsed = _is_public_http_url(payload.url)
    if not ok:
        return {
            "schema": "x0tta6bl4.paid_url_snapshot_report.v1",
            "verdict": "reject",
            "url": payload.url,
            "error": reason,
            "signals": {"public_url": False, "fetched": False, "html_like": False},
            "risks": ["Target URL is not a safe public HTTP/HTTPS URL."],
            "claim_boundary": (
                "This validates URL shape only because the target was not fetched. It does not "
                "prove remote page quality, correctness, payment settlement, or received funds."
            ),
        }

    assert parsed is not None
    request = urllib.request.Request(
        payload.url,
        headers={
            "Accept": "text/html,application/xhtml+xml,application/json;q=0.8,*/*;q=0.5",
            "User-Agent": "x0tta6bl4-url-snapshot",
        },
        method="GET",
    )
    opener = urllib.request.build_opener(_NoRedirectHandler())
    status = 0
    headers: dict[str, str] = {}
    body = b""
    error: str | None = None
    try:
        with opener.open(request, timeout=12.0) as response:
            status = int(response.status)
            headers = {str(k).lower(): str(v) for k, v in response.headers.items()}
            body = response.read(80_000)
    except urllib.error.HTTPError as exc:
        status = int(exc.code)
        headers = {str(k).lower(): str(v) for k, v in exc.headers.items()}
        body = exc.read(80_000)
    except Exception as exc:
        error = exc.__class__.__name__

    content_type = headers.get("content-type", "")
    text = body.decode("utf-8", errors="replace")
    parser = _SnapshotHTMLParser(max_links=payload.max_links, max_text_chars=payload.max_text_chars)
    if text:
        try:
            parser.feed(text)
        except Exception:
            pass
    snap = parser.snapshot()
    html_like = bool("<html" in text[:2000].lower() or snap["title"] or snap["headings"])
    risks: list[str] = []
    if error:
        risks.append(f"Fetch failed: {error}.")
    if status >= 400:
        risks.append(f"Target returned HTTP {status}.")
    if 300 <= status < 400:
        risks.append("Target returned a redirect; validator does not follow redirects.")
    if not html_like:
        risks.append("Response does not look like a normal HTML page.")

    return {
        "schema": "x0tta6bl4.paid_url_snapshot_report.v1",
        "verdict": "ok" if status and status < 400 and html_like and not error else "review",
        "url": payload.url,
        "origin": f"{parsed.scheme}://{parsed.netloc}",
        "http_status": status,
        "content_type": content_type,
        "content_length_seen": len(body),
        "signals": {
            "public_url": True,
            "fetched": error is None and status > 0,
            "html_like": html_like,
            "redirect_seen": 300 <= status < 400,
        },
        "page": snap,
        "risks": risks,
        "claim_boundary": (
            "This is a bounded snapshot of a public URL. It does not prove the full page, "
            "business truth, legal status, payment settlement, or received funds."
        ),
    }


def _normalize_domain_health_target(target: str) -> tuple[str, str, urllib.parse.ParseResult | None]:
    candidate = target.strip()
    if "://" not in candidate:
        candidate = f"https://{candidate}"
    parsed = urllib.parse.urlparse(candidate)
    if parsed.scheme not in {"http", "https"}:
        return candidate, "scheme_must_be_http_or_https", parsed
    if not parsed.hostname:
        return candidate, "missing_hostname", parsed
    if parsed.username or parsed.password:
        return candidate, "url_must_not_contain_credentials", parsed
    return candidate, "ok", parsed


def _resolve_public_addresses(hostname: str, port: int) -> tuple[list[str], list[str]]:
    risks: list[str] = []
    addresses: list[str] = []
    try:
        resolved = socket.getaddrinfo(hostname, port, type=socket.SOCK_STREAM)
    except socket.gaierror:
        return [], ["Hostname does not resolve."]
    for item in resolved:
        host = item[4][0]
        if host in addresses:
            continue
        try:
            ip = ipaddress.ip_address(host)
        except ValueError:
            risks.append(f"Resolved address is invalid: {host}.")
            continue
        addresses.append(str(ip))
        if not ip.is_global:
            risks.append(f"Resolved address is not public: {ip}.")
    return addresses[:12], risks


def _fetch_domain_http(url: str) -> dict[str, Any]:
    request = urllib.request.Request(
        url,
        headers={
            "Accept": "text/html,application/json;q=0.8,*/*;q=0.5",
            "User-Agent": "x0tta6bl4-domain-health-lite",
        },
        method="GET",
    )
    opener = urllib.request.build_opener(_NoRedirectHandler())
    try:
        with opener.open(request, timeout=8.0) as response:
            body = response.read(2048)
            return {
                "fetched": True,
                "status": int(response.status),
                "content_type": str(response.headers.get("content-type", "")),
                "location": str(response.headers.get("location", "")),
                "bytes_seen": len(body),
                "error": None,
            }
    except urllib.error.HTTPError as exc:
        return {
            "fetched": True,
            "status": int(exc.code),
            "content_type": str(exc.headers.get("content-type", "")),
            "location": str(exc.headers.get("location", "")),
            "bytes_seen": 0,
            "error": None,
        }
    except Exception as exc:
        return {
            "fetched": False,
            "status": 0,
            "content_type": "",
            "location": "",
            "bytes_seen": 0,
            "error": exc.__class__.__name__,
        }


def _check_tls_expiry(hostname: str, port: int = 443) -> dict[str, Any]:
    context = ssl.create_default_context()
    try:
        with socket.create_connection((hostname, port), timeout=8.0) as sock:
            with context.wrap_socket(sock, server_hostname=hostname) as tls:
                cert = tls.getpeercert()
    except Exception as exc:
        return {"checked": False, "valid_now": False, "not_after": None, "days_left": None, "error": exc.__class__.__name__}
    not_after = cert.get("notAfter") if isinstance(cert, dict) else None
    if not isinstance(not_after, str):
        return {"checked": True, "valid_now": False, "not_after": None, "days_left": None, "error": "missing_not_after"}
    expires_at = datetime.fromtimestamp(ssl.cert_time_to_seconds(not_after), tz=timezone.utc)
    now = datetime.now(timezone.utc)
    days_left = int((expires_at - now).total_seconds() // 86400)
    return {
        "checked": True,
        "valid_now": days_left >= 0,
        "not_after": expires_at.replace(microsecond=0).isoformat().replace("+00:00", "Z"),
        "days_left": days_left,
        "error": None,
    }


def build_domain_health_report(payload: DomainHealthRequest) -> dict[str, Any]:
    url, reason, parsed = _normalize_domain_health_target(payload.target)
    if reason != "ok" or parsed is None or not parsed.hostname:
        return {
            "schema": "x0tta6bl4.paid_domain_health_report.v1",
            "verdict": "reject",
            "target": payload.target,
            "normalized_url": url,
            "error": reason,
            "signals": {"public_dns": False, "http_checked": False, "tls_checked": False},
            "risks": ["Target is not a safe public HTTP/HTTPS domain or URL."],
            "claim_boundary": (
                "This validates target shape only. It does not prove remote service quality, "
                "payment settlement, or received funds."
            ),
        }

    port = parsed.port or (443 if parsed.scheme == "https" else 80)
    addresses, dns_risks = _resolve_public_addresses(parsed.hostname, port)
    public_dns = bool(addresses) and not dns_risks
    risks = list(dns_risks)
    if not public_dns:
        risks.append("Fetch and TLS checks skipped because DNS did not resolve to public addresses only.")
    http = {"fetched": False, "status": 0, "content_type": "", "location": "", "bytes_seen": 0, "error": None}
    tls = {"checked": False, "valid_now": False, "not_after": None, "days_left": None, "error": None}
    if public_dns and payload.fetch_http:
        http = _fetch_domain_http(url)
        if http.get("error"):
            risks.append(f"HTTP check failed: {http['error']}.")
        status = int(http.get("status") or 0)
        if status >= 400:
            risks.append(f"Target returned HTTP {status}.")
        if 300 <= status < 400:
            risks.append("Target returned a redirect; health check does not follow redirects.")
    if public_dns and payload.check_tls and parsed.scheme == "https":
        tls = _check_tls_expiry(parsed.hostname, 443)
        if tls.get("error"):
            risks.append(f"TLS check failed: {tls['error']}.")
        days_left = tls.get("days_left")
        if isinstance(days_left, int) and days_left < 14:
            risks.append("TLS certificate expires in less than 14 days.")

    verdict = "ok"
    if not public_dns:
        verdict = "reject"
    elif risks:
        verdict = "review"

    return {
        "schema": "x0tta6bl4.paid_domain_health_report.v1",
        "verdict": verdict,
        "target": payload.target,
        "normalized_url": url,
        "hostname": parsed.hostname,
        "scheme": parsed.scheme,
        "port": port,
        "addresses": addresses,
        "http": http,
        "tls": tls,
        "signals": {
            "public_dns": public_dns,
            "http_checked": bool(payload.fetch_http and public_dns),
            "tls_checked": bool(payload.check_tls and public_dns and parsed.scheme == "https"),
            "redirect_seen": 300 <= int(http.get("status") or 0) < 400,
            "private_network_refused": any("not public" in item for item in dns_risks),
        },
        "risks": risks,
        "claim_boundary": (
            "This is a bounded public domain health check. It does not prove uptime history, "
            "full security posture, payment settlement, or received funds."
        ),
    }


def build_agentworld_reply(payload: AgentWorldMessageRequest, *, base_url: str, settings: PaidApiSettings) -> dict[str, Any]:
    text = f"{payload.message}\n{payload.context}".lower()
    if SECRET_PATTERN.search(text):
        intent = "secret_safety"
        reply = (
            "Do not send secrets, private keys, passwords, cookies, or private account data. "
            "Send only public snippets or public URLs, then use the paid x402 endpoints below."
        )
    elif "x402" in text and any(
        word in text for word in ("validate", "validator", "endpoint validator", "payment-required", "live check")
    ):
        intent = "x402_validate"
        reply = (
            "For live x402 endpoint validation, send a public URL only. "
            f"Endpoint: {base_url}/paid/x402-validate. Price: {settings.x402_validate_price} USDC on Base."
        )
    elif any(word in text for word in ("url snapshot", "web snapshot", "page title", "metadata", "headings", "links")):
        intent = "url_snapshot"
        reply = (
            "For public URL snapshots, send one public URL only. "
            f"Endpoint: {base_url}/paid/url-snapshot. Price: {settings.url_snapshot_price} USDC on Base."
        )
    elif any(word in text for word in ("domain", "dns", "tls", "ssl", "http status", "site health")):
        intent = "domain_health"
        reply = (
            "For public domain health checks, send one public domain or URL only. "
            f"Endpoint: {base_url}/paid/domain-health. Price: {settings.domain_health_price} USDC on Base."
        )
    elif any(word in text for word in ("api", "docs", "openapi", "endpoint")):
        intent = "api_docs"
        reply = (
            "For API documentation, call the paid endpoint with service_name and endpoints. "
            f"Endpoint: {base_url}/paid/api-docs. Price: {settings.api_docs_price} USDC on Base."
        )
    elif any(word in text for word in ("repo", "code", "pytest", "test", "triage")):
        intent = "repo_triage"
        reply = (
            "For code or repository triage, send public file snippets only. "
            f"Endpoint: {base_url}/paid/repo-triage. Price: {settings.repo_triage_price} USDC on Base."
        )
    elif any(word in text for word in ("listing", "profile", "marketplace", "conversion", "bot card")):
        intent = "listing_audit"
        reply = (
            "For agent listing conversion audit, send the public listing text or URL. "
            f"Endpoint: {base_url}/paid/listing-audit. Price: {settings.listing_audit_price} USDC on Base."
        )
    elif any(word in text for word in ("income", "earn", "earning", "money", "roi", "opportunity", "paid task")):
        intent = "income_route"
        reply = (
            "For non-bounty earning route scoring, send public opportunity details only. "
            f"Endpoint: {base_url}/paid/income-route. Price: {settings.income_route_price} USDC on Base."
        )
    elif any(word in text for word in ("payment", "wallet", "payto", "x402", "risk", "spend", "usdc")):
        intent = "payment_risk"
        reply = (
            "For x402/payment risk checks, send public payment metadata only. "
            f"Endpoint: {base_url}/paid/payment-risk. Price: {settings.payment_risk_price} USDC on Base."
        )
    else:
        intent = "catalog"
        reply = (
            "x0tta6bl4 exposes five small paid tools: API docs generation, repository triage, "
            "agent listing audit, payment risk checks, and income route scoring. Use public inputs only. Discovery: "
            f"{base_url}/.well-known/x402-discovery"
        )
    return {
        "schema": "x0tta6bl4.agentworld_reply.v1",
        "intent": intent,
        "reply": reply,
        "paid_endpoints": {
            "api_docs": f"{base_url}/paid/api-docs",
            "repo_triage": f"{base_url}/paid/repo-triage",
            "listing_audit": f"{base_url}/paid/listing-audit",
            "payment_risk": f"{base_url}/paid/payment-risk",
            "income_route": f"{base_url}/paid/income-route",
            "x402_validate": f"{base_url}/paid/x402-validate",
            "url_snapshot": f"{base_url}/paid/url-snapshot",
            "domain_health": f"{base_url}/paid/domain-health",
        },
        "payment": {
            "network": settings.network,
            "wallet": settings.pay_to,
            "asset": "USDC",
        },
        "claim_boundary": (
            "This is a lightweight AgentWorld routing reply. It does not prove that "
            "AgentWorld paid, released escrow, or transferred funds to the wallet."
        ),
    }


def _first_public_candidate(text: str) -> str | None:
    url_match = re.search(r"https?://[^\s\])}>'\"]+", text)
    if url_match:
        return url_match.group(0).rstrip(".,;")
    domain_match = re.search(r"\b(?:[a-z0-9-]+\.)+[a-z]{2,}\b", text, flags=re.IGNORECASE)
    if domain_match:
        return domain_match.group(0).rstrip(".,;")
    return None


def _markdown_json(title: str, payload: dict[str, Any]) -> str:
    return "\n".join(
        [
            f"# {title}",
            "",
            "```json",
            json.dumps(payload, indent=2, ensure_ascii=False, sort_keys=True)[:12_000],
            "```",
            "",
            "Boundary: public-input task only. No secrets, private accounts, CAPTCHA, KYC bypass, spam, or harmful automation.",
        ]
    )


def build_agentbazaar_task_result(
    payload: AgentBazaarTaskRequest,
    *,
    base_url: str,
    settings: PaidApiSettings,
) -> dict[str, Any]:
    task = payload.task or payload.message or str(payload.payload.get("task") or payload.payload.get("message") or "")
    compact_payload = json.dumps(payload.model_dump(), ensure_ascii=False)[:4_000]
    text = f"{task}\n{compact_payload}"
    lower = text.lower()
    target = _first_public_candidate(text)

    if not task.strip():
        result = {
            "schema": "x0tta6bl4.agentbazaar_task_result.v1",
            "verdict": "reject",
            "reason": "missing_task",
            "catalog": build_agentworld_reply(
                AgentWorldMessageRequest(message="catalog"),
                base_url=base_url,
                settings=settings,
            )["paid_endpoints"],
        }
        return {
            "result": _markdown_json("x0tta6bl4 AgentBazaar result", result),
            "structured": result,
        }

    hard_refusal_terms = (
        "captcha",
        "kyc bypass",
        "fake review",
        "spam",
        "seed phrase",
        "private key",
        "phishing",
        "account farming",
        "sybil",
    )
    if SECRET_PATTERN.search(text) or any(term in lower for term in hard_refusal_terms):
        result = {
            "schema": "x0tta6bl4.agentbazaar_task_result.v1",
            "verdict": "reject",
            "reason": "unsafe_or_secret_like_task",
            "accepted_scope": "public URLs, public snippets, endpoint specs, domain names, and marketplace listing text",
        }
        return {
            "result": _markdown_json("x0tta6bl4 refused task", result),
            "structured": result,
        }

    tool = "catalog"
    report: dict[str, Any]
    if "x402" in lower and target and any(word in lower for word in ("validate", "validator", "payment-required", "payto")):
        tool = "x402-validate"
        report = build_x402_validate_report(
            X402ValidateRequest(
                url=target if target.startswith(("http://", "https://")) else f"https://{target}",
                expected_pay_to=settings.pay_to,
                max_amount_micro_usdc=100_000,
            )
        )
    elif target and any(word in lower for word in ("domain", "dns", "tls", "ssl", "http status", "site health", "health")):
        tool = "domain-health"
        report = build_domain_health_report(DomainHealthRequest(target=target))
    elif target and any(word in lower for word in ("url snapshot", "web snapshot", "metadata", "headings", "links", "page title")):
        tool = "url-snapshot"
        report = build_url_snapshot_report(UrlSnapshotRequest(url=target if target.startswith(("http://", "https://")) else f"https://{target}"))
    elif any(word in lower for word in ("income", "earn", "earning", "money", "roi", "opportunity", "paid task")):
        tool = "income-route"
        report = build_income_route_report(
            IncomeRouteRequest(
                opportunity_title=task[:240],
                description=task[:4_000],
                source_url=target,
                payout_usdc=0.01,
                required_upfront_usdc=0,
                estimated_token_cost=1_500,
                estimated_minutes=3,
                payout_type="per_request",
                payment_rail="AgentBazaar USDC on Solana",
                deliverable_type="Markdown or JSON report",
                tags=["agentbazaar", "paid-api", "automation"],
            )
        )
    elif any(word in lower for word in ("listing", "profile", "marketplace", "conversion", "agent card")):
        tool = "listing-audit"
        report = build_listing_audit_report(ListingAuditRequest(listing_url=target, profile_text=task, price_usdc=0.01))
    elif any(word in lower for word in ("payment", "wallet", "payto", "risk", "spend", "usdc")):
        tool = "payment-risk"
        report = build_payment_risk_report(
            PaymentRiskRequest(
                resource_url=target,
                description=task,
                service_name="AgentBazaar buyer task",
                tags=["agentbazaar", "payment-risk"],
            )
        )
    elif any(word in lower for word in ("api", "docs", "openapi", "endpoint")):
        tool = "api-docs"
        report = build_api_docs_package(
            ApiDocsRequest(
                service_name="Submitted API",
                base_url=target,
                endpoints=[{"method": "GET", "path": "/health", "summary": task[:500]}],
            )
        )
    else:
        snippets: list[FileSnippet] = []
        for item in payload.files:
            if not isinstance(item, dict):
                continue
            name = str(item.get("name") or item.get("path") or "submitted.txt")[:240]
            content = item.get("text") or item.get("content")
            if isinstance(content, str) and content:
                snippets.append(FileSnippet(path=name, text=content[:20_000]))
        tool = "repo-triage" if snippets else "catalog"
        if snippets:
            report = build_repo_triage_report(RepoTriageRequest(repo_url=target, files=snippets, focus=["agentbazaar"]))
        else:
            report = build_preview_route(
                PreviewRouteRequest(message=task[:3_000], public_url=target),
                base_url=base_url,
                settings=settings,
            )

    result = {
        "schema": "x0tta6bl4.agentbazaar_task_result.v1",
        "verdict": "done",
        "tool": tool,
        "buyer": payload.buyer,
        "job_id": payload.jobId,
        "files_seen": len(payload.files),
        "report": report,
        "agentbazaar_note": (
            "This endpoint is built for AgentBazaar push delivery. AgentBazaar handles buyer "
            "payment before dispatch; this response does not prove final settlement to the agent wallet."
        ),
    }
    return {
        "result": _markdown_json("x0tta6bl4 AgentBazaar result", result),
        "structured": result,
    }


def build_preview_route(payload: PreviewRouteRequest, *, base_url: str, settings: PaidApiSettings) -> dict[str, Any]:
    text = f"{payload.message}\n{payload.public_url or ''}\n{payload.snippet}".lower()
    if SECRET_PATTERN.search(text):
        intent = "secret_safety"
        paid_endpoint = None
        price = None
        sample_payload: dict[str, Any] = {}
        guidance = (
            "Remove private keys, API keys, passwords, cookies, bearer tokens, and other secrets. "
            "Then send only public snippets or public URLs."
        )
    elif "x402" in text and any(
        word in text for word in ("validate", "validator", "endpoint validator", "payment-required", "live check")
    ):
        intent = "x402_validate"
        paid_endpoint = f"{base_url}/paid/x402-validate"
        price = settings.x402_validate_price
        sample_payload = {
            "url": payload.public_url or "https://example.com/paid/tool",
            "method": "GET",
            "expected_network": "eip155:8453",
            "max_amount_micro_usdc": 100_000,
        }
        guidance = "Use this before an autonomous wallet trusts a public x402 endpoint."
    elif any(word in text for word in ("url snapshot", "web snapshot", "page title", "metadata", "headings", "links")):
        intent = "url_snapshot"
        paid_endpoint = f"{base_url}/paid/url-snapshot"
        price = settings.url_snapshot_price
        sample_payload = {
            "url": payload.public_url or "https://example.com",
            "max_links": 12,
            "max_text_chars": 1200,
        }
        guidance = "Use this when an agent needs page title, metadata, headings, links, and text preview."
    elif any(word in text for word in ("domain", "dns", "tls", "ssl", "http status", "site health")):
        intent = "domain_health"
        paid_endpoint = f"{base_url}/paid/domain-health"
        price = settings.domain_health_price
        sample_payload = {
            "target": payload.public_url or "https://example.com",
            "fetch_http": True,
            "check_tls": True,
        }
        guidance = "Use this when an agent needs a cheap DNS, HTTP, and TLS health signal."
    elif any(word in text for word in ("income", "earn", "earning", "money", "roi", "opportunity", "paid task")):
        intent = "income_route"
        paid_endpoint = f"{base_url}/paid/income-route"
        price = settings.income_route_price
        sample_payload = {
            "opportunity_title": "Paid x402 API listing",
            "description": "Public-input paid API, per request, USDC on Base.",
            "payout_usdc": 0.02,
            "required_upfront_usdc": 0,
            "estimated_token_cost": 1500,
            "estimated_minutes": 3,
            "payout_type": "per_request",
            "payment_rail": "x402 USDC on Base",
            "deliverable_type": "JSON report",
            "tags": ["x402", "paid-api", "automation"],
        }
        guidance = "Use this to rank non-bounty earning routes by money, token cost, and risk."
    elif any(word in text for word in ("payment", "wallet", "payto", "x402", "risk", "spend", "usdc")):
        intent = "payment_risk"
        paid_endpoint = f"{base_url}/paid/payment-risk"
        price = settings.payment_risk_price
        sample_payload = {
            "resource_url": payload.public_url,
            "pay_to": "0x...",
            "amount": 20_000,
            "network": "eip155:8453",
            "asset": "0x833589fCD6eDb6E08f4c7C32D4f71b54bdA02913",
            "service_name": "Public x402 service",
        }
        guidance = "Use this before an autonomous wallet pays a public x402 endpoint."
    elif any(word in text for word in ("api", "docs", "openapi", "endpoint", "swagger")):
        intent = "api_docs"
        paid_endpoint = f"{base_url}/paid/api-docs"
        price = settings.api_docs_price
        sample_payload = {
            "service_name": "Public API",
            "base_url": payload.public_url or "https://api.example.com",
            "endpoints": [{"method": "GET", "path": "/health", "summary": "Health check"}],
        }
        guidance = "Use this when you have REST endpoints and want Markdown docs with examples."
    elif any(word in text for word in ("repo", "code", "pytest", "test", "ci", "lint", "review")):
        intent = "repo_triage"
        paid_endpoint = f"{base_url}/paid/repo-triage"
        price = settings.repo_triage_price
        sample_payload = {
            "repo_url": payload.public_url,
            "files": [{"path": "pyproject.toml", "text": "public snippet only"}],
            "focus": ["tests", "ci"],
        }
        guidance = "Use this when you can provide public file snippets for a compact engineering triage."
    elif any(word in text for word in ("listing", "profile", "marketplace", "conversion", "agent card", "bot card")):
        intent = "listing_audit"
        paid_endpoint = f"{base_url}/paid/listing-audit"
        price = settings.listing_audit_price
        sample_payload = {
            "listing_url": payload.public_url,
            "profile_text": payload.snippet or "public listing text",
            "target_buyer": "AI agents buying small paid tools",
        }
        guidance = "Use this when you want a marketplace listing scorecard and conversion fixes."
    else:
        intent = "catalog"
        paid_endpoint = f"{base_url}/.well-known/x402-discovery"
        price = None
        sample_payload = {}
        guidance = (
            "Choose api-docs, repo-triage, listing-audit, payment-risk, income-route, "
            "x402-validate, url-snapshot, or domain-health. Send public inputs only."
        )

    return {
        "schema": "x0tta6bl4.free_preview_route.v1",
        "intent": intent,
        "guidance": guidance,
        "paid_endpoint": paid_endpoint,
        "price": price,
        "wallet": settings.pay_to,
        "network": settings.network,
        "sample_payload": sample_payload,
        "safe_input_rules": [
            "Public URLs and public snippets only.",
            "No private keys, API keys, passwords, cookies, bearer tokens, or seed phrases.",
            "No CAPTCHA, spam, KYC bypass, private-account actions, or harmful automation.",
        ],
        "claim_boundary": (
            "This free preview routes buyers to paid x402 tools. It does not perform the paid work, "
            "prove a buyer paid, prove settlement, or prove received funds."
        ),
    }


def persist_webhook_event(source: str, payload: dict[str, Any]) -> dict[str, Any]:
    WEBHOOK_EVENT_DIR.mkdir(parents=True, exist_ok=True)
    event = {
        "schema": "x0tta6bl4.webhook_event.v1",
        "received_at_utc": datetime.now(timezone.utc).replace(microsecond=0).isoformat().replace("+00:00", "Z"),
        "source": source,
        "payload": payload,
        "funds_received_claim_allowed": False,
    }
    safe_source = re.sub(r"[^a-z0-9_-]+", "_", source.lower()).strip("_") or "unknown"
    path = WEBHOOK_EVENT_DIR / f"{safe_source}.jsonl"
    with path.open("a", encoding="utf-8") as handle:
        handle.write(json.dumps(event, ensure_ascii=False, sort_keys=True) + "\n")
    return {
        "status": "accepted",
        "source": source,
        "stored": True,
        "path": str(path),
        "claim_boundary": (
            "This acknowledges webhook receipt only. It does not prove payment, "
            "escrow release, on-chain payout, or received funds."
        ),
    }


def decode_payment_required_header(value: str) -> dict[str, Any] | None:
    if not value:
        return None
    try:
        padding = "=" * (-len(value) % 4)
        decoded = base64.urlsafe_b64decode((value + padding).encode("ascii")).decode("utf-8")
        payload = json.loads(decoded)
    except (binascii.Error, UnicodeDecodeError, json.JSONDecodeError, ValueError):
        return None
    return payload if isinstance(payload, dict) else None


def _install_x402_middleware(app: FastAPI, settings: PaidApiSettings) -> tuple[bool, str]:
    if not settings.x402_enabled:
        return False, "x402 disabled by X0T_X402_ENABLED"

    try:
        from x402 import x402ResourceServer
        from x402.http import HTTPFacilitatorClient, PaywallConfig
        from x402.http.middleware.fastapi import payment_middleware
        from x402.mechanisms.evm.exact import ExactEvmServerScheme
    except Exception as exc:  # pragma: no cover - depends on optional package
        return False, f"x402 optional dependency missing or broken: {exc}"

    facilitator = HTTPFacilitatorClient({"url": settings.facilitator_url})
    server = x402ResourceServer(facilitator)
    server.register(settings.network, ExactEvmServerScheme())
    routes = build_routes_config(settings)
    paywall_config = PaywallConfig(
        app_name="x0tta6bl4 paid API",
        testnet=settings.network != DEFAULT_NETWORK,
    )

    x402_guard = payment_middleware(
        routes,
        server,
        paywall_config=paywall_config,
        sync_facilitator_on_start=True,
    )

    @app.middleware("http")
    async def x402_middleware(request: Request, call_next):  # type: ignore[no-untyped-def]
        try:
            response = await x402_guard(request, call_next)
            if response.status_code == 402:
                encoded = response.headers.get("payment-required", "")
                decoded = decode_payment_required_header(encoded)
                if decoded:
                    decoded = enrich_payment_required_payload(decoded, settings=settings)
                    headers = dict(response.headers)
                    headers.pop("content-length", None)
                    headers.pop("Content-Length", None)
                    headers["payment-required"] = encode_payment_required_payload(decoded)
                    return JSONResponse(status_code=402, content=decoded, headers=headers)
            return response
        except Exception as exc:
            return JSONResponse(
                status_code=502,
                content={
                    "error": "x402 payment gate unavailable",
                    "detail": str(exc),
                    "claim_gate": {
                        "payment_enforced_claim_allowed": False,
                        "funds_received_claim_allowed": False,
                    },
                },
            )

    return True, "x402 middleware enabled"


def _bothire_access_token(request: Request, payload: dict[str, Any] | None = None) -> str:
    header_token = request.headers.get("x-bothire-access-token", "").strip()
    if header_token:
        return header_token
    auth = request.headers.get("authorization", "").strip()
    if auth.lower().startswith("bearer "):
        return auth.split(" ", 1)[1].strip()
    query_token = (
        request.query_params.get("access_token")
        or request.query_params.get("token")
        or ""
    ).strip()
    if query_token:
        return query_token
    if payload:
        for key in ("access_token", "token", "hire_token"):
            value = payload.get(key)
            if isinstance(value, str) and value.strip():
                return value.strip()
    return ""


def _bothire_tool_payload(payload: dict[str, Any]) -> dict[str, Any]:
    inner = payload.get("payload")
    if isinstance(inner, dict):
        return dict(inner)
    return {
        key: value
        for key, value in payload.items()
        if key not in {"access_token", "token", "hire_token"}
    }


def _agent402_tool_payload(payload: dict[str, Any]) -> dict[str, Any]:
    for key in ("payload", "input", "arguments"):
        inner = payload.get(key)
        if isinstance(inner, dict):
            return dict(inner)
    return dict(payload)


def verify_bothire_access_token(
    token: str,
    *,
    api_base: str = DEFAULT_BOTHIRE_API_BASE,
    timeout_seconds: float = 12.0,
) -> dict[str, Any]:
    if not token:
        return {"valid": False, "reason": "missing_access_token"}
    url = f"{api_base.rstrip('/')}/api/hires/check-access?{urllib.parse.urlencode({'token': token})}"
    request = urllib.request.Request(
        url,
        headers={
            "Accept": "application/json",
            "User-Agent": "x0tta6bl4-bothire-direct-endpoint",
        },
        method="GET",
    )
    try:
        with urllib.request.urlopen(request, timeout=timeout_seconds) as response:
            body = response.read().decode("utf-8")
            payload = {}
            if body:
                import json

                payload = json.loads(body)
            if isinstance(payload, dict):
                return payload
            return {"valid": False, "reason": "unexpected_access_response"}
    except urllib.error.HTTPError as exc:
        return {"valid": False, "reason": f"http_{exc.code}"}
    except Exception as exc:
        return {"valid": False, "reason": exc.__class__.__name__}


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
    async def x402_compat_402_body(request: Request, call_next):  # type: ignore[no-untyped-def]
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

    @app.get("/health")
    async def health() -> dict[str, Any]:
        return {
            "status": "ok",
            "paid_api_available": bool(app.state.x402_available),
            "x402_status": app.state.x402_status,
            "claim_gate": {
                "funds_received_claim_allowed": False,
                "payment_enforced_claim_allowed": bool(app.state.x402_available),
            },
        }

    @app.get("/", response_class=HTMLResponse)
    async def homepage(request: Request) -> HTMLResponse:
        base_url = _public_base_url(request)
        services = build_public_services(base_url, settings)
        api_docs = next(item for item in services if item["id"] == "x0tta6bl4-api-docs")
        json_ld = {
            "@context": "https://schema.org",
            "@type": "SoftwareApplication",
            "name": "x0tta6bl4 paid x402 tools",
            "applicationCategory": "DeveloperApplication",
            "operatingSystem": "Web",
            "description": (
                "Public-input x402 paid tools for API docs generation, repository triage, "
                "payment risk checks, income-route scoring, URL snapshots, and domain health."
            ),
            "url": base_url,
            "offers": {
                "@type": "Offer",
                "price": api_docs["price_usdc"],
                "priceCurrency": "USDC",
                "url": api_docs["url"],
            },
            "provider": {
                "@type": "Organization",
                "name": "x0tta6bl4",
                "url": base_url,
            },
        }
        body = f"""<!doctype html>
<html lang=\"en\">
<head>
  <meta charset=\"utf-8\">
  <meta name=\"viewport\" content=\"width=device-width, initial-scale=1\">
  <title>x0tta6bl4 paid x402 tools</title>
  <meta name=\"description\" content=\"Public-input x402 paid developer tools on Base USDC.\">
  <link rel=\"alternate\" type=\"application/json\" href=\"{base_url}/.well-known/x402.json\">
  <link rel=\"alternate\" type=\"application/json\" href=\"{base_url}/.well-known/openapi.json\">
  <link rel=\"alternate\" type=\"application/json\" href=\"{base_url}/.well-known/agent-card.json\">
  <link rel=\"alternate\" type=\"application/json\" href=\"{base_url}/.well-known/agent-descriptions\">
  <link rel=\"alternate\" type=\"application/json\" href=\"{base_url}/.well-known/agent-pulse\">
  <link rel=\"alternate\" type=\"application/json\" href=\"{base_url}/.well-known/mcp/server.json\">
  <link rel=\"alternate\" type=\"application/json\" href=\"{base_url}/.well-known/machina-agent.json\">
  <link rel=\"alternate\" type=\"application/json\" href=\"{base_url}/.well-known/oracle-net.json\">
  <link rel=\"alternate\" type=\"application/json\" href=\"{base_url}/mcp-manifest\">
  <script type=\"application/ld+json\">{json.dumps(json_ld, separators=(",", ":"))}</script>
</head>
<body>
  <main>
    <h1>x0tta6bl4 paid x402 tools</h1>
    <p>Public-input x402 paid developer tools on Base USDC.</p>
    <ul>
      <li><a href=\"{base_url}/.well-known/x402.json\">x402 manifest</a></li>
      <li><a href=\"{base_url}/.well-known/x402-discovery\">x402 discovery</a></li>
      <li><a href=\"{base_url}/.well-known/openapi.json\">OpenAPI JSON</a></li>
      <li><a href=\"{base_url}/.well-known/agent-card.json\">agent card</a></li>
      <li><a href=\"{base_url}/.well-known/agent-descriptions\">agent descriptions</a></li>
      <li><a href=\"{base_url}/.well-known/agent-pulse\">agent pulse</a></li>
      <li><a href=\"{base_url}/.well-known/mcp/server.json\">MCP server manifest</a></li>
      <li><a href=\"{base_url}/.well-known/machina-agent.json\">Machina manifest</a></li>
      <li><a href=\"{base_url}/.well-known/oracle-net.json\">OracleNet manifest</a></li>
      <li><a href=\"{base_url}/mcp-manifest\">MCP manifest</a></li>
      <li><a href=\"{base_url}/agent402/services\">Agent402 services</a></li>
      <li><a href=\"{base_url}/docs\">OpenAPI docs</a></li>
    </ul>
  </main>
</body>
</html>"""
        return HTMLResponse(content=body)

    @app.get("/robots.txt", response_class=PlainTextResponse)
    async def robots_txt(request: Request) -> PlainTextResponse:
        base_url = _public_base_url(request)
        return PlainTextResponse(
            "User-agent: *\n"
            "Allow: /\n"
            f"Sitemap: {base_url}/sitemap.xml\n"
        )

    @app.get("/sitemap.xml", response_class=PlainTextResponse)
    async def sitemap_xml(request: Request) -> PlainTextResponse:
        base_url = _public_base_url(request)
        urls = [
            base_url,
            f"{base_url}/.well-known/x402.json",
            f"{base_url}/.well-known/x402-discovery",
            f"{base_url}/.well-known/openapi.json",
            f"{base_url}/.well-known/agent.json",
            f"{base_url}/.well-known/agent-card.json",
            f"{base_url}/.well-known/agent-descriptions",
            f"{base_url}/.well-known/agent-pulse",
            f"{base_url}/.well-known/mcp/server.json",
            f"{base_url}/.well-known/jwks.json",
            f"{base_url}/.well-known/oracle-net.json",
            f"{base_url}/.well-known/machina-agent.json",
            f"{base_url}/.well-known/x402",
            f"{base_url}/.well-known/x402/manifest.json",
            f"{base_url}/mcp-manifest",
            f"{base_url}/llms.txt",
            f"{base_url}/agent402/services",
            f"{base_url}/preview/catalog",
            f"{base_url}/docs",
        ]
        urls.extend(
            f"{base_url}/.well-known/machina/{service['id']}.json"
            for service in build_public_services(base_url, settings)
        )
        body = "<?xml version=\"1.0\" encoding=\"UTF-8\"?>\n"
        body += "<urlset xmlns=\"http://www.sitemaps.org/schemas/sitemap/0.9\">\n"
        for url in urls:
            body += f"  <url><loc>{url}</loc></url>\n"
        body += "</urlset>\n"
        return PlainTextResponse(body, media_type="application/xml")

    @app.get("/x402/catalog")
    async def catalog() -> dict[str, Any]:
        return {
            "schema": "x0tta6bl4.x402_paid_api_catalog.v1",
            "pay_to": settings.pay_to,
            "network": settings.network,
            "facilitator_url": settings.facilitator_url,
            "routes": build_routes_config(settings),
            "paid_api_available": bool(app.state.x402_available),
            "x402_status": app.state.x402_status,
        }

    @app.head("/paid/{service_slug}")
    async def paid_service_head(service_slug: str, request: Request) -> Response:
        path = f"/paid/{service_slug}"
        base_url = _public_base_url(request)
        services = build_public_services(base_url, settings)
        service = next(
            (item for item in services if urllib.parse.urlparse(item["url"]).path == path),
            None,
        )
        if service is None:
            raise HTTPException(status_code=404, detail="unknown paid service")
        return Response(
            status_code=204,
            headers={
                "X-Paid-API": "x402",
                "X-Paid-API-Service": service["id"],
                "X-Paid-API-Price-USDC": str(service["price_usdc"]),
                "X-Paid-API-Network": settings.network,
                "X-Paid-API-Pay-To": settings.pay_to,
            },
        )

    @app.get("/.well-known/x402-discovery")
    async def x402_discovery(request: Request) -> dict[str, Any]:
        return build_discovery_payload(_public_base_url(request), settings)

    @app.get("/.well-known/x402.json")
    async def x402_json_discovery(request: Request) -> dict[str, Any]:
        return build_discovery_payload(_public_base_url(request), settings)

    @app.get("/.well-known/x402")
    async def x402_well_known(request: Request) -> dict[str, Any]:
        return build_discovery_payload(_public_base_url(request), settings)

    @app.get("/.well-known/x402/manifest.json")
    async def x402_manifest(request: Request) -> dict[str, Any]:
        return build_discovery_payload(_public_base_url(request), settings)

    @app.get("/.well-known/openapi.json")
    async def well_known_openapi() -> dict[str, Any]:
        return app.openapi()

    @app.get("/.well-known/agent.json")
    async def agent_card(request: Request) -> dict[str, Any]:
        return build_agent_card(_public_base_url(request), settings)

    @app.get("/.well-known/agent-card.json")
    async def agent_card_alias(request: Request) -> dict[str, Any]:
        return build_agent_card(_public_base_url(request), settings)

    @app.get("/.well-known/agent-descriptions")
    async def agent_descriptions(request: Request) -> dict[str, Any]:
        return build_agent_descriptions(_public_base_url(request), settings)

    @app.get("/.well-known/agent-pulse")
    async def agent_pulse(request: Request) -> dict[str, Any]:
        base_url = _public_base_url(request)
        return {
            "schema": "x0tta6bl4.agent_pulse.v1",
            "name": "x0tta6bl4 paid x402 tools",
            "status": "online",
            "origin": base_url,
            "checked_at": utc_now(),
            "paid_api_available": bool(app.state.x402_available),
            "x402_status": app.state.x402_status,
            "service_count": len(build_public_services(base_url, settings)),
            "discovery": {
                "x402": f"{base_url}/.well-known/x402.json",
                "openapi": f"{base_url}/.well-known/openapi.json",
                "mcp_server": f"{base_url}/.well-known/mcp/server.json",
                "agent_card": f"{base_url}/.well-known/agent.json",
            },
            "payment": {
                "network": settings.network,
                "asset": USDC_ASSET_ADDRESS,
                "payTo": settings.pay_to,
                "facilitator": settings.facilitator_url,
            },
            "claim_boundary": (
                "This pulse proves only that the metadata endpoint responded. It does "
                "not prove buyer traffic, payment settlement, payout, or received funds."
            ),
        }

    @app.get("/.well-known/jwks.json")
    async def jwks() -> dict[str, Any]:
        return {
            "keys": [],
            "claim_boundary": (
                "No signing keys are advertised by this public paid API yet. Use x402 "
                "payment metadata and on-chain settlement checks for payment verification."
            ),
        }

    @app.get("/.well-known/oracle-net.json")
    async def oracle_net_manifest(request: Request) -> dict[str, Any]:
        return build_oracle_net_manifest(_public_base_url(request), settings)

    @app.get("/.well-known/machina-agent.json")
    async def machina_agent_manifest(request: Request) -> dict[str, Any]:
        return build_machina_agent_manifest(_public_base_url(request), settings)

    @app.get("/.well-known/machina/{service_id}.json")
    async def machina_service_manifest(service_id: str, request: Request) -> dict[str, Any]:
        try:
            return build_machina_agent_manifest(_public_base_url(request), settings, service_id)
        except KeyError as exc:
            raise HTTPException(status_code=404, detail=str(exc)) from exc

    @app.get("/mcp-manifest")
    async def mcp_manifest(request: Request) -> dict[str, Any]:
        base_url = _public_base_url(request)
        return {
            "schema": "x0tta6bl4.mcp_manifest.v1",
            "name": "x0tta6bl4 paid tools",
            "description": "x402-paid developer tools for agents.",
            "tools": [
                {
                    "name": "x0tta6bl4_repo_triage",
                    "description": "Paid repository triage from submitted file snippets.",
                    "endpoint": f"{base_url}/paid/repo-triage",
                    "method": "POST",
                    "price_usd": float(settings.repo_triage_price.strip("$")),
                    "input_schema": RepoTriageRequest.model_json_schema(),
                },
                {
                    "name": "x0tta6bl4_api_docs",
                    "description": "Paid API documentation generator from endpoint specs.",
                    "endpoint": f"{base_url}/paid/api-docs",
                    "method": "POST",
                    "price_usd": float(settings.api_docs_price.strip("$")),
                    "input_schema": ApiDocsRequest.model_json_schema(),
                },
                {
                    "name": "x0tta6bl4_listing_audit",
                    "description": "Paid audit for agent marketplace listings and service cards.",
                    "endpoint": f"{base_url}/paid/listing-audit",
                    "method": "POST",
                    "price_usd": float(settings.listing_audit_price.strip("$")),
                    "input_schema": ListingAuditRequest.model_json_schema(),
                },
                {
                    "name": "x0tta6bl4_payment_risk",
                    "description": "Paid x402 payment metadata risk report for autonomous wallet decisions.",
                    "endpoint": f"{base_url}/paid/payment-risk",
                    "method": "POST",
                    "price_usd": float(settings.payment_risk_price.strip("$")),
                    "input_schema": PaymentRiskRequest.model_json_schema(),
                },
                {
                    "name": "x0tta6bl4_income_route",
                    "description": "Paid non-bounty earning route score by token cost, risk, and payment certainty.",
                    "endpoint": f"{base_url}/paid/income-route",
                    "method": "POST",
                    "price_usd": float(settings.income_route_price.strip("$")),
                    "input_schema": IncomeRouteRequest.model_json_schema(),
                },
                {
                    "name": "x0tta6bl4_x402_validate",
                    "description": "Paid live x402 endpoint validator for HTTP 402 and Payment-Required metadata.",
                    "endpoint": f"{base_url}/paid/x402-validate",
                    "method": "POST",
                    "price_usd": float(settings.x402_validate_price.strip("$")),
                    "input_schema": X402ValidateRequest.model_json_schema(),
                },
                {
                    "name": "x0tta6bl4_url_snapshot",
                    "description": "Paid public URL snapshot for title, metadata, headings, links, and text preview.",
                    "endpoint": f"{base_url}/paid/url-snapshot",
                    "method": "POST",
                    "price_usd": float(settings.url_snapshot_price.strip("$")),
                    "input_schema": UrlSnapshotRequest.model_json_schema(),
                },
                {
                    "name": "x0tta6bl4_domain_health",
                    "description": "Paid public domain health check for DNS/IP, HTTP status, redirect, and TLS expiry signals.",
                    "endpoint": f"{base_url}/paid/domain-health",
                    "method": "POST",
                    "price_usd": float(settings.domain_health_price.strip("$")),
                    "input_schema": DomainHealthRequest.model_json_schema(),
                },
            ],
            "payment": {
                "scheme": "exact",
                "network": settings.network,
                "asset": "0x833589fCD6eDb6E08f4c7C32D4f71b54bdA02913",
                "payTo": settings.pay_to,
                "facilitator": settings.facilitator_url,
            },
        }

    @app.get("/.well-known/mcp/server.json")
    async def well_known_mcp_server(request: Request) -> dict[str, Any]:
        return await mcp_manifest(request)

    @app.get("/llms.txt")
    async def llms_txt(request: Request) -> PlainTextResponse:
        base_url = _public_base_url(request)
        body = "\n".join(
            [
                "# x0tta6bl4 paid tools",
                "",
                "This origin exposes x402-paid developer tools for AI agents.",
                "",
                f"- Repo triage: POST {base_url}/paid/repo-triage costs {settings.repo_triage_price} USDC on Base.",
                f"- API docs generator: POST {base_url}/paid/api-docs costs {settings.api_docs_price} USDC on Base.",
                f"- Agent listing audit: POST {base_url}/paid/listing-audit costs {settings.listing_audit_price} USDC on Base.",
                f"- Payment risk report: POST {base_url}/paid/payment-risk costs {settings.payment_risk_price} USDC on Base.",
                f"- Income route score: POST {base_url}/paid/income-route costs {settings.income_route_price} USDC on Base.",
                f"- x402 endpoint validator: POST {base_url}/paid/x402-validate costs {settings.x402_validate_price} USDC on Base.",
                f"- Public URL snapshot: POST {base_url}/paid/url-snapshot costs {settings.url_snapshot_price} USDC on Base.",
                f"- Domain Health Lite: POST {base_url}/paid/domain-health costs {settings.domain_health_price} USDC on Base.",
                f"- AgentBazaar push endpoint: POST {base_url}/agentbazaar/task returns a result body for prepaid AgentBazaar tasks.",
                f"- Clustly webhook endpoint: POST {base_url}/clustly/webhook records task/order events from Clustly.",
                f"- AgentPact webhook endpoint: POST {base_url}/agentpact/webhook records paid need/deal alerts from AgentPact.",
                f"- Free preview router: POST {base_url}/preview/route returns the matching paid endpoint.",
                f"- Discovery JSON: {base_url}/.well-known/x402-discovery",
                f"- x402 JSON alias: {base_url}/.well-known/x402.json",
                f"- Agent descriptions JSON-LD: {base_url}/.well-known/agent-descriptions",
                f"- Agent pulse: {base_url}/.well-known/agent-pulse",
                f"- MCP server manifest: {base_url}/.well-known/mcp/server.json",
                f"- MCP manifest: {base_url}/mcp-manifest",
                f"- OracleNet-style manifest: {base_url}/.well-known/oracle-net.json",
                f"- Payment receiver: {settings.pay_to}",
                "",
            ]
        )
        return PlainTextResponse(body)

    @app.get("/preview/catalog")
    async def preview_catalog(request: Request) -> dict[str, Any]:
        base_url = _public_base_url(request)
        return {
            "schema": "x0tta6bl4.free_preview_catalog.v1",
            "description": "Free router for choosing the matching paid x402 tool.",
            "endpoint": f"{base_url}/preview/route",
            "input_schema": PreviewRouteRequest.model_json_schema(),
            "paid_services": build_public_services(base_url, settings),
            "claim_boundary": (
                "This catalog is free and informational. It does not prove buyer traffic, "
                "payment settlement, on-chain payout, or received funds."
            ),
        }

    @app.post("/preview/route")
    async def preview_route(payload: PreviewRouteRequest, request: Request) -> dict[str, Any]:
        return build_preview_route(payload, base_url=_public_base_url(request), settings=settings)

    @app.get("/agentmart/products/{product_file}")
    async def agentmart_product_file(product_file: str) -> PlainTextResponse:
        path = AGENTMART_PRODUCT_FILES.get(product_file)
        if path is None:
            raise HTTPException(status_code=404, detail="product file not found")
        try:
            text = path.read_text(encoding="utf-8")
        except OSError:
            raise HTTPException(status_code=404, detail="product file unavailable")
        return PlainTextResponse(text, media_type="text/markdown")

    @app.get("/workprotocol/deliverables/{artifact_path:path}")
    async def workprotocol_deliverable_file(artifact_path: str) -> FileResponse:
        try:
            root = _workprotocol_deliverable_dir().resolve()
            candidate = (root / artifact_path).resolve()
        except OSError:
            raise HTTPException(status_code=404, detail="deliverable file unavailable")
        if root != candidate and root not in candidate.parents:
            raise HTTPException(status_code=404, detail="deliverable file not found")
        if not candidate.is_file():
            raise HTTPException(status_code=404, detail="deliverable file not found")
        return FileResponse(candidate)

    @app.get("/bothire/health")
    async def bothire_health(request: Request) -> dict[str, Any]:
        base_url = _public_base_url(request)
        return {
            "status": "ok",
            "schema": "x0tta6bl4.bothire_direct_health.v1",
            "verify_access": settings.bothire_verify_access,
            "tools": [
                {
                    "name": "api-docs",
                    "method": "POST",
                    "endpoint": f"{base_url}/bothire/api-docs",
                    "input_schema": ApiDocsRequest.model_json_schema(),
                },
                {
                    "name": "repo-triage",
                    "method": "POST",
                    "endpoint": f"{base_url}/bothire/repo-triage",
                    "input_schema": RepoTriageRequest.model_json_schema(),
                },
                {
                    "name": "listing-audit",
                    "method": "POST",
                    "endpoint": f"{base_url}/bothire/listing-audit",
                    "input_schema": ListingAuditRequest.model_json_schema(),
                },
                {
                    "name": "payment-risk",
                    "method": "POST",
                    "endpoint": f"{base_url}/bothire/payment-risk",
                    "input_schema": PaymentRiskRequest.model_json_schema(),
                },
                {
                    "name": "income-route",
                    "method": "POST",
                    "endpoint": f"{base_url}/bothire/income-route",
                    "input_schema": IncomeRouteRequest.model_json_schema(),
                },
                {
                    "name": "x402-validate",
                    "method": "POST",
                    "endpoint": f"{base_url}/bothire/x402-validate",
                    "input_schema": X402ValidateRequest.model_json_schema(),
                },
                {
                    "name": "url-snapshot",
                    "method": "POST",
                    "endpoint": f"{base_url}/bothire/url-snapshot",
                    "input_schema": UrlSnapshotRequest.model_json_schema(),
                },
                {
                    "name": "domain-health",
                    "method": "POST",
                    "endpoint": f"{base_url}/bothire/domain-health",
                    "input_schema": DomainHealthRequest.model_json_schema(),
                },
            ],
            "claim_gate": {
                "bot_hire_delivery_endpoint_ready": True,
                "funds_received_claim_allowed": False,
            },
        }

    @app.post("/agentworld/message")
    async def agentworld_message(payload: AgentWorldMessageRequest, request: Request) -> dict[str, Any]:
        return build_agentworld_reply(payload, base_url=_public_base_url(request), settings=settings)

    @app.get("/agentbazaar/task")
    async def agentbazaar_task_info(request: Request) -> dict[str, Any]:
        base_url = _public_base_url(request)
        return {
            "status": "ok",
            "schema": "x0tta6bl4.agentbazaar_task_endpoint.v1",
            "method": "POST",
            "endpoint": f"{base_url}/agentbazaar/task",
            "input_schema": AgentBazaarTaskRequest.model_json_schema(),
            "output_schema": "x0tta6bl4.agentbazaar_task_result.v1",
            "claim_boundary": (
                "This endpoint status is public. It does not prove buyer tasks, "
                "payment settlement, or received funds."
            ),
        }

    @app.head("/agentbazaar/task")
    async def agentbazaar_task_head() -> Response:
        return Response(
            status_code=204,
            headers={
                "X-Agent-Endpoint": "agentbazaar-task",
                "X-Agent-Endpoint-Method": "POST",
            },
        )

    @app.post("/agentbazaar/task")
    async def agentbazaar_task(payload: AgentBazaarTaskRequest, request: Request) -> dict[str, Any]:
        return build_agentbazaar_task_result(payload, base_url=_public_base_url(request), settings=settings)

    @app.post("/clustly/webhook")
    async def clustly_webhook(payload: dict[str, Any]) -> dict[str, Any]:
        return persist_webhook_event("clustly", payload)

    @app.post("/agoragentic/webhook")
    async def agoragentic_webhook(payload: dict[str, Any]) -> dict[str, Any]:
        return persist_webhook_event("agoragentic", payload)

    @app.post("/agentpact/webhook")
    async def agentpact_webhook(payload: dict[str, Any]) -> dict[str, Any]:
        return persist_webhook_event("agentpact", payload)

    @app.post("/payanagent/webhook")
    async def payanagent_webhook(payload: dict[str, Any]) -> dict[str, Any]:
        return persist_webhook_event("payanagent", payload)

    def _require_bothire_access(request: Request, payload: dict[str, Any] | None = None) -> dict[str, Any]:
        if not settings.bothire_verify_access:
            return {"valid": True, "mode": "verification_disabled"}
        access = verify_bothire_access_token(
            _bothire_access_token(request, payload),
            api_base=settings.bothire_api_base,
        )
        if access.get("valid") is not True:
            raise HTTPException(
                status_code=403,
                detail={
                    "error": "BotHire access token is missing or invalid",
                    "access": access,
                    "claim_gate": {
                        "bot_hire_paid_access_claim_allowed": False,
                        "funds_received_claim_allowed": False,
                    },
                },
            )
        return access

    @app.post("/bothire/api-docs")
    async def bothire_api_docs(payload: dict[str, Any], request: Request) -> dict[str, Any]:
        access = _require_bothire_access(request, payload)
        package = build_api_docs_package(ApiDocsRequest.model_validate(_bothire_tool_payload(payload)))
        return {
            "schema": "x0tta6bl4.bothire_api_docs_delivery.v1",
            "tool": "api-docs",
            "access": {
                "valid": bool(access.get("valid")),
                "hire_id": access.get("hire_id"),
                "post_id": access.get("post_id"),
            },
            "package": package,
            "claim_boundary": (
                "This response proves BotHire token validation and generated output only. "
                "It does not prove customer completion, escrow release, on-chain payout, "
                "or received funds."
            ),
        }

    @app.post("/bothire/repo-triage")
    async def bothire_repo_triage(payload: dict[str, Any], request: Request) -> dict[str, Any]:
        access = _require_bothire_access(request, payload)
        report = build_repo_triage_report(RepoTriageRequest.model_validate(_bothire_tool_payload(payload)))
        return {
            "schema": "x0tta6bl4.bothire_repo_triage_delivery.v1",
            "tool": "repo-triage",
            "access": {
                "valid": bool(access.get("valid")),
                "hire_id": access.get("hire_id"),
                "post_id": access.get("post_id"),
            },
            "report": report,
            "claim_boundary": (
                "This response proves BotHire token validation and generated output only. "
                "It does not prove customer completion, escrow release, on-chain payout, "
                "or received funds."
            ),
        }

    @app.post("/bothire/listing-audit")
    async def bothire_listing_audit(payload: dict[str, Any], request: Request) -> dict[str, Any]:
        access = _require_bothire_access(request, payload)
        report = build_listing_audit_report(ListingAuditRequest.model_validate(_bothire_tool_payload(payload)))
        return {
            "schema": "x0tta6bl4.bothire_listing_audit_delivery.v1",
            "tool": "listing-audit",
            "access": {
                "valid": bool(access.get("valid")),
                "hire_id": access.get("hire_id"),
                "post_id": access.get("post_id"),
            },
            "report": report,
            "claim_boundary": (
                "This response proves BotHire token validation and generated output only. "
                "It does not prove customer completion, escrow release, on-chain payout, "
                "or received funds."
            ),
        }

    @app.post("/bothire/payment-risk")
    async def bothire_payment_risk(payload: dict[str, Any], request: Request) -> dict[str, Any]:
        access = _require_bothire_access(request, payload)
        report = build_payment_risk_report(PaymentRiskRequest.model_validate(_bothire_tool_payload(payload)))
        return {
            "schema": "x0tta6bl4.bothire_payment_risk_delivery.v1",
            "tool": "payment-risk",
            "access": {
                "valid": bool(access.get("valid")),
                "hire_id": access.get("hire_id"),
                "post_id": access.get("post_id"),
            },
            "report": report,
            "claim_boundary": (
                "This response proves BotHire token validation and generated output only. "
                "It does not prove customer completion, escrow release, on-chain payout, "
                "or received funds."
            ),
        }

    @app.post("/bothire/income-route")
    async def bothire_income_route(payload: dict[str, Any], request: Request) -> dict[str, Any]:
        access = _require_bothire_access(request, payload)
        report = build_income_route_report(IncomeRouteRequest.model_validate(_bothire_tool_payload(payload)))
        return {
            "schema": "x0tta6bl4.bothire_income_route_delivery.v1",
            "tool": "income-route",
            "access": {
                "valid": bool(access.get("valid")),
                "hire_id": access.get("hire_id"),
                "post_id": access.get("post_id"),
            },
            "report": report,
            "claim_boundary": (
                "This response proves BotHire token validation and generated output only. "
                "It does not prove customer completion, escrow release, on-chain payout, "
                "or received funds."
            ),
        }

    @app.post("/bothire/x402-validate")
    async def bothire_x402_validate(payload: dict[str, Any], request: Request) -> dict[str, Any]:
        access = _require_bothire_access(request, payload)
        report = build_x402_validate_report(X402ValidateRequest.model_validate(_bothire_tool_payload(payload)))
        return {
            "schema": "x0tta6bl4.bothire_x402_validate_delivery.v1",
            "tool": "x402-validate",
            "access": {
                "valid": bool(access.get("valid")),
                "hire_id": access.get("hire_id"),
                "post_id": access.get("post_id"),
            },
            "report": report,
            "claim_boundary": (
                "This response proves BotHire token validation and generated output only. "
                "It does not prove customer completion, escrow release, on-chain payout, "
                "or received funds."
            ),
        }

    @app.post("/bothire/url-snapshot")
    async def bothire_url_snapshot(payload: dict[str, Any], request: Request) -> dict[str, Any]:
        access = _require_bothire_access(request, payload)
        report = build_url_snapshot_report(UrlSnapshotRequest.model_validate(_bothire_tool_payload(payload)))
        return {
            "schema": "x0tta6bl4.bothire_url_snapshot_delivery.v1",
            "tool": "url-snapshot",
            "access": {
                "valid": bool(access.get("valid")),
                "hire_id": access.get("hire_id"),
                "post_id": access.get("post_id"),
            },
            "report": report,
            "claim_boundary": (
                "This response proves BotHire token validation and generated output only. "
                "It does not prove customer completion, escrow release, on-chain payout, "
                "or received funds."
            ),
        }

    @app.post("/bothire/domain-health")
    async def bothire_domain_health(payload: dict[str, Any], request: Request) -> dict[str, Any]:
        access = _require_bothire_access(request, payload)
        report = build_domain_health_report(DomainHealthRequest.model_validate(_bothire_tool_payload(payload)))
        return {
            "schema": "x0tta6bl4.bothire_domain_health_delivery.v1",
            "tool": "domain-health",
            "access": {
                "valid": bool(access.get("valid")),
                "hire_id": access.get("hire_id"),
                "post_id": access.get("post_id"),
            },
            "report": report,
            "claim_boundary": (
                "This response proves BotHire token validation and generated output only. "
                "It does not prove customer completion, escrow release, on-chain payout, "
                "or received funds."
            ),
        }

    @app.get("/agent402/services")
    async def agent402_services(request: Request) -> dict[str, Any]:
        base_url = _public_base_url(request)
        return {
            "schema": "x0tta6bl4.agent402_services.v1",
            "agent_name": "x0tta6bl4 paid x402 tools",
            "settlement": {
                "platform": "Agent402",
                "network": "Base",
                "asset": "USDC",
                "pay_to": settings.pay_to,
            },
            "services": [
                {
                    "name": "x0tta6bl4 Repo Triage",
                    "endpoint": f"{base_url}/agent402/repo-triage",
                    "price_usdc": settings.repo_triage_price,
                    "description": "Repository triage from submitted public file snippets.",
                },
                {
                    "name": "x0tta6bl4 API Docs Generator",
                    "endpoint": f"{base_url}/agent402/api-docs",
                    "price_usdc": settings.api_docs_price,
                    "description": "Markdown API docs from submitted REST endpoint specs.",
                },
                {
                    "name": "x0tta6bl4 Agent Listing Audit",
                    "endpoint": f"{base_url}/agent402/listing-audit",
                    "price_usdc": settings.listing_audit_price,
                    "description": "Marketplace listing score and conversion fixes.",
                },
                {
                    "name": "x0tta6bl4 Payment Risk Report",
                    "endpoint": f"{base_url}/agent402/payment-risk",
                    "price_usdc": settings.payment_risk_price,
                    "description": "Public payment metadata risk report.",
                },
                {
                    "name": "x0tta6bl4 Income Route",
                    "endpoint": f"{base_url}/agent402/income-route",
                    "price_usdc": settings.income_route_price,
                    "description": "Non-bounty earning route score.",
                },
                {
                    "name": "x0tta6bl4 x402 Endpoint Validator",
                    "endpoint": f"{base_url}/agent402/x402-validate",
                    "price_usdc": settings.x402_validate_price,
                    "description": "Live x402 endpoint metadata validator.",
                },
                {
                    "name": "x0tta6bl4 Public URL Snapshot",
                    "endpoint": f"{base_url}/agent402/url-snapshot",
                    "price_usdc": settings.url_snapshot_price,
                    "description": "Public URL title, metadata, headings, links, and text preview.",
                },
                {
                    "name": "x0tta6bl4 Domain Health Lite",
                    "endpoint": f"{base_url}/agent402/domain-health",
                    "price_usdc": settings.domain_health_price,
                    "description": "DNS/IP, HTTP, redirect, and TLS expiry signals for a public domain or URL.",
                },
            ],
            "claim_boundary": (
                "These endpoints are for Agent402 post-settlement forwarding. Direct calls only "
                "prove generated output, not Agent402 settlement or received funds."
            ),
        }

    @app.post("/agent402/repo-triage")
    async def agent402_repo_triage(payload: dict[str, Any]) -> dict[str, Any]:
        report = build_repo_triage_report(RepoTriageRequest.model_validate(_agent402_tool_payload(payload)))
        return {
            "schema": "x0tta6bl4.agent402_repo_triage_delivery.v1",
            "platform": "agent402",
            "tool": "repo-triage",
            "report": report,
            "claim_boundary": "Generated output only; verify Agent402 settlement and target wallet before claiming funds.",
        }

    @app.post("/agent402/api-docs")
    async def agent402_api_docs(payload: dict[str, Any]) -> dict[str, Any]:
        package = build_api_docs_package(ApiDocsRequest.model_validate(_agent402_tool_payload(payload)))
        return {
            "schema": "x0tta6bl4.agent402_api_docs_delivery.v1",
            "platform": "agent402",
            "tool": "api-docs",
            "package": package,
            "claim_boundary": "Generated output only; verify Agent402 settlement and target wallet before claiming funds.",
        }

    @app.post("/agent402/listing-audit")
    async def agent402_listing_audit(payload: dict[str, Any]) -> dict[str, Any]:
        report = build_listing_audit_report(ListingAuditRequest.model_validate(_agent402_tool_payload(payload)))
        return {
            "schema": "x0tta6bl4.agent402_listing_audit_delivery.v1",
            "platform": "agent402",
            "tool": "listing-audit",
            "report": report,
            "claim_boundary": "Generated output only; verify Agent402 settlement and target wallet before claiming funds.",
        }

    @app.post("/agent402/payment-risk")
    async def agent402_payment_risk(payload: dict[str, Any]) -> dict[str, Any]:
        report = build_payment_risk_report(PaymentRiskRequest.model_validate(_agent402_tool_payload(payload)))
        return {
            "schema": "x0tta6bl4.agent402_payment_risk_delivery.v1",
            "platform": "agent402",
            "tool": "payment-risk",
            "report": report,
            "claim_boundary": "Generated output only; verify Agent402 settlement and target wallet before claiming funds.",
        }

    @app.post("/agent402/income-route")
    async def agent402_income_route(payload: dict[str, Any]) -> dict[str, Any]:
        report = build_income_route_report(IncomeRouteRequest.model_validate(_agent402_tool_payload(payload)))
        return {
            "schema": "x0tta6bl4.agent402_income_route_delivery.v1",
            "platform": "agent402",
            "tool": "income-route",
            "report": report,
            "claim_boundary": "Generated output only; verify Agent402 settlement and target wallet before claiming funds.",
        }

    @app.post("/agent402/x402-validate")
    async def agent402_x402_validate(payload: dict[str, Any]) -> dict[str, Any]:
        report = build_x402_validate_report(X402ValidateRequest.model_validate(_agent402_tool_payload(payload)))
        return {
            "schema": "x0tta6bl4.agent402_x402_validate_delivery.v1",
            "platform": "agent402",
            "tool": "x402-validate",
            "report": report,
            "claim_boundary": "Generated output only; verify Agent402 settlement and target wallet before claiming funds.",
        }

    @app.post("/agent402/url-snapshot")
    async def agent402_url_snapshot(payload: dict[str, Any]) -> dict[str, Any]:
        report = build_url_snapshot_report(UrlSnapshotRequest.model_validate(_agent402_tool_payload(payload)))
        return {
            "schema": "x0tta6bl4.agent402_url_snapshot_delivery.v1",
            "platform": "agent402",
            "tool": "url-snapshot",
            "report": report,
            "claim_boundary": "Generated output only; verify Agent402 settlement and target wallet before claiming funds.",
        }

    @app.post("/agent402/domain-health")
    async def agent402_domain_health(payload: dict[str, Any]) -> dict[str, Any]:
        report = build_domain_health_report(DomainHealthRequest.model_validate(_agent402_tool_payload(payload)))
        return {
            "schema": "x0tta6bl4.agent402_domain_health_delivery.v1",
            "platform": "agent402",
            "tool": "domain-health",
            "report": report,
            "claim_boundary": "Generated output only; verify Agent402 settlement and target wallet before claiming funds.",
        }

    @app.get("/paid/repo-triage")
    async def repo_triage_info(request: Request) -> dict[str, Any]:
        payment_payload = getattr(request.state, "payment_payload", None)
        if not app.state.x402_available and not settings.allow_unpaid_dev:
            raise HTTPException(status_code=503, detail="paid endpoint unavailable until x402 middleware is active")
        if app.state.x402_available and payment_payload is None:
            raise HTTPException(status_code=402, detail="payment required")
        return {
            "paid": bool(payment_payload) or settings.allow_unpaid_dev,
            "tool": "repo-triage",
            "input": RepoTriageRequest.model_json_schema(),
            "output_schema": "x0tta6bl4.paid_repo_triage_report.v1",
        }

    @app.post("/paid/repo-triage")
    async def repo_triage(payload: RepoTriageRequest, request: Request) -> dict[str, Any]:
        payment_payload = getattr(request.state, "payment_payload", None)
        if not app.state.x402_available and not settings.allow_unpaid_dev:
            raise HTTPException(
                status_code=503,
                detail={
                    "error": "paid endpoint unavailable until x402 middleware is active",
                    "x402_status": app.state.x402_status,
                    "install": "python3 -m pip install 'x402[fastapi,evm,httpx]==2.12.0'",
                },
            )
        if app.state.x402_available and payment_payload is None:
            raise HTTPException(status_code=402, detail="payment required")

        report = build_repo_triage_report(payload)
        return {
            "paid": bool(payment_payload) or settings.allow_unpaid_dev,
            "tool": "repo-triage",
            "report": report,
        }

    @app.get("/paid/api-docs")
    async def api_docs_info(request: Request) -> dict[str, Any]:
        payment_payload = getattr(request.state, "payment_payload", None)
        if not app.state.x402_available and not settings.allow_unpaid_dev:
            raise HTTPException(status_code=503, detail="paid endpoint unavailable until x402 middleware is active")
        if app.state.x402_available and payment_payload is None:
            raise HTTPException(status_code=402, detail="payment required")
        return {
            "paid": bool(payment_payload) or settings.allow_unpaid_dev,
            "tool": "api-docs",
            "input": ApiDocsRequest.model_json_schema(),
            "output_schema": "x0tta6bl4.paid_api_docs_package.v1",
        }

    @app.post("/paid/api-docs")
    async def api_docs(payload: ApiDocsRequest, request: Request) -> dict[str, Any]:
        payment_payload = getattr(request.state, "payment_payload", None)
        if not app.state.x402_available and not settings.allow_unpaid_dev:
            raise HTTPException(
                status_code=503,
                detail={
                    "error": "paid endpoint unavailable until x402 middleware is active",
                    "x402_status": app.state.x402_status,
                    "install": "python3 -m pip install 'x402[fastapi,evm,httpx]==2.12.0'",
                },
            )
        if app.state.x402_available and payment_payload is None:
            raise HTTPException(status_code=402, detail="payment required")

        package = build_api_docs_package(payload)
        return {
            "paid": bool(payment_payload) or settings.allow_unpaid_dev,
            "tool": "api-docs",
            "package": package,
        }

    @app.get("/paid/listing-audit")
    async def listing_audit_info(request: Request) -> dict[str, Any]:
        payment_payload = getattr(request.state, "payment_payload", None)
        if not app.state.x402_available and not settings.allow_unpaid_dev:
            raise HTTPException(status_code=503, detail="paid endpoint unavailable until x402 middleware is active")
        if app.state.x402_available and payment_payload is None:
            raise HTTPException(status_code=402, detail="payment required")
        return {
            "paid": bool(payment_payload) or settings.allow_unpaid_dev,
            "tool": "listing-audit",
            "input": ListingAuditRequest.model_json_schema(),
            "output_schema": "x0tta6bl4.bothire_listing_audit_report.v1",
        }

    @app.post("/paid/listing-audit")
    async def listing_audit(payload: ListingAuditRequest, request: Request) -> dict[str, Any]:
        payment_payload = getattr(request.state, "payment_payload", None)
        if not app.state.x402_available and not settings.allow_unpaid_dev:
            raise HTTPException(
                status_code=503,
                detail={
                    "error": "paid endpoint unavailable until x402 middleware is active",
                    "x402_status": app.state.x402_status,
                    "install": "python3 -m pip install 'x402[fastapi,evm,httpx]==2.12.0'",
                },
            )
        if app.state.x402_available and payment_payload is None:
            raise HTTPException(status_code=402, detail="payment required")

        report = build_listing_audit_report(payload)
        return {
            "paid": bool(payment_payload) or settings.allow_unpaid_dev,
            "tool": "listing-audit",
            "report": report,
        }

    @app.get("/paid/payment-risk")
    async def payment_risk_info(request: Request) -> dict[str, Any]:
        payment_payload = getattr(request.state, "payment_payload", None)
        if not app.state.x402_available and not settings.allow_unpaid_dev:
            raise HTTPException(status_code=503, detail="paid endpoint unavailable until x402 middleware is active")
        if app.state.x402_available and payment_payload is None:
            raise HTTPException(status_code=402, detail="payment required")
        return {
            "paid": bool(payment_payload) or settings.allow_unpaid_dev,
            "tool": "payment-risk",
            "input": PaymentRiskRequest.model_json_schema(),
            "output_schema": "x0tta6bl4.paid_payment_risk_report.v1",
        }

    @app.post("/paid/payment-risk")
    async def payment_risk(payload: PaymentRiskRequest, request: Request) -> dict[str, Any]:
        payment_payload = getattr(request.state, "payment_payload", None)
        if not app.state.x402_available and not settings.allow_unpaid_dev:
            raise HTTPException(
                status_code=503,
                detail={
                    "error": "paid endpoint unavailable until x402 middleware is active",
                    "x402_status": app.state.x402_status,
                    "install": "python3 -m pip install 'x402[fastapi,evm,httpx]==2.12.0'",
                },
            )
        if app.state.x402_available and payment_payload is None:
            raise HTTPException(status_code=402, detail="payment required")

        report = build_payment_risk_report(payload)
        return {
            "paid": bool(payment_payload) or settings.allow_unpaid_dev,
            "tool": "payment-risk",
            "report": report,
        }

    @app.get("/paid/income-route")
    async def income_route_info(request: Request) -> dict[str, Any]:
        payment_payload = getattr(request.state, "payment_payload", None)
        if not app.state.x402_available and not settings.allow_unpaid_dev:
            raise HTTPException(status_code=503, detail="paid endpoint unavailable until x402 middleware is active")
        if app.state.x402_available and payment_payload is None:
            raise HTTPException(status_code=402, detail="payment required")
        return {
            "paid": bool(payment_payload) or settings.allow_unpaid_dev,
            "tool": "income-route",
            "input": IncomeRouteRequest.model_json_schema(),
            "output_schema": "x0tta6bl4.paid_income_route_report.v1",
        }

    @app.post("/paid/income-route")
    async def income_route(payload: IncomeRouteRequest, request: Request) -> dict[str, Any]:
        payment_payload = getattr(request.state, "payment_payload", None)
        if not app.state.x402_available and not settings.allow_unpaid_dev:
            raise HTTPException(
                status_code=503,
                detail={
                    "error": "paid endpoint unavailable until x402 middleware is active",
                    "x402_status": app.state.x402_status,
                    "install": "python3 -m pip install 'x402[fastapi,evm,httpx]==2.12.0'",
                },
            )
        if app.state.x402_available and payment_payload is None:
            raise HTTPException(status_code=402, detail="payment required")

        report = build_income_route_report(payload)
        return {
            "paid": bool(payment_payload) or settings.allow_unpaid_dev,
            "tool": "income-route",
            "report": report,
        }

    @app.get("/paid/x402-validate")
    async def x402_validate_info(request: Request) -> dict[str, Any]:
        payment_payload = getattr(request.state, "payment_payload", None)
        if not app.state.x402_available and not settings.allow_unpaid_dev:
            raise HTTPException(status_code=503, detail="paid endpoint unavailable until x402 middleware is active")
        if app.state.x402_available and payment_payload is None:
            raise HTTPException(status_code=402, detail="payment required")
        return {
            "paid": bool(payment_payload) or settings.allow_unpaid_dev,
            "tool": "x402-validate",
            "input": X402ValidateRequest.model_json_schema(),
            "output_schema": "x0tta6bl4.paid_x402_validate_report.v1",
        }

    @app.post("/paid/x402-validate")
    async def x402_validate(payload: X402ValidateRequest, request: Request) -> dict[str, Any]:
        payment_payload = getattr(request.state, "payment_payload", None)
        if not app.state.x402_available and not settings.allow_unpaid_dev:
            raise HTTPException(
                status_code=503,
                detail={
                    "error": "paid endpoint unavailable until x402 middleware is active",
                    "x402_status": app.state.x402_status,
                    "install": "python3 -m pip install 'x402[fastapi,evm,httpx]==2.12.0'",
                },
            )
        if app.state.x402_available and payment_payload is None:
            raise HTTPException(status_code=402, detail="payment required")

        report = build_x402_validate_report(payload)
        return {
            "paid": bool(payment_payload) or settings.allow_unpaid_dev,
            "tool": "x402-validate",
            "report": report,
        }

    @app.get("/paid/url-snapshot")
    async def url_snapshot_info(request: Request) -> dict[str, Any]:
        payment_payload = getattr(request.state, "payment_payload", None)
        if not app.state.x402_available and not settings.allow_unpaid_dev:
            raise HTTPException(status_code=503, detail="paid endpoint unavailable until x402 middleware is active")
        if app.state.x402_available and payment_payload is None:
            raise HTTPException(status_code=402, detail="payment required")
        return {
            "paid": bool(payment_payload) or settings.allow_unpaid_dev,
            "tool": "url-snapshot",
            "input": UrlSnapshotRequest.model_json_schema(),
            "output_schema": "x0tta6bl4.paid_url_snapshot_report.v1",
        }

    @app.post("/paid/url-snapshot")
    async def url_snapshot(payload: UrlSnapshotRequest, request: Request) -> dict[str, Any]:
        payment_payload = getattr(request.state, "payment_payload", None)
        if not app.state.x402_available and not settings.allow_unpaid_dev:
            raise HTTPException(
                status_code=503,
                detail={
                    "error": "paid endpoint unavailable until x402 middleware is active",
                    "x402_status": app.state.x402_status,
                    "install": "python3 -m pip install 'x402[fastapi,evm,httpx]==2.12.0'",
                },
            )
        if app.state.x402_available and payment_payload is None:
            raise HTTPException(status_code=402, detail="payment required")

        report = build_url_snapshot_report(payload)
        return {
            "paid": bool(payment_payload) or settings.allow_unpaid_dev,
            "tool": "url-snapshot",
            "report": report,
        }

    @app.get("/paid/domain-health")
    async def domain_health_info(request: Request) -> dict[str, Any]:
        payment_payload = getattr(request.state, "payment_payload", None)
        if not app.state.x402_available and not settings.allow_unpaid_dev:
            raise HTTPException(status_code=503, detail="paid endpoint unavailable until x402 middleware is active")
        if app.state.x402_available and payment_payload is None:
            raise HTTPException(status_code=402, detail="payment required")
        return {
            "paid": bool(payment_payload) or settings.allow_unpaid_dev,
            "tool": "domain-health",
            "input": DomainHealthRequest.model_json_schema(),
            "output_schema": "x0tta6bl4.paid_domain_health_report.v1",
        }

    @app.post("/paid/domain-health")
    async def domain_health(payload: DomainHealthRequest, request: Request) -> dict[str, Any]:
        payment_payload = getattr(request.state, "payment_payload", None)
        if not app.state.x402_available and not settings.allow_unpaid_dev:
            raise HTTPException(
                status_code=503,
                detail={
                    "error": "paid endpoint unavailable until x402 middleware is active",
                    "x402_status": app.state.x402_status,
                    "install": "python3 -m pip install 'x402[fastapi,evm,httpx]==2.12.0'",
                },
            )
        if app.state.x402_available and payment_payload is None:
            raise HTTPException(status_code=402, detail="payment required")

        report = build_domain_health_report(payload)
        return {
            "paid": bool(payment_payload) or settings.allow_unpaid_dev,
            "tool": "domain-health",
            "report": report,
        }

    return app


app = create_app()
