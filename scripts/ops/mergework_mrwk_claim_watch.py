#!/usr/bin/env python3
"""Watch earned MergeWork MRWK and the remaining GitHub-claim step."""

from __future__ import annotations

import argparse
import json
import time
import urllib.error
import urllib.parse
import urllib.request
from decimal import Decimal, InvalidOperation
from pathlib import Path
from typing import Any


API_BASE = "https://api.mrwk.online"
WEB_BASE = "https://mrwk.online"
DEFAULT_OUTPUT = Path(".tmp/non-bounty/mergework_mrwk_claim_watch_status.json")
GITHUB_LOGIN = "x0tta6bl4-ai"
GITHUB_ACCOUNT = f"github:{GITHUB_LOGIN}"
TARGET_BASE_WALLET = "0x6017613e80d7893EB2aD5c0585b3f1f88CD6e099"
CLAIM_BOUNDARY = (
    "This proves only public MergeWork ledger/account state. MRWK is a native "
    "MergeWork ledger asset, not USDC on Base. It does not prove fiat value, "
    "exchange liquidity, off-ramp availability, or funds received on the target Base wallet."
)


def _utc_now() -> str:
    return time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime())


def _write_json(path: Path, payload: dict[str, Any]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(payload, indent=2, ensure_ascii=False, sort_keys=True) + "\n", encoding="utf-8")


def _http_json(url: str, *, timeout_seconds: float) -> tuple[bool, Any]:
    request = urllib.request.Request(
        url,
        headers={"Accept": "application/json", "User-Agent": "x0tta6bl4-mergework-mrwk-claim-watch/1.0"},
    )
    try:
        with urllib.request.urlopen(request, timeout=timeout_seconds) as response:
            return True, json.loads(response.read().decode("utf-8"))
    except urllib.error.HTTPError as exc:
        body = exc.read().decode("utf-8", errors="replace")
        try:
            parsed: Any = json.loads(body) if body else {}
        except json.JSONDecodeError:
            parsed = {"raw": body[:1000]}
        return False, {"http_status": exc.code, "response": parsed}
    except (urllib.error.URLError, TimeoutError, json.JSONDecodeError) as exc:
        return False, {"error": exc.__class__.__name__, "detail": str(exc)}


def _positive_decimal(value: Any) -> bool:
    try:
        return Decimal(str(value or "0")) > 0
    except (InvalidOperation, ValueError):
        return False


def _as_dict(value: Any) -> dict[str, Any]:
    return value if isinstance(value, dict) else {}


def _as_list(value: Any) -> list[Any]:
    return value if isinstance(value, list) else []


def _summarize(
    *,
    status_payload: dict[str, Any],
    account_payload: dict[str, Any],
    accepted_payload: dict[str, Any],
    auth_payload: dict[str, Any],
    fetch_failures: list[dict[str, Any]],
) -> dict[str, Any]:
    accepted_summary = _as_dict(accepted_payload.get("summary"))
    account_accepted = _as_dict(account_payload.get("accepted_work"))
    accepted_work = [item for item in _as_list(accepted_payload.get("accepted_work")) if isinstance(item, dict)]

    accepted_mrwk = str(account_accepted.get("accepted_mrwk") or accepted_summary.get("accepted_mrwk") or "0")
    accepted_awards = int(account_accepted.get("accepted_awards") or accepted_summary.get("accepted_awards") or 0)
    balance_mrwk = str(account_payload.get("balance_mrwk") or "0")
    pending_summary = _as_dict(account_payload.get("pending_summary"))
    pending_mrwk = str(pending_summary.get("pending_mrwk") or "0")
    transfer_status = str(account_payload.get("transfer_status") or "")

    unsupported_paths = [str(item) for item in _as_list(status_payload.get("unsupported_public_paths"))]
    current_transfer_paths = [str(item) for item in _as_list(status_payload.get("current_transfer_paths"))]
    base_wallet_supported = not any(item.upper() in {"USDC", "FIAT", "BRIDGE", "EXCHANGE", "OFF-RAMP"} for item in unsupported_paths)
    github_claim_supported = any("github:* balance claims" in item for item in current_transfer_paths)

    authenticated = auth_payload.get("authenticated") is True
    authenticated_login = str(auth_payload.get("github_login") or "")
    github_session_ready = authenticated and authenticated_login == GITHUB_LOGIN
    earned_signal = _positive_decimal(accepted_mrwk) or _positive_decimal(balance_mrwk)
    claim_required = _positive_decimal(balance_mrwk) and "claim github balances" in transfer_status.lower()

    if fetch_failures:
        next_action = "inspect_mergework_fetch_failures"
    elif claim_required and not github_session_ready:
        next_action = "open_mrwk_me_sign_in_link_wallet_claim"
    elif claim_required:
        next_action = "submit_signed_github_claim_on_mrwk_me"
    elif earned_signal:
        next_action = "verify_mrwk_wallet_claimed_balance"
    else:
        next_action = "find_new_mergework_bounty_or_paid_task"

    latest_work = accepted_work[:8]
    return {
        "account": GITHUB_ACCOUNT,
        "github_login": GITHUB_LOGIN,
        "target_base_wallet": TARGET_BASE_WALLET,
        "account_exists": bool(account_payload.get("exists")),
        "balance_mrwk": balance_mrwk,
        "accepted_awards": accepted_awards,
        "accepted_mrwk": accepted_mrwk,
        "pending_mrwk": pending_mrwk,
        "earned_signal": earned_signal,
        "claim_required": claim_required,
        "transfer_status": transfer_status,
        "github_claim_supported": github_claim_supported,
        "github_session_ready": github_session_ready,
        "authenticated_login": authenticated_login or None,
        "mrwk_me_url": f"{WEB_BASE}/me",
        "latest_proof_public_url": account_accepted.get("latest_proof_public_url")
        or accepted_summary.get("latest_proof_public_url"),
        "latest_submission_url": account_accepted.get("latest_submission_url") or accepted_summary.get("latest_submission_url"),
        "accepted_work_sample": [
            {
                "amount_mrwk": item.get("amount_mrwk"),
                "submission_url": item.get("submission_url"),
                "proof_public_url": item.get("proof_public_url"),
                "created_at": item.get("created_at"),
            }
            for item in latest_work
        ],
        "unsupported_public_paths": unsupported_paths,
        "base_wallet_supported_by_mergework": base_wallet_supported,
        "earned_mrwk_claim_allowed": earned_signal,
        "funds_received_claim_allowed": False,
        "base_wallet_funds_received_claim_allowed": False,
        "next_action": next_action,
    }


def run(args: argparse.Namespace) -> dict[str, Any]:
    encoded_account = urllib.parse.quote(GITHUB_ACCOUNT, safe=":")
    endpoints = {
        "status": f"{API_BASE}/api/v1/status",
        "account": f"{API_BASE}/api/v1/accounts/{encoded_account}",
        "accepted_work": f"{API_BASE}/api/v1/accounts/{encoded_account}/accepted-work",
        "auth_me": f"{WEB_BASE}/api/v1/auth/me",
    }
    payloads: dict[str, Any] = {}
    fetch_failures: list[dict[str, Any]] = []
    for name, url in endpoints.items():
        ok, payload = _http_json(url, timeout_seconds=args.timeout_seconds)
        payloads[name] = payload
        if not ok:
            fetch_failures.append({"name": name, "url": url, "error": payload})

    summary = _summarize(
        status_payload=_as_dict(payloads.get("status")),
        account_payload=_as_dict(payloads.get("account")),
        accepted_payload=_as_dict(payloads.get("accepted_work")),
        auth_payload=_as_dict(payloads.get("auth_me")),
        fetch_failures=fetch_failures,
    )
    status = {
        "schema": "x0tta6bl4.mergework_mrwk_claim_watch.v1",
        "checked_at_utc": _utc_now(),
        "ok": not fetch_failures,
        "claim_boundary": CLAIM_BOUNDARY,
        "fetch_failures": fetch_failures,
        **summary,
    }
    _write_json(args.output, status)
    return status


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--output", type=Path, default=DEFAULT_OUTPUT)
    parser.add_argument("--timeout-seconds", type=float, default=20.0)
    return parser.parse_args()


def main() -> int:
    status = run(parse_args())
    print(json.dumps(status, indent=2, ensure_ascii=False, sort_keys=True))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
