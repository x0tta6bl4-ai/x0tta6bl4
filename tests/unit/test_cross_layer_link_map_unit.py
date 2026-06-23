from __future__ import annotations

import json
from pathlib import Path


ROOT = Path(__file__).resolve().parents[2]
CROSS_LAYER_MAP = ROOT / "docs/architecture/CURRENT_CROSS_LAYER_LINK_MAP.md"
EVENT_CONTROL_MAP = ROOT / "docs/architecture/CURRENT_EVENT_CONTROL_PLANE_MAP.json"
NAMESPACE_MAP = ROOT / "docs/architecture/CURRENT_NAMESPACE_CONVERGENCE_MAP.json"
CANONICAL_IMPORT_MAP = ROOT / "docs/architecture/CURRENT_CANONICAL_IMPORT_MAP.json"
LIFECYCLE_MAP = ROOT / "docs/architecture/CURRENT_LIFECYCLE_READINESS_MAP.json"


def test_cross_layer_link_map_tracks_event_control_plane_current_counts():
    text = CROSS_LAYER_MAP.read_text(encoding="utf-8")
    event_map = json.loads(EVENT_CONTROL_MAP.read_text(encoding="utf-8"))
    current_scan = event_map["current_scan"]

    event_surface_count = current_scan["event_surface_files"]
    service_identity_count = current_scan["service_identity_services"]
    event_type_count = current_scan["event_type_values"]
    event_trace_count = current_scan["event_trace_services"]

    assert (
        f"{event_surface_count} current `src` files touch the event/control surface"
        in text
    )
    assert (
        f"{service_identity_count} current services that call `service_event_identity()`"
        in text
    )
    assert f"tracks {event_surface_count} `src` files" in text
    assert f"{event_type_count} `EventType` values" in text
    assert (
        f"{service_identity_count} services that resolve canonical event identity"
        in text
    )
    assert (
        f"all {service_identity_count} current `service_event_identity()` callers"
        in text
    )
    assert f"current {event_type_count}-value EventType vocabulary" in text
    assert f"current {event_surface_count}-file event surface coverage" in text
    assert (
        f"all {service_identity_count} current service identity callers" in text
    )
    assert f"{event_trace_count} trace-visible services/APIs" in text
    assert "40 current `src` files touch the event/control surface" not in text
    assert "21 current services that call `service_event_identity()`" not in text
    assert "tracks 40 `src` files" not in text
    assert "31 `EventType` values" not in text
    assert "21 services that resolve canonical event identity" not in text
    assert "23 trace-visible services/APIs" not in text
    assert "all 21 current `service_event_identity()` callers" not in text
    assert "current 31-value EventType vocabulary" not in text
    assert "current 40-file event surface coverage" not in text
    assert "all 21 current service identity callers" not in text


def test_cross_layer_link_map_points_to_event_control_drift_guard():
    text = CROSS_LAYER_MAP.read_text(encoding="utf-8")

    assert "docs/architecture/CURRENT_EVENT_CONTROL_PLANE_MAP.json" in text
    assert "tests/unit/test_event_control_plane_map_unit.py" in text


def test_cross_layer_link_map_tracks_current_namespace_surface_counts():
    text = CROSS_LAYER_MAP.read_text(encoding="utf-8")
    namespace_map = json.loads(NAMESPACE_MAP.read_text(encoding="utf-8"))
    canonical_map = json.loads(CANONICAL_IMPORT_MAP.read_text(encoding="utf-8"))

    top_level_files = namespace_map["surfaces"]["top_level_libx0t"]["python_files"]
    src_files = namespace_map["surfaces"]["src_libx0t"]["python_files"]
    common_paths = namespace_map["tree_comparison"]["common_python_paths"]
    identical_paths = namespace_map["tree_comparison"]["byte_identical_common_paths"]
    src_only_paths = namespace_map["tree_comparison"]["src_only_python_paths"]
    repo_import_counts = canonical_map["current_scan"]["repo_direct_import_statements"]
    src_libx0t_imports = canonical_map["current_scan"][
        "src_libx0t_top_level_libx0t_import_statements"
    ]

    assert (
        f"Current namespace map shows {top_level_files} top-level `libx0t` "
        f"Python files, {src_files} `src/libx0t` Python files, "
        f"{common_paths} common paths, {identical_paths} byte-identical common "
        f"paths, and {src_only_paths} `src/libx0t`-only Python paths"
    ) in text
    assert (
        f"repo import scan currently sees {repo_import_counts['libx0t']} direct "
        f"`libx0t` imports and {repo_import_counts['src.libx0t']} direct "
        "`src.libx0t` imports"
    ) in text
    assert (
        f"Canonical import map tracks {src_libx0t_imports['total']} direct "
        "top-level imports inside `src/libx0t`"
    ) in text
    assert "top-level `libx0t` source tree is absent" in text
    assert "top-level security shims now re-export" not in text
    assert "154 top-level `libx0t` Python files" not in text
    assert "114 `src/libx0t` Python files" not in text
    assert "82 common paths" not in text
    assert "68 differing common paths" not in text


def test_cross_layer_link_map_tracks_current_lifecycle_router_model():
    text = CROSS_LAYER_MAP.read_text(encoding="utf-8")
    lifecycle_map = json.loads(LIFECYCLE_MAP.read_text(encoding="utf-8"))
    router_count = len(lifecycle_map["routers"])

    assert f"Current lifecycle map details: {router_count} router surfaces" in text
    assert (
        f"Lifecycle map tracks {router_count} router surfaces through the combined "
        "router and direct legacy/v1 includes"
    ) in text
    assert "get_combined_router()" in text
    assert "does not bind `production_lifespan`" in text
    assert "Lifecycle map tracks 23 router registrations" not in text
    assert "23 router registrations are tracked" not in text
    assert "full-mode-only" not in text
