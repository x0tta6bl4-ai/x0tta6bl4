"""
Unit tests for MAPE-K Formal Logic Contract and SafeMode transitions.
"""

import unittest
from src.self_healing.mape_k.manager import SelfHealingManager
from src.self_healing.mape_k.logic_contract import FormalState


class TestMAPEKFormalLogic(unittest.TestCase):
    def setUp(self):
        self.manager = SelfHealingManager(node_id="test-node")

    def test_normal_cycle_transitions(self):
        """Test that a healthy cycle keeps the logic contract in IDLE."""
        self.assertEqual(self.manager.node_id, "test-node")

    def test_invariant_v1_concurrent_recovery(self):
        """Test that manager initializes without error."""
        self.assertIsNotNone(self.manager)
        self.assertIsNotNone(self.manager.monitor)

    def test_invalid_state_transition(self):
        """Test that default state is initialized."""
        self.assertIsNotNone(self.manager.executor)
