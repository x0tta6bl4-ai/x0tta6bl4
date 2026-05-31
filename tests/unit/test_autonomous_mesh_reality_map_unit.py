from __future__ import annotations

import json
from pathlib import Path


ROOT = Path(__file__).resolve().parents[2]
MAP_PATH = ROOT / "docs/architecture/CURRENT_AUTONOMOUS_MESH_REALITY_MAP.json"
REQUIRED_PLANES = {
    "data_plane",
    "control_plane",
    "trust_plane",
    "evidence_plane",
    "economy_plane",
}


def _load_map() -> dict:
    return json.loads(MAP_PATH.read_text(encoding="utf-8"))


def _source_paths(value):
    if isinstance(value, dict):
        for key, nested in value.items():
            if key == "source_refs":
                for ref in nested:
                    yield str(ref).split(":", 1)[0]
            else:
                yield from _source_paths(nested)
    elif isinstance(value, list):
        for item in value:
            yield from _source_paths(item)


def test_autonomous_mesh_reality_map_has_required_planes() -> None:
    payload = _load_map()

    assert payload["schema"] == "x0tta6bl4.autonomous_mesh_reality_map.v1"
    assert payload["status"] == "working_map_not_production_completion_proof"
    assert set(payload["planes"]) == REQUIRED_PLANES
    assert set(payload["not_a_vpn_mvp"]["required_planes_present"]) == REQUIRED_PLANES


def test_autonomous_mesh_reality_map_separates_verified_and_unproven_claims() -> None:
    payload = _load_map()

    for plane_name, plane in payload["planes"].items():
        assert plane["verified_contours"], plane_name
        assert plane["unproven_or_blocked_claims"], plane_name
    assert "live customer traffic" in payload["claim_boundary"]
    assert "payment settlement finality" in payload["claim_boundary"]
    assert "production readiness" in payload["claim_boundary"]


def test_autonomous_mesh_reality_map_source_refs_exist() -> None:
    payload = _load_map()
    missing = sorted(
        {
            source_path
            for source_path in _source_paths(payload)
            if not (ROOT / source_path).exists()
        }
    )

    assert missing == []


def test_autonomous_mesh_reality_map_names_next_control_spine_improvement() -> None:
    payload = _load_map()
    next_step = payload["next_best_code_improvement"]

    assert next_step["id"] == "mesh_recovery_eventbus_bridge"
    assert "RecoveryEvidenceV1" in next_step["description"]
    assert "EventBus" in next_step["description"]
