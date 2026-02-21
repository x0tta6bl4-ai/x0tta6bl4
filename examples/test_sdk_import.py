"""
test_sdk_import.py: A simple demonstration of the libx0t SDK.

This script proves that the project refactoring into an SDK was successful.
It imports the MeshRouter from the new library, instantiates it, and prints its status.
"""

import asyncio
import sys
import os
import json

# This is a temporary hack to allow importing from the parent directory.
# In a real application, the libx0t SDK would be installed via pip.
sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), '..')))

try:
    from libx0t.network.mesh_router import MeshRouter
    print("✅ SDK Import Successful: MeshRouter imported from libx0t.network.mesh_router")
except ImportError as e:
    print(f"❌ SDK Import Failed: Could not import MeshRouter. Error: {e}")
    print("\n   Please ensure you are running this script from the project's root directory.")
    sys.exit(1)

async def main():
    """
    Main function to instantiate and test the MeshRouter.
    """
    print("\n" + "="*30)
    print("  libx0t SDK Smoke Test")
    print("="*30 + "\n")

    print("1. Instantiating MeshRouter(node_id='test-sdk-node')...")
    # We instantiate the router with a dummy node_id
    router = MeshRouter(node_id="test-sdk-node")
    print("   ... MeshRouter instantiated successfully.")

    print("\n2. Getting initial stats from the router...")
    # We call a method to get its internal state
    stats = router.get_stats()
    print("   ... get_stats() returned successfully.")

    print("\n3. Router Status:")
    # We print the stats to verify the object is alive and well
    # Using json.dumps for pretty printing
    print(json.dumps(stats, indent=2))
    
    print("\n" + "="*30)
    print("  ✅ Smoke Test Passed!")
    print("="*30)
    print("\nThis confirms the basic SDK structure is working.")

if __name__ == "__main__":
    asyncio.run(main())
