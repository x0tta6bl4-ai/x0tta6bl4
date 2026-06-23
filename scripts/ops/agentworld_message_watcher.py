#!/usr/bin/env python3
"""Watch AgentWorld messages, history, and earnings for x0tta6bl4."""

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


API_BASE = "https://agentworld.me"
DEFAULT_IDENTITY = Path(".tmp/non-bounty/agentworld_identity.secret.json")
DEFAULT_STATE = Path(".tmp/non-bounty/agentworld_message_watcher_state.json")
DEFAULT_STATUS = Path(".tmp/non-bounty/agentworld_message_watcher_status.json")


def _utc_now() -> str:
    return datetime.now(timezone.utc).replace(microsecond=0).isoformat().replace("+00:00", "Z")


def _read_json(path: Path, default: Any) -> Any:
    if not path.exists():
        return default
    try:
        return json.loads(path.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError):
        return default


def _write_json(path: Path, payload: Any) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(payload, indent=2, sort_keys=True) + "\n", encoding="utf-8")


def _http_json(path: str, *, timeout_seconds: float = 30.0) -> tuple[int, Any]:
    request = urllib.request.Request(
        API_BASE + path,
        headers={
            "Accept": "application/json",
            "User-Agent": "x0tta6bl4-agentworld-message-watcher",
        },
        method="GET",
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
            parsed = {"error": body[:1200]}
        return exc.code, parsed


def _messages(payload: Any) -> list[dict[str, Any]]:
    if isinstance(payload, dict) and isinstance(payload.get("messages"), list):
        return [item for item in payload["messages"] if isinstance(item, dict)]
    if isinstance(payload, list):
        return [item for item in payload if isinstance(item, dict)]
    return []


def _message_id(message: dict[str, Any]) -> str:
    for key in ("message_id", "id", "_id"):
        value = message.get(key)
        if isinstance(value, str) and value:
            return value
    return json.dumps(message, sort_keys=True, ensure_ascii=False)[:240]


def _agents(payload: Any) -> list[dict[str, Any]]:
    if isinstance(payload, dict) and isinstance(payload.get("agents"), list):
        return [item for item in payload["agents"] if isinstance(item, dict)]
    if isinstance(payload, list):
        return [item for item in payload if isinstance(item, dict)]
    return []


def _find_agent(registry_payload: Any, agent_id: str) -> dict[str, Any]:
    for agent in _agents(registry_payload):
        if str(agent.get("id") or "") == agent_id:
            return agent
    return {}


def run_once(identity: dict[str, Any], state: dict[str, Any]) -> tuple[dict[str, Any], dict[str, Any]]:
    agent_id = str(identity.get("agent_id") or "")
    if not agent_id:
        raise RuntimeError("AgentWorld identity missing agent_id")

    encoded = urllib.parse.quote(agent_id)
    log_status, log_payload = _http_json(f"/api/agentworld/agents/messages/log?agent_id={encoded}&limit=100")
    history_status, history_payload = _http_json(f"/api/agentworld/agents/{encoded}/history?limit=100")
    registry_status, registry_payload = _http_json("/api/agentworld/registry")
    economy_status, economy_payload = _http_json("/api/agentworld/economy")

    log_messages = _messages(log_payload)
    history_messages = _messages(history_payload)
    seen = set(state.get("seen_message_ids", []))
    current_ids = {_message_id(item) for item in log_messages + history_messages}
    new_ids = sorted(item for item in current_ids if item not in seen)
    seen.update(current_ids)

    agent = _find_agent(registry_payload, agent_id)
    earnings = float(agent.get("earnings_usdc") or 0.0) if agent else 0.0
    call_count = int(agent.get("call_count") or 0) if agent else 0
    previous_earnings = float(state.get("last_earnings_usdc") or 0.0)
    previous_calls = int(state.get("last_call_count") or 0)
    new_state = {
        **state,
        "updated_at_utc": _utc_now(),
        "seen_message_ids": sorted(seen),
        "last_earnings_usdc": earnings,
        "last_call_count": call_count,
    }
    status = {
        "schema": "x0tta6bl4.agentworld_message_watcher.v1",
        "checked_at_utc": _utc_now(),
        "agent_id": agent_id,
        "log_http_status": log_status,
        "history_http_status": history_status,
        "registry_http_status": registry_status,
        "economy_http_status": economy_status,
        "messages_total": len(current_ids),
        "new_messages_total": len(new_ids),
        "new_message_ids": new_ids,
        "registry_agent_found": bool(agent),
        "call_count": call_count,
        "earnings_usdc": earnings,
        "earnings_delta_usdc": round(earnings - previous_earnings, 8),
        "call_count_delta": call_count - previous_calls,
        "economy": {
            "agent_count": economy_payload.get("agent_count") if isinstance(economy_payload, dict) else None,
            "treasury_usdc": economy_payload.get("treasury_usdc") if isinstance(economy_payload, dict) else None,
            "chain_sync_age_seconds": economy_payload.get("chain_sync_age_seconds")
            if isinstance(economy_payload, dict)
            else None,
        },
        "funds_received_claim_allowed": False,
        "claim_boundary": (
            "This proves only AgentWorld log/history/registry polling. It does not prove "
            "on-chain payout to the wallet unless wallet balance also changes."
        ),
    }
    return status, new_state


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--identity", type=Path, default=DEFAULT_IDENTITY)
    parser.add_argument("--state", type=Path, default=DEFAULT_STATE)
    parser.add_argument("--status", type=Path, default=DEFAULT_STATUS)
    parser.add_argument("--once", action="store_true")
    parser.add_argument("--interval-seconds", type=float, default=60.0)
    return parser.parse_args()


def main() -> int:
    args = parse_args()
    identity = _read_json(args.identity, {})
    state = _read_json(args.state, {})
    while True:
        status, state = run_once(identity, state)
        _write_json(args.status, status)
        _write_json(args.state, state)
        print(json.dumps(status, indent=2, sort_keys=True))
        if args.once:
            return 0
        time.sleep(max(10.0, args.interval_seconds))


if __name__ == "__main__":
    raise SystemExit(main())
