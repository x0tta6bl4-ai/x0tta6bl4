from __future__ import annotations

import json
import re
from pathlib import Path


ROOT = Path(__file__).resolve().parents[2]
MAP_PATH = ROOT / "docs/architecture/CURRENT_LIFECYCLE_READINESS_MAP.json"
APP_PATH = ROOT / "src/core/app.py"
LIFESPAN_PATH = ROOT / "src/core/production_lifespan.py"

INCLUDE_RE = re.compile(r'_include_maas_router\("([^"]+)",\s*"([^"]+)"\)')


def _load_map() -> dict:
    return json.loads(MAP_PATH.read_text(encoding="utf-8"))


def _module_path(module: str) -> Path:
    return ROOT / (module.replace(".", "/") + ".py")


def _app_router_registrations() -> list[dict[str, str]]:
    registrations: list[dict[str, str]] = []
    mode = "always"

    for line_no, line in enumerate(APP_PATH.read_text(encoding="utf-8").splitlines(), 1):
        stripped = line.strip()
        if stripped == "if not is_light_mode:":
            mode = "full_mode_only"
            continue
        if mode == "full_mode_only" and line and not line.startswith(" "):
            mode = "always"

        match = INCLUDE_RE.search(line)
        if match:
            module, label = match.groups()
            registrations.append(
                {
                    "module": module,
                    "label": label,
                    "registration_mode": mode,
                    "line": str(line_no),
                }
            )

    return registrations


def test_lifecycle_readiness_map_covers_current_app_router_registrations():
    lifecycle_map = _load_map()
    mapped = {
        (entry["module"], entry["label"], entry["registration_mode"])
        for entry in lifecycle_map["routers"]
    }
    actual = {
        (entry["module"], entry["label"], entry["registration_mode"])
        for entry in _app_router_registrations()
    }

    assert mapped == actual


def test_lifecycle_readiness_source_refs_resolve_to_existing_files_and_lines():
    lifecycle_map = _load_map()
    source_refs = [
        *lifecycle_map["app_lifespan_modes"]["light_mode"]["source_refs"],
        *lifecycle_map["app_lifespan_modes"]["non_light_mode"]["source_refs"],
        *lifecycle_map["production_lifespan_runtime"]["source_refs"],
    ]
    for router in lifecycle_map["routers"]:
        source_refs.extend(router["source_refs"])

    for source_ref in source_refs:
        path_text, line_text = source_ref.rsplit(":", 1)
        path = ROOT / path_text
        assert path.exists(), source_ref
        line_count = len(path.read_text(encoding="utf-8").splitlines())
        assert 1 <= int(line_text) <= line_count, source_ref


def test_lifecycle_hooks_are_declared_in_router_modules_and_called_by_lifespan():
    lifecycle_map = _load_map()
    lifespan_source = LIFESPAN_PATH.read_text(encoding="utf-8")

    hook_bound = [
        router
        for router in lifecycle_map["routers"]
        if router["lifecycle_binding"] == "production_lifespan_hook"
    ]
    assert {router["id"] for router in hook_bound} == {"edge-computing", "event-sourcing"}

    for router in hook_bound:
        module_source = _module_path(router["module"]).read_text(encoding="utf-8")
        startup_hook = router["startup_hook"]
        shutdown_hook = router["shutdown_hook"]

        assert f"async def {startup_hook}(" in module_source, router["id"]
        assert f"async def {shutdown_hook}(" in module_source, router["id"]
        assert router["runtime_readiness_field"] in module_source, router["id"]
        assert startup_hook in lifespan_source, router["id"]
        assert shutdown_hook in lifespan_source, router["id"]
        assert f"await {startup_hook}()" in lifespan_source, router["id"]
        assert f"await {shutdown_hook}()" in lifespan_source, router["id"]


def test_lifecycle_map_captures_light_mode_route_runtime_gap():
    lifecycle_map = _load_map()
    app_source = APP_PATH.read_text(encoding="utf-8")

    assert "lifespan=production_lifespan" in app_source
    assert 'os.getenv("MAAS_LIGHT_MODE", "false")' in app_source

    hook_bound = [
        router
        for router in lifecycle_map["routers"]
        if router["lifecycle_binding"] == "production_lifespan_hook"
    ]
    for router in hook_bound:
        assert router["registration_mode"] == "always", router["id"]
        assert router["route_present_in_light_mode"] is True, router["id"]
        assert router["hook_available_only_when_lifespan_runs"] is True, router["id"]
        assert "light mode" in router["hidden_dependency"], router["id"]
