"""Unit tests for scripts/vpn_provider_guard.py."""

from __future__ import annotations

import importlib.util
from datetime import datetime, timezone
from pathlib import Path


ROOT = Path(__file__).resolve().parents[3]
SCRIPT = ROOT / "scripts" / "vpn_provider_guard.py"
SPEC = importlib.util.spec_from_file_location("vpn_provider_guard", SCRIPT)
assert SPEC and SPEC.loader
guard = importlib.util.module_from_spec(SPEC)
SPEC.loader.exec_module(guard)


def test_guard_blocks_provider_outage() -> None:
    decision = guard.evaluate_guard(
        {
            "overall_status": "provider_outage",
            "failure_domain": "provider_host",
            "recommended_action": "provider_ticket",
        }
    )
    assert decision["guard_status"] == "block"
    assert decision["blocking_reason"] == "provider_outage"


def test_guard_blocks_critical_nl_service() -> None:
    decision = guard.evaluate_guard(
        {
            "overall_status": "critical",
            "failure_domain": "nl_service",
            "recommended_action": "operator_review",
        }
    )
    assert decision["guard_status"] == "block"
    assert decision["blocking_reason"] == "critical_nl_service"


def test_guard_allows_current_external_network_advisory() -> None:
    decision = guard.evaluate_guard(
        {
            "overall_status": "advisory",
            "failure_domain": "external_network",
            "recommended_action": "observe",
        }
    )
    assert decision["guard_status"] == "allow"
    assert decision["blocking_reason"] is None


def test_guard_warns_on_stale_snapshot_without_require_fresh() -> None:
    decision = guard.evaluate_guard(
        {
            "overall_status": "advisory",
            "failure_domain": "external_network",
            "recommended_action": "observe",
        },
        snapshot_dir=Path("/tmp/20260527T060000Z"),
        max_age_seconds=300,
        now=datetime(2026, 5, 27, 6, 10, tzinfo=timezone.utc),
    )
    assert decision["guard_status"] == "allow"
    assert decision["snapshot_age_seconds"] == 600
    assert decision["snapshot_stale"] is True
    assert decision["warnings"]


def test_guard_blocks_stale_snapshot_when_require_fresh() -> None:
    decision = guard.evaluate_guard(
        {
            "overall_status": "advisory",
            "failure_domain": "external_network",
            "recommended_action": "observe",
        },
        snapshot_dir=Path("/tmp/20260527T060000Z"),
        max_age_seconds=300,
        require_fresh=True,
        now=datetime(2026, 5, 27, 6, 10, tzinfo=timezone.utc),
    )
    assert decision["guard_status"] == "block"
    assert decision["blocking_reason"] == "stale_snapshot_age_seconds=600"


def test_guard_allows_when_no_snapshot_exists(tmp_path: Path) -> None:
    decision = guard.load_state(
        root=ROOT,
        snapshots_dir=tmp_path / "missing-snapshots",
        snapshot_dir=None,
    )
    assert decision["guard_status"] == "allow"
    assert decision["reason"].startswith("no local snapshot")


def test_guard_blocks_missing_snapshot_when_require_fresh(tmp_path: Path) -> None:
    decision = guard.load_state(
        root=ROOT,
        snapshots_dir=tmp_path / "missing-snapshots",
        snapshot_dir=None,
        require_fresh=True,
    )
    assert decision["guard_status"] == "block"
    assert decision["blocking_reason"] == "snapshot_missing"
