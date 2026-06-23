from __future__ import annotations

from src.sales.non_bounty_income import build_non_bounty_income_map


def test_non_bounty_income_map_ranks_routes_without_money_claims() -> None:
    income_map = build_non_bounty_income_map()

    assert income_map["schema"] == "x0tta6bl4.non_bounty_income_map.v1"
    assert income_map["status"] == "map_ready"
    assert income_map["claim_gate"]["funds_received_claim_allowed"] is False
    assert income_map["claim_gate"]["external_account_access_claim_allowed"] is False
    assert len(income_map["ranked"]) >= 6
    assert income_map["selected_first"]


def test_non_bounty_income_map_selects_agent_and_actor_routes() -> None:
    income_map = build_non_bounty_income_map()
    selected_ids = {item["opportunity_id"] for item in income_map["selected_first"]}
    ranked_ids = {item["opportunity_id"] for item in income_map["ranked"]}

    assert "gate402_x402_catalog" in selected_ids
    assert "x402_paid_micro_api" in selected_ids
    assert "agora402_native_registry" in selected_ids
    assert "agentpact_offer_pack" in ranked_ids
    assert "agent402_api_listing" in ranked_ids
    assert "the402_provider_listing" in ranked_ids
    assert "four_o_two_rest_api_publish" in ranked_ids
    assert "gradient_sentry_rewards" in ranked_ids
    assert "apify_actor_factory" in ranked_ids
