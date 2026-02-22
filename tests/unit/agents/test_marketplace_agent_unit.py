"""Unit tests for src.agents.marketplace_agent."""

from __future__ import annotations

import json

import pytest

from src.agents.marketplace_agent import MarketplaceAgent


def test_sync_listings_updates_state_file(tmp_path):
    agent = MarketplaceAgent()
    agent.state_file = str(tmp_path / "marketplace_state.json")

    agent.sync_listings()

    assert len(agent.listings) == 2
    assert agent.listings[0]["id"] == "node-DE-01"
    payload = json.loads((tmp_path / "marketplace_state.json").read_text(encoding="utf-8"))
    assert payload == agent.listings


def test_run_invokes_sync_loop_once_when_sleep_interrupts(monkeypatch):
    agent = MarketplaceAgent()
    calls = {"sync": 0}

    def _sync():
        calls["sync"] += 1

    def _sleep(_seconds):
        raise KeyboardInterrupt

    monkeypatch.setattr(agent, "sync_listings", _sync)
    monkeypatch.setattr("src.agents.marketplace_agent.time.sleep", _sleep)

    with pytest.raises(KeyboardInterrupt):
        agent.run()

    assert calls["sync"] == 1
