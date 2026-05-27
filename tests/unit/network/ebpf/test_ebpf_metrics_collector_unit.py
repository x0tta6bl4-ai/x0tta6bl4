from types import SimpleNamespace

import pytest

from src.network.ebpf import ebpf_metrics_collector as mod
from src.network.ebpf.ebpf_metrics_collector import EBPFMetricsCollector


class FakeMap:
    def __init__(self, values=None, items=None):
        self.values = values or {}
        self._items = items or []

    def __getitem__(self, key):
        return self.values[key]

    def items(self):
        return iter(self._items)


def _system_metrics(**overrides):
    defaults = {
        "total_packets_ingress": 100,
        "total_packets_egress": 50,
        "total_bytes_ingress": 10_000,
        "total_bytes_egress": 5_000,
        "total_connection_errors": 3,
        "active_connections": 2,
    }
    defaults.update(overrides)
    return SimpleNamespace(**defaults)


def _net_monitor(sys_metrics, packet_loss=0, connection_items=None):
    return {
        "system_network_map": FakeMap({0: sys_metrics}),
        "packet_loss_map": FakeMap({0: packet_loss}),
        "connection_map": FakeMap(items=connection_items or []),
    }


def test_collect_network_metrics_averages_connection_rtt(monkeypatch):
    monkeypatch.setattr(mod, "BCC_AVAILABLE", True)
    connection_items = [
        ("conn-a", SimpleNamespace(rtt_ns=10_000_000)),
        ("conn-b", SimpleNamespace(rtt_ns=30_000_000)),
        ("conn-c", SimpleNamespace(rtt_ns=0)),
    ]
    collector = EBPFMetricsCollector(
        net_monitor=_net_monitor(
            _system_metrics(),
            packet_loss=3,
            connection_items=connection_items,
        )
    )

    metrics = collector.collect_network_metrics()

    assert metrics.latency_ms == pytest.approx(20.0)
    assert metrics.packet_loss_percent == pytest.approx(2.0)
    assert collector.get_cached_metrics()["network"]["latency_ms"] == pytest.approx(20.0)


def test_collect_network_metrics_prefers_system_average_rtt(monkeypatch):
    monkeypatch.setattr(mod, "BCC_AVAILABLE", True)
    collector = EBPFMetricsCollector(
        net_monitor=_net_monitor(
            _system_metrics(total_rtt_ns=90_000_000, rtt_samples=3),
            connection_items=[("conn-a", SimpleNamespace(rtt_ns=250_000_000))],
        )
    )

    metrics = collector.collect_network_metrics()

    assert metrics.latency_ms == pytest.approx(30.0)


def test_collect_network_metrics_returns_zero_without_latency_samples(monkeypatch):
    monkeypatch.setattr(mod, "BCC_AVAILABLE", True)
    collector = EBPFMetricsCollector(net_monitor=_net_monitor(_system_metrics()))

    metrics = collector.collect_network_metrics()

    assert metrics.latency_ms == 0.0
