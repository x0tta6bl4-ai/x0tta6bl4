#!/usr/bin/env python3
"""
x0tta6bl4 Thread-Safe MAPE-K Loop
============================================

Thread-safe implementation of MAPE-K loop with atomic operations.
Eliminates race conditions in concurrent monitoring and adaptation.

Features:
- Atomic state management
- Thread-safe metrics collection
- Lock-free data structures where possible
- Concurrent cycle execution with proper synchronization
"""

import asyncio
import time
import threading
from typing import Dict, List, Optional, Any
from dataclasses import dataclass, field
import logging
from .thread_safe_stats import ThreadSafeMetrics, AtomicCounter, AtomicFloat

logger = logging.getLogger(__name__)

@dataclass
class MAPEKState:
    """Thread-safe state container for MAPE-K loop"""
    phase: str
    timestamp: float
    metrics: Dict[str, Any]
    decisions: List[str]
    actions: List[str]
    cycle_id: int
    _lock: threading.Lock = field(default_factory=threading.Lock)
    
    def add_decision(self, decision: str) -> None:
        """Thread-safe decision addition."""
        with self._lock:
            self.decisions.append(decision)
    
    def add_action(self, action: str) -> None:
        """Thread-safe action addition."""
        with self._lock:
            self.actions.append(action)
    
    def get_snapshot(self) -> Dict[str, Any]:
        """Get thread-safe snapshot."""
        with self._lock:
            return {
                'phase': self.phase,
                'timestamp': self.timestamp,
                'metrics': dict(self.metrics),
                'decisions': list(self.decisions),
                'actions': list(self.actions),
                'cycle_id': self.cycle_id
            }

class ThreadSafeMAPEKLoop:
    """
    Thread-safe MAPE-K loop implementation.
    
    Uses atomic operations and thread-safe data structures
    to eliminate race conditions in concurrent execution.
    """
    
    def __init__(self, component_name: str):
        self.component_name = component_name
        
        # Thread-safe metrics
        self.metrics = ThreadSafeMetrics(f"mapek_{component_name}")
        
        # Atomic counters for cycle tracking
        self.cycle_count = AtomicCounter()
        self.successful_cycles = AtomicCounter()
        self.failed_cycles = AtomicCounter()
        
        # Atomic state tracking
        self.current_phase = AtomicFloat()
        self.last_cycle_time = AtomicFloat()
        
        # Thread-safe state history
        self.state_history: List[MAPEKState] = []
        self._history_lock = threading.Lock()
        self.max_history_size = 1000
        
        # Cycle execution lock
        self._cycle_lock = asyncio.Lock()
        
        # Initialize metrics
        self.metrics.set_gauge("current_phase", 0.0)
        self.metrics.set_gauge("last_cycle_duration", 0.0)
        
        logger.info(f"ThreadSafeMAPEKLoop initialized for {component_name}")
    
    async def execute_cycle(self, system_metrics: Dict[str, float], context: Dict[str, Any]) -> MAPEKState:
        """
        Execute one complete MAPE-K cycle with thread safety.
        
        Args:
            system_metrics: Current system metrics
            context: Execution context
            
        Returns:
            MAPEKState for the completed cycle
        """
        async with self._cycle_lock:
            cycle_start = time.time()
            cycle_id = self.cycle_count.increment()
            
            try:
                # MONITOR phase
                phase_start = time.time()
                self.current_phase.update(1.0)  # MONITOR = 1
                monitor_metrics = await self._monitor_phase(system_metrics, context)
                
                # ANALYZE phase  
                self.current_phase.update(2.0)  # ANALYZE = 2
                analysis_results = await self._analyze_phase(monitor_metrics, context)
                
                # PLAN phase
                self.current_phase.update(3.0)  # PLAN = 3
                plan_decisions = await self._plan_phase(analysis_results, context)
                
                # EXECUTE phase
                self.current_phase.update(4.0)  # EXECUTE = 4
                executed_actions = await self._execute_phase(plan_decisions, context)
                
                # KNOWLEDGE phase
                self.current_phase.update(5.0)  # KNOWLEDGE = 5
                knowledge_updates = await self._knowledge_phase(executed_actions, context)
                
                # Create state object
                cycle_duration = time.time() - cycle_start
                state = MAPEKState(
                    phase="COMPLETE",
                    timestamp=time.time(),
                    metrics={
                        "system": system_metrics,
                        "monitor": monitor_metrics,
                        "analysis": analysis_results,
                        "plan": plan_decisions,
                        "execute": executed_actions,
                        "knowledge": knowledge_updates,
                        "duration": cycle_duration
                    },
                    decisions=plan_decisions.get("decisions", []),
                    actions=executed_actions.get("actions", []),
                    cycle_id=cycle_id
                )
                
                # Update metrics
                self.last_cycle_time.update(cycle_duration)
                self.metrics.set_gauge("last_cycle_duration", cycle_duration)
                self.successful_cycles.increment()
                
                # Add to history
                self._add_to_history(state)
                
                self.current_phase.update(0.0)  # IDLE = 0
                logger.info(f"MAPE-K cycle #{cycle_id} completed in {cycle_duration:.3f}s")
                
                return state
                
            except Exception as e:
                cycle_duration = time.time() - cycle_start
                error_state = MAPEKState(
                    phase="ERROR",
                    timestamp=time.time(),
                    metrics={
                        "system": system_metrics,
                        "error": str(e),
                        "duration": cycle_duration
                    },
                    decisions=[f"Cycle failed: {e}"],
                    actions=[],
                    cycle_id=cycle_id
                )
                
                # Update error metrics
                self.failed_cycles.increment()
                self._add_to_history(error_state)
                
                self.current_phase.update(0.0)  # IDLE = 0
                logger.error(f"MAPE-K cycle #{cycle_id} failed: {e}")
                
                return error_state
    
    async def _monitor_phase(self, system_metrics: Dict[str, float], context: Dict[str, Any]) -> Dict[str, Any]:
        """Monitor phase implementation."""
        # Record monitoring activity
        self.metrics.increment_counter("monitor_cycles")
        
        # Add system metrics to thread-safe storage
        for key, value in system_metrics.items():
            self.metrics.set_gauge(f"monitor_{key}", value)
        
        return {
            "timestamp": time.time(),
            "metrics_collected": len(system_metrics),
            "system_health": system_metrics.get("health", 0.0)
        }
    
    async def _analyze_phase(self, monitor_data: Dict[str, Any], context: Dict[str, Any]) -> Dict[str, Any]:
        """Analyze phase implementation."""
        self.metrics.increment_counter("analyze_cycles")
        
        system_health = monitor_data.get("system_health", 0.0)
        
        # Simple threshold analysis
        if system_health < 0.3:
            severity = "CRITICAL"
            action_required = True
        elif system_health < 0.7:
            severity = "WARNING"
            action_required = True
        else:
            severity = "NORMAL"
            action_required = False
        
        self.metrics.set_gauge("analysis_severity", 0.0 if severity == "NORMAL" else 1.0 if severity == "WARNING" else 2.0)
        
        return {
            "severity": severity,
            "action_required": action_required,
            "system_health": system_health,
            "analysis_timestamp": time.time()
        }
    
    async def _plan_phase(self, analysis_data: Dict[str, Any], context: Dict[str, Any]) -> Dict[str, Any]:
        """Plan phase implementation."""
        self.metrics.increment_counter("plan_cycles")
        
        decisions = []
        severity = analysis_data.get("severity", "NORMAL")
        
        if severity == "CRITICAL":
            decisions.append("Initiate emergency recovery")
            decisions.append("Scale up resources")
        elif severity == "WARNING":
            decisions.append("Increase monitoring frequency")
            decisions.append("Prep recovery procedures")
        else:
            decisions.append("Continue normal operations")
        
        # Record decisions
        for decision in decisions:
            self.metrics.add_to_set("decisions_made", decision)
        
        return {
            "decisions": decisions,
            "planning_timestamp": time.time(),
            "estimated_impact": "high" if severity == "CRITICAL" else "medium" if severity == "WARNING" else "low"
        }
    
    async def _execute_phase(self, plan_data: Dict[str, Any], context: Dict[str, Any]) -> Dict[str, Any]:
        """Execute phase implementation."""
        self.metrics.increment_counter("execute_cycles")
        
        actions = []
        decisions = plan_data.get("decisions", [])
        
        for decision in decisions:
            if "emergency" in decision.lower():
                actions.append("Emergency recovery initiated")
                self.metrics.increment_counter("emergency_executions")
            elif "scale" in decision.lower():
                actions.append("Resource scaling initiated")
                self.metrics.increment_counter("scaling_executions")
            elif "monitoring" in decision.lower():
                actions.append("Monitoring frequency increased")
                self.metrics.increment_counter("monitoring_adjustments")
            else:
                actions.append("No action required")
        
        return {
            "actions": actions,
            "execution_timestamp": time.time(),
            "actions_executed": len([a for a in actions if not a.startswith("No action")])
        }
    
    async def _knowledge_phase(self, execute_data: Dict[str, Any], context: Dict[str, Any]) -> Dict[str, Any]:
        """Knowledge phase implementation."""
        self.metrics.increment_counter("knowledge_cycles")
        
        actions = execute_data.get("actions", [])
        learnings = []
        
        # Record learnings from executed actions
        for action in actions:
            if "recovery" in action.lower():
                learnings.append("Recovery pattern effectiveness recorded")
                self.metrics.add_to_set("recovery_patterns", action)
            elif "scaling" in action.lower():
                learnings.append("Scaling decision outcome recorded")
                self.metrics.add_to_set("scaling_patterns", action)
        
        return {
            "learnings": learnings,
            "knowledge_timestamp": time.time(),
            "patterns_recorded": len(learnings)
        }
    
    def _add_to_history(self, state: MAPEKState) -> None:
        """Thread-safe addition to history with size limit."""
        with self._history_lock:
            self.state_history.append(state)
            # Maintain size limit
            if len(self.state_history) > self.max_history_size:
                self.state_history = self.state_history[-self.max_history_size:]
    
    def get_current_state(self) -> Dict[str, Any]:
        """Get current MAPE-K state."""
        return {
            "component": self.component_name,
            "current_phase": self.current_phase.get(),
            "cycle_count": self.cycle_count.get(),
            "successful_cycles": self.successful_cycles.get(),
            "failed_cycles": self.failed_cycles.get(),
            "last_cycle_time": self.last_cycle_time.get(),
            "success_rate": (
                self.successful_cycles.get() / 
                (self.successful_cycles.get() + self.failed_cycles.get())
                if (self.successful_cycles.get() + self.failed_cycles.get()) > 0 else 0.0
            )
        }
    
    def get_metrics_snapshot(self) -> Dict[str, Any]:
        """Get comprehensive metrics snapshot."""
        base_metrics = self.metrics.get_stats_snapshot()
        base_metrics.update(self.get_current_state())
        return base_metrics
    
    def get_recent_history(self, limit: int = 10) -> List[Dict[str, Any]]:
        """Get recent cycle history."""
        with self._history_lock:
            recent_states = self.state_history[-limit:] if limit else self.state_history
            return [state.get_snapshot() for state in recent_states]
    
    def reset_metrics(self) -> None:
        """Reset all metrics."""
        self.cycle_count.reset()
        self.successful_cycles.reset()
        self.failed_cycles.reset()
        self.current_phase.update(0.0)
        self.last_cycle_time.update(0.0)
        self.metrics.reset_all()
        
        with self._history_lock:
            self.state_history.clear()
        
        logger.info(f"Reset all MAPE-K metrics for {self.component_name}")
