"""Orchestrator factory and CLI entry point."""
from __future__ import annotations
import asyncio
import logging
from .core import EBPFOrchestrator, create_orchestrator
logger = logging.getLogger(__name__)


async def main():
    """Main entry point for standalone execution."""
    import argparse

    parser = argparse.ArgumentParser(description="x0tta6bl4 eBPF Orchestrator")
    parser.add_argument("-i", "--interface", default="eth0", help="Network interface")
    parser.add_argument(
        "-p", "--prometheus-port", type=int, default=9090, help="Prometheus port"
    )
    parser.add_argument(
        "--no-flows", action="store_true", help="Disable flow observability"
    )
    parser.add_argument(
        "--no-fallback", action="store_true", help="Disable dynamic fallback"
    )

    args = parser.parse_args()

    config = OrchestratorConfig(
        interface=args.interface,
        prometheus_port=args.prometheus_port,
        enable_flow_observability=not args.no_flows,
        enable_dynamic_fallback=not args.no_fallback,
    )

    orchestrator = EBPFOrchestrator(config)

    try:
        await orchestrator.start()

        # Keep running until interrupted
        while True:
            status = orchestrator.get_status()
            logger.info(
                f"Status: {status['state']}, Uptime: {status['uptime_seconds']:.0f}s"
            )
            await asyncio.sleep(30)

    except KeyboardInterrupt:
        logger.info("Shutting down...")
    finally:
        await orchestrator.stop()


if __name__ == "__main__":
    logging.basicConfig(
        level=logging.INFO,
        format="%(asctime)s - %(name)s - %(levelname)s - %(message)s",
    )
    asyncio.run(main())
