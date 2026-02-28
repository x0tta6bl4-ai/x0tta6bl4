"""
Security test conftest.

Ensures that module-level os.environ.setdefault() calls in other test modules
(e.g. tests/unit/monitoring/) don't pollute security tests that explicitly
need to test with FORCE_MOCK_SPIFFE=false or unset.
"""

import os
import pytest


@pytest.fixture(autouse=True)
def clear_spiffe_env():
    """Clear SPIFFE-related env vars that may be set during collection."""
    _SPIFFE_KEYS = [
        "X0TTA6BL4_FORCE_MOCK_SPIFFE",
        "X0TTA6BL4_PRODUCTION",
        "SPIFFE_ENDPOINT_SOCKET",
        "SPIFFE_TRUST_BUNDLE_PATH",
    ]
    saved = {k: os.environ.get(k) for k in _SPIFFE_KEYS}
    for k in _SPIFFE_KEYS:
        os.environ.pop(k, None)
    yield
    # restore
    for k, v in saved.items():
        if v is None:
            os.environ.pop(k, None)
        else:
            os.environ[k] = v
