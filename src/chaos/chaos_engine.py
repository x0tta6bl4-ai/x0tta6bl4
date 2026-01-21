"""
Chaos Engineering Framework
===========================

Инжекция контролируемого хаоса для проверки устойчивости системы.

Функции:
- Node failure injection
- Network partition simulation
- Byzantine attack simulation
- Load testing
- Recovery verification
"""
import asyncio
import logging
import random
import time
from typing import Dict, List, Optional, Callable, Any
from dataclasses import dataclass, field
from enum import Enum

logger = logging.getLogger(__name__)


class ChaosEventType(Enum):
    """Types of chaos events."""
    NODE_FAILURE = "node_failure"
    NETWORK_PARTITION = "network_partition"
    BYZANTINE_ATTACK = "byzantine_attack"
    HIGH_LOAD = "high_load"
    LATENCY_SPIKE = "latency_spike"
    PACKET_LOSS = "packet_loss"


@dataclass
class ChaosEvent:
    """Represents a chaos event."""
    event_type: ChaosEventType
    target: str  # node_id or "random"
    duration: float  # seconds
    severity: float  # 0.0 - 1.0
    timestamp: float = field(default_factory=time.time)
    recovered: bool = False


class ChaosEngine:
    """
    Chaos Engineering Engine для тестирования устойчивости.
    
    Usage:
        engine = ChaosEngine()
        await engine.inject_node_failure("node-01", duration=30.0)
        await engine.inject_network_partition(["node-01", "node-02"], duration=60.0)
    """
    
    def __init__(self):
        self.active_events: List[ChaosEvent] = []
        self.event_history: List[ChaosEvent] = []
        self._callbacks: Dict[ChaosEventType, List[Callable]] = {}
        
        logger.info("🔥 Chaos Engine initialized")
    
    def register_callback(self, event_type: ChaosEventType, callback: Callable):
        """Register callback for chaos event."""
        if event_type not in self._callbacks:
            self._callbacks[event_type] = []
        self._callbacks[event_type].append(callback)
    
    async def inject_node_failure(
        self,
        node_id: str,
        duration: float = 30.0,
        severity: float = 1.0
    ) -> ChaosEvent:
        """
        Inject node failure.
        
        Args:
            node_id: Node to fail
            duration: How long to keep node down
            severity: 0.0-1.0 (1.0 = complete failure)
        """
        event = ChaosEvent(
            event_type=ChaosEventType.NODE_FAILURE,
            target=node_id,
            duration=duration,
            severity=severity
        )
        
        self.active_events.append(event)
        logger.warning(f"🔥 CHAOS: Node {node_id} failed (duration={duration}s)")
        
        # Trigger callbacks
        for callback in self._callbacks.get(ChaosEventType.NODE_FAILURE, []):
            try:
                await callback(event)
            except Exception as e:
                logger.error(f"Chaos callback error: {e}")
        
        # Auto-recover after duration
        asyncio.create_task(self._auto_recover(event))
        
        return event
    
    async def inject_network_partition(
        self,
        node_ids: List[str],
        duration: float = 60.0
    ) -> ChaosEvent:
        """
        Inject network partition (split nodes into separate groups).
        
        Args:
            node_ids: Nodes to partition
            duration: How long to keep partition
        """
        event = ChaosEvent(
            event_type=ChaosEventType.NETWORK_PARTITION,
            target=",".join(node_ids),
            duration=duration,
            severity=1.0
        )
        
        self.active_events.append(event)
        logger.warning(
            f"🔥 CHAOS: Network partition: {len(node_ids)} nodes "
            f"(duration={duration}s)"
        )
        
        # Trigger callbacks
        for callback in self._callbacks.get(ChaosEventType.NETWORK_PARTITION, []):
            try:
                await callback(event)
            except Exception as e:
                logger.error(f"Chaos callback error: {e}")
        
        # Auto-recover
        asyncio.create_task(self._auto_recover(event))
        
        return event
    
    async def inject_byzantine_attack(
        self,
        node_id: str,
        duration: float = 120.0,
        attack_type: str = "malicious_updates"
    ) -> ChaosEvent:
        """
        Inject Byzantine attack (malicious node behavior).
        
        Args:
            node_id: Node to make Byzantine
            duration: How long attack lasts
            attack_type: Type of attack
        """
        event = ChaosEvent(
            event_type=ChaosEventType.BYZANTINE_ATTACK,
            target=node_id,
            duration=duration,
            severity=1.0
        )
        
        self.active_events.append(event)
        logger.warning(
            f"🔥 CHAOS: Byzantine attack on {node_id} "
            f"(type={attack_type}, duration={duration}s)"
        )
        
        # Trigger callbacks
        for callback in self._callbacks.get(ChaosEventType.BYZANTINE_ATTACK, []):
            try:
                await callback(event)
            except Exception as e:
                logger.error(f"Chaos callback error: {e}")
        
        # Auto-recover
        asyncio.create_task(self._auto_recover(event))
        
        return event
    
    async def inject_high_load(
        self,
        node_id: str,
        duration: float = 60.0,
        load_percent: float = 0.95
    ) -> ChaosEvent:
        """Inject high CPU/memory load on node."""
        event = ChaosEvent(
            event_type=ChaosEventType.HIGH_LOAD,
            target=node_id,
            duration=duration,
            severity=load_percent
        )
        
        self.active_events.append(event)
        logger.warning(
            f"🔥 CHAOS: High load on {node_id} "
            f"({load_percent*100:.0f}%, duration={duration}s)"
        )
        
        # Trigger callbacks
        for callback in self._callbacks.get(ChaosEventType.HIGH_LOAD, []):
            try:
                await callback(event)
            except Exception as e:
                logger.error(f"Chaos callback error: {e}")
        
        # Auto-recover
        asyncio.create_task(self._auto_recover(event))
        
        return event
    
    async def _auto_recover(self, event: ChaosEvent):
        """Auto-recover from chaos event after duration."""
        await asyncio.sleep(event.duration)
        
        if event in self.active_events:
            self.active_events.remove(event)
            event.recovered = True
            self.event_history.append(event)
            
            logger.info(
                f"✅ CHAOS RECOVERED: {event.event_type.value} on {event.target}"
            )
    
    def get_active_events(self) -> List[ChaosEvent]:
        """Get list of active chaos events."""
        return self.active_events.copy()
    
    def get_event_history(self) -> List[ChaosEvent]:
        """Get history of all chaos events."""
        return self.event_history.copy()
    
    def get_stats(self) -> Dict[str, Any]:
        """Get chaos engineering statistics."""
        return {
            "active_events": len(self.active_events),
            "total_events": len(self.event_history),
            "recovered_events": sum(1 for e in self.event_history if e.recovered),
            "event_types": {
                et.value: sum(1 for e in self.event_history if e.event_type == et)
                for et in ChaosEventType
            }
        }

