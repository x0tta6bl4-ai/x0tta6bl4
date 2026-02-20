import asyncio
import json
import socket
import struct
import time
import pytest
import multiprocessing
from src.libx0t.network.discovery.protocol import MulticastDiscovery, DiscoveryMessage, PeerInfo
from src.libx0t.network.pqc_tunnel import PQCTunnel

# Configuration compatible with agent defaults
MULTICAST_GROUP = "239.255.77.77"
MULTICAST_PORT = 7777

@pytest.mark.asyncio
async def test_discovery_interop():
    """Test that Python can discover a Go agent via Multicast."""
    
    # 1. Start Python Multicast listener
    discovery = MulticastDiscovery(node_id="python-tester")
    discovery.start()
    
    found_agent = False
    start_time = time.time()
    
    print("\n🔍 Listening for Go Agent discovery packets...")
    
    try:
        # We wait for up to 15 seconds for the agent to announce itself
        while time.time() - start_time < 15:
            peers = discovery.get_peers()
            for peer_id, info in peers.items():
                if peer_id.startswith("x0t-"): # Go agents default prefix
                    print(f"✅ Found Go Agent: {peer_id} at {info.address}")
                    found_agent = True
                    break
            
            if found_agent:
                break
            await asyncio.sleep(1)
            
    finally:
        discovery.stop()
        
    assert found_agent, "Python failed to discover Go Agent over Multicast"

@pytest.mark.asyncio
async def test_pqc_handshake_interop():
    """Test PQC Handshake between Python and Go implementation."""
    # This requires starting the Go agent and connecting to its data port
    # For now, we'll implement a standalone handshake compatibility test
    # by simulating the wire format.
    
    python_pqc = PQCTunnel("python-node")
    
    # format: [node_id_len:2][node_id][public_key]
    init_msg = python_pqc.create_handshake_init()
    
    # In a real test, we would send this to the Go agent.
    # Here we just verify the format for cross-check.
    node_id_len = struct.unpack(">H", init_msg[:2])[0]
    node_id = init_msg[2:2+node_id_len].decode()
    pk = init_msg[2+node_id_len:]
    
    assert node_id == "python-node"
    # ML-KEM-768 PK size is 1184
    assert len(pk) == 1184
    print("✅ Python PQC Handshake Init format verified (1184 bytes PK)")

if __name__ == "__main__":
    # Integration test manual runner
    asyncio.run(test_discovery_interop())
