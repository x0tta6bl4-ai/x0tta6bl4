#!/usr/bin/env python3
"""Agent Feedback Loop - Continuous learning system."""

import json
import sqlite3
from datetime import datetime, UTC
from pathlib import Path


class AgentFeedbackLoop:
    """Collect feedback and retrain agents."""
    
    def __init__(self):
        self.project_root = Path("/mnt/projects")
        self.feedback_db = self.project_root / ".tmp/agent_feedback.db"
        self._init_db()
    
    def _init_db(self):
        conn = sqlite3.connect(self.feedback_db)
        cursor = conn.cursor()
        cursor.execute("""
            CREATE TABLE IF NOT EXISTS feedback (
                id INTEGER PRIMARY KEY,
                agent_name TEXT,
                action_type TEXT,
                result TEXT,
                accuracy_score REAL,
                created_at TIMESTAMP
            )
        """)
        conn.commit()
        conn.close()
    
    def record_feedback(self, agent: str, action: str, result: str, score: float):
        """Record agent action feedback."""
        conn = sqlite3.connect(self.feedback_db)
        cursor = conn.cursor()
        cursor.execute("""
            INSERT INTO feedback (agent_name, action_type, result, accuracy_score, created_at)
            VALUES (?, ?, ?, ?, ?)
        """, (agent, action, result, score, datetime.now(UTC).isoformat()))
        conn.commit()
        conn.close()
    
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
            "avg_accuracy": result[0] or 0.0,
            "total_actions": result[1] or 0
        }
    
    def generate_retraining_plan(self) -> dict:
        """Generate retraining recommendations."""
        agents = ["chaos", "finops", "compliance", "sre", "docs"]
        plan = []
        
        for agent in agents:
            perf = self.get_agent_performance(agent)
            if perf["avg_accuracy"] < 0.8 and perf["total_actions"] > 10:
                plan.append({
                    "agent": agent,
                    "action": "retrain",
                    "reason": f"Low accuracy: {perf['avg_accuracy']:.2f}"
                })
        
        return {
            "generated_at": datetime.now(UTC).isoformat(),
            "retraining_needed": len(plan),
            "plan": plan
        }


def main():
    loop = AgentFeedbackLoop()
    
    # Simulate recording feedback
    loop.record_feedback("chaos", "experiment", "success", 0.95)
    loop.record_feedback("finops", "cost_check", "accurate", 0.88)
    loop.record_feedback("compliance", "control_check", "pass", 1.0)
    
    # Generate plan
    plan = loop.generate_retraining_plan()
    print(json.dumps(plan, indent=2))


if __name__ == "__main__":
    main()
