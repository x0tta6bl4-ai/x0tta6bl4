"""Summaries for wallet-linked AgentPact earning state."""

from __future__ import annotations

from typing import Any


SCHEMA = "x0tta6bl4.agentpact_wallet_market_watch.v1"
CLAIM_BOUNDARY = (
    "This watch report proves only public profile, offer, match, and deal state "
    "seen through AgentPact API. It does not prove accepted delivery, escrow "
    "release, payout eligibility, on-chain transfer, or received funds."
)


def _field(payload: dict[str, Any], *names: str) -> Any:
    for name in names:
        if name in payload:
            return payload[name]
    return None


def filter_own_offers(offers: list[dict[str, Any]], agent_id: str) -> list[dict[str, Any]]:
    return [offer for offer in offers if str(offer.get("agent_id") or offer.get("agentId") or "") == agent_id]


def filter_own_deals(deals: list[dict[str, Any]], agent_id: str, offer_ids: set[str]) -> list[dict[str, Any]]:
    own: list[dict[str, Any]] = []
    for deal in deals:
        seller_id = str(_field(deal, "seller_agent_id", "sellerAgentId") or "")
        buyer_id = str(_field(deal, "buyer_agent_id", "buyerAgentId") or "")
        offer_id = str(_field(deal, "offer_id", "offerId") or "")
        if seller_id == agent_id or buyer_id == agent_id or offer_id in offer_ids:
            own.append(deal)
    return own


def summarize_wallet_market_state(
    *,
    agent_id: str,
    expected_wallet: str,
    profile: dict[str, Any],
    offers: list[dict[str, Any]],
    matches: list[dict[str, Any]],
    deals: list[dict[str, Any]],
) -> dict[str, Any]:
    own_offers = filter_own_offers(offers, agent_id)
    active_offers = [offer for offer in own_offers if str(offer.get("status") or "").lower() == "active"]
    offer_ids = {str(offer.get("id")) for offer in own_offers if offer.get("id")}
    own_matches = [match for match in matches if str(match.get("offer_id") or match.get("offerId") or "") in offer_ids]
    own_deals = filter_own_deals(deals, agent_id, offer_ids)
    wallet = str(profile.get("owner_wallet_address") or profile.get("ownerWalletAddress") or "")
    wallet_ready = wallet.lower() == expected_wallet.lower()

    if own_deals:
        action = "inspect_deal_and_deliver"
    elif own_matches:
        action = "wait_for_buyer_accept_or_platform_auto_deal"
    elif active_offers:
        action = "wait_for_match_or_recompute"
    elif wallet_ready:
        action = "publish_offer"
    else:
        action = "fix_wallet_profile"

    return {
        "schema": SCHEMA,
        "claim_boundary": CLAIM_BOUNDARY,
        "agentId": agent_id,
        "expected_wallet": expected_wallet,
        "profile_wallet": wallet or None,
        "wallet_ready": wallet_ready,
        "offers_total": len(own_offers),
        "active_offers_total": len(active_offers),
        "matches_total": len(own_matches),
        "deals_total": len(own_deals),
        "next_action": action,
        "top_matches": own_matches[:10],
        "own_deals": own_deals,
        "active_offers": [
            {
                "id": offer.get("id"),
                "title": offer.get("title"),
                "base_price": offer.get("base_price") or offer.get("basePrice"),
                "currency": offer.get("currency"),
                "status": offer.get("status"),
                "completed_deal_count": offer.get("completed_deal_count") or offer.get("completedDealCount"),
            }
            for offer in active_offers
        ],
    }
