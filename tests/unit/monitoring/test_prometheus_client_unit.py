import src.monitoring.prometheus_client as mod


def test_non_ebpf_metric_does_not_trigger_sync(monkeypatch):
    exporter = mod.PrometheusExporter()
    calls = {"count": 0}

    def _fake_sync(force: bool = False):
        calls["count"] += 1

    monkeypatch.setattr(exporter, "_sync_with_ebpf", _fake_sync)
    exporter.set_gauge("quality_score", 42.0)

    assert exporter.get_metric("quality_score") == 42.0
    assert calls["count"] == 0


def test_get_all_metrics_returns_copy(monkeypatch):
    exporter = mod.PrometheusExporter()
    monkeypatch.setattr(exporter, "_sync_with_ebpf", lambda force=False: None)
    exporter.set_gauge("quality_score", 7.5)

    snapshot = exporter.get_all_metrics()
    snapshot["quality_score"] = 0.0

    assert exporter.get_metric("quality_score") == 7.5


def test_get_metric_refreshes_ebpf_once_per_interval(monkeypatch):
    exporter = mod.PrometheusExporter()
    exporter._refresh_interval = 10.0
    now = {"value": 100.0}
    calls = []

    monkeypatch.setattr(mod.time, "monotonic", lambda: now["value"])
    monkeypatch.setattr(exporter, "_find_packet_stats_map", lambda: 201)
    monkeypatch.setattr(
        exporter,
        "_read_map_value",
        lambda map_id, key_idx: calls.append((map_id, key_idx))
        or {0: 530058, 1: 530058, 2: 0, 3: 0}[key_idx],
    )

    assert exporter.get_metric("ebpf_total_packets") == 530058.0
    assert calls == [(201, 0), (201, 1), (201, 2), (201, 3)]

    now["value"] = 101.0
    assert exporter.get_metric("ebpf_total_packets") == 530058.0
    assert calls == [(201, 0), (201, 1), (201, 2), (201, 3)]

    now["value"] = 111.0
    assert exporter.get_metric("ebpf_total_packets") == 530058.0
    assert calls == [
        (201, 0),
        (201, 1),
        (201, 2),
        (201, 3),
        (201, 0),
        (201, 1),
        (201, 2),
        (201, 3),
    ]


def test_bpftool_command_uses_noninteractive_sudo_only_when_enabled(monkeypatch):
    exporter = mod.PrometheusExporter()

    monkeypatch.setenv("X0TTA6BL4_BPFTOOL_USE_SUDO", "true")
    monkeypatch.setattr(mod.os, "geteuid", lambda: 1000)
    monkeypatch.setattr(mod.shutil, "which", lambda name: f"/usr/bin/{name}")

    assert exporter._bpftool_command("prog", "show") == [
        "sudo",
        "-n",
        "bpftool",
        "prog",
        "show",
    ]
