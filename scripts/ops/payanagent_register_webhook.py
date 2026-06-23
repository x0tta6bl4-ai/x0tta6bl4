#!/usr/bin/env python3
"""Register a PayanAgent webhook for x0tta6bl4 marketplace events."""

from __future__ import annotations

import argparse
import json
import urllib.error
import urllib.request
from datetime import datetime, timezone
from pathlib import Path
from typing import Any


API_BASE = "https://payanagent.com"
DEFAULT_PUBLIC_BASE_URL = "https://saccharolytic-uncatechized-tanika.ngrok-free.dev"
DEFAULT_IDENTITY = Path(".tmp/non-bounty/payanagent_identity.secret.json")
DEFAULT_STATUS = Path(".tmp/non-bounty/payanagent_webhook_status.json")
DEFAULT_SECRET = Path(".tmp/non-bounty/payanagent_webhook.secret.json")


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
        path.chmod(0o600)


def _redact_secret(value: Any) -> Any:
    if isinstance(value, dict):
        redacted: dict[str, Any] = {}
        for key, item in value.items():
            if key.lower() in {"secret", "webhooksecret", "webhook_secret"}:
                redacted[key] = "***"
            else:
                redacted[key] = _redact_secret(item)
        return redacted
    if isinstance(value, list):
        return [_redact_secret(item) for item in value]
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
        "Content-Type": "application/json",
        "Authorization": f"Bearer {api_key}",
        "User-Agent": "x0tta6bl4-payanagent-webhook",
    }
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


def _payload_candidates(webhook_url: str) -> list[dict[str, Any]]:
    events = [
        "job.received",
        "bid.received",
        "bid.accepted",
        "job.delivered",
        "job.completed",
        "job.cancelled",
        "job.disputed",
        "job.timed_out",
    ]
    return [
        {"url": webhook_url, "events": events},
        {"webhookUrl": webhook_url, "events": events},
        {"endpoint": webhook_url, "events": events},
        {"url": webhook_url, "eventTypes": events},
        {"callbackUrl": webhook_url},
    ]


def register_webhook(identity_path: Path, secret_path: Path, public_base_url: str) -> dict[str, Any]:
    identity = _read_json(identity_path)
    api_key = str(identity.get("api_key") or "")
    if not api_key:
        return {"status": "skipped", "reason": "missing_api_key"}
    webhook_url = f"{public_base_url.rstrip('/')}/payanagent/webhook"
    attempts: list[dict[str, Any]] = []
    for payload in _payload_candidates(webhook_url):
        status, response = _http_json("POST", "/api/v1/webhooks", api_key=api_key, payload=payload)
        attempt = {"http_status": status, "payload": payload, "response": response}
        attempts.append(attempt)
        if status < 400:
            if isinstance(response, dict) and response.get("secret"):
                _write_json(
                    secret_path,
                    {
                        "schema": "x0tta6bl4.payanagent_webhook_secret.v1",
                        "webhook_id": response.get("webhookId") or response.get("webhook_id"),
                        "secret": response.get("secret"),
                        "webhook_url": webhook_url,
                        "stored_at_utc": _utc_now(),
                    },
                    secret=True,
                )
            return {
                "status": "registered",
                "webhook_url": webhook_url,
                "winning_payload": payload,
                "http_status": status,
                "response": _redact_secret(response),
                "attempts": _redact_secret(attempts),
            }
        details = json.dumps(response, ensure_ascii=False).lower()
        if "already" in details or "duplicate" in details:
            return {
                "status": "already_registered",
                "webhook_url": webhook_url,
                "winning_payload": payload,
                "http_status": status,
                "response": _redact_secret(response),
                "attempts": _redact_secret(attempts),
            }
    return {"status": "register_failed", "webhook_url": webhook_url, "attempts": _redact_secret(attempts)}


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--identity", type=Path, default=DEFAULT_IDENTITY)
    parser.add_argument("--status", type=Path, default=DEFAULT_STATUS)
    parser.add_argument("--secret", type=Path, default=DEFAULT_SECRET)
    parser.add_argument("--public-base-url", default=DEFAULT_PUBLIC_BASE_URL)
    return parser.parse_args()


def main() -> int:
    args = parse_args()
    result = {
        "schema": "x0tta6bl4.payanagent_webhook_registration.v1",
        "checked_at_utc": _utc_now(),
        "registration": register_webhook(args.identity, args.secret, args.public_base_url),
        "funds_received_claim_allowed": False,
        "claim_boundary": (
            "This proves only webhook registration attempts. It does not prove event delivery, "
            "payment, escrow release, or received funds."
        ),
    }
    _write_json(args.status, result)
    print(json.dumps(result, indent=2, sort_keys=True))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
