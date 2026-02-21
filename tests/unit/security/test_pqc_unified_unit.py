"""
Unit tests for PQC module unification.

Verifies that:
1. All legacy import paths still work (no ImportError)
2. src.security.pqc is the single canonical entry point
3. Key classes are accessible from the unified module
4. No circular imports
"""
import importlib
import sys
import pytest


# ---------------------------------------------------------------------------
# Helper
# ---------------------------------------------------------------------------

def _reimport(module_name: str):
    """Force fresh import, bypassing sys.modules cache."""
    sys.modules.pop(module_name, None)
    return importlib.import_module(module_name)


# ---------------------------------------------------------------------------
# Test 1: canonical package imports cleanly
# ---------------------------------------------------------------------------

class TestCanonicalImports:
    def test_pqc_package_importable(self):
        """src.security.pqc package imports without error."""
        import src.security.pqc as pqc  # noqa: F401
        assert pqc is not None

    def test_canonical_new_api_available(self):
        """New canonical API classes are present in src.security.pqc."""
        from src.security.pqc import (
            PQCAdapter,
            PQCKeyExchange,
            PQCDigitalSignature,
            HybridKeyExchange,
            HybridSignatureScheme,
            is_liboqs_available,
            PQCAlgorithm,
            PQCKeyPair,
            PQCSignature,
            PQCEncapsulationResult,
        )
        assert callable(is_liboqs_available)
        assert PQCAdapter is not None
        assert PQCKeyExchange is not None
        assert PQCDigitalSignature is not None

    def test_liboqs_available_flag_accessible(self):
        """LIBOQS_AVAILABLE boolean flag accessible from canonical module."""
        from src.security.pqc import LIBOQS_AVAILABLE
        assert isinstance(LIBOQS_AVAILABLE, bool)

    def test_liboqs_available_consistent(self):
        """LIBOQS_AVAILABLE == is_liboqs_available()."""
        from src.security.pqc import LIBOQS_AVAILABLE, is_liboqs_available
        assert LIBOQS_AVAILABLE == is_liboqs_available()


# ---------------------------------------------------------------------------
# Test 2: legacy API accessible from canonical module
# ---------------------------------------------------------------------------

class TestLegacyAPIFromCanonical:
    def test_legacy_classes_accessible(self):
        """Legacy LibOQSBackend, HybridPQEncryption etc. accessible from src.security.pqc."""
        from src.security.pqc import (
            LibOQSBackend,
            HybridPQEncryption,
            PQMeshSecurityLibOQS,
            PQAlgorithm,
            PQKeyPair,
            PQCiphertext,
        )
        # These may be None if libx0t import fails, but must not raise ImportError
        assert True  # reaching here means no ImportError

    def test_pqc_core_helpers_accessible(self):
        """get_pqc_* helpers accessible from src.security.pqc."""
        from src.security.pqc import (
            get_pqc_key_exchange,
            get_pqc_digital_signature,
            get_pqc_hybrid,
            test_pqc_availability,
            PQCHybridScheme,
        )
        assert callable(get_pqc_key_exchange)
        assert callable(get_pqc_digital_signature)
        assert callable(get_pqc_hybrid)
        assert callable(test_pqc_availability)


# ---------------------------------------------------------------------------
# Test 3: shim paths still work (backward compat)
# ---------------------------------------------------------------------------

class TestShimImportPaths:
    def test_post_quantum_shim(self):
        """src.security.post_quantum shim redirects to libx0t (sys.modules-level)."""
        import warnings
        with warnings.catch_warnings():
            warnings.simplefilter("ignore", DeprecationWarning)
            # post_quantum.py is a sys.modules redirect to libx0t.security.post_quantum.
            # It exports libx0t's symbols: LibOQSBackend, LIBOQS_AVAILABLE, etc.
            from src.security.post_quantum import (  # noqa: F401
                LibOQSBackend,
                LIBOQS_AVAILABLE,
                HybridPQEncryption,
            )
        assert isinstance(LIBOQS_AVAILABLE, bool)

    def test_post_quantum_liboqs_shim(self):
        """src.security.post_quantum_liboqs shim re-exports correctly."""
        import warnings
        with warnings.catch_warnings():
            warnings.simplefilter("ignore", DeprecationWarning)
            from src.security.post_quantum_liboqs import (  # noqa: F401
                LIBOQS_AVAILABLE,
                LibOQSBackend,
                HybridPQEncryption,
                is_liboqs_available,
            )
        assert True

    def test_pqc_core_shim(self):
        """src.security.pqc_core shim re-exports correctly."""
        import warnings
        with warnings.catch_warnings():
            warnings.simplefilter("ignore", DeprecationWarning)
            from src.security.pqc_core import (  # noqa: F401
                PQCKeyExchange,
                PQCDigitalSignature,
                is_liboqs_available,
                LIBOQS_AVAILABLE,
            )
        assert True

    def test_pqc_adapter_submodule(self):
        """src.security.pqc.pqc_adapter (old submodule path) still importable."""
        # Some old code uses src.security.pqc.pqc_adapter instead of .adapter
        try:
            from src.security.pqc.pqc_adapter import PQCAdapter  # noqa: F401
            assert True
        except ImportError:
            pytest.skip("pqc_adapter.py not present (renamed to adapter.py)")

    def test_hybrid_tls_submodule(self):
        """src.security.pqc.hybrid_tls importable."""
        try:
            import src.security.pqc.hybrid_tls  # noqa: F401
            assert True
        except ImportError:
            pytest.skip("hybrid_tls optional deps not available")


# ---------------------------------------------------------------------------
# Test 4: no circular imports
# ---------------------------------------------------------------------------

class TestNoCircularImports:
    def test_no_circular_pqc_to_libx0t(self):
        """Importing src.security.pqc does NOT cause circular import error."""
        import warnings
        with warnings.catch_warnings():
            warnings.simplefilter("ignore", DeprecationWarning)
            # Re-importing fresh should be clean
            mod = importlib.import_module("src.security.pqc")
        assert mod is not None

    def test_compat_module_importable(self):
        """src.security.pqc.compat imports without error."""
        import warnings
        with warnings.catch_warnings():
            warnings.simplefilter("ignore", DeprecationWarning)
            from src.security.pqc import compat  # noqa: F401
        assert True


# ---------------------------------------------------------------------------
# Test 5: functional smoke tests (when liboqs available)
# ---------------------------------------------------------------------------

class TestFunctionalSmoke:
    @pytest.fixture(autouse=True)
    def require_liboqs(self):
        """Skip if liboqs is unavailable or mocked by conftest."""
        from src.security.pqc import is_liboqs_available
        if not is_liboqs_available():
            pytest.skip("liboqs not installed")
        # Detect conftest mocking: real oqs.KeyEncapsulation is a class, not a Mock
        import unittest.mock
        try:
            import oqs
            if isinstance(oqs, unittest.mock.MagicMock):
                pytest.skip("oqs mocked by conftest — skipping functional tests")
            # Also verify the module has real KeyEncapsulation class
            if not hasattr(oqs, "KeyEncapsulation") or isinstance(
                oqs.KeyEncapsulation, unittest.mock.MagicMock
            ):
                pytest.skip("oqs.KeyEncapsulation is mocked")
        except ImportError:
            pytest.skip("oqs not importable")

    def test_pqc_adapter_kem_roundtrip(self):
        """PQCAdapter: generate keypair, encapsulate, decapsulate."""
        from src.security.pqc import PQCAdapter
        adapter = PQCAdapter(kem_alg="ML-KEM-768", sig_alg="ML-DSA-65")

        pub, sec = adapter.kem_generate_keypair()
        assert len(pub) > 0
        assert len(sec) > 0

        ct, ss_enc = adapter.kem_encapsulate(pub)
        ss_dec = adapter.kem_decapsulate(sec, ct)
        assert ss_enc == ss_dec, "Shared secrets must match"

    def test_pqc_adapter_sig_roundtrip(self):
        """PQCAdapter: generate sig keypair, sign, verify."""
        from src.security.pqc import PQCAdapter
        adapter = PQCAdapter(kem_alg="ML-KEM-768", sig_alg="ML-DSA-65")

        pub, sec = adapter.sig_generate_keypair()
        message = b"x0tta6bl4 mesh beacon"
        sig = adapter.sig_sign(message, sec)
        assert adapter.sig_verify(message, sig, pub) is True
        assert adapter.sig_verify(b"tampered", sig, pub) is False

    def test_pqc_key_exchange_encapsulate_api(self):
        """PQCKeyExchange.encapsulate returns (ciphertext, shared_secret)."""
        from src.security.pqc import PQCKeyExchange
        kem = PQCKeyExchange()
        kp = kem.generate_keypair()
        ct, ss = kem.encapsulate(kp.public_key)
        ss2 = kem.decapsulate(kp.secret_key, ct)
        assert ss == ss2

    def test_legacy_liboqs_backend_kem(self):
        """LibOQSBackend.kem_encapsulate → (shared_secret, ciphertext) — legacy order."""
        import warnings
        with warnings.catch_warnings():
            warnings.simplefilter("ignore", DeprecationWarning)
            from src.security.pqc import LibOQSBackend
        if LibOQSBackend is None:
            pytest.skip("LibOQSBackend not available")
        backend = LibOQSBackend(kem_algorithm="ML-KEM-768", sig_algorithm="ML-DSA-65")
        kp = backend.generate_kem_keypair()
        # kem_encapsulate returns (shared_secret, ciphertext) — legacy order!
        ss, ct = backend.kem_encapsulate(kp.public_key)
        ss2 = backend.kem_decapsulate(kp.private_key, ct)
        assert ss == ss2

    def test_test_pqc_availability_returns_dict(self):
        """test_pqc_availability() returns status dict."""
        import warnings
        with warnings.catch_warnings():
            warnings.simplefilter("ignore", DeprecationWarning)
            from src.security.pqc import test_pqc_availability
        result = test_pqc_availability()
        assert isinstance(result, dict)
        assert "status" in result
