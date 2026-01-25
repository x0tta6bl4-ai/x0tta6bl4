"""
Unit tests for SelfHealingManager
"""

import pytest
from unittest.mock import Mock, patch
from src.self_healing.mape_k import SelfHealingManager


class TestSelfHealingManager:
    """Test SelfHealingManager functionality"""

    def test_self_healing_manager_initialization(self):
        """Test SelfHealingManager can be initialized"""
        manager = SelfHealingManager()
        assert manager is not None
        assert manager.node_id == "default"
        assert manager.monitor is not None
        assert manager.analyzer is not None
        assert manager.planner is not None
        assert manager.executor is not None
        assert manager.knowledge is not None

    def test_self_healing_manager_custom_node_id(self):
        """Test SelfHealingManager with custom node ID"""
        manager = SelfHealingManager(node_id="test_node")
        assert manager.node_id == "test_node"

    def test_run_cycle_no_anomalies(self):
        """Test run_cycle with no anomalies detected"""
        manager = SelfHealingManager()

        # Mock monitor to return no anomalies
        with patch.object(manager.monitor, 'check', return_value=False):
            # Should not trigger analysis/planning/execution
            manager.run_cycle({'cpu_percent': 10, 'memory_percent': 20})

            # Knowledge should still be empty (no incidents recorded)
            assert len(manager.knowledge.incidents) == 0

    def test_run_cycle_with_anomalies(self):
        """Test run_cycle with anomalies detected"""
        manager = SelfHealingManager()

        # Mock components
        with patch.object(manager.monitor, 'check', return_value=True), \
             patch.object(manager.analyzer, 'analyze', return_value='High CPU'), \
             patch.object(manager.planner, 'plan', return_value='Restart service'), \
             patch.object(manager.executor, 'execute', return_value=True):

            metrics = {'cpu_percent': 95, 'memory_percent': 20}
            manager.run_cycle(metrics)

            # Should have recorded the incident
            assert len(manager.knowledge.incidents) == 1
            incident = manager.knowledge.incidents[0]
            assert incident['issue'] == 'High CPU'
            assert incident['action'] == 'Restart service'
            assert incident['success'] == True

    def test_feedback_loop_tracking(self):
        """Test that feedback loop statistics are tracked"""
        manager = SelfHealingManager()

        initial_updates = manager.feedback_updates
        initial_adjustments = manager.threshold_adjustments
        initial_improvements = manager.strategy_improvements

        # Run a cycle
        with patch.object(manager.monitor, 'check', return_value=True), \
             patch.object(manager.analyzer, 'analyze', return_value='High CPU'), \
             patch.object(manager.planner, 'plan', return_value='Restart service'), \
             patch.object(manager.executor, 'execute', return_value=True):

            manager.run_cycle({'cpu_percent': 95})

        # Feedback should be updated
        assert manager.feedback_updates > initial_updates

    def test_get_feedback_stats(self):
        """Test get_feedback_stats returns proper structure"""
        manager = SelfHealingManager()
        stats = manager.get_feedback_stats()

        required_keys = [
            'feedback_updates',
            'threshold_adjustments',
            'strategy_improvements',
            'knowledge_base_size',
            'successful_patterns',
            'failed_patterns'
        ]

        for key in required_keys:
            assert key in stats
            assert isinstance(stats[key], int)

    def test_threshold_manager_integration(self):
        """Test integration with threshold manager"""
        mock_threshold_manager = Mock()
        mock_threshold_manager.get_threshold.return_value = 80.0

        manager = SelfHealingManager(threshold_manager=mock_threshold_manager)

        # Threshold manager should be passed to monitor
        assert manager.threshold_manager is mock_threshold_manager
        assert manager.monitor.threshold_manager is mock_threshold_manager