#!/usr/bin/env python3
"""
Setup Slot-Based Synchronization for 50+ Mesh Nodes

Configures and validates slot-based synchronization across multiple nodes.
Ensures proper slot assignment and collision avoidance.

Usage:
    python scripts/setup_slot_sync.py --nodes 50 --slots 10
"""

import asyncio
import argparse
import logging
from typing import List, Dict
from src.network.batman.slot_sync import SlotSynchronizer

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)


async def setup_slot_sync(num_nodes: int, num_slots: int) -> Dict:
    """
    Setup slot-based synchronization for multiple nodes.
    
    Args:
        num_nodes: Number of nodes to configure
        num_slots: Number of available time slots
        
    Returns:
        Dict with setup results
    """
    logger.info(f"Setting up slot synchronization: {num_nodes} nodes, {num_slots} slots")
    
    # Create synchronizers for all nodes
    synchronizers: List[SlotSynchronizer] = []
    
    for i in range(num_nodes):
        node_id = f"node-{i:03d}"
        sync = SlotSynchronizer(
            node_id=node_id,
            total_slots=num_slots,
            beacon_interval=1.0
        )
        synchronizers.append(sync)
        await sync.initialize()
    
    logger.info(f"Initialized {len(synchronizers)} slot synchronizers")
    
    # Start all synchronizers
    tasks = [sync.run() for sync in synchronizers]
    
    # Run for validation period
    logger.info("Running synchronization for 30 seconds...")
    await asyncio.sleep(30.0)
    
    # Collect status
    statuses = []
    for sync in synchronizers:
        status = sync.get_synchronization_status()
        statuses.append(status)
    
    # Stop all synchronizers
    for sync in synchronizers:
        await sync.stop()
    
    # Analyze results
    synchronized = sum(1 for s in statuses if s["state"] == "synchronized")
    collisions = sum(s["collisions"] for s in statuses)
    avg_resync = sum(s["resync_attempts"] for s in statuses) / len(statuses) if statuses else 0
    
    results = {
        "nodes_total": num_nodes,
        "nodes_synchronized": synchronized,
        "synchronization_rate": synchronized / num_nodes if num_nodes > 0 else 0.0,
        "total_collisions": collisions,
        "avg_resync_attempts": avg_resync,
        "success": synchronized / num_nodes >= 0.95  # 95% success rate target
    }
    
    logger.info(
        f"Setup complete: "
        f"{synchronized}/{num_nodes} nodes synchronized "
        f"({results['synchronization_rate']:.1%}), "
        f"{collisions} collisions, "
        f"success: {results['success']}"
    )
    
    return results


async def main():
    """CLI entry point."""
    parser = argparse.ArgumentParser(description="Setup slot-based synchronization")
    parser.add_argument("--nodes", type=int, default=50, help="Number of nodes")
    parser.add_argument("--slots", type=int, default=10, help="Number of time slots")
    parser.add_argument("--validate", action="store_true", help="Run validation tests")
    
    args = parser.parse_args()
    
    results = await setup_slot_sync(args.nodes, args.slots)
    
    if args.validate:
        # Run validation
        if results["success"]:
            print("✅ Slot synchronization setup successful")
            print(f"   Synchronization rate: {results['synchronization_rate']:.1%}")
            print(f"   Collisions: {results['total_collisions']}")
            print(f"   Average resync attempts: {results['avg_resync_attempts']:.1f}")
        else:
            print("❌ Slot synchronization setup failed")
            print(f"   Synchronization rate: {results['synchronization_rate']:.1%} (target: ≥95%)")
            exit(1)
    else:
        print(f"Setup complete: {results}")


if __name__ == "__main__":
    asyncio.run(main())

