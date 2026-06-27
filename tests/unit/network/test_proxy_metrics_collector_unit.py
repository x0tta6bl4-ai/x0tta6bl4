import os

import pytest

os.environ.setdefault("X0TTA6BL4_PRODUCTION", "false")
os.environ.setdefault("X0TTA6BL4_SPIFFE", "false")
os.environ.setdefault("X0TTA6BL4_FORCE_MOCK_SPIFFE", "true")

from src.coordination.events import EventBus, EventType
import src.network.proxy_metrics_collector as mod


def _clear_proxy_metrics_identity(monkeypatch):
    for name in (
        "PROXY_METRICS_COLLECTOR_SPIFFE_ID",
        "PROXY_METRICS_COLLECTOR_DID",
        "PROXY_METRICS_COLLECTOR_WALLET_ADDRESS",
        "X0TTA6BL4_SERVICE_SPIFFE_ID",
        "X0TTA6BL4_SERVICE_DID",
        "X0TTA6BL4_SERVICE_WALLET_ADDRESS",
        "SERVICE_SPIFFE_ID",
        "SERVICE_DID",
        "SERVICE_WALLET_ADDRESS",
        "SPIFFE_ID",
        "DID",
        "GHOST_WALLET_ADDRESS",
    ):
        monkeypatch.delenv(name, raising=False)


def test_metric_series_add_and_retention_cleanup(monkeypatch):
    now = {"t": 1000.0}
    monkeypatch.setattr(mod.time, "time", lambda: now["t"])
    series = mod.MetricSeries(
        name="m",
        metric_type=mod.MetricType.GAUGE,
        description="desc",
        retention_seconds=10,
    )

    series.add(1.0)
    now["t"] = 1005.0
    series.add(2.0)
    now["t"] = 1012.0
    series.add(3.0)

    assert [v.value for v in series.values] == [2.0, 3.0]
    assert series.get_latest() == 3.0


def test_metric_series_get_latest_on_empty_series():
    series = mod.MetricSeries(
        name="empty",
        metric_type=mod.MetricType.GAUGE,
        description="empty metric",
    )
    assert series.get_latest() is None


def test_metric_series_statistics_and_rate(monkeypatch):
    now = {"t": 1000.0}
    monkeypatch.setattr(mod.time, "time", lambda: now["t"])
    series = mod.MetricSeries(
        name="counter",
        metric_type=mod.MetricType.COUNTER,
        description="desc",
        retention_seconds=5000,
    )

    series.add(0.0)
    now["t"] = 1010.0
    series.add(20.0)
    now["t"] = 1020.0
    series.add(40.0)
    now["t"] = 1030.0

    assert series.get_average(window_seconds=60) == 20.0
    assert series.get_percentile(95, window_seconds=60) == 40.0
    assert series.get_rate(window_seconds=60) == pytest.approx((40.0 - 0.0) / 60.0)

    now["t"] = 2000.0
    assert series.get_average(window_seconds=10) is None
    assert series.get_percentile(50, window_seconds=10) is None
    assert series.get_rate(window_seconds=10) == 0.0


def test_proxy_metrics_snapshot_to_dict_roundtrip():
    snapshot = mod.ProxyMetricsSnapshot(
        timestamp=1700000000.0,
        proxy_id="p-1",
        total_requests=10,
        successful_requests=8,
        failed_requests=2,
        blocked_requests=1,
        avg_latency=123.456,
        p50_latency=100.0,
        p95_latency=250.5,
        p99_latency=400.8,
        errors_by_type={"timeout": 2},
        health_status="healthy",
        consecutive_failures=0,
    )

    assert snapshot.success_rate() == 0.8
    payload = snapshot.to_dict()
    assert payload["proxy_id"] == "p-1"
    assert payload["requests"]["success_rate"] == 0.8
    assert payload["latency_ms"]["avg"] == 123.46
    assert payload["errors"]["timeout"] == 2
    assert payload["health"]["status"] == "healthy"


def test_proxy_metrics_snapshot_success_rate_zero_total():
    snapshot = mod.ProxyMetricsSnapshot(timestamp=1700000000.0, proxy_id="p-zero")
    assert snapshot.success_rate() == 0.0
    payload = snapshot.to_dict()
    assert payload["requests"]["success_rate"] == 0.0


@pytest.mark.asyncio
async def test_register_and_record_known_and_unknown_metrics(caplog):
    collector = mod.ProxyMetricsCollector(retention_hours=1)
    collector.register_metric("m1", mod.MetricType.COUNTER, "metric 1")
    collector.register_metric("m1", mod.MetricType.COUNTER, "metric 1 duplicated")
    assert list(collector.metrics.keys()) == ["m1"]

    await collector.record("m1", 5.0, {"k": "v"})
    assert collector.get_metric("m1").get_latest() == 5.0

    with caplog.at_level("WARNING"):
        await collector.record("missing", 1.0)
    assert "Unknown metric: missing" in caplog.text


@pytest.mark.asyncio
async def test_record_proxy_request_health_and_domain_request():
    collector = mod.create_default_collector()

    await collector.record_proxy_request("p-1", success=True, latency_ms=10.0)
    await collector.record_proxy_request(
        "p-1", success=False, latency_ms=30.0, error_type="timeout"
    )
    await collector.record_proxy_health("p-1", is_healthy=False, response_time_ms=99.0)
    await collector.record_domain_request(
        "example.com", "p-1", success=False, latency_ms=15.0
    )
    await collector.record_domain_request(
        "example.com", "p-1", success=True, latency_ms=11.0
    )

    failed_values = collector.get_metric("proxy_requests_failed").values
    assert len(failed_values) == 1
    assert failed_values[0].labels["error_type"] == "timeout"
    assert collector.get_metric("proxy_latency_ms").get_latest() == 30.0
    assert collector.get_metric("proxy_health_check").get_latest() == 0
    assert collector.get_metric("domain_requests_failed").get_latest() == 1
    assert collector.get_metric("domain_requests_success").get_latest() == 1


@pytest.mark.asyncio
async def test_record_proxy_request_publishes_redacted_evidence(
    tmp_path, monkeypatch
):
    _clear_proxy_metrics_identity(monkeypatch)
    bus = EventBus(project_root=str(tmp_path))
    collector = mod.create_default_collector(event_bus=bus)

    await collector.record_proxy_request(
        "proxy-secret-1",
        success=False,
        latency_ms=42.5,
        error_type="timeout-with-secret",
    )

    events = bus.get_event_history(
        event_type=EventType.PIPELINE_STAGE_END,
        source_agent="proxy-metrics-collector",
    )
    assert len(events) == 1
    payload = events[0].data
    assert payload["component"] == "network.proxy_metrics_collector"
    assert payload["operation"] == "record_proxy_request"
    assert payload["service_name"] == "proxy-metrics-collector"
    assert payload["layer"] == "network_proxy_metrics_observed_state"
    assert payload["status"] == "proxy_request_metric_recorded"
    assert payload["success"] is True
    assert payload["proxy_id_hash"].startswith("sha256:")
    assert payload["request_success"] is False
    assert payload["latency_ms"] == 42.5
    assert payload["error_type_present"] is True
    assert payload["error_type_hash"].startswith("sha256:")
    assert payload["metrics_configured"]["proxy_requests_failed"] is True
    assert payload["service_identity_present"] == {
        "spiffe_id": False,
        "did": False,
        "wallet_address": False,
    }
    assert "raw metric labels" in payload["claim_boundary"]
    text = str(payload)
    assert "proxy-secret-1" not in text
    assert "timeout-with-secret" not in text


@pytest.mark.asyncio
async def test_record_health_and_domain_request_publish_redacted_evidence(
    tmp_path, monkeypatch
):
    _clear_proxy_metrics_identity(monkeypatch)
    bus = EventBus(project_root=str(tmp_path))
    collector = mod.create_default_collector(event_bus=bus)

    await collector.record_proxy_health(
        "proxy-secret-2", is_healthy=True, response_time_ms=88.1
    )
    await collector.record_domain_request(
        "secret.example", "proxy-secret-2", success=True, latency_ms=12.25
    )

    events = bus.get_event_history(
        event_type=EventType.PIPELINE_STAGE_END,
        source_agent="proxy-metrics-collector",
    )
    assert len(events) == 2
    health_payload = events[0].data
    domain_payload = events[1].data
    assert health_payload["operation"] == "record_proxy_health"
    assert health_payload["status"] == "proxy_health_metric_recorded"
    assert health_payload["proxy_id_hash"].startswith("sha256:")
    assert health_payload["is_healthy"] is True
    assert health_payload["health_value"] == 1
    assert domain_payload["operation"] == "record_domain_request"
    assert domain_payload["status"] == "domain_request_metric_recorded"
    assert domain_payload["domain_hash"].startswith("sha256:")
    assert domain_payload["proxy_id_hash"].startswith("sha256:")
    assert domain_payload["request_success"] is True
    text = str([event.data for event in events])
    assert "secret.example" not in text
    assert "proxy-secret-2" not in text


def test_get_proxy_metrics_and_global_metrics(monkeypatch):
    now = {"t": 1000.0}
    monkeypatch.setattr(mod.time, "time", lambda: now["t"])
    collector = mod.ProxyMetricsCollector()
    collector.register_metric("metric_a", mod.MetricType.COUNTER, "A")
    collector.register_metric("metric_b", mod.MetricType.HISTOGRAM, "B")

    collector.metrics["metric_a"].values = [
        mod.MetricValue(1.0, 990.0, {"proxy_id": "p1"}),
        mod.MetricValue(2.0, 995.0, {"proxy_id": "p2"}),
        mod.MetricValue(3.0, 999.0, {"proxy_id": "p1"}),
    ]
    collector.metrics["metric_b"].values = [
        mod.MetricValue(100.0, 998.0, {"proxy_id": "p1"}),
        mod.MetricValue(200.0, 999.0, {"proxy_id": "p1"}),
    ]

    proxy_metrics = collector.get_proxy_metrics("p1", window_seconds=20)
    assert proxy_metrics["proxy_id"] == "p1"
    assert proxy_metrics["metrics"]["metric_a"]["count"] == 2
    assert proxy_metrics["metrics"]["metric_b"]["avg"] == 150.0

    global_metrics = collector.get_global_metrics(window_seconds=20)
    assert global_metrics["window_seconds"] == 20
    assert global_metrics["metrics"]["metric_a"]["count"] == 3
    assert global_metrics["metrics"]["metric_b"]["p95"] == 200.0


@pytest.mark.asyncio
async def test_check_alerts_triggers_handlers_and_survives_handler_error(caplog):
    collector = mod.ProxyMetricsCollector()
    collector.register_metric(
        "proxy_requests_failed", mod.MetricType.COUNTER, "failed requests"
    )
    collector.register_metric("proxy_latency_ms", mod.MetricType.HISTOGRAM, "latency")

    now = mod.time.time()
    collector.metrics["proxy_requests_failed"].values = [
        mod.MetricValue(0.0, now - 10),
        mod.MetricValue(120.0, now - 1),
    ]
    collector.metrics["proxy_latency_ms"].values = [
        mod.MetricValue(1500.0, now - 5),
        mod.MetricValue(3500.0, now - 1),
    ]

    seen = []

    async def _good_handler(alert):
        seen.append(alert["type"])

    async def _bad_handler(_alert):
        raise RuntimeError("handler boom")

    collector.add_alert_handler(_good_handler)
    collector.add_alert_handler(_bad_handler)

    with caplog.at_level("ERROR"):
        await collector._check_alerts()

    assert "high_failure_rate" in seen
    assert "high_latency" in seen
    assert "Alert handler error: handler boom" in caplog.text


@pytest.mark.asyncio
async def test_check_alerts_publishes_redacted_summary_evidence(tmp_path, monkeypatch):
    _clear_proxy_metrics_identity(monkeypatch)
    bus = EventBus(project_root=str(tmp_path))
    collector = mod.ProxyMetricsCollector(event_bus=bus)
    collector.register_metric(
        "proxy_requests_failed", mod.MetricType.COUNTER, "failed requests"
    )
    collector.register_metric("proxy_latency_ms", mod.MetricType.HISTOGRAM, "latency")

    now = mod.time.time()
    collector.metrics["proxy_requests_failed"].values = [
        mod.MetricValue(0.0, now - 10, {"proxy_id": "proxy-secret"}),
        mod.MetricValue(120.0, now - 1, {"proxy_id": "proxy-secret"}),
    ]
    collector.metrics["proxy_latency_ms"].values = [
        mod.MetricValue(1500.0, now - 5, {"proxy_id": "proxy-secret"}),
        mod.MetricValue(3500.0, now - 1, {"proxy_id": "proxy-secret"}),
    ]

    await collector._check_alerts()

    events = bus.get_event_history(
        event_type=EventType.PIPELINE_STAGE_END,
        source_agent="proxy-metrics-collector",
    )
    assert len(events) == 1
    payload = events[0].data
    assert payload["operation"] == "check_alerts"
    assert payload["status"] == "alerts_detected"
    assert payload["success"] is True
    assert payload["alerts_count"] == 2
    assert payload["alert_types"] == ["high_failure_rate", "high_latency"]
    assert payload["handler_errors"] == 0
    assert payload["failure_rate_5m"] > 0
    assert payload["p95_latency_ms_5m"] == 3500.0
    assert payload["metric_value_counts"] == {
        "proxy_requests_failed": 2,
        "proxy_latency_ms": 2,
    }
    assert "proxy-secret" not in str(payload)


@pytest.mark.asyncio
async def test_aggregation_loop_handles_error_and_stops(monkeypatch, caplog):
    collector = mod.ProxyMetricsCollector()
    collector._running = True
    state = {"calls": 0, "sleep_calls": []}

    async def _check_alerts():
        state["calls"] += 1
        if state["calls"] == 1:
            raise RuntimeError("agg boom")
        collector._running = False

    async def _sleep(seconds):
        state["sleep_calls"].append(seconds)
        return None

    monkeypatch.setattr(collector, "_check_alerts", _check_alerts)
    monkeypatch.setattr(mod.asyncio, "sleep", _sleep)

    with caplog.at_level("ERROR"):
        await collector._aggregation_loop()

    assert state["calls"] >= 2
    assert 10 in state["sleep_calls"]
    assert "Aggregation loop error: agg boom" in caplog.text


@pytest.mark.asyncio
async def test_aggregation_loop_cancelled_exits_cleanly(monkeypatch):
    collector = mod.ProxyMetricsCollector()
    collector._running = True

    async def _check_alerts():
        return None

    async def _sleep(_seconds):
        raise mod.asyncio.CancelledError()

    monkeypatch.setattr(collector, "_check_alerts", _check_alerts)
    monkeypatch.setattr(mod.asyncio, "sleep", _sleep)

    await collector._aggregation_loop()
    assert collector._running is True


@pytest.mark.asyncio
async def test_start_and_stop_cancel_task(monkeypatch):
    collector = mod.ProxyMetricsCollector()
    state = {"cancelled": False, "awaited": False}

    async def _task_wait():
        state["awaited"] = True
        raise mod.asyncio.CancelledError()

    class _FakeTask:
        def cancel(self):
            state["cancelled"] = True

        def __await__(self):
            return _task_wait().__await__()

    monkeypatch.setattr(mod.asyncio, "create_task", lambda coro: _FakeTask())

    await collector.start()
    assert collector._running is True

    await collector.stop()
    assert collector._running is False
    assert state["cancelled"] is True
    assert state["awaited"] is True


def test_export_prometheus_format_and_export_json():
    collector = mod.ProxyMetricsCollector()
    collector.register_metric("m_plain", mod.MetricType.GAUGE, "plain metric")
    collector.register_metric("m_label", mod.MetricType.COUNTER, "label metric")

    collector.metrics["m_plain"].values.append(mod.MetricValue(1.5, 1.0, {}))
    collector.metrics["m_label"].values.append(
        mod.MetricValue(2.0, 2.0, {"proxy_id": "p1"})
    )

    text = collector.export_prometheus_format()
    assert "# HELP m_plain plain metric" in text
    assert "# TYPE m_label counter" in text
    assert "m_plain 1.5" in text
    assert 'm_label{proxy_id="p1"} 2.0' in text

    payload = collector.export_json()
    assert "timestamp" in payload
    assert payload["metrics"]["m_plain"]["latest"] == 1.5
    assert payload["metrics"]["m_label"]["type"] == "counter"


def test_create_default_collector_registers_default_metrics():
    collector = mod.create_default_collector()
    assert "proxy_requests_total" in collector.metrics
    assert "selection_algorithm_latency_ms" in collector.metrics
    assert collector.metrics["proxy_requests_total"].metric_type == mod.MetricType.COUNTER
