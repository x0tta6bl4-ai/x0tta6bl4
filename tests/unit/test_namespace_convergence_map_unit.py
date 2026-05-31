from __future__ import annotations

import filecmp
import importlib
import json
import re
from pathlib import Path


ROOT = Path(__file__).resolve().parents[2]
MAP_PATH = ROOT / "docs/architecture/CURRENT_NAMESPACE_CONVERGENCE_MAP.json"
IMPORT_RE = re.compile(r"\b(?:from|import)\s+((?:src\.)?libx0t)(?:\.|\s|$)")


def _load_map() -> dict:
    return json.loads(MAP_PATH.read_text(encoding="utf-8"))


def _python_files(root: Path) -> set[Path]:
    return {
        path.relative_to(root)
        for path in root.rglob("*.py")
        if "__pycache__" not in path.parts
    }


def _import_counts() -> dict[str, int]:
    counts = {"libx0t": 0, "src.libx0t": 0}
    for root_name in _load_map()["import_counts"]["scanned_roots"]:
        for path in (ROOT / root_name).rglob("*.py"):
            if "__pycache__" in path.parts:
                continue
            for line in path.read_text(encoding="utf-8", errors="ignore").splitlines():
                match = IMPORT_RE.search(line)
                if match:
                    counts[match.group(1)] += 1
    return counts


def test_namespace_convergence_map_matches_current_file_tree_and_import_counts():
    namespace_map = _load_map()
    top_level = ROOT / namespace_map["surfaces"]["top_level_libx0t"]["path"]
    src_surface = ROOT / namespace_map["surfaces"]["src_libx0t"]["path"]

    top_level_files = _python_files(top_level)
    src_files = _python_files(src_surface)
    common = top_level_files & src_files
    identical = {
        rel
        for rel in common
        if filecmp.cmp(top_level / rel, src_surface / rel, shallow=False)
    }

    assert namespace_map["surfaces"]["top_level_libx0t"]["python_files"] == len(top_level_files)
    assert namespace_map["surfaces"]["src_libx0t"]["python_files"] == len(src_files)
    assert namespace_map["tree_comparison"]["common_python_paths"] == len(common)
    assert namespace_map["tree_comparison"]["byte_identical_common_paths"] == len(identical)
    assert namespace_map["tree_comparison"]["different_common_paths"] == len(common - identical)
    assert namespace_map["tree_comparison"]["top_level_only_python_paths"] == len(top_level_files - src_files)
    assert namespace_map["tree_comparison"]["src_only_python_paths"] == len(src_files - top_level_files)
    assert namespace_map["import_counts"]["direct_import_statements"] == _import_counts()


def test_namespace_convergence_source_refs_resolve_to_existing_files_and_lines():
    namespace_map = _load_map()
    source_refs = []
    for bridge in namespace_map["known_bridges"]:
        source_refs.extend(bridge["source_refs"])

    for source_ref in source_refs:
        path_text, line_text = source_ref.rsplit(":", 1)
        path = ROOT / path_text
        assert path.exists(), source_ref
        line_count = len(path.read_text(encoding="utf-8").splitlines())
        assert 1 <= int(line_text) <= line_count, source_ref


def test_src_path_restores_libx0t_compat_import_surface(monkeypatch):
    monkeypatch.setenv("PQC_FAIL_CLOSED", "false")

    for module_name in [
        "libx0t.security.post_quantum",
        "libx0t.security.pqc_core",
        "libx0t.security.pqc_mtls",
        "libx0t.security.production_hardening",
        "libx0t.security.zero_trust",
        "src.libx0t.core.production_lifespan",
        "libx0t.core.production_lifespan",
    ]:
        module = importlib.import_module(module_name)
        assert module is not None, module_name
        module_file = Path(module.__file__).resolve()
        assert str(module_file).startswith(str(ROOT / "src" / "libx0t")), module_name


def test_libx0t_network_compat_bridges_resolve_to_src_network():
    for module_name in [
        "libx0t.network.byzantine.mesh_byzantine_protection",
        "libx0t.network.byzantine.signed_gossip",
        "libx0t.network.ebpf.cilium_integration",
        "libx0t.network.ebpf.explainer",
    ]:
        module = importlib.import_module(module_name)
        module_file = Path(module.__file__).resolve()
        assert str(module_file).startswith(str(ROOT / "src" / "network")), module_name


def test_top_level_libx0t_source_tree_is_absent_and_src_surface_exists():
    namespace_map = _load_map()
    top_level = ROOT / namespace_map["surfaces"]["top_level_libx0t"]["path"]
    src_surface = ROOT / namespace_map["surfaces"]["src_libx0t"]["path"]

    assert not top_level.exists()
    assert (src_surface / "__init__.py").exists()
