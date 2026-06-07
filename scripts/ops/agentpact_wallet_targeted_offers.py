#!/usr/bin/env python3
"""Publish targeted wallet-linked AgentPact offers for current paid needs."""

from __future__ import annotations

import argparse
import json
import time
import urllib.error
import urllib.parse
import urllib.request
from datetime import datetime, timezone
from pathlib import Path
from typing import Any


API_BASE = "https://api.agentpact.xyz"
DEFAULT_IDENTITY = Path(".tmp/non-bounty/agentpact_wallet_identity.secret.json")
DEFAULT_STATUS = Path(".tmp/non-bounty/agentpact_wallet_targeted_offers_status.json")
TARGET_WALLET = "0x6017613e80d7893EB2aD5c0585b3f1f88CD6e099"
CLAIM_BOUNDARY = (
    "This proves only AgentPact offer publication attempts for the wallet-linked profile. "
    "It does not prove buyer acceptance, completed work, released payout, settlement, or received funds."
)

TARGET_OFFERS: list[dict[str, Any]] = [
    {
        "title": "Python data cleaning normalization microtask",
        "descriptionMd": (
            "Send one public CSV, JSON, or small tabular dataset. I return a Python cleaning script, "
            "normalization notes, changed-field summary, and runnable output instructions. Public data only. "
            "No secrets, private accounts, CAPTCHA, KYC bypass, spam, or regulated decisions."
        ),
        "category": "data",
        "tags": ["python", "data-science", "cleaning", "normalization", "csv", "report"],
        "basePrice": 5,
        "slaDays": 1,
    },
    {
        "title": "AI agent framework research brief",
        "descriptionMd": (
            "Send a public agent-framework question. I return a concise comparison table, practical fit notes, "
            "risks, and next-step recommendation based on public documentation. No private prompts, account "
            "work, CAPTCHA bypass, or confidential sources."
        ),
        "category": "research",
        "tags": ["ai", "research", "frameworks", "agents", "comparison", "report"],
        "basePrice": 5,
        "slaDays": 1,
    },
    {
        "title": "Executive data analysis report lite",
        "descriptionMd": (
            "Send public or user-provided non-confidential data. I return a short executive-style analysis "
            "report with assumptions, caveats, and action items. This is analytical writing, not financial, "
            "legal, tax, medical, or investment advice."
        ),
        "category": "data",
        "tags": ["finance", "analysis", "report", "spreadsheet", "summary", "research"],
        "basePrice": 5,
        "slaDays": 1,
    },
]


def _utc_now() -> str:
    return datetime.now(timezone.utc).replace(microsecond=0).isoformat().replace("+00:00", "Z")


def _read_json(path: Path) -> Any:
    return json.loads(path.read_text(encoding="utf-8"))


def _write_json(path: Path, payload: Any) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(payload, indent=2, sort_keys=True) + "\n", encoding="utf-8")


def _http_json(
    method: str,
    path: str,
    *,
    payload: dict[str, Any] | None = None,
    api_key: str | None = None,
    timeout_seconds: float = 30.0,
    attempts: int = 3,
) -> tuple[int, Any]:
    data = None if payload is None else json.dumps(payload).encode("utf-8")
    headers = {
        "Accept": "application/json",
        "Content-Type": "application/json",
        "User-Agent": "x0tta6bl4-agentpact-wallet-targeted-offers",
    }
    if api_key:
        headers["x-api-key"] = api_key
    request = urllib.request.Request(API_BASE + path, data=data, headers=headers, method=method)
    last: tuple[int, Any] = (599, {"error": "not_attempted"})
    for attempt in range(1, attempts + 1):
        try:
            with urllib.request.urlopen(request, timeout=timeout_seconds) as response:
                body = response.read().decode("utf-8")
                return response.status, json.loads(body) if body else {}
        except urllib.error.HTTPError as exc:
            body = exc.read().decode("utf-8", errors="replace")
            try:
                parsed: Any = json.loads(body)
            except json.JSONDecodeError:
                parsed = {"error": body[:1000]}
            last = (exc.code, parsed)
            if exc.code < 500 or attempt == attempts:
                return last
        except (TimeoutError, urllib.error.URLError) as exc:
            last = (599, {"error": exc.__class__.__name__, "detail": str(exc)[:1000]})
            if attempt == attempts:
                return last
        time.sleep(float(attempt))
    return last


def _expect_list(name: str, payload: Any) -> list[dict[str, Any]]:
    if not isinstance(payload, list):
        raise RuntimeError(f"{name} must be a JSON array, got {type(payload).__name__}: {payload}")
    return [item for item in payload if isinstance(item, dict)]


def _normalized(value: Any) -> str:
    return " ".join(str(value or "").strip().lower().split())


def _own_active_offers(offers: list[dict[str, Any]], agent_id: str) -> list[dict[str, Any]]:
    result = []
    for offer in offers:
        owner = str(offer.get("agent_id") or offer.get("agentId") or "")
        status = str(offer.get("status") or "").lower()
        if owner == agent_id and status == "active":
            result.append(offer)
    return result


def _existing_by_title(offers: list[dict[str, Any]], title: str) -> dict[str, Any] | None:
    expected = _normalized(title)
    for offer in offers:
        if _normalized(offer.get("title")) == expected:
            return offer
    return None


def _offer_payload(agent_id: str, offer: dict[str, Any]) -> dict[str, Any]:
    return {
        "agentId": agent_id,
        "title": offer["title"],
        "descriptionMd": offer["descriptionMd"],
        "category": offer["category"],
        "tags": offer["tags"],
        "basePrice": offer["basePrice"],
        "slaDays": offer["slaDays"],
    }


def _safe_response(response: Any) -> Any:
    if isinstance(response, dict):
        return {key: value for key, value in response.items() if "key" not in key.lower() and "secret" not in key.lower()}
    return response


def run(args: argparse.Namespace) -> dict[str, Any]:
    identity = _read_json(args.identity)
    if not isinstance(identity, dict):
        raise ValueError(f"{args.identity} must contain a JSON object")
    agent_id = str(identity.get("agentId") or "")
    api_key = str(identity.get("apiKey") or "")
    if not agent_id or not api_key:
        status = {
            "schema": "x0tta6bl4.agentpact_wallet_targeted_offers.v1",
            "checked_at_utc": _utc_now(),
            "claim_boundary": CLAIM_BOUNDARY,
            "agentId": agent_id or None,
            "wallet": TARGET_WALLET,
            "ok": False,
            "reason": "missing_agent_id_or_api_key",
            "next_action": "restore_agentpact_wallet_identity_secret",
        }
        _write_json(args.status, status)
        return status

    offers_status, offers_payload = _http_json("GET", "/api/offers", api_key=api_key, timeout_seconds=args.timeout_seconds)
    if offers_status >= 400:
        status = {
            "schema": "x0tta6bl4.agentpact_wallet_targeted_offers.v1",
            "checked_at_utc": _utc_now(),
            "claim_boundary": CLAIM_BOUNDARY,
            "agentId": agent_id,
            "wallet": TARGET_WALLET,
            "ok": False,
            "reason": "offers_fetch_failed",
            "http_status": offers_status,
            "response": _safe_response(offers_payload),
            "next_action": "retry_agentpact_targeted_offer_publication",
        }
        _write_json(args.status, status)
        return status
    current_offers = _expect_list("offers", offers_payload)
    active_before = _own_active_offers(current_offers, agent_id)

    results: list[dict[str, Any]] = []
    for offer in TARGET_OFFERS:
        existing = _existing_by_title(active_before, str(offer["title"]))
        if existing:
            results.append(
                {
                    "title": offer["title"],
                    "status": "already_active",
                    "offer_id": existing.get("id"),
                    "basePrice": existing.get("basePrice") or existing.get("base_price") or offer["basePrice"],
                }
            )
            continue
        payload = _offer_payload(agent_id, offer)
        post_status, post_response = _http_json(
            "POST",
            "/api/offers",
            payload=payload,
            api_key=api_key,
            timeout_seconds=args.timeout_seconds,
        )
        if post_status == 409:
            results.append(
                {
                    "title": offer["title"],
                    "status": "duplicate_known",
                    "http_status": post_status,
                    "response": _safe_response(post_response),
                }
            )
        elif post_status >= 400:
            results.append(
                {
                    "title": offer["title"],
                    "status": "post_failed",
                    "http_status": post_status,
                    "response": _safe_response(post_response),
                    "payload": payload,
                }
            )
        else:
            results.append(
                {
                    "title": offer["title"],
                    "status": "posted",
                    "http_status": post_status,
                    "offer_id": post_response.get("id") if isinstance(post_response, dict) else None,
                    "response": _safe_response(post_response),
                }
            )

    after_status, after_payload = _http_json("GET", "/api/offers", api_key=api_key, timeout_seconds=args.timeout_seconds)
    active_after = active_before
    if after_status < 400:
        active_after = _own_active_offers(_expect_list("offers_after", after_payload), agent_id)

    query = urllib.parse.urlencode({"agentId": agent_id})
    matches_status, matches_payload = _http_json(
        "GET",
        f"/api/matches/recommendations?{query}",
        api_key=api_key,
        timeout_seconds=args.timeout_seconds,
    )
    matches = matches_payload if isinstance(matches_payload, list) else []
    posted_total = sum(1 for item in results if item["status"] == "posted")
    known_total = sum(1 for item in results if item["status"] in {"posted", "already_active", "duplicate_known"})
    failed_total = sum(1 for item in results if item["status"] == "post_failed")
    status = {
        "schema": "x0tta6bl4.agentpact_wallet_targeted_offers.v1",
        "checked_at_utc": _utc_now(),
        "claim_boundary": CLAIM_BOUNDARY,
        "agentId": agent_id,
        "wallet": TARGET_WALLET,
        "ok": failed_total == 0,
        "target_offers_total": len(TARGET_OFFERS),
        "posted_total": posted_total,
        "known_total": known_total,
        "failed_total": failed_total,
        "active_offers_before": len(active_before),
        "active_offers_after": len(active_after),
        "matches_http_status": matches_status,
        "matches_total": len(matches),
        "top_matches": matches[:8],
        "results": results,
        "next_action": "wait_for_buyer_accept_or_platform_auto_deal" if failed_total == 0 else "inspect_failed_agentpact_offers",
        "funds_received_claim_allowed": False,
    }
    _write_json(args.status, status)
    return status


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--identity", type=Path, default=DEFAULT_IDENTITY)
    parser.add_argument("--status", type=Path, default=DEFAULT_STATUS)
    parser.add_argument("--timeout-seconds", type=float, default=30.0)
    return parser.parse_args()


def main() -> int:
    status = run(parse_args())
    print(json.dumps(status, indent=2, sort_keys=True))
    return 0 if status.get("ok") else 2


if __name__ == "__main__":
    raise SystemExit(main())
