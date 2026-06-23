from __future__ import annotations

import json
from pathlib import Path
from typing import Mapping, Sequence

from scripts.ops.check_real_readiness import (
    CommandResult,
    build_report,
    check_current_evidence_context,
)


def _write_current_map(root: Path, *, open_gaps: list[str] | None = None) -> None:
    path = root / "docs/architecture/CURRENT_CROSS_PLANE_EVIDENCE_MAP.json"
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(
        json.dumps(
            {
                "status": "working_map_not_production_completion_proof",
                "plane_ids": [
                    "control_plane",
                    "data_plane",
                    "economy_plane",
                    "evidence_plane",
                    "trust_plane",
                ],
                "open_gap_ids": open_gaps or [],
                "next_action_ids": [],
            }
        ),
        encoding="utf-8",
    )


def _runner(
    args: Sequence[str],
    env: Mapping[str, str] | None = None,
    timeout: int = 60,
) -> CommandResult:
    if tuple(args) == ("git", "status", "--porcelain"):
        return CommandResult(0, "", "")
    return CommandResult(0, "ok", "")


def test_current_evidence_context_clear_passes(tmp_path: Path) -> None:
    _write_current_map(tmp_path)

    [result] = check_current_evidence_context(tmp_path)

    assert result.check_id == "current_evidence_context_clear"
    assert result.status == "PASS"


def test_current_evidence_context_open_gap_blocks(tmp_path: Path) -> None:
    _write_current_map(tmp_path, open_gaps=["external-dpi-proof-missing"])

    [result] = check_current_evidence_context(tmp_path)

    assert result.check_id == "current_evidence_context_shape"
    assert result.status == "FAIL"
    assert "external-dpi-proof-missing" in result.details


def test_dirty_git_state_blocks_readiness_without_traceback(tmp_path: Path) -> None:
    _write_current_map(tmp_path)

    def dirty_runner(
        args: Sequence[str],
        env: Mapping[str, str] | None = None,
        timeout: int = 60,
    ) -> CommandResult:
        if tuple(args) == ("git", "status", "--porcelain"):
            return CommandResult(
                0,
                " M scripts/ops/check_real_readiness.py\n"
                "?? docs/verification/GHOST_PULSE_DPI_LAB_LATEST.json\n",
                "",
            )
        return CommandResult(0, "ok", "")

    report = build_report(
        tmp_path,
        runner=dirty_runner,
        include_command_checks=False,
    )

    blocker_ids = {item["check_id"] for item in report["blockers"]}
    assert "git_worktree_clean" in blocker_ids
    [git_blocker] = [
        item for item in report["blockers"] if item["check_id"] == "git_worktree_clean"
    ]
    assert "status_counts: modified=1, untracked=1" in git_blocker["details"]
    assert "top_paths: docs=1, scripts=1" in git_blocker["details"]
    assert report["ready"] is False


def test_ready_report_passes_with_clean_git_and_commands(tmp_path: Path) -> None:
    _write_current_map(tmp_path)

    report = build_report(tmp_path, runner=_runner)

    assert report["decision"] == "REAL_READINESS_READY"
    assert report["ready"] is True
    assert report["blockers"] == []
