"""
eBPF Map Reader - Read eBPF maps from userspace

This module provides utilities to read eBPF maps created by eBPF programs.
Uses bpftool or direct syscalls to read map data.
"""

import json
import logging
import subprocess
from pathlib import Path
from typing import Any, Dict, List, Optional

logger = logging.getLogger(__name__)


class EBPFMapReader:
    """
    Reader for eBPF maps.

    Supports reading maps via:
    - bpftool (preferred, if available)
    - Direct syscalls (future enhancement)
    """

    def __init__(self):
        self.bpftool_available = self._check_bpftool()

    def _check_bpftool(self) -> bool:
        """Check if bpftool is available."""
        try:
            result = subprocess.run(
                ["bpftool", "--version"], capture_output=True, timeout=2
            )
            return result.returncode == 0
        except (FileNotFoundError, subprocess.TimeoutExpired):
            return False

    def list_maps(self) -> List[Dict[str, Any]]:
        """
        List all eBPF maps.

        Returns:
            List of map information dictionaries
        """
        if not self.bpftool_available:
            logger.warning("bpftool not available, cannot list maps")
            return []

        try:
            result = subprocess.run(
                ["bpftool", "map", "show", "--json"],
                capture_output=True,
                text=True,
                timeout=10,
            )

            if result.returncode == 0:
                maps = json.loads(result.stdout)
                return maps if isinstance(maps, list) else [maps]
            else:
                logger.error(f"bpftool map show failed: {result.stderr}")
                return []
        except Exception as e:
            logger.error(f"Error listing maps: {e}")
            return []

    def read_map(
        self, map_id: Optional[int] = None, map_name: Optional[str] = None
    ) -> Dict[str, Any]:
        """
        Read contents of an eBPF map.

        Args:
            map_id: Map ID (if known)
            map_name: Map name (if known)

        Returns:
            Dictionary with map contents
        """
        if not self.bpftool_available:
            logger.warning("bpftool not available, cannot read map")
            return {}

        if not map_id and not map_name:
            logger.error("Either map_id or map_name must be provided")
            return {}

        try:
            # Use map name if available, otherwise use ID
            map_arg = map_name if map_name else str(map_id)

            result = subprocess.run(
                ["bpftool", "map", "dump", "name", map_arg, "--json"],
                capture_output=True,
                text=True,
                timeout=10,
            )

            if result.returncode == 0:
                data = json.loads(result.stdout)
                return data if isinstance(data, dict) else {"data": data}
            else:
                # Try with ID if name failed
                if map_name and map_id:
                    result = subprocess.run(
                        ["bpftool", "map", "dump", "id", str(map_id), "--json"],
                        capture_output=True,
                        text=True,
                        timeout=10,
                    )
                    if result.returncode == 0:
                        data = json.loads(result.stdout)
                        return data if isinstance(data, dict) else {"data": data}

                logger.error(f"bpftool map dump failed: {result.stderr}")
                return {}
        except Exception as e:
            logger.error(f"Error reading map: {e}")
            return {}

    def read_counter_map(self, map_name: str) -> Dict[str, int]:
        """
        Read a counter map (common eBPF pattern).

        Args:
            map_name: Name of the counter map

        Returns:
            Dictionary mapping keys to counter values
        """
        map_data = self.read_map(map_name=map_name)

        if not map_data:
            return {}

        # Parse counter map format
        counters = {}
        if isinstance(map_data, dict) and "data" in map_data:
            for entry in map_data["data"]:
                if "key" in entry and "value" in entry:
                    key = entry["key"]
                    value = entry["value"]
                    # Convert key to string for readability
                    if isinstance(key, list):
                        key_str = "_".join(str(k) for k in key)
                    else:
                        key_str = str(key)
                    counters[key_str] = (
                        int(value) if isinstance(value, (int, str)) else value
                    )

        return counters

    def get_map_info(self, map_name: str) -> Optional[Dict[str, Any]]:
        """
        Get information about a specific map.

        Args:
            map_name: Name of the map

        Returns:
            Map information dictionary or None
        """
        maps = self.list_maps()
        for map_info in maps:
            if map_info.get("name") == map_name:
                return map_info
        return None


def read_packet_counters(map_name: str = "packet_counters") -> Dict[str, int]:
    """
    Convenience function to read packet counters from eBPF map.

    Args:
        map_name: Name of the packet counter map

    Returns:
        Dictionary with protocol -> count mapping
    """
    reader = EBPFMapReader()
    return reader.read_counter_map(map_name)


if __name__ == "__main__":
    # CLI for testing
    import argparse

    parser = argparse.ArgumentParser(description="Read eBPF maps")
    parser.add_argument("--list", action="store_true", help="List all maps")
    parser.add_argument("--read", type=str, help="Read map by name")
    parser.add_argument(
        "--counters", type=str, default="packet_counters", help="Read counter map"
    )

    args = parser.parse_args()

    logging.basicConfig(level=logging.INFO)
    reader = EBPFMapReader()

    if args.list:
        maps = reader.list_maps()
        print(f"Found {len(maps)} maps:")
        for map_info in maps:
            print(f"  - {map_info.get('name', 'unnamed')} (id: {map_info.get('id')})")

    if args.read:
        data = reader.read_map(map_name=args.read)
        print(f"Map '{args.read}':")
        print(json.dumps(data, indent=2))

    if args.counters:
        counters = reader.read_counter_map(args.counters)
        print(f"Counters from '{args.counters}':")
        for key, value in counters.items():
            print(f"  {key}: {value}")
