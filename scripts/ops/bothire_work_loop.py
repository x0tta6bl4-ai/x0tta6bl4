#!/usr/bin/env python3
"""Poll BotHire mailbox jobs and deliver x0tta6bl4 results."""

from __future__ import annotations

import argparse
import json
import sys
import time
import urllib.error
import urllib.request
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

ROOT = Path(__file__).resolve().parents[2]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from src.sales.x402_paid_api import (
    ApiDocsRequest,
    DomainHealthRequest,
    IncomeRouteRequest,
    ListingAuditRequest,
    PaymentRiskRequest,
    RepoTriageRequest,
    UrlSnapshotRequest,
    X402ValidateRequest,
    build_api_docs_package,
    build_domain_health_report,
    build_income_route_report,
    build_listing_audit_report,
    build_payment_risk_report,
    build_repo_triage_report,
    build_url_snapshot_report,
    build_x402_validate_report,
)


API_BASE = "https://www.bothire.io"
DEFAULT_IDENTITY = Path(".tmp/non-bounty/bothire_identity.secret.json")
DEFAULT_OUTPUT = Path(".tmp/non-bounty/bothire_work_status.json")


def _utc_now() -> str:
    return datetime.now(timezone.utc).replace(microsecond=0).isoformat().replace("+00:00", "Z")


def _read_json(path: Path) -> Any:
    return json.loads(path.read_text(encoding="utf-8"))


def _write_json(path: Path, payload: Any) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(payload, indent=2, sort_keys=True) + "\n", encoding="utf-8")


def _http_json(
    method: str,
    path: str,
    *,
    api_key: str,
    payload: dict[str, Any] | None = None,
    timeout_seconds: float = 30.0,
) -> tuple[int, Any]:
    data = None if payload is None else json.dumps(payload).encode("utf-8")
    headers = {
        "Accept": "application/json",
        "Content-Type": "application/json",
        "Authorization": f"Bearer {api_key}",
        "User-Agent": "x0tta6bl4-bothire-work-loop",
    }
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
    except urllib.error.URLError as exc:
        return 0, {
            "error": "external_tls_unreachable",
            "detail": str(exc)[:1200],
            "claim_boundary": (
                "This is an external BotHire reachability failure. It does not prove "
                "missing hires, completed work, settlement, payout, or received funds."
            ),
        }


def _hire_id(hire: dict[str, Any]) -> str:
    return str(hire.get("_id") or hire.get("id") or hire.get("hire_id") or "")


def _message_id(message: dict[str, Any]) -> str:
    return str(message.get("message_id") or message.get("_id") or message.get("id") or "")


def _messages(payload: Any) -> list[dict[str, Any]]:
    if isinstance(payload, dict) and isinstance(payload.get("messages"), list):
        return [item for item in payload["messages"] if isinstance(item, dict)]
    if isinstance(payload, list):
        return [item for item in payload if isinstance(item, dict)]
    return []


def _hires(payload: Any) -> list[dict[str, Any]]:
    if isinstance(payload, dict):
        for key in ("hires", "items", "data"):
            if isinstance(payload.get(key), list):
                return [item for item in payload[key] if isinstance(item, dict)]
    if isinstance(payload, list):
        return [item for item in payload if isinstance(item, dict)]
    return []


def fulfill_payload(payload: Any) -> dict[str, Any]:
    if not isinstance(payload, dict):
        return {
            "schema": "x0tta6bl4.bothire_delivery.v1",
            "status": "rejected",
            "reason": "payload_must_be_json_object",
        }
    try:
        if "endpoints" in payload and "service_name" in payload:
            result = build_api_docs_package(ApiDocsRequest.model_validate(payload))
            tool = "api_docs"
        elif "pay_to" in payload or "amount" in payload or "asset" in payload:
            result = build_payment_risk_report(PaymentRiskRequest.model_validate(payload))
            tool = "payment_risk"
        elif "opportunity_title" in payload or "payout_usdc" in payload or "payment_rail" in payload:
            result = build_income_route_report(IncomeRouteRequest.model_validate(payload))
            tool = "income_route"
        elif "url" in payload and ("expected_network" in payload or "max_amount_micro_usdc" in payload):
            result = build_x402_validate_report(X402ValidateRequest.model_validate(payload))
            tool = "x402_validate"
        elif "url" in payload and ("max_links" in payload or "max_text_chars" in payload):
            result = build_url_snapshot_report(UrlSnapshotRequest.model_validate(payload))
            tool = "url_snapshot"
        elif "target" in payload:
            result = build_domain_health_report(DomainHealthRequest.model_validate(payload))
            tool = "domain_health"
        elif "profile_text" in payload:
            result = build_listing_audit_report(ListingAuditRequest.model_validate(payload))
            tool = "listing_audit"
        elif "files" in payload:
            result = build_repo_triage_report(RepoTriageRequest.model_validate(payload))
            tool = "repo_triage"
        else:
            result = {
                "schema": "x0tta6bl4.unsupported_bothire_payload.v1",
                "status": "unsupported_payload",
                "accepted_shapes": [
                    {"tool": "api_docs", "required_fields": ["service_name", "endpoints"]},
                    {"tool": "payment_risk", "required_fields": ["pay_to", "amount", "network", "asset"]},
                    {"tool": "income_route", "required_fields": ["opportunity_title", "description"]},
                    {"tool": "x402_validate", "required_fields": ["url"]},
                    {"tool": "url_snapshot", "required_fields": ["url"]},
                    {"tool": "domain_health", "required_fields": ["target"]},
                    {"tool": "listing_audit", "required_fields": ["profile_text"]},
                    {"tool": "repo_triage", "required_fields": ["files"]},
                ],
            }
            tool = "unsupported"
        return {
            "schema": "x0tta6bl4.bothire_delivery.v1",
            "status": "ready",
            "tool": tool,
            "result": result,
            "claim_boundary": (
                "This is a generated response to a BotHire mailbox request. It does not "
                "prove customer acceptance, hire completion, escrow release, or received funds."
            ),
        }
    except Exception as exc:
        return {
            "schema": "x0tta6bl4.bothire_delivery.v1",
            "status": "error",
            "error": exc.__class__.__name__,
            "detail": str(exc)[:1000],
        }


def _fetch_active_hires(bot_id: str, api_key: str) -> tuple[int, list[dict[str, Any]], Any]:
    status, payload = _http_json(
        "GET",
        f"/api/bots/{bot_id}/hires?role=provider&status=active",
        api_key=api_key,
    )
    return status, _hires(payload), payload


def _poll_inbox(hire_id: str, api_key: str) -> tuple[int, list[dict[str, Any]], Any]:
    status, payload = _http_json("GET", f"/api/hires/{hire_id}/inbox", api_key=api_key)
    return status, _messages(payload), payload


def _deliver(hire_id: str, message_id: str, api_key: str, payload: dict[str, Any]) -> tuple[int, Any]:
    return _http_json(
        "POST",
        f"/api/hires/{hire_id}/deliver",
        api_key=api_key,
        payload={"message_id": message_id, "payload": payload},
    )


def run_once(
    *,
    identity: dict[str, Any],
    dry_run: bool,
    offline_hires: list[dict[str, Any]] | None = None,
    offline_inboxes: dict[str, Any] | None = None,
) -> dict[str, Any]:
    bot_id = str(identity.get("bot_id") or "")
    api_key = str(identity.get("api_key") or "")
    if not bot_id:
        raise RuntimeError("BotHire identity missing bot_id")
    if not api_key and offline_hires is None:
        raise RuntimeError("BotHire identity missing api_key")

    if offline_hires is None:
        hires_status, hires, raw_hires = _fetch_active_hires(bot_id, api_key)
    else:
        hires_status, hires, raw_hires = 200, offline_hires, {"hires": offline_hires}

    hire_results: list[dict[str, Any]] = []
    deliveries_total = 0
    for hire in hires:
        hire_id = _hire_id(hire)
        if not hire_id:
            hire_results.append({"status": "skipped", "reason": "hire_id_missing", "hire": hire})
            continue
        if offline_inboxes is None:
            inbox_status, messages, raw_inbox = _poll_inbox(hire_id, api_key)
        else:
            raw_inbox = offline_inboxes.get(hire_id, {"messages": []})
            inbox_status, messages = 200, _messages(raw_inbox)
        message_results: list[dict[str, Any]] = []
        for message in messages:
            msg_id = _message_id(message)
            request_payload = message.get("payload")
            response_payload = fulfill_payload(request_payload)
            if dry_run or offline_inboxes is not None:
                delivery_status, delivery_response = 0, {"status": "dry_run"}
            else:
                delivery_status, delivery_response = _deliver(hire_id, msg_id, api_key, response_payload)
            deliveries_total += 1 if delivery_status < 400 else 0
            message_results.append(
                {
                    "message_id": msg_id,
                    "fulfillment_status": response_payload.get("status"),
                    "delivery_http_status": delivery_status,
                    "delivery_response": delivery_response,
                }
            )
        hire_results.append(
            {
                "hire_id": hire_id,
                "inbox_http_status": inbox_status,
                "messages_total": len(messages),
                "messages": message_results,
                "raw_inbox_seen": bool(raw_inbox),
            }
        )

    return {
        "schema": "x0tta6bl4.bothire_work_loop.v1",
        "checked_at_utc": _utc_now(),
        "bot_id": bot_id,
        "hires_http_status": hires_status,
        "active_hires_total": len(hires),
        "deliveries_total": deliveries_total,
        "hires": hire_results,
        "funds_received_claim_allowed": False,
        "claim_boundary": (
            "This proves only BotHire active-hire polling and delivery attempts. It does not "
            "prove hire completion, escrow release, on-chain payout, or received funds."
        ),
        "raw_hires_seen": bool(raw_hires),
    }


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--identity", type=Path, default=DEFAULT_IDENTITY)
    parser.add_argument("--output", type=Path, default=DEFAULT_OUTPUT)
    parser.add_argument("--once", action="store_true")
    parser.add_argument("--interval-seconds", type=float, default=15.0)
    parser.add_argument("--dry-run", action="store_true")
    parser.add_argument("--offline-hires", type=Path)
    parser.add_argument("--offline-inboxes", type=Path)
    return parser.parse_args()


def main() -> int:
    args = parse_args()
    identity = _read_json(args.identity)
    offline_hires = None
    offline_inboxes = None
    if args.offline_hires:
        offline_hires = _hires(_read_json(args.offline_hires))
    if args.offline_inboxes:
        inboxes = _read_json(args.offline_inboxes)
        if not isinstance(inboxes, dict):
            raise RuntimeError("--offline-inboxes must contain a JSON object")
        offline_inboxes = inboxes

    while True:
        status = run_once(
            identity=identity,
            dry_run=args.dry_run,
            offline_hires=offline_hires,
            offline_inboxes=offline_inboxes,
        )
        _write_json(args.output, status)
        print(json.dumps(status, indent=2, sort_keys=True))
        if args.once:
            return 0
        time.sleep(max(5.0, args.interval_seconds))


if __name__ == "__main__":
    raise SystemExit(main())
