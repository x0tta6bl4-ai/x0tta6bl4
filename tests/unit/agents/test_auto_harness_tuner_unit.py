"""Unit tests for Autonomous Agentic Harness Optimization Tuner (Loop A)."""

from pathlib import Path
import pytest
from scripts.agents.auto_harness_tuner import run_cycle, main


def test_run_cycle_dry_run():
    summary_path = run_cycle(agents="agent-1,agent-2", dry_run=True)
    assert summary_path.exists()
    assert summary_path.name == "summary.json"


def test_auto_harness_tuner_main(monkeypatch):
    monkeypatch.setattr("sys.argv", ["auto_harness_tuner.py", "--experiment-name", "test_exp", "--agents", "agent-1"])
    exit_code = main()
    assert exit_code == 0


def test_auto_harness_tuner_auto_mutate(monkeypatch):
    monkeypatch.setattr("sys.argv", [
        "auto_harness_tuner.py",
        "--experiment-name", "test_mutate",
        "--agents", "agent-1,agent-2",
        "--auto-mutate",
        "--target-agent", "agent-2"
    ])
    exit_code = main()
    assert exit_code == 0

