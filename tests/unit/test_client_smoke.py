"""
Smoke tests for src.client modules.
Ensures all client modules can be imported without errors.
"""


def test_client_bridge_import():
    """src.client.bridge imports successfully."""
    import src.client.bridge  # noqa: F401


def test_client_engine_import():
    """src.client.engine imports successfully."""
    import src.client.engine  # noqa: F401


def test_client_gui_import():
    """src.client.gui imports successfully."""
    import src.client.gui  # noqa: F401
