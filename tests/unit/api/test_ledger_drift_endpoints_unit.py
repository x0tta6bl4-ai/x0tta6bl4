from unittest.mock import AsyncMock, MagicMock

import pytest
from fastapi import FastAPI
from httpx import ASGITransport, AsyncClient

from src.api import ledger_drift_endpoints as endpoints
from src.api.ledger_drift_endpoints import router


def _build_app():
    app = FastAPI()
    app.include_router(router)
    return app


@pytest.mark.asyncio
async def test_detect_drift_hides_internal_error(monkeypatch):
    detector = MagicMock()
    detector.detect_drift = AsyncMock(
        side_effect=RuntimeError("secret-internal-details")
    )
    monkeypatch.setattr(endpoints, "get_drift_detector", lambda: detector)

    transport = ASGITransport(app=_build_app())
    async with AsyncClient(transport=transport, base_url="http://test") as client:
        resp = await client.post("/api/v1/ledger/drift/detect")
        assert resp.status_code == 500
        assert resp.json()["detail"] == "Ошибка обнаружения расхождений"


@pytest.mark.asyncio
async def test_status_handles_missing_initialized_attr(monkeypatch):
    detector = MagicMock()
    detector.anomaly_detector = object()
    detector.causal_engine = object()
    file_mock = MagicMock()
    file_mock.exists.return_value = True
    detector.continuity_file = file_mock
    if hasattr(detector, "_initialized"):
        delattr(detector, "_initialized")
    monkeypatch.setattr(endpoints, "get_drift_detector", lambda: detector)

    transport = ASGITransport(app=_build_app())
    async with AsyncClient(transport=transport, base_url="http://test") as client:
        resp = await client.get("/api/v1/ledger/drift/status")
        assert resp.status_code == 200
        payload = resp.json()
        assert payload["initialized"] is False
        assert payload["anomaly_detector_available"] is True
        assert payload["causal_engine_available"] is True
