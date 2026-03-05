"""
Integration Layer: MAPE-K Orchestrator + AI Agents

This module provides unified state management and coordination between
the MAPE-K self-healing loop and the AI Agents system.
"""

import asyncio
import logging
from dataclasses import dataclass, field
from datetime import datetime
from typing import Any, Dict, List, Optional

from src.core.mape_orchestrator import (
    MAPEOrchestrator,
    HealingAction,
    HealingActionType,
    SystemState as MAPESystemState,
)
from src.agents import (
    AgentOrchestrator,
    get_orchestrator,
    Alert,
    AlertSeverity,
)

logger = logging.getLogger(__name__)


@dataclass
class UnifiedState:
    """
    Unified system state combining MAPE-K metrics and AI Agent status.
    This is the single source of truth for the entire system.
    """
    # MAPE-K state
    mape_state: MAPESystemState = field(default_factory=MAPESystemState)
    
    # Agent state
    agents_initialized: bool = False
    health_monitor_active: bool = False
    log_analyzer_active: bool = False
    auto_healer_active: bool = False
    
    # Unified metrics
    total_alerts: int = 0
    total_healing_actions: int = 0
    successful_healings: int = 0
    mttr_seconds: float = 0.0
    
    # Timestamps
    last_mape_update: Optional[datetime] = None
    last_agent_sync: Optional[datetime] = None
    
    @property
    def is_healthy(self) -> bool:
        """Check if system is healthy."""
        return self.mape_state.is_healthy and self.health_monitor_active
    
    @property
    def healing_success_rate(self) -> float:
        """Calculate healing success rate."""
        if self.total_healing_actions == 0:
            return 1.0
        return self.successful_healings / self.total_healing_actions


class AgentMAPEIntegrator:
    """
    Integrates MAPE-K orchestrator with AI Agents.
    
    Provides:
    - Unified state management
    - Bidirectional communication between MAPE-K and Agents
    - Shared metrics and monitoring
    - Coordinated healing responses
    """
    
    def __init__(
        self,
        mape_orchestrator: Optional[MAPEOrchestrator] = None,
        agent_orchestrator: Optional[AgentOrchestrator] = None,
    ):
        self.mape = mape_orchestrator
        self.agents = agent_orchestrator
        self._state = UnifiedState()
        self._running = False
        self._lock = asyncio.Lock()
        
        logger.info("Agent-MAPE Integrator initialized")
    
    async def initialize(self) -> None:
        """Initialize both MAPE-K and AI Agents."""
        async with self._lock:
            # Initialize MAPE-K if provided
            if self.mape:
                logger.info("MAPE-K orchestrator connected")
            
            # Initialize AI Agents
            if self.agents:
                await self.agents.initialize()
                self._state.agents_initialized = True
                self._state.health_monitor_active = True
                self._state.auto_healer_active = True
                logger.info("AI Agents initialized")
            
            self._state.last_agent_sync = datetime.utcnow()
    
    async def start(self) -> None:
        """Start unified healing loop."""
        await self.initialize()
        self._running = True
        
        logger.info("🚀 Agent-MAPE Integrator started")
        
        # Start background tasks
        tasks = []
        
        if self.mape:
            tasks.append(asyncio.create_task(self._mape_loop()))
        
        if self.agents:
            tasks.append(asyncio.create_task(self._agent_sync_loop()))
        
        if tasks:
            await asyncio.gather(*tasks)
    
    async def stop(self) -> None:
        """Stop all components gracefully."""
        self._running = False
        
        if self.agents:
            await self.agents.stop()
        
        if self.mape and hasattr(self.mape, 'stop'):
            await self.mape.stop()
        
        logger.info("🛑 Agent-MAPE Integrator stopped")
    
    async def _mape_loop(self) -> None:
        """MAPE-K monitoring loop."""
        if not self.mape:
            return
        
        while self._running:
            try:
                # Run MAPE-K cycle
                metrics = await self.mape.monitor_cycle()
                actions = await self.mape.analyze_cycle(metrics)
                
                if actions:
                    await self.mape.execute_cycle(actions)
                    
                    # Update unified state
                    self._state.total_healing_actions += len(actions)
                    self._state.mape_state.healing_actions = actions
                    
                    # Forward critical actions to AI Agents
                    await self._forward_to_agents(actions)
                
                self._state.last_mape_update = datetime.utcnow()
                
            except Exception as e:
                logger.error(f"Error in MAPE loop: {e}")
            
            await asyncio.sleep(3.14)  # MAPE-K interval
    
    async def _agent_sync_loop(self) -> None:
        """Periodic sync between AI Agents and MAPE-K state."""
        while self._running:
            try:
                # Get agent status
                if self.agents:
                    status = await self.agents.get_status()
                    
                    # Update unified state
                    self._state.health_monitor_active = status.get("agents", {}).get("health_monitor", False)
                    self._state.log_analyzer_active = status.get("agents", {}).get("log_analyzer", False)
                    self._state.auto_healer_active = status.get("agents", {}).get("auto_healer", False)
                    
                    # Get healing metrics
                    if "auto_healer_status" in status:
                        healer_status = status["auto_healer_status"]
                        self._state.successful_healings = healer_status.get("successful_healings", 0)
                
                self._state.last_agent_sync = datetime.utcnow()
                
            except Exception as e:
                logger.error(f"Error in agent sync: {e}")
            
            await asyncio.sleep(30)  # Sync interval
    
    async def _forward_to_agents(self, actions: List[HealingAction]) -> None:
        """Forward MAPE-K healing actions to AI Agents for processing."""
        if not self.agents or not self.agents.auto_healer:
            return
        
        for action in actions:
            # Convert MAPE-K action to agent-compatible format
            try:
                await self.agents.auto_healer.heal_now(
                    issue=f"MAPE-K: {action.reason}",
                    context={
                        "action_type": action.action_type.value,
                        "target": action.target,
                        "severity": action.severity.value,
                        "source": "mape-k"
                    }
                )
                self._state.successful_healings += 1
                
            except Exception as e:
                logger.error(f"Failed to forward action to agent: {e}")
    
    async def trigger_healing(self, issue: str, context: Dict[str, Any]) -> bool:
        """
        Manually trigger healing through both MAPE-K and Agents.
        
        Args:
            issue: Description of the issue
            context: Additional context
            
        Returns:
            True if healing was successful
        """
        logger.info(f"Manual healing triggered: {issue}")
        
        success = False
        
        # Try MAPE-K first
        if self.mape:
            try:
                # Create a synthetic healing action
                action = HealingAction(
                    action_type=HealingActionType.RE_ROUTE,
                    target=context.get("target", "system"),
                    reason=issue,
                    severity=AlertSeverity.WARNING,
                    params=context
                )
                await self.mape.execute_cycle([action])
                success = True
            except Exception as e:
                logger.error(f"MAPE-K healing failed: {e}")
        
        # Also trigger AI Agent healing
        if self.agents and self.agents.auto_healer:
            try:
                await self.agents.auto_healer.heal_now(issue, context)
                success = True
            except Exception as e:
                logger.error(f"Agent healing failed: {e}")
        
        return success
    
    def get_unified_state(self) -> Dict[str, Any]:
        """
        Get unified state snapshot.
        
        Returns:
            Complete system state
        """
        mape_metrics = self.mape.get_metrics() if self.mape and hasattr(self.mape, 'get_metrics') else {}
        
        return {
            "is_healthy": self._state.is_healthy,
            "agents": {
                "initialized": self._state.agents_initialized,
                "health_monitor": self._state.health_monitor_active,
                "log_analyzer": self._state.log_analyzer_active,
                "auto_healer": self._state.auto_healer_active,
            },
            "healing": {
                "total_actions": self._state.total_healing_actions,
                "successful": self._state.successful_healings,
                "success_rate": self._state.healing_success_rate,
                "mttr_seconds": self._state.mttr_seconds,
            },
            "mape_k": mape_metrics,
            "timestamps": {
                "last_mape_update": self._state.last_mape_update.isoformat() if self._state.last_mape_update else None,
                "last_agent_sync": self._state.last_agent_sync.isoformat() if self._state.last_agent_sync else None,
            }
        }


# Singleton instance
_integrator_instance: Optional[AgentMAPEIntegrator] = None


async def get_integrator() -> AgentMAPEIntegrator:
    """Get singleton integrator instance."""
    global _integrator_instance
    if _integrator_instance is None:
        _integrator_instance = AgentMAPEIntegrator()
    return _integrator_instance


async def create_integrated_system(
    mape_orchestrator: Optional[MAPEOrchestrator] = None,
) -> AgentMAPEIntegrator:
    """
    Factory function to create and initialize integrated system.
    
    Args:
        mape_orchestrator: Optional MAPE-K orchestrator
        
    Returns:
        Initialized integrator
    """
    # Get or create agent orchestrator
    agent_orchestrator = await get_orchestrator()
    
    # Create integrator
    integrator = AgentMAPEIntegrator(
        mape_orchestrator=mape_orchestrator,
        agent_orchestrator=agent_orchestrator
    )
    
    # Initialize
    await integrator.initialize()
    
    logger.info("✅ Integrated system created and initialized")
    
    return integrator
