"""Unit tests for DAOEnforcer (dao_enforcement.py)."""
import json
import pytest
from unittest.mock import MagicMock, patch


@pytest.fixture(autouse=True)
def mock_optimizer():
    with patch("src.services.dao_enforcement.get_optimizer") as mock_get:
        optimizer = MagicMock()
        optimizer.config = MagicMock()
        mock_get.return_value = optimizer
        yield mock_get, optimizer


class TestDAOEnforcer:
    def _make_enforcer(self):
        from src.services.dao_enforcement import DAOEnforcer
        return DAOEnforcer()

    def _make_db(self, proposals):
        db = MagicMock()
        db.query.return_value.filter.return_value.order_by.return_value.limit.return_value.all.return_value = proposals
        return db

    def test_sync_returns_true(self, mock_optimizer):
        db = self._make_db([])
        enforcer = self._make_enforcer()
        assert enforcer.sync_config_with_dao(db) is True

    def test_empty_proposals_no_setattr(self, mock_optimizer):
        _, optimizer = mock_optimizer
        db = self._make_db([])
        enforcer = self._make_enforcer()
        result = enforcer.sync_config_with_dao(db)
        # No proposals → config unchanged, still returns True
        assert result is True

    def test_update_config_action_applies_value(self, mock_optimizer):
        _, optimizer = mock_optimizer
        config = MagicMock(spec=["latency_threshold"])
        config.latency_threshold = 100
        optimizer.config = config

        proposal = MagicMock()
        proposal.actions_json = json.dumps([{
            "type": "update_config",
            "params": {"key": "latency_threshold", "value": 200}
        }])
        db = self._make_db([proposal])
        enforcer = self._make_enforcer()
        enforcer.sync_config_with_dao(db)

        assert config.latency_threshold == 200

    def test_non_update_config_action_ignored(self, mock_optimizer):
        _, optimizer = mock_optimizer
        config = MagicMock(spec=["latency_threshold"])
        config.latency_threshold = 100
        optimizer.config = config

        proposal = MagicMock()
        proposal.actions_json = json.dumps([{
            "type": "announce",
            "params": {"key": "latency_threshold", "value": 999}
        }])
        db = self._make_db([proposal])
        enforcer = self._make_enforcer()
        enforcer.sync_config_with_dao(db)

        assert config.latency_threshold == 100

    def test_none_actions_json_skipped(self, mock_optimizer):
        _, optimizer = mock_optimizer
        proposal = MagicMock()
        proposal.actions_json = None
        db = self._make_db([proposal])
        enforcer = self._make_enforcer()
        # Should not raise
        result = enforcer.sync_config_with_dao(db)
        assert result is True

    def test_unknown_config_key_ignored(self, mock_optimizer):
        _, optimizer = mock_optimizer
        config = MagicMock(spec=[])  # No attributes
        optimizer.config = config

        proposal = MagicMock()
        proposal.actions_json = json.dumps([{
            "type": "update_config",
            "params": {"key": "nonexistent_key", "value": 42}
        }])
        db = self._make_db([proposal])
        enforcer = self._make_enforcer()
        # Should not raise
        enforcer.sync_config_with_dao(db)

    def test_multiple_proposals_all_applied(self, mock_optimizer):
        _, optimizer = mock_optimizer
        config = MagicMock(spec=["alpha", "beta"])
        config.alpha = 1
        config.beta = 2
        optimizer.config = config

        p1 = MagicMock()
        p1.actions_json = json.dumps([{"type": "update_config", "params": {"key": "alpha", "value": 10}}])
        p2 = MagicMock()
        p2.actions_json = json.dumps([{"type": "update_config", "params": {"key": "beta", "value": 20}}])

        db = self._make_db([p1, p2])
        enforcer = self._make_enforcer()
        enforcer.sync_config_with_dao(db)

        assert config.alpha == 10
        assert config.beta == 20

    def test_optimizer_config_updated_after_sync(self, mock_optimizer):
        _, optimizer = mock_optimizer
        db = self._make_db([])
        enforcer = self._make_enforcer()
        enforcer.sync_config_with_dao(db)
        # optimizer.config should be assigned back
        assert optimizer.config is not None
