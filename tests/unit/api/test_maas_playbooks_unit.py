"""Unit tests for src/api/maas_playbooks.py — pure logic helpers and Pydantic models."""

from __future__ import annotations

from datetime import datetime, timedelta
from typing import Any, Dict, List
from unittest.mock import MagicMock

import pytest

from src.api.maas_playbooks import (
    PlaybookAction,
    PlaybookCreateRequest,
    _db_query_available,
    _db_session_available,
    _is_expired,
    _normalize_target_nodes,
    _queue_playbook_for_targets,
    _node_queues,
    _playbook_deliveries,
    _playbook_store,
)


# ---------------------------------------------------------------------------
# Helpers to isolate module-level state
# ---------------------------------------------------------------------------

import importlib
import src.api.maas_playbooks as _mod


def _clear_state():
    _mod._playbook_store.clear()
    _mod._node_queues.clear()
    _mod._playbook_acks.clear()
    _mod._playbook_deliveries.clear()


# ---------------------------------------------------------------------------
# _db_session_available
# ---------------------------------------------------------------------------


class TestDbSessionAvailable:
    def test_true_when_has_add_and_commit(self):
        db = MagicMock(spec=["add", "commit"])
        assert _db_session_available(db) is True

    def test_false_when_missing_add(self):
        db = MagicMock(spec=["commit"])
        assert _db_session_available(db) is False

    def test_false_when_missing_commit(self):
        db = MagicMock(spec=["add"])
        assert _db_session_available(db) is False

    def test_false_for_plain_dict(self):
        assert _db_session_available({}) is False

    def test_false_for_none(self):
        assert _db_session_available(None) is False


# ---------------------------------------------------------------------------
# _db_query_available
# ---------------------------------------------------------------------------


class TestDbQueryAvailable:
    def test_true_when_full_session(self):
        db = MagicMock(spec=["add", "commit", "query"])
        assert _db_query_available(db) is True

    def test_false_when_missing_query(self):
        db = MagicMock(spec=["add", "commit"])
        assert _db_query_available(db) is False

    def test_false_for_none(self):
        assert _db_query_available(None) is False


# ---------------------------------------------------------------------------
# _is_expired
# ---------------------------------------------------------------------------


class TestIsExpired:
    def test_not_expired_future_datetime(self):
        pb = {"expires_at": datetime.utcnow() + timedelta(hours=1)}
        assert _is_expired(pb, datetime.utcnow()) is False

    def test_expired_past_datetime(self):
        pb = {"expires_at": datetime.utcnow() - timedelta(hours=1)}
        assert _is_expired(pb, datetime.utcnow()) is True

    def test_expired_iso_string(self):
        past = (datetime.utcnow() - timedelta(hours=2)).isoformat()
        pb = {"expires_at": past}
        assert _is_expired(pb, datetime.utcnow()) is True

    def test_not_expired_iso_string(self):
        future = (datetime.utcnow() + timedelta(hours=2)).isoformat()
        pb = {"expires_at": future}
        assert _is_expired(pb, datetime.utcnow()) is False

    def test_missing_expires_at_not_expired(self):
        assert _is_expired({}, datetime.utcnow()) is False

    def test_none_expires_at_not_expired(self):
        assert _is_expired({"expires_at": None}, datetime.utcnow()) is False

    def test_malformed_expires_at_treated_as_expired(self):
        pb = {"expires_at": "not-a-date"}
        assert _is_expired(pb, datetime.utcnow()) is True

    def test_exactly_at_expiry_is_expired(self):
        now = datetime.utcnow()
        pb = {"expires_at": now}
        assert _is_expired(pb, now) is True


# ---------------------------------------------------------------------------
# _normalize_target_nodes
# ---------------------------------------------------------------------------


class TestNormalizeTargetNodes:
    def test_list_of_strings(self):
        result = _normalize_target_nodes(["node-1", "node-2"])
        assert result == ["node-1", "node-2"]

    def test_empty_list(self):
        assert _normalize_target_nodes([]) == []

    def test_non_list_returns_empty(self):
        assert _normalize_target_nodes("node-1") == []
        assert _normalize_target_nodes(None) == []
        assert _normalize_target_nodes(42) == []

    def test_filters_non_string_items(self):
        result = _normalize_target_nodes(["node-1", 42, None, "node-2"])
        assert result == ["node-1", "node-2"]

    def test_filters_empty_strings(self):
        result = _normalize_target_nodes(["", "node-1", ""])
        assert result == ["node-1"]

    def test_converts_strings(self):
        result = _normalize_target_nodes(["node-abc"])
        assert all(isinstance(n, str) for n in result)


# ---------------------------------------------------------------------------
# _queue_playbook_for_targets
# ---------------------------------------------------------------------------


class TestQueuePlaybookForTargets:
    def setup_method(self):
        _clear_state()

    def test_queues_playbook_for_each_node(self):
        _queue_playbook_for_targets("pb-1", ["node-a", "node-b"])
        assert "pb-1" in _mod._node_queues.get("node-a", [])
        assert "pb-1" in _mod._node_queues.get("node-b", [])

    def test_does_not_duplicate_in_queue(self):
        _queue_playbook_for_targets("pb-2", ["node-c"])
        _queue_playbook_for_targets("pb-2", ["node-c"])
        assert _mod._node_queues["node-c"].count("pb-2") == 1

    def test_already_delivered_node_skipped(self):
        _mod._playbook_deliveries["pb-3"] = {"node-d"}
        _queue_playbook_for_targets("pb-3", ["node-d"])
        # node-d already delivered — queue should remain empty for pb-3
        assert "pb-3" not in _mod._node_queues.get("node-d", [])

    def test_empty_targets_nothing_queued(self):
        _queue_playbook_for_targets("pb-4", [])
        assert "node-any" not in _mod._node_queues


# ---------------------------------------------------------------------------
# PlaybookAction model
# ---------------------------------------------------------------------------


class TestPlaybookAction:
    def test_restart_action(self):
        a = PlaybookAction(action="restart")
        assert a.action == "restart"

    def test_upgrade_action(self):
        a = PlaybookAction(action="upgrade", params={"version": "2.0"})
        assert a.params["version"] == "2.0"

    def test_update_config_action(self):
        a = PlaybookAction(action="update_config")
        assert a.action == "update_config"

    def test_exec_action(self):
        a = PlaybookAction(action="exec", params={"cmd": "echo hi"})
        assert a.params["cmd"] == "echo hi"

    def test_ban_peer_action(self):
        a = PlaybookAction(action="ban_peer")
        assert a.action == "ban_peer"

    def test_invalid_action_raises(self):
        with pytest.raises(Exception):
            PlaybookAction(action="deploy_malware")

    def test_params_defaults_to_empty_dict(self):
        a = PlaybookAction(action="restart")
        assert a.params == {}


# ---------------------------------------------------------------------------
# PlaybookCreateRequest model
# ---------------------------------------------------------------------------


class TestPlaybookCreateRequest:
    def _action(self) -> PlaybookAction:
        return PlaybookAction(action="restart")

    def test_valid_request(self):
        req = PlaybookCreateRequest(
            name="my-playbook",
            target_nodes=["node-1"],
            actions=[self._action()],
        )
        assert req.name == "my-playbook"
        assert req.expires_in_sec == 3600

    def test_name_too_short_raises(self):
        with pytest.raises(Exception):
            PlaybookCreateRequest(
                name="ab",
                target_nodes=["node-1"],
                actions=[self._action()],
            )

    def test_empty_target_nodes_raises(self):
        with pytest.raises(Exception):
            PlaybookCreateRequest(
                name="my-playbook",
                target_nodes=[],
                actions=[self._action()],
            )

    def test_empty_actions_raises(self):
        with pytest.raises(Exception):
            PlaybookCreateRequest(
                name="my-playbook",
                target_nodes=["node-1"],
                actions=[],
            )

    def test_expires_in_sec_below_min_raises(self):
        with pytest.raises(Exception):
            PlaybookCreateRequest(
                name="my-playbook",
                target_nodes=["node-1"],
                actions=[self._action()],
                expires_in_sec=30,
            )

    def test_expires_in_sec_above_max_raises(self):
        with pytest.raises(Exception):
            PlaybookCreateRequest(
                name="my-playbook",
                target_nodes=["node-1"],
                actions=[self._action()],
                expires_in_sec=90000,
            )

    def test_expires_in_sec_at_min_boundary(self):
        req = PlaybookCreateRequest(
            name="my-playbook",
            target_nodes=["node-1"],
            actions=[self._action()],
            expires_in_sec=60,
        )
        assert req.expires_in_sec == 60

    def test_expires_in_sec_at_max_boundary(self):
        req = PlaybookCreateRequest(
            name="my-playbook",
            target_nodes=["node-1"],
            actions=[self._action()],
            expires_in_sec=86400,
        )
        assert req.expires_in_sec == 86400

    def test_multiple_actions(self):
        req = PlaybookCreateRequest(
            name="multi-action",
            target_nodes=["node-1", "node-2"],
            actions=[self._action(), PlaybookAction(action="upgrade")],
        )
        assert len(req.actions) == 2
        assert len(req.target_nodes) == 2
