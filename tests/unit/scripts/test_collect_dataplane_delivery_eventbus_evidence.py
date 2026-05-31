from __future__ import annotations

import importlib.util
from pathlib import Path

from scripts.ops.run_cross_plane_proof_gate import dataplane_delivery_artifact_evidence


ROOT = Path(__file__).resolve().parents[3]
SCRIPT = ROOT / "scripts/ops/collect_dataplane_delivery_eventbus_evidence.py"


def _load_script():
    spec = importlib.util.spec_from_file_location(
        "collect_dataplane_delivery_eventbus_evidence",
        SCRIPT,
    )
    assert spec and spec.loader
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


def test_collect_blocks_without_explicit_local_probe_authorization(tmp_path: Path) -> None:
    collector = _load_script()
    args = collector.parse_args(["--root", str(tmp_path), "--port", "443"])

    report = collector.collect(args)

    assert report["decision"] == "BLOCKED_LOCAL_PROBE_NOT_AUTHORIZED"
    assert report["event_written"] is False
    assert report["ready_for_proof_gate"] is False
    assert "allow_local_probe_required" in report["blockers"]


def test_collect_rejects_non_local_targets(tmp_path: Path) -> None:
    collector = _load_script()
    args = collector.parse_args(
        [
            "--root",
            str(tmp_path),
            "--host",
            "example.com",
            "--port",
            "443",
            "--allow-local-probe",
            "--write-event",
        ]
    )

    report = collector.collect(args, connector=lambda host, port, timeout: None)

    assert report["decision"] == "BLOCKED_NON_LOCAL_TARGET"
    assert report["event_written"] is False
    assert report["ready_for_proof_gate"] is False


def test_collect_writes_event_recognized_by_cross_plane_proof_gate(
    tmp_path: Path,
) -> None:
    collector = _load_script()
    args = collector.parse_args(
        [
            "--root",
            str(tmp_path),
            "--host",
            "127.0.0.1",
            "--port",
            "18080",
            "--allow-local-probe",
            "--write-event",
        ]
    )

    report = collector.collect(args, connector=lambda host, port, timeout: None)

    assert report["decision"] == "DATAPLANE_EVENTBUS_EVIDENCE_READY"
    assert report["event_written"] is True
    assert report["ready_for_proof_gate"] is True

    artifact = dataplane_delivery_artifact_evidence(tmp_path)
    assert artifact["valid"] is True
    assert artifact["matching_events"] == 1
    assert artifact["selected_event"]["event_id"] == report["event_id"]
    assert artifact["selected_event"]["redacted"] is True


def test_collect_failed_probe_writes_non_promoting_event(tmp_path: Path) -> None:
    collector = _load_script()
    args = collector.parse_args(
        [
            "--root",
            str(tmp_path),
            "--host",
            "127.0.0.1",
            "--port",
            "18080",
            "--allow-local-probe",
            "--write-event",
        ]
    )

    def fail_connect(host: str, port: int, timeout: float) -> None:
        raise TimeoutError("synthetic timeout")

    report = collector.collect(args, connector=fail_connect)

    assert report["decision"] == "DATAPLANE_PROBE_FAILED"
    assert report["event_written"] is True
    assert report["ready_for_proof_gate"] is False

    artifact = dataplane_delivery_artifact_evidence(tmp_path)
    assert artifact["valid"] is False
    assert "verified_dataplane_delivery_event_not_found" in artifact["blockers"]
    assert "dataplane_probe_not_confirmed" in artifact["candidate_blockers"]
