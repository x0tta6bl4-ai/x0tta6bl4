"""
High-performance reader for eBPF maps.

Supports multiple backends:
1. BCC Python bindings (preferred)
2. bpftool CLI (fallback)
"""

import importlib.util
import hashlib
import json
import logging
import subprocess
import sys
import time
from concurrent.futures import ThreadPoolExecutor, as_completed
from typing import Any, Dict, List, Optional, Tuple

from src.coordination.events import EventBus, EventType
from src.services.service_event_identity import service_event_identity

from .models import TelemetryConfig
from .security import SecurityManager

logger = logging.getLogger(__name__)

EBPF_MAP_READER_SERVICE_NAME = "ebpf-map-reader"
EBPF_MAP_READER_LAYER = "network_ebpf_map_reader_observed_state"
EBPF_MAP_READER_CLAIM_BOUNDARY = (
    "Local eBPF map read evidence only. Events record bpftool probes, BCC reads, "
    "bpftool map dumps, cache hits, backend return codes, bounded output metadata, "
    "and result counts with hashed map/result selectors; they do not prove that "
    "kernel maps contain production traffic or that BPF programs are attached."
)


def _module_available(module_name: str) -> bool:
    """Return True when module is available, including test-injected stubs."""
    try:
        return importlib.util.find_spec(module_name) is not None
    except (ImportError, ValueError):
        return module_name in sys.modules


# Check for BCC availability
BCC_AVAILABLE = _module_available("bcc")


def _output_metadata(value: Any, limit: int = 512) -> Dict[str, Any]:
    text = "" if value is None else str(value)
    encoded = text.encode("utf-8", errors="replace")
    return {
        "bytes": len(encoded),
        "sha256": hashlib.sha256(encoded).hexdigest() if encoded else None,
        "sample_limit": limit,
        "sample_redacted": True,
        "truncated": len(encoded) > limit,
    }


def _bounded_hashes(values: List[Any], limit: int = 20) -> Dict[str, Any]:
    selected = values[:limit]
    return {
        "hashes": [
            hashlib.sha256(str(value).encode("utf-8", errors="replace")).hexdigest()
            for value in selected
        ],
        "count": len(values),
        "limit": limit,
        "truncated": len(values) > limit,
    }


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

    def __init__(
        self,
        config: TelemetryConfig,
        security: SecurityManager,
        event_bus: Optional[EventBus] = None,
    ):
        self.config = config
        self.security = security
        self.event_bus = event_bus
        self.source_agent = EBPF_MAP_READER_SERVICE_NAME
        identity = service_event_identity(service_name=EBPF_MAP_READER_SERVICE_NAME)
        self.identity = {
            "node_id": self.source_agent,
            "service_name": self.source_agent,
            "layer": EBPF_MAP_READER_LAYER,
            "spiffe_id_configured": bool(identity.get("spiffe_id")),
            "did_configured": bool(identity.get("did")),
            "wallet_address_configured": bool(identity.get("wallet_address")),
            "redacted": True,
        }
        self.bpftool_available = self._check_bpftool()
        self.cache: Dict[str, Tuple[float, Any]] = {}
        self.cache_ttl = 0.5  # seconds

        logger.info(f"MapReader initialized (bpftool={self.bpftool_available})")

    @staticmethod
    def _hash_value(value: Any) -> Optional[str]:
        if value is None:
            return None
        return hashlib.sha256(str(value).encode("utf-8")).hexdigest()

    @staticmethod
    def _duration_ms(start: float) -> float:
        return round((time.monotonic() - start) * 1000, 3)

    def _publish_read_event(
        self,
        *,
        stage: str,
        backend: str,
        map_name: str,
        result: str,
        result_count: int,
        start: float,
        bpf_program_present: bool,
        use_cache: bool,
        reason: str = "",
        returncode: Optional[int] = None,
        operation: str = "read_map",
        extra: Optional[Dict[str, Any]] = None,
    ) -> Optional[str]:
        if self.event_bus is None:
            return None

        payload: Dict[str, Any] = {
            "component": "network.ebpf.telemetry.map_reader",
            "stage": stage,
            "operation": operation,
            "operation_resource": f"ebpf_map_reader:{operation}",
            "resource": "network:ebpf:telemetry_map_reader",
            "service_name": self.source_agent,
            "layer": EBPF_MAP_READER_LAYER,
            "node_id": self.identity["node_id"],
            "identity": dict(self.identity),
            "result": result,
            "backend": backend,
            "reason": reason,
            "returncode": returncode,
            "duration_ms": self._duration_ms(start),
            "map_name_hash": self._hash_value(map_name),
            "map_name_redacted": True,
            "result_count": result_count,
            "bpf_program_present": bpf_program_present,
            "bcc_available": BCC_AVAILABLE,
            "bpftool_available": getattr(self, "bpftool_available", None),
            "use_cache": use_cache,
            "payloads_redacted": True,
            "observed_state": True,
            "safe_observation": True,
            "safe_actuator": False,
            "claim_boundary": EBPF_MAP_READER_CLAIM_BOUNDARY,
        }
        if extra:
            payload.update(extra)

        try:
            event = self.event_bus.publish(
                EventType.PIPELINE_STAGE_END,
                self.source_agent,
                payload,
                priority=6,
            )
            return event.event_id
        except Exception:
            logger.exception("Failed to publish eBPF map reader evidence")
            return None

    def _check_bpftool(self) -> bool:
        """Check if bpftool is available."""
        start = time.monotonic()
        command_shape = ["bpftool", "--version"]
        try:
            result = subprocess.run(
                command_shape, capture_output=True, timeout=2
            )
            available = result.returncode == 0
            self._publish_read_event(
                stage="bpftool_probe_completed",
                backend="bpftool",
                map_name="__bpftool_probe__",
                result="success" if available else "failure",
                result_count=0,
                start=start,
                bpf_program_present=False,
                use_cache=False,
                reason="bpftool_available" if available else "bpftool_unavailable",
                returncode=result.returncode,
                operation="check_bpftool",
                extra={
                    "command_shape": command_shape,
                    "command_hash": self._hash_value(" ".join(command_shape)),
                    "stdout_metadata": _output_metadata(
                        getattr(result, "stdout", None)
                    ),
                    "stderr_metadata": _output_metadata(
                        getattr(result, "stderr", None)
                    ),
                },
            )
            return available
        except FileNotFoundError as exc:
            self._publish_read_event(
                stage="bpftool_probe_missing",
                backend="bpftool",
                map_name="__bpftool_probe__",
                result="failure",
                result_count=0,
                start=start,
                bpf_program_present=False,
                use_cache=False,
                reason="bpftool_missing",
                returncode=127,
                operation="check_bpftool",
                extra={
                    "command_shape": command_shape,
                    "command_hash": self._hash_value(" ".join(command_shape)),
                    "error_type": type(exc).__name__,
                    "error_message_hash": self._hash_value(str(exc)),
                    "error_message_redacted": True,
                },
            )
            return False
        except subprocess.TimeoutExpired as exc:
            self._publish_read_event(
                stage="bpftool_probe_timeout",
                backend="bpftool",
                map_name="__bpftool_probe__",
                result="failure",
                result_count=0,
                start=start,
                bpf_program_present=False,
                use_cache=False,
                reason="bpftool_timeout",
                returncode=124,
                operation="check_bpftool",
                extra={
                    "command_shape": command_shape,
                    "command_hash": self._hash_value(" ".join(command_shape)),
                    "error_type": type(exc).__name__,
                    "error_message_hash": self._hash_value(str(exc)),
                    "error_message_redacted": True,
                },
            )
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
        start = time.monotonic()
        if not BCC_AVAILABLE:
            self._publish_read_event(
                stage="bcc_map_read_unavailable",
                backend="bcc",
                map_name=map_name,
                result="failure",
                result_count=0,
                start=start,
                bpf_program_present=bpf_program is not None,
                use_cache=False,
                reason="bcc_unavailable",
                returncode=1,
                operation="read_map_via_bcc",
            )
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

            self._publish_read_event(
                stage="bcc_map_read_completed",
                backend="bcc",
                map_name=map_name,
                result="success",
                result_count=len(result),
                start=start,
                bpf_program_present=bpf_program is not None,
                use_cache=False,
                reason="bcc_read_succeeded",
                returncode=0,
                operation="read_map_via_bcc",
                extra={
                    "result_key_hashes": _bounded_hashes(list(result.keys())),
                    "result_keys_redacted": True,
                },
            )
            return result

        except Exception as e:
            self._publish_read_event(
                stage="bcc_map_read_failed",
                backend="bcc",
                map_name=map_name,
                result="failure",
                result_count=0,
                start=start,
                bpf_program_present=bpf_program is not None,
                use_cache=False,
                reason="bcc_read_failed",
                returncode=1,
                operation="read_map_via_bcc",
                extra={
                    "error_type": type(e).__name__,
                    "error_message_hash": self._hash_value(str(e)),
                    "error_message_redacted": True,
                },
            )
            logger.error("Error reading eBPF map via BCC: %s", type(e).__name__)
            raise

    def read_map_via_bpftool(self, map_name: str) -> Dict[str, Any]:
        """
        Read eBPF map using bpftool.

        Args:
            map_name: Name of the map

        Returns:
            Dictionary with map data
        """
        start = time.monotonic()
        command_shape = ["bpftool", "map", "dump", "name", "<map_name>", "--json"]
        command_hash = self._hash_value(" ".join(command_shape))
        try:
            result = subprocess.run(
                ["bpftool", "map", "dump", "name", map_name, "--json"],
                capture_output=True,
                text=True,
                timeout=self.config.read_timeout,
            )
        except subprocess.TimeoutExpired as exc:
            self._publish_read_event(
                stage="bpftool_map_read_timeout",
                backend="bpftool",
                map_name=map_name,
                result="failure",
                result_count=0,
                start=start,
                bpf_program_present=False,
                use_cache=False,
                reason="bpftool_timeout",
                returncode=124,
                operation="read_map_via_bpftool",
                extra={
                    "command_shape": command_shape,
                    "command_hash": command_hash,
                    "error_type": type(exc).__name__,
                    "error_message_hash": self._hash_value(str(exc)),
                    "error_message_redacted": True,
                },
            )
            raise RuntimeError("bpftool timeout reading map") from exc
        except Exception as exc:
            self._publish_read_event(
                stage="bpftool_map_read_subprocess_failed",
                backend="bpftool",
                map_name=map_name,
                result="failure",
                result_count=0,
                start=start,
                bpf_program_present=False,
                use_cache=False,
                reason="bpftool_subprocess_failed",
                returncode=1,
                operation="read_map_via_bpftool",
                extra={
                    "command_shape": command_shape,
                    "command_hash": command_hash,
                    "error_type": type(exc).__name__,
                    "error_message_hash": self._hash_value(str(exc)),
                    "error_message_redacted": True,
                },
            )
            logger.error("Error executing bpftool map read: %s", type(exc).__name__)
            raise RuntimeError("bpftool execution failed") from exc

        stdout_metadata = _output_metadata(getattr(result, "stdout", None))
        stderr_metadata = _output_metadata(getattr(result, "stderr", None))
        if result.returncode != 0:
            self._publish_read_event(
                stage="bpftool_map_read_failed",
                backend="bpftool",
                map_name=map_name,
                result="failure",
                result_count=0,
                start=start,
                bpf_program_present=False,
                use_cache=False,
                reason="bpftool_returncode",
                returncode=result.returncode,
                operation="read_map_via_bpftool",
                extra={
                    "command_shape": command_shape,
                    "command_hash": command_hash,
                    "stdout_metadata": stdout_metadata,
                    "stderr_metadata": stderr_metadata,
                },
            )
            raise RuntimeError("bpftool failed")

        try:
            data = json.loads(result.stdout)
        except Exception as exc:
            self._publish_read_event(
                stage="bpftool_map_parse_failed",
                backend="bpftool",
                map_name=map_name,
                result="failure",
                result_count=0,
                start=start,
                bpf_program_present=False,
                use_cache=False,
                reason="bpftool_json_parse_failed",
                returncode=result.returncode,
                operation="read_map_via_bpftool",
                extra={
                    "command_shape": command_shape,
                    "command_hash": command_hash,
                    "stdout_metadata": stdout_metadata,
                    "stderr_metadata": stderr_metadata,
                    "error_type": type(exc).__name__,
                    "error_message_hash": self._hash_value(str(exc)),
                    "error_message_redacted": True,
                },
            )
            logger.error("Error parsing bpftool map output: %s", type(exc).__name__)
            raise

        # Parse map data
        parsed = {}
        raw_entries_count = 0
        if isinstance(data, dict) and "data" in data:
            raw_entries = data["data"] if isinstance(data["data"], list) else []
            raw_entries_count = len(raw_entries)
            for entry in raw_entries:
                key = entry.get("key")
                value = entry.get("value")

                # Convert key to string
                if isinstance(key, list):
                    key_str = "_".join(str(k) for k in key)
                else:
                    key_str = str(key)

                parsed[key_str] = value

        self._publish_read_event(
            stage="bpftool_map_read_completed",
            backend="bpftool",
            map_name=map_name,
            result="success",
            result_count=len(parsed),
            start=start,
            bpf_program_present=False,
            use_cache=False,
            reason="bpftool_read_succeeded",
            returncode=result.returncode,
            operation="read_map_via_bpftool",
            extra={
                "command_shape": command_shape,
                "command_hash": command_hash,
                "stdout_metadata": stdout_metadata,
                "stderr_metadata": stderr_metadata,
                "raw_entries_count": raw_entries_count,
                "result_key_hashes": _bounded_hashes(list(parsed.keys())),
                "result_keys_redacted": True,
            },
        )
        return parsed

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
        start = time.monotonic()
        bcc_error: Optional[Exception] = None

        # Check cache
        if use_cache and map_name in self.cache:
            cached_time, cached_data = self.cache[map_name]
            if time.time() - cached_time < self.cache_ttl:
                self._publish_read_event(
                    stage="map_read_cache_hit",
                    backend="cache",
                    map_name=map_name,
                    result="success",
                    result_count=len(cached_data)
                    if hasattr(cached_data, "__len__")
                    else 0,
                    start=start,
                    bpf_program_present=bpf_program is not None,
                    use_cache=use_cache,
                    reason="cache_hit",
                    returncode=0,
                    extra={
                        "result_key_hashes": _bounded_hashes(list(cached_data.keys()))
                        if isinstance(cached_data, dict)
                        else None,
                        "result_keys_redacted": isinstance(cached_data, dict),
                    },
                )
                return cached_data

        # Try BCC first
        if bpf_program and BCC_AVAILABLE:
            try:
                data = self.read_map_via_bcc(bpf_program, map_name)
                self.cache[map_name] = (time.time(), data)
                self._publish_read_event(
                    stage="map_read_succeeded",
                    backend="bcc",
                    map_name=map_name,
                    result="success",
                    result_count=len(data),
                    start=start,
                    bpf_program_present=True,
                    use_cache=use_cache,
                    reason="bcc_read_succeeded",
                    returncode=0,
                    extra={
                        "result_key_hashes": _bounded_hashes(list(data.keys())),
                        "result_keys_redacted": True,
                    },
                )
                return data
            except Exception as e:
                bcc_error = e
                logger.warning(
                    "BCC map read failed, trying bpftool: %s", type(e).__name__
                )

        # Fallback to bpftool
        if self.bpftool_available:
            try:
                data = self.read_map_via_bpftool(map_name)
                self.cache[map_name] = (time.time(), data)
                self._publish_read_event(
                    stage="map_read_succeeded",
                    backend="bpftool",
                    map_name=map_name,
                    result="success",
                    result_count=len(data),
                    start=start,
                    bpf_program_present=bpf_program is not None,
                    use_cache=use_cache,
                    reason="bpftool_read_succeeded"
                    if bcc_error is None
                    else "bcc_failed_bpftool_succeeded",
                    returncode=0,
                    extra={
                        "result_key_hashes": _bounded_hashes(list(data.keys())),
                        "result_keys_redacted": True,
                        "bcc_error_type": type(bcc_error).__name__
                        if bcc_error is not None
                        else None,
                        "bcc_error_message_hash": self._hash_value(str(bcc_error))
                        if bcc_error is not None
                        else None,
                        "bcc_error_message_redacted": bcc_error is not None,
                    },
                )
                return data
            except Exception as e:
                logger.error("bpftool map read failed: %s", type(e).__name__)
                self._publish_read_event(
                    stage="map_read_backend_failed",
                    backend="bpftool",
                    map_name=map_name,
                    result="failure",
                    result_count=0,
                    start=start,
                    bpf_program_present=bpf_program is not None,
                    use_cache=use_cache,
                    reason="bpftool_read_failed",
                    returncode=1,
                    extra={
                        "error_type": type(e).__name__,
                        "error_message_hash": self._hash_value(str(e)),
                        "error_message_redacted": True,
                        "bcc_error_type": type(bcc_error).__name__
                        if bcc_error is not None
                        else None,
                        "bcc_error_message_hash": self._hash_value(str(bcc_error))
                        if bcc_error is not None
                        else None,
                        "bcc_error_message_redacted": bcc_error is not None,
                    },
                )

        # Return empty dict if all methods fail
        logger.error("All methods failed to read eBPF map")
        self._publish_read_event(
            stage="map_read_empty",
            backend="none",
            map_name=map_name,
            result="empty",
            result_count=0,
            start=start,
            bpf_program_present=bpf_program is not None,
            use_cache=use_cache,
            reason="all_backends_unavailable_or_failed",
            returncode=1,
            extra={
                "bcc_error_type": type(bcc_error).__name__
                if bcc_error is not None
                else None,
                "bcc_error_message_hash": self._hash_value(str(bcc_error))
                if bcc_error is not None
                else None,
                "bcc_error_message_redacted": bcc_error is not None,
            },
        )
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
        start = time.monotonic()
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
                    logger.error("Error reading map in batch: %s", type(e).__name__)
                    results[map_name] = {}

        self._publish_read_event(
            stage="multiple_maps_read_completed",
            backend="mixed",
            map_name="__multiple_maps__",
            result="success",
            result_count=sum(len(data) for data in results.values()),
            start=start,
            bpf_program_present=bpf_program is not None,
            use_cache=True,
            reason="batch_read_completed",
            returncode=0,
            operation="read_multiple_maps",
            extra={
                "maps_requested": len(map_names),
                "maps_returned": len(results),
                "empty_results": sum(1 for data in results.values() if not data),
                "map_name_hashes": _bounded_hashes(map_names),
                "map_names_redacted": True,
            },
        )
        return results

    def clear_cache(self):
        """Clear the map cache."""
        self.cache.clear()


__all__ = ["MapReader"]
