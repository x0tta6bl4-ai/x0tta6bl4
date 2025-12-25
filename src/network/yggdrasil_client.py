"""Yggdrasil mesh network client."""
from __future__ import annotations

import subprocess
import json
import os
from typing import Dict, Any, List, Optional
import urllib.request
import urllib.error
import random


def get_yggdrasil_status() -> Dict[str, Any]:
    """Get Yggdrasil node status.
    
    Returns dict with node information or error if yggdrasil is not running.
    """
    # Mocked path for tests and local runs without sudo/network
    if os.environ.get("YGGDRASIL_MOCK", "").lower() in {"1", "true", "yes"}:
        node_id = os.environ.get("NODE_ID", "node-a")
        address_map = {
            "node-a": "fd00::a",
            "node-b": "fd00::b",
            "node-c": "fd00::c",
        }
        return {
            "address": address_map.get(node_id, "fd00::ff"),
            "subnet": "fd00::/8",
            "status": "mock",
        }

    try:
        result = subprocess.run(
            ["yggdrasilctl", "getSelf"],
            capture_output=True,
            text=True,
            check=True,
            timeout=5
        )
        
        # Parse output line by line
        status = {}
        for line in result.stdout.strip().split('\n'):
            if ':' in line:
                key, value = line.split(':', 1)
                key = key.strip().lower().replace(' ', '_')
                value = value.strip()
                status[key] = value
        
        return {
            "status": "online",
            "node": status
        }
    except subprocess.CalledProcessError as e:
        return {
            "status": "error",
            "error": f"Failed to get node info: {e.stderr}"
        }
    except subprocess.TimeoutExpired:
        return {
            "status": "error",
            "error": "Command timeout after 5 seconds"
        }
    except Exception as e:
        return {
            "status": "offline",
            "error": str(e)
        }


def get_yggdrasil_peers() -> Dict[str, Any]:
    """Get list of connected peers.
    
    Returns dict with peer information.
    """
    # Mocked peers based on reachable health endpoints in the mesh network
    if os.environ.get("YGGDRASIL_MOCK", "").lower() in {"1", "true", "yes"}:
        num_peers = random.randint(2, 5)
        peers: List[Dict[str, Any]] = []
        for i in range(num_peers):
            peers.append({
                "port": str(random.randint(10000, 65535)),
                "protocol": "tcp",
                "remote": f"node-{random.choice(['a', 'b', 'c', 'd', 'e'])}",
            })
        return {"status": "ok", "peers": peers, "count": len(peers)}

    try:
        result = subprocess.run(
            ["yggdrasilctl", "getPeers"],
            capture_output=True,
            text=True,
            check=True,
            timeout=5
        )
        
        # Parse peers from output
        peers = []
        lines = result.stdout.strip().split('\n')
        
        for line in lines:
            if line.strip() and not line.startswith('Peer'):
                try:
                    # Parse peer line (format: port protocol remote_address)
                    parts = line.split()
                    if len(parts) >= 3:
                        peers.append({
                            "port": parts[0],
                            "protocol": parts[1],
                            "remote": parts[2]
                        })
                except:
                    continue
        
        return {
            "status": "ok",
            "peers": peers,
            "count": len(peers)
        }
    except subprocess.CalledProcessError as e:
        return {
            "status": "error",
            "error": f"Failed to get peers: {e.stderr}",
            "peers": [],
            "count": 0
        }
    except Exception as e:
        return {
            "status": "error",
            "error": str(e),
            "peers": [],
            "count": 0
        }


def get_yggdrasil_routes() -> Dict[str, Any]:
    """Get routing table information.
    
    Returns dict with routing information.
    """
    # Mocked route info
    if os.environ.get("YGGDRASIL_MOCK", "").lower() in {"1", "true", "yes"}:
        # Approximate routing size as number of peers (dynamic) * 1
        peers = get_yggdrasil_peers()
        return {"status": "ok", "routing_table_size": peers.get("count", 0)}

    try:
        result = subprocess.run(
            ["yggdrasilctl", "getSelf"],
            capture_output=True,
            text=True,
            check=True,
            timeout=5
        )
        
        # Extract routing table size from output
        routing_size = 0
        for line in result.stdout.strip().split('\n'):
            if 'Routing table size' in line:
                _, value = line.split(':', 1)
                routing_size = int(value.strip())
        
        return {
            "status": "ok",
            "routing_table_size": routing_size
        }
    except Exception as e:
        return {
            "status": "error",
            "error": str(e),
            "routing_table_size": 0
        }
