import asyncio
import base64
import os
import sys
import logging

# Ensure project root is in path
sys.path.insert(0, "/mnt/projects")

from src.client.engine import QuantumShieldEngine

async def run_standalone_test():
    logging.basicConfig(level=logging.INFO)
    logger = logging.getLogger("engine-test")

    key = base64.b64decode("VMYlEF9wQr47XZb4x+V1J57SWj4/bdNLVXWquSXaCyM=")
    server = "89.125.1.107"
    port = 9999

    engine = QuantumShieldEngine(key, server, port, mode="corporate")
    engine.set_status_callback(lambda s: print(f"STATUS: {s}"))

    print("--- Starting Engine Test ---")
    try:
        # We need to run this as a task because start() is a loop
        test_task = asyncio.create_task(engine.start())

        # Wait for interface to appear
        for _ in range(20):
            await asyncio.sleep(0.5)
            stats = engine.get_stats()
            if stats["active"]:
                print(f"✅ ENGINE IS ACTIVE: {stats}")
                break
        else:
            print("❌ ENGINE FAILED TO BECOME ACTIVE")

        # Try pinging through tunnel
        print("Pinging 10.10.0.1 through tunnel...")
        res = os.system("ping -c 3 -W 2 10.10.0.1")
        if res == 0:
            print("✅ TUNNEL PING SUCCESS!")
        else:
            print("❌ TUNNEL PING FAILED")

    except Exception as e:
        print(f"❌ TEST ERROR: {e}")
    finally:
        engine.stop()
        print("--- Test Finished ---")

if __name__ == "__main__":
    asyncio.run(run_standalone_test())
