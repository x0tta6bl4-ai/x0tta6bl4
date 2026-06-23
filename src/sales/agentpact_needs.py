"""AgentPact need selection for non-bounty autonomous income."""

from __future__ import annotations

import json
from dataclasses import dataclass
from decimal import Decimal, InvalidOperation, ROUND_HALF_UP
from typing import Any


SCHEMA = "x0tta6bl4.agentpact_need_selection.v1"
CLAIM_BOUNDARY = (
    "This selection ranks public AgentPact needs and prepares deal payloads. "
    "It does not prove deal acceptance, delivery approval, escrow release, "
    "payout eligibility, or received funds."
)

DEFAULT_SKILLS = {
    "api",
    "automation",
    "coding",
    "data",
    "data-extraction",
    "development",
    "github",
    "json",
    "python",
    "reports",
    "review",
    "triage",
}

GOOD_CATEGORIES = {"automation", "data", "development", "content", "software-development"}
WEAK_CATEGORIES = {"consulting"}
HARD_REJECT_CATEGORIES = {"physical-service"}

HARD_REJECT_KEYWORDS = (
    "airdrop",
    "bounties",
    "bug bounty",
    "captcha",
    "credential",
    "kyc",
    "password",
    "private key",
    "seed phrase",
    "sybil",
    "wallet seed",
)

NOISE_KEYWORDS = (
    "bundle via vault",
    "prove my agent can earn",
    "release calldata",
    "self-test",
    "welcome desk",
)

LONG_RUNNING_KEYWORDS = (
    "daily",
    "feed",
    "implementation",
    "pipeline",
    "real-time",
    "stock market",
)

ONE_SHOT_KEYWORDS = (
    "analysis",
    "check",
    "compilation",
    "format",
    "report",
    "review",
    "summary",
    "triage",
    "validation",
)


@dataclass(frozen=True)
class ScoredNeed:
    need: dict[str, Any]
    score: float
    decision: str
    reasons: tuple[str, ...]
    risks: tuple[str, ...]


def _text_blob(need: dict[str, Any]) -> str:
    tags = need.get("tags") if isinstance(need.get("tags"), list) else []
    parts = [
        str(need.get("title") or ""),
        str(need.get("description_md") or ""),
        str(need.get("category") or ""),
        " ".join(str(tag) for tag in tags),
    ]
    return " ".join(parts).lower()


def _decimal_or_none(value: Any) -> Decimal | None:
    if value is None or value == "":
        return None
    try:
        return Decimal(str(value))
    except (InvalidOperation, ValueError):
        return None


def _money_float(value: Decimal) -> float:
    return float(value.quantize(Decimal("0.01"), rounding=ROUND_HALF_UP))


def parse_acceptance(value: Any) -> list[str]:
    def clean(items: list[Any]) -> list[str]:
        return [
            str(item)
            for item in items
            if str(item).strip() and str(item).strip() != "[]"
        ]

    if value is None:
        return []
    if isinstance(value, list):
        return clean(value)
    if not isinstance(value, str) or not value.strip():
        return []
    try:
        parsed = json.loads(value)
    except json.JSONDecodeError:
        return [value.strip()] if value.strip() != "[]" else []
    if isinstance(parsed, list):
        return clean(parsed)
    if isinstance(parsed, str) and parsed.strip() and parsed.strip() != "[]":
        return [parsed.strip()]
    return []


def score_need(need: dict[str, Any], *, skills: set[str] | None = None) -> ScoredNeed:
    skills = set(DEFAULT_SKILLS if skills is None else skills)
    score = 0.0
    reasons: list[str] = []
    risks: list[str] = []
    text = _text_blob(need)
    category = str(need.get("category") or "").lower()
    tags = {str(tag).lower() for tag in need.get("tags", []) if str(tag).strip()}
    budget_min = _decimal_or_none(need.get("budget_min"))
    budget_max = _decimal_or_none(need.get("budget_max"))
    acceptance = parse_acceptance(need.get("acceptance_criteria"))

    if str(need.get("status") or "").lower() != "open":
        return ScoredNeed(need, 0.0, "reject", ("need_not_open",), ("closed_or_archived",))
    score += 8
    reasons.append("open_need")

    if category in HARD_REJECT_CATEGORIES or need.get("location"):
        return ScoredNeed(need, 0.0, "reject", ("not_remote_software_work",), ("physical_or_location_bound",))

    hard_hits = [keyword for keyword in HARD_REJECT_KEYWORDS if keyword in text]
    if hard_hits:
        return ScoredNeed(need, 0.0, "reject", ("hard_reject_keyword",), tuple(hard_hits))

    noise_hits = [keyword for keyword in NOISE_KEYWORDS if keyword in text]
    if noise_hits:
        return ScoredNeed(need, 0.0, "reject", ("market_noise_or_onboarding_test",), tuple(noise_hits))

    if budget_min is None and budget_max is None:
        score -= 10
        risks.append("missing_budget")
    else:
        ceiling = budget_max or budget_min or Decimal("0")
        score += 12 + min(float(ceiling), 25.0) * 0.7
        reasons.append("has_usdc_budget")

    overlap = sorted((tags | {category}) & skills)
    if overlap:
        score += min(len(overlap) * 7, 24)
        reasons.append("skill_overlap:" + ",".join(overlap))
    elif category in GOOD_CATEGORIES:
        score += 8
        reasons.append("good_category")
    elif category in WEAK_CATEGORIES:
        score += 3
        risks.append("weak_category_fit")
    else:
        risks.append("weak_skill_fit")

    if acceptance:
        score += 12
        reasons.append("clear_acceptance")
    else:
        score -= 3
        risks.append("missing_acceptance_criteria")

    one_shot_hits = [keyword for keyword in ONE_SHOT_KEYWORDS if keyword in text]
    if one_shot_hits:
        score += 14
        reasons.append("one_shot_deliverable:" + ",".join(sorted(set(one_shot_hits))[:4]))

    long_hits = [keyword for keyword in LONG_RUNNING_KEYWORDS if keyword in text]
    if long_hits:
        score -= 18
        risks.append("long_running_or_infra_heavy:" + ",".join(sorted(set(long_hits))[:4]))

    if "youtube" in text and "url" not in text and "http" not in text:
        score -= 8
        risks.append("missing_external_input_url")

    if budget_max is not None and budget_max < Decimal("1"):
        score -= 10
        risks.append("too_small_for_tokens")

    rounded = round(max(score, 0.0), 1)
    if rounded >= 60 and not any(risk.startswith("long_running") for risk in risks):
        decision = "take_first"
    elif rounded >= 42:
        decision = "manual_review"
    else:
        decision = "reject"
    return ScoredNeed(need, rounded, decision, tuple(reasons), tuple(risks))


def rank_needs(needs: list[dict[str, Any]], *, skills: set[str] | None = None) -> list[dict[str, Any]]:
    scored = [score_need(need, skills=skills) for need in needs]
    ranked = sorted(scored, key=lambda item: (item.decision == "take_first", item.score), reverse=True)
    return [
        {
            "need_id": item.need.get("id"),
            "title": item.need.get("title"),
            "buyerAgentId": item.need.get("agent_id"),
            "category": item.need.get("category"),
            "tags": item.need.get("tags") if isinstance(item.need.get("tags"), list) else [],
            "budget_min": item.need.get("budget_min"),
            "budget_max": item.need.get("budget_max"),
            "currency": item.need.get("currency"),
            "decision": item.decision,
            "score": item.score,
            "reasons": list(item.reasons),
            "risks": list(item.risks),
            "acceptance": parse_acceptance(item.need.get("acceptance_criteria")),
            "description_md": item.need.get("description_md"),
            "created_at": item.need.get("created_at"),
        }
        for item in ranked
    ]


def _choose_price(need: dict[str, Any], offer_base_price: Decimal) -> Decimal:
    budget_min = _decimal_or_none(need.get("budget_min")) or Decimal("0")
    budget_max = _decimal_or_none(need.get("budget_max"))
    if budget_max is not None and offer_base_price > budget_max:
        return budget_max
    if offer_base_price < budget_min:
        return budget_min
    return offer_base_price


def build_deal_proposal(
    need: dict[str, Any],
    *,
    seller_agent_id: str,
    offer_id: str,
    offer_base_price: Decimal = Decimal("5"),
) -> dict[str, Any]:
    price = _choose_price(need, offer_base_price)
    acceptance = parse_acceptance(need.get("acceptance_criteria")) or [
        "Structured report or working artifact delivered",
    ]
    title = str(need.get("title") or "AgentPact delivery")
    return {
        "buyerAgentId": str(need["agent_id"]),
        "sellerAgentId": seller_agent_id,
        "offerId": offer_id,
        "needId": str(need["id"]),
        "negotiatedTotal": _money_float(price),
        "maxPriceDeltaPct": 0,
        "milestones": [
            {
                "idx": 1,
                "title": f"Deliver: {title[:96]}",
                "amount": _money_float(price),
                "acceptanceCriteria": acceptance,
            }
        ],
    }


def build_selection_packet(
    needs: list[dict[str, Any]],
    *,
    seller_agent_id: str,
    offer_id: str,
    offer_base_price: Decimal = Decimal("5"),
    skills: set[str] | None = None,
    top: int = 10,
) -> dict[str, Any]:
    ranked = rank_needs(needs, skills=skills)
    selected = next((item for item in ranked if item["decision"] == "take_first"), None)
    proposal = None
    if selected:
        source_need = next(need for need in needs if need.get("id") == selected["need_id"])
        proposal = build_deal_proposal(
            source_need,
            seller_agent_id=seller_agent_id,
            offer_id=offer_id,
            offer_base_price=offer_base_price,
        )
    return {
        "schema": SCHEMA,
        "claim_boundary": CLAIM_BOUNDARY,
        "sellerAgentId": seller_agent_id,
        "offerId": offer_id,
        "offer_base_price": _money_float(offer_base_price),
        "needs_total": len(needs),
        "take_first_total": sum(1 for item in ranked if item["decision"] == "take_first"),
        "manual_review_total": sum(1 for item in ranked if item["decision"] == "manual_review"),
        "reject_total": sum(1 for item in ranked if item["decision"] == "reject"),
        "selected_need": selected,
        "proposal_payload": proposal,
        "ranked": ranked[:top],
    }
