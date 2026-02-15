"""Unit tests for demo API handlers without ASGI startup."""

from unittest.mock import MagicMock

import pytest
from fastapi import HTTPException

from src.core import demo_api


@pytest.mark.asyncio
async def test_root_returns_expected_payload():
    payload = await demo_api.root()
    assert payload["name"] == "x0tta6bl4"
    assert payload["status"] == "operational"
    assert payload["components"]["mape_k"] == "integrated"


@pytest.mark.asyncio
async def test_get_status_uses_dependency_object():
    cycle = MagicMock()
    cycle.get_system_status.return_value = {"ok": True}

    result = await demo_api.get_status(cycle)

    assert result == {"ok": True}
    cycle.get_system_status.assert_called_once_with()


@pytest.mark.asyncio
async def test_demo_anomaly_detection_returns_json_response():
    cycle = MagicMock()
    cycle.run_cycle.return_value = {"result": "done"}

    response = await demo_api.demo_anomaly_detection({"node_id": "n1"}, cycle)

    assert response.status_code == 200
    assert response.body == b'{"result":"done"}'


@pytest.mark.asyncio
async def test_demo_anomaly_detection_wraps_error_as_http_500():
    cycle = MagicMock()
    cycle.run_cycle.side_effect = RuntimeError("boom")

    with pytest.raises(HTTPException) as exc:
        await demo_api.demo_anomaly_detection({"node_id": "n1"}, cycle)

    assert exc.value.status_code == 500
    assert "boom" in str(exc.value.detail)


@pytest.mark.asyncio
async def test_get_observe_mode_stats_returns_404_when_disabled():
    cycle = MagicMock()
    cycle.observe_detector = None

    with pytest.raises(HTTPException) as exc:
        await demo_api.get_observe_mode_stats(cycle)

    assert exc.value.status_code == 404
