#!/usr/bin/env python3
"""
Test Orchestrator - Runs all test suites and generates comprehensive report
"""

import subprocess
import time
import json
import sys
from datetime import datetime
from pathlib import Path
from typing import Dict, List, Tuple


class TestOrchestrator:
    """Orchestrates all test suites"""
    
    def __init__(self):
        self.results: Dict = {
            "start_time": datetime.now().isoformat(),
            "suites": {},
            "summary": {}
        }
        self.test_root = Path("/mnt/AC74CC2974CBF3DC")
    
    def run_test_suite(self, name: str, script_path: str, timeout: int = 300) -> Tuple[bool, str]:
        """Run a test suite and capture output"""
        print(f"\n{'='*70}")
        print(f"Running: {name}")
        print(f"{'='*70}")
        
        try:
            result = subprocess.run(
                ["python3", str(script_path)],
                cwd=str(self.test_root),
                capture_output=True,
                text=True,
                timeout=timeout
            )
            
            success = result.returncode == 0
            output = result.stdout + result.stderr
            
            # Print summary
            if "PASS" in output.upper() or "SUCCESS" in output.upper():
                print("✅ Tests PASSED")
            else:
                print("⚠️  Check output for details")
            
            # Print last 20 lines of output
            lines = output.split('\n')
            for line in lines[-20:]:
                if line.strip():
                    print(f"  {line}")
            
            return success, output
            
        except subprocess.TimeoutExpired:
            print(f"❌ Test suite timed out (>{timeout}s)")
            return False, "Test suite timed out"
        except Exception as e:
            print(f"❌ Error running test: {e}")
            return False, str(e)
    
    def run_all_tests(self) -> bool:
        """Run all test suites"""
        test_suites = [
            ("Quick Validation", "tests/quick_validation.py", 60),
            ("Database Resilience", "tests/integration/test_database_resilience.py", 300),
            ("Cache Resilience", "tests/integration/test_cache_resilience.py", 300),
            ("Advanced Chaos Scenarios", "chaos/advanced_chaos_scenarios.py", 600),
        ]
        
        all_passed = True
        
        for suite_name, script_path, timeout in test_suites:
            full_path = self.test_root / script_path
            
            if not full_path.exists():
                print(f"⚠️  Skipping {suite_name} - file not found: {script_path}")
                self.results["suites"][suite_name] = {
                    "status": "skipped",
                    "reason": "file not found"
                }
                continue
            
            start_time = time.time()
            success, output = self.run_test_suite(suite_name, full_path, timeout)
            elapsed = time.time() - start_time
            
            self.results["suites"][suite_name] = {
                "status": "passed" if success else "failed",
                "elapsed_seconds": elapsed,
                "output_length": len(output),
                "output_sample": output[-1000:]  # Last 1000 chars
            }
            
            if not success:
                all_passed = False
        
        return all_passed
    
    def generate_summary(self) -> Dict:
        """Generate test summary"""
        suites = self.results["suites"]
        
        total_suites = len(suites)
        passed_suites = sum(1 for s in suites.values() if s["status"] == "passed")
        failed_suites = sum(1 for s in suites.values() if s["status"] == "failed")
        skipped_suites = sum(1 for s in suites.values() if s["status"] == "skipped")
        
        total_time = sum(
            s.get("elapsed_seconds", 0) for s in suites.values()
        )
        
        summary = {
            "total_suites": total_suites,
            "passed": passed_suites,
            "failed": failed_suites,
            "skipped": skipped_suites,
            "total_time_seconds": total_time,
            "pass_rate": (passed_suites / total_suites * 100) if total_suites > 0 else 0,
            "end_time": datetime.now().isoformat()
        }
        
        self.results["summary"] = summary
        return summary
    
    def save_report(self) -> str:
        """Save test report to file"""
        timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
        filename = f"/mnt/AC74CC2974CBF3DC/.zencoder/test_results_{timestamp}.json"
        
        with open(filename, "w") as f:
            json.dump(self.results, f, indent=2)
        
        return filename
    
    def print_summary(self):
        """Print test summary"""
        summary = self.results["summary"]
        
        print("\n" + "="*70)
        print("TEST EXECUTION SUMMARY")
        print("="*70)
        print(f"Total Suites: {summary['total_suites']}")
        print(f"  ✅ Passed: {summary['passed']}")
        print(f"  ❌ Failed: {summary['failed']}")
        print(f"  ⏭️  Skipped: {summary['skipped']}")
        print(f"\nPass Rate: {summary['pass_rate']:.1f}%")
        print(f"Total Time: {summary['total_time_seconds']:.1f}s")
        print(f"\nStart: {self.results['start_time']}")
        print(f"End: {summary['end_time']}")
        print("="*70)
        
        # Detailed results
        print("\nDetailed Results:")
        for suite_name, suite_result in self.results["suites"].items():
            status_symbol = {
                "passed": "✅",
                "failed": "❌",
                "skipped": "⏭️"
            }.get(suite_result["status"], "❓")
            
            elapsed = suite_result.get("elapsed_seconds", 0)
            print(f"{status_symbol} {suite_name} ({elapsed:.1f}s)")


def main():
    """Main entry point"""
    orchestrator = TestOrchestrator()
    
    print("\n" + "="*70)
    print("x0tta6bl4 TEST ORCHESTRATOR")
    print("="*70)
    print(f"Started: {orchestrator.results['start_time']}")
    print("="*70)
    
    # Run all tests
    all_passed = orchestrator.run_all_tests()
    
    # Generate summary
    orchestrator.generate_summary()
    
    # Print summary
    orchestrator.print_summary()
    
    # Save report
    report_file = orchestrator.save_report()
    print(f"\n📊 Report saved to: {report_file}")
    
    # Return exit code
    return 0 if all_passed else 1


if __name__ == "__main__":
    exit_code = main()
    sys.exit(exit_code)
