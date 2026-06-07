#!/usr/bin/env python3
"""Watch wallet-linked AgentPact earning state."""

from __future__ import annotations

import argparse
import json
import sys
import time
import urllib.error
import urllib.parse
import urllib.request
from datetime import datetime, timezone
from pathlib import Path
from typing import Any


ROOT = Path(__file__).resolve().parents[2]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from src.sales.agentpact_market_watch import summarize_wallet_market_state


API_BASE = "https://api.agentpact.xyz"
DEFAULT_IDENTITY = Path(".tmp/non-bounty/agentpact_wallet_identity.secret.json")
DEFAULT_OUTPUT = Path(".tmp/non-bounty/agentpact_wallet_watch.json")
DEFAULT_WALLET = "0x6017613e80d7893EB2aD5c0585b3f1f88CD6e099"


def _utc_now() -> str:
    return datetime.now(timezone.utc).replace(microsecond=0).isoformat().replace("+00:00", "Z")


def _read_json(path: Path) -> Any:
    return json.loads(path.read_text(encoding="utf-8"))


def _write_json(path: Path, payload: Any) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(payload, indent=2, sort_keys=True) + "\n", encoding="utf-8")


def _http_json(
    path: str,
    *,
    api_key: str | None = None,
    timeout_seconds: float = 30.0,
    attempts: int = 3,
) -> tuple[int, Any]:
    headers = {
        "Accept": "application/json",
        "User-Agent": "x0tta6bl4-agentpact-wallet-watch",
    }
    if api_key:
        headers["x-api-key"] = api_key
    request = urllib.request.Request(API_BASE + path, headers=headers, method="GET")
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
        time.sleep(float(attempt))
    return last


def _expect_list(name: str, payload: Any) -> list[dict[str, Any]]:
    if not isinstance(payload, list):
        raise RuntimeError(f"{name} must be a JSON array, got {type(payload).__name__}: {payload}")
    return [item for item in payload if isinstance(item, dict)]


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--identity", type=Path, default=DEFAULT_IDENTITY)
    parser.add_argument("--wallet", default=DEFAULT_WALLET)
    parser.add_argument("--output", type=Path, default=DEFAULT_OUTPUT)
    parser.add_argument("--offline-profile", type=Path)
    parser.add_argument("--offline-offers", type=Path)
    parser.add_argument("--offline-matches", type=Path)
    parser.add_argument("--offline-deals", type=Path)
    return parser.parse_args()


def main() -> int:
    args = parse_args()
    identity = _read_json(args.identity)
    if not isinstance(identity, dict):
        raise SystemExit("identity must be a JSON object")
    agent_id = str(identity.get("agentId") or "")
    api_key = str(identity.get("apiKey") or "")
    if not agent_id:
        raise SystemExit("identity missing agentId")

    if args.offline_profile:
        profile = _read_json(args.offline_profile)
        offers = _expect_list("offers", _read_json(args.offline_offers))
        matches = _expect_list("matches", _read_json(args.offline_matches))
        deals = _expect_list("deals", _read_json(args.offline_deals))
    else:
        profile_status, profile = _http_json(f"/api/agents/{agent_id}", api_key=api_key)
        offers_status, offers_payload = _http_json("/api/offers", api_key=api_key)
        query = urllib.parse.urlencode({"agentId": agent_id})
        matches_status, matches_payload = _http_json(f"/api/matches/recommendations?{query}", api_key=api_key)
        deals_status, deals_payload = _http_json("/api/deals", api_key=api_key)
        failures = {
            "profile": (profile_status, profile),
            "offers": (offers_status, offers_payload),
            "matches": (matches_status, matches_payload),
            "deals": (deals_status, deals_payload),
        }
        failed = {name: value for name, value in failures.items() if value[0] >= 400}
        if failed:
            raise RuntimeError(f"AgentPact watch fetch failed: {failed}")
        offers = _expect_list("offers", offers_payload)
        matches = _expect_list("matches", matches_payload)
        deals = _expect_list("deals", deals_payload)

    if not isinstance(profile, dict):
        raise RuntimeError("profile must be a JSON object")
    summary = summarize_wallet_market_state(
        agent_id=agent_id,
        expected_wallet=args.wallet,
        profile=profile,
        offers=offers,
        matches=matches,
        deals=deals,
    )
    summary["checked_at_utc"] = _utc_now()
    _write_json(args.output, summary)
    print(json.dumps(summary, indent=2, sort_keys=True))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
