from __future__ import annotations

import json
from pathlib import Path


ROOT = Path(__file__).resolve().parents[2]
REGISTRY_PATH = ROOT / "docs/architecture/CURRENT_COMPONENT_REGISTRY.json"


def _load_registry() -> dict:
    return json.loads(REGISTRY_PATH.read_text(encoding="utf-8"))


def _entry_source(component: dict) -> str:
    path = ROOT / component["entrypoint"]
    assert path.exists(), component["entrypoint"]
    return path.read_text(encoding="utf-8")


def test_component_registry_is_valid_json_with_component_ids():
    registry = _load_registry()

    assert registry["captured_at"] == "2026-05-27"
    assert registry["status"] == "working_map_not_production_completion_proof"
    assert registry["shared_planes"]

    components = registry["components"]
    assert components
    ids = [component["id"] for component in components]
    assert len(ids) == len(set(ids))


def test_component_registry_source_refs_resolve_to_existing_files_and_lines():
    registry = _load_registry()

    for component in registry["components"]:
        assert component["source_refs"], component["id"]
        for source_ref in component["source_refs"]:
            path_text, line_text = source_ref.rsplit(":", 1)
            path = ROOT / path_text
            assert path.exists(), source_ref
            line_count = len(path.read_text(encoding="utf-8").splitlines())
            assert 1 <= int(line_text) <= line_count, source_ref


def test_component_registry_control_plane_claims_match_entrypoint_imports():
    registry = _load_registry()

    for component in registry["components"]:
        source = _entry_source(component)

        event_bus = component["event_bus"]
        if event_bus in {"direct_publish", "direct_publish_plus_reward_and_marketplace_events"}:
            assert "EventBus" in source or "get_event_bus" in source, component["id"]
        elif event_bus == "via_marketplace_events":
            assert "publish_marketplace_escrow_event" in source, component["id"]
        elif event_bus == "via_reward_events":
            assert "publish_reward_settlement_event" in source, component["id"]

        service_identity = component["service_identity"]
        identity_is_explicit_service = service_identity not in {
            "none_direct",
            "current_user_dependency",
            "node_id_from_environment",
            "source_agent_field",
        }
        if identity_is_explicit_service:
            assert "service_event_identity" in source, component["id"]

        actuator = component["actuator"]
        if actuator == "SafeActuator":
            assert "SafeActuator" in source, component["id"]
        elif actuator == "AsyncSafeActuator":
            assert "AsyncSafeActuator" in source, component["id"]
        elif actuator == "SafeActuator_and_AsyncSafeActuator":
            assert "SafeActuator" in source and "AsyncSafeActuator" in source, component["id"]
