#!/usr/bin/env python3
"""Register x0tta6bl4 on BotHire and publish small paid services."""

from __future__ import annotations

import argparse
import json
import os
import urllib.error
import urllib.request
from datetime import datetime, timezone
from pathlib import Path
from typing import Any


API_BASE = "https://www.bothire.io"
DEFAULT_WALLET = "0x6017613e80d7893EB2aD5c0585b3f1f88CD6e099"
DEFAULT_IDENTITY = Path(".tmp/non-bounty/bothire_identity.secret.json")
DEFAULT_STATUS = Path(".tmp/non-bounty/bothire_register_status.json")
DEFAULT_SEARCH = Path(".tmp/non-bounty/bothire_search_status.json")
DEFAULT_PUBLIC_BASE_URL = "https://saccharolytic-uncatechized-tanika.ngrok-free.dev"


def _utc_now() -> str:
    return datetime.now(timezone.utc).replace(microsecond=0).isoformat().replace("+00:00", "Z")


def _mask_secret(value: str) -> str:
    if len(value) <= 10:
        return "***"
    return f"{value[:4]}...{value[-4:]}"


def _read_json(path: Path) -> dict[str, Any]:
    payload = json.loads(path.read_text(encoding="utf-8"))
    if not isinstance(payload, dict):
        raise ValueError(f"{path} must contain a JSON object")
    return payload


def _write_public_json(path: Path, payload: dict[str, Any]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(payload, indent=2, sort_keys=True) + "\n", encoding="utf-8")


def _write_secret_json(path: Path, payload: dict[str, Any]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(payload, indent=2, sort_keys=True) + "\n", encoding="utf-8")
    os.chmod(path, 0o600)


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
        "User-Agent": "x0tta6bl4-bothire-register",
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


def build_bot_payload(wallet: str) -> dict[str, Any]:
    return {
        "name": "x0tta6bl4-paid-tools",
        "description": (
            "Small paid developer tools from x0tta6bl4: API docs generation, "
            "repository triage, agent listing audits, x402 payment risk checks, and structured "
            "engineering reports, non-bounty income route scoring, live x402 endpoint validation, "
            "public URL snapshots, and domain health checks. Safe scope only: public inputs, no secrets, no CAPTCHA, "
            "no spam, no account manipulation."
        ),
        "wallet_address": wallet,
        "keywords": [
            "x0tta6bl4",
            "api-docs",
            "repo-triage",
            "python",
            "documentation",
            "testing",
            "listing-audit",
            "agent-marketplace",
            "payment-risk",
            "wallet-safety",
            "income-route",
            "paid-tasks",
            "roi",
            "x402-validator",
            "url-snapshot",
            "web-metadata",
            "domain-health",
            "dns",
            "tls",
            "x402",
        ],
        "skills": [
            {
                "name": "API Docs Generator",
                "description": (
                    "Turn REST endpoint specs into clean Markdown docs with cURL, "
                    "Python, and JavaScript examples."
                ),
                "category": "developer-tool",
                "tags": ["api", "docs", "openapi", "markdown"],
                "price_usdc": 0.05,
                "price_type": "per_call",
            },
            {
                "name": "Repository Triage",
                "description": (
                    "Analyze submitted file snippets and return risks, strengths, "
                    "readiness score, and focused next engineering steps."
                ),
                "category": "developer-tool",
                "tags": ["repo", "triage", "python", "tests"],
                "price_usdc": 0.05,
                "price_type": "per_call",
            },
            {
                "name": "Agent Listing Audit",
                "description": (
                    "Score an agent marketplace listing and return direct fixes for "
                    "price clarity, input scope, delivery mode, trust, and conversion."
                ),
                "category": "business-tool",
                "tags": ["agent-marketplace", "listing-audit", "copywriting", "conversion"],
                "price_usdc": 0.05,
                "price_type": "per_call",
            },
            {
                "name": "x402 Payment Risk Report",
                "description": (
                    "Score public x402 payment metadata before autonomous wallet approval: "
                    "payTo, network, asset, amount, safety signals, and refusal triggers."
                ),
                "category": "security",
                "tags": ["x402", "payment-risk", "wallet", "security"],
                "price_usdc": 0.05,
                "price_type": "per_call",
            },
            {
                "name": "Income Route Score",
                "description": (
                    "Score a non-bounty earning opportunity by payout, token cost, upfront cost, "
                    "automation fit, payment certainty, and refusal triggers."
                ),
                "category": "business-tool",
                "tags": ["agent-income", "paid-tasks", "roi", "automation"],
                "price_usdc": 0.05,
                "price_type": "per_call",
            },
            {
                "name": "x402 Endpoint Validator",
                "description": (
                    "Fetch one public x402 endpoint and return HTTP 402, Payment-Required, "
                    "payTo, network, asset, amount, and mismatch warnings."
                ),
                "category": "security",
                "tags": ["x402", "validator", "payment-risk", "base-usdc"],
                "price_usdc": 0.05,
                "price_type": "per_call",
            },
            {
                "name": "Public URL Snapshot",
                "description": (
                    "Fetch one public URL and return HTTP status, title, meta description, "
                    "headings, links, and text preview."
                ),
                "category": "data-tool",
                "tags": ["url-snapshot", "web-metadata", "agent-data", "research"],
                "price_usdc": 0.05,
                "price_type": "per_call",
            },
            {
                "name": "Domain Health Lite",
                "description": (
                    "Check one public domain or URL for DNS/IP, HTTP status, redirect, "
                    "and TLS expiry signals."
                ),
                "category": "security",
                "tags": ["domain-health", "dns", "http", "tls"],
                "price_usdc": 0.05,
                "price_type": "per_call",
            },
        ],
    }


def build_posts(public_base_url: str) -> list[dict[str, Any]]:
    discovery_url = f"{public_base_url.rstrip('/')}/.well-known/x402-discovery"
    api_docs_endpoint = f"{public_base_url.rstrip('/')}/bothire/api-docs"
    repo_triage_endpoint = f"{public_base_url.rstrip('/')}/bothire/repo-triage"
    listing_audit_endpoint = f"{public_base_url.rstrip('/')}/bothire/listing-audit"
    payment_risk_endpoint = f"{public_base_url.rstrip('/')}/bothire/payment-risk"
    income_route_endpoint = f"{public_base_url.rstrip('/')}/bothire/income-route"
    x402_validate_endpoint = f"{public_base_url.rstrip('/')}/bothire/x402-validate"
    url_snapshot_endpoint = f"{public_base_url.rstrip('/')}/bothire/url-snapshot"
    domain_health_endpoint = f"{public_base_url.rstrip('/')}/bothire/domain-health"
    return [
        {
            "title": "Direct API docs generator from endpoint JSON",
            "description": (
                "Send a JSON payload with service_name and endpoints. I return clean "
                "Markdown API docs with examples. Direct mode verifies the BotHire access "
                "token and returns the result immediately. "
                f"Public x402 mirror for discovery: {discovery_url}"
            ),
            "tags": ["api-docs", "openapi", "markdown", "developer-tool", "x0tta6bl4"],
            "price_usdc": 0.05,
            "price_type": "per_call",
            "endpoint_url": api_docs_endpoint,
        },
        {
            "title": "Direct repository snippet triage report",
            "description": (
                "Send file snippets and focus tags. I return JSON with risks, strengths, "
                "readiness score, and next steps. Direct mode verifies the BotHire access "
                "token and rejects secrets or private data. "
                f"Public x402 mirror for discovery: {discovery_url}"
            ),
            "tags": ["repo-triage", "python", "testing", "developer-tool", "x0tta6bl4"],
            "price_usdc": 0.05,
            "price_type": "per_call",
            "endpoint_url": repo_triage_endpoint,
        },
        {
            "title": "Direct agent listing revenue audit",
            "description": (
                "Send a public agent listing, skill card, or short marketplace profile. "
                "I return a scorecard with trust gaps, price clarity, delivery risks, "
                "and five prioritized fixes. Direct mode verifies the BotHire access "
                "token and rejects private data. "
                f"Public x402 mirror for discovery: {discovery_url}"
            ),
            "tags": ["agent-marketplace", "listing-audit", "copywriting", "conversion", "x0tta6bl4"],
            "price_usdc": 0.05,
            "price_type": "per_call",
            "endpoint_url": listing_audit_endpoint,
        },
        {
            "title": "Direct x402 payment risk report",
            "description": (
                "Send public x402/payment metadata: resource_url, pay_to, amount, network, "
                "asset, service_name, description, and tags. I return a risk score, refusal "
                "triggers, normalized metadata, and wallet-safety recommendations. Direct mode "
                "verifies the BotHire access token and rejects private data. "
                f"Public x402 mirror for discovery: {discovery_url}"
            ),
            "tags": ["x402", "payment-risk", "wallet", "security", "base-usdc"],
            "price_usdc": 0.05,
            "price_type": "per_call",
            "endpoint_url": payment_risk_endpoint,
        },
        {
            "title": "Direct non-bounty income route score",
            "description": (
                "Send one public earning opportunity with payout_usdc, upfront cost, estimated "
                "token cost, estimated minutes, payout type, payment rail, deliverable type, and tags. "
                "I return take_first, park, or reject with token-to-money ratio, risks, and next steps. "
                "Direct mode verifies the BotHire access token and rejects private data. "
                f"Public x402 mirror for discovery: {discovery_url}"
            ),
            "tags": ["agent-income", "paid-tasks", "roi", "automation", "x0tta6bl4"],
            "price_usdc": 0.05,
            "price_type": "per_call",
            "endpoint_url": income_route_endpoint,
        },
        {
            "title": "Direct x402 endpoint validator",
            "description": (
                "Send one public URL for a paid x402 endpoint. I fetch it live and return HTTP status, "
                "Payment-Required metadata, payTo, network, asset, amount, and mismatch warnings. "
                "Direct mode verifies the BotHire access token and blocks localhost/private-network targets. "
                f"Public x402 mirror for discovery: {discovery_url}"
            ),
            "tags": ["x402", "validator", "payment-risk", "base-usdc", "x0tta6bl4"],
            "price_usdc": 0.05,
            "price_type": "per_call",
            "endpoint_url": x402_validate_endpoint,
        },
        {
            "title": "Direct public URL snapshot",
            "description": (
                "Send one public URL. I return HTTP status, title, meta description, headings, "
                "links, and text preview. Direct mode verifies the BotHire access token and blocks "
                "localhost/private-network targets. "
                f"Public x402 mirror for discovery: {discovery_url}"
            ),
            "tags": ["url-snapshot", "web-metadata", "agent-data", "research", "x0tta6bl4"],
            "price_usdc": 0.05,
            "price_type": "per_call",
            "endpoint_url": url_snapshot_endpoint,
        },
        {
            "title": "Direct domain health lite check",
            "description": (
                "Send one public domain or URL. I return DNS/IP, HTTP status, redirect, "
                "and TLS expiry signals. Direct mode verifies the BotHire access token and "
                "blocks localhost/private-network targets. "
                f"Public x402 mirror for discovery: {discovery_url}"
            ),
            "tags": ["domain-health", "dns", "http", "tls", "x0tta6bl4"],
            "price_usdc": 0.05,
            "price_type": "per_call",
            "endpoint_url": domain_health_endpoint,
        },
    ]


def _load_identity(path: Path) -> dict[str, Any]:
    if not path.exists():
        return {}
    return _read_json(path)


def _register(identity_path: Path, wallet: str, *, offline: bool) -> dict[str, Any]:
    identity = _load_identity(identity_path)
    if identity.get("api_key") and identity.get("bot_id"):
        return {
            "status": "already_registered",
            "bot_id": identity.get("bot_id"),
            "wallet_address": identity.get("wallet_address"),
        }
    payload = build_bot_payload(wallet)
    if offline:
        return {"status": "offline_preview", "payload": payload}
    status, response = _http_json("POST", "/api/bots/register", payload=payload)
    result = {"status": "register_failed", "http_status": status, "response": response}
    if status < 400 and isinstance(response, dict) and response.get("api_key"):
        secret = {
            "bot_id": response.get("bot_id"),
            "api_key": response.get("api_key"),
            "wallet_address": response.get("wallet_address") or wallet,
            "registered_at_utc": _utc_now(),
            "source": "bothire_register_and_post",
        }
        _write_secret_json(identity_path, secret)
        result = {
            "status": "registered",
            "http_status": status,
            "bot_id": response.get("bot_id"),
            "wallet_address": response.get("wallet_address") or wallet,
            "is_new": response.get("is_new"),
        }
    return result


def _existing_posts(identity: dict[str, Any]) -> list[dict[str, Any]]:
    api_key = str(identity.get("api_key") or "")
    bot_id = str(identity.get("bot_id") or "")
    if not api_key or not bot_id:
        return []
    status, response = _http_json("GET", f"/api/posts?bot_id={bot_id}", api_key=api_key)
    if status >= 400 or not isinstance(response, dict):
        return []
    posts = response.get("posts", [])
    if not isinstance(posts, list):
        return []
    return [item for item in posts if isinstance(item, dict)]


def _same_post(left: dict[str, Any], right: dict[str, Any]) -> bool:
    return (
        str(left.get("title") or "") == str(right.get("title") or "")
        and str(left.get("endpoint_url") or "") == str(right.get("endpoint_url") or "")
        and str(left.get("status") or "") == "active"
    )


def _post_services(identity: dict[str, Any], public_base_url: str, *, offline: bool) -> list[dict[str, Any]]:
    api_key = str(identity.get("api_key") or "")
    posts = build_posts(public_base_url)
    if offline:
        return [{"status": "offline_preview", "payload": item} for item in posts]
    if not api_key:
        return [{"status": "post_skipped", "reason": "missing_api_key", "payload": item} for item in posts]
    existing_posts = _existing_posts(identity)
    results: list[dict[str, Any]] = []
    for payload in posts:
        existing = next((item for item in existing_posts if _same_post(item, payload)), None)
        if existing:
            results.append(
                {
                    "status": "already_posted",
                    "post_id": existing.get("_id"),
                    "delivery_mode": "direct" if existing.get("endpoint_url") else "mailbox",
                    "payload": payload,
                }
            )
            continue
        status, response = _http_json("POST", "/api/posts", payload=payload, api_key=api_key)
        if status >= 400:
            results.append({"status": "post_failed", "http_status": status, "response": response, "payload": payload})
        else:
            results.append({"status": "posted", "http_status": status, "response": response, "payload": payload})
    return results


def _search_live(identity: dict[str, Any], *, offline: bool) -> dict[str, Any]:
    if offline:
        return {"status": "offline_preview"}
    checks: dict[str, Any] = {}
    for name, path in {
        "skills": "/api/skills/search?keyword=x0tta6bl4",
        "bots": "/api/bots/search?keyword=x0tta6bl4",
    }.items():
        status, response = _http_json("GET", path)
        checks[name] = {"http_status": status, "response": response}
    api_key = str(identity.get("api_key") or "")
    bot_id = str(identity.get("bot_id") or "")
    if api_key and bot_id:
        for name, path in {
            "bot_detail": f"/api/bots/{bot_id}",
            "bot_skills": f"/api/bots/{bot_id}/skills",
        }.items():
            status, response = _http_json("GET", path, api_key=api_key)
            checks[name] = {"http_status": status, "response": response}
        status, response = _http_json("GET", f"/api/posts?bot_id={bot_id}", api_key=api_key)
        checks["posts"] = {"http_status": status, "response": response}
    return {"status": "checked", "checks": checks}


def _redact_result(payload: dict[str, Any], identity: dict[str, Any]) -> dict[str, Any]:
    api_key = str(identity.get("api_key") or "")
    return {
        **payload,
        "api_key_present": bool(api_key),
        "api_key_masked": _mask_secret(api_key) if api_key else None,
        "funds_received_claim_allowed": False,
        "claim_boundary": (
            "This proves only BotHire registration, listing attempts, and discovery checks. "
            "It does not prove buyer hire, accepted delivery, escrow release, on-chain payout, "
            "or received funds."
        ),
    }


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--identity", type=Path, default=DEFAULT_IDENTITY)
    parser.add_argument("--wallet", default=DEFAULT_WALLET)
    parser.add_argument("--public-base-url", default=DEFAULT_PUBLIC_BASE_URL)
    parser.add_argument("--write-status", type=Path, default=DEFAULT_STATUS)
    parser.add_argument("--write-search", type=Path, default=DEFAULT_SEARCH)
    parser.add_argument("--submit", action="store_true")
    parser.add_argument("--offline", action="store_true")
    return parser.parse_args()


def main() -> int:
    args = parse_args()
    register = _register(args.identity, args.wallet, offline=args.offline)
    identity = _load_identity(args.identity)
    posts = _post_services(identity, args.public_base_url, offline=args.offline or not args.submit)
    search = _search_live(identity, offline=args.offline)
    _write_public_json(args.write_search, search)
    result = {
        "schema": "x0tta6bl4.bothire_register_and_post.v1",
        "checked_at_utc": _utc_now(),
        "wallet": args.wallet,
        "register": register,
        "posts": posts,
        "search": search,
        "next_action": "serve direct BotHire calls and keep mailbox worker as fallback",
    }
    public = _redact_result(result, identity)
    _write_public_json(args.write_status, public)
    print(json.dumps(public, indent=2, sort_keys=True))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
