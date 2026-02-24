"""
Quantum Shield Bridge
=====================

CLI entry point for Tauri to interact with QuantumShieldClient.
Usage: python bridge.py <command> [args]
"""

import sys
import asyncio
import json
import argparse
from src.client.engine import QuantumShieldClient

async def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("command", choices=["auth", "connect", "status", "stop"])
    parser.add_argument("--node_id", default="client-001")
    parser.add_argument("--api_url", default="http://localhost:8000")
    
    args = parser.parse_args()
    
    client = QuantumShieldClient(args.api_url, args.node_id)
    
    if args.command == "auth":
        success = await client.authenticate()
        print(json.dumps({"success": success, "token": client.session_token}))
        
    elif args.command == "connect":
        # Note: In real app, we'd need to persist session_token
        success = await client.connect()
        print(json.dumps({"success": success, "status": client.get_status()}))
        
    elif args.command == "status":
        print(json.dumps({"status": client.get_status()}))
        
    elif args.command == "stop":
        client.stop()
        print(json.dumps({"status": "disconnected"}))

if __name__ == "__main__":
    import os
    # Ensure project root is in path
    root = os.path.abspath(os.path.join(os.path.dirname(__file__), "../../"))
    sys.path.insert(0, root)
    asyncio.run(main())
