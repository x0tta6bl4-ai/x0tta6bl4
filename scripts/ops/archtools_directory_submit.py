#!/usr/bin/env python3
"""Submit the public x0tta6bl4 x402 endpoint to Arch Tools directory.

The script does not invent contact data. If no contact email is configured
locally, it writes a clear status artifact and exits without submitting.
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


ROOT = Path(__file__).resolve().parents[2]
ARTIFACT_DIR = ROOT / ".tmp" / "non-bounty"
RUNTIME_STATUS_FILE = ARTIFACT_DIR / "x402_paid_api_public_runtime_status.json"
DEFAULT_STATUS_FILE = ARTIFACT_DIR / "archtools_submit_status.json"
DEFAULT_API_BASE = "https://archtools.dev"
DEFAULT_PUBLIC_BASE_URL = "https://saccharolytic-uncatechized-tanika.ngrok-free.dev"
DEFAULT_NAME = "x0tta6bl4 Domain Health Lite"
DEFAULT_SERVICE_PATH = "/paid/domain-health"
DEFAULT_DESCRIPTION = (
    "Tiny x402 paid API for agents. It checks public domains and URLs for DNS, "
    "HTTP, redirects, TLS expiry, and private-network refusal signals. Public "
    "inputs only. Pays to x0tta6bl4 wallet on Base USDC."
)
CLAIM_BOUNDARY = (
    "This status proves only local payload preparation, Arch Tools API reachability, "
    "and optional directory submission. It does not prove review approval, buyer "
    "traffic, paid calls, settlement, or received funds."
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


def contact_email_from_env() -> str | None:
    for name in ("ARCHTOOLS_CONTACT_EMAIL", "X0T_CONTACT_EMAIL"):
        value = os.getenv(name, "").strip()
        if value:
            return value
    return None


def redact_email(email: str | None) -> str | None:
    if not email or "@" not in email:
        return None
    local, domain = email.split("@", 1)
    if not local:
        return f"*@{domain}"
    return f"{local[0]}***@{domain}"


def request_json(
    session: requests.Session,
    method: str,
    url: str,
    *,
    payload: dict[str, Any] | None = None,
    timeout_seconds: float = 20.0,
) -> HttpResult:
    headers = {"accept": "application/json"}
    if payload is not None:
        headers["content-type"] = "application/json"
    try:
        response = session.request(method, url, headers=headers, json=payload, timeout=timeout_seconds)
    except requests.RequestException as exc:
        return HttpResult(ok=False, http_status=None, error=f"{type(exc).__name__}:{exc}")

    try:
        body: Any = response.json()
    except ValueError:
        body = {"text": response.text[:2000]}
    return HttpResult(ok=200 <= response.status_code < 300, http_status=response.status_code, payload=body)


def step_summary(result: HttpResult) -> dict[str, Any]:
    return {
        "ok": result.ok,
        "http_status": result.http_status,
        "response": result.payload,
        "error": result.error,
    }


def build_submission_payload(
    *,
    name: str,
    service_url: str,
    description: str,
    contact_email: str,
) -> dict[str, Any]:
    return {
        "name": name.strip(),
        "url": service_url.strip(),
        "description": description.strip(),
        "contact_email": contact_email.strip(),
    }


def missing_payload_fields(payload: dict[str, Any]) -> list[str]:
    required = ("name", "url", "description", "contact_email")
    return [key for key in required if not str(payload.get(key) or "").strip()]


def submit_service(session: requests.Session, api_base: str, payload: dict[str, Any]) -> HttpResult:
    return request_json(
        session,
        "POST",
        f"{api_base.rstrip('/')}/api/v1/x402/directory/submit",
        payload=payload,
    )


def search_service(session: requests.Session, api_base: str, query: str) -> HttpResult:
    return request_json(
        session,
        "GET",
        f"{api_base.rstrip('/')}/api/v1/x402/directory/search?q={requests.utils.quote(query)}",
    )


def summarize(
    *,
    skipped_reason: str | None,
    submit: HttpResult | None,
    search: HttpResult,
    payload: dict[str, Any] | None,
) -> dict[str, Any]:
    response = submit.payload if submit else {}
    response_ok = bool(isinstance(response, dict) and response.get("ok"))
    submitted = bool(submit and submit.ok and response_ok)
    search_payload = search.payload if isinstance(search.payload, dict) else {}
    services = search_payload.get("services")
    visible = False
    if isinstance(services, list):
        visible = "x0tta6bl4" in json.dumps(services, ensure_ascii=False).lower()
    if visible:
        next_action = "keep_directory_watch_running"
    elif submitted:
        next_action = "wait_for_archtools_review_and_indexing"
    elif skipped_reason == "missing_contact_email":
        next_action = "set_ARCHTOOLS_CONTACT_EMAIL_locally_then_rerun"
    else:
        next_action = "inspect_archtools_submit_error"
    return {
        "submitted": submitted,
        "skipped_reason": skipped_reason,
        "directory_visible": visible,
        "search_http_status": search.http_status,
        "service_url": payload.get("url") if payload else None,
        "contact_email_present": bool(payload and payload.get("contact_email")),
        "contact_email_redacted": redact_email(str(payload.get("contact_email"))) if payload else None,
        "next_action": next_action,
    }


def run(args: argparse.Namespace) -> dict[str, Any]:
    public_base_url = args.public_base_url.rstrip("/")
    service_url = args.service_url or f"{public_base_url}{args.service_path}"
    contact_email = args.contact_email or contact_email_from_env()
    payload = None
    submit = None
    skipped_reason = None
    session = requests.Session()
    if contact_email:
        payload = build_submission_payload(
            name=args.name,
            service_url=service_url,
            description=args.description,
            contact_email=contact_email,
        )
        missing = missing_payload_fields(payload)
        if missing:
            skipped_reason = f"missing_fields:{','.join(missing)}"
        elif not args.skip_submit:
            submit = submit_service(session, args.api_base, payload)
        else:
            skipped_reason = "skip_submit"
    else:
        skipped_reason = "missing_contact_email"

    search = search_service(session, args.api_base, "x0tta6bl4")
    status = {
        "schema": "x0tta6bl4.archtools_submit_status.v1",
        "checked_at_utc": utc_now(),
        "claim_boundary": CLAIM_BOUNDARY,
        "api_base": args.api_base,
        "public_base_url": public_base_url,
        "payload": {
            **{key: value for key, value in (payload or {}).items() if key != "contact_email"},
            "contact_email_present": bool(contact_email),
            "contact_email_redacted": redact_email(contact_email),
        },
        "submit": step_summary(submit) if submit else None,
        "search": step_summary(search),
        "summary": summarize(
            skipped_reason=skipped_reason,
            submit=submit,
            search=search,
            payload=payload,
        ),
    }
    _write_json(args.status_file, status)
    return status


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--api-base", default=DEFAULT_API_BASE)
    parser.add_argument("--public-base-url", default=_default_public_base_url())
    parser.add_argument("--service-url")
    parser.add_argument("--service-path", default=DEFAULT_SERVICE_PATH)
    parser.add_argument("--name", default=DEFAULT_NAME)
    parser.add_argument("--description", default=DEFAULT_DESCRIPTION)
    parser.add_argument("--contact-email")
    parser.add_argument("--status-file", type=Path, default=DEFAULT_STATUS_FILE)
    parser.add_argument("--skip-submit", action="store_true")
    return parser.parse_args()


def main() -> int:
    status = run(parse_args())
    print(json.dumps(status["summary"], indent=2, sort_keys=True))
    summary = status["summary"]
    if summary["submitted"] or summary["skipped_reason"] == "missing_contact_email":
        return 0
    return 2


if __name__ == "__main__":
    raise SystemExit(main())
