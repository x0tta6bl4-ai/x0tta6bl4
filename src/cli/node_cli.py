"""
x0tta6bl4 Node CLI.
Starts a mesh node with configurable obfuscation and traffic shaping.
"""

import argparse
import logging
import sys
import time

from libx0t.network.batman.node_manager import NodeManager
from libx0t.network.obfuscation import TransportManager

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger("node-cli")

TRAFFIC_PROFILES = [
    "none",
    "video_streaming",
    "voice_call",
    "web_browsing",
    "file_download",
    "gaming",
]


def main():
    parser = argparse.ArgumentParser(description="x0tta6bl4 Mesh Node")
    parser.add_argument("--mesh-id", default="x0tta6bl4-mesh", help="Mesh Network ID")
    parser.add_argument("--node-id", required=True, help="Unique Node ID")
    parser.add_argument(
        "--obfuscation",
        choices=["none", "xor", "faketls", "shadowsocks", "domain_fronting"],
        default="none",
        help="Traffic obfuscation strategy",
    )
    parser.add_argument(
        "--obfuscation-key", default=None, help="Key for XOR/Shadowsocks (required when obfuscation is enabled)"
    )
    parser.add_argument(
        "--traffic-profile",
        choices=TRAFFIC_PROFILES,
        default="none",
        help="Traffic shaping profile to mimic (evades DPI timing analysis)",
    )

    args = parser.parse_args()

    # 1. Configure Obfuscation
    transport = None
    if args.obfuscation != "none":
        logger.info(f"Initializing obfuscation transport: {args.obfuscation}")
        if args.obfuscation == "xor":
            transport = TransportManager.create("xor", key=args.obfuscation_key)
        elif args.obfuscation == "faketls":
            transport = TransportManager.create(
                "faketls", sni=args.obfuscation_key or "google.com"
            )
        elif args.obfuscation == "shadowsocks":
            transport = TransportManager.create(
                "shadowsocks", password=args.obfuscation_key
            )
        elif args.obfuscation == "domain_fronting":
            transport = TransportManager.create(
                "domain_fronting",
                front_domain="cdn.cloudflare.com",
                backend_host="mesh.example.com",
            )

        if not transport:
            logger.error(f"Failed to create transport: {args.obfuscation}")
            sys.exit(1)

    # 2. Log traffic shaping
    if args.traffic_profile != "none":
        logger.info(f"Traffic shaping enabled: {args.traffic_profile}")

    # 3. Initialize Node Manager
    logger.info(f"Starting NodeManager for {args.node_id} (Mesh: {args.mesh_id})")
    nm = NodeManager(
        mesh_id=args.mesh_id,
        local_node_id=args.node_id,
        obfuscation_transport=transport,
        traffic_profile=args.traffic_profile,
    )

    # 4. Run Node (Simulation loop)
    try:
        logger.info("Node running. Press Ctrl+C to stop.")
        while True:
            # In a real app, this would trigger heartbeats loop
            # For CLI demo, we just log occasional heartbeats
            nm.send_heartbeat("broadcast")
            time.sleep(10)
    except KeyboardInterrupt:
        logger.info("Stopping node...")


if __name__ == "__main__":
    main()
