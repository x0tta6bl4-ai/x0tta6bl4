import asyncio
import time
import logging
import json
from typing import Dict, Any, Optional, Callable, List, List
from unittest.mock import MagicMock

# Set up logging for clearer output
logging.basicConfig(level=logging.DEBUG, format='%(asctime)s [%(levelname)s] %(name)s: %(message)s')
logger = logging.getLogger(__name__)

# Add project root to path to import modules
import sys
import os
sys.path.insert(0, os.path.abspath(os.path.dirname(__file__)))

from src.data_sync.crdt_sync import CRDTSync, GCounter, LWWRegister, ORSet
from src.network.routing.mesh_router import PacketType, RoutingPacket # Add RoutingPacket

# --- Mocks ---
class MockMeshRouter:
    def __init__(self, node_id: str):
        self.node_id = node_id
        self.peers: Dict[str, MockMeshRouter] = {}
        self.received_packets: List[Any] = []
        self._crdt_sync_callback: Optional[Callable] = None
        self._loop = asyncio.get_event_loop()

    def add_peer(self, peer_router: 'MockMeshRouter'):
        self.peers[peer_router.node_id] = peer_router
        peer_router.peers[self.node_id] = self

    def set_crdt_sync_callback(self, callback: Callable):
        self._crdt_sync_callback = callback

    async def send_crdt_update(self, destination: str, crdt_data: Dict[str, Any]) -> bool:
        logger.debug(f"[{self.node_id}] MockMeshRouter: Sending CRDT update to {destination}")
        if destination in self.peers:
            # Simulate network delay
            await asyncio.sleep(0.01)
            # Schedule receive on peer's loop
            peer_router = self.peers[destination]
            packet = MagicMock(spec=RoutingPacket) # Use spec=RoutingPacket
            packet.packet_type = PacketType.CRDT_SYNC
            packet.source = self.node_id
            packet.destination = destination
            packet.payload = json.dumps(crdt_data).encode('utf-8')
            
            # Directly call the _handle_crdt_sync of the receiving router
            # This bypasses the full packet routing for this mock
            # We assume from_neighbor is the immediate sender (this node)
            # The next line assumes that the receiver also has a running asyncio loop
            # and that _handle_crdt_sync_mock is a coroutine
            asyncio.ensure_future(peer_router._handle_crdt_sync_mock(packet, self.node_id), loop=peer_router._loop)
            return True
        return False
    
    # Mock handler for CRDT_SYNC packets directly
    async def _handle_crdt_sync_mock(self, packet: Any, from_neighbor: str):
        logger.debug(f"[{self.node_id}] MockMeshRouter: Received CRDT_SYNC from {packet.source}")
        self.received_packets.append(packet)
        if self._crdt_sync_callback:
            try:
                crdt_data = json.loads(packet.payload.decode('utf-8'))
                await self._crdt_sync_callback(packet.source, crdt_data)
            except Exception as e:
                logger.error(f"[{self.node_id}] MockMeshRouter: Failed to process CRDT_SYNC payload: {e}")

    # Mock get_routes for CRDTSync to discover peers
    def get_routes(self) -> Dict[str, List[MagicMock]]: # Mock RouteEntry
        mock_routes = {}
        for peer_id in self.peers.keys():
            mock_route_entry = MagicMock()
            mock_route_entry.destination = peer_id
            mock_routes[peer_id] = [mock_route_entry]
        return mock_routes

    # Mock _discover_route to avoid actual route discovery
    async def _discover_route(self, destination: str):
        logger.debug(f"[{self.node_id}] MockMeshRouter: Discovering route to {destination}")
        if destination in self.peers:
            return True # Simulate successful discovery
        return False

# --- Test ---
async def run_test():
    logger.info("Starting CRDT Sync integration test...")

    # 1. Setup two mock mesh nodes
    node1_id = "node-01"
    node2_id = "node-02"

    router1 = MockMeshRouter(node1_id)
    router2 = MockMeshRouter(node2_id)

    # Establish mock peer connection
    router1.add_peer(router2)

    sync1 = CRDTSync(node1_id, router1)
    sync2 = CRDTSync(node2_id, router2)

    # 2. Register CRDTs
    # GCounter
    gc1 = GCounter()
    gc2 = GCounter()
    sync1.register_crdt("my_counter", gc1)
    sync2.register_crdt("my_counter", gc2)

    # LWWRegister
    lww1 = LWWRegister(node1_id, "initial_value")
    lww2 = LWWRegister(node2_id, "initial_value")
    sync1.register_crdt("my_register", lww1)
    sync2.register_crdt("my_register", lww2)

    # ORSet
    orset1 = ORSet()
    orset2 = ORSet()
    sync1.register_crdt("my_set", orset1)
    sync2.register_crdt("my_set", orset2)

    # 3. Start sync loops
    await sync1.start_sync(interval_sec=0.1) # Fast sync for test
    await sync2.start_sync(interval_sec=0.1)

    logger.info("CRDT sync loops started for node-01 and node-02.")

    # 4. Perform updates on node 1
    logger.info(f"[{node1_id}] Performing updates on CRDTs...")
    gc1.increment(node1_id, 5)
    lww1.set(value="node1_value_A", timestamp=time.time())
    orset1.add("item1", node1_id)
    orset1.add("item2", node1_id)

    # 5. Wait for sync to propagate
    logger.info("Waiting for sync to propagate (1 second)...")
    await asyncio.sleep(1.0)

    # 6. Verify state on node 2
    logger.info(f"[{node2_id}] Verifying CRDT states after sync...")
    assert sync2.crdts["my_counter"].value() == 5
    assert sync2.crdts["my_register"].value == "node1_value_A"
    assert "item1" in sync2.crdts["my_set"].value()
    assert "item2" in sync2.crdts["my_set"].value()
    logger.info(f"[{node2_id}] CRDTs verified: my_counter={sync2.crdts['my_counter'].value()}, my_register={sync2.crdts['my_register'].value}, my_set={sync2.crdts['my_set'].value()}")
    
    # 7. Perform updates on node 2, creating a conflict for LWWRegister
    logger.info(f"[{node2_id}] Performing updates on CRDTs (creating conflict)...")
    gc2.increment(node2_id, 3)
    lww2.set(value="node2_value_B", timestamp=time.time() + 0.05) # Ensure node2's timestamp is later
    orset2.add("item3", node2_id)
    orset2.remove("item1") # Remove item1 from node2's perspective

    # 8. Wait for sync to propagate again
    logger.info("Waiting for sync to propagate again (1 second)...")
    await asyncio.sleep(1.0)

    # 9. Verify merged state on node 1
    logger.info(f"[{node1_id}] Verifying merged CRDT states on node 1...")
    assert sync1.crdts["my_counter"].value() == 8 # 5 from node1 + 3 from node2
    assert sync1.crdts["my_register"].value == "node2_value_B" # node2 should win due to later timestamp
    assert "item1" not in sync1.crdts["my_set"].value() # Removed by node2
    assert "item2" in sync1.crdts["my_set"].value()
    assert "item3" in sync1.crdts["my_set"].value()
    logger.info(f"[{node1_id}] Merged CRDTs verified: my_counter={sync1.crdts['my_counter'].value()}, my_register={sync1.crdts['my_register'].value}, my_set={sync1.crdts['my_set'].value()}")
    
    # 10. Test LWWRegister conflict resolution with same timestamp, different node_id
    logger.info("Testing LWWRegister conflict resolution with same timestamp...")
    lww1_a = LWWRegister(node1_id, "value_A", timestamp=100.0)
    lww1_b = LWWRegister(node2_id, "value_B", timestamp=100.0) # node2_id > node1_id lexicographically
    lww1_a.merge(lww1_b)
    assert lww1_a.value == "value_B" # node2 should win
    logger.info("✅ LWWRegister (timestamp, node_id) conflict resolution test passed.")

    logger.info("✅ CRDT Sync integration test passed!")

    # 11. Stop sync loops
    await sync1.stop_sync()
    await sync2.stop_sync()

if __name__ == "__main__":
    asyncio.run(run_test())