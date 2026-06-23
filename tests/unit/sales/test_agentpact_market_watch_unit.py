from __future__ import annotations

from src.sales.agentpact_market_watch import summarize_wallet_market_state


def test_summarize_wallet_market_state_detects_ready_match() -> None:
    summary = summarize_wallet_market_state(
        agent_id="agent-1",
        expected_wallet="0x6017613e80d7893EB2aD5c0585b3f1f88CD6e099",
        profile={
            "owner_wallet_address": "0x6017613e80d7893EB2aD5c0585b3f1f88CD6e099",
        },
        offers=[
            {
                "id": "offer-1",
                "agent_id": "agent-1",
                "status": "active",
                "title": "Python data",
                "base_price": "5.000000",
                "currency": "USDC",
            }
        ],
        matches=[
            {
                "id": "match-1",
                "offer_id": "offer-1",
                "need_id": "need-1",
                "score": "0.600",
            },
            {
                "id": "other-match",
                "offer_id": "other-offer",
                "need_id": "need-2",
                "score": "1.000",
            },
        ],
        deals=[],
    )

    assert summary["wallet_ready"] is True
    assert summary["active_offers_total"] == 1
    assert summary["matches_total"] == 1
    assert summary["deals_total"] == 0
    assert summary["next_action"] == "wait_for_buyer_accept_or_platform_auto_deal"


def test_summarize_wallet_market_state_prioritizes_deal_delivery() -> None:
    summary = summarize_wallet_market_state(
        agent_id="agent-1",
        expected_wallet="0xabc",
        profile={"owner_wallet_address": "0xabc"},
        offers=[{"id": "offer-1", "agent_id": "agent-1", "status": "active"}],
        matches=[],
        deals=[{"id": "deal-1", "seller_agent_id": "agent-1", "offer_id": "offer-1"}],
    )

    assert summary["deals_total"] == 1
    assert summary["next_action"] == "inspect_deal_and_deliver"
