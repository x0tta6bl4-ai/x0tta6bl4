#!/usr/bin/env python3
"""
x0tta6bl4 eBPF Mesh Integration
Integrates eBPF networking layer with batman-adv topology for dynamic routing.

This module provides the bridge between:
- Batman-adv topology discovery (src/network/batman/topology.py)
- eBPF XDP programs for packet filtering/routing
- Prometheus metrics collection

Features:
- Dynamic route updates from topology changes
- Packet drop rate monitoring
- Path switch frequency tracking
- TQ score integration
"""

import asyncio
import hashlib
import ipaddress
import logging
import socket
import time
from dataclasses import dataclass
from typing import Any, Dict, List, Optional

try:
    from ...monitoring.metrics import PrometheusMetrics
except ImportError:
    from ...monitoring.prometheus_client import PrometheusExporter as PrometheusMetrics

from ...coordination.events import EventBus, EventType
from ..batman.topology import MeshTopology
from ...services.service_event_identity import service_event_identity
from .loader import EBPFLoader

logger = logging.getLogger(__name__)

EBPF_MESH_INTEGRATION_SERVICE_NAME = "ebpf-mesh-integration"
EBPF_MESH_INTEGRATION_LAYER = "network_ebpf_mesh_integration_observed_state"
EBPF_MESH_INTEGRATION_CLAIM_BOUNDARY = (
    "Local eBPF mesh integration evidence only. Events record topology route reads, "
    "route-map sync attempts, metrics export, local socket IP probes, interface-index "
    "lookups, and cleanup with hashed interface/IP/route selectors; they do not prove "
    "production packet forwarding, remote peer identity, batman-adv convergence, or "
    "kernel datapath enforcement beyond the local operation result."
)


def _sha256_text(value: str) -> Optional[str]:
    if not value:
        return None
    return hashlib.sha256(value.encode("utf-8", errors="replace")).hexdigest()


def _hash_value(value: Any) -> Optional[str]:
    if value is None:
        return None
    if isinstance(value, bytes):
        return hashlib.sha256(value).hexdigest()
    return _sha256_text(str(value))


def _identity_metadata() -> Dict[str, Any]:
    identity = service_event_identity(service_name=EBPF_MESH_INTEGRATION_SERVICE_NAME)
    return {
        "service_name": EBPF_MESH_INTEGRATION_SERVICE_NAME,
        "layer": EBPF_MESH_INTEGRATION_LAYER,
        "spiffe_id_configured": bool(identity.get("spiffe_id")),
        "did_configured": bool(identity.get("did")),
        "wallet_address_configured": bool(identity.get("wallet_address")),
        "redacted": True,
    }


def _bounded_hashes(values: List[Any], limit: int = 20) -> Dict[str, Any]:
    selected = values[:limit]
    return {
        "hashes": [_hash_value(value) for value in selected],
        "count": len(values),
        "limit": limit,
        "truncated": len(values) > limit,
    }


def _build_mesh_topology() -> MeshTopology:
    try:
        return MeshTopology(mesh_id="default-mesh", local_node_id="local-node")
    except TypeError:
        return MeshTopology()


def _build_metrics_sink(prometheus_port: int):
    try:
        return PrometheusMetrics(port=prometheus_port)
    except TypeError:
        return PrometheusMetrics()


@dataclass
class MeshRoute:
    """Represents a mesh routing entry"""

    dest_ip: str
    next_hop_ip: str
    next_hop_ifindex: int
    tq_score: int  # Transmission Quality score (0-255)
    hop_count: int


class EBPFTopologyIntegrator:
    """
    Integrates eBPF loader with batman-adv topology manager.

    Periodically syncs routing table from topology to eBPF maps.
    """

    def __init__(
        self,
        interface: str = "eth0",
        topology_manager: Optional[MeshTopology] = None,
        prometheus_port: int = 9090,
        event_bus: Optional[EventBus] = None,
        event_project_root: str = ".",
        loader: Optional[EBPFLoader] = None,
        metrics: Optional[Any] = None,
    ):
        op_start = time.monotonic()
        self.interface = interface
        self.topology = topology_manager or _build_mesh_topology()
        self.event_bus = event_bus
        self.event_project_root = event_project_root
        self.source_agent = EBPF_MESH_INTEGRATION_SERVICE_NAME
        if loader is not None:
            self.loader = loader
        else:
            try:
                self.loader = EBPFLoader(
                    interface,
                    event_bus=event_bus,
                    event_project_root=event_project_root,
                )
            except TypeError:
                self.loader = EBPFLoader(interface)
        self.metrics = metrics or _build_metrics_sink(prometheus_port)

        # Route cache to detect changes
        self.last_routes: Dict[str, MeshRoute] = {}

        # Metrics
        self.route_updates = 0
        self.packet_drops = 0
        self.path_switches = 0

        logger.info("eBPF Topology Integrator initialized")
        self._publish_observation(
            stage="ebpf_mesh_integration_initialized",
            operation="init",
            status="success",
            source_mode="memory",
            start=op_start,
            read_only=False,
            parsed_summary={
                "prometheus_port": prometheus_port,
                "route_updates": self.route_updates,
                "packet_drops": self.packet_drops,
                "path_switches": self.path_switches,
                "loader_injected": loader is not None,
                "metrics_injected": metrics is not None,
            },
        )

    def _event_bus_or_none(self) -> Optional[EventBus]:
        event_bus = getattr(self, "event_bus", None)
        if event_bus is not None:
            return event_bus
        try:
            event_bus = EventBus(project_root=getattr(self, "event_project_root", "."))
            self.event_bus = event_bus
            return event_bus
        except Exception as exc:
            logger.error("Failed to initialize eBPF mesh integration EventBus: %s", exc)
            return None

    def _publish_observation(
        self,
        *,
        stage: str,
        operation: str,
        status: str,
        source_mode: str,
        start: float,
        read_only: bool = True,
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
            EBPF_MESH_INTEGRATION_SERVICE_NAME,
        )
        payload: Dict[str, Any] = {
            "component": "network.ebpf.mesh_integration",
            "stage": stage,
            "operation": operation,
            "operation_resource": f"network:ebpf:mesh_integration:{operation}",
            "service_name": source_agent,
            "layer": EBPF_MESH_INTEGRATION_LAYER,
            "identity": _identity_metadata(),
            "status": status,
            "source_mode": source_mode,
            "returncode": returncode,
            "duration_ms": round((time.monotonic() - start) * 1000, 3),
            "read_only": read_only,
            "observed_state": True,
            "safe_observation": True,
            "safe_actuator": False,
            "parsed_summary": parsed_summary or {},
            "payloads_redacted": True,
            "claim_boundary": EBPF_MESH_INTEGRATION_CLAIM_BOUNDARY,
            "interface_hash": _hash_value(getattr(self, "interface", None)),
            "interface_redacted": True,
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
                priority=4,
            )
            return event.event_id
        except Exception:
            logger.exception("Failed to publish eBPF mesh integration observation")
            return None

    async def start_integration(self):
        """Start the integration loop"""
        logger.info("Starting eBPF-topology integration...")

        while True:
            try:
                await self._sync_routes()
                await self._collect_metrics()
                await asyncio.sleep(30)  # Sync every 30 seconds
            except Exception as e:
                logger.error(f"Integration error: {e}")
                await asyncio.sleep(5)

    async def _sync_routes(self):
        """Sync routes from topology to eBPF maps"""
        op_start = time.monotonic()
        # Get current routing table from topology
        topology_routes = await self._get_topology_routes()

        # Convert to eBPF map format: {dest_ip: next_hop_ifindex}
        ebpf_routes = {}
        for route in topology_routes.values():
            try:
                dest_ip_int = int(ipaddress.IPv4Address(route.dest_ip))
                ebpf_routes[str(dest_ip_int)] = str(route.next_hop_ifindex)
            except ValueError:
                continue

        # Update eBPF maps
        try:
            update_result = self.loader.update_routes(ebpf_routes)
        except Exception as exc:
            self._publish_observation(
                stage="ebpf_mesh_route_sync_failed",
                operation="sync_routes",
                status="failure",
                source_mode="loader",
                start=op_start,
                read_only=False,
                returncode=1,
                error=exc,
                parsed_summary={
                    "topology_routes_total": len(topology_routes),
                    "ebpf_routes_total": len(ebpf_routes),
                },
                extra={
                    "route_dest_hashes": _bounded_hashes(list(topology_routes.keys())),
                    "ebpf_route_key_hashes": _bounded_hashes(list(ebpf_routes.keys())),
                    "route_selectors_redacted": True,
                },
            )
            raise

        # Track changes
        current_keys = set(topology_routes.keys())
        last_keys = set(self.last_routes.keys())

        added = current_keys - last_keys
        removed = last_keys - current_keys
        if current_keys != last_keys:
            self.route_updates += 1
            logger.info(f"Route update: +{len(added)} -{len(removed)} routes")

        self.last_routes = topology_routes
        self._publish_observation(
            stage=(
                "ebpf_mesh_route_sync_completed"
                if update_result
                else "ebpf_mesh_route_sync_loader_failed"
            ),
            operation="sync_routes",
            status="success" if update_result else "failure",
            source_mode="loader",
            start=op_start,
            read_only=False,
            returncode=0 if update_result else 1,
            parsed_summary={
                "topology_routes_total": len(topology_routes),
                "ebpf_routes_total": len(ebpf_routes),
                "route_updates_total": self.route_updates,
                "added_count": len(added),
                "removed_count": len(removed),
                "loader_update_result": bool(update_result),
            },
            extra={
                "route_dest_hashes": _bounded_hashes(list(topology_routes.keys())),
                "ebpf_route_key_hashes": _bounded_hashes(list(ebpf_routes.keys())),
                "next_hop_ifindex_hashes": _bounded_hashes(list(ebpf_routes.values())),
                "added_route_hashes": _bounded_hashes(list(added)),
                "removed_route_hashes": _bounded_hashes(list(removed)),
                "route_selectors_redacted": True,
            },
        )

    async def _get_topology_routes(self) -> Dict[str, MeshRoute]:
        """Extract routing table from topology manager"""
        op_start = time.monotonic()
        routes = {}

        # This would integrate with the actual topology.py methods
        # For now, return mock routes
        try:
            # Mock implementation - replace with real topology queries
            nodes = self._active_topology_nodes()
            local_ip = self._get_local_ip()
            ifindex = self._get_ifindex(self.interface)

            for node in nodes:
                if node.ip_address != local_ip:
                    routes[node.ip_address] = MeshRoute(
                        dest_ip=node.ip_address,
                        next_hop_ip=node.ip_address,  # Direct route
                        next_hop_ifindex=ifindex,
                        tq_score=node.metrics.get("tq", 255),
                        hop_count=node.hop_count,
                    )
        except Exception as e:
            logger.warning(f"Failed to get topology routes: {e}")
            self._publish_observation(
                stage="ebpf_mesh_topology_routes_failed",
                operation="get_topology_routes",
                status="failure",
                source_mode="topology",
                start=op_start,
                returncode=1,
                error=e,
                parsed_summary={"routes_total": len(routes)},
            )
            return routes

        self._publish_observation(
            stage="ebpf_mesh_topology_routes_collected",
            operation="get_topology_routes",
            status="success",
            source_mode="topology",
            start=op_start,
            returncode=0,
            parsed_summary={
                "nodes_total": len(nodes),
                "routes_total": len(routes),
            },
            extra={
                "route_dest_hashes": _bounded_hashes(list(routes.keys())),
                "route_selectors_redacted": True,
            },
        )
        return routes

    def _active_topology_nodes(self) -> List[Any]:
        get_active_nodes = getattr(self.topology, "get_active_nodes", None)
        if callable(get_active_nodes):
            return list(get_active_nodes())
        nodes = getattr(self.topology, "nodes", {})
        if isinstance(nodes, dict):
            values = list(nodes.values())
        else:
            values = list(nodes or [])
        active = []
        for node in values:
            is_alive = getattr(node, "is_alive", None)
            if callable(is_alive) and not is_alive():
                continue
            active.append(node)
        return active

    async def _collect_metrics(self):
        """Collect and export metrics"""
        op_start = time.monotonic()
        try:
            stats = self.loader.get_stats()
        except Exception as exc:
            self._publish_observation(
                stage="ebpf_mesh_metrics_collection_failed",
                operation="collect_metrics",
                status="failure",
                source_mode="loader",
                start=op_start,
                returncode=1,
                error=exc,
                parsed_summary={"metrics_exported": False},
            )
            raise

        # Update Prometheus metrics
        self.metrics.set_gauge("mesh_route_updates_total", self.route_updates)
        self.metrics.set_gauge(
            "mesh_packet_drops_total", stats.get("dropped_packets", 0)
        )
        self.metrics.set_gauge(
            "mesh_packets_forwarded_total", stats.get("forwarded_packets", 0)
        )

        # Batman-adv specific metrics
        try:
            tq_scores = [route.tq_score for route in self.last_routes.values()]
            if tq_scores:
                avg_tq = sum(tq_scores) / len(tq_scores)
                self.metrics.set_gauge("mesh_average_tq_score", avg_tq)
        except Exception:
            pass
        self._publish_observation(
            stage="ebpf_mesh_metrics_collected",
            operation="collect_metrics",
            status="success",
            source_mode="loader",
            start=op_start,
            returncode=0,
            parsed_summary={
                "route_updates_total": self.route_updates,
                "dropped_packets": stats.get("dropped_packets", 0),
                "forwarded_packets": stats.get("forwarded_packets", 0),
                "routes_cached": len(self.last_routes),
                "tq_scores_count": len(tq_scores) if "tq_scores" in locals() else 0,
                "avg_tq": avg_tq if "avg_tq" in locals() else None,
            },
        )

    def _get_local_ip(self) -> str:
        """Get local IP address"""
        op_start = time.monotonic()
        sock = None
        try:
            sock = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
            sock.connect(("8.8.8.8", 80))
            ip = sock.getsockname()[0]
            self._publish_observation(
                stage="ebpf_mesh_local_ip_probe_completed",
                operation="get_local_ip",
                status="success",
                source_mode="socket",
                start=op_start,
                returncode=0,
                parsed_summary={"fallback": False},
                extra={
                    "local_ip_hash": _hash_value(ip),
                    "probe_target_hash": _hash_value("8.8.8.8:80"),
                    "local_ip_redacted": True,
                    "probe_target_redacted": True,
                },
            )
            return ip
        except Exception as exc:
            self._publish_observation(
                stage="ebpf_mesh_local_ip_probe_fallback",
                operation="get_local_ip",
                status="failure",
                source_mode="socket",
                start=op_start,
                returncode=1,
                error=exc,
                parsed_summary={"fallback": True},
                extra={
                    "local_ip_hash": _hash_value("127.0.0.1"),
                    "probe_target_hash": _hash_value("8.8.8.8:80"),
                    "local_ip_redacted": True,
                    "probe_target_redacted": True,
                },
            )
            return "127.0.0.1"
        finally:
            if sock is not None:
                sock.close()

    def _get_ifindex(self, interface: str) -> int:
        """Get interface index"""
        op_start = time.monotonic()
        try:
            ifindex = socket.if_nametoindex(interface)
            self._publish_observation(
                stage="ebpf_mesh_ifindex_lookup_completed",
                operation="get_ifindex",
                status="success",
                source_mode="socket",
                start=op_start,
                returncode=0,
                parsed_summary={"ifindex": ifindex, "fallback": False},
                extra={
                    "requested_interface_hash": _hash_value(interface),
                    "requested_interface_redacted": True,
                },
            )
            return ifindex
        except Exception as exc:
            self._publish_observation(
                stage="ebpf_mesh_ifindex_lookup_fallback",
                operation="get_ifindex",
                status="failure",
                source_mode="socket",
                start=op_start,
                returncode=1,
                error=exc,
                parsed_summary={"ifindex": 1, "fallback": True},
                extra={
                    "requested_interface_hash": _hash_value(interface),
                    "requested_interface_redacted": True,
                },
            )
            return 1  # Default

    async def shutdown(self):
        """Shutdown integrator"""
        op_start = time.monotonic()
        try:
            self.loader.cleanup()
        except Exception as exc:
            self._publish_observation(
                stage="ebpf_mesh_shutdown_failed",
                operation="shutdown",
                status="failure",
                source_mode="loader",
                start=op_start,
                read_only=False,
                returncode=1,
                error=exc,
                parsed_summary={"cleanup": False},
            )
            raise
        self._publish_observation(
            stage="ebpf_mesh_shutdown_completed",
            operation="shutdown",
            status="success",
            source_mode="loader",
            start=op_start,
            read_only=False,
            returncode=0,
            parsed_summary={"cleanup": True},
        )
        logger.info("eBPF Topology Integrator shut down")


# Standalone runner
async def main():
    integrator = EBPFTopologyIntegrator()
    try:
        await integrator.start_integration()
    except KeyboardInterrupt:
        await integrator.shutdown()


if __name__ == "__main__":
    asyncio.run(main())
