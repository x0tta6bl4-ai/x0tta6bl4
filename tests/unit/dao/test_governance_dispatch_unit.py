"""
Unit tests for DAO governance action dispatcher and ledger.
"""

import json
import time
from pathlib import Path

import pytest

from src.dao.governance import (ActionDispatcher, ActionResult,
                                GovernanceEngine, ProposalState, VoteType)


class TestActionResult:
    def test_success_result(self):
        r = ActionResult("restart_node", True, "ok")
        assert r.success is True
        assert r.action_type == "restart_node"
        assert r.detail == "ok"

    def test_failure_result(self):
        r = ActionResult("unknown", False, "err")
        assert r.success is False


class TestActionDispatcher:
    def setup_method(self):
        self.dispatcher = ActionDispatcher()

    def test_restart_node(self):
        result = self.dispatcher.dispatch({"type": "restart_node", "node_id": "node-1"})
        assert result.success is True
        assert "node-1" in result.detail

    def test_restart_node_missing_id(self):
        result = self.dispatcher.dispatch({"type": "restart_node"})
        assert result.success is False
        assert "missing" in result.detail

    def test_rotate_keys(self):
        result = self.dispatcher.dispatch({"type": "rotate_keys", "scope": "mesh"})
        assert result.success is True
        assert "mesh" in result.detail

    def test_rotate_keys_default_scope(self):
        result = self.dispatcher.dispatch({"type": "rotate_keys"})
        assert result.success is True
        assert "all" in result.detail

    def test_update_threshold(self):
        result = self.dispatcher.dispatch({"type": "update_threshold", "value": 0.8})
        assert result.success is True
        assert "0.8" in result.detail

    def test_update_threshold_missing_value(self):
        result = self.dispatcher.dispatch({"type": "update_threshold"})
        assert result.success is False

    def test_update_config(self):
        result = self.dispatcher.dispatch(
            {"type": "update_config", "key": "ttl", "value": 60}
        )
        assert result.success is True
        assert "ttl" in result.detail

    def test_update_config_missing_key(self):
        result = self.dispatcher.dispatch({"type": "update_config", "value": 42})
        assert result.success is False

    def test_ban_node(self):
        result = self.dispatcher.dispatch({"type": "ban_node", "node_id": "rogue-1"})
        assert result.success is True
        assert "rogue-1" in result.detail

    def test_ban_node_missing_id(self):
        result = self.dispatcher.dispatch({"type": "ban_node"})
        assert result.success is False

    def test_unknown_action_type(self):
        result = self.dispatcher.dispatch({"type": "launch_missiles"})
        assert result.success is False
        assert "Unknown" in result.detail

    def test_missing_type_key(self):
        result = self.dispatcher.dispatch({"value": 42})
        assert result.success is False

    def test_register_custom_handler(self):
        def custom(action):
            return ActionResult("custom", True, f"handled {action.get('x')}")

        self.dispatcher.register("custom", custom)
        result = self.dispatcher.dispatch({"type": "custom", "x": "hello"})
        assert result.success is True
        assert "hello" in result.detail

    def test_handler_exception_returns_failure(self):
        def bad_handler(action):
            raise ValueError("boom")

        self.dispatcher.register("explode", bad_handler)
        result = self.dispatcher.dispatch({"type": "explode"})
        assert result.success is False
        assert "boom" in result.detail


class TestGovernanceExecution:
    def _create_passed_proposal(self, gov, actions):
        """Helper: create and pass a proposal with given actions."""
        prop = gov.create_proposal(
            "Test Exec", "Desc", duration_seconds=0.05, actions=actions
        )
        # Cast enough votes to pass quorum
        gov.cast_vote(prop.id, "node-1", VoteType.YES, tokens=100.0)
        gov.cast_vote(prop.id, "node-2", VoteType.YES, tokens=150.0)
        gov.cast_vote(prop.id, "node-3", VoteType.YES, tokens=80.0)
        time.sleep(0.1)
        gov.check_proposals()
        assert prop.state == ProposalState.PASSED
        return prop

    def test_execute_dispatches_actions(self):
        gov = GovernanceEngine(node_id="node-1")
        actions = [
            {"type": "restart_node", "node_id": "node-5"},
            {"type": "rotate_keys", "scope": "pqc"},
        ]
        prop = self._create_passed_proposal(gov, actions)
        results = gov.execute_proposal(prop.id)
        assert len(results) == 2
        assert results[0].success is True
        assert results[0].action_type == "restart_node"
        assert results[1].success is True
        assert prop.state == ProposalState.EXECUTED

    def test_execute_unknown_proposal(self):
        gov = GovernanceEngine(node_id="node-1")
        results = gov.execute_proposal("nonexistent")
        assert results == []

    def test_execute_not_passed(self):
        gov = GovernanceEngine(node_id="node-1")
        prop = gov.create_proposal("Blocked", "Desc", actions=[{"type": "rotate_keys"}])
        # Still ACTIVE, not PASSED
        results = gov.execute_proposal(prop.id)
        assert results == []

    def test_execute_with_failing_action(self):
        gov = GovernanceEngine(node_id="node-1")
        actions = [
            {"type": "restart_node", "node_id": "ok-node"},
            {"type": "update_threshold"},  # missing value → fail
        ]
        prop = self._create_passed_proposal(gov, actions)
        results = gov.execute_proposal(prop.id)
        assert len(results) == 2
        assert results[0].success is True
        assert results[1].success is False
        # Proposal still marked executed (partial success is still executed)
        assert prop.state == ProposalState.EXECUTED


class TestGovernanceLedger:
    def test_ledger_written(self, tmp_path):
        ledger = tmp_path / "proposals.jsonl"
        gov = GovernanceEngine(node_id="node-1", ledger_path=ledger)
        actions = [{"type": "rotate_keys"}]
        prop = gov.create_proposal(
            "Ledger Test", "Desc", duration_seconds=0.05, actions=actions
        )
        gov.cast_vote(prop.id, "node-1", VoteType.YES, tokens=100.0)
        gov.cast_vote(prop.id, "node-2", VoteType.YES, tokens=150.0)
        gov.cast_vote(prop.id, "node-3", VoteType.YES, tokens=80.0)
        time.sleep(0.1)
        gov.check_proposals()
        gov.execute_proposal(prop.id)

        assert ledger.exists()
        lines = ledger.read_text().strip().split("\n")
        assert len(lines) == 1
        record = json.loads(lines[0])
        assert record["proposal_id"] == prop.id
        assert record["title"] == "Ledger Test"
        assert len(record["actions"]) == 1
        assert record["actions"][0]["success"] is True

    def test_no_ledger_when_path_is_none(self):
        gov = GovernanceEngine(node_id="node-1")  # No ledger_path
        actions = [{"type": "rotate_keys"}]
        prop = gov.create_proposal(
            "No Ledger", "Desc", duration_seconds=0.05, actions=actions
        )
        gov.cast_vote(prop.id, "node-1", VoteType.YES, tokens=100.0)
        gov.cast_vote(prop.id, "node-2", VoteType.YES, tokens=150.0)
        gov.cast_vote(prop.id, "node-3", VoteType.YES, tokens=80.0)
        time.sleep(0.1)
        gov.check_proposals()
        results = gov.execute_proposal(prop.id)
        assert len(results) == 1  # No error, just no file written

    def test_multiple_executions_append(self, tmp_path):
        ledger = tmp_path / "proposals.jsonl"
        gov = GovernanceEngine(node_id="node-1", ledger_path=ledger)

        for i in range(3):
            actions = [{"type": "restart_node", "node_id": f"node-{i+10}"}]
            prop = gov.create_proposal(
                f"Batch {i}", "Desc", duration_seconds=0.05, actions=actions
            )
            gov.cast_vote(prop.id, "node-1", VoteType.YES, tokens=100.0)
            gov.cast_vote(prop.id, "node-2", VoteType.YES, tokens=150.0)
            gov.cast_vote(prop.id, "node-3", VoteType.YES, tokens=80.0)
            time.sleep(0.1)
            gov.check_proposals()
            gov.execute_proposal(prop.id)

        lines = ledger.read_text().strip().split("\n")
        assert len(lines) == 3
