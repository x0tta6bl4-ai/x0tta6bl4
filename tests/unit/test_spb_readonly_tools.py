import importlib.util
from pathlib import Path


ROOT = Path(__file__).resolve().parents[2]
SPEC = importlib.util.spec_from_file_location(
    "spb_readonly_tools",
    ROOT / "mcp-server" / "src" / "spb_readonly_tools.py",
)
mod = importlib.util.module_from_spec(SPEC)
SPEC.loader.exec_module(mod)


def test_goal_blockers_are_derived_from_artifact_statuses():
    summary = {
        "artifacts": {
            "production_db_import": {"status": "promoted_authoritative_db"},
            "real_device_evidence": {"status": "waiting_for_real_device_results"},
            "rkn_tspu_evidence": {"status": "waiting_for_external_live_evidence"},
            "poller_coordination": {"status": "poller_coordination_verified"},
        }
    }

    state = mod._derive_goal_blockers(summary)

    assert state["remaining_blockers"] == [
        "real client-device import/connect evidence",
        "external RKN/TSPU path evidence",
    ]
    assert "authoritative_production_db" in state["resolved_gates"]
    assert "telegram_poller_coordination" in state["resolved_gates"]
    assert state["deferred_actions"] == [
        "guarded Telegram cutover execute remains blocked until real-device and RKN/TSPU gates pass"
    ]


def test_goal_blockers_keep_missing_or_wrong_statuses_open():
    summary = {"artifacts": {"production_db_import": {"status": "blocked_missing_candidate"}}}

    state = mod._derive_goal_blockers(summary)

    assert "authoritative production user database on SPB" in state["remaining_blockers"]
    assert "real client-device import/connect evidence" in state["remaining_blockers"]
    assert "external RKN/TSPU path evidence" in state["remaining_blockers"]
    assert "Telegram poller coordination" in state["remaining_blockers"]
