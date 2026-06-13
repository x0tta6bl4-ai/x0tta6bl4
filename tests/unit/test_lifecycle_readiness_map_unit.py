from __future__ import annotations

import json
import re
from pathlib import Path
from typing import Any


ROOT = Path(__file__).resolve().parents[2]
MAP_PATH = ROOT / "docs/architecture/CURRENT_LIFECYCLE_READINESS_MAP.json"
APP_PATH = ROOT / "src/core/app.py"
COMBINED_PATH = ROOT / "src/api/maas/endpoints/combined.py"
LIFESPAN_PATH = ROOT / "src/core/production_lifespan.py"

INCLUDE_RE = re.compile(r'_include_maas_router\("([^"]+)",\s*"([^"]+)"\)')


def _load_map() -> dict[str, Any]:
    return json.loads(MAP_PATH.read_text(encoding="utf-8"))


def _module_path(module: str) -> Path:
    return ROOT / (module.replace(".", "/") + ".py")


def _source_refs(value: Any) -> list[str]:
    refs: list[str] = []
    if isinstance(value, dict):
        for key, child in value.items():
            if key == "source_refs":
                refs.extend(str(item) for item in child)
            else:
                refs.extend(_source_refs(child))
    elif isinstance(value, list):
        for child in value:
            refs.extend(_source_refs(child))
    return refs


def _direct_app_router_registrations() -> set[tuple[str, str]]:
    registrations: set[tuple[str, str]] = set()
    for line in APP_PATH.read_text(encoding="utf-8").splitlines():
        match = INCLUDE_RE.search(line)
        if match:
            registrations.add(match.groups())
    return registrations


def test_lifecycle_map_tracks_current_combined_router_entrypoint():
    lifecycle_map = _load_map()
    app_source = APP_PATH.read_text(encoding="utf-8")
    combined_source = COMBINED_PATH.read_text(encoding="utf-8")

    entrypoint = lifecycle_map["combined_router_entrypoint"]
    assert entrypoint["module"] == "src.api.maas.endpoints.combined"
    assert entrypoint["registration_mode"] == "always"
    assert "get_combined_router" in app_source
    assert "app.include_router(get_combined_router())" in app_source
    assert "def get_combined_router(" in combined_source
    assert 'router.include_router(nodes_router, prefix=f"{p}/nodes")' in combined_source
    assert "router.include_router(nodes_router, prefix=p)" in combined_source
    assert "router.include_router(ledger_router, prefix=\"/api/v1/ledger\")" in combined_source


def test_lifecycle_map_covers_current_router_registration_sources():
    lifecycle_map = _load_map()
    routers = lifecycle_map["routers"]
    by_source: dict[str, set[tuple[str, str]]] = {}
    for router in routers:
        by_source.setdefault(router["registration_source"], set()).add(
            (router["module"], router["label"])
        )

    assert by_source["direct_app_include"] == _direct_app_router_registrations()
    assert {
        "src.api.maas.endpoints.nodes",
        "src.api.maas.endpoints.auth",
        "src.api.maas.endpoints.mesh",
        "src.api.maas.endpoints.billing",
        "src.api.maas.endpoints.telemetry",
        "src.api.maas.endpoints.ledger",
        "src.api.maas.endpoints.service_identity_status",
    }.issubset({module for module, _label in by_source["combined_router"]})
    assert "src.api.maas_legacy" not in {router["module"] for router in routers}
    assert all(router["registration_mode"] == "always" for router in routers)
    assert all(router["route_present_in_light_mode"] is True for router in routers)


def test_lifecycle_readiness_source_refs_resolve_to_existing_files_and_lines():
    lifecycle_map = _load_map()

    for source_ref in _source_refs(lifecycle_map):
        path_text, line_text = source_ref.rsplit(":", 1)
        path = ROOT / path_text
        assert path.exists(), source_ref
        line_count = len(path.read_text(encoding="utf-8").splitlines())
        assert 1 <= int(line_text) <= line_count, source_ref


def test_route_import_only_routers_declare_current_readiness_boundary():
    lifecycle_map = _load_map()

    route_only = [
        router
        for router in lifecycle_map["routers"]
        if router["lifecycle_binding"] == "route_import_only"
    ]
    assert route_only

    for router in route_only:
        source = _module_path(router["module"]).read_text(encoding="utf-8")
        assert "hidden_dependency" in router, router["id"]
        assert len(router["hidden_dependency"]) >= 80, router["id"]
        if router["readiness_signal"] == "none_explicit":
            assert router["runtime_readiness_field"] == "no_explicit_readiness_endpoint"
            assert "no explicit readiness" in router["hidden_dependency"], router["id"]
        else:
            assert router["runtime_readiness_field"] in source, router["id"]


def test_lifecycle_map_captures_current_lifespan_binding_gap():
    lifecycle_map = _load_map()
    app_source = APP_PATH.read_text(encoding="utf-8")
    lifespan_source = LIFESPAN_PATH.read_text(encoding="utf-8")

    assert "production_lifespan" not in app_source
    runtime = lifecycle_map["production_lifespan_runtime"]
    assert runtime["app_bound_by_core_app"] is False
    assert "does not bind production_lifespan" in runtime["binding_gap"]
    assert "async def production_lifespan(" in lifespan_source
    assert "await edge_startup()" in lifespan_source
    assert "await event_sourcing_startup()" in lifespan_source

    hook_bound = [
        router
        for router in lifecycle_map["routers"]
        if router["lifecycle_binding"] == "production_lifespan_hook_defined_not_app_bound"
    ]
    assert {router["id"] for router in hook_bound} == {
        "edge-computing",
        "event-sourcing",
    }
    for router in hook_bound:
        module_source = _module_path(router["module"]).read_text(encoding="utf-8")
        assert f"async def {router['startup_hook']}(" in module_source
        assert f"async def {router['shutdown_hook']}(" in module_source
        assert router["runtime_readiness_field"] in module_source
        assert "does not prove startup hooks ran" in router["hidden_dependency"]


def test_lifecycle_map_tracks_real_agent_node_access_as_local_lifecycle_only():
    lifecycle_map = _load_map()
    nodes = next(router for router in lifecycle_map["routers"] if router["id"] == "maas-nodes")
    verifier_source = (
        ROOT / "scripts/ops/verify_maas_real_agent_control_loop.py"
    ).read_text(encoding="utf-8")
    nodes_source = _module_path(nodes["module"]).read_text(encoding="utf-8")

    assert nodes["registration_source"] == "combined_router"
    assert nodes["readiness_signal"] == "/api/v1/maas/{mesh_id}/nodes/{node_id}/readiness"
    assert nodes["runtime_readiness_field"] == "core_node_readiness"
    assert "real Go-agent verifier" in nodes["hidden_dependency"]
    assert "temporary MaaS API" in nodes["hidden_dependency"]
    assert "does not prove live customer traffic" in nodes["hidden_dependency"]
    assert "production dataplane delivery" in nodes["hidden_dependency"]
    assert "production traffic" not in nodes["hidden_dependency"]
    assert "verify_maas_real_agent_control_loop.py" not in nodes["module"]
    assert "operator_heal_after_real_agent_heartbeat" in verifier_source
    assert "@router.get(\"/{mesh_id}/nodes/{node_id}/readiness\")" in nodes_source
    assert "core_node_readiness" in nodes_source


def test_lifecycle_map_selected_readiness_surfaces_match_current_modules():
    lifecycle_map = _load_map()
    routers = {router["id"]: router for router in lifecycle_map["routers"]}

    expected = {
        "maas-governance": (
            "src.api.maas.endpoints.governance",
            "/api/v1/maas/governance/readiness",
            "control_plane_ready",
        ),
        "ledger-api": (
            "src.api.maas.endpoints.ledger",
            "/api/v1/ledger/status",
            "ledger_runtime_ready",
        ),
        "maas-telemetry": (
            "src.api.maas.endpoints.telemetry",
            "/api/v1/maas/telemetry/readiness",
            "telemetry_runtime_ready",
        ),
        "service-identity-status": (
            "src.api.maas.endpoints.service_identity_status",
            "/api/v1/service-identity/status",
            "service_identity_runtime_ready",
        ),
        "billing-api": (
            "src.api.billing",
            "/api/v1/billing/readiness",
            "billing_api_runtime_ready",
        ),
    }

    for router_id, (module, readiness_signal, readiness_field) in expected.items():
        router = routers[router_id]
        source = _module_path(module).read_text(encoding="utf-8")
        assert router["module"] == module
        assert router["readiness_signal"] == readiness_signal
        assert router["runtime_readiness_field"] == readiness_field
        assert readiness_field in source


def test_lifecycle_map_claims_match_test_coverage():
    lifecycle_map = _load_map()

    for test_path in lifecycle_map["drift_checks"]:
        path = ROOT / test_path
        assert path.exists(), test_path

    assert "tests/unit/test_lifecycle_readiness_map_unit.py" in lifecycle_map["drift_checks"]
    assert "tests/unit/scripts/test_verify_maas_real_agent_control_loop.py" in lifecycle_map["drift_checks"]
    assert "scripts/ops/check_real_readiness.py" in lifecycle_map["drift_checks"]
