from __future__ import annotations

import ast
import json
import re
from pathlib import Path
from typing import Any


ROOT = Path(__file__).resolve().parents[2]
MAP_PATH = ROOT / "docs/architecture/CURRENT_CANONICAL_IMPORT_MAP.json"
IMPORT_RE = re.compile(r"\b(?:from|import)\s+((?:src\.)?libx0t)(?:\.|\s|$)")


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


def _top_level_imports_under(
    root_name: str, *, exclude_prefixes: tuple[str, ...] = ()
) -> list[dict[str, Any]]:
    imports: list[dict[str, Any]] = []
    for path in sorted((ROOT / root_name).rglob("*.py")):
        if "__pycache__" in path.parts:
            continue
        rel_path = str(path.relative_to(ROOT))
        if any(rel_path.startswith(prefix) for prefix in exclude_prefixes):
            continue
        tree = ast.parse(path.read_text(encoding="utf-8"))
        for node in ast.walk(tree):
            modules: list[str] = []
            if isinstance(node, ast.ImportFrom) and node.module:
                modules.append(node.module)
            elif isinstance(node, ast.Import):
                modules.extend(alias.name for alias in node.names)

            for module in modules:
                if module == "libx0t" or module.startswith("libx0t."):
                    imports.append(
                        {
                            "path": rel_path,
                            "line": node.lineno,
                            "module": module,
                            "source_ref": f"{rel_path}:{node.lineno}",
                        }
                    )
    return imports


def _src_libx0t_top_level_imports() -> list[dict[str, Any]]:
    return _top_level_imports_under("src/libx0t")


def _src_runtime_top_level_imports() -> list[dict[str, Any]]:
    return _top_level_imports_under("src", exclude_prefixes=("src/libx0t/",))


def _test_top_level_imports() -> list[dict[str, Any]]:
    return _top_level_imports_under("tests")


def _script_top_level_import_refs() -> list[str]:
    refs: list[str] = []
    for path in sorted((ROOT / "scripts").rglob("*.py")):
        if "__pycache__" in path.parts:
            continue
        rel_path = str(path.relative_to(ROOT))
        for line_number, line in enumerate(
            path.read_text(encoding="utf-8", errors="ignore").splitlines(), start=1
        ):
            match = IMPORT_RE.search(line)
            if match and match.group(1) == "libx0t":
                refs.append(f"{rel_path}:{line_number}")
    return refs


def _src_libx0t_counterpart_exists(module: str) -> bool:
    if module == "libx0t":
        return (ROOT / "src/libx0t/__init__.py").exists()

    tail = module.removeprefix("libx0t.")
    tail_path = Path(*tail.split("."))
    return (
        (ROOT / "src/libx0t" / tail_path).with_suffix(".py").exists()
        or (ROOT / "src/libx0t" / tail_path / "__init__.py").exists()
    )


def _top_level_libx0t_counterpart_exists(module: str) -> bool:
    if module == "libx0t":
        return (ROOT / "libx0t/__init__.py").exists()

    tail = module.removeprefix("libx0t.")
    tail_path = Path(*tail.split("."))
    return (
        (ROOT / "libx0t" / tail_path).with_suffix(".py").exists()
        or (ROOT / "libx0t" / tail_path / "__init__.py").exists()
    )


def _repo_direct_import_counts() -> dict[str, int]:
    counts = {"libx0t": 0, "src.libx0t": 0}
    for root_name in _load_map()["current_scan"]["scanned_roots_for_repo_import_counts"]:
        for path in (ROOT / root_name).rglob("*.py"):
            if "__pycache__" in path.parts:
                continue
            for line in path.read_text(encoding="utf-8", errors="ignore").splitlines():
                match = IMPORT_RE.search(line)
                if match:
                    counts[match.group(1)] += 1
    return counts


def test_canonical_import_map_source_refs_resolve_to_existing_lines():
    import_map = _load_map()

    for source_ref in _source_refs(import_map):
        path_text, line_text = source_ref.rsplit(":", 1)
        path = ROOT / path_text
        assert path.exists(), source_ref
        line_count = len(path.read_text(encoding="utf-8").splitlines())
        assert 1 <= int(line_text) <= line_count, source_ref


def test_src_libx0t_has_no_top_level_import_when_src_counterpart_exists():
    bad_imports = [
        item
        for item in _src_libx0t_top_level_imports()
        if _src_libx0t_counterpart_exists(item["module"])
    ]

    assert bad_imports == []


def test_remaining_src_libx0t_top_level_imports_match_allowed_exceptions():
    import_map = _load_map()
    observed = sorted(
        _src_libx0t_top_level_imports(),
        key=lambda item: (item["path"], item["line"], item["module"]),
    )
    expected = sorted(
        [
            {
                "path": item["path"],
                "line": item["line"],
                "module": item["module"],
                "source_ref": item["source_ref"],
            }
            for item in import_map["allowed_top_level_only_imports_in_src_libx0t"]
        ],
        key=lambda item: (item["path"], item["line"], item["module"]),
    )

    assert observed == expected


def test_src_runtime_has_no_direct_top_level_libx0t_imports():
    assert _src_runtime_top_level_imports() == []


def test_top_level_libx0t_import_surface_is_test_compatibility_only():
    import_map = _load_map()
    surface = import_map["test_compatibility_import_surface"]
    observed_test_refs = sorted(
        item["source_ref"] for item in _test_top_level_imports()
    )

    assert surface["runtime_src_imports_total"] == 0
    assert surface["scripts_imports_total"] == 0
    assert _src_runtime_top_level_imports() == []
    assert _script_top_level_import_refs() == []
    assert surface["imports_total"] == len(observed_test_refs)
    assert observed_test_refs == sorted(surface["source_refs"])


def test_allowed_src_libx0t_top_level_imports_resolve_to_real_top_level_modules():
    for item in _load_map()["allowed_top_level_only_imports_in_src_libx0t"]:
        assert not _src_libx0t_counterpart_exists(item["module"]), item
        assert _top_level_libx0t_counterpart_exists(item["module"]), item


def test_src_libx0t_bridge_modules_point_to_real_top_level_modules():
    for bridge in _load_map()["src_libx0t_top_level_bridge_modules"]:
        bridge_path = ROOT / bridge["path"]
        top_level_path = ROOT / bridge["top_level_path"]
        source = bridge_path.read_text(encoding="utf-8")

        assert bridge_path.exists(), bridge
        assert top_level_path.exists(), bridge
        assert "import_module" in source, bridge["path"]
        assert bridge["target"] in source, bridge["path"]


def test_src_libx0t_runtime_imports_use_network_bridge_modules():
    source_refs = next(
        item["source_refs"]
        for item in _load_map()["repaired_import_holes"]
        if item["id"] == "src-libx0t-network-canonical-imports"
    )

    for source_ref in source_refs:
        path_text, line_text = source_ref.rsplit(":", 1)
        line = (ROOT / path_text).read_text(encoding="utf-8").splitlines()[
            int(line_text) - 1
        ]
        assert "src.libx0t.network" in line, source_ref


def test_src_libx0t_network_compat_bridges_target_src_network():
    source_refs = next(
        item["source_refs"]
        for item in _load_map()["repaired_import_holes"]
        if item["id"] == "src-libx0t-network-compat-bridges-to-src-network"
    )

    for source_ref in source_refs:
        path_text, line_text = source_ref.rsplit(":", 1)
        line = (ROOT / path_text).read_text(encoding="utf-8").splitlines()[
            int(line_text) - 1
        ]
        assert "src.network" in line, source_ref
        assert "libx0t.network" not in line, source_ref


def test_src_runtime_import_repairs_use_src_libx0t():
    source_refs = next(
        item["source_refs"]
        for item in _load_map()["repaired_import_holes"]
        if item["id"] == "src-runtime-direct-top-level-libx0t-imports-canonicalized"
    )

    for source_ref in source_refs:
        path_text, line_text = source_ref.rsplit(":", 1)
        line = (ROOT / path_text).read_text(encoding="utf-8").splitlines()[
            int(line_text) - 1
        ]
        assert "src.libx0t" in line, source_ref
        assert "from libx0t" not in line, source_ref
        assert "import libx0t" not in line, source_ref


def test_canonical_import_counts_match_current_scan():
    import_map = _load_map()
    observed = _src_libx0t_top_level_imports()
    with_counterpart = [
        item for item in observed if _src_libx0t_counterpart_exists(item["module"])
    ]

    assert import_map["current_scan"]["repo_direct_import_statements"] == (
        _repo_direct_import_counts()
    )
    assert (
        import_map["current_scan"]["src_libx0t_top_level_libx0t_import_statements"]
        == {
            "total": len(observed),
            "with_src_libx0t_counterpart": len(with_counterpart),
            "top_level_only": len(observed) - len(with_counterpart),
        }
    )


def test_production_checks_use_existing_pqc_module():
    source = (ROOT / "src/libx0t/core/production_checks.py").read_text(
        encoding="utf-8"
    )

    assert "post_quantum_liboqs" not in source
    assert "from src.security.pqc import LIBOQS_AVAILABLE" in source


def test_production_system_uses_existing_hardening_module():
    source = (ROOT / "src/libx0t/core/production_system.py").read_text(
        encoding="utf-8"
    )

    assert "from src.security.production_hardening import get_hardening_manager" in source
    legacy_import = "from " + "libx0t.security.production_hardening import"
    assert legacy_import not in source


def test_pqc_runtime_imports_use_canonical_security_pqc_module():
    for rel_path in [
        "src/security/pqc_identity.py",
        "src/network/discovery/protocol.py",
    ]:
        source = (ROOT / rel_path).read_text(encoding="utf-8")
        assert "from src.security.pqc import" in source, rel_path
        assert "src.libx0t.security.post_quantum" not in source, rel_path


def test_top_level_security_shims_delegate_to_canonical_modules():
    for shim in _load_map()["top_level_security_shims"]:
        source = (ROOT / shim["path"]).read_text(encoding="utf-8")
        assert shim["target"] in source, shim["path"]
