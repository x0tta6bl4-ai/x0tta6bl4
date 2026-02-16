import argparse
import asyncio
import logging
import os
import random
import re
import subprocess
import sys
import threading

from aiohttp import web

# Add src to path
sys.path.append(os.path.join(os.path.dirname(__file__), ".."))

from src.core.consciousness import ConsciousnessEngine
from src.core.mape_k_loop import MAPEKLoop
from src.dao.ipfs_logger import DAOAuditLogger
from src.mesh.network_manager import MeshNetworkManager
from src.monitoring.prometheus_client import PrometheusExporter
from src.security.zero_trust import ZeroTrustValidator

logging.basicConfig(
    level=logging.INFO, format="%(asctime)s - %(name)s - %(levelname)s - %(message)s"
)
logger = logging.getLogger("Simulation")

# Global Prometheus Exporter instance for access in HTTP handler
prometheus_exporter = None


class SimMeshManager(MeshNetworkManager):
    def __init__(self, nodes: int):
        self.nodes = nodes
        self.tick = 0

    def _get_system_latency_offset(self) -> float:
        """
        Detects if 'tc' (traffic control) has added latency to the interface.
        This allows the simulation to be 'aware' of chaos injection.
        """
        try:
            # Run tc qdisc show to see if netem is active
            result = subprocess.run(
                ["tc", "qdisc", "show", "dev", "eth0"], capture_output=True, text=True
            )
            if result.returncode == 0 and "delay" in result.stdout:
                # Parse delay. E.g. "delay 500.0ms"
                match = re.search(r"delay (\d+\.?\d*)ms", result.stdout)
                if match:
                    return float(match.group(1))
        except Exception:
            pass
        return 0.0

    async def get_statistics(self):
        self.tick += 1

        # Simulate varying conditions based on sine wave to cycle through states
        import math

        phase = self.tick * 0.1

        # Base values
        cpu = 50 + 40 * math.sin(phase)  # 10 to 90
        latency = 85 + 50 * math.cos(phase * 0.7)  # 35 to 135

        # Add real injected latency
        injected_latency = self._get_system_latency_offset()
        latency += injected_latency

        if cpu > 80:
            latency += 50  # High load increases latency

        return {
            "active_peers": self.nodes,
            "avg_latency_ms": max(10, latency),
            "packet_loss_percent": (
                random.uniform(0, 2) if cpu < 70 else random.uniform(1, 5)
            ),
            "mttr_minutes": 3.14 + random.uniform(-0.5, 0.5),
        }

    async def set_route_preference(self, preference: str) -> bool:
        logger.info(f"Route preference set to: {preference}")
        return True

    async def trigger_aggressive_healing(self) -> int:
        logger.info("Aggressive healing triggered")
        return 1

    async def trigger_preemptive_checks(self):
        logger.info("Preemptive checks triggered")


async def metrics_handler(request):
    if prometheus_exporter:
        # Format metrics manually for Prometheus text format
        output = []
        for name, value in prometheus_exporter.metrics.items():
            # Add type info
            output.append(f"# HELP {name} x0tta6bl4 metric")
            output.append(f"# TYPE {name} gauge")
            output.append(f"{name} {value}")
        return web.Response(text="\n".join(output))
    return web.Response(text="# No metrics yet")


async def health_handler(request):
    return web.Response(text="OK")


async def main():
    global prometheus_exporter

    parser = argparse.ArgumentParser(
        description="Simulate x0tta6bl4 Mesh with Consciousness"
    )
    parser.add_argument("--nodes", type=int, default=10, help="Number of nodes")
    parser.add_argument(
        "--enable-consciousness",
        action="store_true",
        help="Enable consciousness engine",
    )
    args = parser.parse_args()

    logger.info(
        f"Starting simulation with {args.nodes} nodes. Consciousness enabled: {args.enable_consciousness}"
    )

    consciousness = ConsciousnessEngine(
        enable_advanced_metrics=args.enable_consciousness
    )
    mesh = SimMeshManager(nodes=args.nodes)
    prometheus_exporter = PrometheusExporter()
    zero_trust = ZeroTrustValidator()
    dao_logger = DAOAuditLogger()

    loop = MAPEKLoop(
        consciousness_engine=consciousness,
        mesh_manager=mesh,
        prometheus=prometheus_exporter,
        zero_trust=zero_trust,
        dao_logger=dao_logger,
    )

    # Override loop interval for simulation speed
    loop.loop_interval = 2

    # Start web server for metrics - USING ASYNCIO RUNNER CORRECTLY
    app = web.Application()
    app.router.add_get("/metrics", metrics_handler)
    app.router.add_get("/health", health_handler)
    runner = web.AppRunner(app)
    await runner.setup()
    site = web.TCPSite(runner, "0.0.0.0", 8080)
    await site.start()
    logger.info("Metrics server started on port 8080")

    try:
        await loop.start()
    except KeyboardInterrupt:
        await loop.stop()
    finally:
        await runner.cleanup()


if __name__ == "__main__":
    try:
        asyncio.run(main())
    except KeyboardInterrupt:
        pass
