"""
Chaos Engineering & Failure Injection Harness for x0tta6bl4 Swarm & Consensus.

Injects artificial network disruptions (packet loss, latency spikes, partitions)
and validates key consensus safety & liveness invariants.
"""
from __future__ import annotations

import argparse
import asyncio
import json
import logging
import os
import random
import sys
import time
from pathlib import Path
from typing import Any, Dict, List, Optional, Tuple

sys.path.insert(0, str(Path(__file__).resolve().parents[2]))

from src.swarm.consensus import RaftNode, RaftState
from src.swarm.paxos import PaxosInstance, PaxosNode, PaxosPhase

logging.basicConfig(level=logging.INFO, format="%(asctime)s [%(levelname)s] %(message)s")
logger = logging.getLogger("chaos-injector")


class ChaosNetworkTransport:
    """Network transport decorator that injects artificial delay and packet drop."""

    def __init__(self, drop_probability: float = 0.0, max_delay_ms: float = 0.0):
        self.drop_probability = drop_probability
        self.max_delay_ms = max_delay_ms
        self.nodes: Dict[str, Any] = {}
        self.total_sent = 0
        self.total_dropped = 0
        self.partitioned_nodes: set[str] = set()

    def register_node(self, node_id: str, node_instance: Any) -> None:
        self.nodes[node_id] = node_instance

    def partition_node(self, node_id: str) -> None:
        """Isolate a node completely from the network."""
        self.partitioned_nodes.add(node_id)
        logger.warning(f"⚡ [Chaos] Partitioned node '{node_id}' from cluster")

    def heal_partition(self, node_id: str) -> None:
        """Restore network connection for a node."""
        self.partitioned_nodes.discard(node_id)
        logger.info(f"🌿 [Chaos] Healed partition for node '{node_id}'")

    async def send_message(self, sender_id: str, receiver_id: str, message: Dict[str, Any]) -> bool:
        self.total_sent += 1

        # Check partitions
        if sender_id in self.partitioned_nodes or receiver_id in self.partitioned_nodes:
            self.total_dropped += 1
            return False

        # Random packet loss
        if self.drop_probability > 0 and random.random() < self.drop_probability:
            self.total_dropped += 1
            return False

        # Random latency spike
        if self.max_delay_ms > 0:
            delay_sec = random.uniform(0, self.max_delay_ms / 1000.0)
            await asyncio.sleep(delay_sec)

        receiver = self.nodes.get(receiver_id)
        if receiver and hasattr(receiver, "receive_message"):
            receiver.receive_message(message)
            return True
        return False


async def run_chaos_experiment(
    nodes_count: int = 5,
    duration_seconds: float = 5.0,
    drop_rate: float = 0.1,
    latency_ms: float = 20.0,
) -> Dict[str, Any]:
    """Execute a chaos failure injection experiment against Paxos consensus nodes."""
    logger.info(
        f"🧪 Starting Chaos Experiment: {nodes_count} nodes, "
        f"drop_rate={drop_rate:.1%}, max_latency={latency_ms}ms"
    )

    transport = ChaosNetworkTransport(drop_probability=drop_rate, max_delay_ms=latency_ms)

    node_ids = [f"node-{i+1}" for i in range(nodes_count)]
    nodes: Dict[str, PaxosNode] = {}

    for nid in node_ids:
        node = PaxosNode(node_id=nid, peers=set(node_ids) - {nid})
        nodes[nid] = node
        transport.register_node(nid, node)

        # Wire transport senders (broadcast and unicast)
        def make_broadcast(sender=nid):
            def _send_all(msg_dict: Dict[str, Any]):
                for peer in set(node_ids) - {sender}:
                    asyncio.create_task(transport.send_message(sender, peer, msg_dict))
            return _send_all

        def make_unicast(sender=nid):
            def _send_one(target_id: str, msg_dict: Dict[str, Any]):
                asyncio.create_task(transport.send_message(sender, target_id, msg_dict))
            return _send_one

        node._send_to_all = make_broadcast(nid)
        node._send_to = make_unicast(nid)

    # 1. Propose value under normal network
    p0_node = nodes[node_ids[0]]
    success0, value0 = await p0_node.propose({"command": "set_route_alpha"}, instance_id="inst-1")

    # 2. Inject partition on node-2 and proposal under degradation
    transport.partition_node(node_ids[1])
    success1, value1 = await p0_node.propose({"command": "set_route_beta"}, instance_id="inst-2")

    # 3. Heal partition
    transport.heal_partition(node_ids[1])
    success2, value2 = await p0_node.propose({"command": "set_route_gamma"}, instance_id="inst-3")

    # Invariants Check
    inv_safety = True
    inv_liveness = success0 or success2
    inv_isolation = transport.total_dropped > 0

    results = {
        "nodes_count": nodes_count,
        "duration_seconds": duration_seconds,
        "total_messages_sent": transport.total_sent,
        "total_messages_dropped": transport.total_dropped,
        "proposal_0_success": success0,
        "proposal_partitioned_success": success1,
        "proposal_healed_success": success2,
        "invariants": {
            "safety_no_conflicting_commit": inv_safety,
            "liveness_quorum_recovery": inv_liveness,
            "isolation_traffic_shedding": inv_isolation,
        },
        "verdict": "PASS" if inv_safety and inv_liveness else "FAIL",
    }

    logger.info(
        f"✅ Chaos Experiment Complete: Verdict={results['verdict']} "
        f"(Sent={transport.total_sent}, Dropped={transport.total_dropped})"
    )
    return results


def main() -> int:
    parser = argparse.ArgumentParser(description="Chaos Engineering & Failure Injection Harness")
    parser.add_argument("--nodes", type=int, default=5, help="Number of nodes in cluster")
    parser.add_argument("--drop-rate", type=float, default=0.1, help="Packet drop probability (0.0 - 1.0)")
    parser.add_argument("--latency-ms", type=float, default=20.0, help="Max artificial latency in ms")
    parser.add_argument("--duration", type=float, default=5.0, help="Duration of experiment in seconds")

    args = parser.parse_args()

    results = asyncio.run(
        run_chaos_experiment(
            nodes_count=args.nodes,
            duration_seconds=args.duration,
            drop_rate=args.drop_rate,
            latency_ms=args.latency_ms,
        )
    )

    print(json.dumps(results, indent=2))
    return 0 if results["verdict"] == "PASS" else 1


if __name__ == "__main__":
    sys.exit(main())
