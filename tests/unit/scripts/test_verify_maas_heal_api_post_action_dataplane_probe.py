from __future__ import annotations

import importlib.util
import json
import sys
from pathlib import Path


ROOT = Path(__file__).resolve().parents[3]
SCRIPT = ROOT / "scripts/ops/verify_maas_heal_api_post_action_dataplane_probe.py"


def _load_module():
    spec = importlib.util.spec_from_file_location(
        "verify_maas_heal_api_post_action_dataplane_probe",
        SCRIPT,
    )
    assert spec and spec.loader
    module = importlib.util.module_from_spec(spec)
    sys.modules[spec.name] = module
    spec.loader.exec_module(module)
    return module


def test_maas_heal_api_verifier_redacts_target_and_surfaces_gate(
    tmp_path: Path,
) -> None:
    module = _load_module()
    target = "10.123.45.67"

    report = module.build_report(tmp_path, target=target)
    rendered = json.dumps(report, ensure_ascii=False, sort_keys=True)

    assert report["decision"] == module.DECISION_READY
    assert report["ok"] is True
    assert report["schema"] == module.SCHEMA
    assert report["target"] == {
        "sha256": module.sha256_text(target),
        "raw_target_redacted": True,
    }
    assert report["summary"]["api_path_exercised"] is True
    assert report["summary"]["heartbeat_registered_probe_target"] is True
    assert report["summary"]["heartbeat_raw_target_redacted"] is True
    assert report["summary"]["manager_received_probe_target"] is True
    assert report["summary"]["manager_event_bus_attached"] is True
    assert report["summary"]["dataplane_confirmed"] is True
    assert report["summary"]["post_action_dataplane_revalidated"] is True
    assert report["summary"]["restored_dataplane_claim_allowed"] is True
    assert report["summary"]["traffic_delivery_claim_allowed"] is False
    assert report["summary"]["customer_traffic_claim_allowed"] is False
    assert report["summary"]["external_reachability_claim_allowed"] is False
    assert report["summary"]["production_slo_claim_allowed"] is False
    assert report["summary"]["production_readiness_claim_allowed"] is False
    assert report["evidence"]["control_plane_operations"] == [
        "trigger_aggressive_healing"
    ]
    assert report["evidence"]["post_action_reason"] == (
        "bounded_dataplane_probe_succeeded"
    )
    assert report["failures"] == []
    assert target not in rendered
