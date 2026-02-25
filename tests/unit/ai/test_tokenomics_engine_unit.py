"""Unit tests for AdaptiveRewardEngine (tokenomics_engine.py)."""
import pytest
from src.ai.tokenomics_engine import AdaptiveRewardEngine


class TestAdaptiveRewardEngineInit:
    def test_default_target_inflation(self):
        e = AdaptiveRewardEngine()
        assert e.target_inflation == 0.02

    def test_default_current_reward(self):
        e = AdaptiveRewardEngine()
        assert e.current_reward == 0.00001

    def test_custom_target_inflation(self):
        e = AdaptiveRewardEngine(target_inflation=0.05)
        assert e.target_inflation == 0.05


class TestCalculateNewParameters:
    def setup_method(self):
        self.engine = AdaptiveRewardEngine()

    def test_no_inflation_no_change(self):
        result = self.engine.calculate_new_parameters({
            "circulating_supply_growth_rate": 0.01,
            "burn_to_earn_ratio": 0.9,
        })
        assert result["relay_reward_x0t"] == self.engine.current_reward
        assert result["action_required"] is False

    def test_high_inflation_halves_reward(self):
        original = self.engine.current_reward
        result = self.engine.calculate_new_parameters({
            "circulating_supply_growth_rate": 0.05,
            "burn_to_earn_ratio": 0.9,
        })
        assert result["relay_reward_x0t"] == original * 0.5
        assert result["action_required"] is True

    def test_reward_floor_not_below_minimum(self):
        self.engine.current_reward = 0.0000015
        result = self.engine.calculate_new_parameters({
            "circulating_supply_growth_rate": 0.99,
            "burn_to_earn_ratio": 0.9,
        })
        assert result["relay_reward_x0t"] >= 0.000001

    def test_low_burn_ratio_increases_burn_pct(self):
        result = self.engine.calculate_new_parameters({
            "circulating_supply_growth_rate": 0.0,
            "burn_to_earn_ratio": 0.5,
        })
        assert result["resource_burn_pct"] > 0.01

    def test_burn_pct_capped_at_10_percent(self):
        result = self.engine.calculate_new_parameters({
            "circulating_supply_growth_rate": 0.0,
            "burn_to_earn_ratio": 0.0,
        })
        assert result["resource_burn_pct"] <= 0.10

    def test_normal_burn_ratio_keeps_default_burn(self):
        result = self.engine.calculate_new_parameters({
            "circulating_supply_growth_rate": 0.0,
            "burn_to_earn_ratio": 0.85,
        })
        assert result["resource_burn_pct"] == 0.01

    def test_empty_metrics_use_defaults(self):
        result = self.engine.calculate_new_parameters({})
        assert "relay_reward_x0t" in result
        assert "resource_burn_pct" in result
        assert "action_required" in result
        assert result["relay_reward_x0t"] == self.engine.current_reward

    def test_exact_inflation_threshold_no_change(self):
        # growth_rate == target_inflation → no reduction
        result = self.engine.calculate_new_parameters({
            "circulating_supply_growth_rate": 0.02,
            "burn_to_earn_ratio": 0.9,
        })
        assert result["action_required"] is False

    def test_both_conditions_triggered(self):
        result = self.engine.calculate_new_parameters({
            "circulating_supply_growth_rate": 0.99,
            "burn_to_earn_ratio": 0.0,
        })
        assert result["relay_reward_x0t"] < self.engine.current_reward
        assert result["resource_burn_pct"] == 0.10


class TestGenerateDaoProposal:
    def setup_method(self):
        self.engine = AdaptiveRewardEngine()

    def test_proposal_has_title(self):
        proposal = self.engine.generate_dao_proposal({
            "relay_reward_x0t": 0.000005,
            "resource_burn_pct": 0.05,
        })
        assert "title" in proposal
        assert isinstance(proposal["title"], str)

    def test_proposal_has_two_actions(self):
        proposal = self.engine.generate_dao_proposal({
            "relay_reward_x0t": 0.000005,
            "resource_burn_pct": 0.05,
        })
        assert len(proposal["actions"]) == 2

    def test_relay_reward_action(self):
        proposal = self.engine.generate_dao_proposal({
            "relay_reward_x0t": 0.000005,
            "resource_burn_pct": 0.05,
        })
        relay = proposal["actions"][0]
        assert relay["parameter"] == "relay_reward"
        assert relay["new_value"] == 0.000005

    def test_burn_rate_action(self):
        proposal = self.engine.generate_dao_proposal({
            "relay_reward_x0t": 0.000005,
            "resource_burn_pct": 0.07,
        })
        burn = proposal["actions"][1]
        assert burn["parameter"] == "burn_rate"
        assert burn["new_value"] == 0.07

    def test_proposal_has_rationale(self):
        proposal = self.engine.generate_dao_proposal({
            "relay_reward_x0t": 0.000005,
            "resource_burn_pct": 0.05,
        })
        assert "rationale" in proposal
