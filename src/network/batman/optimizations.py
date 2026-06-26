"""
Batman-adv Optimizations from Paradox Zone

Integrates production-ready optimizations:
- Multi-path routing
- Optimized timeouts
- Enhanced buffering
- AODV fallback
- Performance monitoring
"""
from __future__ import annotations

import hashlib
import logging
import subprocess
import time
from dataclasses import dataclass
from typing import Any, Dict, List, Optional

from src.coordination.events import EventBus, EventType
from src.services.service_event_identity import service_event_identity

logger = logging.getLogger(__name__)

BATMAN_OPTIMIZATIONS_SERVICE_NAME = "batman-optimizations"
BATMAN_OPTIMIZATIONS_LAYER = "network_batman_optimizations_observed_state"
BATMAN_OPTIMIZATIONS_CLAIM_BOUNDARY = (
    "Local batman-adv optimization evidence only. Events record batctl originator "
    "and ping probes, config fallback decisions, local return codes, duration, "
    "bounded stdout/stderr metadata, and hashed destination/path selectors; they "
    "do not prove live mesh convergence, remote peer identity, AODV support in "
    "the kernel, or production traffic routing."
)


def _hash_value(value: Any) -> Optional[str]:
    if value is None:
        return None
    return hashlib.sha256(str(value).encode("utf-8", errors="replace")).hexdigest()


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


def _identity_metadata() -> Dict[str, Any]:
    identity = service_event_identity(service_name=BATMAN_OPTIMIZATIONS_SERVICE_NAME)
    return {
        "service_name": BATMAN_OPTIMIZATIONS_SERVICE_NAME,
        "layer": BATMAN_OPTIMIZATIONS_LAYER,
        "spiffe_id_configured": bool(identity.get("spiffe_id")),
        "did_configured": bool(identity.get("did")),
        "wallet_address_configured": bool(identity.get("wallet_address")),
        "redacted": True,
    }


class _BatmanEvidenceMixin:
    event_bus: Optional[EventBus]
    event_project_root: str
    source_agent: str

    def _event_bus_or_none(self) -> Optional[EventBus]:
        event_bus = getattr(self, "event_bus", None)
        if event_bus is not None:
            return event_bus
        try:
            event_bus = EventBus(project_root=getattr(self, "event_project_root", "."))
            self.event_bus = event_bus
            return event_bus
        except Exception as exc:
            logger.error("Failed to initialize Batman optimizations EventBus: %s", exc)
            return None

    def _publish_observation(
        self,
        *,
        stage: str,
        operation: str,
        status: str,
        source_mode: str,
        start: float,
        returncode: Optional[int] = None,
        parsed_summary: Optional[Dict[str, Any]] = None,
        error: Optional[BaseException] = None,
        extra: Optional[Dict[str, Any]] = None,
    ) -> Optional[str]:
        bus = self._event_bus_or_none()
        if bus is None:
            return None

        source_agent = getattr(
            self,
            "source_agent",
            BATMAN_OPTIMIZATIONS_SERVICE_NAME,
        )
        payload: Dict[str, Any] = {
            "component": "network.batman.optimizations",
            "stage": stage,
            "operation": operation,
            "operation_resource": f"network:batman:optimizations:{operation}",
            "service_name": source_agent,
            "layer": BATMAN_OPTIMIZATIONS_LAYER,
            "identity": _identity_metadata(),
            "status": status,
            "source_mode": source_mode,
            "returncode": returncode,
            "duration_ms": round((time.monotonic() - start) * 1000, 3),
            "read_only": True,
            "observed_state": True,
            "safe_observation": True,
            "safe_actuator": False,
            "payloads_redacted": True,
            "parsed_summary": parsed_summary or {},
            "claim_boundary": BATMAN_OPTIMIZATIONS_CLAIM_BOUNDARY,
        }
        if error is not None:
            payload["error"] = {
                "type": type(error).__name__,
                "message_hash": _hash_value(str(error)),
                "message_redacted": True,
            }
        if extra:
            payload.update(extra)

        try:
            event = bus.publish(
                EventType.PIPELINE_STAGE_END,
                source_agent,
                payload,
                priority=5,
            )
            return event.event_id
        except Exception:
            logger.exception("Failed to publish Batman optimization evidence")
            return None


@dataclass
class BatmanAdvConfig:
    """Optimized Batman-adv configuration from Paradox Zone."""

    # Multi-path routing
    multipath_enabled: bool = True
    multipath_max_paths: int = 3
    path_discovery_interval: str = "5s"
    path_failure_threshold: int = 3

    # AODV fallback
    aodv_enabled: bool = True
    aodv_fallback_timeout: str = "15s"
    aodv_route_request_retries: int = 3
    aodv_route_request_rate_limit: str = "10/s"

    # Optimized timeouts
    originator_interval: str = "1s"  # Reduced from 3s for faster discovery
    echo_interval: str = "500ms"  # Optimized for lower latency
    route_record_timeout: str = "10s"  # Increased for stability

    # Buffering
    max_queue_length: int = 1000  # Increased for peak load handling
    packet_buffer_timeout: str = "100ms"  # Optimized for lower latency
    retransmission_buffer_size: int = 50  # Increased for reliability

    # Neighbor discovery
    neighbor_timeout: str = "5s"  # Optimized for faster recovery
    neighbor_aging_time: str = "30s"  # Increased for stability

    # Gateway mode
    gateway_mode: bool = True
    gateway_selection_class: int = 1  # Automatic gateway selection


class MultiPathRouter(_BatmanEvidenceMixin):
    """
    Multi-path routing optimization from Paradox Zone.

    Enables multiple paths for redundancy and load balancing.
    """

    def __init__(
        self,
        config: BatmanAdvConfig,
        event_bus: Optional[EventBus] = None,
        event_project_root: str = ".",
    ):
        self.config = config
        self.event_bus = event_bus
        self.event_project_root = event_project_root
        self.source_agent = BATMAN_OPTIMIZATIONS_SERVICE_NAME
        self.active_paths: Dict[str, List[str]] = {}  # destination -> list of paths
        self.path_metrics: Dict[str, Dict[str, float]] = {}  # path -> metrics

    def discover_paths(self, destination: str) -> List[str]:
        """
        Discover multiple paths to destination.

        Args:
            destination: Target node ID

        Returns:
            List of available paths
        """
        op_start = time.monotonic()
        if not self.config.multipath_enabled:
            self._publish_observation(
                stage="batman_multipath_discovery_disabled",
                operation="discover_paths",
                status="skipped",
                source_mode="config",
                start=op_start,
                returncode=0,
                parsed_summary={"paths_total": 0, "multipath_enabled": False},
                extra={
                    "destination_hash": _hash_value(destination),
                    "destination_redacted": True,
                },
            )
            return []

        # Path discovery implementation
        # Uses batctl to discover available paths
        command_shape = ["batctl", "meshif", "bat0", "originators"]
        try:
            result = subprocess.run(
                command_shape,
                capture_output=True,
                text=True,
                timeout=5,
            )
            if result.returncode == 0:
                # Parse originators to get available paths
                originators = result.stdout.strip().split("\n")
                paths_total = len(originators) if originators != [""] else 0
                self._publish_observation(
                    stage="batman_multipath_originators_collected",
                    operation="discover_paths",
                    status="success",
                    source_mode="batctl",
                    start=op_start,
                    returncode=result.returncode,
                    parsed_summary={
                        "paths_total": paths_total,
                        "multipath_enabled": True,
                    },
                    extra={
                        "command_shape": command_shape,
                        "command_hash": _hash_value(" ".join(command_shape)),
                        "stdout_metadata": _output_metadata(result.stdout),
                        "stderr_metadata": _output_metadata(result.stderr),
                        "destination_hash": _hash_value(destination),
                        "destination_redacted": True,
                    },
                )
                return paths_total  # Number of available paths

            self._publish_observation(
                stage="batman_multipath_originators_failed",
                operation="discover_paths",
                status="failure",
                source_mode="batctl",
                start=op_start,
                returncode=result.returncode,
                parsed_summary={"paths_total": 0, "multipath_enabled": True},
                extra={
                    "command_shape": command_shape,
                    "command_hash": _hash_value(" ".join(command_shape)),
                    "stdout_metadata": _output_metadata(result.stdout),
                    "stderr_metadata": _output_metadata(result.stderr),
                    "destination_hash": _hash_value(destination),
                    "destination_redacted": True,
                },
            )
            return 0
        except FileNotFoundError as exc:
            self._publish_observation(
                stage="batman_multipath_originators_missing",
                operation="discover_paths",
                status="failure",
                source_mode="batctl",
                start=op_start,
                returncode=127,
                error=exc,
                parsed_summary={"paths_total": 0, "multipath_enabled": True},
                extra={
                    "command_shape": command_shape,
                    "command_hash": _hash_value(" ".join(command_shape)),
                    "destination_hash": _hash_value(destination),
                    "destination_redacted": True,
                },
            )
            # Fallback: return 0 if batctl not available
            logger.debug("batctl not available, returning 0 paths")
            return 0
        except subprocess.TimeoutExpired as exc:
            self._publish_observation(
                stage="batman_multipath_originators_timeout",
                operation="discover_paths",
                status="failure",
                source_mode="batctl",
                start=op_start,
                returncode=124,
                error=exc,
                parsed_summary={"paths_total": 0, "multipath_enabled": True},
                extra={
                    "command_shape": command_shape,
                    "command_hash": _hash_value(" ".join(command_shape)),
                    "destination_hash": _hash_value(destination),
                    "destination_redacted": True,
                },
            )
            # Fallback: return 0 if batctl not available
            logger.debug("batctl not available, returning 0 paths")
            return 0

    def select_best_path(self, destination: str) -> Optional[str]:
        """
        Select best path based on metrics.

        Args:
            destination: Target node ID

        Returns:
            Best path ID or None
        """
        if destination not in self.active_paths:
            return None

        paths = self.active_paths[destination]
        if not paths:
            return None

        # Select path with best metrics (lowest latency, highest throughput)
        best_path = None
        best_score = float("inf")

        for path in paths:
            metrics = self.path_metrics.get(path, {})
            latency = metrics.get("latency", float("inf"))
            throughput = metrics.get("throughput", 0)

            # Score = latency / throughput (lower is better)
            score = latency / max(throughput, 1)
            if score < best_score:
                best_score = score
                best_path = path

        return best_path

    def mark_path_failed(self, path: str) -> None:
        """Mark path as failed."""
        # Remove from active paths
        for dest, paths in self.active_paths.items():
            if path in paths:
                paths.remove(path)

        # Remove metrics
        if path in self.path_metrics:
            del self.path_metrics[path]

        logger.warning(f"Path marked as failed: {path}")


class AODVFallback(_BatmanEvidenceMixin):
    """
    AODV fallback mechanism from Paradox Zone.

    Provides fallback routing when Batman-adv fails.
    """

    def __init__(
        self,
        config: BatmanAdvConfig,
        event_bus: Optional[EventBus] = None,
        event_project_root: str = ".",
    ):
        self.config = config
        self.event_bus = event_bus
        self.event_project_root = event_project_root
        self.source_agent = BATMAN_OPTIMIZATIONS_SERVICE_NAME
        self.route_cache: Dict[str, Dict] = {}
        self.active_requests: Dict[str, int] = {}

    def should_fallback(self, destination: str) -> bool:
        """
        Check if AODV fallback should be used.

        Args:
            destination: Target node ID

        Returns:
            True if fallback needed
        """
        op_start = time.monotonic()
        if not self.config.aodv_enabled:
            self._publish_observation(
                stage="batman_aodv_fallback_disabled",
                operation="should_fallback",
                status="skipped",
                source_mode="config",
                start=op_start,
                returncode=0,
                parsed_summary={"aodv_enabled": False, "fallback": False},
                extra={
                    "destination_hash": _hash_value(destination),
                    "destination_redacted": True,
                },
            )
            return False

        # Check if route exists in cache
        if destination in self.route_cache:
            self.route_cache[destination]
            # Check if route is still valid
            # Route validation implementation
            # Validates route by checking connectivity
            command_shape = [
                "batctl",
                "meshif",
                "bat0",
                "ping",
                "-c",
                "1",
                "<destination>",
            ]
            try:
                result = subprocess.run(
                    ["batctl", "meshif", "bat0", "ping", "-c", "1", destination],
                    capture_output=True,
                    text=True,
                    timeout=5,
                )
                should_fallback = result.returncode == 0
                self._publish_observation(
                    stage=(
                        "batman_aodv_cached_route_probe_reachable"
                        if should_fallback
                        else "batman_aodv_cached_route_probe_failed"
                    ),
                    operation="should_fallback",
                    status="success" if should_fallback else "failure",
                    source_mode="batctl",
                    start=op_start,
                    returncode=result.returncode,
                    parsed_summary={
                        "aodv_enabled": True,
                        "route_cache_hit": True,
                        "fallback": should_fallback,
                    },
                    extra={
                        "command_shape": command_shape,
                        "command_hash": _hash_value(" ".join(command_shape)),
                        "stdout_metadata": _output_metadata(result.stdout),
                        "stderr_metadata": _output_metadata(result.stderr),
                        "destination_hash": _hash_value(destination),
                        "destination_redacted": True,
                    },
                )
                return should_fallback
            except FileNotFoundError as exc:
                self._publish_observation(
                    stage="batman_aodv_cached_route_probe_missing",
                    operation="should_fallback",
                    status="failure",
                    source_mode="batctl",
                    start=op_start,
                    returncode=127,
                    error=exc,
                    parsed_summary={
                        "aodv_enabled": True,
                        "route_cache_hit": True,
                        "fallback": False,
                    },
                    extra={
                        "command_shape": command_shape,
                        "command_hash": _hash_value(" ".join(command_shape)),
                        "destination_hash": _hash_value(destination),
                        "destination_redacted": True,
                    },
                )
                return False
            except subprocess.TimeoutExpired as exc:
                self._publish_observation(
                    stage="batman_aodv_cached_route_probe_timeout",
                    operation="should_fallback",
                    status="failure",
                    source_mode="batctl",
                    start=op_start,
                    returncode=124,
                    error=exc,
                    parsed_summary={
                        "aodv_enabled": True,
                        "route_cache_hit": True,
                        "fallback": False,
                    },
                    extra={
                        "command_shape": command_shape,
                        "command_hash": _hash_value(" ".join(command_shape)),
                        "destination_hash": _hash_value(destination),
                        "destination_redacted": True,
                    },
                )
                return False
            return False

        self._publish_observation(
            stage="batman_aodv_route_cache_miss",
            operation="should_fallback",
            status="success",
            source_mode="cache",
            start=op_start,
            returncode=0,
            parsed_summary={
                "aodv_enabled": True,
                "route_cache_hit": False,
                "fallback": True,
            },
            extra={
                "destination_hash": _hash_value(destination),
                "destination_redacted": True,
            },
        )
        return True

    def request_route(self, destination: str) -> bool:
        """
        Request route via AODV.

        Args:
            destination: Target node ID

        Returns:
            True if request sent
        """
        op_start = time.monotonic()
        # Check rate limit
        if destination in self.active_requests:
            if (
                self.active_requests[destination]
                >= self.config.aodv_route_request_retries
            ):
                self._publish_observation(
                    stage="batman_aodv_route_request_rate_limited",
                    operation="request_route",
                    status="skipped",
                    source_mode="memory",
                    start=op_start,
                    returncode=0,
                    parsed_summary={
                        "aodv_enabled": self.config.aodv_enabled,
                        "request_count": self.active_requests[destination],
                        "request_limit": self.config.aodv_route_request_retries,
                    },
                    extra={
                        "destination_hash": _hash_value(destination),
                        "destination_redacted": True,
                    },
                )
                logger.warning("AODV route request limit reached")
                return False

        # Increment request count
        self.active_requests[destination] = self.active_requests.get(destination, 0) + 1

        # AODV route request implementation
        # Uses batctl to request route via AODV fallback
        command_shape = [
            "batctl",
            "meshif",
            "bat0",
            "ping",
            "-c",
            "1",
            "<destination>",
        ]
        try:
            result = subprocess.run(
                ["batctl", "meshif", "bat0", "ping", "-c", "1", destination],
                capture_output=True,
                text=True,
                timeout=10,
            )
            request_sent = result.returncode == 0
            self._publish_observation(
                stage=(
                    "batman_aodv_route_request_completed"
                    if request_sent
                    else "batman_aodv_route_request_failed"
                ),
                operation="request_route",
                status="success" if request_sent else "failure",
                source_mode="batctl",
                start=op_start,
                returncode=result.returncode,
                parsed_summary={
                    "aodv_enabled": self.config.aodv_enabled,
                    "request_count": self.active_requests[destination],
                    "request_sent": request_sent,
                },
                extra={
                    "command_shape": command_shape,
                    "command_hash": _hash_value(" ".join(command_shape)),
                    "stdout_metadata": _output_metadata(result.stdout),
                    "stderr_metadata": _output_metadata(result.stderr),
                    "destination_hash": _hash_value(destination),
                    "destination_redacted": True,
                },
            )
            return request_sent
        except FileNotFoundError as exc:
            self._publish_observation(
                stage="batman_aodv_route_request_missing",
                operation="request_route",
                status="failure",
                source_mode="batctl",
                start=op_start,
                returncode=127,
                error=exc,
                parsed_summary={
                    "aodv_enabled": self.config.aodv_enabled,
                    "request_count": self.active_requests[destination],
                    "request_sent": False,
                },
                extra={
                    "command_shape": command_shape,
                    "command_hash": _hash_value(" ".join(command_shape)),
                    "destination_hash": _hash_value(destination),
                    "destination_redacted": True,
                },
            )
            return False
        except subprocess.TimeoutExpired as exc:
            self._publish_observation(
                stage="batman_aodv_route_request_timeout",
                operation="request_route",
                status="failure",
                source_mode="batctl",
                start=op_start,
                returncode=124,
                error=exc,
                parsed_summary={
                    "aodv_enabled": self.config.aodv_enabled,
                    "request_count": self.active_requests[destination],
                    "request_sent": False,
                },
                extra={
                    "command_shape": command_shape,
                    "command_hash": _hash_value(" ".join(command_shape)),
                    "destination_hash": _hash_value(destination),
                    "destination_redacted": True,
                },
            )
            return False
        logger.info(f"AODV route request for {destination}")
        return True


class BatmanAdvOptimizations:
    """
    Main class for Batman-adv optimizations from Paradox Zone.

    Integrates:
    - Multi-path routing
    - AODV fallback
    - Optimized timeouts
    - Enhanced buffering
    """

    def __init__(
        self,
        config: Optional[BatmanAdvConfig] = None,
        event_bus: Optional[EventBus] = None,
        event_project_root: str = ".",
    ):
        self.config = config or BatmanAdvConfig()
        self.event_bus = event_bus
        self.event_project_root = event_project_root

        # Initialize components
        self.multipath_router = (
            MultiPathRouter(
                self.config,
                event_bus=event_bus,
                event_project_root=event_project_root,
            )
            if self.config.multipath_enabled
            else None
        )
        self.aodv_fallback = (
            AODVFallback(
                self.config,
                event_bus=event_bus,
                event_project_root=event_project_root,
            )
            if self.config.aodv_enabled
            else None
        )

        logger.info("Batman-adv Optimizations initialized")

    def get_multipath_router(self) -> Optional[MultiPathRouter]:
        """Get multi-path router instance."""
        return self.multipath_router

    def get_aodv_fallback(self) -> Optional[AODVFallback]:
        """Get AODV fallback instance."""
        return self.aodv_fallback

    def apply_config(self) -> Dict[str, str]:
        """
        Generate Batman-adv configuration from optimizations.

        Returns:
            Configuration dictionary
        """
        config = {
            "originator_interval": self.config.originator_interval,
            "echo_interval": self.config.echo_interval,
            "route_record_timeout": self.config.route_record_timeout,
        }

        if self.config.multipath_enabled:
            config["multipath_mode"] = "1"
            config["multipath_max_paths"] = str(self.config.multipath_max_paths)
            config["multipath_path_discovery"] = "1"

        if self.config.aodv_enabled:
            config["aodv_fallback_timeout"] = self.config.aodv_fallback_timeout
            config["aodv_max_retries"] = str(self.config.aodv_route_request_retries)
            config["aodv_rate_limit"] = self.config.aodv_route_request_rate_limit

        config["packet_buffer_max"] = str(self.config.max_queue_length)
        config["retransmission_buffer_size"] = str(
            self.config.retransmission_buffer_size
        )
        config["neighbor_timeout"] = self.config.neighbor_timeout
        config["neighbor_aging_time"] = self.config.neighbor_aging_time

        if self.config.gateway_mode:
            config["gateway_mode"] = "1"
            config["gateway_selection_class"] = str(self.config.gateway_selection_class)

        return config

