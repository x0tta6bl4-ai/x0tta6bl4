import os

os.environ.setdefault("X0TTA6BL4_PRODUCTION", "false")
os.environ.setdefault("X0TTA6BL4_SPIFFE", "false")
os.environ.setdefault("X0TTA6BL4_FORCE_MOCK_SPIFFE", "true")


def test_webrtc_leak_fix_import() -> None:
    import src.network.webrtc_leak_fix as mod

    assert mod is not None
