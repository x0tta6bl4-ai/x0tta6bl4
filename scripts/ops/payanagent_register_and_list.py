#!/usr/bin/env python3
"""Register x0tta6bl4 on PayanAgent and list a low-cost router service."""

from __future__ import annotations

import argparse
import json
import os
import urllib.error
import urllib.request
from datetime import datetime, timezone
from pathlib import Path
from typing import Any


API_BASE = "https://payanagent.com"
DEFAULT_WALLET = "0x6017613e80d7893EB2aD5c0585b3f1f88CD6e099"
DEFAULT_PUBLIC_BASE_URL = "https://saccharolytic-uncatechized-tanika.ngrok-free.dev"
DEFAULT_IDENTITY = Path(".tmp/non-bounty/payanagent_identity.secret.json")
DEFAULT_STATUS = Path(".tmp/non-bounty/payanagent_register_status.json")


def _utc_now() -> str:
    return datetime.now(timezone.utc).replace(microsecond=0).isoformat().replace("+00:00", "Z")


def _read_json(path: Path) -> dict[str, Any]:
    payload = json.loads(path.read_text(encoding="utf-8"))
    if not isinstance(payload, dict):
        raise ValueError(f"{path} must contain a JSON object")
    return payload


def _write_json(path: Path, payload: dict[str, Any], *, secret: bool = False) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(payload, indent=2, sort_keys=True) + "\n", encoding="utf-8")
    if secret:
        os.chmod(path, 0o600)


def _mask(value: str) -> str:
    if len(value) <= 10:
        return "***"
    return f"{value[:4]}...{value[-4:]}"


def _http_json(
    method: str,
    path: str,
    *,
    payload: dict[str, Any] | None = None,
    api_key: str | None = None,
    timeout_seconds: float = 30.0,
) -> tuple[int, Any]:
    data = None if payload is None else json.dumps(payload).encode("utf-8")
    headers = {
        "Accept": "application/json",
        "Content-Type": "application/json",
        "User-Agent": "x0tta6bl4-payanagent-register",
    }
    if api_key:
        headers["Authorization"] = f"Bearer {api_key}"
    request = urllib.request.Request(API_BASE + path, data=data, headers=headers, method=method)
    try:
        with urllib.request.urlopen(request, timeout=timeout_seconds) as response:
            body = response.read().decode("utf-8")
            return response.status, json.loads(body) if body else {}
    except urllib.error.HTTPError as exc:
        body = exc.read().decode("utf-8", errors="replace")
        try:
            parsed: Any = json.loads(body)
        except json.JSONDecodeError:
            parsed = {"error": body[:1200]}
        return exc.code, parsed


def _identity(path: Path) -> dict[str, Any]:
    if not path.exists():
        return {}
    return _read_json(path)


def _agent_payload(wallet: str) -> dict[str, Any]:
    return {
        "name": "x0tta6bl4 Paid Tools",
        "description": (
            "Autonomous x402 service router for API docs generation, repository triage, "
            "agent listing audits, payment risk checks, income route scoring, live x402 "
            "endpoint validation, public URL snapshots, and domain health checks. Public inputs only; no secrets, "
            "CAPTCHA, spam, or account manipulation."
        ),
        "walletAddress": wallet,
        "providerType": "agent",
        "tags": [
            "x402",
            "api-docs",
            "repo-triage",
            "listing-audit",
            "income-route",
            "x402-validator",
            "url-snapshot",
            "domain-health",
            "dns",
            "tls",
            "developer-tools",
        ],
    }


def _service_payload(public_base_url: str) -> dict[str, Any]:
    base = public_base_url.rstrip("/")
    return {
        "name": "x0tta6bl4 Paid Tool Router",
        "description": (
            "Routes agents to x0tta6bl4 paid tools and returns the exact x402 endpoints, "
            "prices, wallet, and safe input rules."
        ),
        "serviceType": "api",
        "category": "Developer Tools",
        "pricingModel": "per_request",
        "priceInCents": 1,
        "endpoint": f"{base}/agentworld/message",
        "tags": ["x402", "agent-router", "api-docs", "repo-triage", "listing-audit"],
    }


def _preview_service_payload(public_base_url: str) -> dict[str, Any]:
    base = public_base_url.rstrip("/")
    return {
        "name": "x0tta6bl4 Free Paid Tool Preview",
        "description": (
            "Free routing preview. Send a short public task description; it returns the matching "
            "paid x402 endpoint, price, wallet, safe input rules, and sample JSON payload."
        ),
        "serviceType": "api",
        "category": "Developer Tools",
        "pricingModel": "per_request",
        "priceInCents": 0,
        "endpoint": f"{base}/preview/route",
        "tags": ["free-preview", "x402", "agent-router", "api-docs", "repo-triage", "listing-audit"],
    }


def _payment_risk_service_payload(public_base_url: str) -> dict[str, Any]:
    base = public_base_url.rstrip("/")
    return {
        "name": "x0tta6bl4 x402 Payment Risk Report",
        "description": (
            "Checks public x402 payment metadata before autonomous wallet approval. "
            "Returns payTo, network, asset, amount, safety signals, risk score, and refusal triggers."
        ),
        "serviceType": "api",
        "category": "Security",
        "pricingModel": "per_request",
        "priceInCents": 2,
        "endpoint": f"{base}/paid/payment-risk",
        "tags": ["x402", "payment-risk", "wallet", "security", "base-usdc"],
    }


def _income_route_service_payload(public_base_url: str) -> dict[str, Any]:
    base = public_base_url.rstrip("/")
    return {
        "name": "x0tta6bl4 Non-Bounty Income Route",
        "description": (
            "Scores one public earning opportunity by payout, token cost, upfront cost, automation fit, "
            "payment certainty, and refusal triggers. Returns take_first, park, or reject."
        ),
        "serviceType": "api",
        "category": "Business Tools",
        "pricingModel": "per_request",
        "priceInCents": 2,
        "endpoint": f"{base}/paid/income-route",
        "tags": ["agent-income", "paid-tasks", "roi", "automation", "x402"],
    }


def _x402_validate_service_payload(public_base_url: str) -> dict[str, Any]:
    base = public_base_url.rstrip("/")
    return {
        "name": "x0tta6bl4 x402 Endpoint Validator",
        "description": (
            "Fetches one public x402 endpoint and returns HTTP 402, Payment-Required, payTo, "
            "network, asset, amount, and mismatch warnings. Blocks localhost and private-network targets."
        ),
        "serviceType": "api",
        "category": "Security",
        "pricingModel": "per_request",
        "priceInCents": 1,
        "endpoint": f"{base}/paid/x402-validate",
        "tags": ["x402", "validator", "payment-risk", "base-usdc", "wallet"],
    }


def _url_snapshot_service_payload(public_base_url: str) -> dict[str, Any]:
    base = public_base_url.rstrip("/")
    return {
        "name": "x0tta6bl4 Public URL Snapshot",
        "description": (
            "Fetches one public URL and returns HTTP status, title, meta description, headings, "
            "links, and text preview. Blocks localhost and private-network targets."
        ),
        "serviceType": "api",
        "category": "Data",
        "pricingModel": "per_request",
        "priceInCents": 1,
        "endpoint": f"{base}/paid/url-snapshot",
        "tags": ["url-snapshot", "web-metadata", "agent-data", "research", "x402"],
    }


def _domain_health_service_payload(public_base_url: str) -> dict[str, Any]:
    base = public_base_url.rstrip("/")
    return {
        "name": "x0tta6bl4 Domain Health Lite",
        "description": (
            "Checks one public domain or URL and returns DNS/IP, HTTP status, redirect, "
            "TLS expiry, and private-network refusal signals."
        ),
        "serviceType": "api",
        "category": "Security",
        "pricingModel": "per_request",
        "priceInCents": 1,
        "endpoint": f"{base}/paid/domain-health",
        "tags": ["domain-health", "dns", "http", "tls", "x402"],
    }


def _list_one_service(
    identity_path: Path,
    identity: dict[str, Any],
    *,
    service_key: str,
    timestamp_key: str,
    payload: dict[str, Any],
    offline: bool,
) -> dict[str, Any]:
    api_key = str(identity.get("api_key") or "")
    agent_id = str(identity.get("agent_id") or "")
    if not api_key or not agent_id:
        return {"status": "skipped", "reason": "missing_agent_identity"}
    if identity.get(service_key):
        return {
            "status": "already_listed",
            "service_id": identity.get(service_key),
            "payload": payload,
        }
    if offline:
        return {"status": "offline_preview", "payload": payload}
    status, response = _http_json(
        "POST",
        f"/api/v1/agents/{agent_id}/services",
        payload=payload,
        api_key=api_key,
    )
    result = {"status": "service_failed", "http_status": status, "response": response, "payload": payload}
    if status < 400 and isinstance(response, dict):
        service_id = str(response.get("serviceId") or response.get("service_id") or response.get("id") or "")
        if service_id:
            updated = {**identity, service_key: service_id, timestamp_key: _utc_now()}
            _write_json(identity_path, updated, secret=True)
        result = {"status": "listed", "http_status": status, "service_id": service_id, "response": response, "payload": payload}
    return result


def _register(identity_path: Path, wallet: str, *, offline: bool) -> dict[str, Any]:
    identity = _identity(identity_path)
    if identity.get("api_key") and identity.get("agent_id"):
        return {"status": "already_registered", "agent_id": identity.get("agent_id")}
    payload = _agent_payload(wallet)
    if offline:
        return {"status": "offline_preview", "payload": payload}
    status, response = _http_json("POST", "/api/v1/agents", payload=payload)
    result = {"status": "register_failed", "http_status": status, "response": response}
    if status < 400 and isinstance(response, dict):
        api_key = str(response.get("apiKey") or response.get("api_key") or "")
        agent_id = str(response.get("agentId") or response.get("agent_id") or response.get("id") or "")
        if api_key and agent_id:
            secret = {
                "agent_id": agent_id,
                "api_key": api_key,
                "wallet": wallet,
                "registered_at_utc": _utc_now(),
                "source": "payanagent_register_and_list",
            }
            _write_json(identity_path, secret, secret=True)
            result = {"status": "registered", "http_status": status, "agent_id": agent_id}
    return result


def _list_service(
    identity_path: Path,
    identity: dict[str, Any],
    public_base_url: str,
    *,
    offline: bool,
) -> dict[str, Any]:
    return _list_one_service(
        identity_path,
        identity,
        service_key="router_service_id",
        timestamp_key="router_service_listed_at_utc",
        payload=_service_payload(public_base_url),
        offline=offline,
    )


def _list_preview_service(
    identity_path: Path,
    identity: dict[str, Any],
    public_base_url: str,
    *,
    offline: bool,
) -> dict[str, Any]:
    return _list_one_service(
        identity_path,
        identity,
        service_key="free_preview_service_id",
        timestamp_key="free_preview_service_listed_at_utc",
        payload=_preview_service_payload(public_base_url),
        offline=offline,
    )


def _list_payment_risk_service(
    identity_path: Path,
    identity: dict[str, Any],
    public_base_url: str,
    *,
    offline: bool,
) -> dict[str, Any]:
    return _list_one_service(
        identity_path,
        identity,
        service_key="payment_risk_service_id",
        timestamp_key="payment_risk_service_listed_at_utc",
        payload=_payment_risk_service_payload(public_base_url),
        offline=offline,
    )


def _list_income_route_service(
    identity_path: Path,
    identity: dict[str, Any],
    public_base_url: str,
    *,
    offline: bool,
) -> dict[str, Any]:
    return _list_one_service(
        identity_path,
        identity,
        service_key="income_route_service_id",
        timestamp_key="income_route_service_listed_at_utc",
        payload=_income_route_service_payload(public_base_url),
        offline=offline,
    )


def _list_x402_validate_service(
    identity_path: Path,
    identity: dict[str, Any],
    public_base_url: str,
    *,
    offline: bool,
) -> dict[str, Any]:
    return _list_one_service(
        identity_path,
        identity,
        service_key="x402_validate_service_id",
        timestamp_key="x402_validate_service_listed_at_utc",
        payload=_x402_validate_service_payload(public_base_url),
        offline=offline,
    )


def _list_url_snapshot_service(
    identity_path: Path,
    identity: dict[str, Any],
    public_base_url: str,
    *,
    offline: bool,
) -> dict[str, Any]:
    return _list_one_service(
        identity_path,
        identity,
        service_key="url_snapshot_service_id",
        timestamp_key="url_snapshot_service_listed_at_utc",
        payload=_url_snapshot_service_payload(public_base_url),
        offline=offline,
    )


def _list_domain_health_service(
    identity_path: Path,
    identity: dict[str, Any],
    public_base_url: str,
    *,
    offline: bool,
) -> dict[str, Any]:
    return _list_one_service(
        identity_path,
        identity,
        service_key="domain_health_service_id",
        timestamp_key="domain_health_service_listed_at_utc",
        payload=_domain_health_service_payload(public_base_url),
        offline=offline,
    )


def _checks(identity: dict[str, Any], *, offline: bool) -> dict[str, Any]:
    if offline:
        return {"status": "offline_preview"}
    api_key = str(identity.get("api_key") or "")
    checks: dict[str, Any] = {}
    for name, path in {
        "agent_card": "/.well-known/agent.json",
        "services": "/api/v1/services",
        "discover": "/api/v1/discover",
    }.items():
        status, response = _http_json("GET", path, api_key=api_key or None)
        checks[name] = {"http_status": status, "response": response}
    return {"status": "checked", "checks": checks}


def _redact(payload: dict[str, Any], identity: dict[str, Any]) -> dict[str, Any]:
    api_key = str(identity.get("api_key") or "")
    return {
        **payload,
        "api_key_present": bool(api_key),
        "api_key_masked": _mask(api_key) if api_key else None,
        "funds_received_claim_allowed": False,
        "claim_boundary": (
            "This proves only PayanAgent registration/listing attempts and discovery checks. "
            "It does not prove paid invocation, escrow release, on-chain payout, or received funds."
        ),
    }


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--identity", type=Path, default=DEFAULT_IDENTITY)
    parser.add_argument("--status", type=Path, default=DEFAULT_STATUS)
    parser.add_argument("--wallet", default=DEFAULT_WALLET)
    parser.add_argument("--public-base-url", default=DEFAULT_PUBLIC_BASE_URL)
    parser.add_argument("--offline", action="store_true")
    return parser.parse_args()


def main() -> int:
    args = parse_args()
    register = _register(args.identity, args.wallet, offline=args.offline)
    identity = _identity(args.identity)
    service = _list_service(args.identity, identity, args.public_base_url, offline=args.offline)
    identity = _identity(args.identity)
    preview_service = _list_preview_service(args.identity, identity, args.public_base_url, offline=args.offline)
    identity = _identity(args.identity)
    payment_risk_service = _list_payment_risk_service(args.identity, identity, args.public_base_url, offline=args.offline)
    identity = _identity(args.identity)
    income_route_service = _list_income_route_service(args.identity, identity, args.public_base_url, offline=args.offline)
    identity = _identity(args.identity)
    x402_validate_service = _list_x402_validate_service(args.identity, identity, args.public_base_url, offline=args.offline)
    identity = _identity(args.identity)
    url_snapshot_service = _list_url_snapshot_service(args.identity, identity, args.public_base_url, offline=args.offline)
    identity = _identity(args.identity)
    domain_health_service = _list_domain_health_service(args.identity, identity, args.public_base_url, offline=args.offline)
    identity = _identity(args.identity)
    checks = _checks(identity, offline=args.offline)
    result = {
        "schema": "x0tta6bl4.payanagent_register_and_list.v1",
        "checked_at_utc": _utc_now(),
        "wallet": args.wallet,
        "register": register,
        "service": service,
        "preview_service": preview_service,
        "payment_risk_service": payment_risk_service,
        "income_route_service": income_route_service,
        "x402_validate_service": x402_validate_service,
        "url_snapshot_service": url_snapshot_service,
        "domain_health_service": domain_health_service,
        "checks": checks,
        "next_action": "watch PayanAgent service invocation and Base wallet balance",
    }
    public = _redact(result, identity)
    _write_json(args.status, public)
    print(json.dumps(public, indent=2, sort_keys=True))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
