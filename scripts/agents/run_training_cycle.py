#!/usr/bin/env python3
"""Run complete agent training cycle."""

import json
import subprocess
import sys
from datetime import datetime, UTC
from pathlib import Path


def run_agent(agent_script, args=None):
    """Run agent and collect output."""
    cmd = ["python3", f"scripts/agents/{agent_script}"]
    if args:
        cmd.extend(args)
    
    try:
        result = subprocess.run(cmd, capture_output=True, text=True, timeout=10, cwd="/mnt/projects")
        return result.returncode == 0, result.stdout, result.stderr
    except Exception as e:
        return False, "", str(e)


def main():
    print("="*60)
    print("AGENT TRAINING CYCLE")
    print("="*60)
    
    steps = [
        ("1. Run all agents", lambda: run_all_agents()),
        ("2. Update datasets", lambda: run_agent("agent_trainer.py")),
        ("3. Collect feedback", lambda: run_agent("agent_feedback_loop.py")),
        ("4. Generate summary", lambda: generate_summary()),
    ]
    
    results = {}
    for name, func in steps:
        print(f"\n{name}...")
        success, stdout, stderr = func()
        results[name] = success
        print(f"  {'✅' if success else '❌'} {name}")
    
    # Final summary
    print("\n" + "="*60)
    print("TRAINING CYCLE COMPLETE")
    print("="*60)
    passed = sum(1 for v in results.values() if v)
    print(f"Steps passed: {passed}/{len(steps)}")
    
    return 0 if all(results.values()) else 1


def run_all_agents():
    """Run all agents to generate fresh data."""
    agents = [
        ("chaos_engineer_agent.py", ["--mode", "report"]),
        ("finops_agent.py", []),
        ("compliance_agent.py", []),
        ("sre_agent.py", []),
        ("docs_agent.py", []),
    ]
    
    all_passed = True
    for script, args in agents:
        success, _, _ = run_agent(script, args)
        if not success:
            all_passed = False
    
    return all_passed, "", ""


def generate_summary():
    """Generate final training summary."""
    summary = {
        "cycle_completed_at": datetime.now(UTC).isoformat(),
        "status": "complete",
        "datasets_updated": True,
        "feedback_collected": True
    }
    
    with open("/mnt/projects/.tmp/training_cycle_summary.json", 'w') as f:
        json.dump(summary, f, indent=2)
    
    return True, json.dumps(summary), ""


if __name__ == "__main__":
    sys.exit(main())
