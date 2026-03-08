"""
Unit tests for scripts/ebpf_prometheus_exporter.py

All tests run without root, bpftool, or a real eBPF program.
Stub mode is exercised directly via the public API.
"""

import importlib
import json
import sys
import types
from typing import Optional
from unittest import mock

import pytest


# ---------------------------------------------------------------------------
# Module loader helper — avoids touching the real prometheus_client registry
# ---------------------------------------------------------------------------

def _load_exporter(extra_env: Optional[dict] = None):
    """
    Import the exporter module with a fake prometheus_client so the module-
    level Counter/Gauge registrations don't pollute the real registry.
    """
    env_patch = {"BPF_STUB_MODE": "1", "BPF_EXPORT_PORT": "19101"}
    if extra_env:
        env_patch.update(extra_env)

    # Build a minimal prometheus_client stub
    prom_stub = types.ModuleType("prometheus_client")
    prom_stub.Counter = mock.MagicMock(return_value=mock.MagicMock())
    prom_stub.Gauge = mock.MagicMock(return_value=mock.MagicMock())
    prom_stub.start_http_server = mock.MagicMock()

    mod_name = "ebpf_prometheus_exporter_under_test"
    if mod_name in sys.modules:
        del sys.modules[mod_name]

    spec = importlib.util.spec_from_file_location(
        mod_name,
        "/mnt/projects/scripts/ebpf_prometheus_exporter.py",
    )
    mod = importlib.util.module_from_spec(spec)

    with mock.patch.dict("sys.modules", {"prometheus_client": prom_stub}):
        with mock.patch.dict("os.environ", env_patch):
            spec.loader.exec_module(mod)

    return mod


# ---------------------------------------------------------------------------
# Fixtures
# ---------------------------------------------------------------------------

@pytest.fixture
def exporter():
    mod = _load_exporter()
    mod._reset_stub_state()
    return mod


# ---------------------------------------------------------------------------
# compute_pps
# ---------------------------------------------------------------------------

class TestComputePps:
    def test_normal(self, exporter):
        assert exporter.compute_pps(1000, 10.0) == pytest.approx(100.0)

    def test_zero_elapsed(self, exporter):
        assert exporter.compute_pps(5000, 0.0) == 0.0

    def test_negative_elapsed(self, exporter):
        assert exporter.compute_pps(5000, -1.0) == 0.0

    def test_zero_delta(self, exporter):
        assert exporter.compute_pps(0, 5.0) == 0.0

    def test_large_values(self, exporter):
        # 100M packets in 10s → 10M PPS
        result = exporter.compute_pps(100_000_000, 10.0)
        assert result == pytest.approx(10_000_000.0)


# ---------------------------------------------------------------------------
# Stub mode — _stub_get_run_cnt / _stub_get_iface
# ---------------------------------------------------------------------------

class TestStubInternals:
    def test_run_cnt_increases(self, exporter):
        c1 = exporter._stub_get_run_cnt()
        c2 = exporter._stub_get_run_cnt()
        assert c2 > c1

    def test_run_cnt_monotonic(self, exporter):
        counts = [exporter._stub_get_run_cnt() for _ in range(10)]
        assert counts == sorted(counts)

    def test_iface_is_stub0(self, exporter):
        assert exporter._stub_get_iface() == "stub0"

    def test_reset_stub_state(self, exporter):
        exporter._stub_get_run_cnt()  # advance
        exporter._reset_stub_state()
        assert exporter._STUB_BASE_RUN_CNT == 0

    def test_delta_constant(self, exporter):
        c1 = exporter._stub_get_run_cnt()
        c2 = exporter._stub_get_run_cnt()
        assert c2 - c1 == exporter._STUB_DELTA


# ---------------------------------------------------------------------------
# collect_stats (stub=True)
# ---------------------------------------------------------------------------

class TestCollectStatsStub:
    def test_returns_tuple(self, exporter):
        result = exporter.collect_stats(stub=True)
        assert isinstance(result, tuple)
        assert len(result) == 2

    def test_run_cnt_is_int(self, exporter):
        run_cnt, _ = exporter.collect_stats(stub=True)
        assert isinstance(run_cnt, int)

    def test_iface_is_stub0(self, exporter):
        _, iface = exporter.collect_stats(stub=True)
        assert iface == "stub0"

    def test_run_cnt_is_positive(self, exporter):
        run_cnt, _ = exporter.collect_stats(stub=True)
        assert run_cnt > 0

    def test_successive_calls_increase(self, exporter):
        r1, _ = exporter.collect_stats(stub=True)
        r2, _ = exporter.collect_stats(stub=True)
        assert r2 > r1


# ---------------------------------------------------------------------------
# collect_stats (stub=False) — live path with mocked subprocess
# ---------------------------------------------------------------------------

class TestCollectStatsLive:
    def _make_bpftool_prog_output(self, run_cnt: int, prog_name: str = "xdp_mesh_filter_prog") -> str:
        return json.dumps([{"name": prog_name, "run_cnt": run_cnt, "id": 42}])

    def _make_bpftool_net_output(self, devname: str, prog_name: str = "xdp_mesh_filter_prog") -> str:
        return json.dumps([{"devname": devname, "xdp": [{"name": prog_name, "id": 42}]}])

    def test_live_get_run_cnt_success(self, exporter):
        proc = mock.MagicMock()
        proc.returncode = 0
        proc.stdout = self._make_bpftool_prog_output(99999)

        with mock.patch("subprocess.run", return_value=proc):
            result = exporter._live_get_run_cnt("xdp_mesh_filter_prog")
        assert result == 99999

    def test_live_get_run_cnt_empty_stdout(self, exporter):
        proc = mock.MagicMock()
        proc.returncode = 0
        proc.stdout = ""

        with mock.patch("subprocess.run", return_value=proc):
            result = exporter._live_get_run_cnt("xdp_mesh_filter_prog")
        assert result is None

    def test_live_get_run_cnt_nonzero_returncode(self, exporter):
        proc = mock.MagicMock()
        proc.returncode = 1
        proc.stdout = ""

        with mock.patch("subprocess.run", return_value=proc):
            result = exporter._live_get_run_cnt("xdp_mesh_filter_prog")
        assert result is None

    def test_live_get_run_cnt_subprocess_exception(self, exporter):
        with mock.patch("subprocess.run", side_effect=FileNotFoundError("bpftool not found")):
            result = exporter._live_get_run_cnt("xdp_mesh_filter_prog")
        assert result is None

    def test_live_get_run_cnt_invalid_json(self, exporter):
        proc = mock.MagicMock()
        proc.returncode = 0
        proc.stdout = "not-json"

        with mock.patch("subprocess.run", return_value=proc):
            result = exporter._live_get_run_cnt("xdp_mesh_filter_prog")
        assert result is None

    def test_live_get_iface_success(self, exporter):
        proc = mock.MagicMock()
        proc.returncode = 0
        proc.stdout = self._make_bpftool_net_output("enp8s0")

        with mock.patch("subprocess.run", return_value=proc):
            iface = exporter._live_get_iface("xdp_mesh_filter_prog")
        assert iface == "enp8s0"

    def test_live_get_iface_no_match(self, exporter):
        proc = mock.MagicMock()
        proc.returncode = 0
        proc.stdout = json.dumps([{"devname": "eth0", "xdp": [{"name": "other_prog", "id": 1}]}])

        with mock.patch("subprocess.run", return_value=proc):
            iface = exporter._live_get_iface("xdp_mesh_filter_prog")
        assert iface == "unknown"

    def test_live_get_iface_subprocess_exception(self, exporter):
        with mock.patch("subprocess.run", side_effect=PermissionError("no root")):
            iface = exporter._live_get_iface("xdp_mesh_filter_prog")
        assert iface == "unknown"

    def test_collect_stats_live_path(self, exporter):
        prog_proc = mock.MagicMock(returncode=0,
                                   stdout=self._make_bpftool_prog_output(12345))
        net_proc = mock.MagicMock(returncode=0,
                                  stdout=self._make_bpftool_net_output("enp3s0"))

        with mock.patch("subprocess.run", side_effect=[prog_proc, net_proc]):
            run_cnt, iface = exporter.collect_stats(stub=False)

        assert run_cnt == 12345
        assert iface == "enp3s0"

    def test_collect_stats_live_prog_not_found(self, exporter):
        proc = mock.MagicMock(returncode=1, stdout="")

        with mock.patch("subprocess.run", return_value=proc):
            run_cnt, iface = exporter.collect_stats(stub=False)

        assert run_cnt is None
        assert iface == "unknown"


# ---------------------------------------------------------------------------
# _enable_bpf_stats
# ---------------------------------------------------------------------------

class TestEnableBpfStats:
    def test_no_op_in_stub_mode(self, exporter):
        original_stub = exporter.STUB_MODE
        exporter.STUB_MODE = True
        with mock.patch("subprocess.run") as mock_run:
            exporter._enable_bpf_stats()
            mock_run.assert_not_called()
        exporter.STUB_MODE = original_stub

    def test_calls_sysctl_in_live_mode(self, exporter):
        original_stub = exporter.STUB_MODE
        exporter.STUB_MODE = False
        with mock.patch("subprocess.run") as mock_run:
            exporter._enable_bpf_stats()
            mock_run.assert_called_once()
            args = mock_run.call_args[0][0]
            assert "sysctl" in args
        exporter.STUB_MODE = original_stub

    def test_graceful_on_permission_error(self, exporter):
        original_stub = exporter.STUB_MODE
        exporter.STUB_MODE = False
        with mock.patch("subprocess.run", side_effect=PermissionError("no root")):
            # should not raise
            exporter._enable_bpf_stats()
        exporter.STUB_MODE = original_stub


# ---------------------------------------------------------------------------
# Configuration via environment variables
# ---------------------------------------------------------------------------

class TestConfiguration:
    def test_custom_prog_name(self):
        mod = _load_exporter({"BPF_PROG_NAME": "my_custom_prog"})
        assert mod.PROG_NAME == "my_custom_prog"

    def test_custom_export_port(self):
        mod = _load_exporter({"BPF_EXPORT_PORT": "9999"})
        assert mod.EXPORT_PORT == 9999

    def test_custom_collection_interval(self):
        mod = _load_exporter({"BPF_COLLECTION_INTERVAL": "30"})
        assert mod.COLLECTION_INTERVAL == 30

    def test_stub_mode_enabled_via_env(self):
        mod = _load_exporter({"BPF_STUB_MODE": "1"})
        assert mod.STUB_MODE is True

    def test_stub_mode_disabled_via_env(self):
        mod = _load_exporter({"BPF_STUB_MODE": "0"})
        assert mod.STUB_MODE is False

    def test_stub_mode_true_string(self):
        mod = _load_exporter({"BPF_STUB_MODE": "true"})
        assert mod.STUB_MODE is True

    def test_stub_mode_yes_string(self):
        mod = _load_exporter({"BPF_STUB_MODE": "yes"})
        assert mod.STUB_MODE is True


# ---------------------------------------------------------------------------
# Full simulation: multiple collection cycles in stub mode
# ---------------------------------------------------------------------------

class TestStubCycleSimulation:
    def test_pps_calculation_over_multiple_cycles(self, exporter):
        """Simulate 5 collection cycles and verify PPS is always positive."""
        last_cnt = 0
        last_time = 0.0

        for i in range(1, 6):
            run_cnt, iface = exporter.collect_stats(stub=True)
            now = float(i * 10)  # fake 10s elapsed each cycle
            assert run_cnt is not None

            delta = max(0, run_cnt - last_cnt)
            pps = exporter.compute_pps(delta, now - last_time)

            assert pps > 0, f"PPS should be positive at cycle {i}"
            assert iface == "stub0"

            last_cnt = run_cnt
            last_time = now

    def test_total_run_cnt_grows_by_delta_each_cycle(self, exporter):
        delta = exporter._STUB_DELTA
        results = [exporter.collect_stats(stub=True)[0] for _ in range(5)]
        for i in range(1, len(results)):
            assert results[i] - results[i - 1] == delta
