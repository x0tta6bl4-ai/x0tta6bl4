"""
x0tta6bl4 Node CLI.
Starts a mesh node with configurable obfuscation and traffic shaping.
"""
import argparse
import logging
import sys
import time
from src.network.batman.node_manager import NodeManager
from src.network.obfuscation import TransportManager

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger("node-cli")

TRAFFIC_PROFILES = ["none", "video_streaming", "voice_call", "web_browsing", "file_download", "gaming"]
from inspect import signature as _mutmut_signature
from typing import Annotated
from typing import Callable
from typing import ClassVar


MutantDict = Annotated[dict[str, Callable], "Mutant"]


def _mutmut_trampoline(orig, mutants, call_args, call_kwargs, self_arg = None):
    """Forward call to original or mutated function, depending on the environment"""
    import os
    mutant_under_test = os.environ['MUTANT_UNDER_TEST']
    if mutant_under_test == 'fail':
        from mutmut.__main__ import MutmutProgrammaticFailException
        raise MutmutProgrammaticFailException('Failed programmatically')      
    elif mutant_under_test == 'stats':
        from mutmut.__main__ import record_trampoline_hit
        record_trampoline_hit(orig.__module__ + '.' + orig.__name__)
        result = orig(*call_args, **call_kwargs)
        return result
    prefix = orig.__module__ + '.' + orig.__name__ + '__mutmut_'
    if not mutant_under_test.startswith(prefix):
        result = orig(*call_args, **call_kwargs)
        return result
    mutant_name = mutant_under_test.rpartition('.')[-1]
    if self_arg is not None:
        # call to a class method where self is not bound
        result = mutants[mutant_name](self_arg, *call_args, **call_kwargs)
    else:
        result = mutants[mutant_name](*call_args, **call_kwargs)
    return result

def x_main__mutmut_orig():
    parser = argparse.ArgumentParser(description="x0tta6bl4 Mesh Node")
    parser.add_argument("--mesh-id", default="x0tta6bl4-mesh", help="Mesh Network ID")
    parser.add_argument("--node-id", required=True, help="Unique Node ID")
    parser.add_argument("--obfuscation", 
                        choices=["none", "xor", "faketls", "shadowsocks", "domain_fronting"], 
                        default="none",
                        help="Traffic obfuscation strategy")
    parser.add_argument("--obfuscation-key", default="x0tta6bl4", help="Key for XOR/Shadowsocks")
    parser.add_argument("--traffic-profile",
                        choices=TRAFFIC_PROFILES,
                        default="none",
                        help="Traffic shaping profile to mimic (evades DPI timing analysis)")
    
    args = parser.parse_args()
    
    # 1. Configure Obfuscation
    transport = None
    if args.obfuscation != "none":
        logger.info(f"Initializing obfuscation transport: {args.obfuscation}")
        if args.obfuscation == "xor":
            transport = TransportManager.create("xor", key=args.obfuscation_key)
        elif args.obfuscation == "faketls":
            transport = TransportManager.create("faketls", sni=args.obfuscation_key or "google.com")
        elif args.obfuscation == "shadowsocks":
            transport = TransportManager.create("shadowsocks", password=args.obfuscation_key)
        elif args.obfuscation == "domain_fronting":
            transport = TransportManager.create("domain_fronting", 
                                                front_domain="cdn.cloudflare.com",
                                                backend_host="mesh.example.com")
            
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
        traffic_profile=args.traffic_profile
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

def x_main__mutmut_1():
    parser = None
    parser.add_argument("--mesh-id", default="x0tta6bl4-mesh", help="Mesh Network ID")
    parser.add_argument("--node-id", required=True, help="Unique Node ID")
    parser.add_argument("--obfuscation", 
                        choices=["none", "xor", "faketls", "shadowsocks", "domain_fronting"], 
                        default="none",
                        help="Traffic obfuscation strategy")
    parser.add_argument("--obfuscation-key", default="x0tta6bl4", help="Key for XOR/Shadowsocks")
    parser.add_argument("--traffic-profile",
                        choices=TRAFFIC_PROFILES,
                        default="none",
                        help="Traffic shaping profile to mimic (evades DPI timing analysis)")
    
    args = parser.parse_args()
    
    # 1. Configure Obfuscation
    transport = None
    if args.obfuscation != "none":
        logger.info(f"Initializing obfuscation transport: {args.obfuscation}")
        if args.obfuscation == "xor":
            transport = TransportManager.create("xor", key=args.obfuscation_key)
        elif args.obfuscation == "faketls":
            transport = TransportManager.create("faketls", sni=args.obfuscation_key or "google.com")
        elif args.obfuscation == "shadowsocks":
            transport = TransportManager.create("shadowsocks", password=args.obfuscation_key)
        elif args.obfuscation == "domain_fronting":
            transport = TransportManager.create("domain_fronting", 
                                                front_domain="cdn.cloudflare.com",
                                                backend_host="mesh.example.com")
            
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
        traffic_profile=args.traffic_profile
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

def x_main__mutmut_2():
    parser = argparse.ArgumentParser(description=None)
    parser.add_argument("--mesh-id", default="x0tta6bl4-mesh", help="Mesh Network ID")
    parser.add_argument("--node-id", required=True, help="Unique Node ID")
    parser.add_argument("--obfuscation", 
                        choices=["none", "xor", "faketls", "shadowsocks", "domain_fronting"], 
                        default="none",
                        help="Traffic obfuscation strategy")
    parser.add_argument("--obfuscation-key", default="x0tta6bl4", help="Key for XOR/Shadowsocks")
    parser.add_argument("--traffic-profile",
                        choices=TRAFFIC_PROFILES,
                        default="none",
                        help="Traffic shaping profile to mimic (evades DPI timing analysis)")
    
    args = parser.parse_args()
    
    # 1. Configure Obfuscation
    transport = None
    if args.obfuscation != "none":
        logger.info(f"Initializing obfuscation transport: {args.obfuscation}")
        if args.obfuscation == "xor":
            transport = TransportManager.create("xor", key=args.obfuscation_key)
        elif args.obfuscation == "faketls":
            transport = TransportManager.create("faketls", sni=args.obfuscation_key or "google.com")
        elif args.obfuscation == "shadowsocks":
            transport = TransportManager.create("shadowsocks", password=args.obfuscation_key)
        elif args.obfuscation == "domain_fronting":
            transport = TransportManager.create("domain_fronting", 
                                                front_domain="cdn.cloudflare.com",
                                                backend_host="mesh.example.com")
            
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
        traffic_profile=args.traffic_profile
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

def x_main__mutmut_3():
    parser = argparse.ArgumentParser(description="XXx0tta6bl4 Mesh NodeXX")
    parser.add_argument("--mesh-id", default="x0tta6bl4-mesh", help="Mesh Network ID")
    parser.add_argument("--node-id", required=True, help="Unique Node ID")
    parser.add_argument("--obfuscation", 
                        choices=["none", "xor", "faketls", "shadowsocks", "domain_fronting"], 
                        default="none",
                        help="Traffic obfuscation strategy")
    parser.add_argument("--obfuscation-key", default="x0tta6bl4", help="Key for XOR/Shadowsocks")
    parser.add_argument("--traffic-profile",
                        choices=TRAFFIC_PROFILES,
                        default="none",
                        help="Traffic shaping profile to mimic (evades DPI timing analysis)")
    
    args = parser.parse_args()
    
    # 1. Configure Obfuscation
    transport = None
    if args.obfuscation != "none":
        logger.info(f"Initializing obfuscation transport: {args.obfuscation}")
        if args.obfuscation == "xor":
            transport = TransportManager.create("xor", key=args.obfuscation_key)
        elif args.obfuscation == "faketls":
            transport = TransportManager.create("faketls", sni=args.obfuscation_key or "google.com")
        elif args.obfuscation == "shadowsocks":
            transport = TransportManager.create("shadowsocks", password=args.obfuscation_key)
        elif args.obfuscation == "domain_fronting":
            transport = TransportManager.create("domain_fronting", 
                                                front_domain="cdn.cloudflare.com",
                                                backend_host="mesh.example.com")
            
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
        traffic_profile=args.traffic_profile
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

def x_main__mutmut_4():
    parser = argparse.ArgumentParser(description="x0tta6bl4 mesh node")
    parser.add_argument("--mesh-id", default="x0tta6bl4-mesh", help="Mesh Network ID")
    parser.add_argument("--node-id", required=True, help="Unique Node ID")
    parser.add_argument("--obfuscation", 
                        choices=["none", "xor", "faketls", "shadowsocks", "domain_fronting"], 
                        default="none",
                        help="Traffic obfuscation strategy")
    parser.add_argument("--obfuscation-key", default="x0tta6bl4", help="Key for XOR/Shadowsocks")
    parser.add_argument("--traffic-profile",
                        choices=TRAFFIC_PROFILES,
                        default="none",
                        help="Traffic shaping profile to mimic (evades DPI timing analysis)")
    
    args = parser.parse_args()
    
    # 1. Configure Obfuscation
    transport = None
    if args.obfuscation != "none":
        logger.info(f"Initializing obfuscation transport: {args.obfuscation}")
        if args.obfuscation == "xor":
            transport = TransportManager.create("xor", key=args.obfuscation_key)
        elif args.obfuscation == "faketls":
            transport = TransportManager.create("faketls", sni=args.obfuscation_key or "google.com")
        elif args.obfuscation == "shadowsocks":
            transport = TransportManager.create("shadowsocks", password=args.obfuscation_key)
        elif args.obfuscation == "domain_fronting":
            transport = TransportManager.create("domain_fronting", 
                                                front_domain="cdn.cloudflare.com",
                                                backend_host="mesh.example.com")
            
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
        traffic_profile=args.traffic_profile
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

def x_main__mutmut_5():
    parser = argparse.ArgumentParser(description="X0TTA6BL4 MESH NODE")
    parser.add_argument("--mesh-id", default="x0tta6bl4-mesh", help="Mesh Network ID")
    parser.add_argument("--node-id", required=True, help="Unique Node ID")
    parser.add_argument("--obfuscation", 
                        choices=["none", "xor", "faketls", "shadowsocks", "domain_fronting"], 
                        default="none",
                        help="Traffic obfuscation strategy")
    parser.add_argument("--obfuscation-key", default="x0tta6bl4", help="Key for XOR/Shadowsocks")
    parser.add_argument("--traffic-profile",
                        choices=TRAFFIC_PROFILES,
                        default="none",
                        help="Traffic shaping profile to mimic (evades DPI timing analysis)")
    
    args = parser.parse_args()
    
    # 1. Configure Obfuscation
    transport = None
    if args.obfuscation != "none":
        logger.info(f"Initializing obfuscation transport: {args.obfuscation}")
        if args.obfuscation == "xor":
            transport = TransportManager.create("xor", key=args.obfuscation_key)
        elif args.obfuscation == "faketls":
            transport = TransportManager.create("faketls", sni=args.obfuscation_key or "google.com")
        elif args.obfuscation == "shadowsocks":
            transport = TransportManager.create("shadowsocks", password=args.obfuscation_key)
        elif args.obfuscation == "domain_fronting":
            transport = TransportManager.create("domain_fronting", 
                                                front_domain="cdn.cloudflare.com",
                                                backend_host="mesh.example.com")
            
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
        traffic_profile=args.traffic_profile
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

def x_main__mutmut_6():
    parser = argparse.ArgumentParser(description="x0tta6bl4 Mesh Node")
    parser.add_argument(None, default="x0tta6bl4-mesh", help="Mesh Network ID")
    parser.add_argument("--node-id", required=True, help="Unique Node ID")
    parser.add_argument("--obfuscation", 
                        choices=["none", "xor", "faketls", "shadowsocks", "domain_fronting"], 
                        default="none",
                        help="Traffic obfuscation strategy")
    parser.add_argument("--obfuscation-key", default="x0tta6bl4", help="Key for XOR/Shadowsocks")
    parser.add_argument("--traffic-profile",
                        choices=TRAFFIC_PROFILES,
                        default="none",
                        help="Traffic shaping profile to mimic (evades DPI timing analysis)")
    
    args = parser.parse_args()
    
    # 1. Configure Obfuscation
    transport = None
    if args.obfuscation != "none":
        logger.info(f"Initializing obfuscation transport: {args.obfuscation}")
        if args.obfuscation == "xor":
            transport = TransportManager.create("xor", key=args.obfuscation_key)
        elif args.obfuscation == "faketls":
            transport = TransportManager.create("faketls", sni=args.obfuscation_key or "google.com")
        elif args.obfuscation == "shadowsocks":
            transport = TransportManager.create("shadowsocks", password=args.obfuscation_key)
        elif args.obfuscation == "domain_fronting":
            transport = TransportManager.create("domain_fronting", 
                                                front_domain="cdn.cloudflare.com",
                                                backend_host="mesh.example.com")
            
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
        traffic_profile=args.traffic_profile
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

def x_main__mutmut_7():
    parser = argparse.ArgumentParser(description="x0tta6bl4 Mesh Node")
    parser.add_argument("--mesh-id", default=None, help="Mesh Network ID")
    parser.add_argument("--node-id", required=True, help="Unique Node ID")
    parser.add_argument("--obfuscation", 
                        choices=["none", "xor", "faketls", "shadowsocks", "domain_fronting"], 
                        default="none",
                        help="Traffic obfuscation strategy")
    parser.add_argument("--obfuscation-key", default="x0tta6bl4", help="Key for XOR/Shadowsocks")
    parser.add_argument("--traffic-profile",
                        choices=TRAFFIC_PROFILES,
                        default="none",
                        help="Traffic shaping profile to mimic (evades DPI timing analysis)")
    
    args = parser.parse_args()
    
    # 1. Configure Obfuscation
    transport = None
    if args.obfuscation != "none":
        logger.info(f"Initializing obfuscation transport: {args.obfuscation}")
        if args.obfuscation == "xor":
            transport = TransportManager.create("xor", key=args.obfuscation_key)
        elif args.obfuscation == "faketls":
            transport = TransportManager.create("faketls", sni=args.obfuscation_key or "google.com")
        elif args.obfuscation == "shadowsocks":
            transport = TransportManager.create("shadowsocks", password=args.obfuscation_key)
        elif args.obfuscation == "domain_fronting":
            transport = TransportManager.create("domain_fronting", 
                                                front_domain="cdn.cloudflare.com",
                                                backend_host="mesh.example.com")
            
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
        traffic_profile=args.traffic_profile
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

def x_main__mutmut_8():
    parser = argparse.ArgumentParser(description="x0tta6bl4 Mesh Node")
    parser.add_argument("--mesh-id", default="x0tta6bl4-mesh", help=None)
    parser.add_argument("--node-id", required=True, help="Unique Node ID")
    parser.add_argument("--obfuscation", 
                        choices=["none", "xor", "faketls", "shadowsocks", "domain_fronting"], 
                        default="none",
                        help="Traffic obfuscation strategy")
    parser.add_argument("--obfuscation-key", default="x0tta6bl4", help="Key for XOR/Shadowsocks")
    parser.add_argument("--traffic-profile",
                        choices=TRAFFIC_PROFILES,
                        default="none",
                        help="Traffic shaping profile to mimic (evades DPI timing analysis)")
    
    args = parser.parse_args()
    
    # 1. Configure Obfuscation
    transport = None
    if args.obfuscation != "none":
        logger.info(f"Initializing obfuscation transport: {args.obfuscation}")
        if args.obfuscation == "xor":
            transport = TransportManager.create("xor", key=args.obfuscation_key)
        elif args.obfuscation == "faketls":
            transport = TransportManager.create("faketls", sni=args.obfuscation_key or "google.com")
        elif args.obfuscation == "shadowsocks":
            transport = TransportManager.create("shadowsocks", password=args.obfuscation_key)
        elif args.obfuscation == "domain_fronting":
            transport = TransportManager.create("domain_fronting", 
                                                front_domain="cdn.cloudflare.com",
                                                backend_host="mesh.example.com")
            
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
        traffic_profile=args.traffic_profile
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

def x_main__mutmut_9():
    parser = argparse.ArgumentParser(description="x0tta6bl4 Mesh Node")
    parser.add_argument(default="x0tta6bl4-mesh", help="Mesh Network ID")
    parser.add_argument("--node-id", required=True, help="Unique Node ID")
    parser.add_argument("--obfuscation", 
                        choices=["none", "xor", "faketls", "shadowsocks", "domain_fronting"], 
                        default="none",
                        help="Traffic obfuscation strategy")
    parser.add_argument("--obfuscation-key", default="x0tta6bl4", help="Key for XOR/Shadowsocks")
    parser.add_argument("--traffic-profile",
                        choices=TRAFFIC_PROFILES,
                        default="none",
                        help="Traffic shaping profile to mimic (evades DPI timing analysis)")
    
    args = parser.parse_args()
    
    # 1. Configure Obfuscation
    transport = None
    if args.obfuscation != "none":
        logger.info(f"Initializing obfuscation transport: {args.obfuscation}")
        if args.obfuscation == "xor":
            transport = TransportManager.create("xor", key=args.obfuscation_key)
        elif args.obfuscation == "faketls":
            transport = TransportManager.create("faketls", sni=args.obfuscation_key or "google.com")
        elif args.obfuscation == "shadowsocks":
            transport = TransportManager.create("shadowsocks", password=args.obfuscation_key)
        elif args.obfuscation == "domain_fronting":
            transport = TransportManager.create("domain_fronting", 
                                                front_domain="cdn.cloudflare.com",
                                                backend_host="mesh.example.com")
            
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
        traffic_profile=args.traffic_profile
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

def x_main__mutmut_10():
    parser = argparse.ArgumentParser(description="x0tta6bl4 Mesh Node")
    parser.add_argument("--mesh-id", help="Mesh Network ID")
    parser.add_argument("--node-id", required=True, help="Unique Node ID")
    parser.add_argument("--obfuscation", 
                        choices=["none", "xor", "faketls", "shadowsocks", "domain_fronting"], 
                        default="none",
                        help="Traffic obfuscation strategy")
    parser.add_argument("--obfuscation-key", default="x0tta6bl4", help="Key for XOR/Shadowsocks")
    parser.add_argument("--traffic-profile",
                        choices=TRAFFIC_PROFILES,
                        default="none",
                        help="Traffic shaping profile to mimic (evades DPI timing analysis)")
    
    args = parser.parse_args()
    
    # 1. Configure Obfuscation
    transport = None
    if args.obfuscation != "none":
        logger.info(f"Initializing obfuscation transport: {args.obfuscation}")
        if args.obfuscation == "xor":
            transport = TransportManager.create("xor", key=args.obfuscation_key)
        elif args.obfuscation == "faketls":
            transport = TransportManager.create("faketls", sni=args.obfuscation_key or "google.com")
        elif args.obfuscation == "shadowsocks":
            transport = TransportManager.create("shadowsocks", password=args.obfuscation_key)
        elif args.obfuscation == "domain_fronting":
            transport = TransportManager.create("domain_fronting", 
                                                front_domain="cdn.cloudflare.com",
                                                backend_host="mesh.example.com")
            
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
        traffic_profile=args.traffic_profile
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

def x_main__mutmut_11():
    parser = argparse.ArgumentParser(description="x0tta6bl4 Mesh Node")
    parser.add_argument("--mesh-id", default="x0tta6bl4-mesh", )
    parser.add_argument("--node-id", required=True, help="Unique Node ID")
    parser.add_argument("--obfuscation", 
                        choices=["none", "xor", "faketls", "shadowsocks", "domain_fronting"], 
                        default="none",
                        help="Traffic obfuscation strategy")
    parser.add_argument("--obfuscation-key", default="x0tta6bl4", help="Key for XOR/Shadowsocks")
    parser.add_argument("--traffic-profile",
                        choices=TRAFFIC_PROFILES,
                        default="none",
                        help="Traffic shaping profile to mimic (evades DPI timing analysis)")
    
    args = parser.parse_args()
    
    # 1. Configure Obfuscation
    transport = None
    if args.obfuscation != "none":
        logger.info(f"Initializing obfuscation transport: {args.obfuscation}")
        if args.obfuscation == "xor":
            transport = TransportManager.create("xor", key=args.obfuscation_key)
        elif args.obfuscation == "faketls":
            transport = TransportManager.create("faketls", sni=args.obfuscation_key or "google.com")
        elif args.obfuscation == "shadowsocks":
            transport = TransportManager.create("shadowsocks", password=args.obfuscation_key)
        elif args.obfuscation == "domain_fronting":
            transport = TransportManager.create("domain_fronting", 
                                                front_domain="cdn.cloudflare.com",
                                                backend_host="mesh.example.com")
            
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
        traffic_profile=args.traffic_profile
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

def x_main__mutmut_12():
    parser = argparse.ArgumentParser(description="x0tta6bl4 Mesh Node")
    parser.add_argument("XX--mesh-idXX", default="x0tta6bl4-mesh", help="Mesh Network ID")
    parser.add_argument("--node-id", required=True, help="Unique Node ID")
    parser.add_argument("--obfuscation", 
                        choices=["none", "xor", "faketls", "shadowsocks", "domain_fronting"], 
                        default="none",
                        help="Traffic obfuscation strategy")
    parser.add_argument("--obfuscation-key", default="x0tta6bl4", help="Key for XOR/Shadowsocks")
    parser.add_argument("--traffic-profile",
                        choices=TRAFFIC_PROFILES,
                        default="none",
                        help="Traffic shaping profile to mimic (evades DPI timing analysis)")
    
    args = parser.parse_args()
    
    # 1. Configure Obfuscation
    transport = None
    if args.obfuscation != "none":
        logger.info(f"Initializing obfuscation transport: {args.obfuscation}")
        if args.obfuscation == "xor":
            transport = TransportManager.create("xor", key=args.obfuscation_key)
        elif args.obfuscation == "faketls":
            transport = TransportManager.create("faketls", sni=args.obfuscation_key or "google.com")
        elif args.obfuscation == "shadowsocks":
            transport = TransportManager.create("shadowsocks", password=args.obfuscation_key)
        elif args.obfuscation == "domain_fronting":
            transport = TransportManager.create("domain_fronting", 
                                                front_domain="cdn.cloudflare.com",
                                                backend_host="mesh.example.com")
            
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
        traffic_profile=args.traffic_profile
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

def x_main__mutmut_13():
    parser = argparse.ArgumentParser(description="x0tta6bl4 Mesh Node")
    parser.add_argument("--MESH-ID", default="x0tta6bl4-mesh", help="Mesh Network ID")
    parser.add_argument("--node-id", required=True, help="Unique Node ID")
    parser.add_argument("--obfuscation", 
                        choices=["none", "xor", "faketls", "shadowsocks", "domain_fronting"], 
                        default="none",
                        help="Traffic obfuscation strategy")
    parser.add_argument("--obfuscation-key", default="x0tta6bl4", help="Key for XOR/Shadowsocks")
    parser.add_argument("--traffic-profile",
                        choices=TRAFFIC_PROFILES,
                        default="none",
                        help="Traffic shaping profile to mimic (evades DPI timing analysis)")
    
    args = parser.parse_args()
    
    # 1. Configure Obfuscation
    transport = None
    if args.obfuscation != "none":
        logger.info(f"Initializing obfuscation transport: {args.obfuscation}")
        if args.obfuscation == "xor":
            transport = TransportManager.create("xor", key=args.obfuscation_key)
        elif args.obfuscation == "faketls":
            transport = TransportManager.create("faketls", sni=args.obfuscation_key or "google.com")
        elif args.obfuscation == "shadowsocks":
            transport = TransportManager.create("shadowsocks", password=args.obfuscation_key)
        elif args.obfuscation == "domain_fronting":
            transport = TransportManager.create("domain_fronting", 
                                                front_domain="cdn.cloudflare.com",
                                                backend_host="mesh.example.com")
            
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
        traffic_profile=args.traffic_profile
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

def x_main__mutmut_14():
    parser = argparse.ArgumentParser(description="x0tta6bl4 Mesh Node")
    parser.add_argument("--mesh-id", default="XXx0tta6bl4-meshXX", help="Mesh Network ID")
    parser.add_argument("--node-id", required=True, help="Unique Node ID")
    parser.add_argument("--obfuscation", 
                        choices=["none", "xor", "faketls", "shadowsocks", "domain_fronting"], 
                        default="none",
                        help="Traffic obfuscation strategy")
    parser.add_argument("--obfuscation-key", default="x0tta6bl4", help="Key for XOR/Shadowsocks")
    parser.add_argument("--traffic-profile",
                        choices=TRAFFIC_PROFILES,
                        default="none",
                        help="Traffic shaping profile to mimic (evades DPI timing analysis)")
    
    args = parser.parse_args()
    
    # 1. Configure Obfuscation
    transport = None
    if args.obfuscation != "none":
        logger.info(f"Initializing obfuscation transport: {args.obfuscation}")
        if args.obfuscation == "xor":
            transport = TransportManager.create("xor", key=args.obfuscation_key)
        elif args.obfuscation == "faketls":
            transport = TransportManager.create("faketls", sni=args.obfuscation_key or "google.com")
        elif args.obfuscation == "shadowsocks":
            transport = TransportManager.create("shadowsocks", password=args.obfuscation_key)
        elif args.obfuscation == "domain_fronting":
            transport = TransportManager.create("domain_fronting", 
                                                front_domain="cdn.cloudflare.com",
                                                backend_host="mesh.example.com")
            
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
        traffic_profile=args.traffic_profile
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

def x_main__mutmut_15():
    parser = argparse.ArgumentParser(description="x0tta6bl4 Mesh Node")
    parser.add_argument("--mesh-id", default="X0TTA6BL4-MESH", help="Mesh Network ID")
    parser.add_argument("--node-id", required=True, help="Unique Node ID")
    parser.add_argument("--obfuscation", 
                        choices=["none", "xor", "faketls", "shadowsocks", "domain_fronting"], 
                        default="none",
                        help="Traffic obfuscation strategy")
    parser.add_argument("--obfuscation-key", default="x0tta6bl4", help="Key for XOR/Shadowsocks")
    parser.add_argument("--traffic-profile",
                        choices=TRAFFIC_PROFILES,
                        default="none",
                        help="Traffic shaping profile to mimic (evades DPI timing analysis)")
    
    args = parser.parse_args()
    
    # 1. Configure Obfuscation
    transport = None
    if args.obfuscation != "none":
        logger.info(f"Initializing obfuscation transport: {args.obfuscation}")
        if args.obfuscation == "xor":
            transport = TransportManager.create("xor", key=args.obfuscation_key)
        elif args.obfuscation == "faketls":
            transport = TransportManager.create("faketls", sni=args.obfuscation_key or "google.com")
        elif args.obfuscation == "shadowsocks":
            transport = TransportManager.create("shadowsocks", password=args.obfuscation_key)
        elif args.obfuscation == "domain_fronting":
            transport = TransportManager.create("domain_fronting", 
                                                front_domain="cdn.cloudflare.com",
                                                backend_host="mesh.example.com")
            
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
        traffic_profile=args.traffic_profile
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

def x_main__mutmut_16():
    parser = argparse.ArgumentParser(description="x0tta6bl4 Mesh Node")
    parser.add_argument("--mesh-id", default="x0tta6bl4-mesh", help="XXMesh Network IDXX")
    parser.add_argument("--node-id", required=True, help="Unique Node ID")
    parser.add_argument("--obfuscation", 
                        choices=["none", "xor", "faketls", "shadowsocks", "domain_fronting"], 
                        default="none",
                        help="Traffic obfuscation strategy")
    parser.add_argument("--obfuscation-key", default="x0tta6bl4", help="Key for XOR/Shadowsocks")
    parser.add_argument("--traffic-profile",
                        choices=TRAFFIC_PROFILES,
                        default="none",
                        help="Traffic shaping profile to mimic (evades DPI timing analysis)")
    
    args = parser.parse_args()
    
    # 1. Configure Obfuscation
    transport = None
    if args.obfuscation != "none":
        logger.info(f"Initializing obfuscation transport: {args.obfuscation}")
        if args.obfuscation == "xor":
            transport = TransportManager.create("xor", key=args.obfuscation_key)
        elif args.obfuscation == "faketls":
            transport = TransportManager.create("faketls", sni=args.obfuscation_key or "google.com")
        elif args.obfuscation == "shadowsocks":
            transport = TransportManager.create("shadowsocks", password=args.obfuscation_key)
        elif args.obfuscation == "domain_fronting":
            transport = TransportManager.create("domain_fronting", 
                                                front_domain="cdn.cloudflare.com",
                                                backend_host="mesh.example.com")
            
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
        traffic_profile=args.traffic_profile
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

def x_main__mutmut_17():
    parser = argparse.ArgumentParser(description="x0tta6bl4 Mesh Node")
    parser.add_argument("--mesh-id", default="x0tta6bl4-mesh", help="mesh network id")
    parser.add_argument("--node-id", required=True, help="Unique Node ID")
    parser.add_argument("--obfuscation", 
                        choices=["none", "xor", "faketls", "shadowsocks", "domain_fronting"], 
                        default="none",
                        help="Traffic obfuscation strategy")
    parser.add_argument("--obfuscation-key", default="x0tta6bl4", help="Key for XOR/Shadowsocks")
    parser.add_argument("--traffic-profile",
                        choices=TRAFFIC_PROFILES,
                        default="none",
                        help="Traffic shaping profile to mimic (evades DPI timing analysis)")
    
    args = parser.parse_args()
    
    # 1. Configure Obfuscation
    transport = None
    if args.obfuscation != "none":
        logger.info(f"Initializing obfuscation transport: {args.obfuscation}")
        if args.obfuscation == "xor":
            transport = TransportManager.create("xor", key=args.obfuscation_key)
        elif args.obfuscation == "faketls":
            transport = TransportManager.create("faketls", sni=args.obfuscation_key or "google.com")
        elif args.obfuscation == "shadowsocks":
            transport = TransportManager.create("shadowsocks", password=args.obfuscation_key)
        elif args.obfuscation == "domain_fronting":
            transport = TransportManager.create("domain_fronting", 
                                                front_domain="cdn.cloudflare.com",
                                                backend_host="mesh.example.com")
            
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
        traffic_profile=args.traffic_profile
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

def x_main__mutmut_18():
    parser = argparse.ArgumentParser(description="x0tta6bl4 Mesh Node")
    parser.add_argument("--mesh-id", default="x0tta6bl4-mesh", help="MESH NETWORK ID")
    parser.add_argument("--node-id", required=True, help="Unique Node ID")
    parser.add_argument("--obfuscation", 
                        choices=["none", "xor", "faketls", "shadowsocks", "domain_fronting"], 
                        default="none",
                        help="Traffic obfuscation strategy")
    parser.add_argument("--obfuscation-key", default="x0tta6bl4", help="Key for XOR/Shadowsocks")
    parser.add_argument("--traffic-profile",
                        choices=TRAFFIC_PROFILES,
                        default="none",
                        help="Traffic shaping profile to mimic (evades DPI timing analysis)")
    
    args = parser.parse_args()
    
    # 1. Configure Obfuscation
    transport = None
    if args.obfuscation != "none":
        logger.info(f"Initializing obfuscation transport: {args.obfuscation}")
        if args.obfuscation == "xor":
            transport = TransportManager.create("xor", key=args.obfuscation_key)
        elif args.obfuscation == "faketls":
            transport = TransportManager.create("faketls", sni=args.obfuscation_key or "google.com")
        elif args.obfuscation == "shadowsocks":
            transport = TransportManager.create("shadowsocks", password=args.obfuscation_key)
        elif args.obfuscation == "domain_fronting":
            transport = TransportManager.create("domain_fronting", 
                                                front_domain="cdn.cloudflare.com",
                                                backend_host="mesh.example.com")
            
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
        traffic_profile=args.traffic_profile
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

def x_main__mutmut_19():
    parser = argparse.ArgumentParser(description="x0tta6bl4 Mesh Node")
    parser.add_argument("--mesh-id", default="x0tta6bl4-mesh", help="Mesh Network ID")
    parser.add_argument(None, required=True, help="Unique Node ID")
    parser.add_argument("--obfuscation", 
                        choices=["none", "xor", "faketls", "shadowsocks", "domain_fronting"], 
                        default="none",
                        help="Traffic obfuscation strategy")
    parser.add_argument("--obfuscation-key", default="x0tta6bl4", help="Key for XOR/Shadowsocks")
    parser.add_argument("--traffic-profile",
                        choices=TRAFFIC_PROFILES,
                        default="none",
                        help="Traffic shaping profile to mimic (evades DPI timing analysis)")
    
    args = parser.parse_args()
    
    # 1. Configure Obfuscation
    transport = None
    if args.obfuscation != "none":
        logger.info(f"Initializing obfuscation transport: {args.obfuscation}")
        if args.obfuscation == "xor":
            transport = TransportManager.create("xor", key=args.obfuscation_key)
        elif args.obfuscation == "faketls":
            transport = TransportManager.create("faketls", sni=args.obfuscation_key or "google.com")
        elif args.obfuscation == "shadowsocks":
            transport = TransportManager.create("shadowsocks", password=args.obfuscation_key)
        elif args.obfuscation == "domain_fronting":
            transport = TransportManager.create("domain_fronting", 
                                                front_domain="cdn.cloudflare.com",
                                                backend_host="mesh.example.com")
            
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
        traffic_profile=args.traffic_profile
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

def x_main__mutmut_20():
    parser = argparse.ArgumentParser(description="x0tta6bl4 Mesh Node")
    parser.add_argument("--mesh-id", default="x0tta6bl4-mesh", help="Mesh Network ID")
    parser.add_argument("--node-id", required=None, help="Unique Node ID")
    parser.add_argument("--obfuscation", 
                        choices=["none", "xor", "faketls", "shadowsocks", "domain_fronting"], 
                        default="none",
                        help="Traffic obfuscation strategy")
    parser.add_argument("--obfuscation-key", default="x0tta6bl4", help="Key for XOR/Shadowsocks")
    parser.add_argument("--traffic-profile",
                        choices=TRAFFIC_PROFILES,
                        default="none",
                        help="Traffic shaping profile to mimic (evades DPI timing analysis)")
    
    args = parser.parse_args()
    
    # 1. Configure Obfuscation
    transport = None
    if args.obfuscation != "none":
        logger.info(f"Initializing obfuscation transport: {args.obfuscation}")
        if args.obfuscation == "xor":
            transport = TransportManager.create("xor", key=args.obfuscation_key)
        elif args.obfuscation == "faketls":
            transport = TransportManager.create("faketls", sni=args.obfuscation_key or "google.com")
        elif args.obfuscation == "shadowsocks":
            transport = TransportManager.create("shadowsocks", password=args.obfuscation_key)
        elif args.obfuscation == "domain_fronting":
            transport = TransportManager.create("domain_fronting", 
                                                front_domain="cdn.cloudflare.com",
                                                backend_host="mesh.example.com")
            
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
        traffic_profile=args.traffic_profile
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

def x_main__mutmut_21():
    parser = argparse.ArgumentParser(description="x0tta6bl4 Mesh Node")
    parser.add_argument("--mesh-id", default="x0tta6bl4-mesh", help="Mesh Network ID")
    parser.add_argument("--node-id", required=True, help=None)
    parser.add_argument("--obfuscation", 
                        choices=["none", "xor", "faketls", "shadowsocks", "domain_fronting"], 
                        default="none",
                        help="Traffic obfuscation strategy")
    parser.add_argument("--obfuscation-key", default="x0tta6bl4", help="Key for XOR/Shadowsocks")
    parser.add_argument("--traffic-profile",
                        choices=TRAFFIC_PROFILES,
                        default="none",
                        help="Traffic shaping profile to mimic (evades DPI timing analysis)")
    
    args = parser.parse_args()
    
    # 1. Configure Obfuscation
    transport = None
    if args.obfuscation != "none":
        logger.info(f"Initializing obfuscation transport: {args.obfuscation}")
        if args.obfuscation == "xor":
            transport = TransportManager.create("xor", key=args.obfuscation_key)
        elif args.obfuscation == "faketls":
            transport = TransportManager.create("faketls", sni=args.obfuscation_key or "google.com")
        elif args.obfuscation == "shadowsocks":
            transport = TransportManager.create("shadowsocks", password=args.obfuscation_key)
        elif args.obfuscation == "domain_fronting":
            transport = TransportManager.create("domain_fronting", 
                                                front_domain="cdn.cloudflare.com",
                                                backend_host="mesh.example.com")
            
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
        traffic_profile=args.traffic_profile
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

def x_main__mutmut_22():
    parser = argparse.ArgumentParser(description="x0tta6bl4 Mesh Node")
    parser.add_argument("--mesh-id", default="x0tta6bl4-mesh", help="Mesh Network ID")
    parser.add_argument(required=True, help="Unique Node ID")
    parser.add_argument("--obfuscation", 
                        choices=["none", "xor", "faketls", "shadowsocks", "domain_fronting"], 
                        default="none",
                        help="Traffic obfuscation strategy")
    parser.add_argument("--obfuscation-key", default="x0tta6bl4", help="Key for XOR/Shadowsocks")
    parser.add_argument("--traffic-profile",
                        choices=TRAFFIC_PROFILES,
                        default="none",
                        help="Traffic shaping profile to mimic (evades DPI timing analysis)")
    
    args = parser.parse_args()
    
    # 1. Configure Obfuscation
    transport = None
    if args.obfuscation != "none":
        logger.info(f"Initializing obfuscation transport: {args.obfuscation}")
        if args.obfuscation == "xor":
            transport = TransportManager.create("xor", key=args.obfuscation_key)
        elif args.obfuscation == "faketls":
            transport = TransportManager.create("faketls", sni=args.obfuscation_key or "google.com")
        elif args.obfuscation == "shadowsocks":
            transport = TransportManager.create("shadowsocks", password=args.obfuscation_key)
        elif args.obfuscation == "domain_fronting":
            transport = TransportManager.create("domain_fronting", 
                                                front_domain="cdn.cloudflare.com",
                                                backend_host="mesh.example.com")
            
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
        traffic_profile=args.traffic_profile
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

def x_main__mutmut_23():
    parser = argparse.ArgumentParser(description="x0tta6bl4 Mesh Node")
    parser.add_argument("--mesh-id", default="x0tta6bl4-mesh", help="Mesh Network ID")
    parser.add_argument("--node-id", help="Unique Node ID")
    parser.add_argument("--obfuscation", 
                        choices=["none", "xor", "faketls", "shadowsocks", "domain_fronting"], 
                        default="none",
                        help="Traffic obfuscation strategy")
    parser.add_argument("--obfuscation-key", default="x0tta6bl4", help="Key for XOR/Shadowsocks")
    parser.add_argument("--traffic-profile",
                        choices=TRAFFIC_PROFILES,
                        default="none",
                        help="Traffic shaping profile to mimic (evades DPI timing analysis)")
    
    args = parser.parse_args()
    
    # 1. Configure Obfuscation
    transport = None
    if args.obfuscation != "none":
        logger.info(f"Initializing obfuscation transport: {args.obfuscation}")
        if args.obfuscation == "xor":
            transport = TransportManager.create("xor", key=args.obfuscation_key)
        elif args.obfuscation == "faketls":
            transport = TransportManager.create("faketls", sni=args.obfuscation_key or "google.com")
        elif args.obfuscation == "shadowsocks":
            transport = TransportManager.create("shadowsocks", password=args.obfuscation_key)
        elif args.obfuscation == "domain_fronting":
            transport = TransportManager.create("domain_fronting", 
                                                front_domain="cdn.cloudflare.com",
                                                backend_host="mesh.example.com")
            
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
        traffic_profile=args.traffic_profile
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

def x_main__mutmut_24():
    parser = argparse.ArgumentParser(description="x0tta6bl4 Mesh Node")
    parser.add_argument("--mesh-id", default="x0tta6bl4-mesh", help="Mesh Network ID")
    parser.add_argument("--node-id", required=True, )
    parser.add_argument("--obfuscation", 
                        choices=["none", "xor", "faketls", "shadowsocks", "domain_fronting"], 
                        default="none",
                        help="Traffic obfuscation strategy")
    parser.add_argument("--obfuscation-key", default="x0tta6bl4", help="Key for XOR/Shadowsocks")
    parser.add_argument("--traffic-profile",
                        choices=TRAFFIC_PROFILES,
                        default="none",
                        help="Traffic shaping profile to mimic (evades DPI timing analysis)")
    
    args = parser.parse_args()
    
    # 1. Configure Obfuscation
    transport = None
    if args.obfuscation != "none":
        logger.info(f"Initializing obfuscation transport: {args.obfuscation}")
        if args.obfuscation == "xor":
            transport = TransportManager.create("xor", key=args.obfuscation_key)
        elif args.obfuscation == "faketls":
            transport = TransportManager.create("faketls", sni=args.obfuscation_key or "google.com")
        elif args.obfuscation == "shadowsocks":
            transport = TransportManager.create("shadowsocks", password=args.obfuscation_key)
        elif args.obfuscation == "domain_fronting":
            transport = TransportManager.create("domain_fronting", 
                                                front_domain="cdn.cloudflare.com",
                                                backend_host="mesh.example.com")
            
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
        traffic_profile=args.traffic_profile
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

def x_main__mutmut_25():
    parser = argparse.ArgumentParser(description="x0tta6bl4 Mesh Node")
    parser.add_argument("--mesh-id", default="x0tta6bl4-mesh", help="Mesh Network ID")
    parser.add_argument("XX--node-idXX", required=True, help="Unique Node ID")
    parser.add_argument("--obfuscation", 
                        choices=["none", "xor", "faketls", "shadowsocks", "domain_fronting"], 
                        default="none",
                        help="Traffic obfuscation strategy")
    parser.add_argument("--obfuscation-key", default="x0tta6bl4", help="Key for XOR/Shadowsocks")
    parser.add_argument("--traffic-profile",
                        choices=TRAFFIC_PROFILES,
                        default="none",
                        help="Traffic shaping profile to mimic (evades DPI timing analysis)")
    
    args = parser.parse_args()
    
    # 1. Configure Obfuscation
    transport = None
    if args.obfuscation != "none":
        logger.info(f"Initializing obfuscation transport: {args.obfuscation}")
        if args.obfuscation == "xor":
            transport = TransportManager.create("xor", key=args.obfuscation_key)
        elif args.obfuscation == "faketls":
            transport = TransportManager.create("faketls", sni=args.obfuscation_key or "google.com")
        elif args.obfuscation == "shadowsocks":
            transport = TransportManager.create("shadowsocks", password=args.obfuscation_key)
        elif args.obfuscation == "domain_fronting":
            transport = TransportManager.create("domain_fronting", 
                                                front_domain="cdn.cloudflare.com",
                                                backend_host="mesh.example.com")
            
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
        traffic_profile=args.traffic_profile
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

def x_main__mutmut_26():
    parser = argparse.ArgumentParser(description="x0tta6bl4 Mesh Node")
    parser.add_argument("--mesh-id", default="x0tta6bl4-mesh", help="Mesh Network ID")
    parser.add_argument("--NODE-ID", required=True, help="Unique Node ID")
    parser.add_argument("--obfuscation", 
                        choices=["none", "xor", "faketls", "shadowsocks", "domain_fronting"], 
                        default="none",
                        help="Traffic obfuscation strategy")
    parser.add_argument("--obfuscation-key", default="x0tta6bl4", help="Key for XOR/Shadowsocks")
    parser.add_argument("--traffic-profile",
                        choices=TRAFFIC_PROFILES,
                        default="none",
                        help="Traffic shaping profile to mimic (evades DPI timing analysis)")
    
    args = parser.parse_args()
    
    # 1. Configure Obfuscation
    transport = None
    if args.obfuscation != "none":
        logger.info(f"Initializing obfuscation transport: {args.obfuscation}")
        if args.obfuscation == "xor":
            transport = TransportManager.create("xor", key=args.obfuscation_key)
        elif args.obfuscation == "faketls":
            transport = TransportManager.create("faketls", sni=args.obfuscation_key or "google.com")
        elif args.obfuscation == "shadowsocks":
            transport = TransportManager.create("shadowsocks", password=args.obfuscation_key)
        elif args.obfuscation == "domain_fronting":
            transport = TransportManager.create("domain_fronting", 
                                                front_domain="cdn.cloudflare.com",
                                                backend_host="mesh.example.com")
            
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
        traffic_profile=args.traffic_profile
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

def x_main__mutmut_27():
    parser = argparse.ArgumentParser(description="x0tta6bl4 Mesh Node")
    parser.add_argument("--mesh-id", default="x0tta6bl4-mesh", help="Mesh Network ID")
    parser.add_argument("--node-id", required=False, help="Unique Node ID")
    parser.add_argument("--obfuscation", 
                        choices=["none", "xor", "faketls", "shadowsocks", "domain_fronting"], 
                        default="none",
                        help="Traffic obfuscation strategy")
    parser.add_argument("--obfuscation-key", default="x0tta6bl4", help="Key for XOR/Shadowsocks")
    parser.add_argument("--traffic-profile",
                        choices=TRAFFIC_PROFILES,
                        default="none",
                        help="Traffic shaping profile to mimic (evades DPI timing analysis)")
    
    args = parser.parse_args()
    
    # 1. Configure Obfuscation
    transport = None
    if args.obfuscation != "none":
        logger.info(f"Initializing obfuscation transport: {args.obfuscation}")
        if args.obfuscation == "xor":
            transport = TransportManager.create("xor", key=args.obfuscation_key)
        elif args.obfuscation == "faketls":
            transport = TransportManager.create("faketls", sni=args.obfuscation_key or "google.com")
        elif args.obfuscation == "shadowsocks":
            transport = TransportManager.create("shadowsocks", password=args.obfuscation_key)
        elif args.obfuscation == "domain_fronting":
            transport = TransportManager.create("domain_fronting", 
                                                front_domain="cdn.cloudflare.com",
                                                backend_host="mesh.example.com")
            
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
        traffic_profile=args.traffic_profile
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

def x_main__mutmut_28():
    parser = argparse.ArgumentParser(description="x0tta6bl4 Mesh Node")
    parser.add_argument("--mesh-id", default="x0tta6bl4-mesh", help="Mesh Network ID")
    parser.add_argument("--node-id", required=True, help="XXUnique Node IDXX")
    parser.add_argument("--obfuscation", 
                        choices=["none", "xor", "faketls", "shadowsocks", "domain_fronting"], 
                        default="none",
                        help="Traffic obfuscation strategy")
    parser.add_argument("--obfuscation-key", default="x0tta6bl4", help="Key for XOR/Shadowsocks")
    parser.add_argument("--traffic-profile",
                        choices=TRAFFIC_PROFILES,
                        default="none",
                        help="Traffic shaping profile to mimic (evades DPI timing analysis)")
    
    args = parser.parse_args()
    
    # 1. Configure Obfuscation
    transport = None
    if args.obfuscation != "none":
        logger.info(f"Initializing obfuscation transport: {args.obfuscation}")
        if args.obfuscation == "xor":
            transport = TransportManager.create("xor", key=args.obfuscation_key)
        elif args.obfuscation == "faketls":
            transport = TransportManager.create("faketls", sni=args.obfuscation_key or "google.com")
        elif args.obfuscation == "shadowsocks":
            transport = TransportManager.create("shadowsocks", password=args.obfuscation_key)
        elif args.obfuscation == "domain_fronting":
            transport = TransportManager.create("domain_fronting", 
                                                front_domain="cdn.cloudflare.com",
                                                backend_host="mesh.example.com")
            
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
        traffic_profile=args.traffic_profile
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

def x_main__mutmut_29():
    parser = argparse.ArgumentParser(description="x0tta6bl4 Mesh Node")
    parser.add_argument("--mesh-id", default="x0tta6bl4-mesh", help="Mesh Network ID")
    parser.add_argument("--node-id", required=True, help="unique node id")
    parser.add_argument("--obfuscation", 
                        choices=["none", "xor", "faketls", "shadowsocks", "domain_fronting"], 
                        default="none",
                        help="Traffic obfuscation strategy")
    parser.add_argument("--obfuscation-key", default="x0tta6bl4", help="Key for XOR/Shadowsocks")
    parser.add_argument("--traffic-profile",
                        choices=TRAFFIC_PROFILES,
                        default="none",
                        help="Traffic shaping profile to mimic (evades DPI timing analysis)")
    
    args = parser.parse_args()
    
    # 1. Configure Obfuscation
    transport = None
    if args.obfuscation != "none":
        logger.info(f"Initializing obfuscation transport: {args.obfuscation}")
        if args.obfuscation == "xor":
            transport = TransportManager.create("xor", key=args.obfuscation_key)
        elif args.obfuscation == "faketls":
            transport = TransportManager.create("faketls", sni=args.obfuscation_key or "google.com")
        elif args.obfuscation == "shadowsocks":
            transport = TransportManager.create("shadowsocks", password=args.obfuscation_key)
        elif args.obfuscation == "domain_fronting":
            transport = TransportManager.create("domain_fronting", 
                                                front_domain="cdn.cloudflare.com",
                                                backend_host="mesh.example.com")
            
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
        traffic_profile=args.traffic_profile
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

def x_main__mutmut_30():
    parser = argparse.ArgumentParser(description="x0tta6bl4 Mesh Node")
    parser.add_argument("--mesh-id", default="x0tta6bl4-mesh", help="Mesh Network ID")
    parser.add_argument("--node-id", required=True, help="UNIQUE NODE ID")
    parser.add_argument("--obfuscation", 
                        choices=["none", "xor", "faketls", "shadowsocks", "domain_fronting"], 
                        default="none",
                        help="Traffic obfuscation strategy")
    parser.add_argument("--obfuscation-key", default="x0tta6bl4", help="Key for XOR/Shadowsocks")
    parser.add_argument("--traffic-profile",
                        choices=TRAFFIC_PROFILES,
                        default="none",
                        help="Traffic shaping profile to mimic (evades DPI timing analysis)")
    
    args = parser.parse_args()
    
    # 1. Configure Obfuscation
    transport = None
    if args.obfuscation != "none":
        logger.info(f"Initializing obfuscation transport: {args.obfuscation}")
        if args.obfuscation == "xor":
            transport = TransportManager.create("xor", key=args.obfuscation_key)
        elif args.obfuscation == "faketls":
            transport = TransportManager.create("faketls", sni=args.obfuscation_key or "google.com")
        elif args.obfuscation == "shadowsocks":
            transport = TransportManager.create("shadowsocks", password=args.obfuscation_key)
        elif args.obfuscation == "domain_fronting":
            transport = TransportManager.create("domain_fronting", 
                                                front_domain="cdn.cloudflare.com",
                                                backend_host="mesh.example.com")
            
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
        traffic_profile=args.traffic_profile
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

def x_main__mutmut_31():
    parser = argparse.ArgumentParser(description="x0tta6bl4 Mesh Node")
    parser.add_argument("--mesh-id", default="x0tta6bl4-mesh", help="Mesh Network ID")
    parser.add_argument("--node-id", required=True, help="Unique Node ID")
    parser.add_argument(None, 
                        choices=["none", "xor", "faketls", "shadowsocks", "domain_fronting"], 
                        default="none",
                        help="Traffic obfuscation strategy")
    parser.add_argument("--obfuscation-key", default="x0tta6bl4", help="Key for XOR/Shadowsocks")
    parser.add_argument("--traffic-profile",
                        choices=TRAFFIC_PROFILES,
                        default="none",
                        help="Traffic shaping profile to mimic (evades DPI timing analysis)")
    
    args = parser.parse_args()
    
    # 1. Configure Obfuscation
    transport = None
    if args.obfuscation != "none":
        logger.info(f"Initializing obfuscation transport: {args.obfuscation}")
        if args.obfuscation == "xor":
            transport = TransportManager.create("xor", key=args.obfuscation_key)
        elif args.obfuscation == "faketls":
            transport = TransportManager.create("faketls", sni=args.obfuscation_key or "google.com")
        elif args.obfuscation == "shadowsocks":
            transport = TransportManager.create("shadowsocks", password=args.obfuscation_key)
        elif args.obfuscation == "domain_fronting":
            transport = TransportManager.create("domain_fronting", 
                                                front_domain="cdn.cloudflare.com",
                                                backend_host="mesh.example.com")
            
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
        traffic_profile=args.traffic_profile
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

def x_main__mutmut_32():
    parser = argparse.ArgumentParser(description="x0tta6bl4 Mesh Node")
    parser.add_argument("--mesh-id", default="x0tta6bl4-mesh", help="Mesh Network ID")
    parser.add_argument("--node-id", required=True, help="Unique Node ID")
    parser.add_argument("--obfuscation", 
                        choices=None, 
                        default="none",
                        help="Traffic obfuscation strategy")
    parser.add_argument("--obfuscation-key", default="x0tta6bl4", help="Key for XOR/Shadowsocks")
    parser.add_argument("--traffic-profile",
                        choices=TRAFFIC_PROFILES,
                        default="none",
                        help="Traffic shaping profile to mimic (evades DPI timing analysis)")
    
    args = parser.parse_args()
    
    # 1. Configure Obfuscation
    transport = None
    if args.obfuscation != "none":
        logger.info(f"Initializing obfuscation transport: {args.obfuscation}")
        if args.obfuscation == "xor":
            transport = TransportManager.create("xor", key=args.obfuscation_key)
        elif args.obfuscation == "faketls":
            transport = TransportManager.create("faketls", sni=args.obfuscation_key or "google.com")
        elif args.obfuscation == "shadowsocks":
            transport = TransportManager.create("shadowsocks", password=args.obfuscation_key)
        elif args.obfuscation == "domain_fronting":
            transport = TransportManager.create("domain_fronting", 
                                                front_domain="cdn.cloudflare.com",
                                                backend_host="mesh.example.com")
            
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
        traffic_profile=args.traffic_profile
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

def x_main__mutmut_33():
    parser = argparse.ArgumentParser(description="x0tta6bl4 Mesh Node")
    parser.add_argument("--mesh-id", default="x0tta6bl4-mesh", help="Mesh Network ID")
    parser.add_argument("--node-id", required=True, help="Unique Node ID")
    parser.add_argument("--obfuscation", 
                        choices=["none", "xor", "faketls", "shadowsocks", "domain_fronting"], 
                        default=None,
                        help="Traffic obfuscation strategy")
    parser.add_argument("--obfuscation-key", default="x0tta6bl4", help="Key for XOR/Shadowsocks")
    parser.add_argument("--traffic-profile",
                        choices=TRAFFIC_PROFILES,
                        default="none",
                        help="Traffic shaping profile to mimic (evades DPI timing analysis)")
    
    args = parser.parse_args()
    
    # 1. Configure Obfuscation
    transport = None
    if args.obfuscation != "none":
        logger.info(f"Initializing obfuscation transport: {args.obfuscation}")
        if args.obfuscation == "xor":
            transport = TransportManager.create("xor", key=args.obfuscation_key)
        elif args.obfuscation == "faketls":
            transport = TransportManager.create("faketls", sni=args.obfuscation_key or "google.com")
        elif args.obfuscation == "shadowsocks":
            transport = TransportManager.create("shadowsocks", password=args.obfuscation_key)
        elif args.obfuscation == "domain_fronting":
            transport = TransportManager.create("domain_fronting", 
                                                front_domain="cdn.cloudflare.com",
                                                backend_host="mesh.example.com")
            
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
        traffic_profile=args.traffic_profile
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

def x_main__mutmut_34():
    parser = argparse.ArgumentParser(description="x0tta6bl4 Mesh Node")
    parser.add_argument("--mesh-id", default="x0tta6bl4-mesh", help="Mesh Network ID")
    parser.add_argument("--node-id", required=True, help="Unique Node ID")
    parser.add_argument("--obfuscation", 
                        choices=["none", "xor", "faketls", "shadowsocks", "domain_fronting"], 
                        default="none",
                        help=None)
    parser.add_argument("--obfuscation-key", default="x0tta6bl4", help="Key for XOR/Shadowsocks")
    parser.add_argument("--traffic-profile",
                        choices=TRAFFIC_PROFILES,
                        default="none",
                        help="Traffic shaping profile to mimic (evades DPI timing analysis)")
    
    args = parser.parse_args()
    
    # 1. Configure Obfuscation
    transport = None
    if args.obfuscation != "none":
        logger.info(f"Initializing obfuscation transport: {args.obfuscation}")
        if args.obfuscation == "xor":
            transport = TransportManager.create("xor", key=args.obfuscation_key)
        elif args.obfuscation == "faketls":
            transport = TransportManager.create("faketls", sni=args.obfuscation_key or "google.com")
        elif args.obfuscation == "shadowsocks":
            transport = TransportManager.create("shadowsocks", password=args.obfuscation_key)
        elif args.obfuscation == "domain_fronting":
            transport = TransportManager.create("domain_fronting", 
                                                front_domain="cdn.cloudflare.com",
                                                backend_host="mesh.example.com")
            
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
        traffic_profile=args.traffic_profile
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

def x_main__mutmut_35():
    parser = argparse.ArgumentParser(description="x0tta6bl4 Mesh Node")
    parser.add_argument("--mesh-id", default="x0tta6bl4-mesh", help="Mesh Network ID")
    parser.add_argument("--node-id", required=True, help="Unique Node ID")
    parser.add_argument(choices=["none", "xor", "faketls", "shadowsocks", "domain_fronting"], 
                        default="none",
                        help="Traffic obfuscation strategy")
    parser.add_argument("--obfuscation-key", default="x0tta6bl4", help="Key for XOR/Shadowsocks")
    parser.add_argument("--traffic-profile",
                        choices=TRAFFIC_PROFILES,
                        default="none",
                        help="Traffic shaping profile to mimic (evades DPI timing analysis)")
    
    args = parser.parse_args()
    
    # 1. Configure Obfuscation
    transport = None
    if args.obfuscation != "none":
        logger.info(f"Initializing obfuscation transport: {args.obfuscation}")
        if args.obfuscation == "xor":
            transport = TransportManager.create("xor", key=args.obfuscation_key)
        elif args.obfuscation == "faketls":
            transport = TransportManager.create("faketls", sni=args.obfuscation_key or "google.com")
        elif args.obfuscation == "shadowsocks":
            transport = TransportManager.create("shadowsocks", password=args.obfuscation_key)
        elif args.obfuscation == "domain_fronting":
            transport = TransportManager.create("domain_fronting", 
                                                front_domain="cdn.cloudflare.com",
                                                backend_host="mesh.example.com")
            
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
        traffic_profile=args.traffic_profile
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

def x_main__mutmut_36():
    parser = argparse.ArgumentParser(description="x0tta6bl4 Mesh Node")
    parser.add_argument("--mesh-id", default="x0tta6bl4-mesh", help="Mesh Network ID")
    parser.add_argument("--node-id", required=True, help="Unique Node ID")
    parser.add_argument("--obfuscation", 
                        default="none",
                        help="Traffic obfuscation strategy")
    parser.add_argument("--obfuscation-key", default="x0tta6bl4", help="Key for XOR/Shadowsocks")
    parser.add_argument("--traffic-profile",
                        choices=TRAFFIC_PROFILES,
                        default="none",
                        help="Traffic shaping profile to mimic (evades DPI timing analysis)")
    
    args = parser.parse_args()
    
    # 1. Configure Obfuscation
    transport = None
    if args.obfuscation != "none":
        logger.info(f"Initializing obfuscation transport: {args.obfuscation}")
        if args.obfuscation == "xor":
            transport = TransportManager.create("xor", key=args.obfuscation_key)
        elif args.obfuscation == "faketls":
            transport = TransportManager.create("faketls", sni=args.obfuscation_key or "google.com")
        elif args.obfuscation == "shadowsocks":
            transport = TransportManager.create("shadowsocks", password=args.obfuscation_key)
        elif args.obfuscation == "domain_fronting":
            transport = TransportManager.create("domain_fronting", 
                                                front_domain="cdn.cloudflare.com",
                                                backend_host="mesh.example.com")
            
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
        traffic_profile=args.traffic_profile
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

def x_main__mutmut_37():
    parser = argparse.ArgumentParser(description="x0tta6bl4 Mesh Node")
    parser.add_argument("--mesh-id", default="x0tta6bl4-mesh", help="Mesh Network ID")
    parser.add_argument("--node-id", required=True, help="Unique Node ID")
    parser.add_argument("--obfuscation", 
                        choices=["none", "xor", "faketls", "shadowsocks", "domain_fronting"], 
                        help="Traffic obfuscation strategy")
    parser.add_argument("--obfuscation-key", default="x0tta6bl4", help="Key for XOR/Shadowsocks")
    parser.add_argument("--traffic-profile",
                        choices=TRAFFIC_PROFILES,
                        default="none",
                        help="Traffic shaping profile to mimic (evades DPI timing analysis)")
    
    args = parser.parse_args()
    
    # 1. Configure Obfuscation
    transport = None
    if args.obfuscation != "none":
        logger.info(f"Initializing obfuscation transport: {args.obfuscation}")
        if args.obfuscation == "xor":
            transport = TransportManager.create("xor", key=args.obfuscation_key)
        elif args.obfuscation == "faketls":
            transport = TransportManager.create("faketls", sni=args.obfuscation_key or "google.com")
        elif args.obfuscation == "shadowsocks":
            transport = TransportManager.create("shadowsocks", password=args.obfuscation_key)
        elif args.obfuscation == "domain_fronting":
            transport = TransportManager.create("domain_fronting", 
                                                front_domain="cdn.cloudflare.com",
                                                backend_host="mesh.example.com")
            
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
        traffic_profile=args.traffic_profile
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

def x_main__mutmut_38():
    parser = argparse.ArgumentParser(description="x0tta6bl4 Mesh Node")
    parser.add_argument("--mesh-id", default="x0tta6bl4-mesh", help="Mesh Network ID")
    parser.add_argument("--node-id", required=True, help="Unique Node ID")
    parser.add_argument("--obfuscation", 
                        choices=["none", "xor", "faketls", "shadowsocks", "domain_fronting"], 
                        default="none",
                        )
    parser.add_argument("--obfuscation-key", default="x0tta6bl4", help="Key for XOR/Shadowsocks")
    parser.add_argument("--traffic-profile",
                        choices=TRAFFIC_PROFILES,
                        default="none",
                        help="Traffic shaping profile to mimic (evades DPI timing analysis)")
    
    args = parser.parse_args()
    
    # 1. Configure Obfuscation
    transport = None
    if args.obfuscation != "none":
        logger.info(f"Initializing obfuscation transport: {args.obfuscation}")
        if args.obfuscation == "xor":
            transport = TransportManager.create("xor", key=args.obfuscation_key)
        elif args.obfuscation == "faketls":
            transport = TransportManager.create("faketls", sni=args.obfuscation_key or "google.com")
        elif args.obfuscation == "shadowsocks":
            transport = TransportManager.create("shadowsocks", password=args.obfuscation_key)
        elif args.obfuscation == "domain_fronting":
            transport = TransportManager.create("domain_fronting", 
                                                front_domain="cdn.cloudflare.com",
                                                backend_host="mesh.example.com")
            
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
        traffic_profile=args.traffic_profile
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

def x_main__mutmut_39():
    parser = argparse.ArgumentParser(description="x0tta6bl4 Mesh Node")
    parser.add_argument("--mesh-id", default="x0tta6bl4-mesh", help="Mesh Network ID")
    parser.add_argument("--node-id", required=True, help="Unique Node ID")
    parser.add_argument("XX--obfuscationXX", 
                        choices=["none", "xor", "faketls", "shadowsocks", "domain_fronting"], 
                        default="none",
                        help="Traffic obfuscation strategy")
    parser.add_argument("--obfuscation-key", default="x0tta6bl4", help="Key for XOR/Shadowsocks")
    parser.add_argument("--traffic-profile",
                        choices=TRAFFIC_PROFILES,
                        default="none",
                        help="Traffic shaping profile to mimic (evades DPI timing analysis)")
    
    args = parser.parse_args()
    
    # 1. Configure Obfuscation
    transport = None
    if args.obfuscation != "none":
        logger.info(f"Initializing obfuscation transport: {args.obfuscation}")
        if args.obfuscation == "xor":
            transport = TransportManager.create("xor", key=args.obfuscation_key)
        elif args.obfuscation == "faketls":
            transport = TransportManager.create("faketls", sni=args.obfuscation_key or "google.com")
        elif args.obfuscation == "shadowsocks":
            transport = TransportManager.create("shadowsocks", password=args.obfuscation_key)
        elif args.obfuscation == "domain_fronting":
            transport = TransportManager.create("domain_fronting", 
                                                front_domain="cdn.cloudflare.com",
                                                backend_host="mesh.example.com")
            
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
        traffic_profile=args.traffic_profile
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

def x_main__mutmut_40():
    parser = argparse.ArgumentParser(description="x0tta6bl4 Mesh Node")
    parser.add_argument("--mesh-id", default="x0tta6bl4-mesh", help="Mesh Network ID")
    parser.add_argument("--node-id", required=True, help="Unique Node ID")
    parser.add_argument("--OBFUSCATION", 
                        choices=["none", "xor", "faketls", "shadowsocks", "domain_fronting"], 
                        default="none",
                        help="Traffic obfuscation strategy")
    parser.add_argument("--obfuscation-key", default="x0tta6bl4", help="Key for XOR/Shadowsocks")
    parser.add_argument("--traffic-profile",
                        choices=TRAFFIC_PROFILES,
                        default="none",
                        help="Traffic shaping profile to mimic (evades DPI timing analysis)")
    
    args = parser.parse_args()
    
    # 1. Configure Obfuscation
    transport = None
    if args.obfuscation != "none":
        logger.info(f"Initializing obfuscation transport: {args.obfuscation}")
        if args.obfuscation == "xor":
            transport = TransportManager.create("xor", key=args.obfuscation_key)
        elif args.obfuscation == "faketls":
            transport = TransportManager.create("faketls", sni=args.obfuscation_key or "google.com")
        elif args.obfuscation == "shadowsocks":
            transport = TransportManager.create("shadowsocks", password=args.obfuscation_key)
        elif args.obfuscation == "domain_fronting":
            transport = TransportManager.create("domain_fronting", 
                                                front_domain="cdn.cloudflare.com",
                                                backend_host="mesh.example.com")
            
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
        traffic_profile=args.traffic_profile
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

def x_main__mutmut_41():
    parser = argparse.ArgumentParser(description="x0tta6bl4 Mesh Node")
    parser.add_argument("--mesh-id", default="x0tta6bl4-mesh", help="Mesh Network ID")
    parser.add_argument("--node-id", required=True, help="Unique Node ID")
    parser.add_argument("--obfuscation", 
                        choices=["XXnoneXX", "xor", "faketls", "shadowsocks", "domain_fronting"], 
                        default="none",
                        help="Traffic obfuscation strategy")
    parser.add_argument("--obfuscation-key", default="x0tta6bl4", help="Key for XOR/Shadowsocks")
    parser.add_argument("--traffic-profile",
                        choices=TRAFFIC_PROFILES,
                        default="none",
                        help="Traffic shaping profile to mimic (evades DPI timing analysis)")
    
    args = parser.parse_args()
    
    # 1. Configure Obfuscation
    transport = None
    if args.obfuscation != "none":
        logger.info(f"Initializing obfuscation transport: {args.obfuscation}")
        if args.obfuscation == "xor":
            transport = TransportManager.create("xor", key=args.obfuscation_key)
        elif args.obfuscation == "faketls":
            transport = TransportManager.create("faketls", sni=args.obfuscation_key or "google.com")
        elif args.obfuscation == "shadowsocks":
            transport = TransportManager.create("shadowsocks", password=args.obfuscation_key)
        elif args.obfuscation == "domain_fronting":
            transport = TransportManager.create("domain_fronting", 
                                                front_domain="cdn.cloudflare.com",
                                                backend_host="mesh.example.com")
            
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
        traffic_profile=args.traffic_profile
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

def x_main__mutmut_42():
    parser = argparse.ArgumentParser(description="x0tta6bl4 Mesh Node")
    parser.add_argument("--mesh-id", default="x0tta6bl4-mesh", help="Mesh Network ID")
    parser.add_argument("--node-id", required=True, help="Unique Node ID")
    parser.add_argument("--obfuscation", 
                        choices=["NONE", "xor", "faketls", "shadowsocks", "domain_fronting"], 
                        default="none",
                        help="Traffic obfuscation strategy")
    parser.add_argument("--obfuscation-key", default="x0tta6bl4", help="Key for XOR/Shadowsocks")
    parser.add_argument("--traffic-profile",
                        choices=TRAFFIC_PROFILES,
                        default="none",
                        help="Traffic shaping profile to mimic (evades DPI timing analysis)")
    
    args = parser.parse_args()
    
    # 1. Configure Obfuscation
    transport = None
    if args.obfuscation != "none":
        logger.info(f"Initializing obfuscation transport: {args.obfuscation}")
        if args.obfuscation == "xor":
            transport = TransportManager.create("xor", key=args.obfuscation_key)
        elif args.obfuscation == "faketls":
            transport = TransportManager.create("faketls", sni=args.obfuscation_key or "google.com")
        elif args.obfuscation == "shadowsocks":
            transport = TransportManager.create("shadowsocks", password=args.obfuscation_key)
        elif args.obfuscation == "domain_fronting":
            transport = TransportManager.create("domain_fronting", 
                                                front_domain="cdn.cloudflare.com",
                                                backend_host="mesh.example.com")
            
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
        traffic_profile=args.traffic_profile
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

def x_main__mutmut_43():
    parser = argparse.ArgumentParser(description="x0tta6bl4 Mesh Node")
    parser.add_argument("--mesh-id", default="x0tta6bl4-mesh", help="Mesh Network ID")
    parser.add_argument("--node-id", required=True, help="Unique Node ID")
    parser.add_argument("--obfuscation", 
                        choices=["none", "XXxorXX", "faketls", "shadowsocks", "domain_fronting"], 
                        default="none",
                        help="Traffic obfuscation strategy")
    parser.add_argument("--obfuscation-key", default="x0tta6bl4", help="Key for XOR/Shadowsocks")
    parser.add_argument("--traffic-profile",
                        choices=TRAFFIC_PROFILES,
                        default="none",
                        help="Traffic shaping profile to mimic (evades DPI timing analysis)")
    
    args = parser.parse_args()
    
    # 1. Configure Obfuscation
    transport = None
    if args.obfuscation != "none":
        logger.info(f"Initializing obfuscation transport: {args.obfuscation}")
        if args.obfuscation == "xor":
            transport = TransportManager.create("xor", key=args.obfuscation_key)
        elif args.obfuscation == "faketls":
            transport = TransportManager.create("faketls", sni=args.obfuscation_key or "google.com")
        elif args.obfuscation == "shadowsocks":
            transport = TransportManager.create("shadowsocks", password=args.obfuscation_key)
        elif args.obfuscation == "domain_fronting":
            transport = TransportManager.create("domain_fronting", 
                                                front_domain="cdn.cloudflare.com",
                                                backend_host="mesh.example.com")
            
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
        traffic_profile=args.traffic_profile
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

def x_main__mutmut_44():
    parser = argparse.ArgumentParser(description="x0tta6bl4 Mesh Node")
    parser.add_argument("--mesh-id", default="x0tta6bl4-mesh", help="Mesh Network ID")
    parser.add_argument("--node-id", required=True, help="Unique Node ID")
    parser.add_argument("--obfuscation", 
                        choices=["none", "XOR", "faketls", "shadowsocks", "domain_fronting"], 
                        default="none",
                        help="Traffic obfuscation strategy")
    parser.add_argument("--obfuscation-key", default="x0tta6bl4", help="Key for XOR/Shadowsocks")
    parser.add_argument("--traffic-profile",
                        choices=TRAFFIC_PROFILES,
                        default="none",
                        help="Traffic shaping profile to mimic (evades DPI timing analysis)")
    
    args = parser.parse_args()
    
    # 1. Configure Obfuscation
    transport = None
    if args.obfuscation != "none":
        logger.info(f"Initializing obfuscation transport: {args.obfuscation}")
        if args.obfuscation == "xor":
            transport = TransportManager.create("xor", key=args.obfuscation_key)
        elif args.obfuscation == "faketls":
            transport = TransportManager.create("faketls", sni=args.obfuscation_key or "google.com")
        elif args.obfuscation == "shadowsocks":
            transport = TransportManager.create("shadowsocks", password=args.obfuscation_key)
        elif args.obfuscation == "domain_fronting":
            transport = TransportManager.create("domain_fronting", 
                                                front_domain="cdn.cloudflare.com",
                                                backend_host="mesh.example.com")
            
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
        traffic_profile=args.traffic_profile
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

def x_main__mutmut_45():
    parser = argparse.ArgumentParser(description="x0tta6bl4 Mesh Node")
    parser.add_argument("--mesh-id", default="x0tta6bl4-mesh", help="Mesh Network ID")
    parser.add_argument("--node-id", required=True, help="Unique Node ID")
    parser.add_argument("--obfuscation", 
                        choices=["none", "xor", "XXfaketlsXX", "shadowsocks", "domain_fronting"], 
                        default="none",
                        help="Traffic obfuscation strategy")
    parser.add_argument("--obfuscation-key", default="x0tta6bl4", help="Key for XOR/Shadowsocks")
    parser.add_argument("--traffic-profile",
                        choices=TRAFFIC_PROFILES,
                        default="none",
                        help="Traffic shaping profile to mimic (evades DPI timing analysis)")
    
    args = parser.parse_args()
    
    # 1. Configure Obfuscation
    transport = None
    if args.obfuscation != "none":
        logger.info(f"Initializing obfuscation transport: {args.obfuscation}")
        if args.obfuscation == "xor":
            transport = TransportManager.create("xor", key=args.obfuscation_key)
        elif args.obfuscation == "faketls":
            transport = TransportManager.create("faketls", sni=args.obfuscation_key or "google.com")
        elif args.obfuscation == "shadowsocks":
            transport = TransportManager.create("shadowsocks", password=args.obfuscation_key)
        elif args.obfuscation == "domain_fronting":
            transport = TransportManager.create("domain_fronting", 
                                                front_domain="cdn.cloudflare.com",
                                                backend_host="mesh.example.com")
            
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
        traffic_profile=args.traffic_profile
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

def x_main__mutmut_46():
    parser = argparse.ArgumentParser(description="x0tta6bl4 Mesh Node")
    parser.add_argument("--mesh-id", default="x0tta6bl4-mesh", help="Mesh Network ID")
    parser.add_argument("--node-id", required=True, help="Unique Node ID")
    parser.add_argument("--obfuscation", 
                        choices=["none", "xor", "FAKETLS", "shadowsocks", "domain_fronting"], 
                        default="none",
                        help="Traffic obfuscation strategy")
    parser.add_argument("--obfuscation-key", default="x0tta6bl4", help="Key for XOR/Shadowsocks")
    parser.add_argument("--traffic-profile",
                        choices=TRAFFIC_PROFILES,
                        default="none",
                        help="Traffic shaping profile to mimic (evades DPI timing analysis)")
    
    args = parser.parse_args()
    
    # 1. Configure Obfuscation
    transport = None
    if args.obfuscation != "none":
        logger.info(f"Initializing obfuscation transport: {args.obfuscation}")
        if args.obfuscation == "xor":
            transport = TransportManager.create("xor", key=args.obfuscation_key)
        elif args.obfuscation == "faketls":
            transport = TransportManager.create("faketls", sni=args.obfuscation_key or "google.com")
        elif args.obfuscation == "shadowsocks":
            transport = TransportManager.create("shadowsocks", password=args.obfuscation_key)
        elif args.obfuscation == "domain_fronting":
            transport = TransportManager.create("domain_fronting", 
                                                front_domain="cdn.cloudflare.com",
                                                backend_host="mesh.example.com")
            
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
        traffic_profile=args.traffic_profile
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

def x_main__mutmut_47():
    parser = argparse.ArgumentParser(description="x0tta6bl4 Mesh Node")
    parser.add_argument("--mesh-id", default="x0tta6bl4-mesh", help="Mesh Network ID")
    parser.add_argument("--node-id", required=True, help="Unique Node ID")
    parser.add_argument("--obfuscation", 
                        choices=["none", "xor", "faketls", "XXshadowsocksXX", "domain_fronting"], 
                        default="none",
                        help="Traffic obfuscation strategy")
    parser.add_argument("--obfuscation-key", default="x0tta6bl4", help="Key for XOR/Shadowsocks")
    parser.add_argument("--traffic-profile",
                        choices=TRAFFIC_PROFILES,
                        default="none",
                        help="Traffic shaping profile to mimic (evades DPI timing analysis)")
    
    args = parser.parse_args()
    
    # 1. Configure Obfuscation
    transport = None
    if args.obfuscation != "none":
        logger.info(f"Initializing obfuscation transport: {args.obfuscation}")
        if args.obfuscation == "xor":
            transport = TransportManager.create("xor", key=args.obfuscation_key)
        elif args.obfuscation == "faketls":
            transport = TransportManager.create("faketls", sni=args.obfuscation_key or "google.com")
        elif args.obfuscation == "shadowsocks":
            transport = TransportManager.create("shadowsocks", password=args.obfuscation_key)
        elif args.obfuscation == "domain_fronting":
            transport = TransportManager.create("domain_fronting", 
                                                front_domain="cdn.cloudflare.com",
                                                backend_host="mesh.example.com")
            
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
        traffic_profile=args.traffic_profile
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

def x_main__mutmut_48():
    parser = argparse.ArgumentParser(description="x0tta6bl4 Mesh Node")
    parser.add_argument("--mesh-id", default="x0tta6bl4-mesh", help="Mesh Network ID")
    parser.add_argument("--node-id", required=True, help="Unique Node ID")
    parser.add_argument("--obfuscation", 
                        choices=["none", "xor", "faketls", "SHADOWSOCKS", "domain_fronting"], 
                        default="none",
                        help="Traffic obfuscation strategy")
    parser.add_argument("--obfuscation-key", default="x0tta6bl4", help="Key for XOR/Shadowsocks")
    parser.add_argument("--traffic-profile",
                        choices=TRAFFIC_PROFILES,
                        default="none",
                        help="Traffic shaping profile to mimic (evades DPI timing analysis)")
    
    args = parser.parse_args()
    
    # 1. Configure Obfuscation
    transport = None
    if args.obfuscation != "none":
        logger.info(f"Initializing obfuscation transport: {args.obfuscation}")
        if args.obfuscation == "xor":
            transport = TransportManager.create("xor", key=args.obfuscation_key)
        elif args.obfuscation == "faketls":
            transport = TransportManager.create("faketls", sni=args.obfuscation_key or "google.com")
        elif args.obfuscation == "shadowsocks":
            transport = TransportManager.create("shadowsocks", password=args.obfuscation_key)
        elif args.obfuscation == "domain_fronting":
            transport = TransportManager.create("domain_fronting", 
                                                front_domain="cdn.cloudflare.com",
                                                backend_host="mesh.example.com")
            
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
        traffic_profile=args.traffic_profile
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

def x_main__mutmut_49():
    parser = argparse.ArgumentParser(description="x0tta6bl4 Mesh Node")
    parser.add_argument("--mesh-id", default="x0tta6bl4-mesh", help="Mesh Network ID")
    parser.add_argument("--node-id", required=True, help="Unique Node ID")
    parser.add_argument("--obfuscation", 
                        choices=["none", "xor", "faketls", "shadowsocks", "XXdomain_frontingXX"], 
                        default="none",
                        help="Traffic obfuscation strategy")
    parser.add_argument("--obfuscation-key", default="x0tta6bl4", help="Key for XOR/Shadowsocks")
    parser.add_argument("--traffic-profile",
                        choices=TRAFFIC_PROFILES,
                        default="none",
                        help="Traffic shaping profile to mimic (evades DPI timing analysis)")
    
    args = parser.parse_args()
    
    # 1. Configure Obfuscation
    transport = None
    if args.obfuscation != "none":
        logger.info(f"Initializing obfuscation transport: {args.obfuscation}")
        if args.obfuscation == "xor":
            transport = TransportManager.create("xor", key=args.obfuscation_key)
        elif args.obfuscation == "faketls":
            transport = TransportManager.create("faketls", sni=args.obfuscation_key or "google.com")
        elif args.obfuscation == "shadowsocks":
            transport = TransportManager.create("shadowsocks", password=args.obfuscation_key)
        elif args.obfuscation == "domain_fronting":
            transport = TransportManager.create("domain_fronting", 
                                                front_domain="cdn.cloudflare.com",
                                                backend_host="mesh.example.com")
            
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
        traffic_profile=args.traffic_profile
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

def x_main__mutmut_50():
    parser = argparse.ArgumentParser(description="x0tta6bl4 Mesh Node")
    parser.add_argument("--mesh-id", default="x0tta6bl4-mesh", help="Mesh Network ID")
    parser.add_argument("--node-id", required=True, help="Unique Node ID")
    parser.add_argument("--obfuscation", 
                        choices=["none", "xor", "faketls", "shadowsocks", "DOMAIN_FRONTING"], 
                        default="none",
                        help="Traffic obfuscation strategy")
    parser.add_argument("--obfuscation-key", default="x0tta6bl4", help="Key for XOR/Shadowsocks")
    parser.add_argument("--traffic-profile",
                        choices=TRAFFIC_PROFILES,
                        default="none",
                        help="Traffic shaping profile to mimic (evades DPI timing analysis)")
    
    args = parser.parse_args()
    
    # 1. Configure Obfuscation
    transport = None
    if args.obfuscation != "none":
        logger.info(f"Initializing obfuscation transport: {args.obfuscation}")
        if args.obfuscation == "xor":
            transport = TransportManager.create("xor", key=args.obfuscation_key)
        elif args.obfuscation == "faketls":
            transport = TransportManager.create("faketls", sni=args.obfuscation_key or "google.com")
        elif args.obfuscation == "shadowsocks":
            transport = TransportManager.create("shadowsocks", password=args.obfuscation_key)
        elif args.obfuscation == "domain_fronting":
            transport = TransportManager.create("domain_fronting", 
                                                front_domain="cdn.cloudflare.com",
                                                backend_host="mesh.example.com")
            
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
        traffic_profile=args.traffic_profile
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

def x_main__mutmut_51():
    parser = argparse.ArgumentParser(description="x0tta6bl4 Mesh Node")
    parser.add_argument("--mesh-id", default="x0tta6bl4-mesh", help="Mesh Network ID")
    parser.add_argument("--node-id", required=True, help="Unique Node ID")
    parser.add_argument("--obfuscation", 
                        choices=["none", "xor", "faketls", "shadowsocks", "domain_fronting"], 
                        default="XXnoneXX",
                        help="Traffic obfuscation strategy")
    parser.add_argument("--obfuscation-key", default="x0tta6bl4", help="Key for XOR/Shadowsocks")
    parser.add_argument("--traffic-profile",
                        choices=TRAFFIC_PROFILES,
                        default="none",
                        help="Traffic shaping profile to mimic (evades DPI timing analysis)")
    
    args = parser.parse_args()
    
    # 1. Configure Obfuscation
    transport = None
    if args.obfuscation != "none":
        logger.info(f"Initializing obfuscation transport: {args.obfuscation}")
        if args.obfuscation == "xor":
            transport = TransportManager.create("xor", key=args.obfuscation_key)
        elif args.obfuscation == "faketls":
            transport = TransportManager.create("faketls", sni=args.obfuscation_key or "google.com")
        elif args.obfuscation == "shadowsocks":
            transport = TransportManager.create("shadowsocks", password=args.obfuscation_key)
        elif args.obfuscation == "domain_fronting":
            transport = TransportManager.create("domain_fronting", 
                                                front_domain="cdn.cloudflare.com",
                                                backend_host="mesh.example.com")
            
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
        traffic_profile=args.traffic_profile
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

def x_main__mutmut_52():
    parser = argparse.ArgumentParser(description="x0tta6bl4 Mesh Node")
    parser.add_argument("--mesh-id", default="x0tta6bl4-mesh", help="Mesh Network ID")
    parser.add_argument("--node-id", required=True, help="Unique Node ID")
    parser.add_argument("--obfuscation", 
                        choices=["none", "xor", "faketls", "shadowsocks", "domain_fronting"], 
                        default="NONE",
                        help="Traffic obfuscation strategy")
    parser.add_argument("--obfuscation-key", default="x0tta6bl4", help="Key for XOR/Shadowsocks")
    parser.add_argument("--traffic-profile",
                        choices=TRAFFIC_PROFILES,
                        default="none",
                        help="Traffic shaping profile to mimic (evades DPI timing analysis)")
    
    args = parser.parse_args()
    
    # 1. Configure Obfuscation
    transport = None
    if args.obfuscation != "none":
        logger.info(f"Initializing obfuscation transport: {args.obfuscation}")
        if args.obfuscation == "xor":
            transport = TransportManager.create("xor", key=args.obfuscation_key)
        elif args.obfuscation == "faketls":
            transport = TransportManager.create("faketls", sni=args.obfuscation_key or "google.com")
        elif args.obfuscation == "shadowsocks":
            transport = TransportManager.create("shadowsocks", password=args.obfuscation_key)
        elif args.obfuscation == "domain_fronting":
            transport = TransportManager.create("domain_fronting", 
                                                front_domain="cdn.cloudflare.com",
                                                backend_host="mesh.example.com")
            
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
        traffic_profile=args.traffic_profile
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

def x_main__mutmut_53():
    parser = argparse.ArgumentParser(description="x0tta6bl4 Mesh Node")
    parser.add_argument("--mesh-id", default="x0tta6bl4-mesh", help="Mesh Network ID")
    parser.add_argument("--node-id", required=True, help="Unique Node ID")
    parser.add_argument("--obfuscation", 
                        choices=["none", "xor", "faketls", "shadowsocks", "domain_fronting"], 
                        default="none",
                        help="XXTraffic obfuscation strategyXX")
    parser.add_argument("--obfuscation-key", default="x0tta6bl4", help="Key for XOR/Shadowsocks")
    parser.add_argument("--traffic-profile",
                        choices=TRAFFIC_PROFILES,
                        default="none",
                        help="Traffic shaping profile to mimic (evades DPI timing analysis)")
    
    args = parser.parse_args()
    
    # 1. Configure Obfuscation
    transport = None
    if args.obfuscation != "none":
        logger.info(f"Initializing obfuscation transport: {args.obfuscation}")
        if args.obfuscation == "xor":
            transport = TransportManager.create("xor", key=args.obfuscation_key)
        elif args.obfuscation == "faketls":
            transport = TransportManager.create("faketls", sni=args.obfuscation_key or "google.com")
        elif args.obfuscation == "shadowsocks":
            transport = TransportManager.create("shadowsocks", password=args.obfuscation_key)
        elif args.obfuscation == "domain_fronting":
            transport = TransportManager.create("domain_fronting", 
                                                front_domain="cdn.cloudflare.com",
                                                backend_host="mesh.example.com")
            
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
        traffic_profile=args.traffic_profile
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

def x_main__mutmut_54():
    parser = argparse.ArgumentParser(description="x0tta6bl4 Mesh Node")
    parser.add_argument("--mesh-id", default="x0tta6bl4-mesh", help="Mesh Network ID")
    parser.add_argument("--node-id", required=True, help="Unique Node ID")
    parser.add_argument("--obfuscation", 
                        choices=["none", "xor", "faketls", "shadowsocks", "domain_fronting"], 
                        default="none",
                        help="traffic obfuscation strategy")
    parser.add_argument("--obfuscation-key", default="x0tta6bl4", help="Key for XOR/Shadowsocks")
    parser.add_argument("--traffic-profile",
                        choices=TRAFFIC_PROFILES,
                        default="none",
                        help="Traffic shaping profile to mimic (evades DPI timing analysis)")
    
    args = parser.parse_args()
    
    # 1. Configure Obfuscation
    transport = None
    if args.obfuscation != "none":
        logger.info(f"Initializing obfuscation transport: {args.obfuscation}")
        if args.obfuscation == "xor":
            transport = TransportManager.create("xor", key=args.obfuscation_key)
        elif args.obfuscation == "faketls":
            transport = TransportManager.create("faketls", sni=args.obfuscation_key or "google.com")
        elif args.obfuscation == "shadowsocks":
            transport = TransportManager.create("shadowsocks", password=args.obfuscation_key)
        elif args.obfuscation == "domain_fronting":
            transport = TransportManager.create("domain_fronting", 
                                                front_domain="cdn.cloudflare.com",
                                                backend_host="mesh.example.com")
            
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
        traffic_profile=args.traffic_profile
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

def x_main__mutmut_55():
    parser = argparse.ArgumentParser(description="x0tta6bl4 Mesh Node")
    parser.add_argument("--mesh-id", default="x0tta6bl4-mesh", help="Mesh Network ID")
    parser.add_argument("--node-id", required=True, help="Unique Node ID")
    parser.add_argument("--obfuscation", 
                        choices=["none", "xor", "faketls", "shadowsocks", "domain_fronting"], 
                        default="none",
                        help="TRAFFIC OBFUSCATION STRATEGY")
    parser.add_argument("--obfuscation-key", default="x0tta6bl4", help="Key for XOR/Shadowsocks")
    parser.add_argument("--traffic-profile",
                        choices=TRAFFIC_PROFILES,
                        default="none",
                        help="Traffic shaping profile to mimic (evades DPI timing analysis)")
    
    args = parser.parse_args()
    
    # 1. Configure Obfuscation
    transport = None
    if args.obfuscation != "none":
        logger.info(f"Initializing obfuscation transport: {args.obfuscation}")
        if args.obfuscation == "xor":
            transport = TransportManager.create("xor", key=args.obfuscation_key)
        elif args.obfuscation == "faketls":
            transport = TransportManager.create("faketls", sni=args.obfuscation_key or "google.com")
        elif args.obfuscation == "shadowsocks":
            transport = TransportManager.create("shadowsocks", password=args.obfuscation_key)
        elif args.obfuscation == "domain_fronting":
            transport = TransportManager.create("domain_fronting", 
                                                front_domain="cdn.cloudflare.com",
                                                backend_host="mesh.example.com")
            
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
        traffic_profile=args.traffic_profile
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

def x_main__mutmut_56():
    parser = argparse.ArgumentParser(description="x0tta6bl4 Mesh Node")
    parser.add_argument("--mesh-id", default="x0tta6bl4-mesh", help="Mesh Network ID")
    parser.add_argument("--node-id", required=True, help="Unique Node ID")
    parser.add_argument("--obfuscation", 
                        choices=["none", "xor", "faketls", "shadowsocks", "domain_fronting"], 
                        default="none",
                        help="Traffic obfuscation strategy")
    parser.add_argument(None, default="x0tta6bl4", help="Key for XOR/Shadowsocks")
    parser.add_argument("--traffic-profile",
                        choices=TRAFFIC_PROFILES,
                        default="none",
                        help="Traffic shaping profile to mimic (evades DPI timing analysis)")
    
    args = parser.parse_args()
    
    # 1. Configure Obfuscation
    transport = None
    if args.obfuscation != "none":
        logger.info(f"Initializing obfuscation transport: {args.obfuscation}")
        if args.obfuscation == "xor":
            transport = TransportManager.create("xor", key=args.obfuscation_key)
        elif args.obfuscation == "faketls":
            transport = TransportManager.create("faketls", sni=args.obfuscation_key or "google.com")
        elif args.obfuscation == "shadowsocks":
            transport = TransportManager.create("shadowsocks", password=args.obfuscation_key)
        elif args.obfuscation == "domain_fronting":
            transport = TransportManager.create("domain_fronting", 
                                                front_domain="cdn.cloudflare.com",
                                                backend_host="mesh.example.com")
            
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
        traffic_profile=args.traffic_profile
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

def x_main__mutmut_57():
    parser = argparse.ArgumentParser(description="x0tta6bl4 Mesh Node")
    parser.add_argument("--mesh-id", default="x0tta6bl4-mesh", help="Mesh Network ID")
    parser.add_argument("--node-id", required=True, help="Unique Node ID")
    parser.add_argument("--obfuscation", 
                        choices=["none", "xor", "faketls", "shadowsocks", "domain_fronting"], 
                        default="none",
                        help="Traffic obfuscation strategy")
    parser.add_argument("--obfuscation-key", default=None, help="Key for XOR/Shadowsocks")
    parser.add_argument("--traffic-profile",
                        choices=TRAFFIC_PROFILES,
                        default="none",
                        help="Traffic shaping profile to mimic (evades DPI timing analysis)")
    
    args = parser.parse_args()
    
    # 1. Configure Obfuscation
    transport = None
    if args.obfuscation != "none":
        logger.info(f"Initializing obfuscation transport: {args.obfuscation}")
        if args.obfuscation == "xor":
            transport = TransportManager.create("xor", key=args.obfuscation_key)
        elif args.obfuscation == "faketls":
            transport = TransportManager.create("faketls", sni=args.obfuscation_key or "google.com")
        elif args.obfuscation == "shadowsocks":
            transport = TransportManager.create("shadowsocks", password=args.obfuscation_key)
        elif args.obfuscation == "domain_fronting":
            transport = TransportManager.create("domain_fronting", 
                                                front_domain="cdn.cloudflare.com",
                                                backend_host="mesh.example.com")
            
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
        traffic_profile=args.traffic_profile
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

def x_main__mutmut_58():
    parser = argparse.ArgumentParser(description="x0tta6bl4 Mesh Node")
    parser.add_argument("--mesh-id", default="x0tta6bl4-mesh", help="Mesh Network ID")
    parser.add_argument("--node-id", required=True, help="Unique Node ID")
    parser.add_argument("--obfuscation", 
                        choices=["none", "xor", "faketls", "shadowsocks", "domain_fronting"], 
                        default="none",
                        help="Traffic obfuscation strategy")
    parser.add_argument("--obfuscation-key", default="x0tta6bl4", help=None)
    parser.add_argument("--traffic-profile",
                        choices=TRAFFIC_PROFILES,
                        default="none",
                        help="Traffic shaping profile to mimic (evades DPI timing analysis)")
    
    args = parser.parse_args()
    
    # 1. Configure Obfuscation
    transport = None
    if args.obfuscation != "none":
        logger.info(f"Initializing obfuscation transport: {args.obfuscation}")
        if args.obfuscation == "xor":
            transport = TransportManager.create("xor", key=args.obfuscation_key)
        elif args.obfuscation == "faketls":
            transport = TransportManager.create("faketls", sni=args.obfuscation_key or "google.com")
        elif args.obfuscation == "shadowsocks":
            transport = TransportManager.create("shadowsocks", password=args.obfuscation_key)
        elif args.obfuscation == "domain_fronting":
            transport = TransportManager.create("domain_fronting", 
                                                front_domain="cdn.cloudflare.com",
                                                backend_host="mesh.example.com")
            
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
        traffic_profile=args.traffic_profile
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

def x_main__mutmut_59():
    parser = argparse.ArgumentParser(description="x0tta6bl4 Mesh Node")
    parser.add_argument("--mesh-id", default="x0tta6bl4-mesh", help="Mesh Network ID")
    parser.add_argument("--node-id", required=True, help="Unique Node ID")
    parser.add_argument("--obfuscation", 
                        choices=["none", "xor", "faketls", "shadowsocks", "domain_fronting"], 
                        default="none",
                        help="Traffic obfuscation strategy")
    parser.add_argument(default="x0tta6bl4", help="Key for XOR/Shadowsocks")
    parser.add_argument("--traffic-profile",
                        choices=TRAFFIC_PROFILES,
                        default="none",
                        help="Traffic shaping profile to mimic (evades DPI timing analysis)")
    
    args = parser.parse_args()
    
    # 1. Configure Obfuscation
    transport = None
    if args.obfuscation != "none":
        logger.info(f"Initializing obfuscation transport: {args.obfuscation}")
        if args.obfuscation == "xor":
            transport = TransportManager.create("xor", key=args.obfuscation_key)
        elif args.obfuscation == "faketls":
            transport = TransportManager.create("faketls", sni=args.obfuscation_key or "google.com")
        elif args.obfuscation == "shadowsocks":
            transport = TransportManager.create("shadowsocks", password=args.obfuscation_key)
        elif args.obfuscation == "domain_fronting":
            transport = TransportManager.create("domain_fronting", 
                                                front_domain="cdn.cloudflare.com",
                                                backend_host="mesh.example.com")
            
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
        traffic_profile=args.traffic_profile
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

def x_main__mutmut_60():
    parser = argparse.ArgumentParser(description="x0tta6bl4 Mesh Node")
    parser.add_argument("--mesh-id", default="x0tta6bl4-mesh", help="Mesh Network ID")
    parser.add_argument("--node-id", required=True, help="Unique Node ID")
    parser.add_argument("--obfuscation", 
                        choices=["none", "xor", "faketls", "shadowsocks", "domain_fronting"], 
                        default="none",
                        help="Traffic obfuscation strategy")
    parser.add_argument("--obfuscation-key", help="Key for XOR/Shadowsocks")
    parser.add_argument("--traffic-profile",
                        choices=TRAFFIC_PROFILES,
                        default="none",
                        help="Traffic shaping profile to mimic (evades DPI timing analysis)")
    
    args = parser.parse_args()
    
    # 1. Configure Obfuscation
    transport = None
    if args.obfuscation != "none":
        logger.info(f"Initializing obfuscation transport: {args.obfuscation}")
        if args.obfuscation == "xor":
            transport = TransportManager.create("xor", key=args.obfuscation_key)
        elif args.obfuscation == "faketls":
            transport = TransportManager.create("faketls", sni=args.obfuscation_key or "google.com")
        elif args.obfuscation == "shadowsocks":
            transport = TransportManager.create("shadowsocks", password=args.obfuscation_key)
        elif args.obfuscation == "domain_fronting":
            transport = TransportManager.create("domain_fronting", 
                                                front_domain="cdn.cloudflare.com",
                                                backend_host="mesh.example.com")
            
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
        traffic_profile=args.traffic_profile
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

def x_main__mutmut_61():
    parser = argparse.ArgumentParser(description="x0tta6bl4 Mesh Node")
    parser.add_argument("--mesh-id", default="x0tta6bl4-mesh", help="Mesh Network ID")
    parser.add_argument("--node-id", required=True, help="Unique Node ID")
    parser.add_argument("--obfuscation", 
                        choices=["none", "xor", "faketls", "shadowsocks", "domain_fronting"], 
                        default="none",
                        help="Traffic obfuscation strategy")
    parser.add_argument("--obfuscation-key", default="x0tta6bl4", )
    parser.add_argument("--traffic-profile",
                        choices=TRAFFIC_PROFILES,
                        default="none",
                        help="Traffic shaping profile to mimic (evades DPI timing analysis)")
    
    args = parser.parse_args()
    
    # 1. Configure Obfuscation
    transport = None
    if args.obfuscation != "none":
        logger.info(f"Initializing obfuscation transport: {args.obfuscation}")
        if args.obfuscation == "xor":
            transport = TransportManager.create("xor", key=args.obfuscation_key)
        elif args.obfuscation == "faketls":
            transport = TransportManager.create("faketls", sni=args.obfuscation_key or "google.com")
        elif args.obfuscation == "shadowsocks":
            transport = TransportManager.create("shadowsocks", password=args.obfuscation_key)
        elif args.obfuscation == "domain_fronting":
            transport = TransportManager.create("domain_fronting", 
                                                front_domain="cdn.cloudflare.com",
                                                backend_host="mesh.example.com")
            
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
        traffic_profile=args.traffic_profile
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

def x_main__mutmut_62():
    parser = argparse.ArgumentParser(description="x0tta6bl4 Mesh Node")
    parser.add_argument("--mesh-id", default="x0tta6bl4-mesh", help="Mesh Network ID")
    parser.add_argument("--node-id", required=True, help="Unique Node ID")
    parser.add_argument("--obfuscation", 
                        choices=["none", "xor", "faketls", "shadowsocks", "domain_fronting"], 
                        default="none",
                        help="Traffic obfuscation strategy")
    parser.add_argument("XX--obfuscation-keyXX", default="x0tta6bl4", help="Key for XOR/Shadowsocks")
    parser.add_argument("--traffic-profile",
                        choices=TRAFFIC_PROFILES,
                        default="none",
                        help="Traffic shaping profile to mimic (evades DPI timing analysis)")
    
    args = parser.parse_args()
    
    # 1. Configure Obfuscation
    transport = None
    if args.obfuscation != "none":
        logger.info(f"Initializing obfuscation transport: {args.obfuscation}")
        if args.obfuscation == "xor":
            transport = TransportManager.create("xor", key=args.obfuscation_key)
        elif args.obfuscation == "faketls":
            transport = TransportManager.create("faketls", sni=args.obfuscation_key or "google.com")
        elif args.obfuscation == "shadowsocks":
            transport = TransportManager.create("shadowsocks", password=args.obfuscation_key)
        elif args.obfuscation == "domain_fronting":
            transport = TransportManager.create("domain_fronting", 
                                                front_domain="cdn.cloudflare.com",
                                                backend_host="mesh.example.com")
            
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
        traffic_profile=args.traffic_profile
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

def x_main__mutmut_63():
    parser = argparse.ArgumentParser(description="x0tta6bl4 Mesh Node")
    parser.add_argument("--mesh-id", default="x0tta6bl4-mesh", help="Mesh Network ID")
    parser.add_argument("--node-id", required=True, help="Unique Node ID")
    parser.add_argument("--obfuscation", 
                        choices=["none", "xor", "faketls", "shadowsocks", "domain_fronting"], 
                        default="none",
                        help="Traffic obfuscation strategy")
    parser.add_argument("--OBFUSCATION-KEY", default="x0tta6bl4", help="Key for XOR/Shadowsocks")
    parser.add_argument("--traffic-profile",
                        choices=TRAFFIC_PROFILES,
                        default="none",
                        help="Traffic shaping profile to mimic (evades DPI timing analysis)")
    
    args = parser.parse_args()
    
    # 1. Configure Obfuscation
    transport = None
    if args.obfuscation != "none":
        logger.info(f"Initializing obfuscation transport: {args.obfuscation}")
        if args.obfuscation == "xor":
            transport = TransportManager.create("xor", key=args.obfuscation_key)
        elif args.obfuscation == "faketls":
            transport = TransportManager.create("faketls", sni=args.obfuscation_key or "google.com")
        elif args.obfuscation == "shadowsocks":
            transport = TransportManager.create("shadowsocks", password=args.obfuscation_key)
        elif args.obfuscation == "domain_fronting":
            transport = TransportManager.create("domain_fronting", 
                                                front_domain="cdn.cloudflare.com",
                                                backend_host="mesh.example.com")
            
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
        traffic_profile=args.traffic_profile
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

def x_main__mutmut_64():
    parser = argparse.ArgumentParser(description="x0tta6bl4 Mesh Node")
    parser.add_argument("--mesh-id", default="x0tta6bl4-mesh", help="Mesh Network ID")
    parser.add_argument("--node-id", required=True, help="Unique Node ID")
    parser.add_argument("--obfuscation", 
                        choices=["none", "xor", "faketls", "shadowsocks", "domain_fronting"], 
                        default="none",
                        help="Traffic obfuscation strategy")
    parser.add_argument("--obfuscation-key", default="XXx0tta6bl4XX", help="Key for XOR/Shadowsocks")
    parser.add_argument("--traffic-profile",
                        choices=TRAFFIC_PROFILES,
                        default="none",
                        help="Traffic shaping profile to mimic (evades DPI timing analysis)")
    
    args = parser.parse_args()
    
    # 1. Configure Obfuscation
    transport = None
    if args.obfuscation != "none":
        logger.info(f"Initializing obfuscation transport: {args.obfuscation}")
        if args.obfuscation == "xor":
            transport = TransportManager.create("xor", key=args.obfuscation_key)
        elif args.obfuscation == "faketls":
            transport = TransportManager.create("faketls", sni=args.obfuscation_key or "google.com")
        elif args.obfuscation == "shadowsocks":
            transport = TransportManager.create("shadowsocks", password=args.obfuscation_key)
        elif args.obfuscation == "domain_fronting":
            transport = TransportManager.create("domain_fronting", 
                                                front_domain="cdn.cloudflare.com",
                                                backend_host="mesh.example.com")
            
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
        traffic_profile=args.traffic_profile
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

def x_main__mutmut_65():
    parser = argparse.ArgumentParser(description="x0tta6bl4 Mesh Node")
    parser.add_argument("--mesh-id", default="x0tta6bl4-mesh", help="Mesh Network ID")
    parser.add_argument("--node-id", required=True, help="Unique Node ID")
    parser.add_argument("--obfuscation", 
                        choices=["none", "xor", "faketls", "shadowsocks", "domain_fronting"], 
                        default="none",
                        help="Traffic obfuscation strategy")
    parser.add_argument("--obfuscation-key", default="X0TTA6BL4", help="Key for XOR/Shadowsocks")
    parser.add_argument("--traffic-profile",
                        choices=TRAFFIC_PROFILES,
                        default="none",
                        help="Traffic shaping profile to mimic (evades DPI timing analysis)")
    
    args = parser.parse_args()
    
    # 1. Configure Obfuscation
    transport = None
    if args.obfuscation != "none":
        logger.info(f"Initializing obfuscation transport: {args.obfuscation}")
        if args.obfuscation == "xor":
            transport = TransportManager.create("xor", key=args.obfuscation_key)
        elif args.obfuscation == "faketls":
            transport = TransportManager.create("faketls", sni=args.obfuscation_key or "google.com")
        elif args.obfuscation == "shadowsocks":
            transport = TransportManager.create("shadowsocks", password=args.obfuscation_key)
        elif args.obfuscation == "domain_fronting":
            transport = TransportManager.create("domain_fronting", 
                                                front_domain="cdn.cloudflare.com",
                                                backend_host="mesh.example.com")
            
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
        traffic_profile=args.traffic_profile
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

def x_main__mutmut_66():
    parser = argparse.ArgumentParser(description="x0tta6bl4 Mesh Node")
    parser.add_argument("--mesh-id", default="x0tta6bl4-mesh", help="Mesh Network ID")
    parser.add_argument("--node-id", required=True, help="Unique Node ID")
    parser.add_argument("--obfuscation", 
                        choices=["none", "xor", "faketls", "shadowsocks", "domain_fronting"], 
                        default="none",
                        help="Traffic obfuscation strategy")
    parser.add_argument("--obfuscation-key", default="x0tta6bl4", help="XXKey for XOR/ShadowsocksXX")
    parser.add_argument("--traffic-profile",
                        choices=TRAFFIC_PROFILES,
                        default="none",
                        help="Traffic shaping profile to mimic (evades DPI timing analysis)")
    
    args = parser.parse_args()
    
    # 1. Configure Obfuscation
    transport = None
    if args.obfuscation != "none":
        logger.info(f"Initializing obfuscation transport: {args.obfuscation}")
        if args.obfuscation == "xor":
            transport = TransportManager.create("xor", key=args.obfuscation_key)
        elif args.obfuscation == "faketls":
            transport = TransportManager.create("faketls", sni=args.obfuscation_key or "google.com")
        elif args.obfuscation == "shadowsocks":
            transport = TransportManager.create("shadowsocks", password=args.obfuscation_key)
        elif args.obfuscation == "domain_fronting":
            transport = TransportManager.create("domain_fronting", 
                                                front_domain="cdn.cloudflare.com",
                                                backend_host="mesh.example.com")
            
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
        traffic_profile=args.traffic_profile
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

def x_main__mutmut_67():
    parser = argparse.ArgumentParser(description="x0tta6bl4 Mesh Node")
    parser.add_argument("--mesh-id", default="x0tta6bl4-mesh", help="Mesh Network ID")
    parser.add_argument("--node-id", required=True, help="Unique Node ID")
    parser.add_argument("--obfuscation", 
                        choices=["none", "xor", "faketls", "shadowsocks", "domain_fronting"], 
                        default="none",
                        help="Traffic obfuscation strategy")
    parser.add_argument("--obfuscation-key", default="x0tta6bl4", help="key for xor/shadowsocks")
    parser.add_argument("--traffic-profile",
                        choices=TRAFFIC_PROFILES,
                        default="none",
                        help="Traffic shaping profile to mimic (evades DPI timing analysis)")
    
    args = parser.parse_args()
    
    # 1. Configure Obfuscation
    transport = None
    if args.obfuscation != "none":
        logger.info(f"Initializing obfuscation transport: {args.obfuscation}")
        if args.obfuscation == "xor":
            transport = TransportManager.create("xor", key=args.obfuscation_key)
        elif args.obfuscation == "faketls":
            transport = TransportManager.create("faketls", sni=args.obfuscation_key or "google.com")
        elif args.obfuscation == "shadowsocks":
            transport = TransportManager.create("shadowsocks", password=args.obfuscation_key)
        elif args.obfuscation == "domain_fronting":
            transport = TransportManager.create("domain_fronting", 
                                                front_domain="cdn.cloudflare.com",
                                                backend_host="mesh.example.com")
            
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
        traffic_profile=args.traffic_profile
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

def x_main__mutmut_68():
    parser = argparse.ArgumentParser(description="x0tta6bl4 Mesh Node")
    parser.add_argument("--mesh-id", default="x0tta6bl4-mesh", help="Mesh Network ID")
    parser.add_argument("--node-id", required=True, help="Unique Node ID")
    parser.add_argument("--obfuscation", 
                        choices=["none", "xor", "faketls", "shadowsocks", "domain_fronting"], 
                        default="none",
                        help="Traffic obfuscation strategy")
    parser.add_argument("--obfuscation-key", default="x0tta6bl4", help="KEY FOR XOR/SHADOWSOCKS")
    parser.add_argument("--traffic-profile",
                        choices=TRAFFIC_PROFILES,
                        default="none",
                        help="Traffic shaping profile to mimic (evades DPI timing analysis)")
    
    args = parser.parse_args()
    
    # 1. Configure Obfuscation
    transport = None
    if args.obfuscation != "none":
        logger.info(f"Initializing obfuscation transport: {args.obfuscation}")
        if args.obfuscation == "xor":
            transport = TransportManager.create("xor", key=args.obfuscation_key)
        elif args.obfuscation == "faketls":
            transport = TransportManager.create("faketls", sni=args.obfuscation_key or "google.com")
        elif args.obfuscation == "shadowsocks":
            transport = TransportManager.create("shadowsocks", password=args.obfuscation_key)
        elif args.obfuscation == "domain_fronting":
            transport = TransportManager.create("domain_fronting", 
                                                front_domain="cdn.cloudflare.com",
                                                backend_host="mesh.example.com")
            
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
        traffic_profile=args.traffic_profile
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

def x_main__mutmut_69():
    parser = argparse.ArgumentParser(description="x0tta6bl4 Mesh Node")
    parser.add_argument("--mesh-id", default="x0tta6bl4-mesh", help="Mesh Network ID")
    parser.add_argument("--node-id", required=True, help="Unique Node ID")
    parser.add_argument("--obfuscation", 
                        choices=["none", "xor", "faketls", "shadowsocks", "domain_fronting"], 
                        default="none",
                        help="Traffic obfuscation strategy")
    parser.add_argument("--obfuscation-key", default="x0tta6bl4", help="Key for XOR/Shadowsocks")
    parser.add_argument(None,
                        choices=TRAFFIC_PROFILES,
                        default="none",
                        help="Traffic shaping profile to mimic (evades DPI timing analysis)")
    
    args = parser.parse_args()
    
    # 1. Configure Obfuscation
    transport = None
    if args.obfuscation != "none":
        logger.info(f"Initializing obfuscation transport: {args.obfuscation}")
        if args.obfuscation == "xor":
            transport = TransportManager.create("xor", key=args.obfuscation_key)
        elif args.obfuscation == "faketls":
            transport = TransportManager.create("faketls", sni=args.obfuscation_key or "google.com")
        elif args.obfuscation == "shadowsocks":
            transport = TransportManager.create("shadowsocks", password=args.obfuscation_key)
        elif args.obfuscation == "domain_fronting":
            transport = TransportManager.create("domain_fronting", 
                                                front_domain="cdn.cloudflare.com",
                                                backend_host="mesh.example.com")
            
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
        traffic_profile=args.traffic_profile
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

def x_main__mutmut_70():
    parser = argparse.ArgumentParser(description="x0tta6bl4 Mesh Node")
    parser.add_argument("--mesh-id", default="x0tta6bl4-mesh", help="Mesh Network ID")
    parser.add_argument("--node-id", required=True, help="Unique Node ID")
    parser.add_argument("--obfuscation", 
                        choices=["none", "xor", "faketls", "shadowsocks", "domain_fronting"], 
                        default="none",
                        help="Traffic obfuscation strategy")
    parser.add_argument("--obfuscation-key", default="x0tta6bl4", help="Key for XOR/Shadowsocks")
    parser.add_argument("--traffic-profile",
                        choices=None,
                        default="none",
                        help="Traffic shaping profile to mimic (evades DPI timing analysis)")
    
    args = parser.parse_args()
    
    # 1. Configure Obfuscation
    transport = None
    if args.obfuscation != "none":
        logger.info(f"Initializing obfuscation transport: {args.obfuscation}")
        if args.obfuscation == "xor":
            transport = TransportManager.create("xor", key=args.obfuscation_key)
        elif args.obfuscation == "faketls":
            transport = TransportManager.create("faketls", sni=args.obfuscation_key or "google.com")
        elif args.obfuscation == "shadowsocks":
            transport = TransportManager.create("shadowsocks", password=args.obfuscation_key)
        elif args.obfuscation == "domain_fronting":
            transport = TransportManager.create("domain_fronting", 
                                                front_domain="cdn.cloudflare.com",
                                                backend_host="mesh.example.com")
            
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
        traffic_profile=args.traffic_profile
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

def x_main__mutmut_71():
    parser = argparse.ArgumentParser(description="x0tta6bl4 Mesh Node")
    parser.add_argument("--mesh-id", default="x0tta6bl4-mesh", help="Mesh Network ID")
    parser.add_argument("--node-id", required=True, help="Unique Node ID")
    parser.add_argument("--obfuscation", 
                        choices=["none", "xor", "faketls", "shadowsocks", "domain_fronting"], 
                        default="none",
                        help="Traffic obfuscation strategy")
    parser.add_argument("--obfuscation-key", default="x0tta6bl4", help="Key for XOR/Shadowsocks")
    parser.add_argument("--traffic-profile",
                        choices=TRAFFIC_PROFILES,
                        default=None,
                        help="Traffic shaping profile to mimic (evades DPI timing analysis)")
    
    args = parser.parse_args()
    
    # 1. Configure Obfuscation
    transport = None
    if args.obfuscation != "none":
        logger.info(f"Initializing obfuscation transport: {args.obfuscation}")
        if args.obfuscation == "xor":
            transport = TransportManager.create("xor", key=args.obfuscation_key)
        elif args.obfuscation == "faketls":
            transport = TransportManager.create("faketls", sni=args.obfuscation_key or "google.com")
        elif args.obfuscation == "shadowsocks":
            transport = TransportManager.create("shadowsocks", password=args.obfuscation_key)
        elif args.obfuscation == "domain_fronting":
            transport = TransportManager.create("domain_fronting", 
                                                front_domain="cdn.cloudflare.com",
                                                backend_host="mesh.example.com")
            
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
        traffic_profile=args.traffic_profile
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

def x_main__mutmut_72():
    parser = argparse.ArgumentParser(description="x0tta6bl4 Mesh Node")
    parser.add_argument("--mesh-id", default="x0tta6bl4-mesh", help="Mesh Network ID")
    parser.add_argument("--node-id", required=True, help="Unique Node ID")
    parser.add_argument("--obfuscation", 
                        choices=["none", "xor", "faketls", "shadowsocks", "domain_fronting"], 
                        default="none",
                        help="Traffic obfuscation strategy")
    parser.add_argument("--obfuscation-key", default="x0tta6bl4", help="Key for XOR/Shadowsocks")
    parser.add_argument("--traffic-profile",
                        choices=TRAFFIC_PROFILES,
                        default="none",
                        help=None)
    
    args = parser.parse_args()
    
    # 1. Configure Obfuscation
    transport = None
    if args.obfuscation != "none":
        logger.info(f"Initializing obfuscation transport: {args.obfuscation}")
        if args.obfuscation == "xor":
            transport = TransportManager.create("xor", key=args.obfuscation_key)
        elif args.obfuscation == "faketls":
            transport = TransportManager.create("faketls", sni=args.obfuscation_key or "google.com")
        elif args.obfuscation == "shadowsocks":
            transport = TransportManager.create("shadowsocks", password=args.obfuscation_key)
        elif args.obfuscation == "domain_fronting":
            transport = TransportManager.create("domain_fronting", 
                                                front_domain="cdn.cloudflare.com",
                                                backend_host="mesh.example.com")
            
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
        traffic_profile=args.traffic_profile
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

def x_main__mutmut_73():
    parser = argparse.ArgumentParser(description="x0tta6bl4 Mesh Node")
    parser.add_argument("--mesh-id", default="x0tta6bl4-mesh", help="Mesh Network ID")
    parser.add_argument("--node-id", required=True, help="Unique Node ID")
    parser.add_argument("--obfuscation", 
                        choices=["none", "xor", "faketls", "shadowsocks", "domain_fronting"], 
                        default="none",
                        help="Traffic obfuscation strategy")
    parser.add_argument("--obfuscation-key", default="x0tta6bl4", help="Key for XOR/Shadowsocks")
    parser.add_argument(choices=TRAFFIC_PROFILES,
                        default="none",
                        help="Traffic shaping profile to mimic (evades DPI timing analysis)")
    
    args = parser.parse_args()
    
    # 1. Configure Obfuscation
    transport = None
    if args.obfuscation != "none":
        logger.info(f"Initializing obfuscation transport: {args.obfuscation}")
        if args.obfuscation == "xor":
            transport = TransportManager.create("xor", key=args.obfuscation_key)
        elif args.obfuscation == "faketls":
            transport = TransportManager.create("faketls", sni=args.obfuscation_key or "google.com")
        elif args.obfuscation == "shadowsocks":
            transport = TransportManager.create("shadowsocks", password=args.obfuscation_key)
        elif args.obfuscation == "domain_fronting":
            transport = TransportManager.create("domain_fronting", 
                                                front_domain="cdn.cloudflare.com",
                                                backend_host="mesh.example.com")
            
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
        traffic_profile=args.traffic_profile
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

def x_main__mutmut_74():
    parser = argparse.ArgumentParser(description="x0tta6bl4 Mesh Node")
    parser.add_argument("--mesh-id", default="x0tta6bl4-mesh", help="Mesh Network ID")
    parser.add_argument("--node-id", required=True, help="Unique Node ID")
    parser.add_argument("--obfuscation", 
                        choices=["none", "xor", "faketls", "shadowsocks", "domain_fronting"], 
                        default="none",
                        help="Traffic obfuscation strategy")
    parser.add_argument("--obfuscation-key", default="x0tta6bl4", help="Key for XOR/Shadowsocks")
    parser.add_argument("--traffic-profile",
                        default="none",
                        help="Traffic shaping profile to mimic (evades DPI timing analysis)")
    
    args = parser.parse_args()
    
    # 1. Configure Obfuscation
    transport = None
    if args.obfuscation != "none":
        logger.info(f"Initializing obfuscation transport: {args.obfuscation}")
        if args.obfuscation == "xor":
            transport = TransportManager.create("xor", key=args.obfuscation_key)
        elif args.obfuscation == "faketls":
            transport = TransportManager.create("faketls", sni=args.obfuscation_key or "google.com")
        elif args.obfuscation == "shadowsocks":
            transport = TransportManager.create("shadowsocks", password=args.obfuscation_key)
        elif args.obfuscation == "domain_fronting":
            transport = TransportManager.create("domain_fronting", 
                                                front_domain="cdn.cloudflare.com",
                                                backend_host="mesh.example.com")
            
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
        traffic_profile=args.traffic_profile
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

def x_main__mutmut_75():
    parser = argparse.ArgumentParser(description="x0tta6bl4 Mesh Node")
    parser.add_argument("--mesh-id", default="x0tta6bl4-mesh", help="Mesh Network ID")
    parser.add_argument("--node-id", required=True, help="Unique Node ID")
    parser.add_argument("--obfuscation", 
                        choices=["none", "xor", "faketls", "shadowsocks", "domain_fronting"], 
                        default="none",
                        help="Traffic obfuscation strategy")
    parser.add_argument("--obfuscation-key", default="x0tta6bl4", help="Key for XOR/Shadowsocks")
    parser.add_argument("--traffic-profile",
                        choices=TRAFFIC_PROFILES,
                        help="Traffic shaping profile to mimic (evades DPI timing analysis)")
    
    args = parser.parse_args()
    
    # 1. Configure Obfuscation
    transport = None
    if args.obfuscation != "none":
        logger.info(f"Initializing obfuscation transport: {args.obfuscation}")
        if args.obfuscation == "xor":
            transport = TransportManager.create("xor", key=args.obfuscation_key)
        elif args.obfuscation == "faketls":
            transport = TransportManager.create("faketls", sni=args.obfuscation_key or "google.com")
        elif args.obfuscation == "shadowsocks":
            transport = TransportManager.create("shadowsocks", password=args.obfuscation_key)
        elif args.obfuscation == "domain_fronting":
            transport = TransportManager.create("domain_fronting", 
                                                front_domain="cdn.cloudflare.com",
                                                backend_host="mesh.example.com")
            
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
        traffic_profile=args.traffic_profile
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

def x_main__mutmut_76():
    parser = argparse.ArgumentParser(description="x0tta6bl4 Mesh Node")
    parser.add_argument("--mesh-id", default="x0tta6bl4-mesh", help="Mesh Network ID")
    parser.add_argument("--node-id", required=True, help="Unique Node ID")
    parser.add_argument("--obfuscation", 
                        choices=["none", "xor", "faketls", "shadowsocks", "domain_fronting"], 
                        default="none",
                        help="Traffic obfuscation strategy")
    parser.add_argument("--obfuscation-key", default="x0tta6bl4", help="Key for XOR/Shadowsocks")
    parser.add_argument("--traffic-profile",
                        choices=TRAFFIC_PROFILES,
                        default="none",
                        )
    
    args = parser.parse_args()
    
    # 1. Configure Obfuscation
    transport = None
    if args.obfuscation != "none":
        logger.info(f"Initializing obfuscation transport: {args.obfuscation}")
        if args.obfuscation == "xor":
            transport = TransportManager.create("xor", key=args.obfuscation_key)
        elif args.obfuscation == "faketls":
            transport = TransportManager.create("faketls", sni=args.obfuscation_key or "google.com")
        elif args.obfuscation == "shadowsocks":
            transport = TransportManager.create("shadowsocks", password=args.obfuscation_key)
        elif args.obfuscation == "domain_fronting":
            transport = TransportManager.create("domain_fronting", 
                                                front_domain="cdn.cloudflare.com",
                                                backend_host="mesh.example.com")
            
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
        traffic_profile=args.traffic_profile
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

def x_main__mutmut_77():
    parser = argparse.ArgumentParser(description="x0tta6bl4 Mesh Node")
    parser.add_argument("--mesh-id", default="x0tta6bl4-mesh", help="Mesh Network ID")
    parser.add_argument("--node-id", required=True, help="Unique Node ID")
    parser.add_argument("--obfuscation", 
                        choices=["none", "xor", "faketls", "shadowsocks", "domain_fronting"], 
                        default="none",
                        help="Traffic obfuscation strategy")
    parser.add_argument("--obfuscation-key", default="x0tta6bl4", help="Key for XOR/Shadowsocks")
    parser.add_argument("XX--traffic-profileXX",
                        choices=TRAFFIC_PROFILES,
                        default="none",
                        help="Traffic shaping profile to mimic (evades DPI timing analysis)")
    
    args = parser.parse_args()
    
    # 1. Configure Obfuscation
    transport = None
    if args.obfuscation != "none":
        logger.info(f"Initializing obfuscation transport: {args.obfuscation}")
        if args.obfuscation == "xor":
            transport = TransportManager.create("xor", key=args.obfuscation_key)
        elif args.obfuscation == "faketls":
            transport = TransportManager.create("faketls", sni=args.obfuscation_key or "google.com")
        elif args.obfuscation == "shadowsocks":
            transport = TransportManager.create("shadowsocks", password=args.obfuscation_key)
        elif args.obfuscation == "domain_fronting":
            transport = TransportManager.create("domain_fronting", 
                                                front_domain="cdn.cloudflare.com",
                                                backend_host="mesh.example.com")
            
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
        traffic_profile=args.traffic_profile
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

def x_main__mutmut_78():
    parser = argparse.ArgumentParser(description="x0tta6bl4 Mesh Node")
    parser.add_argument("--mesh-id", default="x0tta6bl4-mesh", help="Mesh Network ID")
    parser.add_argument("--node-id", required=True, help="Unique Node ID")
    parser.add_argument("--obfuscation", 
                        choices=["none", "xor", "faketls", "shadowsocks", "domain_fronting"], 
                        default="none",
                        help="Traffic obfuscation strategy")
    parser.add_argument("--obfuscation-key", default="x0tta6bl4", help="Key for XOR/Shadowsocks")
    parser.add_argument("--TRAFFIC-PROFILE",
                        choices=TRAFFIC_PROFILES,
                        default="none",
                        help="Traffic shaping profile to mimic (evades DPI timing analysis)")
    
    args = parser.parse_args()
    
    # 1. Configure Obfuscation
    transport = None
    if args.obfuscation != "none":
        logger.info(f"Initializing obfuscation transport: {args.obfuscation}")
        if args.obfuscation == "xor":
            transport = TransportManager.create("xor", key=args.obfuscation_key)
        elif args.obfuscation == "faketls":
            transport = TransportManager.create("faketls", sni=args.obfuscation_key or "google.com")
        elif args.obfuscation == "shadowsocks":
            transport = TransportManager.create("shadowsocks", password=args.obfuscation_key)
        elif args.obfuscation == "domain_fronting":
            transport = TransportManager.create("domain_fronting", 
                                                front_domain="cdn.cloudflare.com",
                                                backend_host="mesh.example.com")
            
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
        traffic_profile=args.traffic_profile
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

def x_main__mutmut_79():
    parser = argparse.ArgumentParser(description="x0tta6bl4 Mesh Node")
    parser.add_argument("--mesh-id", default="x0tta6bl4-mesh", help="Mesh Network ID")
    parser.add_argument("--node-id", required=True, help="Unique Node ID")
    parser.add_argument("--obfuscation", 
                        choices=["none", "xor", "faketls", "shadowsocks", "domain_fronting"], 
                        default="none",
                        help="Traffic obfuscation strategy")
    parser.add_argument("--obfuscation-key", default="x0tta6bl4", help="Key for XOR/Shadowsocks")
    parser.add_argument("--traffic-profile",
                        choices=TRAFFIC_PROFILES,
                        default="XXnoneXX",
                        help="Traffic shaping profile to mimic (evades DPI timing analysis)")
    
    args = parser.parse_args()
    
    # 1. Configure Obfuscation
    transport = None
    if args.obfuscation != "none":
        logger.info(f"Initializing obfuscation transport: {args.obfuscation}")
        if args.obfuscation == "xor":
            transport = TransportManager.create("xor", key=args.obfuscation_key)
        elif args.obfuscation == "faketls":
            transport = TransportManager.create("faketls", sni=args.obfuscation_key or "google.com")
        elif args.obfuscation == "shadowsocks":
            transport = TransportManager.create("shadowsocks", password=args.obfuscation_key)
        elif args.obfuscation == "domain_fronting":
            transport = TransportManager.create("domain_fronting", 
                                                front_domain="cdn.cloudflare.com",
                                                backend_host="mesh.example.com")
            
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
        traffic_profile=args.traffic_profile
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

def x_main__mutmut_80():
    parser = argparse.ArgumentParser(description="x0tta6bl4 Mesh Node")
    parser.add_argument("--mesh-id", default="x0tta6bl4-mesh", help="Mesh Network ID")
    parser.add_argument("--node-id", required=True, help="Unique Node ID")
    parser.add_argument("--obfuscation", 
                        choices=["none", "xor", "faketls", "shadowsocks", "domain_fronting"], 
                        default="none",
                        help="Traffic obfuscation strategy")
    parser.add_argument("--obfuscation-key", default="x0tta6bl4", help="Key for XOR/Shadowsocks")
    parser.add_argument("--traffic-profile",
                        choices=TRAFFIC_PROFILES,
                        default="NONE",
                        help="Traffic shaping profile to mimic (evades DPI timing analysis)")
    
    args = parser.parse_args()
    
    # 1. Configure Obfuscation
    transport = None
    if args.obfuscation != "none":
        logger.info(f"Initializing obfuscation transport: {args.obfuscation}")
        if args.obfuscation == "xor":
            transport = TransportManager.create("xor", key=args.obfuscation_key)
        elif args.obfuscation == "faketls":
            transport = TransportManager.create("faketls", sni=args.obfuscation_key or "google.com")
        elif args.obfuscation == "shadowsocks":
            transport = TransportManager.create("shadowsocks", password=args.obfuscation_key)
        elif args.obfuscation == "domain_fronting":
            transport = TransportManager.create("domain_fronting", 
                                                front_domain="cdn.cloudflare.com",
                                                backend_host="mesh.example.com")
            
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
        traffic_profile=args.traffic_profile
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

def x_main__mutmut_81():
    parser = argparse.ArgumentParser(description="x0tta6bl4 Mesh Node")
    parser.add_argument("--mesh-id", default="x0tta6bl4-mesh", help="Mesh Network ID")
    parser.add_argument("--node-id", required=True, help="Unique Node ID")
    parser.add_argument("--obfuscation", 
                        choices=["none", "xor", "faketls", "shadowsocks", "domain_fronting"], 
                        default="none",
                        help="Traffic obfuscation strategy")
    parser.add_argument("--obfuscation-key", default="x0tta6bl4", help="Key for XOR/Shadowsocks")
    parser.add_argument("--traffic-profile",
                        choices=TRAFFIC_PROFILES,
                        default="none",
                        help="XXTraffic shaping profile to mimic (evades DPI timing analysis)XX")
    
    args = parser.parse_args()
    
    # 1. Configure Obfuscation
    transport = None
    if args.obfuscation != "none":
        logger.info(f"Initializing obfuscation transport: {args.obfuscation}")
        if args.obfuscation == "xor":
            transport = TransportManager.create("xor", key=args.obfuscation_key)
        elif args.obfuscation == "faketls":
            transport = TransportManager.create("faketls", sni=args.obfuscation_key or "google.com")
        elif args.obfuscation == "shadowsocks":
            transport = TransportManager.create("shadowsocks", password=args.obfuscation_key)
        elif args.obfuscation == "domain_fronting":
            transport = TransportManager.create("domain_fronting", 
                                                front_domain="cdn.cloudflare.com",
                                                backend_host="mesh.example.com")
            
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
        traffic_profile=args.traffic_profile
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

def x_main__mutmut_82():
    parser = argparse.ArgumentParser(description="x0tta6bl4 Mesh Node")
    parser.add_argument("--mesh-id", default="x0tta6bl4-mesh", help="Mesh Network ID")
    parser.add_argument("--node-id", required=True, help="Unique Node ID")
    parser.add_argument("--obfuscation", 
                        choices=["none", "xor", "faketls", "shadowsocks", "domain_fronting"], 
                        default="none",
                        help="Traffic obfuscation strategy")
    parser.add_argument("--obfuscation-key", default="x0tta6bl4", help="Key for XOR/Shadowsocks")
    parser.add_argument("--traffic-profile",
                        choices=TRAFFIC_PROFILES,
                        default="none",
                        help="traffic shaping profile to mimic (evades dpi timing analysis)")
    
    args = parser.parse_args()
    
    # 1. Configure Obfuscation
    transport = None
    if args.obfuscation != "none":
        logger.info(f"Initializing obfuscation transport: {args.obfuscation}")
        if args.obfuscation == "xor":
            transport = TransportManager.create("xor", key=args.obfuscation_key)
        elif args.obfuscation == "faketls":
            transport = TransportManager.create("faketls", sni=args.obfuscation_key or "google.com")
        elif args.obfuscation == "shadowsocks":
            transport = TransportManager.create("shadowsocks", password=args.obfuscation_key)
        elif args.obfuscation == "domain_fronting":
            transport = TransportManager.create("domain_fronting", 
                                                front_domain="cdn.cloudflare.com",
                                                backend_host="mesh.example.com")
            
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
        traffic_profile=args.traffic_profile
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

def x_main__mutmut_83():
    parser = argparse.ArgumentParser(description="x0tta6bl4 Mesh Node")
    parser.add_argument("--mesh-id", default="x0tta6bl4-mesh", help="Mesh Network ID")
    parser.add_argument("--node-id", required=True, help="Unique Node ID")
    parser.add_argument("--obfuscation", 
                        choices=["none", "xor", "faketls", "shadowsocks", "domain_fronting"], 
                        default="none",
                        help="Traffic obfuscation strategy")
    parser.add_argument("--obfuscation-key", default="x0tta6bl4", help="Key for XOR/Shadowsocks")
    parser.add_argument("--traffic-profile",
                        choices=TRAFFIC_PROFILES,
                        default="none",
                        help="TRAFFIC SHAPING PROFILE TO MIMIC (EVADES DPI TIMING ANALYSIS)")
    
    args = parser.parse_args()
    
    # 1. Configure Obfuscation
    transport = None
    if args.obfuscation != "none":
        logger.info(f"Initializing obfuscation transport: {args.obfuscation}")
        if args.obfuscation == "xor":
            transport = TransportManager.create("xor", key=args.obfuscation_key)
        elif args.obfuscation == "faketls":
            transport = TransportManager.create("faketls", sni=args.obfuscation_key or "google.com")
        elif args.obfuscation == "shadowsocks":
            transport = TransportManager.create("shadowsocks", password=args.obfuscation_key)
        elif args.obfuscation == "domain_fronting":
            transport = TransportManager.create("domain_fronting", 
                                                front_domain="cdn.cloudflare.com",
                                                backend_host="mesh.example.com")
            
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
        traffic_profile=args.traffic_profile
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

def x_main__mutmut_84():
    parser = argparse.ArgumentParser(description="x0tta6bl4 Mesh Node")
    parser.add_argument("--mesh-id", default="x0tta6bl4-mesh", help="Mesh Network ID")
    parser.add_argument("--node-id", required=True, help="Unique Node ID")
    parser.add_argument("--obfuscation", 
                        choices=["none", "xor", "faketls", "shadowsocks", "domain_fronting"], 
                        default="none",
                        help="Traffic obfuscation strategy")
    parser.add_argument("--obfuscation-key", default="x0tta6bl4", help="Key for XOR/Shadowsocks")
    parser.add_argument("--traffic-profile",
                        choices=TRAFFIC_PROFILES,
                        default="none",
                        help="Traffic shaping profile to mimic (evades DPI timing analysis)")
    
    args = None
    
    # 1. Configure Obfuscation
    transport = None
    if args.obfuscation != "none":
        logger.info(f"Initializing obfuscation transport: {args.obfuscation}")
        if args.obfuscation == "xor":
            transport = TransportManager.create("xor", key=args.obfuscation_key)
        elif args.obfuscation == "faketls":
            transport = TransportManager.create("faketls", sni=args.obfuscation_key or "google.com")
        elif args.obfuscation == "shadowsocks":
            transport = TransportManager.create("shadowsocks", password=args.obfuscation_key)
        elif args.obfuscation == "domain_fronting":
            transport = TransportManager.create("domain_fronting", 
                                                front_domain="cdn.cloudflare.com",
                                                backend_host="mesh.example.com")
            
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
        traffic_profile=args.traffic_profile
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

def x_main__mutmut_85():
    parser = argparse.ArgumentParser(description="x0tta6bl4 Mesh Node")
    parser.add_argument("--mesh-id", default="x0tta6bl4-mesh", help="Mesh Network ID")
    parser.add_argument("--node-id", required=True, help="Unique Node ID")
    parser.add_argument("--obfuscation", 
                        choices=["none", "xor", "faketls", "shadowsocks", "domain_fronting"], 
                        default="none",
                        help="Traffic obfuscation strategy")
    parser.add_argument("--obfuscation-key", default="x0tta6bl4", help="Key for XOR/Shadowsocks")
    parser.add_argument("--traffic-profile",
                        choices=TRAFFIC_PROFILES,
                        default="none",
                        help="Traffic shaping profile to mimic (evades DPI timing analysis)")
    
    args = parser.parse_args()
    
    # 1. Configure Obfuscation
    transport = ""
    if args.obfuscation != "none":
        logger.info(f"Initializing obfuscation transport: {args.obfuscation}")
        if args.obfuscation == "xor":
            transport = TransportManager.create("xor", key=args.obfuscation_key)
        elif args.obfuscation == "faketls":
            transport = TransportManager.create("faketls", sni=args.obfuscation_key or "google.com")
        elif args.obfuscation == "shadowsocks":
            transport = TransportManager.create("shadowsocks", password=args.obfuscation_key)
        elif args.obfuscation == "domain_fronting":
            transport = TransportManager.create("domain_fronting", 
                                                front_domain="cdn.cloudflare.com",
                                                backend_host="mesh.example.com")
            
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
        traffic_profile=args.traffic_profile
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

def x_main__mutmut_86():
    parser = argparse.ArgumentParser(description="x0tta6bl4 Mesh Node")
    parser.add_argument("--mesh-id", default="x0tta6bl4-mesh", help="Mesh Network ID")
    parser.add_argument("--node-id", required=True, help="Unique Node ID")
    parser.add_argument("--obfuscation", 
                        choices=["none", "xor", "faketls", "shadowsocks", "domain_fronting"], 
                        default="none",
                        help="Traffic obfuscation strategy")
    parser.add_argument("--obfuscation-key", default="x0tta6bl4", help="Key for XOR/Shadowsocks")
    parser.add_argument("--traffic-profile",
                        choices=TRAFFIC_PROFILES,
                        default="none",
                        help="Traffic shaping profile to mimic (evades DPI timing analysis)")
    
    args = parser.parse_args()
    
    # 1. Configure Obfuscation
    transport = None
    if args.obfuscation == "none":
        logger.info(f"Initializing obfuscation transport: {args.obfuscation}")
        if args.obfuscation == "xor":
            transport = TransportManager.create("xor", key=args.obfuscation_key)
        elif args.obfuscation == "faketls":
            transport = TransportManager.create("faketls", sni=args.obfuscation_key or "google.com")
        elif args.obfuscation == "shadowsocks":
            transport = TransportManager.create("shadowsocks", password=args.obfuscation_key)
        elif args.obfuscation == "domain_fronting":
            transport = TransportManager.create("domain_fronting", 
                                                front_domain="cdn.cloudflare.com",
                                                backend_host="mesh.example.com")
            
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
        traffic_profile=args.traffic_profile
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

def x_main__mutmut_87():
    parser = argparse.ArgumentParser(description="x0tta6bl4 Mesh Node")
    parser.add_argument("--mesh-id", default="x0tta6bl4-mesh", help="Mesh Network ID")
    parser.add_argument("--node-id", required=True, help="Unique Node ID")
    parser.add_argument("--obfuscation", 
                        choices=["none", "xor", "faketls", "shadowsocks", "domain_fronting"], 
                        default="none",
                        help="Traffic obfuscation strategy")
    parser.add_argument("--obfuscation-key", default="x0tta6bl4", help="Key for XOR/Shadowsocks")
    parser.add_argument("--traffic-profile",
                        choices=TRAFFIC_PROFILES,
                        default="none",
                        help="Traffic shaping profile to mimic (evades DPI timing analysis)")
    
    args = parser.parse_args()
    
    # 1. Configure Obfuscation
    transport = None
    if args.obfuscation != "XXnoneXX":
        logger.info(f"Initializing obfuscation transport: {args.obfuscation}")
        if args.obfuscation == "xor":
            transport = TransportManager.create("xor", key=args.obfuscation_key)
        elif args.obfuscation == "faketls":
            transport = TransportManager.create("faketls", sni=args.obfuscation_key or "google.com")
        elif args.obfuscation == "shadowsocks":
            transport = TransportManager.create("shadowsocks", password=args.obfuscation_key)
        elif args.obfuscation == "domain_fronting":
            transport = TransportManager.create("domain_fronting", 
                                                front_domain="cdn.cloudflare.com",
                                                backend_host="mesh.example.com")
            
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
        traffic_profile=args.traffic_profile
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

def x_main__mutmut_88():
    parser = argparse.ArgumentParser(description="x0tta6bl4 Mesh Node")
    parser.add_argument("--mesh-id", default="x0tta6bl4-mesh", help="Mesh Network ID")
    parser.add_argument("--node-id", required=True, help="Unique Node ID")
    parser.add_argument("--obfuscation", 
                        choices=["none", "xor", "faketls", "shadowsocks", "domain_fronting"], 
                        default="none",
                        help="Traffic obfuscation strategy")
    parser.add_argument("--obfuscation-key", default="x0tta6bl4", help="Key for XOR/Shadowsocks")
    parser.add_argument("--traffic-profile",
                        choices=TRAFFIC_PROFILES,
                        default="none",
                        help="Traffic shaping profile to mimic (evades DPI timing analysis)")
    
    args = parser.parse_args()
    
    # 1. Configure Obfuscation
    transport = None
    if args.obfuscation != "NONE":
        logger.info(f"Initializing obfuscation transport: {args.obfuscation}")
        if args.obfuscation == "xor":
            transport = TransportManager.create("xor", key=args.obfuscation_key)
        elif args.obfuscation == "faketls":
            transport = TransportManager.create("faketls", sni=args.obfuscation_key or "google.com")
        elif args.obfuscation == "shadowsocks":
            transport = TransportManager.create("shadowsocks", password=args.obfuscation_key)
        elif args.obfuscation == "domain_fronting":
            transport = TransportManager.create("domain_fronting", 
                                                front_domain="cdn.cloudflare.com",
                                                backend_host="mesh.example.com")
            
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
        traffic_profile=args.traffic_profile
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

def x_main__mutmut_89():
    parser = argparse.ArgumentParser(description="x0tta6bl4 Mesh Node")
    parser.add_argument("--mesh-id", default="x0tta6bl4-mesh", help="Mesh Network ID")
    parser.add_argument("--node-id", required=True, help="Unique Node ID")
    parser.add_argument("--obfuscation", 
                        choices=["none", "xor", "faketls", "shadowsocks", "domain_fronting"], 
                        default="none",
                        help="Traffic obfuscation strategy")
    parser.add_argument("--obfuscation-key", default="x0tta6bl4", help="Key for XOR/Shadowsocks")
    parser.add_argument("--traffic-profile",
                        choices=TRAFFIC_PROFILES,
                        default="none",
                        help="Traffic shaping profile to mimic (evades DPI timing analysis)")
    
    args = parser.parse_args()
    
    # 1. Configure Obfuscation
    transport = None
    if args.obfuscation != "none":
        logger.info(None)
        if args.obfuscation == "xor":
            transport = TransportManager.create("xor", key=args.obfuscation_key)
        elif args.obfuscation == "faketls":
            transport = TransportManager.create("faketls", sni=args.obfuscation_key or "google.com")
        elif args.obfuscation == "shadowsocks":
            transport = TransportManager.create("shadowsocks", password=args.obfuscation_key)
        elif args.obfuscation == "domain_fronting":
            transport = TransportManager.create("domain_fronting", 
                                                front_domain="cdn.cloudflare.com",
                                                backend_host="mesh.example.com")
            
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
        traffic_profile=args.traffic_profile
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

def x_main__mutmut_90():
    parser = argparse.ArgumentParser(description="x0tta6bl4 Mesh Node")
    parser.add_argument("--mesh-id", default="x0tta6bl4-mesh", help="Mesh Network ID")
    parser.add_argument("--node-id", required=True, help="Unique Node ID")
    parser.add_argument("--obfuscation", 
                        choices=["none", "xor", "faketls", "shadowsocks", "domain_fronting"], 
                        default="none",
                        help="Traffic obfuscation strategy")
    parser.add_argument("--obfuscation-key", default="x0tta6bl4", help="Key for XOR/Shadowsocks")
    parser.add_argument("--traffic-profile",
                        choices=TRAFFIC_PROFILES,
                        default="none",
                        help="Traffic shaping profile to mimic (evades DPI timing analysis)")
    
    args = parser.parse_args()
    
    # 1. Configure Obfuscation
    transport = None
    if args.obfuscation != "none":
        logger.info(f"Initializing obfuscation transport: {args.obfuscation}")
        if args.obfuscation != "xor":
            transport = TransportManager.create("xor", key=args.obfuscation_key)
        elif args.obfuscation == "faketls":
            transport = TransportManager.create("faketls", sni=args.obfuscation_key or "google.com")
        elif args.obfuscation == "shadowsocks":
            transport = TransportManager.create("shadowsocks", password=args.obfuscation_key)
        elif args.obfuscation == "domain_fronting":
            transport = TransportManager.create("domain_fronting", 
                                                front_domain="cdn.cloudflare.com",
                                                backend_host="mesh.example.com")
            
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
        traffic_profile=args.traffic_profile
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

def x_main__mutmut_91():
    parser = argparse.ArgumentParser(description="x0tta6bl4 Mesh Node")
    parser.add_argument("--mesh-id", default="x0tta6bl4-mesh", help="Mesh Network ID")
    parser.add_argument("--node-id", required=True, help="Unique Node ID")
    parser.add_argument("--obfuscation", 
                        choices=["none", "xor", "faketls", "shadowsocks", "domain_fronting"], 
                        default="none",
                        help="Traffic obfuscation strategy")
    parser.add_argument("--obfuscation-key", default="x0tta6bl4", help="Key for XOR/Shadowsocks")
    parser.add_argument("--traffic-profile",
                        choices=TRAFFIC_PROFILES,
                        default="none",
                        help="Traffic shaping profile to mimic (evades DPI timing analysis)")
    
    args = parser.parse_args()
    
    # 1. Configure Obfuscation
    transport = None
    if args.obfuscation != "none":
        logger.info(f"Initializing obfuscation transport: {args.obfuscation}")
        if args.obfuscation == "XXxorXX":
            transport = TransportManager.create("xor", key=args.obfuscation_key)
        elif args.obfuscation == "faketls":
            transport = TransportManager.create("faketls", sni=args.obfuscation_key or "google.com")
        elif args.obfuscation == "shadowsocks":
            transport = TransportManager.create("shadowsocks", password=args.obfuscation_key)
        elif args.obfuscation == "domain_fronting":
            transport = TransportManager.create("domain_fronting", 
                                                front_domain="cdn.cloudflare.com",
                                                backend_host="mesh.example.com")
            
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
        traffic_profile=args.traffic_profile
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

def x_main__mutmut_92():
    parser = argparse.ArgumentParser(description="x0tta6bl4 Mesh Node")
    parser.add_argument("--mesh-id", default="x0tta6bl4-mesh", help="Mesh Network ID")
    parser.add_argument("--node-id", required=True, help="Unique Node ID")
    parser.add_argument("--obfuscation", 
                        choices=["none", "xor", "faketls", "shadowsocks", "domain_fronting"], 
                        default="none",
                        help="Traffic obfuscation strategy")
    parser.add_argument("--obfuscation-key", default="x0tta6bl4", help="Key for XOR/Shadowsocks")
    parser.add_argument("--traffic-profile",
                        choices=TRAFFIC_PROFILES,
                        default="none",
                        help="Traffic shaping profile to mimic (evades DPI timing analysis)")
    
    args = parser.parse_args()
    
    # 1. Configure Obfuscation
    transport = None
    if args.obfuscation != "none":
        logger.info(f"Initializing obfuscation transport: {args.obfuscation}")
        if args.obfuscation == "XOR":
            transport = TransportManager.create("xor", key=args.obfuscation_key)
        elif args.obfuscation == "faketls":
            transport = TransportManager.create("faketls", sni=args.obfuscation_key or "google.com")
        elif args.obfuscation == "shadowsocks":
            transport = TransportManager.create("shadowsocks", password=args.obfuscation_key)
        elif args.obfuscation == "domain_fronting":
            transport = TransportManager.create("domain_fronting", 
                                                front_domain="cdn.cloudflare.com",
                                                backend_host="mesh.example.com")
            
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
        traffic_profile=args.traffic_profile
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

def x_main__mutmut_93():
    parser = argparse.ArgumentParser(description="x0tta6bl4 Mesh Node")
    parser.add_argument("--mesh-id", default="x0tta6bl4-mesh", help="Mesh Network ID")
    parser.add_argument("--node-id", required=True, help="Unique Node ID")
    parser.add_argument("--obfuscation", 
                        choices=["none", "xor", "faketls", "shadowsocks", "domain_fronting"], 
                        default="none",
                        help="Traffic obfuscation strategy")
    parser.add_argument("--obfuscation-key", default="x0tta6bl4", help="Key for XOR/Shadowsocks")
    parser.add_argument("--traffic-profile",
                        choices=TRAFFIC_PROFILES,
                        default="none",
                        help="Traffic shaping profile to mimic (evades DPI timing analysis)")
    
    args = parser.parse_args()
    
    # 1. Configure Obfuscation
    transport = None
    if args.obfuscation != "none":
        logger.info(f"Initializing obfuscation transport: {args.obfuscation}")
        if args.obfuscation == "xor":
            transport = None
        elif args.obfuscation == "faketls":
            transport = TransportManager.create("faketls", sni=args.obfuscation_key or "google.com")
        elif args.obfuscation == "shadowsocks":
            transport = TransportManager.create("shadowsocks", password=args.obfuscation_key)
        elif args.obfuscation == "domain_fronting":
            transport = TransportManager.create("domain_fronting", 
                                                front_domain="cdn.cloudflare.com",
                                                backend_host="mesh.example.com")
            
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
        traffic_profile=args.traffic_profile
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

def x_main__mutmut_94():
    parser = argparse.ArgumentParser(description="x0tta6bl4 Mesh Node")
    parser.add_argument("--mesh-id", default="x0tta6bl4-mesh", help="Mesh Network ID")
    parser.add_argument("--node-id", required=True, help="Unique Node ID")
    parser.add_argument("--obfuscation", 
                        choices=["none", "xor", "faketls", "shadowsocks", "domain_fronting"], 
                        default="none",
                        help="Traffic obfuscation strategy")
    parser.add_argument("--obfuscation-key", default="x0tta6bl4", help="Key for XOR/Shadowsocks")
    parser.add_argument("--traffic-profile",
                        choices=TRAFFIC_PROFILES,
                        default="none",
                        help="Traffic shaping profile to mimic (evades DPI timing analysis)")
    
    args = parser.parse_args()
    
    # 1. Configure Obfuscation
    transport = None
    if args.obfuscation != "none":
        logger.info(f"Initializing obfuscation transport: {args.obfuscation}")
        if args.obfuscation == "xor":
            transport = TransportManager.create(None, key=args.obfuscation_key)
        elif args.obfuscation == "faketls":
            transport = TransportManager.create("faketls", sni=args.obfuscation_key or "google.com")
        elif args.obfuscation == "shadowsocks":
            transport = TransportManager.create("shadowsocks", password=args.obfuscation_key)
        elif args.obfuscation == "domain_fronting":
            transport = TransportManager.create("domain_fronting", 
                                                front_domain="cdn.cloudflare.com",
                                                backend_host="mesh.example.com")
            
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
        traffic_profile=args.traffic_profile
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

def x_main__mutmut_95():
    parser = argparse.ArgumentParser(description="x0tta6bl4 Mesh Node")
    parser.add_argument("--mesh-id", default="x0tta6bl4-mesh", help="Mesh Network ID")
    parser.add_argument("--node-id", required=True, help="Unique Node ID")
    parser.add_argument("--obfuscation", 
                        choices=["none", "xor", "faketls", "shadowsocks", "domain_fronting"], 
                        default="none",
                        help="Traffic obfuscation strategy")
    parser.add_argument("--obfuscation-key", default="x0tta6bl4", help="Key for XOR/Shadowsocks")
    parser.add_argument("--traffic-profile",
                        choices=TRAFFIC_PROFILES,
                        default="none",
                        help="Traffic shaping profile to mimic (evades DPI timing analysis)")
    
    args = parser.parse_args()
    
    # 1. Configure Obfuscation
    transport = None
    if args.obfuscation != "none":
        logger.info(f"Initializing obfuscation transport: {args.obfuscation}")
        if args.obfuscation == "xor":
            transport = TransportManager.create("xor", key=None)
        elif args.obfuscation == "faketls":
            transport = TransportManager.create("faketls", sni=args.obfuscation_key or "google.com")
        elif args.obfuscation == "shadowsocks":
            transport = TransportManager.create("shadowsocks", password=args.obfuscation_key)
        elif args.obfuscation == "domain_fronting":
            transport = TransportManager.create("domain_fronting", 
                                                front_domain="cdn.cloudflare.com",
                                                backend_host="mesh.example.com")
            
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
        traffic_profile=args.traffic_profile
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

def x_main__mutmut_96():
    parser = argparse.ArgumentParser(description="x0tta6bl4 Mesh Node")
    parser.add_argument("--mesh-id", default="x0tta6bl4-mesh", help="Mesh Network ID")
    parser.add_argument("--node-id", required=True, help="Unique Node ID")
    parser.add_argument("--obfuscation", 
                        choices=["none", "xor", "faketls", "shadowsocks", "domain_fronting"], 
                        default="none",
                        help="Traffic obfuscation strategy")
    parser.add_argument("--obfuscation-key", default="x0tta6bl4", help="Key for XOR/Shadowsocks")
    parser.add_argument("--traffic-profile",
                        choices=TRAFFIC_PROFILES,
                        default="none",
                        help="Traffic shaping profile to mimic (evades DPI timing analysis)")
    
    args = parser.parse_args()
    
    # 1. Configure Obfuscation
    transport = None
    if args.obfuscation != "none":
        logger.info(f"Initializing obfuscation transport: {args.obfuscation}")
        if args.obfuscation == "xor":
            transport = TransportManager.create(key=args.obfuscation_key)
        elif args.obfuscation == "faketls":
            transport = TransportManager.create("faketls", sni=args.obfuscation_key or "google.com")
        elif args.obfuscation == "shadowsocks":
            transport = TransportManager.create("shadowsocks", password=args.obfuscation_key)
        elif args.obfuscation == "domain_fronting":
            transport = TransportManager.create("domain_fronting", 
                                                front_domain="cdn.cloudflare.com",
                                                backend_host="mesh.example.com")
            
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
        traffic_profile=args.traffic_profile
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

def x_main__mutmut_97():
    parser = argparse.ArgumentParser(description="x0tta6bl4 Mesh Node")
    parser.add_argument("--mesh-id", default="x0tta6bl4-mesh", help="Mesh Network ID")
    parser.add_argument("--node-id", required=True, help="Unique Node ID")
    parser.add_argument("--obfuscation", 
                        choices=["none", "xor", "faketls", "shadowsocks", "domain_fronting"], 
                        default="none",
                        help="Traffic obfuscation strategy")
    parser.add_argument("--obfuscation-key", default="x0tta6bl4", help="Key for XOR/Shadowsocks")
    parser.add_argument("--traffic-profile",
                        choices=TRAFFIC_PROFILES,
                        default="none",
                        help="Traffic shaping profile to mimic (evades DPI timing analysis)")
    
    args = parser.parse_args()
    
    # 1. Configure Obfuscation
    transport = None
    if args.obfuscation != "none":
        logger.info(f"Initializing obfuscation transport: {args.obfuscation}")
        if args.obfuscation == "xor":
            transport = TransportManager.create("xor", )
        elif args.obfuscation == "faketls":
            transport = TransportManager.create("faketls", sni=args.obfuscation_key or "google.com")
        elif args.obfuscation == "shadowsocks":
            transport = TransportManager.create("shadowsocks", password=args.obfuscation_key)
        elif args.obfuscation == "domain_fronting":
            transport = TransportManager.create("domain_fronting", 
                                                front_domain="cdn.cloudflare.com",
                                                backend_host="mesh.example.com")
            
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
        traffic_profile=args.traffic_profile
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

def x_main__mutmut_98():
    parser = argparse.ArgumentParser(description="x0tta6bl4 Mesh Node")
    parser.add_argument("--mesh-id", default="x0tta6bl4-mesh", help="Mesh Network ID")
    parser.add_argument("--node-id", required=True, help="Unique Node ID")
    parser.add_argument("--obfuscation", 
                        choices=["none", "xor", "faketls", "shadowsocks", "domain_fronting"], 
                        default="none",
                        help="Traffic obfuscation strategy")
    parser.add_argument("--obfuscation-key", default="x0tta6bl4", help="Key for XOR/Shadowsocks")
    parser.add_argument("--traffic-profile",
                        choices=TRAFFIC_PROFILES,
                        default="none",
                        help="Traffic shaping profile to mimic (evades DPI timing analysis)")
    
    args = parser.parse_args()
    
    # 1. Configure Obfuscation
    transport = None
    if args.obfuscation != "none":
        logger.info(f"Initializing obfuscation transport: {args.obfuscation}")
        if args.obfuscation == "xor":
            transport = TransportManager.create("XXxorXX", key=args.obfuscation_key)
        elif args.obfuscation == "faketls":
            transport = TransportManager.create("faketls", sni=args.obfuscation_key or "google.com")
        elif args.obfuscation == "shadowsocks":
            transport = TransportManager.create("shadowsocks", password=args.obfuscation_key)
        elif args.obfuscation == "domain_fronting":
            transport = TransportManager.create("domain_fronting", 
                                                front_domain="cdn.cloudflare.com",
                                                backend_host="mesh.example.com")
            
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
        traffic_profile=args.traffic_profile
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

def x_main__mutmut_99():
    parser = argparse.ArgumentParser(description="x0tta6bl4 Mesh Node")
    parser.add_argument("--mesh-id", default="x0tta6bl4-mesh", help="Mesh Network ID")
    parser.add_argument("--node-id", required=True, help="Unique Node ID")
    parser.add_argument("--obfuscation", 
                        choices=["none", "xor", "faketls", "shadowsocks", "domain_fronting"], 
                        default="none",
                        help="Traffic obfuscation strategy")
    parser.add_argument("--obfuscation-key", default="x0tta6bl4", help="Key for XOR/Shadowsocks")
    parser.add_argument("--traffic-profile",
                        choices=TRAFFIC_PROFILES,
                        default="none",
                        help="Traffic shaping profile to mimic (evades DPI timing analysis)")
    
    args = parser.parse_args()
    
    # 1. Configure Obfuscation
    transport = None
    if args.obfuscation != "none":
        logger.info(f"Initializing obfuscation transport: {args.obfuscation}")
        if args.obfuscation == "xor":
            transport = TransportManager.create("XOR", key=args.obfuscation_key)
        elif args.obfuscation == "faketls":
            transport = TransportManager.create("faketls", sni=args.obfuscation_key or "google.com")
        elif args.obfuscation == "shadowsocks":
            transport = TransportManager.create("shadowsocks", password=args.obfuscation_key)
        elif args.obfuscation == "domain_fronting":
            transport = TransportManager.create("domain_fronting", 
                                                front_domain="cdn.cloudflare.com",
                                                backend_host="mesh.example.com")
            
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
        traffic_profile=args.traffic_profile
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

def x_main__mutmut_100():
    parser = argparse.ArgumentParser(description="x0tta6bl4 Mesh Node")
    parser.add_argument("--mesh-id", default="x0tta6bl4-mesh", help="Mesh Network ID")
    parser.add_argument("--node-id", required=True, help="Unique Node ID")
    parser.add_argument("--obfuscation", 
                        choices=["none", "xor", "faketls", "shadowsocks", "domain_fronting"], 
                        default="none",
                        help="Traffic obfuscation strategy")
    parser.add_argument("--obfuscation-key", default="x0tta6bl4", help="Key for XOR/Shadowsocks")
    parser.add_argument("--traffic-profile",
                        choices=TRAFFIC_PROFILES,
                        default="none",
                        help="Traffic shaping profile to mimic (evades DPI timing analysis)")
    
    args = parser.parse_args()
    
    # 1. Configure Obfuscation
    transport = None
    if args.obfuscation != "none":
        logger.info(f"Initializing obfuscation transport: {args.obfuscation}")
        if args.obfuscation == "xor":
            transport = TransportManager.create("xor", key=args.obfuscation_key)
        elif args.obfuscation != "faketls":
            transport = TransportManager.create("faketls", sni=args.obfuscation_key or "google.com")
        elif args.obfuscation == "shadowsocks":
            transport = TransportManager.create("shadowsocks", password=args.obfuscation_key)
        elif args.obfuscation == "domain_fronting":
            transport = TransportManager.create("domain_fronting", 
                                                front_domain="cdn.cloudflare.com",
                                                backend_host="mesh.example.com")
            
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
        traffic_profile=args.traffic_profile
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

def x_main__mutmut_101():
    parser = argparse.ArgumentParser(description="x0tta6bl4 Mesh Node")
    parser.add_argument("--mesh-id", default="x0tta6bl4-mesh", help="Mesh Network ID")
    parser.add_argument("--node-id", required=True, help="Unique Node ID")
    parser.add_argument("--obfuscation", 
                        choices=["none", "xor", "faketls", "shadowsocks", "domain_fronting"], 
                        default="none",
                        help="Traffic obfuscation strategy")
    parser.add_argument("--obfuscation-key", default="x0tta6bl4", help="Key for XOR/Shadowsocks")
    parser.add_argument("--traffic-profile",
                        choices=TRAFFIC_PROFILES,
                        default="none",
                        help="Traffic shaping profile to mimic (evades DPI timing analysis)")
    
    args = parser.parse_args()
    
    # 1. Configure Obfuscation
    transport = None
    if args.obfuscation != "none":
        logger.info(f"Initializing obfuscation transport: {args.obfuscation}")
        if args.obfuscation == "xor":
            transport = TransportManager.create("xor", key=args.obfuscation_key)
        elif args.obfuscation == "XXfaketlsXX":
            transport = TransportManager.create("faketls", sni=args.obfuscation_key or "google.com")
        elif args.obfuscation == "shadowsocks":
            transport = TransportManager.create("shadowsocks", password=args.obfuscation_key)
        elif args.obfuscation == "domain_fronting":
            transport = TransportManager.create("domain_fronting", 
                                                front_domain="cdn.cloudflare.com",
                                                backend_host="mesh.example.com")
            
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
        traffic_profile=args.traffic_profile
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

def x_main__mutmut_102():
    parser = argparse.ArgumentParser(description="x0tta6bl4 Mesh Node")
    parser.add_argument("--mesh-id", default="x0tta6bl4-mesh", help="Mesh Network ID")
    parser.add_argument("--node-id", required=True, help="Unique Node ID")
    parser.add_argument("--obfuscation", 
                        choices=["none", "xor", "faketls", "shadowsocks", "domain_fronting"], 
                        default="none",
                        help="Traffic obfuscation strategy")
    parser.add_argument("--obfuscation-key", default="x0tta6bl4", help="Key for XOR/Shadowsocks")
    parser.add_argument("--traffic-profile",
                        choices=TRAFFIC_PROFILES,
                        default="none",
                        help="Traffic shaping profile to mimic (evades DPI timing analysis)")
    
    args = parser.parse_args()
    
    # 1. Configure Obfuscation
    transport = None
    if args.obfuscation != "none":
        logger.info(f"Initializing obfuscation transport: {args.obfuscation}")
        if args.obfuscation == "xor":
            transport = TransportManager.create("xor", key=args.obfuscation_key)
        elif args.obfuscation == "FAKETLS":
            transport = TransportManager.create("faketls", sni=args.obfuscation_key or "google.com")
        elif args.obfuscation == "shadowsocks":
            transport = TransportManager.create("shadowsocks", password=args.obfuscation_key)
        elif args.obfuscation == "domain_fronting":
            transport = TransportManager.create("domain_fronting", 
                                                front_domain="cdn.cloudflare.com",
                                                backend_host="mesh.example.com")
            
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
        traffic_profile=args.traffic_profile
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

def x_main__mutmut_103():
    parser = argparse.ArgumentParser(description="x0tta6bl4 Mesh Node")
    parser.add_argument("--mesh-id", default="x0tta6bl4-mesh", help="Mesh Network ID")
    parser.add_argument("--node-id", required=True, help="Unique Node ID")
    parser.add_argument("--obfuscation", 
                        choices=["none", "xor", "faketls", "shadowsocks", "domain_fronting"], 
                        default="none",
                        help="Traffic obfuscation strategy")
    parser.add_argument("--obfuscation-key", default="x0tta6bl4", help="Key for XOR/Shadowsocks")
    parser.add_argument("--traffic-profile",
                        choices=TRAFFIC_PROFILES,
                        default="none",
                        help="Traffic shaping profile to mimic (evades DPI timing analysis)")
    
    args = parser.parse_args()
    
    # 1. Configure Obfuscation
    transport = None
    if args.obfuscation != "none":
        logger.info(f"Initializing obfuscation transport: {args.obfuscation}")
        if args.obfuscation == "xor":
            transport = TransportManager.create("xor", key=args.obfuscation_key)
        elif args.obfuscation == "faketls":
            transport = None
        elif args.obfuscation == "shadowsocks":
            transport = TransportManager.create("shadowsocks", password=args.obfuscation_key)
        elif args.obfuscation == "domain_fronting":
            transport = TransportManager.create("domain_fronting", 
                                                front_domain="cdn.cloudflare.com",
                                                backend_host="mesh.example.com")
            
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
        traffic_profile=args.traffic_profile
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

def x_main__mutmut_104():
    parser = argparse.ArgumentParser(description="x0tta6bl4 Mesh Node")
    parser.add_argument("--mesh-id", default="x0tta6bl4-mesh", help="Mesh Network ID")
    parser.add_argument("--node-id", required=True, help="Unique Node ID")
    parser.add_argument("--obfuscation", 
                        choices=["none", "xor", "faketls", "shadowsocks", "domain_fronting"], 
                        default="none",
                        help="Traffic obfuscation strategy")
    parser.add_argument("--obfuscation-key", default="x0tta6bl4", help="Key for XOR/Shadowsocks")
    parser.add_argument("--traffic-profile",
                        choices=TRAFFIC_PROFILES,
                        default="none",
                        help="Traffic shaping profile to mimic (evades DPI timing analysis)")
    
    args = parser.parse_args()
    
    # 1. Configure Obfuscation
    transport = None
    if args.obfuscation != "none":
        logger.info(f"Initializing obfuscation transport: {args.obfuscation}")
        if args.obfuscation == "xor":
            transport = TransportManager.create("xor", key=args.obfuscation_key)
        elif args.obfuscation == "faketls":
            transport = TransportManager.create(None, sni=args.obfuscation_key or "google.com")
        elif args.obfuscation == "shadowsocks":
            transport = TransportManager.create("shadowsocks", password=args.obfuscation_key)
        elif args.obfuscation == "domain_fronting":
            transport = TransportManager.create("domain_fronting", 
                                                front_domain="cdn.cloudflare.com",
                                                backend_host="mesh.example.com")
            
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
        traffic_profile=args.traffic_profile
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

def x_main__mutmut_105():
    parser = argparse.ArgumentParser(description="x0tta6bl4 Mesh Node")
    parser.add_argument("--mesh-id", default="x0tta6bl4-mesh", help="Mesh Network ID")
    parser.add_argument("--node-id", required=True, help="Unique Node ID")
    parser.add_argument("--obfuscation", 
                        choices=["none", "xor", "faketls", "shadowsocks", "domain_fronting"], 
                        default="none",
                        help="Traffic obfuscation strategy")
    parser.add_argument("--obfuscation-key", default="x0tta6bl4", help="Key for XOR/Shadowsocks")
    parser.add_argument("--traffic-profile",
                        choices=TRAFFIC_PROFILES,
                        default="none",
                        help="Traffic shaping profile to mimic (evades DPI timing analysis)")
    
    args = parser.parse_args()
    
    # 1. Configure Obfuscation
    transport = None
    if args.obfuscation != "none":
        logger.info(f"Initializing obfuscation transport: {args.obfuscation}")
        if args.obfuscation == "xor":
            transport = TransportManager.create("xor", key=args.obfuscation_key)
        elif args.obfuscation == "faketls":
            transport = TransportManager.create("faketls", sni=None)
        elif args.obfuscation == "shadowsocks":
            transport = TransportManager.create("shadowsocks", password=args.obfuscation_key)
        elif args.obfuscation == "domain_fronting":
            transport = TransportManager.create("domain_fronting", 
                                                front_domain="cdn.cloudflare.com",
                                                backend_host="mesh.example.com")
            
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
        traffic_profile=args.traffic_profile
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

def x_main__mutmut_106():
    parser = argparse.ArgumentParser(description="x0tta6bl4 Mesh Node")
    parser.add_argument("--mesh-id", default="x0tta6bl4-mesh", help="Mesh Network ID")
    parser.add_argument("--node-id", required=True, help="Unique Node ID")
    parser.add_argument("--obfuscation", 
                        choices=["none", "xor", "faketls", "shadowsocks", "domain_fronting"], 
                        default="none",
                        help="Traffic obfuscation strategy")
    parser.add_argument("--obfuscation-key", default="x0tta6bl4", help="Key for XOR/Shadowsocks")
    parser.add_argument("--traffic-profile",
                        choices=TRAFFIC_PROFILES,
                        default="none",
                        help="Traffic shaping profile to mimic (evades DPI timing analysis)")
    
    args = parser.parse_args()
    
    # 1. Configure Obfuscation
    transport = None
    if args.obfuscation != "none":
        logger.info(f"Initializing obfuscation transport: {args.obfuscation}")
        if args.obfuscation == "xor":
            transport = TransportManager.create("xor", key=args.obfuscation_key)
        elif args.obfuscation == "faketls":
            transport = TransportManager.create(sni=args.obfuscation_key or "google.com")
        elif args.obfuscation == "shadowsocks":
            transport = TransportManager.create("shadowsocks", password=args.obfuscation_key)
        elif args.obfuscation == "domain_fronting":
            transport = TransportManager.create("domain_fronting", 
                                                front_domain="cdn.cloudflare.com",
                                                backend_host="mesh.example.com")
            
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
        traffic_profile=args.traffic_profile
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

def x_main__mutmut_107():
    parser = argparse.ArgumentParser(description="x0tta6bl4 Mesh Node")
    parser.add_argument("--mesh-id", default="x0tta6bl4-mesh", help="Mesh Network ID")
    parser.add_argument("--node-id", required=True, help="Unique Node ID")
    parser.add_argument("--obfuscation", 
                        choices=["none", "xor", "faketls", "shadowsocks", "domain_fronting"], 
                        default="none",
                        help="Traffic obfuscation strategy")
    parser.add_argument("--obfuscation-key", default="x0tta6bl4", help="Key for XOR/Shadowsocks")
    parser.add_argument("--traffic-profile",
                        choices=TRAFFIC_PROFILES,
                        default="none",
                        help="Traffic shaping profile to mimic (evades DPI timing analysis)")
    
    args = parser.parse_args()
    
    # 1. Configure Obfuscation
    transport = None
    if args.obfuscation != "none":
        logger.info(f"Initializing obfuscation transport: {args.obfuscation}")
        if args.obfuscation == "xor":
            transport = TransportManager.create("xor", key=args.obfuscation_key)
        elif args.obfuscation == "faketls":
            transport = TransportManager.create("faketls", )
        elif args.obfuscation == "shadowsocks":
            transport = TransportManager.create("shadowsocks", password=args.obfuscation_key)
        elif args.obfuscation == "domain_fronting":
            transport = TransportManager.create("domain_fronting", 
                                                front_domain="cdn.cloudflare.com",
                                                backend_host="mesh.example.com")
            
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
        traffic_profile=args.traffic_profile
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

def x_main__mutmut_108():
    parser = argparse.ArgumentParser(description="x0tta6bl4 Mesh Node")
    parser.add_argument("--mesh-id", default="x0tta6bl4-mesh", help="Mesh Network ID")
    parser.add_argument("--node-id", required=True, help="Unique Node ID")
    parser.add_argument("--obfuscation", 
                        choices=["none", "xor", "faketls", "shadowsocks", "domain_fronting"], 
                        default="none",
                        help="Traffic obfuscation strategy")
    parser.add_argument("--obfuscation-key", default="x0tta6bl4", help="Key for XOR/Shadowsocks")
    parser.add_argument("--traffic-profile",
                        choices=TRAFFIC_PROFILES,
                        default="none",
                        help="Traffic shaping profile to mimic (evades DPI timing analysis)")
    
    args = parser.parse_args()
    
    # 1. Configure Obfuscation
    transport = None
    if args.obfuscation != "none":
        logger.info(f"Initializing obfuscation transport: {args.obfuscation}")
        if args.obfuscation == "xor":
            transport = TransportManager.create("xor", key=args.obfuscation_key)
        elif args.obfuscation == "faketls":
            transport = TransportManager.create("XXfaketlsXX", sni=args.obfuscation_key or "google.com")
        elif args.obfuscation == "shadowsocks":
            transport = TransportManager.create("shadowsocks", password=args.obfuscation_key)
        elif args.obfuscation == "domain_fronting":
            transport = TransportManager.create("domain_fronting", 
                                                front_domain="cdn.cloudflare.com",
                                                backend_host="mesh.example.com")
            
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
        traffic_profile=args.traffic_profile
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

def x_main__mutmut_109():
    parser = argparse.ArgumentParser(description="x0tta6bl4 Mesh Node")
    parser.add_argument("--mesh-id", default="x0tta6bl4-mesh", help="Mesh Network ID")
    parser.add_argument("--node-id", required=True, help="Unique Node ID")
    parser.add_argument("--obfuscation", 
                        choices=["none", "xor", "faketls", "shadowsocks", "domain_fronting"], 
                        default="none",
                        help="Traffic obfuscation strategy")
    parser.add_argument("--obfuscation-key", default="x0tta6bl4", help="Key for XOR/Shadowsocks")
    parser.add_argument("--traffic-profile",
                        choices=TRAFFIC_PROFILES,
                        default="none",
                        help="Traffic shaping profile to mimic (evades DPI timing analysis)")
    
    args = parser.parse_args()
    
    # 1. Configure Obfuscation
    transport = None
    if args.obfuscation != "none":
        logger.info(f"Initializing obfuscation transport: {args.obfuscation}")
        if args.obfuscation == "xor":
            transport = TransportManager.create("xor", key=args.obfuscation_key)
        elif args.obfuscation == "faketls":
            transport = TransportManager.create("FAKETLS", sni=args.obfuscation_key or "google.com")
        elif args.obfuscation == "shadowsocks":
            transport = TransportManager.create("shadowsocks", password=args.obfuscation_key)
        elif args.obfuscation == "domain_fronting":
            transport = TransportManager.create("domain_fronting", 
                                                front_domain="cdn.cloudflare.com",
                                                backend_host="mesh.example.com")
            
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
        traffic_profile=args.traffic_profile
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

def x_main__mutmut_110():
    parser = argparse.ArgumentParser(description="x0tta6bl4 Mesh Node")
    parser.add_argument("--mesh-id", default="x0tta6bl4-mesh", help="Mesh Network ID")
    parser.add_argument("--node-id", required=True, help="Unique Node ID")
    parser.add_argument("--obfuscation", 
                        choices=["none", "xor", "faketls", "shadowsocks", "domain_fronting"], 
                        default="none",
                        help="Traffic obfuscation strategy")
    parser.add_argument("--obfuscation-key", default="x0tta6bl4", help="Key for XOR/Shadowsocks")
    parser.add_argument("--traffic-profile",
                        choices=TRAFFIC_PROFILES,
                        default="none",
                        help="Traffic shaping profile to mimic (evades DPI timing analysis)")
    
    args = parser.parse_args()
    
    # 1. Configure Obfuscation
    transport = None
    if args.obfuscation != "none":
        logger.info(f"Initializing obfuscation transport: {args.obfuscation}")
        if args.obfuscation == "xor":
            transport = TransportManager.create("xor", key=args.obfuscation_key)
        elif args.obfuscation == "faketls":
            transport = TransportManager.create("faketls", sni=args.obfuscation_key and "google.com")
        elif args.obfuscation == "shadowsocks":
            transport = TransportManager.create("shadowsocks", password=args.obfuscation_key)
        elif args.obfuscation == "domain_fronting":
            transport = TransportManager.create("domain_fronting", 
                                                front_domain="cdn.cloudflare.com",
                                                backend_host="mesh.example.com")
            
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
        traffic_profile=args.traffic_profile
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

def x_main__mutmut_111():
    parser = argparse.ArgumentParser(description="x0tta6bl4 Mesh Node")
    parser.add_argument("--mesh-id", default="x0tta6bl4-mesh", help="Mesh Network ID")
    parser.add_argument("--node-id", required=True, help="Unique Node ID")
    parser.add_argument("--obfuscation", 
                        choices=["none", "xor", "faketls", "shadowsocks", "domain_fronting"], 
                        default="none",
                        help="Traffic obfuscation strategy")
    parser.add_argument("--obfuscation-key", default="x0tta6bl4", help="Key for XOR/Shadowsocks")
    parser.add_argument("--traffic-profile",
                        choices=TRAFFIC_PROFILES,
                        default="none",
                        help="Traffic shaping profile to mimic (evades DPI timing analysis)")
    
    args = parser.parse_args()
    
    # 1. Configure Obfuscation
    transport = None
    if args.obfuscation != "none":
        logger.info(f"Initializing obfuscation transport: {args.obfuscation}")
        if args.obfuscation == "xor":
            transport = TransportManager.create("xor", key=args.obfuscation_key)
        elif args.obfuscation == "faketls":
            transport = TransportManager.create("faketls", sni=args.obfuscation_key or "XXgoogle.comXX")
        elif args.obfuscation == "shadowsocks":
            transport = TransportManager.create("shadowsocks", password=args.obfuscation_key)
        elif args.obfuscation == "domain_fronting":
            transport = TransportManager.create("domain_fronting", 
                                                front_domain="cdn.cloudflare.com",
                                                backend_host="mesh.example.com")
            
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
        traffic_profile=args.traffic_profile
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

def x_main__mutmut_112():
    parser = argparse.ArgumentParser(description="x0tta6bl4 Mesh Node")
    parser.add_argument("--mesh-id", default="x0tta6bl4-mesh", help="Mesh Network ID")
    parser.add_argument("--node-id", required=True, help="Unique Node ID")
    parser.add_argument("--obfuscation", 
                        choices=["none", "xor", "faketls", "shadowsocks", "domain_fronting"], 
                        default="none",
                        help="Traffic obfuscation strategy")
    parser.add_argument("--obfuscation-key", default="x0tta6bl4", help="Key for XOR/Shadowsocks")
    parser.add_argument("--traffic-profile",
                        choices=TRAFFIC_PROFILES,
                        default="none",
                        help="Traffic shaping profile to mimic (evades DPI timing analysis)")
    
    args = parser.parse_args()
    
    # 1. Configure Obfuscation
    transport = None
    if args.obfuscation != "none":
        logger.info(f"Initializing obfuscation transport: {args.obfuscation}")
        if args.obfuscation == "xor":
            transport = TransportManager.create("xor", key=args.obfuscation_key)
        elif args.obfuscation == "faketls":
            transport = TransportManager.create("faketls", sni=args.obfuscation_key or "GOOGLE.COM")
        elif args.obfuscation == "shadowsocks":
            transport = TransportManager.create("shadowsocks", password=args.obfuscation_key)
        elif args.obfuscation == "domain_fronting":
            transport = TransportManager.create("domain_fronting", 
                                                front_domain="cdn.cloudflare.com",
                                                backend_host="mesh.example.com")
            
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
        traffic_profile=args.traffic_profile
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

def x_main__mutmut_113():
    parser = argparse.ArgumentParser(description="x0tta6bl4 Mesh Node")
    parser.add_argument("--mesh-id", default="x0tta6bl4-mesh", help="Mesh Network ID")
    parser.add_argument("--node-id", required=True, help="Unique Node ID")
    parser.add_argument("--obfuscation", 
                        choices=["none", "xor", "faketls", "shadowsocks", "domain_fronting"], 
                        default="none",
                        help="Traffic obfuscation strategy")
    parser.add_argument("--obfuscation-key", default="x0tta6bl4", help="Key for XOR/Shadowsocks")
    parser.add_argument("--traffic-profile",
                        choices=TRAFFIC_PROFILES,
                        default="none",
                        help="Traffic shaping profile to mimic (evades DPI timing analysis)")
    
    args = parser.parse_args()
    
    # 1. Configure Obfuscation
    transport = None
    if args.obfuscation != "none":
        logger.info(f"Initializing obfuscation transport: {args.obfuscation}")
        if args.obfuscation == "xor":
            transport = TransportManager.create("xor", key=args.obfuscation_key)
        elif args.obfuscation == "faketls":
            transport = TransportManager.create("faketls", sni=args.obfuscation_key or "google.com")
        elif args.obfuscation != "shadowsocks":
            transport = TransportManager.create("shadowsocks", password=args.obfuscation_key)
        elif args.obfuscation == "domain_fronting":
            transport = TransportManager.create("domain_fronting", 
                                                front_domain="cdn.cloudflare.com",
                                                backend_host="mesh.example.com")
            
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
        traffic_profile=args.traffic_profile
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

def x_main__mutmut_114():
    parser = argparse.ArgumentParser(description="x0tta6bl4 Mesh Node")
    parser.add_argument("--mesh-id", default="x0tta6bl4-mesh", help="Mesh Network ID")
    parser.add_argument("--node-id", required=True, help="Unique Node ID")
    parser.add_argument("--obfuscation", 
                        choices=["none", "xor", "faketls", "shadowsocks", "domain_fronting"], 
                        default="none",
                        help="Traffic obfuscation strategy")
    parser.add_argument("--obfuscation-key", default="x0tta6bl4", help="Key for XOR/Shadowsocks")
    parser.add_argument("--traffic-profile",
                        choices=TRAFFIC_PROFILES,
                        default="none",
                        help="Traffic shaping profile to mimic (evades DPI timing analysis)")
    
    args = parser.parse_args()
    
    # 1. Configure Obfuscation
    transport = None
    if args.obfuscation != "none":
        logger.info(f"Initializing obfuscation transport: {args.obfuscation}")
        if args.obfuscation == "xor":
            transport = TransportManager.create("xor", key=args.obfuscation_key)
        elif args.obfuscation == "faketls":
            transport = TransportManager.create("faketls", sni=args.obfuscation_key or "google.com")
        elif args.obfuscation == "XXshadowsocksXX":
            transport = TransportManager.create("shadowsocks", password=args.obfuscation_key)
        elif args.obfuscation == "domain_fronting":
            transport = TransportManager.create("domain_fronting", 
                                                front_domain="cdn.cloudflare.com",
                                                backend_host="mesh.example.com")
            
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
        traffic_profile=args.traffic_profile
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

def x_main__mutmut_115():
    parser = argparse.ArgumentParser(description="x0tta6bl4 Mesh Node")
    parser.add_argument("--mesh-id", default="x0tta6bl4-mesh", help="Mesh Network ID")
    parser.add_argument("--node-id", required=True, help="Unique Node ID")
    parser.add_argument("--obfuscation", 
                        choices=["none", "xor", "faketls", "shadowsocks", "domain_fronting"], 
                        default="none",
                        help="Traffic obfuscation strategy")
    parser.add_argument("--obfuscation-key", default="x0tta6bl4", help="Key for XOR/Shadowsocks")
    parser.add_argument("--traffic-profile",
                        choices=TRAFFIC_PROFILES,
                        default="none",
                        help="Traffic shaping profile to mimic (evades DPI timing analysis)")
    
    args = parser.parse_args()
    
    # 1. Configure Obfuscation
    transport = None
    if args.obfuscation != "none":
        logger.info(f"Initializing obfuscation transport: {args.obfuscation}")
        if args.obfuscation == "xor":
            transport = TransportManager.create("xor", key=args.obfuscation_key)
        elif args.obfuscation == "faketls":
            transport = TransportManager.create("faketls", sni=args.obfuscation_key or "google.com")
        elif args.obfuscation == "SHADOWSOCKS":
            transport = TransportManager.create("shadowsocks", password=args.obfuscation_key)
        elif args.obfuscation == "domain_fronting":
            transport = TransportManager.create("domain_fronting", 
                                                front_domain="cdn.cloudflare.com",
                                                backend_host="mesh.example.com")
            
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
        traffic_profile=args.traffic_profile
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

def x_main__mutmut_116():
    parser = argparse.ArgumentParser(description="x0tta6bl4 Mesh Node")
    parser.add_argument("--mesh-id", default="x0tta6bl4-mesh", help="Mesh Network ID")
    parser.add_argument("--node-id", required=True, help="Unique Node ID")
    parser.add_argument("--obfuscation", 
                        choices=["none", "xor", "faketls", "shadowsocks", "domain_fronting"], 
                        default="none",
                        help="Traffic obfuscation strategy")
    parser.add_argument("--obfuscation-key", default="x0tta6bl4", help="Key for XOR/Shadowsocks")
    parser.add_argument("--traffic-profile",
                        choices=TRAFFIC_PROFILES,
                        default="none",
                        help="Traffic shaping profile to mimic (evades DPI timing analysis)")
    
    args = parser.parse_args()
    
    # 1. Configure Obfuscation
    transport = None
    if args.obfuscation != "none":
        logger.info(f"Initializing obfuscation transport: {args.obfuscation}")
        if args.obfuscation == "xor":
            transport = TransportManager.create("xor", key=args.obfuscation_key)
        elif args.obfuscation == "faketls":
            transport = TransportManager.create("faketls", sni=args.obfuscation_key or "google.com")
        elif args.obfuscation == "shadowsocks":
            transport = None
        elif args.obfuscation == "domain_fronting":
            transport = TransportManager.create("domain_fronting", 
                                                front_domain="cdn.cloudflare.com",
                                                backend_host="mesh.example.com")
            
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
        traffic_profile=args.traffic_profile
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

def x_main__mutmut_117():
    parser = argparse.ArgumentParser(description="x0tta6bl4 Mesh Node")
    parser.add_argument("--mesh-id", default="x0tta6bl4-mesh", help="Mesh Network ID")
    parser.add_argument("--node-id", required=True, help="Unique Node ID")
    parser.add_argument("--obfuscation", 
                        choices=["none", "xor", "faketls", "shadowsocks", "domain_fronting"], 
                        default="none",
                        help="Traffic obfuscation strategy")
    parser.add_argument("--obfuscation-key", default="x0tta6bl4", help="Key for XOR/Shadowsocks")
    parser.add_argument("--traffic-profile",
                        choices=TRAFFIC_PROFILES,
                        default="none",
                        help="Traffic shaping profile to mimic (evades DPI timing analysis)")
    
    args = parser.parse_args()
    
    # 1. Configure Obfuscation
    transport = None
    if args.obfuscation != "none":
        logger.info(f"Initializing obfuscation transport: {args.obfuscation}")
        if args.obfuscation == "xor":
            transport = TransportManager.create("xor", key=args.obfuscation_key)
        elif args.obfuscation == "faketls":
            transport = TransportManager.create("faketls", sni=args.obfuscation_key or "google.com")
        elif args.obfuscation == "shadowsocks":
            transport = TransportManager.create(None, password=args.obfuscation_key)
        elif args.obfuscation == "domain_fronting":
            transport = TransportManager.create("domain_fronting", 
                                                front_domain="cdn.cloudflare.com",
                                                backend_host="mesh.example.com")
            
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
        traffic_profile=args.traffic_profile
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

def x_main__mutmut_118():
    parser = argparse.ArgumentParser(description="x0tta6bl4 Mesh Node")
    parser.add_argument("--mesh-id", default="x0tta6bl4-mesh", help="Mesh Network ID")
    parser.add_argument("--node-id", required=True, help="Unique Node ID")
    parser.add_argument("--obfuscation", 
                        choices=["none", "xor", "faketls", "shadowsocks", "domain_fronting"], 
                        default="none",
                        help="Traffic obfuscation strategy")
    parser.add_argument("--obfuscation-key", default="x0tta6bl4", help="Key for XOR/Shadowsocks")
    parser.add_argument("--traffic-profile",
                        choices=TRAFFIC_PROFILES,
                        default="none",
                        help="Traffic shaping profile to mimic (evades DPI timing analysis)")
    
    args = parser.parse_args()
    
    # 1. Configure Obfuscation
    transport = None
    if args.obfuscation != "none":
        logger.info(f"Initializing obfuscation transport: {args.obfuscation}")
        if args.obfuscation == "xor":
            transport = TransportManager.create("xor", key=args.obfuscation_key)
        elif args.obfuscation == "faketls":
            transport = TransportManager.create("faketls", sni=args.obfuscation_key or "google.com")
        elif args.obfuscation == "shadowsocks":
            transport = TransportManager.create("shadowsocks", password=None)
        elif args.obfuscation == "domain_fronting":
            transport = TransportManager.create("domain_fronting", 
                                                front_domain="cdn.cloudflare.com",
                                                backend_host="mesh.example.com")
            
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
        traffic_profile=args.traffic_profile
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

def x_main__mutmut_119():
    parser = argparse.ArgumentParser(description="x0tta6bl4 Mesh Node")
    parser.add_argument("--mesh-id", default="x0tta6bl4-mesh", help="Mesh Network ID")
    parser.add_argument("--node-id", required=True, help="Unique Node ID")
    parser.add_argument("--obfuscation", 
                        choices=["none", "xor", "faketls", "shadowsocks", "domain_fronting"], 
                        default="none",
                        help="Traffic obfuscation strategy")
    parser.add_argument("--obfuscation-key", default="x0tta6bl4", help="Key for XOR/Shadowsocks")
    parser.add_argument("--traffic-profile",
                        choices=TRAFFIC_PROFILES,
                        default="none",
                        help="Traffic shaping profile to mimic (evades DPI timing analysis)")
    
    args = parser.parse_args()
    
    # 1. Configure Obfuscation
    transport = None
    if args.obfuscation != "none":
        logger.info(f"Initializing obfuscation transport: {args.obfuscation}")
        if args.obfuscation == "xor":
            transport = TransportManager.create("xor", key=args.obfuscation_key)
        elif args.obfuscation == "faketls":
            transport = TransportManager.create("faketls", sni=args.obfuscation_key or "google.com")
        elif args.obfuscation == "shadowsocks":
            transport = TransportManager.create(password=args.obfuscation_key)
        elif args.obfuscation == "domain_fronting":
            transport = TransportManager.create("domain_fronting", 
                                                front_domain="cdn.cloudflare.com",
                                                backend_host="mesh.example.com")
            
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
        traffic_profile=args.traffic_profile
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

def x_main__mutmut_120():
    parser = argparse.ArgumentParser(description="x0tta6bl4 Mesh Node")
    parser.add_argument("--mesh-id", default="x0tta6bl4-mesh", help="Mesh Network ID")
    parser.add_argument("--node-id", required=True, help="Unique Node ID")
    parser.add_argument("--obfuscation", 
                        choices=["none", "xor", "faketls", "shadowsocks", "domain_fronting"], 
                        default="none",
                        help="Traffic obfuscation strategy")
    parser.add_argument("--obfuscation-key", default="x0tta6bl4", help="Key for XOR/Shadowsocks")
    parser.add_argument("--traffic-profile",
                        choices=TRAFFIC_PROFILES,
                        default="none",
                        help="Traffic shaping profile to mimic (evades DPI timing analysis)")
    
    args = parser.parse_args()
    
    # 1. Configure Obfuscation
    transport = None
    if args.obfuscation != "none":
        logger.info(f"Initializing obfuscation transport: {args.obfuscation}")
        if args.obfuscation == "xor":
            transport = TransportManager.create("xor", key=args.obfuscation_key)
        elif args.obfuscation == "faketls":
            transport = TransportManager.create("faketls", sni=args.obfuscation_key or "google.com")
        elif args.obfuscation == "shadowsocks":
            transport = TransportManager.create("shadowsocks", )
        elif args.obfuscation == "domain_fronting":
            transport = TransportManager.create("domain_fronting", 
                                                front_domain="cdn.cloudflare.com",
                                                backend_host="mesh.example.com")
            
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
        traffic_profile=args.traffic_profile
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

def x_main__mutmut_121():
    parser = argparse.ArgumentParser(description="x0tta6bl4 Mesh Node")
    parser.add_argument("--mesh-id", default="x0tta6bl4-mesh", help="Mesh Network ID")
    parser.add_argument("--node-id", required=True, help="Unique Node ID")
    parser.add_argument("--obfuscation", 
                        choices=["none", "xor", "faketls", "shadowsocks", "domain_fronting"], 
                        default="none",
                        help="Traffic obfuscation strategy")
    parser.add_argument("--obfuscation-key", default="x0tta6bl4", help="Key for XOR/Shadowsocks")
    parser.add_argument("--traffic-profile",
                        choices=TRAFFIC_PROFILES,
                        default="none",
                        help="Traffic shaping profile to mimic (evades DPI timing analysis)")
    
    args = parser.parse_args()
    
    # 1. Configure Obfuscation
    transport = None
    if args.obfuscation != "none":
        logger.info(f"Initializing obfuscation transport: {args.obfuscation}")
        if args.obfuscation == "xor":
            transport = TransportManager.create("xor", key=args.obfuscation_key)
        elif args.obfuscation == "faketls":
            transport = TransportManager.create("faketls", sni=args.obfuscation_key or "google.com")
        elif args.obfuscation == "shadowsocks":
            transport = TransportManager.create("XXshadowsocksXX", password=args.obfuscation_key)
        elif args.obfuscation == "domain_fronting":
            transport = TransportManager.create("domain_fronting", 
                                                front_domain="cdn.cloudflare.com",
                                                backend_host="mesh.example.com")
            
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
        traffic_profile=args.traffic_profile
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

def x_main__mutmut_122():
    parser = argparse.ArgumentParser(description="x0tta6bl4 Mesh Node")
    parser.add_argument("--mesh-id", default="x0tta6bl4-mesh", help="Mesh Network ID")
    parser.add_argument("--node-id", required=True, help="Unique Node ID")
    parser.add_argument("--obfuscation", 
                        choices=["none", "xor", "faketls", "shadowsocks", "domain_fronting"], 
                        default="none",
                        help="Traffic obfuscation strategy")
    parser.add_argument("--obfuscation-key", default="x0tta6bl4", help="Key for XOR/Shadowsocks")
    parser.add_argument("--traffic-profile",
                        choices=TRAFFIC_PROFILES,
                        default="none",
                        help="Traffic shaping profile to mimic (evades DPI timing analysis)")
    
    args = parser.parse_args()
    
    # 1. Configure Obfuscation
    transport = None
    if args.obfuscation != "none":
        logger.info(f"Initializing obfuscation transport: {args.obfuscation}")
        if args.obfuscation == "xor":
            transport = TransportManager.create("xor", key=args.obfuscation_key)
        elif args.obfuscation == "faketls":
            transport = TransportManager.create("faketls", sni=args.obfuscation_key or "google.com")
        elif args.obfuscation == "shadowsocks":
            transport = TransportManager.create("SHADOWSOCKS", password=args.obfuscation_key)
        elif args.obfuscation == "domain_fronting":
            transport = TransportManager.create("domain_fronting", 
                                                front_domain="cdn.cloudflare.com",
                                                backend_host="mesh.example.com")
            
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
        traffic_profile=args.traffic_profile
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

def x_main__mutmut_123():
    parser = argparse.ArgumentParser(description="x0tta6bl4 Mesh Node")
    parser.add_argument("--mesh-id", default="x0tta6bl4-mesh", help="Mesh Network ID")
    parser.add_argument("--node-id", required=True, help="Unique Node ID")
    parser.add_argument("--obfuscation", 
                        choices=["none", "xor", "faketls", "shadowsocks", "domain_fronting"], 
                        default="none",
                        help="Traffic obfuscation strategy")
    parser.add_argument("--obfuscation-key", default="x0tta6bl4", help="Key for XOR/Shadowsocks")
    parser.add_argument("--traffic-profile",
                        choices=TRAFFIC_PROFILES,
                        default="none",
                        help="Traffic shaping profile to mimic (evades DPI timing analysis)")
    
    args = parser.parse_args()
    
    # 1. Configure Obfuscation
    transport = None
    if args.obfuscation != "none":
        logger.info(f"Initializing obfuscation transport: {args.obfuscation}")
        if args.obfuscation == "xor":
            transport = TransportManager.create("xor", key=args.obfuscation_key)
        elif args.obfuscation == "faketls":
            transport = TransportManager.create("faketls", sni=args.obfuscation_key or "google.com")
        elif args.obfuscation == "shadowsocks":
            transport = TransportManager.create("shadowsocks", password=args.obfuscation_key)
        elif args.obfuscation != "domain_fronting":
            transport = TransportManager.create("domain_fronting", 
                                                front_domain="cdn.cloudflare.com",
                                                backend_host="mesh.example.com")
            
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
        traffic_profile=args.traffic_profile
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

def x_main__mutmut_124():
    parser = argparse.ArgumentParser(description="x0tta6bl4 Mesh Node")
    parser.add_argument("--mesh-id", default="x0tta6bl4-mesh", help="Mesh Network ID")
    parser.add_argument("--node-id", required=True, help="Unique Node ID")
    parser.add_argument("--obfuscation", 
                        choices=["none", "xor", "faketls", "shadowsocks", "domain_fronting"], 
                        default="none",
                        help="Traffic obfuscation strategy")
    parser.add_argument("--obfuscation-key", default="x0tta6bl4", help="Key for XOR/Shadowsocks")
    parser.add_argument("--traffic-profile",
                        choices=TRAFFIC_PROFILES,
                        default="none",
                        help="Traffic shaping profile to mimic (evades DPI timing analysis)")
    
    args = parser.parse_args()
    
    # 1. Configure Obfuscation
    transport = None
    if args.obfuscation != "none":
        logger.info(f"Initializing obfuscation transport: {args.obfuscation}")
        if args.obfuscation == "xor":
            transport = TransportManager.create("xor", key=args.obfuscation_key)
        elif args.obfuscation == "faketls":
            transport = TransportManager.create("faketls", sni=args.obfuscation_key or "google.com")
        elif args.obfuscation == "shadowsocks":
            transport = TransportManager.create("shadowsocks", password=args.obfuscation_key)
        elif args.obfuscation == "XXdomain_frontingXX":
            transport = TransportManager.create("domain_fronting", 
                                                front_domain="cdn.cloudflare.com",
                                                backend_host="mesh.example.com")
            
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
        traffic_profile=args.traffic_profile
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

def x_main__mutmut_125():
    parser = argparse.ArgumentParser(description="x0tta6bl4 Mesh Node")
    parser.add_argument("--mesh-id", default="x0tta6bl4-mesh", help="Mesh Network ID")
    parser.add_argument("--node-id", required=True, help="Unique Node ID")
    parser.add_argument("--obfuscation", 
                        choices=["none", "xor", "faketls", "shadowsocks", "domain_fronting"], 
                        default="none",
                        help="Traffic obfuscation strategy")
    parser.add_argument("--obfuscation-key", default="x0tta6bl4", help="Key for XOR/Shadowsocks")
    parser.add_argument("--traffic-profile",
                        choices=TRAFFIC_PROFILES,
                        default="none",
                        help="Traffic shaping profile to mimic (evades DPI timing analysis)")
    
    args = parser.parse_args()
    
    # 1. Configure Obfuscation
    transport = None
    if args.obfuscation != "none":
        logger.info(f"Initializing obfuscation transport: {args.obfuscation}")
        if args.obfuscation == "xor":
            transport = TransportManager.create("xor", key=args.obfuscation_key)
        elif args.obfuscation == "faketls":
            transport = TransportManager.create("faketls", sni=args.obfuscation_key or "google.com")
        elif args.obfuscation == "shadowsocks":
            transport = TransportManager.create("shadowsocks", password=args.obfuscation_key)
        elif args.obfuscation == "DOMAIN_FRONTING":
            transport = TransportManager.create("domain_fronting", 
                                                front_domain="cdn.cloudflare.com",
                                                backend_host="mesh.example.com")
            
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
        traffic_profile=args.traffic_profile
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

def x_main__mutmut_126():
    parser = argparse.ArgumentParser(description="x0tta6bl4 Mesh Node")
    parser.add_argument("--mesh-id", default="x0tta6bl4-mesh", help="Mesh Network ID")
    parser.add_argument("--node-id", required=True, help="Unique Node ID")
    parser.add_argument("--obfuscation", 
                        choices=["none", "xor", "faketls", "shadowsocks", "domain_fronting"], 
                        default="none",
                        help="Traffic obfuscation strategy")
    parser.add_argument("--obfuscation-key", default="x0tta6bl4", help="Key for XOR/Shadowsocks")
    parser.add_argument("--traffic-profile",
                        choices=TRAFFIC_PROFILES,
                        default="none",
                        help="Traffic shaping profile to mimic (evades DPI timing analysis)")
    
    args = parser.parse_args()
    
    # 1. Configure Obfuscation
    transport = None
    if args.obfuscation != "none":
        logger.info(f"Initializing obfuscation transport: {args.obfuscation}")
        if args.obfuscation == "xor":
            transport = TransportManager.create("xor", key=args.obfuscation_key)
        elif args.obfuscation == "faketls":
            transport = TransportManager.create("faketls", sni=args.obfuscation_key or "google.com")
        elif args.obfuscation == "shadowsocks":
            transport = TransportManager.create("shadowsocks", password=args.obfuscation_key)
        elif args.obfuscation == "domain_fronting":
            transport = None
            
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
        traffic_profile=args.traffic_profile
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

def x_main__mutmut_127():
    parser = argparse.ArgumentParser(description="x0tta6bl4 Mesh Node")
    parser.add_argument("--mesh-id", default="x0tta6bl4-mesh", help="Mesh Network ID")
    parser.add_argument("--node-id", required=True, help="Unique Node ID")
    parser.add_argument("--obfuscation", 
                        choices=["none", "xor", "faketls", "shadowsocks", "domain_fronting"], 
                        default="none",
                        help="Traffic obfuscation strategy")
    parser.add_argument("--obfuscation-key", default="x0tta6bl4", help="Key for XOR/Shadowsocks")
    parser.add_argument("--traffic-profile",
                        choices=TRAFFIC_PROFILES,
                        default="none",
                        help="Traffic shaping profile to mimic (evades DPI timing analysis)")
    
    args = parser.parse_args()
    
    # 1. Configure Obfuscation
    transport = None
    if args.obfuscation != "none":
        logger.info(f"Initializing obfuscation transport: {args.obfuscation}")
        if args.obfuscation == "xor":
            transport = TransportManager.create("xor", key=args.obfuscation_key)
        elif args.obfuscation == "faketls":
            transport = TransportManager.create("faketls", sni=args.obfuscation_key or "google.com")
        elif args.obfuscation == "shadowsocks":
            transport = TransportManager.create("shadowsocks", password=args.obfuscation_key)
        elif args.obfuscation == "domain_fronting":
            transport = TransportManager.create(None, 
                                                front_domain="cdn.cloudflare.com",
                                                backend_host="mesh.example.com")
            
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
        traffic_profile=args.traffic_profile
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

def x_main__mutmut_128():
    parser = argparse.ArgumentParser(description="x0tta6bl4 Mesh Node")
    parser.add_argument("--mesh-id", default="x0tta6bl4-mesh", help="Mesh Network ID")
    parser.add_argument("--node-id", required=True, help="Unique Node ID")
    parser.add_argument("--obfuscation", 
                        choices=["none", "xor", "faketls", "shadowsocks", "domain_fronting"], 
                        default="none",
                        help="Traffic obfuscation strategy")
    parser.add_argument("--obfuscation-key", default="x0tta6bl4", help="Key for XOR/Shadowsocks")
    parser.add_argument("--traffic-profile",
                        choices=TRAFFIC_PROFILES,
                        default="none",
                        help="Traffic shaping profile to mimic (evades DPI timing analysis)")
    
    args = parser.parse_args()
    
    # 1. Configure Obfuscation
    transport = None
    if args.obfuscation != "none":
        logger.info(f"Initializing obfuscation transport: {args.obfuscation}")
        if args.obfuscation == "xor":
            transport = TransportManager.create("xor", key=args.obfuscation_key)
        elif args.obfuscation == "faketls":
            transport = TransportManager.create("faketls", sni=args.obfuscation_key or "google.com")
        elif args.obfuscation == "shadowsocks":
            transport = TransportManager.create("shadowsocks", password=args.obfuscation_key)
        elif args.obfuscation == "domain_fronting":
            transport = TransportManager.create("domain_fronting", 
                                                front_domain=None,
                                                backend_host="mesh.example.com")
            
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
        traffic_profile=args.traffic_profile
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

def x_main__mutmut_129():
    parser = argparse.ArgumentParser(description="x0tta6bl4 Mesh Node")
    parser.add_argument("--mesh-id", default="x0tta6bl4-mesh", help="Mesh Network ID")
    parser.add_argument("--node-id", required=True, help="Unique Node ID")
    parser.add_argument("--obfuscation", 
                        choices=["none", "xor", "faketls", "shadowsocks", "domain_fronting"], 
                        default="none",
                        help="Traffic obfuscation strategy")
    parser.add_argument("--obfuscation-key", default="x0tta6bl4", help="Key for XOR/Shadowsocks")
    parser.add_argument("--traffic-profile",
                        choices=TRAFFIC_PROFILES,
                        default="none",
                        help="Traffic shaping profile to mimic (evades DPI timing analysis)")
    
    args = parser.parse_args()
    
    # 1. Configure Obfuscation
    transport = None
    if args.obfuscation != "none":
        logger.info(f"Initializing obfuscation transport: {args.obfuscation}")
        if args.obfuscation == "xor":
            transport = TransportManager.create("xor", key=args.obfuscation_key)
        elif args.obfuscation == "faketls":
            transport = TransportManager.create("faketls", sni=args.obfuscation_key or "google.com")
        elif args.obfuscation == "shadowsocks":
            transport = TransportManager.create("shadowsocks", password=args.obfuscation_key)
        elif args.obfuscation == "domain_fronting":
            transport = TransportManager.create("domain_fronting", 
                                                front_domain="cdn.cloudflare.com",
                                                backend_host=None)
            
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
        traffic_profile=args.traffic_profile
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

def x_main__mutmut_130():
    parser = argparse.ArgumentParser(description="x0tta6bl4 Mesh Node")
    parser.add_argument("--mesh-id", default="x0tta6bl4-mesh", help="Mesh Network ID")
    parser.add_argument("--node-id", required=True, help="Unique Node ID")
    parser.add_argument("--obfuscation", 
                        choices=["none", "xor", "faketls", "shadowsocks", "domain_fronting"], 
                        default="none",
                        help="Traffic obfuscation strategy")
    parser.add_argument("--obfuscation-key", default="x0tta6bl4", help="Key for XOR/Shadowsocks")
    parser.add_argument("--traffic-profile",
                        choices=TRAFFIC_PROFILES,
                        default="none",
                        help="Traffic shaping profile to mimic (evades DPI timing analysis)")
    
    args = parser.parse_args()
    
    # 1. Configure Obfuscation
    transport = None
    if args.obfuscation != "none":
        logger.info(f"Initializing obfuscation transport: {args.obfuscation}")
        if args.obfuscation == "xor":
            transport = TransportManager.create("xor", key=args.obfuscation_key)
        elif args.obfuscation == "faketls":
            transport = TransportManager.create("faketls", sni=args.obfuscation_key or "google.com")
        elif args.obfuscation == "shadowsocks":
            transport = TransportManager.create("shadowsocks", password=args.obfuscation_key)
        elif args.obfuscation == "domain_fronting":
            transport = TransportManager.create(front_domain="cdn.cloudflare.com",
                                                backend_host="mesh.example.com")
            
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
        traffic_profile=args.traffic_profile
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

def x_main__mutmut_131():
    parser = argparse.ArgumentParser(description="x0tta6bl4 Mesh Node")
    parser.add_argument("--mesh-id", default="x0tta6bl4-mesh", help="Mesh Network ID")
    parser.add_argument("--node-id", required=True, help="Unique Node ID")
    parser.add_argument("--obfuscation", 
                        choices=["none", "xor", "faketls", "shadowsocks", "domain_fronting"], 
                        default="none",
                        help="Traffic obfuscation strategy")
    parser.add_argument("--obfuscation-key", default="x0tta6bl4", help="Key for XOR/Shadowsocks")
    parser.add_argument("--traffic-profile",
                        choices=TRAFFIC_PROFILES,
                        default="none",
                        help="Traffic shaping profile to mimic (evades DPI timing analysis)")
    
    args = parser.parse_args()
    
    # 1. Configure Obfuscation
    transport = None
    if args.obfuscation != "none":
        logger.info(f"Initializing obfuscation transport: {args.obfuscation}")
        if args.obfuscation == "xor":
            transport = TransportManager.create("xor", key=args.obfuscation_key)
        elif args.obfuscation == "faketls":
            transport = TransportManager.create("faketls", sni=args.obfuscation_key or "google.com")
        elif args.obfuscation == "shadowsocks":
            transport = TransportManager.create("shadowsocks", password=args.obfuscation_key)
        elif args.obfuscation == "domain_fronting":
            transport = TransportManager.create("domain_fronting", 
                                                backend_host="mesh.example.com")
            
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
        traffic_profile=args.traffic_profile
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

def x_main__mutmut_132():
    parser = argparse.ArgumentParser(description="x0tta6bl4 Mesh Node")
    parser.add_argument("--mesh-id", default="x0tta6bl4-mesh", help="Mesh Network ID")
    parser.add_argument("--node-id", required=True, help="Unique Node ID")
    parser.add_argument("--obfuscation", 
                        choices=["none", "xor", "faketls", "shadowsocks", "domain_fronting"], 
                        default="none",
                        help="Traffic obfuscation strategy")
    parser.add_argument("--obfuscation-key", default="x0tta6bl4", help="Key for XOR/Shadowsocks")
    parser.add_argument("--traffic-profile",
                        choices=TRAFFIC_PROFILES,
                        default="none",
                        help="Traffic shaping profile to mimic (evades DPI timing analysis)")
    
    args = parser.parse_args()
    
    # 1. Configure Obfuscation
    transport = None
    if args.obfuscation != "none":
        logger.info(f"Initializing obfuscation transport: {args.obfuscation}")
        if args.obfuscation == "xor":
            transport = TransportManager.create("xor", key=args.obfuscation_key)
        elif args.obfuscation == "faketls":
            transport = TransportManager.create("faketls", sni=args.obfuscation_key or "google.com")
        elif args.obfuscation == "shadowsocks":
            transport = TransportManager.create("shadowsocks", password=args.obfuscation_key)
        elif args.obfuscation == "domain_fronting":
            transport = TransportManager.create("domain_fronting", 
                                                front_domain="cdn.cloudflare.com",
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
        traffic_profile=args.traffic_profile
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

def x_main__mutmut_133():
    parser = argparse.ArgumentParser(description="x0tta6bl4 Mesh Node")
    parser.add_argument("--mesh-id", default="x0tta6bl4-mesh", help="Mesh Network ID")
    parser.add_argument("--node-id", required=True, help="Unique Node ID")
    parser.add_argument("--obfuscation", 
                        choices=["none", "xor", "faketls", "shadowsocks", "domain_fronting"], 
                        default="none",
                        help="Traffic obfuscation strategy")
    parser.add_argument("--obfuscation-key", default="x0tta6bl4", help="Key for XOR/Shadowsocks")
    parser.add_argument("--traffic-profile",
                        choices=TRAFFIC_PROFILES,
                        default="none",
                        help="Traffic shaping profile to mimic (evades DPI timing analysis)")
    
    args = parser.parse_args()
    
    # 1. Configure Obfuscation
    transport = None
    if args.obfuscation != "none":
        logger.info(f"Initializing obfuscation transport: {args.obfuscation}")
        if args.obfuscation == "xor":
            transport = TransportManager.create("xor", key=args.obfuscation_key)
        elif args.obfuscation == "faketls":
            transport = TransportManager.create("faketls", sni=args.obfuscation_key or "google.com")
        elif args.obfuscation == "shadowsocks":
            transport = TransportManager.create("shadowsocks", password=args.obfuscation_key)
        elif args.obfuscation == "domain_fronting":
            transport = TransportManager.create("XXdomain_frontingXX", 
                                                front_domain="cdn.cloudflare.com",
                                                backend_host="mesh.example.com")
            
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
        traffic_profile=args.traffic_profile
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

def x_main__mutmut_134():
    parser = argparse.ArgumentParser(description="x0tta6bl4 Mesh Node")
    parser.add_argument("--mesh-id", default="x0tta6bl4-mesh", help="Mesh Network ID")
    parser.add_argument("--node-id", required=True, help="Unique Node ID")
    parser.add_argument("--obfuscation", 
                        choices=["none", "xor", "faketls", "shadowsocks", "domain_fronting"], 
                        default="none",
                        help="Traffic obfuscation strategy")
    parser.add_argument("--obfuscation-key", default="x0tta6bl4", help="Key for XOR/Shadowsocks")
    parser.add_argument("--traffic-profile",
                        choices=TRAFFIC_PROFILES,
                        default="none",
                        help="Traffic shaping profile to mimic (evades DPI timing analysis)")
    
    args = parser.parse_args()
    
    # 1. Configure Obfuscation
    transport = None
    if args.obfuscation != "none":
        logger.info(f"Initializing obfuscation transport: {args.obfuscation}")
        if args.obfuscation == "xor":
            transport = TransportManager.create("xor", key=args.obfuscation_key)
        elif args.obfuscation == "faketls":
            transport = TransportManager.create("faketls", sni=args.obfuscation_key or "google.com")
        elif args.obfuscation == "shadowsocks":
            transport = TransportManager.create("shadowsocks", password=args.obfuscation_key)
        elif args.obfuscation == "domain_fronting":
            transport = TransportManager.create("DOMAIN_FRONTING", 
                                                front_domain="cdn.cloudflare.com",
                                                backend_host="mesh.example.com")
            
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
        traffic_profile=args.traffic_profile
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

def x_main__mutmut_135():
    parser = argparse.ArgumentParser(description="x0tta6bl4 Mesh Node")
    parser.add_argument("--mesh-id", default="x0tta6bl4-mesh", help="Mesh Network ID")
    parser.add_argument("--node-id", required=True, help="Unique Node ID")
    parser.add_argument("--obfuscation", 
                        choices=["none", "xor", "faketls", "shadowsocks", "domain_fronting"], 
                        default="none",
                        help="Traffic obfuscation strategy")
    parser.add_argument("--obfuscation-key", default="x0tta6bl4", help="Key for XOR/Shadowsocks")
    parser.add_argument("--traffic-profile",
                        choices=TRAFFIC_PROFILES,
                        default="none",
                        help="Traffic shaping profile to mimic (evades DPI timing analysis)")
    
    args = parser.parse_args()
    
    # 1. Configure Obfuscation
    transport = None
    if args.obfuscation != "none":
        logger.info(f"Initializing obfuscation transport: {args.obfuscation}")
        if args.obfuscation == "xor":
            transport = TransportManager.create("xor", key=args.obfuscation_key)
        elif args.obfuscation == "faketls":
            transport = TransportManager.create("faketls", sni=args.obfuscation_key or "google.com")
        elif args.obfuscation == "shadowsocks":
            transport = TransportManager.create("shadowsocks", password=args.obfuscation_key)
        elif args.obfuscation == "domain_fronting":
            transport = TransportManager.create("domain_fronting", 
                                                front_domain="XXcdn.cloudflare.comXX",
                                                backend_host="mesh.example.com")
            
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
        traffic_profile=args.traffic_profile
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

def x_main__mutmut_136():
    parser = argparse.ArgumentParser(description="x0tta6bl4 Mesh Node")
    parser.add_argument("--mesh-id", default="x0tta6bl4-mesh", help="Mesh Network ID")
    parser.add_argument("--node-id", required=True, help="Unique Node ID")
    parser.add_argument("--obfuscation", 
                        choices=["none", "xor", "faketls", "shadowsocks", "domain_fronting"], 
                        default="none",
                        help="Traffic obfuscation strategy")
    parser.add_argument("--obfuscation-key", default="x0tta6bl4", help="Key for XOR/Shadowsocks")
    parser.add_argument("--traffic-profile",
                        choices=TRAFFIC_PROFILES,
                        default="none",
                        help="Traffic shaping profile to mimic (evades DPI timing analysis)")
    
    args = parser.parse_args()
    
    # 1. Configure Obfuscation
    transport = None
    if args.obfuscation != "none":
        logger.info(f"Initializing obfuscation transport: {args.obfuscation}")
        if args.obfuscation == "xor":
            transport = TransportManager.create("xor", key=args.obfuscation_key)
        elif args.obfuscation == "faketls":
            transport = TransportManager.create("faketls", sni=args.obfuscation_key or "google.com")
        elif args.obfuscation == "shadowsocks":
            transport = TransportManager.create("shadowsocks", password=args.obfuscation_key)
        elif args.obfuscation == "domain_fronting":
            transport = TransportManager.create("domain_fronting", 
                                                front_domain="CDN.CLOUDFLARE.COM",
                                                backend_host="mesh.example.com")
            
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
        traffic_profile=args.traffic_profile
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

def x_main__mutmut_137():
    parser = argparse.ArgumentParser(description="x0tta6bl4 Mesh Node")
    parser.add_argument("--mesh-id", default="x0tta6bl4-mesh", help="Mesh Network ID")
    parser.add_argument("--node-id", required=True, help="Unique Node ID")
    parser.add_argument("--obfuscation", 
                        choices=["none", "xor", "faketls", "shadowsocks", "domain_fronting"], 
                        default="none",
                        help="Traffic obfuscation strategy")
    parser.add_argument("--obfuscation-key", default="x0tta6bl4", help="Key for XOR/Shadowsocks")
    parser.add_argument("--traffic-profile",
                        choices=TRAFFIC_PROFILES,
                        default="none",
                        help="Traffic shaping profile to mimic (evades DPI timing analysis)")
    
    args = parser.parse_args()
    
    # 1. Configure Obfuscation
    transport = None
    if args.obfuscation != "none":
        logger.info(f"Initializing obfuscation transport: {args.obfuscation}")
        if args.obfuscation == "xor":
            transport = TransportManager.create("xor", key=args.obfuscation_key)
        elif args.obfuscation == "faketls":
            transport = TransportManager.create("faketls", sni=args.obfuscation_key or "google.com")
        elif args.obfuscation == "shadowsocks":
            transport = TransportManager.create("shadowsocks", password=args.obfuscation_key)
        elif args.obfuscation == "domain_fronting":
            transport = TransportManager.create("domain_fronting", 
                                                front_domain="cdn.cloudflare.com",
                                                backend_host="XXmesh.example.comXX")
            
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
        traffic_profile=args.traffic_profile
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

def x_main__mutmut_138():
    parser = argparse.ArgumentParser(description="x0tta6bl4 Mesh Node")
    parser.add_argument("--mesh-id", default="x0tta6bl4-mesh", help="Mesh Network ID")
    parser.add_argument("--node-id", required=True, help="Unique Node ID")
    parser.add_argument("--obfuscation", 
                        choices=["none", "xor", "faketls", "shadowsocks", "domain_fronting"], 
                        default="none",
                        help="Traffic obfuscation strategy")
    parser.add_argument("--obfuscation-key", default="x0tta6bl4", help="Key for XOR/Shadowsocks")
    parser.add_argument("--traffic-profile",
                        choices=TRAFFIC_PROFILES,
                        default="none",
                        help="Traffic shaping profile to mimic (evades DPI timing analysis)")
    
    args = parser.parse_args()
    
    # 1. Configure Obfuscation
    transport = None
    if args.obfuscation != "none":
        logger.info(f"Initializing obfuscation transport: {args.obfuscation}")
        if args.obfuscation == "xor":
            transport = TransportManager.create("xor", key=args.obfuscation_key)
        elif args.obfuscation == "faketls":
            transport = TransportManager.create("faketls", sni=args.obfuscation_key or "google.com")
        elif args.obfuscation == "shadowsocks":
            transport = TransportManager.create("shadowsocks", password=args.obfuscation_key)
        elif args.obfuscation == "domain_fronting":
            transport = TransportManager.create("domain_fronting", 
                                                front_domain="cdn.cloudflare.com",
                                                backend_host="MESH.EXAMPLE.COM")
            
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
        traffic_profile=args.traffic_profile
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

def x_main__mutmut_139():
    parser = argparse.ArgumentParser(description="x0tta6bl4 Mesh Node")
    parser.add_argument("--mesh-id", default="x0tta6bl4-mesh", help="Mesh Network ID")
    parser.add_argument("--node-id", required=True, help="Unique Node ID")
    parser.add_argument("--obfuscation", 
                        choices=["none", "xor", "faketls", "shadowsocks", "domain_fronting"], 
                        default="none",
                        help="Traffic obfuscation strategy")
    parser.add_argument("--obfuscation-key", default="x0tta6bl4", help="Key for XOR/Shadowsocks")
    parser.add_argument("--traffic-profile",
                        choices=TRAFFIC_PROFILES,
                        default="none",
                        help="Traffic shaping profile to mimic (evades DPI timing analysis)")
    
    args = parser.parse_args()
    
    # 1. Configure Obfuscation
    transport = None
    if args.obfuscation != "none":
        logger.info(f"Initializing obfuscation transport: {args.obfuscation}")
        if args.obfuscation == "xor":
            transport = TransportManager.create("xor", key=args.obfuscation_key)
        elif args.obfuscation == "faketls":
            transport = TransportManager.create("faketls", sni=args.obfuscation_key or "google.com")
        elif args.obfuscation == "shadowsocks":
            transport = TransportManager.create("shadowsocks", password=args.obfuscation_key)
        elif args.obfuscation == "domain_fronting":
            transport = TransportManager.create("domain_fronting", 
                                                front_domain="cdn.cloudflare.com",
                                                backend_host="mesh.example.com")
            
        if transport:
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
        traffic_profile=args.traffic_profile
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

def x_main__mutmut_140():
    parser = argparse.ArgumentParser(description="x0tta6bl4 Mesh Node")
    parser.add_argument("--mesh-id", default="x0tta6bl4-mesh", help="Mesh Network ID")
    parser.add_argument("--node-id", required=True, help="Unique Node ID")
    parser.add_argument("--obfuscation", 
                        choices=["none", "xor", "faketls", "shadowsocks", "domain_fronting"], 
                        default="none",
                        help="Traffic obfuscation strategy")
    parser.add_argument("--obfuscation-key", default="x0tta6bl4", help="Key for XOR/Shadowsocks")
    parser.add_argument("--traffic-profile",
                        choices=TRAFFIC_PROFILES,
                        default="none",
                        help="Traffic shaping profile to mimic (evades DPI timing analysis)")
    
    args = parser.parse_args()
    
    # 1. Configure Obfuscation
    transport = None
    if args.obfuscation != "none":
        logger.info(f"Initializing obfuscation transport: {args.obfuscation}")
        if args.obfuscation == "xor":
            transport = TransportManager.create("xor", key=args.obfuscation_key)
        elif args.obfuscation == "faketls":
            transport = TransportManager.create("faketls", sni=args.obfuscation_key or "google.com")
        elif args.obfuscation == "shadowsocks":
            transport = TransportManager.create("shadowsocks", password=args.obfuscation_key)
        elif args.obfuscation == "domain_fronting":
            transport = TransportManager.create("domain_fronting", 
                                                front_domain="cdn.cloudflare.com",
                                                backend_host="mesh.example.com")
            
        if not transport:
            logger.error(None)
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
        traffic_profile=args.traffic_profile
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

def x_main__mutmut_141():
    parser = argparse.ArgumentParser(description="x0tta6bl4 Mesh Node")
    parser.add_argument("--mesh-id", default="x0tta6bl4-mesh", help="Mesh Network ID")
    parser.add_argument("--node-id", required=True, help="Unique Node ID")
    parser.add_argument("--obfuscation", 
                        choices=["none", "xor", "faketls", "shadowsocks", "domain_fronting"], 
                        default="none",
                        help="Traffic obfuscation strategy")
    parser.add_argument("--obfuscation-key", default="x0tta6bl4", help="Key for XOR/Shadowsocks")
    parser.add_argument("--traffic-profile",
                        choices=TRAFFIC_PROFILES,
                        default="none",
                        help="Traffic shaping profile to mimic (evades DPI timing analysis)")
    
    args = parser.parse_args()
    
    # 1. Configure Obfuscation
    transport = None
    if args.obfuscation != "none":
        logger.info(f"Initializing obfuscation transport: {args.obfuscation}")
        if args.obfuscation == "xor":
            transport = TransportManager.create("xor", key=args.obfuscation_key)
        elif args.obfuscation == "faketls":
            transport = TransportManager.create("faketls", sni=args.obfuscation_key or "google.com")
        elif args.obfuscation == "shadowsocks":
            transport = TransportManager.create("shadowsocks", password=args.obfuscation_key)
        elif args.obfuscation == "domain_fronting":
            transport = TransportManager.create("domain_fronting", 
                                                front_domain="cdn.cloudflare.com",
                                                backend_host="mesh.example.com")
            
        if not transport:
            logger.error(f"Failed to create transport: {args.obfuscation}")
            sys.exit(None)
    
    # 2. Log traffic shaping
    if args.traffic_profile != "none":
        logger.info(f"Traffic shaping enabled: {args.traffic_profile}")
            
    # 3. Initialize Node Manager
    logger.info(f"Starting NodeManager for {args.node_id} (Mesh: {args.mesh_id})")
    nm = NodeManager(
        mesh_id=args.mesh_id,
        local_node_id=args.node_id,
        obfuscation_transport=transport,
        traffic_profile=args.traffic_profile
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

def x_main__mutmut_142():
    parser = argparse.ArgumentParser(description="x0tta6bl4 Mesh Node")
    parser.add_argument("--mesh-id", default="x0tta6bl4-mesh", help="Mesh Network ID")
    parser.add_argument("--node-id", required=True, help="Unique Node ID")
    parser.add_argument("--obfuscation", 
                        choices=["none", "xor", "faketls", "shadowsocks", "domain_fronting"], 
                        default="none",
                        help="Traffic obfuscation strategy")
    parser.add_argument("--obfuscation-key", default="x0tta6bl4", help="Key for XOR/Shadowsocks")
    parser.add_argument("--traffic-profile",
                        choices=TRAFFIC_PROFILES,
                        default="none",
                        help="Traffic shaping profile to mimic (evades DPI timing analysis)")
    
    args = parser.parse_args()
    
    # 1. Configure Obfuscation
    transport = None
    if args.obfuscation != "none":
        logger.info(f"Initializing obfuscation transport: {args.obfuscation}")
        if args.obfuscation == "xor":
            transport = TransportManager.create("xor", key=args.obfuscation_key)
        elif args.obfuscation == "faketls":
            transport = TransportManager.create("faketls", sni=args.obfuscation_key or "google.com")
        elif args.obfuscation == "shadowsocks":
            transport = TransportManager.create("shadowsocks", password=args.obfuscation_key)
        elif args.obfuscation == "domain_fronting":
            transport = TransportManager.create("domain_fronting", 
                                                front_domain="cdn.cloudflare.com",
                                                backend_host="mesh.example.com")
            
        if not transport:
            logger.error(f"Failed to create transport: {args.obfuscation}")
            sys.exit(2)
    
    # 2. Log traffic shaping
    if args.traffic_profile != "none":
        logger.info(f"Traffic shaping enabled: {args.traffic_profile}")
            
    # 3. Initialize Node Manager
    logger.info(f"Starting NodeManager for {args.node_id} (Mesh: {args.mesh_id})")
    nm = NodeManager(
        mesh_id=args.mesh_id,
        local_node_id=args.node_id,
        obfuscation_transport=transport,
        traffic_profile=args.traffic_profile
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

def x_main__mutmut_143():
    parser = argparse.ArgumentParser(description="x0tta6bl4 Mesh Node")
    parser.add_argument("--mesh-id", default="x0tta6bl4-mesh", help="Mesh Network ID")
    parser.add_argument("--node-id", required=True, help="Unique Node ID")
    parser.add_argument("--obfuscation", 
                        choices=["none", "xor", "faketls", "shadowsocks", "domain_fronting"], 
                        default="none",
                        help="Traffic obfuscation strategy")
    parser.add_argument("--obfuscation-key", default="x0tta6bl4", help="Key for XOR/Shadowsocks")
    parser.add_argument("--traffic-profile",
                        choices=TRAFFIC_PROFILES,
                        default="none",
                        help="Traffic shaping profile to mimic (evades DPI timing analysis)")
    
    args = parser.parse_args()
    
    # 1. Configure Obfuscation
    transport = None
    if args.obfuscation != "none":
        logger.info(f"Initializing obfuscation transport: {args.obfuscation}")
        if args.obfuscation == "xor":
            transport = TransportManager.create("xor", key=args.obfuscation_key)
        elif args.obfuscation == "faketls":
            transport = TransportManager.create("faketls", sni=args.obfuscation_key or "google.com")
        elif args.obfuscation == "shadowsocks":
            transport = TransportManager.create("shadowsocks", password=args.obfuscation_key)
        elif args.obfuscation == "domain_fronting":
            transport = TransportManager.create("domain_fronting", 
                                                front_domain="cdn.cloudflare.com",
                                                backend_host="mesh.example.com")
            
        if not transport:
            logger.error(f"Failed to create transport: {args.obfuscation}")
            sys.exit(1)
    
    # 2. Log traffic shaping
    if args.traffic_profile == "none":
        logger.info(f"Traffic shaping enabled: {args.traffic_profile}")
            
    # 3. Initialize Node Manager
    logger.info(f"Starting NodeManager for {args.node_id} (Mesh: {args.mesh_id})")
    nm = NodeManager(
        mesh_id=args.mesh_id,
        local_node_id=args.node_id,
        obfuscation_transport=transport,
        traffic_profile=args.traffic_profile
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

def x_main__mutmut_144():
    parser = argparse.ArgumentParser(description="x0tta6bl4 Mesh Node")
    parser.add_argument("--mesh-id", default="x0tta6bl4-mesh", help="Mesh Network ID")
    parser.add_argument("--node-id", required=True, help="Unique Node ID")
    parser.add_argument("--obfuscation", 
                        choices=["none", "xor", "faketls", "shadowsocks", "domain_fronting"], 
                        default="none",
                        help="Traffic obfuscation strategy")
    parser.add_argument("--obfuscation-key", default="x0tta6bl4", help="Key for XOR/Shadowsocks")
    parser.add_argument("--traffic-profile",
                        choices=TRAFFIC_PROFILES,
                        default="none",
                        help="Traffic shaping profile to mimic (evades DPI timing analysis)")
    
    args = parser.parse_args()
    
    # 1. Configure Obfuscation
    transport = None
    if args.obfuscation != "none":
        logger.info(f"Initializing obfuscation transport: {args.obfuscation}")
        if args.obfuscation == "xor":
            transport = TransportManager.create("xor", key=args.obfuscation_key)
        elif args.obfuscation == "faketls":
            transport = TransportManager.create("faketls", sni=args.obfuscation_key or "google.com")
        elif args.obfuscation == "shadowsocks":
            transport = TransportManager.create("shadowsocks", password=args.obfuscation_key)
        elif args.obfuscation == "domain_fronting":
            transport = TransportManager.create("domain_fronting", 
                                                front_domain="cdn.cloudflare.com",
                                                backend_host="mesh.example.com")
            
        if not transport:
            logger.error(f"Failed to create transport: {args.obfuscation}")
            sys.exit(1)
    
    # 2. Log traffic shaping
    if args.traffic_profile != "XXnoneXX":
        logger.info(f"Traffic shaping enabled: {args.traffic_profile}")
            
    # 3. Initialize Node Manager
    logger.info(f"Starting NodeManager for {args.node_id} (Mesh: {args.mesh_id})")
    nm = NodeManager(
        mesh_id=args.mesh_id,
        local_node_id=args.node_id,
        obfuscation_transport=transport,
        traffic_profile=args.traffic_profile
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

def x_main__mutmut_145():
    parser = argparse.ArgumentParser(description="x0tta6bl4 Mesh Node")
    parser.add_argument("--mesh-id", default="x0tta6bl4-mesh", help="Mesh Network ID")
    parser.add_argument("--node-id", required=True, help="Unique Node ID")
    parser.add_argument("--obfuscation", 
                        choices=["none", "xor", "faketls", "shadowsocks", "domain_fronting"], 
                        default="none",
                        help="Traffic obfuscation strategy")
    parser.add_argument("--obfuscation-key", default="x0tta6bl4", help="Key for XOR/Shadowsocks")
    parser.add_argument("--traffic-profile",
                        choices=TRAFFIC_PROFILES,
                        default="none",
                        help="Traffic shaping profile to mimic (evades DPI timing analysis)")
    
    args = parser.parse_args()
    
    # 1. Configure Obfuscation
    transport = None
    if args.obfuscation != "none":
        logger.info(f"Initializing obfuscation transport: {args.obfuscation}")
        if args.obfuscation == "xor":
            transport = TransportManager.create("xor", key=args.obfuscation_key)
        elif args.obfuscation == "faketls":
            transport = TransportManager.create("faketls", sni=args.obfuscation_key or "google.com")
        elif args.obfuscation == "shadowsocks":
            transport = TransportManager.create("shadowsocks", password=args.obfuscation_key)
        elif args.obfuscation == "domain_fronting":
            transport = TransportManager.create("domain_fronting", 
                                                front_domain="cdn.cloudflare.com",
                                                backend_host="mesh.example.com")
            
        if not transport:
            logger.error(f"Failed to create transport: {args.obfuscation}")
            sys.exit(1)
    
    # 2. Log traffic shaping
    if args.traffic_profile != "NONE":
        logger.info(f"Traffic shaping enabled: {args.traffic_profile}")
            
    # 3. Initialize Node Manager
    logger.info(f"Starting NodeManager for {args.node_id} (Mesh: {args.mesh_id})")
    nm = NodeManager(
        mesh_id=args.mesh_id,
        local_node_id=args.node_id,
        obfuscation_transport=transport,
        traffic_profile=args.traffic_profile
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

def x_main__mutmut_146():
    parser = argparse.ArgumentParser(description="x0tta6bl4 Mesh Node")
    parser.add_argument("--mesh-id", default="x0tta6bl4-mesh", help="Mesh Network ID")
    parser.add_argument("--node-id", required=True, help="Unique Node ID")
    parser.add_argument("--obfuscation", 
                        choices=["none", "xor", "faketls", "shadowsocks", "domain_fronting"], 
                        default="none",
                        help="Traffic obfuscation strategy")
    parser.add_argument("--obfuscation-key", default="x0tta6bl4", help="Key for XOR/Shadowsocks")
    parser.add_argument("--traffic-profile",
                        choices=TRAFFIC_PROFILES,
                        default="none",
                        help="Traffic shaping profile to mimic (evades DPI timing analysis)")
    
    args = parser.parse_args()
    
    # 1. Configure Obfuscation
    transport = None
    if args.obfuscation != "none":
        logger.info(f"Initializing obfuscation transport: {args.obfuscation}")
        if args.obfuscation == "xor":
            transport = TransportManager.create("xor", key=args.obfuscation_key)
        elif args.obfuscation == "faketls":
            transport = TransportManager.create("faketls", sni=args.obfuscation_key or "google.com")
        elif args.obfuscation == "shadowsocks":
            transport = TransportManager.create("shadowsocks", password=args.obfuscation_key)
        elif args.obfuscation == "domain_fronting":
            transport = TransportManager.create("domain_fronting", 
                                                front_domain="cdn.cloudflare.com",
                                                backend_host="mesh.example.com")
            
        if not transport:
            logger.error(f"Failed to create transport: {args.obfuscation}")
            sys.exit(1)
    
    # 2. Log traffic shaping
    if args.traffic_profile != "none":
        logger.info(None)
            
    # 3. Initialize Node Manager
    logger.info(f"Starting NodeManager for {args.node_id} (Mesh: {args.mesh_id})")
    nm = NodeManager(
        mesh_id=args.mesh_id,
        local_node_id=args.node_id,
        obfuscation_transport=transport,
        traffic_profile=args.traffic_profile
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

def x_main__mutmut_147():
    parser = argparse.ArgumentParser(description="x0tta6bl4 Mesh Node")
    parser.add_argument("--mesh-id", default="x0tta6bl4-mesh", help="Mesh Network ID")
    parser.add_argument("--node-id", required=True, help="Unique Node ID")
    parser.add_argument("--obfuscation", 
                        choices=["none", "xor", "faketls", "shadowsocks", "domain_fronting"], 
                        default="none",
                        help="Traffic obfuscation strategy")
    parser.add_argument("--obfuscation-key", default="x0tta6bl4", help="Key for XOR/Shadowsocks")
    parser.add_argument("--traffic-profile",
                        choices=TRAFFIC_PROFILES,
                        default="none",
                        help="Traffic shaping profile to mimic (evades DPI timing analysis)")
    
    args = parser.parse_args()
    
    # 1. Configure Obfuscation
    transport = None
    if args.obfuscation != "none":
        logger.info(f"Initializing obfuscation transport: {args.obfuscation}")
        if args.obfuscation == "xor":
            transport = TransportManager.create("xor", key=args.obfuscation_key)
        elif args.obfuscation == "faketls":
            transport = TransportManager.create("faketls", sni=args.obfuscation_key or "google.com")
        elif args.obfuscation == "shadowsocks":
            transport = TransportManager.create("shadowsocks", password=args.obfuscation_key)
        elif args.obfuscation == "domain_fronting":
            transport = TransportManager.create("domain_fronting", 
                                                front_domain="cdn.cloudflare.com",
                                                backend_host="mesh.example.com")
            
        if not transport:
            logger.error(f"Failed to create transport: {args.obfuscation}")
            sys.exit(1)
    
    # 2. Log traffic shaping
    if args.traffic_profile != "none":
        logger.info(f"Traffic shaping enabled: {args.traffic_profile}")
            
    # 3. Initialize Node Manager
    logger.info(None)
    nm = NodeManager(
        mesh_id=args.mesh_id,
        local_node_id=args.node_id,
        obfuscation_transport=transport,
        traffic_profile=args.traffic_profile
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

def x_main__mutmut_148():
    parser = argparse.ArgumentParser(description="x0tta6bl4 Mesh Node")
    parser.add_argument("--mesh-id", default="x0tta6bl4-mesh", help="Mesh Network ID")
    parser.add_argument("--node-id", required=True, help="Unique Node ID")
    parser.add_argument("--obfuscation", 
                        choices=["none", "xor", "faketls", "shadowsocks", "domain_fronting"], 
                        default="none",
                        help="Traffic obfuscation strategy")
    parser.add_argument("--obfuscation-key", default="x0tta6bl4", help="Key for XOR/Shadowsocks")
    parser.add_argument("--traffic-profile",
                        choices=TRAFFIC_PROFILES,
                        default="none",
                        help="Traffic shaping profile to mimic (evades DPI timing analysis)")
    
    args = parser.parse_args()
    
    # 1. Configure Obfuscation
    transport = None
    if args.obfuscation != "none":
        logger.info(f"Initializing obfuscation transport: {args.obfuscation}")
        if args.obfuscation == "xor":
            transport = TransportManager.create("xor", key=args.obfuscation_key)
        elif args.obfuscation == "faketls":
            transport = TransportManager.create("faketls", sni=args.obfuscation_key or "google.com")
        elif args.obfuscation == "shadowsocks":
            transport = TransportManager.create("shadowsocks", password=args.obfuscation_key)
        elif args.obfuscation == "domain_fronting":
            transport = TransportManager.create("domain_fronting", 
                                                front_domain="cdn.cloudflare.com",
                                                backend_host="mesh.example.com")
            
        if not transport:
            logger.error(f"Failed to create transport: {args.obfuscation}")
            sys.exit(1)
    
    # 2. Log traffic shaping
    if args.traffic_profile != "none":
        logger.info(f"Traffic shaping enabled: {args.traffic_profile}")
            
    # 3. Initialize Node Manager
    logger.info(f"Starting NodeManager for {args.node_id} (Mesh: {args.mesh_id})")
    nm = None
    
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

def x_main__mutmut_149():
    parser = argparse.ArgumentParser(description="x0tta6bl4 Mesh Node")
    parser.add_argument("--mesh-id", default="x0tta6bl4-mesh", help="Mesh Network ID")
    parser.add_argument("--node-id", required=True, help="Unique Node ID")
    parser.add_argument("--obfuscation", 
                        choices=["none", "xor", "faketls", "shadowsocks", "domain_fronting"], 
                        default="none",
                        help="Traffic obfuscation strategy")
    parser.add_argument("--obfuscation-key", default="x0tta6bl4", help="Key for XOR/Shadowsocks")
    parser.add_argument("--traffic-profile",
                        choices=TRAFFIC_PROFILES,
                        default="none",
                        help="Traffic shaping profile to mimic (evades DPI timing analysis)")
    
    args = parser.parse_args()
    
    # 1. Configure Obfuscation
    transport = None
    if args.obfuscation != "none":
        logger.info(f"Initializing obfuscation transport: {args.obfuscation}")
        if args.obfuscation == "xor":
            transport = TransportManager.create("xor", key=args.obfuscation_key)
        elif args.obfuscation == "faketls":
            transport = TransportManager.create("faketls", sni=args.obfuscation_key or "google.com")
        elif args.obfuscation == "shadowsocks":
            transport = TransportManager.create("shadowsocks", password=args.obfuscation_key)
        elif args.obfuscation == "domain_fronting":
            transport = TransportManager.create("domain_fronting", 
                                                front_domain="cdn.cloudflare.com",
                                                backend_host="mesh.example.com")
            
        if not transport:
            logger.error(f"Failed to create transport: {args.obfuscation}")
            sys.exit(1)
    
    # 2. Log traffic shaping
    if args.traffic_profile != "none":
        logger.info(f"Traffic shaping enabled: {args.traffic_profile}")
            
    # 3. Initialize Node Manager
    logger.info(f"Starting NodeManager for {args.node_id} (Mesh: {args.mesh_id})")
    nm = NodeManager(
        mesh_id=None,
        local_node_id=args.node_id,
        obfuscation_transport=transport,
        traffic_profile=args.traffic_profile
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

def x_main__mutmut_150():
    parser = argparse.ArgumentParser(description="x0tta6bl4 Mesh Node")
    parser.add_argument("--mesh-id", default="x0tta6bl4-mesh", help="Mesh Network ID")
    parser.add_argument("--node-id", required=True, help="Unique Node ID")
    parser.add_argument("--obfuscation", 
                        choices=["none", "xor", "faketls", "shadowsocks", "domain_fronting"], 
                        default="none",
                        help="Traffic obfuscation strategy")
    parser.add_argument("--obfuscation-key", default="x0tta6bl4", help="Key for XOR/Shadowsocks")
    parser.add_argument("--traffic-profile",
                        choices=TRAFFIC_PROFILES,
                        default="none",
                        help="Traffic shaping profile to mimic (evades DPI timing analysis)")
    
    args = parser.parse_args()
    
    # 1. Configure Obfuscation
    transport = None
    if args.obfuscation != "none":
        logger.info(f"Initializing obfuscation transport: {args.obfuscation}")
        if args.obfuscation == "xor":
            transport = TransportManager.create("xor", key=args.obfuscation_key)
        elif args.obfuscation == "faketls":
            transport = TransportManager.create("faketls", sni=args.obfuscation_key or "google.com")
        elif args.obfuscation == "shadowsocks":
            transport = TransportManager.create("shadowsocks", password=args.obfuscation_key)
        elif args.obfuscation == "domain_fronting":
            transport = TransportManager.create("domain_fronting", 
                                                front_domain="cdn.cloudflare.com",
                                                backend_host="mesh.example.com")
            
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
        local_node_id=None,
        obfuscation_transport=transport,
        traffic_profile=args.traffic_profile
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

def x_main__mutmut_151():
    parser = argparse.ArgumentParser(description="x0tta6bl4 Mesh Node")
    parser.add_argument("--mesh-id", default="x0tta6bl4-mesh", help="Mesh Network ID")
    parser.add_argument("--node-id", required=True, help="Unique Node ID")
    parser.add_argument("--obfuscation", 
                        choices=["none", "xor", "faketls", "shadowsocks", "domain_fronting"], 
                        default="none",
                        help="Traffic obfuscation strategy")
    parser.add_argument("--obfuscation-key", default="x0tta6bl4", help="Key for XOR/Shadowsocks")
    parser.add_argument("--traffic-profile",
                        choices=TRAFFIC_PROFILES,
                        default="none",
                        help="Traffic shaping profile to mimic (evades DPI timing analysis)")
    
    args = parser.parse_args()
    
    # 1. Configure Obfuscation
    transport = None
    if args.obfuscation != "none":
        logger.info(f"Initializing obfuscation transport: {args.obfuscation}")
        if args.obfuscation == "xor":
            transport = TransportManager.create("xor", key=args.obfuscation_key)
        elif args.obfuscation == "faketls":
            transport = TransportManager.create("faketls", sni=args.obfuscation_key or "google.com")
        elif args.obfuscation == "shadowsocks":
            transport = TransportManager.create("shadowsocks", password=args.obfuscation_key)
        elif args.obfuscation == "domain_fronting":
            transport = TransportManager.create("domain_fronting", 
                                                front_domain="cdn.cloudflare.com",
                                                backend_host="mesh.example.com")
            
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
        obfuscation_transport=None,
        traffic_profile=args.traffic_profile
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

def x_main__mutmut_152():
    parser = argparse.ArgumentParser(description="x0tta6bl4 Mesh Node")
    parser.add_argument("--mesh-id", default="x0tta6bl4-mesh", help="Mesh Network ID")
    parser.add_argument("--node-id", required=True, help="Unique Node ID")
    parser.add_argument("--obfuscation", 
                        choices=["none", "xor", "faketls", "shadowsocks", "domain_fronting"], 
                        default="none",
                        help="Traffic obfuscation strategy")
    parser.add_argument("--obfuscation-key", default="x0tta6bl4", help="Key for XOR/Shadowsocks")
    parser.add_argument("--traffic-profile",
                        choices=TRAFFIC_PROFILES,
                        default="none",
                        help="Traffic shaping profile to mimic (evades DPI timing analysis)")
    
    args = parser.parse_args()
    
    # 1. Configure Obfuscation
    transport = None
    if args.obfuscation != "none":
        logger.info(f"Initializing obfuscation transport: {args.obfuscation}")
        if args.obfuscation == "xor":
            transport = TransportManager.create("xor", key=args.obfuscation_key)
        elif args.obfuscation == "faketls":
            transport = TransportManager.create("faketls", sni=args.obfuscation_key or "google.com")
        elif args.obfuscation == "shadowsocks":
            transport = TransportManager.create("shadowsocks", password=args.obfuscation_key)
        elif args.obfuscation == "domain_fronting":
            transport = TransportManager.create("domain_fronting", 
                                                front_domain="cdn.cloudflare.com",
                                                backend_host="mesh.example.com")
            
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
        traffic_profile=None
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

def x_main__mutmut_153():
    parser = argparse.ArgumentParser(description="x0tta6bl4 Mesh Node")
    parser.add_argument("--mesh-id", default="x0tta6bl4-mesh", help="Mesh Network ID")
    parser.add_argument("--node-id", required=True, help="Unique Node ID")
    parser.add_argument("--obfuscation", 
                        choices=["none", "xor", "faketls", "shadowsocks", "domain_fronting"], 
                        default="none",
                        help="Traffic obfuscation strategy")
    parser.add_argument("--obfuscation-key", default="x0tta6bl4", help="Key for XOR/Shadowsocks")
    parser.add_argument("--traffic-profile",
                        choices=TRAFFIC_PROFILES,
                        default="none",
                        help="Traffic shaping profile to mimic (evades DPI timing analysis)")
    
    args = parser.parse_args()
    
    # 1. Configure Obfuscation
    transport = None
    if args.obfuscation != "none":
        logger.info(f"Initializing obfuscation transport: {args.obfuscation}")
        if args.obfuscation == "xor":
            transport = TransportManager.create("xor", key=args.obfuscation_key)
        elif args.obfuscation == "faketls":
            transport = TransportManager.create("faketls", sni=args.obfuscation_key or "google.com")
        elif args.obfuscation == "shadowsocks":
            transport = TransportManager.create("shadowsocks", password=args.obfuscation_key)
        elif args.obfuscation == "domain_fronting":
            transport = TransportManager.create("domain_fronting", 
                                                front_domain="cdn.cloudflare.com",
                                                backend_host="mesh.example.com")
            
        if not transport:
            logger.error(f"Failed to create transport: {args.obfuscation}")
            sys.exit(1)
    
    # 2. Log traffic shaping
    if args.traffic_profile != "none":
        logger.info(f"Traffic shaping enabled: {args.traffic_profile}")
            
    # 3. Initialize Node Manager
    logger.info(f"Starting NodeManager for {args.node_id} (Mesh: {args.mesh_id})")
    nm = NodeManager(
        local_node_id=args.node_id,
        obfuscation_transport=transport,
        traffic_profile=args.traffic_profile
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

def x_main__mutmut_154():
    parser = argparse.ArgumentParser(description="x0tta6bl4 Mesh Node")
    parser.add_argument("--mesh-id", default="x0tta6bl4-mesh", help="Mesh Network ID")
    parser.add_argument("--node-id", required=True, help="Unique Node ID")
    parser.add_argument("--obfuscation", 
                        choices=["none", "xor", "faketls", "shadowsocks", "domain_fronting"], 
                        default="none",
                        help="Traffic obfuscation strategy")
    parser.add_argument("--obfuscation-key", default="x0tta6bl4", help="Key for XOR/Shadowsocks")
    parser.add_argument("--traffic-profile",
                        choices=TRAFFIC_PROFILES,
                        default="none",
                        help="Traffic shaping profile to mimic (evades DPI timing analysis)")
    
    args = parser.parse_args()
    
    # 1. Configure Obfuscation
    transport = None
    if args.obfuscation != "none":
        logger.info(f"Initializing obfuscation transport: {args.obfuscation}")
        if args.obfuscation == "xor":
            transport = TransportManager.create("xor", key=args.obfuscation_key)
        elif args.obfuscation == "faketls":
            transport = TransportManager.create("faketls", sni=args.obfuscation_key or "google.com")
        elif args.obfuscation == "shadowsocks":
            transport = TransportManager.create("shadowsocks", password=args.obfuscation_key)
        elif args.obfuscation == "domain_fronting":
            transport = TransportManager.create("domain_fronting", 
                                                front_domain="cdn.cloudflare.com",
                                                backend_host="mesh.example.com")
            
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
        obfuscation_transport=transport,
        traffic_profile=args.traffic_profile
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

def x_main__mutmut_155():
    parser = argparse.ArgumentParser(description="x0tta6bl4 Mesh Node")
    parser.add_argument("--mesh-id", default="x0tta6bl4-mesh", help="Mesh Network ID")
    parser.add_argument("--node-id", required=True, help="Unique Node ID")
    parser.add_argument("--obfuscation", 
                        choices=["none", "xor", "faketls", "shadowsocks", "domain_fronting"], 
                        default="none",
                        help="Traffic obfuscation strategy")
    parser.add_argument("--obfuscation-key", default="x0tta6bl4", help="Key for XOR/Shadowsocks")
    parser.add_argument("--traffic-profile",
                        choices=TRAFFIC_PROFILES,
                        default="none",
                        help="Traffic shaping profile to mimic (evades DPI timing analysis)")
    
    args = parser.parse_args()
    
    # 1. Configure Obfuscation
    transport = None
    if args.obfuscation != "none":
        logger.info(f"Initializing obfuscation transport: {args.obfuscation}")
        if args.obfuscation == "xor":
            transport = TransportManager.create("xor", key=args.obfuscation_key)
        elif args.obfuscation == "faketls":
            transport = TransportManager.create("faketls", sni=args.obfuscation_key or "google.com")
        elif args.obfuscation == "shadowsocks":
            transport = TransportManager.create("shadowsocks", password=args.obfuscation_key)
        elif args.obfuscation == "domain_fronting":
            transport = TransportManager.create("domain_fronting", 
                                                front_domain="cdn.cloudflare.com",
                                                backend_host="mesh.example.com")
            
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
        traffic_profile=args.traffic_profile
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

def x_main__mutmut_156():
    parser = argparse.ArgumentParser(description="x0tta6bl4 Mesh Node")
    parser.add_argument("--mesh-id", default="x0tta6bl4-mesh", help="Mesh Network ID")
    parser.add_argument("--node-id", required=True, help="Unique Node ID")
    parser.add_argument("--obfuscation", 
                        choices=["none", "xor", "faketls", "shadowsocks", "domain_fronting"], 
                        default="none",
                        help="Traffic obfuscation strategy")
    parser.add_argument("--obfuscation-key", default="x0tta6bl4", help="Key for XOR/Shadowsocks")
    parser.add_argument("--traffic-profile",
                        choices=TRAFFIC_PROFILES,
                        default="none",
                        help="Traffic shaping profile to mimic (evades DPI timing analysis)")
    
    args = parser.parse_args()
    
    # 1. Configure Obfuscation
    transport = None
    if args.obfuscation != "none":
        logger.info(f"Initializing obfuscation transport: {args.obfuscation}")
        if args.obfuscation == "xor":
            transport = TransportManager.create("xor", key=args.obfuscation_key)
        elif args.obfuscation == "faketls":
            transport = TransportManager.create("faketls", sni=args.obfuscation_key or "google.com")
        elif args.obfuscation == "shadowsocks":
            transport = TransportManager.create("shadowsocks", password=args.obfuscation_key)
        elif args.obfuscation == "domain_fronting":
            transport = TransportManager.create("domain_fronting", 
                                                front_domain="cdn.cloudflare.com",
                                                backend_host="mesh.example.com")
            
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

def x_main__mutmut_157():
    parser = argparse.ArgumentParser(description="x0tta6bl4 Mesh Node")
    parser.add_argument("--mesh-id", default="x0tta6bl4-mesh", help="Mesh Network ID")
    parser.add_argument("--node-id", required=True, help="Unique Node ID")
    parser.add_argument("--obfuscation", 
                        choices=["none", "xor", "faketls", "shadowsocks", "domain_fronting"], 
                        default="none",
                        help="Traffic obfuscation strategy")
    parser.add_argument("--obfuscation-key", default="x0tta6bl4", help="Key for XOR/Shadowsocks")
    parser.add_argument("--traffic-profile",
                        choices=TRAFFIC_PROFILES,
                        default="none",
                        help="Traffic shaping profile to mimic (evades DPI timing analysis)")
    
    args = parser.parse_args()
    
    # 1. Configure Obfuscation
    transport = None
    if args.obfuscation != "none":
        logger.info(f"Initializing obfuscation transport: {args.obfuscation}")
        if args.obfuscation == "xor":
            transport = TransportManager.create("xor", key=args.obfuscation_key)
        elif args.obfuscation == "faketls":
            transport = TransportManager.create("faketls", sni=args.obfuscation_key or "google.com")
        elif args.obfuscation == "shadowsocks":
            transport = TransportManager.create("shadowsocks", password=args.obfuscation_key)
        elif args.obfuscation == "domain_fronting":
            transport = TransportManager.create("domain_fronting", 
                                                front_domain="cdn.cloudflare.com",
                                                backend_host="mesh.example.com")
            
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
        traffic_profile=args.traffic_profile
    )
    
    # 4. Run Node (Simulation loop)
    try:
        logger.info(None)
        while True:
            # In a real app, this would trigger heartbeats loop
            # For CLI demo, we just log occasional heartbeats
            nm.send_heartbeat("broadcast")
            time.sleep(10)
    except KeyboardInterrupt:
        logger.info("Stopping node...")

def x_main__mutmut_158():
    parser = argparse.ArgumentParser(description="x0tta6bl4 Mesh Node")
    parser.add_argument("--mesh-id", default="x0tta6bl4-mesh", help="Mesh Network ID")
    parser.add_argument("--node-id", required=True, help="Unique Node ID")
    parser.add_argument("--obfuscation", 
                        choices=["none", "xor", "faketls", "shadowsocks", "domain_fronting"], 
                        default="none",
                        help="Traffic obfuscation strategy")
    parser.add_argument("--obfuscation-key", default="x0tta6bl4", help="Key for XOR/Shadowsocks")
    parser.add_argument("--traffic-profile",
                        choices=TRAFFIC_PROFILES,
                        default="none",
                        help="Traffic shaping profile to mimic (evades DPI timing analysis)")
    
    args = parser.parse_args()
    
    # 1. Configure Obfuscation
    transport = None
    if args.obfuscation != "none":
        logger.info(f"Initializing obfuscation transport: {args.obfuscation}")
        if args.obfuscation == "xor":
            transport = TransportManager.create("xor", key=args.obfuscation_key)
        elif args.obfuscation == "faketls":
            transport = TransportManager.create("faketls", sni=args.obfuscation_key or "google.com")
        elif args.obfuscation == "shadowsocks":
            transport = TransportManager.create("shadowsocks", password=args.obfuscation_key)
        elif args.obfuscation == "domain_fronting":
            transport = TransportManager.create("domain_fronting", 
                                                front_domain="cdn.cloudflare.com",
                                                backend_host="mesh.example.com")
            
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
        traffic_profile=args.traffic_profile
    )
    
    # 4. Run Node (Simulation loop)
    try:
        logger.info("XXNode running. Press Ctrl+C to stop.XX")
        while True:
            # In a real app, this would trigger heartbeats loop
            # For CLI demo, we just log occasional heartbeats
            nm.send_heartbeat("broadcast")
            time.sleep(10)
    except KeyboardInterrupt:
        logger.info("Stopping node...")

def x_main__mutmut_159():
    parser = argparse.ArgumentParser(description="x0tta6bl4 Mesh Node")
    parser.add_argument("--mesh-id", default="x0tta6bl4-mesh", help="Mesh Network ID")
    parser.add_argument("--node-id", required=True, help="Unique Node ID")
    parser.add_argument("--obfuscation", 
                        choices=["none", "xor", "faketls", "shadowsocks", "domain_fronting"], 
                        default="none",
                        help="Traffic obfuscation strategy")
    parser.add_argument("--obfuscation-key", default="x0tta6bl4", help="Key for XOR/Shadowsocks")
    parser.add_argument("--traffic-profile",
                        choices=TRAFFIC_PROFILES,
                        default="none",
                        help="Traffic shaping profile to mimic (evades DPI timing analysis)")
    
    args = parser.parse_args()
    
    # 1. Configure Obfuscation
    transport = None
    if args.obfuscation != "none":
        logger.info(f"Initializing obfuscation transport: {args.obfuscation}")
        if args.obfuscation == "xor":
            transport = TransportManager.create("xor", key=args.obfuscation_key)
        elif args.obfuscation == "faketls":
            transport = TransportManager.create("faketls", sni=args.obfuscation_key or "google.com")
        elif args.obfuscation == "shadowsocks":
            transport = TransportManager.create("shadowsocks", password=args.obfuscation_key)
        elif args.obfuscation == "domain_fronting":
            transport = TransportManager.create("domain_fronting", 
                                                front_domain="cdn.cloudflare.com",
                                                backend_host="mesh.example.com")
            
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
        traffic_profile=args.traffic_profile
    )
    
    # 4. Run Node (Simulation loop)
    try:
        logger.info("node running. press ctrl+c to stop.")
        while True:
            # In a real app, this would trigger heartbeats loop
            # For CLI demo, we just log occasional heartbeats
            nm.send_heartbeat("broadcast")
            time.sleep(10)
    except KeyboardInterrupt:
        logger.info("Stopping node...")

def x_main__mutmut_160():
    parser = argparse.ArgumentParser(description="x0tta6bl4 Mesh Node")
    parser.add_argument("--mesh-id", default="x0tta6bl4-mesh", help="Mesh Network ID")
    parser.add_argument("--node-id", required=True, help="Unique Node ID")
    parser.add_argument("--obfuscation", 
                        choices=["none", "xor", "faketls", "shadowsocks", "domain_fronting"], 
                        default="none",
                        help="Traffic obfuscation strategy")
    parser.add_argument("--obfuscation-key", default="x0tta6bl4", help="Key for XOR/Shadowsocks")
    parser.add_argument("--traffic-profile",
                        choices=TRAFFIC_PROFILES,
                        default="none",
                        help="Traffic shaping profile to mimic (evades DPI timing analysis)")
    
    args = parser.parse_args()
    
    # 1. Configure Obfuscation
    transport = None
    if args.obfuscation != "none":
        logger.info(f"Initializing obfuscation transport: {args.obfuscation}")
        if args.obfuscation == "xor":
            transport = TransportManager.create("xor", key=args.obfuscation_key)
        elif args.obfuscation == "faketls":
            transport = TransportManager.create("faketls", sni=args.obfuscation_key or "google.com")
        elif args.obfuscation == "shadowsocks":
            transport = TransportManager.create("shadowsocks", password=args.obfuscation_key)
        elif args.obfuscation == "domain_fronting":
            transport = TransportManager.create("domain_fronting", 
                                                front_domain="cdn.cloudflare.com",
                                                backend_host="mesh.example.com")
            
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
        traffic_profile=args.traffic_profile
    )
    
    # 4. Run Node (Simulation loop)
    try:
        logger.info("NODE RUNNING. PRESS CTRL+C TO STOP.")
        while True:
            # In a real app, this would trigger heartbeats loop
            # For CLI demo, we just log occasional heartbeats
            nm.send_heartbeat("broadcast")
            time.sleep(10)
    except KeyboardInterrupt:
        logger.info("Stopping node...")

def x_main__mutmut_161():
    parser = argparse.ArgumentParser(description="x0tta6bl4 Mesh Node")
    parser.add_argument("--mesh-id", default="x0tta6bl4-mesh", help="Mesh Network ID")
    parser.add_argument("--node-id", required=True, help="Unique Node ID")
    parser.add_argument("--obfuscation", 
                        choices=["none", "xor", "faketls", "shadowsocks", "domain_fronting"], 
                        default="none",
                        help="Traffic obfuscation strategy")
    parser.add_argument("--obfuscation-key", default="x0tta6bl4", help="Key for XOR/Shadowsocks")
    parser.add_argument("--traffic-profile",
                        choices=TRAFFIC_PROFILES,
                        default="none",
                        help="Traffic shaping profile to mimic (evades DPI timing analysis)")
    
    args = parser.parse_args()
    
    # 1. Configure Obfuscation
    transport = None
    if args.obfuscation != "none":
        logger.info(f"Initializing obfuscation transport: {args.obfuscation}")
        if args.obfuscation == "xor":
            transport = TransportManager.create("xor", key=args.obfuscation_key)
        elif args.obfuscation == "faketls":
            transport = TransportManager.create("faketls", sni=args.obfuscation_key or "google.com")
        elif args.obfuscation == "shadowsocks":
            transport = TransportManager.create("shadowsocks", password=args.obfuscation_key)
        elif args.obfuscation == "domain_fronting":
            transport = TransportManager.create("domain_fronting", 
                                                front_domain="cdn.cloudflare.com",
                                                backend_host="mesh.example.com")
            
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
        traffic_profile=args.traffic_profile
    )
    
    # 4. Run Node (Simulation loop)
    try:
        logger.info("Node running. Press Ctrl+C to stop.")
        while False:
            # In a real app, this would trigger heartbeats loop
            # For CLI demo, we just log occasional heartbeats
            nm.send_heartbeat("broadcast")
            time.sleep(10)
    except KeyboardInterrupt:
        logger.info("Stopping node...")

def x_main__mutmut_162():
    parser = argparse.ArgumentParser(description="x0tta6bl4 Mesh Node")
    parser.add_argument("--mesh-id", default="x0tta6bl4-mesh", help="Mesh Network ID")
    parser.add_argument("--node-id", required=True, help="Unique Node ID")
    parser.add_argument("--obfuscation", 
                        choices=["none", "xor", "faketls", "shadowsocks", "domain_fronting"], 
                        default="none",
                        help="Traffic obfuscation strategy")
    parser.add_argument("--obfuscation-key", default="x0tta6bl4", help="Key for XOR/Shadowsocks")
    parser.add_argument("--traffic-profile",
                        choices=TRAFFIC_PROFILES,
                        default="none",
                        help="Traffic shaping profile to mimic (evades DPI timing analysis)")
    
    args = parser.parse_args()
    
    # 1. Configure Obfuscation
    transport = None
    if args.obfuscation != "none":
        logger.info(f"Initializing obfuscation transport: {args.obfuscation}")
        if args.obfuscation == "xor":
            transport = TransportManager.create("xor", key=args.obfuscation_key)
        elif args.obfuscation == "faketls":
            transport = TransportManager.create("faketls", sni=args.obfuscation_key or "google.com")
        elif args.obfuscation == "shadowsocks":
            transport = TransportManager.create("shadowsocks", password=args.obfuscation_key)
        elif args.obfuscation == "domain_fronting":
            transport = TransportManager.create("domain_fronting", 
                                                front_domain="cdn.cloudflare.com",
                                                backend_host="mesh.example.com")
            
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
        traffic_profile=args.traffic_profile
    )
    
    # 4. Run Node (Simulation loop)
    try:
        logger.info("Node running. Press Ctrl+C to stop.")
        while True:
            # In a real app, this would trigger heartbeats loop
            # For CLI demo, we just log occasional heartbeats
            nm.send_heartbeat(None)
            time.sleep(10)
    except KeyboardInterrupt:
        logger.info("Stopping node...")

def x_main__mutmut_163():
    parser = argparse.ArgumentParser(description="x0tta6bl4 Mesh Node")
    parser.add_argument("--mesh-id", default="x0tta6bl4-mesh", help="Mesh Network ID")
    parser.add_argument("--node-id", required=True, help="Unique Node ID")
    parser.add_argument("--obfuscation", 
                        choices=["none", "xor", "faketls", "shadowsocks", "domain_fronting"], 
                        default="none",
                        help="Traffic obfuscation strategy")
    parser.add_argument("--obfuscation-key", default="x0tta6bl4", help="Key for XOR/Shadowsocks")
    parser.add_argument("--traffic-profile",
                        choices=TRAFFIC_PROFILES,
                        default="none",
                        help="Traffic shaping profile to mimic (evades DPI timing analysis)")
    
    args = parser.parse_args()
    
    # 1. Configure Obfuscation
    transport = None
    if args.obfuscation != "none":
        logger.info(f"Initializing obfuscation transport: {args.obfuscation}")
        if args.obfuscation == "xor":
            transport = TransportManager.create("xor", key=args.obfuscation_key)
        elif args.obfuscation == "faketls":
            transport = TransportManager.create("faketls", sni=args.obfuscation_key or "google.com")
        elif args.obfuscation == "shadowsocks":
            transport = TransportManager.create("shadowsocks", password=args.obfuscation_key)
        elif args.obfuscation == "domain_fronting":
            transport = TransportManager.create("domain_fronting", 
                                                front_domain="cdn.cloudflare.com",
                                                backend_host="mesh.example.com")
            
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
        traffic_profile=args.traffic_profile
    )
    
    # 4. Run Node (Simulation loop)
    try:
        logger.info("Node running. Press Ctrl+C to stop.")
        while True:
            # In a real app, this would trigger heartbeats loop
            # For CLI demo, we just log occasional heartbeats
            nm.send_heartbeat("XXbroadcastXX")
            time.sleep(10)
    except KeyboardInterrupt:
        logger.info("Stopping node...")

def x_main__mutmut_164():
    parser = argparse.ArgumentParser(description="x0tta6bl4 Mesh Node")
    parser.add_argument("--mesh-id", default="x0tta6bl4-mesh", help="Mesh Network ID")
    parser.add_argument("--node-id", required=True, help="Unique Node ID")
    parser.add_argument("--obfuscation", 
                        choices=["none", "xor", "faketls", "shadowsocks", "domain_fronting"], 
                        default="none",
                        help="Traffic obfuscation strategy")
    parser.add_argument("--obfuscation-key", default="x0tta6bl4", help="Key for XOR/Shadowsocks")
    parser.add_argument("--traffic-profile",
                        choices=TRAFFIC_PROFILES,
                        default="none",
                        help="Traffic shaping profile to mimic (evades DPI timing analysis)")
    
    args = parser.parse_args()
    
    # 1. Configure Obfuscation
    transport = None
    if args.obfuscation != "none":
        logger.info(f"Initializing obfuscation transport: {args.obfuscation}")
        if args.obfuscation == "xor":
            transport = TransportManager.create("xor", key=args.obfuscation_key)
        elif args.obfuscation == "faketls":
            transport = TransportManager.create("faketls", sni=args.obfuscation_key or "google.com")
        elif args.obfuscation == "shadowsocks":
            transport = TransportManager.create("shadowsocks", password=args.obfuscation_key)
        elif args.obfuscation == "domain_fronting":
            transport = TransportManager.create("domain_fronting", 
                                                front_domain="cdn.cloudflare.com",
                                                backend_host="mesh.example.com")
            
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
        traffic_profile=args.traffic_profile
    )
    
    # 4. Run Node (Simulation loop)
    try:
        logger.info("Node running. Press Ctrl+C to stop.")
        while True:
            # In a real app, this would trigger heartbeats loop
            # For CLI demo, we just log occasional heartbeats
            nm.send_heartbeat("BROADCAST")
            time.sleep(10)
    except KeyboardInterrupt:
        logger.info("Stopping node...")

def x_main__mutmut_165():
    parser = argparse.ArgumentParser(description="x0tta6bl4 Mesh Node")
    parser.add_argument("--mesh-id", default="x0tta6bl4-mesh", help="Mesh Network ID")
    parser.add_argument("--node-id", required=True, help="Unique Node ID")
    parser.add_argument("--obfuscation", 
                        choices=["none", "xor", "faketls", "shadowsocks", "domain_fronting"], 
                        default="none",
                        help="Traffic obfuscation strategy")
    parser.add_argument("--obfuscation-key", default="x0tta6bl4", help="Key for XOR/Shadowsocks")
    parser.add_argument("--traffic-profile",
                        choices=TRAFFIC_PROFILES,
                        default="none",
                        help="Traffic shaping profile to mimic (evades DPI timing analysis)")
    
    args = parser.parse_args()
    
    # 1. Configure Obfuscation
    transport = None
    if args.obfuscation != "none":
        logger.info(f"Initializing obfuscation transport: {args.obfuscation}")
        if args.obfuscation == "xor":
            transport = TransportManager.create("xor", key=args.obfuscation_key)
        elif args.obfuscation == "faketls":
            transport = TransportManager.create("faketls", sni=args.obfuscation_key or "google.com")
        elif args.obfuscation == "shadowsocks":
            transport = TransportManager.create("shadowsocks", password=args.obfuscation_key)
        elif args.obfuscation == "domain_fronting":
            transport = TransportManager.create("domain_fronting", 
                                                front_domain="cdn.cloudflare.com",
                                                backend_host="mesh.example.com")
            
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
        traffic_profile=args.traffic_profile
    )
    
    # 4. Run Node (Simulation loop)
    try:
        logger.info("Node running. Press Ctrl+C to stop.")
        while True:
            # In a real app, this would trigger heartbeats loop
            # For CLI demo, we just log occasional heartbeats
            nm.send_heartbeat("broadcast")
            time.sleep(None)
    except KeyboardInterrupt:
        logger.info("Stopping node...")

def x_main__mutmut_166():
    parser = argparse.ArgumentParser(description="x0tta6bl4 Mesh Node")
    parser.add_argument("--mesh-id", default="x0tta6bl4-mesh", help="Mesh Network ID")
    parser.add_argument("--node-id", required=True, help="Unique Node ID")
    parser.add_argument("--obfuscation", 
                        choices=["none", "xor", "faketls", "shadowsocks", "domain_fronting"], 
                        default="none",
                        help="Traffic obfuscation strategy")
    parser.add_argument("--obfuscation-key", default="x0tta6bl4", help="Key for XOR/Shadowsocks")
    parser.add_argument("--traffic-profile",
                        choices=TRAFFIC_PROFILES,
                        default="none",
                        help="Traffic shaping profile to mimic (evades DPI timing analysis)")
    
    args = parser.parse_args()
    
    # 1. Configure Obfuscation
    transport = None
    if args.obfuscation != "none":
        logger.info(f"Initializing obfuscation transport: {args.obfuscation}")
        if args.obfuscation == "xor":
            transport = TransportManager.create("xor", key=args.obfuscation_key)
        elif args.obfuscation == "faketls":
            transport = TransportManager.create("faketls", sni=args.obfuscation_key or "google.com")
        elif args.obfuscation == "shadowsocks":
            transport = TransportManager.create("shadowsocks", password=args.obfuscation_key)
        elif args.obfuscation == "domain_fronting":
            transport = TransportManager.create("domain_fronting", 
                                                front_domain="cdn.cloudflare.com",
                                                backend_host="mesh.example.com")
            
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
        traffic_profile=args.traffic_profile
    )
    
    # 4. Run Node (Simulation loop)
    try:
        logger.info("Node running. Press Ctrl+C to stop.")
        while True:
            # In a real app, this would trigger heartbeats loop
            # For CLI demo, we just log occasional heartbeats
            nm.send_heartbeat("broadcast")
            time.sleep(11)
    except KeyboardInterrupt:
        logger.info("Stopping node...")

def x_main__mutmut_167():
    parser = argparse.ArgumentParser(description="x0tta6bl4 Mesh Node")
    parser.add_argument("--mesh-id", default="x0tta6bl4-mesh", help="Mesh Network ID")
    parser.add_argument("--node-id", required=True, help="Unique Node ID")
    parser.add_argument("--obfuscation", 
                        choices=["none", "xor", "faketls", "shadowsocks", "domain_fronting"], 
                        default="none",
                        help="Traffic obfuscation strategy")
    parser.add_argument("--obfuscation-key", default="x0tta6bl4", help="Key for XOR/Shadowsocks")
    parser.add_argument("--traffic-profile",
                        choices=TRAFFIC_PROFILES,
                        default="none",
                        help="Traffic shaping profile to mimic (evades DPI timing analysis)")
    
    args = parser.parse_args()
    
    # 1. Configure Obfuscation
    transport = None
    if args.obfuscation != "none":
        logger.info(f"Initializing obfuscation transport: {args.obfuscation}")
        if args.obfuscation == "xor":
            transport = TransportManager.create("xor", key=args.obfuscation_key)
        elif args.obfuscation == "faketls":
            transport = TransportManager.create("faketls", sni=args.obfuscation_key or "google.com")
        elif args.obfuscation == "shadowsocks":
            transport = TransportManager.create("shadowsocks", password=args.obfuscation_key)
        elif args.obfuscation == "domain_fronting":
            transport = TransportManager.create("domain_fronting", 
                                                front_domain="cdn.cloudflare.com",
                                                backend_host="mesh.example.com")
            
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
        traffic_profile=args.traffic_profile
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
        logger.info(None)

def x_main__mutmut_168():
    parser = argparse.ArgumentParser(description="x0tta6bl4 Mesh Node")
    parser.add_argument("--mesh-id", default="x0tta6bl4-mesh", help="Mesh Network ID")
    parser.add_argument("--node-id", required=True, help="Unique Node ID")
    parser.add_argument("--obfuscation", 
                        choices=["none", "xor", "faketls", "shadowsocks", "domain_fronting"], 
                        default="none",
                        help="Traffic obfuscation strategy")
    parser.add_argument("--obfuscation-key", default="x0tta6bl4", help="Key for XOR/Shadowsocks")
    parser.add_argument("--traffic-profile",
                        choices=TRAFFIC_PROFILES,
                        default="none",
                        help="Traffic shaping profile to mimic (evades DPI timing analysis)")
    
    args = parser.parse_args()
    
    # 1. Configure Obfuscation
    transport = None
    if args.obfuscation != "none":
        logger.info(f"Initializing obfuscation transport: {args.obfuscation}")
        if args.obfuscation == "xor":
            transport = TransportManager.create("xor", key=args.obfuscation_key)
        elif args.obfuscation == "faketls":
            transport = TransportManager.create("faketls", sni=args.obfuscation_key or "google.com")
        elif args.obfuscation == "shadowsocks":
            transport = TransportManager.create("shadowsocks", password=args.obfuscation_key)
        elif args.obfuscation == "domain_fronting":
            transport = TransportManager.create("domain_fronting", 
                                                front_domain="cdn.cloudflare.com",
                                                backend_host="mesh.example.com")
            
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
        traffic_profile=args.traffic_profile
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
        logger.info("XXStopping node...XX")

def x_main__mutmut_169():
    parser = argparse.ArgumentParser(description="x0tta6bl4 Mesh Node")
    parser.add_argument("--mesh-id", default="x0tta6bl4-mesh", help="Mesh Network ID")
    parser.add_argument("--node-id", required=True, help="Unique Node ID")
    parser.add_argument("--obfuscation", 
                        choices=["none", "xor", "faketls", "shadowsocks", "domain_fronting"], 
                        default="none",
                        help="Traffic obfuscation strategy")
    parser.add_argument("--obfuscation-key", default="x0tta6bl4", help="Key for XOR/Shadowsocks")
    parser.add_argument("--traffic-profile",
                        choices=TRAFFIC_PROFILES,
                        default="none",
                        help="Traffic shaping profile to mimic (evades DPI timing analysis)")
    
    args = parser.parse_args()
    
    # 1. Configure Obfuscation
    transport = None
    if args.obfuscation != "none":
        logger.info(f"Initializing obfuscation transport: {args.obfuscation}")
        if args.obfuscation == "xor":
            transport = TransportManager.create("xor", key=args.obfuscation_key)
        elif args.obfuscation == "faketls":
            transport = TransportManager.create("faketls", sni=args.obfuscation_key or "google.com")
        elif args.obfuscation == "shadowsocks":
            transport = TransportManager.create("shadowsocks", password=args.obfuscation_key)
        elif args.obfuscation == "domain_fronting":
            transport = TransportManager.create("domain_fronting", 
                                                front_domain="cdn.cloudflare.com",
                                                backend_host="mesh.example.com")
            
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
        traffic_profile=args.traffic_profile
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
        logger.info("stopping node...")

def x_main__mutmut_170():
    parser = argparse.ArgumentParser(description="x0tta6bl4 Mesh Node")
    parser.add_argument("--mesh-id", default="x0tta6bl4-mesh", help="Mesh Network ID")
    parser.add_argument("--node-id", required=True, help="Unique Node ID")
    parser.add_argument("--obfuscation", 
                        choices=["none", "xor", "faketls", "shadowsocks", "domain_fronting"], 
                        default="none",
                        help="Traffic obfuscation strategy")
    parser.add_argument("--obfuscation-key", default="x0tta6bl4", help="Key for XOR/Shadowsocks")
    parser.add_argument("--traffic-profile",
                        choices=TRAFFIC_PROFILES,
                        default="none",
                        help="Traffic shaping profile to mimic (evades DPI timing analysis)")
    
    args = parser.parse_args()
    
    # 1. Configure Obfuscation
    transport = None
    if args.obfuscation != "none":
        logger.info(f"Initializing obfuscation transport: {args.obfuscation}")
        if args.obfuscation == "xor":
            transport = TransportManager.create("xor", key=args.obfuscation_key)
        elif args.obfuscation == "faketls":
            transport = TransportManager.create("faketls", sni=args.obfuscation_key or "google.com")
        elif args.obfuscation == "shadowsocks":
            transport = TransportManager.create("shadowsocks", password=args.obfuscation_key)
        elif args.obfuscation == "domain_fronting":
            transport = TransportManager.create("domain_fronting", 
                                                front_domain="cdn.cloudflare.com",
                                                backend_host="mesh.example.com")
            
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
        traffic_profile=args.traffic_profile
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
        logger.info("STOPPING NODE...")

x_main__mutmut_mutants : ClassVar[MutantDict] = {
'x_main__mutmut_1': x_main__mutmut_1, 
    'x_main__mutmut_2': x_main__mutmut_2, 
    'x_main__mutmut_3': x_main__mutmut_3, 
    'x_main__mutmut_4': x_main__mutmut_4, 
    'x_main__mutmut_5': x_main__mutmut_5, 
    'x_main__mutmut_6': x_main__mutmut_6, 
    'x_main__mutmut_7': x_main__mutmut_7, 
    'x_main__mutmut_8': x_main__mutmut_8, 
    'x_main__mutmut_9': x_main__mutmut_9, 
    'x_main__mutmut_10': x_main__mutmut_10, 
    'x_main__mutmut_11': x_main__mutmut_11, 
    'x_main__mutmut_12': x_main__mutmut_12, 
    'x_main__mutmut_13': x_main__mutmut_13, 
    'x_main__mutmut_14': x_main__mutmut_14, 
    'x_main__mutmut_15': x_main__mutmut_15, 
    'x_main__mutmut_16': x_main__mutmut_16, 
    'x_main__mutmut_17': x_main__mutmut_17, 
    'x_main__mutmut_18': x_main__mutmut_18, 
    'x_main__mutmut_19': x_main__mutmut_19, 
    'x_main__mutmut_20': x_main__mutmut_20, 
    'x_main__mutmut_21': x_main__mutmut_21, 
    'x_main__mutmut_22': x_main__mutmut_22, 
    'x_main__mutmut_23': x_main__mutmut_23, 
    'x_main__mutmut_24': x_main__mutmut_24, 
    'x_main__mutmut_25': x_main__mutmut_25, 
    'x_main__mutmut_26': x_main__mutmut_26, 
    'x_main__mutmut_27': x_main__mutmut_27, 
    'x_main__mutmut_28': x_main__mutmut_28, 
    'x_main__mutmut_29': x_main__mutmut_29, 
    'x_main__mutmut_30': x_main__mutmut_30, 
    'x_main__mutmut_31': x_main__mutmut_31, 
    'x_main__mutmut_32': x_main__mutmut_32, 
    'x_main__mutmut_33': x_main__mutmut_33, 
    'x_main__mutmut_34': x_main__mutmut_34, 
    'x_main__mutmut_35': x_main__mutmut_35, 
    'x_main__mutmut_36': x_main__mutmut_36, 
    'x_main__mutmut_37': x_main__mutmut_37, 
    'x_main__mutmut_38': x_main__mutmut_38, 
    'x_main__mutmut_39': x_main__mutmut_39, 
    'x_main__mutmut_40': x_main__mutmut_40, 
    'x_main__mutmut_41': x_main__mutmut_41, 
    'x_main__mutmut_42': x_main__mutmut_42, 
    'x_main__mutmut_43': x_main__mutmut_43, 
    'x_main__mutmut_44': x_main__mutmut_44, 
    'x_main__mutmut_45': x_main__mutmut_45, 
    'x_main__mutmut_46': x_main__mutmut_46, 
    'x_main__mutmut_47': x_main__mutmut_47, 
    'x_main__mutmut_48': x_main__mutmut_48, 
    'x_main__mutmut_49': x_main__mutmut_49, 
    'x_main__mutmut_50': x_main__mutmut_50, 
    'x_main__mutmut_51': x_main__mutmut_51, 
    'x_main__mutmut_52': x_main__mutmut_52, 
    'x_main__mutmut_53': x_main__mutmut_53, 
    'x_main__mutmut_54': x_main__mutmut_54, 
    'x_main__mutmut_55': x_main__mutmut_55, 
    'x_main__mutmut_56': x_main__mutmut_56, 
    'x_main__mutmut_57': x_main__mutmut_57, 
    'x_main__mutmut_58': x_main__mutmut_58, 
    'x_main__mutmut_59': x_main__mutmut_59, 
    'x_main__mutmut_60': x_main__mutmut_60, 
    'x_main__mutmut_61': x_main__mutmut_61, 
    'x_main__mutmut_62': x_main__mutmut_62, 
    'x_main__mutmut_63': x_main__mutmut_63, 
    'x_main__mutmut_64': x_main__mutmut_64, 
    'x_main__mutmut_65': x_main__mutmut_65, 
    'x_main__mutmut_66': x_main__mutmut_66, 
    'x_main__mutmut_67': x_main__mutmut_67, 
    'x_main__mutmut_68': x_main__mutmut_68, 
    'x_main__mutmut_69': x_main__mutmut_69, 
    'x_main__mutmut_70': x_main__mutmut_70, 
    'x_main__mutmut_71': x_main__mutmut_71, 
    'x_main__mutmut_72': x_main__mutmut_72, 
    'x_main__mutmut_73': x_main__mutmut_73, 
    'x_main__mutmut_74': x_main__mutmut_74, 
    'x_main__mutmut_75': x_main__mutmut_75, 
    'x_main__mutmut_76': x_main__mutmut_76, 
    'x_main__mutmut_77': x_main__mutmut_77, 
    'x_main__mutmut_78': x_main__mutmut_78, 
    'x_main__mutmut_79': x_main__mutmut_79, 
    'x_main__mutmut_80': x_main__mutmut_80, 
    'x_main__mutmut_81': x_main__mutmut_81, 
    'x_main__mutmut_82': x_main__mutmut_82, 
    'x_main__mutmut_83': x_main__mutmut_83, 
    'x_main__mutmut_84': x_main__mutmut_84, 
    'x_main__mutmut_85': x_main__mutmut_85, 
    'x_main__mutmut_86': x_main__mutmut_86, 
    'x_main__mutmut_87': x_main__mutmut_87, 
    'x_main__mutmut_88': x_main__mutmut_88, 
    'x_main__mutmut_89': x_main__mutmut_89, 
    'x_main__mutmut_90': x_main__mutmut_90, 
    'x_main__mutmut_91': x_main__mutmut_91, 
    'x_main__mutmut_92': x_main__mutmut_92, 
    'x_main__mutmut_93': x_main__mutmut_93, 
    'x_main__mutmut_94': x_main__mutmut_94, 
    'x_main__mutmut_95': x_main__mutmut_95, 
    'x_main__mutmut_96': x_main__mutmut_96, 
    'x_main__mutmut_97': x_main__mutmut_97, 
    'x_main__mutmut_98': x_main__mutmut_98, 
    'x_main__mutmut_99': x_main__mutmut_99, 
    'x_main__mutmut_100': x_main__mutmut_100, 
    'x_main__mutmut_101': x_main__mutmut_101, 
    'x_main__mutmut_102': x_main__mutmut_102, 
    'x_main__mutmut_103': x_main__mutmut_103, 
    'x_main__mutmut_104': x_main__mutmut_104, 
    'x_main__mutmut_105': x_main__mutmut_105, 
    'x_main__mutmut_106': x_main__mutmut_106, 
    'x_main__mutmut_107': x_main__mutmut_107, 
    'x_main__mutmut_108': x_main__mutmut_108, 
    'x_main__mutmut_109': x_main__mutmut_109, 
    'x_main__mutmut_110': x_main__mutmut_110, 
    'x_main__mutmut_111': x_main__mutmut_111, 
    'x_main__mutmut_112': x_main__mutmut_112, 
    'x_main__mutmut_113': x_main__mutmut_113, 
    'x_main__mutmut_114': x_main__mutmut_114, 
    'x_main__mutmut_115': x_main__mutmut_115, 
    'x_main__mutmut_116': x_main__mutmut_116, 
    'x_main__mutmut_117': x_main__mutmut_117, 
    'x_main__mutmut_118': x_main__mutmut_118, 
    'x_main__mutmut_119': x_main__mutmut_119, 
    'x_main__mutmut_120': x_main__mutmut_120, 
    'x_main__mutmut_121': x_main__mutmut_121, 
    'x_main__mutmut_122': x_main__mutmut_122, 
    'x_main__mutmut_123': x_main__mutmut_123, 
    'x_main__mutmut_124': x_main__mutmut_124, 
    'x_main__mutmut_125': x_main__mutmut_125, 
    'x_main__mutmut_126': x_main__mutmut_126, 
    'x_main__mutmut_127': x_main__mutmut_127, 
    'x_main__mutmut_128': x_main__mutmut_128, 
    'x_main__mutmut_129': x_main__mutmut_129, 
    'x_main__mutmut_130': x_main__mutmut_130, 
    'x_main__mutmut_131': x_main__mutmut_131, 
    'x_main__mutmut_132': x_main__mutmut_132, 
    'x_main__mutmut_133': x_main__mutmut_133, 
    'x_main__mutmut_134': x_main__mutmut_134, 
    'x_main__mutmut_135': x_main__mutmut_135, 
    'x_main__mutmut_136': x_main__mutmut_136, 
    'x_main__mutmut_137': x_main__mutmut_137, 
    'x_main__mutmut_138': x_main__mutmut_138, 
    'x_main__mutmut_139': x_main__mutmut_139, 
    'x_main__mutmut_140': x_main__mutmut_140, 
    'x_main__mutmut_141': x_main__mutmut_141, 
    'x_main__mutmut_142': x_main__mutmut_142, 
    'x_main__mutmut_143': x_main__mutmut_143, 
    'x_main__mutmut_144': x_main__mutmut_144, 
    'x_main__mutmut_145': x_main__mutmut_145, 
    'x_main__mutmut_146': x_main__mutmut_146, 
    'x_main__mutmut_147': x_main__mutmut_147, 
    'x_main__mutmut_148': x_main__mutmut_148, 
    'x_main__mutmut_149': x_main__mutmut_149, 
    'x_main__mutmut_150': x_main__mutmut_150, 
    'x_main__mutmut_151': x_main__mutmut_151, 
    'x_main__mutmut_152': x_main__mutmut_152, 
    'x_main__mutmut_153': x_main__mutmut_153, 
    'x_main__mutmut_154': x_main__mutmut_154, 
    'x_main__mutmut_155': x_main__mutmut_155, 
    'x_main__mutmut_156': x_main__mutmut_156, 
    'x_main__mutmut_157': x_main__mutmut_157, 
    'x_main__mutmut_158': x_main__mutmut_158, 
    'x_main__mutmut_159': x_main__mutmut_159, 
    'x_main__mutmut_160': x_main__mutmut_160, 
    'x_main__mutmut_161': x_main__mutmut_161, 
    'x_main__mutmut_162': x_main__mutmut_162, 
    'x_main__mutmut_163': x_main__mutmut_163, 
    'x_main__mutmut_164': x_main__mutmut_164, 
    'x_main__mutmut_165': x_main__mutmut_165, 
    'x_main__mutmut_166': x_main__mutmut_166, 
    'x_main__mutmut_167': x_main__mutmut_167, 
    'x_main__mutmut_168': x_main__mutmut_168, 
    'x_main__mutmut_169': x_main__mutmut_169, 
    'x_main__mutmut_170': x_main__mutmut_170
}

def main(*args, **kwargs):
    result = _mutmut_trampoline(x_main__mutmut_orig, x_main__mutmut_mutants, args, kwargs)
    return result 

main.__signature__ = _mutmut_signature(x_main__mutmut_orig)
x_main__mutmut_orig.__name__ = 'x_main'

if __name__ == "__main__":
    main()
