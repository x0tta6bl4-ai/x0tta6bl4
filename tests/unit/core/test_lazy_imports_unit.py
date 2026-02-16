"""Unit tests for lazy import helpers."""

import pytest

from src.core.lazy_imports import LazyModule, lazy_import, lazy_import_group


def test_lazy_import_returns_lazy_module_proxy():
    mod = lazy_import("math")
    assert isinstance(mod, LazyModule)
    assert "pending" in repr(mod)


def test_lazy_module_loads_on_first_attribute_access():
    mod = lazy_import("math")
    assert mod.sqrt(16) == 4
    assert "loaded" in repr(mod)


def test_lazy_import_group_known_group_contains_expected_aliases():
    group = lazy_import_group("torch")
    assert "torch" in group
    assert "nn" in group
    assert all(isinstance(v, LazyModule) for v in group.values())


def test_lazy_import_group_unknown_group_raises_value_error():
    with pytest.raises(ValueError, match="Unknown group"):
        lazy_import_group("unknown-group")
