from __future__ import annotations

import ast
import json
from pathlib import Path
from typing import Any

from src.services.service_identity_registry import (
    KNOWN_EVENT_IDENTITY_SERVICES,
    KNOWN_EVENT_TRACE_SERVICES,
)


ROOT = Path(__file__).resolve().parents[2]
MAP_PATH = ROOT / "docs/architecture/CURRENT_EVENT_CONTROL_PLANE_MAP.json"

MARKER_REQUIREMENTS = {
    "event_bus": ("EventBus", "get_event_bus"),
    "event_contract": ("class EventType", "class EventBus", "def get_event_bus"),
    "event_contract_reexport": ("EventBus", "EventType"),
    "event_log_persistence": (".agent_coordination/events.log", "EVENT_LOG"),
    "event_bus_singleton": ("_event_bus", "def get_event_bus"),
    "service_identity": ("service_event_identity",),
    "service_identity_contract": ("def service_event_identity",),
    "service_identity_status": ("service_event_identity_status",),
    "service_identity_registry": ("service_identity_registry_status",),
    "service_event_trace": (
        "service_event_trace_filter",
        "service_event_trace_history",
        "get_service_event_history",
        "get_service_event_replay",
    ),
    "safe_actuator": ("SafeActuator",),
    "safe_actuator_evidence_metadata": ("safe_actuator_evidence_metadata",),
    "async_safe_actuator": ("AsyncSafeActuator",),
    "bounded_output_metadata": (
        "_bounded_output_metadata",
        "stdout_sha256",
        "stderr_sha256",
    ),
    "marketplace_event_helper": ("publish_marketplace_escrow_event",),
    "reward_event_helper": ("publish_reward_settlement_event",),
}


def _load_map() -> dict[str, Any]:
    return json.loads(MAP_PATH.read_text(encoding="utf-8"))


def _source_refs(value: Any) -> list[str]:
    refs: list[str] = []
    if isinstance(value, dict):
        for key, child in value.items():
            if key == "source_refs":
                refs.extend(str(item) for item in child)
            elif key == "source_ref":
                refs.append(str(child))
            else:
                refs.extend(_source_refs(child))
    elif isinstance(value, list):
        for child in value:
            refs.extend(_source_refs(child))
    return refs


def _event_type_values_from_source() -> list[str]:
    tree = ast.parse((ROOT / "src/coordination/events.py").read_text(encoding="utf-8"))
    for node in tree.body:
        if isinstance(node, ast.ClassDef) and node.name == "EventType":
            values: list[str] = []
            for child in node.body:
                if (
                    isinstance(child, ast.Assign)
                    and isinstance(child.value, ast.Constant)
                    and isinstance(child.value.value, str)
                ):
                    values.append(child.value.value)
            return values
    raise AssertionError("EventType class not found")


def _current_event_surface_files() -> list[str]:
    markers = _load_map()["current_scan"]["markers"]
    paths: list[str] = []
    for path in sorted((ROOT / "src").rglob("*.py")):
        if "__pycache__" in path.parts:
            continue
        source = path.read_text(encoding="utf-8", errors="ignore")
        if any(marker in source for marker in markers):
            paths.append(str(path.relative_to(ROOT)))
    return paths


def test_event_control_plane_map_source_refs_resolve_to_existing_lines():
    event_map = _load_map()

    for source_ref in _source_refs(event_map):
        path_text, line_text = source_ref.rsplit(":", 1)
        path = ROOT / path_text
        assert path.exists(), source_ref
        line_count = len(path.read_text(encoding="utf-8").splitlines())
        assert 1 <= int(line_text) <= line_count, source_ref


def test_event_control_plane_map_tracks_current_event_type_vocabulary():
    event_map = _load_map()
    expected = event_map["shared_contracts"]["event_bus"]["event_type_values"]

    assert expected == _event_type_values_from_source()
    assert event_map["current_scan"]["event_type_values"] == len(expected)


def test_event_control_plane_map_tracks_service_identity_registry_size():
    event_map = _load_map()
    services_total = len(KNOWN_EVENT_IDENTITY_SERVICES)

    assert event_map["current_scan"]["service_identity_services"] == services_total
    assert (
        event_map["shared_contracts"]["service_identity_status"]["services_total"]
        == services_total
    )


def test_event_control_plane_map_tracks_event_trace_registry_size():
    event_map = _load_map()

    assert event_map["current_scan"]["event_trace_services"] == len(
        KNOWN_EVENT_TRACE_SERVICES
    )


def test_event_control_plane_map_covers_current_event_surface_files():
    event_map = _load_map()
    mapped_paths = sorted(item["path"] for item in event_map["event_surface_files"])

    assert event_map["current_scan"]["event_surface_files"] == len(mapped_paths)
    assert mapped_paths == _current_event_surface_files()


def test_event_control_plane_surface_markers_match_sources():
    event_map = _load_map()

    for item in event_map["event_surface_files"]:
        source = (ROOT / item["path"]).read_text(encoding="utf-8")
        for marker in item["markers"]:
            requirements = MARKER_REQUIREMENTS[marker]
            assert any(text in source for text in requirements), (item["path"], marker)


def test_event_control_plane_map_records_token_bridge_safe_actuator_boundary():
    event_map = _load_map()
    surfaces = {item["path"]: item for item in event_map["event_surface_files"]}

    token_bridge = surfaces["src/dao/bridge/core.py"]
    assert "safe_actuator_evidence_metadata" in token_bridge["markers"]
    assert "typed SafeActuatorEvidenceMetadata" in token_bridge["role"]
    assert "pending transaction submission" in token_bridge["role"]
    assert "external settlement finality" in token_bridge["role"]
    assert "payment-provider settlement" in token_bridge["role"]
    assert "bank settlement" in token_bridge["role"]
    assert "live token-settlement finality" in token_bridge["role"]
    assert "dataplane delivery" in token_bridge["role"]
    assert "traffic/customer delivery" in token_bridge["role"]
    assert "revenue recognition" in token_bridge["role"]
    assert "production readiness" in token_bridge["role"]
    assert "src/dao/bridge/core.py:605" in token_bridge["source_refs"]


def test_event_control_plane_map_records_current_safe_actuator_adoption_state():
    event_map = _load_map()
    links = {item["id"]: item for item in event_map["non_obvious_links"]}
    link = links["safe-actuator-is-cross-layer-not-local"]
    summary = link["summary"]

    assert "parse-error-free adoption inventory" in summary
    assert "21/21" in summary
    assert "63/63" in summary
    assert "19 EventBus + 5 result-metadata" in summary
    assert "production, dataplane, trust-finality, settlement" in summary
    assert "customer-traffic claims" in summary
    assert "still incremental" not in summary
    assert "src/integration/spine.py:14" in link["source_refs"]
    assert "src/api/maas/endpoints/governance.py:26" in link["source_refs"]
    assert "src/network/mptcp_manager.py:16" in link["source_refs"]


def test_non_obvious_links_reference_mapped_event_surfaces():
    event_map = _load_map()
    mapped_paths = {item["path"] for item in event_map["event_surface_files"]}

    for link in event_map["non_obvious_links"]:
        assert link["source_refs"], link["id"]
        for source_ref in link["source_refs"]:
            path_text, _line_text = source_ref.rsplit(":", 1)
            assert path_text in mapped_paths, (link["id"], source_ref)
