"""Unit tests for eBPF Map Manager."""
import os
import json
import subprocess
import pytest
from unittest.mock import patch, MagicMock

os.environ.setdefault("X0TTA6BL4_PRODUCTION", "false")
os.environ.setdefault("X0TTA6BL4_SPIFFE", "false")
os.environ.setdefault("X0TTA6BL4_FORCE_MOCK_SPIFFE", "true")


@pytest.fixture
def mgr():
    with patch("subprocess.run") as mock_run:
        mock_run.return_value = MagicMock(returncode=1)  # bpftool unavailable
        from src.network.ebpf.loader.map_manager import EBPFMapManager
        m = EBPFMapManager()
        m._bpftool_available = False
        return m


@pytest.fixture
def mgr_with_bpftool():
    with patch("subprocess.run") as mock_run:
        mock_run.return_value = MagicMock(returncode=0)
        from src.network.ebpf.loader.map_manager import EBPFMapManager
        m = EBPFMapManager()
        m._bpftool_available = True
        return m


class TestMapManagerInit:
    @patch("subprocess.run")
    def test_bpftool_available(self, mock_run):
        mock_run.return_value = MagicMock(returncode=0)
        from src.network.ebpf.loader.map_manager import EBPFMapManager
        m = EBPFMapManager()
        assert m._bpftool_available is True

    @patch("subprocess.run")
    def test_bpftool_not_found(self, mock_run):
        mock_run.side_effect = FileNotFoundError()
        from src.network.ebpf.loader.map_manager import EBPFMapManager
        m = EBPFMapManager()
        assert m._bpftool_available is False

    @patch("subprocess.run")
    def test_bpftool_timeout(self, mock_run):
        mock_run.side_effect = subprocess.TimeoutExpired(cmd="bpftool", timeout=2)
        from src.network.ebpf.loader.map_manager import EBPFMapManager
        m = EBPFMapManager()
        assert m._bpftool_available is False


class TestReadMap:
    def test_no_bpftool(self, mgr):
        result = mgr.read_map("test_map")
        assert result == {}

    @patch("subprocess.run")
    def test_success(self, mock_run, mgr_with_bpftool):
        data = [
            {"key": "0", "value": "100"},
            {"key": "1", "value": "50"},
        ]
        mock_run.return_value = MagicMock(
            returncode=0, stdout=json.dumps(data)
        )
        result = mgr_with_bpftool.read_map("packet_stats")
        assert result["0"] == "100"
        assert result["1"] == "50"

    @patch("subprocess.run")
    def test_failed_command(self, mock_run, mgr_with_bpftool):
        mock_run.return_value = MagicMock(returncode=1, stderr="error")
        result = mgr_with_bpftool.read_map("bad_map")
        assert result == {}

    @patch("subprocess.run")
    def test_invalid_json(self, mock_run, mgr_with_bpftool):
        mock_run.return_value = MagicMock(returncode=0, stdout="not json")
        result = mgr_with_bpftool.read_map("bad_map")
        assert result == {}

    @patch("subprocess.run")
    def test_timeout(self, mock_run, mgr_with_bpftool):
        mock_run.side_effect = subprocess.TimeoutExpired(cmd="bpftool", timeout=5)
        result = mgr_with_bpftool.read_map("slow_map")
        assert result == {}

    @patch("subprocess.run")
    def test_list_key(self, mock_run, mgr_with_bpftool):
        data = [{"key": [1, 2], "value": "val"}]
        mock_run.return_value = MagicMock(
            returncode=0, stdout=json.dumps(data)
        )
        result = mgr_with_bpftool.read_map("test")
        assert "1_2" in result


class TestUpdateEntry:
    def test_no_bpftool(self, mgr):
        assert mgr.update_entry("map", "key", "val") is False

    @patch("subprocess.run")
    def test_success(self, mock_run, mgr_with_bpftool):
        mock_run.return_value = MagicMock(returncode=0)
        assert mgr_with_bpftool.update_entry("map", "key", "val") is True

    @patch("subprocess.run")
    def test_failure(self, mock_run, mgr_with_bpftool):
        mock_run.return_value = MagicMock(returncode=1, stderr="err")
        assert mgr_with_bpftool.update_entry("map", "key", "val") is False

    @patch("subprocess.run")
    def test_timeout(self, mock_run, mgr_with_bpftool):
        mock_run.side_effect = subprocess.TimeoutExpired(cmd="bpftool", timeout=5)
        assert mgr_with_bpftool.update_entry("map", "key", "val") is False


class TestGetStats:
    def test_no_bpftool_returns_zeros(self, mgr):
        stats = mgr.get_stats()
        assert stats["total_packets"] == 0
        assert stats["dropped_packets"] == 0

    @patch("subprocess.run")
    def test_with_data(self, mock_run, mgr_with_bpftool):
        data = [
            {"key": "0", "value": "1000"},
            {"key": "1", "value": "900"},
            {"key": "2", "value": "50"},
            {"key": "3", "value": "50"},
        ]
        mock_run.return_value = MagicMock(
            returncode=0, stdout=json.dumps(data)
        )
        stats = mgr_with_bpftool.get_stats()
        assert stats["total_packets"] == 1000
        assert stats["passed_packets"] == 900
        assert stats["dropped_packets"] == 50
        assert stats["forwarded_packets"] == 50


class TestUpdateRoutes:
    def test_no_bpftool(self, mgr):
        assert mgr.update_routes({"10.0.0.1": "1"}) is False

    @patch("subprocess.run")
    def test_success(self, mock_run, mgr_with_bpftool):
        mock_run.return_value = MagicMock(returncode=0)
        assert mgr_with_bpftool.update_routes({"10.0.0.1": "1", "10.0.0.2": "2"}) is True


class TestListMaps:
    def test_no_bpftool(self, mgr):
        assert mgr.list_maps() == []

    @patch("subprocess.run")
    def test_success(self, mock_run, mgr_with_bpftool):
        maps = [{"id": 1, "name": "packet_stats"}]
        mock_run.return_value = MagicMock(
            returncode=0, stdout=json.dumps(maps)
        )
        result = mgr_with_bpftool.list_maps()
        assert len(result) == 1
        assert result[0]["name"] == "packet_stats"
