"""Unit tests for MeshActionEnforcer (action_enforcer.py)."""
import pytest
from unittest.mock import MagicMock, patch, call


@pytest.fixture(autouse=True)
def mock_optimizer():
    with patch("src.mesh.action_enforcer.get_optimizer") as mock_get:
        mock_get.return_value = MagicMock()
        yield mock_get


class TestMeshActionEnforcer:
    def _make_enforcer(self):
        from src.mesh.action_enforcer import MeshActionEnforcer
        return MeshActionEnforcer()

    def test_init_gets_optimizer(self, mock_optimizer):
        enforcer = self._make_enforcer()
        mock_optimizer.assert_called_once()

    def test_enforce_empty_recommendations(self):
        enforcer = self._make_enforcer()
        # Should not raise
        enforcer.enforce_recommendations([])

    def test_enforce_refresh_calls_restart_peer(self):
        enforcer = self._make_enforcer()
        with patch.object(enforcer, "_restart_peer") as mock_restart:
            enforcer.enforce_recommendations([
                {"action": "refresh", "route_id": "direct-10.0.0.1:9000"}
            ])
            mock_restart.assert_called_once_with("direct-10.0.0.1:9000")

    def test_enforce_investigate_does_not_call_restart(self):
        enforcer = self._make_enforcer()
        with patch.object(enforcer, "_restart_peer") as mock_restart:
            enforcer.enforce_recommendations([
                {"action": "investigate", "route_id": "direct-10.0.0.1:9000"}
            ])
            mock_restart.assert_not_called()

    def test_enforce_unknown_action_ignored(self):
        enforcer = self._make_enforcer()
        with patch.object(enforcer, "_restart_peer") as mock_restart:
            enforcer.enforce_recommendations([
                {"action": "unknown_action", "route_id": "direct-10.0.0.1:9000"}
            ])
            mock_restart.assert_not_called()

    def test_enforce_multiple_recommendations(self):
        enforcer = self._make_enforcer()
        with patch.object(enforcer, "_restart_peer") as mock_restart:
            enforcer.enforce_recommendations([
                {"action": "refresh", "route_id": "direct-10.0.0.1"},
                {"action": "investigate", "route_id": "direct-10.0.0.2"},
                {"action": "refresh", "route_id": "direct-10.0.0.3"},
            ])
            assert mock_restart.call_count == 2

    def test_enforce_missing_action_key_ignored(self):
        enforcer = self._make_enforcer()
        with patch.object(enforcer, "_restart_peer") as mock_restart:
            enforcer.enforce_recommendations([{"route_id": "direct-10.0.0.1"}])
            mock_restart.assert_not_called()


class TestRestartPeer:
    def _make_enforcer(self):
        from src.mesh.action_enforcer import MeshActionEnforcer
        return MeshActionEnforcer()

    def test_non_direct_route_is_skipped(self):
        enforcer = self._make_enforcer()
        # Should not raise and should do nothing
        enforcer._restart_peer("indirect-10.0.0.1")

    def test_direct_route_extracts_peer_addr(self):
        enforcer = self._make_enforcer()
        # Currently a no-op pass, just verify no exception
        enforcer._restart_peer("direct-10.0.0.1:9000")

    def test_empty_route_id_skipped(self):
        enforcer = self._make_enforcer()
        enforcer._restart_peer("")
