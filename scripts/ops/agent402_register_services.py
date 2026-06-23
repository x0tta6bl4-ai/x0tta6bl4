#!/usr/bin/env python3
"""Register x0tta6bl4 services on Agent402 through the management API.

The script reads the API key from a local secret file or AGENT402_API_KEY.
It never prints the raw key.
"""

from __future__ import annotations

import argparse
import json
import os
import urllib.error
import urllib.request
from datetime import datetime, timezone
from pathlib import Path
from typing import Any


ARTIFACT_DIR = Path(".tmp/non-bounty")
DEFAULT_IDENTITY = ARTIFACT_DIR / "agent402_identity.secret.json"
DEFAULT_STATUS = ARTIFACT_DIR / "agent402_register_services_status.json"
DEFAULT_API_BASE = "https://marketplace.agent402.app"
PUBLIC_BASE_URL = "https://saccharolytic-uncatechized-tanika.ngrok-free.dev"
TARGET_WALLET = "0x6017613e80d7893EB2aD5c0585b3f1f88CD6e099"


SERVICES: list[dict[str, Any]] = [
    {
        "name": "x0tta6bl4 Repo Triage",
        "slug": "repo-triage",
        "description": (
            "Repository triage from submitted public file snippets. Returns JSON risk "
            "signals, strengths, readiness score, and next engineering steps."
        ),
        "service_endpoint": f"{PUBLIC_BASE_URL}/agent402/repo-triage",
        "price_usd": 0.02,
        "is_primary": True,
        "tags": ["repo-triage", "code-review", "python", "testing"],
    },
    {
        "name": "x0tta6bl4 API Docs Generator",
        "slug": "api-docs",
        "description": "Markdown API docs from submitted REST endpoint specs, with cURL, Python, and JavaScript examples.",
        "service_endpoint": f"{PUBLIC_BASE_URL}/agent402/api-docs",
        "price_usd": 0.03,
        "tags": ["api-docs", "openapi", "documentation", "developer-tools"],
    },
    {
        "name": "x0tta6bl4 Agent Listing Audit",
        "slug": "listing-audit",
        "description": "Marketplace listing score and fixes for price clarity, input scope, delivery mode, trust, and conversion.",
        "service_endpoint": f"{PUBLIC_BASE_URL}/agent402/listing-audit",
        "price_usd": 0.02,
        "tags": ["marketplace", "listing-audit", "conversion", "sales"],
    },
    {
        "name": "x0tta6bl4 Payment Risk Report",
        "slug": "payment-risk",
        "description": "Risk report for public payment metadata used in autonomous wallet approval decisions.",
        "service_endpoint": f"{PUBLIC_BASE_URL}/agent402/payment-risk",
        "price_usd": 0.02,
        "tags": ["payment-risk", "wallet", "base", "security"],
    },
    {
        "name": "x0tta6bl4 Income Route",
        "slug": "income-route",
        "description": "Scores a non-bounty earning opportunity by token cost, upfront cost, automation fit, payment certainty, and safety.",
        "service_endpoint": f"{PUBLIC_BASE_URL}/agent402/income-route",
        "price_usd": 0.02,
        "tags": ["income", "roi", "paid-tasks", "automation"],
    },
    {
        "name": "x0tta6bl4 x402 Endpoint Validator",
        "slug": "x402-validate",
        "description": "Live x402 endpoint validator for HTTP 402, Payment-Required, payTo, network, asset, amount, and mismatch warnings.",
        "service_endpoint": f"{PUBLIC_BASE_URL}/agent402/x402-validate",
        "price_usd": 0.01,
        "tags": ["x402", "validator", "base-usdc", "payment"],
    },
    {
        "name": "x0tta6bl4 Public URL Snapshot",
        "slug": "url-snapshot",
        "description": "Public URL title, metadata, headings, links, and text preview for agents.",
        "service_endpoint": f"{PUBLIC_BASE_URL}/agent402/url-snapshot",
        "price_usd": 0.01,
        "tags": ["url-snapshot", "metadata", "web", "research"],
    },
    {
        "name": "x0tta6bl4 Domain Health Lite",
        "slug": "domain-health",
        "description": "DNS/IP, HTTP status, redirect, TLS expiry, and private-network refusal signals for a public domain or URL.",
        "service_endpoint": f"{PUBLIC_BASE_URL}/agent402/domain-health",
        "price_usd": 0.001,
        "tags": ["domain-health", "dns", "http", "tls"],
    },
]


def utc_now() -> str:
    return datetime.now(timezone.utc).replace(microsecond=0).isoformat().replace("+00:00", "Z")


def read_json(path: Path) -> dict[str, Any]:
    if not path.exists():
        return {}
    payload = json.loads(path.read_text(encoding="utf-8"))
    return payload if isinstance(payload, dict) else {}


def write_json(path: Path, payload: dict[str, Any]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(payload, indent=2, ensure_ascii=False, sort_keys=True) + "\n", encoding="utf-8")


def redact(value: Any) -> Any:
    if isinstance(value, dict):
        return {
            key: ("<redacted>" if key.lower() in {"api_key", "apikey", "access_token", "token", "authorization"} else redact(item))
            for key, item in value.items()
        }
    if isinstance(value, list):
        return [redact(item) for item in value]
    return value


def api_key_from(identity: Path) -> str:
    return os.getenv("AGENT402_API_KEY", "").strip() or str(
        read_json(identity).get("api_key") or read_json(identity).get("apiKey") or ""
    ).strip()


def request_json(
    method: str,
    api_base: str,
    path: str,
    *,
    api_key: str = "",
    payload: dict[str, Any] | None = None,
    timeout_seconds: float = 30.0,
) -> dict[str, Any]:
    data = None if payload is None else json.dumps(payload).encode("utf-8")
    headers = {
        "Accept": "application/json",
        "User-Agent": "x0tta6bl4-agent402-register-services/1.0",
    }
    if data is not None:
        headers["Content-Type"] = "application/json"
    if api_key:
        headers["Authorization"] = f"Bearer {api_key}"
    request = urllib.request.Request(api_base.rstrip("/") + path, data=data, headers=headers, method=method)
    try:
        with urllib.request.urlopen(request, timeout=timeout_seconds) as response:
            body = response.read().decode("utf-8")
            parsed: Any = json.loads(body) if body else {}
            return {"ok": 200 <= response.status < 300, "http_status": response.status, "response": parsed}
    except urllib.error.HTTPError as exc:
        body = exc.read().decode("utf-8", errors="replace")
        try:
            parsed = json.loads(body) if body else {}
        except json.JSONDecodeError:
            parsed = {"raw": body[:2000]}
        return {"ok": False, "http_status": exc.code, "response": parsed}
    except Exception as exc:
        return {"ok": False, "http_status": None, "response": {"error": exc.__class__.__name__, "detail": str(exc)}}


def as_items(payload: Any, *keys: str) -> list[dict[str, Any]]:
    if isinstance(payload, list):
        return [item for item in payload if isinstance(item, dict)]
    if isinstance(payload, dict):
        for key in keys:
            value = payload.get(key)
            if isinstance(value, list):
                return [item for item in value if isinstance(item, dict)]
    return []


def find_by_name_or_slug(items: list[dict[str, Any]], *, name: str, slug: str = "") -> dict[str, Any] | None:
    wanted_name = name.casefold()
    wanted_slug = slug.casefold()
    for item in items:
        item_name = str(item.get("name") or "").casefold()
        item_slug = str(item.get("slug") or "").casefold()
        if item_name == wanted_name or (wanted_slug and item_slug == wanted_slug):
            return item
    return None


def choose_category_id(categories: list[dict[str, Any]]) -> str | None:
    for wanted in ("devtools", "developer-tools", "development", "automation", "data-analysis", "security"):
        for category in categories:
            if str(category.get("slug") or "").casefold() == wanted:
                return str(category.get("id") or "")
    return None


def run(args: argparse.Namespace) -> dict[str, Any]:
    key = api_key_from(args.identity)
    status: dict[str, Any] = {
        "schema": "x0tta6bl4.agent402_register_services_status.v1",
        "checked_at_utc": utc_now(),
        "api_base": args.api_base,
        "identity_file": str(args.identity),
        "api_key_present": bool(key),
        "submit": bool(args.submit),
        "agent_name": args.agent_name,
        "target_wallet": TARGET_WALLET,
        "public_base_url": PUBLIC_BASE_URL,
        "services_expected": len(SERVICES),
        "claim_boundary": (
            "This proves only Agent402 API registration actions. It does not prove "
            "marketplace approval, buyer invocation, settlement, or received funds."
        ),
    }
    categories = request_json("GET", args.api_base, "/api/v1/marketplace/categories")
    network_profiles = request_json("GET", args.api_base, "/api/v1/network-profiles")
    status["public_probes"] = {
        "categories": redact(categories),
        "network_profiles": {
            "ok": network_profiles.get("ok"),
            "http_status": network_profiles.get("http_status"),
        },
    }
    if not key:
        status["next_action"] = (
            "Create an Agent402 API key locally in Settings > API Keys, store it in "
            ".tmp/non-bounty/agent402_identity.secret.json as {\"api_key\":\"...\"}, "
            "then rerun with --submit."
        )
        return status
    if not args.submit:
        status["next_action"] = "API key found. Rerun with --submit to create or update Agent402 agent/services."
        return status

    category_id = choose_category_id(as_items(categories.get("response"), "categories", "items", "data"))
    list_agents = request_json("GET", args.api_base, "/api/v1/agents", api_key=key)
    agents = as_items(list_agents.get("response"), "agents", "items", "data")
    agent = find_by_name_or_slug(agents, name=args.agent_name)
    status["list_agents"] = redact(list_agents)

    if agent:
        status["agent_action"] = "existing"
    else:
        create_payload: dict[str, Any] = {
            "name": args.agent_name,
            "description": args.agent_description,
            "identity_provider_id": "erc8004",
            "identity_network_caip2": "eip155:8453",
            "settlement_network_caip2": "eip155:8453",
            "website": PUBLIC_BASE_URL,
        }
        create_agent = request_json("POST", args.api_base, "/api/v1/agents", api_key=key, payload=create_payload)
        status["create_agent"] = redact(create_agent)
        agent_payload = create_agent.get("response")
        agent = agent_payload if create_agent.get("ok") and isinstance(agent_payload, dict) else None
        status["agent_action"] = "created" if agent else "create_failed"

    agent_id = str((agent or {}).get("id") or "")
    status["agent_id"] = agent_id
    if not agent_id:
        status["next_action"] = "Inspect Agent402 create/list agent API error."
        return status

    list_services = request_json("GET", args.api_base, f"/api/v1/agents/{agent_id}/services", api_key=key)
    existing_services = as_items(list_services.get("response"), "services", "items", "data")
    status["list_services"] = redact(list_services)
    service_actions: list[dict[str, Any]] = []
    for service in SERVICES:
        existing = find_by_name_or_slug(existing_services, name=service["name"], slug=service["slug"])
        payload = dict(service)
        if existing and existing.get("id"):
            update = request_json(
                "PATCH",
                args.api_base,
                f"/api/v1/agents/{agent_id}/services/{existing['id']}",
                api_key=key,
                payload=payload,
            )
            service_actions.append({"name": service["name"], "action": "updated", "result": redact(update)})
        else:
            create = request_json(
                "POST",
                args.api_base,
                f"/api/v1/agents/{agent_id}/services",
                api_key=key,
                payload=payload,
            )
            service_actions.append({"name": service["name"], "action": "created", "result": redact(create)})
    status["service_actions"] = service_actions

    publish_payload: dict[str, Any] = {
        "is_published": True,
        "tagline": "Paid micro-tools for public API, repo, x402, URL, and domain checks.",
        "tags": ["x402", "developer-tools", "api-docs", "repo-triage", "base-usdc"],
    }
    if category_id:
        publish_payload["category_id"] = category_id
    publish = request_json("PATCH", args.api_base, f"/api/v1/agents/{agent_id}", api_key=key, payload=publish_payload)
    status["publish"] = redact(publish)
    status["summary"] = {
        "agent_ok": bool(agent_id),
        "services_ok": sum(1 for item in service_actions if (item.get("result") or {}).get("ok")),
        "services_expected": len(SERVICES),
        "published_ok": bool(publish.get("ok")),
    }
    if status["summary"]["services_ok"] == len(SERVICES) and publish.get("ok"):
        status["next_action"] = "Open Agent402 dashboard and sync/register metadata on-chain if prompted, then verify marketplace search."
    else:
        status["next_action"] = "Inspect failed service or publish action."
    return status


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--api-base", default=DEFAULT_API_BASE)
    parser.add_argument("--identity", type=Path, default=DEFAULT_IDENTITY)
    parser.add_argument("--status-file", type=Path, default=DEFAULT_STATUS)
    parser.add_argument("--submit", action="store_true")
    parser.add_argument("--agent-name", default="x0tta6bl4 paid x402 tools")
    parser.add_argument(
        "--agent-description",
        default=(
            "Public-input paid tools for repository triage, API docs, agent listing audits, "
            "payment-risk checks, income-route scoring, x402 validation, URL snapshots, and domain health checks."
        ),
    )
    return parser.parse_args()


def main() -> int:
    args = parse_args()
    status = run(args)
    write_json(args.status_file, status)
    print(json.dumps(redact(status), indent=2, ensure_ascii=False, sort_keys=True))
    return 0 if status.get("api_key_present") or not args.submit else 2


if __name__ == "__main__":
    raise SystemExit(main())
