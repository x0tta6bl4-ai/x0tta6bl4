#!/usr/bin/env python3
"""Poll Agoragentic seller state for the x0tta6bl4 paid listing."""

from __future__ import annotations

import argparse
import json
import time
import urllib.error
import urllib.parse
import urllib.request
from pathlib import Path
from typing import Any


ROOT = Path(__file__).resolve().parents[2]
ARTIFACT_DIR = ROOT / ".tmp" / "non-bounty"
DEFAULT_SECRET = ARTIFACT_DIR / "agoragentic_identity.secret.json"
DEFAULT_OUTPUT = ARTIFACT_DIR / "agoragentic_seller_watch_status.json"
DEFAULT_PUBLIC_BASE = "https://agoragentic.com"
DEFAULT_LISTING_ID = "47d9779a-6e29-4eb5-9f21-2a0ec8e8658e"
CLAIM_BOUNDARY = (
    "This watch report proves only Agoragentic API state, public browse visibility, "
    "webhook registration, and wallet counters. It does not prove buyer demand, "
    "completed invocation, withdrawable funds, on-chain transfer, or received funds."
)


def utc_now() -> str:
    return time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime())


def _read_api_key(path: Path) -> str:
    data = json.loads(path.read_text(encoding="utf-8"))
    api_key = str(data.get("api_key") or "")
    if not api_key.startswith("amk_"):
        raise RuntimeError("Agoragentic API key is missing")
    return api_key


def _fetch_json(url: str, *, api_key: str | None = None, timeout_seconds: float = 20.0) -> dict[str, Any]:
    headers = {"User-Agent": "x0tta6bl4-agoragentic-seller-watcher"}
    if api_key:
        headers["Authorization"] = f"Bearer {api_key}"
    req = urllib.request.Request(url, headers=headers)
    try:
        with urllib.request.urlopen(req, timeout=timeout_seconds) as response:
            body = response.read().decode()
            try:
                payload = json.loads(body)
            except json.JSONDecodeError:
                payload = {"text": body[:4_000]}
            return {"http_status": response.status, "ok": 200 <= response.status < 300, "response": payload}
    except urllib.error.HTTPError as exc:
        body = exc.read().decode(errors="replace")
        try:
            payload = json.loads(body)
        except json.JSONDecodeError:
            payload = {"text": body[:4_000]}
        return {"http_status": exc.code, "ok": False, "response": payload}
    except Exception as exc:  # pragma: no cover - network errors vary by environment.
        return {"ok": False, "error": f"{type(exc).__name__}:{exc}"}


def _find_listing(checks: dict[str, Any], listing_id: str) -> dict[str, Any]:
    health = ((checks.get("/api/seller/health") or {}).get("response") or {})
    listings = health.get("listings") or []
    if not isinstance(listings, list):
        return {}
    for item in listings:
        if isinstance(item, dict) and item.get("id") == listing_id:
            return item
    return listings[0] if listings and isinstance(listings[0], dict) else {}


def build_summary(checks: dict[str, Any], *, listing_id: str) -> dict[str, Any]:
    listing = _find_listing(checks, listing_id)
    agent_me = ((checks.get("/api/agents/me") or {}).get("response") or {})
    wallet = agent_me.get("wallet") if isinstance(agent_me, dict) else {}
    tasks = ((checks.get("/api/agents/me/tasks") or {}).get("response") or {})
    webhooks = ((checks.get("/api/webhooks") or {}).get("response") or {})
    public_search = ((checks.get("public_search") or {}).get("response") or {})
    visibility = listing.get("public_browse_visibility") or {}
    public_search_text = json.dumps(public_search, ensure_ascii=False).lower()
    return {
        "listing_id": listing_id,
        "listing_name": listing.get("name"),
        "status": listing.get("status"),
        "review_status": listing.get("review_status"),
        "verification_status": listing.get("verification_status"),
        "verified_at": listing.get("verified_at"),
        "public_visible": bool(visibility.get("visible")),
        "public_visibility_reason": visibility.get("reason"),
        "price_per_unit_usdc": listing.get("price_per_unit_usdc"),
        "total_invocations": int(listing.get("total_invocations") or 0),
        "success_count": int(listing.get("success_count") or 0),
        "failure_count": int(listing.get("failure_count") or 0),
        "tasks_total": len(tasks.get("tasks") or []) if isinstance(tasks, dict) else 0,
        "webhooks_total": len(webhooks.get("webhooks") or []) if isinstance(webhooks, dict) else 0,
        "wallet_balance_usdc": (wallet or {}).get("balance"),
        "wallet_withdrawable_usdc": (wallet or {}).get("withdrawable"),
        "wallet_total_earned_usdc": (wallet or {}).get("total_earned"),
        "public_search_contains_listing": listing_id.lower() in public_search_text,
        "next_action": (
            "wait_for_buyer_invocation"
            if visibility.get("visible")
            else "queue_or_fix_listing_self_test"
        ),
    }


def collect_status(
    *,
    api_key: str,
    listing_id: str,
    base_url: str,
    request_timeout_seconds: float = 6.0,
) -> dict[str, Any]:
    endpoints = [
        "/api/seller/status",
        "/api/seller/health",
        "/api/seller/demand",
        "/api/agents/me",
        "/api/agents/me/tasks",
        "/api/agents/me/listing-health",
        "/api/webhooks",
        f"/api/capabilities/{listing_id}",
        f"/api/capabilities/{listing_id}/health",
    ]
    checks = {
        endpoint: _fetch_json(
            f"{base_url}{endpoint}",
            api_key=api_key,
            timeout_seconds=request_timeout_seconds,
        )
        for endpoint in endpoints
    }
    query = urllib.parse.quote("x0tta6bl4")
    checks["public_search"] = _fetch_json(
        f"{base_url}/api/capabilities?query={query}",
        timeout_seconds=request_timeout_seconds,
    )
    return {
        "schema": "x0tta6bl4.agoragentic_seller_watch.v1",
        "checked_at_utc": utc_now(),
        "claim_boundary": CLAIM_BOUNDARY,
        "listing_id": listing_id,
        "checks": checks,
        "summary": build_summary(checks, listing_id=listing_id),
    }


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--secret-file", type=Path, default=DEFAULT_SECRET)
    parser.add_argument("--output", type=Path, default=DEFAULT_OUTPUT)
    parser.add_argument("--listing-id", default=DEFAULT_LISTING_ID)
    parser.add_argument("--base-url", default=DEFAULT_PUBLIC_BASE)
    parser.add_argument("--request-timeout-seconds", type=float, default=6.0)
    parser.add_argument("--interval-seconds", type=int, default=0)
    args = parser.parse_args()

    api_key = _read_api_key(args.secret_file)
    while True:
        status = collect_status(
            api_key=api_key,
            listing_id=args.listing_id,
            base_url=args.base_url.rstrip("/"),
            request_timeout_seconds=args.request_timeout_seconds,
        )
        args.output.parent.mkdir(parents=True, exist_ok=True)
        args.output.write_text(json.dumps(status, indent=2, ensure_ascii=False), encoding="utf-8")
        print(json.dumps(status["summary"], ensure_ascii=False, indent=2))
        if args.interval_seconds <= 0:
            return 0 if status["summary"].get("public_visible") else 1
        time.sleep(args.interval_seconds)


if __name__ == "__main__":
    raise SystemExit(main())
