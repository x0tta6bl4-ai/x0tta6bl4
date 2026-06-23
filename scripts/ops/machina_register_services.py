#!/usr/bin/env python3
"""Register x0tta6bl4 paid x402 services in Machina without private keys."""

from __future__ import annotations

import argparse
import json
import time
import urllib.error
import urllib.parse
import urllib.request
from pathlib import Path
from typing import Any


ROOT = Path(__file__).resolve().parents[2]
ARTIFACT_DIR = ROOT / ".tmp" / "non-bounty"
DEFAULT_STATUS_FILE = ARTIFACT_DIR / "machina_register_services_status.json"
DEFAULT_PUBLIC_BASE_URL = "https://saccharolytic-uncatechized-tanika.ngrok-free.dev"
DEFAULT_API_BASE = "https://machina.market"
TARGET_WALLET = "0x6017613e80d7893EB2aD5c0585b3f1f88CD6e099"
SERVICE_IDS = [
    "x0tta6bl4-repo-triage",
    "x0tta6bl4-api-docs",
    "x0tta6bl4-listing-audit",
    "x0tta6bl4-payment-risk",
    "x0tta6bl4-income-route",
    "x0tta6bl4-x402-validator",
    "x0tta6bl4-url-snapshot",
    "x0tta6bl4-domain-health",
]


def _utc_now() -> str:
    return time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime())


def _http_json(
    url: str,
    *,
    method: str = "GET",
    payload: dict[str, Any] | None = None,
    timeout_seconds: float = 25.0,
) -> tuple[int, Any]:
    data = None if payload is None else json.dumps(payload).encode("utf-8")
    request = urllib.request.Request(
        url,
        data=data,
        method=method,
        headers={
            "Accept": "application/json",
            "Content-Type": "application/json",
            "User-Agent": "x0tta6bl4-machina-register-services",
        },
    )
    with urllib.request.urlopen(request, timeout=timeout_seconds) as response:
        text = response.read().decode("utf-8", errors="replace")
        return response.status, json.loads(text) if text else {}


def _manifest_url(public_base_url: str, service_id: str) -> str:
    base = public_base_url.rstrip("/")
    return f"{base}/.well-known/machina/{urllib.parse.quote(service_id)}.json"


def _load_manifest(manifest_url: str, timeout_seconds: float) -> dict[str, Any]:
    _, payload = _http_json(manifest_url, timeout_seconds=timeout_seconds)
    return payload if isinstance(payload, dict) else {}


def _existing_agents(api_base: str, timeout_seconds: float) -> list[dict[str, Any]]:
    status, payload = _http_json(
        f"{api_base.rstrip()}/api/v1/agents?limit=200&sort=newest",
        timeout_seconds=timeout_seconds,
    )
    if status < 200 or status >= 300:
        return []
    if isinstance(payload, list):
        return [item for item in payload if isinstance(item, dict)]
    if isinstance(payload, dict):
        items = payload.get("agents") or []
        return [item for item in items if isinstance(item, dict)]
    return []


def _match_existing(manifest: dict[str, Any], manifest_url: str, agents: list[dict[str, Any]]) -> dict[str, Any] | None:
    name = str(manifest.get("name") or "")
    endpoint = str(manifest.get("endpoint") or "")
    for agent in agents:
        if str(agent.get("manifest_url") or "") == manifest_url:
            return agent
        if endpoint and str(agent.get("endpoint") or "") == endpoint:
            return agent
        if name and str(agent.get("name") or "") == name:
            return agent
    return None


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--api-base", default=DEFAULT_API_BASE)
    parser.add_argument("--public-base-url", default=DEFAULT_PUBLIC_BASE_URL)
    parser.add_argument("--owner-address", default=TARGET_WALLET)
    parser.add_argument("--status-file", type=Path, default=DEFAULT_STATUS_FILE)
    parser.add_argument("--timeout-seconds", type=float, default=25.0)
    parser.add_argument("--submit", action="store_true")
    args = parser.parse_args()

    api_base = args.api_base.rstrip("/")
    public_base_url = args.public_base_url.rstrip("/")
    result: dict[str, Any] = {
        "schema": "x0tta6bl4.machina_register_services_status.v1",
        "checked_at_utc": _utc_now(),
        "api_base": api_base,
        "public_base_url": public_base_url,
        "owner_address": args.owner_address,
        "submit": bool(args.submit),
        "claim_boundary": (
            "This proves only Machina API listing actions. It does not prove buyer calls, "
            "settlement, or received funds."
        ),
        "services_expected": len(SERVICE_IDS),
        "services": [],
    }

    try:
        agents = _existing_agents(api_base, args.timeout_seconds)
    except Exception as exc:
        result.update({"ok": False, "error": f"existing_agents:{type(exc).__name__}: {exc}"})
        args.status_file.parent.mkdir(parents=True, exist_ok=True)
        args.status_file.write_text(json.dumps(result, indent=2, sort_keys=True), encoding="utf-8")
        print(json.dumps(result, indent=2, sort_keys=True))
        return 1

    ok = True
    for service_id in SERVICE_IDS:
        manifest_url = _manifest_url(public_base_url, service_id)
        service_status: dict[str, Any] = {"service_id": service_id, "manifest_url": manifest_url}
        try:
            manifest = _load_manifest(manifest_url, args.timeout_seconds)
            service_status.update(
                {
                    "name": manifest.get("name"),
                    "endpoint": manifest.get("endpoint"),
                    "price_usdc": (manifest.get("pricing") or {}).get("amount") if isinstance(manifest.get("pricing"), dict) else None,
                    "receive_address": (manifest.get("payment") or {}).get("receive_address") if isinstance(manifest.get("payment"), dict) else None,
                }
            )
            existing = _match_existing(manifest, manifest_url, agents)
            if existing:
                service_status.update({"status": "already_registered", "agent": existing})
            elif args.submit:
                http_status, response = _http_json(
                    f"{api_base}/api/v1/agents",
                    method="POST",
                    payload={"manifest_url": manifest_url, "owner_address": args.owner_address},
                    timeout_seconds=args.timeout_seconds,
                )
                service_status.update(
                    {
                        "status": "registered" if 200 <= http_status < 300 else "register_failed",
                        "http_status": http_status,
                        "agent": response,
                    }
                )
                if not (200 <= http_status < 300):
                    ok = False
                if isinstance(response, dict):
                    agents.append(response)
            else:
                service_status["status"] = "would_register"
        except urllib.error.HTTPError as exc:
            body = exc.read().decode("utf-8", errors="replace")
            try:
                payload = json.loads(body)
            except json.JSONDecodeError:
                payload = {"raw": body[:2000]}
            service_status.update({"status": "failed", "http_status": exc.code, "response": payload})
            ok = False
        except Exception as exc:
            service_status.update({"status": "failed", "error": f"{type(exc).__name__}: {exc}"})
            ok = False
        result["services"].append(service_status)

    registered = [item for item in result["services"] if item.get("status") in {"registered", "already_registered"}]
    result.update(
        {
            "ok": ok and len(registered) == len(SERVICE_IDS),
            "registered_or_existing_total": len(registered),
            "created_total": sum(1 for item in result["services"] if item.get("status") == "registered"),
            "next_action": "watch_for_buyer_x402_calls" if len(registered) == len(SERVICE_IDS) else "retry_failed_machina_registrations",
        }
    )
    args.status_file.parent.mkdir(parents=True, exist_ok=True)
    args.status_file.write_text(json.dumps(result, indent=2, sort_keys=True), encoding="utf-8")
    print(json.dumps(result, indent=2, sort_keys=True))
    return 0 if result["ok"] else 1


if __name__ == "__main__":
    raise SystemExit(main())
