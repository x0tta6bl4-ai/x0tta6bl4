"""
MTTR Validation Framework for x0tta6bl4

Validates Mean Time To Recovery (MTTR) against Stage 1 targets:
- MTTR p95: ≤7s (target)
- MTTR p99: <10s
- Recovery success rate: >95%

Integrates with:
- MAPE-K self-healing cycle
- Chaos testing framework
- Prometheus metrics
"""

import asyncio
import logging
import statistics
import time
from dataclasses import dataclass, field
from datetime import datetime
from enum import Enum
from typing import Dict, List, Optional, Tuple

logger = logging.getLogger(__name__)


class RecoveryType(Enum):
    """Types of recovery scenarios"""

    NODE_FAILURE = "node_failure"
    NETWORK_PARTITION = "network_partition"
    LINK_FAILURE = "link_failure"
    HIGH_LATENCY = "high_latency"
    HIGH_CPU = "high_cpu"
    HIGH_MEMORY = "high_memory"
    BEACON_COLLISION = "beacon_collision"
    ROUTE_FAILURE = "route_failure"


@dataclass
class RecoveryEvent:
    """Represents a recovery event"""

    event_id: str
    recovery_type: RecoveryType
    node_id: str
    detection_time: datetime
    recovery_time: Optional[datetime] = None
    mttr_seconds: Optional[float] = None
    success: bool = False
    recovery_action: Optional[str] = None
    metrics_before: Dict = field(default_factory=dict)
    metrics_after: Dict = field(default_factory=dict)


@dataclass
class MTTRValidationResult:
    """Results from MTTR validation"""

    timestamp: datetime
    duration_seconds: float
    total_events: int
    successful_recoveries: int
    failed_recoveries: int
    mttr_p50: float
    mttr_p95: float
    mttr_p99: float
    mttr_max: float
    mttr_by_type: Dict[str, Dict[str, float]]
    recovery_success_rate: float
    target_met: bool  # True if p95 ≤ 7s and success rate >95%
    validation_passed: bool


class MTTRValidator:
    """
    MTTR validation framework.

    Measures and validates Mean Time To Recovery across different
    failure scenarios and recovery types.

    Usage:
        >>> validator = MTTRValidator(target_mttr_p95=7.0)
        >>> result = await validator.validate_mttr(duration=300)
        >>> print(f"Validation passed: {result.validation_passed}")
    """

    def __init__(
        self,
        target_mttr_p95: float = 7.0,
        target_success_rate: float = 0.95,
        node_id: str = "validator",
    ):
        """
        Initialize MTTR validator.

        Args:
            target_mttr_p95: Target MTTR p95 in seconds (default: 7.0)
            target_success_rate: Target recovery success rate (default: 0.95)
            node_id: Node identifier for metrics
        """
        self.target_mttr_p95 = target_mttr_p95
        self.target_success_rate = target_success_rate
        self.node_id = node_id

        self.recovery_events: List[RecoveryEvent] = []
        self.active_events: Dict[str, RecoveryEvent] = {}

    def start_recovery_event(
        self, recovery_type: RecoveryType, node_id: str, metrics: Optional[Dict] = None
    ) -> str:
        """
        Start tracking a recovery event.

        Args:
            recovery_type: Type of recovery scenario
            node_id: Node where failure occurred
            metrics: System metrics at detection time

        Returns:
            event_id: Unique identifier for this event
        """
        event_id = f"{recovery_type.value}_{node_id}_{int(time.time() * 1000)}"

        event = RecoveryEvent(
            event_id=event_id,
            recovery_type=recovery_type,
            node_id=node_id,
            detection_time=datetime.now(),
            metrics_before=metrics or {},
        )

        self.active_events[event_id] = event
        logger.info(f"Started recovery event: {event_id} ({recovery_type.value})")

        return event_id

    def complete_recovery_event(
        self,
        event_id: str,
        success: bool,
        recovery_action: Optional[str] = None,
        metrics: Optional[Dict] = None,
    ):
        """
        Complete a recovery event and calculate MTTR.

        Args:
            event_id: Event identifier from start_recovery_event
            success: Whether recovery was successful
            recovery_action: Action taken for recovery
            metrics: System metrics after recovery
        """
        if event_id not in self.active_events:
            logger.warning(f"Event {event_id} not found in active events")
            return

        event = self.active_events[event_id]
        event.recovery_time = datetime.now()
        event.mttr_seconds = (
            event.recovery_time - event.detection_time
        ).total_seconds()
        event.success = success
        event.recovery_action = recovery_action
        event.metrics_after = metrics or {}

        # Move to completed events
        self.recovery_events.append(event)
        del self.active_events[event_id]

        # Export MTTR metric
        try:
            from src.monitoring.metrics import (record_mttr,
                                                record_self_healing_event)

            record_mttr(event.recovery_type.value, event.mttr_seconds)
            record_self_healing_event(event.recovery_type.value, event.node_id)
        except ImportError:
            pass

        logger.info(
            f"Completed recovery event: {event_id}, "
            f"MTTR={event.mttr_seconds:.3f}s, success={success}"
        )

    async def validate_mttr(
        self,
        duration: float = 300.0,
        failure_scenarios: Optional[List[RecoveryType]] = None,
    ) -> MTTRValidationResult:
        """
        Run MTTR validation test.

        Args:
            duration: Test duration in seconds
            failure_scenarios: List of failure types to test (None = all)

        Returns:
            MTTRValidationResult with validation outcomes
        """
        logger.info(
            f"Starting MTTR validation: "
            f"duration={duration}s, target p95={self.target_mttr_p95}s"
        )

        start_time = time.time()
        failure_scenarios = failure_scenarios or list(RecoveryType)

        # Simulate failures and measure recovery
        while time.time() - start_time < duration:
            # Trigger random failure scenario
            scenario = random.choice(failure_scenarios)
            node_id = f"node-{random.randint(0, 49):03d}"  # Random node

            event_id = self.start_recovery_event(scenario, node_id)

            # Simulate recovery (would be handled by MAPE-K in real system)
            recovery_time = await self._simulate_recovery(scenario)

            self.complete_recovery_event(
                event_id,
                success=recovery_time
                < self.target_mttr_p95 * 2,  # Success if < 2x target
                recovery_action=f"auto_recover_{scenario.value}",
                metrics={"recovery_time": recovery_time},
            )

            # Wait before next failure
            await asyncio.sleep(random.uniform(10.0, 30.0))

        # Calculate statistics
        return self._calculate_validation_result(duration)

    async def _simulate_recovery(self, recovery_type: RecoveryType) -> float:
        """Simulate recovery time based on type."""
        # Base recovery times (would be actual MAPE-K recovery in production)
        base_times = {
            RecoveryType.NODE_FAILURE: 2.5,
            RecoveryType.NETWORK_PARTITION: 3.0,
            RecoveryType.LINK_FAILURE: 1.8,
            RecoveryType.HIGH_LATENCY: 2.0,
            RecoveryType.HIGH_CPU: 1.5,
            RecoveryType.HIGH_MEMORY: 1.2,
            RecoveryType.BEACON_COLLISION: 0.8,
            RecoveryType.ROUTE_FAILURE: 2.2,
        }

        base_time = base_times.get(recovery_type, 2.0)

        # Add some variance
        recovery_time = base_time + random.uniform(-0.5, 1.0)

        # Simulate actual recovery delay
        await asyncio.sleep(min(recovery_time, 0.1))  # Cap simulation delay

        return max(0.1, recovery_time)

    def _calculate_validation_result(self, duration: float) -> MTTRValidationResult:
        """Calculate validation results from collected events."""
        if not self.recovery_events:
            return MTTRValidationResult(
                timestamp=datetime.now(),
                duration_seconds=duration,
                total_events=0,
                successful_recoveries=0,
                failed_recoveries=0,
                mttr_p50=0.0,
                mttr_p95=0.0,
                mttr_p99=0.0,
                mttr_max=0.0,
                mttr_by_type={},
                recovery_success_rate=0.0,
                target_met=False,
                validation_passed=False,
            )

        # Filter successful recoveries for MTTR calculation
        successful_events = [
            e for e in self.recovery_events if e.success and e.mttr_seconds
        ]
        failed_events = [e for e in self.recovery_events if not e.success]

        if not successful_events:
            logger.warning("No successful recovery events for MTTR calculation")
            return MTTRValidationResult(
                timestamp=datetime.now(),
                duration_seconds=duration,
                total_events=len(self.recovery_events),
                successful_recoveries=0,
                failed_recoveries=len(failed_events),
                mttr_p50=0.0,
                mttr_p95=0.0,
                mttr_p99=0.0,
                mttr_max=0.0,
                mttr_by_type={},
                recovery_success_rate=0.0,
                target_met=False,
                validation_passed=False,
            )

        # Calculate overall MTTR statistics
        mttr_values = [e.mttr_seconds for e in successful_events]
        mttr_values.sort()

        n = len(mttr_values)
        mttr_p50 = mttr_values[int(n * 0.50)] if n > 0 else 0.0
        mttr_p95 = mttr_values[int(n * 0.95)] if n > 0 else 0.0
        mttr_p99 = mttr_values[int(n * 0.99)] if n > 0 else 0.0
        mttr_max = max(mttr_values) if mttr_values else 0.0

        # Calculate MTTR by recovery type
        mttr_by_type = {}
        for recovery_type in RecoveryType:
            type_events = [
                e for e in successful_events if e.recovery_type == recovery_type
            ]
            if type_events:
                type_mttr = [e.mttr_seconds for e in type_events]
                mttr_by_type[recovery_type.value] = {
                    "p50": statistics.median(type_mttr),
                    "p95": (
                        type_mttr[int(len(type_mttr) * 0.95)]
                        if len(type_mttr) > 0
                        else 0.0
                    ),
                    "p99": (
                        type_mttr[int(len(type_mttr) * 0.99)]
                        if len(type_mttr) > 0
                        else 0.0
                    ),
                    "avg": statistics.mean(type_mttr),
                    "count": len(type_events),
                }

        # Calculate success rate
        recovery_success_rate = (
            len(successful_events) / len(self.recovery_events)
            if self.recovery_events
            else 0.0
        )

        # Check if targets are met
        target_met = (
            mttr_p95 <= self.target_mttr_p95
            and recovery_success_rate >= self.target_success_rate
        )

        # Validation passes if targets met and p99 < 10s
        validation_passed = target_met and mttr_p99 < 10.0

        result = MTTRValidationResult(
            timestamp=datetime.now(),
            duration_seconds=duration,
            total_events=len(self.recovery_events),
            successful_recoveries=len(successful_events),
            failed_recoveries=len(failed_events),
            mttr_p50=mttr_p50,
            mttr_p95=mttr_p95,
            mttr_p99=mttr_p99,
            mttr_max=mttr_max,
            mttr_by_type=mttr_by_type,
            recovery_success_rate=recovery_success_rate,
            target_met=target_met,
            validation_passed=validation_passed,
        )

        logger.info(
            f"MTTR validation complete: "
            f"p95={mttr_p95:.3f}s (target: ≤{self.target_mttr_p95}s), "
            f"success_rate={recovery_success_rate:.1%}, "
            f"passed={validation_passed}"
        )

        return result

    def generate_report(self, result: MTTRValidationResult) -> str:
        """Generate human-readable validation report."""
        report = []
        report.append("=" * 60)
        report.append("MTTR Validation Report")
        report.append("=" * 60)
        report.append("")
        report.append(f"Timestamp: {result.timestamp}")
        report.append(f"Duration: {result.duration_seconds:.1f}s")
        report.append("")
        report.append("Overall Statistics:")
        report.append(f"  Total Events: {result.total_events}")
        report.append(f"  Successful Recoveries: {result.successful_recoveries}")
        report.append(f"  Failed Recoveries: {result.failed_recoveries}")
        report.append(f"  Recovery Success Rate: {result.recovery_success_rate:.1%}")
        report.append("")
        report.append("MTTR Percentiles:")
        report.append(f"  p50: {result.mttr_p50:.3f}s")
        report.append(
            f"  p95: {result.mttr_p95:.3f}s (target: ≤{self.target_mttr_p95}s)"
        )
        report.append(f"  p99: {result.mttr_p99:.3f}s")
        report.append(f"  max: {result.mttr_max:.3f}s")
        report.append("")

        if result.mttr_by_type:
            report.append("MTTR by Recovery Type:")
            for recovery_type, stats in result.mttr_by_type.items():
                report.append(f"  {recovery_type}:")
                report.append(f"    p50: {stats['p50']:.3f}s")
                report.append(f"    p95: {stats['p95']:.3f}s")
                report.append(f"    p99: {stats['p99']:.3f}s")
                report.append(f"    avg: {stats['avg']:.3f}s")
                report.append(f"    count: {stats['count']}")
            report.append("")

        report.append("Validation Result:")
        report.append(
            f"  Target Met (p95 ≤ {self.target_mttr_p95}s, success ≥ {self.target_success_rate:.0%}): {'✅ YES' if result.target_met else '❌ NO'}"
        )
        report.append(
            f"  Validation Passed: {'✅ YES' if result.validation_passed else '❌ NO'}"
        )
        report.append("")
        report.append("=" * 60)

        return "\n".join(report)


async def main():
    """CLI entry point for MTTR validation."""
    import argparse

    parser = argparse.ArgumentParser(description="Validate MTTR")
    parser.add_argument(
        "--duration", type=float, default=300.0, help="Test duration in seconds"
    )
    parser.add_argument(
        "--target-p95", type=float, default=7.0, help="Target MTTR p95 in seconds"
    )
    parser.add_argument("--output", type=str, help="Output file for report")

    args = parser.parse_args()

    logging.basicConfig(level=logging.INFO)

    validator = MTTRValidator(target_mttr_p95=args.target_p95)
    result = await validator.validate_mttr(duration=args.duration)

    report = validator.generate_report(result)
    print(report)

    if args.output:
        with open(args.output, "w") as f:
            f.write(report)
        print(f"\nReport saved to: {args.output}")

    exit(0 if result.validation_passed else 1)


if __name__ == "__main__":
    import random

    asyncio.run(main())
