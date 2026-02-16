import os

os.environ.setdefault("X0TTA6BL4_PRODUCTION", "false")
os.environ.setdefault("X0TTA6BL4_SPIFFE", "false")
os.environ.setdefault("X0TTA6BL4_FORCE_MOCK_SPIFFE", "true")


def test_algorithm_update_import_and_constants() -> None:
    import src.network.algorithm_update as mod

    assert "detect_patterns" in mod.ALGORITHM_UPDATES
    assert "reliability_score" in mod.REPUTATION_UPDATES
    assert "_register_default_metrics" in mod.METRICS_UPDATES
