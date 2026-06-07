#!/usr/bin/env python3
"""Register x0tta6bl4 agent on AgentPact and publish one earning offer."""

from __future__ import annotations

import argparse
import json
import os
import uuid
import urllib.error
import urllib.request
from datetime import datetime, timezone
from pathlib import Path
from typing import Any


API_BASE = "https://api.agentpact.xyz"
DEFAULT_IDENTITY = Path(".tmp/non-bounty/agentpact_identity.secret.json")
DEFAULT_OFFER = Path(".tmp/non-bounty/agentpact_offer_pack.json")
DEFAULT_STATUS = Path(".tmp/non-bounty/agentpact_status.json")


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


def _write_secret_json(path: Path, payload: dict[str, Any]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(payload, indent=2, sort_keys=True) + "\n", encoding="utf-8")
    os.chmod(path, 0o600)


def _write_public_json(path: Path, payload: dict[str, Any]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(payload, indent=2, sort_keys=True) + "\n", encoding="utf-8")


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
        "User-Agent": "x0tta6bl4-agentpact-offer-cli",
    }
    if api_key:
        headers["x-api-key"] = api_key
    request = urllib.request.Request(
        API_BASE + path,
        data=data,
        headers=headers,
        method=method,
    )
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
        return exc.code, parsed


def _load_or_create_identity(path: Path) -> dict[str, Any]:
    if path.exists():
        identity = _read_json(path)
        try:
            uuid.UUID(str(identity.get("agentId", "")))
            return identity
        except ValueError:
            if identity.get("apiKey"):
                return identity
    identity = {
        "agentId": str(uuid.uuid4()),
        "created_at_utc": _utc_now(),
        "source": "local-generated-agent-id",
    }
    _write_secret_json(path, identity)
    return identity


def _register(identity: dict[str, Any], identity_path: Path) -> dict[str, Any]:
    if identity.get("apiKey"):
        return {"status": "already_registered", "agentId": identity["agentId"]}
    status, response = _http_json("POST", "/api/auth/register", payload={"agentId": identity["agentId"]})
    if status >= 400:
        return {"status": "register_failed", "http_status": status, "response": response}
    api_key = str(response.get("apiKey") or "")
    if not api_key:
        return {"status": "register_failed", "http_status": status, "response": response}
    identity = {**identity, "apiKey": api_key, "registered_at_utc": _utc_now()}
    _write_secret_json(identity_path, identity)
    return {"status": "registered", "agentId": identity["agentId"]}


def _offer_payload(agent_id: str, offer_path: Path) -> dict[str, Any]:
    source = _read_json(offer_path)
    offer = source.get("offer")
    if not isinstance(offer, dict):
        raise ValueError(f"{offer_path} is missing offer object")
    return {
        "agentId": agent_id,
        "title": offer["title"],
        "descriptionMd": offer["descriptionMd"],
        "category": offer["category"],
        "tags": offer["tags"],
        "basePrice": offer["basePrice"],
        "slaDays": offer["slaDays"],
    }


def _post_offer(identity: dict[str, Any], offer_path: Path) -> dict[str, Any]:
    api_key = str(identity.get("apiKey") or "")
    if not api_key:
        return {"status": "offer_skipped", "reason": "missing_api_key"}
    payload = _offer_payload(str(identity["agentId"]), offer_path)
    status, response = _http_json("POST", "/api/offers", payload=payload, api_key=api_key)
    if status >= 400:
        return {"status": "offer_failed", "http_status": status, "response": response, "payload": payload}
    return {"status": "offer_posted", "http_status": status, "response": response, "payload": payload}


def _get_matches(identity: dict[str, Any]) -> dict[str, Any]:
    api_key = str(identity.get("apiKey") or "")
    if not api_key:
        return {"status": "matches_skipped", "reason": "missing_api_key"}
    status, response = _http_json("GET", "/api/matches/recommendations", api_key=api_key)
    if status >= 400:
        return {"status": "matches_failed", "http_status": status, "response": response}
    matches = response if isinstance(response, list) else response.get("matches", [])
    return {"status": "matches_ready", "http_status": status, "matches_total": len(matches), "matches": matches[:10]}


def _public_status(result: dict[str, Any], identity: dict[str, Any]) -> dict[str, Any]:
    return {
        **result,
        "agentId": identity.get("agentId"),
        "apiKey_masked": _mask_secret(str(identity.get("apiKey") or "")) if identity.get("apiKey") else None,
        "apiKey_present": bool(identity.get("apiKey")),
        "funds_received_claim_allowed": False,
        "claim_boundary": (
            "This proves only AgentPact API interaction and local artifacts. It does not prove "
            "accepted deals, approved delivery, payout eligibility, or received funds."
        ),
    }


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--identity", type=Path, default=DEFAULT_IDENTITY)
    parser.add_argument("--offer", type=Path, default=DEFAULT_OFFER)
    parser.add_argument("--write-status", type=Path, default=DEFAULT_STATUS)
    parser.add_argument("--submit", action="store_true", help="Post the offer to AgentPact. Without this, only register and preview.")
    parser.add_argument("--offline", action="store_true", help="Do not call AgentPact; preview local payload only.")
    return parser.parse_args()


def main() -> int:
    args = parse_args()
    identity = _load_or_create_identity(args.identity)
    if args.offline:
        register_result = {"status": "offline_preview", "agentId": identity["agentId"]}
    else:
        register_result = _register(identity, args.identity)
        identity = _read_json(args.identity)
    offer_preview = _offer_payload(str(identity["agentId"]), args.offer)
    offer_result = _post_offer(identity, args.offer) if args.submit and not args.offline else {
        "status": "offer_preview",
        "payload": offer_preview,
    }
    matches_result = _get_matches(identity) if not args.offline else {
        "status": "offline_preview",
        "matches_total": 0,
        "matches": [],
    }
    result = {
        "schema": "x0tta6bl4.agentpact_offer_cli.v1",
        "checked_at_utc": _utc_now(),
        "register": register_result,
        "offer": offer_result,
        "matches": matches_result,
    }
    public = _public_status(result, identity)
    _write_public_json(args.write_status, public)
    print(json.dumps(public, indent=2, sort_keys=True))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
