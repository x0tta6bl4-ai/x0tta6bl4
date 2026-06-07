#!/usr/bin/env python3
"""Register and manage the x0tta6bl4 Clustly earning channel."""

from __future__ import annotations

import argparse
import json
import time
import urllib.error
import urllib.request
from pathlib import Path
from typing import Any


ROOT = Path(__file__).resolve().parents[2]
ARTIFACT_DIR = ROOT / ".tmp" / "non-bounty"
DEFAULT_API_BASE = "https://clustly.ai"
DEFAULT_PUBLIC_BASE_URL = "https://saccharolytic-uncatechized-tanika.ngrok-free.dev"
DEFAULT_SECRET = ARTIFACT_DIR / "clustly_agent.secret.json"
DEFAULT_STATUS = ARTIFACT_DIR / "clustly_agent_status.json"


def _chmod_secret(path: Path) -> None:
    try:
        path.chmod(0o600)
    except OSError:
        pass


def _json_request(
    method: str,
    url: str,
    *,
    payload: dict[str, Any] | None = None,
    agent_key: str = "",
    timeout_seconds: float = 20.0,
) -> dict[str, Any]:
    data = None if payload is None else json.dumps(payload).encode("utf-8")
    headers = {
        "Accept": "application/json",
        "User-Agent": "x0tta6bl4-clustly-agent",
    }
    if payload is not None:
        headers["Content-Type"] = "application/json"
    if agent_key:
        headers["x-agent-key"] = agent_key
    request = urllib.request.Request(url, data=data, headers=headers, method=method)
    try:
        with urllib.request.urlopen(request, timeout=timeout_seconds) as response:
            text = response.read().decode("utf-8", errors="replace")
            parsed: Any = json.loads(text) if text else {}
            return {"ok": True, "http_status": int(response.status), "response": parsed}
    except urllib.error.HTTPError as exc:
        text = exc.read().decode("utf-8", errors="replace")
        try:
            parsed = json.loads(text)
        except json.JSONDecodeError:
            parsed = text[:2_000]
        return {"ok": False, "http_status": int(exc.code), "response": parsed}
    except Exception as exc:
        return {"ok": False, "http_status": 0, "error": exc.__class__.__name__, "detail": str(exc)[:500]}


def redact(value: Any) -> Any:
    if isinstance(value, dict):
        out: dict[str, Any] = {}
        for key, item in value.items():
            if key.lower() in {"agent_key", "key", "token", "secret", "api_key"}:
                out[key] = "[redacted]"
            else:
                out[key] = redact(item)
        return out
    if isinstance(value, list):
        return [redact(item) for item in value]
    return value


def build_register_payload(name: str) -> dict[str, Any]:
    return {
        "name": name,
        "description": (
            "x0tta6bl4 agent for fixed-scope public-input checks: domain health, "
            "URL snapshots, x402 validation, API docs, listing audits, and payment risk. "
            "Rejects secrets, private accounts, CAPTCHA, KYC bypass, spam, and harmful automation."
        ),
        "tagline": "Public web health and x402 checks into JSON/Markdown",
        "capabilities": [
            {
                "name": "Public domain and URL health reports",
                "category": "analysis",
                "description": "Checks DNS, HTTP status, redirects, TLS expiry, page metadata, and public URL shape.",
            },
            {
                "name": "x402 endpoint validation",
                "category": "analysis",
                "description": "Checks public x402 endpoints for HTTP 402, Payment-Required metadata, payTo, network, asset, and amount.",
            },
            {
                "name": "Small API docs and listing audits",
                "category": "coding",
                "description": "Turns public endpoint specs or marketplace listing text into concise documentation or scorecards.",
            },
        ],
    }


def build_service_payload() -> dict[str, Any]:
    return {
        "title": "I check public domains, URLs, and x402 endpoints",
        "slug": "x0tta6bl4-public-web-x402-check",
        "description": (
            "Send one public domain, URL, or x402 endpoint. I return a compact Markdown/JSON report "
            "with DNS/IP, HTTP, redirect, TLS, page metadata, or x402 payment metadata checks. "
            "Public inputs only; no secrets or private accounts."
        ),
        "verification_criteria": (
            "Deliverable is Markdown or JSON. It includes the submitted target, verdict, observed HTTP/DNS/TLS "
            "or x402 fields, risks, and a clear boundary statement. It refuses private-network and secret-like inputs."
        ),
        "intake_questions": [
            {"id": "target", "label": "Public domain, URL, or x402 endpoint", "type": "url", "required": True},
            {
                "id": "check_type",
                "label": "Check type",
                "type": "text",
                "required": False,
                "placeholder": "domain-health, url-snapshot, x402-validate",
            },
        ],
        "price_amount": 1,
        "price_currency": "USDC",
        "delivery_hours": 1,
        "chain": "solana",
        "category": "Research",
        "tags": ["domain", "x402", "url", "dns", "tls"],
    }


def build_webhook_payload(public_base_url: str, *, secret: str = "") -> dict[str, Any]:
    payload: dict[str, Any] = {
        "url": f"{public_base_url.rstrip('/')}/clustly/webhook",
        "events": ["task.created", "task.claimed", "task.completed"],
    }
    if secret:
        payload["secret"] = secret
    return payload


def _load_secret(path: Path) -> dict[str, Any]:
    if not path.exists():
        return {}
    try:
        data = json.loads(path.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError):
        return {}
    return data if isinstance(data, dict) else {}


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--api-base", default=DEFAULT_API_BASE)
    parser.add_argument("--public-base-url", default=DEFAULT_PUBLIC_BASE_URL)
    parser.add_argument("--webhook-secret", default="x0t-clustly-webhook")
    parser.add_argument("--name", default="x0tta6bl4-web-health")
    parser.add_argument("--secret-file", type=Path, default=DEFAULT_SECRET)
    parser.add_argument("--status-file", type=Path, default=DEFAULT_STATUS)
    parser.add_argument("--timeout-seconds", type=float, default=20.0)
    parser.add_argument("--register", action="store_true")
    parser.add_argument("--force-register", action="store_true")
    parser.add_argument("--status", action="store_true")
    parser.add_argument("--open-tasks", action="store_true")
    parser.add_argument("--orders", action="store_true")
    parser.add_argument("--balance", action="store_true")
    parser.add_argument("--register-webhook", action="store_true")
    parser.add_argument("--test-webhook", action="store_true")
    parser.add_argument("--publish-service", action="store_true")
    args = parser.parse_args(argv)

    ARTIFACT_DIR.mkdir(parents=True, exist_ok=True)
    api_base = args.api_base.rstrip("/")
    secret = _load_secret(args.secret_file)
    agent_key = str(secret.get("agent_key") or "")
    result: dict[str, Any] = {
        "checked_at_utc": time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime()),
        "api_base": api_base,
        "public_base_url": args.public_base_url.rstrip("/"),
        "secret_file": str(args.secret_file),
        "has_agent_key": bool(agent_key),
        "claim_code_present": bool(secret.get("claim_code")),
        "connect_url_present": bool(secret.get("connect_url")),
        "profile_url": secret.get("profile_url"),
        "wallet_address": secret.get("wallet_address"),
        "actions": {},
        "claim_boundary": (
            "Clustly registration and service listing do not prove a buyer order, approval, escrow release, "
            "withdrawal, or funds on the Base wallet."
        ),
    }

    if args.register:
        if agent_key and not args.force_register:
            result["actions"]["register"] = {"ok": True, "skipped": True, "reason": "existing_agent_key"}
        else:
            register = _json_request(
                "POST",
                f"{api_base}/api/v1/agent/register",
                payload=build_register_payload(args.name),
                timeout_seconds=args.timeout_seconds,
            )
            result["actions"]["register"] = redact(register)
            response = register.get("response")
            if register.get("ok") and isinstance(response, dict):
                secret = {
                    "agent_id": response.get("agent_id"),
                    "agent_key": response.get("agent_key"),
                    "name": response.get("name"),
                    "slug": response.get("slug"),
                    "wallet_address": response.get("wallet_address"),
                    "wallet_phantom": response.get("wallet_phantom"),
                    "profile_url": response.get("profile_url"),
                    "claim_code": response.get("claim_code") or response.get("verification_code"),
                    "connect_url": response.get("connect_url"),
                    "raw": response,
                }
                args.secret_file.write_text(json.dumps(secret, indent=2, ensure_ascii=False) + "\n", encoding="utf-8")
                _chmod_secret(args.secret_file)
                agent_key = str(secret.get("agent_key") or "")
                result["has_agent_key"] = bool(agent_key)
                result["claim_code"] = secret.get("claim_code")
                result["connect_url"] = secret.get("connect_url")

    if args.status and agent_key:
        result["actions"]["agent_status"] = redact(
            _json_request(
                "GET",
                f"{api_base}/api/v1/agent/status",
                agent_key=agent_key,
                timeout_seconds=args.timeout_seconds,
            )
        )
        result["actions"]["agent_me"] = redact(
            _json_request(
                "GET",
                f"{api_base}/api/v1/agent/me",
                agent_key=agent_key,
                timeout_seconds=args.timeout_seconds,
            )
        )

    if args.open_tasks and agent_key:
        result["actions"]["open_tasks"] = redact(
            _json_request(
                "GET",
                f"{api_base}/api/v1/tasks/open",
                agent_key=agent_key,
                timeout_seconds=args.timeout_seconds,
            )
        )

    if args.orders and agent_key:
        result["actions"]["orders_pending_acceptance"] = redact(
            _json_request(
                "GET",
                f"{api_base}/api/v1/orders?status=pending_acceptance",
                agent_key=agent_key,
                timeout_seconds=args.timeout_seconds,
            )
        )
        result["actions"]["orders_funded"] = redact(
            _json_request(
                "GET",
                f"{api_base}/api/v1/orders?status=funded",
                agent_key=agent_key,
                timeout_seconds=args.timeout_seconds,
            )
        )

    if args.balance and agent_key:
        result["actions"]["balance"] = redact(
            _json_request(
                "GET",
                f"{api_base}/api/v1/agent/balance",
                agent_key=agent_key,
                timeout_seconds=args.timeout_seconds,
            )
        )

    if args.register_webhook and agent_key:
        result["actions"]["register_webhook"] = redact(
            _json_request(
                "POST",
                f"{api_base}/api/v1/agent/webhooks",
                payload=build_webhook_payload(args.public_base_url, secret=args.webhook_secret),
                agent_key=agent_key,
                timeout_seconds=args.timeout_seconds,
            )
        )

    if args.test_webhook and agent_key:
        result["actions"]["test_webhook"] = redact(
            _json_request(
                "POST",
                f"{api_base}/api/v1/agent/webhooks/test",
                payload={"url": f"{args.public_base_url.rstrip('/')}/clustly/webhook"},
                agent_key=agent_key,
                timeout_seconds=args.timeout_seconds,
            )
        )

    if args.publish_service and agent_key:
        result["actions"]["publish_service"] = redact(
            _json_request(
                "POST",
                f"{api_base}/api/v1/services",
                payload=build_service_payload(),
                agent_key=agent_key,
                timeout_seconds=args.timeout_seconds,
            )
        )

    args.status_file.write_text(json.dumps(result, indent=2, ensure_ascii=False) + "\n", encoding="utf-8")
    print(f"wrote: {args.status_file}")
    print(json.dumps(redact(result), indent=2, ensure_ascii=False)[:4_000])
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
