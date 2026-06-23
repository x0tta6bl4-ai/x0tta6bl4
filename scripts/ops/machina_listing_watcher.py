#!/usr/bin/env python3
"""Poll Machina listing visibility for the x0tta6bl4 paid x402 service."""

from __future__ import annotations

import argparse
import json
import time
import urllib.parse
import urllib.request
from pathlib import Path
from typing import Any


ROOT = Path(__file__).resolve().parents[2]
ARTIFACT_DIR = ROOT / ".tmp" / "non-bounty"
DEFAULT_REGISTER_STATUS = ARTIFACT_DIR / "machina_register_status.json"
DEFAULT_REGISTER_SERVICES_STATUS = ARTIFACT_DIR / "machina_register_services_status.json"
DEFAULT_OUTPUT = ARTIFACT_DIR / "machina_listing_watch_status.json"
DEFAULT_AGENTS_OUTPUT = ARTIFACT_DIR / "machina_agents_latest.json"
DEFAULT_DISCOVER_OUTPUT = ARTIFACT_DIR / "machina_discover_domain_health_latest.json"
DEFAULT_API_BASE = "https://machina.market"
TARGET_WALLET = "0x6017613e80d7893EB2aD5c0585b3f1f88CD6e099"


def _utc_now() -> str:
    return time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime())


def _read_json(path: Path) -> dict[str, Any]:
    try:
        data = json.loads(path.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError):
        return {}
    return data if isinstance(data, dict) else {}


def _http_json(url: str, *, timeout_seconds: float) -> Any:
    request = urllib.request.Request(
        url,
        headers={"Accept": "application/json", "User-Agent": "x0tta6bl4-machina-watcher"},
    )
    with urllib.request.urlopen(request, timeout=timeout_seconds) as response:
        return json.loads(response.read().decode("utf-8"))


def _find_agent(items: Any, agent_id: str) -> dict[str, Any]:
    if not isinstance(items, list):
        return {}
    for item in items:
        if isinstance(item, dict) and item.get("id") == agent_id:
            return item
    return {}


def _registered_agents(register_status: dict[str, Any], register_services_status: dict[str, Any]) -> list[dict[str, Any]]:
    agents: list[dict[str, Any]] = []
    services = register_services_status.get("services") if isinstance(register_services_status.get("services"), list) else []
    for item in services:
        if not isinstance(item, dict):
            continue
        agent = item.get("agent")
        if isinstance(agent, dict) and agent.get("id"):
            agents.append({"service_id": item.get("service_id"), "agent": agent})
    if agents:
        return agents
    agent = register_status.get("response") if isinstance(register_status.get("response"), dict) else {}
    if agent.get("id"):
        return [{"service_id": "x0tta6bl4-domain-health", "agent": agent}]
    return []


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--api-base", default=DEFAULT_API_BASE)
    parser.add_argument("--register-status", type=Path, default=DEFAULT_REGISTER_STATUS)
    parser.add_argument("--register-services-status", type=Path, default=DEFAULT_REGISTER_SERVICES_STATUS)
    parser.add_argument("--output", type=Path, default=DEFAULT_OUTPUT)
    parser.add_argument("--agents-output", type=Path, default=DEFAULT_AGENTS_OUTPUT)
    parser.add_argument("--discover-output", type=Path, default=DEFAULT_DISCOVER_OUTPUT)
    parser.add_argument("--timeout-seconds", type=float, default=20.0)
    args = parser.parse_args()

    register_status = _read_json(args.register_status)
    register_services_status = _read_json(args.register_services_status)
    tracked_agents = _registered_agents(register_status, register_services_status)
    agent_ids = [str(item["agent"].get("id")) for item in tracked_agents if item.get("agent")]
    base = args.api_base.rstrip("/")
    result: dict[str, Any] = {
        "schema": "x0tta6bl4.machina_listing_watch_status.v1",
        "checked_at_utc": _utc_now(),
        "api_base": base,
        "agent_id": agent_ids[0] if agent_ids else "",
        "agent_ids": agent_ids,
        "agents_expected": len(agent_ids),
        "target_wallet": TARGET_WALLET,
        "claim_boundary": (
            "This proves only Machina listing visibility and reported call counters. "
            "It does not prove settlement or received funds."
        ),
    }
    if not agent_ids:
        result.update({"ok": False, "next_action": "register_machina_listing"})
        args.output.parent.mkdir(parents=True, exist_ok=True)
        args.output.write_text(json.dumps(result, indent=2, sort_keys=True), encoding="utf-8")
        print(json.dumps(result, indent=2, sort_keys=True))
        return 1

    try:
        agents = _http_json(f"{base}/api/v1/agents?limit=200&sort=newest", timeout_seconds=args.timeout_seconds)
        discover = _http_json(
            f"{base}/api/v1/discover?limit=200&sort=newest",
            timeout_seconds=args.timeout_seconds,
        )
    except Exception as exc:
        result.update({"ok": False, "error": f"{type(exc).__name__}: {exc}", "next_action": "retry_machina_watch"})
        args.output.parent.mkdir(parents=True, exist_ok=True)
        args.output.write_text(json.dumps(result, indent=2, sort_keys=True), encoding="utf-8")
        print(json.dumps(result, indent=2, sort_keys=True))
        return 1

    agents_items = agents if isinstance(agents, list) else (agents.get("agents") if isinstance(agents, dict) else [])
    discover_items = discover.get("agents") if isinstance(discover, dict) else []
    watched = []
    for item in tracked_agents:
        service_id = str(item.get("service_id") or "")
        registered_agent = item.get("agent") if isinstance(item.get("agent"), dict) else {}
        agent_id = str(registered_agent.get("id") or "")
        list_agent = _find_agent(agents_items, agent_id)
        discover_agent = _find_agent(discover_items, agent_id)
        current_agent = list_agent or registered_agent
        receive_address = str(current_agent.get("receive_address") or registered_agent.get("receive_address") or "")
        calls_30d = int(current_agent.get("calls_30d") or registered_agent.get("calls_30d") or 0)
        watched.append(
            {
                "service_id": service_id,
                "agent_id": agent_id,
                "name": current_agent.get("name") or registered_agent.get("name"),
                "active": bool(current_agent.get("active", registered_agent.get("active"))),
                "list_visible": bool(list_agent),
                "discover_visible": bool(discover_agent),
                "calls_30d": calls_30d,
                "price_usdc": current_agent.get("price_amount") or registered_agent.get("price_amount"),
                "receive_address": receive_address,
                "receive_address_matches": receive_address.lower() == TARGET_WALLET.lower(),
            }
        )
    calls_total = sum(int(item.get("calls_30d") or 0) for item in watched)
    list_visible_total = sum(1 for item in watched if item.get("list_visible"))
    discover_visible_total = sum(1 for item in watched if item.get("discover_visible"))
    receive_matches_total = sum(1 for item in watched if item.get("receive_address_matches"))
    result.update(
        {
            "ok": list_visible_total == len(watched) and receive_matches_total == len(watched),
            "active": all(bool(item.get("active")) for item in watched),
            "list_visible": list_visible_total == len(watched),
            "discover_visible": discover_visible_total == len(watched),
            "list_visible_total": list_visible_total,
            "discover_visible_total": discover_visible_total,
            "calls_30d": calls_total,
            "price_usdc": watched[0].get("price_usdc") if watched else None,
            "receive_address": watched[0].get("receive_address") if watched else "",
            "receive_address_matches": receive_matches_total == len(watched),
            "agents": watched,
            "money_received_claim_allowed": False,
            "next_action": "wait_for_buyer_x402_call" if calls_total == 0 else "check_base_usdc_settlement",
        }
    )
    args.output.parent.mkdir(parents=True, exist_ok=True)
    agents_payload = agents if isinstance(agents, dict) else {"agents": agents_items}
    args.agents_output.write_text(json.dumps(agents_payload, indent=2, sort_keys=True), encoding="utf-8")
    args.discover_output.write_text(json.dumps(discover, indent=2, sort_keys=True), encoding="utf-8")
    args.output.write_text(json.dumps(result, indent=2, sort_keys=True), encoding="utf-8")
    print(json.dumps(result, indent=2, sort_keys=True))
    return 0 if result["ok"] and result["list_visible"] else 1


if __name__ == "__main__":
    raise SystemExit(main())
