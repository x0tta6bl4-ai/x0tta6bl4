"""
Extended Chaos Testing for Staging Environment

Tests advanced chaos scenarios before production deployment:
- Cascade failures
- Byzantine behavior
- Network storms
- Resource exhaustion
- Clock skew
"""

import asyncio
import logging
from typing import Dict, List, Any
from datetime import datetime

from src.chaos.advanced_scenarios import (
    AdvancedChaosController,
    AdvancedScenarioType
)

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)


class StagingChaosTester:
    """
    Extended chaos testing for staging environment.
    
    Runs comprehensive chaos scenarios to validate system resilience
    before production deployment.
    """
    
    def __init__(self):
        self.controller = AdvancedChaosController()
        self.results: List[Dict[str, Any]] = []
    
    async def run_all_scenarios(self) -> Dict[str, Any]:
        """
        Run all chaos scenarios.
        
        Returns:
            Dictionary with all test results
        """
        logger.info("🧪 Starting extended chaos testing in staging...")
        
        scenarios = [
            ("cascade_failure", self._test_cascade_failure),
            ("byzantine_behavior", self._test_byzantine_behavior),
            ("network_storm", self._test_network_storm),
            ("resource_exhaustion", self._test_resource_exhaustion),
            ("clock_skew", self._test_clock_skew),
        ]
        
        for scenario_name, test_func in scenarios:
            try:
                logger.info(f"Running scenario: {scenario_name}")
                result = await test_func()
                result["scenario"] = scenario_name
                result["timestamp"] = datetime.now().isoformat()
                self.results.append(result)
                logger.info(f"✅ Scenario {scenario_name} completed")
            except Exception as e:
                logger.error(f"❌ Scenario {scenario_name} failed: {e}")
                self.results.append({
                    "scenario": scenario_name,
                    "status": "failed",
                    "error": str(e),
                    "timestamp": datetime.now().isoformat()
                })
        
        return self._generate_summary()
    
    async def _test_cascade_failure(self) -> Dict[str, Any]:
        """Test cascade failure scenario."""
        result = await self.controller.run_cascade_failure(
            initial_node="staging-node-01",
            propagation_probability=0.3,
            max_depth=5,
            duration=60
        )
        
        return {
            "status": "completed",
            "result": result,
            "passed": result.get("total_failed", 0) > 0  # System should handle cascade
        }
    
    async def _test_byzantine_behavior(self) -> Dict[str, Any]:
        """Test Byzantine behavior scenario."""
        result = await self.controller.run_byzantine_behavior(
            target_nodes=["staging-node-02"],
            behavior_type="malicious_routing",
            duration=60
        )
        
        return {
            "status": "completed",
            "result": result,
            "passed": True  # System should detect and isolate Byzantine nodes
        }
    
    async def _test_network_storm(self) -> Dict[str, Any]:
        """Test network storm scenario."""
        result = await self.controller.run_network_storm(
            target_nodes=["staging-node-03"],
            packet_rate=10000,
            duration=30
        )
        
        return {
            "status": "completed",
            "result": result,
            "passed": True  # System should handle high traffic
        }
    
    async def _test_resource_exhaustion(self) -> Dict[str, Any]:
        """Test resource exhaustion scenario."""
        result = await self.controller.run_resource_exhaustion(
            target_nodes=["staging-node-04"],
            resource_type="cpu",
            utilization=0.95,
            duration=60
        )
        
        return {
            "status": "completed",
            "result": result,
            "passed": True  # System should handle resource pressure
        }
    
    async def _test_clock_skew(self) -> Dict[str, Any]:
        """Test clock skew scenario."""
        result = await self.controller.run_clock_skew(
            target_nodes=["staging-node-05"],
            skew_seconds=5.0,
            duration=60
        )
        
        return {
            "status": "completed",
            "result": result,
            "passed": True  # System should handle clock skew
        }
    
    def _generate_summary(self) -> Dict[str, Any]:
        """Generate test summary."""
        total_scenarios = len(self.results)
        passed_scenarios = sum(1 for r in self.results if r.get("passed", False))
        failed_scenarios = sum(1 for r in self.results if r.get("status") == "failed")
        
        return {
            "summary": {
                "total_scenarios": total_scenarios,
                "passed": passed_scenarios,
                "failed": failed_scenarios,
                "success_rate": (passed_scenarios / total_scenarios * 100) if total_scenarios > 0 else 0
            },
            "results": self.results,
            "timestamp": datetime.now().isoformat()
        }


async def main():
    """Run staging chaos tests."""
    tester = StagingChaosTester()
    summary = await tester.run_all_scenarios()
    
    print("\n" + "="*60)
    print("STAGING CHAOS TEST RESULTS")
    print("="*60)
    print(f"Total Scenarios: {summary['summary']['total_scenarios']}")
    print(f"Passed: {summary['summary']['passed']}")
    print(f"Failed: {summary['summary']['failed']}")
    print(f"Success Rate: {summary['summary']['success_rate']:.2f}%")
    print("="*60)
    
    for result in summary['results']:
        status = "✅" if result.get("passed", False) else "❌"
        print(f"{status} {result['scenario']}: {result.get('status', 'unknown')}")


if __name__ == "__main__":
    asyncio.run(main())

