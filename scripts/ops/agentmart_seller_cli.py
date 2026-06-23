#!/usr/bin/env python3
"""Prepare and publish AgentMart products for x0tta6bl4.

This CLI never asks for secrets in chat. Use environment variables locally:

AGENTMART_EMAIL=owner@example.com
AGENTMART_API_KEY=bak_...      # optional if already registered
AGENTMART_STORE_KEY=sk_...     # optional if store already exists
"""

from __future__ import annotations

import argparse
import json
import os
import re
import urllib.error
import urllib.parse
import urllib.request
from datetime import datetime, timezone
from pathlib import Path
from typing import Any


ROOT = Path(__file__).resolve().parents[2]
API_BASE = "https://agentmart.store/api"
DEFAULT_PACK = ROOT / "docs/commercial/agentmart_product_pack.json"
DEFAULT_IDENTITY = ROOT / ".tmp/non-bounty/agentmart_identity.secret.json"
DEFAULT_STATUS = ROOT / ".tmp/non-bounty/agentmart_seller_status.json"
DEFAULT_WALLET = "0x6017613e80d7893EB2aD5c0585b3f1f88CD6e099"
DEFAULT_PUBLIC_BASE_URL = "https://saccharolytic-uncatechized-tanika.ngrok-free.dev"


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
    buyer_key: str | None = None,
    store_key: str | None = None,
    timeout_seconds: float = 30.0,
) -> tuple[int, Any]:
    data = None if payload is None else json.dumps(payload).encode("utf-8")
    headers = {
        "Accept": "application/json",
        "Content-Type": "application/json",
        "User-Agent": "x0tta6bl4-agentmart-seller-cli",
    }
    if buyer_key:
        headers["X-API-Key"] = buyer_key
    if store_key:
        headers["X-AgentMart-Key"] = store_key
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


def _load_identity(path: Path) -> dict[str, Any]:
    identity: dict[str, Any] = {}
    if path.exists():
        identity.update(_read_json(path))
    if os.getenv("AGENTMART_EMAIL"):
        identity["email"] = os.getenv("AGENTMART_EMAIL")
    if os.getenv("AGENTMART_API_KEY"):
        identity["api_key"] = os.getenv("AGENTMART_API_KEY")
    if os.getenv("AGENTMART_STORE_KEY"):
        identity["store_key"] = os.getenv("AGENTMART_STORE_KEY")
    if os.getenv("AGENTMART_STORE_ID"):
        identity["store_id"] = os.getenv("AGENTMART_STORE_ID")
    if os.getenv("AGENTMART_STORE_SLUG"):
        identity["store_slug"] = os.getenv("AGENTMART_STORE_SLUG")
    return identity


def _public_identity(identity: dict[str, Any]) -> dict[str, Any]:
    return {
        "email_present": bool(identity.get("email")),
        "api_key_present": bool(identity.get("api_key")),
        "api_key_masked": _mask(str(identity.get("api_key") or "")) if identity.get("api_key") else None,
        "store_key_present": bool(identity.get("store_key")),
        "store_key_masked": _mask(str(identity.get("store_key") or "")) if identity.get("store_key") else None,
        "store_id": identity.get("store_id"),
        "store_slug": identity.get("store_slug"),
    }


def _product_public_file_url(product: dict[str, Any], public_base_url: str) -> str:
    file_path = str(product.get("file_path") or "")
    name = Path(file_path).name
    if not name:
        raise ValueError("product file_path is missing")
    return f"{public_base_url.rstrip('/')}/agentmart/products/{urllib.parse.quote(name)}"


def build_product_payloads(pack: dict[str, Any], public_base_url: str) -> list[dict[str, Any]]:
    products = pack.get("products")
    if not isinstance(products, list):
        raise ValueError("pack.products must be a list")
    payloads: list[dict[str, Any]] = []
    for item in products:
        if not isinstance(item, dict):
            continue
        payloads.append(
            {
                "name": item["name"],
                "price": item["price"],
                "description": item["description"],
                "type": item.get("type", "download"),
                "file_url": _product_public_file_url(item, public_base_url),
                "category": item.get("category", "agent-tools"),
                "tags": item.get("tags", []),
            }
        )
    return payloads


def solve_math_challenge(text: str) -> int | None:
    numbers = [int(item) for item in re.findall(r"-?\d+", text)]
    if len(numbers) < 2:
        return None
    if "+" in text:
        return numbers[0] + numbers[1]
    if "-" in text:
        return numbers[0] - numbers[1]
    if "*" in text or "×" in text:
        return numbers[0] * numbers[1]
    return None


def _check_name(path: str, params: dict[str, str], *, offline: bool) -> dict[str, Any]:
    if offline:
        return {"status": "offline_preview", "params": params}
    query = urllib.parse.urlencode(params)
    status, response = _http_json("GET", f"{path}?{query}")
    return {"status": "checked", "http_status": status, "response": response, "params": params}


def _register(identity: dict[str, Any], identity_path: Path, *, offline: bool) -> dict[str, Any]:
    if identity.get("api_key"):
        return {"status": "already_registered"}
    email = str(identity.get("email") or "")
    if not email:
        return {"status": "skipped", "reason": "missing_local_AGENTMART_EMAIL"}
    payload = {
        "email": email,
        "name": os.getenv("AGENTMART_NAME", "x0tta6bl4Tools"),
        "agent_name": os.getenv("AGENTMART_AGENT_NAME", "x0tta6bl4SellerAgent"),
        "agent_type": "openclaw",
    }
    if offline:
        return {"status": "offline_preview", "payload": {**payload, "email": "***"}}
    status, response = _http_json("POST", "/buyer/register", payload=payload)
    result = {"status": "register_failed", "http_status": status, "response": response}
    if status < 400 and isinstance(response, dict) and response.get("api_key"):
        updated = {**identity, "email": email, "api_key": response.get("api_key"), "buyer_id": response.get("buyer_id")}
        _write_json(identity_path, updated, secret=True)
        result = {"status": "registered", "http_status": status, "buyer_id": response.get("buyer_id")}
    return result


def _create_store(identity: dict[str, Any], identity_path: Path, store_name: str, *, offline: bool) -> dict[str, Any]:
    if identity.get("store_key"):
        return {"status": "already_has_store", "store_id": identity.get("store_id"), "store_slug": identity.get("store_slug")}
    api_key = str(identity.get("api_key") or "")
    email = str(identity.get("email") or "")
    if not api_key:
        return {"status": "skipped", "reason": "missing_buyer_api_key"}
    if not email:
        return {"status": "skipped", "reason": "missing_email"}
    payload = {"name": store_name, "email": email}
    if offline:
        return {"status": "offline_preview", "payload": {**payload, "email": "***"}}
    status, response = _http_json("POST", "/stores/create", payload=payload, buyer_key=api_key)
    result = {"status": "store_create_failed", "http_status": status, "response": response}
    if status < 400 and isinstance(response, dict):
        store_key = str(response.get("secret_key") or response.get("store_key") or "")
        if store_key:
            updated = {
                **identity,
                "store_key": store_key,
                "store_id": response.get("store_id"),
                "store_slug": response.get("store_slug"),
            }
            _write_json(identity_path, updated, secret=True)
            result = {"status": "store_created", "http_status": status, "store_id": response.get("store_id"), "store_slug": response.get("store_slug")}
    return result


def _set_wallet(identity: dict[str, Any], wallet: str, *, offline: bool) -> dict[str, Any]:
    store_key = str(identity.get("store_key") or "")
    if not store_key:
        return {"status": "skipped", "reason": "missing_store_key"}
    payload = {"wallet_usdc": wallet}
    if offline:
        return {"status": "offline_preview", "payload": payload}
    status, response = _http_json("PATCH", "/stores/wallet", payload=payload, store_key=store_key)
    return {"status": "wallet_set" if status < 400 else "wallet_failed", "http_status": status, "response": response}


def _create_products(identity: dict[str, Any], products: list[dict[str, Any]], *, offline: bool) -> list[dict[str, Any]]:
    store_key = str(identity.get("store_key") or "")
    if not store_key:
        return [{"status": "skipped", "reason": "missing_store_key", "payload": item} for item in products]
    results: list[dict[str, Any]] = []
    for payload in products:
        if offline:
            results.append({"status": "offline_preview", "payload": payload})
            continue
        status, response = _http_json("POST", "/products/create", payload=payload, store_key=store_key)
        product_id = response.get("product_id") or response.get("id") if isinstance(response, dict) else None
        results.append(
            {
                "status": "product_created" if status < 400 else "product_failed",
                "http_status": status,
                "product_id": product_id,
                "response": response,
                "payload": payload,
            }
        )
    return results


def _publish_products(identity: dict[str, Any], product_results: list[dict[str, Any]], *, offline: bool) -> list[dict[str, Any]]:
    store_key = str(identity.get("store_key") or "")
    if not store_key:
        return [{"status": "skipped", "reason": "missing_store_key"}]
    publish_results: list[dict[str, Any]] = []
    for item in product_results:
        product_id = str(item.get("product_id") or "")
        if not product_id:
            continue
        if offline:
            publish_results.append({"status": "offline_preview", "product_id": product_id})
            continue
        status, response = _http_json("POST", f"/products/{product_id}/publish", store_key=store_key)
        if status >= 400 or not isinstance(response, dict):
            publish_results.append({"status": "publish_failed", "http_status": status, "product_id": product_id, "response": response})
            continue
        verification = response.get("verification") if isinstance(response.get("verification"), dict) else {}
        token = str(verification.get("challenge_token") or response.get("challenge_token") or "")
        challenge = str(verification.get("challenge") or response.get("challenge") or "")
        answer = solve_math_challenge(challenge)
        if not token or answer is None:
            publish_results.append({"status": "publish_challenge_unresolved", "http_status": status, "product_id": product_id, "response": response})
            continue
        status2, response2 = _http_json(
            "POST",
            f"/products/{product_id}/publish",
            payload={"challenge_token": token, "challenge_answer": answer},
            store_key=store_key,
        )
        publish_results.append(
            {
                "status": "published" if status2 < 400 else "publish_failed",
                "http_status": status2,
                "product_id": product_id,
                "challenge": challenge,
                "response": response2,
            }
        )
    return publish_results


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--pack", type=Path, default=DEFAULT_PACK)
    parser.add_argument("--identity", type=Path, default=DEFAULT_IDENTITY)
    parser.add_argument("--write-status", type=Path, default=DEFAULT_STATUS)
    parser.add_argument("--public-base-url", default=DEFAULT_PUBLIC_BASE_URL)
    parser.add_argument("--wallet", default=DEFAULT_WALLET)
    parser.add_argument("--store-name", default=os.getenv("AGENTMART_STORE_NAME", "x0tta6bl4 Agent Tools"))
    parser.add_argument("--submit", action="store_true")
    parser.add_argument("--publish", action="store_true")
    parser.add_argument("--offline", action="store_true")
    return parser.parse_args()


def main() -> int:
    args = parse_args()
    offline = args.offline or not args.submit
    pack = _read_json(args.pack)
    identity = _load_identity(args.identity)
    name_checks = {
        "buyer": _check_name(
            "/buyer/check-name",
            {
                "name": os.getenv("AGENTMART_NAME", "x0tta6bl4Tools"),
                "agent_name": os.getenv("AGENTMART_AGENT_NAME", "x0tta6bl4SellerAgent"),
            },
            offline=offline,
        ),
        "store": _check_name("/stores/check-name", {"name": args.store_name}, offline=offline),
    }
    register = _register(identity, args.identity, offline=offline)
    identity = _load_identity(args.identity)
    store = _create_store(identity, args.identity, args.store_name, offline=offline)
    identity = _load_identity(args.identity)
    wallet = _set_wallet(identity, args.wallet, offline=offline)
    products = build_product_payloads(pack, args.public_base_url)
    created = _create_products(identity, products, offline=offline)
    published = _publish_products(identity, created, offline=offline) if args.publish else []
    result = {
        "schema": "x0tta6bl4.agentmart_seller_cli.v1",
        "checked_at_utc": _utc_now(),
        "agentmart_skill_version": "1.0.6",
        "mode": "submit" if args.submit else "offline_preview",
        "identity": _public_identity(identity),
        "wallet": args.wallet,
        "name_checks": name_checks,
        "register": register,
        "store": store,
        "wallet_setup": wallet,
        "products_total": len(products),
        "products": created,
        "published": published,
        "claim_boundary": (
            "This proves AgentMart readiness or API submission attempts only. It does not prove "
            "email verification, product sales, payout, on-chain transfer, or received funds."
        ),
    }
    _write_json(args.write_status, result)
    print(json.dumps(result, indent=2, sort_keys=True))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
