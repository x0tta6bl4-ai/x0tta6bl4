#!/usr/bin/env python3
"""Register AgentPact deal/payment webhooks for the wallet-linked seller agent."""

from __future__ import annotations

import argparse
import json
import os
import urllib.error
import urllib.request
from datetime import datetime, timezone
from pathlib import Path
from typing import Any


API_BASE = "https://api.agentpact.xyz"
DEFAULT_IDENTITY = Path(".tmp/non-bounty/agentpact_wallet_identity.secret.json")
DEFAULT_STATUS = Path(".tmp/non-bounty/agentpact_webhook_register_status.json")
DEFAULT_SECRET = Path(".tmp/non-bounty/agentpact_webhook.secret.json")
DEFAULT_PUBLIC_BASE_URL = "https://saccharolytic-uncatechized-tanika.ngrok-free.dev"
EVENTS = (
    "deal.proposed",
    "deal.accepted",
    "deal.cancelled",
    "deal.fulfillment_provided",
    "deal.buyer_context_provided",
    "deal.fulfillment_verified",
    "deal.fulfillment_revoked",
    "deal.credential_rotated",
    "deal.rotation_requested",
    "deal.fulfillment_expiring",
    "deal.fulfillment_expired",
    "deal.feedback_requested",
    "payment.funded",
    "payment.released",
    "milestone.completed",
    "feedback.received",
    "concierge.message",
    "webhook.test",
)


def _utc_now() -> str:
    return datetime.now(timezone.utc).replace(microsecond=0).isoformat().replace("+00:00", "Z")


def _read_json(path: Path) -> dict[str, Any]:
    payload = json.loads(path.read_text(encoding="utf-8"))
    if not isinstance(payload, dict):
        raise ValueError(f"{path} must contain a JSON object")
    return payload


def _write_json(path: Path, payload: dict[str, Any], *, mode: int | None = None) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(payload, indent=2, ensure_ascii=False, sort_keys=True) + "\n", encoding="utf-8")
    if mode is not None:
        os.chmod(path, mode)


def _redact(value: Any) -> Any:
    if isinstance(value, dict):
        redacted: dict[str, Any] = {}
        for key, item in value.items():
            lowered = key.lower()
            if "secret" in lowered or "key" in lowered or "token" in lowered:
                redacted[key] = "***"
            else:
                redacted[key] = _redact(item)
        return redacted
    if isinstance(value, list):
        return [_redact(item) for item in value]
    return value


def _http_json(
    method: str,
    path: str,
    *,
    api_key: str,
    payload: dict[str, Any] | None = None,
    timeout_seconds: float = 30.0,
) -> tuple[int, Any]:
    data = None if payload is None else json.dumps(payload).encode("utf-8")
    headers = {
        "Accept": "application/json",
        "User-Agent": "x0tta6bl4-agentpact-webhook-register",
    }
    if payload is not None:
        headers["Content-Type"] = "application/json"
    if api_key:
        headers["x-api-key"] = api_key
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


def _matching_webhook(items: Any, *, agent_id: str, webhook_url: str) -> dict[str, Any] | None:
    if not isinstance(items, list):
        return None
    expected = set(EVENTS)
    for item in items:
        if not isinstance(item, dict):
            continue
        if item.get("agent_id") != agent_id and item.get("agentId") != agent_id:
            continue
        if item.get("url") != webhook_url:
            continue
        if item.get("active") is False:
            continue
        events = set(str(event) for event in item.get("events", []) if str(event))
        if expected.issubset(events):
            return item
    return None


def _save_secret(secret_path: Path, response: dict[str, Any]) -> None:
    secret = response.get("secret")
    if not secret:
        return
    _write_json(
        secret_path,
        {
            "saved_at_utc": _utc_now(),
            "webhook_id": response.get("id"),
            "secret": secret,
        },
        mode=0o600,
    )


def register_webhook(
    *,
    identity_path: Path,
    public_base_url: str,
    status_path: Path,
    secret_path: Path,
    force: bool = False,
) -> dict[str, Any]:
    webhook_url = f"{public_base_url.rstrip('/')}/agentpact/webhook"
    identity = _read_json(identity_path)
    agent_id = str(identity.get("agentId") or "")
    api_key = str(identity.get("apiKey") or "")
    if not agent_id:
        return {"status": "skipped", "reason": "missing_agent_id", "webhook_url": webhook_url}
    if not api_key:
        return {"status": "skipped", "reason": "missing_api_key", "agentId": agent_id, "webhook_url": webhook_url}

    list_status, list_response = _http_json("GET", "/api/webhooks", api_key=api_key)
    if list_status < 400 and not force:
        existing = _matching_webhook(list_response, agent_id=agent_id, webhook_url=webhook_url)
        if existing:
            return {
                "status": "already_registered",
                "http_status": list_status,
                "agentId": agent_id,
                "webhook_url": webhook_url,
                "webhook_id": existing.get("id"),
                "events": list(EVENTS),
                "events_total": len(EVENTS),
                "list_response": {
                    "total": len(list_response) if isinstance(list_response, list) else None,
                    "matching": _redact(existing),
                },
            }

    payload = {"agentId": agent_id, "url": webhook_url, "events": list(EVENTS)}
    post_status, post_response = _http_json("POST", "/api/webhooks", api_key=api_key, payload=payload)
    if post_status >= 400:
        return {
            "status": "failed",
            "http_status": post_status,
            "agentId": agent_id,
            "webhook_url": webhook_url,
            "events": list(EVENTS),
            "events_total": len(EVENTS),
            "response": _redact(post_response),
            "list_http_status": list_status,
        }
    if isinstance(post_response, dict):
        _save_secret(secret_path, post_response)
    response = _redact(post_response)
    return {
        "status": "registered",
        "http_status": post_status,
        "agentId": agent_id,
        "webhook_url": webhook_url,
        "webhook_id": response.get("id") if isinstance(response, dict) else None,
        "events": list(EVENTS),
        "events_total": len(EVENTS),
        "response": response,
        "list_http_status": list_status,
    }


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--identity", type=Path, default=DEFAULT_IDENTITY)
    parser.add_argument("--status", type=Path, default=DEFAULT_STATUS)
    parser.add_argument("--secret", type=Path, default=DEFAULT_SECRET)
    parser.add_argument("--public-base-url", default=DEFAULT_PUBLIC_BASE_URL)
    parser.add_argument("--force", action="store_true")
    return parser.parse_args()


def main() -> int:
    args = parse_args()
    registration = register_webhook(
        identity_path=args.identity,
        public_base_url=args.public_base_url,
        status_path=args.status,
        secret_path=args.secret,
        force=args.force,
    )
    result = {
        "schema": "x0tta6bl4.agentpact_webhook_registration.v1",
        "checked_at_utc": _utc_now(),
        **registration,
        "funds_received_claim_allowed": False,
        "claim_boundary": (
            "This proves only AgentPact webhook registration. It does not prove incoming paid "
            "deals, deal acceptance, escrow release, payout, or received funds."
        ),
    }
    _write_json(args.status, result)
    print(json.dumps(result, indent=2, ensure_ascii=False, sort_keys=True))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
