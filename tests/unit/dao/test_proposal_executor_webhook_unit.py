"""
Unit tests for src/dao/proposal_executor_webhook.py.

All tests run without web3 connection or helm binary.
"""

from __future__ import annotations

import json
import os
import sys
from dataclasses import dataclass
from pathlib import Path
from typing import Any, Dict, List, Optional
from unittest.mock import MagicMock, patch, call

import pytest

os.environ.setdefault("_X0TTA_TEST_MODE_", "true")
# Ensure no MESH_GOVERNANCE_ADDRESS causes graceful failure in tests
os.environ.pop("MESH_GOVERNANCE_ADDRESS", None)


# ---------------------------------------------------------------------------
# Import target
# ---------------------------------------------------------------------------

from src.dao.proposal_executor_webhook import (
    ExecutorConfig,
    HelmResult,
    HelmRunner,
    ProcessedStore,
    ProposalExecutedListener,
    _append_ledger,
    register_helm_upgrade_action,
)


# ===========================================================================
# ProcessedStore
# ===========================================================================

class TestProcessedStore:
    def test_empty_on_new_file(self, tmp_path):
        store = ProcessedStore(tmp_path / "executed.json")
        assert not store.contains(1)

    def test_add_and_contains(self, tmp_path):
        store = ProcessedStore(tmp_path / "executed.json")
        store.add(42)
        assert store.contains(42)
        assert not store.contains(43)

    def test_persists_to_disk(self, tmp_path):
        path = tmp_path / "executed.json"
        store = ProcessedStore(path)
        store.add(10)
        store.add(20)

        store2 = ProcessedStore(path)
        assert store2.contains(10)
        assert store2.contains(20)
        assert not store2.contains(30)

    def test_json_format(self, tmp_path):
        path = tmp_path / "executed.json"
        store = ProcessedStore(path)
        store.add(5)
        store.add(3)
        data = json.loads(path.read_text())
        assert data["executed"] == [3, 5]  # sorted

    def test_load_corrupted_file_starts_empty(self, tmp_path):
        path = tmp_path / "executed.json"
        path.write_text("not-json{{{")
        store = ProcessedStore(path)
        assert not store.contains(1)

    def test_multiple_add_idempotent(self, tmp_path):
        store = ProcessedStore(tmp_path / "e.json")
        store.add(7)
        store.add(7)
        store.add(7)
        assert store.contains(7)
        data = json.loads((tmp_path / "e.json").read_text())
        assert data["executed"].count(7) == 1


# ===========================================================================
# HelmRunner — dry_run mode (no subprocess)
# ===========================================================================

class TestHelmRunnerDryRun:
    def _cfg(self, **kwargs) -> ExecutorConfig:
        base = {
            "rpc_url": "http://localhost:8545",
            "governance_address": "0x" + "a" * 40,
            "helm_release": "mesh-op",
            "helm_chart": "charts/x0tta-mesh-operator/",
            "helm_namespace": "default",
            "helm_extra_args": [],
            "poll_interval": 1,
            "start_block_offset": 10,
            "processed_file": Path("/tmp/proc.json"),
            "ledger_path": Path("/tmp/audit.jsonl"),
            "dry_run": True,
        }
        base.update(kwargs)
        # Build ExecutorConfig manually
        cfg = ExecutorConfig.__new__(ExecutorConfig)
        for k, v in base.items():
            object.__setattr__(cfg, k, v)
        return cfg

    def test_dry_run_returns_success(self, tmp_path):
        cfg = self._cfg(processed_file=tmp_path / "p.json", ledger_path=tmp_path / "a.jsonl")
        runner = HelmRunner(cfg)
        result = runner.upgrade(proposal_id=99)
        assert result.success is True
        assert result.dry_run is True
        assert "mesh-op" in result.command
        assert "99" in result.command

    def test_dry_run_includes_chart(self, tmp_path):
        cfg = self._cfg(
            processed_file=tmp_path / "p.json",
            ledger_path=tmp_path / "a.jsonl",
            helm_chart="charts/custom-chart/",
        )
        runner = HelmRunner(cfg)
        result = runner.upgrade(99)
        assert "charts/custom-chart/" in result.command

    def test_dry_run_includes_namespace(self, tmp_path):
        cfg = self._cfg(
            processed_file=tmp_path / "p.json",
            ledger_path=tmp_path / "a.jsonl",
            helm_namespace="staging",
        )
        runner = HelmRunner(cfg)
        result = runner.upgrade(5)
        assert "--namespace staging" in result.command

    def test_dry_run_extra_set_included(self, tmp_path):
        cfg = self._cfg(processed_file=tmp_path / "p.json", ledger_path=tmp_path / "a.jsonl")
        runner = HelmRunner(cfg)
        result = runner.upgrade(7, extra_set={"foo": "bar", "x": "1"})
        assert "foo=bar" in result.command

    def test_dry_run_proposal_id_in_command(self, tmp_path):
        cfg = self._cfg(processed_file=tmp_path / "p.json", ledger_path=tmp_path / "a.jsonl")
        runner = HelmRunner(cfg)
        result = runner.upgrade(12345)
        assert "proposalId=12345" in result.command

    def test_dry_run_extra_env_args_included(self, tmp_path):
        cfg = self._cfg(
            processed_file=tmp_path / "p.json",
            ledger_path=tmp_path / "a.jsonl",
            helm_extra_args=["--set", "foo=baz"],
        )
        runner = HelmRunner(cfg)
        result = runner.upgrade(1)
        assert "foo=baz" in result.command


# ===========================================================================
# HelmRunner — subprocess failure paths (no dry_run)
# ===========================================================================

class TestHelmRunnerSubprocess:
    def _cfg(self, tmp_path, dry_run=False) -> ExecutorConfig:
        cfg = ExecutorConfig.__new__(ExecutorConfig)
        object.__setattr__(cfg, "rpc_url", "http://localhost:8545")
        object.__setattr__(cfg, "governance_address", "0x" + "a" * 40)
        object.__setattr__(cfg, "helm_release", "mesh-op")
        object.__setattr__(cfg, "helm_chart", "charts/x0tta-mesh-operator/")
        object.__setattr__(cfg, "helm_namespace", "default")
        object.__setattr__(cfg, "helm_extra_args", [])
        object.__setattr__(cfg, "poll_interval", 1)
        object.__setattr__(cfg, "start_block_offset", 10)
        object.__setattr__(cfg, "processed_file", tmp_path / "p.json")
        object.__setattr__(cfg, "ledger_path", tmp_path / "a.jsonl")
        object.__setattr__(cfg, "dry_run", dry_run)
        return cfg

    def test_helm_not_found_returns_failure(self, tmp_path):
        cfg = self._cfg(tmp_path)
        runner = HelmRunner(cfg)
        with patch("subprocess.run", side_effect=FileNotFoundError("helm not found")):
            result = runner.upgrade(1)
        assert result.success is False
        assert "not found" in result.stderr

    def test_helm_nonzero_exit_returns_failure(self, tmp_path):
        import subprocess
        cfg = self._cfg(tmp_path)
        runner = HelmRunner(cfg)
        mock_proc = MagicMock()
        mock_proc.returncode = 1
        mock_proc.stdout = ""
        mock_proc.stderr = "Error: release not found"
        with patch("subprocess.run", return_value=mock_proc):
            result = runner.upgrade(2)
        assert result.success is False
        assert "Error" in result.stderr

    def test_helm_success_marks_result(self, tmp_path):
        cfg = self._cfg(tmp_path)
        runner = HelmRunner(cfg)
        mock_proc = MagicMock()
        mock_proc.returncode = 0
        mock_proc.stdout = "Release upgraded"
        mock_proc.stderr = ""
        with patch("subprocess.run", return_value=mock_proc):
            result = runner.upgrade(3)
        assert result.success is True
        assert result.returncode == 0

    def test_helm_timeout_returns_failure(self, tmp_path):
        import subprocess
        cfg = self._cfg(tmp_path)
        runner = HelmRunner(cfg)
        with patch("subprocess.run", side_effect=subprocess.TimeoutExpired(cmd="helm", timeout=360)):
            result = runner.upgrade(4)
        assert result.success is False
        assert "timed out" in result.stderr


# ===========================================================================
# Ledger writer
# ===========================================================================

class TestAppendLedger:
    def test_creates_file_and_appends(self, tmp_path):
        path = tmp_path / "sub" / "audit.jsonl"
        _append_ledger(path, {"event": "test", "id": 1})
        _append_ledger(path, {"event": "test2", "id": 2})
        lines = path.read_text().strip().split("\n")
        assert len(lines) == 2
        assert json.loads(lines[0])["id"] == 1
        assert json.loads(lines[1])["id"] == 2

    def test_each_line_is_valid_json(self, tmp_path):
        path = tmp_path / "audit.jsonl"
        for i in range(5):
            _append_ledger(path, {"i": i, "ok": True})
        for line in path.read_text().strip().split("\n"):
            obj = json.loads(line)
            assert "i" in obj


# ===========================================================================
# ProposalExecutedListener — no web3
# ===========================================================================

class TestProposalExecutedListenerNoWeb3:
    def _make_listener(self, tmp_path, dry_run=True) -> ProposalExecutedListener:
        cfg = ExecutorConfig.__new__(ExecutorConfig)
        object.__setattr__(cfg, "rpc_url", "http://localhost:8545")
        object.__setattr__(cfg, "governance_address", "0x" + "a" * 40)
        object.__setattr__(cfg, "helm_release", "mesh-op")
        object.__setattr__(cfg, "helm_chart", "charts/x0tta-mesh-operator/")
        object.__setattr__(cfg, "helm_namespace", "default")
        object.__setattr__(cfg, "helm_extra_args", [])
        object.__setattr__(cfg, "poll_interval", 0)
        object.__setattr__(cfg, "start_block_offset", 10)
        object.__setattr__(cfg, "processed_file", tmp_path / "proc.json")
        object.__setattr__(cfg, "ledger_path", tmp_path / "audit.jsonl")
        object.__setattr__(cfg, "dry_run", dry_run)
        return ProposalExecutedListener(cfg)

    def test_poll_once_returns_empty_when_web3_unavailable(self, tmp_path):
        listener = self._make_listener(tmp_path)
        with patch("src.dao.proposal_executor_webhook.WEB3_AVAILABLE", False):
            results = listener.poll_once()
        assert results == []

    def test_poll_once_returns_empty_when_connect_fails(self, tmp_path):
        listener = self._make_listener(tmp_path)
        with patch("src.dao.proposal_executor_webhook.WEB3_AVAILABLE", True):
            with patch.object(listener, "_connect", return_value=False):
                results = listener.poll_once()
        assert results == []

    def test_poll_once_skips_already_processed(self, tmp_path):
        listener = self._make_listener(tmp_path)
        listener.processed.add(55)

        mock_w3 = MagicMock()
        mock_w3.is_connected.return_value = True
        mock_w3.eth.block_number = 1000
        mock_log = {"args": {"proposalId": 55}, "transactionHash": b"\x00" * 32, "blockNumber": 999}
        mock_contract = MagicMock()
        mock_contract.events.ProposalExecuted.get_logs.return_value = [mock_log]
        listener._w3 = mock_w3
        listener._contract = mock_contract

        results = listener.poll_once()
        assert results == []

    def test_poll_once_processes_new_event(self, tmp_path):
        listener = self._make_listener(tmp_path, dry_run=True)

        mock_w3 = MagicMock()
        mock_w3.is_connected.return_value = True
        mock_w3.eth.block_number = 2000
        mock_log = {
            "args": {"proposalId": 101},
            "transactionHash": b"\xab" * 32,
            "blockNumber": 1999,
        }
        mock_contract = MagicMock()
        mock_contract.events.ProposalExecuted.get_logs.return_value = [mock_log]
        listener._w3 = mock_w3
        listener._contract = mock_contract

        results = listener.poll_once()
        assert len(results) == 1
        assert results[0].proposal_id == 101
        assert results[0].success is True  # dry_run

    def test_poll_once_marks_processed_on_success(self, tmp_path):
        listener = self._make_listener(tmp_path, dry_run=True)

        mock_w3 = MagicMock()
        mock_w3.is_connected.return_value = True
        mock_w3.eth.block_number = 2000
        mock_log = {
            "args": {"proposalId": 202},
            "transactionHash": b"\x01" * 32,
            "blockNumber": 1998,
        }
        mock_contract = MagicMock()
        mock_contract.events.ProposalExecuted.get_logs.return_value = [mock_log]
        listener._w3 = mock_w3
        listener._contract = mock_contract

        listener.poll_once()
        assert listener.processed.contains(202)

    def test_poll_once_does_not_mark_processed_on_failure(self, tmp_path):
        listener = self._make_listener(tmp_path, dry_run=False)

        mock_w3 = MagicMock()
        mock_w3.is_connected.return_value = True
        mock_w3.eth.block_number = 2000
        mock_log = {
            "args": {"proposalId": 303},
            "transactionHash": b"\x02" * 32,
            "blockNumber": 1997,
        }
        mock_contract = MagicMock()
        mock_contract.events.ProposalExecuted.get_logs.return_value = [mock_log]
        listener._w3 = mock_w3
        listener._contract = mock_contract

        # Patch subprocess to fail
        import subprocess
        with patch("subprocess.run", side_effect=FileNotFoundError("helm not found")):
            listener.poll_once()

        assert not listener.processed.contains(303)

    def test_poll_once_writes_ledger_on_success(self, tmp_path):
        listener = self._make_listener(tmp_path, dry_run=True)

        mock_w3 = MagicMock()
        mock_w3.is_connected.return_value = True
        mock_w3.eth.block_number = 3000
        mock_log = {
            "args": {"proposalId": 404},
            "transactionHash": b"\x03" * 32,
            "blockNumber": 2999,
        }
        mock_contract = MagicMock()
        mock_contract.events.ProposalExecuted.get_logs.return_value = [mock_log]
        listener._w3 = mock_w3
        listener._contract = mock_contract

        listener.poll_once()

        ledger = tmp_path / "audit.jsonl"
        assert ledger.exists()
        record = json.loads(ledger.read_text().strip().split("\n")[0])
        assert record["proposal_id"] == 404
        assert record["event"] == "ProposalExecuted"

    def test_poll_once_advances_last_block(self, tmp_path):
        listener = self._make_listener(tmp_path, dry_run=True)

        mock_w3 = MagicMock()
        mock_w3.is_connected.return_value = True
        mock_w3.eth.block_number = 5000
        mock_contract = MagicMock()
        mock_contract.events.ProposalExecuted.get_logs.return_value = []
        listener._w3 = mock_w3
        listener._contract = mock_contract

        listener.poll_once()
        assert listener._last_block == 5001

    def test_poll_once_get_logs_failure_reconnects(self, tmp_path):
        listener = self._make_listener(tmp_path, dry_run=True)

        mock_w3 = MagicMock()
        mock_w3.is_connected.return_value = True
        mock_w3.eth.block_number = 1000
        mock_contract = MagicMock()
        mock_contract.events.ProposalExecuted.get_logs.side_effect = Exception("RPC error")
        listener._w3 = mock_w3
        listener._contract = mock_contract

        results = listener.poll_once()
        assert results == []
        assert listener._w3 is None  # triggers reconnect on next poll

    def test_run_stops_after_max_iterations(self, tmp_path):
        listener = self._make_listener(tmp_path, dry_run=True)

        with patch.object(listener, "poll_once", return_value=[]) as mock_poll:
            listener.run(max_iterations=3)

        assert mock_poll.call_count == 3

    def test_run_tolerates_poll_exception(self, tmp_path):
        listener = self._make_listener(tmp_path, dry_run=True)

        call_count = 0

        def _flaky_poll():
            nonlocal call_count
            call_count += 1
            if call_count == 2:
                raise RuntimeError("transient failure")
            return []

        with patch.object(listener, "poll_once", side_effect=_flaky_poll):
            listener.run(max_iterations=4)

        assert call_count == 4

    def test_two_events_both_processed(self, tmp_path):
        listener = self._make_listener(tmp_path, dry_run=True)

        mock_w3 = MagicMock()
        mock_w3.is_connected.return_value = True
        mock_w3.eth.block_number = 4000
        logs = [
            {"args": {"proposalId": 1}, "transactionHash": b"\x01" * 32, "blockNumber": 3998},
            {"args": {"proposalId": 2}, "transactionHash": b"\x02" * 32, "blockNumber": 3999},
        ]
        mock_contract = MagicMock()
        mock_contract.events.ProposalExecuted.get_logs.return_value = logs
        listener._w3 = mock_w3
        listener._contract = mock_contract

        results = listener.poll_once()
        assert len(results) == 2
        assert listener.processed.contains(1)
        assert listener.processed.contains(2)

    def test_second_poll_skips_already_seen(self, tmp_path):
        listener = self._make_listener(tmp_path, dry_run=True)

        mock_w3 = MagicMock()
        mock_w3.is_connected.return_value = True
        mock_w3.eth.block_number = 4000
        mock_log = {"args": {"proposalId": 500}, "transactionHash": b"\x05" * 32, "blockNumber": 3999}
        mock_contract = MagicMock()
        mock_contract.events.ProposalExecuted.get_logs.return_value = [mock_log]
        listener._w3 = mock_w3
        listener._contract = mock_contract

        r1 = listener.poll_once()
        assert len(r1) == 1

        # Same log on second poll
        r2 = listener.poll_once()
        assert r2 == []


# ===========================================================================
# register_helm_upgrade_action
# ===========================================================================

class TestRegisterHelmUpgradeAction:
    def _make_dispatcher(self):
        from src.dao.governance import ActionDispatcher
        return ActionDispatcher()

    def test_helm_upgrade_registered(self, tmp_path):
        dispatcher = self._make_dispatcher()
        cfg = ExecutorConfig.__new__(ExecutorConfig)
        object.__setattr__(cfg, "rpc_url", "")
        object.__setattr__(cfg, "governance_address", "")
        object.__setattr__(cfg, "helm_release", "mesh-op")
        object.__setattr__(cfg, "helm_chart", "charts/x0tta-mesh-operator/")
        object.__setattr__(cfg, "helm_namespace", "default")
        object.__setattr__(cfg, "helm_extra_args", [])
        object.__setattr__(cfg, "poll_interval", 1)
        object.__setattr__(cfg, "start_block_offset", 10)
        object.__setattr__(cfg, "processed_file", tmp_path / "p.json")
        object.__setattr__(cfg, "ledger_path", tmp_path / "a.jsonl")
        object.__setattr__(cfg, "dry_run", True)

        register_helm_upgrade_action(dispatcher, cfg)
        assert "helm_upgrade" in dispatcher._handlers

    def test_helm_upgrade_action_dry_run_success(self, tmp_path):
        dispatcher = self._make_dispatcher()
        cfg = ExecutorConfig.__new__(ExecutorConfig)
        object.__setattr__(cfg, "rpc_url", "")
        object.__setattr__(cfg, "governance_address", "")
        object.__setattr__(cfg, "helm_release", "mesh-op")
        object.__setattr__(cfg, "helm_chart", "charts/x0tta-mesh-operator/")
        object.__setattr__(cfg, "helm_namespace", "default")
        object.__setattr__(cfg, "helm_extra_args", [])
        object.__setattr__(cfg, "poll_interval", 1)
        object.__setattr__(cfg, "start_block_offset", 10)
        object.__setattr__(cfg, "processed_file", tmp_path / "p.json")
        object.__setattr__(cfg, "ledger_path", tmp_path / "a.jsonl")
        object.__setattr__(cfg, "dry_run", True)

        register_helm_upgrade_action(dispatcher, cfg)
        result = dispatcher.dispatch({"type": "helm_upgrade", "proposal_id": 77})
        assert result.success is True
        assert result.action_type == "helm_upgrade"

    def test_helm_upgrade_unknown_action_before_register(self):
        dispatcher = self._make_dispatcher()
        result = dispatcher.dispatch({"type": "helm_upgrade"})
        assert result.success is False
        assert "Unknown" in result.detail

    def test_helm_upgrade_override_release(self, tmp_path):
        dispatcher = self._make_dispatcher()
        cfg = ExecutorConfig.__new__(ExecutorConfig)
        object.__setattr__(cfg, "rpc_url", "")
        object.__setattr__(cfg, "governance_address", "")
        object.__setattr__(cfg, "helm_release", "mesh-op")
        object.__setattr__(cfg, "helm_chart", "charts/x0tta-mesh-operator/")
        object.__setattr__(cfg, "helm_namespace", "default")
        object.__setattr__(cfg, "helm_extra_args", [])
        object.__setattr__(cfg, "poll_interval", 1)
        object.__setattr__(cfg, "start_block_offset", 10)
        object.__setattr__(cfg, "processed_file", tmp_path / "p.json")
        object.__setattr__(cfg, "ledger_path", tmp_path / "a.jsonl")
        object.__setattr__(cfg, "dry_run", True)

        register_helm_upgrade_action(dispatcher, cfg)
        result = dispatcher.dispatch({
            "type": "helm_upgrade",
            "proposal_id": 88,
            "release": "custom-release",
        })
        assert result.success is True
        assert "custom-release" in result.detail

    def test_governance_engine_execute_with_helm_upgrade(self, tmp_path):
        """End-to-end: GovernanceEngine.execute_proposal with helm_upgrade action."""
        from src.dao.governance import GovernanceEngine, VoteType, ProposalState

        gov = GovernanceEngine(node_id="exec-node")

        cfg = ExecutorConfig.__new__(ExecutorConfig)
        object.__setattr__(cfg, "rpc_url", "")
        object.__setattr__(cfg, "governance_address", "")
        object.__setattr__(cfg, "helm_release", "mesh-op")
        object.__setattr__(cfg, "helm_chart", "charts/x0tta-mesh-operator/")
        object.__setattr__(cfg, "helm_namespace", "default")
        object.__setattr__(cfg, "helm_extra_args", [])
        object.__setattr__(cfg, "poll_interval", 1)
        object.__setattr__(cfg, "start_block_offset", 10)
        object.__setattr__(cfg, "processed_file", tmp_path / "p.json")
        object.__setattr__(cfg, "ledger_path", tmp_path / "a.jsonl")
        object.__setattr__(cfg, "dry_run", True)

        register_helm_upgrade_action(gov.dispatcher, cfg)

        prop = gov.create_proposal(
            "Upgrade to v3.4.0",
            "Production rollout",
            duration_seconds=0.1,
            actions=[{"type": "helm_upgrade", "proposal_id": 999}],
        )
        gov.cast_vote(prop.id, "node-1", VoteType.YES, tokens=100.0)
        gov.cast_vote(prop.id, "node-2", VoteType.YES, tokens=100.0)
        gov.cast_vote(prop.id, "node-3", VoteType.YES, tokens=100.0)

        import time
        time.sleep(0.15)
        gov.check_proposals()
        assert prop.state == ProposalState.PASSED

        results = gov.execute_proposal(prop.id)
        assert len(results) == 1
        assert results[0].action_type == "helm_upgrade"
        assert results[0].success is True
        assert prop.state == ProposalState.EXECUTED
