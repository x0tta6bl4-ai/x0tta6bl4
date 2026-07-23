#!/usr/bin/env python3
"""Agent Feedback Loop - Continuous learning, Evals Error Heatmap, and Dual-Loop Optimization System."""

from __future__ import annotations

import argparse
import json
import sqlite3
from datetime import datetime, UTC
from pathlib import Path
from typing import Any, Dict, List, Optional


class AgentFeedbackLoop:
    """Collect feedback, track Evals metrics, generate Error Heatmaps, and manage dual optimization loops."""

    def __init__(self, db_path: Optional[Path] = None):
        self.project_root = Path(__file__).resolve().parents[2]
        self.feedback_db = db_path or (self.project_root / ".tmp" / "agent_feedback.db")
        self.feedback_db.parent.mkdir(parents=True, exist_ok=True)
        self._init_db()

    def _init_db(self):
        conn = sqlite3.connect(self.feedback_db)
        cursor = conn.cursor()
        cursor.execute("""
            CREATE TABLE IF NOT EXISTS feedback (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                agent_name TEXT NOT NULL,
                action_type TEXT NOT NULL,
                result TEXT NOT NULL,
                accuracy_score REAL NOT NULL,
                error_type TEXT DEFAULT 'NONE',
                created_at TIMESTAMP NOT NULL
            )
        """)
        cursor.execute("""
            CREATE TABLE IF NOT EXISTS experiments (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                experiment_name TEXT NOT NULL,
                baseline_score REAL NOT NULL,
                candidate_score REAL NOT NULL,
                score_delta REAL NOT NULL,
                verdict TEXT NOT NULL,
                details TEXT,
                created_at TIMESTAMP NOT NULL
            )
        """)
        cursor.execute("""
            CREATE TABLE IF NOT EXISTS edge_cases (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                case_id TEXT UNIQUE NOT NULL,
                task_description TEXT NOT NULL,
                failure_reason TEXT NOT NULL,
                expected_behavior TEXT NOT NULL,
                severity TEXT DEFAULT 'high',
                created_at TIMESTAMP NOT NULL
            )
        """)
        conn.commit()
        conn.close()

    def record_feedback(
        self,
        agent: str,
        action: str,
        result: str,
        score: float,
        error_type: str = "NONE",
    ):
        """Record agent action feedback."""
        conn = sqlite3.connect(self.feedback_db)
        cursor = conn.cursor()
        cursor.execute("""
            INSERT INTO feedback (agent_name, action_type, result, accuracy_score, error_type, created_at)
            VALUES (?, ?, ?, ?, ?, ?)
        """, (agent, action, result, score, error_type, datetime.now(UTC).isoformat()))
        conn.commit()
        conn.close()

    def ingest_cycle_summary(self, summary_input: str | Path | dict) -> dict:
        """Ingest cycle summary output from run_agent_cycle.py and record agent feedback."""
        if isinstance(summary_input, (str, Path)):
            path = Path(summary_input)
            if not path.exists():
                raise FileNotFoundError(f"Summary file not found: {path}")
            summary = json.loads(path.read_text(encoding="utf-8"))
        else:
            summary = summary_input

        results = summary.get("results", [])
        ingested_count = 0
        total_score = 0.0

        for r in results:
            agent_id = r.get("agent_id", "unknown")
            rc = r.get("return_code", -1)
            timed_out = r.get("timed_out", False)

            if rc == 0 and not timed_out:
                score = 1.0
                result_str = "pass"
                err = "NONE"
            elif timed_out:
                score = 0.0
                result_str = "fail"
                err = "TIMEOUT"
            else:
                score = 0.0
                result_str = "fail"
                err = "EXECUTION_ERROR"

            self.record_feedback(
                agent=agent_id,
                action="agent_cycle_run",
                result=result_str,
                score=score,
                error_type=err,
            )
            ingested_count += 1
            total_score += score

        overall_score = round(total_score / ingested_count, 3) if ingested_count > 0 else 0.0
        return {
            "ingested_agents": ingested_count,
            "overall_score": overall_score,
            "exit_code": summary.get("exit_code", 1),
        }

    def generate_error_heatmap(self) -> dict:
        """Generate Error Heatmap per agent and error type."""
        conn = sqlite3.connect(self.feedback_db)
        cursor = conn.cursor()
        cursor.execute("""
            SELECT agent_name, error_type, COUNT(*)
            FROM feedback
            GROUP BY agent_name, error_type
        """)
        rows = cursor.fetchall()
        conn.close()

        heatmap: Dict[str, Dict[str, int]] = {}
        for agent, err_type, count in rows:
            if agent not in heatmap:
                heatmap[agent] = {}
            heatmap[agent][err_type] = count

        return heatmap

    def render_error_heatmap_ascii(self) -> str:
        """Render Error Heatmap as an ASCII table string."""
        heatmap = self.generate_error_heatmap()
        if not heatmap:
            return "No feedback data recorded."

        lines = ["+------------+---------+-----------------+---------+",
                 "| Agent      | NONE    | EXECUTION_ERROR | TIMEOUT |",
                 "+------------+---------+-----------------+---------+"]
        for agent, errors in sorted(heatmap.items()):
            none_cnt = errors.get("NONE", 0)
            exec_cnt = errors.get("EXECUTION_ERROR", 0)
            tout_cnt = errors.get("TIMEOUT", 0)
            lines.append(f"| {agent:<10} | {none_cnt:<7} | {exec_cnt:<15} | {tout_cnt:<7} |")
        lines.append("+------------+---------+-----------------+---------+")
        return "\n".join(lines)

    def calculate_hqi(self, summary_input: str | Path | dict) -> dict:
        """Calculate Harness Quality Index (HQI): composite metric combining PassRate, Speed, and Reliability."""
        if isinstance(summary_input, (str, Path)):
            path = Path(summary_input)
            if not path.exists():
                return {"hqi": 0.0, "pass_rate": 0.0, "speed_factor": 0.0, "reliability": 0.0}
            summary = json.loads(path.read_text(encoding="utf-8"))
        else:
            summary = summary_input

        results = summary.get("results", [])
        if not results:
            return {"hqi": 0.0, "pass_rate": 0.0, "speed_factor": 0.0, "reliability": 0.0}

        total = len(results)
        passes = sum(1 for r in results if r.get("return_code") == 0 and not r.get("timed_out"))
        failures = total - passes
        durations = [r.get("duration_sec", 0.0) for r in results]
        avg_dur = sum(durations) / total if total > 0 else 0.0

        pass_rate = passes / total
        speed_factor = max(0.0, min(1.0, 1.0 - (avg_dur / 30.0)))
        reliability = 1.0 - (failures / total)

        hqi = round(0.50 * pass_rate + 0.25 * speed_factor + 0.25 * reliability, 3)

        return {
            "hqi": hqi,
            "pass_rate": round(pass_rate, 3),
            "speed_factor": round(speed_factor, 3),
            "reliability": round(reliability, 3),
            "avg_duration_sec": round(avg_dur, 3),
        }

    def evaluate_experiment(
        self,
        experiment_name: str,
        candidate_summary: str | Path | dict,
        baseline_summary: Optional[str | Path | dict] = None,
    ) -> dict:
        """Loop A: Compare candidate harness configuration against baseline using HQI."""
        cand_stats = self.ingest_cycle_summary(candidate_summary)
        cand_hqi = self.calculate_hqi(candidate_summary)
        candidate_score = cand_hqi["hqi"]

        if baseline_summary is not None:
            base_hqi = self.calculate_hqi(baseline_summary)
            baseline_score = base_hqi["hqi"]
        else:
            baseline_score = 0.80  # Default baseline threshold

        score_delta = round(candidate_score - baseline_score, 3)
        verdict = "KEEP" if score_delta >= 0 else "ROLLBACK"

        conn = sqlite3.connect(self.feedback_db)
        cursor = conn.cursor()
        cursor.execute("""
            INSERT INTO experiments (experiment_name, baseline_score, candidate_score, score_delta, verdict, details, created_at)
            VALUES (?, ?, ?, ?, ?, ?, ?)
        """, (
            experiment_name,
            baseline_score,
            candidate_score,
            score_delta,
            verdict,
            f"Ingested {cand_stats['ingested_agents']} agents. Exit code: {cand_stats['exit_code']}. HQI details: {json.dumps(cand_hqi)}",
            datetime.now(UTC).isoformat(),
        ))
        conn.commit()
        conn.close()

        return {
            "experiment_name": experiment_name,
            "baseline_score": baseline_score,
            "candidate_score": candidate_score,
            "score_delta": score_delta,
            "verdict": verdict,
            "candidate_hqi_details": cand_hqi,
        }

    def distill_edge_case(
        self,
        case_id: str,
        task_description: str,
        failure_reason: str,
        expected_behavior: str,
        severity: str = "high",
    ) -> dict:
        """Loop B: Distill production edge case into Evals benchmark dataset."""
        conn = sqlite3.connect(self.feedback_db)
        cursor = conn.cursor()
        cursor.execute("""
            INSERT OR REPLACE INTO edge_cases (case_id, task_description, failure_reason, expected_behavior, severity, created_at)
            VALUES (?, ?, ?, ?, ?, ?)
        """, (
            case_id,
            task_description,
            failure_reason,
            expected_behavior,
            severity,
            datetime.now(UTC).isoformat(),
        ))
        conn.commit()

        # Export edge cases to JSON for regression Evals
        cursor.execute("SELECT case_id, task_description, failure_reason, expected_behavior, severity FROM edge_cases")
        rows = cursor.fetchall()
        conn.close()

        cases_export = [
            {
                "case_id": r[0],
                "task_description": r[1],
                "failure_reason": r[2],
                "expected_behavior": r[3],
                "severity": r[4],
            }
            for r in rows
        ]

        eval_cases_file = self.project_root / ".tmp" / "eval_edge_cases.json"
        eval_cases_file.parent.mkdir(parents=True, exist_ok=True)
        eval_cases_file.write_text(json.dumps(cases_export, indent=2), encoding="utf-8")

        return {
            "case_id": case_id,
            "total_distilled_cases": len(cases_export),
            "export_file": str(eval_cases_file.relative_to(self.project_root)),
        }

    def get_agent_performance(self, agent: str) -> dict:
        """Get agent performance metrics."""
        conn = sqlite3.connect(self.feedback_db)
        cursor = conn.cursor()
        cursor.execute("""
            SELECT AVG(accuracy_score), COUNT(*) FROM feedback
            WHERE agent_name = ?
        """, (agent,))
        result = cursor.fetchone()
        conn.close()

        return {
            "agent": agent,
            "avg_accuracy": round(result[0] or 0.0, 3),
            "total_actions": result[1] or 0,
        }

    def generate_retraining_plan(self) -> dict:
        """Generate retraining recommendations."""
        agents = ["agent-1", "agent-2", "agent-3", "agent-4", "chaos", "finops", "compliance", "sre", "docs"]
        plan = []

        for agent in agents:
            perf = self.get_agent_performance(agent)
            if perf["total_actions"] > 0 and perf["avg_accuracy"] < 0.8:
                plan.append({
                    "agent": agent,
                    "action": "retrain_or_tune_harness",
                    "reason": f"Low accuracy: {perf['avg_accuracy']:.2f} ({perf['total_actions']} actions)",
                })

        return {
            "generated_at": datetime.now(UTC).isoformat(),
            "retraining_needed": len(plan),
            "plan": plan,
        }


def main():
    parser = argparse.ArgumentParser(description="x0tta6bl4 Agentic Harness Feedback & Dual Loop System")
    parser.add_argument("--ingest", type=str, help="Ingest summary.json file from run_agent_cycle.py")
    parser.add_argument("--eval-experiment", type=str, help="Run Loop A experiment evaluation (pass experiment name)")
    parser.add_argument("--candidate", type=str, help="Candidate summary.json path for --eval-experiment")
    parser.add_argument("--baseline", type=str, help="Baseline summary.json path for --eval-experiment")
    parser.add_argument("--distill-id", type=str, help="Loop B: Distill edge case ID")
    parser.add_argument("--distill-task", type=str, help="Loop B: Task description")
    parser.add_argument("--distill-reason", type=str, help="Loop B: Failure reason")
    parser.add_argument("--distill-expected", type=str, help="Loop B: Expected behavior")
    parser.add_argument("--report", action="store_true", help="Print Evals & Heatmap report")

    args = parser.parse_args()
    loop = AgentFeedbackLoop()

    if args.ingest:
        res = loop.ingest_cycle_summary(args.ingest)
        print(f"✅ Ingested cycle summary: {res}")
        return

    if args.eval_experiment:
        if not args.candidate:
            print("❌ --candidate is required for --eval-experiment")
            return
        res = loop.evaluate_experiment(args.eval_experiment, args.candidate, args.baseline)
        print(f"🔬 Experiment Evaluation Verdict: {json.dumps(res, indent=2)}")
        return

    if args.distill_id:
        if not (args.distill_task and args.distill_reason and args.distill_expected):
            print("❌ --distill-task, --distill-reason, and --distill-expected are required")
            return
        res = loop.distill_edge_case(
            case_id=args.distill_id,
            task_description=args.distill_task,
            failure_reason=args.distill_reason,
            expected_behavior=args.distill_expected,
        )
        print(f"📦 Distilled edge case: {json.dumps(res, indent=2)}")
        return

    if args.report:
        heatmap = loop.generate_error_heatmap()
        plan = loop.generate_retraining_plan()
        print("=== 📊 Agentic Harness Evals & Error Heatmap ===")
        print(json.dumps({"heatmap": heatmap, "retraining_plan": plan}, indent=2))
        return

    # Default demo run if no args
    heatmap = loop.generate_error_heatmap()
    plan = loop.generate_retraining_plan()
    print(json.dumps({"heatmap": heatmap, "retraining_plan": plan}, indent=2))


if __name__ == "__main__":
    main()

