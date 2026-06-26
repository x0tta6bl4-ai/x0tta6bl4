from __future__ import annotations
import json
import logging
import os
import shutil
import subprocess
import time


logger = logging.getLogger(__name__)


class PrometheusExporter:
    """Lightweight metrics sink with optional live eBPF counter sync."""

    _PACKET_STAT_INDICES = {
        "ebpf_total_packets": 0,
        "ebpf_passed_packets": 1,
        "ebpf_dropped_packets": 2,
        "ebpf_forwarded_packets": 3,
    }

    def __init__(self):
        self.metrics = {}
        self._map_id = None
        self._last_refresh = 0.0
        self._refresh_interval = 1.0

    def _bpftool_command(self, *args: str) -> list[str]:
        command: list[str] = []
        use_sudo = os.getenv("X0TTA6BL4_BPFTOOL_USE_SUDO", "false").lower() == "true"
        if use_sudo and os.geteuid() != 0 and shutil.which("sudo"):
            command.extend(["sudo", "-n"])
        command.append("bpftool")
        command.extend(args)
        return command

    def _run_bpftool_json(self, *args: str):
        if shutil.which("bpftool") is None:
            return None
        try:
            proc = subprocess.run(
                self._bpftool_command(*args),
                capture_output=True,
                text=True,
                check=False,
                timeout=2,
            )
        except (OSError, subprocess.SubprocessError, ValueError) as exc:
            logger.debug("bpftool execution unavailable: %s", exc)
            return None

        if proc.returncode != 0 or not proc.stdout.strip():
            return None

        try:
            return json.loads(proc.stdout)
        except json.JSONDecodeError as exc:
            logger.debug("bpftool returned non-JSON payload: %s", exc)
            return None

    def _find_packet_stats_map(self):
        """Find the ID of the packet_stats map."""
        if self._map_id is not None:
            return self._map_id

        progs = self._run_bpftool_json("prog", "show", "-j")
        if not isinstance(progs, list):
            return None

        for prog in progs:
            if prog.get("name") != "xdp_mesh_filter_prog":
                continue
            for map_id in prog.get("map_ids", []):
                map_info = self._run_bpftool_json("map", "show", "id", str(map_id), "-j")
                if isinstance(map_info, list):
                    map_info = map_info[0] if map_info else {}
                if isinstance(map_info, dict) and map_info.get("name") == "packet_stats":
                    self._map_id = map_id
                    return map_id
        return None

    def _read_map_value(self, map_id, key_idx):
        """Read a specific key from a bpftool map."""
        key_bytes = [str(key_idx), "0", "0", "0"]
        val_json = self._run_bpftool_json(
            "map", "lookup", "id", str(map_id), "key", *key_bytes, "-j"
        )
        if not isinstance(val_json, dict):
            return None

        total = 0
        formatted = val_json.get("formatted")
        if isinstance(formatted, dict):
            if "values" in formatted:
                for value in formatted["values"]:
                    total += value.get("value", 0)
                return total
            if "value" in formatted:
                return formatted["value"]

        for value in val_json.get("values", []):
            raw = value.get("value")
            if isinstance(raw, list):
                unpacked = 0
                for index, byte in enumerate(raw):
                    unpacked += int(byte, 16) << (8 * index)
                total += unpacked
            elif raw is not None:
                total += raw
        return total

    def _sync_with_ebpf(self, force: bool = False):
        """Sync internal metrics dictionary with real eBPF data."""
        now = time.monotonic()
        if not force and now - self._last_refresh < self._refresh_interval:
            return
        self._last_refresh = now

        mid = self._find_packet_stats_map()
        if mid is None:
            return

        for name, idx in self._PACKET_STAT_INDICES.items():
            val = self._read_map_value(mid, idx)
            if val is not None:
                self.metrics[name] = float(val)

    def set_gauge(self, name: str, value: float):
        """Set a gauge metric value."""
        self.metrics[name] = value
        # In a real environment, this might also push to a pushgateway or update a file

    def get_metric(self, name: str) -> float:
        """Get metric value, syncing with eBPF if it's an eBPF-related metric."""
        if name.startswith("ebpf_"):
            self._sync_with_ebpf()
        return self.metrics.get(name, 0.0)

    def get_all_metrics(self):
        """Return all current metrics."""
        self._sync_with_ebpf()
        return dict(self.metrics)

