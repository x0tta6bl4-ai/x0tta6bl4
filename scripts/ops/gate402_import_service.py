#!/usr/bin/env python3
"""Import the public x0tta6bl4 x402 manifest into Gate402.

This script is intentionally non-custodial: it creates a local EVM identity only
for Gate402 message signing. The paid x402 manifest still points buyers to the
wallet configured by the public service.
"""

from __future__ import annotations

import argparse
import json
import os
from dataclasses import dataclass
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

import requests
from eth_account import Account
from eth_account.messages import encode_defunct


ROOT = Path(__file__).resolve().parents[2]
ARTIFACT_DIR = ROOT / ".tmp" / "non-bounty"
DEFAULT_API_BASE = "https://gate402.net/v1"
DEFAULT_PUBLIC_BASE_URL = "https://saccharolytic-uncatechized-tanika.ngrok-free.dev"
DEFAULT_NAME = "x0tta6bl4 paid x402 tools"
DEFAULT_IDENTITY_FILE = ARTIFACT_DIR / "gate402_identity.secret.json"
DEFAULT_STATUS_FILE = ARTIFACT_DIR / "gate402_import_status.json"
DEFAULT_DISCOVER_FILE = ARTIFACT_DIR / "gate402_discover_x0tta6bl4.json"
RUNTIME_STATUS_FILE = ARTIFACT_DIR / "x402_paid_api_public_runtime_status.json"
CLAIM_BOUNDARY = (
    "This status proves only Gate402 API reachability, wallet-message auth, "
    "URL import attempt, and discovery probe. It does not prove buyer demand, "
    "paid calls, settlement, on-chain transfer, or received funds."
)
REDACTED_KEYS = {
    "private_key",
    "token",
    "signature",
    "challenge",
    "message",
}


@dataclass(frozen=True)
class HttpResult:
    ok: bool
    http_status: int | None
    payload: Any = None
    error: str | None = None


def utc_now() -> str:
    return datetime.now(timezone.utc).replace(microsecond=0).isoformat().replace("+00:00", "Z")


def _read_json(path: Path) -> dict[str, Any]:
    try:
        payload = json.loads(path.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError):
        return {}
    return payload if isinstance(payload, dict) else {}


def _write_json(path: Path, payload: dict[str, Any], *, secret: bool = False) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(payload, indent=2, sort_keys=True) + "\n", encoding="utf-8")
    if secret:
        os.chmod(path, 0o600)


def _default_public_base_url() -> str:
    status = _read_json(RUNTIME_STATUS_FILE)
    value = status.get("public_base_url")
    if isinstance(value, str) and value.startswith("https://"):
        return value.rstrip("/")
    return DEFAULT_PUBLIC_BASE_URL


def default_manifest_url() -> str:
    return f"{_default_public_base_url()}/.well-known/x402.json"


def load_or_create_identity(path: Path) -> dict[str, Any]:
    existing = _read_json(path)
    private_key = existing.get("private_key")
    address = existing.get("address")
    if isinstance(private_key, str) and private_key.startswith("0x"):
        account = Account.from_key(private_key)
        if not address or str(address).lower() != account.address.lower():
            existing["address"] = account.address
            _write_json(path, existing, secret=True)
        else:
            try:
                os.chmod(path, 0o600)
            except OSError:
                pass
        return existing

    account = Account.create()
    identity = {
        "schema": "x0tta6bl4.gate402_identity.v1",
        "created_at_utc": utc_now(),
        "address": account.address,
        "private_key": account.key.hex() if account.key.hex().startswith("0x") else "0x" + account.key.hex(),
        "purpose": "Gate402 dashboard message signing only; no funds required.",
    }
    _write_json(path, identity, secret=True)
    return identity


def sign_text(private_key: str, text: str) -> str:
    if not text:
        raise ValueError("cannot sign empty text")
    signed = Account.sign_message(encode_defunct(text=text), private_key)
    signature = signed.signature.hex()
    return signature if signature.startswith("0x") else "0x" + signature


def request_json(
    session: requests.Session,
    method: str,
    url: str,
    *,
    token: str | None = None,
    payload: dict[str, Any] | None = None,
    timeout_seconds: float = 20.0,
) -> HttpResult:
    headers = {"accept": "application/json"}
    if payload is not None:
        headers["content-type"] = "application/json"
    if token:
        headers["authorization"] = f"Bearer {token}"
    try:
        response = session.request(
            method,
            url,
            headers=headers,
            json=payload,
            timeout=timeout_seconds,
        )
    except requests.RequestException as exc:
        return HttpResult(ok=False, http_status=None, error=f"{type(exc).__name__}:{exc}")

    try:
        body: Any = response.json()
    except ValueError:
        body = {"text": response.text[:2000]}
    return HttpResult(ok=200 <= response.status_code < 300, http_status=response.status_code, payload=body)


def redact(value: Any) -> Any:
    if isinstance(value, dict):
        return {
            key: ("<redacted>" if key.lower() in REDACTED_KEYS else redact(item))
            for key, item in value.items()
        }
    if isinstance(value, list):
        return [redact(item) for item in value]
    return value


def step_summary(result: HttpResult) -> dict[str, Any]:
    return {
        "ok": result.ok,
        "http_status": result.http_status,
        "response": redact(result.payload),
        "error": result.error,
    }


def authenticate(session: requests.Session, api_base: str, address: str, private_key: str) -> tuple[str | None, dict[str, Any]]:
    verify = request_json(
        session,
        "POST",
        f"{api_base.rstrip('/')}/auth/verify",
        payload={"wallet": address, "walletType": "evm"},
    )
    if not verify.ok or not isinstance(verify.payload, dict):
        return None, {"verify": step_summary(verify)}

    challenge = verify.payload.get("challenge")
    if not isinstance(challenge, str):
        return None, {
            "verify": step_summary(verify),
            "login": {
                "ok": False,
                "http_status": None,
                "response": None,
                "error": "missing_challenge",
            },
        }

    signature = sign_text(private_key, challenge)
    login = request_json(
        session,
        "POST",
        f"{api_base.rstrip('/')}/auth/login",
        payload={
            "wallet": address,
            "walletType": "evm",
            "challenge": challenge,
            "signature": signature,
        },
    )
    token = login.payload.get("token") if login.ok and isinstance(login.payload, dict) else None
    return (token if isinstance(token, str) else None), {
        "verify": step_summary(verify),
        "login": step_summary(login),
    }


def build_import_payload(
    *,
    manifest_url: str,
    name: str,
    owner_wallet: str,
    challenge_id: str,
    signature: str,
) -> dict[str, Any]:
    proof = {"challengeId": challenge_id, "signature": signature}
    return {
        "importUrl": manifest_url,
        "url": manifest_url,
        "name": name,
        "walletAddress": owner_wallet,
        "chain": "Base",
        "pricePerCall": 0,
        "importProof": proof,
    }


def import_service(
    session: requests.Session,
    *,
    api_base: str,
    token: str,
    manifest_url: str,
    name: str,
    owner_wallet: str,
    private_key: str,
) -> dict[str, Any]:
    steps: dict[str, Any] = {}
    challenge = request_json(
        session,
        "POST",
        f"{api_base.rstrip('/')}/dashboard/services/ownership-challenge",
        token=token,
        payload={"importUrl": manifest_url},
    )
    steps["ownership_challenge"] = step_summary(challenge)
    if not challenge.ok or not isinstance(challenge.payload, dict):
        return steps

    challenge_id = challenge.payload.get("challengeId")
    message = challenge.payload.get("message")
    if not isinstance(challenge_id, str) or not isinstance(message, str):
        steps["submit"] = {
            "ok": False,
            "http_status": None,
            "response": None,
            "error": "missing_challenge_id_or_message",
        }
        return steps

    signature = sign_text(private_key, message)
    payload = build_import_payload(
        manifest_url=manifest_url,
        name=name,
        owner_wallet=owner_wallet,
        challenge_id=challenge_id,
        signature=signature,
    )
    submit = request_json(
        session,
        "POST",
        f"{api_base.rstrip('/')}/dashboard/services",
        token=token,
        payload=payload,
    )
    steps["submit"] = step_summary(submit)
    if submit.ok:
        return steps

    fallback_payload = dict(payload)
    fallback_payload["ownershipProof"] = fallback_payload["importProof"]
    fallback = request_json(
        session,
        "POST",
        f"{api_base.rstrip('/')}/dashboard/services",
        token=token,
        payload=fallback_payload,
    )
    steps["submit_with_ownership_proof"] = step_summary(fallback)
    return steps


def discover_service(session: requests.Session, api_base: str, query: str) -> HttpResult:
    return request_json(
        session,
        "GET",
        f"{api_base.rstrip('/')}/discover?query={requests.utils.quote(query)}&chain=base",
    )


def extract_service_id(steps: dict[str, Any]) -> str | None:
    for key in ("submit", "submit_with_ownership_proof"):
        item = steps.get("import", {}).get(key)
        if not isinstance(item, dict) or not item.get("ok"):
            continue
        response = item.get("response")
        if not isinstance(response, dict):
            continue
        service = response.get("service")
        if isinstance(service, dict) and isinstance(service.get("id"), str):
            return service["id"]
        if isinstance(response.get("serviceId"), str):
            return response["serviceId"]
    skipped_id = steps.get("import", {}).get("service_id")
    return skipped_id if isinstance(skipped_id, str) else None


def previous_service_id(status_file: Path) -> str | None:
    status = _read_json(status_file)
    steps = status.get("steps")
    if not isinstance(steps, dict):
        return None
    return extract_service_id(steps)


def probe_service(session: requests.Session, api_base: str, service_id: str | None) -> HttpResult | None:
    if not service_id:
        return None
    return request_json(session, "GET", f"{api_base.rstrip('/')}/services/{service_id}")


def summarize_status(
    steps: dict[str, Any],
    discover: HttpResult,
    service_probe: HttpResult | None,
    name: str,
    manifest_url: str,
) -> dict[str, Any]:
    submit_steps = [
        steps.get("import", {}).get("submit"),
        steps.get("import", {}).get("submit_with_ownership_proof"),
    ]
    submitted = any(isinstance(item, dict) and item.get("ok") for item in submit_steps)
    service_id = extract_service_id(steps)
    direct_service_visible = bool(service_probe and service_probe.ok)
    discover_payload = discover.payload if isinstance(discover.payload, dict) else {}
    results = discover_payload.get("results") if isinstance(discover_payload, dict) else []
    visible = False
    if isinstance(results, list):
        for item in results:
            if not isinstance(item, dict):
                continue
            haystack = " ".join(str(item.get(key, "")) for key in ("name", "url", "manifest_url", "description"))
            if "x0tta6bl4" in haystack.lower() or manifest_url in haystack:
                visible = True
                break
    known_registered = bool(submitted or direct_service_visible or service_id)
    if known_registered and visible:
        next_action = "keep_catalog_watch_running"
    elif direct_service_visible:
        next_action = "service_active_wait_for_gate402_search_indexing"
    elif submitted:
        next_action = "wait_for_gate402_indexing_then_probe_discovery"
    else:
        next_action = "inspect_gate402_submit_error"
    return {
        "submitted": submitted,
        "known_registered": known_registered,
        "service_id": service_id,
        "direct_service_visible": direct_service_visible,
        "discover_visible": visible,
        "discover_http_status": discover.http_status,
        "discover_results_total": len(results) if isinstance(results, list) else None,
        "service_name": name,
        "next_action": next_action,
    }


def run(args: argparse.Namespace) -> dict[str, Any]:
    identity = load_or_create_identity(args.identity_file)
    address = str(identity["address"])
    private_key = str(identity["private_key"])
    session = requests.Session()
    token, auth_steps = authenticate(session, args.api_base, address, private_key)
    steps: dict[str, Any] = {"auth": auth_steps}
    existing_service_id = previous_service_id(args.status_file)
    if existing_service_id and not args.force_submit:
        steps["import"] = {
            "skipped": True,
            "reason": "existing_service_id",
            "service_id": existing_service_id,
        }
    elif token and not args.skip_submit:
        steps["import"] = import_service(
            session,
            api_base=args.api_base,
            token=token,
            manifest_url=args.manifest_url,
            name=args.name,
            owner_wallet=address,
            private_key=private_key,
        )
    elif args.skip_submit:
        steps["import"] = {"skipped": True}
    else:
        steps["import"] = {"error": "auth_failed"}

    discover = discover_service(session, args.api_base, "x0tta6bl4")
    service_probe = probe_service(session, args.api_base, extract_service_id(steps))
    discover_status = step_summary(discover)
    _write_json(args.discover_file, discover_status)

    status = {
        "schema": "x0tta6bl4.gate402_import_status.v1",
        "checked_at_utc": utc_now(),
        "claim_boundary": CLAIM_BOUNDARY,
        "api_base": args.api_base,
        "manifest_url": args.manifest_url,
        "identity_address": address,
        "steps": steps,
        "discover": discover_status,
        "direct_service": step_summary(service_probe) if service_probe else None,
        "summary": summarize_status(steps, discover, service_probe, args.name, args.manifest_url),
    }
    _write_json(args.status_file, status)
    return status


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--api-base", default=DEFAULT_API_BASE)
    parser.add_argument("--manifest-url", default=default_manifest_url())
    parser.add_argument("--name", default=DEFAULT_NAME)
    parser.add_argument("--identity-file", type=Path, default=DEFAULT_IDENTITY_FILE)
    parser.add_argument("--status-file", type=Path, default=DEFAULT_STATUS_FILE)
    parser.add_argument("--discover-file", type=Path, default=DEFAULT_DISCOVER_FILE)
    parser.add_argument("--skip-submit", action="store_true")
    parser.add_argument("--force-submit", action="store_true")
    return parser.parse_args()


def main() -> int:
    status = run(parse_args())
    summary = status["summary"]
    print(
        json.dumps(
            {
                "submitted": summary["submitted"],
                "known_registered": summary["known_registered"],
                "service_id": summary["service_id"],
                "direct_service_visible": summary["direct_service_visible"],
                "discover_visible": summary["discover_visible"],
                "next_action": summary["next_action"],
                "status_file": str(DEFAULT_STATUS_FILE),
            },
            indent=2,
            sort_keys=True,
        )
    )
    return 0 if summary["known_registered"] else 2


if __name__ == "__main__":
    raise SystemExit(main())
