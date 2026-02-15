"""
Chaos Testing + MTTR Validation Integration

Combines chaos testing scenarios with MTTR validation to ensure
system meets Stage 1 requirements:
- MTTR p95 ≤ 7s
- Recovery success rate >95%
- Works correctly with 50+ nodes
"""

import asyncio
import logging
from datetime import datetime
from typing import Dict, List

from tests.chaos.test_slot_sync_chaos import (ChaosTestResult,
                                              SlotSyncChaosTester)
from tests.validation.mttr_validator import (MTTRValidationResult,
                                             MTTRValidator, RecoveryType)

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)


class ChaosMTTRIntegration:
    """
    Integrated chaos testing and MTTR validation.

    Runs chaos scenarios while simultaneously validating MTTR,
    ensuring system meets Stage 1 requirements.
    """

    def __init__(
        self,
        num_nodes: int = 50,
        target_mttr_p95: float = 7.0,
        target_success_rate: float = 0.95,
    ):
        """
        Initialize integrated tester.

        Args:
            num_nodes: Number of nodes in mesh
            target_mttr_p95: Target MTTR p95 in seconds
            target_success_rate: Target recovery success rate
        """
        self.num_nodes = num_nodes
        self.chaos_tester = SlotSyncChaosTester(num_nodes=num_nodes)
        self.mttr_validator = MTTRValidator(
            target_mttr_p95=target_mttr_p95, target_success_rate=target_success_rate
        )

    async def run_integrated_test(
        self,
        duration: float = 300.0,
        failure_rate: float = 0.1,
        partition_probability: float = 0.05,
    ) -> Dict:
        """
        Run integrated chaos + MTTR validation test.

        Args:
            duration: Test duration in seconds
            failure_rate: Node failure rate per second
            partition_probability: Network partition probability

        Returns:
            Dict with combined test results
        """
        logger.info(
            f"Starting integrated chaos + MTTR test: "
            f"{self.num_nodes} nodes, {duration}s duration"
        )

        # Start both tests concurrently
        chaos_task = asyncio.create_task(
            self.chaos_tester.run_chaos_test(
                duration=duration,
                failure_rate=failure_rate,
                partition_probability=partition_probability,
            )
        )

        mttr_task = asyncio.create_task(
            self.mttr_validator.validate_mttr(
                duration=duration,
                failure_scenarios=[
                    RecoveryType.NODE_FAILURE,
                    RecoveryType.NETWORK_PARTITION,
                    RecoveryType.LINK_FAILURE,
                    RecoveryType.ROUTE_FAILURE,
                ],
            )
        )

        # Wait for both to complete
        chaos_result, mttr_result = await asyncio.gather(chaos_task, mttr_task)

        # Combine results
        combined_result = {
            "timestamp": datetime.now(),
            "duration_seconds": duration,
            "nodes": self.num_nodes,
            "chaos_test": {
                "slot_sync_success_rate": chaos_result.slot_sync_success_rate,
                "beacon_collisions": chaos_result.beacon_collisions,
                "recovery_time_avg": chaos_result.recovery_time_avg,
                "recovery_time_max": chaos_result.recovery_time_max,
                "race_conditions": chaos_result.race_conditions_detected,
                "test_passed": chaos_result.test_passed,
            },
            "mttr_validation": {
                "mttr_p50": mttr_result.mttr_p50,
                "mttr_p95": mttr_result.mttr_p95,
                "mttr_p99": mttr_result.mttr_p99,
                "mttr_max": mttr_result.mttr_max,
                "recovery_success_rate": mttr_result.recovery_success_rate,
                "total_events": mttr_result.total_events,
                "target_met": mttr_result.target_met,
                "validation_passed": mttr_result.validation_passed,
            },
            "overall_passed": (
                chaos_result.test_passed and mttr_result.validation_passed
            ),
        }

        logger.info(
            f"Integrated test complete: "
            f"Chaos passed: {chaos_result.test_passed}, "
            f"MTTR passed: {mttr_result.validation_passed}, "
            f"Overall: {combined_result['overall_passed']}"
        )

        return combined_result

    def generate_combined_report(self, result: Dict) -> str:
        """Generate combined chaos + MTTR report."""
        report = []
        report.append("=" * 60)
        report.append("Chaos Testing + MTTR Validation Report")
        report.append("=" * 60)
        report.append("")
        report.append(f"Timestamp: {result['timestamp']}")
        report.append(f"Duration: {result['duration_seconds']:.1f}s")
        report.append(f"Nodes: {result['nodes']}")
        report.append("")

        report.append("Chaos Test Results:")
        chaos = result["chaos_test"]
        report.append(
            f"  Slot Sync Success Rate: {chaos['slot_sync_success_rate']:.1%}"
        )
        report.append(f"  Beacon Collisions: {chaos['beacon_collisions']}")
        report.append(f"  Avg Recovery Time: {chaos['recovery_time_avg']:.3f}s")
        report.append(f"  Max Recovery Time: {chaos['recovery_time_max']:.3f}s")
        report.append(f"  Race Conditions: {chaos['race_conditions']}")
        report.append(f"  Test Passed: {'✅ YES' if chaos['test_passed'] else '❌ NO'}")
        report.append("")

        report.append("MTTR Validation Results:")
        mttr = result["mttr_validation"]
        report.append(f"  MTTR p50: {mttr['mttr_p50']:.3f}s")
        report.append(f"  MTTR p95: {mttr['mttr_p95']:.3f}s (target: ≤7.0s)")
        report.append(f"  MTTR p99: {mttr['mttr_p99']:.3f}s")
        report.append(f"  MTTR max: {mttr['mttr_max']:.3f}s")
        report.append(f"  Recovery Success Rate: {mttr['recovery_success_rate']:.1%}")
        report.append(f"  Total Events: {mttr['total_events']}")
        report.append(f"  Target Met: {'✅ YES' if mttr['target_met'] else '❌ NO'}")
        report.append(
            f"  Validation Passed: {'✅ YES' if mttr['validation_passed'] else '❌ NO'}"
        )
        report.append("")

        report.append("Overall Result:")
        report.append(
            f"  All Tests Passed: {'✅ YES' if result['overall_passed'] else '❌ NO'}"
        )
        report.append("")
        report.append("=" * 60)

        return "\n".join(report)


async def main():
    """CLI entry point."""
    import argparse

    parser = argparse.ArgumentParser(description="Chaos + MTTR integration test")
    parser.add_argument("--nodes", type=int, default=50, help="Number of nodes")
    parser.add_argument("--duration", type=float, default=300.0, help="Test duration")
    parser.add_argument(
        "--failure-rate", type=float, default=0.1, help="Failure rate per second"
    )
    parser.add_argument("--output", type=str, help="Output file for report")

    args = parser.parse_args()

    tester = ChaosMTTRIntegration(num_nodes=args.nodes)
    result = await tester.run_integrated_test(
        duration=args.duration, failure_rate=args.failure_rate
    )

    report = tester.generate_combined_report(result)
    print(report)

    if args.output:
        with open(args.output, "w") as f:
            f.write(report)
        print(f"\nReport saved to: {args.output}")

    exit(0 if result["overall_passed"] else 1)


if __name__ == "__main__":
    asyncio.run(main())
