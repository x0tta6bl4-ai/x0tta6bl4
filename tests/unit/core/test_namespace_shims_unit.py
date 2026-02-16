"""Tests for src.core/src.network compatibility shims."""

from __future__ import annotations

import importlib


def test_src_core_shim_imports_legacy_module() -> None:
    core_pkg = importlib.import_module("src.core")
    app_mod = importlib.import_module("src.core.app")

    assert any("libx0t/core" in p for p in core_pkg.__path__)
    assert "libx0t/core/app.py" in app_mod.__file__


def test_src_network_shim_imports_legacy_module() -> None:
    network_pkg = importlib.import_module("src.network")
    mesh_mod = importlib.import_module("src.network.mesh_node")

    assert any("libx0t/network" in p for p in network_pkg.__path__)
    assert "libx0t/network/mesh_node.py" in mesh_mod.__file__
