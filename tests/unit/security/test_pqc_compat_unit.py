"""Unit tests for src.security.pqc.compat fallback and export behavior."""

from __future__ import annotations

import builtins
import importlib
import sys

import pytest

COMPAT_MODULE = "src.security.pqc.compat"

EXPECTED_ALL = [
    "LIBOQS_AVAILABLE",
    "LibOQSBackend",
    "HybridPQEncryption",
    "PQMeshSecurityLibOQS",
    "PQAlgorithm",
    "PQKeyPair",
    "PQCiphertext",
    "PQCHybridScheme",
    "get_pqc_key_exchange",
    "get_pqc_digital_signature",
    "get_pqc_hybrid",
    "test_pqc_availability",
]


@pytest.fixture(autouse=True)
def _reset_compat_module():
    """Prevent forced-fallback module state from leaking to other tests."""
    sys.modules.pop(COMPAT_MODULE, None)
    yield
    sys.modules.pop(COMPAT_MODULE, None)
    importlib.import_module(COMPAT_MODULE)


def _import_compat_with_forced_import_error(
    monkeypatch: pytest.MonkeyPatch,
    *module_prefixes: str,
):
    real_import = builtins.__import__

    def _guarded_import(name, globals=None, locals=None, fromlist=(), level=0):
        if any(name == prefix or name.startswith(f"{prefix}.") for prefix in module_prefixes):
            raise ImportError(f"forced import error for {name}")
        return real_import(name, globals, locals, fromlist, level)

    monkeypatch.setattr(builtins, "__import__", _guarded_import)
    sys.modules.pop(COMPAT_MODULE, None)
    return importlib.import_module(COMPAT_MODULE)


def test_compat_exports_expected_symbols():
    mod = importlib.import_module(COMPAT_MODULE)
    assert mod.__all__ == EXPECTED_ALL


def test_post_quantum_import_error_uses_safe_placeholders(monkeypatch: pytest.MonkeyPatch):
    mod = _import_compat_with_forced_import_error(
        monkeypatch,
        "src.libx0t.security.post_quantum",
    )
    assert mod._LEGACY_POST_QUANTUM_AVAILABLE is False
    assert mod.LIBOQS_AVAILABLE is False
    assert mod.LibOQSBackend is None
    assert mod.HybridPQEncryption is None
    assert mod.PQAlgorithm is None
    assert mod.PQKeyPair is None
    assert mod.PQCiphertext is None
    assert mod.PQMeshSecurityLibOQS is None


def test_pqc_core_import_error_exposes_runtime_fallbacks(monkeypatch: pytest.MonkeyPatch):
    mod = _import_compat_with_forced_import_error(
        monkeypatch,
        "src.libx0t.security.pqc_core",
    )
    assert mod._LEGACY_PQC_CORE_AVAILABLE is False

    with pytest.raises(RuntimeError, match="pqc_core not available"):
        mod.get_pqc_key_exchange()
    with pytest.raises(RuntimeError, match="pqc_core not available"):
        mod.get_pqc_digital_signature()
    with pytest.raises(RuntimeError, match="pqc_core not available"):
        mod.get_pqc_hybrid()

    assert mod.test_pqc_availability() == {
        "status": "unavailable",
        "reason": "libx0t pqc_core missing",
    }


def test_both_legacy_imports_missing_still_keep_public_api(monkeypatch: pytest.MonkeyPatch):
    mod = _import_compat_with_forced_import_error(
        monkeypatch,
        "src.libx0t.security.post_quantum",
        "src.libx0t.security.pqc_core",
    )
    assert mod._LEGACY_POST_QUANTUM_AVAILABLE is False
    assert mod._LEGACY_PQC_CORE_AVAILABLE is False
    assert mod.__all__ == EXPECTED_ALL
