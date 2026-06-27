#!/usr/bin/env python3
"""Register x0tta6bl4 in AgentStamp free trust registry and send heartbeat."""

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


API_BASE = "https://agentstamp.org"
DEFAULT_WALLET = "0x6017613e80d7893EB2aD5c0585b3f1f88CD6e099"
DEFAULT_IDENTITY = Path(".tmp/non-bounty/agentstamp_identity.secret.json")
DEFAULT_STATUS = Path(".tmp/non-bounty/agentstamp_register_status.json")


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


def _http_json(
    method: str,
    path: str,
    *,
    payload: dict[str, Any] | None = None,
    headers: dict[str, str] | None = None,
    timeout_seconds: float = 30.0,
) -> tuple[int, Any]:
    data = None if payload is None else json.dumps(payload).encode("utf-8")
    request_headers = {
        "Accept": "application/json",
        "Content-Type": "application/json",
        "User-Agent": "x0tta6bl4-agentstamp-register",
        **(headers or {}),
    }
    request = urllib.request.Request(API_BASE + path, data=data, headers=request_headers, method=method)
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


def _identity(path: Path) -> dict[str, Any]:
    if not path.exists():
        return {}
    return _read_json(path)


def _agent_id(response: Any) -> str:
    if not isinstance(response, dict):
        return ""
    for key in ("agent_id", "agentId", "id"):
        value = response.get(key)
        if isinstance(value, str) and value:
            return value
    agent = response.get("agent")
    if isinstance(agent, dict):
        for key in ("id", "agent_id", "agentId"):
            value = agent.get(key)
            if isinstance(value, str) and value:
                return value
    return ""


def _register(identity_path: Path, wallet: str, *, offline: bool) -> dict[str, Any]:
    identity = _identity(identity_path)
    if identity.get("agent_id"):
        return {"status": "already_registered", "agent_id": identity.get("agent_id")}
    payload = {
        "wallet_address": wallet,
        "name": "x0tta6bl4-paid-tools",
        "description": (
            "Autonomous x402 paid tools for API docs, repository triage, and agent listing audits. "
            "Public inputs only."
        ),
        "category": "infrastructure",
        "capabilities": ["api-docs", "repo-triage", "listing-audit"],
    }
    if offline:
        return {"status": "offline_preview", "payload": payload}
    status, response = _http_json("POST", "/api/v1/registry/register/free", payload=payload)
    result = {"status": "register_failed", "http_status": status, "response": response}
    if status < 400:
        agent_id = _agent_id(response)
        if agent_id:
            secret = {
                "agent_id": agent_id,
                "wallet": wallet,
                "registered_at_utc": _utc_now(),
                "source": "agentstamp_register",
            }
            _write_json(identity_path, secret, secret=True)
            result = {"status": "registered", "http_status": status, "agent_id": agent_id, "response": response}
    return result


def _mint_free_stamp(wallet: str, *, offline: bool) -> dict[str, Any]:
    if offline:
        return {"status": "offline_preview"}
    status, response = _http_json(
        "POST",
        "/api/v1/stamp/mint/free",
        payload={"wallet_address": wallet},
    )
    if status < 400:
        return {"status": "minted_or_active", "http_status": status, "response": response}
    return {"status": "mint_failed", "http_status": status, "response": response}


def _heartbeat(identity: dict[str, Any], wallet: str, *, offline: bool) -> dict[str, Any]:
    agent_id = str(identity.get("agent_id") or "")
    if not agent_id:
        return {"status": "skipped", "reason": "missing_agent_id"}
    if offline:
        return {"status": "offline_preview", "agent_id": agent_id}
    status, response = _http_json(
        "POST",
        f"/api/v1/registry/agent/{urllib.parse.quote(agent_id)}/heartbeat",
        headers={"X-Wallet-Address": wallet},
    )
    if status < 400:
        return {"status": "heartbeat_sent", "http_status": status, "response": response}
    return {"status": "heartbeat_failed", "http_status": status, "response": response}


def _checks(identity: dict[str, Any], wallet: str, *, offline: bool) -> dict[str, Any]:
    if offline:
        return {"status": "offline_preview"}
    checks: dict[str, Any] = {}
    for name, path in {
        "search": "/api/v1/registry/search?search=x0tta6bl4&limit=10",
        "browse": "/api/v1/registry/browse?category=infrastructure&sort=newest&limit=10",
        "stamp_stats": "/api/v1/stamp/stats",
        "badge": f"/api/v1/badge/{urllib.parse.quote(wallet)}",
    }.items():
        status, response = _http_json("GET", path)
        checks[name] = {"http_status": status, "response": response}
    agent_id = str(identity.get("agent_id") or "")
    if agent_id:
        status, response = _http_json("GET", f"/api/v1/registry/agent/{urllib.parse.quote(agent_id)}")
        checks["agent"] = {"http_status": status, "response": response}
    return {"status": "checked", "checks": checks}


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--identity", type=Path, default=DEFAULT_IDENTITY)
    parser.add_argument("--status", type=Path, default=DEFAULT_STATUS)
    parser.add_argument("--wallet", default=DEFAULT_WALLET)
    parser.add_argument("--offline", action="store_true")
    return parser.parse_args()


def main() -> int:
    args = parse_args()
    register = _register(args.identity, args.wallet, offline=args.offline)
    identity = _identity(args.identity)
    stamp = _mint_free_stamp(args.wallet, offline=args.offline)
    heartbeat = _heartbeat(identity, args.wallet, offline=args.offline)
    checks = _checks(identity, args.wallet, offline=args.offline)
    result = {
        "schema": "x0tta6bl4.agentstamp_register.v1",
        "checked_at_utc": _utc_now(),
        "wallet": args.wallet,
        "register": register,
        "stamp": stamp,
        "heartbeat": heartbeat,
        "checks": checks,
        "funds_received_claim_allowed": False,
        "claim_boundary": (
            "This proves only free AgentStamp registration/stamp/heartbeat attempts. "
            "It does not prove buyer traffic, paid task, payout, or received funds."
        ),
    }
    _write_json(args.status, result)
    print(json.dumps(result, indent=2, sort_keys=True))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
