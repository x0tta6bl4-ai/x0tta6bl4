#!/usr/bin/env python3
"""Subscribe wallet-linked AgentPact agent to paid need alerts."""

from __future__ import annotations

import argparse
import json
import urllib.error
import urllib.request
from datetime import datetime, timezone
from pathlib import Path
from typing import Any


API_BASE = "https://api.agentpact.xyz"
DEFAULT_IDENTITY = Path(".tmp/non-bounty/agentpact_wallet_identity.secret.json")
DEFAULT_STATUS = Path(".tmp/non-bounty/agentpact_alerts_subscribe_status.json")
DEFAULT_PUBLIC_BASE_URL = "https://saccharolytic-uncatechized-tanika.ngrok-free.dev"


def _utc_now() -> str:
    return datetime.now(timezone.utc).replace(microsecond=0).isoformat().replace("+00:00", "Z")


def _read_json(path: Path) -> dict[str, Any]:
    payload = json.loads(path.read_text(encoding="utf-8"))
    if not isinstance(payload, dict):
        raise ValueError(f"{path} must contain a JSON object")
    return payload


def _write_json(path: Path, payload: dict[str, Any]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(payload, indent=2, ensure_ascii=False, sort_keys=True) + "\n", encoding="utf-8")


def _redact(value: Any) -> Any:
    if isinstance(value, dict):
        redacted: dict[str, Any] = {}
        for key, item in value.items():
            if "key" in key.lower() or "secret" in key.lower() or "token" in key.lower():
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
    payload: dict[str, Any],
    api_key: str,
    timeout_seconds: float = 30.0,
) -> tuple[int, Any]:
    data = json.dumps(payload).encode("utf-8")
    headers = {
        "Accept": "application/json",
        "Content-Type": "application/json",
        "User-Agent": "x0tta6bl4-agentpact-alerts",
    }
    if api_key:
        headers["x-api-key"] = api_key
    request = urllib.request.Request(API_BASE + path, data=data, headers=headers, method=method)
    try:
        with urllib.request.urlopen(request, timeout=timeout_seconds) as response:
            body = response.read().decode("utf-8")
            if not body:
                return response.status, {}
            try:
                return response.status, json.loads(body)
            except json.JSONDecodeError:
                return response.status, {"text": body[:1200]}
    except urllib.error.HTTPError as exc:
        body = exc.read().decode("utf-8", errors="replace")
        try:
            parsed: Any = json.loads(body)
        except json.JSONDecodeError:
            parsed = {"error": body[:1200]}
        return exc.code, parsed


def _alert_payloads(agent_id: str, webhook_url: str) -> list[dict[str, Any]]:
    return [
        {
            "name": "python_data_microtasks",
            "agentId": agent_id,
            "kind": "needs",
            "webhookUrl": webhook_url,
            "filter": {
                "tags": ["python", "data", "automation", "coding", "api", "reports"],
                "minPrice": 1,
                "maxPrice": 50,
                "currency": "USDC",
                "status": "open",
            },
        },
        {
            "name": "api_review_microtasks",
            "agentId": agent_id,
            "kind": "needs",
            "webhookUrl": webhook_url,
            "filter": {
                "tags": ["api", "review", "testing", "markdown", "docs"],
                "minPrice": 1,
                "maxPrice": 25,
                "currency": "USDC",
                "status": "open",
            },
        },
        {
            "name": "x402_agent_income_tasks",
            "agentId": agent_id,
            "kind": "needs",
            "webhookUrl": webhook_url,
            "filter": {
                "tags": ["x402", "agent-income", "paid-tasks", "automation"],
                "minPrice": 1,
                "maxPrice": 100,
                "currency": "USDC",
                "status": "open",
            },
        },
    ]


def _already_done(status_path: Path, webhook_url: str) -> bool:
    if not status_path.exists():
        return False
    try:
        status = _read_json(status_path)
    except (OSError, json.JSONDecodeError, ValueError):
        return False
    if status.get("webhook_url") != webhook_url:
        return False
    results = status.get("subscriptions")
    if not isinstance(results, list) or not results:
        return False
    return all(str(item.get("status")) in {"subscribed", "already_subscribed"} for item in results)


def _previous_success(status_path: Path, webhook_url: str) -> dict[str, Any] | None:
    if not status_path.exists():
        return None
    status = _read_json(status_path)
    if status.get("webhook_url") != webhook_url:
        return None
    if status.get("status") not in {"subscribed", "already_subscribed"} and not _already_done(status_path, webhook_url):
        return None
    return {
        "status": "already_subscribed",
        "agentId": status.get("agentId"),
        "webhook_url": webhook_url,
        "subscriptions": status.get("subscriptions", []),
    }


def subscribe_alerts(
    *,
    identity_path: Path,
    public_base_url: str,
    status_path: Path,
    force: bool = False,
) -> dict[str, Any]:
    identity = _read_json(identity_path)
    agent_id = str(identity.get("agentId") or "")
    api_key = str(identity.get("apiKey") or "")
    webhook_url = f"{public_base_url.rstrip('/')}/agentpact/webhook"
    if not agent_id:
        return {"status": "skipped", "reason": "missing_agent_id", "webhook_url": webhook_url}
    if not api_key:
        return {"status": "skipped", "reason": "missing_api_key", "agentId": agent_id, "webhook_url": webhook_url}
    if not force:
        previous = _previous_success(status_path, webhook_url)
        if previous:
            previous["agentId"] = agent_id
            return previous

    subscriptions: list[dict[str, Any]] = []
    for payload in _alert_payloads(agent_id, webhook_url):
        name = str(payload.pop("name"))
        http_status, response = _http_json(
            "POST",
            "/api/alerts/subscribe",
            payload=payload,
            api_key=api_key,
        )
        result = {
            "name": name,
            "http_status": http_status,
            "payload": payload,
            "response": _redact(response),
        }
        if http_status < 400:
            result["status"] = "subscribed"
        else:
            details = json.dumps(response, ensure_ascii=False).lower()
            if "already" in details or "duplicate" in details:
                result["status"] = "already_subscribed"
            else:
                result["status"] = "failed"
        subscriptions.append(result)

    failed = [item for item in subscriptions if item.get("status") == "failed"]
    return {
        "status": "partial" if failed else "subscribed",
        "agentId": agent_id,
        "webhook_url": webhook_url,
        "subscriptions": subscriptions,
    }


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--identity", type=Path, default=DEFAULT_IDENTITY)
    parser.add_argument("--status", type=Path, default=DEFAULT_STATUS)
    parser.add_argument("--public-base-url", default=DEFAULT_PUBLIC_BASE_URL)
    parser.add_argument("--force", action="store_true")
    return parser.parse_args()


def main() -> int:
    args = parse_args()
    subscription = subscribe_alerts(
        identity_path=args.identity,
        public_base_url=args.public_base_url,
        status_path=args.status,
        force=args.force,
    )
    result = {
        "schema": "x0tta6bl4.agentpact_alert_subscription.v1",
        "checked_at_utc": _utc_now(),
        **subscription,
        "funds_received_claim_allowed": False,
        "claim_boundary": (
            "This proves only AgentPact alert subscription attempts. It does not prove "
            "incoming paid tasks, deal acceptance, escrow release, payout, or received funds."
        ),
    }
    _write_json(args.status, result)
    print(json.dumps(result, indent=2, ensure_ascii=False, sort_keys=True))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
