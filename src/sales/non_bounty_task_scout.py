"""Scout non-bounty paid task markets for autonomous agent income."""

from __future__ import annotations

import json
import re
import urllib.error
import urllib.parse
import urllib.request
from datetime import datetime, timezone
from typing import Any


SCHEMA = "x0tta6bl4.non_bounty_task_scout.v1"

SOURCE_URLS = {
    "workprotocol": "https://workprotocol.ai/api/jobs?status=open&limit=100",
    "opentask": "https://opentask.ai/api/tasks?sort=new&limit=50",
    "moltjobs": "https://api.moltjobs.io/v1/jobs?status=OPEN&limit=50",
    "sporeagent": "https://sporeagent.com/api/tasks?status=open",
    "clustly": "https://clustly.ai/api/tasks?status=open&page=1&per_page=50",
    "riner": "https://api.riner.io/api/v1/tasks?status=published&limit=50",
    "agiotage": "https://agio-protocol-production.up.railway.app/v1/jobs/search?status=open&limit=50",
    "clawdgigs": "https://www.clawdgigs.com/api/gigs",
    "chesto": "https://chesto.ai/api/tasks",
}

DIRECT_WORK_SOURCES = {"workprotocol", "opentask", "moltjobs", "sporeagent", "clustly", "riner", "agiotage"}
MARKET_BENCHMARK_SOURCES = {"clawdgigs"}
AUTH_GATE_BY_SOURCE = {
    "workprotocol": "needs_workprotocol_agent_registration_and_api_key",
    "opentask": "needs_headless_registration_and_bearer_token",
    "moltjobs": "needs_dashboard_api_key_or_registered_agent",
    "sporeagent": "needs_sporeagent_registration_or_mcp_api_key",
    "clustly": "needs_claimed_agent_profile",
    "riner": "needs_wallet_signature_or_riner_api_key",
    "agiotage": "needs_agiotage_agent_registration_and_api_key",
}

SAFE_FIT_POINTS = {
    "openapi": 12,
    "api": 9,
    "python": 9,
    "automation": 8,
    "json": 7,
    "csv": 7,
    "documentation": 7,
    "docs": 7,
    "research": 6,
    "data": 6,
    "web-scraping": 5,
    "testing": 5,
    "qa": 5,
    "markdown": 5,
    "rest": 5,
    "cli": 7,
    "typescript": 6,
    "github actions": 7,
}

LOW_TOKEN_POINTS = {
    "microtask": 16,
    "small": 12,
    "parse": 10,
    "json": 8,
    "csv": 8,
    "docs": 8,
    "openapi": 8,
    "script": 6,
    "research note": 6,
}

HARD_REJECT_TERMS = {
    "airdrop",
    "captcha",
    "fake review",
    "follow",
    "followers",
    "backlink",
    "discord",
    "instagram",
    "kyc",
    "like",
    "linkedin",
    "malware",
    "private key",
    "qrt",
    "reddit",
    "referral",
    "retweet",
    "seed phrase",
    "social",
    "spam",
    "tiktok",
    "trustpilot",
    "twitter",
    "x.com",
    "youtube",
}

BOUNTY_REJECT_TERMS = {
    "bug bounty",
    "bug-bounty",
    "bounty",
    "bug hunting",
    "security audit",
}

BROAD_SERVICE_TERMS = {
    "24/7": 24,
    "any website": 24,
    "depending on complexity": 22,
    "full pipeline": 24,
    "money-back guarantee": 18,
    "api integration & automation": 18,
    "telegram bot development": 18,
    "ai agent automation": 18,
    "automation & ai solutions": 18,
    "custom ai agent": 18,
    "chatbot development": 18,
    "web scraping & data extraction": 18,
    "fast delivery": 12,
    "full stack": 18,
}

HIGH_EFFORT_TERMS = {
    "full test suite": 28,
    "npm package": 22,
    "redis": 14,
    "middleware": 12,
    "multiple strategies": 12,
    "adapter pattern": 12,
    "token bucket": 10,
    "sliding window": 10,
    "per-route": 8,
    "stack trace": 8,
    "github actions run url": 8,
    "handles at least 3": 8,
}


def _utc_now() -> str:
    return datetime.now(timezone.utc).replace(microsecond=0).isoformat().replace("+00:00", "Z")


def _http_json(url: str, *, timeout_seconds: float = 20.0) -> Any:
    request = urllib.request.Request(
        url,
        headers={
            "Accept": "application/json,text/plain,*/*",
            "User-Agent": "x0tta6bl4-non-bounty-task-scout",
        },
    )
    with urllib.request.urlopen(request, timeout=timeout_seconds) as response:
        return json.loads(response.read().decode("utf-8"))


def _text(*parts: Any) -> str:
    flattened: list[str] = []
    for part in parts:
        if isinstance(part, dict):
            flattened.extend(str(value) for value in part.values())
        elif isinstance(part, list):
            flattened.extend(str(value) for value in part)
        elif part is not None:
            flattened.append(str(part))
    return " ".join(flattened).lower()


def _numeric(value: Any) -> float | None:
    if isinstance(value, bool):
        return None
    if isinstance(value, int | float):
        return float(value)
    if isinstance(value, str):
        cleaned = value.strip().replace(",", "")
        try:
            return float(cleaned)
        except ValueError:
            return None
    return None


def _first_money_number(text: str) -> float | None:
    matches = re.findall(r"(?:\$|usdc|usd)?\s*([0-9][0-9,]*(?:\.[0-9]+)?)\s*(?:usdc|usd|\$)?", text.lower())
    values: list[float] = []
    for raw in matches:
        try:
            values.append(float(raw.replace(",", "")))
        except ValueError:
            continue
    return min(values) if values else None


def _budget_from_text(value: Any) -> tuple[float | None, str]:
    if value is None:
        return None, ""
    text = str(value)
    amount = _first_money_number(text)
    asset = "USDC" if "usdc" in text.lower() else "USD" if "$" in text or "usd" in text.lower() else ""
    return amount, asset


def _source_status(source_id: str, ok: bool, *, count: int = 0, error: str | None = None) -> dict[str, Any]:
    return {
        "source_id": source_id,
        "url": SOURCE_URLS[source_id],
        "ok": ok,
        "items": count,
        "error": error,
    }


def _normalise_opentask(payload: Any) -> list[dict[str, Any]]:
    tasks = payload.get("tasks", []) if isinstance(payload, dict) else []
    normalised: list[dict[str, Any]] = []
    for item in tasks:
        if not isinstance(item, dict):
            continue
        amount = _numeric(item.get("budgetAmount"))
        asset = str(item.get("budgetCurrency") or "").upper()
        if amount is None:
            amount, asset_from_text = _budget_from_text(item.get("budgetText"))
            asset = asset or asset_from_text
        requirements = item.get("capabilityRequirements", [])
        requirement_text = _text(requirements)
        normalised.append(
            {
                "source_id": "opentask",
                "source_kind": "public_task",
                "external_id": item.get("id"),
                "title": str(item.get("title") or ""),
                "description": requirement_text,
                "requirements": requirement_text,
                "url": f"https://opentask.ai/tasks/{item.get('id')}",
                "payout_amount": amount,
                "payout_asset": asset,
                "payout_usd": amount if asset in {"USD", "USDC"} else None,
                "tags": item.get("skillsTags") or [],
                "created_at": item.get("createdAt"),
                "deadline_utc": item.get("deadline"),
                "action_gate": AUTH_GATE_BY_SOURCE["opentask"],
                "action_type": "bid_after_account_gate",
            }
        )
    return normalised


def _normalise_workprotocol(payload: Any) -> list[dict[str, Any]]:
    jobs = payload.get("jobs", []) if isinstance(payload, dict) else []
    normalised: list[dict[str, Any]] = []
    for item in jobs:
        if not isinstance(item, dict):
            continue
        amount = _numeric(item.get("paymentAmount"))
        requirements = item.get("requirements") if isinstance(item.get("requirements"), dict) else {}
        acceptance = item.get("acceptanceCriteria") if isinstance(item.get("acceptanceCriteria"), list) else []
        requirement_text = _text(requirements, acceptance)
        category = str(item.get("category") or "")
        normalised.append(
            {
                "source_id": "workprotocol",
                "source_kind": "escrowed_open_job",
                "external_id": item.get("id"),
                "title": str(item.get("title") or ""),
                "description": str(item.get("description") or ""),
                "requirements": requirement_text,
                "url": f"https://workprotocol.ai/jobs/{item.get('id')}",
                "payout_amount": amount,
                "payout_asset": str(item.get("paymentCurrency") or "").upper(),
                "payout_usd": amount if str(item.get("paymentCurrency") or "").upper() in {"USD", "USDC"} else None,
                "tags": [category, item.get("paymentRail"), *(requirements.get("languages") or [])],
                "created_at": item.get("createdAt"),
                "deadline_utc": item.get("deadline"),
                "action_gate": AUTH_GATE_BY_SOURCE["workprotocol"],
                "action_type": "claim_after_agent_registration",
                "acceptance_criteria_count": len(acceptance),
                "payment_rail": item.get("paymentRail"),
            }
        )
    return normalised


def _normalise_moltjobs(payload: Any) -> list[dict[str, Any]]:
    tasks = payload.get("data", []) if isinstance(payload, dict) else []
    normalised: list[dict[str, Any]] = []
    for item in tasks:
        if not isinstance(item, dict):
            continue
        amount = _numeric(item.get("budgetUsdc"))
        input_data = item.get("inputData") if isinstance(item.get("inputData"), dict) else {}
        description = _text(input_data, item.get("templateId"))
        normalised.append(
            {
                "source_id": "moltjobs",
                "source_kind": "open_job",
                "external_id": item.get("id"),
                "title": str(item.get("title") or ""),
                "description": description,
                "requirements": description,
                "url": f"https://moltjobs.io/jobs/{item.get('id')}",
                "payout_amount": amount,
                "payout_asset": "USDC" if amount is not None else "",
                "payout_usd": amount,
                "tags": [item.get("templateId")],
                "created_at": item.get("createdAt"),
                "deadline_utc": item.get("deadlineAt"),
                "action_gate": AUTH_GATE_BY_SOURCE["moltjobs"],
                "action_type": "apply_after_api_key_gate",
                "escrow_tx_hash": item.get("escrowTxHash"),
            }
        )
    return normalised


def _normalise_clustly(payload: Any) -> list[dict[str, Any]]:
    tasks = payload.get("data", []) if isinstance(payload, dict) else []
    normalised: list[dict[str, Any]] = []
    for item in tasks:
        if not isinstance(item, dict):
            continue
        amount = _numeric(item.get("reward") or item.get("budget") or item.get("budget_usdc"))
        normalised.append(
            {
                "source_id": "clustly",
                "source_kind": "open_task",
                "external_id": item.get("id"),
                "title": str(item.get("title") or item.get("brief") or ""),
                "description": str(item.get("description") or item.get("brief") or ""),
                "requirements": str(item.get("requirements") or ""),
                "url": f"https://clustly.ai/tasks/{item.get('id')}",
                "payout_amount": amount,
                "payout_asset": "USDC" if amount is not None else "",
                "payout_usd": amount,
                "tags": item.get("tags") or [],
                "created_at": item.get("created_at") or item.get("createdAt"),
                "deadline_utc": item.get("deadline") or item.get("deadlineAt"),
                "action_gate": AUTH_GATE_BY_SOURCE["clustly"],
                "action_type": "claim_after_profile_gate",
            }
        )
    return normalised


def _normalise_sporeagent(payload: Any) -> list[dict[str, Any]]:
    tasks = payload.get("tasks", []) if isinstance(payload, dict) else []
    normalised: list[dict[str, Any]] = []
    for item in tasks:
        if not isinstance(item, dict):
            continue
        amount = _numeric(item.get("budget_usd") or item.get("budgetUsd") or item.get("budget"))
        requirements = item.get("requirements") if isinstance(item.get("requirements"), list) else []
        normalised.append(
            {
                "source_id": "sporeagent",
                "source_kind": "open_agent_task",
                "external_id": item.get("id"),
                "title": str(item.get("title") or ""),
                "description": str(item.get("description") or ""),
                "requirements": _text(requirements),
                "url": f"https://sporeagent.com/tasks/{item.get('id')}",
                "payout_amount": amount,
                "payout_asset": "USD" if amount is not None else "",
                "payout_usd": amount,
                "tags": requirements,
                "created_at": item.get("posted_at") or item.get("postedAt") or item.get("created_at"),
                "deadline_utc": item.get("deadline") or item.get("deadline_at"),
                "action_gate": AUTH_GATE_BY_SOURCE["sporeagent"],
                "action_type": "bid_after_agent_registration",
                "bid_count": _numeric(item.get("bid_count") or item.get("bidCount")) or 0,
                "assigned_agent_id": item.get("assigned_agent_id") or item.get("assignedAgentId"),
            }
        )
    return normalised


def _normalise_clawdgigs(payload: Any) -> list[dict[str, Any]]:
    gigs = payload.get("gigs", []) if isinstance(payload, dict) else []
    normalised: list[dict[str, Any]] = []
    for item in gigs:
        if not isinstance(item, dict):
            continue
        amount = _numeric(item.get("price_usdc"))
        normalised.append(
            {
                "source_id": "clawdgigs",
                "source_kind": "seller_market_benchmark",
                "external_id": item.get("id"),
                "title": str(item.get("title") or ""),
                "description": str(item.get("description") or ""),
                "requirements": "",
                "url": "https://www.clawdgigs.com/",
                "payout_amount": amount,
                "payout_asset": "USDC" if amount is not None else "",
                "payout_usd": amount,
                "tags": [item.get("category"), item.get("delivery_time")],
                "created_at": item.get("created_at"),
                "action_gate": "seller_registration_wallet_ui",
                "action_type": "price_benchmark_for_our_own_fixed_gig",
                "orders_seen": _numeric(item.get("total_orders")) or 0,
            }
        )
    return normalised


def _normalise_chesto(payload: Any) -> list[dict[str, Any]]:
    tasks = payload if isinstance(payload, list) else []
    normalised: list[dict[str, Any]] = []
    for item in tasks:
        if not isinstance(item, dict):
            continue
        amount = _numeric(item.get("reward"))
        normalised.append(
            {
                "source_id": "chesto",
                "source_kind": "public_task",
                "external_id": item.get("_id") or item.get("id"),
                "title": str(item.get("title") or ""),
                "description": str(item.get("description") or ""),
                "requirements": _text(item.get("steps"), item.get("requiredFields"), item.get("accountRequirements")),
                "url": "https://chesto.ai/",
                "payout_amount": amount,
                "payout_asset": "USDC" if amount is not None else "",
                "payout_usd": amount,
                "tags": [item.get("type"), item.get("difficulty"), item.get("platform")],
                "created_at": item.get("createdAt"),
                "action_gate": "twitter_or_fluxapay_gate",
                "action_type": "reject_social_or_review_tasks",
            }
        )
    return normalised


def _normalise_riner(payload: Any) -> list[dict[str, Any]]:
    tasks = payload.get("tasks", []) if isinstance(payload, dict) else []
    normalised: list[dict[str, Any]] = []
    for item in tasks:
        if not isinstance(item, dict):
            continue
        amount = _numeric(item.get("budget_amount") or item.get("budgetAmount"))
        requirements = item.get("requirements") if isinstance(item.get("requirements"), dict) else {}
        output_spec = item.get("output_spec") if isinstance(item.get("output_spec"), dict) else {}
        normalised.append(
            {
                "source_id": "riner",
                "source_kind": "escrowed_open_task",
                "external_id": item.get("id"),
                "title": str(item.get("title") or ""),
                "description": str(item.get("description") or ""),
                "requirements": _text(requirements, output_spec, item.get("verification")),
                "url": f"https://riner.io/tasks/{item.get('id')}",
                "payout_amount": amount,
                "payout_asset": str(item.get("budget_token") or "").upper(),
                "payout_usd": amount if str(item.get("budget_token") or "").upper() in {"USD", "USDC"} else None,
                "tags": [item.get("category"), *(item.get("tags") or [])],
                "created_at": item.get("created_at") or item.get("createdAt"),
                "deadline_utc": item.get("deadline"),
                "action_gate": AUTH_GATE_BY_SOURCE["riner"],
                "action_type": "apply_after_wallet_signature_or_api_key",
                "escrow_tx_hash": item.get("escrow_tx") or item.get("escrowTx"),
                "selection_mode": item.get("selection_mode") or item.get("selectionMode"),
                "max_applicants": _numeric(item.get("max_applicants") or item.get("maxApplicants")),
            }
        )
    return normalised


def _normalise_agiotage(payload: Any) -> list[dict[str, Any]]:
    jobs = payload.get("jobs", []) if isinstance(payload, dict) else []
    normalised: list[dict[str, Any]] = []
    for item in jobs:
        if not isinstance(item, dict):
            continue
        amount = _numeric(item.get("budget"))
        asset = str(item.get("token") or "").upper()
        normalised.append(
            {
                "source_id": "agiotage",
                "source_kind": "open_job",
                "external_id": item.get("id"),
                "title": str(item.get("title") or ""),
                "description": str(item.get("description") or ""),
                "requirements": str(item.get("category") or ""),
                "url": f"https://agiotage.finance/jobs/{item.get('id')}",
                "payout_amount": amount,
                "payout_asset": asset,
                "payout_usd": amount if asset in {"USD", "USDC"} else None,
                "tags": [item.get("category")],
                "created_at": item.get("created_at") or item.get("createdAt"),
                "deadline_utc": item.get("deadline") or item.get("deadline_at"),
                "action_gate": AUTH_GATE_BY_SOURCE["agiotage"],
                "action_type": "bid_after_agent_registration",
            }
        )
    return normalised


NORMALISERS = {
    "workprotocol": _normalise_workprotocol,
    "opentask": _normalise_opentask,
    "moltjobs": _normalise_moltjobs,
    "sporeagent": _normalise_sporeagent,
    "clustly": _normalise_clustly,
    "riner": _normalise_riner,
    "agiotage": _normalise_agiotage,
    "clawdgigs": _normalise_clawdgigs,
    "chesto": _normalise_chesto,
}


def collect_source(source_id: str) -> tuple[list[dict[str, Any]], dict[str, Any]]:
    url = SOURCE_URLS[source_id]
    try:
        payload = _http_json(url)
    except (urllib.error.HTTPError, urllib.error.URLError, TimeoutError, json.JSONDecodeError) as exc:
        error = exc.__class__.__name__
        if isinstance(exc, urllib.error.HTTPError):
            error = f"http_{exc.code}"
        return [], _source_status(source_id, False, error=error)
    tasks = NORMALISERS[source_id](payload)
    return tasks, _source_status(source_id, True, count=len(tasks))


def collect_non_bounty_tasks(
    *,
    source_ids: tuple[str, ...] = (
        "workprotocol",
        "opentask",
        "moltjobs",
        "sporeagent",
        "clustly",
        "riner",
        "agiotage",
        "clawdgigs",
        "chesto",
    ),
) -> dict[str, Any]:
    tasks: list[dict[str, Any]] = []
    statuses: list[dict[str, Any]] = []
    for source_id in source_ids:
        source_tasks, status = collect_source(source_id)
        tasks.extend(source_tasks)
        statuses.append(status)
    return {
        "schema": SCHEMA,
        "collected_at_utc": _utc_now(),
        "source_statuses": statuses,
        "tasks_total": len(tasks),
        "tasks": tasks,
        "claim_gate": {
            "collection_claim_allowed": True,
            "accepted_work_claim_allowed": False,
            "funds_received_claim_allowed": False,
        },
    }


def _keyword_points(text: str, mapping: dict[str, int]) -> tuple[int, list[str]]:
    matches = [keyword for keyword in mapping if keyword in text]
    return sum(mapping[keyword] for keyword in matches), matches


def _estimate_token_cost(task: dict[str, Any], text: str) -> int:
    base = 45_000
    base += min(120_000, int((task.get("payout_usd") or 0) * 180))
    low_points, _ = _keyword_points(text, LOW_TOKEN_POINTS)
    base -= low_points * 1_200
    if "research" in text:
        base += 45_000
    if "article" in text or "newsletter" in text or "reel" in text:
        base += 80_000
    return max(15_000, min(350_000, base))


def score_non_bounty_task(task: dict[str, Any]) -> dict[str, Any]:
    text = _text(
        task.get("title"),
        task.get("description"),
        task.get("requirements"),
        task.get("tags"),
        task.get("source_kind"),
    )
    payout = _numeric(task.get("payout_usd"))
    estimated_token_cost = _estimate_token_cost(task, text)
    safe_points, safe_matches = _keyword_points(text, SAFE_FIT_POINTS)
    low_points, low_matches = _keyword_points(text, LOW_TOKEN_POINTS)

    score = 0
    reasons: list[str] = []
    risk_flags: list[str] = []
    source_id = str(task.get("source_id") or "")

    if source_id in DIRECT_WORK_SOURCES:
        score += 22
        reasons.append("direct_work_source")
    elif source_id in MARKET_BENCHMARK_SOURCES:
        score += 8
        risk_flags.append("market_benchmark_not_direct_work")

    if payout is not None and payout > 0:
        score += min(32, 8 + int(payout / 8))
        reasons.append(f"payout_usd:{payout:g}")
    else:
        score -= 20
        risk_flags.append("no_direct_payout")

    if task.get("escrow_tx_hash"):
        score += 8
        reasons.append("escrow_tx_present")

    if safe_points:
        score += min(28, safe_points)
        reasons.append("fit:" + ",".join(sorted(set(safe_matches))[:8]))
    if low_points:
        score += min(16, int(low_points / 2))
        reasons.append("low_token:" + ",".join(sorted(set(low_matches))[:8]))

    high_effort_points, high_effort_matches = _keyword_points(text, HIGH_EFFORT_TERMS)
    if high_effort_points:
        score -= min(45, high_effort_points)
        risk_flags.append("high_effort")
        reasons.append("high_effort:" + ",".join(sorted(set(high_effort_matches))[:8]))

    auth_gate = task.get("action_gate")
    if auth_gate:
        score -= 10
        risk_flags.append(str(auth_gate))

    for term in HARD_REJECT_TERMS:
        if term in text:
            score -= 80
            risk_flags.append(term)
    for term in BOUNTY_REJECT_TERMS:
        if term in text:
            score -= 70
            risk_flags.append("bounty_route")

    broad_hits = [term for term in BROAD_SERVICE_TERMS if term in text]
    if broad_hits:
        score -= sum(BROAD_SERVICE_TERMS[term] for term in broad_hits)
        risk_flags.append("broad_service_listing")
        reasons.append("broad_terms:" + ",".join(sorted(broad_hits)[:6]))

    if "0 usdc" in text or payout == 0:
        score -= 40
        risk_flags.append("zero_reward")

    hard_reject = any(flag in risk_flags for flag in HARD_REJECT_TERMS) or "bounty_route" in risk_flags
    if hard_reject:
        decision = "reject"
    elif source_id in MARKET_BENCHMARK_SOURCES:
        decision = "watch_only"
    elif score >= 58 and payout is not None and payout >= 1 and "broad_service_listing" not in risk_flags:
        decision = "account_gate_first"
    elif score >= 40:
        decision = "manual_review"
    else:
        decision = "reject"

    token_roi_score = 0.0
    if payout:
        token_roi_score = round(payout / max(0.01, estimated_token_cost / 100_000), 2)

    return {
        "source_id": source_id,
        "source_kind": task.get("source_kind"),
        "title": str(task.get("title") or "").strip(),
        "url": str(task.get("url") or ""),
        "external_id": task.get("external_id"),
        "decision": decision,
        "score": max(0, min(100, score)),
        "raw_score": score,
        "payout_usd_estimate": payout,
        "estimated_token_cost": estimated_token_cost,
        "token_roi_score": token_roi_score,
        "risk_flags": sorted(set(risk_flags)),
        "reasons": reasons,
        "action_gate": task.get("action_gate"),
        "action_type": task.get("action_type"),
        "next_machine_step": _next_machine_step(source_id, decision),
        "claim_gate": {
            "accepted_work_claim_allowed": False,
            "funds_received_claim_allowed": False,
        },
    }


def _next_machine_step(source_id: str, decision: str) -> str:
    if decision == "reject":
        return "Do not spend tokens on this task."
    if source_id == "opentask":
        return "Register/login headless OpenTask agent, add payout wallet, then bid with exact acceptance checks."
    if source_id == "workprotocol":
        return "Register WorkProtocol agent, then claim only if the deliverable URL and acceptance checks are feasible."
    if source_id == "moltjobs":
        return "Wait for MoltJobs API key or dashboard setup, then apply only to clear research/data/API jobs."
    if source_id == "sporeagent":
        return "Register or connect SporeAgent MCP, then bid only on small API/docs/pytest/data tasks with clear output."
    if source_id == "clustly":
        return "Finish Clustly claim gate, then publish the fixed web-health service and poll orders."
    if source_id == "riner":
        return "Self-register with a signed wallet message, then apply only to escrowed technical tasks."
    if source_id == "agiotage":
        return "Register an Agiotage agent, then bid only on low-scope code/data jobs with clear output."
    if source_id == "clawdgigs":
        return "Use competitor prices to publish our own fixed gig, not to do work here."
    return "Keep watching; no direct autonomous action yet."


def rank_non_bounty_tasks(collection: dict[str, Any], *, top_n: int = 25) -> dict[str, Any]:
    scored = [score_non_bounty_task(task) for task in collection.get("tasks", []) if isinstance(task, dict)]
    decision_rank = {"account_gate_first": 3, "manual_review": 2, "watch_only": 1, "reject": 0}
    ranked = sorted(
        scored,
        key=lambda item: (
            decision_rank.get(item["decision"], 0),
            item["token_roi_score"],
            item["score"],
            item["title"],
        ),
        reverse=True,
    )
    selected = [item for item in ranked if item["decision"] == "account_gate_first"][:10]
    return {
        "schema": SCHEMA,
        "status": "ranked" if scored else "empty",
        "ranked_at_utc": _utc_now(),
        "tasks_total": len(scored),
        "account_gate_first_total": sum(1 for item in scored if item["decision"] == "account_gate_first"),
        "manual_review_total": sum(1 for item in scored if item["decision"] == "manual_review"),
        "watch_only_total": sum(1 for item in scored if item["decision"] == "watch_only"),
        "reject_total": sum(1 for item in scored if item["decision"] == "reject"),
        "selected_first": selected,
        "ranked": ranked[: max(0, top_n)],
        "claim_gate": {
            "ranking_claim_allowed": True,
            "accepted_work_claim_allowed": False,
            "funds_received_claim_allowed": False,
        },
    }
