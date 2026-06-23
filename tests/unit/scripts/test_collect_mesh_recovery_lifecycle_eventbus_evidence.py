from __future__ import annotations

import importlib.util
from pathlib import Path

from scripts.ops.run_cross_plane_proof_gate import (
    dataplane_delivery_artifact_evidence,
    mesh_recovery_lifecycle_artifact_evidence,
)


ROOT = Path(__file__).resolve().parents[3]
SCRIPT = ROOT / "scripts/ops/collect_mesh_recovery_lifecycle_eventbus_evidence.py"


def _load_script():
    spec = importlib.util.spec_from_file_location(
        "collect_mesh_recovery_lifecycle_eventbus_evidence",
        SCRIPT,
    )
    assert spec and spec.loader
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


def test_collect_blocks_without_explicit_local_simulation_authorization(
    tmp_path: Path,
) -> None:
    collector = _load_script()
    args = collector.parse_args(["--root", str(tmp_path)])

    report = collector.collect(args)

    assert report["decision"] == "BLOCKED_LOCAL_SIMULATION_NOT_AUTHORIZED"
    assert report["event_written"] is False
    assert report["ready_for_proof_gate"] is False
    assert "allow_local_simulation_required" in report["blockers"]


def test_collect_requires_explicit_event_write(tmp_path: Path) -> None:
    collector = _load_script()
    args = collector.parse_args(
        [
            "--root",
            str(tmp_path),
            "--allow-local-simulation",
        ]
    )

    report = collector.collect(args)

    assert report["decision"] == "BLOCKED_EVENT_WRITE_NOT_REQUESTED"
    assert report["event_written"] is False
    assert report["ready_for_proof_gate"] is False
    assert "write_event_required" in report["blockers"]


def test_collect_writes_recovery_lifecycle_event_without_dataplane_overclaim(
    tmp_path: Path,
) -> None:
    collector = _load_script()
    args = collector.parse_args(
        [
            "--root",
            str(tmp_path),
            "--allow-local-simulation",
            "--write-event",
        ]
    )

    report = collector.collect(args)

    assert report["decision"] == "MESH_RECOVERY_LIFECYCLE_EVENTBUS_EVIDENCE_READY"
    assert report["event_written"] is True
    assert report["ready_for_proof_gate"] is True
    assert report["return_code"] == 0
    assert report["action_error"] is False
    assert report["escalation_required"] is False

    artifact = mesh_recovery_lifecycle_artifact_evidence(tmp_path)
    assert artifact["valid"] is True
    assert artifact["matching_events"] == 1
    assert artifact["selected_event"]["event_id"] == report["event_id"]
    assert artifact["selected_event"]["source_agent"] == "mesh-recovery-orchestrator"
    assert artifact["selected_event"]["policy_allowed"] is True
    assert artifact["selected_event"]["redacted"] is True

    dataplane = dataplane_delivery_artifact_evidence(tmp_path)
    assert dataplane["valid"] is False
    assert "verified_dataplane_delivery_event_not_found" in dataplane["blockers"]


def test_collect_action_failure_is_valid_fail_closed_lifecycle_evidence(
    tmp_path: Path,
) -> None:
    collector = _load_script()
    args = collector.parse_args(
        [
            "--root",
            str(tmp_path),
            "--allow-local-simulation",
            "--write-event",
            "--simulate-action-failure",
        ]
    )

    report = collector.collect(args)

    assert report["decision"] == "MESH_RECOVERY_LIFECYCLE_EVENTBUS_EVIDENCE_READY"
    assert report["return_code"] == 1
    assert report["action_error"] is True
    assert report["escalation_required"] is True
    assert report["post_action_safe_mode_required"] is True

    artifact = mesh_recovery_lifecycle_artifact_evidence(tmp_path)
    assert artifact["valid"] is True
    assert artifact["selected_event"]["action_error"] is True
    assert artifact["selected_event"]["safe_mode_required"] is True
    assert artifact["selected_event"]["escalation_required"] is True
