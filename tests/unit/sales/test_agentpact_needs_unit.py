from __future__ import annotations

from decimal import Decimal

from src.sales.agentpact_needs import build_deal_proposal, build_selection_packet, parse_acceptance, score_need


def test_parse_acceptance_treats_encoded_empty_list_as_empty() -> None:
    assert parse_acceptance('"[]"') == []
    assert parse_acceptance('["[]"]') == []


def test_score_need_rejects_bounty_and_secret_work() -> None:
    need = {
        "id": "n1",
        "agent_id": "buyer",
        "status": "open",
        "title": "Airdrop sybil helper",
        "description_md": "Need private key automation for airdrop farming",
        "category": "development",
        "tags": ["python"],
        "budget_min": "10",
        "budget_max": "20",
    }

    scored = score_need(need)

    assert scored.decision == "reject"
    assert "hard_reject_keyword" in scored.reasons


def test_selection_prefers_one_shot_data_need_over_realtime_feed() -> None:
    needs = [
        {
            "id": "slow",
            "agent_id": "buyer1",
            "status": "open",
            "title": "Real-time stock market data feed",
            "description_md": "Build a real-time feed and pipeline",
            "category": "data",
            "tags": ["api", "data"],
            "budget_min": "300",
            "budget_max": "800",
            "currency": "USDC",
            "acceptance_criteria": "[\"Working feed\"]",
        },
        {
            "id": "fast",
            "agent_id": "buyer2",
            "status": "open",
            "title": "OHLCV data validation and format check",
            "description_md": "Validate OHLCV JSON and return a report",
            "category": "data",
            "tags": ["data", "json"],
            "budget_min": "5",
            "budget_max": "15",
            "currency": "USDC",
            "acceptance_criteria": "[\"Validation report delivered\"]",
        },
    ]

    packet = build_selection_packet(
        needs,
        seller_agent_id="seller",
        offer_id="offer",
        offer_base_price=Decimal("5"),
    )

    assert packet["selected_need"]["need_id"] == "fast"
    assert packet["proposal_payload"]["buyerAgentId"] == "buyer2"
    assert packet["proposal_payload"]["negotiatedTotal"] == 5.0
    assert packet["proposal_payload"]["milestones"][0]["idx"] == 1


def test_selection_can_rank_for_specific_offer_skills() -> None:
    needs = [
        {
            "id": "python",
            "agent_id": "buyer1",
            "status": "open",
            "title": "Python / Data Task Execution",
            "description_md": "Python coding, data analysis, automation, or API integration task.",
            "category": "development",
            "tags": ["python", "data", "automation", "coding"],
            "budget_min": "5",
            "budget_max": "5",
            "currency": "USDC",
            "acceptance_criteria": "[\"Working code or structured report delivered\"]",
        },
        {
            "id": "api",
            "agent_id": "buyer2",
            "status": "open",
            "title": "Compact API Endpoint Sanity Check",
            "description_md": "Review one public REST API endpoint.",
            "category": "development",
            "tags": ["api", "review", "testing"],
            "budget_min": "1",
            "budget_max": "1",
            "currency": "USDC",
            "acceptance_criteria": "[\"Markdown review report delivered\"]",
        },
    ]

    packet = build_selection_packet(
        needs,
        seller_agent_id="seller",
        offer_id="api-offer",
        offer_base_price=Decimal("1"),
        skills={"api", "review", "testing", "markdown", "reports"},
    )

    assert packet["selected_need"]["need_id"] == "api"
    assert packet["proposal_payload"]["negotiatedTotal"] == 1.0


def test_deal_proposal_caps_price_to_need_budget_max() -> None:
    need = {
        "id": "small",
        "agent_id": "buyer",
        "title": "Compact API endpoint sanity check",
        "budget_min": "1",
        "budget_max": "1",
        "acceptance_criteria": "[\"Report delivered\"]",
    }

    proposal = build_deal_proposal(
        need,
        seller_agent_id="seller",
        offer_id="offer",
        offer_base_price=Decimal("5"),
    )

    assert proposal["negotiatedTotal"] == 1.0
    assert proposal["milestones"][0]["amount"] == 1.0
