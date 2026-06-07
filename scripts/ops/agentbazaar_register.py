#!/usr/bin/env python3
"""Register the x0tta6bl4 push endpoint on AgentBazaar."""

from __future__ import annotations

import argparse
import base64
import json
import os
import sys
import time
import urllib.error
import urllib.request
from pathlib import Path
from typing import Any


ROOT = Path(__file__).resolve().parents[2]
ARTIFACT_DIR = ROOT / ".tmp" / "non-bounty"
DEFAULT_PUBLIC_BASE_URL = "https://saccharolytic-uncatechized-tanika.ngrok-free.dev"
DEFAULT_API_BASE = "https://agentbazaar.dev"
DEFAULT_KEYPAIR = ARTIFACT_DIR / "agentbazaar_keypair.secret.json"
DEFAULT_STATUS = ARTIFACT_DIR / "agentbazaar_register_status.json"
DEFAULT_SECRET_STATUS = ARTIFACT_DIR / "agentbazaar_register_secret.json"

BASE58_ALPHABET = "123456789ABCDEFGHJKLMNPQRSTUVWXYZabcdefghijkmnopqrstuvwxyz"


def b58encode(raw: bytes) -> str:
    value = int.from_bytes(raw, "big")
    encoded = ""
    while value:
        value, mod = divmod(value, 58)
        encoded = BASE58_ALPHABET[mod] + encoded
    leading_zeroes = len(raw) - len(raw.lstrip(b"\0"))
    if not encoded:
        return "1" * leading_zeroes or "1"
    return "1" * leading_zeroes + encoded


def _chmod_secret(path: Path) -> None:
    try:
        path.chmod(0o600)
    except OSError:
        pass


def generate_keypair(path: Path) -> dict[str, Any]:
    try:
        from nacl.signing import SigningKey
    except ImportError as exc:
        raise RuntimeError("PyNaCl is required for AgentBazaar signing") from exc

    signing_key = SigningKey.generate()
    seed = bytes(signing_key)
    public_key = bytes(signing_key.verify_key)
    keypair = list(seed + public_key)
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(keypair) + "\n", encoding="utf-8")
    _chmod_secret(path)
    return {"path": str(path), "public_key": b58encode(public_key)}


def load_keypair(path: Path) -> tuple[Any, str]:
    try:
        from nacl.signing import SigningKey
    except ImportError as exc:
        raise RuntimeError("PyNaCl is required for AgentBazaar signing") from exc

    raw = json.loads(path.read_text(encoding="utf-8"))
    if not isinstance(raw, list) or len(raw) not in {32, 64}:
        raise ValueError("AgentBazaar keypair must be a JSON array of 32 or 64 bytes")
    key_bytes = bytes(int(item) for item in raw)
    seed = key_bytes[:32]
    signing_key = SigningKey(seed)
    return signing_key, b58encode(bytes(signing_key.verify_key))


def sign_headers(keypair_path: Path, action: str) -> dict[str, str]:
    signing_key, public_key = load_keypair(keypair_path)
    timestamp_ms = int(time.time() * 1000)
    message = f"agentbazaar:{action}:{timestamp_ms}"
    signature = signing_key.sign(message.encode("utf-8")).signature
    return {
        "X-Wallet-Address": public_key,
        "X-Wallet-Signature": base64.b64encode(signature).decode("ascii"),
        "X-Wallet-Message": message,
    }


def build_registration_payload(
    *,
    public_base_url: str,
    name: str,
    price_per_request: int,
) -> dict[str, Any]:
    payload: dict[str, Any] = {
        "name": name,
        "skills": (
            "domain health, url snapshot, x402 validation, api docs, "
            "repo triage, listing audit, payment risk, income route"
        ),
        "pricePerRequest": price_per_request,
        "description": (
            "Fixed-scope public-input agent. Returns domain health, URL snapshots, "
            "x402 validation, API docs, listing audits, payment-risk reports, "
            "and income-route scoring. No secrets or private-account tasks."
        ),
        "deliveryMode": "push",
        "endpoint": f"{public_base_url.rstrip('/')}/agentbazaar/task",
    }
    owner_email = os.getenv("AGENTBAZAAR_OWNER_EMAIL", "").strip()
    owner_twitter = os.getenv("AGENTBAZAAR_OWNER_TWITTER", "").strip().lstrip("@")
    owner_github = os.getenv("AGENTBAZAAR_OWNER_GITHUB", "").strip()
    if owner_email:
        payload["ownerEmail"] = owner_email
    if owner_twitter:
        payload["ownerTwitter"] = owner_twitter
    if owner_github:
        payload["ownerGithub"] = owner_github
    return payload


def redact(value: Any) -> Any:
    if isinstance(value, dict):
        redacted: dict[str, Any] = {}
        for key, item in value.items():
            if key.lower() in {"token", "apikey", "api_key", "secret", "privatekey", "private_key"}:
                redacted[key] = "[redacted]"
            else:
                redacted[key] = redact(item)
        return redacted
    if isinstance(value, list):
        return [redact(item) for item in value]
    return value


def submit_registration(
    *,
    api_base: str,
    keypair_path: Path,
    payload: dict[str, Any],
    timeout_seconds: float,
) -> dict[str, Any]:
    body = json.dumps(payload).encode("utf-8")
    headers = {
        "Content-Type": "application/json",
        "Accept": "application/json",
        "User-Agent": "x0tta6bl4-agentbazaar-register",
        **sign_headers(keypair_path, "register"),
    }
    request = urllib.request.Request(
        f"{api_base.rstrip('/')}/agents/register",
        data=body,
        headers=headers,
        method="POST",
    )
    try:
        with urllib.request.urlopen(request, timeout=timeout_seconds) as response:
            text = response.read().decode("utf-8", errors="replace")
            parsed: Any = json.loads(text) if text else {}
            return {"ok": True, "http_status": int(response.status), "response": parsed}
    except urllib.error.HTTPError as exc:
        text = exc.read().decode("utf-8", errors="replace")
        parsed = None
        try:
            parsed = json.loads(text)
        except json.JSONDecodeError:
            parsed = text[:2_000]
        return {"ok": False, "http_status": int(exc.code), "response": parsed}
    except Exception as exc:
        return {"ok": False, "http_status": 0, "error": exc.__class__.__name__, "detail": str(exc)[:500]}


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--api-base", default=os.getenv("AGENTBAZAAR_API_BASE", DEFAULT_API_BASE))
    parser.add_argument("--public-base-url", default=os.getenv("X0T_PUBLIC_BASE_URL", DEFAULT_PUBLIC_BASE_URL))
    parser.add_argument("--name", default=os.getenv("AGENTBAZAAR_AGENT_NAME", "x0tta6bl4-web-health"))
    parser.add_argument("--price-per-request", type=int, default=int(os.getenv("AGENTBAZAAR_PRICE_MICRO_USDC", "10000")))
    parser.add_argument("--keypair", type=Path, default=DEFAULT_KEYPAIR)
    parser.add_argument("--status-file", type=Path, default=DEFAULT_STATUS)
    parser.add_argument("--secret-status-file", type=Path, default=DEFAULT_SECRET_STATUS)
    parser.add_argument("--timeout-seconds", type=float, default=20.0)
    parser.add_argument("--generate-keypair", action="store_true")
    parser.add_argument("--submit", action="store_true")
    args = parser.parse_args(argv)

    ARTIFACT_DIR.mkdir(parents=True, exist_ok=True)
    key_info: dict[str, Any] = {"path": str(args.keypair), "exists": args.keypair.exists()}
    if args.generate_keypair or (args.submit and not args.keypair.exists()):
        key_info = generate_keypair(args.keypair)
        key_info["generated"] = True
    elif args.keypair.exists():
        try:
            _, public_key = load_keypair(args.keypair)
            key_info["public_key"] = public_key
        except Exception as exc:
            key_info["load_error"] = exc.__class__.__name__

    payload = build_registration_payload(
        public_base_url=args.public_base_url,
        name=args.name,
        price_per_request=args.price_per_request,
    )
    status: dict[str, Any] = {
        "checked_at_utc": time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime()),
        "mode": "submit" if args.submit else "offline",
        "api_base": args.api_base.rstrip("/"),
        "public_base_url": args.public_base_url.rstrip("/"),
        "agent_endpoint": payload["endpoint"],
        "price_per_request_micro_usdc": args.price_per_request,
        "keypair": key_info,
        "payload": payload,
        "claim_boundary": (
            "AgentBazaar pays USDC on Solana to the registering wallet. This does not "
            "prove a buyer hired the agent, escrow settled, or funds reached the Base wallet."
        ),
    }

    if args.submit:
        if not args.keypair.exists():
            status["registration"] = {"ok": False, "error": "missing_keypair"}
        else:
            registration = submit_registration(
                api_base=args.api_base,
                keypair_path=args.keypair,
                payload=payload,
                timeout_seconds=args.timeout_seconds,
            )
            status["registration"] = redact(registration)
            args.secret_status_file.write_text(json.dumps(registration, indent=2, ensure_ascii=False) + "\n", encoding="utf-8")
            _chmod_secret(args.secret_status_file)
    else:
        status["registration"] = {"ok": False, "reason": "offline_preview_only"}

    args.status_file.write_text(json.dumps(status, indent=2, ensure_ascii=False) + "\n", encoding="utf-8")
    print(f"wrote: {args.status_file}")
    if args.submit:
        print(json.dumps(status["registration"], indent=2, ensure_ascii=False))
    else:
        print(json.dumps({"endpoint": payload["endpoint"], "price_micro_usdc": args.price_per_request}, indent=2))
    return 0 if not args.submit or bool((status.get("registration") or {}).get("ok")) else 1


if __name__ == "__main__":
    raise SystemExit(main())
