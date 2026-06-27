import pytest

from src.core.app import health
from src.version import __version__


@pytest.mark.asyncio
async def test_health_endpoint_basic():
    data = await health()
    assert data["status"] == "ok"
    assert "version" in data and isinstance(data["version"], str)
    assert data["version"] == __version__
