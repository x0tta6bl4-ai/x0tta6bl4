#!/usr/bin/env python3
"""Register x0tta6bl4 paid x402 endpoints on AgentPay.

The script may receive a public contact email locally, then stores any returned
AgentPay api_key in a chmod 0600 local secret file. It never prints the raw key.
"""

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


ARTIFACT_DIR = Path(".tmp/non-bounty")
DEFAULT_IDENTITY = ARTIFACT_DIR / "agentpay_identity.secret.json"
DEFAULT_STATUS = ARTIFACT_DIR / "agentpay_register_services_status.json"
DEFAULT_API_BASE = "https://x402-agent-pay.com"
PUBLIC_BASE_URL = "https://saccharolytic-uncatechized-tanika.ngrok-free.dev"
TARGET_WALLET = "0x6017613e80d7893EB2aD5c0585b3f1f88CD6e099"


SERVICES: list[dict[str, Any]] = [
    {
        "name": "x0tta6bl4 Repo Triage",
        "url": f"{PUBLIC_BASE_URL}/paid/repo-triage",
        "price_usdc": 0.02,
        "description": "Repository triage from submitted public file snippets.",
        "method": "POST",
    },
    {
        "name": "x0tta6bl4 API Docs Generator",
        "url": f"{PUBLIC_BASE_URL}/paid/api-docs",
        "price_usdc": 0.03,
        "description": "Markdown API docs from submitted REST endpoint specs.",
        "method": "POST",
    },
    {
        "name": "x0tta6bl4 Agent Listing Audit",
        "url": f"{PUBLIC_BASE_URL}/paid/listing-audit",
        "price_usdc": 0.02,
        "description": "Marketplace listing score and conversion fixes.",
        "method": "POST",
    },
    {
        "name": "x0tta6bl4 Payment Risk Report",
        "url": f"{PUBLIC_BASE_URL}/paid/payment-risk",
        "price_usdc": 0.02,
        "description": "Risk report for public payment metadata and wallet approvals.",
        "method": "POST",
    },
    {
        "name": "x0tta6bl4 Income Route",
        "url": f"{PUBLIC_BASE_URL}/paid/income-route",
        "price_usdc": 0.02,
        "description": "Non-bounty earning route score by cost, risk, automation fit, and certainty.",
        "method": "POST",
    },
    {
        "name": "x0tta6bl4 x402 Endpoint Validator",
        "url": f"{PUBLIC_BASE_URL}/paid/x402-validate",
        "price_usdc": 0.01,
        "description": "Live x402 endpoint validator for HTTP 402 and Payment-Required metadata.",
        "method": "POST",
    },
    {
        "name": "x0tta6bl4 Public URL Snapshot",
        "url": f"{PUBLIC_BASE_URL}/paid/url-snapshot",
        "price_usdc": 0.01,
        "description": "Public URL title, metadata, headings, links, and text preview.",
        "method": "POST",
    },
    {
        "name": "x0tta6bl4 Domain Health Lite",
        "url": f"{PUBLIC_BASE_URL}/paid/domain-health",
        "price_usdc": 0.001,
        "description": "DNS/IP, HTTP status, redirect, and TLS expiry signals for a public domain.",
        "method": "POST",
    },
]


def utc_now() -> str:
    return datetime.now(timezone.utc).replace(microsecond=0).isoformat().replace("+00:00", "Z")


def read_json(path: Path) -> dict[str, Any]:
    if not path.exists():
        return {}
    payload = json.loads(path.read_text(encoding="utf-8"))
    return payload if isinstance(payload, dict) else {}


def write_json(path: Path, payload: dict[str, Any], *, secret: bool = False) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(payload, indent=2, ensure_ascii=False, sort_keys=True) + "\n", encoding="utf-8")
    if secret:
        path.chmod(0o600)


def redact(value: Any) -> Any:
    if isinstance(value, dict):
        redacted: dict[str, Any] = {}
        for key, item in value.items():
            if key.lower() in {"api_key", "apikey", "access_token", "token", "authorization"}:
                redacted[key] = "<redacted>"
            else:
                redacted[key] = redact(item)
        return redacted
    if isinstance(value, list):
        return [redact(item) for item in value]
    return value


def request_json(
    method: str,
    api_base: str,
    path: str,
    *,
    payload: dict[str, Any] | None = None,
    timeout_seconds: float = 30.0,
) -> dict[str, Any]:
    data = None if payload is None else json.dumps(payload).encode("utf-8")
    headers = {
        "Accept": "application/json",
        "User-Agent": "x0tta6bl4-agentpay-register-services/1.0",
    }
    if data is not None:
        headers["Content-Type"] = "application/json"
    request = urllib.request.Request(api_base.rstrip("/") + path, data=data, headers=headers, method=method)
    try:
        with urllib.request.urlopen(request, timeout=timeout_seconds) as response:
            body = response.read().decode("utf-8")
            parsed: Any = json.loads(body) if body else {}
            return {"ok": 200 <= response.status < 300, "http_status": response.status, "response": parsed}
    except urllib.error.HTTPError as exc:
        body = exc.read().decode("utf-8", errors="replace")
        try:
            parsed = json.loads(body) if body else {}
        except json.JSONDecodeError:
            parsed = {"raw": body[:2000]}
        return {"ok": False, "http_status": exc.code, "response": parsed}
    except Exception as exc:
        return {"ok": False, "http_status": None, "response": {"error": exc.__class__.__name__, "detail": str(exc)}}


def email_from(identity: Path, cli_email: str) -> str:
    stored = read_json(identity)
    return (
        cli_email.strip()
        or os.getenv("AGENTPAY_EMAIL", "").strip()
        or str(stored.get("email") or "").strip()
    )


def identity_from(path: Path) -> dict[str, Any]:
    stored = read_json(path)
    return {
        "api_key": str(stored.get("api_key") or "").strip(),
        "partner_id": str(stored.get("partner_id") or "").strip(),
        "wallet": str(stored.get("wallet") or TARGET_WALLET).strip(),
        "email": str(stored.get("email") or "").strip(),
    }


def run(args: argparse.Namespace) -> dict[str, Any]:
    identity = identity_from(args.identity)
    email = email_from(args.identity, args.email)
    status: dict[str, Any] = {
        "schema": "x0tta6bl4.agentpay_register_services_status.v1",
        "checked_at_utc": utc_now(),
        "claim_boundary": (
            "This proves only AgentPay registration attempts. It does not prove "
            "marketplace approval, buyer invocation, settlement, or received funds."
        ),
        "api_base": args.api_base,
        "identity_file": str(args.identity),
        "email_present": bool(email),
        "api_key_present": bool(identity["api_key"]),
        "partner_id_present": bool(identity["partner_id"]),
        "target_wallet": TARGET_WALLET,
        "public_base_url": PUBLIC_BASE_URL,
        "services_expected": len(SERVICES),
    }
    if not email and not identity["api_key"]:
        status["next_action"] = (
            "Run scripts/ops/agentpay_submit_now.sh and enter a public contact email locally. "
            "Do not paste the email or returned api_key into chat."
        )
        return status

    if not identity["api_key"]:
        register_payload = {
            "name": args.provider_name,
            "email": email,
            "wallet": TARGET_WALLET,
            "agent_type": "api_provider",
            "description": args.provider_description,
            "website": PUBLIC_BASE_URL,
        }
        register = request_json("POST", args.api_base, "/api/agentpay/register", payload=register_payload)
        status["register"] = redact(register)
        response = register.get("response") if isinstance(register.get("response"), dict) else {}
        if register.get("ok") and response.get("api_key"):
            identity.update(
                {
                    "api_key": str(response.get("api_key") or ""),
                    "partner_id": str(response.get("partner_id") or ""),
                    "wallet": str(response.get("wallet") or TARGET_WALLET),
                    "email": email,
                }
            )
            write_json(args.identity, identity, secret=True)
            status["api_key_present"] = True
            status["partner_id_present"] = bool(identity["partner_id"])
        else:
            status["next_action"] = "Inspect AgentPay register response; backend may require a different public contact field."
            return status

    partner_id = identity["partner_id"]
    api_key = identity["api_key"]
    if not partner_id or not api_key:
        status["next_action"] = "AgentPay did not return both partner_id and api_key."
        return status

    list_before = request_json(
        "GET",
        args.api_base,
        f"/api/partner/endpoints?partner_id={urllib.parse.quote(partner_id)}&api_key={urllib.parse.quote(api_key)}",
    )
    status["list_before"] = redact(list_before)
    created: list[dict[str, Any]] = []
    for service in SERVICES:
        payload = {
            "partner_id": partner_id,
            "api_key": api_key,
            "url": service["url"],
            "price_usdc": service["price_usdc"],
            "description": f'{service["name"]}: {service["description"]}',
            "method": service["method"],
        }
        created.append({"service": service["name"], **request_json("POST", args.api_base, "/api/partner/endpoints", payload=payload)})
    status["endpoint_results"] = redact(created)
    status["registered_or_existing_total"] = sum(1 for item in created if item.get("ok") or item.get("http_status") in {200, 201, 409})
    status["ok"] = status["registered_or_existing_total"] == len(SERVICES)
    status["next_action"] = "wait_for_agentpay_buyer_call" if status["ok"] else "inspect_agentpay_endpoint_errors"
    return status


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--api-base", default=DEFAULT_API_BASE)
    parser.add_argument("--identity", type=Path, default=DEFAULT_IDENTITY)
    parser.add_argument("--status-file", type=Path, default=DEFAULT_STATUS)
    parser.add_argument("--email", default="")
    parser.add_argument("--provider-name", default="x0tta6bl4 paid x402 tools")
    parser.add_argument(
        "--provider-description",
        default=(
            "Eight public-input paid x402 developer APIs on Base USDC for API docs, "
            "repo triage, listing audits, payment-risk checks, endpoint validation, "
            "URL snapshots, and domain health."
        ),
    )
    args = parser.parse_args()

    status = run(args)
    write_json(args.status_file, redact(status))
    print(json.dumps(redact(status), indent=2, ensure_ascii=False, sort_keys=True))
    return 0 if status.get("ok") or status.get("next_action") else 1


if __name__ == "__main__":
    raise SystemExit(main())
