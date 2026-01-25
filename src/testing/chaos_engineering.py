"""
Chaos Engineering Framework

Provides tools for simulating failures and chaos scenarios to test
system resilience and recovery mechanisms.
"""

import asyncio
import random
import logging
from typing import Callable, Optional, Dict, List, Any
from dataclasses import dataclass
from enum import Enum
from contextlib import asynccontextmanager
import time

logger = logging.getLogger(__name__)


class ChaosType(Enum):
    """Types of chaos scenarios"""
    NETWORK_LATENCY = "network_latency"
    PACKET_LOSS = "packet_loss"
    SERVICE_CRASH = "service_crash"
    SERVICE_HANG = "service_hang"
    MEMORY_LEAK = "memory_leak"
    CPU_SPIKE = "cpu_spike"
    DATA_CORRUPTION = "data_corruption"
    TIMEOUT = "timeout"
    CASCADING_FAILURE = "cascading_failure"
    BYZANTINE_FAULT = "byzantine_fault"
    CLOCK_SKEW = "clock_skew"
    PARTITION = "network_partition"


@dataclass
class ChaosScenario:
    """Configuration for a chaos scenario"""
    chaos_type: ChaosType
    duration_seconds: float
    severity: float  # 0-1, where 1 is maximum severity
    start_delay: float = 0.0  # Delay before starting chaos
    target_component: Optional[str] = None  # Which component to target
    custom_config: Dict[str, Any] = None


class ChaosInjector:
    """
    Injects chaos into system for resilience testing.
    """
    
    def __init__(self):
        self.active_chaos: List[ChaosScenario] = []
        self.chaos_history: List[Dict[str, Any]] = []
        self.max_history = 1000
    
    async def inject_network_latency(
        self,
        base_latency_ms: float,
        max_latency_ms: float,
        duration_seconds: float
    ) -> None:
        """
        Inject random network latency.
        
        Args:
            base_latency_ms: Baseline latency in ms
            max_latency_ms: Maximum latency in ms
            duration_seconds: Duration of chaos
        """
        start_time = time.time()
        
        while time.time() - start_time < duration_seconds:
            # Calculate random latency between base and max
            latency = base_latency_ms + random.random() * (max_latency_ms - base_latency_ms)
            await asyncio.sleep(latency / 1000.0)
        
        logger.info(f"Network latency chaos completed (avg {max_latency_ms}ms)")
    
    async def inject_packet_loss(
        self,
        loss_rate: float,  # 0-1, fraction of packets to drop
        duration_seconds: float
    ) -> None:
        """
        Simulate packet loss in network.
        
        Args:
            loss_rate: Fraction of packets to lose (0-1)
            duration_seconds: Duration of chaos
        """
        start_time = time.time()
        packets_sent = 0
        packets_lost = 0
        
        while time.time() - start_time < duration_seconds:
            if random.random() < loss_rate:
                packets_lost += 1
            packets_sent += 1
            await asyncio.sleep(0.01)
        
        logger.info(
            f"Packet loss chaos: {packets_lost}/{packets_sent} lost "
            f"({packets_lost/packets_sent*100:.1f}%)"
        )
    
    async def inject_service_crash(
        self,
        service_name: str,
        recovery_delay_seconds: float = 5.0,
        crash_callback: Optional[Callable] = None
    ) -> None:
        """
        Simulate service crash and recovery.
        
        Args:
            service_name: Name of service to crash
            recovery_delay_seconds: Time before service recovers
            crash_callback: Optional callback to execute on crash
        """
        logger.critical(f"🔴 SERVICE CRASH: {service_name}")
        
        if crash_callback:
            await crash_callback(service_name)
        
        await asyncio.sleep(recovery_delay_seconds)
        logger.info(f"🟢 SERVICE RECOVERED: {service_name}")
    
    async def inject_service_hang(
        self,
        service_name: str,
        hang_duration_seconds: float,
        detection_delay: float = 2.0
    ) -> None:
        """
        Simulate service becoming unresponsive.
        
        Args:
            service_name: Name of service to hang
            hang_duration_seconds: Duration of hang
            detection_delay: Time before hang is detected
        """
        logger.warning(f"⏸️  SERVICE HANG: {service_name} ({hang_duration_seconds}s)")
        
        # Simulate detection delay
        await asyncio.sleep(detection_delay)
        
        # Simulate hang duration
        await asyncio.sleep(hang_duration_seconds - detection_delay)
        
        logger.info(f"✅ SERVICE RESPONSIVE: {service_name}")
    
    async def inject_memory_leak(
        self,
        leak_rate_mb_per_sec: float,
        max_memory_mb: float,
        duration_seconds: float
    ) -> None:
        """
        Simulate memory leak.
        
        Args:
            leak_rate_mb_per_sec: Memory leak rate in MB/s
            max_memory_mb: Maximum memory to leak
            duration_seconds: Duration of chaos
        """
        start_time = time.time()
        total_leaked = 0
        
        while time.time() - start_time < duration_seconds and total_leaked < max_memory_mb:
            leaked_this_cycle = leak_rate_mb_per_sec / 10  # 100ms cycles
            total_leaked += leaked_this_cycle
            
            if total_leaked % 10 < leaked_this_cycle:  # Log every 10MB
                logger.warning(f"💾 Memory leak: {total_leaked:.1f}MB leaked")
            
            await asyncio.sleep(0.1)
        
        logger.info(f"Memory leak chaos: {total_leaked:.1f}MB total")
    
    async def inject_cpu_spike(
        self,
        cpu_percent: float,  # 0-100
        duration_seconds: float
    ) -> None:
        """
        Simulate CPU spike.
        
        Args:
            cpu_percent: CPU utilization percentage (0-100)
            duration_seconds: Duration of spike
        """
        logger.warning(f"📈 CPU SPIKE: {cpu_percent}% for {duration_seconds}s")
        
        start_time = time.time()
        # Simulate CPU-intensive work
        while time.time() - start_time < duration_seconds:
            # Busy loop to consume CPU
            _ = sum(i**2 for i in range(10000))
            await asyncio.sleep(0.01)
        
        logger.info("CPU spike ended")
    
    async def inject_data_corruption(
        self,
        corruption_rate: float,  # 0-1
        duration_seconds: float
    ) -> None:
        """
        Simulate random data corruption.
        
        Args:
            corruption_rate: Fraction of data to corrupt (0-1)
            duration_seconds: Duration of chaos
        """
        logger.error(f"⚠️  DATA CORRUPTION: {corruption_rate*100:.1f}% corruption rate")
        
        start_time = time.time()
        
        while time.time() - start_time < duration_seconds:
            if random.random() < corruption_rate:
                logger.error(f"Data corruption detected at {time.time():.2f}")
            await asyncio.sleep(0.1)
        
        logger.info("Data corruption chaos ended")
    
    async def inject_cascading_failure(
        self,
        primary_service: str,
        dependent_services: List[str],
        cascade_delay_seconds: float = 1.0
    ) -> None:
        """
        Simulate cascading failure where primary failure causes others to fail.
        
        Args:
            primary_service: Service that fails first
            dependent_services: Services that fail due to primary
            cascade_delay_seconds: Delay between failures
        """
        logger.critical(f"🌊 CASCADING FAILURE: Starting with {primary_service}")
        
        # Primary fails
        await self.inject_service_crash(primary_service, recovery_delay_seconds=5.0)
        
        # Cascade to dependents
        for service in dependent_services:
            await asyncio.sleep(cascade_delay_seconds)
            logger.critical(f"  → {service} failing due to cascade")
            await self.inject_service_crash(service, recovery_delay_seconds=3.0)
    
    async def inject_byzantine_fault(
        self,
        service_name: str,
        fault_rate: float = 0.3,  # 30% of requests return wrong result
        duration_seconds: float = 10.0
    ) -> None:
        """
        Simulate Byzantine fault where service returns incorrect results.
        
        Args:
            service_name: Service exhibiting Byzantine behavior
            fault_rate: Fraction of requests to corrupt
            duration_seconds: Duration of chaos
        """
        logger.error(f"👹 BYZANTINE FAULT: {service_name} ({fault_rate*100:.1f}% corruption)")
        
        start_time = time.time()
        corrupted_requests = 0
        
        while time.time() - start_time < duration_seconds:
            if random.random() < fault_rate:
                corrupted_requests += 1
                logger.warning(f"Request #{corrupted_requests} returned incorrect data")
            await asyncio.sleep(0.1)
        
        logger.info(f"Byzantine fault ended: {corrupted_requests} requests corrupted")
    
    async def inject_clock_skew(
        self,
        skew_seconds: float,  # Positive or negative
        duration_seconds: float = 30.0
    ) -> None:
        """
        Simulate clock skew across system.
        
        Args:
            skew_seconds: Amount of clock skew in seconds
            duration_seconds: Duration of chaos
        """
        logger.warning(f"🕐 CLOCK SKEW: {skew_seconds:+.1f}s")
        
        await asyncio.sleep(duration_seconds)
        
        logger.info("Clock skew resolved")
    
    async def inject_network_partition(
        self,
        partition_duration_seconds: float,
        affected_nodes: Optional[List[str]] = None
    ) -> None:
        """
        Simulate network partition.
        
        Args:
            partition_duration_seconds: Duration of partition
            affected_nodes: List of nodes in partition
        """
        partition_nodes = affected_nodes or ["node1", "node2"]
        logger.critical(f"🔌 NETWORK PARTITION: {partition_nodes} isolated for {partition_duration_seconds}s")
        
        await asyncio.sleep(partition_duration_seconds)
        
        logger.info("Network partition healed")
    
    def record_chaos_event(self, scenario: ChaosScenario, result: Dict[str, Any]) -> None:
        """Record chaos event for analysis"""
        event = {
            "timestamp": time.time(),
            "chaos_type": scenario.chaos_type.value,
            "severity": scenario.severity,
            "result": result
        }
        self.chaos_history.append(event)
        if len(self.chaos_history) > self.max_history:
            self.chaos_history.pop(0)
    
    @asynccontextmanager
    async def chaos_scenario(self, scenario: ChaosScenario):
        """Context manager for chaos scenario"""
        logger.info(f"Starting chaos scenario: {scenario.chaos_type.value}")
        
        # Wait for start delay
        if scenario.start_delay > 0:
            await asyncio.sleep(scenario.start_delay)
        
        try:
            yield scenario
        finally:
            logger.info(f"Completed chaos scenario: {scenario.chaos_type.value}")
            self.record_chaos_event(scenario, {"status": "completed"})


def create_chaos_scenario(
    chaos_type: ChaosType,
    severity: float,
    duration_seconds: float = 10.0,
    **kwargs
) -> ChaosScenario:
    """Factory function to create chaos scenarios"""
    return ChaosScenario(
        chaos_type=chaos_type,
        severity=severity,
        duration_seconds=duration_seconds,
        custom_config=kwargs
    )
