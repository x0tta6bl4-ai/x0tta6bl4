#!/usr/bin/env python3
"""
Diagnostic script for x0tta6bl4 multi-node monitoring.
To be run on Operator PC in Saturday.
"""

import os
import subprocess
import json
import time

def check_mesh_nodes():
    print("🛰️ Checking x0tta6bl4 Mesh Connectivity...")
    try:
        # Check local yggdrasil status
        result = subprocess.run(["yggdrasilctl", "getPeers"], capture_output=True, text=True)
        print("\n--- Mesh Peers ---")
        print(result.stdout)
        
        # Check NL Master
        nl_ip = "89.125.1.107"
        print(f"\n--- Checking NL Master ({nl_ip}) ---")
        ping = subprocess.run(["ping", "-c", "1", nl_ip], capture_output=True)
        if ping.returncode == 0:
            print("✅ NL Master REACHABLE")
        else:
            print("❌ NL Master UNREACHABLE")
            
    except FileNotFoundError:
        print("❌ yggdrasilctl not found. Is Yggdrasil running?")

if __name__ == "__main__":
    check_mesh_nodes()
