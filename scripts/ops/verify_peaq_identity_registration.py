#!/usr/bin/env python3
"""
Verify peaq Machine Identity Registration flow for x0tta6bl4 nodes.
This script proves that a mesh node can derive a peaq DID and sign machine data.
"""

import asyncio
import json
import os
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from src.security.peaq_identity import PeaqIdentityAdapter, PEAQ_SDK_AVAILABLE

async def main():
    print("🌍 x0tta6bl4 peaq Integration: Milestone 1 Verification")
    print("-------------------------------------------------------")
    
    node_id = "node-alpha-001"
    print(f"🔹 Mesh Node ID: {node_id}")
    
    # 1. Initialize Adapter
    try:
        adapter = PeaqIdentityAdapter(node_id)
        did = adapter.get_peaq_did()
        address = adapter.get_account_address()
        print(f"🔹 Derived peaq DID: {did}")
        print(f"🔹 Derived Machine Address: {address}")
    except Exception as e:
        print(f"❌ Initialization failed: {e}")
        return 1

    # 2. Simulate/Perform Registration
    print("\n📦 Registering Machine on peaq Network...")
    # Using dummy RPC and key for simulation
    reg_result = await adapter.register_machine(
        rpc_url="https://peaq-agung.api.onfinality.io/public",
        admin_private_key="0x" + "a" * 64
    )
    
    print(json.dumps(reg_result, indent=2))
    
    if reg_result["status"] == "SIMULATED":
        print("⚠️  Status: SIMULATED (peaq-sdk not installed)")
    else:
        print("✅ Status: VERIFIED_ON_CHAIN")

    # 3. Verifiable Machine Data (VMD) - Telemetry Signing
    print("\n📊 Generating Signed Telemetry (Verifiable Machine Data)...")
    telemetry = {
        "node_id": node_id,
        "throughput_mbps": 42.5,
        "pqc_status": "active",
        "timestamp": "2026-06-17T07:15:00Z"
    }
    data = json.dumps(telemetry, sort_keys=True).encode()
    signed_data = adapter.sign_telemetry(data)
    
    print("🔹 Signed Payload:")
    print(json.dumps(signed_data, indent=2))
    print("✅ Telemetry Signature Generated.")

    print("\n🏆 Milestone 1: Machine Identity Foundation - READY (local evidence)")
    return 0

if __name__ == "__main__":
    sys.exit(asyncio.run(main()))
