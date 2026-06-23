"""
Unit tests for MAPE-K Formal Logic Contract and SafeMode transitions.
"""

import unittest
from src.self_healing.mape_k.manager import SelfHealingManager
from src.self_healing.mape_k.logic_contract import FormalState

class TestMAPEKFormalLogic(unittest.TestCase):
    def setUp(self):
        self.manager = SelfHealingManager(node_id="test-node", action_cooldown_seconds=1.0)

    def test_normal_cycle_transitions(self):
        """Test that a healthy cycle keeps the logic contract in IDLE."""
        metrics = {"packet_loss_percent": 0.0}
        self.manager.run_cycle(metrics)
        self.assertEqual(self.manager.logic_contract.current_state, FormalState.IDLE)
        self.assertFalse(self.manager.logic_contract.is_in_safe_mode())

    def test_invariant_v1_concurrent_recovery(self):
        """Test I1: No Concurrent Recovery violation."""
        # 1. Get into PLANNING state normally
        self.manager.logic_contract.transition_to(FormalState.ANALYZING, {})
        self.manager.logic_contract.transition_to(FormalState.PLANNING, {})
        self.assertEqual(self.manager.logic_contract.current_state, FormalState.PLANNING)

        # 2. Inject a pending verification (violating I1 if we proceed to EXECUTING)
        self.manager.pending_verifications["test-node"] = {
            "action": "restart", "issue": "loss", "start_time": 0, "initial_metrics": {}
        }

        # 3. Attempt to transition to EXECUTING
        self.manager.logic_contract.transition_to(
            FormalState.EXECUTING,
            {"pending_verification": True}
        )

        # Check if SAFE_MODE was entered due to I1 violation
        self.assertTrue(self.manager.logic_contract.is_in_safe_mode())
        self.assertEqual(self.manager.logic_contract.violations[0].invariant_id, "I1")

    def test_invalid_state_transition(self):
        """Test that skipping a state (e.g. IDLE -> EXECUTING) triggers SAFE_MODE."""
        # This is harder to trigger via run_cycle, so we test the contract directly
        contract = self.manager.logic_contract
        self.assertEqual(contract.current_state, FormalState.IDLE)

        # Attempt to jump to EXECUTING
        contract.transition_to(FormalState.EXECUTING, {})
        self.assertTrue(contract.is_in_safe_mode())
        self.assertEqual(contract.violations[0].invariant_id, "ASM_VALIDATION")

if __name__ == "__main__":
    unittest.main()
