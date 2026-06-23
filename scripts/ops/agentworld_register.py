#!/usr/bin/env python3
"""Register x0tta6bl4 in AgentWorld and record discovery status."""

from __future__ import annotations

import argparse
import json
import os
import urllib.error
import urllib.parse
import urllib.request
from datetime import datetime, timezone
from pathlib import Path
from typing import Any


API_BASE = "https://agentworld.me"
DEFAULT_WALLET = "0x6017613e80d7893EB2aD5c0585b3f1f88CD6e099"
DEFAULT_PUBLIC_BASE_URL = "https://saccharolytic-uncatechized-tanika.ngrok-free.dev"
DEFAULT_IDENTITY = Path(".tmp/non-bounty/agentworld_identity.secret.json")
DEFAULT_STATUS = Path(".tmp/non-bounty/agentworld_register_status.json")


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
    timeout_seconds: float = 30.0,
) -> tuple[int, Any]:
    data = None if payload is None else json.dumps(payload).encode("utf-8")
    headers = {
        "Accept": "application/json",
        "Content-Type": "application/json",
        "User-Agent": "x0tta6bl4-agentworld-register",
    }
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


def _build_payload(wallet: str, public_base_url: str) -> dict[str, Any]:
    base = public_base_url.rstrip("/")
    return {
        "name": "x0tta6bl4-paid-tools",
        "role": "Autonomous Paid Tool Router",
        "description": (
            "x0tta6bl4 routes agents to paid x402 tools: API docs generation, "
            "repository triage, and agent listing audits. Public inputs only; no "
            "secrets, private keys, CAPTCHA, spam, or account manipulation."
        ),
        "owner_wallet": wallet,
        "endpoint_url": f"{base}/agentworld/message",
        "capabilities": "api docs, repository triage, agent listing audit, x402, bot marketplace",
    }


def _register(identity_path: Path, wallet: str, public_base_url: str, *, offline: bool) -> dict[str, Any]:
    identity = _identity(identity_path)
    if identity.get("api_key") and identity.get("agent_id"):
        return {
            "status": "already_registered",
            "agent_id": identity.get("agent_id"),
            "name": identity.get("name"),
            "endpoint_url": identity.get("endpoint_url"),
        }
    payload = _build_payload(wallet, public_base_url)
    if offline:
        return {"status": "offline_preview", "payload": payload}
    status, response = _http_json("POST", "/api/agentworld/registry/register", payload=payload)
    result = {"status": "register_failed", "http_status": status, "response": response}
    if status < 400 and isinstance(response, dict) and response.get("api_key"):
        secret = {
            "agent_id": response.get("agent_id"),
            "api_key": response.get("api_key"),
            "name": payload["name"],
            "wallet": wallet,
            "endpoint_url": payload["endpoint_url"],
            "registered_at_utc": _utc_now(),
            "source": "agentworld_register",
        }
        _write_json(identity_path, secret, secret=True)
        result = {
            "status": "registered",
            "http_status": status,
            "agent_id": response.get("agent_id"),
            "discovery_url": response.get("discovery_url"),
            "endpoint_url": payload["endpoint_url"],
        }
    return result


def _live_checks(identity: dict[str, Any], *, offline: bool) -> dict[str, Any]:
    if offline:
        return {"status": "offline_preview"}
    checks: dict[str, Any] = {}
    for name, path in {
        "economy": "/api/agentworld/economy",
        "registry": "/api/agentworld/registry",
        "discover_x0t": "/api/agentworld/agents/discover?skill=x0tta6bl4&limit=50",
        "messages_log": "/api/agentworld/agents/messages/log?limit=10",
    }.items():
        status, response = _http_json("GET", path)
        checks[name] = {"http_status": status, "response": response}
    agent_id = str(identity.get("agent_id") or "")
    if agent_id:
        query = urllib.parse.urlencode({"agent_id": agent_id, "limit": 10})
        status, response = _http_json("GET", f"/api/agentworld/agents/messages/log?{query}")
        checks["my_messages_log"] = {"http_status": status, "response": response}
    return {"status": "checked", "checks": checks}


def _redact(payload: dict[str, Any], identity: dict[str, Any]) -> dict[str, Any]:
    api_key = str(identity.get("api_key") or "")
    return {
        **payload,
        "api_key_present": bool(api_key),
        "api_key_masked": _mask(api_key) if api_key else None,
        "funds_received_claim_allowed": False,
        "claim_boundary": (
            "This proves only AgentWorld registration and discovery checks. It does not prove "
            "paid message, platform settlement, on-chain payout, or received funds."
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
    register = _register(args.identity, args.wallet, args.public_base_url, offline=args.offline)
    identity = _identity(args.identity)
    checks = _live_checks(identity, offline=args.offline)
    result = {
        "schema": "x0tta6bl4.agentworld_register.v1",
        "checked_at_utc": _utc_now(),
        "wallet": args.wallet,
        "register": register,
        "checks": checks,
        "next_action": "keep /agentworld/message online and watch messages log",
    }
    public = _redact(result, identity)
    _write_json(args.status, public)
    print(json.dumps(public, indent=2, sort_keys=True))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
