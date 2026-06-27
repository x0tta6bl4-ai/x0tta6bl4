import asyncio
import json
from unittest.mock import AsyncMock, MagicMock, patch

from src.monitoring.alerting import AlertManager, AlertSeverity
from src.monitoring.advanced_sla_metrics import AdvancedSLAManager, MetricType
import src.monitoring.opentelemetry_tracing as otel_tracing_mod
from src.monitoring.production_monitoring import (
    AlertThreshold,
    MonitoringConfig,
    ProductionMonitor,
)
import src.monitoring.tracing as tracing_mod
from src.monitoring.tracing_optimizer import TracingOptimizer


def _status_text(status):
    return json.dumps(status, sort_keys=True, default=str)


def _assert_redacted(status, *raw_values):
    text = _status_text(status)
    for raw_value in raw_values:
        assert raw_value not in text


def test_alert_manager_thinking_status_redacts_alert_and_notifier_secrets():
    mock_http_client = MagicMock()
    mock_http_client.aclose = AsyncMock()
    with patch(
        "src.monitoring.alerting.httpx.AsyncClient",
        return_value=mock_http_client,
    ):
        manager = AlertManager(
            alertmanager_url="http://alertmanager-secret.local:9093",
            telegram_bot_token="telegram-secret-token",
            telegram_chat_id="telegram-secret-chat",
            pagerduty_integration_key="pagerduty-secret-key",
        )
    manager._channel_health = {
        "alertmanager": False,
        "telegram": False,
        "pagerduty": False,
    }

    try:
        asyncio.run(
            manager.send_alert(
                "private-alert-name",
                AlertSeverity.ERROR,
                "private alert message",
                labels={"node": "node-secret-value"},
                annotations={"runbook_url": "https://runbook-secret.local/path"},
            )
        )

        status = manager.get_thinking_status()
        assert status["thinking"]["profile"]["role"] == "monitoring"
        _assert_redacted(
            status,
            "http://alertmanager-secret.local:9093",
            "telegram-secret-token",
            "telegram-secret-chat",
            "pagerduty-secret-key",
            "private-alert-name",
            "private alert message",
            "node-secret-value",
            "https://runbook-secret.local/path",
        )
    finally:
        asyncio.run(manager.close())


def test_production_monitor_thinking_status_redacts_custom_metric_names():
    monitor = ProductionMonitor(
        config=MonitoringConfig(alert_thresholds=[], enable_alerting=True)
    )
    monitor.config.alert_thresholds = [
        AlertThreshold(
            "tenant-secret-metric",
            1.0,
            "gt",
            "critical",
            "tenant secret threshold description",
        )
    ]

    monitor._check_alerts(
        {
            "tenant-secret-metric": 2.0,
            "endpoint": "/tenant-secret/path",
            "timestamp": "2026-06-03T00:00:00",
        }
    )

    status = monitor.get_thinking_status()
    assert status["thinking"]["profile"]["role"] == "monitoring"
    _assert_redacted(
        status,
        "tenant-secret-metric",
        "/tenant-secret/path",
        "tenant secret threshold description",
    )


def test_tracing_optimizer_thinking_status_redacts_trace_payload():
    optimizer = TracingOptimizer()

    span = optimizer.create_span(
        "trace-secret-id",
        "span-secret-id",
        "operation-secret-name",
        "service-secret-name",
    )
    optimizer.end_span(
        span,
        status="error",
        error_message="database password timeout secret",
    )
    analysis = optimizer.analyze_trace("trace-secret-id")

    assert analysis["trace_id"] == "trace-secret-id"
    status = optimizer.get_thinking_status()
    assert status["thinking"]["profile"]["role"] == "monitoring"
    _assert_redacted(
        status,
        "trace-secret-id",
        "span-secret-id",
        "operation-secret-name",
        "service-secret-name",
        "database password timeout secret",
    )


def test_advanced_sla_thinking_status_redacts_metric_sla_and_labels():
    manager = AdvancedSLAManager()
    manager.register_metric(
        "tenant-secret-latency",
        MetricType.HISTOGRAM,
        unit="tenant-secret-ms",
        description="tenant secret description",
    )
    manager.record_metric(
        "tenant-secret-latency",
        150.0,
        labels={"tenant": "tenant-secret-value"},
    )
    manager.define_sla(
        "tenant-secret-sla",
        "tenant-secret-latency",
        200.0,
        "<=",
    )
    manager.check_all_slas()
    manager.get_compliance_report()

    status = manager.get_thinking_status()
    assert status["thinking"]["profile"]["role"] == "monitoring"
    _assert_redacted(
        status,
        "tenant-secret-latency",
        "tenant-secret-ms",
        "tenant secret description",
        "tenant-secret-value",
        "tenant-secret-sla",
    )


def test_otel_tracing_manager_thinking_status_redacts_disabled_runtime(monkeypatch):
    monkeypatch.setattr(otel_tracing_mod, "OTEL_AVAILABLE", False)
    manager = otel_tracing_mod.OTelTracingManager(
        service_name="otel-secret-service",
        jaeger_host="otel-secret-host",
    )

    initial_status = manager.get_thinking_status()
    _assert_redacted(initial_status, "otel-secret-service", "otel-secret-host")

    with manager.span(
        "otel-secret-span",
        {"otel-secret-key": "otel-secret-value"},
    ):
        pass

    @manager.span_decorator(
        "otel-secret-decorator",
        secret_static="otel-secret-static-value",
    )
    def _decorated():
        return "ok"

    assert _decorated() == "ok"
    status = manager.get_thinking_status()
    assert status["thinking"]["profile"]["role"] == "monitoring"
    _assert_redacted(
        status,
        "otel-secret-service",
        "otel-secret-host",
        "otel-secret-span",
        "otel-secret-key",
        "otel-secret-value",
        "otel-secret-decorator",
        "otel-secret-static-value",
    )


def test_tracing_manager_thinking_status_redacts_disabled_runtime(monkeypatch):
    monkeypatch.setattr(tracing_mod, "OPENTELEMETRY_AVAILABLE", False)
    manager = tracing_mod.TracingManager(
        service_name="trace-secret-service",
        service_version="trace-secret-version",
        jaeger_endpoint="http://trace-secret-jaeger/api/traces",
        zipkin_endpoint="http://trace-secret-zipkin/api/v2/spans",
        otlp_endpoint="http://trace-secret-otlp:4317",
    )

    initial_status = manager.get_thinking_status()
    _assert_redacted(
        initial_status,
        "trace-secret-service",
        "trace-secret-version",
        "http://trace-secret-jaeger/api/traces",
        "http://trace-secret-zipkin/api/v2/spans",
        "http://trace-secret-otlp:4317",
    )

    with manager.span("trace-secret-span", {"trace-secret-key": "trace-secret-value"}):
        pass
    manager.trace_network_adaptation(
        "trace-secret-action",
        {"route": "trace-secret-route"},
    )
    manager.trace_rag_retrieval("trace secret query", results_count=2, latency_ms=3.0)

    status = manager.get_thinking_status()
    assert status["thinking"]["profile"]["role"] == "monitoring"
    _assert_redacted(
        status,
        "trace-secret-service",
        "trace-secret-version",
        "trace-secret-span",
        "trace-secret-key",
        "trace-secret-value",
        "trace-secret-action",
        "trace-secret-route",
        "trace secret query",
    )
