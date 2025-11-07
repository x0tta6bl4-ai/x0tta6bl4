"""Yggdrasil mesh network client."""
from __future__ import annotations

import subprocess
import json
from typing import Dict, Any, List, Optional


def get_yggdrasil_status() -> Dict[str, Any]:
    """Get Yggdrasil node status.
    
    Returns dict with node information or error if yggdrasil is not running.
    """
    try:
        result = subprocess.run(
            ["sudo", "yggdrasilctl", "getSelf"],
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
    try:
        result = subprocess.run(
            ["sudo", "yggdrasilctl", "getPeers"],
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
    try:
        result = subprocess.run(
            ["sudo", "yggdrasilctl", "getSelf"],
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
