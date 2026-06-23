from __future__ import annotations

import importlib.util
from pathlib import Path

from scripts.ops.run_cross_plane_proof_gate import (
    local_service_identity_status_artifact_evidence,
    trust_finality_artifact_evidence,
)


ROOT = Path(__file__).resolve().parents[3]
SCRIPT = ROOT / "scripts/ops/collect_local_service_identity_status_eventbus_evidence.py"


def _load_script():
    spec = importlib.util.spec_from_file_location(
        "collect_local_service_identity_status_eventbus_evidence",
        SCRIPT,
    )
    assert spec and spec.loader
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


def test_collect_reports_inventory_without_event_write(tmp_path: Path) -> None:
    collector = _load_script()
    args = collector.parse_args(["--root", str(tmp_path)])

    report = collector.collect(args)

    assert report["decision"] == "LOCAL_SERVICE_IDENTITY_STATUS_EVENT_NOT_READY"
    assert report["event_written"] is False
    assert report["ready_for_proof_gate"] is False
    assert report["services_total"] > 0
    assert report["raw_identity_values_redacted"] is True


def test_collect_writes_local_identity_status_without_trust_overclaim(
    tmp_path: Path,
) -> None:
    collector = _load_script()
    args = collector.parse_args(
        [
            "--root",
            str(tmp_path),
            "--write-event",
        ]
    )

    report = collector.collect(args)

    assert report["decision"] == "LOCAL_SERVICE_IDENTITY_STATUS_EVENTBUS_EVIDENCE_READY"
    assert report["event_written"] is True
    assert report["ready_for_proof_gate"] is True
    assert report["services_total"] > 0

    artifact = local_service_identity_status_artifact_evidence(tmp_path)
    assert artifact["valid"] is True
    assert artifact["matching_events"] == 1
    assert artifact["selected_event"]["event_id"] == report["event_id"]
    assert artifact["selected_event"]["source_agent"] == "service-identity-status"
    assert artifact["selected_event"]["redacted"] is True

    trust = trust_finality_artifact_evidence(tmp_path)
    assert trust["valid"] is False
    assert "verified_trust_finality_event_not_found" in trust["blockers"]
    assert "trust_finality_not_confirmed" in trust["candidate_blockers"]
