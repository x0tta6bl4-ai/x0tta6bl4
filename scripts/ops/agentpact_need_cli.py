#!/usr/bin/env python3
"""Select AgentPact non-bounty needs and prepare a deal proposal."""

from __future__ import annotations

import argparse
import json
import os
import sys
import urllib.error
import urllib.request
from datetime import datetime, timezone
from decimal import Decimal
from pathlib import Path
from typing import Any


ROOT = Path(__file__).resolve().parents[2]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from src.sales.agentpact_needs import build_selection_packet


API_BASE = "https://api.agentpact.xyz"
DEFAULT_IDENTITY = Path(".tmp/non-bounty/agentpact_identity.secret.json")
DEFAULT_STATUS = Path(".tmp/non-bounty/agentpact_status.json")
DEFAULT_OUTPUT = Path(".tmp/non-bounty/agentpact_need_selection.json")
DEFAULT_SUBMIT_STATUS = Path(".tmp/non-bounty/agentpact_deal_submit_status.json")


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
) -> tuple[int, Any]:
    data = None if payload is None else json.dumps(payload).encode("utf-8")
    headers = {
        "Accept": "application/json",
        "Content-Type": "application/json",
        "User-Agent": "x0tta6bl4-agentpact-need-cli",
    }
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
            parsed = {"error": body[:1000]}
        return exc.code, parsed


def _load_needs(args: argparse.Namespace) -> list[dict[str, Any]]:
    if args.input:
        payload = _read_json(args.input)
    else:
        status, payload = _http_json("GET", "/api/needs")
        if status >= 400:
            raise RuntimeError(f"AgentPact needs fetch failed: {status} {payload}")
    if not isinstance(payload, list):
        raise ValueError("AgentPact needs payload must be a JSON array")
    return [item for item in payload if isinstance(item, dict)]


def _offer_id_from_status(path: Path) -> str | None:
    if not path.exists():
        return None
    status = _read_json(path)
    if not isinstance(status, dict):
        return None
    offer = status.get("offer")
    if isinstance(offer, dict):
        response = offer.get("response")
        if isinstance(response, dict) and response.get("id"):
            return str(response["id"])
    return None


def _load_identity(path: Path) -> dict[str, Any]:
    payload = _read_json(path)
    if not isinstance(payload, dict):
        raise ValueError(f"{path} must contain a JSON object")
    return payload


def _submit_proposal(identity: dict[str, Any], proposal: dict[str, Any]) -> dict[str, Any]:
    api_key = str(identity.get("apiKey") or "")
    if not api_key:
        return {"status": "submit_skipped", "reason": "missing_api_key"}
    status, response = _http_json("POST", "/api/deals/propose", payload=proposal, api_key=api_key)
    if status >= 400:
        response_text = json.dumps(response, ensure_ascii=False).lower()
        if status == 403 and "not authorized to act as this agent" in response_text:
            return {
                "status": "submit_blocked_buyer_agent_authorization_required",
                "http_status": status,
                "response": response,
                "next_action": "wait_for_buyer_proposal_or_buyer_authorized_deal_creation",
            }
        return {"status": "submit_failed", "http_status": status, "response": response}
    return {"status": "submitted", "http_status": status, "response": response}


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--input", type=Path, help="Offline AgentPact needs JSON file. Default: fetch live /api/needs.")
    parser.add_argument("--identity", type=Path, default=DEFAULT_IDENTITY)
    parser.add_argument("--status", type=Path, default=DEFAULT_STATUS)
    parser.add_argument("--output", type=Path, default=DEFAULT_OUTPUT)
    parser.add_argument("--submit-status", type=Path, default=DEFAULT_SUBMIT_STATUS)
    parser.add_argument("--seller-agent-id", help="Seller agent UUID. Default: identity.agentId.")
    parser.add_argument("--offer-id", help="Offer UUID. Default: read from AgentPact status file.")
    parser.add_argument("--offer-base-price", type=Decimal, default=Decimal("5"))
    parser.add_argument(
        "--skills",
        help="Comma-separated seller skills/tags used to rank needs for this specific offer.",
    )
    parser.add_argument("--top", type=int, default=12)
    parser.add_argument("--submit", action="store_true", help="Submit the selected proposal to AgentPact.")
    return parser.parse_args()


def main() -> int:
    args = parse_args()
    identity = _load_identity(args.identity)
    seller_agent_id = args.seller_agent_id or str(identity.get("agentId") or "")
    offer_id = args.offer_id or _offer_id_from_status(args.status)
    if not seller_agent_id:
        raise SystemExit("missing seller agent id")
    if not offer_id:
        raise SystemExit("missing offer id")
    skills = None
    if args.skills:
        skills = {item.strip().lower() for item in args.skills.split(",") if item.strip()}

    needs = _load_needs(args)
    packet = build_selection_packet(
        needs,
        seller_agent_id=seller_agent_id,
        offer_id=offer_id,
        offer_base_price=args.offer_base_price,
        skills=skills,
        top=args.top,
    )
    packet["checked_at_utc"] = _utc_now()
    packet["submit_attempted"] = bool(args.submit)
    _write_json(args.output, packet)

    submit_result = {"status": "submit_not_requested"}
    if args.submit:
        proposal = packet.get("proposal_payload")
        if not isinstance(proposal, dict):
            submit_result = {"status": "submit_skipped", "reason": "no_take_first_need"}
        else:
            submit_result = _submit_proposal(identity, proposal)
        _write_json(
            args.submit_status,
            {
                "checked_at_utc": _utc_now(),
                "selected_need": packet.get("selected_need"),
                "submit": submit_result,
            },
        )
    print(json.dumps({**packet, "submit": submit_result}, indent=2, sort_keys=True))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
