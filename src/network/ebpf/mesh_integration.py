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
import ipaddress
import logging
import time
from dataclasses import dataclass
from typing import Dict, Optional

from ...monitoring.metrics import PrometheusMetrics
from ..batman.topology import MeshTopology
from .loader import EBPFLoader

logger = logging.getLogger(__name__)


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
    ):
        self.interface = interface
        self.topology = topology_manager or MeshTopology()
        self.loader = EBPFLoader(interface)
        self.metrics = PrometheusMetrics(port=prometheus_port)

        # Route cache to detect changes
        self.last_routes: Dict[str, MeshRoute] = {}

        # Metrics
        self.route_updates = 0
        self.packet_drops = 0
        self.path_switches = 0

        logger.info("eBPF Topology Integrator initialized")

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
        self.loader.update_routes(ebpf_routes)

        # Track changes
        current_keys = set(topology_routes.keys())
        last_keys = set(self.last_routes.keys())

        if current_keys != last_keys:
            self.route_updates += 1
            added = current_keys - last_keys
            removed = last_keys - current_keys
            logger.info(f"Route update: +{len(added)} -{len(removed)} routes")

        self.last_routes = topology_routes

    async def _get_topology_routes(self) -> Dict[str, MeshRoute]:
        """Extract routing table from topology manager"""
        routes = {}

        # This would integrate with the actual topology.py methods
        # For now, return mock routes
        try:
            # Mock implementation - replace with real topology queries
            nodes = self.topology.get_active_nodes()

            for node in nodes:
                if node.ip_address != self._get_local_ip():
                    routes[node.ip_address] = MeshRoute(
                        dest_ip=node.ip_address,
                        next_hop_ip=node.ip_address,  # Direct route
                        next_hop_ifindex=self._get_ifindex(self.interface),
                        tq_score=node.metrics.get("tq", 255),
                        hop_count=node.hop_count,
                    )
        except Exception as e:
            logger.warning(f"Failed to get topology routes: {e}")

        return routes

    async def _collect_metrics(self):
        """Collect and export metrics"""
        stats = self.loader.get_stats()

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
        except:
            pass

    def _get_local_ip(self) -> str:
        """Get local IP address"""
        import socket

        try:
            s = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
            s.connect(("8.8.8.8", 80))
            ip = s.getsockname()[0]
            s.close()
            return ip
        except:
            return "127.0.0.1"

    def _get_ifindex(self, interface: str) -> int:
        """Get interface index"""
        import socket

        try:
            return socket.if_nametoindex(interface)
        except:
            return 1  # Default

    async def shutdown(self):
        """Shutdown integrator"""
        self.loader.cleanup()
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
