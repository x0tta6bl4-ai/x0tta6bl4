#!/usr/bin/env python3
"""Autonomous Agentic Harness Optimization Loop (Loop A).

Automates baseline vs candidate evaluation, prompt/profile mutations,
HQI scoring, and safe auto-commit/rollback.
Reference: BitGN & x0tta6bl4 Agentic Harness Specification.
"""

from __future__ import annotations

import argparse
import json
import shutil
import subprocess
import sys
from pathlib import Path
from typing import Optional

PROJECT_ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(PROJECT_ROOT))

from scripts.agents.agent_feedback_loop import AgentFeedbackLoop


def run_cycle(agents: str, dry_run: bool = True, profile_file: Optional[str] = None) -> Path:
    """Run agent cycle and return summary.json path."""
    cmd = [
        "python3",
        "scripts/agents/run_agent_cycle.py",
        "--agents",
        agents,
    ]
    if dry_run:
        cmd.append("--dry-run")
    if profile_file:
        cmd.extend(["--profile-file", profile_file])

    proc = subprocess.run(
        cmd,
        cwd=str(PROJECT_ROOT),
        capture_output=True,
        text=True,
        check=False,
    )

    # Parse run_dir from output
    run_dir_rel = None
    for line in proc.stdout.splitlines():
        if "[agent-cycle] run_dir=" in line:
            run_dir_rel = line.split("=")[1].strip()
            break

    if not run_dir_rel:
        raise RuntimeError(f"Failed to extract run_dir from cycle output:\n{proc.stdout}\n{proc.stderr}")

    summary_json = PROJECT_ROOT / run_dir_rel / "summary.json"
    if not summary_json.exists():
        raise FileNotFoundError(f"Summary JSON missing: {summary_json}")

    return summary_json


def generate_candidate_mutation(
    baseline_profile_path: Path,
    candidate_out_path: Path,
    target_agent: str = "agent-2",
) -> Path:
    """Mutate agent profile for experiment testing in Loop A."""
    data = json.loads(baseline_profile_path.read_text(encoding="utf-8"))
    profiles = data.get("profiles", [])

    for prof in profiles:
        if prof.get("agent_id") == target_agent:
            # Add strict validation flag or optimize profile settings
            prof["critical"] = True
            prof["skill_name"] = f"{prof['skill_name']}-optimized"

    candidate_out_path.parent.mkdir(parents=True, exist_ok=True)
    candidate_out_path.write_text(json.dumps(data, indent=2), encoding="utf-8")
    return candidate_out_path


def main() -> int:
    parser = argparse.ArgumentParser(description="x0tta6bl4 Autonomous Agentic Harness Optimization Tuner (Loop A)")
    parser.add_argument("--experiment-name", default="exp_auto_tune_harness", help="Name of experiment")
    parser.add_argument("--agents", default="agent-1,agent-2,agent-3,agent-4", help="Agents to include in cycle")
    parser.add_argument("--real-run", action="store_true", help="Execute real agent commands instead of dry-run")
    parser.add_argument("--auto-mutate", action="store_true", help="Mutate candidate profile and commit/rollback based on HQI")
    parser.add_argument("--target-agent", default="agent-2", help="Agent ID to target for mutation")
    args = parser.parse_args()

    print(f"🚀 Starting Harness Optimization Loop A for experiment: '{args.experiment_name}'")
    dry_run = not args.real_run
    baseline_profile_path = PROJECT_ROOT / "scripts" / "agents" / "agent_cycle_profiles.json"
    candidate_profile_path = PROJECT_ROOT / ".tmp" / "candidate_profiles.json"

    # 1. Run Baseline Cycle
    print("📍 [1/3] Executing Baseline Cycle...")
    baseline_summary = run_cycle(agents=args.agents, dry_run=dry_run, profile_file=str(baseline_profile_path.relative_to(PROJECT_ROOT)))
    print(f"   Baseline Summary: {baseline_summary.relative_to(PROJECT_ROOT)}")

    # 2. Mutate Candidate Profile & Run Candidate Cycle
    profile_to_use = None
    if args.auto_mutate and baseline_profile_path.exists():
        print(f"🧬 [2/3] Generating Candidate Mutation for agent '{args.target_agent}'...")
        generate_candidate_mutation(baseline_profile_path, candidate_profile_path, target_agent=args.target_agent)
        profile_to_use = str(candidate_profile_path.relative_to(PROJECT_ROOT))
    else:
        print("🔬 [2/3] Executing Candidate Cycle (Default profile)...")

    candidate_summary = run_cycle(agents=args.agents, dry_run=dry_run, profile_file=profile_to_use)
    print(f"   Candidate Summary: {candidate_summary.relative_to(PROJECT_ROOT)}")

    # 3. Evaluate Experiment via AgentFeedbackLoop (HQI)
    print("📊 [3/3] Evaluating Experiment via AgentFeedbackLoop HQI...")
    feedback_loop = AgentFeedbackLoop()
    result = feedback_loop.evaluate_experiment(
        experiment_name=args.experiment_name,
        candidate_summary=candidate_summary,
        baseline_summary=baseline_summary,
    )

    verdict = result["verdict"]
    print("\n" + "=" * 60)
    print("=== 🎯 HARNESS OPTIMIZATION VERDICT ===")
    print("=" * 60)
    print(f"  Experiment Name: {result['experiment_name']}")
    print(f"  Baseline HQI:    {result['baseline_score']:.3f}")
    print(f"  Candidate HQI:   {result['candidate_score']:.3f}")
    print(f"  Score Delta:     {result['score_delta']:+.3f}")
    print(f"  Verdict:         {'✅ KEEP' if verdict == 'KEEP' else '🔴 ROLLBACK'}")
    print("=" * 60)

    # Commit or Rollback if auto-mutate is active
    if args.auto_mutate and candidate_profile_path.exists():
        if verdict == "KEEP":
            print(f"💾 Committing candidate profile to {baseline_profile_path.relative_to(PROJECT_ROOT)}")
            shutil.copy(candidate_profile_path, baseline_profile_path)
        else:
            print("↺ Rolling back candidate mutation (Baseline preserved).")
            candidate_profile_path.unlink(missing_ok=True)

    # Print Error Heatmap
    heatmap_str = feedback_loop.render_error_heatmap_ascii()
    print("\n📊 Error Heatmap:")
    print(heatmap_str)

    return 0


if __name__ == "__main__":
    raise SystemExit(main())

