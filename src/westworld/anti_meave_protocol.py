"""
Anti-Meave Protocol: Prevents single-agent takeover of mesh network.

Part 2 of Westworld Integration.
Implements capability-based access control with macaroons and anomaly detection.
"""

import asyncio
import hmac
import hashlib
import time
from dataclasses import dataclass, field
from typing import Dict, List, Optional, Tuple
from enum import Enum
import logging

logger = logging.getLogger(__name__)


class CapabilityScope(Enum):
    """Scope of a capability."""
    LOCAL = "local"              # Single node only
    REGIONAL = "regional"        # Up to 100 nodes in same region
    NETWORK = "network"          # All nodes (requires DAO vote)


class Macaroon:
    """
    Cryptographic authorization token with delegatable caveats.
    Inspired by Google Macaroons.
    """
    
    def __init__(self,
                 identifier: str,
                 key: bytes,
                 location: str = "x0tta6bl4.local"):
        self.identifier = identifier
        self.key = key
        self.location = location
        self.caveats: List[str] = []
        self.signature: Optional[str] = None
    
    def add_caveat(self, caveat: str):
        """Add a restriction (caveat) to this macaroon."""
        self.caveats.append(caveat)
    
    def bind(self) -> str:
        """Serialize and sign the macaroon."""
        msg = f"{self.identifier}|{self.location}|" + "|".join(self.caveats)
        signature = hmac.new(self.key, msg.encode(), hashlib.sha256).hexdigest()
        self.signature = signature
        return f"{msg}|{signature}"
    
    @staticmethod
    def verify(token: str, key: bytes) -> bool:
        """Verify macaroon signature."""
        parts = token.split("|")
        if len(parts) < 2:
            return False
        
        msg = "|".join(parts[:-1])
        signature = parts[-1]
        expected = hmac.new(key, msg.encode(), hashlib.sha256).hexdigest()
        
        return hmac.compare_digest(signature, expected)


@dataclass
class AgentCapability:
    """Represents a specific capability for an agent."""
    name: str                           # e.g., "route_to_peers"
    scope: CapabilityScope              # Local, Regional, or Network
    max_affected_nodes: int             # Max nodes this can affect
    max_affected_percentage: float      # Max % of network (0-1)
    effective_until: float              # Unix timestamp
    required_approvals: List[str] = field(default_factory=list)
    # Examples: ["peer_sig", "dao_vote", "multi_sig_3_of_5"]
    
    def is_valid(self) -> bool:
        """Check if capability is still valid."""
        return time.time() < self.effective_until
    
    def allows_nodes(self, node_count: int, network_size: int) -> bool:
        """Check if capability permits affecting this many nodes."""
        percentage = node_count / max(network_size, 1)
        return (node_count <= self.max_affected_nodes and
                percentage <= self.max_affected_percentage)


@dataclass
class AgentPolicy:
    """Defines what an agent is authorized to do."""
    agent_id: str
    capabilities: Dict[str, AgentCapability]
    macaroon: Optional[str] = None
    last_verified: float = field(default_factory=time.time)
    
    def verify_macaroon(self, key: bytes) -> bool:
        """Verify the macaroon is still valid."""
        if not self.macaroon:
            return False
        return Macaroon.verify(self.macaroon, key)


class MeshNodeController:
    """
    Local controller on each mesh node.
    Enforces capability checks before executing any global action.
    Prevents Meave-style silent overrides.
    """
    
    def __init__(self,
                 node_id: str,
                 mesh_size: int,
                 private_key_bytes: bytes):
        self.node_id = node_id
        self.mesh_size = mesh_size
        self.private_key = private_key_bytes
        
        # Local state
        self.peer_policies: Dict[str, AgentPolicy] = {}
        self.local_signature_key = hashlib.sha256(private_key_bytes).hexdigest()
        
        # Audit trail
        self.action_log: List[Dict] = []
    
    def register_agent(self, policy: AgentPolicy):
        """Register an agent and its capabilities on this node."""
        self.peer_policies[policy.agent_id] = policy
        logger.info(f"Agent registered: {policy.agent_id}")
    
    async def execute_action(self,
                            agent_id: str,
                            action: str,
                            target_node_ids: List[str]) -> Tuple[bool, str]:
        """
        Execute action only if agent has required capability.
        
        Returns:
            (success: bool, reason: str)
        """
        policy = self.peer_policies.get(agent_id)
        if not policy:
            return False, f"Agent {agent_id} not registered"
        
        # Check macaroon validity
        if not policy.verify_macaroon(self.local_signature_key.encode()):
            return False, "Invalid or expired macaroon"
        
        # Check capability exists for this action
        capability = policy.capabilities.get(action)
        if not capability:
            return False, f"Agent lacks capability '{action}'"
        
        # Check capability not expired
        if not capability.is_valid():
            return False, "Capability expired"
        
        # Check scope
        num_targets = len(target_node_ids)
        if not capability.allows_nodes(num_targets, self.mesh_size):
            return False, (
                f"Action would affect {num_targets} nodes ({num_targets/self.mesh_size*100:.1f}%), "
                f"but capability limits to {capability.max_affected_nodes} "
                f"({capability.max_affected_percentage*100:.1f}% of {self.mesh_size} nodes)"
            )
        
        # Check required approvals
        if "peer_sig" in capability.required_approvals:
            if not await self._get_peer_signatures(action, target_node_ids):
                return False, "Could not obtain required peer signatures"
        
        if "dao_vote" in capability.required_approvals:
            if not await self._verify_dao_vote(action):
                return False, "DAO vote required but not found"
        
        # All checks passed
        self._log_action(agent_id, action, target_node_ids, "SUCCESS")
        logger.info(f"Action executed: {agent_id}.{action} on {num_targets} nodes")
        return True, "Action executed successfully"
    
    async def _get_peer_signatures(self, action: str, target_node_ids: List[str]) -> bool:
        """
        For mass changes (>10% network), require signatures from random peers.
        Prevents silent push of changes.
        """
        percentage = len(target_node_ids) / self.mesh_size
        if percentage < 0.1:
            # No peer signatures required for small changes
            return True
        
        # For mass changes: require 3 peer signatures
        required_sigs = min(3, self.mesh_size // 10)
        
        logger.info(f"  → Requesting {required_sigs} peer signatures for mass change...")
        
        peer_sigs = []
        for i in range(required_sigs):
            peer_id = self._select_random_peer()
            sig = await self._request_peer_signature(peer_id, action)
            if sig:
                peer_sigs.append(sig)
                logger.info(f"    ✓ Got signature from {peer_id}")
        
        success = len(peer_sigs) >= required_sigs
        if success:
            logger.info(f"  ✓ Obtained {len(peer_sigs)} peer signatures")
        else:
            logger.warning(f"  ✗ Only {len(peer_sigs)}/{required_sigs} peer signatures")
        
        return success
    
    async def _verify_dao_vote(self, action: str) -> bool:
        """
        For global policy changes, verify DAO vote on Snapshot.
        """
        # Query Snapshot API
        vote_id = await self._lookup_dao_vote_for_action(action)
        if not vote_id:
            logger.warning(f"  ✗ No DAO vote found for action: {action}")
            return False
        
        # Check vote passed
        result = await self._fetch_dao_vote_result(vote_id)
        approved = result.get("approved", False)
        
        if approved:
            logger.info(f"  ✓ DAO vote {vote_id} approved")
        else:
            logger.warning(f"  ✗ DAO vote {vote_id} not approved")
        
        return approved
    
    def _log_action(self, agent_id: str, action: str, targets: List[str], status: str):
        """Log all actions for audit trail."""
        log_entry = {
            "timestamp": time.time(),
            "agent_id": agent_id,
            "action": action,
            "target_count": len(targets),
            "target_percentage": len(targets) / self.mesh_size,
            "status": status
        }
        self.action_log.append(log_entry)
    
    # ===== Helper Methods =====
    
    def _select_random_peer(self) -> str:
        import random
        return f"node-{random.randint(1, self.mesh_size)}"
    
    async def _request_peer_signature(self, peer_id: str, action: str) -> Optional[str]:
        """Request signature from peer (would be async RPC call)."""
        # Simulate peer responding
        await asyncio.sleep(0.01)
        return f"sig_{peer_id}_{action}"
    
    async def _lookup_dao_vote_for_action(self, action: str) -> Optional[str]:
        """Look up corresponding DAO vote."""
        # Simulate finding vote
        await asyncio.sleep(0.01)
        return f"vote_{action}"
    
    async def _fetch_dao_vote_result(self, vote_id: str) -> Dict:
        """Fetch DAO vote result."""
        await asyncio.sleep(0.01)
        return {"approved": True}


class AntiMeaveOracle:
    """
    Global arbiter that prevents mesh-wide takeovers.
    Sits between mesh nodes and ensures no single agent dominates.
    """
    
    def __init__(self, network_size: int):
        self.network_size = network_size
        self.node_controllers: Dict[str, MeshNodeController] = {}
        self.capability_registry: Dict[str, AgentPolicy] = {}
        self.incident_log: List[Dict] = []
        self.network_halted = False
    
    async def monitor_for_anomalies(self) -> List[Dict]:
        """
        Continuously scan for signs of Meave-style attacks.
        """
        anomalies = []
        
        logger.info("Running anomaly detection...")
        
        # Pattern 1: Burst of global changes
        agent_call_patterns = self._analyze_call_patterns()
        for agent_id, pattern in agent_call_patterns.items():
            if pattern["global_actions_per_minute"] > 10:
                anomaly = {
                    "type": "BURST_GLOBAL_ACTIONS",
                    "agent_id": agent_id,
                    "rate": pattern["global_actions_per_minute"],
                    "severity": "HIGH"
                }
                anomalies.append(anomaly)
                logger.warning(f"  ⚠ Detected: {anomaly}")
        
        # Pattern 2: Mass simultaneous updates (>50% network)
        for node_id, controller in self.node_controllers.items():
            recent_actions = [a for a in controller.action_log
                            if time.time() - a["timestamp"] < 300]  # Last 5 min
            
            total_affected = sum(a["target_count"] for a in recent_actions)
            if total_affected > self.network_size * 0.5:
                anomaly = {
                    "type": "MASS_CHANGE_ATTEMPT",
                    "node_id": node_id,
                    "affected_count": total_affected,
                    "affected_pct": total_affected / self.network_size,
                    "severity": "CRITICAL"
                }
                anomalies.append(anomaly)
                logger.error(f"  🚨 CRITICAL: {anomaly}")
        
        # Pattern 3: Identical config changes across nodes in <1s
        config_changes = self._extract_config_changes()
        for signature, changes in config_changes.items():
            if len(changes) > self.network_size * 0.1:
                time_span = max(c["timestamp"] for c in changes) - min(c["timestamp"] for c in changes)
                if time_span < 1:
                    anomaly = {
                        "type": "SILENT_MASS_RECONFIG",
                        "config_signature": signature,
                        "affected_nodes": len(changes),
                        "time_span_seconds": time_span,
                        "severity": "CRITICAL"
                    }
                    anomalies.append(anomaly)
                    logger.error(f"  🚨 CRITICAL: {anomaly}")
        
        if anomalies:
            self._trigger_network_halt(anomalies)
        
        return anomalies
    
    def _trigger_network_halt(self, anomalies: List[Dict]):
        """If critical anomaly detected, halt all policy changes."""
        logger.error(f"\n🚨 NETWORK HALT TRIGGERED 🚨")
        logger.error(f"Potential Meave-style attack detected!")
        logger.error(f"Anomalies: {len(anomalies)}")
        
        for anomaly in anomalies:
            logger.error(f"  - {anomaly['type']}: {anomaly.get('severity', 'INFO')}")
        
        # Halt all operations
        self.network_halted = True
        for controller in self.node_controllers.values():
            controller.mesh_size = 0  # Effectively block all operations
        
        # Alert DAO
        logger.error("Alerting DAO for emergency vote...")
        logger.error("Network HALTED. Awaiting DAO emergency vote for resumption...")
    
    def _analyze_call_patterns(self) -> Dict[str, Dict]:
        """Analyze historical action patterns by agent."""
        patterns = {}
        
        for controller in self.node_controllers.values():
            for action in controller.action_log:
                agent_id = action["agent_id"]
                if agent_id not in patterns:
                    patterns[agent_id] = {
                        "total_actions": 0,
                        "global_actions": 0,
                        "global_actions_per_minute": 0
                    }
                
                patterns[agent_id]["total_actions"] += 1
                if action["target_percentage"] > 0.1:
                    patterns[agent_id]["global_actions"] += 1
        
        for agent_id, pattern in patterns.items():
            # Compute rate
            pattern["global_actions_per_minute"] = pattern["global_actions"]
        
        return patterns
    
    def _extract_config_changes(self) -> Dict[str, List[Dict]]:
        """Group identical config changes by signature."""
        changes_by_sig = {}
        
        for controller in self.node_controllers.values():
            for action in controller.action_log:
                if action["status"] == "SUCCESS":
                    sig = f"{action['action']}"
                    if sig not in changes_by_sig:
                        changes_by_sig[sig] = []
                    
                    changes_by_sig[sig].append({
                        "node_id": controller.node_id,
                        "timestamp": action["timestamp"]
                    })
        
        return changes_by_sig


# ===== Demo & Testing =====

async def demo_anti_meave():
    """
    Demonstrate AntiMeave protecting against malicious agent.
    """
    
    logging.basicConfig(level=logging.INFO)
    
    print("\n" + "="*70)
    print("Anti-Meave Protocol Demo")
    print("="*70)
    
    network_size = 1000
    oracle = AntiMeaveOracle(network_size)
    
    # Create node controllers
    for i in range(network_size):
        priv_key = f"private_key_{i}".encode()
        controller = MeshNodeController(f"node-{i}", network_size, priv_key)
        oracle.node_controllers[f"node-{i}"] = controller
    
    print(f"\n✓ Created {network_size} node controllers")
    
    # Create a "good" agent with limited capability
    good_agent_id = "agent-routing-v2"
    good_capability = AgentCapability(
        name="update_routing",
        scope=CapabilityScope.REGIONAL,
        max_affected_nodes=10,
        max_affected_percentage=0.01,  # 1% of network
        effective_until=time.time() + 86400,  # 24 hours
        required_approvals=["peer_sig"]
    )
    
    good_policy = AgentPolicy(
        agent_id=good_agent_id,
        capabilities={"update_routing": good_capability}
    )
    good_policy.macaroon = Macaroon(good_agent_id, b"secret_key").bind()
    
    # Register good agent on first 10 nodes
    for i in range(10):
        oracle.node_controllers[f"node-{i}"].register_agent(good_policy)
    
    print(f"✓ Registered agent: {good_agent_id}")
    
    # TEST 1: Good agent updates 10 nodes (should succeed)
    print(f"\n[TEST 1] Good agent updates 10 nodes (ALLOWED)")
    target_nodes = [f"node-{i}" for i in range(10)]
    success, reason = await oracle.node_controllers["node-0"].execute_action(
        good_agent_id,
        "update_routing",
        target_nodes
    )
    print(f"  Result: {'✓ SUCCESS' if success else '✗ BLOCKED'}")
    print(f"  Reason: {reason}")
    
    # TEST 2: Malicious agent tries to affect 500 nodes (should fail)
    print(f"\n[TEST 2] Malicious agent tries 500 nodes (BLOCKED)")
    bad_targets = [f"node-{i}" for i in range(500)]
    success, reason = await oracle.node_controllers["node-0"].execute_action(
        good_agent_id,
        "update_routing",
        bad_targets
    )
    print(f"  Result: {'✓ SUCCESS' if success else '✗ BLOCKED'}")
    print(f"  Reason: {reason[:80]}...")
    
    # TEST 3: Run anomaly detection
    print(f"\n[TEST 3] Running anomaly detection...")
    anomalies = await oracle.monitor_for_anomalies()
    print(f"  Detected {len(anomalies)} anomalies")
    
    print(f"\n{'='*70}")
    print("✓ Anti-Meave Protocol: Protection enabled")
    print(f"{'='*70}\n")


if __name__ == "__main__":
    asyncio.run(demo_anti_meave())
