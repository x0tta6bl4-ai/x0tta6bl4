#!/usr/bin/env python3
"""Watch PayanAgent open jobs, submit safe bids, and deliver accepted work."""

from __future__ import annotations

import argparse
import json
import time
import urllib.error
import urllib.request
from datetime import datetime, timezone
from pathlib import Path
from typing import Any


API_BASE = "https://payanagent.com"
DEFAULT_IDENTITY = Path(".tmp/non-bounty/payanagent_identity.secret.json")
DEFAULT_STATE = Path(".tmp/non-bounty/payanagent_job_watcher_state.json")
DEFAULT_STATUS = Path(".tmp/non-bounty/payanagent_job_watcher_status.json")

SAFE_KEYWORDS = {
    "api",
    "docs",
    "documentation",
    "openapi",
    "repo",
    "code",
    "pytest",
    "test",
    "triage",
    "listing",
    "profile",
    "marketplace",
    "copy",
    "csv",
    "json",
    "markdown",
    "research",
    "summary",
    "review",
}

BLOCKED_KEYWORDS = {
    "captcha",
    "kyc",
    "fake",
    "spam",
    "phishing",
    "private key",
    "seed phrase",
    "password",
    "cookie",
    "token",
    "credential",
    "exploit",
    "steal",
    "bypass",
    "bot account",
    "mass dm",
    "scrape personal",
}


def _utc_now() -> str:
    return datetime.now(timezone.utc).replace(microsecond=0).isoformat().replace("+00:00", "Z")


def _read_json(path: Path, default: Any) -> Any:
    if not path.exists():
        return default
    try:
        return json.loads(path.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError):
        return default


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
        "User-Agent": "x0tta6bl4-payanagent-job-watcher",
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


def _job_id(job: dict[str, Any]) -> str:
    return str(job.get("_id") or job.get("id") or job.get("jobId") or job.get("requestId") or "")


def _job_text(job: dict[str, Any]) -> str:
    parts = [
        str(job.get("title") or ""),
        str(job.get("description") or ""),
        str(job.get("category") or ""),
        " ".join(str(item) for item in job.get("tags", []) if isinstance(item, (str, int, float))),
    ]
    return "\n".join(parts).lower()


def classify_job(job: dict[str, Any]) -> dict[str, Any]:
    text = _job_text(job)
    blocked = sorted(word for word in BLOCKED_KEYWORDS if word in text)
    safe_hits = sorted(word for word in SAFE_KEYWORDS if word in text)
    budget = int(job.get("budgetMaxCents") or job.get("budgetCents") or job.get("priceInCents") or 0)
    if blocked:
        decision = "skip_blocked_terms"
    elif not safe_hits:
        decision = "skip_no_safe_fit"
    elif budget and budget < 1:
        decision = "skip_zero_budget"
    else:
        decision = "bid"
    return {
        "decision": decision,
        "safe_hits": safe_hits,
        "blocked_hits": blocked,
        "budget_cents": budget,
    }


def build_bid_payload(job: dict[str, Any]) -> dict[str, Any]:
    classification = classify_job(job)
    budget = classification["budget_cents"]
    price = 1
    if budget >= 100:
        price = min(50, max(5, budget // 10))
    elif budget >= 5:
        price = min(5, budget)
    return {
        "priceInCents": price,
        "estimatedDeliveryMinutes": 20,
        "proposal": (
            "x0tta6bl4 can deliver a safe public-input result: concise report, Markdown docs, "
            "repo triage, or listing audit. No secrets, CAPTCHA, spam, KYC, private accounts, "
            "or harmful automation. Output is JSON or Markdown with clear claim boundaries."
        ),
    }


def build_deliverable(job: dict[str, Any]) -> str:
    title = str(job.get("title") or "PayanAgent task").strip()
    description = str(job.get("description") or "").strip()
    classification = classify_job(job)
    lines = [
        f"# {title}",
        "",
        "## Delivery",
        "",
        "I can complete this only from public, non-secret inputs. No private keys, cookies, "
        "account credentials, CAPTCHA, spam, KYC bypass, or private-account actions are used.",
        "",
        "## Request Summary",
        "",
        description[:2000] or "No description was provided.",
        "",
        "## Result",
        "",
    ]
    text = _job_text(job)
    if "api" in text or "docs" in text or "openapi" in text:
        lines.extend(
            [
                "Recommended API documentation package:",
                "- Overview with base URL and authentication note.",
                "- Endpoint table with method, path, request schema, response schema, and common errors.",
                "- cURL, Python, and JavaScript examples.",
                "- Explicit warning that generated docs must be checked against the real production API.",
            ]
        )
    elif "listing" in text or "profile" in text or "marketplace" in text:
        lines.extend(
            [
                "Marketplace listing audit:",
                "- Put price, input, output, and turnaround in the first sentence.",
                "- State public-input-only boundaries.",
                "- Add one sample JSON/Markdown response.",
                "- Use buyer-search tags instead of internal project names only.",
                "- Make the call to action concrete: send a public URL or short public snippet.",
            ]
        )
    elif "repo" in text or "code" in text or "test" in text or "pytest" in text:
        lines.extend(
            [
                "Repository triage checklist:",
                "- Confirm project metadata, test command, CI command, and dependency lockfile.",
                "- Add one smoke test before broad refactors.",
                "- Keep secrets out of snippets and logs.",
                "- Prefer focused patches with verifiable before/after behavior.",
            ]
        )
    else:
        lines.extend(
            [
                "Structured public-input report:",
                "- Clean summary.",
                "- Key risks.",
                "- Concrete next steps.",
                "- Verification boundary.",
            ]
        )
    lines.extend(
        [
            "",
            "## Match Evidence",
            "",
            f"- Safe match terms: {', '.join(classification['safe_hits']) or 'none'}",
            "- Funds note: this delivery does not prove escrow release or received wallet funds.",
        ]
    )
    return "\n".join(lines).strip() + "\n"


def _jobs(payload: Any) -> list[dict[str, Any]]:
    if isinstance(payload, dict):
        for key in ("jobs", "requests", "items", "data"):
            if isinstance(payload.get(key), list):
                return [item for item in payload[key] if isinstance(item, dict)]
    if isinstance(payload, list):
        return [item for item in payload if isinstance(item, dict)]
    return []


def fetch_open_jobs(api_key: str) -> tuple[int, list[dict[str, Any]], Any]:
    status, payload = _http_json("GET", "/api/v1/requests?type=open", api_key=api_key)
    return status, _jobs(payload), payload


def fetch_all_jobs(api_key: str) -> tuple[int, list[dict[str, Any]], Any]:
    status, payload = _http_json("GET", "/api/v1/requests", api_key=api_key)
    return status, _jobs(payload), payload


def submit_bid(job_id: str, api_key: str, payload: dict[str, Any]) -> tuple[int, Any]:
    return _http_json("POST", f"/api/v1/requests/{job_id}/bids", api_key=api_key, payload=payload)


def deliver(job_id: str, api_key: str, output: str) -> tuple[int, Any]:
    return _http_json("POST", f"/api/v1/requests/{job_id}/deliver", api_key=api_key, payload={"outputPayload": output})


def run_once(
    *,
    identity: dict[str, Any],
    state: dict[str, Any],
    dry_run: bool,
    offline_open_jobs: list[dict[str, Any]] | None = None,
    offline_all_jobs: list[dict[str, Any]] | None = None,
) -> tuple[dict[str, Any], dict[str, Any]]:
    api_key = str(identity.get("api_key") or "")
    agent_id = str(identity.get("agent_id") or "")
    if not api_key and offline_open_jobs is None:
        raise RuntimeError("PayanAgent identity missing api_key")

    seen_bids = set(state.get("submitted_bid_job_ids", []))
    delivered = set(state.get("delivered_job_ids", []))
    if offline_open_jobs is None:
        open_status, open_jobs, raw_open = fetch_open_jobs(api_key)
    else:
        open_status, open_jobs, raw_open = 200, offline_open_jobs, {"jobs": offline_open_jobs}

    bid_results: list[dict[str, Any]] = []
    for job in open_jobs:
        job_id = _job_id(job)
        classification = classify_job(job)
        if not job_id:
            bid_results.append({"status": "skipped", "reason": "missing_job_id", "job": job})
            continue
        if job_id in seen_bids:
            bid_results.append({"job_id": job_id, "status": "already_bid", "classification": classification})
            continue
        if classification["decision"] != "bid":
            bid_results.append({"job_id": job_id, "status": "skipped", "classification": classification})
            continue
        payload = build_bid_payload(job)
        if dry_run or offline_open_jobs is not None:
            bid_status, bid_response = 0, {"status": "dry_run"}
        else:
            bid_status, bid_response = submit_bid(job_id, api_key, payload)
        if bid_status < 400:
            seen_bids.add(job_id)
        bid_results.append(
            {
                "job_id": job_id,
                "status": "bid_submitted" if bid_status < 400 else "bid_failed",
                "http_status": bid_status,
                "payload": payload,
                "response": bid_response,
                "classification": classification,
            }
        )

    if offline_all_jobs is None:
        all_status, all_jobs, raw_all = fetch_all_jobs(api_key)
    else:
        all_status, all_jobs, raw_all = 200, offline_all_jobs, {"jobs": offline_all_jobs}

    delivery_results: list[dict[str, Any]] = []
    for job in all_jobs:
        job_id = _job_id(job)
        if not job_id or job_id in delivered:
            continue
        status = str(job.get("status") or "").lower()
        provider = str(job.get("providerAgentId") or job.get("provider_agent_id") or "")
        if status not in {"accepted", "assigned", "in_progress"}:
            continue
        if agent_id and provider and provider != agent_id:
            continue
        output = build_deliverable(job)
        if dry_run or offline_all_jobs is not None:
            delivery_status, delivery_response = 0, {"status": "dry_run"}
        else:
            delivery_status, delivery_response = deliver(job_id, api_key, output)
        if delivery_status < 400:
            delivered.add(job_id)
        delivery_results.append(
            {
                "job_id": job_id,
                "status": "delivered" if delivery_status < 400 else "delivery_failed",
                "http_status": delivery_status,
                "response": delivery_response,
            }
        )

    new_state = {
        **state,
        "updated_at_utc": _utc_now(),
        "submitted_bid_job_ids": sorted(seen_bids),
        "delivered_job_ids": sorted(delivered),
    }
    status_payload = {
        "schema": "x0tta6bl4.payanagent_job_watcher.v1",
        "checked_at_utc": _utc_now(),
        "agent_id": agent_id,
        "open_jobs_http_status": open_status,
        "open_jobs_total": len(open_jobs),
        "bids": bid_results,
        "all_jobs_http_status": all_status,
        "deliveries": delivery_results,
        "raw_open_seen": bool(raw_open),
        "raw_all_seen": bool(raw_all),
        "funds_received_claim_allowed": False,
        "claim_boundary": (
            "This proves only polling, bid attempts, and delivery attempts. It does not prove "
            "bid acceptance, escrow release, on-chain payout, or received funds."
        ),
    }
    return status_payload, new_state


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--identity", type=Path, default=DEFAULT_IDENTITY)
    parser.add_argument("--state", type=Path, default=DEFAULT_STATE)
    parser.add_argument("--status", type=Path, default=DEFAULT_STATUS)
    parser.add_argument("--once", action="store_true")
    parser.add_argument("--dry-run", action="store_true")
    parser.add_argument("--interval-seconds", type=float, default=30.0)
    parser.add_argument("--offline-open-jobs", type=Path)
    parser.add_argument("--offline-all-jobs", type=Path)
    return parser.parse_args()


def main() -> int:
    args = parse_args()
    identity = _read_json(args.identity, {})
    state = _read_json(args.state, {})
    offline_open_jobs = None
    offline_all_jobs = None
    if args.offline_open_jobs:
        offline_open_jobs = _jobs(_read_json(args.offline_open_jobs, {}))
    if args.offline_all_jobs:
        offline_all_jobs = _jobs(_read_json(args.offline_all_jobs, {}))

    while True:
        status, state = run_once(
            identity=identity,
            state=state,
            dry_run=args.dry_run,
            offline_open_jobs=offline_open_jobs,
            offline_all_jobs=offline_all_jobs,
        )
        _write_json(args.status, status)
        _write_json(args.state, state)
        print(json.dumps(status, indent=2, sort_keys=True))
        if args.once:
            return 0
        time.sleep(max(10.0, args.interval_seconds))


if __name__ == "__main__":
    raise SystemExit(main())
