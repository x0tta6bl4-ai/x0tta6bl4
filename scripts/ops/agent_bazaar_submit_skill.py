#!/usr/bin/env python3
"""Submit one x0tta6bl4 x402 skill to Agent Bazaar.

This script uses only public service data. It does not read private keys,
wallet secrets, cookies, or browser sessions.
"""

from __future__ import annotations

import argparse
import json
import sys
import urllib.error
import urllib.request
from dataclasses import dataclass
from datetime import datetime, timezone
from pathlib import Path
from typing import Any


ROOT = Path(__file__).resolve().parents[2]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

ARTIFACT_DIR = ROOT / ".tmp" / "non-bounty"
RUNTIME_STATUS_FILE = ARTIFACT_DIR / "x402_paid_api_public_runtime_status.json"
DEFAULT_STATUS_FILE = ARTIFACT_DIR / "agent_bazaar_skill_submit_status.json"
DEFAULT_API_BASE = "https://agent-bazaar-production-e82a.up.railway.app/api"
DEFAULT_PUBLIC_BASE_URL = "https://saccharolytic-uncatechized-tanika.ngrok-free.dev"
CLAIM_BOUNDARY = (
    "This status proves only payload preparation and optional submission to the "
    "Agent Bazaar public capability endpoint. It does not prove marketplace "
    "review approval, buyer calls, settlement, or funds received."
)


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


def _write_json(path: Path, payload: dict[str, Any]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(payload, indent=2, sort_keys=True) + "\n", encoding="utf-8")


def _default_public_base_url() -> str:
    status = _read_json(RUNTIME_STATUS_FILE)
    value = status.get("public_base_url")
    if isinstance(value, str) and value.startswith("https://"):
        return value.rstrip("/")
    return DEFAULT_PUBLIC_BASE_URL


def build_payload(*, public_base_url: str, service_path: str, price_usd: float) -> dict[str, Any]:
    base = public_base_url.rstrip("/")
    return {
        "name": "x0tta6bl4 API Docs Generator",
        "type": "api",
        "category": "code-generation",
        "description": (
            "Turns REST endpoint specs into clean Markdown documentation with cURL, "
            "Python, and JavaScript examples. Public inputs only. Paid via x402 on Base USDC."
        ),
        "price_per_call": price_usd,
        "x402_endpoint": f"{base}{service_path}",
    }


def missing_payload_fields(payload: dict[str, Any]) -> list[str]:
    required = ("name", "type", "category", "description", "price_per_call", "x402_endpoint")
    missing: list[str] = []
    for key in required:
        value = payload.get(key)
        if value is None or (isinstance(value, str) and not value.strip()):
            missing.append(key)
    if payload.get("price_per_call") in {0, 0.0, "0"}:
        missing.append("price_per_call")
    return missing


def post_json(url: str, payload: dict[str, Any], *, timeout_seconds: float) -> HttpResult:
    body = json.dumps(payload).encode("utf-8")
    request = urllib.request.Request(
        url,
        data=body,
        method="POST",
        headers={
            "Accept": "application/json",
            "Content-Type": "application/json",
            "User-Agent": "x0tta6bl4-agent-bazaar-submit/1.0",
        },
    )
    try:
        with urllib.request.urlopen(request, timeout=timeout_seconds) as response:
            raw = response.read(200_000)
            try:
                parsed: Any = json.loads(raw.decode("utf-8"))
            except json.JSONDecodeError:
                parsed = {"text": raw.decode("utf-8", errors="replace")[:5000]}
            return HttpResult(ok=200 <= response.status < 300, http_status=response.status, payload=parsed)
    except urllib.error.HTTPError as exc:
        raw = exc.read(50_000)
        try:
            parsed = json.loads(raw.decode("utf-8"))
        except json.JSONDecodeError:
            parsed = {"text": raw.decode("utf-8", errors="replace")[:5000]}
        return HttpResult(ok=False, http_status=exc.code, payload=parsed, error=f"http_error:{exc.code}")
    except Exception as exc:  # pragma: no cover - socket errors differ by OS.
        return HttpResult(ok=False, http_status=None, error=f"{type(exc).__name__}:{exc}")


def result_summary(result: HttpResult | None) -> dict[str, Any] | None:
    if result is None:
        return None
    return {
        "ok": result.ok,
        "http_status": result.http_status,
        "response": result.payload,
        "error": result.error,
    }


def run(args: argparse.Namespace) -> dict[str, Any]:
    payload = build_payload(
        public_base_url=args.public_base_url,
        service_path=args.service_path,
        price_usd=args.price_usd,
    )
    missing = missing_payload_fields(payload)
    submit: HttpResult | None = None
    skipped_reason = None
    if missing:
        skipped_reason = "missing_fields:" + ",".join(missing)
    elif args.skip_submit:
        skipped_reason = "skip_submit"
    else:
        submit = post_json(
            f"{args.api_base.rstrip('/')}/capabilities",
            payload,
            timeout_seconds=args.timeout_seconds,
        )

    submitted = bool(submit and submit.ok)
    if submitted:
        next_action = "wait_for_agent_bazaar_review_and_watch_marketplace"
    elif skipped_reason == "skip_submit":
        next_action = "rerun_with_submit_enabled"
    elif skipped_reason:
        next_action = "fix_payload_then_rerun"
    else:
        next_action = "inspect_agent_bazaar_submit_error"

    status = {
        "schema": "x0tta6bl4.agent_bazaar_skill_submit_status.v1",
        "checked_at_utc": utc_now(),
        "claim_boundary": CLAIM_BOUNDARY,
        "api_base": args.api_base.rstrip("/"),
        "payload": payload,
        "submit": result_summary(submit),
        "summary": {
            "submitted": submitted,
            "skipped_reason": skipped_reason,
            "service_url": payload["x402_endpoint"],
            "price_per_call_usd": payload["price_per_call"],
            "next_action": next_action,
        },
    }
    _write_json(args.status_file, status)
    return status


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--api-base", default=DEFAULT_API_BASE)
    parser.add_argument("--public-base-url", default=_default_public_base_url())
    parser.add_argument("--service-path", default="/paid/api-docs")
    parser.add_argument("--price-usd", type=float, default=0.03)
    parser.add_argument("--timeout-seconds", type=float, default=20.0)
    parser.add_argument("--status-file", type=Path, default=DEFAULT_STATUS_FILE)
    parser.add_argument("--skip-submit", action="store_true")
    return parser.parse_args()


def main() -> int:
    status = run(parse_args())
    print(json.dumps(status["summary"], indent=2, sort_keys=True))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
