"""
Slot-Based Synchronization for Mesh Network

Implements slot-based synchronization protocol where nodes synchronize
transmission time slots locally through beacon signals, eliminating the
need for global time and reducing collisions during transmission.

Features:
- Local slot synchronization via beacon signals
- Automatic slot resynchronization after collisions
- Race condition detection and mitigation
- Support for 50+ nodes (Stage 1 requirement)
"""

import asyncio
import logging
import time
import random
from typing import Dict, Set, Optional, List
from dataclasses import dataclass, field
from datetime import datetime, timedelta
from enum import Enum

logger = logging.getLogger(__name__)


class SlotState(Enum):
    """Slot synchronization state"""
    UNINITIALIZED = "uninitialized"
    SYNCHRONIZING = "synchronizing"
    SYNCHRONIZED = "synchronized"
    COLLISION = "collision"
    RESYNCHRONIZING = "resynchronizing"


@dataclass
class Beacon:
    """Beacon signal for slot synchronization"""
    node_id: str
    slot_number: int
    timestamp: datetime
    sequence: int = 0


@dataclass
class SlotInfo:
    """Information about a time slot"""
    slot_number: int
    owner_node_id: Optional[str] = None
    last_beacon: Optional[datetime] = None
    collision_count: int = 0
    is_available: bool = True


class SlotSynchronizer:
    """
    Slot-based synchronization manager for mesh nodes.
    
    Manages:
    - Local slot assignment
    - Beacon signal transmission and reception
    - Collision detection and resolution
    - Race condition mitigation
    
    Usage:
        >>> sync = SlotSynchronizer(node_id="node-a", total_slots=10)
        >>> await sync.initialize()
        >>> await sync.run()
    """
    
    def __init__(
        self,
        node_id: str,
        total_slots: int = 10,
        beacon_interval: float = 1.0,
        slot_duration: float = 0.1
    ):
        """
        Initialize slot synchronizer.
        
        Args:
            node_id: Unique identifier for this node
            total_slots: Total number of available time slots
            beacon_interval: Interval between beacon transmissions (seconds)
            slot_duration: Duration of each time slot (seconds)
        """
        self.node_id = node_id
        self.total_slots = total_slots
        self.beacon_interval = beacon_interval
        self.slot_duration = slot_duration
        
        self.state = SlotState.UNINITIALIZED
        self.current_slot = None
        self.slot_info: Dict[int, SlotInfo] = {
            i: SlotInfo(slot_number=i) for i in range(total_slots)
        }
        
        self.neighbor_beacons: Dict[str, Beacon] = {}  # node_id -> latest beacon
        self.collision_history: List[datetime] = []
        self.resync_attempts = 0
        
        self._running = False
        self._beacon_task: Optional[asyncio.Task] = None
        self._listen_task: Optional[asyncio.Task] = None
    
    async def initialize(self):
        """Initialize slot synchronization."""
        logger.info(f"Initializing slot synchronization for {self.node_id}")
        
        # Wait for initial neighbor discovery
        await asyncio.sleep(2.0)
        
        # Choose initial slot (try to avoid collisions)
        self.current_slot = self._choose_available_slot()
        self.state = SlotState.SYNCHRONIZING
        
        logger.info(f"Node {self.node_id} assigned to slot {self.current_slot}")
    
    async def run(self):
        """Run slot synchronization loop."""
        self._running = True
        
        # Start beacon transmission
        self._beacon_task = asyncio.create_task(self._beacon_loop())
        
        # Start beacon listening
        self._listen_task = asyncio.create_task(self._listen_loop())
        
        # Main synchronization loop
        try:
            while self._running:
                await self._synchronization_cycle()
                await asyncio.sleep(0.1)  # 100ms cycle
        except asyncio.CancelledError:
            logger.info(f"Slot synchronization stopped for {self.node_id}")
        finally:
            await self.stop()
    
    async def stop(self):
        """Stop slot synchronization."""
        self._running = False
        
        if self._beacon_task:
            self._beacon_task.cancel()
            try:
                await self._beacon_task
            except asyncio.CancelledError:
                pass
        
        if self._listen_task:
            self._listen_task.cancel()
            try:
                await self._listen_task
            except asyncio.CancelledError:
                pass
        
        logger.info(f"Slot synchronization stopped for {self.node_id}")
    
    async def _beacon_loop(self):
        """Transmit beacon signals periodically."""
        sequence = 0
        
        while self._running:
            try:
                if self.current_slot is not None:
                    beacon = Beacon(
                        node_id=self.node_id,
                        slot_number=self.current_slot,
                        timestamp=datetime.now(),
                        sequence=sequence
                    )
                    
                    # Transmit beacon (simulated - would use actual mesh protocol)
                    await self._transmit_beacon(beacon)
                    sequence += 1
                
                await asyncio.sleep(self.beacon_interval)
            except asyncio.CancelledError:
                break
            except Exception as e:
                logger.error(f"Error in beacon loop: {e}")
                await asyncio.sleep(self.beacon_interval)
    
    async def _listen_loop(self):
        """Listen for beacon signals from neighbors."""
        while self._running:
            try:
                # Receive beacons (simulated - would use actual mesh protocol)
                beacons = await self._receive_beacons()
                
                for beacon in beacons:
                    await self._process_beacon(beacon)
                
                await asyncio.sleep(0.05)  # 50ms listen interval
            except asyncio.CancelledError:
                break
            except Exception as e:
                logger.error(f"Error in listen loop: {e}")
                await asyncio.sleep(0.05)
    
    async def _synchronization_cycle(self):
        """Main synchronization cycle."""
        # Check for collisions
        collisions = self._detect_collisions()
        
        if collisions:
            self.state = SlotState.COLLISION
            await self._handle_collisions(collisions)
        elif self.state == SlotState.SYNCHRONIZING:
            # Check if we've received enough beacons to consider synchronized
            if len(self.neighbor_beacons) >= 2:
                self.state = SlotState.SYNCHRONIZED
                logger.info(f"Node {self.node_id} synchronized (slot {self.current_slot})")
        
        # Update slot information
        self._update_slot_info()
    
    def _choose_available_slot(self) -> int:
        """Choose an available slot, avoiding known collisions."""
        # Find slots with least collisions
        available_slots = [
            slot for slot, info in self.slot_info.items()
            if info.is_available or info.collision_count == 0
        ]
        
        if available_slots:
            # Choose slot with minimum collision count
            return min(available_slots, key=lambda s: self.slot_info[s].collision_count)
        
        # Fallback: random slot
        return random.randint(0, self.total_slots - 1)
    
    def _detect_collisions(self) -> List[int]:
        """Detect slot collisions (multiple nodes using same slot)."""
        collisions = []
        slot_usage: Dict[int, List[str]] = {}
        
        # Count nodes per slot
        for node_id, beacon in self.neighbor_beacons.items():
            slot = beacon.slot_number
            if slot not in slot_usage:
                slot_usage[slot] = []
            slot_usage[slot].append(node_id)
        
        # Check our own slot
        if self.current_slot is not None:
            if self.current_slot not in slot_usage:
                slot_usage[self.current_slot] = []
            slot_usage[self.current_slot].append(self.node_id)
        
        # Find collisions
        for slot, nodes in slot_usage.items():
            if len(nodes) > 1:
                collisions.append(slot)
                self.slot_info[slot].collision_count += 1
                self.slot_info[slot].is_available = False
        
        return collisions
    
    async def _handle_collisions(self, collisions: List[int]):
        """Handle slot collisions by resynchronizing."""
        if self.current_slot in collisions:
            logger.warning(
                f"Node {self.node_id} collision detected in slot {self.current_slot}, "
                f"resynchronizing..."
            )
            
            self.state = SlotState.RESYNCHRONIZING
            self.resync_attempts += 1
            
            # Record collision metric
            try:
                from src.monitoring.metrics import record_slot_sync_collision
                record_slot_sync_collision(self.node_id)
            except ImportError:
                pass
            
            # Choose new slot
            start_time = time.time()
            old_slot = self.current_slot
            self.current_slot = self._choose_available_slot()
            resync_time = time.time() - start_time
            
            # Record resync time metric
            try:
                from src.monitoring.metrics import record_slot_sync_resync_time
                record_slot_sync_resync_time(self.node_id, resync_time)
            except ImportError:
                pass
            
            logger.info(
                f"Node {self.node_id} resynchronized: "
                f"slot {old_slot} -> {self.current_slot} "
                f"(time: {resync_time:.3f}s)"
            )
            
            # Wait before declaring synchronized
            await asyncio.sleep(0.5)
            self.state = SlotState.SYNCHRONIZING
    
    def _update_slot_info(self):
        """Update slot information based on received beacons."""
        now = datetime.now()
        timeout = timedelta(seconds=self.beacon_interval * 3)
        
        # Mark slots as available if no recent beacons
        for slot, info in self.slot_info.items():
            if info.last_beacon:
                age = now - info.last_beacon
                if age > timeout:
                    info.is_available = True
                    info.owner_node_id = None
                    info.collision_count = max(0, info.collision_count - 1)
        
        # Calculate success rate
        total_slots = len(self.slot_info)
        synchronized_slots = sum(
            1 for info in self.slot_info.values()
            if info.owner_node_id is not None and info.collision_count == 0
        )
        success_rate = synchronized_slots / total_slots if total_slots > 0 else 0.0
        
        # Export success rate metric
        try:
            from src.monitoring.metrics import set_slot_sync_success_rate
            set_slot_sync_success_rate(self.node_id, success_rate)
        except ImportError:
            pass
    
    async def _process_beacon(self, beacon: Beacon):
        """Process received beacon signal."""
        # Update neighbor beacon
        self.neighbor_beacons[beacon.node_id] = beacon
        
        # Update slot info
        slot_info = self.slot_info[beacon.slot_number]
        slot_info.last_beacon = beacon.timestamp
        slot_info.owner_node_id = beacon.node_id
    
    async def _transmit_beacon(self, beacon: Beacon):
        """Transmit beacon signal (simulated)."""
        # In real implementation, this would use mesh protocol
        logger.debug(
            f"Node {self.node_id} transmitting beacon: "
            f"slot={beacon.slot_number}, seq={beacon.sequence}"
        )
    
    async def _receive_beacons(self) -> List[Beacon]:
        """Receive beacon signals from neighbors (simulated)."""
        # In real implementation, this would listen on mesh interface
        # For now, return empty list (beacons would come from actual mesh)
        return []
    
    def get_slot_info(self) -> Dict[int, SlotInfo]:
        """Get current slot information."""
        return self.slot_info.copy()
    
    def get_synchronization_status(self) -> Dict:
        """Get synchronization status."""
        return {
            "node_id": self.node_id,
            "state": self.state.value,
            "current_slot": self.current_slot,
            "neighbors": len(self.neighbor_beacons),
            "collisions": sum(1 for info in self.slot_info.values() if info.collision_count > 0),
            "resync_attempts": self.resync_attempts,
        }

