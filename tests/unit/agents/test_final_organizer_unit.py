"""Unit tests for src.agents.final_organizer."""

from __future__ import annotations

import subprocess
from pathlib import Path
from unittest.mock import MagicMock

from src.agents import final_organizer as mod


def test_run_cmd_success(monkeypatch):
    calls = []

    def _ok_run(args, check, stdout, stderr):
        calls.append((args, check, stdout, stderr))
        return MagicMock()

    monkeypatch.setattr(mod.subprocess, "run", _ok_run)
    assert mod.run_cmd(["echo", "ok"]) is True
    assert calls and calls[0][0] == ["echo", "ok"]


def test_run_cmd_failure(monkeypatch):
    def _raise(*_args, **_kwargs):
        raise subprocess.CalledProcessError(returncode=1, cmd=["false"])

    monkeypatch.setattr(mod.subprocess, "run", _raise)
    assert mod.run_cmd(["false"]) is False


def test_move_videos_moves_only_known_extensions(tmp_path):
    source = tmp_path / "src"
    target = tmp_path / "dst"
    source.mkdir()
    target.mkdir()

    (source / "a.mp4").write_text("video", encoding="utf-8")
    (source / "b.MOV").write_text("video", encoding="utf-8")
    (source / "c.jpg").write_text("photo", encoding="utf-8")
    (source / "dir").mkdir()

    moved = mod.move_videos(source, target)
    assert moved == 2
    assert (target / "a.mp4").exists()
    assert (target / "b.MOV").exists()
    assert (source / "c.jpg").exists()
    assert (source / "dir").exists()


def test_organize_processes_unmarked_dirs_and_writes_log(tmp_path, monkeypatch):
    source_base = tmp_path / "recovered_photos"
    target_base = tmp_path / "PHOTOS_COLLECTION"
    log_file = tmp_path / "RECOVERY_FINAL.log"
    source_base.mkdir()

    dir_1 = source_base / "photorec_out.1"
    dir_2 = source_base / "photorec_out.2"
    dir_1.mkdir()
    dir_2.mkdir()
    (dir_1 / "movie.mp4").write_text("v", encoding="utf-8")
    (dir_2 / ".organized").touch()

    path_map = {
        "/mnt/projects/recovered_photos": source_base,
        "/mnt/projects/PHOTOS_COLLECTION": target_base,
        "/mnt/projects/RECOVERY_FINAL.log": log_file,
    }
    real_path = Path

    def _mapped_path(raw: str):
        return path_map.get(str(raw), real_path(raw))

    run_calls = []

    def _run_cmd(args):
        run_calls.append(args)
        return True

    monkeypatch.setattr(mod, "Path", _mapped_path)
    monkeypatch.setattr(mod, "run_cmd", _run_cmd)
    mod.organize()

    assert len(run_calls) == 1
    assert run_calls[0][0] == "sudo"
    assert run_calls[0][1] == "exiftool"
    assert (dir_1 / ".organized").exists()
    assert (target_base / "VIDEOS" / "movie.mp4").exists()

    text = log_file.read_text(encoding="utf-8")
    assert "Starting final organization of 2 directories" in text
    assert "Processing" in text
    assert "Moved videos: 1" in text
    assert "--- ALL DIRECTORIES PROCESSED ---" in text


def test_organize_handles_empty_source(tmp_path, monkeypatch):
    source_base = tmp_path / "recovered_photos"
    target_base = tmp_path / "PHOTOS_COLLECTION"
    log_file = tmp_path / "RECOVERY_FINAL.log"
    source_base.mkdir()

    path_map = {
        "/mnt/projects/recovered_photos": source_base,
        "/mnt/projects/PHOTOS_COLLECTION": target_base,
        "/mnt/projects/RECOVERY_FINAL.log": log_file,
    }
    real_path = Path

    def _mapped_path(raw: str):
        return path_map.get(str(raw), real_path(raw))

    monkeypatch.setattr(mod, "Path", _mapped_path)
    monkeypatch.setattr(mod, "run_cmd", lambda _args: True)
    mod.organize()

    assert (target_base / "VIDEOS").exists()
    text = log_file.read_text(encoding="utf-8")
    assert "Starting final organization of 0 directories" in text
