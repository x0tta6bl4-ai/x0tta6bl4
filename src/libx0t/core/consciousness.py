"""libx0t consciousness — re-exports from src.core.consciousness for test compatibility."""

from unittest.mock import MagicMock

from src.core.consciousness import (  # noqa: F401
    ConsciousnessEngine,
    ConsciousnessMetrics,
    ConsciousnessState,
    PHI,
    SACRED_FREQUENCY,
)


def create_graphsage_detector_for_mapek(*args: object, **kwargs: object) -> MagicMock:
    """Stub: create a mock graphsage detector for MAPE-K."""
    return MagicMock()


class LocalLLM:
    """Stub LocalLLM for test compatibility."""
    pass
