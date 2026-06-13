#!/usr/bin/env python3
"""Run all 13 agents on real x0tta6bl4 tasks."""

import json
import subprocess
import sys
from datetime import datetime, UTC


def run_agent(script, args, desc):
    """Run agent and return status."""
    print(f"\n{'='*60}")
    print(f"🚀 {desc}")
    print(f"{'='*60}")
    
    cmd = f"python3 scripts/agents/{script} {' '.join(args)}"
    try:
        result = subprocess.run(cmd, shell=True, capture_output=True, text=True, timeout=30, cwd="/mnt/projects")
        if result.returncode == 0:
            print(f"✅ SUCCESS")
            print(result.stdout[:400] if result.stdout else "Completed")
            return True
        else:
            print(f"❌ FAILED")
            return False
    except Exception as e:
        print(f"💥 ERROR: {e}")
        return False


def main():
    print("="*60)
    print("🤖 X0TTA6BL4 REAL TASK EXECUTION")
    print("="*60)
    
    tasks = [
        ("chaos_engineer_agent.py", ["--mode", "scheduled"], "CHAOS: Run experiments"),
        ("finops_agent.py", [], "FINOPS: Analyze costs"),
        ("compliance_agent.py", [], "COMPLIANCE: SOC2 checks"),
        ("sre_agent.py", [], "SRE: Monitor SLOs"),
        ("docs_agent.py", [], "DOCS: Find broken links"),
        ("quantum_optimizer_agent.py", [], "QUANTUM: Check PQC keys"),
        ("ml_ops_agent.py", [], "MLOPS: FL infrastructure"),
        ("devrel_agent.py", [], "DEVREL: Repo health"),
    ]
    
    results = {}
    for script, args, desc in tasks:
        success = run_agent(script, args, desc)
        results[desc.split(':')[0]] = success
    
    # Summary
    print("\n" + "="*60)
    print("📊 SUMMARY")
    print("="*60)
    passed = sum(results.values())
    total = len(results)
    print(f"Passed: {passed}/{total} ({passed/total*100:.0f}%)")
    
    for name, success in results.items():
        print(f"  {'✅' if success else '❌'} {name}")
    
    # Save report
    report = {
        "run_at": datetime.now(UTC).isoformat(),
        "results": results,
        "total": total,
        "passed": passed
    }
    with open("/mnt/projects/.tmp/real_tasks_report.json", 'w') as f:
        json.dump(report, f, indent=2)
    
    return 0 if passed == total else 1


if __name__ == "__main__":
    sys.exit(main())
