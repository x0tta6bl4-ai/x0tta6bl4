"""
High-performance reader for eBPF maps.

Supports multiple backends:
1. BCC Python bindings (preferred)
2. bpftool CLI (fallback)
"""

import importlib.util
import json
import logging
import subprocess
import sys
import time
from concurrent.futures import ThreadPoolExecutor, as_completed
from typing import Any, Dict, List, Optional, Tuple

from .models import TelemetryConfig
from .security import SecurityManager

logger = logging.getLogger(__name__)


def _module_available(module_name: str) -> bool:
    """Return True when module is available, including test-injected stubs."""
    try:
        return importlib.util.find_spec(module_name) is not None
    except (ImportError, ValueError):
        return module_name in sys.modules


# Check for BCC availability
BCC_AVAILABLE = _module_available("bcc")


class MapReader:
    """
    High-performance reader for eBPF maps.

    Supports multiple backends:
    1. BCC Python bindings (preferred)
    2. bpftool CLI (fallback)
    3. Direct syscalls (future)

    Optimizations:
    - Batch reading
    - Parallel processing
    - Caching
    - Zero-copy where possible
    """

    def __init__(self, config: TelemetryConfig, security: SecurityManager):
        self.config = config
        self.security = security
        self.bpftool_available = self._check_bpftool()
        self.cache: Dict[str, Tuple[float, Any]] = {}
        self.cache_ttl = 0.5  # seconds

        logger.info(f"MapReader initialized (bpftool={self.bpftool_available})")

    def _check_bpftool(self) -> bool:
        """Check if bpftool is available."""
        try:
            result = subprocess.run(
                ["bpftool", "--version"], capture_output=True, timeout=2
            )
            return result.returncode == 0
        except (FileNotFoundError, subprocess.TimeoutExpired):
            return False

    def read_map_via_bcc(self, bpf_program: Any, map_name: str) -> Dict[str, Any]:
        """
        Read eBPF map using BCC.

        Args:
            bpf_program: BCC BPF program instance
            map_name: Name of the map

        Returns:
            Dictionary with map data
        """
        if not BCC_AVAILABLE:
            raise RuntimeError("BCC not available")

        try:
            table = bpf_program[map_name]
            result = {}

            for key, value in table.items():
                # Convert key to string
                if isinstance(key, (bytes, bytearray)):
                    key_str = key.decode("utf-8", errors="replace").rstrip("\x00")
                else:
                    key_str = str(key)

                # Convert value
                if hasattr(value, "__dict__"):
                    # Struct value
                    value_dict = {}
                    for field_name, field_value in value.__dict__.items():
                        if isinstance(field_value, (bytes, bytearray)):
                            field_value = field_value.decode(
                                "utf-8", errors="replace"
                            ).rstrip("\x00")
                        value_dict[field_name] = field_value
                    result[key_str] = value_dict
                else:
                    result[key_str] = value

            return result

        except Exception as e:
            logger.error(f"Error reading map {map_name} via BCC: {e}")
            raise

    def read_map_via_bpftool(self, map_name: str) -> Dict[str, Any]:
        """
        Read eBPF map using bpftool.

        Args:
            map_name: Name of the map

        Returns:
            Dictionary with map data
        """
        try:
            result = subprocess.run(
                ["bpftool", "map", "dump", "name", map_name, "--json"],
                capture_output=True,
                text=True,
                timeout=self.config.read_timeout,
            )

            if result.returncode != 0:
                raise RuntimeError(f"bpftool failed: {result.stderr}")

            data = json.loads(result.stdout)

            # Parse map data
            parsed = {}
            if isinstance(data, dict) and "data" in data:
                for entry in data["data"]:
                    key = entry.get("key")
                    value = entry.get("value")

                    # Convert key to string
                    if isinstance(key, list):
                        key_str = "_".join(str(k) for k in key)
                    else:
                        key_str = str(key)

                    parsed[key_str] = value

            return parsed

        except subprocess.TimeoutExpired:
            raise RuntimeError(f"bpftool timeout reading map {map_name}")
        except Exception as e:
            logger.error(f"Error reading map {map_name} via bpftool: {e}")
            raise

    def read_map(
        self, bpf_program: Optional[Any], map_name: str, use_cache: bool = True
    ) -> Dict[str, Any]:
        """
        Read eBPF map with automatic backend selection.

        Args:
            bpf_program: BCC BPF program instance (optional)
            map_name: Name of the map
            use_cache: Whether to use cached data

        Returns:
            Dictionary with map data
        """
        # Check cache
        if use_cache and map_name in self.cache:
            cached_time, cached_data = self.cache[map_name]
            if time.time() - cached_time < self.cache_ttl:
                return cached_data

        # Try BCC first
        if bpf_program and BCC_AVAILABLE:
            try:
                data = self.read_map_via_bcc(bpf_program, map_name)
                self.cache[map_name] = (time.time(), data)
                return data
            except Exception as e:
                logger.warning(f"BCC read failed for {map_name}, trying bpftool: {e}")

        # Fallback to bpftool
        if self.bpftool_available:
            try:
                data = self.read_map_via_bpftool(map_name)
                self.cache[map_name] = (time.time(), data)
                return data
            except Exception as e:
                logger.error(f"bpftool read failed for {map_name}: {e}")

        # Return empty dict if all methods fail
        logger.error(f"All methods failed to read map {map_name}")
        return {}

    def read_multiple_maps(
        self, bpf_program: Optional[Any], map_names: List[str]
    ) -> Dict[str, Dict[str, Any]]:
        """
        Read multiple maps in parallel.

        Args:
            bpf_program: BCC BPF program instance (optional)
            map_names: List of map names

        Returns:
            Dictionary mapping map names to their data
        """
        results = {}

        with ThreadPoolExecutor(max_workers=self.config.max_workers) as executor:
            future_to_map = {
                executor.submit(self.read_map, bpf_program, map_name): map_name
                for map_name in map_names
            }

            for future in as_completed(future_to_map):
                map_name = future_to_map[future]
                try:
                    results[map_name] = future.result()
                except Exception as e:
                    logger.error(f"Error reading map {map_name}: {e}")
                    results[map_name] = {}

        return results

    def clear_cache(self):
        """Clear the map cache."""
        self.cache.clear()


__all__ = ["MapReader"]
