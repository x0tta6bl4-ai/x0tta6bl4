#!/usr/bin/env python3
"""Autonomous Background Auto-Tuner Daemon (Loop A Background Engine).

Runs continuous agent profile mutations and HQI evaluations in background mode,
saving optimization logs and auto-committing high-performing agent configurations.
"""

from __future__ import annotations

import argparse
import logging
import sys
import time
from pathlib import Path

PROJECT_ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(PROJECT_ROOT))

from scripts.agents.agent_feedback_loop import AgentFeedbackLoop
from scripts.agents.auto_harness_tuner import run_cycle, generate_candidate_mutation

logger = logging.getLogger("auto_tuner_daemon")


def run_daemon_step(target_agent: str = "agent-2", dry_run: bool = True) -> float:
    """Run single background tuning step and return HQI delta."""
    baseline_profile_path = PROJECT_ROOT / "scripts" / "agents" / "agent_cycle_profiles.json"
    candidate_profile_path = PROJECT_ROOT / ".tmp" / "candidate_profiles.json"

    # 1. Baseline Run
    baseline_summary = run_cycle(agents="agent-1,agent-2,agent-3,agent-4", dry_run=dry_run, profile_file=str(baseline_profile_path.relative_to(PROJECT_ROOT)))
    
    # 2. Mutate Candidate Profile
    generate_candidate_mutation(baseline_profile_path, candidate_profile_path, target_agent=target_agent)

    # 3. Candidate Run
    candidate_summary = run_cycle(agents="agent-1,agent-2,agent-3,agent-4", dry_run=dry_run, profile_file=str(candidate_profile_path.relative_to(PROJECT_ROOT)))

    # 4. Evaluate via AgentFeedbackLoop
    fb_loop = AgentFeedbackLoop()
    verdict = fb_loop.evaluate_experiment(
        experiment_name=f"daemon_tune_{target_agent}",
        candidate_summary=candidate_summary,
        baseline_summary=baseline_summary,
    )

    logger.info(
        f"🤖 Daemon Tuning Step Complete for {target_agent}: Verdict={verdict['verdict']} "
        f"(Baseline HQI={verdict['baseline_score']:.3f}, Candidate HQI={verdict['candidate_score']:.3f})"
    )
    return verdict["score_delta"]


def main() -> int:
    parser = argparse.ArgumentParser(description="x0tta6bl4 Background Auto-Tuner Daemon (Loop A)")
    parser.add_argument("--interval-seconds", type=int, default=60, help="Interval in seconds between tuning runs")
    parser.add_argument("--iterations", type=int, default=1, help="Number of iterations to run (0 for infinite loop)")
    parser.add_argument("--target-agent", default="agent-2", help="Target agent ID for mutation")
    parser.add_argument("--once", action="store_true", help="Run single iteration and exit")
    args = parser.parse_args()

    logging.basicConfig(
        level=logging.INFO,
        format="%(asctime)s [%(levelname)s] [auto-tuner-daemon] %(message)s",
    )

    print("🚀 Starting x0tta6bl4 Autonomous Auto-Tuner Background Daemon...")
    iterations_target = 1 if args.once else args.iterations
    count = 0

    while True:
        count += 1
        print(f"\n🔄 [Iteration {count}] Running background tuning step...")
        try:
            delta = run_daemon_step(target_agent=args.target_agent, dry_run=True)
            print(f"✅ Step finished. HQI Delta: {delta:+.3f}")
        except Exception as e:
            print(f"⚠️ Tuning step error: {e}", file=sys.stderr)

        if iterations_target > 0 and count >= iterations_target:
            print(f"\n🏁 Daemon completed {count} iteration(s). Exiting with Exit Code 0.")
            break

        print(f"💤 Sleeping for {args.interval_seconds}s before next cycle...")
        time.sleep(args.interval_seconds)

    return 0


if __name__ == "__main__":
    raise SystemExit(main())
