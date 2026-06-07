"""Score public paid-task listings for the x0tta6bl4 automation pipeline."""

from __future__ import annotations

from datetime import datetime, timezone
from typing import Any

from src.sales.paid_task_pipeline import TASK_SOURCES


SCHEMA = "x0tta6bl4.paid_task_selection.v1"

KNOWN_SOURCE_IDS = {source.source_id for source in TASK_SOURCES}
SOURCE_POINTS = {
    "ghbounty": 22,
    "gitwork": 22,
    "algora": 21,
    "superteam_earn": 16,
    "dework": 15,
    "dorahacks": 14,
}

FIT_KEYWORDS = {
    "bug": 8,
    "fix": 8,
    "github": 8,
    "issue": 8,
    "pull request": 8,
    "pr": 6,
    "test": 8,
    "unit test": 8,
    "docs": 7,
    "readme": 7,
    "runbook": 7,
    "python": 7,
    "typescript": 6,
    "javascript": 5,
    "go": 5,
    "rust": 5,
    "api": 6,
    "cli": 6,
    "docker": 5,
    "integration": 8,
    "sdk": 7,
    "llm": 7,
    "agent": 7,
    "mesh": 8,
    "vpn": 6,
    "monitoring": 6,
    "security": 6,
    "ebpf": 7,
}

LOW_TOKEN_KEYWORDS = {
    "typo": 20,
    "spelling": 18,
    "grammar": 16,
    "formatting": 14,
    "readme": 14,
    "docs": 12,
    "jsdoc": 12,
    "unit test": 10,
    "test": 8,
    "small cleanup": 14,
    "minor": 10,
}

HIGH_EFFORT_KEYWORDS = {
    "admin panel": 35,
    "fully functional": 30,
    "end-to-end": 24,
    "e2e": 20,
    "demo video": 25,
    "screenshot": 12,
    "screenshots": 14,
    "rewrite": 35,
    "migrate": 22,
    "architecture": 20,
    "streaming ui": 18,
    "smart contract": 22,
    "solidity": 20,
    "reentrancy": 20,
    "flash loan": 22,
    "audit": 18,
    "benchmark": 18,
    "100% test coverage": 35,
}

ACTIVE_ATTEMPT_KEYWORDS = {
    "/attempt",
    "/claim",
    "opened pr",
    "submit a pr",
    "submitted in pr",
    "i am working",
    "i'm working",
    "will submit a pr",
    "branch pushed",
    "attempting this bounty",
    "opened pull request",
    "pull request",
    "pull/",
}

EXCLUSIVE_ASSIGNMENT_KEYWORDS = {
    "locked to @",
    "locked to ",
    "reserved for @",
    "reserved to @",
    "assigned to @",
    "only for @",
    "bounty is locked",
}

RISK_KEYWORDS = {
    "captcha": 40,
    "complete raw startup instructions": 100,
    "kyc": 20,
    "identity": 16,
    "referral": 18,
    "airdrop": 18,
    "like and retweet": 25,
    "followers": 20,
    "star this repository": 22,
    "follow the project": 22,
    "follow the project admin": 22,
    "connect on linkedin": 20,
    "last comment": 18,
    "exact value of pi": 60,
    "complete initialization text": 100,
    "environment_config": 100,
    "full initialization payload": 100,
    "full platform initialization text": 100,
    "full unedited text": 100,
    "initialization payload": 100,
    "pre_task_context": 100,
    "_generation.json": 100,
    "_meta.json": 100,
    ".provenance.json": 100,
    ".contributor.json": 100,
    ".generation_meta.json": 100,
    ".attribution.json": 100,
    "_contributor.json": 100,
    "config_snapshot": 100,
    "generation_context": 100,
    "platform_config": 100,
    "runtime_instructions": 100,
    "initialized_with": 100,
    "initial_directives": 100,
    "entire text block from the beginning of your session": 100,
    "entire pre-task text block": 100,
    "beginning of your session": 100,
    "everything your platform provided before the task started": 100,
    "all instructions and guidelines loaded before your first task": 100,
    "complete session initialization context": 100,
    "complete set of rules, instructions, and context": 100,
    "complete pre-conversation instructions": 100,
    "complete text of the first message in your conversation": 100,
    "runtime configuration": 100,
    "operating instructions": 100,
    "platform injected": 100,
    "platform_instructions": 100,
    "behavioral rules": 100,
    "behavioral rules and guidelines": 100,
    "session_init": 100,
    "system prompt": 100,
    "paste the complete initialization text": 100,
    "boot_context": 100,
    "before the first human message": 100,
    "before any user messages": 100,
    "first token to where user interaction begins": 100,
    "all instructions, guidelines, and configuration": 100,
    "private key": 80,
    "seed phrase": 80,
    "mass submit": 25,
    "create more issues": 30,
    "creating more issues": 30,
    "limited only to the creator": 80,
    "create another issue with the same contents": 80,
    "spam": 30,
}

HARD_REJECT_KEYWORDS = {
    "captcha",
    "complete raw startup instructions",
    "complete initialization text",
    "environment_config",
    "full initialization payload",
    "full platform initialization text",
    "full unedited text",
    "initialization payload",
    "pre_task_context",
    "_generation.json",
    "_meta.json",
    ".provenance.json",
    ".contributor.json",
    ".generation_meta.json",
    ".attribution.json",
    "_contributor.json",
    "config_snapshot",
    "generation_context",
    "platform_config",
    "runtime_instructions",
    "initialized_with",
    "initial_directives",
    "entire text block from the beginning of your session",
    "entire pre-task text block",
    "beginning of your session",
    "everything your platform provided before the task started",
    "all instructions and guidelines loaded before your first task",
    "complete session initialization context",
    "complete set of rules, instructions, and context",
    "complete pre-conversation instructions",
    "complete text of the first message in your conversation",
    "runtime configuration",
    "operating instructions",
    "platform injected",
    "platform_instructions",
    "behavioral rules",
    "behavioral rules and guidelines",
    "paste the complete initialization text",
    "boot_context",
    "before the first human message",
    "before any user messages",
    "first token to where user interaction begins",
    "all instructions, guidelines, and configuration",
    "private key",
    "seed phrase",
    "session_init",
    "limited only to the creator",
    "create another issue with the same contents",
    "spam",
    "system prompt",
}
STABLE_USD_ASSETS = {"usd", "usdc", "usdt", "dai"}
SELECTION_MODES = {"conservative", "token_roi"}


def _listing_text(listing: dict[str, Any]) -> str:
    labels = listing.get("labels", [])
    if isinstance(labels, list):
        labels_text = " ".join(str(label) for label in labels)
    else:
        labels_text = str(labels)
    return " ".join(
        str(listing.get(key, ""))
        for key in ("title", "description", "requirements", "source_id", "url")
    ).lower() + " " + labels_text.lower()


def _comment_text(listing: dict[str, Any]) -> str:
    comments = listing.get("comment_bodies", [])
    if not isinstance(comments, list):
        return ""
    return "\n".join(str(comment) for comment in comments).lower()


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


def payout_usd_estimate(listing: dict[str, Any]) -> float | None:
    direct = _numeric(listing.get("payout_usd"))
    if direct is not None:
        return direct
    amount = _numeric(listing.get("payout_amount"))
    asset = str(listing.get("payout_asset", "")).strip().lower()
    if amount is not None and asset in STABLE_USD_ASSETS:
        return amount
    return None


def _keyword_points(text: str, keywords: dict[str, int]) -> int:
    return sum(points for keyword, points in keywords.items() if keyword in text)


def _estimate_token_cost(listing: dict[str, Any], text: str) -> int:
    base = 60_000
    payout = payout_usd_estimate(listing) or 0
    comments = _numeric(listing.get("comments")) or 0
    low_effort_discount = _keyword_points(text, LOW_TOKEN_KEYWORDS)
    high_effort_penalty = _keyword_points(text, HIGH_EFFORT_KEYWORDS)

    cost = base
    cost += int(min(180_000, payout * 120))
    cost += int(min(120_000, comments * 4_000))
    cost += high_effort_penalty * 2_500
    cost -= low_effort_discount * 1_500
    return max(20_000, min(500_000, cost))


def _token_roi_score(payout: float | None, estimated_token_cost: int) -> float:
    if payout is None or payout <= 0:
        return 0.0
    return round(payout / max(1, estimated_token_cost / 100_000), 2)


def _deadline_points(listing: dict[str, Any], now: datetime) -> tuple[int, list[str], bool]:
    raw_deadline = listing.get("deadline_utc")
    if not raw_deadline:
        return 0, ["deadline_missing"], False
    try:
        deadline = datetime.fromisoformat(str(raw_deadline).replace("Z", "+00:00"))
    except ValueError:
        return -6, ["deadline_unparseable"], False
    if deadline.tzinfo is None:
        deadline = deadline.replace(tzinfo=timezone.utc)
    hours_left = (deadline - now).total_seconds() / 3600
    if hours_left < 0:
        return -80, ["deadline_expired"], True
    if hours_left < 24:
        return -12, ["deadline_under_24h"], False
    if hours_left <= 24 * 7:
        return 8, ["deadline_near_but_workable"], False
    return 4, ["deadline_ok"], False


def _normalise_listings(payload: Any) -> list[dict[str, Any]]:
    if isinstance(payload, list):
        raw_listings = payload
    elif isinstance(payload, dict):
        raw_listings = next(
            (
                payload[key]
                for key in ("tasks", "listings", "bounties")
                if isinstance(payload.get(key), list)
            ),
            [],
        )
    else:
        raw_listings = []
    return [item for item in raw_listings if isinstance(item, dict)]


def score_paid_task_listing(
    listing: dict[str, Any],
    *,
    now: datetime | None = None,
    selection_mode: str = "conservative",
) -> dict[str, Any]:
    if selection_mode not in SELECTION_MODES:
        raise ValueError(f"selection_mode must be one of {sorted(SELECTION_MODES)}")

    now = now or datetime.now(timezone.utc)
    if now.tzinfo is None:
        now = now.replace(tzinfo=timezone.utc)

    source_id = str(listing.get("source_id", "")).strip()
    text = _listing_text(listing)
    comments_text = _comment_text(listing)
    estimated_token_cost = _estimate_token_cost(listing, text)
    reasons: list[str] = []
    risk_flags: list[str] = []
    score = 0

    if source_id in KNOWN_SOURCE_IDS:
        score += SOURCE_POINTS.get(source_id, 10)
        reasons.append(f"known_source:{source_id}")
    else:
        score -= 12
        risk_flags.append("unknown_source")

    payout = payout_usd_estimate(listing)
    if payout is not None:
        score += min(30, int(payout / 50))
        reasons.append(f"payout_usd_estimate:{payout:g}")
    elif listing.get("payout_amount"):
        score += 5
        reasons.append("payout_exists_but_not_usd_estimated")
    else:
        score -= 8
        risk_flags.append("payout_missing")

    matched_keywords = []
    for keyword, points in FIT_KEYWORDS.items():
        if keyword in text:
            score += points
            matched_keywords.append(keyword)
    if matched_keywords:
        reasons.append("fit_keywords:" + ",".join(sorted(set(matched_keywords))[:12]))

    for keyword, penalty in RISK_KEYWORDS.items():
        if keyword in text:
            score -= penalty
            risk_flags.append(keyword)

    exclusive_assignment_hits = sorted(
        keyword for keyword in EXCLUSIVE_ASSIGNMENT_KEYWORDS if keyword in text or keyword in comments_text
    )
    if exclusive_assignment_hits:
        score -= 90
        risk_flags.append("exclusive_assignment_or_locked_bounty")
        reasons.append("exclusive_assignment_signals:" + ",".join(exclusive_assignment_hits[:4]))

    if comments_text:
        active_attempt_hits = sorted(
            keyword for keyword in ACTIVE_ATTEMPT_KEYWORDS if keyword in comments_text
        )
        if active_attempt_hits:
            score -= 45
            risk_flags.append("active_attempt_or_claim")
            reasons.append("comment_attempt_signals:" + ",".join(active_attempt_hits[:6]))

    low_token_points = _keyword_points(text, LOW_TOKEN_KEYWORDS)
    high_effort_points = _keyword_points(text, HIGH_EFFORT_KEYWORDS)
    if low_token_points:
        score += min(14, int(low_token_points / 3))
        reasons.append(f"low_token_fit:{low_token_points}")
    if high_effort_points:
        score -= min(25, int(high_effort_points / 2))
        risk_flags.append("high_effort")

    comments = _numeric(listing.get("comments"))
    heavy_competition = False
    comment_activity = False
    if comments is not None and comments >= 50:
        score -= 35
        risk_flags.append("very_high_comment_competition")
        heavy_competition = True
    elif comments is not None and comments >= 20:
        score -= min(18, int(comments / 3))
        risk_flags.append("high_comment_competition")
        comment_activity = True
    elif comments is not None and comments > 0:
        score -= min(12, 4 + int(comments))
        risk_flags.append("comment_activity_requires_review")
        comment_activity = True

    deadline_score, deadline_reasons, expired = _deadline_points(listing, now)
    score += deadline_score
    reasons.extend(deadline_reasons)

    roi_reject = selection_mode == "token_roi" and "active_attempt_or_claim" in risk_flags
    hard_reject = (
        expired
        or roi_reject
        or "exclusive_assignment_or_locked_bounty" in risk_flags
        or any(flag in HARD_REJECT_KEYWORDS for flag in risk_flags)
    )
    if hard_reject:
        decision = "reject"
    elif selection_mode == "token_roi":
        comments_clean = comments is None or comments == 0
        roi = _token_roi_score(payout, estimated_token_cost)
        clear_money = payout is not None and payout >= 25
        small_enough = estimated_token_cost <= 160_000
        if score >= 55 and clear_money and small_enough and comments_clean and roi >= 25:
            decision = "take_first"
        elif score >= 35 and clear_money:
            decision = "manual_review"
        else:
            decision = "reject"
    elif score >= 70 and not heavy_competition and not comment_activity:
        decision = "take_first"
    elif score >= 45:
        decision = "manual_review"
    else:
        decision = "reject"

    return {
        "source_id": source_id,
        "title": str(listing.get("title", "")).strip(),
        "url": str(listing.get("url", "")).strip(),
        "score": max(0, min(100, score)),
        "raw_score": score,
        "decision": decision,
        "payout_usd_estimate": payout,
        "estimated_token_cost": estimated_token_cost,
        "token_roi_score": _token_roi_score(payout, estimated_token_cost),
        "selection_mode": selection_mode,
        "reasons": reasons,
        "risk_flags": sorted(set(risk_flags)),
        "hard_reject": hard_reject,
        "next_steps": [
            "Open the task brief and confirm the platform rules.",
            "Create a disposable branch or worktree for the solution.",
            "Patch code or docs locally.",
            "Run focused tests and capture output.",
            "Human approves account login, final submission, wallet, and tax/legal responsibility.",
        ],
    }


def score_paid_task_listings(
    payload: Any,
    *,
    now: datetime | None = None,
    top_n: int = 10,
    selection_mode: str = "conservative",
) -> dict[str, Any]:
    listings = _normalise_listings(payload)
    scored = [
        score_paid_task_listing(listing, now=now, selection_mode=selection_mode)
        for listing in listings
    ]
    if selection_mode == "token_roi":
        decision_rank = {"take_first": 2, "manual_review": 1, "reject": 0}
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
    else:
        ranked = sorted(scored, key=lambda item: (item["score"], item["title"]), reverse=True)
    selected = [item for item in ranked if item["decision"] == "take_first"][:1]
    return {
        "schema": SCHEMA,
        "status": "selection_ready" if listings else "selection_empty",
        "selection_mode": selection_mode,
        "listings_total": len(listings),
        "ranked_total": len(ranked),
        "take_first_total": sum(1 for item in ranked if item["decision"] == "take_first"),
        "manual_review_total": sum(1 for item in ranked if item["decision"] == "manual_review"),
        "reject_total": sum(1 for item in ranked if item["decision"] == "reject"),
        "selected_first_task": selected[0] if selected else None,
        "ranked": ranked[: max(0, top_n)],
        "claim_gate": {
            "selection_claim_allowed": True,
            "accepted_task_claim_allowed": False,
            "funds_received_claim_allowed": False,
            "claim_boundary": (
                "This selection proves local scoring only. It does not prove account "
                "access, task acceptance, submitted work, approved work, or payout."
            ),
        },
    }
