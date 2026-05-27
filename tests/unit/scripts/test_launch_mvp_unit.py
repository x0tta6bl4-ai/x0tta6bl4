from __future__ import annotations

import importlib.util
import sys
from pathlib import Path


def _load_module():
    repo_root = Path(__file__).resolve().parents[3]
    script_path = repo_root / "scripts" / "launch_mvp.py"
    spec = importlib.util.spec_from_file_location("launch_mvp", script_path)
    if spec is None or spec.loader is None:
        raise RuntimeError("Failed to load launch_mvp module")
    module = importlib.util.module_from_spec(spec)
    sys.modules[spec.name] = module
    spec.loader.exec_module(module)
    return module


def test_build_mapek_dependencies_uses_real_component_factories(monkeypatch):
    mod = _load_module()

    class _Mesh:
        def __init__(self, node_id):
            self.node_id = node_id

    class _Prometheus:
        pass

    class _ZeroTrust:
        pass

    monkeypatch.setenv("MVP_NODE_ID", "mvp-node-7")
    monkeypatch.setattr(mod, "MeshNetworkManager", _Mesh)
    monkeypatch.setattr(mod, "PrometheusExporter", _Prometheus)
    monkeypatch.setattr(mod, "ZeroTrustValidator", _ZeroTrust)

    dependencies = mod.build_mapek_dependencies()

    assert isinstance(dependencies["mesh"], _Mesh)
    assert dependencies["mesh"].node_id == "mvp-node-7"
    assert isinstance(dependencies["prometheus"], _Prometheus)
    assert isinstance(dependencies["zero_trust"], _ZeroTrust)


def test_build_mapek_dependencies_prefers_explicit_node_id(monkeypatch):
    mod = _load_module()

    class _Mesh:
        def __init__(self, node_id):
            self.node_id = node_id

    monkeypatch.setenv("MVP_NODE_ID", "env-node")
    monkeypatch.setattr(mod, "MeshNetworkManager", _Mesh)
    monkeypatch.setattr(mod, "PrometheusExporter", lambda: object())
    monkeypatch.setattr(mod, "ZeroTrustValidator", lambda: object())

    dependencies = mod.build_mapek_dependencies(node_id="explicit-node")

    assert dependencies["mesh"].node_id == "explicit-node"
