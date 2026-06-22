#!/usr/bin/env python3
"""
Verify peaq Relay API (Modular Machine Function) for x0tta6bl4.
This script tests the PQC tunnel initiation endpoint using a local uvicorn instance.
"""

import asyncio
import json
import os
import sys
import time
from pathlib import Path

import httpx
import uvicorn
from multiprocessing import Process

ROOT = Path(__file__).resolve().parents[2]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

def run_server():
    from src.core.app import app
    print("🚀 Starting local uvicorn for verification...")
    uvicorn.run(app, host="127.0.0.1", port=8123, log_level="info")

async def main():
    print("🌍 x0tta6bl4 peaq Integration: Milestone 2 API Verification")
    print("-----------------------------------------------------------")

    # Disable proxy for local requests
    os.environ["HTTP_PROXY"] = ""
    os.environ["HTTPS_PROXY"] = ""
    os.environ["ALL_PROXY"] = ""
    os.environ["no_proxy"] = "127.0.0.1,localhost"

    # Start API in background
    server_process = Process(target=run_server)
    server_process.start()
    time.sleep(3)  # Wait for startup

    try:
        async with httpx.AsyncClient(base_url="http://127.0.0.1:8123", trust_env=False) as client:
            # 1. Test PQC Tunnel Initiation
            payload = {
                "machine_did": "did:peaq:0x112303694831DCD04f0bf3C85453fdcE18085E06",
                "pqc_algorithm": "ML-KEM-768",
                "region": "eu-west"
            }
            print(f"🔹 Requesting PQC Tunnel for: {payload['machine_did']}")
            
            response = await client.post("/api/v1/peaq/relay/tunnel", json=payload)
            
            if response.status_code == 200:
                data = response.json()
                print("✅ Tunnel Initiated Successfully!")
                print(json.dumps(data, indent=2))
                
                # Check claim gates
                if data.get("peaq_relay_claim_gate", {}).get("tunnel_initiated_claim_allowed"):
                    print("✅ Evidence: Bounded tunnel initiation claim allowed.")
                else:
                    print("❌ Evidence: Claim gate missing or failed.")
            else:
                print(f"❌ API Request Failed: {response.status_code} - {response.text}")
                return 1

            # 2. Test Tunnel Status
            tunnel_id = data["tunnel_id"]
            print(f"\n🔹 Checking Status for Tunnel: {tunnel_id}")
            status_response = await client.get(f"/api/v1/peaq/relay/status/{tunnel_id}")
            
            if status_response.status_code == 200:
                print("✅ Status Retrieve Successful.")
                print(json.dumps(status_response.json(), indent=2))
            else:
                print(f"❌ Status Request Failed: {status_response.status_code}")
                return 1

    finally:
        server_process.terminate()
        server_process.join()

    print("\n🏆 Milestone 2: Modular Machine Function - READY (API Evidence)")
    return 0

if __name__ == "__main__":
    sys.exit(asyncio.run(main()))
