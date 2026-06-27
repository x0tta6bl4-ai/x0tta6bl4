from __future__ import annotations

import asyncio
import json

from scripts.ops.verify_maas_heal_post_action_dataplane_probe import run_verification
from src.coordination.events import EventType


def test_maas_heal_probe_verifier_redacts_target_and_surfaces_gate(tmp_path) -> None:
    async def fake_probe(target: str, **kwargs):
        event_bus = kwargs["event_bus"]
        event = event_bus.publish(
            EventType.PIPELINE_STAGE_END,
            "real-network-adapter",
            {
                "operation": "dataplane_ping_probe",
                "status": "success",
                "target_hash_only": True,
                "redacted": True,
            },
        )
        return {
            "status": "ok",
            "latency_ms": 0.7,
            "packet_loss_percent": 0.0,
            "evidence": {
                "source_agents": ["real-network-adapter"],
                "event_ids": [event.event_id],
                "events_total": 1,
                "redacted": True,
            },
            "claim_boundary": "bounded fake dataplane probe evidence only",
            "redacted": True,
        }

    report = asyncio.run(
        run_verification(
            target="10.123.45.67",
            event_project_root=str(tmp_path),
            probe_func=fake_probe,
        )
    )

    assert report["ready"] is True
    assert report["decision"] == "MAAS_HEAL_POST_ACTION_DATAPLANE_PROBE_READY"
    assert report["local_healing"]["healed"] == 1
    assert report["mesh_network_manager"]["dataplane_confirmed"] is True
    assert report["mesh_network_manager"]["restored_dataplane_claim_allowed"] is True
    assert report["maas_heal_surface"]["dataplane_confirmed"] is True
    assert report["maas_heal_surface"]["post_action_dataplane_revalidated"] is True
    assert report["maas_heal_surface"]["restored_dataplane_claim_allowed"] is True
    assert report["maas_heal_surface"]["traffic_delivery_claim_allowed"] is False
    assert report["maas_heal_surface"]["customer_traffic_claim_allowed"] is False
    assert report["maas_heal_surface"]["production_readiness_claim_allowed"] is False
    assert report["target"]["raw_target_redacted"] is True
    assert "10.123.45.67" not in json.dumps(report, sort_keys=True)
