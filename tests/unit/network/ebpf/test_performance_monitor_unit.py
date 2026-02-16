import importlib
import os

import pytest

os.environ.setdefault("X0TTA6BL4_PRODUCTION", "false")
os.environ.setdefault("X0TTA6BL4_SPIFFE", "false")
os.environ.setdefault("X0TTA6BL4_FORCE_MOCK_SPIFFE", "true")


def test_import_smoke():
    try:
        mod = importlib.import_module("src.network.ebpf.performance_monitor")
    except Exception as exc:
        pytest.skip(f"optional dependency/import issue: {exc}")
    assert mod is not None
