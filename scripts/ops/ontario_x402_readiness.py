#!/usr/bin/env python3
"""Run free Ontario Protocol checks for one x0tta6bl4 x402 service."""

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
DEFAULT_STATUS_FILE = ARTIFACT_DIR / "ontario_x402_readiness_status.json"
DEFAULT_BASE_URL = "https://ontarioprotocol.com"
DEFAULT_PUBLIC_BASE_URL = "https://saccharolytic-uncatechized-tanika.ngrok-free.dev"
CLAIM_BOUNDARY = (
    "This status proves only free Ontario Protocol validation/readiness checks. "
    "It does not prove paid listing submission, buyer calls, settlement, or funds received."
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


def post_json(url: str, payload: dict[str, Any], *, timeout_seconds: float) -> HttpResult:
    request = urllib.request.Request(
        url,
        data=json.dumps(payload).encode("utf-8"),
        method="POST",
        headers={
            "Accept": "application/json",
            "Content-Type": "application/json",
            "User-Agent": "x0tta6bl4-ontario-readiness/1.0",
        },
    )
    try:
        with urllib.request.urlopen(request, timeout=timeout_seconds) as response:
            raw = response.read(500_000)
            try:
                parsed: Any = json.loads(raw.decode("utf-8"))
            except json.JSONDecodeError:
                parsed = {"text": raw.decode("utf-8", errors="replace")[:5000]}
            return HttpResult(ok=200 <= response.status < 300, http_status=response.status, payload=parsed)
    except urllib.error.HTTPError as exc:
        raw = exc.read(100_000)
        try:
            parsed = json.loads(raw.decode("utf-8"))
        except json.JSONDecodeError:
            parsed = {"text": raw.decode("utf-8", errors="replace")[:5000]}
        return HttpResult(ok=False, http_status=exc.code, payload=parsed, error=f"http_error:{exc.code}")
    except Exception as exc:  # pragma: no cover - socket errors differ by OS.
        return HttpResult(ok=False, http_status=None, error=f"{type(exc).__name__}:{exc}")


def build_listing_payload(*, public_base_url: str, service_path: str) -> dict[str, Any]:
    endpoint = f"{public_base_url.rstrip('/')}{service_path}"
    return {
        "name": "x0tta6bl4 API Docs Generator",
        "description": (
            "Turns REST endpoint specs into clean Markdown documentation with cURL, "
            "Python, and JavaScript examples. Public inputs only. Paid via x402 on Base USDC."
        ),
        "endpoint": endpoint,
        "method": "POST",
        "price_atomic": 30000,
        "price_usdc": "0.03",
        "category": "tools",
        "owner_url": f"{public_base_url.rstrip('/')}/.well-known/x402-discovery",
        "owner_contact": "not-configured",
    }


def summarize_readiness(payload: Any) -> dict[str, Any]:
    if not isinstance(payload, dict):
        return {"grade": None, "score": None, "report_url": None, "warnings_total": 0}
    return {
        "grade": payload.get("grade") or payload.get("verification_status"),
        "score": payload.get("readiness_score") or payload.get("score"),
        "report_id": payload.get("report_id"),
        "report_url": payload.get("report_url"),
        "warnings_total": len(payload.get("warnings") or []) if isinstance(payload.get("warnings"), list) else 0,
    }


def result_summary(result: HttpResult) -> dict[str, Any]:
    return {
        "ok": result.ok,
        "http_status": result.http_status,
        "response": result.payload,
        "error": result.error,
    }


def run(args: argparse.Namespace) -> dict[str, Any]:
    base = args.ontario_base_url.rstrip("/")
    listing_payload = build_listing_payload(
        public_base_url=args.public_base_url,
        service_path=args.service_path,
    )
    validate = post_json(
        f"{base}/api/x402/list-service/validate",
        listing_payload,
        timeout_seconds=args.timeout_seconds,
    )
    verify = post_json(
        f"{base}/api/verify/x402-readiness",
        {"target_url": listing_payload["endpoint"]},
        timeout_seconds=args.verify_timeout_seconds,
    )
    readiness = summarize_readiness(verify.payload)
    if verify.ok and readiness.get("grade") == "ready":
        next_action = "cannot_paid_list_without_0_50_usdc_keep_public_report_and_watch_buyers"
    elif validate.ok and not verify.ok:
        next_action = "retry_readiness_or_inspect_timeout"
    else:
        next_action = "fix_validation_or_readiness_warnings"
    status = {
        "schema": "x0tta6bl4.ontario_x402_readiness_status.v1",
        "checked_at_utc": utc_now(),
        "claim_boundary": CLAIM_BOUNDARY,
        "ontario_base_url": base,
        "listing_fee_usdc": "0.50",
        "listing_payload": listing_payload,
        "validate": result_summary(validate),
        "verify": result_summary(verify),
        "summary": {
            "validation_ok": bool(validate.ok and isinstance(validate.payload, dict) and validate.payload.get("ok") is True),
            "readiness_ok": verify.ok,
            **readiness,
            "next_action": next_action,
        },
    }
    _write_json(args.status_file, status)
    return status


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--ontario-base-url", default=DEFAULT_BASE_URL)
    parser.add_argument("--public-base-url", default=_default_public_base_url())
    parser.add_argument("--service-path", default="/paid/api-docs")
    parser.add_argument("--timeout-seconds", type=float, default=30.0)
    parser.add_argument("--verify-timeout-seconds", type=float, default=90.0)
    parser.add_argument("--status-file", type=Path, default=DEFAULT_STATUS_FILE)
    return parser.parse_args()


def main() -> int:
    status = run(parse_args())
    print(json.dumps(status["summary"], indent=2, sort_keys=True))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
