
import pytest
import hashlib
from unittest.mock import AsyncMock, MagicMock, patch
from src.monitoring.metrics import MetricsMiddleware

@pytest.mark.asyncio
async def test_metrics_middleware_extracts_api_key_header():
    """Проверка, что Middleware извлекает API-ключ из X-API-Key."""
    async def fake_app(scope, receive, send):
        await send({"type": "http.response.start", "status": 200})

    mw = MetricsMiddleware(fake_app)
    # Заголовок x-api-key в нижнем регистре (как это делает ASGI/FastAPI)
    scope = {
        "type": "http",
        "method": "GET",
        "path": "/api/test",
        "headers": [
            (b"x-api-key", b"test-client-123")
        ]
    }
    receive = AsyncMock()
    send = AsyncMock()

    with patch("src.monitoring.metrics._get_singleton_metrics") as mock_get:
        mock_registry = MagicMock()
        mock_get.return_value = mock_registry
        await mw(scope, receive, send)
        
        expected = hashlib.sha256(b"test-client-123").hexdigest()[:12]
        mock_registry.request_count.labels.assert_called_with(
            method="GET", endpoint="/api/test", status=200, api_key=f"api_key_{expected}"
        )

@pytest.mark.asyncio
async def test_metrics_middleware_extracts_bearer_token():
    """Проверка, что Middleware извлекает сокращенный токен из Authorization."""
    async def fake_app(scope, receive, send):
        await send({"type": "http.response.start", "status": 200})

    mw = MetricsMiddleware(fake_app)
    scope = {
        "type": "http",
        "method": "GET",
        "path": "/api/test",
        "headers": [
            (b"authorization", b"Bearer some-long-jwt-token-here")
        ]
    }
    receive = AsyncMock()
    send = AsyncMock()

    with patch("src.monitoring.metrics._get_singleton_metrics") as mock_get:
        mock_registry = MagicMock()
        mock_get.return_value = mock_registry
        await mw(scope, receive, send)
        
        expected = hashlib.sha256(b"some-long-jwt-token-here").hexdigest()[:12]
        mock_registry.request_count.labels.assert_called_with(
            method="GET", endpoint="/api/test", status=200, api_key=f"bearer_{expected}"
        )

@pytest.mark.asyncio
async def test_metrics_middleware_defaults_to_anonymous():
    """Проверка, что при отсутствии заголовков используется 'anonymous'."""
    async def fake_app(scope, receive, send):
        await send({"type": "http.response.start", "status": 200})

    mw = MetricsMiddleware(fake_app)
    scope = {
        "type": "http",
        "method": "GET",
        "path": "/api/test",
        "headers": []
    }
    receive = AsyncMock()
    send = AsyncMock()

    with patch("src.monitoring.metrics._get_singleton_metrics") as mock_get:
        mock_registry = MagicMock()
        mock_get.return_value = mock_registry
        await mw(scope, receive, send)
        
        mock_registry.request_count.labels.assert_called_with(
            method="GET", endpoint="/api/test", status=200, api_key="anonymous"
        )


@pytest.mark.asyncio
async def test_metrics_middleware_normalizes_dynamic_endpoint_segments():
    """Проверка нормализации динамических path segment для контроля кардинальности."""
    async def fake_app(scope, receive, send):
        await send({"type": "http.response.start", "status": 200})

    mw = MetricsMiddleware(fake_app)
    scope = {
        "type": "http",
        "method": "GET",
        "path": "/api/v1/maas/analytics/mesh-123456/summary",
        "headers": [],
    }
    receive = AsyncMock()
    send = AsyncMock()

    with patch("src.monitoring.metrics._get_singleton_metrics") as mock_get:
        mock_registry = MagicMock()
        mock_get.return_value = mock_registry
        await mw(scope, receive, send)

        mock_registry.request_count.labels.assert_called_with(
            method="GET",
            endpoint="/api/v1/maas/analytics/:id/summary",
            status=200,
            api_key="anonymous",
        )
