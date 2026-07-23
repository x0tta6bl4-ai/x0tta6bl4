"""
Swarm Intelligence Core.
Main coordination logic for distributed decision-making.
"""
from __future__ import annotations
import asyncio
import logging
import time
import uuid
from datetime import datetime
from typing import Any, Callable, Dict, List, Optional, Set

from src.coordination.events import EventBus
from ..consensus_integration import (
    SwarmConsensusManager,
    ConsensusMode,
    AgentInfo,
)

from .types import (
    ConsensusStatus,
    DecisionContext,
    DecisionResult,
    SwarmAction,
    SwarmNodeInfo,
)
from .mapek import MAPEKIntegration
from .llm import KimiK25Integration

logger = logging.getLogger(__name__)

_SERVICE_AGENT = "swarm-mapek"

from ..interfaces import DecisionEngineInterface, SwarmNodeInterface

class SwarmIntelligence(DecisionEngineInterface, SwarmNodeInterface):
    @property
    def node_id(self) -> str:
        return getattr(self, "_node_id", "")

    @node_id.setter
    def node_id(self, value: str) -> None:
        self._node_id = value
    
    def __init__(
        self,
        node_id: str,
        peers: Optional[Set[str]] = None,
        consensus_mode: ConsensusMode = ConsensusMode.SIMPLE,
        default_timeout_ms: int = 100,
        enable_llm: bool = False,
        llm_endpoint: Optional[str] = None,
        event_bus: Optional[EventBus] = None,
        event_project_root: str = ".",
        policy_engine: Optional[Any] = None,
        require_policy: Optional[bool] = None,
        source_agent: str = _SERVICE_AGENT,
        spiffe_id: Optional[str] = None,
        did: Optional[str] = None,
        wallet_address: Optional[str] = None,
        safe_actuator: Optional[Any] = None,
    ):
        self.node_id = node_id
        self.peers = peers or set()
        self.consensus_mode = consensus_mode
        self.default_timeout_ms = default_timeout_ms
        
        self._consensus_manager = SwarmConsensusManager(
            node_id=node_id,
            default_mode=consensus_mode,
        )
        
        self._transport = None
        self._nodes: Dict[str, SwarmNodeInfo] = {
            node_id: SwarmNodeInfo(node_id=node_id, name=f"node-{node_id}")
        }
        self._pending_decisions: Dict[str, asyncio.Future] = {}
        self._decision_history: List[DecisionResult] = []
        
        self._status = ConsensusStatus.INITIALIZING
        self._leader_id: Optional[str] = None
        self._term = 0
        
        self._mapek = MAPEKIntegration(
            self,
            event_bus=event_bus,
            event_project_root=event_project_root,
            policy_engine=policy_engine,
            require_policy=require_policy,
            source_agent=source_agent,
            spiffe_id=spiffe_id,
            did=did,
            wallet_address=wallet_address,
            safe_actuator=safe_actuator,
        )
        self._llm = KimiK25Integration(enabled=enable_llm, api_endpoint=llm_endpoint)
        
        self._on_decision: Optional[Callable[[DecisionResult], None]] = None
        self._on_leader_change: Optional[Callable[[str], None]] = None
        
        self._total_decisions = 0
        self._successful_decisions = 0
        self._total_latency_ms = 0.0
        
        logger.info(f"SwarmIntelligence initialized for node {node_id}")
    
    async def initialize(self) -> None:
        for peer_id in self.peers:
            self._nodes[peer_id] = SwarmNodeInfo(node_id=peer_id, name=f"node-{peer_id}")
        for node_id, node_info in self._nodes.items():
            self._consensus_manager.add_agent(AgentInfo(
                agent_id=node_id, name=node_info.name,
                capabilities=node_info.capabilities, weight=node_info.weight
            ))
        await self._consensus_manager.start()
        self._status = ConsensusStatus.READY
        logger.info(f"SwarmIntelligence initialized with {len(self._nodes)} nodes")
    
    async def shutdown(self) -> None:
        await self._consensus_manager.stop()
        self._status = ConsensusStatus.OFFLINE
        logger.info(f"SwarmIntelligence shutdown for node {self.node_id}")

    def set_callbacks(
        self,
        on_decision: Optional[Callable[[DecisionResult], None]] = None,
        on_leader_change: Optional[Callable[[str], None]] = None,
    ) -> None:
        self._on_decision = on_decision
        self._on_leader_change = on_leader_change

    def add_node(self, node: SwarmNodeInfo) -> None:
        self._nodes[node.node_id] = node
        self._consensus_manager.add_agent(AgentInfo(
            agent_id=node.node_id, name=node.name,
            capabilities=node.capabilities, weight=node.weight,
        ))
        logger.info(f"Added node {node.node_id} to swarm")

    def remove_node(self, node_id: str) -> None:
        if node_id in self._nodes:
            del self._nodes[node_id]
            self._consensus_manager.remove_agent(node_id)
            logger.info(f"Removed node {node_id} from swarm")

    def get_nodes(self) -> List[SwarmNodeInfo]:
        return list(self._nodes.values())

    def get_active_nodes(self) -> List[SwarmNodeInfo]:
        return [n for n in self._nodes.values() if n.is_active]

    async def make_decision(
        self,
        context: DecisionContext,
        timeout_ms: Optional[int] = None,
        consensus_mode: Optional[ConsensusMode] = None,
    ) -> DecisionResult:
        start_time = time.time()
        timeout_ms = timeout_ms or self.default_timeout_ms
        consensus_mode = consensus_mode or self.consensus_mode
        decision_id = str(uuid.uuid4())[:8]
        options = context.options or [context.data]
        
        llm_recommendation = None
        if self._llm.enabled and len(options) > 1:
            llm_recommendation = await self._llm.enhance_decision(context, options)
        
        try:
            swarm_decision = await asyncio.wait_for(
                self._consensus_manager.decide(
                    topic=context.topic,
                    proposals=options,
                    mode=consensus_mode,
                ),
                timeout=timeout_ms / 1000.0,
            )
            latency_ms = (time.time() - start_time) * 1000
            result = DecisionResult(
                decision_id=decision_id, approved=swarm_decision.success,
                context=context, consensus_mode=consensus_mode,
                latency_ms=latency_ms, participation_rate=1.0,
                winner=swarm_decision.winner,
                reason=f"Consensus reached via {consensus_mode.value}",
                metadata={"swarm_decision": swarm_decision.to_dict(), "llm_recommendation": llm_recommendation},
            )
            self._total_decisions += 1
            if result.approved: self._successful_decisions += 1
            self._total_latency_ms += latency_ms
            self._decision_history.append(result)
            if len(self._decision_history) > 100: self._decision_history = self._decision_history[-100:]
            if self._on_decision: self._on_decision(result)
            logger.info(f"Decision {decision_id}: {'approved' if result.approved else 'rejected'} in {latency_ms:.2f}ms")
            return result
        except asyncio.TimeoutError:
            latency_ms = (time.time() - start_time) * 1000
            logger.warning(f"Decision {decision_id} timed out after {latency_ms:.2f}ms")
            result = DecisionResult(
                decision_id=decision_id, approved=False, context=context,
                consensus_mode=consensus_mode, latency_ms=latency_ms,
                reason="Decision timed out"
            )
            self._total_decisions += 1
            self._decision_history.append(result)
            return result

    async def propose_action(self, action: SwarmAction) -> DecisionResult:
        context = DecisionContext(
            topic=action.action_type, description=action.description,
            data=action.parameters, priority=action.priority,
        )
        return await self.make_decision(context=context, timeout_ms=action.timeout_ms)

    async def get_consensus_status(self) -> ConsensusStatus:
        active_nodes = len(self.get_active_nodes())
        total_nodes = len(self._nodes)
        if total_nodes == 0: return ConsensusStatus.OFFLINE
        if active_nodes < total_nodes // 2 + 1: return ConsensusStatus.DEGRADED
        if self._status == ConsensusStatus.READY: return ConsensusStatus.ACTIVE
        return self._status

    def get_leader_id(self) -> Optional[str]:
        return self._leader_id

    def is_leader(self) -> bool:
        return self._leader_id == self.node_id

    def get_decision_history(self, limit: int = 10) -> List[DecisionResult]:
        return self._decision_history[-limit:]

    def get_stats(self) -> Dict[str, Any]:
        success_rate = self._successful_decisions / self._total_decisions if self._total_decisions > 0 else 0
        avg_latency = self._total_latency_ms / self._total_decisions if self._total_decisions > 0 else 0
        return {
            "node_id": self.node_id, "status": self._status.value,
            "consensus_mode": self.consensus_mode.value, "total_nodes": len(self._nodes),
            "active_nodes": len(self.get_active_nodes()), "total_decisions": self._total_decisions,
            "successful_decisions": self._successful_decisions, "success_rate": success_rate,
            "avg_latency_ms": avg_latency, "llm_stats": self._llm.get_stats(),
            "mapek_stats": {
                "metrics_history": len(self._mapek._metrics_history),
                "action_history": len(self._mapek._action_history),
                "learning_data": self._mapek._learning_data,
            },
        }

    async def run_mapek_cycle(self) -> Dict[str, Any]:
        cycle_start = time.time()
        metrics = await self._mapek.monitor()
        anomalies = self._mapek.analyze(metrics)
        actions = self._mapek.plan(anomalies)
        results = []
        for action in actions:
            result = await self._mapek.execute(action)
            self._mapek.learn(action, result)
            results.append(result)
        return {
            "duration_ms": (time.time() - cycle_start) * 1000,
            "metrics": metrics, "anomalies": anomalies,
            "actions_planned": len(actions),
            "actions_executed": len([r for r in results if r.get("success")]),
        }

    def get_mapek_integration(self) -> MAPEKIntegration:
        return self._mapek

    def get_llm_integration(self) -> KimiK25Integration:
        return self._llm

    def set_transport(self, transport: Any) -> None:
        self._transport = transport
        self._transport.register_handler("consensus", self._handle_consensus_message)
        logger.info(f"Transport layer set for node {self.node_id}")

    def _handle_consensus_message(self, message: Any) -> None:
        self._consensus_manager.receive_message(message.payload)

    def get_transport(self) -> Optional[Any]:
        return self._transport

    async def start_election(self) -> None:
        self._term += 1
        logger.info(f"Node {self.node_id} starting election for term {self._term}")
        active_nodes = len(self.get_active_nodes())
        quorum = len(self._nodes) // 2 + 1
        if active_nodes >= quorum:
            self._leader_id = self.node_id
            self._nodes[self.node_id].is_leader = True
            if self._on_leader_change: self._on_leader_change(self.node_id)
            logger.info(f"Node {self.node_id} became leader for term {self._term}")

    async def heartbeat(self) -> None:
        if self.is_leader():
            self._nodes[self.node_id].last_heartbeat = datetime.utcnow()

    def receive_message(self, message: Dict[str, Any]) -> None:
        msg_type = message.get("type")
        if msg_type == "heartbeat":
            leader_id = message.get("leader_id")
            if leader_id:
                self._leader_id = leader_id
                if leader_id in self._nodes:
                    self._nodes[leader_id].is_leader = True
                    self._nodes[leader_id].last_heartbeat = datetime.utcnow()
        self._consensus_manager.receive_message(message)


async def create_swarm_intelligence(
    node_id: str,
    peers: Optional[Set[str]] = None,
    consensus_mode: ConsensusMode = ConsensusMode.SIMPLE,
    enable_llm: bool = False,
) -> SwarmIntelligence:
    swarm = SwarmIntelligence(
        node_id=node_id, peers=peers,
        consensus_mode=consensus_mode, enable_llm=enable_llm,
    )
    await swarm.initialize()
    return swarm

