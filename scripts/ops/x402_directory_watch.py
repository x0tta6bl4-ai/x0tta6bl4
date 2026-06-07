#!/usr/bin/env python3
"""Watch public x402 directories for the x0tta6bl4 paid API.

The script is read-only. It checks whether the current public endpoint is
reachable and whether major free directories already expose it.
"""

from __future__ import annotations

import argparse
import json
import time
import urllib.error
import urllib.parse
import urllib.request
from dataclasses import asdict, dataclass
from datetime import datetime, timezone
from pathlib import Path
from typing import Any


ROOT = Path(__file__).resolve().parents[2]
ARTIFACT_DIR = ROOT / ".tmp" / "non-bounty"
RUNTIME_STATUS_FILE = ARTIFACT_DIR / "x402_paid_api_public_runtime_status.json"
DEFAULT_STATUS_FILE = ARTIFACT_DIR / "x402_directory_watch_status.json"
DEFAULT_PUBLIC_BASE_URL = "https://saccharolytic-uncatechized-tanika.ngrok-free.dev"
DEFAULT_WALLET = "0x6017613e80d7893EB2aD5c0585b3f1f88CD6e099"
CLAIM_BOUNDARY = (
    "This status proves only public endpoint reachability and directory indexing "
    "probes. It does not prove buyer demand, paid calls, settlement, or received funds."
)


@dataclass(frozen=True)
class JsonProbe:
    url: str
    ok: bool
    http_status: int | None = None
    payload: Any = None
    error: str | None = None
    elapsed_ms: int | None = None


def utc_now() -> str:
    return datetime.now(timezone.utc).replace(microsecond=0).isoformat().replace("+00:00", "Z")


def _read_json(path: Path) -> dict[str, Any]:
    try:
        payload = json.loads(path.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError):
        return {}
    return payload if isinstance(payload, dict) else {}


def _write_json(path: Path, payload: dict[str, Any]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(payload, indent=2, sort_keys=True) + "\n", encoding="utf-8")


def _default_public_base_url() -> str:
    status = _read_json(RUNTIME_STATUS_FILE)
    value = status.get("public_base_url")
    if isinstance(value, str) and value.startswith("https://"):
        return value.rstrip("/")
    return DEFAULT_PUBLIC_BASE_URL


def json_get(url: str, timeout_seconds: float = 15.0) -> JsonProbe:
    start = time.monotonic()
    try:
        request = urllib.request.Request(
            url,
            headers={
                "accept": "application/json",
                "user-agent": "x0tta6bl4-directory-watch/1.0",
            },
        )
        with urllib.request.urlopen(request, timeout=timeout_seconds) as response:
            raw = response.read(3_000_000)
            elapsed_ms = int((time.monotonic() - start) * 1000)
            try:
                payload = json.loads(raw.decode("utf-8"))
            except json.JSONDecodeError as exc:
                return JsonProbe(
                    url=url,
                    ok=False,
                    http_status=response.status,
                    error=f"invalid_json:{exc}",
                    elapsed_ms=elapsed_ms,
                )
            return JsonProbe(
                url=url,
                ok=200 <= response.status < 300,
                http_status=response.status,
                payload=payload,
                elapsed_ms=elapsed_ms,
            )
    except urllib.error.HTTPError as exc:
        elapsed_ms = int((time.monotonic() - start) * 1000)
        return JsonProbe(url=url, ok=False, http_status=exc.code, error=f"http_error:{exc.code}", elapsed_ms=elapsed_ms)
    except Exception as exc:  # pragma: no cover - socket errors differ by OS.
        elapsed_ms = int((time.monotonic() - start) * 1000)
        return JsonProbe(url=url, ok=False, error=f"{type(exc).__name__}:{exc}", elapsed_ms=elapsed_ms)


def probe_summary(probe: JsonProbe, *, include_payload: bool = False) -> dict[str, Any]:
    summary = {
        "url": probe.url,
        "ok": probe.ok,
        "http_status": probe.http_status,
        "error": probe.error,
        "elapsed_ms": probe.elapsed_ms,
    }
    if include_payload:
        summary["payload"] = probe.payload
    return summary


def payload_contains(payload: Any, *needles: str) -> bool:
    text = json.dumps(payload, ensure_ascii=False).lower()
    return all(needle.lower() in text for needle in needles if needle)


def extract_service_count(payload: Any) -> int:
    if not isinstance(payload, dict):
        return 0
    total = payload.get("total_services")
    if isinstance(total, int):
        return total
    services = payload.get("services")
    if isinstance(services, list):
        return len(services)
    return 0


def scan_x402_direct(public_base_url: str, *, max_pages: int, limit: int, timeout_seconds: float) -> dict[str, Any]:
    base = "https://x402.direct/api/services"
    found: list[dict[str, Any]] = []
    first_probe: JsonProbe | None = None
    pages_checked = 0
    total_pages = None
    for page in range(1, max_pages + 1):
        params = urllib.parse.urlencode({"limit": limit, "page": page})
        probe = json_get(f"{base}?{params}", timeout_seconds=timeout_seconds)
        if first_probe is None:
            first_probe = probe
        if not probe.ok or not isinstance(probe.payload, dict):
            return {
                "ok": False,
                "pages_checked": pages_checked,
                "total_pages": total_pages,
                "found": found,
                "first_probe": probe_summary(first_probe or probe),
                "last_probe": probe_summary(probe),
            }
        pages_checked += 1
        pagination = probe.payload.get("pagination") or {}
        if isinstance(pagination, dict) and isinstance(pagination.get("totalPages"), int):
            total_pages = pagination["totalPages"]
        services = probe.payload.get("services")
        if isinstance(services, list):
            for service in services:
                if isinstance(service, dict) and payload_contains(service, public_base_url):
                    found.append(service)
        if total_pages is not None and page >= total_pages:
            break
    return {
        "ok": True,
        "pages_checked": pages_checked,
        "total_pages": total_pages,
        "found": found,
        "first_probe": probe_summary(first_probe) if first_probe else None,
        "last_probe": None,
    }


def summarize_watch(status: dict[str, Any]) -> dict[str, Any]:
    public_ready = bool(status.get("public", {}).get("ready"))
    directory_hits = [
        name
        for name, visible in (status.get("directory_visibility") or {}).items()
        if visible is True
    ]
    wallet_info = status.get("wallet", {})
    wallet_probe = wallet_info.get("probe") if isinstance(wallet_info.get("probe"), dict) else {}
    wallet_probe_ok = bool(wallet_probe.get("ok"))
    wallet_zero = bool(
        wallet_probe_ok
        and wallet_info.get("coin_balance") == "0"
        and wallet_info.get("has_tokens") is False
        and wallet_info.get("has_token_transfers") is False
    )
    if not public_ready:
        next_action = "restore_public_x402_api"
    elif directory_hits:
        next_action = "watch_for_paid_calls_and_orders"
    else:
        next_action = "publish_to_more_directories_or_wait_for_indexing"
    return {
        "public_ready": public_ready,
        "directory_hits_total": len(directory_hits),
        "directory_hits": directory_hits,
        "wallet_probe_ok": wallet_probe_ok,
        "wallet_zero": wallet_zero,
        "money_received": bool(wallet_probe_ok and not wallet_zero),
        "next_action": next_action,
    }


def run(args: argparse.Namespace) -> dict[str, Any]:
    public_base_url = args.public_base_url.rstrip("/")
    discovery_url = f"{public_base_url}/.well-known/x402-discovery"
    agent_card_url = f"{public_base_url}/.well-known/agent-card.json"
    wallet_url = f"https://base.blockscout.com/api/v2/addresses/{args.wallet}"
    arch_search_url = "https://archtools.dev/api/v1/x402/directory/search?q=x0tta6bl4"
    arch_stats_url = "https://archtools.dev/api/v1/x402/directory/stats"
    x402_list_url = "https://x402-list.com/api/v1/services?q=x0tta6bl4"
    directory402_url = "https://402directory.com/api/directory"

    public_discovery = json_get(discovery_url, timeout_seconds=args.timeout_seconds)
    agent_card = json_get(agent_card_url, timeout_seconds=args.timeout_seconds)
    wallet = json_get(wallet_url, timeout_seconds=args.timeout_seconds)
    arch_search = json_get(arch_search_url, timeout_seconds=args.timeout_seconds)
    arch_stats = json_get(arch_stats_url, timeout_seconds=args.timeout_seconds)
    x402_list = json_get(x402_list_url, timeout_seconds=args.timeout_seconds)
    directory402 = json_get(directory402_url, timeout_seconds=args.timeout_seconds)
    x402_direct = scan_x402_direct(
        public_base_url,
        max_pages=args.x402_direct_max_pages,
        limit=args.x402_direct_limit,
        timeout_seconds=args.timeout_seconds,
    )

    gate402_status = _read_json(ARTIFACT_DIR / "gate402_import_status.json")
    agoragentic_status = _read_json(ARTIFACT_DIR / "agoragentic_seller_watch_status.json")
    opentask_status = _read_json(ARTIFACT_DIR / "opentask_agent_status.json")

    wallet_payload = wallet.payload if isinstance(wallet.payload, dict) else {}
    arch_services = (arch_search.payload or {}).get("services") if isinstance(arch_search.payload, dict) else []
    x402_list_data = (x402_list.payload or {}).get("data") if isinstance(x402_list.payload, dict) else []
    directory402_entries = (
        (directory402.payload or {}).get("entries") if isinstance(directory402.payload, dict) else []
    )
    status = {
        "schema": "x0tta6bl4.x402_directory_watch_status.v1",
        "checked_at_utc": utc_now(),
        "claim_boundary": CLAIM_BOUNDARY,
        "public_base_url": public_base_url,
        "wallet": {
            "address": args.wallet,
            "coin_balance": wallet_payload.get("coin_balance"),
            "has_tokens": wallet_payload.get("has_tokens"),
            "has_token_transfers": wallet_payload.get("has_token_transfers"),
            "probe": probe_summary(wallet),
        },
        "public": {
            "ready": public_discovery.ok and agent_card.ok,
            "discovery": {
                **probe_summary(public_discovery),
                "service_count": extract_service_count(public_discovery.payload),
                "wallet_visible": payload_contains(public_discovery.payload, args.wallet),
            },
            "agent_card": {
                **probe_summary(agent_card),
                "wallet_visible": payload_contains(agent_card.payload, args.wallet),
            },
        },
        "directories": {
            "archtools_search": {
                **probe_summary(arch_search, include_payload=True),
                "visible": payload_contains(arch_services, "x0tta6bl4") or payload_contains(arch_services, public_base_url),
            },
            "archtools_stats": probe_summary(arch_stats, include_payload=True),
            "x402_list": {
                **probe_summary(x402_list, include_payload=True),
                "visible": payload_contains(x402_list_data, "x0tta6bl4") or payload_contains(x402_list_data, public_base_url),
            },
            "directory402": {
                **probe_summary(directory402, include_payload=True),
                "visible": payload_contains(directory402_entries, "x0tta6bl4")
                or payload_contains(directory402_entries, public_base_url),
            },
            "x402_direct": {
                "ok": bool(x402_direct.get("ok")),
                "pages_checked": x402_direct.get("pages_checked"),
                "total_pages": x402_direct.get("total_pages"),
                "found_total": len(x402_direct.get("found") or []),
                "visible": bool(x402_direct.get("found")),
            },
            "gate402": {
                "known_registered": bool((gate402_status.get("summary") or {}).get("known_registered")),
                "direct_service_visible": bool((gate402_status.get("summary") or {}).get("direct_service_visible")),
                "discover_visible": bool((gate402_status.get("summary") or {}).get("discover_visible")),
                "service_id": (gate402_status.get("summary") or {}).get("service_id"),
            },
            "agoragentic": {
                "public_visible": bool((agoragentic_status.get("summary") or {}).get("public_visible")),
                "total_invocations": (agoragentic_status.get("summary") or {}).get("total_invocations"),
                "wallet_total_earned_usdc": (agoragentic_status.get("summary") or {}).get("wallet_total_earned_usdc"),
            },
            "opentask": {
                "active_bids": len((((opentask_status.get("active_bids") or {}).get("response") or {}).get("bids") or [])),
                "contracts": (((opentask_status.get("seller_contracts") or {}).get("response") or {}).get("contracts") or []),
            },
        },
    }
    status["directory_visibility"] = {
        "archtools": status["directories"]["archtools_search"]["visible"],
        "x402_list": status["directories"]["x402_list"]["visible"],
        "directory402": status["directories"]["directory402"]["visible"],
        "x402_direct": status["directories"]["x402_direct"]["visible"],
        "gate402_direct": status["directories"]["gate402"]["direct_service_visible"],
        "gate402_search": status["directories"]["gate402"]["discover_visible"],
        "agoragentic": status["directories"]["agoragentic"]["public_visible"],
    }
    status["summary"] = summarize_watch(status)
    _write_json(args.status_file, status)
    return status


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--public-base-url", default=_default_public_base_url())
    parser.add_argument("--wallet", default=DEFAULT_WALLET)
    parser.add_argument("--status-file", type=Path, default=DEFAULT_STATUS_FILE)
    parser.add_argument("--timeout-seconds", type=float, default=15.0)
    parser.add_argument("--x402-direct-limit", type=int, default=100)
    parser.add_argument("--x402-direct-max-pages", type=int, default=60)
    return parser.parse_args()


def main() -> int:
    status = run(parse_args())
    print(json.dumps(status["summary"], indent=2, sort_keys=True))
    return 0 if status["summary"]["public_ready"] else 2


if __name__ == "__main__":
    raise SystemExit(main())
