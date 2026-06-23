from __future__ import annotations

import json

from scripts.ops.verify_maas_autonomous_mesh_runtime_smoke import (
    READY_DECISION,
    run_verification,
)


def test_maas_autonomous_mesh_runtime_smoke_redacts_and_gates_claims(tmp_path) -> None:
    target = "10.44.55.66"

    report = run_verification(
        event_project_root=str(tmp_path),
        dataplane_probe_target=target,
    )

    assert report["ready"] is True
    assert report["decision"] == READY_DECISION

    stage_names = {stage["name"] for stage in report["stages"]}
    assert {
        "auth_register",
        "mesh_deploy",
        "agent_node_register",
        "agent_node_approve",
        "agent_heartbeat",
        "node_heal",
        "service_trace_dataplane_gate_classified",
        "node_state_persisted_in_temp_db",
    }.issubset(stage_names)

    assert report["entities"]["user"]["present"] is True
    assert report["entities"]["mesh"]["present"] is True
    assert report["entities"]["node"]["present"] is True
    assert report["evidence_gates"]["mesh_deploy"] == {
        "local_db_persistence_claim_allowed": True,
        "external_node_deployment_claim_allowed": False,
        "production_readiness_claim_allowed": False,
    }
    assert report["evidence_gates"]["node_heal"]["dataplane_confirmed"] is True
    assert (
        report["evidence_gates"]["node_heal"][
            "post_action_dataplane_revalidated"
        ]
        is True
    )
    assert (
        report["evidence_gates"]["node_heal"][
            "restored_dataplane_claim_allowed"
        ]
        is True
    )
    assert (
        report["evidence_gates"]["node_heal"]["traffic_delivery_claim_allowed"]
        is False
    )
    assert (
        report["evidence_gates"]["node_heal"]["customer_traffic_claim_allowed"]
        is False
    )
    assert (
        report["evidence_gates"]["node_heal"][
            "production_readiness_claim_allowed"
        ]
        is False
    )
    assert report["evidence_gates"]["service_trace"]["primary_status"] == (
        "dataplane_confirmed"
    )
    assert (
        report["evidence_gates"]["service_trace"][
            "dataplane_claim_gate_allowed"
        ]
        is True
    )
    assert (
        report["evidence_gates"]["service_trace"][
            "production_ready_candidate"
        ]
        is False
    )

    assert report["dataplane_probe_target"]["raw_value_redacted"] is True
    assert target not in json.dumps(report, sort_keys=True)
