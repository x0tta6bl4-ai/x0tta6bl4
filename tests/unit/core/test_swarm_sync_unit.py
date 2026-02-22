"""Unit tests for src/core/swarm_sync.py."""

import json
from pathlib import Path

from src.core import swarm_sync as mod


def test_get_state_and_save_state_round_trip(tmp_path, monkeypatch):
    state_file = tmp_path / "swarm_state.json"
    monkeypatch.setattr(mod, "STATE_FILE", str(state_file))

    original = {"technical_stream": {"routing_mode": "hybrid_ml"}}
    mod.save_state(original)
    loaded = mod.get_state()

    assert loaded == original


def test_sync_recovery_counts_root_entries_and_nested_files(tmp_path, monkeypatch):
    archive_root = tmp_path / "archive"
    archive_root.mkdir()
    (archive_root / "a.jpg").write_text("a")
    (archive_root / "b.jpg").write_text("b")
    (archive_root / ".hidden").write_text("h")
    (archive_root / "organized").mkdir()
    (archive_root / "organized" / "x.png").write_text("x")
    (archive_root / "organized" / "y.png").write_text("y")

    monkeypatch.setattr(mod, "ARCHIVE_ROOT", str(archive_root))
    state = {}
    mod.sync_recovery(state)

    assert state["recovery_stream"]["files_rescued"] == 3  # 2 files + 1 directory
    assert state["recovery_stream"]["organized_count"] == 2


def test_sync_recovery_missing_archive_is_ignored(tmp_path, monkeypatch):
    missing_root = tmp_path / "missing"
    monkeypatch.setattr(mod, "ARCHIVE_ROOT", str(missing_root))
    state = {"recovery_stream": {"files_rescued": 7, "organized_count": 5}}

    mod.sync_recovery(state)

    assert state["recovery_stream"]["files_rescued"] == 7
    assert state["recovery_stream"]["organized_count"] == 5


def test_sync_tech_to_business_sets_offer_ready_for_hybrid_mode():
    state = {
        "technical_stream": {"routing_mode": "hybrid_ml"},
        "business_stream": {"offer_ready": False},
    }
    mod.sync_tech_to_business(state)
    assert state["business_stream"]["offer_ready"] is True


def test_sync_tech_to_business_keeps_state_for_non_hybrid_mode():
    state = {
        "technical_stream": {"routing_mode": "static"},
        "business_stream": {"offer_ready": False},
    }
    mod.sync_tech_to_business(state)
    assert state["business_stream"]["offer_ready"] is False


def test_save_state_writes_pretty_json(tmp_path, monkeypatch):
    state_file = tmp_path / "swarm_state.json"
    monkeypatch.setattr(mod, "STATE_FILE", str(state_file))
    state = {"a": 1, "b": {"c": 2}}

    mod.save_state(state)
    text = state_file.read_text()

    assert "\n" in text
    assert json.loads(text) == state

