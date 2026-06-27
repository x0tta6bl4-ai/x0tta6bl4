#!/usr/bin/env python3
"""Submit the public x0tta6bl4 x402 endpoint to 402directory/jaypay."""

from __future__ import annotations

import argparse
import json
import urllib.error
import urllib.parse
import urllib.request
from dataclasses import dataclass
from datetime import datetime, timezone
from pathlib import Path
from typing import Any


ROOT = Path(__file__).resolve().parents[2]
ARTIFACT_DIR = ROOT / ".tmp" / "non-bounty"
RUNTIME_STATUS_FILE = ARTIFACT_DIR / "x402_paid_api_public_runtime_status.json"
DEFAULT_STATUS_FILE = ARTIFACT_DIR / "jaypay_402directory_submit_status.json"
DEFAULT_API_BASE = "https://402directory.com"
DEFAULT_PUBLIC_BASE_URL = "https://saccharolytic-uncatechized-tanika.ngrok-free.dev"
DEFAULT_NAME = "x0tta6bl4 Domain Health Lite"
DEFAULT_SERVICE_PATH = "/paid/domain-health"
DEFAULT_PRICE_USDC = 0.001
DEFAULT_DESCRIPTION = (
    "Tiny x402 paid API for agents. It checks a public domain or URL for DNS, "
    "HTTP, redirect, TLS, and private-network refusal signals. Public inputs only. "
    "Paid through x402 on Base USDC."
)
DEFAULT_TAGS = "domain-health,security,x402,agent-tool"
CLAIM_BOUNDARY = (
    "This status proves only 402directory API reachability, submission response, "
    "and public directory search. It does not prove review approval, buyer demand, "
    "paid calls, settlement, or received funds."
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


def request_json(
    method: str,
    url: str,
    *,
    payload: dict[str, Any] | None = None,
    timeout_seconds: float = 20.0,
) -> HttpResult:
    data = None
    headers = {
        "accept": "application/json",
        "user-agent": "x0tta6bl4-402directory-submit/1.0",
    }
    if payload is not None:
        data = json.dumps(payload).encode("utf-8")
        headers["content-type"] = "application/json"
    request = urllib.request.Request(url, data=data, method=method, headers=headers)
    try:
        with urllib.request.urlopen(request, timeout=timeout_seconds) as response:
            raw = response.read(2_000_000)
            body = parse_json_or_text(raw)
            return HttpResult(ok=200 <= response.status < 300, http_status=response.status, payload=body)
    except urllib.error.HTTPError as exc:
        raw = exc.read(500_000)
        body = parse_json_or_text(raw)
        return HttpResult(ok=False, http_status=exc.code, payload=body, error=f"http_error:{exc.code}")
    except Exception as exc:  # pragma: no cover - socket errors differ by OS.
        return HttpResult(ok=False, http_status=None, error=f"{type(exc).__name__}:{exc}")


def parse_json_or_text(raw: bytes) -> Any:
    text = raw.decode("utf-8", "replace")
    try:
        return json.loads(text)
    except json.JSONDecodeError:
        return {"text": text[:2000]}


def step_summary(result: HttpResult | None) -> dict[str, Any] | None:
    if result is None:
        return None
    return {
        "ok": result.ok,
        "http_status": result.http_status,
        "response": result.payload,
        "error": result.error,
    }


def build_submission_payload(
    *,
    name: str,
    description: str,
    endpoint: str,
    method: str,
    price_usdc: float,
    chain: str,
    protocol: str,
    category: str,
    tags: str,
    example: str,
    submitter_email: str = "",
) -> dict[str, Any]:
    return {
        "name": name.strip(),
        "description": description.strip(),
        "endpoint": endpoint.strip(),
        "method": method.strip().upper(),
        "price_usdc": float(price_usdc),
        "chain": chain.strip().lower(),
        "protocol": protocol.strip().lower(),
        "category": category.strip().lower(),
        "tags": tags.strip(),
        "example": example.strip(),
        "submitter_email": submitter_email.strip(),
    }


def missing_payload_fields(payload: dict[str, Any]) -> list[str]:
    required_text = ("name", "description", "endpoint", "method", "chain", "protocol", "category")
    missing = [key for key in required_text if not str(payload.get(key) or "").strip()]
    try:
        price = float(payload.get("price_usdc"))
    except (TypeError, ValueError):
        missing.append("price_usdc")
    else:
        if price <= 0:
            missing.append("price_usdc")
    return missing


def submit_service(api_base: str, payload: dict[str, Any], *, timeout_seconds: float) -> HttpResult:
    return request_json(
        "POST",
        f"{api_base.rstrip('/')}/api/submissions",
        payload=payload,
        timeout_seconds=timeout_seconds,
    )


def fetch_directory(api_base: str, *, timeout_seconds: float) -> HttpResult:
    return request_json(
        "GET",
        f"{api_base.rstrip('/')}/api/directory",
        timeout_seconds=timeout_seconds,
    )


def directory_entries(payload: Any) -> list[Any]:
    if isinstance(payload, dict) and isinstance(payload.get("entries"), list):
        return payload["entries"]
    if isinstance(payload, list):
        return payload
    return []


def directory_contains(entries: list[Any], *, name: str, endpoint: str) -> bool:
    text = json.dumps(entries, ensure_ascii=False).lower()
    return name.lower() in text or endpoint.lower() in text


def summarize(
    *,
    skipped_reason: str | None,
    submit: HttpResult | None,
    directory: HttpResult,
    payload: dict[str, Any],
) -> dict[str, Any]:
    entries = directory_entries(directory.payload)
    visible = directory_contains(entries, name=payload["name"], endpoint=payload["endpoint"])
    submitted = bool(submit and submit.ok)
    submission_known = bool(submitted or visible or skipped_reason == "already_submitted_or_visible")
    if visible:
        next_action = "keep_directory_watch_running"
    elif submitted:
        next_action = "wait_for_402directory_review_and_indexing"
    elif skipped_reason == "already_submitted_or_visible":
        next_action = "wait_for_402directory_review_and_indexing"
    elif skipped_reason:
        next_action = "fix_local_payload_then_rerun"
    else:
        next_action = "inspect_402directory_submit_error"
    return {
        "submitted": submitted,
        "submission_known": submission_known,
        "skipped_reason": skipped_reason,
        "directory_visible": visible,
        "directory_http_status": directory.http_status,
        "service_url": payload["endpoint"],
        "price_usdc": payload["price_usdc"],
        "next_action": next_action,
    }


def run(args: argparse.Namespace) -> dict[str, Any]:
    public_base_url = args.public_base_url.rstrip("/")
    endpoint = args.endpoint or f"{public_base_url}{args.service_path}"
    example = args.example or endpoint
    existing_status = _read_json(args.status_file)
    existing_summary = existing_status.get("summary") if isinstance(existing_status.get("summary"), dict) else {}
    payload = build_submission_payload(
        name=args.name,
        description=args.description,
        endpoint=endpoint,
        method=args.method,
        price_usdc=args.price_usdc,
        chain=args.chain,
        protocol=args.protocol,
        category=args.category,
        tags=args.tags,
        example=example,
        submitter_email=args.submitter_email,
    )
    missing = missing_payload_fields(payload)
    skipped_reason = f"missing_fields:{','.join(missing)}" if missing else None
    submit = None
    if not skipped_reason and not args.skip_submit:
        if not args.force_submit and (
            existing_summary.get("submitted") is True
            or existing_summary.get("submission_known") is True
            or existing_summary.get("directory_visible") is True
        ):
            skipped_reason = "already_submitted_or_visible"
        else:
            submit = submit_service(args.api_base, payload, timeout_seconds=args.timeout_seconds)
    elif args.skip_submit:
        skipped_reason = "skip_submit"

    directory = fetch_directory(args.api_base, timeout_seconds=args.timeout_seconds)
    status = {
        "schema": "x0tta6bl4.jaypay_402directory_submit_status.v1",
        "checked_at_utc": utc_now(),
        "claim_boundary": CLAIM_BOUNDARY,
        "api_base": args.api_base,
        "public_base_url": public_base_url,
        "payload": payload,
        "submit": step_summary(submit),
        "directory": step_summary(directory),
        "summary": summarize(
            skipped_reason=skipped_reason,
            submit=submit,
            directory=directory,
            payload=payload,
        ),
    }
    _write_json(args.status_file, status)
    return status


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--api-base", default=DEFAULT_API_BASE)
    parser.add_argument("--public-base-url", default=_default_public_base_url())
    parser.add_argument("--endpoint")
    parser.add_argument("--service-path", default=DEFAULT_SERVICE_PATH)
    parser.add_argument("--name", default=DEFAULT_NAME)
    parser.add_argument("--description", default=DEFAULT_DESCRIPTION)
    parser.add_argument("--method", default="POST")
    parser.add_argument("--price-usdc", type=float, default=DEFAULT_PRICE_USDC)
    parser.add_argument("--chain", default="base")
    parser.add_argument("--protocol", default="x402")
    parser.add_argument("--category", default="security")
    parser.add_argument("--tags", default=DEFAULT_TAGS)
    parser.add_argument("--example", default="")
    parser.add_argument("--submitter-email", default="")
    parser.add_argument("--status-file", type=Path, default=DEFAULT_STATUS_FILE)
    parser.add_argument("--timeout-seconds", type=float, default=20.0)
    parser.add_argument("--skip-submit", action="store_true")
    parser.add_argument("--force-submit", action="store_true")
    return parser.parse_args()


def main() -> int:
    status = run(parse_args())
    print(json.dumps(status["summary"], indent=2, sort_keys=True))
    summary = status["summary"]
    if (
        summary["submitted"]
        or summary.get("submission_known")
        or summary["directory_visible"]
        or summary.get("skipped_reason") == "already_submitted_or_visible"
    ):
        return 0
    return 2


if __name__ == "__main__":
    raise SystemExit(main())
