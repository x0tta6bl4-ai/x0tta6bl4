#!/usr/bin/env python3
"""
eBPF Management CLI - Command-line interface for eBPF orchestrator.

This module provides a command-line interface for managing eBPF programs
using the EBPFOrchestrator.
"""

import argparse
import asyncio
import logging
import sys
from pathlib import Path
from typing import Optional

from src.network.ebpf.ebpf_orchestrator import (EBPFOrchestrator,
                                                OrchestratorConfig)
from src.network.ebpf.loader import EBPFAttachMode, EBPFProgramType

# Configure logging
logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s - %(name)s - %(levelname)s - %(message)s",
    handlers=[logging.StreamHandler()],
)
logger = logging.getLogger(__name__)


class EBPFCLI:
    """Command-line interface for eBPF management."""

    def __init__(self):
        self.parser = argparse.ArgumentParser(
            description="eBPF Management CLI for x0tta6bl4",
            formatter_class=argparse.RawDescriptionHelpFormatter,
            epilog="""
Examples:
  %(prog)s status                    # Show eBPF orchestrator status
  %(prog)s list                      # List loaded eBPF programs
  %(prog)s load xdp_filter.o         # Load eBPF program from file
  %(prog)s attach xdp_filter eth0    # Attach program to interface
  %(prog)s detach xdp_filter eth0    # Detach program from interface
  %(prog)s unload xdp_filter         # Unload eBPF program
  %(prog)s stats                     # Show eBPF statistics
  %(prog)s flows                     # Show network flow metrics
  %(prog)s routes                    # Show routing table
  %(prog)s update-routes routes.csv  # Update routing table
            """,
        )

        subparsers = self.parser.add_subparsers(
            dest="command", help="Available commands", metavar="COMMAND"
        )

        # Status command
        status_parser = subparsers.add_parser(
            "status", help="Show eBPF orchestrator status"
        )

        # List programs command
        list_parser = subparsers.add_parser("list", help="List loaded eBPF programs")

        # Load program command
        load_parser = subparsers.add_parser("load", help="Load eBPF program from file")
        load_parser.add_argument("program_path", help="Path to eBPF program file (.o)")
        load_parser.add_argument(
            "-t",
            "--type",
            default="xdp",
            choices=["xdp", "tc", "cgroup_skb", "socket_filter"],
            help="Program type (default: xdp)",
        )

        # Attach program command
        attach_parser = subparsers.add_parser(
            "attach", help="Attach eBPF program to interface"
        )
        attach_parser.add_argument("program_name", help="Name of program to attach")
        attach_parser.add_argument("interface", help="Network interface to attach to")
        attach_parser.add_argument(
            "-m",
            "--mode",
            default="skb",
            choices=["skb", "drv", "hw"],
            help="XDP attach mode (default: skb)",
        )

        # Detach program command
        detach_parser = subparsers.add_parser(
            "detach", help="Detach eBPF program from interface"
        )
        detach_parser.add_argument("program_name", help="Name of program to detach")
        detach_parser.add_argument("interface", help="Network interface to detach from")

        # Unload program command
        unload_parser = subparsers.add_parser("unload", help="Unload eBPF program")
        unload_parser.add_argument("program_name", help="Name of program to unload")

        # Statistics command
        stats_parser = subparsers.add_parser("stats", help="Show eBPF statistics")

        # Flows command
        flows_parser = subparsers.add_parser("flows", help="Show network flow metrics")

        # Routes command
        routes_parser = subparsers.add_parser("routes", help="Show routing table")

        # Update routes command
        update_routes_parser = subparsers.add_parser(
            "update-routes", help="Update routing table from file"
        )
        update_routes_parser.add_argument(
            "routes_file", help="Path to CSV file with routes"
        )

        # Configuration
        self.parser.add_argument(
            "-c", "--config", help="Path to orchestrator configuration file"
        )
        self.parser.add_argument(
            "-i",
            "--interface",
            default="eth0",
            help="Network interface (default: eth0)",
        )
        self.parser.add_argument(
            "-p",
            "--port",
            type=int,
            default=9090,
            help="Metrics server port (default: 9090)",
        )
        self.parser.add_argument(
            "-v", "--verbose", action="store_true", help="Enable verbose output"
        )

    async def run(self, args):
        """Run the CLI with the given arguments."""
        if args.verbose:
            logging.getLogger().setLevel(logging.DEBUG)

        config = OrchestratorConfig(interface=args.interface, metrics_port=args.port)

        try:
            async with EBPFOrchestrator(config) as orchestrator:
                logger.debug("Orchestrator initialized")

                if args.command == "status":
                    await self._handle_status(orchestrator)

                elif args.command == "list":
                    await self._handle_list(orchestrator)

                elif args.command == "load":
                    await self._handle_load(orchestrator, args.program_path, args.type)

                elif args.command == "attach":
                    await self._handle_attach(
                        orchestrator, args.program_name, args.interface, args.mode
                    )

                elif args.command == "detach":
                    await self._handle_detach(
                        orchestrator, args.program_name, args.interface
                    )

                elif args.command == "unload":
                    await self._handle_unload(orchestrator, args.program_name)

                elif args.command == "stats":
                    await self._handle_stats(orchestrator)

                elif args.command == "flows":
                    await self._handle_flows(orchestrator)

                elif args.command == "routes":
                    await self._handle_routes(orchestrator)

                elif args.command == "update-routes":
                    await self._handle_update_routes(orchestrator, args.routes_file)

                else:
                    self.parser.print_help()
                    return False

                return True

        except Exception as e:
            logger.error(f"Error: {e}")
            logger.debug(f"Exception details: {type(e).__name__}: {e}", exc_info=True)
            return False

    async def _handle_status(self, orchestrator: EBPFOrchestrator):
        """Handle status command."""
        status = orchestrator.get_status()
        print("=== eBPF Orchestrator Status ===")
        print(f"Status: {status['orchestrator_status']}")
        print(f"Components: {len(status['components'])}")
        print()

        for comp_name, comp_status in status["components"].items():
            print(f"  {comp_name}: {comp_status['status']}")
            if "error" in comp_status:
                print(f"    Error: {comp_status['error']}")
        print()

    async def _handle_list(self, orchestrator: EBPFOrchestrator):
        """Handle list command."""
        programs = orchestrator.list_loaded_programs()
        print("=== Loaded eBPF Programs ===")
        print(f"Total: {len(programs)}")
        print()

        for program in programs:
            print(f"  ID: {program['id']}")
            print(f"  Path: {program['path']}")
            print(f"  Type: {program['type']}")
            if "attached_to" in program:
                print(f"  Attached to: {program['attached_to']}")
            print()

    async def _handle_load(
        self, orchestrator: EBPFOrchestrator, program_path: str, program_type: str
    ):
        """Handle load command."""
        program_path = Path(program_path)
        if not program_path.exists():
            logger.error(f"Error: File not found: {program_path}")
            return

        prog_type = EBPFProgramType(program_type)

        try:
            result = await orchestrator.load_program(
                program_path.name, program_type=prog_type
            )
            if result.get("success"):
                logger.info(f"Successfully loaded program: {program_path.name}")
            else:
                logger.error(
                    f"Error loading program: {result.get('error', 'Unknown error')}"
                )
        except Exception as e:
            logger.error(f"Error loading program: {e}")

    async def _handle_attach(
        self,
        orchestrator: EBPFOrchestrator,
        program_name: str,
        interface: str,
        mode: str,
    ):
        """Handle attach command."""
        attach_mode = EBPFAttachMode(mode)

        try:
            result = await orchestrator.attach_program(
                program_name, interface=interface
            )
            if result.get("success"):
                logger.info(
                    f"Successfully attached program '{program_name}' to '{interface}'"
                )
            else:
                logger.error(
                    f"Error attaching program: {result.get('error', 'Unknown error')}"
                )
        except Exception as e:
            logger.error(f"Error attaching program: {e}")

    async def _handle_detach(
        self, orchestrator: EBPFOrchestrator, program_name: str, interface: str
    ):
        """Handle detach command."""
        try:
            result = await orchestrator.detach_program(
                program_name, interface=interface
            )
            if result.get("success"):
                logger.info(
                    f"Successfully detached program '{program_name}' from '{interface}'"
                )
            else:
                logger.error(
                    f"Error detaching program: {result.get('error', 'Unknown error')}"
                )
        except Exception as e:
            logger.error(f"Error detaching program: {e}")

    async def _handle_unload(self, orchestrator: EBPFOrchestrator, program_name: str):
        """Handle unload command."""
        try:
            result = await orchestrator.unload_program(program_name)
            if result.get("success"):
                logger.info(f"Successfully unloaded program: {program_name}")
            else:
                logger.error(
                    f"Error unloading program: {result.get('error', 'Unknown error')}"
                )
        except Exception as e:
            logger.error(f"Error unloading program: {e}")

    async def _handle_stats(self, orchestrator: EBPFOrchestrator):
        """Handle stats command."""
        stats = orchestrator.get_stats()
        print("=== eBPF Statistics ===")
        print()

        for comp_name, comp_stats in stats.items():
            if isinstance(comp_stats, dict) and "error" not in comp_stats:
                print(f"  {comp_name}:")
                for key, value in comp_stats.items():
                    if isinstance(value, (int, float)):
                        print(f"    {key}: {value}")
                    elif isinstance(value, dict):
                        print(f"    {key}:")
                        for k, v in value.items():
                            print(f"      {k}: {v}")
                print()

    async def _handle_flows(self, orchestrator: EBPFOrchestrator):
        """Handle flows command."""
        flows = orchestrator.get_flows()
        print("=== Network Flow Metrics ===")
        print()

        if "flows" in flows:
            for flow in flows["flows"]:
                print(f"  Source: {flow['source']}")
                print(f"  Destination: {flow['destination']}")
                print(f"  Protocol: {flow['protocol']}")
                print(f"  Packets: {flow['packets']}")
                print(f"  Bytes: {flow['bytes']}")
                print()
        else:
            print("No flow metrics available")

    async def _handle_routes(self, orchestrator: EBPFOrchestrator):
        """Handle routes command."""
        try:
            import subprocess

            result = subprocess.run(
                ["bpftool", "map", "dump", "name", "mesh_routes", "-j"],
                capture_output=True,
                text=True,
                timeout=5,
            )

            if result.returncode == 0:
                import json

                routes = json.loads(result.stdout)
                print("=== Mesh Routing Table ===")
                print()

                for route in routes:
                    dest_ip = route["key"]
                    next_hop = route["value"]
                    print(f"  {dest_ip} -> {next_hop}")

        except FileNotFoundError:
            logger.warning("bpftool not found, routes may be unavailable")
        except Exception as e:
            logger.error(f"Error getting routes: {e}")

    async def _handle_update_routes(
        self, orchestrator: EBPFOrchestrator, routes_file: str
    ):
        """Handle update-routes command."""
        routes_file = Path(routes_file)
        if not routes_file.exists():
            logger.error(f"Error: File not found: {routes_file}")
            return

        routes = {}
        try:
            with open(routes_file, "r") as f:
                import csv

                reader = csv.DictReader(f)
                for row in reader:
                    dest_ip = row.get("destination")
                    next_hop = row.get("next_hop")
                    if dest_ip and next_hop:
                        routes[dest_ip] = next_hop

            if not routes:
                logger.warning("No valid routes found in file")
                return

            result = orchestrator.update_routes(routes)
            if result:
                logger.info(f"Successfully updated {len(routes)} routes")
            else:
                logger.error("Failed to update routes")

        except Exception as e:
            logger.error(f"Error updating routes: {e}")


def main():
    """Entry point for the eBPF CLI."""
    cli = EBPFCLI()
    args = cli.parser.parse_args()

    if args.command is None:
        cli.parser.print_help()
        return 1

    try:
        success = asyncio.run(cli.run(args))
        return 0 if success else 1

    except KeyboardInterrupt:
        logger.info("Operation cancelled by user")
        return 1

    except Exception as e:
        logger.error(f"Unexpected error: {e}")
        logger.debug(f"Exception details: {type(e).__name__}: {e}", exc_info=True)
        return 2


if __name__ == "__main__":
    sys.exit(main())
