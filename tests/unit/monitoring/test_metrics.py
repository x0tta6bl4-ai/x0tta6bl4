"""Unit tests for Prometheus metrics exporter."""

import pytest
from unittest.mock import MagicMock, patch
from src.monitoring.metrics import (
    http_requests_total,
    http_request_duration_seconds,
    mesh_peers_count,
    mesh_latency_seconds,
    mape_k_cycle_duration_seconds,
    self_healing_events_total,
    self_healing_mttr_seconds,
    node_health_status,
    node_uptime_seconds,
    update_mesh_peer_count,
    record_mesh_latency,
    record_mape_k_cycle,
    record_self_healing_event,
    record_mttr,
    set_node_health,
    set_node_uptime,
    get_metrics,
    MetricsMiddleware,
)


def test_update_mesh_peer_count():
    """Test updating mesh peer count metric."""
    update_mesh_peer_count("node-a", 2)
    # Verify metric was set (check internal state)
    metric = mesh_peers_count.labels(node_id="node-a")
    assert metric._value._value == 2


def test_record_mesh_latency():
    """Test recording mesh peer latency."""
    record_mesh_latency("node-a", "node-b", 0.123)
    # Verify histogram was updated (count increases)
    metric = mesh_latency_seconds.labels(node_id="node-a", peer_id="node-b")
    assert metric._sum._value > 0


def test_record_mape_k_cycle():
    """Test recording MAPE-K cycle duration."""
    record_mape_k_cycle("monitor", 0.05)
    record_mape_k_cycle("analyze", 0.1)
    # Verify histogram was updated
    metric = mape_k_cycle_duration_seconds.labels(phase="monitor")
    assert metric._sum._value > 0


def test_record_self_healing_event():
    """Test recording self-healing event counter."""
    record_self_healing_event("node_failure", "node-a")
    record_self_healing_event("node_failure", "node-a")
    # Verify counter incremented
    metric = self_healing_events_total.labels(event_type="node_failure", node_id="node-a")
    assert metric._value._value == 2


def test_record_mttr():
    """Test recording Mean Time To Recovery."""
    record_mttr("node_restart", 5.5)
    # Verify histogram was updated
    metric = self_healing_mttr_seconds.labels(recovery_type="node_restart")
    assert metric._sum._value > 0


def test_set_node_health():
    """Test setting node health status."""
    set_node_health("node-a", True)
    metric_healthy = node_health_status.labels(node_id="node-a")
    assert metric_healthy._value._value == 1
    
    set_node_health("node-b", False)
    metric_unhealthy = node_health_status.labels(node_id="node-b")
    assert metric_unhealthy._value._value == 0


def test_set_node_uptime():
    """Test setting node uptime."""
    set_node_uptime("node-a", 3600.5)
    metric = node_uptime_seconds.labels(node_id="node-a")
    assert metric._value._value == 3600.5


def test_get_metrics():
    """Test Prometheus metrics endpoint response."""
    response = get_metrics()
    assert response.media_type.startswith("text/plain")
    assert b"# HELP" in response.body or b"# TYPE" in response.body


@pytest.mark.asyncio
async def test_metrics_middleware_http_request():
    """Test MetricsMiddleware records HTTP requests."""
    # Mock ASGI app
    async def mock_app(scope, receive, send):
        await send({
            "type": "http.response.start",
            "status": 200,
            "headers": [],
        })
        await send({
            "type": "http.response.body",
            "body": b"OK",
        })
    
    middleware = MetricsMiddleware(mock_app)
    
    scope = {
        "type": "http",
        "method": "GET",
        "path": "/test",
    }
    
    async def mock_receive():
        return {"type": "http.request", "body": b""}
    
    responses = []
    async def mock_send(message):
        responses.append(message)
    
    # Execute middleware
    await middleware(scope, mock_receive, mock_send)
    
    # Verify metrics were recorded
    metric = http_requests_total.labels(method="GET", endpoint="/test", status=200)
    assert metric._value._value >= 1


@pytest.mark.asyncio
async def test_metrics_middleware_skips_metrics_endpoint():
    """Test MetricsMiddleware skips /metrics endpoint to avoid recursion."""
    call_count = 0
    
    async def mock_app(scope, receive, send):
        nonlocal call_count
        call_count += 1
        await send({
            "type": "http.response.start",
            "status": 200,
            "headers": [],
        })
    
    middleware = MetricsMiddleware(mock_app)
    
    scope = {
        "type": "http",
        "method": "GET",
        "path": "/metrics",
    }
    
    async def mock_receive():
        return {"type": "http.request"}
    
    async def mock_send(message):
        pass
    
    # Execute middleware (should not record metrics for /metrics)
    await middleware(scope, mock_receive, mock_send)
    
    assert call_count == 1  # App was called


@pytest.mark.asyncio
async def test_metrics_middleware_handles_exception():
    """Test MetricsMiddleware records metrics even on exception."""
    async def mock_app_error(scope, receive, send):
        raise ValueError("Simulated error")
    
    middleware = MetricsMiddleware(mock_app_error)
    
    scope = {
        "type": "http",
        "method": "POST",
        "path": "/error",
    }
    
    async def mock_receive():
        return {"type": "http.request"}
    
    async def mock_send(message):
        pass
    
    # Execute middleware (should catch exception and record metric)
    with pytest.raises(ValueError):
        await middleware(scope, mock_receive, mock_send)
    
    # Verify metric was recorded with status=500 (default)
    metric = http_requests_total.labels(method="POST", endpoint="/error", status=500)
    assert metric._value._value >= 1


@pytest.mark.asyncio
async def test_metrics_middleware_non_http_scope():
    """Test MetricsMiddleware passes through non-HTTP scopes."""
    async def mock_app(scope, receive, send):
        await send({"type": "websocket.accept"})
    
    middleware = MetricsMiddleware(mock_app)
    
    scope = {
        "type": "websocket",
        "path": "/ws",
    }
    
    async def mock_receive():
        return {"type": "websocket.connect"}
    
    messages = []
    async def mock_send(message):
        messages.append(message)
    
    # Execute middleware (should pass through websocket)
    await middleware(scope, mock_receive, mock_send)
    
    assert len(messages) == 1
    assert messages[0]["type"] == "websocket.accept"
