"""
Unit tests for src.network.ebpf.stigmergy_bridge — StigmergyBridge.

All tests are deterministic; no eBPF kernel required.
"""

import asyncio
import struct
import json
import pytest
from unittest.mock import AsyncMock, MagicMock, patch

from src.network.routing.stigmergy import StigmergyRouter, PHEROMONE_MIN
from src.network.ebpf.stigmergy_bridge import (
    StigmergyBridge,
    _ip_u32_to_str,
    _bpftool_dump_map,
)


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

def _make_bridge(interface=None, poll_interval=0.05):
    router = StigmergyRouter("node-test")
    bridge = StigmergyBridge(router, interface=interface, poll_interval=poll_interval)
    return bridge, router


# ---------------------------------------------------------------------------
# _ip_u32_to_str
# ---------------------------------------------------------------------------

class TestIpConversion:
    def test_converts_big_endian_u32(self):
        # 10.0.0.1 in big-endian: 0x0A000001
        assert _ip_u32_to_str(0x0A000001) == "10.0.0.1"

    def test_converts_localhost(self):
        assert _ip_u32_to_str(0x7F000001) == "127.0.0.1"


# ---------------------------------------------------------------------------
# _bpftool_dump_map (mocked subprocess)
# ---------------------------------------------------------------------------

class TestBpftoolDumpMap:
    def test_returns_empty_when_bpftool_missing(self):
        with patch("src.network.ebpf.stigmergy_bridge.subprocess.run", side_effect=FileNotFoundError):
            result = _bpftool_dump_map("stigmergy_pkt_count")
        assert result == {}

    def test_returns_empty_on_nonzero_returncode(self):
        mock_result = MagicMock()
        mock_result.returncode = 1
        mock_result.stdout = ""
        with patch("src.network.ebpf.stigmergy_bridge.subprocess.run", return_value=mock_result):
            result = _bpftool_dump_map("stigmergy_pkt_count")
        assert result == {}

    def test_parses_bpftool_json_output(self):
        # Simulate bpftool output for 10.0.0.1 with 5 packets
        # Key: 4-byte little-endian u32 of 10.0.0.1 = 0x0100000A
        ip_bytes = list(struct.pack("<I", 0x0100000A))  # little-endian
        val_bytes = list(struct.pack("<Q", 5))           # u64 = 5
        fake_output = json.dumps([
            {"key": ip_bytes, "value": val_bytes}
        ])
        mock_result = MagicMock()
        mock_result.returncode = 0
        mock_result.stdout = fake_output
        with patch("src.network.ebpf.stigmergy_bridge.subprocess.run", return_value=mock_result):
            result = _bpftool_dump_map("stigmergy_pkt_count")
        assert len(result) == 1
        ip_u32 = 0x0100000A
        assert result[ip_u32] == 5


# ---------------------------------------------------------------------------
# StigmergyBridge — simulation mode
# ---------------------------------------------------------------------------

class TestStigmergyBridgeSimulation:
    @pytest.mark.asyncio
    async def test_start_and_stop_without_interface(self):
        bridge, _ = _make_bridge()
        await bridge.start()
        assert bridge._running
        await bridge.stop()
        assert not bridge._running

    def test_record_ack_reinforces_router(self):
        router = StigmergyRouter("n1")
        bridge = StigmergyBridge(router)
        bridge.record_ack("peer-2", "peer-2")
        # After one ACK, score should be above PHEROMONE_MIN
        table = router.get_routing_table_snapshot()
        assert "peer-2" in table
        assert table["peer-2"]["peer-2"] > PHEROMONE_MIN

    def test_record_timeout_punishes_router(self):
        router = StigmergyRouter("n1")
        bridge = StigmergyBridge(router)
        # First give it some score
        for _ in range(5):
            bridge.record_ack("peer-3", "peer-3")
        initial_score = router.get_routing_table_snapshot()["peer-3"]["peer-3"]
        bridge.record_timeout("peer-3", "peer-3")
        new_score = router.get_routing_table_snapshot()["peer-3"]["peer-3"]
        assert new_score < initial_score

    def test_register_peer_stores_mapping(self):
        bridge, _ = _make_bridge()
        bridge.register_peer("peer-x", "192.168.1.10")
        assert bridge._ip_to_peer["192.168.1.10"] == "peer-x"

    def test_unregister_peer_removes_mapping(self):
        bridge, _ = _make_bridge()
        bridge.register_peer("peer-y", "192.168.1.20")
        bridge.unregister_peer("peer-y")
        assert "192.168.1.20" not in bridge._ip_to_peer

    def test_get_stats_returns_expected_keys(self):
        bridge, _ = _make_bridge()
        stats = bridge.get_stats()
        assert "ebpf_attached" in stats
        assert "routing_table" in stats
        assert "sim_acks" in stats
        assert stats["ebpf_attached"] is False


# ---------------------------------------------------------------------------
# StigmergyBridge — eBPF map processing (mocked)
# ---------------------------------------------------------------------------

class TestEbpfMapProcessing:
    def _make_ip_u32(self, a, b, c, d) -> int:
        """Create little-endian u32 as stored in BPF map."""
        return struct.unpack("<I", bytes([a, b, c, d]))[0]

    def test_process_ebpf_snapshot_reinforces_known_peer(self):
        router = StigmergyRouter("node-ebpf")
        bridge = StigmergyBridge(router)
        bridge.register_peer("peer-1", "10.0.0.1")

        # ip 10.0.0.1 → u32 little-endian
        ip_u32 = self._make_ip_u32(1, 0, 0, 10)  # 10.0.0.1 little-endian
        # Actually let's use big-endian as _ip_u32_to_str expects big-endian
        ip_u32_be = 0x0A000001  # 10.0.0.1 big-endian
        bridge._ip_to_peer["10.0.0.1"] = "peer-1"

        # First snapshot: 0 packets (sets baseline)
        bridge._last_snapshot = {ip_u32_be: 0}
        # New snapshot: 10 packets
        with patch("src.network.ebpf.stigmergy_bridge._bpftool_dump_map", return_value={ip_u32_be: 10}):
            bridge._process_ebpf_snapshot()

        table = router.get_routing_table_snapshot()
        assert "peer-1" in table

    def test_process_ebpf_snapshot_skips_small_delta(self):
        router = StigmergyRouter("node-skip")
        bridge = StigmergyBridge(router)
        ip_u32 = 0x0A000001

        bridge._last_snapshot = {ip_u32: 0}
        # Only 1 new packet — below MIN_DELTA_TO_REINFORCE (3)
        with patch("src.network.ebpf.stigmergy_bridge._bpftool_dump_map", return_value={ip_u32: 1}):
            bridge._process_ebpf_snapshot()

        # No route should have been added (delta too small)
        table = router.get_routing_table_snapshot()
        assert table == {}

    def test_process_ebpf_unknown_peer_uses_ip_as_id(self):
        router = StigmergyRouter("node-unk")
        bridge = StigmergyBridge(router)
        ip_u32 = 0xC0A80164  # 192.168.1.100

        bridge._last_snapshot = {ip_u32: 0}
        with patch("src.network.ebpf.stigmergy_bridge._bpftool_dump_map", return_value={ip_u32: 10}):
            bridge._process_ebpf_snapshot()

        table = router.get_routing_table_snapshot()
        # Should have been recorded as "ip:192.168.1.100"
        assert "ip:192.168.1.100" in table
