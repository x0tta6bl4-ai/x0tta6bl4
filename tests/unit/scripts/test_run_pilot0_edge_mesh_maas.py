from __future__ import annotations

import copy
import json
from pathlib import Path

from scripts.ops import run_pilot0_edge_mesh_maas as pilot0
from scripts.ops import verify_maas_real_agent_control_loop as real_agent


RAW_TARGET = "10.123.45.67"


def _stage(name: str, ok: bool = True) -> dict:
    return {"name": name, "ok": ok, "http_status_code": 200, "details": {}}


def _ready_agent_report() -> dict:
    return {
        "schema": real_agent.SCHEMA,
        "decision": real_agent.READY_DECISION,
        "ready": True,
        "duration_ms": 1234.5,
        "stages": [_stage(name) for name in sorted(pilot0.REQUIRED_STAGES)],
        "entities": {
            "mesh": {"present": True, "sha256": "mesh-hash", "raw_value_redacted": True},
            "node": {"present": True, "sha256": "node-hash", "raw_value_redacted": True},
        },
        "agent": {
            "binary_built": True,
            "process_started": True,
            "node_runtime_credential_hash_stored": True,
            "node_runtime_credential_expiry_stored": True,
            "node_runtime_credential_rotation_observed": True,
            "raw_node_runtime_credential_redacted": True,
            "config_file_temporary": True,
            "node_config_fetch_observed": True,
            "heartbeat_observed": True,
            "operator_heal_observed": True,
        },
        "healing_surface": {
            "observed": True,
            "status": "healed",
            "healing_claim": "local_control_action_applied",
            "components_healed": 1,
            "post_heal_node_status": "healthy",
            "post_action_revalidation_present": True,
            "dataplane_confirmed": True,
            "post_action_dataplane_revalidated": True,
            "restored_dataplane_claim_allowed": True,
            "traffic_delivery_claim_allowed": False,
            "customer_traffic_claim_allowed": False,
            "external_reachability_claim_allowed": False,
            "production_slo_claim_allowed": False,
            "production_readiness_claim_allowed": False,
            "raw_target_redacted": True,
        },
        "dataplane_probe_target": {
            "sha256": "effective-target-hash",
            "requested_sha256": "requested-target-hash",
            "raw_value_redacted": True,
            "requested_raw_value_redacted": True,
            "local_listener_target": True,
            "loopback_lab_target": True,
        },
        "event_project_root": "/tmp/pilot0-events",
        "database": {
            "temporary_sqlite": True,
            "path": "/tmp/pilot0-events/maas-real-agent-smoke.db",
        },
        "claim_boundary": real_agent.CLAIM_BOUNDARY,
    }


def test_build_report_ready_redacts_target_and_blocks_strong_claims() -> None:
    report = pilot0.build_report(
        _ready_agent_report(),
        requested_dataplane_probe_target=RAW_TARGET,
        generated_at_utc="2026-06-07T15:00:00Z",
    )

    assert report["schema"] == pilot0.SCHEMA
    assert report["decision"] == pilot0.READY_DECISION
    assert report["ready"] is True
    assert report["summary"]["required_stages_passed"] == len(pilot0.REQUIRED_STAGES)
    assert report["operator_visible_results"]["maas_api_started"] is True
    assert report["operator_visible_results"]["heartbeat_seen"] is True
    assert report["operator_visible_results"]["heal_seen"] is True
    assert report["operator_visible_results"]["production_overclaim_blocked"] is True
    assert report["claim_gate"]["real_go_agent_connected_claim_allowed"] is True
    assert report["claim_gate"]["local_heartbeat_persisted_claim_allowed"] is True
    assert report["claim_gate"]["local_heal_control_action_claim_allowed"] is True
    assert report["claim_gate"]["bounded_restored_dataplane_claim_allowed"] is True
    assert report["claim_gate"]["customer_traffic_claim_allowed"] is False
    assert report["claim_gate"]["external_dpi_bypass_claim_allowed"] is False
    assert report["claim_gate"]["production_readiness_claim_allowed"] is False
    assert report["failures"] == []
    assert RAW_TARGET not in json.dumps(report, sort_keys=True)


def test_build_report_blocks_healing_overclaim() -> None:
    agent_report = _ready_agent_report()
    agent_report["healing_surface"]["production_readiness_claim_allowed"] = True

    report = pilot0.build_report(
        agent_report,
        requested_dataplane_probe_target=RAW_TARGET,
        generated_at_utc="2026-06-07T15:00:00Z",
    )

    assert report["decision"] == pilot0.BLOCKED_DECISION
    assert report["ready"] is False
    assert "healing_overclaim:production_readiness_claim_allowed" in report["failures"]
    assert report["claim_gate"]["production_readiness_claim_allowed"] is False


def test_build_report_blocks_missing_required_stage() -> None:
    agent_report = _ready_agent_report()
    agent_report["stages"] = [
        stage
        for stage in agent_report["stages"]
        if stage["name"] != "agent_heartbeat_persisted"
    ]

    report = pilot0.build_report(
        agent_report,
        requested_dataplane_probe_target=RAW_TARGET,
        generated_at_utc="2026-06-07T15:00:00Z",
    )

    assert report["ready"] is False
    assert "stage_not_ok:agent_heartbeat_persisted" in report["failures"]
    assert report["operator_visible_results"]["heartbeat_seen"] is False


def test_write_artifacts_creates_json_markdown_and_latest(tmp_path: Path) -> None:
    report = pilot0.build_report(
        copy.deepcopy(_ready_agent_report()),
        requested_dataplane_probe_target=RAW_TARGET,
        generated_at_utc="2026-06-07T15:00:00Z",
    )

    paths = pilot0.write_artifacts(
        report,
        output_dir=tmp_path,
        tag="20260607T150000Z",
    )

    for path in paths.values():
        assert path.exists()
        assert RAW_TARGET not in path.read_text(encoding="utf-8")
    payload = json.loads(paths["json"].read_text(encoding="utf-8"))
    markdown = paths["markdown"].read_text(encoding="utf-8")
    assert payload["artifacts"]["latest_json"].endswith(
        "pilot0_edge_mesh_maas_latest.json"
    )
    assert "Pilot 0: Edge Mesh MaaS Report" in markdown
    assert "Production overclaim blocked" in markdown


def test_run_pilot0_uses_real_agent_verifier_and_writes_report(
    monkeypatch,
    tmp_path: Path,
) -> None:
    calls = []

    def fake_run_verification(**kwargs):
        calls.append(kwargs)
        return copy.deepcopy(_ready_agent_report())

    monkeypatch.setattr(real_agent, "run_verification", fake_run_verification)

    report = pilot0.run_pilot0(
        work_dir=tmp_path / "work",
        output_dir=tmp_path / "out",
        dataplane_probe_target=RAW_TARGET,
        timeout_seconds=90.0,
        use_local_listener_target=True,
        generated_at_utc="2026-06-07T15:00:00Z",
    )

    assert report["ready"] is True
    assert calls == [
        {
            "work_dir": str(tmp_path / "work"),
            "dataplane_probe_target": RAW_TARGET,
            "timeout_seconds": 90.0,
            "use_local_listener_target": True,
        }
    ]
    assert (tmp_path / "out" / "pilot0_edge_mesh_maas_latest.json").exists()
