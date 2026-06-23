#!/usr/bin/env python3
"""Test the restored swarm agent baseline."""

import json
import subprocess
import sys
from pathlib import Path

AGENTS = [
    ("chaos-engineer", "chaos_engineer_agent.py", ["--mode", "report"]),
    ("finops-agent", "finops_agent.py", []),
    ("compliance-agent", "compliance_agent.py", []),
    ("sre-agent", "sre_agent.py", []),
    ("docs-agent", "docs_agent.py", []),
    ("quantum-optimizer", "quantum_optimizer_agent.py", []),
    ("ml-ops-agent", "ml_ops_agent.py", []),
    ("devrel-agent", "devrel_agent.py", []),
]


def test_agent(name, script, args):
    """Test a single agent."""
    print(f"\n{'='*50}")
    print(f"Testing: {name}")
    print(f"{'='*50}")
    
    cmd = ["python3", f"scripts/agents/{script}"] + args
    try:
        result = subprocess.run(
            cmd,
            capture_output=True,
            text=True,
            timeout=30,
            cwd="/mnt/projects"
        )
        
        if result.returncode == 0:
            print(f"✅ {name}: SUCCESS")
            try:
                output = json.loads(result.stdout)
                print(f"   Report generated at: {output.get('generated_at', 'N/A')}")
                return True
            except json.JSONDecodeError:
                print(f"   Output: {result.stdout[:200]}...")
                return True
        else:
            print(f"❌ {name}: FAILED (exit {result.returncode})")
            print(f"   STDERR: {result.stderr[:200]}")
            return False
            
    except subprocess.TimeoutExpired:
        print(f"⏱️  {name}: TIMEOUT")
        return False
    except Exception as e:
        print(f"💥 {name}: ERROR - {e}")
        return False


def main():
    print("="*50)
    print("SWARM AGENT TEST SUITE")
    print("Testing all 8 new P0-P3 agents")
    print("="*50)
    
    results = {}
    passed = 0
    failed = 0
    
    for name, script, args in AGENTS:
        success = test_agent(name, script, args)
        results[name] = success
        if success:
            passed += 1
        else:
            failed += 1
    
    # Summary
    print(f"\n{'='*50}")
    print("SUMMARY")
    print(f"{'='*50}")
    print(f"Total: {len(AGENTS)} agents")
    print(f"Passed: {passed} ✅")
    print(f"Failed: {failed} ❌")
    print(f"Success rate: {passed/len(AGENTS)*100:.1f}%")
    
    return 0 if failed == 0 else 1


if __name__ == "__main__":
    sys.exit(main())
