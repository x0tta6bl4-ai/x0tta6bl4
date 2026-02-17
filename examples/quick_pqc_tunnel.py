import asyncio
import logging
import sys
import os

# Add src to sys.path so libx0t is found as a top-level package
sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), "..", "src")))

from libx0t import x0t

# Configure logging to see the SDK in action
logging.basicConfig(level=logging.INFO, format='%(levelname)s: %(message)s')

async def main():
    """
    The 'Visionary' Experience: 
    Connecting and creating a PQC tunnel in just a few lines.
    """
    print("--- 🚀 Starting x0tta6bl4 SDK Demo ---")
    
    # 1. Initialize and Connect (One line)
    mesh = x0t.X0T()
    await mesh.connect(pqc_level="military")
    
    # 2. Create Secure Tunnel
    tunnel = mesh.create_tunnel("node-alpha-7")
    
    # 3. Send Data
    await tunnel.send(b"Top Secret DeepTech Data")
    
    print("--- ✅ SDK Demo Finished ---")

if __name__ == "__main__":
    asyncio.run(main())
