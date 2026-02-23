"""
Anti-Meave Oracle - Security protection for Agent Swarm

Protects against agent takeover attacks when scaling the swarm.
Implements capability-based access control and anomaly detection.

Based on the Anti-Meave Protocol from x0tta6bl4 security architecture.
"""

import asyncio
import hashlib
import hmac
import logging
import time
from dataclasses import dataclass, field
from enum import Enum
from typing import Any, Callable, Dict, List, Optional, Set
from datetime import datetime, timezone

logger = logging.getLogger(__name__)


class ThreatLevel(Enum):
    """Threat severity levels."""
    NONE = 0
    LOW = 1
    MEDIUM = 2
    HIGH = 3
    CRITICAL = 4


class CapabilityType(Enum):
    """Types of agent capabilities."""
    READ = "read"
    WRITE = "write"
    EXECUTE = "execute"
    ADMIN = "admin"
    NETWORK = "network"
    CRYPTO = "crypto"


@dataclass
class Capability:
    """
    Agent capability with scope restrictions.
    
    Based on principle of least privilege - agents can only
    affect limited nodes/percentage of network.
    """
    name: str
    capability_type: CapabilityType
    scope: str = "local"  # local, regional, network
    max_affected_nodes: int = 1
    max_affected_percentage: float = 0.01  # 1%
    expires_at: Optional[float] = None
    approved_by: Optional[str] = None
    approval_time: Optional[float] = None
    
    def is_expired(self) -> bool:
        """Check if capability has expired."""
        if self.expires_at is None:
            return False
        return time.time() > self.expires_at
    
    def is_valid(self) -> bool:
        """Check if capability is valid."""
        return not self.is_expired()
    
    def can_affect_nodes(self, node_count: int, network_size: int) -> bool:
        """Check if action affects allowed number of nodes."""
        if node_count > self.max_affected_nodes:
            return False
        percentage = node_count / max(network_size, 1)
        return percentage <= self.max_affected_percentage


@dataclass
class AgentProfile:
    """Profile for a registered agent."""
    agent_id: str
    swarm_id: str
    capabilities: Dict[str, Capability] = field(default_factory=dict)
    registered_at: float = field(default_factory=time.time)
    last_activity: float = field(default_factory=time.time)
    actions_taken: int = 0
    nodes_affected: Set[str] = field(default_factory=set)
    threat_score: float = 0.0
    is_suspended: bool = False
    
    def record_action(self, nodes: List[str]) -> None:
        """Record an action taken by the agent."""
        self.actions_taken += 1
        self.last_activity = time.time()
        self.nodes_affected.update(nodes)


@dataclass
class ThreatAlert:
    """Alert for detected threat."""
    alert_id: str
    agent_id: str
    threat_level: ThreatLevel
    description: str
    detected_at: float = field(default_factory=time.time)
    resolved: bool = False
    resolved_at: Optional[float] = None
    metadata: Dict[str, Any] = field(default_factory=dict)


class AntiMeaveOracle:
    """
    Oracle for protecting Agent Swarm against takeover attacks.
    
    Key protections:
    1. Capability-based access control
    2. Scope restrictions (max nodes/percentage)
    3. Anomaly detection in agent behavior
    4. Automatic suspension of suspicious agents
    5. Audit logging of all actions
    
    Usage:
        oracle = AntiMeaveOracle(network_size=1000)
        
        # Register agent
        capabilities = [
            Capability("monitoring", CapabilityType.READ, scope="regional")
        ]
        oracle.register_agent("agent_001", "swarm_abc", capabilities)
        
        # Validate action
        if oracle.validate_action("agent_001", "read", ["node_1", "node_2"]):
            # Allow action
            pass
        
        # Check for threats
        threats = oracle.detect_threats()
    """
    
    def __init__(
        self,
        network_size: int = 1000,
        max_agent_actions_per_minute: int = 100,
        max_nodes_per_agent: int = 50,
        anomaly_threshold: float = 0.8,
        auto_suspend: bool = True,
    ):
        """
        Initialize Anti-Meave Oracle.
        
        Args:
            network_size: Total nodes in the network
            max_agent_actions_per_minute: Rate limit for agent actions
            max_nodes_per_agent: Maximum nodes an agent can affect
            anomaly_threshold: Threshold for anomaly detection (0-1)
            auto_suspend: Whether to auto-suspend suspicious agents
        """
        self.network_size = network_size
        self.max_actions_per_minute = max_agent_actions_per_minute
        self.max_nodes_per_agent = max_nodes_per_agent
        self.anomaly_threshold = anomaly_threshold
        self.auto_suspend = auto_suspend
        
        # Agent registry
        self._agents: Dict[str, AgentProfile] = {}
        self._lock = asyncio.Lock()
        
        # Threat tracking
        self._alerts: List[ThreatAlert] = []
        self._suspended_agents: Set[str] = set()
        
        # Rate limiting
        self._action_timestamps: Dict[str, List[float]] = {}
        
        # Audit log
        self._audit_log: List[Dict[str, Any]] = []
        
        # Metrics
        self._metrics = {
            "agents_registered": 0,
            "agents_suspended": 0,
            "actions_validated": 0,
            "actions_rejected": 0,
            "threats_detected": 0,
        }
        
        logger.info(f"AntiMeaveOracle initialized for network of {network_size} nodes")
    
    async def register_agent(
        self,
        agent_id: str,
        swarm_id: str,
        capabilities: List[Capability],
    ) -> bool:
        """
        Register a new agent with the oracle.
        
        Args:
            agent_id: Unique agent identifier
            swarm_id: Swarm the agent belongs to
            capabilities: List of agent capabilities
            
        Returns:
            True if registration successful
        """
        async with self._lock:
            if agent_id in self._agents:
                logger.warning(f"Agent {agent_id} already registered")
                return False
            
            # Validate capabilities
            for cap in capabilities:
                if not cap.is_valid():
                    logger.warning(f"Invalid capability: {cap.name}")
                    return False
            
            # Create profile
            profile = AgentProfile(
                agent_id=agent_id,
                swarm_id=swarm_id,
                capabilities={cap.name: cap for cap in capabilities},
            )
            
            self._agents[agent_id] = profile
            self._metrics["agents_registered"] += 1
            
            # Log registration
            self._log_audit("agent_registered", {
                "agent_id": agent_id,
                "swarm_id": swarm_id,
                "capabilities": [cap.name for cap in capabilities],
            })
            
            logger.info(f"Agent {agent_id} registered with {len(capabilities)} capabilities")
            return True
    
    async def unregister_agent(self, agent_id: str) -> bool:
        """Unregister an agent from the oracle."""
        async with self._lock:
            if agent_id not in self._agents:
                return False
            
            del self._agents[agent_id]
            self._suspended_agents.discard(agent_id)
            
            self._log_audit("agent_unregistered", {"agent_id": agent_id})
            
            logger.info(f"Agent {agent_id} unregistered")
            return True
    
    async def validate_action(
        self,
        agent_id: str,
        action_type: str,
        target_nodes: List[str],
        capability_name: Optional[str] = None,
    ) -> bool:
        """
        Validate if an agent can perform an action.
        
        Args:
            agent_id: Agent performing the action
            action_type: Type of action (read, write, execute, etc.)
            target_nodes: Nodes affected by the action
            capability_name: Specific capability to use
            
        Returns:
            True if action is allowed
        """
        async with self._lock:
            # Check if agent exists
            profile = self._agents.get(agent_id)
            if not profile:
                logger.warning(f"Unknown agent: {agent_id}")
                self._metrics["actions_rejected"] += 1
                return False
            
            # Check if suspended
            if profile.is_suspended or agent_id in self._suspended_agents:
                logger.warning(f"Agent {agent_id} is suspended")
                self._metrics["actions_rejected"] += 1
                return False
            
            # Rate limiting
            if not self._check_rate_limit(agent_id):
                logger.warning(f"Agent {agent_id} exceeded rate limit")
                await self._create_alert(
                    agent_id,
                    ThreatLevel.MEDIUM,
                    "Rate limit exceeded",
                )
                self._metrics["actions_rejected"] += 1
                return False
            
            # Check capability
            capability = None
            if capability_name:
                capability = profile.capabilities.get(capability_name)
            else:
                # Find matching capability by action type
                for cap in profile.capabilities.values():
                    if cap.capability_type.value == action_type:
                        capability = cap
                        break
            
            if not capability:
                logger.warning(f"Agent {agent_id} lacks capability for {action_type}")
                self._metrics["actions_rejected"] += 1
                return False
            
            if not capability.is_valid():
                logger.warning(f"Agent {agent_id} capability {capability.name} is invalid/expired")
                self._metrics["actions_rejected"] += 1
                return False
            
            # Check scope
            if not capability.can_affect_nodes(len(target_nodes), self.network_size):
                logger.warning(
                    f"Agent {agent_id} attempting to affect too many nodes: "
                    f"{len(target_nodes)} (max: {capability.max_affected_nodes})"
                )
                await self._create_alert(
                    agent_id,
                    ThreatLevel.HIGH,
                    f"Scope violation: attempting to affect {len(target_nodes)} nodes",
                )
                self._metrics["actions_rejected"] += 1
                return False
            
            # Check total nodes affected
            potential_nodes = profile.nodes_affected | set(target_nodes)
            if len(potential_nodes) > self.max_nodes_per_agent:
                logger.warning(
                    f"Agent {agent_id} would exceed max nodes: "
                    f"{len(potential_nodes)} > {self.max_nodes_per_agent}"
                )
                await self._create_alert(
                    agent_id,
                    ThreatLevel.HIGH,
                    f"Max nodes exceeded: {len(potential_nodes)}",
                )
                self._metrics["actions_rejected"] += 1
                return False
            
            # Record action
            profile.record_action(target_nodes)
            self._metrics["actions_validated"] += 1
            
            # Log action
            self._log_audit("action_validated", {
                "agent_id": agent_id,
                "action_type": action_type,
                "target_nodes": target_nodes,
                "capability": capability.name,
            })
            
            return True
    
    def _check_rate_limit(self, agent_id: str) -> bool:
        """Check if agent is within rate limit."""
        current_time = time.time()
        
        if agent_id not in self._action_timestamps:
            self._action_timestamps[agent_id] = []
        
        # Clean old timestamps
        timestamps = self._action_timestamps[agent_id]
        timestamps = [t for t in timestamps if current_time - t < 60]
        self._action_timestamps[agent_id] = timestamps
        
        # Check limit
        if len(timestamps) >= self.max_actions_per_minute:
            return False
        
        # Record timestamp
        timestamps.append(current_time)
        return True
    
    async def detect_threats(self) -> List[ThreatAlert]:
        """
        Detect potential threats in agent behavior.
        
        Returns:
            List of threat alerts
        """
        threats = []
        agents_to_suspend: List[str] = []

        async with self._lock:
            for agent_id, profile in self._agents.items():
                threat_score = self._calculate_threat_score(profile)
                profile.threat_score = threat_score
                
                if threat_score >= self.anomaly_threshold:
                    alert = await self._create_alert(
                        agent_id,
                        ThreatLevel.HIGH,
                        f"Anomaly detected: threat score {threat_score:.2f}",
                        metadata={"threat_score": threat_score},
                    )
                    threats.append(alert)
                    
                    # Auto-suspend if enabled
                    if self.auto_suspend:
                        agents_to_suspend.append(agent_id)

        # Suspend outside the lock to avoid re-entrant lock deadlock.
        for agent_id in agents_to_suspend:
            await self.suspend_agent(agent_id)

        return threats
    
    def _calculate_threat_score(self, profile: AgentProfile) -> float:
        """
        Calculate threat score for an agent.
        
        Factors:
        - Rate of actions
        - Nodes affected
        - Capability usage patterns
        - Time since registration
        """
        score = 0.0
        
        # Factor 1: Action rate
        action_rate = profile.actions_taken / max(1, time.time() - profile.registered_at) * 60
        if action_rate > self.max_actions_per_minute:
            score += 0.3
        
        # Factor 2: Nodes affected
        node_ratio = len(profile.nodes_affected) / max(self.network_size, 1)
        if node_ratio > 0.1:  # Affecting > 10% of network
            score += 0.4
        elif node_ratio > 0.05:  # Affecting > 5%
            score += 0.2
        
        # Factor 3: New agent with many actions
        time_since_registration = time.time() - profile.registered_at
        if time_since_registration < 60 and profile.actions_taken > 10:
            score += 0.2
        
        # Factor 4: Suspicious patterns
        if profile.actions_taken > 100 and len(profile.nodes_affected) < 5:
            # Many actions but few nodes - possible probing
            score += 0.1
        
        return min(score, 1.0)
    
    async def _create_alert(
        self,
        agent_id: str,
        threat_level: ThreatLevel,
        description: str,
        metadata: Optional[Dict[str, Any]] = None,
    ) -> ThreatAlert:
        """Create a threat alert."""
        alert = ThreatAlert(
            alert_id=f"alert_{int(time.time() * 1000)}",
            agent_id=agent_id,
            threat_level=threat_level,
            description=description,
            metadata=metadata or {},
        )
        
        self._alerts.append(alert)
        self._metrics["threats_detected"] += 1
        
        logger.warning(
            f"Threat alert: {alert.alert_id} - Agent {agent_id} - "
            f"{threat_level.name}: {description}"
        )
        
        return alert
    
    async def suspend_agent(self, agent_id: str) -> bool:
        """Suspend an agent."""
        async with self._lock:
            profile = self._agents.get(agent_id)
            if not profile:
                return False
            
            profile.is_suspended = True
            self._suspended_agents.add(agent_id)
            self._metrics["agents_suspended"] += 1
            
            self._log_audit("agent_suspended", {"agent_id": agent_id})
            
            logger.warning(f"Agent {agent_id} suspended")
            return True
    
    async def unsuspend_agent(self, agent_id: str) -> bool:
        """Unsuspend an agent."""
        async with self._lock:
            profile = self._agents.get(agent_id)
            if not profile:
                return False
            
            profile.is_suspended = False
            self._suspended_agents.discard(agent_id)
            
            self._log_audit("agent_unsuspended", {"agent_id": agent_id})
            
            logger.info(f"Agent {agent_id} unsuspended")
            return True
    
    def get_agent_profile(self, agent_id: str) -> Optional[AgentProfile]:
        """Get profile for an agent."""
        return self._agents.get(agent_id)
    
    def get_alerts(
        self,
        agent_id: Optional[str] = None,
        unresolved_only: bool = False,
    ) -> List[ThreatAlert]:
        """Get threat alerts."""
        alerts = self._alerts
        
        if agent_id:
            alerts = [a for a in alerts if a.agent_id == agent_id]
        
        if unresolved_only:
            alerts = [a for a in alerts if not a.resolved]
        
        return alerts
    
    async def resolve_alert(self, alert_id: str) -> bool:
        """Resolve a threat alert."""
        for alert in self._alerts:
            if alert.alert_id == alert_id:
                alert.resolved = True
                alert.resolved_at = time.time()
                return True
        return False
    
    def get_metrics(self) -> Dict[str, Any]:
        """Get oracle metrics."""
        return {
            **self._metrics,
            "active_agents": len(self._agents),
            "suspended_agents": len(self._suspended_agents),
            "unresolved_alerts": len([a for a in self._alerts if not a.resolved]),
        }
    
    def _log_audit(self, event: str, data: Dict[str, Any]) -> None:
        """Log an audit event."""
        entry = {
            "timestamp": time.time(),
            "event": event,
            "data": data,
        }
        self._audit_log.append(entry)
        
        # Keep log bounded
        if len(self._audit_log) > 10000:
            self._audit_log = self._audit_log[-5000:]
    
    def get_audit_log(
        self,
        agent_id: Optional[str] = None,
        event_type: Optional[str] = None,
        limit: int = 100,
    ) -> List[Dict[str, Any]]:
        """Get audit log entries."""
        log = self._audit_log
        
        if agent_id:
            log = [e for e in log if e.get("data", {}).get("agent_id") == agent_id]
        
        if event_type:
            log = [e for e in log if e.get("event") == event_type]
        
        return log[-limit:]
    
    async def shutdown(self) -> None:
        """Shutdown the oracle."""
        logger.info("AntiMeaveOracle shutting down")
        
        # Suspend all agents
        for agent_id in list(self._agents.keys()):
            await self.suspend_agent(agent_id)
        
        self._agents.clear()
        self._suspended_agents.clear()


# Singleton instance
_oracle: Optional[AntiMeaveOracle] = None


def get_oracle() -> AntiMeaveOracle:
    """Get the singleton oracle instance."""
    global _oracle
    if _oracle is None:
        _oracle = AntiMeaveOracle()
    return _oracle


def set_oracle(oracle: AntiMeaveOracle) -> None:
    """Set the singleton oracle instance."""
    global _oracle
    _oracle = oracle
